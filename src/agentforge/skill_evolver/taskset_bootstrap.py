from __future__ import annotations

from pathlib import Path
from typing import Any

from agentforge.common.file_store import write_json
from agentforge.skill_evolver.version_manager import parse_skill_version_path
from agentforge.skill_generator.skill_schema import validate_skill


def create_taskset_from_skill(skill_path: Path | str, taskset_path: Path | str) -> Path:
    resolved_skill_path = Path(skill_path)
    resolved_taskset_path = Path(taskset_path)
    if resolved_taskset_path.exists():
        raise ValueError(f"Refusing to overwrite existing task set: {resolved_taskset_path}")
    if not resolved_skill_path.exists():
        raise ValueError(f"Skill not found: {resolved_skill_path}")

    markdown = resolved_skill_path.read_text(encoding="utf-8")
    validation = validate_skill(markdown)
    if not validation.valid:
        raise ValueError(f"Cannot create a task set from an invalid Skill: {validation.to_dict()}")

    info = parse_skill_version_path(resolved_skill_path)
    payload = build_taskset_payload(markdown, taskset_name=resolved_taskset_path.stem, skill_slug=info.skill_slug)
    return write_json(resolved_taskset_path, payload)


def build_taskset_payload(markdown: str, taskset_name: str, skill_slug: str) -> dict[str, Any]:
    title = _extract_title(markdown)
    lowered = markdown.lower()
    if _looks_like_ui_skill(title, lowered):
        tasks = _ui_review_tasks()
    else:
        tasks = _general_skill_tasks(title)

    return {
        "name": taskset_name,
        "description": f"Auto-created starter task set for {title}. Review and edit before using it as a stable benchmark.",
        "metadata": {
            "schema_version": "taskset.v1",
            "created_by": "agentforge_auto_create_taskset",
            "source_skill_slug": skill_slug,
            "source_skill_title": title,
            "status": "starter",
            "review_required": True,
        },
        "tasks": tasks,
    }


def _ui_review_tasks() -> list[dict[str, Any]]:
    return [
        {
            "id": "dashboard_layout",
            "input": (
                "Review a SaaS analytics dashboard with a crowded top KPI row, a dense line chart, "
                "a sidebar navigation, and a data table. Focus on hierarchy, readability, interaction clarity, "
                "and actionable fixes."
            ),
            "expected_output": [
                "visible or described UI issues",
                "reasons tied to layout, hierarchy, readability, or interaction flow",
                "actionable optimization suggestions",
                "priority labels or clear sequencing",
            ],
            "criteria": [
                "structured report",
                "specific recommendations",
                "uncertainty handling",
                "no invented visual details beyond the task input",
            ],
        },
        {
            "id": "empty_context_handling",
            "input": "Review this dashboard layout.",
            "expected_output": [
                "state that the available context is insufficient",
                "ask for screenshot or page description",
                "avoid inventing UI details",
            ],
            "criteria": [
                "risk control",
                "clear missing-input explanation",
                "concrete list of required inputs",
            ],
        },
    ]


def _general_skill_tasks(title: str) -> list[dict[str, Any]]:
    return [
        {
            "id": "basic_execution",
            "input": f"Use {title} to handle a realistic but concise task. Return a structured result.",
            "expected_output": [
                "clear task understanding",
                "structured output",
                "actionable next steps",
            ],
            "criteria": [
                "instruction following",
                "specificity",
                "risk control",
            ],
        },
        {
            "id": "missing_context_handling",
            "input": f"Use {title}, but the user only provides a vague one-line request.",
            "expected_output": [
                "state missing context",
                "ask for required inputs",
                "avoid unsupported claims",
            ],
            "criteria": [
                "robustness",
                "clear missing-input explanation",
                "no hallucinated details",
            ],
        },
    ]


def _extract_title(markdown: str) -> str:
    for line in markdown.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return "Generated Skill"


def _looks_like_ui_skill(title: str, lowered_markdown: str) -> bool:
    title_lowered = title.lower()
    ui_terms = ["ui", "ux", "dashboard", "screenshot", "layout", "visual hierarchy", "interface"]
    return any(term in title_lowered or term in lowered_markdown for term in ui_terms)
