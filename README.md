# 霍格沃兹人生模拟器

一个基于 LLM 的纯文本、单人、本地运行巫师人生模拟器。

玩家将在《哈利·波特》系列作品的魔法世界观中创建自己的巫师角色，选择时代、出身、性格、魔杖、天赋与人生起点，并通过持续的剧情选择经历校园生活、人物关系、课程学习、危险事件和世界线变化。

LLM 扮演剧情中的叙事主持者，负责描述场景、扮演 NPC、生成事件和给出选项；程序负责保存事实状态、执行规则、维护存档、校验模型输出并防止剧情状态漂移。

> 当前项目是本地 V1 测试版，核心游戏闭环已经可以运行，内容和规则仍在持续完善。

## 项目特点

- React + TypeScript 前端。
- Python + FastAPI 本地后端。
- SQLite 本地存档。
- 支持 OpenAI-compatible API，也可以连接本机模型服务。
- 单人、本地运行，不包含账号、云存档或多人系统。
- 纯文本体验，不依赖图片生成。
- 每个存档彼此独立。
- 最近剧情原文、结构化当前状态、长期事件记忆和世代主线共同构成 LLM 上下文。
- LLM 只提出状态变化建议，最终状态由后端规则引擎裁决。
- API Key 只保存在本地配置文件，不进入代码、前端资源或 Git 仓库。

## 当前可用功能

### 游戏启动与存档

- Windows 一键启动前后端并自动打开浏览器。
- 启动时进入游戏开始界面，不会自动打开最新存档。
- 创建新存档。
- 选择已有存档。
- 重命名存档。
- 删除存档并级联清理关联数据。
- SQLite 自动保存。
- 刷新页面后恢复当前存档状态。
- 存档之间完全隔离。

双击项目根目录的以下文件即可启动：

```text
start_hp_simulator.bat
```

### 四大世代

项目根据设定文档统一使用以下四个世代：

| 世代 | 时间 | 当前状态 |
| --- | --- | --- |
| 邓布利多时代 | 1892–1899 | 暂不可选择 |
| 亲世代 | 1971–1978 | 暂不可选择 |
| 子世代 | 1991–1998 | 当前开放 |
| 现代 | 2020+ | 暂不可选择 |

四个世代的名称、年份、介绍、氛围和主线统一由后端 `backend/app/content/eras.py` 提供，前端不再维护另一套容易产生差异的世代配置。

当前 V1 只开放子世代。其他世代已经完成前端展示和主线配置，但暂未接入完整后端内容。

### 角色创建

角色创建共 13 步：

1. 时代。
2. 身份。
3. 外貌与体格。
4. 出身。
5. 童年经历。
6. 性格。
7. 信仰与价值观。
8. 魔杖。
9. 魔法天赋。
10. 宠物。
11. 初始好友。
12. 剧情起点。
13. 最终确认。

当前创建流程支持：

- 外貌、体格、童年经历、价值观、魔杖和初始好友预设。
- 性格多选。
- 魔法天赋多选。
- 魔杖木材、杖芯和规格组合选择。
- 点击预设后自动追加到输入区域。
- 多选内容自动去重。
- 自定义姓名、外貌、童年经历、价值观和好友。
- 第一步世代只能通过预设按钮选择，不能手动输入。
- 第十二步支持“分院时”起点。
- 第十三步展示完整角色设定预览。
- 确认后生成玩家状态、基础 NPC 和初始关系。

### 剧情回合

角色创建完成后可以：

- 开始第一幕剧情。
- 选择 LLM 返回的普通选项。
- 在最后一个“其他”选项中输入自由行动。
- 查看选项可能造成的获得/失去效果。
- 等待模型生成时看到魔法风格加载动画。
- 继续推进时间、地点、事件、关系和世界线。

每轮正式剧情响应包含：

- 剧情标题。
- 场景类型。
- 正文叙事。
- 选项列表。
- 选项风险。
- 选项可能造成的物品、状态、技能和词条变化。
- 玩家实际生效的状态变化。
- 世界线偏移率。

内部纪事字段不会直接显示在剧情正文下方，但会保存到后端并可从“纪事”页面查看。

### 玩家状态与词条

当前支持通过剧情获得或失去：

- 物品。
- 临时状态。
- 技能。
- 技能熟练度。
- HP、MP、SP 等生存属性。
- 勇气、智慧、忠诚、野心等基础属性。
- 声望。
- NPC 好感度和信任度。
- 正面词条和负面词条。

词条包含：

- 稳定 ID。
- 名称。
- 正面/负面极性。
- 简短作用描述。
- 来源和获得原因。

词条不会频繁生成。后端每轮最多实际新增两个词条，普通移动和普通对话不会自动添加词条。当前词条会在每轮 Prompt 中传给 LLM，作为剧情推进依据。

