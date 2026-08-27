from __future__ import annotations

from launcher.instance import (
    clear_runtime,
    mutex_name,
    read_runtime,
    write_runtime,
)


def test_mutex_name_is_stable_and_path_specific(tmp_path) -> None:
    first = mutex_name(tmp_path / "one")
    second = mutex_name(tmp_path / "one")
    other = mutex_name(tmp_path / "two")
    assert first == second
    assert first != other
    assert first.startswith("Local\\HogwartsLifeSimulator-")


def test_runtime_is_atomic_and_pid_guarded(tmp_path) -> None:
    runtime_path = tmp_path / "runtime.json"
    write_runtime(runtime_path, pid=100, port=8000)
    assert read_runtime(runtime_path)["port"] == 8000
    clear_runtime(runtime_path, pid=101)
    assert runtime_path.exists()
    clear_runtime(runtime_path, pid=100)
    assert not runtime_path.exists()
