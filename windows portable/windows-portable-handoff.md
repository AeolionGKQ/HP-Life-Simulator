# Windows 便携版交接文档（v3.6）

本文只覆盖 **Windows 便携版（免安装 EXE 包）** 这一条链路。主项目源码端与安卓端各自单独有总结，本文不重复。

## 1. 交付物

- 工作区：`D:\HP Simulator\windows portable`（主项目的隔离副本，已纳入 git 跟踪）
- 最新产物：`D:\HP Simulator\windows portable\HP-Life-Simulator-v3.6-Windows-Portable.zip`
  - 大小 34,427,908 bytes（约 32.8 MiB）
  - SHA-256 `920BB952693CBAF54327A8D89249804D8BC5659E75609B1B6920ED227C78E12E`
- 历史产物同目录保留：`HP-Life-Simulator-v2.7-...zip`、`HP-Life-Simulator-v3.0-...zip`
- 便携链路与主项目原生启动方式（`start_hp_simulator.bat` / `scripts\start_hp_simulator.ps1`）完全独立，互不影响

## 2. 打包方法（当前方案）

**PyInstaller one-folder（COLLECT）+ Tkinter 控制窗口 + 单端口 FastAPI 内嵌 uvicorn。**

- 入口不是后端，而是 `launcher/app.py`：先建目录、设环境变量，再在后台线程里起 uvicorn，主线程跑 Tk 控制窗口
- 前端不带 Vite/Node 运行时：构建期 `npm run build` 出 `frontend/dist`，运行期由 FastAPI 静态托管，**前后端同一个端口**
- 打包为 one-folder（不是单文件 EXE）：启动快、无解压到 temp 的开销；`upx=False`、`console=False`（windowed）
- 打包配置：`packaging/hp_simulator.spec`
  - `hiddenimports = collect_submodules("backend.app")` + 显式 `launcher.*`
  - `datas`：`frontend/dist` → `frontend/dist`，`config/settings.example.toml` → `config`
  - `excludes = ["pytest", "playwright", "tkinter.test"]`
  - EXE 名与文件夹名均为 `霍格沃兹人生模拟器`，带 `packaging/hp-simulator.ico` 图标与 `packaging/version_info.txt` 版本资源
- 压缩：PowerShell `Compress-Archive -CompressionLevel Optimal`，ZIP 内只有一个顶层目录

## 3. 需要安装的工具

构建机（一次性安装）：

- **Windows 10/11 + PowerShell 5.1**（脚本按 5.1 兼容写；注意 5.1 无法可靠解析中文字面量，所以 `build_portable.ps1` 全英文输出，中文文案都放在 Python 脚本里）
- **Python ≥ 3.12**（当前构建机 3.12.13），必须能在 PATH 里以 `python.exe` 调用
- **Node.js + npm**（当前构建机 Node v24.18.0 / npm 11.16.0），需要 `node.exe`、`npm.cmd` 在 PATH
- 无需管理员权限，无需 UPX，无需 Inno Setup / NSIS

脚本自动准备（不用手动装）：

- 临时构建虚拟环境 `portable-build\venv`
- `pip install -e "<workspace>[dev]"`（含 fastapi / uvicorn / sqlalchemy / pydantic / pytest）
- `pip install -r packaging\requirements-build.txt` → `pyinstaller==6.16.0`、`Pillow==11.3.0`

终端用户机：**只需要 Windows**。ZIP 解压即用，不需要 Python / Node / npm，不需要管理员权限（只有调用模型需要联网）。

## 4. 一键构建

```powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "D:\HP Simulator\windows portable\scripts\build_portable.ps1" -Force
```

- 不加 `-Force` 时，若同名 ZIP 已存在会直接报错退出，避免误覆盖
- 全程约 2.5 分钟（本机实测 149 秒）
- 版本号只从 `pyproject.toml` 的 `version` 读取，ZIP 名由它推导：`3.6.0` → `v3.6`，`3.6.1` → `v3.6.1`（第三位非 0 才带上）

`scripts\build_portable.ps1` 的步骤顺序：

