import { useEffect, useMemo, useState } from "react";
import { BookOpenText, MagicWand, Sparkle } from "@phosphor-icons/react";
import {
  api,
  type JournalEntry,
  type CourseView,
  type NPCState,
  type PlayerChanges,
  type StoredTurn,
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
  const [courses, setCourses] = useState<CourseView | null>(null);
  const [selectedCourses, setSelectedCourses] = useState<string[]>([]);
  const [savingCourses, setSavingCourses] = useState(false);
  const [turn, setTurn] = useState<TurnResult | null>(null);
  const [turnHistory, setTurnHistory] = useState<StoredTurn[]>([]);
  const [viewedTurnIndex, setViewedTurnIndex] = useState(-1);
  const [freeText, setFreeText] = useState("");
  const [loading, setLoading] = useState(false);
  const [initializingAttributes, setInitializingAttributes] = useState(false);
  const [error, setError] = useState("");

  async function refreshState() {
    const [stateResponse, journalResponse, relationshipResponse, npcResponse, turnsResponse, coursesResponse] = await Promise.all([
      api.state(sessionId),
      api.journal(sessionId),
      api.relationships(sessionId),
      api.npcs(sessionId),
      api.turns(sessionId),
      api.courses(sessionId),
    ]);
    setState(stateResponse.state);
    setStateVersion(stateResponse.state_version);
    setJournal(journalResponse);
    setRelationships(relationshipResponse);
    setNpcs(npcResponse);
    setTurnHistory(turnsResponse);
    setCourses(coursesResponse);
    setViewedTurnIndex(turnsResponse.length - 1);
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
    if (
      (turnHistory.length > 0 && viewedTurnIndex !== turnHistory.length - 1)
      || courses?.course_selection?.status === "pending"
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

  const player = state ?? {};
  const identity = player.identity ?? {};
  const context = player.current_context ?? {};
  const worldline = player.worldline ?? {};
  const resources = player.resources ?? {};
  const dimensions = player.dimensions ?? {};
  const lifecycle = player.lifecycle ?? {};
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
      }
    : context;
  const displayWorldline = visibleResponse?.worldline ?? worldline;
  const hasStarted = turnHistory.length > 0 || journal.length > 0 || turn !== null;
  const courseSelectionPending = courses?.course_selection?.status === "pending";

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
              <Stat label="地点" value={translateValue(context.location_id ?? "unknown")} />
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
        {["声望", "信件"].includes(activeMenu) && (
          <ReadableSection
            title={activeMenu === "声望" ? "魔法社会中的名声" : "猫头鹰邮递"}
            data={player[activeMenu === "声望" ? "reputation" : "letters"] ?? {}}
            emptyText={activeMenu === "信件" ? "猫头鹰棚里暂时没有寄给你的新信。" : "这页羊皮纸暂时没有可显示的记录。"}
          />
        )}
      </div>
    );
  }

  if (attributeInitialization.status !== "ready") {
    async function retryAttributeInitialization() {
      setInitializingAttributes(true);
      setError("");
      try {
        await api.initializeAttributes(sessionId);
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

  return (
    <section className="game-panel" aria-label="剧情档案">
      {error && <div className="error-banner">{error}</div>}
      {lifecycle.status === "dead" ? (
        <div className="empty-panel ending-panel">
          <span className="empty-icon" aria-hidden="true"><BookOpenText /></span>
          <h3>这条世界线已经走到终点</h3>
          <p>生命值归零，角色故事已封存。你仍可以查看角色、纪事与已经留下的关系记录。</p>
        </div>
      ) : loading ? (
        <div className="magic-loading" role="status" aria-live="polite">
          <div className="magic-orbit" aria-hidden="true"><MagicWand /></div>
          <h3>羽毛笔正在书写命运</h3>
          <p>魔法回响穿过时间与空间，命运正在为你编织下一幕……</p>
        </div>
      ) : (
        <>
          <div className="game-meta">
            <span>日期：{displayContext.current_date ?? formatStoryDate(displayContext.datetime) ?? "1991-07-01"}</span>
            <span>地点：{translateValue(displayContext.location_id ?? "unknown")}</span>
            <span>世界线 {Number(displayWorldline.offset_rate ?? 0).toFixed(1)}%</span>
          </div>
          {!hasStarted ? (
            <div className="first-scene">
              <span className="empty-icon" aria-hidden="true"><Sparkle /></span>
              <h3>角色属性已经校准</h3>
              <p>{player.attribute_initialization?.calibration_summary || "你的初始资源与长期维度已经根据角色设定生成，并会在剧情中继续变化。"}</p>
              <ResourceSection resources={resources} />
              <DimensionSection dimensions={dimensions} />
              <button className="primary-button" disabled={courseSelectionPending} onClick={() => void submitAction("choice", "start_story")}>
                踏入魔法世界
              </button>
            </div>
          ) : (
            <>
              <article className="narrative-card">
                <p className="eyebrow">{translateSceneType(visibleResponse?.turn.scene_type)}</p>
                <h3>{visibleResponse?.turn.title ?? "最近的故事"}</h3>
                <p className="narrative-text">
                  {visibleResponse?.turn.narrative ?? journal[0]?.summary ?? "羽毛笔悬停在羊皮纸上，等待你写下下一步行动。"}
                </p>
                {visibleResponse && <ChangeNotice changes={visibleResponse.applied_changes} />}
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
                        disabled={!isViewingLatest || loading || courseSelectionPending}
                        value={freeText}
                        onChange={(event) => setFreeText(event.target.value)}
                        placeholder="写下一个不在预言之中的行动…"
                        onKeyDown={(event) => {
                          if (event.key === "Enter" && freeText.trim()) {
                            void submitAction("free_text", choice.id, freeText.trim());
                          }
                        }}
                      />
                      <button className="secondary-button" disabled={!isViewingLatest || loading || courseSelectionPending || !freeText.trim()} onClick={() => void submitAction("free_text", choice.id, freeText.trim())}>
                        让羽毛笔记录
                      </button>
                    </div>
                  ) : (
                    <button className="choice-button" disabled={!isViewingLatest || loading || courseSelectionPending} key={choice.id} onClick={() => void submitAction("choice", choice.id)}>
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
  library: "图书馆",
  hogwarts_library: "霍格沃茨图书馆",
  hogwarts: "霍格沃茨",
  unknown: "未知地点",
  gryffindor: "格兰芬多",
  hufflepuff: "赫奇帕奇",
  ravenclaw: "拉文克劳",
  slytherin: "斯莱特林",
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
          ...Object.entries(changes.skill_experience_deltas ?? {}).map(
            ([key, value]) => `技能 ${key} 经验：+${value}`,
          ),
          ...changes.resource_deltas.map((item) =>
            `${resourceLabel(item.id)}：${formatDelta(item.delta)}${item.reason ? `（${item.reason}）` : ""}`,
          ),
          ...changes.dimension_deltas.map((item) =>
            `${dimensionLabel(item.id)}：${formatDelta(item.delta)}${item.reason ? `（${item.reason}）` : ""}`,
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
    changes.dimension_cap_deltas.length,
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
            value={`${resources[id]?.value ?? 0}/${resources[id]?.max ?? 100}`}
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
            value={`${dimensions[id]?.value ?? 0}/${dimensions[id]?.max ?? 20}`}
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
  return `${value > 0 ? "+" : ""}${value}`;
}
