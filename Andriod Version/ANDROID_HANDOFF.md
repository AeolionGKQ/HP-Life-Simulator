# 安卓端交接文档（v3.6）

> 本文只覆盖安卓端。PC 源码端与 Windows 便携版另有单独总结，本文不再重复。
>
> 对应版本：`versionName 3.6` / `versionCode 17`，最后一次实机验证时间 2026-08-28。

## 1. 项目定位

安卓端是**完全本地运行**的应用，没有开发者服务器：

- 玩家自行填写 LLM 的 base_url / api_key / model；
- 网络请求由玩家手机直接发往模型服务；
- 存档写入应用私有目录的 SQLite；
- 业务规则、提示词、内容与 PC 端同源。

安卓端全部代码隔离在 `D:\HP Simulator\Andriod Version`，改动不影响 PC 源码端和便携版。

## 2. 目录结构

```text
Andriod Version/
├─ backend/                        # 被打进 APK 的 Python 业务层（Chaquopy 源码根）
│  ├─ app/services/                # 业务逻辑
│  ├─ app/prompts/ app/content/    # 提示词与世代内容
│  ├─ app/compat.py                # 替代 FastAPI 的 HTTPException 等
│  └─ tests/                       # 安卓端自己的 pytest（190 条）
├─ frontend/
│  ├─ src/                         # React 前端
│  ├─ dist/                        # vite 产物，cap sync 会拷进 APK
│  ├─ capacitor.config.ts          # appId=com.hpsimulator.app, webDir=dist
│  └─ android/                     # 原生 Android 工程
│     ├─ variables.gradle          # minSdk 24 / compileSdk 36 / targetSdk 36
│     ├─ build.gradle              # AGP 8.13.0 + Chaquopy 17.0.0
│     ├─ gradle.properties         # 刻意压低内存与并发
│     └─ app/
│        ├─ build.gradle           # 版本号、ABI、Chaquopy 配置
│        └─ src/main/
│           ├─ java/com/hpsimulator/app/PythonBridgePlugin.java
│           └─ python/             # mobile_api / mobile_backend 等桥接层
└─ pyproject.toml
```

## 3. 运行架构

调用链：

```text
React (src/api.ts)
  → isAndroidNative() 为真时走 src/pythonBridge.ts
  → Capacitor 插件 PythonBridge（Java）
  → Chaquopy 内嵌 Python
  → mobile_api.request → mobile_backend.request
  → backend.app.services / prompts / content
  → 本地 SQLite + 玩家自己的 LLM
```

桥接层文件（`frontend/android/app/src/main/python/`）：

| 文件 | 作用 |
| --- | --- |
| `mobile_api.py` | Java 调用入口，只转发 `mobile_backend.request` |
| `mobile_backend.py` | 核心路由表 + 运行时装载 + Pydantic 兼容补丁 |
| `mobile_validation.py` | 启动自检（probe），Java 侧直接加载 |

Java 侧只会 `getModule("mobile_validation")` 和 `getModule("mobile_api")`，业务逻辑一律来自 `backend/`。早期分阶段迁移留下的 `mobile_setup.py` / `mobile_eras.py` / `mobile_origins.py` / `mobile_attributes.py` 已于 2026-08-28 删除——它们无人引用，却是 PC 内容的影子副本，会静默漂移。**不要再往这个目录里放业务规则或世代内容。**

必须知道的几条约束：

