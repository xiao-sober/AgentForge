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
        self.assertEqual(run_steps[2].tool_input["subtask_count"], 3)
        self.assertIn("original_query", run_steps[2].tool_input)
        self.assertIn("Review dashboard layout then summarize accessibility risks", run_steps[2].tool_input["skill_input"])
        self.assertIn("propose concrete fixes", run_steps[2].tool_input["skill_input"])
        self.assertEqual(run_steps[2].permission_required, "execute")

    def test_api_review_with_semicolon_context_is_not_fragmented(self):
        intent = parse_intent(
            "请用 API Design Skill 评审这个草案：POST /orders 创建订单但没有 Idempotency-Key；"
            "GET /order/list 使用单数路径并没有分页上限；错误统一 500 failed；"
            "没有鉴权说明和 request_id。请给出按严重程度排序的问题与修复建议。"
        )
        skill = SkillCandidate(
            skill_slug="api_design_skill",
            version="v4",
            skill_path=Path("skills/api_design_skill/v4/SKILL.md"),
            title="API Design Skill",
            score=5.0,
            reasons=["test"],
        )

        plan = build_plan(intent, skill)

        self.assertEqual(plan.action, "run_skill")
        self.assertEqual(plan.complexity, "simple")
        self.assertEqual(len(plan.subtasks), 1)
        run_steps = [step for step in plan.steps if step.name.startswith("run_skill")]
        self.assertEqual(len(run_steps), 1)
        self.assertIn("POST /orders", run_steps[0].tool_input["skill_input"])
        self.assertIn("GET /order/list", run_steps[0].tool_input["skill_input"])
        self.assertIn("request_id", run_steps[0].tool_input["skill_input"])


if __name__ == "__main__":
    unittest.main()
