from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen


def mutex_name(executable_root: Path) -> str:
    digest = hashlib.sha256(
        str(executable_root.resolve()).casefold().encode("utf-8")
    ).hexdigest()[:32]
    return f"Local\\HogwartsLifeSimulator-{digest}"


class InstanceLock:
    def __init__(self, executable_root: Path) -> None:
        self.executable_root = executable_root
        self._handle: int | None = None
        self._lock_file: Path | None = None

    def acquire(self) -> bool:
        if sys.platform == "win32":
            import ctypes

            kernel32 = ctypes.windll.kernel32
            handle = kernel32.CreateMutexW(
                None,
                False,
                mutex_name(self.executable_root),
            )
            if not handle:
                raise OSError("无法创建单实例互斥量")
            if kernel32.GetLastError() == 183:
                kernel32.CloseHandle(handle)
                return False
            self._handle = handle
            return True

        lock_file = self.executable_root / ".launcher.lock"
        try:
            descriptor = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            return False
        os.close(descriptor)
        self._lock_file = lock_file
        return True

    def release(self) -> None:
        if self._handle is not None and sys.platform == "win32":
            import ctypes

            ctypes.windll.kernel32.CloseHandle(self._handle)
            self._handle = None
        if self._lock_file is not None:
            self._lock_file.unlink(missing_ok=True)
            self._lock_file = None


def write_runtime(path: Path, *, pid: int, port: int) -> None:
    payload = {
        "pid": pid,
        "port": port,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def read_runtime(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def clear_runtime(path: Path, *, pid: int) -> None:
    runtime = read_runtime(path)
    if runtime and runtime.get("pid") == pid:
        path.unlink(missing_ok=True)


def wait_for_health(port: int, timeout_seconds: float = 15.0) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with urlopen(
                f"http://127.0.0.1:{port}/api/health",
                timeout=0.8,
            ) as response:
                if response.status != 200:
                    continue
                payload = json.loads(response.read().decode("utf-8"))
                if payload.get("status") == "ok" and payload.get("database") == "ok":
                    return True
        except (OSError, URLError, ValueError, json.JSONDecodeError):
            pass
        time.sleep(0.2)
    return False
