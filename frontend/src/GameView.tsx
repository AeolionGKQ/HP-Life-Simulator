import { useEffect, useMemo, useState } from "react";
import {
  api,
  type JournalEntry,
  type NPCState,
  type PlayerChanges,
  type Relationship,
  type TurnResult,
} from "./api";

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
  luna_lovegood: "卢娜·洛夫古德",
  fred_weasley: "弗雷德·韦斯莱",
  george_weasley: "乔治·韦斯莱",
  cedric_diggory: "塞德里克·迪戈里",
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
  const [npcs, setNpcs] = useState<NPCState[]>([]);
  const [turn, setTurn] = useState<TurnResult | null>(null);
  const [freeText, setFreeText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function refreshState() {
    const [stateResponse, journalResponse, relationshipResponse, npcResponse, turnsResponse] = await Promise.all([
      api.state(sessionId),
      api.journal(sessionId),
      api.relationships(sessionId),
      api.npcs(sessionId),
      api.turns(sessionId),
    ]);
    setState(stateResponse.state);
    setStateVersion(stateResponse.state_version);
    setJournal(journalResponse);
    setRelationships(relationshipResponse);
    setNpcs(npcResponse);
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

  const npcNames = useMemo(
    () => Object.fromEntries(
      npcs.map((npc) => [
        npc.npc_id,
        String(npc.state.name || NPC_NAMES[npc.npc_id] || "未留名的巫师"),
      ]),
    ),
    [npcs],
  );

  const relationshipRows = useMemo(
    () =>
      relationships.filter((item) => item.source_id === "player").map((item) => ({
        ...item,
        name: npcNames[item.target_id] ?? NPC_NAMES[item.target_id] ?? "未留名的巫师",
      })),
    [relationships, npcNames],
  );

  const romanceRows = relationshipRows.filter((item) => isRomanticRelationship(item.state));

  if (!state) {
    return <div className="empty-panel"><span className="empty-icon">✧</span><p>正在读取人生状态…</p></div>;
  }

  if (loading) {
    return (
      <div className="magic-loading">
        <div className="magic-orbit"><span>✦</span><span>✧</span><span>✦</span></div>
        <h3>羽毛笔正在书写命运</h3>
        <p>魔法回响穿过时间与空间，命运正在为你编织下一幕……</p>
      </div>
    );
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
              <Stat label="地点" value={translateValue(context.location_id ?? "unknown")} />
              <Stat label="HP" value={`${vitals.hp ?? 0}/${vitals.max_hp ?? 100}`} />
              <Stat label="MP" value={`${vitals.mp ?? 0}/${vitals.max_mp ?? 100}`} />
              <Stat label="SP" value={`${vitals.sp ?? 0}/${vitals.max_sp ?? 100}`} />
              <Stat label="精力" value={`${vitals.energy ?? 0}/100`} />
            </div>
            <ReadableSection title="家族与出身" data={player.family} emptyText="墨迹尚未揭示更多家族往事。" />
            <ReadableSection title="性格与价值观" data={{ ...player.personality, ...player.values }} />
            <ReadableSection title="魔法天赋" data={player.magic_talents ?? []} emptyText="尚未显露特殊的魔法天赋。" />
            <ReadableSection title="技能与熟练度" data={player.skills} emptyText="技能页还是一张等待书写的羊皮纸。" />
            <ReadableSection title="当前状态" data={player.statuses ?? []} emptyText="此刻身心平稳，没有特殊状态。" />
            <TraitSection traits={player.traits ?? []} />
            <ReadableSection title="随身物品与宠物" data={{ inventory: player.inventory, pet: player.pet }} emptyText="口袋与行囊暂时空空如也。" />
          </>
        )}
        {activeMenu === "纪事" && (
          <div className="journal-list">
            {journal.length === 0 ? <EmptyText text="羊皮卷上尚无墨迹，第一段值得铭记的往事仍在前方。" /> : journal.map((entry) => (
              <article className="journal-entry" key={entry.id}>
                <span className="journal-sequence">{entry.data.sequence ?? "·"}</span>
                <div><h3>{entry.title}</h3><p>{entry.summary}</p></div>
              </article>
            ))}
          </div>
        )}
        {activeMenu === "关系与好感" && (
          <div className="relationship-list">
            {relationshipRows.length === 0 ? <EmptyText text="你还没有与任何人建立足以记录的羁绊。" /> : relationshipRows.map((item) => (
              <article className="relationship-row" key={item.target_id}>
                <div><strong>{item.name}</strong><small>{translateValue(item.state.stage ?? "stranger")}</small></div>
                <span>好感 {item.state.affinity ?? 0} · 信任 {item.state.trust ?? 0}</span>
              </article>
            ))}
          </div>
        )}
        {activeMenu === "恋爱" && (
          <div className="relationship-list romance-list">
            {romanceRows.length === 0 ? <EmptyText text="心形墨水尚未为任何名字显色。真正的悸动，也许会在未来某个走廊转角出现。" /> : romanceRows.map((item) => (
              <article className="relationship-row romance-row" key={item.target_id}>
                <div><strong>{item.name}</strong><small>{translateValue(item.state.stage ?? item.state.romance_state)}</small></div>
                <span>好感 {item.state.affinity ?? 0} · 信任 {item.state.trust ?? 0}</span>
              </article>
            ))}
          </div>
        )}
        {activeMenu === "世界线" && (
          <div className="worldline-panel">
            <div className="worldline-large">{Number(worldline.offset_rate ?? 0).toFixed(1)}%</div>
            <p>{worldline.reason ?? "历史的星轨仍循着原本的方向安静运行。"}</p>
            <ReadableSection title="受到波动的命运节点" data={worldline.affected_nodes ?? []} emptyText="暂时没有原著节点受到波及。" />
          </div>
        )}
        {["声望", "课程", "信件"].includes(activeMenu) && (
          <ReadableSection
            title={activeMenu === "声望" ? "魔法社会中的名声" : activeMenu === "课程" ? "霍格沃茨课业" : "猫头鹰邮递"}
            data={player[activeMenu === "声望" ? "reputation" : activeMenu === "课程" ? "school" : "letters"] ?? {}}
            emptyText={activeMenu === "信件" ? "猫头鹰棚里暂时没有寄给你的新信。" : "这页羊皮纸暂时没有可显示的记录。"}
          />
        )}
      </div>
    );
  }

  return (
    <div className="game-panel">
      {error && <div className="error-banner">{error}</div>}
      <div className="game-meta">
        <span>{context.datetime ?? "1991-07-01 09:00"}</span>
        <span>{translateValue(context.location_id ?? "unknown")}</span>
        <span>世界线 {Number(worldline.offset_rate ?? 0).toFixed(1)}%</span>
      </div>
      {!hasStarted ? (
        <div className="first-scene">
          <span className="empty-icon">✧</span>
          <h3>城堡的烛火正在远方亮起</h3>
          <p>闭上眼，听蒸汽列车穿过薄雾。属于你的魔法世界，只差最后一步便会显现。</p>
          <button className="primary-button" disabled={loading} onClick={() => void submitAction("choice", "start_story")}>
            {loading ? "星光正在聚拢…" : "踏入魔法世界"}
          </button>
        </div>
      ) : (
        <>
          <article className="narrative-card">
            <p className="eyebrow">{translateSceneType(turn?.response.turn.scene_type)}</p>
            <h3>{turn?.response.turn.title ?? "最近的故事"}</h3>
            <p className="narrative-text">
              {turn?.response.turn.narrative ?? journal[0]?.summary ?? "羽毛笔悬停在羊皮纸上，等待你写下下一步行动。"}
            </p>
            {turn && <ChangeNotice changes={turn.response.applied_changes} />}
          </article>
          <div className="choices">
            {(turn?.response.choices ?? []).map((choice) => (
              choice.kind === "free_text" ? (
                <div className="free-text-choice" key={choice.id}>
                  <input
                    value={freeText}
                    onChange={(event) => setFreeText(event.target.value)}
                    placeholder="写下一个不在预言之中的行动…"
                    onKeyDown={(event) => {
                      if (event.key === "Enter" && freeText.trim()) {
                        void submitAction("free_text", choice.id, freeText.trim());
                      }
                    }}
                  />
                  <button className="secondary-button" disabled={loading || !freeText.trim()} onClick={() => void submitAction("free_text", choice.id, freeText.trim())}>
                    让羽毛笔记录
                  </button>
                </div>
              ) : (
                <button className="choice-button" key={choice.id} disabled={loading} onClick={() => void submitAction("choice", choice.id)}>
                  <span className="choice-main">
                    <strong>{choice.label}</strong>
                    <ChoiceEffects effects={choice.effects} />
                  </span>
                  <small>{choice.risk !== "unknown" ? `风险：${choice.risk}` : ""}</small>
                </button>
              )
            ))}
            {!turn && <EmptyText text="上一页羊皮纸已经封存，新的墨迹正等待你的选择。" />}
          </div>
        </>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return <div className="stat"><span>{label}</span><strong>{value}</strong></div>;
}

const FIELD_LABELS: Record<string, string> = {
  bloodline: "血统与出身",
  description: "说明",
  traits: "性格特征",
  primary: "核心性格",
  level: "熟练度",
  experience: "经验",
  source: "来源",
  inventory: "随身物品",
  pet: "宠物伙伴",
  name: "名称",
  quantity: "数量",
  item_id: "物品编号",
  id: "记录编号",
  severity: "程度",
  duration_minutes: "持续时间",
  school_year: "学年",
  year_level: "年级",
  house: "学院",
  status: "状态",
  stage: "关系阶段",
  affinity: "好感",
  trust: "信任",
  romance_state: "恋爱状态",
  known_secrets: "已知秘密",
  pending_stage_unlocks: "待解锁阶段",
  galleons: "加隆",
  sickles: "西可",
  knuts: "纳特",
  courage: "勇气",
  wisdom: "智慧",
  loyalty: "忠诚",
  ambition: "野心",
  academic: "学术声望",
  social: "社交声望",
  combat: "战斗声望",
  morality: "道德声望",
  leadership: "领导声望",
  dark_magic: "黑魔法声望",
};

const VALUE_LABELS: Record<string, string> = {
  stranger: "陌生",
  acquaintance: "相识",
  friend: "朋友",
  close_friend: "挚友",
  dating: "恋爱",
  romance: "恋爱",
  lover: "恋人",
  committed: "稳定恋情",
  adult_stage: "成年亲密关系",
  marriage: "婚姻",
  married: "已婚",
  unavailable: "尚未开启",
  single: "单身",
  normal: "正常",
  positive: "正面",
  negative: "负面",
  morning: "清晨",
  afternoon: "午后",
  evening: "傍晚",
  night: "夜晚",
  home: "家中",
  diagon_alley: "对角巷",
  platform_nine_three_quarters: "九又四分之三站台",
  hogwarts_great_hall: "霍格沃茨礼堂",
  hogwarts: "霍格沃茨",
  unknown: "未知地点",
  before_first_letter: "等待霍格沃茨来信",
  sorting_ceremony: "分院仪式",
  ready_for_first_scene: "等待命运启程",
  true: "是",
  false: "否",
};

function ReadableSection({
  title,
  data,
  emptyText = "这页羊皮纸暂时没有留下墨迹。",
}: {
  title: string;
  data: unknown;
  emptyText?: string;
}) {
  return (
    <section className="data-section">
      <h3>{title}</h3>
      {isEmptyData(data) ? <EmptyText text={emptyText} /> : <ReadableValue value={data} />}
    </section>
  );
}

function ReadableValue({ value, fieldName }: { value: unknown; fieldName?: string }) {
  if (value === null || value === undefined || value === "") {
    return <span className="readable-empty">尚未记录</span>;
  }
  if (Array.isArray(value)) {
    return (
      <div className="readable-list">
        {value.map((item, index) => (
          <div className="readable-list-item" key={`${fieldName ?? "item"}-${index}`}>
            <ReadableValue value={item} />
          </div>
        ))}
      </div>
    );
  }
  if (typeof value === "object") {
    return (
      <div className="readable-grid">
        {Object.entries(value as Record<string, unknown>)
          .filter(([key, item]) => !isHiddenField(key, item))
          .map(([key, item]) => (
            <div className="readable-row" key={key}>
              <span>{translateField(key)}</span>
              <div><ReadableValue value={item} fieldName={key} /></div>
            </div>
          ))}
      </div>
    );
  }
  return <span className="readable-value">{translateValue(value)}</span>;
}

function isEmptyData(data: unknown): boolean {
  if (data === null || data === undefined || data === "") return true;
  if (Array.isArray(data)) return data.length === 0;
  if (typeof data === "object") return Object.keys(data as object).length === 0;
  return false;
}

function isHiddenField(key: string, value: unknown): boolean {
  return (
    key === "recent_interaction_ids" ||
    (key === "id" && typeof value === "string" && value.includes("_"))
  );
}

function translateField(key: string): string {
  if (FIELD_LABELS[key]) return FIELD_LABELS[key];
  if (NPC_NAMES[key]) return NPC_NAMES[key];
  return key
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function translateValue(value: unknown): string {
  if (typeof value === "boolean") return value ? "是" : "否";
  const text = String(value);
  return VALUE_LABELS[text] ?? NPC_NAMES[text] ?? text;
}

function translateSceneType(value: unknown): string {
  const labels: Record<string, string> = {
    dialogue: "对话场景",
    encounter: "命运邂逅",
    combat: "魔法冲突",
    class: "课堂时光",
    exploration: "城堡探索",
    letter: "猫头鹰来信",
    ending: "命运终章",
  };
  return labels[String(value ?? "")] ?? "故事片段";
}

function isRomanticRelationship(state: Record<string, any>): boolean {
  const romanticStages = new Set([
    "dating",
    "romance",
    "lover",
    "committed",
    "adult_stage",
    "marriage",
    "married",
  ]);
  return romanticStages.has(String(state.stage ?? "")) ||
    romanticStages.has(String(state.romance_state ?? ""));
}

function EmptyText({ text }: { text: string }) {
  return <p className="empty-text">{text}</p>;
}

function TraitSection({ traits }: { traits: Array<Record<string, any>> }) {
  return (
    <section className="trait-section">
      <h3>词条</h3>
      {traits.length === 0 ? (
        <p className="empty-text">目前还没有特殊词条。</p>
      ) : (
        <div className="trait-list">
          {traits.map((trait) => (
            <article className={`trait-card ${trait.polarity === "negative" ? "negative" : "positive"}`} key={trait.id}>
              <div><strong>【{trait.name}】</strong><small>{trait.polarity === "negative" ? "负面词条" : "正面词条"}</small></div>
              <p>{trait.description}</p>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function ChoiceEffects({
  effects,
}: {
  effects: {
    gains: Array<{ name: string; description: string }>;
    losses: Array<{ name: string; description: string }>;
    note: string;
  };
}) {
  if (!effects || (!effects.gains.length && !effects.losses.length && !effects.note)) {
    return null;
  }
  return (
    <span className="choice-effects">
      {effects.gains.map((effect) => (
        <em className="effect-gain" key={`gain-${effect.name}`}>获得：{effect.name}{effect.description ? `（${effect.description}）` : ""}</em>
      ))}
      {effects.losses.map((effect) => (
        <em className="effect-loss" key={`loss-${effect.name}`}>失去：{effect.name}{effect.description ? `（${effect.description}）` : ""}</em>
      ))}
      {effects.note && <em className="effect-note">{effects.note}</em>}
    </span>
  );
}

function ChangeNotice({ changes }: { changes: PlayerChanges }) {
  if (!changes || !hasChanges(changes)) return null;
  return (
    <div className="change-notice">
      <strong>本回合状态变化</strong>
      <div className="change-columns">
        <ChangeList title="获得" items={[
          ...changes.inventory_add.map((item) => `物品：${item.name ?? item.item_id}`),
          ...changes.status_add.map((item) => `状态：${item.name ?? item.id}`),
          ...changes.skill_add.map((item) => `技能：${item.name ?? item.id}`),
          ...changes.trait_add.map((item) => `词条：${item.name}`),
        ]} />
        <ChangeList title="失去" items={[
          ...changes.inventory_remove.map((item) => `物品：${item}`),
          ...changes.status_remove.map((item) => `状态：${item}`),
          ...changes.skill_remove.map((item) => `技能：${item}`),
          ...changes.trait_remove.map((item) => `词条：${item}`),
        ]} />
        <ChangeList title="变化" items={[
          ...Object.entries(changes.skill_deltas).map(([key, value]) => `技能 ${key}：${value > 0 ? "+" : ""}${value}`),
          ...Object.entries(changes.vital_deltas).map(([key, value]) => `${key}：${value > 0 ? "+" : ""}${value}`),
          ...Object.entries(changes.attribute_deltas).map(([key, value]) => `属性 ${key}：${value > 0 ? "+" : ""}${value}`),
        ]} />
      </div>
    </div>
  );
}

function ChangeList({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;
  return <div><span>{title}</span>{items.map((item) => <small key={item}>{item}</small>)}</div>;
}

function hasChanges(changes: PlayerChanges): boolean {
  return Boolean(
    changes.inventory_add.length ||
    changes.inventory_remove.length ||
    changes.status_add.length ||
    changes.status_remove.length ||
    changes.skill_add.length ||
    changes.skill_remove.length ||
    changes.trait_add.length ||
    changes.trait_remove.length ||
    Object.keys(changes.skill_deltas).length ||
    Object.keys(changes.vital_deltas).length ||
    Object.keys(changes.attribute_deltas).length,
  );
}
