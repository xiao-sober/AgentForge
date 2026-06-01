import json
import tempfile
import unittest
from pathlib import Path

from agentforge.skill_generator.generator import generate_skill_from_input


class FakeLLMClient:
    def __init__(self, content):
        self.content = content
        self.calls = []

    def complete(self, prompt, system_prompt=None):
        self.calls.append({"prompt": prompt, "system_prompt": system_prompt})
        return self.content

    def metadata(self):
        return {"provider": "fake", "type": "openai_compatible", "model": "fake-model"}


class SkillGenerationFlowTest(unittest.TestCase):
    def test_generation_flow_writes_skill_and_trace(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            result = generate_skill_from_input("帮我做一个能根据网页截图分析 UI 问题并给出优化建议的 Skill", root)

            self.assertTrue(result.validation_result.valid)
            self.assertTrue(result.skill_path.exists())
            self.assertEqual(result.skill_path.name, "SKILL.md")
            self.assertTrue(result.trace_path.exists())

            trace = json.loads(result.trace_path.read_text(encoding="utf-8"))
            self.assertEqual(trace["type"], "skill_generation")
            self.assertEqual(trace["generated_skill_path"], "skills/ui_review_skill/v1/SKILL.md")
            self.assertTrue(trace["validation_result"]["valid"])

    def test_generation_flow_can_use_llm_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            llm = FakeLLMClient(
                """# UI Review Skill

## Purpose

Analyze UI screenshots.

## When to Use

Use for UI review.

## Inputs

- screenshot

## Outputs

- issues
- suggestions

## Workflow

1. Inspect the input.
2. Report issues.

## Constraints

- Do not invent details.

## Quality Criteria

- Specific and actionable.

## Failure Modes

- Input is unclear.

## Examples

- Analyze a dashboard screenshot.

## Version Notes

- v1: Initial model-generated Skill.
"""
            )

            result = generate_skill_from_input(
                "帮我做一个能根据网页截图分析 UI 问题并给出优化建议的 Skill",
                root,
                llm_client=llm,
            )

            self.assertEqual(result.generation_mode, "model")
            self.assertTrue(result.validation_result.valid)
            self.assertEqual(len(llm.calls), 1)
            self.assertIn("Analyze UI screenshots.", result.skill_path.read_text(encoding="utf-8"))

            trace = json.loads(result.trace_path.read_text(encoding="utf-8"))
            self.assertEqual(trace["generation_mode"], "model")
            self.assertEqual(trace["provider"]["provider"], "fake")

    def test_generation_repairs_incomplete_llm_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            llm = FakeLLMClient("# UI Review Skill\n\n## Purpose\n\nAnalyze UI screenshots.")

            result = generate_skill_from_input(
                "帮我做一个能根据网页截图分析 UI 问题并给出优化建议的 Skill",
                root,
                llm_client=llm,
            )

            self.assertTrue(result.validation_result.valid)
            markdown = result.skill_path.read_text(encoding="utf-8")
            self.assertIn("## Version Notes", markdown)

            trace = json.loads(result.trace_path.read_text(encoding="utf-8"))
            self.assertTrue(trace["output"]["was_repaired"])


if __name__ == "__main__":
    unittest.main()
