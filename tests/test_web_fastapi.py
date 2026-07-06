import json
import socket
import tempfile
import threading
import time
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import uvicorn

from agentforge_web_backend.main import MAX_REQUEST_BODY_BYTES, create_app


class WebFastApiTest(unittest.TestCase):
    def test_fastapi_serves_api_and_frontend(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            frontend_dist = _write_frontend_dist(root)
            host = "127.0.0.1"
            port = _free_port()
            server = uvicorn.Server(
                uvicorn.Config(
                    create_app(project_root=root, frontend_dist=frontend_dist),
                    host=host,
                    port=port,
                    log_level="warning",
                )
            )
            thread = threading.Thread(target=server.run, daemon=True)
            thread.start()
            try:
                _wait_for_json(f"http://{host}:{port}/api/health")

                health = _get_json(f"http://{host}:{port}/api/health")
                self.assertEqual(health["status"], "ok")

                frontend = _get_text(f"http://{host}:{port}/")
                self.assertIn("AgentForge", frontend)
                self.assertIn("/app.js", frontend)

                chat = _post_json(
                    f"http://{host}:{port}/api/chat",
                    {"message": "hello AgentForge"},
                )
                self.assertIn("response", chat)
                self.assertTrue(chat["trace_url"].startswith("/api/traces/"))
                self.assertTrue(Path(chat["trace_path"]).exists())

                legacy_health = _get_json(f"http://{host}:{port}/health")
                self.assertEqual(legacy_health["status"], "ok")

                oversized = Request(
                    f"http://{host}:{port}/api/chat",
                    data=b"x" * (MAX_REQUEST_BODY_BYTES + 1),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with self.assertRaises(HTTPError) as error:
                    urlopen(oversized, timeout=10)
                self.assertEqual(error.exception.code, 413)
            finally:
                server.should_exit = True
                thread.join(timeout=10)

    def test_fastapi_reports_missing_frontend_build(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            host = "127.0.0.1"
            port = _free_port()
            server = uvicorn.Server(
                uvicorn.Config(
                    create_app(project_root=root),
                    host=host,
                    port=port,
                    log_level="warning",
                )
            )
            thread = threading.Thread(target=server.run, daemon=True)
            thread.start()
            try:
                _wait_for_json(f"http://{host}:{port}/api/health")

                with self.assertRaises(HTTPError) as error:
                    urlopen(f"http://{host}:{port}/", timeout=10)
                self.assertEqual(error.exception.code, 503)
                body = error.exception.read().decode("utf-8")
                self.assertIn("frontend is not built", body)
            finally:
                server.should_exit = True
                thread.join(timeout=10)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _write_frontend_dist(root: Path) -> Path:
    dist = root / "apps" / "web" / "frontend" / "dist"
    dist.mkdir(parents=True)
    (dist / "index.html").write_text(
        '<!doctype html><html lang="zh-CN"><body><h1>AgentForge</h1><script type="module" src="/app.js"></script></body></html>',
        encoding="utf-8",
    )
    (dist / "app.js").write_text("console.log('AgentForge');", encoding="utf-8")
    return dist


def _wait_for_json(url: str) -> None:
    deadline = time.time() + 10
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            _get_json(url)
            return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(0.1)
    raise AssertionError(f"Server did not become ready: {last_error}")


def _get_json(url: str):
    return json.loads(_get_text(url))


def _get_text(url: str) -> str:
    with urlopen(url, timeout=10) as response:
        return response.read().decode("utf-8")


def _post_json(url: str, payload):
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