1. 校验 `python.exe` / `node.exe` / `npm.cmd` 是否在 PATH
2. 清空 `portable-build\`、`portable-dist\`
3. `python -m venv portable-build\venv`
4. `pip install -e "<workspace>[dev]"` + `pip install -r packaging\requirements-build.txt`
5. `python -m scripts.create_windows_icon` 生成/复用 `packaging\hp-simulator.ico`
6. 写 `packaging\version_info.txt`（Windows 版本资源）
7. `npm ci --no-audit --no-fund` + `npm run build`（产出 `frontend\dist`）
8. 把 `HP_SIMULATOR_CONFIG` 临时指向 `config\settings.example.toml`
9. `python -m scripts.prepare_test_database` 建临时 SQLite 表结构
10. `python -m pytest`（`backend/tests` + `launcher/tests`，v3.6 为 197 passed）——**失败即中止打包**
11. `python -m PyInstaller --clean --noconfirm --distpath portable-dist --workpath portable-build\pyinstaller packaging\hp_simulator.spec`
12. 复制到 `portable-build\stage\` → `python -m scripts.create_player_guide` 写入 `玩家指南.txt` → `Compress-Archive` → `python -m scripts.audit_portable_zip` 审计

所有 Python 调用都走 `python -m 模块`，不用 `python xxx.py`。

## 5. 辅助脚本

- `scripts\create_windows_icon.py`：`packaging\hp-simulator.ico` 已存在且非空则直接复用；否则用安卓 `mipmap-xxxhdpi\ic_launcher.png` 转 ICO；再不行用 Pillow 画一个兜底图标
- `scripts\prepare_test_database.py`：只调 `initialize_database()`，解决构建期 pytest 报 `no such table: game_sessions`
- `scripts\create_player_guide.py`：生成包内中文 `玩家指南.txt`（中文文案放这里，避开 PowerShell 5.1 编码问题）
- `scripts\audit_portable_zip.py`：ZIP 审计，任一条不过返回码 1
  - CRC 校验、必须只有一个顶层目录
  - 必须存在 `霍格沃兹人生模拟器.exe`、`_internal/`、`_internal/frontend/dist/index.html`、`_internal/config/settings.example.toml`、`玩家指南.txt`
  - 禁止出现 `LLM API KEY.txt`、`settings.local.toml`、`game.db`、`.git/`、`.venv/`、`node_modules/` 等
  - 正则扫描疑似密钥（`sk-`、`gh[pousr]_`、`AKIA`）
  - `玩家指南.txt` / `version_info.txt` 里的版本号必须与 `pyproject.toml` 一致

## 6. 产物结构与运行期行为

ZIP 解压后：

```
霍格沃兹人生模拟器\
  霍格沃兹人生模拟器.exe
  玩家指南.txt
  _internal\            # PyInstaller 运行时、后端代码、frontend\dist、config\settings.example.toml
  user-data\            # 首次启动后生成（配置/存档/日志/runtime.json）
