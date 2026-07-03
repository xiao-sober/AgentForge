import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agentforge.cli import main


class FailingProviderClient:
    def complete(self, prompt, system_prompt=None):
        raise TimeoutError("provider timed out")

    def metadata(self):
        return {"provider": "fake", "model": "fake"}


class CliSmokeTest(unittest.TestCase):
    def test_local_cli_baseline_generate_run_evolve(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            self.assertEqual(_run_cli(["check-config", "--project-root", str(root), "--json"]), 0)

            self.assertEqual(
                _run_cli(
                    [
                        "generate-skill",
                        "--project-root",
                        str(root),
                        "--local-only",
                        "--input",
                        "Create a UI review Skill for dashboard readability.",
                        "--json",
                    ]
                ),
                0,
            )

            skill_path = root / "skills" / "ui_review_skill" / "v1" / "SKILL.md"
            self.assertTrue(skill_path.exists())

            self.assertEqual(
                _run_cli(
                    [
                        "run-skill",
                        "--project-root",
                        str(root),
                        "--skill",
                        str(skill_path),
                        "--input",
                        "Review a dashboard with dense KPI cards and unclear filters.",
                        "--json",
                    ]
                ),
                0,
            )

            taskset_path = root / "tasksets" / "auto_ui.json"
            self.assertEqual(
                _run_cli(
                    [
                        "evolve-skill",
                        "--project-root",
                        str(root),
                        "--skill",
                        str(skill_path),
                        "--taskset",
                        str(taskset_path),
                        "--auto-create-taskset",
                        "--max-iterations",
                        "1",
                        "--json",
                    ]
                ),
                0,
            )

            self.assertTrue(taskset_path.exists())
            self.assertTrue(any((root / "traces").glob("*.json")))
            self.assertTrue(any((root / "runs").glob("**/run_result.json")))

    def test_generate_skill_stops_when_provider_call_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_provider_config(root)

            with patch("agentforge.cli.create_llm_client", return_value=FailingProviderClient()):
                exit_code, stdout, stderr = _run_cli_capture(
                    [
                        "generate-skill",
                        "--project-root",
                        str(root),
                        "--input",
                        "Create an API design Skill for JSON response contracts.",
                        "--json",
                    ]
                )

            self.assertEqual(exit_code, 1)
            self.assertEqual(stdout, "")
            self.assertIn("provider timed out", stderr)
            self.assertFalse((root / "skills" / "api_design_skill" / "v1" / "SKILL.md").exists())

    def test_cli_accepts_stdin_for_generate_run_and_evolve_taskset(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            self.assertEqual(
                _run_cli_with_stdin(
                    [
                        "generate-skill",
                        "--project-root",
                        str(root),
                        "--local-only",
                        "--stdin",
                        "--json",
                    ],
                    "Create a UI review Skill for dashboard readability.",
                ),
                0,
            )

            skill_path = root / "skills" / "ui_review_skill" / "v1" / "SKILL.md"
            self.assertTrue(skill_path.exists())

            self.assertEqual(
                _run_cli_with_stdin(
                    [
                        "run-skill",
                        "--project-root",
                        str(root),
                        "--skill",
                        str(skill_path),
                        "--stdin",
                        "--json",
                    ],
                    "Review a dashboard with crowded filters.",
                ),
                0,
            )

            taskset_json = "\ufeff" + json.dumps(
                {
                    "name": "stdin_ui_tasks",
                    "tasks": [
                        {
                            "id": "dashboard",
                            "input": "Review a dashboard with dense KPI cards.",
                            "expected_output": ["issues", "recommendations"],
                        }
                    ],
                }
            )
            self.assertEqual(
                _run_cli_with_stdin(
                    [
                        "evolve-skill",
                        "--project-root",
                        str(root),
                        "--skill",
                        str(skill_path),
                        "--stdin",
                        "--max-iterations",
                        "1",
                        "--min-improvement",
                        "0",
                        "--json",
                    ],
                    taskset_json,
                ),
                0,
            )
            self.assertTrue(any((root / "runs" / "ui_review_skill").glob("**/run_result.json")))


def _run_cli(args: list[str]) -> int:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return main(args)


def _run_cli_with_stdin(args: list[str], stdin_text: str) -> int:
    with (
        contextlib.redirect_stdout(io.StringIO()),
        contextlib.redirect_stderr(io.StringIO()),
        patch("sys.stdin", io.StringIO(stdin_text)),
    ):
        return main(args)


def _run_cli_capture(args: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        try:
            exit_code = main(args)
        except SystemExit as exc:
            exit_code = exc.code if isinstance(exc.code, int) else 1
    return exit_code, stdout.getvalue(), stderr.getvalue()


def _write_provider_config(root: Path) -> Path:
    config_path = root / "config" / "providers.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        """{
  "default_provider": "fake",
  "providers": {
    "fake": {
      "type": "openai_compatible",
      "base_url": "https://example.invalid/v1",
      "api_key": "test-key",
      "model": "fake-model"
    }
  }
}
""",
        encoding="utf-8",
    )
    return config_path


if __name__ == "__main__":
    unittest.main()