1. **Chaquopy 打的是 `Andriod Version/backend`**，由 `app/build.gradle` 的 `srcDir("../../../backend")` 决定，不是 PC 端那份代码。
2. **FastAPI 不进 APK。** `mobile_backend.request()` 用 `if path == ...` 的路由表模拟 PC 的 REST 接口。PC 新增接口后必须在这里补一条，否则前端会报「移动端暂不支持 …」。v3.6 就是补了 `story-arcs/compress`。
3. **安卓内嵌 Pydantic 1.x**，`mobile_backend._patch_pydantic()` 补齐了 `model_validate` / `model_dump` / `model_copy` / `ConfigDict` 等。schema 里不要用 Pydantic 2 独有写法（例如 list 字段上的 `max_length`），否则导入即失败。
4. 运行时会设置 `HP_SIMULATOR_ANDROID=1`，故事弧后台任务因此走独立线程而不是 asyncio task。
5. 运行时装载阶段会调用 `repair_orphaned_story_arc_jobs()`，修复旧存档导入后故事弧不可见的问题。
6. **存档导出必须保持「先写私有 cache 文件 → 只把 token 传给 Activity → 流式写入 SAF 目标」**。不要改回直接把 JSON 当插件参数传，大存档会触发 `TransactionTooLargeException` 闪退并留下 0B 文件。
7. `PythonBridgePlugin` 用 `PYTHON_START_LOCK` 同步 `Python.start()`，避免并发启动竞态。

## 4. 打包方式

当前用的是 **Capacitor + Chaquopy + Gradle 命令行打 debug APK**：

- 不使用 Android Studio；
- 没有配置 release 签名，一直发的是 debug 包（自带 debug 签名，APK Signature Scheme v2 有效）；
- 全部手工执行，没有 CI 和打包脚本。

### 4.1 三步流程

```powershell
# 1. 前端构建 + 同步到原生工程
cd "D:\HP Simulator\Andriod Version\frontend"
npm run build
npx cap sync android

# 2. 指向 JDK 21 并打包
cd "D:\HP Simulator\Andriod Version\frontend\android"
$env:JAVA_HOME='D:\Android\jdk-21'
$env:Path='D:\Android\jdk-21\bin;'+$env:Path
cmd.exe /c gradlew.bat assembleDebug --no-daemon --console=plain
```

产物固定路径：

```text
D:\HP Simulator\Andriod Version\frontend\android\app\build\outputs\apk\debug\app-debug.apk
```

### 4.2 版本号需要同时改的位置

以 v3.6 为例：

- `frontend/android/app/build.gradle`：`versionCode 17`、`versionName "3.6"`
- `frontend/package.json`：`"version": "3.6.0"`
- `frontend/package-lock.json`：顶层两处 `"version": "3.6.0"`
- `pyproject.toml`：`version = "3.6.0"`
- `backend/app/main.py`：`version="3.6.0"`

`versionCode` 必须严格递增，否则覆盖安装会被系统拒绝。

## 5. 需要安装的工具

| 工具 | 版本 | 当前路径 / 说明 |
| --- | --- | --- |
| JDK | OpenJDK / Temurin **21** | `D:\Android\jdk-21`（实测 21.0.12.1）。必须显式设置 `JAVA_HOME`，系统默认 Java 会报「无效的源发行版：21」 |
| Android SDK | Platform **36** | `D:\Android\Sdk` |
| Build Tools | **36.0.0** | `D:\Android\Sdk\build-tools\36.0.0`，提供 `zipalign` / `apksigner` / `aapt` |
| Platform Tools | 随 SDK | `D:\Android\Sdk\platform-tools\adb.exe`，未加入 PATH，需要用绝对路径调用 |
| Gradle | 8.14.3 | 用工程自带 wrapper，无需单独安装 |
| AGP | 8.13.0 | `frontend/android/build.gradle` |
| Chaquopy | 17.0.0 | Gradle 插件，负责把 Python 嵌入 APK |
| Node.js + npm | 支持 Vite 6 的 LTS 版本 | 用于 `npm run build` 与 `npx cap sync` |
| 桌面 Python | **3.12** | Chaquopy 的 `buildPython("python")` 会调用命令行 `python`，版本必须是 3.12，并且能正常 pip 安装 |

首次构建需要联网：Chaquopy 会 pip 安装 `httpx`、`pydantic`、`sqlalchemy`、`tomli-w`。

### 5.1 固定不要随意改的原生配置

