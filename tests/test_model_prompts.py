import unittest

from agentforge.skill_evolver.rewriter import SKILL_REWRITE_SYSTEM_PROMPT
from agentforge.skill_evolver.skill_runner import SKILL_RUN_SYSTEM_PROMPT
from agentforge.skill_generator.prompts import SKILL_GENERATION_SYSTEM_PROMPT, build_skill_generation_prompt
from agentforge.skill_generator.requirement_parser import parse_requirement


class ModelPromptsTest(unittest.TestCase):
    def test_skill_generation_prompt_is_chinese_first_but_keeps_schema_headings(self):
        requirement = parse_requirement("生成一个 API 契约评审 Skill")
        prompt = build_skill_generation_prompt("生成一个 API 契约评审 Skill", requirement)

        self.assertIn("你是 AgentForge 的 Skill 作者", SKILL_GENERATION_SYSTEM_PROMPT)
        self.assertIn("默认使用中文", SKILL_GENERATION_SYSTEM_PROMPT)
        self.assertIn("请根据原始输入和归一化需求", prompt)
        self.assertIn("- ## Purpose", prompt)
        self.assertIn("标题文本保持英文", prompt)

    def test_skill_run_prompt_is_chinese_first_but_keeps_output_contract(self):
        self.assertIn("你是 AgentForge 的 Skill 执行器", SKILL_RUN_SYSTEM_PROMPT)
        self.assertIn("默认使用中文", SKILL_RUN_SYSTEM_PROMPT)
        self.assertIn("# Skill Run Output", SKILL_RUN_SYSTEM_PROMPT)
        self.assertIn("## Assumptions and Gaps", SKILL_RUN_SYSTEM_PROMPT)

    def test_skill_rewrite_prompt_is_chinese_first_but_keeps_schema_contract(self):
        self.assertIn("你是 AgentForge 的 Skill 重写器", SKILL_REWRITE_SYSTEM_PROMPT)
        self.assertIn("固定章节标题必须保持英文", SKILL_REWRITE_SYSTEM_PROMPT)
        self.assertIn("默认使用中文", SKILL_REWRITE_SYSTEM_PROMPT)


if __name__ == "__main__":
    unittest.main()
