from __future__ import annotations

import logging
import os
import shutil
import sys
import threading
import tkinter as tk
import webbrowser
from datetime import datetime
from tkinter import messagebox

from launcher.instance import (
    InstanceLock,
    clear_runtime,
    read_runtime,
    wait_for_health,
    write_runtime,
)
from launcher.paths import LauncherPaths
from launcher.server import PortableServer


class LauncherWindow:
    def __init__(
        self,
        root: tk.Tk,
        paths: LauncherPaths,
        server: PortableServer,
        instance: InstanceLock,
        logger: logging.Logger,
    ) -> None:
        self.root = root
        self.paths = paths
        self.server = server
        self.instance = instance
        self.logger = logger
        self.status = tk.StringVar(value="正在准备启动……")
        self.open_button = tk.Button(
            root,
            text="打开游戏",
            command=self.open_game,
            state=tk.DISABLED,
        )
        self.archive_button = tk.Button(
            root,
            text="打开存档目录",
            command=self.open_archive,
            state=tk.DISABLED,
        )
        self.log_button = tk.Button(
            root,
            text="打开日志",
            command=self.open_log,
            state=tk.DISABLED,
        )
        self.config_button = tk.Button(
            root,
            text="打开配置目录",
            command=self.open_config,
            state=tk.DISABLED,
        )
        self.reset_button = tk.Button(
            root,
            text="备份并重置配置",
            command=self.reset_config,
            state=tk.DISABLED,
        )
        self.exit_button = tk.Button(root, text="退出游戏", command=self.close)
        self._closed = False
        self._build()
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def _build(self) -> None:
        self.root.title("霍格沃兹人生模拟器")
        self.root.geometry("680x220")
        self.root.resizable(False, False)
        self.root.columnconfigure(0, weight=1)
        tk.Label(
            self.root,
            text="霍格沃兹人生模拟器",
            font=("Microsoft YaHei UI", 15, "bold"),
        ).grid(row=0, column=0, padx=24, pady=(22, 8))
        tk.Label(
            self.root,
            textvariable=self.status,
            wraplength=360,
            justify=tk.CENTER,
            font=("Microsoft YaHei UI", 10),
        ).grid(row=1, column=0, padx=24, pady=4)
        buttons = tk.Frame(self.root)
        buttons.grid(row=2, column=0, padx=20, pady=(14, 20))
        self.open_button.pack(in_=buttons, side=tk.LEFT, padx=4)
        self.archive_button.pack(in_=buttons, side=tk.LEFT, padx=4)
        self.log_button.pack(in_=buttons, side=tk.LEFT, padx=4)
        self.config_button.pack(in_=buttons, side=tk.LEFT, padx=4)
        self.reset_button.pack(in_=buttons, side=tk.LEFT, padx=4)
        self.exit_button.pack(in_=buttons, side=tk.LEFT, padx=4)

    def set_status(self, value: str, *, failed: bool = False) -> None:
        if not self._closed:
            self.root.after(0, self._set_status, value, failed)

    def _set_status(self, value: str, failed: bool) -> None:
        self.status.set(value)
        self.log_button.configure(state=tk.NORMAL if failed else tk.DISABLED)
        self.config_button.configure(state=tk.NORMAL if failed else tk.DISABLED)
        self.reset_button.configure(state=tk.NORMAL if failed else tk.DISABLED)

    def enable_game_buttons(self) -> None:
        self.root.after(
            0,
            lambda: (
                self.open_button.configure(state=tk.NORMAL),
                self.archive_button.configure(state=tk.NORMAL),
            ),
        )

    def open_game(self) -> None:
        if self.server.state.port:
            webbrowser.open(f"http://127.0.0.1:{self.server.state.port}/")

    def open_archive(self) -> None:
        self.paths.data_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(self.paths.data_dir)  # type: ignore[attr-defined]

    def open_log(self) -> None:
        os.startfile(self.paths.log_dir)  # type: ignore[attr-defined]

    def open_config(self) -> None:
        self.paths.config_path.parent.mkdir(parents=True, exist_ok=True)
        os.startfile(self.paths.config_path.parent)  # type: ignore[attr-defined]

    def reset_config(self) -> None:
        if not messagebox.askyesno(
            "备份并重置配置",
            "这会把当前配置备份为带时间戳的文件，并创建新的配置模板。\n确定继续吗？",
            parent=self.root,
        ):
            return
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = self.paths.config_path.with_name(
            f"settings.local.toml.backup-{timestamp}"
        )
        shutil.copyfile(self.paths.config_path, backup)
        shutil.copyfile(self.paths.config_template_path, self.paths.config_path)
        messagebox.showinfo(
            "配置已重置",
            "配置模板已创建，请重新启动游戏后填写模型设置。",
            parent=self.root,
        )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.status.set("正在退出游戏……")
        self.server.stop()
        clear_runtime(self.paths.runtime_path, pid=os.getpid())
        self.instance.release()
        self.root.destroy()


