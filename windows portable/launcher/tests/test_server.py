from __future__ import annotations

import socket

from launcher.paths import LauncherPaths
from launcher.server import PortableServer


def make_paths(tmp_path) -> LauncherPaths:
    return LauncherPaths(
        executable_root=tmp_path,
        resource_root=tmp_path,
        user_data_root=tmp_path / "user-data",
        config_path=tmp_path / "user-data/config/settings.local.toml",
        config_template_path=tmp_path / "config/settings.example.toml",
        data_dir=tmp_path / "user-data/data",
        frontend_dist_dir=tmp_path / "frontend/dist",
        log_dir=tmp_path / "user-data/logs",
        runtime_path=tmp_path / "user-data/runtime.json",
    )


def test_server_prefers_8000_when_available(tmp_path) -> None:
    server = PortableServer(make_paths(tmp_path))
    port = server.bind_socket()
    if port != 8000:
        server.stop()
        import pytest

        pytest.skip("port 8000 is already occupied by an external process")
    assert port == 8000
    server.stop()


def test_bind_socket_falls_back_when_8000_is_occupied(tmp_path) -> None:
    occupied = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        occupied.bind(("127.0.0.1", 8000))
    except OSError:
        occupied.close()
        import pytest

        pytest.skip("port 8000 is already occupied by an external process")
    occupied.listen()
    try:
        server = PortableServer(make_paths(tmp_path))
        port = server.bind_socket()
        assert port != 8000
        server.stop()
    finally:
        occupied.close()
