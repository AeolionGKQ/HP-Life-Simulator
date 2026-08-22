import { useEffect, useRef, useState } from "react";
import {
  Archive,
  BookOpenText,
  Envelope,
  GearSix,
  GitBranch,
  GraduationCap,
  Heart,
  MagicWand,
  Medal,
  PencilSimple,
  Plus,
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
  { label: "羁绊", icon: UsersThree },
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
  const configTriggerRef = useRef<HTMLButtonElement>(null);
  const configDialogRef = useRef<HTMLElement>(null);
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

  useEffect(() => {
    if (!configOpen) return;
    const trigger = configTriggerRef.current;
    const dialog = configDialogRef.current;
    if (!dialog) return;

    const focusableSelector = [
      "button:not([disabled])",
      "input:not([disabled])",
      "textarea:not([disabled])",
      "[href]",
      "[tabindex]:not([tabindex='-1'])",
    ].join(",");
    const focusables = () => Array.from(dialog.querySelectorAll<HTMLElement>(focusableSelector));
    const focusFrame = window.requestAnimationFrame(() => focusables()[0]?.focus());

    const handleDialogKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        setConfigOpen(false);
        return;
      }
      if (event.key !== "Tab") return;

      const items = focusables();
      if (items.length === 0) {
        event.preventDefault();
        return;
      }
      const first = items[0];
      const last = items[items.length - 1];
      const active = document.activeElement;
      if (event.shiftKey && (active === first || !dialog.contains(active))) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && active === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", handleDialogKeyDown);
    return () => {
      window.cancelAnimationFrame(focusFrame);
      document.removeEventListener("keydown", handleDialogKeyDown);
      window.requestAnimationFrame(() => trigger?.focus());
    };
  }, [configOpen]);

  const selectedSession = sessions.find((session) => session.id === selectedSessionId);
  const eraById = Object.fromEntries(eras.map((era) => [era.id, era]));
  const currentEra = selectedSession
    ? eraById[selectedSession.era_id] ?? GENERIC_ERA
    : GENERIC_ERA;

  useEffect(() => {
    if (!setup || setup.completed) return;
    const savedAnswer = setup.answers[String(setup.current_step)];
    setSetupAnswer(formatSetupInputAnswer(setup.current_step, savedAnswer));
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
    if (
      !selectedSessionId ||
      !setup ||
      (
        !setupAnswer.trim()
        && setup.current_step !== 13
        && setup.current_step !== 17
      )
    ) return;
    setSetupLoading(true);
    setError("");
    try {
      const next = await api.answerSetup(
        selectedSessionId,
        setup.current_step,
        setupAnswer.trim(),
      );
      setSetup(next);
      if (setup.current_step === 1 && next.era_id) {
        setSessions((current) =>
          current.map((session) =>
            session.id === selectedSessionId
              ? { ...session, era_id: next.era_id }
              : session,
          ),
        );
      }
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
      const message = reason instanceof Error ? reason.message : "初始属性生成失败";
      try {
        const latest = await api.setup(selectedSessionId);
        setSetup(latest);
        setError(message);
      } catch {
        setError(message);
      }
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

  function beginNewSession() {
    setSelectedSessionId(null);
    setSetup(null);
    setSetupAnswer("");
    setName("");
    setError("");
    setWorldlineRate(0);
    setRenamingSessionId(null);
    setRenameDraft("");
    setActiveMenu("角色");
    window.requestAnimationFrame(() => {
      document.querySelector(".empty-panel")?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    });
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
    label: string,
    mode: "single" | "append" | "text" | "confirm",
  ) {
    const inputValue = formatSetupOptionValue(setup?.current_step, value, label);
    if (mode !== "append") {
      setSetupAnswer(inputValue);
      return;
    }
    const values = setupAnswer
      .replaceAll("，", ",")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
    if (!values.includes(inputValue)) values.push(inputValue);
    setSetupAnswer(values.join("，"));
  }

  function isSelectedOption(value: string): boolean {
    const option = setup?.current.options.find(
      (item) => (item.value ?? item.label) === value,
    );
    const inputValue = formatSetupOptionValue(
      setup?.current_step,
      value,
      option?.label ?? value,
    );
    return setupAnswer
      .replaceAll("，", ",")
      .split(",")
      .map((item) => item.trim())
      .includes(inputValue);
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
          <button ref={configTriggerRef} className="config-button" onClick={openConfig}><GearSix aria-hidden="true" />修改 / 测试</button>
        </div>
      </section>

      {error && <div className="error-banner">{error}</div>}

      {configOpen && (
        <div className="modal-backdrop" onClick={() => setConfigOpen(false)}>
          <section
            aria-labelledby="config-title"
            aria-modal="true"
            className="config-modal"
            ref={configDialogRef}
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
            <label>
              Base URL
              <input
                aria-describedby="base-url-hint"
                value={configDraft.base_url}
                onChange={(event) => setConfigDraft({ ...configDraft, base_url: event.target.value })}
                placeholder="https://api.example.com"
              />
              <span className="config-field-hint" id="base-url-hint">
                只填写服务根地址，例如 https://api.openai.com；请勿附加 /v1 或 /v1/chat/completions。
              </span>
            </label>
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
            <span className="state-pill">
              {setup?.completed && setup.attribute_initialization?.status === "ready"
                ? "世界线流转中"
                : setup?.completed && setup.attribute_initialization?.status === "failed"
                  ? "属性校准失败"
                  : "命运尚待书写"}
            </span>
          </div>
          {setup && (!setup.completed || setup.attribute_initialization?.status !== "ready") ? (
            <div className="setup-panel">
              <span className="setup-progress">
                第 {setup.current_step} / {setup.steps_total} 步
              </span>
              <h3>{setup.current.title}</h3>
              <p className="muted">{setup.current.description}</p>
              {setupLoading && setup.current.selection_mode === "confirm" ? (
                <AttributeInitializationLoading />
              ) : setup.current.selection_mode === "confirm" ? (
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
                              aria-pressed={isSelectedOption(value)}
                              className={isSelectedOption(value) ? "setup-option selected" : "setup-option"}
                              disabled={!option.available}
                              key={option.id}
                              onClick={() => option.available && chooseSetupOption(
                                value,
                                option.label,
                                setup.current.selection_mode,
                              )}
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
                {setup.current.selection_mode !== "confirm" ? (
                  <>
                    {setup.current_step !== 1 && setup.current_step !== 14 && setup.current_step !== 15 && (
                      setup.current_step === 4 ? (
                        <input
                          aria-label="生日"
                          autoComplete="bday"
                          type="date"
                          value={setupAnswer}
                          onChange={(event) => setSetupAnswer(event.target.value)}
                        />
                      ) : (
                        <textarea
                          aria-label={setup.current.title}
                          value={setupAnswer}
                          onChange={(event) => setSetupAnswer(event.target.value)}
                          placeholder={
                            setup.current.selection_mode === "append"
                              ? "点击预设会追加到这里，也可以继续输入，用逗号分隔"
                              : setup.current_step === 2
                                ? "输入角色姓名"
                                : setup.current_step === 16
                                  ? "选择上方预设，或写下你的独特守护神"
                                  : setup.current_step === 17
                                    ? "写下任何希望魔法世界记住的角色设定（可留空）"
                                : "选择上方预设，或输入自定义设定"
                          }
                          onKeyDown={(event) => {
                            if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
                              void submitSetupAnswer();
                            }
                          }}
                        />
                      )
                    )}
                    <button
                      className={
                        setup.current_step === 1
                          ? "primary-button setup-era-next"
                          : setup.current_step === 15
                            ? "primary-button setup-single-next"
                            : "primary-button"
                      }
                      disabled={
                        setupLoading ||
                        (
                          !setupAnswer.trim()
                          && setup.current_step !== 13
                          && setup.current_step !== 17
                        )
                      }
                      onClick={() => void submitSetupAnswer()}
                    >
                      {setupLoading
                        ? "保存中…"
                        : setup.current_step === 1
                          ? "以所选世代继续"
                          : setup.current_step === 13 && !setupAnswer.trim()
                            ? "不选择预设好友，继续"
                            : setup.current_step === 17 && !setupAnswer.trim()
                              ? "不再补充，继续"
                            : "下一步"}
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
                  : setup.current.selection_mode !== "confirm" && " 可按 Ctrl + Enter 进入下一步。"}
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
          <button
            aria-label="创建新存档"
            className="secondary-button save-create-button"
            disabled={creating || saveManaging}
            onClick={beginNewSession}
          >
            <Plus aria-hidden="true" />
            创建新存档
          </button>
        </div>
        <div className="save-grid">
          {sessions.length === 0 ? (
            <div className="save-empty">档案柜仍空空如也。第一卷命运，将从你的名字开始。</div>
          ) : (
            sessions.map((session) => (
              <article
                className={selectedSessionId === session.id ? "save-card selected" : "save-card"}
                key={session.id}
              >
                <div className="save-card-icon" aria-hidden="true"><Archive /></div>
                <div className="save-card-body">
                  {renamingSessionId === session.id ? (
                    <>
                      <div className="save-rename">
                        <input
                          aria-label={`重命名存档：${session.name}`}
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
                      <span className="save-card-meta">
                        {(eraById[session.era_id] ?? GENERIC_ERA).years} ·{" "}
                        {session.status === "setup" ? "命运书写中" : "世界线流转中"}
                      </span>
                    </>
                  ) : (
                    <button
                      aria-label={`打开存档：${session.name}`}
                      aria-pressed={selectedSessionId === session.id}
                      className="save-card-open"
                      onClick={() => setSelectedSessionId(session.id)}
                    >
                      <span className="save-card-name">{session.name}</span>
                      <span className="save-card-meta">
                        {(eraById[session.era_id] ?? GENERIC_ERA).years} ·{" "}
                        {session.status === "setup" ? "命运书写中" : "世界线流转中"}
                      </span>
                    </button>
                  )}
                </div>
                <div className="save-card-actions">
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
    "2": "姓名",
    "3": "性别",
    "4": "生日",
    "5": "外貌与体格",
    "6": "出身",
    "7": "童年经历",
    "8": "性格",
    "9": "信仰与价值观",
    "10": "魔杖",
    "11": "魔法天赋",
    "12": "宠物",
    "13": "初始好友",
    "14": "剧情起点",
    "15": "学院",
    "16": "守护神",
    "17": "角色补充",
  };
  return (
    <div className="setup-summary">
      {Object.entries(titles).map(([step, title]) => (
        <article key={step}>
          <span>{title}</span>
          <p>
            {step === "1"
              ? formatEraAnswer(answers[step], eras)
              : step === "14"
                ? formatStartingPointAnswer(answers[step])
              : step === "15"
                ? formatHouseAnswer(answers[step])
              : formatSetupAnswer(answers[step])}
          </p>
        </article>
      ))}
    </div>
  );
}

function AttributeInitializationLoading() {
  return (
    <div className="magic-loading attribute-init-loading" role="status" aria-live="polite">
      <div className="magic-orbit" aria-hidden="true"><MagicWand /></div>
      <h3>命运正在校准你的魔法回响</h3>
      <p>
        学院、出身与天赋的星轨正在交汇，魔法世界正为你测定生命、魔力、精神与五项长期维度……
      </p>
      <small>请稍候，属性校准完成后才会开启你的第一幕故事。</small>
    </div>
  );
}

function formatEraAnswer(answer: unknown, eras: EraInfo[]): string {
  const eraId = String(answer ?? "");
  const era = eras.find((item) => item.id === eraId);
  return era ? `${era.name}（${era.years}）` : formatSetupAnswer(answer);
}

const STARTING_POINT_LABELS: Record<string, string> = {
  owl_letter_arrival: "收到霍格沃茨来信之前",
  before_first_letter: "收到霍格沃茨来信之前",
  before_letter: "收到霍格沃茨来信之前",
  diagon_alley: "第一次踏入对角巷",
  platform_nine_three_quarters: "九又四分之三站台",
  sorting_ceremony: "分院时",
};

const ORIGIN_LABELS: Record<string, string> = {
  pure_blood: "纯血家族",
  half_blood: "混血家庭",
  muggle_born: "麻瓜出身",
};

function formatSetupOptionValue(
  step: number | undefined,
  value: string,
  label: string,
): string {
  return step === 6 ? ORIGIN_LABELS[value] ?? label : value;
}

function formatSetupInputAnswer(step: number, answer: unknown): string {
  if (typeof answer !== "string") return "";
  return step === 6 ? ORIGIN_LABELS[answer] ?? answer : answer;
}

function formatStartingPointAnswer(answer: unknown): string {
  const value = String(answer ?? "");
  return STARTING_POINT_LABELS[value] ?? formatSetupAnswer(answer);
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

function formatHouseAnswer(answer: unknown): string {
  const houses: Record<string, string> = {
    gryffindor: "格兰芬多",
    hufflepuff: "赫奇帕奇",
    ravenclaw: "拉文克劳",
    slytherin: "斯莱特林",
  };
  const value = String(answer ?? "");
  return houses[value] ?? "未选择";
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
