import { useEffect, useMemo, useRef, useState } from "react";
import { BookOpenText, MagicWand, Sparkle } from "@phosphor-icons/react";
import {
  api,
  getPendingAction,
  type JournalEntry,
  type CourseView,
  type NPCState,
  type PlayerChanges,
  type StoredTurn,
  type Relationship,
  type StoryArc,
  type StoryArcStatus,
  type TurnResult,
} from "./api";
import { translateMemoryStatus, translateTimelineId } from "./temporalLabels";

interface GameViewProps {
  sessionId: string;
  activeMenu: string;
  eraId: string;
  timelineLabel: string;
  onWorldlineChange: (value: number) => void;
}

const NPC_NAMES: Record<string, string> = {
  albus_potter: "阿不思·西弗勒斯·波特",
  scorpius_malfoy: "斯科皮·马尔福",
  rose_granger_weasley: "罗丝·格兰杰-韦斯莱",
  polly_chapman: "波莉·查普曼",
  karl_jenkins: "卡尔·詹金斯",
  craig_bowker_junior: "克雷格·鲍克二世",
  delphini: "德尔菲",
  amos_diggory: "阿莫斯·迪戈里",
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
  eraId,
  timelineLabel,
  onWorldlineChange,
}: GameViewProps) {
  const [state, setState] = useState<Record<string, any> | null>(null);
  const [stateVersion, setStateVersion] = useState(0);
  const [journal, setJournal] = useState<JournalEntry[]>([]);
  const [relationships, setRelationships] = useState<Relationship[]>([]);
  const [npcs, setNpcs] = useState<NPCState[]>([]);
  const [courses, setCourses] = useState<CourseView | null>(null);
  const [selectedCourses, setSelectedCourses] = useState<string[]>([]);
  const [savingCourses, setSavingCourses] = useState(false);
  const [turn, setTurn] = useState<TurnResult | null>(null);
  const [turnHistory, setTurnHistory] = useState<StoredTurn[]>([]);
  const [viewedTurnIndex, setViewedTurnIndex] = useState(-1);
  const [freeText, setFreeText] = useState("");
  const [fateInterventionOpen, setFateInterventionOpen] = useState(false);
  const [fateInstruction, setFateInstruction] = useState("");
  const [fateIntervening, setFateIntervening] = useState(false);
  const [reshapeOpen, setReshapeOpen] = useState(false);
  const [reshapeInstruction, setReshapeInstruction] = useState("");
  const [reshaping, setReshaping] = useState(false);
  const [acknowledgingDeparture, setAcknowledgingDeparture] = useState(false);
  const [loading, setLoading] = useState(false);
  const [initializingAttributes, setInitializingAttributes] = useState(false);
  const [attributeRegenerateOpen, setAttributeRegenerateOpen] = useState(false);
  const [attributeAdjustment, setAttributeAdjustment] = useState("");
  const [regeneratingAttributes, setRegeneratingAttributes] = useState(false);
  const [error, setError] = useState("");
  const [storyArcs, setStoryArcs] = useState<StoryArc[]>([]);
  const [storyArcStatus, setStoryArcStatus] = useState<StoryArcStatus | null>(null);
  const [retryingStoryArc, setRetryingStoryArc] = useState(false);
  const [compressingStoryArcs, setCompressingStoryArcs] = useState(false);
  const [storyArcCompressError, setStoryArcCompressError] = useState("");
  const refreshRequestRef = useRef(0);

  async function refreshState() {
    const requestId = ++refreshRequestRef.current;
    const stateResponse = await api.state(sessionId);
    if (requestId !== refreshRequestRef.current) return;
    setState(stateResponse.state);
    setStateVersion(stateResponse.state_version);
    onWorldlineChange(
      eraId === "modern"
        ? stateResponse.state.worldline?.temporal_disturbance ?? 0
        : stateResponse.state.worldline?.offset_rate ?? 0,
    );
    if (eraId === "modern") {
      setCourses(null);
    }

    const courseRequest = eraId === "modern"
      ? Promise.resolve(null)
      : api.courses(sessionId);
    const results = await Promise.allSettled([
      api.journal(sessionId),
      api.relationships(sessionId),
      api.npcs(sessionId),
      api.turns(sessionId),
      courseRequest,
    ]);
    if (requestId !== refreshRequestRef.current) return;
    const [journalResult, relationshipResult, npcResult, turnsResult, coursesResult] = results;
    if (journalResult.status === "fulfilled") {
      setJournal(journalResult.value);
    }
    if (relationshipResult.status === "fulfilled") {
      setRelationships(relationshipResult.value);
    }
    if (npcResult.status === "fulfilled") {
      setNpcs(npcResult.value);
    }
    if (turnsResult.status === "fulfilled") {
      const turns = turnsResult.value;
      setTurnHistory(turns);
      setViewedTurnIndex(turns.length - 1);
      const latestTurn = turns[turns.length - 1];
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
    }
    if (coursesResult.status === "fulfilled" && coursesResult.value !== null) {
      setCourses(coursesResult.value);
    }
  }

  useEffect(() => {
    let active = true;
    const pendingAction = getPendingAction(sessionId);
    refreshRequestRef.current += 1;
    setFateInterventionOpen(false);
    setFateInstruction("");
    setFateIntervening(false);
    setReshapeOpen(false);
    setReshapeInstruction("");
    setReshaping(false);
    setLoading(Boolean(pendingAction));
    void refreshState().catch((reason: unknown) => {
      if (active) setError(reason instanceof Error ? reason.message : "无法读取游戏状态");
    });
    if (pendingAction) {
      void pendingAction.then(
        async () => {
          if (!active) return;
          try {
            await refreshState();
          } catch (reason: unknown) {
            if (active) setError(reason instanceof Error ? reason.message : "无法读取最新剧情");
          } finally {
            if (active) setLoading(false);
          }
        },
        (reason: unknown) => {
          if (active) {
            setError(reason instanceof Error ? reason.message : "剧情生成失败");
            setLoading(false);
          }
        },
      );
    }
    return () => {
      active = false;
    };
  }, [sessionId]);

  useEffect(() => {
    let active = true;
    let previousActiveJobId: string | null = null;
    let pollInFlight = false;
    setStoryArcStatus(null);
    setStoryArcs([]);
    setRetryingStoryArc(false);
    async function pollStoryArcStatus() {
      if (pollInFlight) return;
      pollInFlight = true;
      try {
        const [status, arcs] = await Promise.all([
          api.storyArcStatus(sessionId),
          api.storyArcs(sessionId),
        ]);
        if (!active) return;
        const nextJobId = status.active_job?.id ?? null;
        if (previousActiveJobId && !nextJobId) {
          if (!active) return;
          await refreshState();
          if (!active) return;
        }
        previousActiveJobId = nextJobId;
        setStoryArcStatus(status);
        setStoryArcs(arcs);
      } catch (reason: unknown) {
        if (active) {
          setError(reason instanceof Error ? reason.message : "无法读取故事弧状态");
        }
      } finally {
        pollInFlight = false;
      }
    }
    void pollStoryArcStatus();
    const timer = window.setInterval(() => void pollStoryArcStatus(), 2000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [sessionId]);

  async function submitAction(
    kind: "choice" | "free_text",
    choiceId?: string,
    text?: string,
  ) {
    if (
      (turnHistory.length > 0 && viewedTurnIndex !== turnHistory.length - 1)
      || loading
      || Boolean(getPendingAction(sessionId))
      || courses?.course_selection?.status === "pending"
      || state?.school?.departure_notice?.status === "pending"
      || storyArcBlocked
    ) return;
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

  async function submitFateIntervention() {
    const instruction = fateInstruction.trim();
    if (
      !instruction
      || instruction.length > 2000
      || !isViewingLatest
      || loading
      || Boolean(getPendingAction(sessionId))
      || courseSelectionPending
      || departureNoticePending
      || lifecycle.status === "dead"
      || storyArcBlocked
    ) return;
    setLoading(true);
    setFateIntervening(true);
    setError("");
    try {
      const nextTurn = await api.action(sessionId, {
        client_action_id: crypto.randomUUID(),
        expected_state_version: stateVersion,
        kind: "fate_intervention",
        fate_instruction: instruction,
      });
      setTurn(nextTurn);
      await refreshState();
      setFateInstruction("");
      setFateInterventionOpen(false);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "干涉命运失败");
    } finally {
      setFateIntervening(false);
      setLoading(false);
    }
  }

  async function submitReshapeFate() {
    const instruction = reshapeInstruction.trim();
    if (
      !instruction
      || instruction.length > 2000
      || !isViewingLatest
      || loading
      || courseSelectionPending
      || departureNoticePending
      || lifecycle.status === "dead"
      || turnHistory.length === 0
      || storyArcBlocked
    ) return;
    setLoading(true);
    setReshaping(true);
    setError("");
    try {
      const nextTurn = await api.action(sessionId, {
        client_action_id: crypto.randomUUID(),
        expected_state_version: stateVersion,
        kind: "reshape_fate",
        reshape_instruction: instruction,
      });
      setTurn(nextTurn);
      await refreshState();
      setReshapeInstruction("");
      setReshapeOpen(false);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "重塑命运失败");
    } finally {
      setReshaping(false);
      setLoading(false);
    }
  }

  async function compressAllStoryArcs() {
    setCompressingStoryArcs(true);
    setStoryArcCompressError("");
    let compressed = false;
    try {
      await api.compressStoryArcs(sessionId);
      compressed = true;
    } catch (reason) {
      const detail = reason instanceof Error ? reason.message.trim() : "";
      setStoryArcCompressError(detail || "故事弧压缩失败，请稍后重试");
    } finally {
      setCompressingStoryArcs(false);
    }
    if (!compressed) return;
    try {
      setStoryArcs(await api.storyArcs(sessionId));
    } catch {
      // 压缩已经提交成功，只是列表没刷新，不能报成压缩失败。
      setStoryArcCompressError("故事弧已压缩成功，但列表刷新失败，请重新打开本面板查看。");
    }
  }

  const player = state ?? {};
  const identity = player.identity ?? {};
  const context = player.current_context ?? {};
  const worldline = player.worldline ?? {};
  const resources = player.resources ?? {};
  const dimensions = player.dimensions ?? {};
  const lifecycle = player.lifecycle ?? {};
  const departureNotice = player.school?.departure_notice ?? {};
  const attributeInitialization = player.attribute_initialization ?? {};
  const latestTurnIndex = turnHistory.length - 1;
  const isViewingLatest = turnHistory.length === 0 || viewedTurnIndex === latestTurnIndex;
  const viewedTurn = turnHistory[viewedTurnIndex] ?? null;
  const visibleResponse = viewedTurn?.response ?? turn?.response ?? null;
  const displayContext = visibleResponse
    ? {
        ...context,
        current_date: visibleResponse.turn.current_date,
        location_id: visibleResponse.turn.location_id,
        location_name: visibleResponse.turn.location_name,
      }
    : context;
  const displayWorldline = eraId === "modern"
    ? worldline
    : visibleResponse?.worldline ?? worldline;
  const hasStarted = turnHistory.length > 0 || journal.length > 0 || turn !== null;
  const courseSelectionPending = courses?.course_selection?.status === "pending";
  const departureNoticePending = departureNotice.status === "pending";
  const storyArcBlocked = Boolean(storyArcStatus?.blocked);
  const currentNodeWasFateIntervention = viewedTurn?.action?.kind === "fate_intervention";
  const fateInterventionDisabled = (
    !isViewingLatest
    || loading
    || courseSelectionPending
    || departureNoticePending
    || lifecycle.status === "dead"
    || storyArcBlocked
  );
  const reshapeDisabled = (
    turnHistory.length === 0
    || !isViewingLatest
    || loading
    || courseSelectionPending
    || departureNoticePending
    || lifecycle.status === "dead"
    || storyArcBlocked
  );

  async function acknowledgeDepartureNotice() {
    if (!departureNoticePending || acknowledgingDeparture) return;
    setAcknowledgingDeparture(true);
    setError("");
    try {
      const response = await api.acknowledgeDepartureNotice(sessionId);
      setState(response.state);
      setStateVersion(response.state_version);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "开除通知确认失败");
    } finally {
      setAcknowledgingDeparture(false);
    }
  }

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

  function goToPreviousTurn() {
    setViewedTurnIndex((index) => Math.max(0, index - 1));
    setFreeText("");
  }

  function goToNextTurn() {
    setViewedTurnIndex((index) => Math.min(latestTurnIndex, index + 1));
    setFreeText("");
  }

  if (!state) {
    return <div className="empty-panel"><span className="empty-icon" aria-hidden="true"><BookOpenText /></span><p>正在读取人生状态…</p></div>;
  }

  if (activeMenu !== "剧情") {
    return (
      <div className="query-panel">
        <StoryArcNotice
          status={storyArcStatus}
          retrying={retryingStoryArc}
          onRetry={async () => {
            setRetryingStoryArc(true);
            try {
              await api.retryStoryArc(sessionId);
              const nextStatus = await api.storyArcStatus(sessionId);
              setStoryArcStatus(nextStatus);
            } catch (reason) {
              setError(reason instanceof Error ? reason.message : "故事弧重试失败");
            } finally {
              setRetryingStoryArc(false);
            }
          }}
        />
        {departureNoticePending && (
          <DepartureNoticePanel
            notice={departureNotice}
            acknowledging={acknowledgingDeparture}
            onAcknowledge={() => void acknowledgeDepartureNotice()}
          />
        )}
        {error && <div className="error-banner">{error}</div>}
        {activeMenu === "角色" && (
          <>
            <div className="status-grid">
              <Stat label="姓名" value={identity.name ?? "未命名巫师"} />
              <Stat label="性别" value={identity.gender ?? "未记录"} />
              <Stat label="生日" value={identity.birthday ?? "未记录"} />
              <Stat label="年龄" value={`${identity.age ?? "未记录"} 岁`} />
              <Stat label="年级" value={translateGrade(player.school?.grade)} />
              <Stat label="学院" value={translateValue(player.school?.house ?? "unknown")} />
              <Stat
                label="地点"
                value={context.location_name || translateValue(context.location_id ?? "unknown")}
              />
            </div>
            <ResourceSection resources={resources} />
            <DimensionSection dimensions={dimensions} />
            <ReadableSection title="家族与出身" data={player.family} emptyText="墨迹尚未揭示更多家族往事。" />
            <ReadableSection title="性格与价值观" data={{ ...player.personality, ...player.values }} />
            <ReadableSection title="守护神" data={player.patronus} emptyText="银白色的守护形态尚未显现。" />
            <ReadableSection title="角色补充" data={player.character_notes} emptyText="命运卷宗没有留下额外批注。" />
            <ReadableSection title="魔法天赋" data={player.magic_talents ?? []} emptyText="尚未显露特殊的魔法天赋。" />
            <ReadableSection title="技能与熟练度" data={player.skills} emptyText="技能页还是一张等待书写的羊皮纸。" />
            <ReadableSection title="当前状态" data={player.statuses ?? []} emptyText="此刻身心平稳，没有特殊状态。" />
            <TraitSection traits={player.traits ?? []} />
            <ReadableSection
              title="随身物品与宠物"
              data={{ inventory: displayInventory(player.inventory), pet: player.pet }}
              emptyText="口袋与行囊暂时空空如也。"
            />
          </>
        )}
        {activeMenu === "记忆管理" && (
          <StoryArcPanel
            arcs={storyArcs}
            compressing={compressingStoryArcs}
            compressError={storyArcCompressError}
            onCompress={() => void compressAllStoryArcs()}
          />
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
        {activeMenu === "羁绊" && (
          <div className="relationship-list">
            {relationshipRows.length === 0 ? <EmptyText text="你还没有与任何人建立足以记录的羁绊。" /> : relationshipRows.map((item) => (
              <article className="relationship-row" key={item.target_id}>
                <div>
                  <strong>{item.name}</strong>
                  <small>
                    {translateValue(item.state.stage ?? "stranger")}
                    {" · "}
                    {translateValue(item.state.bond_type ?? "potential")}
                  </small>
                </div>
                <span>好感 {item.state.affinity ?? 0}/100 · 信任 {item.state.trust ?? 0}/100</span>
                {getRomanceStage(item.state) !== "none" && getRomanceStage(item.state) !== "locked" && (
                  <small className="bond-detail">恋爱阶段：{translateValue(getRomanceStage(item.state))}</small>
                )}
                {item.state.last_change?.reason && (
                  <small className="bond-detail">最近变化：{item.state.last_change.reason}</small>
                )}
                {Array.isArray(item.state.pending_unlocks ?? item.state.pending_stage_unlocks)
                  && (item.state.pending_unlocks ?? item.state.pending_stage_unlocks).length > 0 && (
                  <small className="bond-detail">
                    有 {(item.state.pending_unlocks ?? item.state.pending_stage_unlocks).length} 个阶段等待条件解锁
                  </small>
                )}
              </article>
            ))}
          </div>
        )}
        {activeMenu === "恋爱" && (
          <div className="relationship-list romance-list">
            {romanceRows.length === 0 ? <EmptyText text="心形墨水尚未为任何名字显色。真正的悸动，也许会在未来某个走廊转角出现。" /> : romanceRows.map((item) => (
              <article className="relationship-row romance-row" key={item.target_id}>
                <div><strong>{item.name}</strong><small>{translateValue(getRomanceStage(item.state))}</small></div>
                <span>好感 {item.state.affinity ?? 0}/100 · 信任 {item.state.trust ?? 0}/100</span>
                <small className="bond-detail">普通关系：{translateValue(item.state.stage ?? "stranger")}</small>
              </article>
            ))}
          </div>
        )}
        {activeMenu === timelineLabel && (
          <div className="worldline-panel">
            <div className="worldline-large">{Number(
              eraId === "modern"
                ? worldline.temporal_disturbance ?? 0
                : worldline.offset_rate ?? 0,
            ).toFixed(1)}%</div>
            <p>{worldline.reason ?? (
              eraId === "modern"
                ? "时间结构仍沿着原始2020年稳定运行。"
                : "历史的星轨仍循着原本的方向安静运行。"
            )}</p>
            {eraId === "modern" && (
              <div className="worldline-modern-meta">
                <Stat label="时间稳定度" value={`${Number(worldline.temporal_stability ?? 100).toFixed(1)}%`} />
                <Stat
                  label="当前时间线"
                  value={translateTimelineId(worldline.current_timeline_id ?? "original_2020")}
                />
                <Stat
                  label="记忆状态"
                  value={translateMemoryStatus(worldline.memory_status ?? "original")}
                />
              </div>
            )}
            <ReadableSection
              title="受到波动的命运节点"
              data={worldline.affected_nodes ?? []}
              emptyText={eraId === "modern" ? "暂时没有时间节点受到影响。" : "暂时没有原著节点受到波及。"}
            />
          </div>
        )}
        {activeMenu === "课程" && courses && (
          <CoursePanel
            courses={courses}
            selectedCourses={selectedCourses}
            setSelectedCourses={setSelectedCourses}
            savingCourses={savingCourses}
            onSubmit={async () => {
              if (!courses.course_selection) return;
              setSavingCourses(true);
              setError("");
            try {
                const phase = courses.course_selection?.phase ?? courses.editable_phase;
                if (!phase) return;
                const nextCourses = await api.selectCourses(sessionId, {
                  expected_state_version: courses.state_version,
                  selection_phase: phase,
                  course_ids: selectedCourses,
                });
                setCourses(nextCourses);
                setSelectedCourses([]);
                await refreshState();
              } catch (reason) {
                setError(reason instanceof Error ? reason.message : "课程选择保存失败");
                if (reason instanceof Error && reason.message.includes("版本")) {
                  await refreshState().catch(() => undefined);
                }
              } finally {
                setSavingCourses(false);
              }
            }}
          />
        )}
        {activeMenu === "声望" && (
          <ReputationPanel value={player.reputation} />
        )}
      </div>
    );
  }

  if (attributeInitialization.status !== "ready") {
    async function retryAttributeInitialization() {
      setInitializingAttributes(true);
      setError("");
      try {
        await api.initializeAttributes(sessionId, "", true);
        await refreshState();
      } catch (reason) {
        setError(reason instanceof Error ? reason.message : "初始属性生成失败");
      } finally {
        setInitializingAttributes(false);
      }
    }

    return (
      <section className="game-panel" aria-label="剧情档案">
        {error && <div className="error-banner">{error}</div>}
        <div className="first-scene">
          <span className="empty-icon" aria-hidden="true"><Sparkle /></span>
          <h3>角色属性尚未校准完成</h3>
          <p>{attributeInitialization.error || "需要先根据角色设定生成完整的初始资源与长期维度。"}</p>
          <button
            className="primary-button"
            disabled={initializingAttributes}
            onClick={() => void retryAttributeInitialization()}
          >
            {initializingAttributes ? "正在重新校准…" : "重新生成初始属性"}
          </button>
        </div>
      </section>
    );
  }

  async function regenerateAttributes() {
    if (regeneratingAttributes || turnHistory.length > 0 || journal.length > 0) return;
    setRegeneratingAttributes(true);
    setError("");
    try {
      await api.initializeAttributes(sessionId, attributeAdjustment.trim(), true);
      await refreshState();
      setAttributeAdjustment("");
      setAttributeRegenerateOpen(false);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "初始属性重新生成失败");
    } finally {
      setRegeneratingAttributes(false);
    }
  }

  if (departureNoticePending) {
    return (
      <section className="game-panel" aria-label="退学通知">
        {error && <div className="error-banner">{error}</div>}
        <DepartureNoticePanel
          notice={departureNotice}
          acknowledging={acknowledgingDeparture}
          onAcknowledge={() => void acknowledgeDepartureNotice()}
        />
      </section>
    );
  }

  return (
    <section className="game-panel" aria-label="剧情档案">
      {error && <div className="error-banner">{error}</div>}
      <StoryArcNotice
        status={storyArcStatus}
        retrying={retryingStoryArc}
        onRetry={async () => {
          setRetryingStoryArc(true);
          try {
            await api.retryStoryArc(sessionId);
            setStoryArcStatus(await api.storyArcStatus(sessionId));
          } catch (reason) {
            setError(reason instanceof Error ? reason.message : "故事弧重试失败");
          } finally {
            setRetryingStoryArc(false);
          }
        }}
      />
      {lifecycle.status === "dead" ? (
        <div className="empty-panel ending-panel">
          <span className="empty-icon" aria-hidden="true"><BookOpenText /></span>
          <h3>这条世界线已经走到终点</h3>
          <p>生命值归零，角色故事已封存。你仍可以查看角色、纪事与已经留下的关系记录。</p>
        </div>
      ) : storyArcBlocked ? (
        <div className="magic-loading" role="status" aria-live="polite">
          <div className="magic-orbit" aria-hidden="true"><MagicWand /></div>
          <h3>正在整理故事弧</h3>
          <p>为了保持模型调用顺序，剧情选项、自由行动和命运功能会在整理完成后重新开放……</p>
        </div>
      ) : regeneratingAttributes ? (
        <div className="magic-loading" role="status" aria-live="polite">
          <div className="magic-orbit" aria-hidden="true"><MagicWand /></div>
          <h3>命运正在重新校准你的魔法回响</h3>
          <p>魔法世界正在根据你的调整重新测定初始属性，请稍候……</p>
        </div>
      ) : loading ? (
        <div className="magic-loading" role="status" aria-live="polite">
          <div className="magic-orbit" aria-hidden="true"><MagicWand /></div>
          <h3>
            {fateIntervening
              ? "命运的墨迹正在改道"
              : reshaping
                ? "命运正在重新书写"
                : "羽毛笔正在书写命运"}
          </h3>
          <p>
            {fateIntervening
              ? "羽毛笔正在为现实寻找一条通往你所指定未来的道路……"
              : reshaping
                ? "旧页的墨迹正在退回命运深处，重塑后的这一幕即将显现……"
                : "魔法回响穿过时间与空间，命运正在为你编织下一幕……"}
          </p>
        </div>
      ) : (
        <>
          <div className="game-meta">
            <span>日期：{displayContext.current_date ?? formatStoryDate(displayContext.datetime) ?? "1991-07-01"}</span>
            <span>
              地点：{displayContext.location_name || translateValue(displayContext.location_id ?? "unknown")}
            </span>
            <span>{timelineLabel} {Number(
              eraId === "modern"
                ? displayWorldline.temporal_disturbance ?? 0
                : displayWorldline.offset_rate ?? 0,
            ).toFixed(1)}%</span>
          </div>
          {!hasStarted ? (
            <div className="first-scene">
              <span className="empty-icon" aria-hidden="true"><Sparkle /></span>
              <h3>角色属性已经校准</h3>
              <p>{player.attribute_initialization?.calibration_summary || "你的初始资源与长期维度已经根据角色设定生成，并会在剧情中继续变化。"}</p>
              <ResourceSection resources={resources} />
              <DimensionSection dimensions={dimensions} />
              <div className="attribute-regenerate">
                <button
                  className="secondary-button"
                  disabled={regeneratingAttributes || loading || storyArcBlocked}
                  onClick={() => setAttributeRegenerateOpen((current) => !current)}
                >
                  {attributeRegenerateOpen ? "收起调整说明" : "重新生成属性"}
                </button>
                {attributeRegenerateOpen && (
                  <div className="attribute-regenerate-form">
                    <textarea
                      aria-label="属性调整说明"
                      value={attributeAdjustment}
                      onChange={(event) => setAttributeAdjustment(event.target.value)}
                      placeholder="可选：告诉模型希望如何调整，例如“体质和意志稍高，魔力保持普通，不要让属性过于极端”。"
                      maxLength={2000}
                    />
                    <button
                      className="primary-button"
                      disabled={regeneratingAttributes || loading}
                      onClick={() => void regenerateAttributes()}
                    >
                      {regeneratingAttributes ? "正在重新生成…" : "确认重新生成"}
                    </button>
                  </div>
                )}
              </div>
              <button className="primary-button" disabled={courseSelectionPending || regeneratingAttributes || loading || storyArcBlocked} onClick={() => void submitAction("choice", "start_story")}>
                踏入魔法世界
              </button>
            </div>
          ) : (
            <>
              <article className="narrative-card">
                <p className="eyebrow">{translateSceneType(visibleResponse?.turn.scene_type)}</p>
                {currentNodeWasFateIntervention && <span className="fate-badge">命运干涉</span>}
                <h3>{visibleResponse?.turn.title ?? "最近的故事"}</h3>
                <p className="narrative-text">
                  {visibleResponse?.turn.narrative ?? journal[0]?.summary ?? "羽毛笔悬停在羊皮纸上，等待你写下下一步行动。"}
                </p>
                {visibleResponse && (
                  <ChangeNotice
                    changes={visibleResponse.applied_changes}
                    npcNames={npcNames}
                  />
                )}
              </article>
              {!isViewingLatest && (
                <p className="story-browse-note" role="status">
                  正在浏览历史剧情节点，选项仅供查看。返回最新节点后才能继续行动。
                </p>
              )}
              <div className={isViewingLatest ? "choices" : "choices story-browsing"}>
                {(visibleResponse?.choices ?? []).map((choice) => (
                  choice.kind === "free_text" ? (
                    <div className="free-text-choice" key={choice.id}>
                      <input
                        disabled={!isViewingLatest || loading || courseSelectionPending || storyArcBlocked}
                        value={freeText}
                        onChange={(event) => setFreeText(event.target.value)}
                        placeholder="写下一个不在预言之中的行动…"
                        onKeyDown={(event) => {
                          if (event.key === "Enter" && freeText.trim()) {
                            void submitAction("free_text", choice.id, freeText.trim());
                          }
                        }}
                      />
                      <button className="secondary-button" disabled={!isViewingLatest || loading || courseSelectionPending || storyArcBlocked || !freeText.trim()} onClick={() => void submitAction("free_text", choice.id, freeText.trim())}>
                        让羽毛笔记录
                      </button>
                    </div>
                  ) : (
                    <button className="choice-button" disabled={!isViewingLatest || loading || courseSelectionPending || storyArcBlocked} key={choice.id} onClick={() => void submitAction("choice", choice.id)}>
                      <span className="choice-main">
                        <strong>{choice.label}</strong>
                        <ChoiceEffects effects={choice.effects} />
                      </span>
                      <small className={`choice-risk risk-${choice.risk}`}>
                        风险：{translateRisk(choice.risk)}
                      </small>
                    </button>
                  )
                ))}
                {!visibleResponse && <EmptyText text="上一页羊皮纸已经封存，新的墨迹正等待你的选择。" />}
              </div>
              <section className={`reshape-fate ${reshapeOpen ? "is-open" : ""}`} aria-label="重塑命运">
                {!reshapeOpen ? (
                  <button
                    className="reshape-fate-trigger"
                    disabled={reshapeDisabled}
                    onClick={() => setReshapeOpen(true)}
                  >
                    <span>
                      <strong>重塑命运</strong>
                      <small>重新生成：让羽毛笔重新写下你的故事</small>
                    </span>
                    <span aria-hidden="true">✦</span>
                  </button>
                ) : (
                  <div className="reshape-fate-form">
                    <div className="reshape-fate-heading">
                      <div>
                        <p className="eyebrow">命运修订 · 回溯一页</p>
                        <h3>你希望这一幕如何重写？</h3>
                      </div>
                      <span className="reshape-counter">{reshapeInstruction.length}/2000</span>
                    </div>
                    <p className="reshape-fate-help">
                      可以告诉羽毛笔你希望如何改变这一幕，也可以指出当前生成内容的问题。
                      已经发生的世界状态会先被还原，再只结算重写后的版本。
                    </p>
                    <textarea
                      aria-label="你希望这一幕如何重写"
                      maxLength={2000}
                      disabled={reshaping || reshapeDisabled}
                      value={reshapeInstruction}
                      onChange={(event) => setReshapeInstruction(event.target.value)}
                      placeholder="例如：保留无名书出现的事实，但让这次相遇更缓慢一些，先通过脚步声制造悬念。"
                    />
                    <div className="reshape-fate-actions">
                      <button
                        className="secondary-button"
                        disabled={reshaping}
                        onClick={() => setReshapeOpen(false)}
                      >
                        收起羽毛笔
                      </button>
                      <button
                        className="reshape-submit-button"
                        disabled={reshapeDisabled || !reshapeInstruction.trim()}
                        onClick={() => void submitReshapeFate()}
                      >
                        {reshaping ? "命运重写中…" : "重塑这一节点"}
                      </button>
                    </div>
                  </div>
                )}
              </section>
              {turnHistory.length > 0 && (
                <div className="story-navigation" aria-label="剧情节点浏览">
                  <button
                    className="secondary-button"
                    disabled={loading || viewedTurnIndex <= 0}
                    onClick={goToPreviousTurn}
                  >
                    上一节点
                  </button>
                  <span>
                    第 {Math.max(viewedTurnIndex + 1, 1)} / {turnHistory.length} 个剧情节点
                  </span>
                  <button
                    className="secondary-button"
                    disabled={loading || isViewingLatest}
                    onClick={goToNextTurn}
                  >
                    下一节点
                  </button>
                </div>
              )}
              <section className={`fate-intervention ${fateInterventionOpen ? "is-open" : ""}`} aria-label="干涉命运">
                {!fateInterventionOpen ? (
                  <button
                    className="fate-intervention-trigger"
                    disabled={fateInterventionDisabled}
                    onClick={() => setFateInterventionOpen(true)}
                  >
                    <span>
                      <strong>干涉命运</strong>
                      <small>作弊模式：直接指定下一个剧情节点想要发生的事情。</small>
                    </span>
                    <span aria-hidden="true">✦</span>
                  </button>
                ) : (
                  <div className="fate-intervention-form">
                    <div className="fate-intervention-heading">
                      <div>
                        <p className="eyebrow">作弊模式 · 命运改道</p>
                        <h3>你希望接下来发生什么？</h3>
                      </div>
                      <span className="fate-counter">{fateInstruction.length}/2000</span>
                    </div>
                    <p className="fate-intervention-help">
                      当前节点会在成功生成下一幕后结束。请描述你希望下一节点实际发生的核心事件，羽毛笔会负责补足自然过渡。
                    </p>
                    <textarea
                      aria-label="你希望接下来发生什么"
                      maxLength={2000}
                      disabled={fateIntervening || fateInterventionDisabled}
                      value={fateInstruction}
                      onChange={(event) => setFateInstruction(event.target.value)}
                      placeholder="例如：下一幕让我在禁书区发现一本记载着我家族秘密的无名书。"
                    />
                    <div className="fate-intervention-actions">
                      <button
                        className="secondary-button"
                        disabled={fateIntervening}
                        onClick={() => setFateInterventionOpen(false)}
                      >
                        取消
                      </button>
                      <button
                        className="fate-submit-button"
                        disabled={fateInterventionDisabled || !fateInstruction.trim()}
                        onClick={() => void submitFateIntervention()}
                      >
                        {fateIntervening ? "命运改道中…" : "干涉命运并结束当前节点"}
                      </button>
                    </div>
                  </div>
                )}
              </section>
            </>
          )}
        </>
      )}
    </section>
  );
}

function CoursePanel({
  courses,
  selectedCourses,
  setSelectedCourses,
  savingCourses,
  onSubmit,
}: {
  courses: CourseView;
  selectedCourses: string[];
  setSelectedCourses: (value: string[]) => void;
  savingCourses: boolean;
  onSubmit: () => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const selection = courses.course_selection;
  const selectionPending = selection?.status === "pending";
  const editorVisible = selectionPending || editing;
  const phase = selection?.phase ?? courses.editable_phase;
  const minCourses = selection?.min_courses ?? 0;
  const maxCourses = selection?.max_courses ?? 0;

  function toggleCourse(courseId: string) {
    if (!editorVisible) return;
    setSelectedCourses(
      selectedCourses.includes(courseId)
        ? selectedCourses.filter((id) => id !== courseId)
        : selectedCourses.length < maxCourses
          ? [...selectedCourses, courseId]
          : selectedCourses,
    );
  }

  return (
    <div className="course-panel">
      <div className="course-overview">
        <Stat label="当前年级" value={translateGrade(courses.grade)} />
        <Stat label="学年" value={courses.school_year || "尚未入学"} />
        <Stat label="学期" value={translateValue(courses.term)} />
      </div>
      {!selectionPending && courses.editable_phase && !editing && (
        <button
          className="secondary-button"
          onClick={() => {
            setSelectedCourses(
              courses.editable_phase === "elective"
                ? courses.elective_courses
                : courses.newt_courses,
            );
            setEditing(true);
          }}
        >
          修改高年级课表
        </button>
      )}
      {editorVisible && (
        <section className="course-selection-panel" aria-label="课程选择">
          <p className="eyebrow">课程选择 · {phase === "elective" ? "选修课程" : "N.E.W.T."}</p>
          <h3>请写下你的课表</h3>
          <p>
            请选择 {selectionPending ? `${minCourses} 至 ${maxCourses} 门课程。选课完成前，新的剧情节点会暂时锁定。` : "新的课程组合；已退课技能会保留，但不再获得六月自然成长。"}
          </p>
          <div className="course-option-list">
            {courses.selection_options.map((course) => (
              <button
                className={`course-option ${selectedCourses.includes(course.id) ? "selected" : ""}`}
                disabled={!course.available || savingCourses}
                key={course.id}
                onClick={() => toggleCourse(course.id)}
              >
                <span>
                  <strong>{course.name}</strong>
                  <small>{course.description}</small>
                </span>
                <em>{course.skill_level}/10</em>
              </button>
            ))}
          </div>
          <button
            className="primary-button"
            disabled={savingCourses || selectedCourses.length < (selectionPending ? minCourses : 1) || selectedCourses.length > (selectionPending ? maxCourses : 5)}
            onClick={() => void onSubmit().then(() => setEditing(false))}
          >
            {savingCourses ? "正在写入课表…" : selectionPending ? "确认课程选择" : "保存课表修改"}
          </button>
        </section>
      )}
      <section className="data-section">
        <h3>当前修读课程</h3>
        {courses.active_courses.length === 0 ? (
          <EmptyText text="尚未正式入学，课表仍等待分院与入学剧情。" />
        ) : (
          <div className="course-card-grid">
            {courses.active_courses.map((course) => (
              <article className="course-card" key={course.id}>
                <div>
                  <strong>{course.name}</strong>
                  <small>{course.description}</small>
                </div>
                <span>{course.skill_level}/10</span>
              </article>
            ))}
          </div>
        )}
      </section>
      <section className="data-section">
        <h3>课程技能</h3>
        {courses.skills.length === 0 ? (
          <EmptyText text="正式课程技能会在入学或选课后出现在这里。" />
        ) : (
          <div className="readable-list">
            {courses.skills.map((skill) => (
              <div className="readable-list-item course-skill-row" key={skill.id}>
                <span>{skill.name}</span>
                <strong>{skill.level}/10</strong>
              </div>
            ))}
          </div>
        )}
      </section>
      {(courses.owl_results.length > 0 || courses.newt_results.length > 0) && (
        <section className="data-section">
          <h3>考试成绩</h3>
          <div className="readable-list">
            {courses.owl_results.map((result) => (
              <div className="readable-list-item course-skill-row" key={`owl-${result.id}`}>
                <span>O.W.L. · {result.name}</span><strong>{result.grade}</strong>
              </div>
            ))}
            {courses.newt_results.map((result) => (
              <div className="readable-list-item course-skill-row" key={`newt-${result.id}`}>
                <span>N.E.W.T. · {result.name}</span><strong>{result.grade}</strong>
              </div>
            ))}
          </div>
        </section>
      )}
      <section className="data-section">
        <h3>年度记录</h3>
        {courses.course_history.length === 0 ? (
          <EmptyText text="六月结算和选课记录会在学年推进后留在这里。" />
        ) : (
          <ReadableValue value={courses.course_history} />
        )}
      </section>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return <div className="stat"><span>{label}</span><strong>{value}</strong></div>;
}

function StoryArcNotice({
  status,
  retrying,
  onRetry,
}: {
  status: StoryArcStatus | null;
  retrying: boolean;
  onRetry: () => Promise<void>;
}) {
  if (!status?.active_job && !status?.latest_failed_job) return null;
  const job = status.active_job;
  return (
    <div className={`story-arc-notice ${status.blocked ? "is-blocking" : ""}`} role="status" aria-live="polite">
      {job ? (
        <>
          <strong>{status.blocked ? "正在整理故事弧，剧情暂时排队" : "正在后台整理故事弧"}</strong>
          <span>
            整理第 {job.source_turn_start}—{job.source_turn_end} 轮；
            {status.blocked ? "完成后会自动恢复所有剧情操作。" : "你仍可继续推进剧情。"}
            请不要退出或关闭软件，生成结束后此提示会自动消失。
          </span>
        </>
      ) : status.latest_failed_job ? (
        <>
          <strong>故事弧整理失败</strong>
          <span>{status.latest_failed_job.error || "原始节点摘要仍会继续保留，不影响剧情。"}</span>
          <button className="secondary-button" disabled={retrying} onClick={() => void onRetry()}>
            {retrying ? "正在重试…" : "重试整理"}
          </button>
        </>
      ) : null}
    </div>
  );
}

function StoryArcPanel({
  arcs,
  compressing,
  compressError,
  onCompress,
}: {
  arcs: StoryArc[];
  compressing: boolean;
  compressError: string;
  onCompress: () => void;
}) {
  return (
    <div className="story-arc-panel">
      <section className="data-section">
        <p className="eyebrow">长期剧情记忆</p>
        <h2>故事弧</h2>
        <p className="muted">原始剧情节点不会被删除；故事弧只负责让后续叙事用更少的上下文记住较远的经历。</p>
        <div className="story-arc-actions">
          <button
            className="secondary-button"
            disabled={compressing || arcs.length < 2}
            onClick={onCompress}
          >
            {compressing ? "正在压缩…" : "压缩全部故事弧"}
          </button>
          <span className="muted">
            {arcs.length < 2
              ? "至少需要两条故事弧才能压缩。"
              : "把现有故事弧精简合并成一条，继承覆盖轮次并清理过期线索。"}
          </span>
        </div>
        {compressError && <div className="error-banner">{compressError}</div>}
      </section>
      {arcs.length === 0 ? (
        <div className="data-section"><EmptyText text="完成足够的剧情节点后，阶段性故事弧会自动出现在这里。" /></div>
      ) : (
        arcs.map((arc) => (
          <article className="story-arc-card" key={arc.scope_key}>
            <div className="story-arc-card-meta">
              <span>第 {arc.covered_turn_start}—{arc.covered_turn_end} 轮</span>
              <span>{new Date(arc.updated_at).toLocaleDateString("zh-CN")}</span>
            </div>
            <h3>{arc.title}</h3>
            <p>{arc.summary}</p>
            {arc.open_threads.length > 0 && (
              <div className="story-arc-threads">
                <strong>未解决线索</strong>
                <ul>
                  {arc.open_threads.map((thread, index) => <li key={`${arc.scope_key}-thread-${index}`}>{String(thread)}</li>)}
                </ul>
              </div>
            )}
          </article>
        ))
      )}
    </div>
  );
}

function DepartureNoticePanel({
  notice,
  acknowledging,
  onAcknowledge,
}: {
  notice: Record<string, any>;
  acknowledging: boolean;
  onAcknowledge: () => void;
}) {
  return (
    <section className="departure-notice-panel" role="alertdialog" aria-modal="true" aria-labelledby="departure-notice-title">
      <p className="eyebrow">学籍状态变更</p>
      <h2 id="departure-notice-title">{notice.title || "霍格沃兹离校通知"}</h2>
      <p>{notice.message || "你的学籍已经终止，课程已清空，请尽快离开学校。"}</p>
      <p className="departure-notice-help">确认后，剧情会继续记录你的离校状态；你不能再以普通学生身份返回学校。</p>
      <button className="primary-button" disabled={acknowledging} onClick={onAcknowledge}>
        {acknowledging ? "正在确认…" : "确认并离开学校"}
      </button>
    </section>
  );
}

function ReputationPanel({ value }: { value: unknown }) {
  const reputation = getReputationDisplay(value);
  const position = ((reputation.score + 100) / 200) * 100;
  const deltaLabel = reputation.lastDelta > 0
    ? `本回合声望上升 +${reputation.lastDelta}`
    : reputation.lastDelta < 0
      ? `本回合声望下降 ${reputation.lastDelta}`
      : "本回合声望没有变化";

  return (
    <div className="reputation-panel">
      <section className="reputation-hero" aria-label="当前声望">
        <p className="eyebrow">魔法社会中的名声</p>
        <div className={`reputation-score ${reputation.score > 0 ? "positive" : reputation.score < 0 ? "negative" : "neutral"}`}>
          {reputation.score > 0 ? "+" : ""}{reputation.score}
        </div>
        <h2>{reputation.levelName}</h2>
        <p>{reputation.alignment}</p>
      </section>
      <section className="reputation-scale" aria-label="声望刻度">
        <div className="reputation-scale-labels">
          <span>黑暗倾向 −100</span>
          <span>中立 0</span>
          <span>白巫师倾向 +100</span>
        </div>
        <div className="reputation-track">
          <span className="reputation-marker" style={{ left: `${position}%` }} aria-label={`当前声望 ${reputation.score}`} />
        </div>
      </section>
      <section className="reputation-description">
        <h3>当前影响</h3>
        <p>{reputation.description}</p>
        <p className="muted">
          {reputation.score > 10
            ? "陌生人和关键人物通常更愿意先听你解释，并在合理范围内提供帮助。"
            : reputation.score < -10
              ? "陌生人和管理者通常会更谨慎地对待你，可能要求额外证明或担保。"
              : "你还没有在魔法社会中留下明确的善恶印象，NPC 会更多依据当前行为判断你。"}
        </p>
      </section>
      <section className="reputation-latest">
        <h3>最近变化</h3>
        <div className={`reputation-change ${reputation.lastDelta > 0 ? "positive" : reputation.lastDelta < 0 ? "negative" : "neutral"}`}>
          <strong>{deltaLabel}</strong>
          {reputation.lastReason && <span>{reputation.lastReason}</span>}
        </div>
      </section>
    </div>
  );
}

function getReputationDisplay(value: unknown) {
  const raw = value && typeof value === "object" ? value as Record<string, unknown> : {};
  const scoreValue = typeof raw.score === "number" && Number.isFinite(raw.score) ? raw.score : 0;
  const score = Math.max(-100, Math.min(100, Math.trunc(scoreValue)));
  const levels = [
    { name: "黑暗典范", min: -100, max: -81, alignment: "强烈偏向黑巫师", description: "声名极其恶劣，接近被整个社会视为重大威胁。" },
    { name: "黑巫师", min: -80, max: -61, alignment: "偏向黑巫师", description: "公开被视为危险的黑巫师或黑魔法倾向者。" },
    { name: "危险人物", min: -60, max: -31, alignment: "偏向黑暗", description: "被认为可能伤害他人或为了目的不择手段。" },
    { name: "可疑倾向", min: -30, max: -11, alignment: "轻微负面", description: "行为动机不稳定，别人会多问一句、多观察一步。" },
    { name: "中立", min: -10, max: 10, alignment: "中立倾向", description: "尚无明确的善恶或阵营印象。" },
    { name: "友善倾向", min: 11, max: 30, alignment: "轻微正面", description: "通常被看作善意、愿意合作，但还没有形成强烈公众声誉。" },
    { name: "正直可靠", min: 31, max: 60, alignment: "正面倾向", description: "多数普通巫师愿意相信其动机。" },
    { name: "白巫师", min: 61, max: 80, alignment: "偏向白巫师", description: "明显站在正义和保护弱者的一侧。" },
    { name: "光明典范", min: 81, max: 100, alignment: "强烈偏向白巫师", description: "被普遍认为是极其正直、可靠且愿意保护他人的巫师。" },
  ];
  const level = levels.find((item) => item.min <= score && score <= item.max) ?? levels[4];
  const lastDelta = typeof raw.last_delta === "number" && Number.isFinite(raw.last_delta)
    ? Math.max(-10, Math.min(10, Math.trunc(raw.last_delta)))
    : 0;
  return {
    score,
    levelName: level.name,
    alignment: level.alignment,
    description: level.description,
    lastDelta,
    lastReason: typeof raw.last_reason === "string" ? raw.last_reason : "",
  };
}

function formatStoryDate(value: unknown): string | null {
  if (typeof value !== "string" || !value) return null;
  const match = value.match(/^\d{4}-\d{2}-\d{2}/);
  return match ? match[0] : null;
}

function translateGrade(value: unknown): string {
  const labels: Record<string, string> = {
    not_enrolled: "未入学",
    year_1: "一年级",
    year_2: "二年级",
    year_3: "三年级",
    year_4: "四年级",
    year_5: "五年级",
    year_6: "六年级",
    year_7: "七年级",
    left_school: "已离校",
  };
  return labels[String(value)] ?? "未记录";
}

const FIELD_LABELS: Record<string, string> = {
  bloodline: "血统与出身",
  description: "说明",
  form: "形态",
  summoning_requirement: "召唤条件",
  traits: "性格特征",
  primary: "核心性格",
  level: "熟练度",
  experience: "经验",
  source: "来源",
  course_id: "课程",
  course_skill: "课程技能",
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
  romance_stage: "恋爱阶段",
  bond_type: "羁绊类型",
  known_secrets: "已知秘密",
  pending_stage_unlocks: "待解锁阶段",
  galleons: "加隆",
  sickles: "西可",
  knuts: "纳特",
  academic: "学术声望",
  social: "社交声望",
  combat: "战斗声望",
  morality: "道德声望",
  leadership: "领导声望",
  dark_magic: "黑魔法声望",
};

const VALUE_LABELS: Record<string, string> = {
  initial_magic_talent: "初始魔法天赋",
  course: "正式课程",
  model_delta: "剧情成长",
  stranger: "陌生",
  acquaintance: "相识",
  friend: "朋友",
  close_friend: "挚友",
  estranged: "疏远",
  hostile: "敌对",
  locked: "尚未开放",
  none: "暂无恋爱关系",
  dating: "恋爱",
  romance: "恋爱",
  lover: "恋人",
  committed: "稳定恋情",
  adult_stage: "成年亲密关系",
  marriage: "婚姻",
  married: "已婚",
  unavailable: "尚未开启",
  single: "单身",
  multiple_bonds: "多段羁绊",
  potential: "潜在羁绊",
  friendship: "友情",
  rivalry: "竞争关系",
  mentor: "师生羁绊",
  family: "家人",
  professional: "工作关系",
  other: "其他羁绊",
  normal: "正常",
  positive: "正面",
  negative: "负面",
  summer: "夏季",
  autumn: "秋季",
  spring: "春季",
  winter: "冬季",
  morning: "清晨",
  afternoon: "午后",
  evening: "傍晚",
  night: "夜晚",
  home: "家中",
  diagon_alley: "对角巷",
  platform_nine_three_quarters: "九又四分之三站台",
  hogwarts_great_hall: "霍格沃茨礼堂",
  library: "图书馆",
  hogwarts_library: "霍格沃茨图书馆",
  hogwarts: "霍格沃茨",
  ollivanders: "奥利凡德魔杖店",
  flourish_and_blotts: "丽痕书店",
  madam_malkins: "摩金夫人长袍店",
  gringotts: "古灵阁",
  leaky_cauldron: "破釜酒吧",
  king_cross_station: "国王十字车站",
  great_hall: "霍格沃茨礼堂",
  unknown: "未知地点",
  gryffindor: "格兰芬多",
  hufflepuff: "赫奇帕奇",
  ravenclaw: "拉文克劳",
  slytherin: "斯莱特林",
  before_first_letter: "等待霍格沃茨来信",
  sorting_ceremony: "分院仪式",
  ready_for_first_scene: "等待命运启程",
  letter_and_enrollment: "来信与入学",
  first_letter_and_enrollment: "霍格沃茨来信与入学",
  castle_old_secrets: "城堡旧秘密",
  philosophers_stone_protections: "魔法石的秘密防线",
  chamber_and_fear: "密室与恐惧",
  chamber_of_secrets: "密室之谜",
  fugitive_and_time: "逃犯与时间",
  sirius_escape: "小天狼星越狱",
  tournament_and_war_shadow: "比赛与战争阴影",
  triwizard_tournament: "三强争霸赛",
  dark_lord_return: "黑魔王归来",
  resistance_and_battle: "分裂、抵抗与霍格沃茨之战",
  da_resistance: "D.A.抵抗行动",
  astronomy_tower: "天文塔悲剧",
  battle_of_hogwarts: "霍格沃茨之战",
  postwar_aftermath: "战后余波",
  true: "是",
  false: "否",
};

const COURSE_LABELS: Record<string, string> = {
  transfiguration: "变形术",
  charms: "咒语",
  potions: "魔药",
  history_of_magic: "魔法史",
  defence_against_dark_arts: "黑魔法防御术",
  astronomy: "天文学",
  herbology: "草药学",
  flying: "飞行课",
  arithmancy: "算术占卜",
  muggle_studies: "麻瓜研究",
  divination: "占卜",
  ancient_runes: "古代魔文研究",
  care_of_magical_creatures: "神奇动物保护",
  alchemy: "炼金术",
  apparition: "幻影移形",
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

function displayItemName(item: unknown): string {
  if (typeof item === "string" && item.trim()) return item.trim();
  if (!item || typeof item !== "object" || Array.isArray(item)) return "未命名物品";

  const record = item as Record<string, unknown>;
  for (const key of ["name", "item_name"]) {
    if (typeof record[key] === "string" && record[key].trim()) {
      return record[key].trim();
    }
  }
  for (const key of ["item_id", "id"]) {
    if (typeof record[key] === "string" && record[key].trim()) {
      return record[key].trim();
    }
  }
  return "未命名物品";
}

function displayInventory(inventory: unknown): unknown {
  if (!Array.isArray(inventory)) return inventory;
  return inventory.map((item) => {
    if (!item || typeof item !== "object" || Array.isArray(item)) return item;
    return {
      ...(item as Record<string, unknown>),
      name: displayItemName(item),
    };
  });
}

function ReadableValue({ value, fieldName }: { value: unknown; fieldName?: string }) {
  if (value === null || value === undefined || value === "") {
    return <span className="readable-empty">尚未记录</span>;
  }
  if (fieldName === "level" && typeof value === "number") {
    return <span className="readable-value">{value}/10</span>;
  }
  if (fieldName === "experience" && typeof value === "number") {
    return <span className="readable-value">{value}/100</span>;
  }
  if (Array.isArray(value)) {
    return (
      <div className="readable-list">
        {value.map((item, index) => (
          <div className="readable-list-item" key={`${fieldName ?? "item"}-${index}`}>
            <ReadableValue value={item} fieldName={fieldName} />
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
  return <span className="readable-value">{translateValue(value, fieldName)}</span>;
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
  if (COURSE_LABELS[key.toLowerCase()]) return COURSE_LABELS[key.toLowerCase()];
  return key
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function translateValue(value: unknown, fieldName?: string): string {
  if (typeof value === "boolean") return value ? "是" : "否";
  const text = String(value);
  if (fieldName === "course_id" || fieldName === "id" || fieldName === "skill_id") {
    return COURSE_LABELS[text.toLowerCase()] ?? text;
  }
  if (fieldName === "active_courses" || fieldName === "selected_courses") {
    return COURSE_LABELS[text.toLowerCase()] ?? text;
  }
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

function translateRisk(value: TurnResult["response"]["choices"][number]["risk"]): string {
  return {
    low: "低",
    medium: "中",
    high: "高",
    fatal: "致命",
  }[value];
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
  return romanticStages.has(getRomanceStage(state));
}

function getRomanceStage(state: Record<string, any>): string {
  const canonical = String(state.romance_stage ?? "");
  if (canonical) return canonical;
  const legacyRomance = String(state.romance_state ?? "");
  if (legacyRomance && legacyRomance !== "unavailable") return legacyRomance;
  const legacyStage = String(state.stage ?? "");
  return [
    "dating",
    "romance",
    "lover",
    "committed",
    "adult_stage",
    "marriage",
    "married",
  ].includes(legacyStage) ? legacyStage : "none";
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

function ChangeNotice({
  changes,
  npcNames,
}: {
  changes: PlayerChanges;
  npcNames: Record<string, string>;
}) {
  if (!changes || !hasChanges(changes)) return null;
  return (
    <div className="change-notice">
      <strong>本回合状态变化</strong>
      <div className="change-columns">
        <ChangeList title="获得" items={[
          ...changes.inventory_add.map((item) => `物品：${displayItemName(item)}`),
          ...changes.status_add.map((item) => `状态：${item.name ?? item.id}`),
          ...changes.skill_add.map((item) => `技能：${item.name ?? item.id}`),
          ...changes.trait_add.map((item) => `词条：${item.name}`),
          ...(changes.relationship_creations ?? []).map(
            (item) => `新羁绊：${item.character?.name ?? "未留名的巫师"}`,
          ),
        ]} />
        <ChangeList title="失去" items={[
          ...changes.inventory_remove.map((item) => `物品：${displayItemName(item)}`),
          ...changes.status_remove.map((item) => `状态：${item}`),
          ...changes.skill_remove.map((item) => `技能：${item}`),
          ...changes.trait_remove.map((item) => `词条：${item}`),
        ]} />
        <ChangeList title="变化" items={[
          ...Object.entries(changes.skill_deltas).map(([key, value]) => `技能 ${key}：${formatDelta(value)}`),
          ...Object.entries(changes.skill_experience_deltas ?? {}).map(
            ([key, value]) => `技能 ${key} 经验：+${value}`,
          ),
          ...changes.resource_deltas.map((item) =>
            `${resourceLabel(item.id)}：${formatDelta(item.delta)}${item.reason ? `（${item.reason}）` : ""}`,
          ),
          ...changes.dimension_deltas.map((item) =>
            `${dimensionLabel(item.id)}：${formatDelta(item.delta)}${item.reason ? `（${item.reason}）` : ""}`,
          ),
          ...(changes.relationship_deltas ?? []).map((item) =>
            `羁绊 ${npcNames[item.npc_id] ?? NPC_NAMES[item.npc_id] ?? item.npc_id}：好感 ${formatDelta(item.affinity_delta ?? 0)}，信任 ${formatDelta(item.trust_delta ?? 0)}${item.reason ? `（${item.reason}）` : ""}`,
          ),
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
    Object.keys(changes.skill_experience_deltas ?? {}).length ||
    changes.resource_deltas.length ||
    changes.dimension_deltas.length ||
    changes.resource_cap_deltas.length ||
    changes.dimension_cap_deltas.length ||
    (changes.relationship_deltas ?? []).length ||
    (changes.relationship_creations ?? []).length,
  );
}

function ResourceSection({ resources }: { resources: Record<string, any> }) {
  return (
    <section className="data-section">
      <h3>核心与辅助资源</h3>
      <div className="status-grid">
        {["health", "mana", "sanity", "energy", "satiety"].map((id) => (
          <Stat
            key={id}
            label={resourceLabel(id)}
            value={`${formatNumber(resources[id]?.value ?? 0)}/${formatNumber(resources[id]?.max ?? 100)}`}
          />
        ))}
      </div>
    </section>
  );
}

function DimensionSection({ dimensions }: { dimensions: Record<string, any> }) {
  return (
    <section className="data-section">
      <h3>长期维度</h3>
      <div className="status-grid">
        {["constitution", "intelligence", "willpower", "charisma", "magical_power"].map((id) => (
          <Stat
            key={id}
            label={dimensionLabel(id)}
            value={`${formatNumber(dimensions[id]?.value ?? 0)}/${formatNumber(dimensions[id]?.max ?? 20)}`}
          />
        ))}
      </div>
    </section>
  );
}

function resourceLabel(id: string): string {
  return {
    health: "生命值",
    mana: "魔力值",
    sanity: "精神值",
    energy: "精力",
    satiety: "饱食度",
  }[id] ?? id;
}

function dimensionLabel(id: string): string {
  return {
    constitution: "体质",
    intelligence: "智力",
    willpower: "精神强度",
    charisma: "魅力",
    magical_power: "魔力强度",
  }[id] ?? id;
}

function formatDelta(value: number): string {
  const normalized = Number.isFinite(value) ? Number(value.toFixed(4)) : 0;
  return `${normalized > 0 ? "+" : ""}${normalized}`;
}

function formatNumber(value: unknown): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "0";
  return String(Number(value.toFixed(4)));
}
