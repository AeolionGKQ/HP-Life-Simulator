from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LauncherPaths:
    """All paths used by the launcher and the frozen application."""

    executable_root: Path
    resource_root: Path
    user_data_root: Path
    config_path: Path
    config_template_path: Path
    data_dir: Path
    frontend_dist_dir: Path
    log_dir: Path
    runtime_path: Path

    @classmethod
    def discover(cls) -> "LauncherPaths":
        frozen = bool(getattr(sys, "frozen", False))
        if frozen:
            executable_root = Path(sys.executable).resolve().parent
            resource_root = Path(getattr(sys, "_MEIPASS")).resolve()
        else:
            executable_root = Path(__file__).resolve().parents[1]
            resource_root = executable_root

        user_data_root = executable_root / "user-data" if frozen else executable_root
        return cls(
            executable_root=executable_root,
            resource_root=resource_root,
            user_data_root=user_data_root,
            config_path=(
                user_data_root / "config" / "settings.local.toml"
                if frozen
                else executable_root / "config" / "settings.local.toml"
            ),
            config_template_path=resource_root / "config" / "settings.example.toml",
            data_dir=user_data_root / "data" if frozen else executable_root / "data",
            frontend_dist_dir=resource_root / "frontend" / "dist",
            log_dir=user_data_root / "logs" if frozen else executable_root / "logs",
            runtime_path=(
                user_data_root / "runtime.json"
                if frozen
                else executable_root / ".launcher-runtime.json"
            ),
        )

    @property
    def is_frozen(self) -> bool:
        return bool(getattr(sys, "frozen", False))

    def prepare(self) -> None:
        self.user_data_root.mkdir(parents=True, exist_ok=True)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        if not self.config_path.exists():
            shutil.copyfile(self.config_template_path, self.config_path)

        if not self.user_data_root.is_dir():
            raise OSError(f"用户数据目录不是文件夹：{self.user_data_root}")
        probe = self.user_data_root / ".write-test"
        probe.write_text("", encoding="utf-8")
        probe.unlink()

    def validate_resources(self) -> None:
        required = (
            self.config_template_path,
            self.frontend_dist_dir / "index.html",
        )
        missing = [str(path) for path in required if not path.is_file()]
        if missing:
            raise FileNotFoundError("缺少程序资源：" + "、".join(missing))

    def configure_environment(self) -> None:
        """Set backend overrides before backend.app.main is imported."""
        os.environ["HP_SIMULATOR_CONFIG"] = str(self.config_path)
        os.environ["HP_SIMULATOR_PROJECT_ROOT"] = str(self.executable_root)
        os.environ["HP_SIMULATOR_DATA_DIR"] = str(self.data_dir)
        os.environ["HP_SIMULATOR_FRONTEND_DIST"] = str(self.frontend_dist_dir)
        database_path = (self.data_dir / "game.db").resolve()
        os.environ["HP_SIMULATOR_DATABASE_URL"] = (
            f"sqlite:///{database_path.as_posix()}"
        )
