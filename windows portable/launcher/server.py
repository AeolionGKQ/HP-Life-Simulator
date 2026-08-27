from __future__ import annotations

import json
import logging
import socket
import threading
import time
from dataclasses import dataclass
from urllib.error import URLError
from urllib.request import urlopen

from .logging_config import configure_logging
from .paths import LauncherPaths


@dataclass
class ServerState:
    port: int = 0
    ready: bool = False
    error: Exception | None = None


class PortableServer:
    def __init__(self, paths: LauncherPaths) -> None:
        self.paths = paths
        self.logger = configure_logging(paths.log_dir)
        self.state = ServerState()
        self._socket: socket.socket | None = None
        self._server = None
        self._thread: threading.Thread | None = None
        self._stopped = threading.Event()

    def bind_socket(self) -> int:
        server_socket: socket.socket
        preferred_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            preferred_socket.bind(("127.0.0.1", 8000))
            server_socket = preferred_socket
        except OSError:
            preferred_socket.close()
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.bind(("127.0.0.1", 0))
        server_socket.listen(2048)
        server_socket.set_inheritable(False)
        self._socket = server_socket
        self.state.port = int(server_socket.getsockname()[1])
        return self.state.port

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeError("本地服务已经启动")
        self.paths.configure_environment()
        self.bind_socket()
        self._thread = threading.Thread(
            target=self._run,
            name="hp-simulator-server",
            daemon=True,
        )
        self._thread.start()

    def _run(self) -> None:
        try:
            import uvicorn

            config = uvicorn.Config(
                "backend.app.main:app",
                host="127.0.0.1",
                port=self.state.port,
                log_config=None,
                access_log=False,
                server_header=False,
                date_header=False,
            )
            self._server = uvicorn.Server(config)
            self._server.run(sockets=[self._socket])
        except Exception as error:
            self.state.error = error
            self.logger.exception("本地服务线程异常")
        finally:
            self._stopped.set()

    def wait_until_ready(self, timeout_seconds: float = 30.0) -> bool:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if self.state.error is not None:
                return False
            if self.state.port and self._health_ok(self.state.port):
                self.state.ready = True
                return True
            if self._stopped.is_set():
                return False
            time.sleep(0.25)
        return False

    @staticmethod
    def _health_ok(port: int) -> bool:
        try:
            with urlopen(
                f"http://127.0.0.1:{port}/api/health",
                timeout=1,
            ) as response:
                if response.status != 200:
                    return False
                payload = json.loads(response.read().decode("utf-8"))
                return (
                    payload.get("status") == "ok"
                    and payload.get("database") == "ok"
                )
        except (OSError, URLError, ValueError, json.JSONDecodeError):
            return False

    def stop(self, timeout_seconds: float = 8.0) -> bool:
        if self._server is not None:
            self._server.should_exit = True
        if self._thread is not None:
            self._thread.join(timeout_seconds)
        stopped = self._thread is None or not self._thread.is_alive()
        if not stopped:
            self.logger.error("本地服务退出超时，未执行外部进程终止")
        if self._socket is not None:
            self._socket.close()
            self._socket = None
        return stopped