- `minSdk 24`、`targetSdk 36`、`compileSdk 36`
- `abiFilters "arm64-v8a"`（只打 64 位 ARM）
- `useLegacyPackaging = true`：为兼容测试机安装器保留压缩的 native 库打包方式
- `gradle.properties` 中 `-Xmx256m`、`-Xint`、`org.gradle.workers.max=1`、`org.gradle.parallel=false`

因为刻意限制了内存和并发，一次全量构建约需 1～2 分钟，属于正常现象。

## 6. 校验与安装

```powershell
$apk = 'D:\HP Simulator\Andriod Version\frontend\android\app\build\outputs\apk\debug\app-debug.apk'
$sdk = 'D:\Android\Sdk'

# 包名 / 版本号 / ABI
& "$sdk\build-tools\36.0.0\aapt.exe" dump badging $apk

# ZIP 对齐
& "$sdk\build-tools\36.0.0\zipalign.exe" -c -P 16 4 $apk

# 签名
$env:JAVA_HOME='D:\Android\jdk-21'
& "$sdk\build-tools\36.0.0\apksigner.bat" verify --verbose $apk

# 校验和
certutil.exe -hashfile $apk SHA256

# 覆盖安装（保留存档）
& "$sdk\platform-tools\adb.exe" -s 912618110264 install --no-streaming -r $apk
```

### 6.1 v3.6 实际结果

- 包名：`com.hpsimulator.app`
- 版本：`versionName 3.6` / `versionCode 17`
- ABI：`arm64-v8a`
- ZIP 对齐：通过
- 签名：APK Signature Scheme v2 通过（v1/v3 为 false，属 debug 包正常表现）
- SHA-256：`be24812b8faccb74b1b553418c79c5f7d03b4ba1b4ae235f6c3cafd4cced769d`
- 体积：约 20.8 MB（21852297 字节）

### 6.2 测试机

- 序列号 `912618110264`，型号 `NX809J`，Android 16
- 安装后实机确认：`versionCode=17`、`versionName=3.6`、进程正常启动、`files/game.db`（约 42 MB）仍在，说明存档未被清除
- 备用设备：`3B1F5CE5MS12LURU` / `PJZ110`

## 7. 测试

安卓端有独立的一套 pytest，跑的是 `Andriod Version/backend`：

```powershell
cd "D:\HP Simulator\Andriod Version"
python -m pytest backend/tests
```

v3.6 打包前结果：**190 passed**。

桥接层语法快速校验：

```powershell
python -m compileall -q backend frontend/android/app/src/main/python
```

前端类型检查已包含在 `npm run build`（`tsc -b && vite build`）中。

## 8. 踩过的坑

1. **JDK 版本**：不设 `JAVA_HOME=D:\Android\jdk-21`，会在 `:capacitor-android:compileDebugJavaWithJavac` 报「无效的源发行版：21」。
2. **PowerShell 5.1**：不支持 `&&`，要用 `;`；带空格的绝对路径必须写成 `& '...'` 调用；`$pid` 是只读内置变量，不能赋值。
3. **adb 安装失败**：这台测试机需要在开发者选项里额外开启「允许通过 USB 安装应用」，否则报 `Caller has no access to session -1`；另外必须加 `--no-streaming`。
4. **PC 改了接口但安卓没跟**：现象是页面报「移动端暂不支持 …」，去 `mobile_backend.py` 补路由。
5. **Pydantic 1/2 差异**：涉及 schema 的改动一定要在安卓端跑一遍测试，PC 通过不代表安卓能导入。
6. **大存档导出**：不要退回「JSON 直接作为插件参数」的写法，会 `TransactionTooLargeException` 闪退。
7. **纪事排序**：`list_journal` 必须用 `outerjoin(TurnRecord)` 并按 `TurnRecord.sequence` 倒序，仅按 `created_at` 排序会让导入存档的纪事顺序错乱。这条曾被后续改动回退过两次，改 `sessions.py` 时要留意。
8. **构建被中途中断**：若终端/agent 在 `:app:packageDebug` 之前挂掉，就不会有新 APK。确认没有残留 java 进程后重跑 `assembleDebug`。
9. **`__pycache__` 差异**：`Andriod Version/backend` 下会有 `.pyc` 造成的 diff，属正常，不要误判为代码不同步。
10. **PC 同步会覆盖安卓专属前端分支**：已经发生过多次——纪事排序被回退两次，存档导出的 `saveTextFile` 分支被换回 PC 的 Blob 下载（导致无法唤出保存位置选择页面），提示条被换成安卓不存在的 `success-banner`（导致样式丢失变成黑白字）。同步后务必按第 9 节的清单复查。

