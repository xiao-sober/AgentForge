import tempfile
import unittest
from pathlib import Path

from agentforge.common.artifact_schema import ArtifactValidationError
from agentforge.common.artifacts import cleanup_artifacts
from agentforge.common.file_store import write_json


class ArtifactSchemaAndCleanupTest(unittest.TestCase):
    def test_write_json_rejects_invalid_trace_artifact(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(ArtifactValidationError):
                write_json(Path(temp_dir) / "traces" / "bad.json", {"type": "agent_chat"})

    def test_cleanup_artifacts_dry_run_keeps_newest_traces_and_runs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            traces = root / "traces"
            traces.mkdir(parents=True)
            for index in range(3):
                write_json(
                    traces / f"20260101T00000{index}Z_agent_chat.json",
                    {
                        "trace_id": f"trace_{index}",
                        "type": "agent_chat",
                        "created_at": "2026-01-01T00:00:00Z",
                        "input": {},
                        "steps": [],
                        "output": {},
                        "artifacts": [],
                        "errors": [],
                    },
                )

            for index in range(3):
                run_dir = root / "runs" / "ui_review_skill" / "v1" / f"run_{index}"
                run_dir.mkdir(parents=True)
                (run_dir / "output.md").write_text("x", encoding="utf-8")

            result = cleanup_artifacts(root, max_traces=1, max_runs_per_skill_version=1, dry_run=True)

            self.assertTrue(result.dry_run)
            self.assertEqual(len(result.removed), 4)
            self.assertEqual(len(list(traces.glob("*.json"))), 3)


if __name__ == "__main__":
    unittest.main()
