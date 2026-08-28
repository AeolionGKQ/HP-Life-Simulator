# 霍格沃兹人生模拟器 · 源码版（主仓库）交接文档

面向接手主仓库开发的工程师。安卓端（`Andriod Version/`）与便携版（`windows portable/`）另有独立交接文档，本文只覆盖源码版：`backend/` + `frontend/` + 根目录配置与脚本。

## 1. 项目是什么

一个由大模型驱动的哈利波特世界文字人生模拟器。后端是 FastAPI + SQLite 的单机服务，负责会话、世界状态、规则裁决、提示词组装与故事弧长期记忆；前端是 React + Vite 的单页应用。玩家每一次选择都会发一次 LLM 请求，模型返回结构化 JSON，后端用确定性规则把它结算进存档，而不是让模型直接改数值。

四个世代（`backend/app/content/eras.py`）：

- `dumbledore_era`（1890s 戈德里克山谷 / 邓布利多少年时代）
- `parent_generation`（1971—1978 掠夺者时代）
- `second_generation`（1991—1998 子世代）
- `modern`（2020+ 现代世代）

## 2. 目录与模块职责

- `backend/app/main.py` — `create_app()`：CORS（仅放行 `localhost:5173` / `127.0.0.1:5173`）、挂载路由、若 `frontend/dist` 存在则以 `StaticFiles(html=True)` 挂到 `/`。lifespan 里做三件事：建 `data_dir`、`initialize_database()`、`recover_story_arc_jobs()`（重启后修复中断的故事弧任务）。
- `backend/app/core/config.py` — `get_settings()`（`lru_cache`）读取 `config/settings.local.toml`；`HP_SIMULATOR_CONFIG` 环境变量可指定其它路径。**配置文件缺失会直接抛 `RuntimeError`**，这是新环境最常见的第一个报错。
- `backend/app/api/routes.py` — 全部 HTTP 端点，薄薄一层：校验会话存在、调用 service、把 `ValueError` 转 409、把上游异常转 502。
- `backend/app/models/game.py` — SQLAlchemy 模型：`GameSession`、`TurnRecord`、`JournalEntry`、`Relationship`、`NpcProfile`、`MemoryEntry`、`StoryArc`、`StoryArcGenerationJob`。
- `backend/app/schemas/` — Pydantic v2。`game.py` 里是 LLM 响应契约（`NarrativeResponse`、`StoryArcResponse`、`AttributeInitializationResponse`）与对外读模型。
- `backend/app/rules/state.py`（约 1.7k 行）— `apply_turn_rules()`：唯一有权改存档的地方，负责资源/维度/技能/词条/物品/声望/羁绊/年级/课程/生命周期。改玩法规则基本都落在这里。
- `backend/app/rules/timeline.py` — 世界线偏移。历史世代用 `worldline.offset_rate`，`modern` 用 `temporal_disturbance`。
- `backend/app/services/turns.py` — 回合主流程：拼上下文 → 调 provider → 校验 JSON → 裁决 → 落库 → 触发故事弧任务。
- `backend/app/services/setup.py` — 开局问答流程（世代、出身、预设好友、剧情起点、直入终局分支）。
- `backend/app/services/story_arcs.py` — 长期记忆层，详见第 5 节。
- `backend/app/services/sessions.py` — 会话 CRUD、存档导出/导入。
- `backend/app/services/{courses,attributes,memory}.py` — 选课、开局属性初始化、记忆召回。
- `backend/app/content/` — 纯数据层：`mainlines.py`（主线）、`dumbledore_cast.py` / `parent_cast.py` / `modern_cast.py`（角色）、`setup.py`、`attributes.py`、`bonds.py`、`courses.py`、`origins.py`、`reputation.py`、`school.py`、`eras.py`。**文案改动优先落在这里，不要写进 prompts。**
- `backend/app/prompts/turn.py` / `attributes.py` — 系统提示与输出协议。
- `backend/app/providers/openai_compatible.py` — 唯一的 LLM 适配层（OpenAI 兼容接口）。
- `frontend/src/GameView.tsx`（约 1.8k 行）— 游戏主界面：叙事、选项、侧栏（人物卡/纪事/关系/记忆管理等）、故事弧提示条。
- `frontend/src/App.tsx` — 世代选择、存档列表、开局问答、LLM 配置面板。
- `frontend/src/api.ts` — 所有后端调用与 TS 类型，前后端契约的唯一出口。
- `frontend/src/styles.css`、`temporalLabels.ts`（现代世代时间扰动文案）。
- 根目录：`start_hp_simulator.bat` + `scripts/*.ps1`（一键启动）、`config/settings.example.toml`、`pyproject.toml`、`README.md`（面向玩家）。

