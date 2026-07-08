import json
import socket
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from urllib.request import Request, urlopen

import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "web" / "backend"))

from agentforge_web_backend.main import create_app


class WebE2ESmokeTest(unittest.TestCase):
    def test_workbench_observability_e2e_smoke(self):
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
                base_url = f"http://{host}:{port}"
                _wait_for_json(f"{base_url}/api/health")

                index = _get_text(f"{base_url}/")
                self.assertIn("AgentForge", index)

                tools = _get_json(f"{base_url}/api/tools")
                self.assertTrue(any(tool["name"] == "execute_plan" for tool in tools["tools"]))

                task_types = _get_json(f"{base_url}/api/tasks/types")
                task_type_names = {item["task_type"] for item in task_types["task_types"]}
                self.assertTrue({"code_analysis", "document_analysis", "data_analysis"}.issubset(task_type_names))

                chat = _post_json(
                    f"{base_url}/api/chat",
                    {
                        "message": (
                            "Please analyze this Python code:\n"
                            "```python\n"
                            "password = 'secret'\n"
                            "print(password)\n"
                            "```"
                        )
                    },
                )
                self.assertEqual(chat["intent"]["task_type"], "code_analysis")
                self.assertEqual(chat["task_result"]["task_type"], "code_analysis")
                self.assertEqual(chat["task_result"]["status"], "completed")

                chat_run = _get_json(f"{base_url}/api/runs/{chat['run_id']}")
                self.assertEqual(chat_run["run_id"], chat["run_id"])
                self.assertTrue(chat_run["steps"])

                task_run_id = chat["task_result"]["run_id"]
                task_run = _get_json(f"{base_url}/api/runs/{task_run_id}")
                self.assertEqual(task_run["task_type"], "code_analysis")
                self.assertTrue(task_run["workflow_checkpoints"])

                trace_file = Path(chat["trace_path"]).name
                traces = _get_json(f"{base_url}/api/traces")
                self.assertTrue(any(trace["filename"] == trace_file for trace in traces["traces"]))
                trace_detail = _get_json(f"{base_url}/api/traces/{trace_file}")
                self.assertEqual(trace_detail["type"], "agent_chat")

                document_task = _post_json(
                    f"{base_url}/api/tasks",
                    {
                        "task_type": "document_analysis",
                        "input": {"input": "# Release\n\nTODO: finish this section.\n"},
                    },
                )
                self.assertEqual(document_task["status"], "completed")
                document_run = _get_json(f"{base_url}/api/runs/{document_task['run_id']}")
                self.assertEqual(document_run["task_type"], "document_analysis")
                self.assertTrue(document_run["steps"])
                self.assertTrue(document_run["workflow_checkpoints"])

                self.assertIn("episodes", _get_json(f"{base_url}/api/memory/episodes"))
                self.assertIn("semantic_memory", _get_json(f"{base_url}/api/memory/semantic"))
                self.assertIn("current_system_hqs", _get_json(f"{base_url}/api/hqs"))
                self.assertIn("artifacts", _get_json(f"{base_url}/api/runs/{document_task['run_id']}/artifacts"))
                self.assertIn("tool_calls", _get_json(f"{base_url}/api/runs/{document_task['run_id']}/tool-calls"))
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
