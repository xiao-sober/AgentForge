from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from agentforge.runs.service import RunService
from agentforge.web.routes import WebResponse, handle_request

MAX_REQUEST_BODY_BYTES = 1_000_000


def create_server(project_root: Path | str = ".", host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    root = Path(project_root).resolve()
    RunService(root).ensure_initialized()

    class AgentForgeHandler(BaseHTTPRequestHandler):
        server_version = "AgentForgeHTTP/0.1"

        def do_GET(self) -> None:  # noqa: N802
            self._handle()

        def do_POST(self) -> None:  # noqa: N802
            self._handle()

        def _handle(self) -> None:
            try:
                body = self._read_body()
            except ValueError as exc:
                self._send_response(
                    WebResponse(
                        status=413,
                        payload={"error": str(exc)},
                        headers={"Content-Type": "application/json; charset=utf-8", "Connection": "close"},
                    )
                )
                self.close_connection = True
                return
            response = handle_request(self.command, self.path, body=body, project_root=root)
            self._send_response(response)

        def _read_body(self) -> bytes:
            content_length = self.headers.get("Content-Length")
            if not content_length:
                return b""
            try:
                byte_count = int(content_length)
            except ValueError as exc:
                raise ValueError("Content-Length must be an integer.") from exc
            if byte_count > MAX_REQUEST_BODY_BYTES:
                self._discard_request_body(byte_count)
                raise ValueError(f"Request body exceeds {MAX_REQUEST_BODY_BYTES} bytes.")
            return self.rfile.read(byte_count)

        def _discard_request_body(self, byte_count: int) -> None:
            remaining = min(byte_count, MAX_REQUEST_BODY_BYTES + 1)
            while remaining > 0:
                chunk = self.rfile.read(min(remaining, 64 * 1024))
                if not chunk:
                    break
                remaining -= len(chunk)

        def _send_response(self, response: WebResponse) -> None:
            body = response.body()
            self.send_response(response.status)
            headers: dict[str, Any] = response.headers or {}
            for key, value in headers.items():
                self.send_header(key, str(value))
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:
            return

    return ThreadingHTTPServer((host, port), AgentForgeHandler)


def run_server(project_root: Path | str = ".", host: str = "127.0.0.1", port: int = 8765) -> None:
    from agentforge_web_backend.main import run_server as run_fastapi_server

    run_fastapi_server(project_root=project_root, host=host, port=port)
