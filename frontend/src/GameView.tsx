import { useEffect, useMemo, useState } from "react";
import { api, type JournalEntry, type Relationship, type TurnResult } from "./api";

interface GameViewProps {
  sessionId: string;
  activeMenu: string;
  onWorldlineChange: (value: number) => void;
}

const NPC_NAMES: Record<string, string> = {
  harry_potter: "哈利·波特",
  ron_weasley: "罗恩·韦斯莱",
  hermione_granger: "赫敏·格兰杰",
  draco_malfoy: "德拉科·马尔福",
  ginny_weasley: "金妮·韦斯莱",
  neville_longbottom: "纳威·隆巴顿",
  albus_dumbledore: "阿不思·邓布利多",
  minerva_mcgonagall: "米勒娃·麦格",
  severus_snape: "西弗勒斯·斯内普",
};

export function GameView({
  sessionId,
  activeMenu,
  onWorldlineChange,
}: GameViewProps) {
  const [state, setState] = useState<Record<string, any> | null>(null);
  const [stateVersion, setStateVersion] = useState(0);
  const [journal, setJournal] = useState<JournalEntry[]>([]);
  const [relationships, setRelationships] = useState<Relationship[]>([]);
  const [turn, setTurn] = useState<TurnResult | null>(null);
  const [freeText, setFreeText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function refreshState() {
    const [stateResponse, journalResponse, relationshipResponse, turnsResponse] = await Promise.all([
      api.state(sessionId),
      api.journal(sessionId),
      api.relationships(sessionId),
      api.turns(sessionId),
    ]);
    setState(stateResponse.state);
    setStateVersion(stateResponse.state_version);
    setJournal(journalResponse);
    setRelationships(relationshipResponse);
    const latestTurn = turnsResponse[turnsResponse.length - 1];
    if (latestTurn) {
      setTurn({
        turn_id: latestTurn.id,
        sequence: latestTurn.sequence,
        state_version: latestTurn.state_version_after,
        recalled_memory_ids: [],
        response: latestTurn.response,
      });
    } else {
      setTurn(null);
    }
    onWorldlineChange(stateResponse.state.worldline?.offset_rate ?? 0);
  }

  useEffect(() => {
    void refreshState().catch((reason: unknown) => {
      setError(reason instanceof Error ? reason.message : "无法读取游戏状态");
    });
  }, [sessionId]);

  async function submitAction(
    kind: "choice" | "free_text",
    choiceId?: string,
    text?: string,
  ) {
    setLoading(true);
    setError("");
    try {
      const nextTurn = await api.action(sessionId, {
        client_action_id: crypto.randomUUID(),
        expected_state_version: stateVersion,
        kind,
        choice_id: choiceId,
        free_text: text,
      });
      setTurn(nextTurn);
      await refreshState();
      setFreeText("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "剧情推进失败");
    } finally {
      setLoading(false);
    }
  }

  const hasStarted = journal.length > 0 || turn !== null;
  const player = state ?? {};
  const identity = player.identity ?? {};
  const vitals = player.vitals ?? {};
  const context = player.current_context ?? {};
  const worldline = player.worldline ?? {};

  const relationshipRows = useMemo(
    () =>
      relationships.filter((item) => item.source_id === "player").map((item) => ({
        ...item,
        name: NPC_NAMES[item.target_id] ?? item.target_id,
      })),
    [relationships],
  );

  if (!state) {
    return <div className="empty-panel"><span className="empty-icon">✧</span><p>正在读取人生状态…</p></div>;
  }

  if (activeMenu !== "剧情") {
    return (
      <div className="query-panel">
        {error && <div className="error-banner">{error}</div>}
        {activeMenu === "角色" && (
          <>
            <div className="status-grid">
              <Stat label="姓名" value={identity.name ?? "未命名巫师"} />
              <Stat label="年龄" value={`${identity.age ?? "—"} 岁`} />
              <Stat label="年级" value={`${player.school?.year_level ?? 1} 年级`} />
              <Stat label="地点" value={context.location_id ?? "未知"} />
              <Stat label="HP" value={`${vitals.hp ?? 0}/${vitals.max_hp ?? 100}`} />
              <Stat label="MP" value={`${vitals.mp ?? 0}/${vitals.max_mp ?? 100}`} />
              <Stat label="SP" value={`${vitals.sp ?? 0}/${vitals.max_sp ?? 100}`} />
              <Stat label="精力" value={`${vitals.energy ?? 0}/100`} />
            </div>
            <DataSection title="基础设定" data={player.family} />
            <DataSection title="性格与价值观" data={{ ...player.personality, ...player.values }} />
            <DataSection title="技能" data={player.skills} />
            <DataSection title="物品与宠物" data={{ inventory: player.inventory, pet: player.pet }} />
          </>
        )}
        {activeMenu === "纪事" && (
          <div className="journal-list">
            {journal.length === 0 ? <EmptyText text="故事还没有留下纪事。" /> : journal.map((entry) => (
              <article className="journal-entry" key={entry.id}>
                <span className="journal-sequence">{entry.data.sequence ?? "·"}</span>
                <div><h3>{entry.title}</h3><p>{entry.summary}</p></div>
              </article>
            ))}
          </div>
        )}
        {(activeMenu === "好感" || activeMenu === "恋爱" || activeMenu === "关系") && (
          <div className="relationship-list">
            {relationshipRows.map((item) => (
              <article className="relationship-row" key={item.target_id}>
                <div><strong>{item.name}</strong><small>{item.state.stage ?? "陌生人"}</small></div>
                <span>好感 {item.state.affinity ?? 0} · 信任 {item.state.trust ?? 0}</span>
              </article>
            ))}
          </div>
        )}
        {activeMenu === "世界线" && (
          <div className="worldline-panel">
            <div className="worldline-large">{Number(worldline.offset_rate ?? 0).toFixed(1)}%</div>
            <p>{worldline.reason ?? "尚未发生世界线偏移。"}</p>
            <DataSection title="受影响节点" data={worldline.affected_nodes ?? []} />
          </div>
        )}
        {["声望", "课程", "信件"].includes(activeMenu) && (
          <DataSection title={activeMenu} data={player[activeMenu === "声望" ? "reputation" : activeMenu === "课程" ? "school" : "letters"] ?? {}} />
        )}
      </div>
    );
  }

  return (
    <div className="game-panel">
      {error && <div className="error-banner">{error}</div>}
      <div className="game-meta">
        <span>{context.datetime ?? "1991-07-01 09:00"}</span>
        <span>{context.location_id ?? "未知地点"}</span>
        <span>世界线 {Number(worldline.offset_rate ?? 0).toFixed(1)}%</span>
      </div>
      {!hasStarted ? (
        <div className="first-scene">
          <span className="empty-icon">✧</span>
          <h3>猫头鹰还没有抵达</h3>
          <p>你的故事已经准备好。开始第一幕，看看命运会把信送到哪里。</p>
          <button className="primary-button" disabled={loading} onClick={() => void submitAction("choice", "start_story")}>
            {loading ? "主持人准备中…" : "开始第一幕"}
          </button>
        </div>
      ) : (
        <>
          <article className="narrative-card">
            <p className="eyebrow">{turn?.response.turn.scene_type ?? "STORY"}</p>
            <h3>{turn?.response.turn.title ?? "最近的故事"}</h3>
            <p className="narrative-text">
              {turn?.response.turn.narrative ?? journal[0]?.summary ?? "选择一个方向，继续你的故事。"}
            </p>
            {turn?.response.memory_update.summary && (
              <p className="memory-note">纪事：{turn.response.memory_update.summary}</p>
            )}
          </article>
          <div className="choices">
            {(turn?.response.choices ?? []).map((choice) => (
              choice.kind === "free_text" ? (
                <div className="free-text-choice" key={choice.id}>
                  <input
                    value={freeText}
                    onChange={(event) => setFreeText(event.target.value)}
                    placeholder="输入你想做的其他事情…"
                    onKeyDown={(event) => {
                      if (event.key === "Enter" && freeText.trim()) {
                        void submitAction("free_text", choice.id, freeText.trim());
                      }
                    }}
                  />
                  <button className="secondary-button" disabled={loading || !freeText.trim()} onClick={() => void submitAction("free_text", choice.id, freeText.trim())}>
                    发送
                  </button>
                </div>
              ) : (
                <button className="choice-button" key={choice.id} disabled={loading} onClick={() => void submitAction("choice", choice.id)}>
                  <span>{choice.label}</span><small>{choice.risk !== "unknown" ? `风险：${choice.risk}` : ""}</small>
                </button>
              )
            ))}
            {!turn && <EmptyText text="上一段故事已保存。开始下一幕以继续。" />}
          </div>
        </>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return <div className="stat"><span>{label}</span><strong>{value}</strong></div>;
}

function DataSection({ title, data }: { title: string; data: unknown }) {
  return (
    <section className="data-section">
      <h3>{title}</h3>
      <pre>{JSON.stringify(data, null, 2)}</pre>
    </section>
  );
}

function EmptyText({ text }: { text: string }) {
  return <p className="empty-text">{text}</p>;
}
