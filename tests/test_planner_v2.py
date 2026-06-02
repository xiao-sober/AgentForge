import unittest
from pathlib import Path

from agentforge.agent.intent_parser import parse_intent
from agentforge.agent.planner import build_plan
from agentforge.agent.skill_selector import SkillCandidate


class PlannerV2Test(unittest.TestCase):
    def test_complex_skill_task_is_decomposed_into_dependent_steps(self):
        intent = parse_intent(
            "Review dashboard layout then summarize accessibility risks then propose concrete fixes."
        )
        skill = SkillCandidate(
            skill_slug="ui_review_skill",
            version="v2",
            skill_path=Path("skills/ui_review_skill/v2/SKILL.md"),
            title="UI Review Skill",
            score=4.5,
            reasons=["test"],
        )

        plan = build_plan(intent, skill)

        self.assertEqual(plan.action, "run_skill")
        self.assertEqual(plan.complexity, "complex")
        self.assertEqual(len(plan.subtasks), 3)
        self.assertTrue(any(condition.name == "max_steps" for condition in plan.stop_conditions))
        run_steps = [step for step in plan.steps if step.name.startswith("run_skill_subtask")]
        self.assertEqual(len(run_steps), 3)
        self.assertEqual(run_steps[0].depends_on, [])
        self.assertEqual(run_steps[1].depends_on, ["step_001"])
        self.assertEqual(run_steps[2].tool_input["subtask_index"], 3)
        self.assertEqual(run_steps[2].permission_required, "execute")


if __name__ == "__main__":
    unittest.main()
