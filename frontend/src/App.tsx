import { useEffect, useState } from "react";
import {
  Archive,
  BookOpenText,
  Envelope,
  GearSix,
  GitBranch,
  GraduationCap,
  Heart,
  Medal,
  PencilSimple,
  Scroll,
  Sparkle,
  Star,
  Trash,
  User,
  UsersThree,
  WifiHigh,
  WifiSlash,
  X,
} from "@phosphor-icons/react";
import {
  api,
  type EraInfo,
  type GameSession,
  type HealthResponse,
  type LLMConfigStatus,
  type SetupView,
} from "./api";
import { GameView } from "./GameView";

const menuItems = [
  { label: "剧情", icon: BookOpenText },
  { label: "角色", icon: User },
  { label: "纪事", icon: Scroll },
  { label: "关系与好感", icon: UsersThree },
  { label: "恋爱", icon: Heart },
  { label: "声望", icon: Medal },
  { label: "课程", icon: GraduationCap },
  { label: "信件", icon: Envelope },
  { label: "世界线", icon: GitBranch },
];

const GENERIC_ERA: EraInfo = {
  id: "second_generation",
  name: "未定世代",
  years: "四个世代，等待你的选择",
  eyebrow: "霍格沃兹人生模拟器 · 未定世界线",
  title: "命运的猫头鹰，正在寻找你的窗台。",
  description:
    "魔法世界的四段岁月在时间深处静静交汇。写下你的名字，选择一条时代的河流，让分院帽、城堡密道与尚未发生的历史见证另一种可能。",
  mainline: "",
  atmosphere: "",
  available: true,
};

