from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agentforge.common.file_store import write_text
from agentforge.skill_generator.requirement_parser import SkillRequirement
from agentforge.skill_generator.skill_schema import SkillValidationResult, validate_skill


@dataclass(frozen=True)
class WrittenSkill:
    skill_path: Path
    markdown: str
    validation_result: SkillValidationResult
    version: str
    validation_before_repair: SkillValidationResult | None = None
    was_repaired: bool = False


def build_skill_markdown(requirement: SkillRequirement, version: str = "v1") -> str:
    return "\n".join(
        [
            f"# {requirement.skill_name}",
            "",
            "## Purpose",
            "",
            requirement.purpose,
            "",
            "## When to Use",
            "",
            requirement.scenario,
            "",
            "Use this Skill when the user asks for this capability or provides a similar task pattern.",
            "",
            "## Inputs",
            "",
            _bullet_list(requirement.inputs),
            "",
            "## Outputs",
            "",
            _bullet_list(requirement.outputs),
            "",
            "## Workflow",
            "",
            _numbered_list(requirement.workflow),
            "",
            "## Constraints",
            "",
            _bullet_list(requirement.constraints),
            "",
            "## Quality Criteria",
            "",
            _bullet_list(requirement.quality_criteria),
            "",
            "## Failure Modes",
            "",
            _bullet_list(requirement.failure_modes),
            "",
            "## Examples",
            "",
            _examples(requirement.examples),
            "",
            "## Version Notes",
            "",
            f"- {version}: Initial generated Skill from the source requirement.",
            "",
        ]
    )


def normalize_generated_skill_markdown(
    markdown: str,
    requirement: SkillRequirement,
    version: str = "v1",
) -> tuple[str, SkillValidationResult, bool]:
    cleaned = _strip_markdown_fence(markdown).strip()
    if not cleaned:
        cleaned = build_skill_markdown(requirement, version=version)

    if not cleaned.startswith("# "):
        cleaned = f"# {requirement.skill_name}\n\n{cleaned}"

    before = validate_skill(cleaned)
    repaired = False
    if before.missing_sections:
        repaired = True
        for section in before.missing_sections:
            cleaned = f"{cleaned.rstrip()}\n\n## {section}\n\n{_fallback_section_content(requirement, section, version)}\n"

    return cleaned.rstrip() + "\n", before, repaired


def write_skill(
    requirement: SkillRequirement,
    project_root: Path,
    preferred_version: str = "v1",
    markdown: str | None = None,
) -> WrittenSkill:
    version = _next_available_version(project_root / "skills" / requirement.skill_slug, preferred_version)
    validation_before_repair = None
    was_repaired = False
    if markdown is None:
        final_markdown = build_skill_markdown(requirement, version=version)
    else:
        final_markdown, validation_before_repair, was_repaired = normalize_generated_skill_markdown(
            markdown,
            requirement,
            version=version,
        )
    validation_result = validate_skill(final_markdown)
    skill_path = project_root / "skills" / requirement.skill_slug / version / "SKILL.md"
    write_text(skill_path, final_markdown)
    return WrittenSkill(
        skill_path=skill_path,
        markdown=final_markdown,
        validation_result=validation_result,
        version=version,
        validation_before_repair=validation_before_repair,
        was_repaired=was_repaired,
    )


def _next_available_version(skill_root: Path, preferred_version: str) -> str:
    preferred_path = skill_root / preferred_version / "SKILL.md"
    if not preferred_path.exists():
        return preferred_version

    highest = 0
    if skill_root.exists():
        for child in skill_root.iterdir():
            if child.is_dir() and child.name.startswith("v") and child.name[1:].isdigit():
                highest = max(highest, int(child.name[1:]))
    return f"v{highest + 1}"


def _bullet_list(values: list[str]) -> str:
    return "\n".join(f"- {value}" for value in values)


def _numbered_list(values: list[str]) -> str:
    return "\n".join(f"{index}. {value}" for index, value in enumerate(values, start=1))


def _examples(values: list[str]) -> str:
    if not values:
        return "- No concrete Skill execution example was provided in the source requirement."
    rendered = []
    for value in values:
        rendered.append("- Source example:")
        rendered.append("")
        rendered.append("```text")
        rendered.append(value)
        rendered.append("```")
    return "\n".join(rendered)


def _strip_markdown_fence(markdown: str) -> str:
    stripped = markdown.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 2 and lines[-1].strip() == "```":
            return "\n".join(lines[1:-1])
    return markdown


def _fallback_section_content(requirement: SkillRequirement, section: str, version: str) -> str:
    if section == "Purpose":
        return requirement.purpose
    if section == "When to Use":
        return requirement.scenario
    if section == "Inputs":
        return _bullet_list(requirement.inputs)
    if section == "Outputs":
        return _bullet_list(requirement.outputs)
    if section == "Workflow":
        return _numbered_list(requirement.workflow)
    if section == "Constraints":
        return _bullet_list(requirement.constraints)
    if section == "Quality Criteria":
        return _bullet_list(requirement.quality_criteria)
    if section == "Failure Modes":
        return _bullet_list(requirement.failure_modes)
    if section == "Examples":
        return _examples(requirement.examples)
    if section == "Version Notes":
        return f"- {version}: Initial generated Skill from the source requirement."
    return "No content was generated for this section."
