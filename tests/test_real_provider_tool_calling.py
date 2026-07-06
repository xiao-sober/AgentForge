import json
import os
import unittest
from pathlib import Path

from agentforge.agent.harness import AgentHarness
from agentforge.providers import create_llm_client, load_provider_config


RUN_REAL_PROVIDER_TESTS = os.environ.get("AGENTFORGE_RUN_REAL_PROVIDER_TESTS") == "1"


@unittest.skipUnless(RUN_REAL_PROVIDER_TESTS, "Set AGENTFORGE_RUN_REAL_PROVIDER_TESTS=1 to run real provider tests.")
class RealProviderToolCallingTest(unittest.TestCase):
    def test_real_provider_tool_calling_smoke(self):
        root = Path(os.environ.get("AGENTFORGE_PROJECT_ROOT", Path.cwd())).resolve()
        config_path = root / "config" / "providers.json"
        providers = [
            name.strip()
            for name in os.environ.get("AGENTFORGE_REAL_PROVIDERS", "deepseek_v4_pro,dashscope").split(",")
            if name.strip()
        ]
        if not config_path.exists():
            self.skipTest(f"Missing provider config: {config_path}")

        for provider_name in providers:
            with self.subTest(provider=provider_name):
                config = load_provider_config(config_path, provider_name=provider_name)
                client = create_llm_client(config)
                result = AgentHarness(project_root=root, llm_client=client).tool_chat(
                    "Inspect the latest trace and summarize its status, errors, and final answer source."
                )

                self.assertTrue(result.trace_path.exists())
                self.assertEqual(result.agent_mode, "tool_calling_agent")
                self.assertIn(result.tool_calling.state.status, {"completed", "failed", "blocked", "stopped"})
                trace = json.loads(result.trace_path.read_text(encoding="utf-8"))
                self.assertEqual(trace["type"], "tool_calling_agent")
                self.assertIn("tool_call_timeline", trace["output"])


if __name__ == "__main__":
    unittest.main()
