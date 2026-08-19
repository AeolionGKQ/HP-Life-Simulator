# Magic Archive Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 HP Life Simulator 的测试前端重构为电影感魔法档案界面，同时保持全部游戏行为和后端连接不变。

**Architecture:** 保留现有 `App` 与 `GameView` 的状态和 API 边界，只为结构增加语义标签、样式钩子和统一图标，再以单一 CSS 设计系统完成桌面、平板和移动端布局。Playwright 使用完整 API 形状的路由夹具提供确定性界面状态，真实后端另做连通验证。

**Tech Stack:** React 19、TypeScript、Vite 6、CSS、Phosphor Icons、Playwright、Vitest、FastAPI

**Spec:** `docs/superpowers/specs/2026-08-19-magic-archive-frontend-design.md`

## Global Constraints

- 不修改 `frontend/src/api.ts`、后端接口、数据库结构、LLM 配置格式、游戏状态转换、菜单名称、角色创建步骤和 API 请求负载。
- 固定夜间主题；琥珀金是唯一品牌强调色；不使用通用 AI 紫色渐变。
- 新增且仅新增一个生产依赖 `@phosphor-icons/react`；动效只用 CSS。
- 所有非必要动效必须支持 `prefers-reduced-motion: reduce`。
- Playwright 不创建或删除真实用户存档，也不读取、输出或截图 API Key。

---

### Task 1: 固化工具链与前端语义契约

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`
- Create: `frontend/playwright.config.ts`
- Create: `frontend/tests/ui-contract.spec.ts`

**Interfaces:**
- Consumes: Vite 开发服务器 `http://127.0.0.1:5173` 与现有 `/api/*` 请求。
- Produces: `npm run test:e2e` 脚本和 Playwright 测试入口；页面必须暴露名称为“魔法档案导航”的导航区以及名称为“模型服务配置”的对话框。

- [ ] **Step 1: 安装确定版本的依赖并登记脚本**

  运行 `npm install @phosphor-icons/react@^2.1.10` 和 `npm install -D @playwright/test@^1.54.2`，在 `package.json` 增加 `"test:e2e": "playwright test"`。

- [ ] **Step 2: 添加 Playwright 配置**

  配置 `testDir: "./tests"`、`baseURL: "http://127.0.0.1:5173"`、失败时保留截图，并用 Windows Node 直接启动 `node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5173 --strictPort`。

- [ ] **Step 3: 写入失败的语义契约测试**

  测试在访问页面前拦截 `/api/health`、`/api/config/llm`、`/api/sessions`、`/api/content/eras`，返回完整字段夹具；断言：页面存在一级标题、名称为“魔法档案导航”的 `navigation`、打开设置后存在名称为“模型服务配置”的 `dialog`、关闭按钮具有可访问名称。

- [ ] **Step 4: 运行测试并确认因缺少语义结构而失败**

  运行 `npx playwright test tests/ui-contract.spec.ts --project=chromium`。预期失败点为当前页面没有命名导航或标准对话框，而不是服务器或夹具错误。

