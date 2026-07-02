from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agentforge.common.artifacts import cleanup_artifacts
from agentforge.common.diagnostics import build_config_report, build_health_report, build_version_report
from agentforge.common.llm_client import LLMProviderError
from agentforge.common.trace_inspector import format_trace_summary, inspect_trace
from agentforge.providers import ProviderConfigError, create_llm_client, load_provider_config
from agentforge.skill_evolver.evolution_loop import evolve_skill
from agentforge.skill_evolver.skill_runner import run_skill
from agentforge.skill_evolver.taskset_bootstrap import create_taskset_from_skill
from agentforge.skill_generator.generator import generate_skill_from_input
from agentforge.skill_generator.skill_schema import validate_skill
from agentforge.web.app import run_server


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentforge",
        description="AgentForge local-first Agent tooling.",
    )
    subparsers = parser.add_subparsers(dest="command")

    generate = subparsers.add_parser(
        "generate-skill",
        help="Generate a versioned SKILL.md from a requirement or conversation.",
    )
    input_group = generate.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--input", help="One-line requirement or conversation text.")
    input_group.add_argument("--input-file", type=Path, help="Path to a text file containing the requirement.")
    generate.add_argument("--project-root", type=Path, default=Path.cwd(), help="Project root for skills/ and traces/.")
    generate.add_argument(
        "--provider-config",
        type=Path,
        default=Path("config/providers.json"),
        help="Provider JSON path. Relative paths are resolved under --project-root.",
    )
    generate.add_argument("--provider", help="Provider name in the provider JSON.")
    generate.add_argument("--model", help="Override the configured model name.")
    generate.add_argument(
        "--local-only",
        action="store_true",
        help="Skip model calls and use deterministic local Skill generation.",
    )
    generate.add_argument("--json", action="store_true", help="Print machine-readable JSON.")

    validate = subparsers.add_parser("validate-skill", help="Validate a SKILL.md file.")
    validate.add_argument("path", type=Path, help="Path to SKILL.md.")
    validate.add_argument("--json", action="store_true", help="Print machine-readable JSON.")

    run = subparsers.add_parser("run-skill", help="Run a versioned Skill against one input.")
    run.add_argument("--skill", type=Path, required=True, help="Path to skills/<skill_slug>/<version>/SKILL.md.")
    run_input_group = run.add_mutually_exclusive_group(required=True)
    run_input_group.add_argument("--input", help="Task input text.")
    run_input_group.add_argument("--input-file", type=Path, help="Path to a text file containing the task input.")
    run.add_argument("--project-root", type=Path, default=Path.cwd(), help="Project root for runs/ and traces/.")
    run.add_argument(
        "--provider-config",
        type=Path,
        default=Path("config/providers.json"),
        help="Provider JSON path. Relative paths are resolved under --project-root.",
    )
    run.add_argument("--provider", help="Provider name in the provider JSON.")
    run.add_argument("--model", help="Override the configured model name.")
    run.add_argument(
        "--use-provider",
        action="store_true",
        help="Use the configured model provider instead of deterministic local execution.",
    )
    run.add_argument("--json", action="store_true", help="Print machine-readable JSON.")

    evolve = subparsers.add_parser("evolve-skill", help="Run a Skill evolution loop against a task set.")
    evolve.add_argument("--skill", type=Path, required=True, help="Path to skills/<skill_slug>/<version>/SKILL.md.")
    evolve.add_argument("--taskset", type=Path, required=True, help="Path to a JSON or YAML task set.")
    evolve.add_argument(
        "--auto-create-taskset",
        action="store_true",
        help="Create a starter JSON task set if --taskset does not exist, then continue evolution.",
    )
    evolve.add_argument("--max-iterations", type=int, default=3, help="Maximum rewrite iterations.")
    evolve.add_argument("--target-hqs", type=float, default=5.0, help="Stop when average HQS reaches this score.")
    evolve.add_argument(
        "--min-improvement",
        type=float,
        default=0.01,
        help="Reject candidate rewrites that improve HQS by less than this amount.",
    )
    evolve.add_argument("--project-root", type=Path, default=Path.cwd(), help="Project root for runs/ and traces/.")
    evolve.add_argument(
        "--provider-config",
        type=Path,
        default=Path("config/providers.json"),
        help="Provider JSON path. Relative paths are resolved under --project-root.",
    )
    evolve.add_argument("--provider", help="Provider name in the provider JSON.")
    evolve.add_argument("--model", help="Override the configured model name.")
    evolve.add_argument(
        "--use-provider",
        action="store_true",
        help="Use the configured model provider for execution and rewriting.",
    )
    evolve.add_argument("--json", action="store_true", help="Print machine-readable JSON.")

    serve = subparsers.add_parser("serve", help="Start the Phase 3 local JSON API server.")
    serve.add_argument("--project-root", type=Path, default=Path.cwd(), help="Project root for local artifacts.")
    serve.add_argument("--host", default="127.0.0.1", help="Bind host.")
    serve.add_argument("--port", type=int, default=8765, help="Bind port.")

    check = subparsers.add_parser("check-config", help="Inspect local health, version, and provider config.")
    check.add_argument("--project-root", type=Path, default=Path.cwd(), help="Project root for local artifacts.")
    check.add_argument(
        "--provider-config",
        type=Path,
        default=Path("config/providers.json"),
        help="Provider JSON path. Relative paths are resolved under --project-root.",
    )
    check.add_argument("--json", action="store_true", help="Print machine-readable JSON.")

    inspect = subparsers.add_parser("inspect-trace", help="Print a readable summary of a trace JSON file.")
    inspect.add_argument("trace", type=Path, help="Trace filename under traces/ or path to a trace JSON file.")
    inspect.add_argument("--project-root", type=Path, default=Path.cwd(), help="Project root for traces/.")
    inspect.add_argument("--json", action="store_true", help="Print machine-readable JSON.")

    cleanup = subparsers.add_parser("cleanup-artifacts", help="Apply trace/run artifact retention rules.")
    cleanup.add_argument("--project-root", type=Path, default=Path.cwd(), help="Project root for runs/ and traces/.")
    cleanup.add_argument("--max-traces", type=int, default=200, help="Keep this many newest trace JSON files.")
    cleanup.add_argument(
        "--max-runs-per-skill-version",
        type=int,
        default=20,
        help="Keep this many newest run directories per skill/version.",
    )
    cleanup.add_argument("--delete", action="store_true", help="Actually delete old artifacts. Omit for dry-run.")
    cleanup.add_argument("--json", action="store_true", help="Print machine-readable JSON.")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "generate-skill":
        try:
            input_text = args.input if args.input is not None else args.input_file.read_text(encoding="utf-8")
            project_root = args.project_root.resolve()
            llm_client = None
            if not args.local_only:
                provider_config_path = _resolve_project_path(project_root, args.provider_config)
                provider_config = load_provider_config(
                    provider_config_path,
                    provider_name=args.provider,
                    model_override=args.model,
                )
                llm_client = create_llm_client(provider_config)
            result = generate_skill_from_input(input_text, project_root=project_root, llm_client=llm_client)
        except (ProviderConfigError, LLMProviderError, ValueError, OSError) as exc:
            parser.exit(1, f"error: {exc}\n")

        payload = {
            "skill_path": str(result.skill_path),
            "trace_path": str(result.trace_path),
            "valid": result.validation_result.valid,
            "missing_sections": result.validation_result.missing_sections,
            "skill_slug": result.requirement.skill_slug,
            "version": result.version,
            "generation_mode": result.generation_mode,
        }
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"Generated Skill: {result.skill_path}")
            print(f"Trace: {result.trace_path}")
            print(f"Validation: {'valid' if result.validation_result.valid else 'invalid'}")
            if result.validation_result.missing_sections:
                print("Missing sections: " + ", ".join(result.validation_result.missing_sections))
        return 0 if result.validation_result.valid else 2

    if args.command == "validate-skill":
        markdown = args.path.read_text(encoding="utf-8")
        result = validate_skill(markdown)
        payload = {
            "valid": result.valid,
            "missing_sections": result.missing_sections,
            "unexpected_sections": result.unexpected_sections,
            "has_title": result.has_title,
        }
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print("valid" if result.valid else "invalid")
            if result.missing_sections:
                print("Missing sections: " + ", ".join(result.missing_sections))
        return 0 if result.valid else 2

    if args.command == "run-skill":
        try:
            input_text = args.input if args.input is not None else args.input_file.read_text(encoding="utf-8")
            project_root = args.project_root.resolve()
            llm_client = _optional_llm_client(args, project_root)
            result = run_skill(args.skill, input_text, project_root=project_root, llm_client=llm_client)
        except (ProviderConfigError, LLMProviderError, ValueError, OSError) as exc:
            parser.exit(1, f"error: {exc}\n")

        payload = {
            "skill_path": str(result.skill_path),
            "run_dir": str(result.run_dir),
            "result_path": str(result.result_path),
            "trace_path": str(result.trace_path),
            "mode": result.mode,
            "outputs": [output.to_dict() for output in result.outputs],
        }
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"Run directory: {result.run_dir}")
            print(f"Run result: {result.result_path}")
            print(f"Trace: {result.trace_path}")
            print(f"Mode: {result.mode}")
        return 0

    if args.command == "evolve-skill":
        try:
            project_root = args.project_root.resolve()
            llm_client = _optional_llm_client(args, project_root)
            skill_path = _resolve_project_path(project_root, args.skill)
            taskset_path = _resolve_project_path(project_root, args.taskset)
            created_taskset_path = None
            if args.auto_create_taskset and not taskset_path.exists():
                created_taskset_path = create_taskset_from_skill(skill_path, taskset_path)
            result = evolve_skill(
                skill_path,
                taskset_path,
                project_root=project_root,
                max_iterations=args.max_iterations,
                target_hqs=args.target_hqs,
                min_improvement=args.min_improvement,
                llm_client=llm_client,
            )
        except (ProviderConfigError, LLMProviderError, ValueError, OSError) as exc:
            parser.exit(1, f"error: {exc}\n")

        payload = result.to_dict()
        payload["created_taskset_path"] = str(created_taskset_path) if created_taskset_path else None
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            if created_taskset_path:
                print(f"Created task set: {created_taskset_path}")
            print(f"Final Skill: {result.final_skill_path}")
            print(f"Trace: {result.trace_path}")
            print(f"Stop reason: {result.stop_reason}")
            for iteration in result.iterations:
                print(f"Iteration {iteration.iteration}: HQS {iteration.hqs_report.average_score:.2f}")
                if iteration.candidate_hqs_report:
                    print(
                        "  Candidate: "
                        f"HQS {iteration.candidate_hqs_report.average_score:.2f}, "
                        f"improvement {iteration.candidate_improvement:.2f}, "
                        f"decision {iteration.decision}"
                    )
                if iteration.rewritten_skill:
                    print(f"  New version: {iteration.rewritten_skill.skill_path}")
        return 0

    if args.command == "serve":
        run_server(project_root=args.project_root.resolve(), host=args.host, port=args.port)
        return 0

    if args.command == "check-config":
        project_root = args.project_root.resolve()
        payload = {
            "version": build_version_report(project_root),
            "health": build_health_report(project_root),
            "config": build_config_report(project_root, provider_config=args.provider_config),
        }
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"AgentForge {payload['version']['version']}")
            print(f"Project root: {payload['version']['project_root']}")
            print(f"Health: {payload['health']['status']}")
            print(f"Config: {payload['config']['status']}")
            if payload["config"].get("errors"):
                print("Config errors:")
                for error in payload["config"]["errors"]:
                    print(f"- {error}")
        return 0 if payload["health"]["status"] == "ok" and payload["config"]["status"] in {"ok", "local_only"} else 2

    if args.command == "inspect-trace":
        try:
            summary = inspect_trace(args.trace, project_root=args.project_root.resolve())
        except (ValueError, OSError) as exc:
            parser.exit(1, f"error: {exc}\n")
        if args.json:
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        else:
            print(format_trace_summary(summary))
        return 0 if summary["schema"]["valid"] else 2

    if args.command == "cleanup-artifacts":
        try:
            result = cleanup_artifacts(
                project_root=args.project_root.resolve(),
                max_traces=args.max_traces,
                max_runs_per_skill_version=args.max_runs_per_skill_version,
                dry_run=not args.delete,
            )
        except (ValueError, OSError) as exc:
            parser.exit(1, f"error: {exc}\n")
        payload = result.to_dict()
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            mode = "dry-run" if result.dry_run else "deleted"
            print(f"Cleanup mode: {mode}")
            print(f"Would remove: {len(result.removed)}" if result.dry_run else f"Removed: {len(result.removed)}")
            print(f"Kept: {len(result.kept)}")
            for path in result.removed[:20]:
                print(f"- {path}")
        return 0

    parser.print_help()
    return 0


def _resolve_project_path(project_root: Path, path: Path) -> Path:
    if path.is_absolute():
        return path
    return project_root / path


def _optional_llm_client(args: argparse.Namespace, project_root: Path):
    if not (args.use_provider or args.provider or args.model):
        return None
    provider_config_path = _resolve_project_path(project_root, args.provider_config)
    provider_config = load_provider_config(
        provider_config_path,
        provider_name=args.provider,
        model_override=args.model,
    )
    return create_llm_client(provider_config)


if __name__ == "__main__":
    sys.exit(main())