## 3. 环境与运行

技术栈：Python 3.12+、FastAPI、Pydantic v2、SQLAlchemy 2、SQLite、uvicorn、httpx；React 19、TypeScript、Vite 6、Vitest、Playwright。

**运行规范：一律用 `python -m`，不要 `python xxx.py`。**

```powershell
# 1. 准备配置（必需，settings.local.toml 已 gitignore）
Copy-Item config/settings.example.toml config/settings.local.toml
# 填入 LLM base_url / api_key / model

# 2. 后端（仓库根目录执行）
python -m uvicorn backend.app.main:app --reload --port 8000

# 3. 前端
cd frontend; npm install; npm run dev -- --strictPort
```

也可以直接双击 `start_hp_simulator.bat`（会拉起后端 + 前端并打开浏览器）。

数据库落在 `data/game.db`（gitignore），无迁移框架，靠 `initialize_database()` 建表；改模型字段时要么手动删库重建，要么自己写兼容逻辑。

## 4. 一个回合怎么走

1. 前端 `POST /api/sessions/{id}/actions`，带 `client_action_id`（幂等）与 `expected_state_version`（乐观锁，不匹配报冲突）。
2. `services/turns.py` 组装上下文：世代设定 + 当前存档 + 最近 `recent_narrative_turns`（默认 10，受 `recent_turn_token_limit=12000` 约束）+ 故事弧摘要 + 召回的记忆。
3. 调 provider，要求返回 `NarrativeResponse`。校验失败会带上校验原因重试一次，仍失败抛 `TurnGenerationError`。
4. `apply_turn_rules()` 结算世界状态；写 `TurnRecord` / `JournalEntry` / 关系 / 记忆；`state_version` +1。
5. 满足条件时创建 `StoryArcGenerationJob`。

`kind` 支持 `choice`、`free_text`、`fate_intervention`（干涉命运）、`reshape_fate`（重塑命运：先撤回旧版本带来的变化，再重新结算一次，纪事不会多出重复段落）。

## 5. 故事弧（长期记忆与上下文压缩）

这是全项目最容易踩坑的一块，`backend/app/services/story_arcs.py`。

- 每满 `story_arc_turns`（默认 25）回合，生成一条 `StoryArc`：`title`、`summary`、`causal_chain`、`open_threads`、`key_characters`、`key_locations`、`keywords`、`important_turns`，并记录 `covered_turn_start/end`、`source_turn_ids`、`scope_key`。
- `build_story_arc_context()` 用 `ready_source_turn_ids` 把已被故事弧覆盖的回合从上下文里排除；`recall_story_arcs()` 最多带 3 条（最新一条 + 打分 top2）。这就是上下文压缩的实际机制。
- 生成模式由 `story_arc_mode()` 决定：`parallel`（与玩法并行）或 `queue`。当 provider 不支持并发（`supports_concurrent_requests=False`）时自动降级为 `queue`，此时 `is_story_arc_blocking()` 为真，前端会禁用所有行动按钮并显示提示条。
- 失败恢复：`recover_story_arc_jobs()`（启动时）、`repair_orphaned_story_arc_jobs()`、`POST .../story-arcs/retry`（手动重试）。
- **手动压缩**（`compress_story_arcs()`）：把所有 `status="ready"` 的故事弧精简合并成一条。输入是已有摘要而非原始回合，token 成本低；`covered_turn_start` 取最小、`covered_turn_end` 取最大（1-25 + 26-50 + 51-75 → 1-75），旧弧标记 `status="merged"` 而非删除，`list_story_arc_reads()` 只返回 `ready`，所以展示与召回自然只剩合并后那一条。可反复压缩：`1-75` + 新 `76-100` → `arc-compressed-0001-0100`。程序侧还会做去重、单条截断（summary 4000 字）、条数限流与过期线索过滤（`_compact_text_list(discard_obsolete=True)`，匹配"已解决/已完成/失效"等标记）。入口在前端"记忆管理"面板的"压缩全部故事弧"按钮，少于两条时按钮禁用。
- 压缩期间用进程内 `_compressing_sessions` 防重入；有 `pending`/`generating` 任务时拒绝压缩（409）。

## 6. 其它需要知道的机制

