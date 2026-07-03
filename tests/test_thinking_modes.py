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

    def test_deepseek_mode_adds_thinking_and_effort(self):
        body = {"model": "deepseek-v4-pro"}
        config = ThinkingModeConfig(enabled=True, provider="deepseek", reasoning_effort="high")

        apply_thinking_mode(body, config, "deepseek-v4-pro")

        self.assertEqual(body["thinking"], {"type": "enabled"})
        self.assertEqual(body["reasoning_effort"], "high")
        self.assertNotIn("enable_thinking", body)

    def test_auto_provider_infers_deepseek(self):
        body = {"model": "deepseek-v4-pro"}
        config = ThinkingModeConfig(enabled=True, provider="auto", reasoning_effort="max")

        apply_thinking_mode(body, config, "deepseek-v4-pro")

        self.assertEqual(body["thinking"], {"type": "enabled"})
        self.assertEqual(body["reasoning_effort"], "max")

    def test_deepseek_disabled_mode_is_explicit(self):
        body = {"model": "deepseek-v4-pro", "reasoning_effort": "high"}
        config = ThinkingModeConfig(enabled=False, provider="deepseek")

        apply_thinking_mode(body, config, "deepseek-v4-pro")

        self.assertEqual(body["thinking"], {"type": "disabled"})
        self.assertNotIn("reasoning_effort", body)

    def test_deepseek_rejects_qwen_only_options(self):
        body = {"model": "deepseek-v4-pro"}
        config = ThinkingModeConfig(enabled=True, provider="deepseek", thinking_budget=500)

        with self.assertRaises(ThinkingModeConfigError):
            apply_thinking_mode(body, config, "deepseek-v4-pro")

    def test_auto_provider_requires_known_model_family(self):
        with self.assertRaises(ThinkingModeConfigError):
            apply_thinking_mode({}, ThinkingModeConfig(enabled=True, provider="auto"), "unknown-model")

    def test_parse_boolean_shortcut(self):
        config = parse_thinking_mode_config(True, "dashscope")

        self.assertTrue(config.enabled)
        self.assertEqual(config.provider, "auto")
        self.assertTrue(config.configured)

    def test_parse_reasoning_effort(self):
        config = parse_thinking_mode_config(
            {"enabled": True, "provider": "deepseek", "reasoning_effort": "MAX"},
            "deepseek_v4_pro",
        )

        self.assertEqual(config.reasoning_effort, "max")


if __name__ == "__main__":
    unittest.main()