## 9. 与 PC 端的同步检查清单

每次 PC 端有较大更新后，按下面顺序核对安卓端：

1. 用 `git diff --no-index` 逐个比较 `backend/app` 下的同名文件，确认差异只剩下**有意为之**的那几处：
   - `turns.py`：用 `backend.app.compat.HTTPException` 替代 FastAPI，并兼容 `exc.errors(include_url=False)`；
   - `story_arcs.py`：`HP_SIMULATOR_ANDROID=1` 时用线程跑后台任务；
   - `schemas/game.py`：去掉 list 字段上的 `max_length`；
   - `courses.py`：旧存档课程历史的兼容读取；
   - `content/parent_cast.py` 等：安卓端为体积做过紧凑化改写。
2. 确认 PC 新增的接口都在 `mobile_backend.py` 有对应分支，并且前端 `api.ts` 的安卓分支也接上了。
3. **确认安卓专属前端分支没有被 PC 版覆盖**（这类回退已经发生过多次）：

   ```powershell
   cd "D:\HP Simulator"
   git grep -n "pythonBridge" -- "Andriod Version/frontend/src"
   ```

   `App.tsx` 必须仍然导入并使用 `isAndroidNative` / `saveTextFile` / `pickTextFile`：存档导出要走 `saveTextFile`（否则 WebView 里点 `<a download>` 不会唤出系统保存位置选择页面），导入要走 `pickTextFile`，`<input type="file">` 只在非安卓渲染。
4. **确认前端用到的 CSS 类在安卓自己的 `styles.css` 里存在**。两端样式表并不同名同款，PC 的 `success-banner` 在安卓不存在，安卓用的是 `save-notice`；直接搬 PC 的 JSX 会让提示条掉成无样式的黑白文字。可以用下面这段做一次全量核对：

   ```powershell
   cd "D:\HP Simulator\Andriod Version\frontend\src"
   $src = Get-Content -Raw App.tsx, GameView.tsx
   $css = Get-Content -Raw styles.css
   [regex]::Matches($src, 'className="([^"{}]+)"') |
     ForEach-Object { $_.Groups[1].Value -split '\s+' } |
     Sort-Object -Unique |
     Where-Object { $_ -and ($css -notmatch ('\.' + [regex]::Escape($_) + '(?![-\w])')) }
   ```

   已知可以忽略的纯包装类：`course-panel`、`ending-panel`、`romance-list`。
5. 跑 `python -m pytest backend/tests`，并跑一次 `npx tsc -b`。
6. 改版本号 → `npm run build` → `npx cap sync android` → `assembleDebug` → 校验 → 安装 → 实机确认版本与存档。

## 10. 后续可做的事

- 目前仍是 debug 包。要正式发布需创建 release keystore，在 `app/build.gradle` 配 `signingConfigs`，改用 `assembleRelease`。
- 整套流程纯手工，可以写一个脚本把「改版本号 → build → sync → assemble → 校验 → 安装」串起来。
- 只打了 `arm64-v8a`，32 位设备和多数 x86 模拟器装不上；若需要要扩 `abiFilters`（会显著增大体积）。
- `mobile_backend.py` 的路由表是纯手工维护，容易漏。长期看可以考虑用一份接口清单做自动比对。