```

`launcher/paths.py` 负责冻结态与源码态的路径分流：

- 冻结态：`executable_root = EXE 所在目录`，资源在 `sys._MEIPASS`，用户数据一律写 `EXE 同级 user-data\`
  - `user-data\config\settings.local.toml`（首启从 `settings.example.toml` 复制）
  - `user-data\data\game.db`、`user-data\logs\launcher.log`、`user-data\runtime.json`
- 源码态：直接用仓库里的 `config\`、`data\`、`logs\`，runtime 文件为 `.launcher-runtime.json`
- `configure_environment()` 在**导入 `backend.app.main` 之前**设置 5 个环境变量：`HP_SIMULATOR_CONFIG` / `HP_SIMULATOR_PROJECT_ROOT` / `HP_SIMULATOR_DATA_DIR` / `HP_SIMULATOR_FRONTEND_DIST` / `HP_SIMULATOR_DATABASE_URL`（`get_settings()` 在 import 期就会执行，顺序错了配置就不生效）

其他运行期要点：

- 端口：`launcher/server.py` 先抢占 `127.0.0.1:8000`，占用则退到系统随机端口；**先绑 socket 再 `server.run(sockets=[sock])`**，避免端口竞争。只监听回环地址，不对外暴露
- 就绪判定：必须 `/api/health` 返回 `status == "ok"` **且** `database == "ok"`。健康接口在数据库异常时也返回 HTTP 200，只看状态码会误判
- 单实例：`CreateMutexW` + `GetLastError() == 183`；第二个实例不会重复起服务，而是读 `runtime.json` 的端口、健康探测通过后直接开浏览器
- 退出：控制窗口关闭/「退出游戏」→ `server.stop()` → 删除自己的 `runtime.json` → 释放互斥量。**强杀进程会残留 `runtime.json`**，但下次启动能正常覆盖，不影响使用
- 日志：`user-data\logs\launcher.log`，1 MiB × 3 轮转，写入前用正则脱敏（Authorization/Bearer、api_key、`sk-`、`gh[pousr]_`、`AKIA`）
- 控制窗口所有跨线程 UI 更新都走 `root.after`，含「打开游戏 / 打开存档目录 / 打开日志 / 打开配置目录 / 备份并重置配置 / 退出游戏」

## 7. 从主项目同步代码（每次发版必做）

便携工作区是主项目的副本，同步用 robocopy，注意排除项：

```powershell
robocopy "D:\HP Simulator\backend"  "D:\HP Simulator\windows portable\backend"  /MIR /XD __pycache__ .pytest_cache
robocopy "D:\HP Simulator\frontend" "D:\HP Simulator\windows portable\frontend" /MIR /XD node_modules dist .vite
robocopy "D:\HP Simulator\config"   "D:\HP Simulator\windows portable\config"   /MIR /XF settings.local.toml
```

不要同步 `data\`（存档）和 `config\settings.local.toml`（含 API Key）。

**同步后必须重做的两件事（否则构建能过但功能不对）：**

1. **重新加回 `backend/app/core/config.py` 的环境变量覆盖**——这是便携版唯一的后端专属改动，每次 `/MIR` 都会被主项目版本冲掉。`get_settings()` 结尾需保留：

```python
    runtime_root = os.getenv("HP_SIMULATOR_PROJECT_ROOT")
    project_root = (
        Path(runtime_root).expanduser().resolve() if runtime_root else PROJECT_ROOT
    )
    if frontend_dist := os.getenv("HP_SIMULATOR_FRONTEND_DIST"):
        raw.setdefault("app", {})["frontend_dist_dir"] = frontend_dist
    if data_dir := os.getenv("HP_SIMULATOR_DATA_DIR"):
        raw.setdefault("app", {})["data_dir"] = data_dir
    if database_url := os.getenv("HP_SIMULATOR_DATABASE_URL"):
        raw.setdefault("database", {})["url"] = database_url
    return Settings(**raw, project_root=project_root, config_path=config_path)
```

2. **统一版本号**（v3.6 当前值，六处）：
   - `pyproject.toml` → `version = "3.6.0"`（ZIP 名与审计都以此为准）
   - `backend/app/main.py` → `version="3.6.0"`
   - `frontend/package.json` → `"version": "3.6.0"`
   - `frontend/package-lock.json` → 两处 `"version": "3.6.0"`
   - `launcher/__init__.py` → `__version__ = "3.6.0"`
   - `README.md` → 标题与 ZIP 名
   - `packaging/version_info.txt` 由构建脚本自动改写，不用手动动

## 8. 验收清单

构建脚本已内置 pytest 与 ZIP 审计，人工再补一遍实机冒烟（v3.6 已全部通过）：

1. 解压到临时目录，确认只有一个顶层目录、含 `_internal\` 与 `玩家指南.txt`
2. 双击 EXE，20 秒内 `user-data\runtime.json` 出现且带 pid/port
3. `Invoke-WebRequest http://127.0.0.1:<port>/api/health` → `status=ok, database=ok`
4. `Invoke-WebRequest http://127.0.0.1:<port>/` → 200（前端 dist 正常托管）
5. `/openapi.json` 的 `info.version` 与目标版本一致（v3.6 → `3.6.0`）
6. 关闭控制窗口 → 进程退出且 `runtime.json` 被清理
7. 记录 ZIP 大小与 SHA-256

## 9. 已知问题与注意事项

- 三端（主项目 / 安卓端 / 便携副本）的 `pyproject.toml`、`backend/app/main.py`、`frontend/package.json`（含 `package-lock.json`）已统一到 `3.6.0`，同步时只需核对，不再需要单独修主项目那一处
- 构建日志里的中文是 PowerShell 重定向导致的乱码（GBK/UTF-8 混用），只影响显示，不影响产物；判断成功看退出码与最后一行 `Portable package created:`
- `launcher/tests` 里两个 8000 端口相关用例在端口被外部进程占用时会 `pytest.skip`，属预期行为
- 尚未验证：**完全干净的 Windows 沙箱/虚拟机实跑**（无 Python/Node/npm），以及真实 API Key 的模型连通性（隔离副本里没配真实 Key；`llm_configured` 只判断 `settings.llm.api_key` 非空，模板里的占位值也会让它为 true，不代表能连通）
- 产物 ZIP 目前留在 `windows portable\` 目录下，未复制到项目根目录



