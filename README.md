# 霍格沃兹人生模拟器

本项目是纯文本、本地单人运行的 LLM 人生模拟器。当前已完成 V1 的第一阶段骨架：

- FastAPI 本地后端。
- React + TypeScript 前端。
- SQLite 本地存档。
- 独立 TOML 配置。
- OpenAI-compatible LLM Provider。
- 存档创建、列表和详情基础 API。
- 查询菜单的前端基础布局。

## 配置

运行时配置文件是：

```text
config/settings.local.toml
```

API Key 只应放在这个本地文件中，不要写入 Python、TypeScript、Prompt 或提交到版本库。项目已经将该文件加入 `.gitignore`。

如果需要重新配置，可以复制：

```text
config/settings.example.toml
```

然后填写本地模型服务的 `base_url`、`api_key` 和 `model`。

也可以通过 `HP_SIMULATOR_CONFIG` 环境变量指定另一份 TOML 配置文件。

## 启动后端

在 Windows 下，也可以直接双击项目根目录的：

```text
start_hp_simulator.bat
```

启动器会自动检查配置和依赖，分别打开后端、前端窗口，并在前端可访问后自动打开浏览器。首次运行如果尚未安装依赖，启动器会先自动安装。

在项目根目录执行：

```powershell
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

后端启动时会自动创建：

```text
data/game.db
```

接口文档地址：

```text
http://127.0.0.1:8000/docs
```

## 启动前端开发服务器

```powershell
cd frontend
npm run dev
```

打开：

```text
http://127.0.0.1:5173
```

前端开发服务器会把 `/api` 请求代理到本地 FastAPI。

## 验证

后端测试：

```powershell
python -m pytest
```

前端构建：

```powershell
cd frontend
npm run build
```

测试模型连接：

```text
POST http://127.0.0.1:8000/api/llm/test
```

该接口只返回连接是否成功、模型名、响应耗时和脱敏提示，不返回 API Key。