export function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [llm, setLlm] = useState<LLMConfigStatus | null>(null);
  const [sessions, setSessions] = useState<GameSession[]>([]);
  const [eras, setEras] = useState<EraInfo[]>([]);
  const [activeMenu, setActiveMenu] = useState("角色");
  const [error, setError] = useState("");
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [setup, setSetup] = useState<SetupView | null>(null);
  const [setupAnswer, setSetupAnswer] = useState("");
  const [setupLoading, setSetupLoading] = useState(false);
  const [worldlineRate, setWorldlineRate] = useState(0);
  const [configOpen, setConfigOpen] = useState(false);
  const [configDraft, setConfigDraft] = useState({
    base_url: "",
    api_key: "",
    model: "",
  });
  const [configMessage, setConfigMessage] = useState("");
  const [configSaving, setConfigSaving] = useState(false);
  const [renamingSessionId, setRenamingSessionId] = useState<string | null>(null);
  const [renameDraft, setRenameDraft] = useState("");
  const [saveManaging, setSaveManaging] = useState(false);

  useEffect(() => {
    void Promise.all([api.health(), api.llmConfig(), api.sessions(), api.eras()])
      .then(([healthResponse, llmResponse, sessionResponse, eraResponse]) => {
        setHealth(healthResponse);
        setLlm(llmResponse);
        setSessions(sessionResponse);
        setEras(eraResponse);
      })
      .catch((reason: unknown) => {
        setError(reason instanceof Error ? reason.message : "无法连接本地后端");
      });
  }, []);

  useEffect(() => {
    if (!selectedSessionId) {
      setSetup(null);
      return;
    }
    void api.setup(selectedSessionId)
      .then((nextSetup) => {
        setSetup(nextSetup);
        if (nextSetup.completed) setActiveMenu("剧情");
      })
      .catch((reason: unknown) => {
        setError(reason instanceof Error ? reason.message : "无法读取角色创建状态");
      });
  }, [selectedSessionId]);

  const selectedSession = sessions.find((session) => session.id === selectedSessionId);
  const eraById = Object.fromEntries(eras.map((era) => [era.id, era]));
  const currentEra = selectedSession
    ? eraById[selectedSession.era_id] ?? GENERIC_ERA
    : GENERIC_ERA;

  useEffect(() => {
    if (!setup || setup.completed) return;
    const savedAnswer = setup.answers[String(setup.current_step)];
    setSetupAnswer(typeof savedAnswer === "string" ? savedAnswer : "");
  }, [setup?.current_step, setup?.completed]);

  async function handleCreateSession() {
    const sessionName = name.trim() || "我的霍格沃兹人生";
    setCreating(true);
    setError("");
    try {
      const session = await api.createSession(sessionName);
      setSessions((current) => [session, ...current]);
      setName("");
      setSelectedSessionId(session.id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "创建存档失败");
    } finally {
      setCreating(false);
    }
  }

  async function submitSetupAnswer() {
    if (!selectedSessionId || !setup || !setupAnswer.trim()) return;
    setSetupLoading(true);
    setError("");
    try {
      const next = await api.answerSetup(
        selectedSessionId,
        setup.current_step,
        setupAnswer.trim(),
      );
      setSetup(next);
      setSetupAnswer("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "保存角色设定失败");
    } finally {
      setSetupLoading(false);
    }
  }

  async function confirmSetup() {
    if (!selectedSessionId) return;
    setSetupLoading(true);
    setError("");
    try {
      const next = await api.confirmSetup(selectedSessionId);
      setSetup(next);
      setSessions((current) =>
        current.map((session) =>
          session.id === selectedSessionId
            ? { ...session, status: "active", state_version: 1 }
            : session,
        ),
      );
      setActiveMenu("剧情");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "无法确认角色");
    } finally {
      setSetupLoading(false);
    }
  }

  function openConfig() {
    setConfigDraft({
      base_url: llm?.base_url ?? "",
      api_key: "",
      model: llm?.model ?? "",
    });
    setConfigMessage("");
    setConfigOpen(true);
  }

  async function saveConfig() {
    if (!configDraft.api_key.trim()) {
      setConfigMessage("请输入 API Key；出于安全原因，现有 Key 不会回显。");
      return;
    }
    setConfigSaving(true);
    setConfigMessage("");
    try {
      const next = await api.updateLlmConfig({
        base_url: configDraft.base_url.trim(),
        api_key: configDraft.api_key.trim(),
        model: configDraft.model.trim(),
      });
      setLlm(next);
      setConfigMessage("配置已保存。");
      setConfigDraft((current) => ({ ...current, api_key: "" }));
    } catch (reason) {
      setConfigMessage(reason instanceof Error ? reason.message : "配置保存失败");
    } finally {
      setConfigSaving(false);
    }
  }

  async function testConfig() {
    if (
      !configDraft.base_url.trim() ||
      !configDraft.api_key.trim() ||
      !configDraft.model.trim()
    ) {
      setConfigMessage("请完整填写 Base URL、API Key 和模型名后再测试。");
      return;
    }
    setConfigSaving(true);
    setConfigMessage("正在测试模型服务…");
    try {
      const result = await api.testLlm({
        base_url: configDraft.base_url.trim(),
        api_key: configDraft.api_key.trim(),
        model: configDraft.model.trim(),
      });
      setConfigMessage(
        result.success
          ? `连接成功：${displayMessage(result.message, "模型服务已正常响应")}，耗时 ${result.latency_ms} ms。`
          : `连接失败：${displayMessage(result.message, "模型服务未能响应")}`,
      );
    } catch (reason) {
      setConfigMessage(reason instanceof Error ? reason.message : "模型服务测试失败");
    } finally {
      setConfigSaving(false);
    }
  }

  function beginRename(session: GameSession) {
    setRenamingSessionId(session.id);
    setRenameDraft(session.name);
  }

  async function saveRename(sessionId: string) {
    const nextName = renameDraft.trim();
    if (!nextName) {
      setError("命运卷宗必须拥有一个可以辨认的名字。");
      return;
    }
    setSaveManaging(true);
    setError("");
    try {
      const renamed = await api.renameSession(sessionId, nextName);
      setSessions((current) =>
        current.map((session) => session.id === sessionId ? renamed : session),
      );
      setRenamingSessionId(null);
      setRenameDraft("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "卷宗重命名失败");
    } finally {
      setSaveManaging(false);
    }
  }

  async function removeSession(session: GameSession) {
    const confirmed = window.confirm(
      `确定要永久焚毁命运卷宗“${session.name}”吗？\n\n其中的角色、纪事、关系与所有世界线记录都将无法恢复。`,
    );
    if (!confirmed) return;
    setSaveManaging(true);
    setError("");
    try {
      await api.deleteSession(session.id);
      setSessions((current) => current.filter((item) => item.id !== session.id));
      if (selectedSessionId === session.id) {
        setSelectedSessionId(null);
        setSetup(null);
        setWorldlineRate(0);
        setActiveMenu("剧情");
      }
      if (renamingSessionId === session.id) {
        setRenamingSessionId(null);
        setRenameDraft("");
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "卷宗销毁失败");
    } finally {
      setSaveManaging(false);
    }
  }

  function chooseSetupOption(
    value: string,
    mode: "single" | "append" | "text" | "confirm",
  ) {
    if (mode !== "append") {
      setSetupAnswer(value);
      return;
    }
    const values = setupAnswer
      .replaceAll("，", ",")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
    if (!values.includes(value)) values.push(value);
    setSetupAnswer(values.join("，"));
  }

  function isSelectedOption(value: string): boolean {
    return setupAnswer
      .replaceAll("，", ",")
      .split(",")
      .map((item) => item.trim())
      .includes(value);
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand-lockup">
          <span className="brand-sigil" aria-hidden="true"><Star weight="fill" /></span>
          <div>
          <p className="eyebrow">{currentEra.eyebrow}</p>
          <h1>霍格沃兹人生模拟器</h1>
          </div>
        </div>
        <div className="connection-status">
          {health?.status === "ok"
            ? <WifiHigh className="connection-icon online" aria-hidden="true" />
            : <WifiSlash className="connection-icon" aria-hidden="true" />}
          {health?.status === "ok" ? "本地服务已连接" : "等待本地服务"}
        </div>
      </header>

      <section className="intro-card">
        <div>
          <p className="eyebrow">{currentEra.years}</p>
          <h2>{currentEra.title}</h2>
          <p className="muted">{currentEra.description}</p>
        </div>
        <div className="config-card">
          <span className="service-label"><Sparkle aria-hidden="true" />模型服务</span>
          <strong>{llm?.model ?? "等待水晶球回应"}</strong>
          <small>{llm?.api_key_present ? "叙事水晶已与远方回响相连" : "叙事水晶尚未建立连接"}</small>
          <button className="config-button" onClick={openConfig}><GearSix aria-hidden="true" />修改 / 测试</button>
        </div>
      </section>

      {error && <div className="error-banner">{error}</div>}

      {configOpen && (
        <div className="modal-backdrop" onClick={() => setConfigOpen(false)}>
          <section
            aria-labelledby="config-title"
            aria-modal="true"
            className="config-modal"
            role="dialog"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="modal-heading">
              <div>
                <p className="eyebrow">LOCAL MODEL SERVICE</p>
                <h2 id="config-title">模型服务配置</h2>
              </div>
              <button aria-label="关闭模型服务配置" className="modal-close" onClick={() => setConfigOpen(false)}><X aria-hidden="true" /></button>
            </div>
            <p className="modal-note">配置只保存到本机文件，API Key 不会回显到页面。</p>
            <label>Base URL<input value={configDraft.base_url} onChange={(event) => setConfigDraft({ ...configDraft, base_url: event.target.value })} placeholder="https://api.example.com" /></label>
            <label>API Key<input type="password" value={configDraft.api_key} onChange={(event) => setConfigDraft({ ...configDraft, api_key: event.target.value })} placeholder="输入新的 API Key" /></label>
            <label>模型名<input value={configDraft.model} onChange={(event) => setConfigDraft({ ...configDraft, model: event.target.value })} placeholder="model-name" /></label>
            {configMessage && <div className="config-message">{configMessage}</div>}
            <div className="modal-actions">
              <button className="secondary-button" disabled={configSaving} onClick={() => void testConfig()}>测试连通性</button>
              <button className="primary-button" disabled={configSaving} onClick={() => void saveConfig()}>{configSaving ? "处理中…" : "保存配置"}</button>
            </div>
          </section>
        </div>
      )}

      <section className="workspace">
        <aside className="sidebar">
          <div className="sidebar-title">
            <span>魔法档案</span>
            <Sparkle className="menu-mark" aria-hidden="true" />
          </div>
          <nav aria-label="魔法档案导航">
            {menuItems.map(({ label, icon: MenuIcon }) => (
                <button
                  aria-current={activeMenu === label ? "page" : undefined}
                  className={activeMenu === label ? "menu-item active" : "menu-item"}
                  key={label}
                  onClick={() => setActiveMenu(label)}
                >
                  <span className="menu-label"><MenuIcon aria-hidden="true" />{label}</span>
                  {label === "世界线" && <span className="worldline-value">{worldlineRate.toFixed(1)}%</span>}
                </button>
              ))}
          </nav>
          <div className="sidebar-note">
            这里的查看不会惊动时间齿轮，也不会打断正在编织的剧情。
          </div>
        </aside>

        <section className="content-card">
          <div className="content-heading">
            <div>
              <p className="eyebrow">魔法档案阅览台</p>
              <h2>{activeMenu}</h2>
            </div>
            <span className="state-pill">{setup?.completed ? "世界线流转中" : "命运尚待书写"}</span>
          </div>
          {setup && !setup.completed ? (
            <div className="setup-panel">
              <span className="setup-progress">
                第 {setup.current_step} / {setup.steps_total} 步
              </span>
              <h3>{setup.current.title}</h3>
              <p className="muted">{setup.current.description}</p>
              {setup.current.selection_mode === "confirm" ? (
                <SetupSummary answers={setup.answers} eras={eras} />
              ) : (
                <div className="setup-options">
                  {groupSetupOptions(setup.current.options).map(([category, options]) => (
                    <section className="setup-option-group" key={category || "default"}>
                      {category && <h4>{category}</h4>}
                      <div>
                        {options.map((option) => {
                          const value = option.value ?? option.label;
                          return (
                            <button
                              className={isSelectedOption(value) ? "setup-option selected" : "setup-option"}
                              disabled={!option.available}
                              key={option.id}
                              onClick={() => option.available && chooseSetupOption(value, setup.current.selection_mode)}
                            >
                              <strong>{option.label}</strong>
                              {option.description && <small>{option.description}</small>}
                              {!option.available && <small className="unavailable-note">暂不可选择</small>}
                            </button>
                          );
                        })}
                      </div>
                    </section>
                  ))}
                </div>
              )}
              <div className="setup-input-row">
                {setup.current_step < 13 ? (
                  <>
                    {setup.current_step !== 1 && (
                      <textarea
                        value={setupAnswer}
                        onChange={(event) => setSetupAnswer(event.target.value)}
                        placeholder={
                          setup.current.selection_mode === "append"
                            ? "点击预设会追加到这里，也可以继续输入，用逗号分隔"
                            : "选择上方预设，或输入自定义设定"
                        }
                        onKeyDown={(event) => {
                          if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
                            void submitSetupAnswer();
                          }
                        }}
                      />
                    )}
                    <button
                      className={setup.current_step === 1 ? "primary-button setup-era-next" : "primary-button"}
                      disabled={setupLoading || !setupAnswer.trim()}
                      onClick={() => void submitSetupAnswer()}
                    >
                      {setupLoading ? "保存中…" : setup.current_step === 1 ? "以所选世代继续" : "下一步"}
                    </button>
                  </>
                ) : (
                  <button
                    className="primary-button"
                    disabled={setupLoading}
                    onClick={() => void confirmSetup()}
                  >
                    {setupLoading ? "确认中…" : "确认角色并开始"}
                  </button>
                )}
              </div>
              <p className="setup-hint">
                当前设定会保存在本地存档中。
                {setup.current_step === 1
                  ? " 请选择上方一个已开放的世代。"
                  : setup.current_step < 13 && " 可按 Ctrl + Enter 进入下一步。"}
              </p>
            </div>
          ) : setup?.completed && selectedSessionId ? (
            <GameView
              sessionId={selectedSessionId}
              activeMenu={activeMenu}
              onWorldlineChange={setWorldlineRate}
            />
          ) : (
            <div className="empty-panel">
              <span className="empty-icon" aria-hidden="true"><Sparkle /></span>
              <h3>从档案柜中取出一卷羊皮纸</h3>
              <p>为这段尚未书写的命运题名，随后将在角色创建的第一步选择时代。</p>
              <div className="era-start-actions">
                <input
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  placeholder="为这段命运题名（可选）"
                  maxLength={200}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") void handleCreateSession();
                  }}
                />
                <button
                  className="primary-button era-start-button"
                  disabled={creating}
                  onClick={() => void handleCreateSession()}
                >
                  {creating
                    ? "羊皮纸正在显字…"
                    : "开始新的游戏"}
                </button>
              </div>
            </div>
          )}
        </section>
      </section>

      <section className="save-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">封存的世界线</p>
            <h2>命运卷宗</h2>
          </div>
        </div>
        <div className="save-grid">
          {sessions.length === 0 ? (
            <div className="save-empty">档案柜仍空空如也。第一卷命运，将从你的名字开始。</div>
          ) : (
            sessions.map((session) => (
              <article
                className={selectedSessionId === session.id ? "save-card selected" : "save-card"}
                key={session.id}
                onClick={() => setSelectedSessionId(session.id)}
              >
                <div className="save-card-icon" aria-hidden="true"><Archive /></div>
                <div>
                  {renamingSessionId === session.id ? (
                    <div className="save-rename" onClick={(event) => event.stopPropagation()}>
                      <input
                        autoFocus
                        maxLength={200}
                        value={renameDraft}
                        onChange={(event) => setRenameDraft(event.target.value)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter") void saveRename(session.id);
                          if (event.key === "Escape") setRenamingSessionId(null);
                        }}
                      />
                      <button disabled={saveManaging} onClick={() => void saveRename(session.id)}>保存</button>
                      <button disabled={saveManaging} onClick={() => setRenamingSessionId(null)}>取消</button>
                    </div>
                  ) : (
                    <h3>{session.name}</h3>
                  )}
                  <p>
                    {(eraById[session.era_id] ?? GENERIC_ERA).years} ·{" "}
                    {session.status === "setup" ? "命运书写中" : "世界线流转中"}
                  </p>
                </div>
                <div className="save-card-actions" onClick={(event) => event.stopPropagation()}>
                  <span className="version">v{session.state_version}</span>
                  <button disabled={saveManaging} onClick={() => beginRename(session)}><PencilSimple aria-hidden="true" />重命名</button>
                  <button className="danger" disabled={saveManaging} onClick={() => void removeSession(session)}><Trash aria-hidden="true" />删除</button>
                </div>
              </article>
            ))
          )}
        </div>
      </section>
    </main>
  );
}

