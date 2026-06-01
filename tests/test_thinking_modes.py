import unittest

from agentforge.providers.thinking_modes import (
    ThinkingModeConfig,
    ThinkingModeConfigError,
    apply_thinking_mode,
    parse_thinking_mode_config,
)


class ThinkingModesTest(unittest.TestCase):
    def test_disabled_mode_leaves_body_unchanged(self):
        body = {"model": "qwen3.6-plus"}

        result = apply_thinking_mode(body, ThinkingModeConfig(enabled=False), "qwen3.6-plus")

        self.assertIs(result, body)
        self.assertNotIn("enable_thinking", body)

    def test_qwen_mode_adds_enable_thinking(self):
        body = {"model": "qwen3.6-plus"}
        config = ThinkingModeConfig(enabled=True, provider="qwen")

        apply_thinking_mode(body, config, "qwen3.6-plus")

        self.assertTrue(body["enable_thinking"])
        self.assertNotIn("thinking_budget", body)

    def test_qwen_mode_adds_budget_and_preserve(self):
        body = {"model": "qwen3.6-plus"}
        config = ThinkingModeConfig(
            enabled=True,
            provider="qwen",
            thinking_budget=500,
            preserve_thinking=True,
        )

        apply_thinking_mode(body, config, "qwen3.6-plus")

        self.assertTrue(body["enable_thinking"])
        self.assertEqual(body["thinking_budget"], 500)
        self.assertTrue(body["preserve_thinking"])

    def test_auto_provider_infers_qwen(self):
        body = {"model": "qwen3.6-plus"}
        config = ThinkingModeConfig(enabled=True, provider="auto")

        apply_thinking_mode(body, config, "qwen3.6-plus")

        self.assertTrue(body["enable_thinking"])

    def test_auto_provider_requires_known_model_family(self):
        with self.assertRaises(ThinkingModeConfigError):
            apply_thinking_mode({}, ThinkingModeConfig(enabled=True, provider="auto"), "unknown-model")

    def test_parse_boolean_shortcut(self):
        config = parse_thinking_mode_config(True, "dashscope")

        self.assertTrue(config.enabled)
        self.assertEqual(config.provider, "auto")


if __name__ == "__main__":
    unittest.main()