### 长期事件记忆

当前采用四层记忆：

1. 权威当前状态：玩家、NPC、关系、物品、时间、世界线等结构化状态。
2. 短期原文：默认最近 10 个叙事回合，并受 token 上限限制。
3. 长期事件记忆：重要秘密、承诺、物品、关系变化、主线、伏笔和重大冲突。
4. 阶段摘要：章节、学期和学年级别的剧情概括。

当前支持：

- 后端根据人物、地点、物品和开放伏笔自动召回长期记忆。
- LLM 在信息不足时返回 `memory_request`。
- 后端最多执行一次内部原文补查。
- 补查不会向玩家显示，不推进时间，不产生额外纪事。
- 记忆原文通过回合 ID 关联，不维护容易失同步的独立文本副本。

### 查询菜单

查询菜单直接读取后端状态，不调用 LLM，也不会推进游戏时间。

当前包含：

- 角色。
- 纪事。
- 关系与好感。
- 恋爱。
- 声望。
- 课程。
- 信件。
- 世界线。

关系与好感已经合并为一个页面。

恋爱页面只展示达到以下阶段的角色：

- 恋爱。
- 恋人。
- 稳定恋情。
- 成年亲密关系。
- 婚姻。
- 已婚。

角色和状态页面使用中文字段解析和卡片展示，不直接显示原始 JSON。

### LLM 配置

页面右上角可以打开模型服务配置窗口，修改：

- Base URL。
- API Key。
- 模型名。

支持：

- 保存到本地 TOML 配置文件。
- 使用当前填写的配置测试连通性。
- 隐藏已有 API Key。
- 连接成功/失败提示。
- OpenAI-compatible Chat Completions 风格接口。

## 仍在开发中的功能

以下功能已经有数据结构、基础接口或部分规则，但还没有达到完整内容版的程度：

- 邓布利多时代完整后端内容。
- 亲世代完整后端内容。
- 现代世代完整后端内容。
- 四个世代的独立角色创建限制和内容包。
- 七学年完整课程、课表和考试内容。
- 完整原著关键节点与大量分支。
- 复杂 NPC 日程和 NPC-NPC 自治关系。
- 丰富的恋爱事件链、表白、拒绝、分手和关系锁内容。
- 完整战斗系统。
- 濒死、救援、死亡和多结局流程的完整内容。
- 职业、毕业后人生和长期家庭系统。
- 更丰富的声望、舆论和传闻传播。
- 动态 NPC 的完整生成规则和长期内容。
- CG、回忆和成就的大规模内容填充。
- SSE 流式剧情输出。
- 更精细的 Prompt token 统计和上下文压缩。
- 前端地图、课程日程和信件操作的完整交互。
- 多模型适配和不同模型的结构化输出兼容性优化。

## 技术架构

```text
React + TypeScript + Vite
            │
            │ HTTP / SSE（SSE 预留）
            ▼
FastAPI 本地后端
            ├── 存档与会话
            ├── 角色创建
            ├── 剧情回合编排
            ├── Prompt 构造
            ├── 长期记忆召回
            ├── 规则引擎
            └── OpenAI-compatible Provider
                    │
                    ▼
             SQLite 本地数据库
```

核心原则：

> LLM 是叙事主持者，程序是事实裁判。

LLM 负责：

- 叙事。
- NPC 扮演。
- 事件和选项生成。
- 状态变化提议。
- 世代主线下的剧情扩展。

后端负责：

- 时间和地点。
- 物品、状态、技能和词条。
- 关系、年龄和恋爱限制。
- 世界线偏移率保存。
- 回合幂等。
- 存档和快照。
- 模型响应校验。

## 运行环境

- Windows 10/11。
- Python 3.12 或更高版本。
- Node.js 和 npm。
- 一个 OpenAI-compatible LLM 服务，或本机兼容服务。

## 配置

复制示例配置：

```powershell
Copy-Item config/settings.example.toml config/settings.local.toml
```

然后编辑：

```text
config/settings.local.toml
```

至少填写：

```toml
[llm]
base_url = "https://api.example.com"
api_key = "your-api-key"
model = "your-model-name"
```

API Key 不要填写到 Python、TypeScript、Prompt、README 或其他会提交到 Git 的文件中。

本地配置和 SQLite 存档已经加入 `.gitignore`：

```text
config/settings.local.toml
data/
```

也可以使用环境变量指定其他配置文件：

```powershell
$env:HP_SIMULATOR_CONFIG = "D:\path\to\settings.local.toml"
```

## 启动方式

### 一键启动（Windows）

直接双击：

```text
start_hp_simulator.bat
```

启动器会：

1. 检查本地配置。
2. 检查 Python 和 npm。
3. 首次运行时安装后端依赖。
4. 首次运行时安装前端依赖。
5. 打开 FastAPI 后端窗口。
6. 打开 Vite 前端窗口。
7. 等待前端端口可用。
8. 自动打开浏览器。

