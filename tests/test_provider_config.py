import json
import os
import tempfile
import unittest
from pathlib import Path

from agentforge.providers.config import ProviderConfigError, load_provider_config


class ProviderConfigTest(unittest.TestCase):
    def test_loads_direct_api_key_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "providers.json"
            path.write_text(
                json.dumps(
                    {
                        "default_provider": "dashscope",
                        "providers": {
                            "dashscope": {
                                "type": "openai_compatible",
                                "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                                "api_key": "sk-test",
                                "model": "qwen3.6-plus",
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            config = load_provider_config(path)

            self.assertEqual(config.name, "dashscope")
            self.assertEqual(config.model, "qwen3.6-plus")
            self.assertEqual(config.resolved_api_key(), "sk-test")
            self.assertEqual(config.timeout_seconds, 60)
            self.assertFalse(config.use_env_proxy)
            self.assertFalse(config.thinking_mode.enabled)

    def test_loads_env_template_api_key_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            old_value = os.environ.get("AGENTFORGE_TEST_API_KEY")
            os.environ["AGENTFORGE_TEST_API_KEY"] = "sk-env-test"
            try:
                path = Path(temp_dir) / "providers.json"
                path.write_text(
                    json.dumps(
                        {
                            "default_provider": "example",
                            "providers": {
                                "example": {
                                    "type": "openai_compatible",
                                    "base_url": "https://api.example.com/v1",
                                    "api_key": "${AGENTFORGE_TEST_API_KEY}",
                                    "model": "example-model",
                                }
                            },
                        }
                    ),
                    encoding="utf-8",
                )

                config = load_provider_config(path)

                self.assertEqual(config.resolved_api_key(), "sk-env-test")
            finally:
                if old_value is None:
                    os.environ.pop("AGENTFORGE_TEST_API_KEY", None)
                else:
                    os.environ["AGENTFORGE_TEST_API_KEY"] = old_value

    def test_missing_config_is_actionable(self):
        with self.assertRaises(ProviderConfigError) as context:
            load_provider_config(Path("missing-providers.json"))

        self.assertIn("config/providers.example.json", str(context.exception))

    def test_use_env_proxy_must_be_boolean(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "providers.json"
            path.write_text(
                json.dumps(
                    {
                        "default_provider": "example",
                        "providers": {
                            "example": {
                                "type": "openai_compatible",
                                "base_url": "https://api.example.com/v1",
                                "api_key": "sk-test",
                                "model": "example-model",
                                "use_env_proxy": "false",
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(ProviderConfigError) as context:
                load_provider_config(path)

            self.assertIn("use_env_proxy", str(context.exception))

    def test_loads_qwen_thinking_mode_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "providers.json"
            path.write_text(
                json.dumps(
                    {
                        "default_provider": "dashscope",
                        "providers": {
                            "dashscope": {
                                "type": "openai_compatible",
                                "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                                "api_key": "sk-test",
                                "model": "qwen3.6-plus",
                                "thinking_mode": {
                                    "enabled": True,
                                    "provider": "qwen",
                                    "thinking_budget": 500,
                                    "preserve_thinking": True,
                                },
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            config = load_provider_config(path)

            self.assertTrue(config.thinking_mode.enabled)
            self.assertEqual(config.thinking_mode.provider, "qwen")
            self.assertEqual(config.thinking_mode.thinking_budget, 500)
            self.assertTrue(config.thinking_mode.preserve_thinking)
            self.assertEqual(config.timeout_seconds, 180)

    def test_loads_deepseek_v4_pro_example_config(self):
        old_value = os.environ.get("DEEPSEEK_API_KEY")
        os.environ["DEEPSEEK_API_KEY"] = "sk-deepseek-test"
        try:
            path = Path(__file__).resolve().parents[1] / "config" / "providers.example.json"

            config = load_provider_config(path, provider_name="deepseek_v4_pro")

            self.assertEqual(config.base_url, "https://api.deepseek.com")
            self.assertEqual(config.model, "deepseek-v4-pro")
            self.assertEqual(config.resolved_api_key(), "sk-deepseek-test")
            self.assertEqual(config.timeout_seconds, 300)
            self.assertTrue(config.thinking_mode.enabled)
            self.assertEqual(config.thinking_mode.provider, "deepseek")
            self.assertEqual(config.thinking_mode.reasoning_effort, "high")
        finally:
            if old_value is None:
                os.environ.pop("DEEPSEEK_API_KEY", None)
            else:
                os.environ["DEEPSEEK_API_KEY"] = old_value

    def test_explicit_timeout_overrides_thinking_default(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "providers.json"
            path.write_text(
                json.dumps(
                    {
                        "default_provider": "dashscope",
                        "providers": {
                            "dashscope": {
                                "type": "openai_compatible",
                                "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                                "api_key": "sk-test",
                                "model": "qwen3.7-plus",
                                "timeout_seconds": 240,
                                "thinking_mode": {"enabled": True},
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            config = load_provider_config(path)

            self.assertEqual(config.timeout_seconds, 240)

    def test_thinking_mode_enabled_must_be_boolean(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "providers.json"
            path.write_text(
                json.dumps(
                    {
                        "default_provider": "dashscope",
                        "providers": {
                            "dashscope": {
                                "type": "openai_compatible",
                                "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                                "api_key": "sk-test",
                                "model": "qwen3.6-plus",
                                "thinking_mode": {
                                    "enabled": "true",
                                    "provider": "qwen",
                                },
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(ProviderConfigError) as context:
                load_provider_config(path)

            self.assertIn("thinking_mode.enabled", str(context.exception))


if __name__ == "__main__":
    unittest.main()
