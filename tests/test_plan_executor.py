import tempfile
import unittest
from pathlib import Path

from agentforge.agent.executor import execute_plan
from agentforge.agent.intent_parser import Intent
from agentforge.agent.planner import AgentPlan, PlanStep, build_plan
from agentforge.agent.skill_selector import SkillCandidate


class FailingLLMClient:
    def complete(self, prompt, system_prompt=None):
        raise TimeoutError("provider timed out")

    def metadata(self):
        return {"provider": "fake", "model": "fake"}


class PlanExecutorTest(unittest.TestCase):
    def test_executes_multistep_skill_plan_through_state_machine(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            skill_path = _write_skill(root)
            intent = Intent(
                intent_type="run_skill",
                query="Review dashboard layout then summarize accessibility risks.",
                requires_skill=True,
                needs_skill_generation=False,
                skill_hint="ui_review_skill",
                confidence=0.9,
                reasons=["test"],
            )
            selected = SkillCandidate(
                skill_slug="ui_review_skill",
                version="v1",
                skill_path=skill_path,
                title="UI Review Skill",
                score=5.0,
                reasons=["test"],
            )
            plan = build_plan(intent, selected)

            result = execute_plan(plan, intent, selected, project_root=root)

            self.assertEqual(result.execution_state["status"], "completed")
            self.assertEqual(len(result.run_results), 2)
            self.assertEqual(len(result.plan_step_results), 2)
            self.assertTrue(all(item["status"] == "completed" for item in result.plan_step_results))
            self.assertIn("Multi-Step Skill Output", result.output_text)
            first_input = result.run_results[0].outputs[0].input
            second_input = result.run_results[1].outputs[0].input
            self.assertIn("原始完整用户请求", first_input)
            self.assertIn("Review dashboard layout then summarize accessibility risks.", first_input)
            self.assertIn("当前执行焦点", second_input)
            self.assertIn("summarize accessibility risks", second_input)
            self.assertIn("Review dashboard layout", second_input)
            transition_names = [
                transition.get("plan_step_name")
                for transition in result.execution_state["transitions"]
                if transition.get("to_status") == "completed"
            ]
            self.assertIn("run_skill_subtask_1", transition_names)
            self.assertIn("run_skill_subtask_2", transition_names)

    def test_skips_dependents_when_required_step_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            intent = Intent(
                intent_type="run_skill",
                query="Review dashboard layout then summarize accessibility risks.",
                requires_skill=True,
                needs_skill_generation=False,
                skill_hint=None,
                confidence=0.9,
                reasons=["test"],
            )
            plan = AgentPlan(
                action="run_skill",
                objective="test dependency handling",
                rationale="test",
                steps=[
                    PlanStep(
                        name="run_skill_subtask_1",
                        action="run first subtask",
                        tool_name="execute_plan",
                        step_id="step_001",
                        tool_input={"subtask": "Review dashboard layout.", "subtask_index": 1},
                    ),
                    PlanStep(
                        name="run_skill_subtask_2",
                        action="run second subtask",
                        tool_name="execute_plan",
                        step_id="step_002",
                        depends_on=["step_001"],
                        tool_input={"subtask": "Summarize accessibility risks.", "subtask_index": 2},
                    ),
                ],
            )

            result = execute_plan(plan, intent, None, project_root=root)

            self.assertEqual(result.execution_state["status"], "failed")
            self.assertEqual(result.execution_state["step_statuses"]["step_001"], "failed")
            self.assertEqual(result.execution_state["step_statuses"]["step_002"], "skipped")
            self.assertEqual([item["status"] for item in result.plan_step_results], ["failed", "skipped"])

    def test_provider_task_error_stops_execution(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            skill_path = _write_skill(root)
            intent = Intent(
                intent_type="run_skill",
                query="Review dashboard layout.",
                requires_skill=True,
                needs_skill_generation=False,
                skill_hint="ui_review_skill",
                confidence=0.9,
                reasons=["test"],
            )
            selected = SkillCandidate(
                skill_slug="ui_review_skill",
                version="v1",
                skill_path=skill_path,
                title="UI Review Skill",
                score=5.0,
                reasons=["test"],
            )
            plan = build_plan(intent, selected)

            result = execute_plan(plan, intent, selected, project_root=root, llm_client=FailingLLMClient())

            self.assertEqual(result.execution_state["status"], "failed")
            self.assertEqual(result.plan_step_results[0]["status"], "failed")
            self.assertEqual(result.errors[0]["error_type"], "LLMProviderError")
            self.assertFalse(result.errors[0]["recoverable"])
            self.assertIn("provider timed out", result.errors[0]["message"])


def _write_skill(root: Path) -> Path:
    skill_path = root / "skills" / "ui_review_skill" / "v1" / "SKILL.md"
    skill_path.parent.mkdir(parents=True)
    skill_path.write_text(
        """# UI Review Skill

## Purpose

Analyze UI screenshots or page descriptions and produce structured improvement advice.

## When to Use

Use for dashboard and admin page UI review.

## Inputs

- screenshot
- page context

## Outputs

- issues
- reasons
- optimization suggestions
- structured report

## Workflow

1. Identify the available input.
2. Extract visible UI areas and data elements.
3. Analyze layout, hierarchy, interactions, and data readability.
4. List issues with reasons and suggestions.

## Constraints

- Do not invent facts, UI elements, or data that are not provided.
- Prefer concrete guidance over generic advice.

## Quality Criteria

- Output follows the requested structure.
- Advice is specific enough to act on.

## Failure Modes

- Input is too vague to support a specific recommendation.
- Output ignores the required structure.

## Examples

- Analyze a dashboard screenshot.

## Version Notes

- v1: Initial test Skill.
""",
        encoding="utf-8",
    )
    return skill_path


if __name__ == "__main__":
    unittest.main()