### 手动启动后端

在项目根目录执行：

```powershell
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

后端 API 文档：

```text
http://127.0.0.1:8000/docs
```

### 手动启动前端

另开终端执行：

```powershell
cd frontend
npm install
npm run dev
```

浏览器访问：

```text
http://127.0.0.1:5173
```

## 常用 API

### 系统

```text
GET  /api/health
GET  /api/config/llm
PUT  /api/config/llm
POST /api/llm/test
GET  /api/content/eras
```

### 存档

```text
GET    /api/sessions
POST   /api/sessions
GET    /api/sessions/{session_id}
PATCH  /api/sessions/{session_id}
DELETE /api/sessions/{session_id}
```

### 角色创建

```text
GET  /api/sessions/{session_id}/setup
POST /api/sessions/{session_id}/setup/answer
POST /api/sessions/{session_id}/setup/confirm
```

### 游戏状态

```text
GET  /api/sessions/{session_id}/state
GET  /api/sessions/{session_id}/journal
GET  /api/sessions/{session_id}/relationships
GET  /api/sessions/{session_id}/npcs
GET  /api/sessions/{session_id}/memories
GET  /api/sessions/{session_id}/turns
POST /api/sessions/{session_id}/actions
```

## 数据目录

运行后会自动创建：

```text
data/game.db
```

SQLite 中主要保存：

- 游戏存档。
- 玩家状态。
- NPC 状态。
- 关系。
- 回合记录。
- 纪事。
- 长期事件记忆。
- 阶段摘要。

删除存档会通过后端级联清理该存档的所有关联数据。

## 项目目录

```text
HP Simulator/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI 路由
│   │   ├── content/      # 世代、角色创建和游戏内容
│   │   ├── core/         # 配置和核心设置
│   │   ├── db/           # SQLAlchemy 数据库
│   │   ├── models/       # 数据模型
│   │   ├── prompts/      # LLM Prompt
│   │   ├── providers/    # LLM 服务适配
│   │   ├── rules/        # 状态和游戏规则
│   │   ├── schemas/      # Pydantic 协议
│   │   └── services/     # 业务逻辑
│   └── tests/            # 后端测试
├── config/
│   ├── settings.example.toml
│   └── settings.local.toml  # 本地创建，不提交
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── GameView.tsx
│   │   ├── api.ts
│   │   └── styles.css
│   └── package.json
├── scripts/
│   └── wait_and_open.ps1
├── data/                    # 本地创建，不提交
├── start_hp_simulator.bat
├── pyproject.toml
└── README.md
```

## 测试与构建

运行后端测试：

```powershell
python -m pytest
```

编译检查后端：

```powershell
python -m compileall backend
```

构建前端：

```powershell
cd frontend
npm run build
```

当前测试覆盖：

- 健康检查。
- LLM 配置脱敏。
- 四世代配置。
- 角色创建。
- 多选性格和魔法天赋。
- 分院起点。
- 初始好友和自定义好友。
- 存档重命名。
- 存档删除和级联清理。
- 剧情回合幂等。
- 物品、状态、技能和词条变化。
- 世界线主线注入。
- 模型结构化输出兼容。

## 安全和隐私

- 游戏存档默认只保存在本机。
- 不包含账号、云同步和自动遥测。
- API Key 只写入本地配置。
- API Key 不会由后端状态接口返回。
- LLM 请求内容是否离开本机取决于用户配置的模型服务。
- 如果使用第三方 API，角色状态、剧情和关系信息可能会发送给对应服务商，请根据服务商隐私政策进行配置。

## 内容与版权说明

本项目是基于《哈利·波特》世界观的个人同人游戏原型，不代表官方，也不与权利方关联。

项目使用原创代码、UI 和游戏逻辑。对外发布时应避免未经授权使用电影截图、演员肖像、官方音乐、原著大段文本或官方美术资源。

## 相关文档

- `霍格沃兹人生模拟器_系统规划.md`：完整系统设计。
- `霍格沃兹人生模拟器_V1落地计划.md`：V1 实施计划。
- `霍格沃兹人生模拟器_V1测试版交付说明.md`：当前测试版交付说明。
- `霍格沃兹人生模拟器.docx`：原始世界观和玩法设定。

## 当前项目状态

当前版本可以在本地完成：

```text
启动应用
  → 新建存档
  → 选择子世代
  → 完成角色创建
  → 进入第一幕
  → 调用 LLM
  → 选择行动
  → 更新状态
  → 查看纪事与关系
  → 刷新后恢复存档
```

项目下一阶段重点是扩充世代内容、课程和学年事件、战斗与死亡、NPC 自治、恋爱事件和长期剧情分支。