def _show_error(title: str, message: str) -> None:
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(title, message, parent=root)
    root.destroy()


def _open_existing_instance(paths: LauncherPaths) -> int:
    runtime = read_runtime(paths.runtime_path)
    if runtime and isinstance(runtime.get("port"), int):
        if wait_for_health(runtime["port"]):
            webbrowser.open(f"http://127.0.0.1:{runtime['port']}/")
            return 0
    _show_error("霍格沃兹人生模拟器", "游戏正在启动或启动失败，请查看原窗口和日志。")
    return 1


def _startup_worker(window: LauncherWindow) -> None:
    try:
        window.set_status("正在检查程序资源……")
        window.paths.validate_resources()
        window.set_status("正在准备数据目录……")
        window.paths.prepare()
        window.set_status("正在启动本地服务……")
        window.server.start()
        write_runtime(
            window.paths.runtime_path,
            pid=os.getpid(),
            port=window.server.state.port,
        )
        window.set_status("正在等待本地服务就绪……")
        if not window.server.wait_until_ready():
            raise RuntimeError("本地服务启动超时或数据库不可用")
        window.enable_game_buttons()
        game_url = f"http://127.0.0.1:{window.server.state.port}/"
        window.set_status(f"启动完成，可以开始游戏：\n{game_url}")
        if not webbrowser.open(game_url):
            window.set_status("服务已启动，但浏览器未能自动打开。")
    except Exception as error:
        window.logger.exception("启动失败")
        window.set_status("启动失败，请打开日志查看处理建议。", failed=True)
        if not window._closed:
            window.root.after(
                0,
                lambda: messagebox.showerror(
                    "无法启动游戏",
                    "程序资源、数据目录或本地服务启动失败。\n"
                    "请点击“打开日志”查看详细信息，或重新完整解压 ZIP。",
                    parent=window.root,
                ),
            )
        window.logger.error("启动错误类型：%s", type(error).__name__)


def run() -> int:
    paths = LauncherPaths.discover()
    instance = InstanceLock(paths.executable_root)
    if not instance.acquire():
        return _open_existing_instance(paths)

    try:
        paths.validate_resources()
        paths.prepare()
        paths.configure_environment()
        server = PortableServer(paths)
        root = tk.Tk()
        window = LauncherWindow(root, paths, server, instance, server.logger)
        threading.Thread(
            target=_startup_worker,
            args=(window,),
            name="hp-simulator-launcher",
            daemon=True,
        ).start()
        root.mainloop()
        return 0
    except Exception as error:
        try:
            _show_error(
                "无法启动游戏",
                "启动器资源或用户数据目录不可用。\n"
                "请完整解压 ZIP，或将文件夹移动到普通可写目录后重试。",
            )
        except Exception:
            pass
        return 1
    finally:
        instance.release()


if __name__ == "__main__":
    sys.exit(run())
