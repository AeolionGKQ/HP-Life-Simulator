import { useEffect, useState } from "react";
import {
  api,
  type GameSession,
  type HealthResponse,
  type LLMConfigStatus,
  type SetupView,
} from "./api";
import { GameView } from "./GameView";

const menuItems = ["剧情", "角色", "纪事", "恋爱", "好感", "关系", "声望", "课程", "信件", "世界线"];

export function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [llm, setLlm] = useState<LLMConfigStatus | null>(null);
  const [sessions, setSessions] = useState<GameSession[]>([]);
  const [activeMenu, setActiveMenu] = useState("角色");
  const [error, setError] = useState("");
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [setup, setSetup] = useState<SetupView | null>(null);
  const [setupAnswer, setSetupAnswer] = useState("");
  const [setupLoading, setSetupLoading] = useState(false);
  const [worldlineRate, setWorldlineRate] = useState(0);

  useEffect(() => {
    void Promise.all([api.health(), api.llmConfig(), api.sessions()])
      .then(([healthResponse, llmResponse, sessionResponse]) => {
        setHealth(healthResponse);
        setLlm(llmResponse);
        setSessions(sessionResponse);
        if (sessionResponse[0]) setSelectedSessionId(sessionResponse[0].id);
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

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">SECOND GENERATION · LOCAL EDITION</p>
          <h1>霍格沃兹人生模拟器</h1>
        </div>
        <div className="connection-status">
          <span className={`status-dot ${health?.status === "ok" ? "online" : ""}`} />
          {health?.status === "ok" ? "本地服务已连接" : "等待本地服务"}
        </div>
      </header>

      <section className="intro-card">
        <div>
          <p className="eyebrow">1991 · 1998</p>
          <h2>你的故事，从一封信开始。</h2>
          <p className="muted">
            这是 V1 本地运行骨架。角色、纪事和查询菜单会直接读取后端保存的状态，
            剧情回合再交给已配置的主持人模型。
          </p>
        </div>
        <div className="config-card">
          <span>模型服务</span>
          <strong>{llm?.model ?? "未读取"}</strong>
          <small>{llm?.api_key_present ? "API 配置已加载" : "尚未配置 API Key"}</small>
        </div>
      </section>

      {error && <div className="error-banner">{error}</div>}

      <section className="workspace">
        <aside className="sidebar">
          <div className="sidebar-title">
            <span>查询菜单</span>
            <span className="menu-mark">✦</span>
          </div>
          <nav>
            {menuItems.map((item) => (
              <button
                className={activeMenu === item ? "menu-item active" : "menu-item"}
                key={item}
                onClick={() => setActiveMenu(item)}
              >
                {item}
                {item === "世界线" && <span className="worldline-value">{worldlineRate.toFixed(1)}%</span>}
              </button>
            ))}
          </nav>
          <div className="sidebar-note">
            查询菜单不会调用 LLM，也不会推进游戏时间。
          </div>
        </aside>

        <section className="content-card">
          <div className="content-heading">
            <div>
              <p className="eyebrow">CURRENT PANEL</p>
              <h2>{activeMenu}</h2>
            </div>
            <span className="state-pill">{setup?.completed ? "进行中" : "初始化阶段"}</span>
          </div>
          {setup && !setup.completed ? (
            <div className="setup-panel">
              <span className="setup-progress">
                第 {setup.current_step} / {setup.steps_total} 步
              </span>
              <h3>{setup.current.title}</h3>
              <p className="muted">{setup.current.description}</p>
              <div className="setup-options">
                {setup.current.options.map((option) => (
                  <button
                    className="setup-option"
                    key={option.id}
                    onClick={() => setSetupAnswer(option.label)}
                  >
                    <strong>{option.label}</strong>
                    {option.description && <small>{option.description}</small>}
                  </button>
                ))}
              </div>
              <div className="setup-input-row">
                {setup.current_step < 13 ? (
                  <>
                    <input
                      value={setupAnswer}
                      onChange={(event) => setSetupAnswer(event.target.value)}
                      placeholder="选择上方选项，或输入自定义设定"
                      onKeyDown={(event) => {
                        if (event.key === "Enter") void submitSetupAnswer();
                      }}
                    />
                    <button
                      className="primary-button"
                      disabled={setupLoading || !setupAnswer.trim()}
                      onClick={() => void submitSetupAnswer()}
                    >
                      {setupLoading ? "保存中…" : "下一步"}
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
              <p className="setup-hint">当前设定会保存在本地存档中。</p>
            </div>
          ) : setup?.completed && selectedSessionId ? (
            <GameView
              sessionId={selectedSessionId}
              activeMenu={activeMenu}
              onWorldlineChange={setWorldlineRate}
            />
          ) : (
            <div className="empty-panel">
              <span className="empty-icon">✧</span>
              <h3>选择或建立一份人生存档</h3>
              <p>完成角色创建后，这里会展示你的角色与故事状态。</p>
            </div>
          )}
        </section>
      </section>

      <section className="save-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">YOUR STORIES</p>
            <h2>人生存档</h2>
          </div>
          <div className="create-form">
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="存档名称（可选）"
              maxLength={200}
              onKeyDown={(event) => {
                if (event.key === "Enter") void handleCreateSession();
              }}
            />
            <button className="primary-button" disabled={creating} onClick={() => void handleCreateSession()}>
              {creating ? "创建中…" : "新建人生"}
            </button>
          </div>
        </div>
        <div className="save-grid">
          {sessions.length === 0 ? (
            <div className="save-empty">还没有存档。每一段人生，都从一次选择开始。</div>
          ) : (
            sessions.map((session) => (
              <article
                className={selectedSessionId === session.id ? "save-card selected" : "save-card"}
                key={session.id}
                onClick={() => setSelectedSessionId(session.id)}
              >
                <div className="save-card-icon">♜</div>
                <div>
                  <h3>{session.name}</h3>
                  <p>子世代 · {session.status === "setup" ? "角色创建中" : "进行中"}</p>
                </div>
                <span className="version">v{session.state_version}</span>
              </article>
            ))
          )}
        </div>
      </section>
    </main>
  );
}