function groupSetupOptions(options: SetupView["current"]["options"]) {
  const groups = new Map<string, typeof options>();
  for (const option of options) {
    const category = option.category || "";
    groups.set(category, [...(groups.get(category) ?? []), option]);
  }
  return Array.from(groups.entries());
}

function SetupSummary({
  answers,
  eras,
}: {
  answers: Record<string, unknown>;
  eras: EraInfo[];
}) {
  const titles: Record<string, string> = {
    "1": "时代",
    "2": "身份",
    "3": "外貌与体格",
    "4": "出身",
    "5": "童年经历",
    "6": "性格",
    "7": "信仰与价值观",
    "8": "魔杖",
    "9": "魔法天赋",
    "10": "宠物",
    "11": "初始好友",
    "12": "剧情起点",
  };
  return (
    <div className="setup-summary">
      {Object.entries(titles).map(([step, title]) => (
        <article key={step}>
          <span>{title}</span>
          <p>
            {step === "1"
              ? formatEraAnswer(answers[step], eras)
              : formatSetupAnswer(answers[step])}
          </p>
        </article>
      ))}
    </div>
  );
}

function formatEraAnswer(answer: unknown, eras: EraInfo[]): string {
  const eraId = String(answer ?? "");
  const era = eras.find((item) => item.id === eraId);
  return era ? `${era.name}（${era.years}）` : formatSetupAnswer(answer);
}

function formatSetupAnswer(answer: unknown): string {
  if (answer === null || answer === undefined || answer === "") return "未填写";
  if (typeof answer === "string") return answer;
  if (Array.isArray(answer)) return answer.join("、");
  if (typeof answer === "object") {
    return Object.entries(answer as Record<string, unknown>)
      .map(([key, value]) => `${key}：${String(value)}`)
      .join("；");
  }
  return String(answer);
}

function displayMessage(value: unknown, fallback: string): string {
  if (typeof value === "string" && value.trim()) return value.trim();
  if (value && typeof value === "object") {
    const objectValue = value as Record<string, unknown>;
    for (const key of ["message", "content", "text", "detail"]) {
      const candidate = objectValue[key];
      if (typeof candidate === "string" && candidate.trim()) return candidate.trim();
    }
  }
  return fallback;
}