- **学籍**：`not_enrolled` / `year_1..year_7` / `left_school`，配套 `school.enrollment_started`、`sorting_completed`、`grade_started_year`、`active_courses`、`course_history`、`departure_reason`、`departure_notice`。退学/毕业通知要玩家显式确认（`departure-notice/acknowledge`）。
- **直入终局**：邓布利多时代可跳过校园岁月，以成年巫师身份从 `godrics_hollow_1899_summer` / `godrics_hollow_1899_fall` 开局，`life_stage = adult_graduate`。
- **跨端存档**：`SaveExport` / `.hp-save.json`，导入会生成带"（导入）"标记的新会话，不覆盖原档。
- **配置项**（`GameSettings`）：`recent_narrative_turns=10`、`recent_turn_token_limit=12000`、`automatic_memory_recall_limit=6`、`memory_request_limit=5`、`allow_story_arc_parallel_with_gameplay=True`、`story_arc_turns=25`、`story_arc_job_timeout_seconds=900`。

## 7. API 端点（`/api` 前缀，共 31 个）

- 内容与健康：`GET /content/eras`、`GET /health`
- LLM 配置：`GET|PUT /config/llm`、`POST /llm/test`
- 会话：`GET|POST /sessions`、`GET|DELETE /sessions/{id}`、`PATCH /sessions/{id}`（重命名）、`GET /sessions/{id}/export`、`POST /sessions/import`
- 状态与只读数据：`GET /sessions/{id}/state`、`/journal`、`/relationships`、`/npcs`、`/memories`、`/turns`
- 学籍：`POST /sessions/{id}/departure-notice/acknowledge`
- 选课：`GET|PUT /sessions/{id}/courses`
- 故事弧：`GET /sessions/{id}/story-arcs`、`GET .../story-arcs/status`、`POST .../story-arcs/retry`、`POST .../story-arcs/compress`
- 开局：`GET /sessions/{id}/setup`、`POST .../setup/answer`、`POST .../setup/navigate`、`POST .../setup/confirm`、`POST .../attributes/initialize`
- 玩法：`POST /sessions/{id}/actions`

## 8. 测试与校验

```powershell
# 后端：必须从仓库根执行（pyproject 里 testpaths=["backend/tests"]、pythonpath=["."]）
python -m pytest backend/tests -q     # 当前 192 passed

# 前端
cd frontend
npx tsc --noEmit        # 注意：没有 npm run typecheck 这个脚本
npx vitest run          # 单元测试（temporalLabels.test.ts）
npm run test            # Playwright: ui-contract + visual-review（mock 后端）
npm run test:e2e:real   # Playwright: real-backend，需要真实后端与可用 LLM 配置
```

坑：**不要在 `backend/` 目录下执行 `python -m pytest tests`**，会把其它代码树的同名测试也收进来（曾出现 192 vs 190 的假失败）。唯一的告警是 `StarletteDeprecationWarning`（httpx + starlette testclient），无害。

后端测试覆盖：`test_attributes`、`test_bonds`、`test_courses`、`test_health`、`test_mainlines`、`test_reputation`、`test_sessions`、`test_story_arcs`、`test_timeline`、`test_turn_output_contract`。注意 `test_sessions.py` 里有若干**对具体文案的断言**（例如开局起点描述中的关键词），润色文案时会连带失败，改文案要同步改断言。

## 9. 三端同步纪律

仓库里同时存在三套代码树：主仓库、`Andriod Version/`、`windows portable/`。功能改动原则上三端同步，但**不能整体覆盖**：

- 安卓端有自己的兼容层（`backend.app.compat.HTTPException` 与旧版 Pydantic 错误格式）和 Python bridge（`mobile_backend.py` / `mobile_eras.py` / `mobile_setup.py`），直接拷主仓库文件会编译失败。
- 便携版没有 `config/settings.local.toml`（也不该提交），跑它的测试要临时按 example 建一份，**测完立刻删掉**。

## 10. 已知不一致与遗留事项

- 版本号：主仓库 `pyproject.toml`、`backend/app/main.py`、`frontend/package.json` 与 `package-lock.json` 均为 `3.6.0`，与安卓端、便携版一致（安卓 `build.gradle` 为 `versionName "3.6"`）。发版时四处要一起改。
- `README.md` 第 15 行称"邓布利多时代与亲世代的入口暂时关闭"，但 `backend/app/content/eras.py` 中四个世代 `available` 均为 `True`，文档与代码不符。
- 根目录有 10 份规划/变更文档（`context-compression-plan.md`、`story-arc-memory-plan.md`、`重塑命运功能设计与落地计划.md`、邓布利多/亲世代/现代世代的 plan 与 changelog 等）。它们记录了设计意图，但已与实现脱节，建议归档到 `docs/` 或删除。
- 没有数据库迁移方案，改模型即意味着老存档不兼容。
- 没有 CI，测试全靠本地手动跑。

