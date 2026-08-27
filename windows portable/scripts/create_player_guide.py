from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    package_root = Path(sys.argv[1])
    version = sys.argv[2]
    guide = f"""霍格沃兹人生模拟器 v{version}

请完整解压整个文件夹，然后双击“霍格沃兹人生模拟器.exe”。
程序不需要安装 Python、Node.js 或 npm，也不需要管理员权限。

首次启动后，配置、存档和日志会保存在本文件夹的 user-data 目录。
模型服务需要联网；没有网络时仍可以打开本地游戏界面和存档目录。

如果启动失败，请在控制窗口中点击“打开日志”，或将整个文件夹移动到桌面、
文档或其他普通可写目录后重试。

当前版本：v{version}
"""
    (package_root / "玩家指南.txt").write_text(guide, encoding="utf-8")


if __name__ == "__main__":
    main()
