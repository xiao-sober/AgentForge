import unittest

from agentforge.hqs.response_evaluator import RESPONSE_HQS_DIMENSIONS, evaluate_response
from agentforge.hqs.system_evaluator import SYSTEM_HQS_DIMENSIONS, evaluate_system


class ResponseHQSEvaluatorTest(unittest.TestCase):
    def test_scores_response_dimensions(self):
        report = evaluate_response(
            "Review dashboard layout readability.",
            """# AgentForge Response

## Result

- Reviewed dashboard layout readability with specific recommendations.
- Trace recorded the local deterministic run.

## Memory

- Retrieved context from previous memory.
""",
            memory_context={"episodes": [{"user_input": "dashboard"}], "semantic_memory": [], "working_memory": {}},
            intent={"intent_type": "run_skill"},
        )

        self.assertEqual(report.dimensions, RESPONSE_HQS_DIMENSIONS)
        self.assertGreater(report.average_score, 0)
        self.assertIn("calibration", report.to_dict())
        self.assertGreaterEqual(report.confidence, 0)
        self.assertLessEqual(report.confidence, 1)
        for dimension in RESPONSE_HQS_DIMENSIONS:
            self.assertIn(dimension, report.scores)
            self.assertGreaterEqual(report.scores[dimension], 0)
            self.assertLessEqual(report.scores[dimension], 5)

    def test_generic_structured_response_scores_below_evidence_tied_response(self):
        user_input = "Review dashboard KPI contrast and unclear filters."
        generic = evaluate_response(
            user_input,
            """# AgentForge Response

## Result

- Recommended approach: follow the Skill workflow and return a structured task output.
- Actionable output: provide specific enough advice to act on.
""",
            memory_context={"episodes": [], "semantic_memory": [], "working_memory": {}},
            intent={"intent_type": "run_skill"},
        )
        evidence_tied = evaluate_response(
            user_input,
            """# AgentForge Response

## Result

- The dashboard KPI contrast and unclear filters are the main review targets from the input.
- Improve label contrast, separate KPI density, and make filter state visible because those issues affect readability.

## Assumptions

- No screenshot was provided, so no extra UI elements are invented.
""",
            memory_context={"episodes": [], "semantic_memory": [], "working_memory": {}},
            intent={"intent_type": "run_skill"},
        )

        self.assertLess(generic.scores["Specificity"], evidence_tied.scores["Specificity"])
        self.assertGreater(generic.calibration["generic_penalty"], 0)
        self.assertGreater(evidence_tied.calibration["evidence_overlap_ratio"], generic.calibration["evidence_overlap_ratio"])

    def test_scores_system_dimensions(self):
        report = evaluate_system(
            {
                "response": "AgentForge response with trace and HQS.",
                "steps": [{"name": "parse_intent"}],
                "errors": [],
                "memory_context": {"working_memory": {}, "episodes": [], "semantic_memory": []},
                "intent": {"requires_skill": False},
                "selected_skill": None,
            }
        )

        self.assertEqual(report.dimensions, SYSTEM_HQS_DIMENSIONS)
        self.assertGreater(report.average_score, 0)


if __name__ == "__main__":
    unittest.main()
