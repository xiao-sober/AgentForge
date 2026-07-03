import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from agentforge.common.llm_client import LLMProviderError
from agentforge.providers.config import ModelProviderConfig
from agentforge.providers.openai_compatible import OpenAICompatibleChatClient
from agentforge.providers.thinking_modes import ThinkingModeConfig


class CaptureHandler(BaseHTTPRequestHandler):
    request_body = None
    request_path = None
    response_status = 200
    response_payload = {"choices": [{"message": {"content": "# Skill\n\nGenerated content"}}]}

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        CaptureHandler.request_body = json.loads(self.rfile.read(length).decode("utf-8"))
        CaptureHandler.request_path = self.path
        payload = CaptureHandler.response_payload
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(CaptureHandler.response_status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format, *args):
        pass


class OpenAICompatibleClientTest(unittest.TestCase):
    def setUp(self):
        CaptureHandler.request_body = None
        CaptureHandler.request_path = None
        CaptureHandler.response_status = 200
        CaptureHandler.response_payload = {"choices": [{"message": {"content": "# Skill\n\nGenerated content"}}]}

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

    def test_sends_deepseek_v4_pro_thinking_request(self):
        CaptureHandler.response_payload = {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "reasoning_content": "hidden reasoning",
                        "content": "Final answer",
                    },
                }
            ]
        }
        server = HTTPServer(("127.0.0.1", 0), CaptureHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            config = ModelProviderConfig(
                name="deepseek_v4_pro",
                provider_type="openai_compatible",
                base_url=f"http://127.0.0.1:{server.server_port}/v1",
                model="DeepSeek-V4-Pro",
                api_key="sk-test",
                thinking_mode=ThinkingModeConfig(
                    enabled=True,
                    provider="deepseek",
                    reasoning_effort="high",
                ),
            )

            content = OpenAICompatibleChatClient(config).complete("hello")

            self.assertEqual(content, "Final answer")
            self.assertEqual(CaptureHandler.request_path, "/v1/chat/completions")
            self.assertEqual(CaptureHandler.request_body["model"], "deepseek-v4-pro")
            self.assertEqual(CaptureHandler.request_body["thinking"], {"type": "enabled"})
            self.assertEqual(CaptureHandler.request_body["reasoning_effort"], "high")
            self.assertNotIn("temperature", CaptureHandler.request_body)
            self.assertNotIn("enable_thinking", CaptureHandler.request_body)
        finally:
            server.shutdown()
            server.server_close()

    def test_sends_deepseek_disabled_thinking_request(self):
        server = HTTPServer(("127.0.0.1", 0), CaptureHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            config = ModelProviderConfig(
                name="deepseek_v4_pro",
                provider_type="openai_compatible",
                base_url=f"http://127.0.0.1:{server.server_port}/v1",
                model="deepseek-v4-pro",
                api_key="sk-test",
                temperature=0.6,
                thinking_mode=ThinkingModeConfig(enabled=False, provider="deepseek"),
            )

            OpenAICompatibleChatClient(config).complete("hello")

            self.assertEqual(CaptureHandler.request_body["thinking"], {"type": "disabled"})
            self.assertEqual(CaptureHandler.request_body["temperature"], 0.6)
        finally:
            server.shutdown()
            server.server_close()

    def test_deepseek_http_error_uses_provider_hint(self):
        CaptureHandler.response_status = 402
        CaptureHandler.response_payload = {"error": {"message": "no balance"}}
        server = HTTPServer(("127.0.0.1", 0), CaptureHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            config = ModelProviderConfig(
                name="deepseek_v4_pro",
                provider_type="openai_compatible",
                base_url=f"http://127.0.0.1:{server.server_port}/v1",
                model="deepseek-v4-pro",
                api_key="sk-test",
            )

            with self.assertRaises(LLMProviderError) as context:
                OpenAICompatibleChatClient(config).complete("hello")

            self.assertIn("insufficient balance", str(context.exception))
        finally:
            server.shutdown()
            server.server_close()

    def test_deepseek_resource_interruption_is_actionable(self):
        CaptureHandler.response_payload = {
            "choices": [
                {
                    "finish_reason": "insufficient_system_resource",
                    "message": {"content": "", "reasoning_content": ""},
                }
            ]
        }
        server = HTTPServer(("127.0.0.1", 0), CaptureHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            config = ModelProviderConfig(
                name="deepseek_v4_pro",
                provider_type="openai_compatible",
                base_url=f"http://127.0.0.1:{server.server_port}/v1",
                model="deepseek-v4-pro",
                api_key="sk-test",
            )

            with self.assertRaises(LLMProviderError) as context:
                OpenAICompatibleChatClient(config).complete("hello")

            self.assertIn("insufficient system resources", str(context.exception))
        finally:
            server.shutdown()
            server.server_close()

    def test_deepseek_v4_default_metadata_reports_provider_default_thinking(self):
        config = ModelProviderConfig(
            name="deepseek_v4_pro",
            provider_type="openai_compatible",
            base_url="https://api.deepseek.com",
            model="deepseek-v4-pro",
            api_key="sk-test",
        )

        metadata = OpenAICompatibleChatClient(config).metadata()

        self.assertEqual(metadata["provider_family"], "deepseek")
        self.assertEqual(metadata["request_model"], "deepseek-v4-pro")
        self.assertEqual(metadata["configured_thinking_mode"]["enabled"], False)
        self.assertEqual(metadata["thinking_mode"]["enabled"], True)
        self.assertEqual(metadata["thinking_mode"]["provider"], "deepseek")
        self.assertEqual(metadata["thinking_mode"]["source"], "provider_default")
        self.assertEqual(metadata["thinking_mode"]["request_body"], {"thinking": "omitted"})

    def test_deepseek_explicit_disabled_metadata_is_preserved(self):
        config = ModelProviderConfig(
            name="deepseek_v4_pro",
            provider_type="openai_compatible",
            base_url="https://api.deepseek.com",
            model="deepseek-v4-pro",
            api_key="sk-test",
            thinking_mode=ThinkingModeConfig(enabled=False, provider="deepseek"),
        )

        metadata = OpenAICompatibleChatClient(config).metadata()

        self.assertEqual(metadata["thinking_mode"]["enabled"], False)
        self.assertEqual(metadata["thinking_mode"]["provider"], "deepseek")
        self.assertEqual(metadata["thinking_mode"]["source"], "explicit_config")
        self.assertEqual(metadata["thinking_mode"]["request_body"], {"thinking": {"type": "disabled"}})

    def test_deepseek_explicit_enabled_metadata_includes_effort(self):
        config = ModelProviderConfig(
            name="deepseek_v4_pro",
            provider_type="openai_compatible",
            base_url="https://api.deepseek.com",
            model="DeepSeek-V4-Pro",
            api_key="sk-test",
            thinking_mode=ThinkingModeConfig(enabled=True, provider="deepseek", reasoning_effort="high"),
        )

        metadata = OpenAICompatibleChatClient(config).metadata()

        self.assertEqual(metadata["request_model"], "deepseek-v4-pro")
        self.assertEqual(metadata["thinking_mode"]["enabled"], True)
        self.assertEqual(metadata["thinking_mode"]["source"], "explicit_config")
        self.assertEqual(metadata["thinking_mode"]["request_body"]["thinking"], {"type": "enabled"})
        self.assertEqual(metadata["thinking_mode"]["request_body"]["reasoning_effort"], "high")


if __name__ == "__main__":
    unittest.main()
