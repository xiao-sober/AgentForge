import unittest

from agentforge.skill_generator.requirement_parser import parse_requirement


class RequirementParserTest(unittest.TestCase):
    def test_parse_ui_one_line_requirement(self):
        requirement = parse_requirement("帮我做一个能根据网页截图分析 UI 问题并给出优化建议的 Skill")

        self.assertEqual(requirement.skill_slug, "ui_review_skill")
        self.assertIn("screenshot", requirement.inputs)
        self.assertIn("issues", requirement.outputs)
        self.assertIn("optimization suggestions", requirement.outputs)
        self.assertIn("structured report", requirement.outputs)

    def test_parse_multi_turn_conversation(self):
        requirement = parse_requirement(
            """
            User: 我经常要分析后台管理系统页面。
            Assistant: 你主要分析什么？
            User: 主要看布局、视觉层级、图表、交互闭环和数据表达。
            Assistant: 输出格式有什么要求？
            User: 要分问题、原因、优化建议、优先级。
            """
        )

        self.assertEqual(requirement.skill_slug, "ui_review_skill")
        self.assertIn("priority", requirement.outputs)
        self.assertIn("reasons", requirement.outputs)
        self.assertIn("B-end dashboard", requirement.scenario)
        self.assertEqual(requirement.examples, [])

    def test_does_not_treat_skill_generation_request_as_usage_example(self):
        requirement = parse_requirement("帮我做一个能根据网页截图分析 UI 问题并给出优化建议的 Skill")

        self.assertEqual(requirement.examples, [])

    def test_extracts_explicit_usage_examples(self):
        requirement = parse_requirement(
            "帮我做一个 UI 分析 Skill。例如：请分析一个数据驾驶舱页面的视觉层级问题。"
        )

        self.assertEqual(
            requirement.examples,
            ["请分析一个数据驾驶舱页面的视觉层级问题。"],
        )


if __name__ == "__main__":
    unittest.main()
