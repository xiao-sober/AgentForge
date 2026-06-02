import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from agentforge.web.app import MAX_REQUEST_BODY_BYTES, create_server


class WebHttpE2ETest(unittest.TestCase):
    def test_chat_endpoint_over_http(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            server = create_server(project_root=root, host="127.0.0.1", port=0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                health = _get_json(f"http://{host}:{port}/health")
                self.assertEqual(health["status"], "ok")

                chat = _post_json(
                    f"http://{host}:{port}/chat",
                    {"message": "hello AgentForge"},
                )
                self.assertIn("response", chat)
                self.assertIn("trace_path", chat)
                self.assertGreater(chat["hqs"]["average_score"], 0)
                self.assertTrue(Path(chat["trace_path"]).exists())

                oversized = Request(
                    f"http://{host}:{port}/chat",
                    data=b"x" * (MAX_REQUEST_BODY_BYTES + 1),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with self.assertRaises(HTTPError) as error:
                    urlopen(oversized, timeout=10)
                self.assertEqual(error.exception.code, 413)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


def _get_json(url: str):
    with urlopen(url, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


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