### Task 2: 实现应用外壳与魔法档案设计系统

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/styles.css`
- Test: `frontend/tests/ui-contract.spec.ts`

**Interfaces:**
- Consumes: 现有 `App` 状态、`api` 方法和 Task 1 的语义契约。
- Produces: `nav[aria-label="魔法档案导航"]`、`div[role="dialog"][aria-labelledby="config-title"]`、一致的 Phosphor 图标和完整响应式外壳。

- [ ] **Step 1: 只调整 App 表现层结构**

  为顶部、欢迎区、侧栏、内容区、存档区和弹窗增加语义元素与样式钩子；用 Phosphor 的 `Sparkle`、`BookOpenText`、`GearSix`、`WifiHigh`、`Archive`、`PencilSimple`、`Trash`、`X` 等图标替换装饰字符。保留所有事件处理器、请求和状态判断原样。

- [ ] **Step 2: 建立 CSS token 与桌面布局**

  在 `:root` 定义画布、表面、发丝线、正文、次要文字、琥珀金和语义色 token；设置双字体栈、1360px 外壳、两列工作区、阅读宽度、按钮状态、表单焦点和小圆角体系。

- [ ] **Step 3: 完成平板与移动布局**

  在 900px 和 640px 断点下将侧栏变为横向档案标签，将顶部、欢迎区、创建操作和存档垂直重排；确保触控目标至少 44px，并防止横向溢出。

- [ ] **Step 4: 增加动效保护**

  为页面进入、加载符号、按钮和弹窗使用克制 CSS 动效，并在 `prefers-reduced-motion: reduce` 中禁用动画和非必要过渡。

- [ ] **Step 5: 运行语义契约与生产构建**

  运行 `npx playwright test tests/ui-contract.spec.ts --project=chromium`，预期全部通过；运行 `npm run build`，预期 TypeScript 和 Vite 构建退出码为 0。

### Task 3: 重构剧情、查询与角色创建的视觉层级

**Files:**
- Modify: `frontend/src/GameView.tsx`
- Modify: `frontend/src/styles.css`
- Create: `frontend/tests/visual-review.spec.ts`

**Interfaces:**
- Consumes: `GameViewProps`、`PlayerStateResponse`、`JournalEntry`、`Relationship`、`NPCState`、`StoredTurn` 和 Task 2 的 CSS token。
- Produces: 保持原有操作负载的剧情、角色、纪事、关系、恋爱、声望、课程、信件和世界线视图；截图输出到 `frontend/test-results/visual-review/`。

- [ ] **Step 1: 调整 GameView 表现层**

  用语义标题、档案元数据、状态格、阅读容器和 Phosphor 图标重排现有 JSX；保留 `submitAction`、查询映射、选择与自由文本提交逻辑原样。

- [ ] **Step 2: 完成游戏内容样式**

  为剧情正文、选择项、变化提示、属性格、列表、关系、特质、创建选项和世界线建立统一层级；选项收益、损失和说明继续使用独立语义色。

- [ ] **Step 3: 添加完整状态夹具**

  在 `visual-review.spec.ts` 中返回完整的健康、LLM、时代、会话、创建步骤、玩家状态、纪事、关系、NPC 与回合结构；所有 POST/PUT/PATCH/DELETE 请求直接返回对应完整夹具，不落盘。

- [ ] **Step 4: 生成确定性截图**

  在 1440x1000 和 390x844 两个 viewport 下截取首页、配置弹窗、创建向导和剧情视图；隐藏或固定可能变化的时间信息，截图使用固定名称。

- [ ] **Step 5: 审查并修正视觉缺陷**

  逐张检查文字重叠、横向溢出、截断、低对比、选中态、移动端触控和弹窗边界。发现缺陷时先为可自动验证的问题增加失败断言，再修改 JSX 或 CSS 并重新截图。

### Task 4: 后端集成与最终验证

**Files:**
- Verify: `frontend/src/api.ts` 未改变
- Verify: `backend/`
- Verify: `frontend/`

**Interfaces:**
- Consumes: Windows `.venv`、Windows Node/npm、FastAPI 8000 端口和 Vite 5173 端口。
- Produces: 可从 `Start HP Simulator.bat` 启动并连接真实后端的最终工作树。

- [ ] **Step 1: 运行后端测试**

  使用 `D:\HP Simulator\.venv\Scripts\python.exe -m pytest -q`，要求 0 failures。

- [ ] **Step 2: 运行全部前端验证**

  使用 Windows Node 环境运行 `npm run build` 和 `npm run test:e2e`，要求退出码均为 0。

- [ ] **Step 3: 真实启动并验证接口**

  启动 FastAPI 127.0.0.1:8000 和 Vite 127.0.0.1:5173；通过浏览器访问前端，确认健康状态与 LLM 已配置状态来自真实后端。只检查 `api_key_present`，不输出密钥。

- [ ] **Step 4: 做设计自测清单**

  按 `design-taste-frontend` 检查：单一强调色、圆角一致、无装饰性 emoji、无 CTA 换行、焦点可见、移动端 44px 触控、无意外横向溢出、减少动态效果生效、所有按钮状态明确。

- [ ] **Step 5: 检查差异与清理测试进程**

  运行 `git diff --check`、`git status --short` 和 `git diff -- frontend/src/api.ts`；要求无空白错误、`api.ts` 无差异。精确终止本轮 5173/8000 测试进程并确认端口释放。

