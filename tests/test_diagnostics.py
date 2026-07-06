import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agentforge.common.diagnostics import build_config_report


class DiagnosticsTest(unittest.TestCase):
    def test_selected_deepseek_v4_provider_reports_effective_default_thinking(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / "config" / "providers.json"
            config_path.parent.mkdir(parents=True)
            config_path.write_text(
                json.dumps(
                    {
                        "default_provider": "deepseek_v4_pro",
                        "providers": {
                            "deepseek_v4_pro": {
                                "type": "openai_compatible",
                                "base_url": "https://api.deepseek.com",
                                "api_key": "sk-test",
                                "model": "deepseek-v4-pro",
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            report = build_config_report(root)

            selected = report["selected_provider"]
            self.assertEqual(selected["provider"], "deepseek_v4_pro")
            self.assertEqual(selected["thinking_mode"]["enabled"], True)
            self.assertEqual(selected["thinking_mode"]["source"], "provider_default")
            self.assertEqual(selected["configured_thinking_mode"]["enabled"], False)

    def test_config_report_exposes_real_provider_test_gate(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / "config" / "providers.json"
            config_path.parent.mkdir(parents=True)
            config_path.write_text(
                json.dumps(
                    {
                        "default_provider": "deepseek_v4_pro",
                        "providers": {
                            "deepseek_v4_pro": {
                                "type": "openai_compatible",
                                "base_url": "https://api.deepseek.com",
                                "api_key": "sk-test",
                                "model": "deepseek-v4-pro",
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            env = {
                **os.environ,
                "AGENTFORGE_RUN_REAL_PROVIDER_TESTS": "1",
                "AGENTFORGE_REAL_PROVIDERS": "deepseek_v4_pro,dashscope",
            }
            with patch.dict(os.environ, env, clear=True):
                report = build_config_report(root)

            gate = report["real_provider_tests"]
            self.assertEqual(gate["status"], "enabled")
            self.assertTrue(gate["enabled"])
            self.assertEqual(gate["requested_providers"], ["deepseek_v4_pro", "dashscope"])
            self.assertEqual(gate["missing_requested_providers"], ["dashscope"])


if __name__ == "__main__":
    unittest.main()
