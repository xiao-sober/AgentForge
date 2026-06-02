import unittest

from agentforge.agent.intent_parser import parse_intent


class IntentParserTest(unittest.TestCase):
    def test_detects_skill_generation(self):
        intent = parse_intent("Please generate Skill for UI review.")

        self.assertEqual(intent.intent_type, "generate_skill")
        self.assertTrue(intent.needs_skill_generation)
        self.assertEqual(intent.skill_hint, "ui_review_skill")

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

    def test_falls_back_to_chat(self):
        intent = parse_intent("hello")

        self.assertEqual(intent.intent_type, "chat")
        self.assertFalse(intent.requires_skill)


if __name__ == "__main__":
    unittest.main()
