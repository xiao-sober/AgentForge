from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agentforge.common.llm_client import LLMProviderError
from agentforge.providers import ProviderConfigError, create_llm_client, load_provider_config
from agentforge.skill_generator.generator import generate_skill_from_input
from agentforge.skill_generator.skill_schema import validate_skill


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

    parser.print_help()
    return 0


def _resolve_project_path(project_root: Path, path: Path) -> Path:
    if path.is_absolute():
        return path
    return project_root / path


if __name__ == "__main__":
    sys.exit(main())
