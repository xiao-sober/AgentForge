import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from agentforge.providers.config import ModelProviderConfig
from agentforge.providers.openai_compatible import OpenAICompatibleChatClient
from agentforge.providers.thinking_modes import ThinkingModeConfig


class CaptureHandler(BaseHTTPRequestHandler):
    request_body = None

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        CaptureHandler.request_body = json.loads(self.rfile.read(length).decode("utf-8"))
        payload = {"choices": [{"message": {"content": "# Skill\n\nGenerated content"}}]}
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format, *args):
        pass


class OpenAICompatibleClientTest(unittest.TestCase):
    def test_sends_qwen_thinking_mode_fields(self):
        server = HTTPServer(("127.0.0.1", 0), CaptureHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            config = ModelProviderConfig(
                name="fake",
                provider_type="openai_compatible",
                base_url=f"http://127.0.0.1:{server.server_port}/v1",
                model="qwen3.6-plus",
                api_key="sk-test",
                thinking_mode=ThinkingModeConfig(
                    enabled=True,
                    provider="qwen",
                    thinking_budget=500,
                    preserve_thinking=True,
                ),
            )

            content = OpenAICompatibleChatClient(config).complete("hello")

            self.assertEqual(content, "# Skill\n\nGenerated content")
            self.assertTrue(CaptureHandler.request_body["enable_thinking"])
            self.assertEqual(CaptureHandler.request_body["thinking_budget"], 500)
            self.assertTrue(CaptureHandler.request_body["preserve_thinking"])
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
