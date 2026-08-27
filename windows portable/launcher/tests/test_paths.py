from __future__ import annotations

import sys
from pathlib import Path

from launcher.paths import LauncherPaths


def test_source_paths_use_repository_root() -> None:
    paths = LauncherPaths.discover()
    project_root = Path(__file__).resolve().parents[2]
    assert paths.is_frozen is False
    assert paths.executable_root == project_root
    assert paths.config_path == project_root / "config" / "settings.local.toml"
    assert paths.data_dir == project_root / "data"


def test_frozen_paths_use_executable_and_resource_roots(monkeypatch, tmp_path) -> None:
    executable_root = tmp_path / "中文 portable"
    resource_root = tmp_path / "resources"
    executable_root.mkdir()
    resource_root.mkdir()
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(executable_root / "game.exe"))
    monkeypatch.setattr(sys, "_MEIPASS", str(resource_root), raising=False)

    paths = LauncherPaths.discover()

    assert paths.is_frozen is True
    assert paths.executable_root == executable_root
    assert paths.resource_root == resource_root
    assert paths.user_data_root == executable_root / "user-data"
    assert paths.config_path == executable_root / "user-data/config/settings.local.toml"
    assert paths.frontend_dist_dir == resource_root / "frontend/dist"
