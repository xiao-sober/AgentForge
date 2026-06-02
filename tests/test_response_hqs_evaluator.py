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
        for dimension in RESPONSE_HQS_DIMENSIONS:
            self.assertIn(dimension, report.scores)
            self.assertGreaterEqual(report.scores[dimension], 0)
            self.assertLessEqual(report.scores[dimension], 5)

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
