import unittest

from agentforge.agent.intent_parser import parse_intent


class IntentParserTest(unittest.TestCase):
    def test_detects_skill_generation(self):
        intent = parse_intent("Please generate Skill for UI review.")

        self.assertEqual(intent.intent_type, "generate_skill")
        self.assertTrue(intent.needs_skill_generation)
        self.assertEqual(intent.skill_hint, "ui_review_skill")

    def test_detects_english_skill_generation_with_article(self):
        intent = parse_intent("Generate a Skill for API response contract review.")

        self.assertEqual(intent.intent_type, "generate_skill")
        self.assertTrue(intent.needs_skill_generation)
        self.assertFalse(intent.requires_skill)
        self.assertEqual(intent.skill_hint, "api_design_skill")

    def test_detects_chinese_skill_generation_with_descriptor(self):
        intent = parse_intent("生成一个 UI 分析 Skill")

        self.assertEqual(intent.intent_type, "generate_skill")
        self.assertTrue(intent.needs_skill_generation)
        self.assertFalse(intent.requires_skill)

    def test_detects_skill_run_task(self):
        intent = parse_intent("Review this dashboard layout for readability.")

        self.assertEqual(intent.intent_type, "run_skill")
        self.assertTrue(intent.requires_skill)
        self.assertEqual(intent.skill_hint, "ui_review_skill")

    def test_trace_url_field_does_not_force_trace_inspection(self):
        intent = parse_intent("Analyze API JSON output with trace_url, hqs, and warnings.")

        self.assertEqual(intent.intent_type, "run_skill")
        self.assertTrue(intent.requires_skill)
        self.assertEqual(intent.skill_hint, "api_design_skill")

    def test_explicit_trace_inspection_still_works(self):
        intent = parse_intent("Inspect the latest trace.")

        self.assertEqual(intent.intent_type, "inspect_traces")
        self.assertFalse(intent.requires_skill)

    def test_detects_memory_query(self):
        intent = parse_intent("What useful AgentForge memory do you have about recent provider dry runs?")

        self.assertEqual(intent.intent_type, "query_memory")
        self.assertFalse(intent.requires_skill)

    def test_falls_back_to_chat(self):
        intent = parse_intent("hello")

        self.assertEqual(intent.intent_type, "chat")
        self.assertFalse(intent.requires_skill)


if __name__ == "__main__":
    unittest.main()
