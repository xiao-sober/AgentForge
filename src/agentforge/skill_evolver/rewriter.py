from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentforge.common.llm_client import LLMClient
from agentforge.skill_evolver.diff_writer import create_unified_diff, write_diff
from agentforge.skill_evolver.hqs_evaluator import HQSReport
from agentforge.skill_evolver.version_manager import next_version, parse_skill_version_path, write_next_skill_version
from agentforge.skill_generator.skill_schema import validate_skill


@dataclass(frozen=True)
class RewriteCandidate:
    markdown: str
    validation: dict[str, Any]
    target_version: str
    rewrite_mode: str
    model_attempted: bool
    model_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_version": self.target_version,
            "rewrite_mode": self.rewrite_mode,
            "model_attempted": self.model_attempted,
            "model_error": self.model_error,
            "validation": self.validation,
        }


@dataclass(frozen=True)
class RewrittenSkill:
    skill_path: Path
    metadata_path: Path
    diff_path: Path
    version: str
    previous_version: str
    validation: dict[str, Any]
    rewrite_mode: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_path": str(self.skill_path),
            "metadata_path": str(self.metadata_path),
            "diff_path": str(self.diff_path),
            "version": self.version,
            "previous_version": self.previous_version,
            "validation": self.validation,
            "rewrite_mode": self.rewrite_mode,
        }


SKILL_REWRITE_SYSTEM_PROMPT = (
    "You are AgentForge's Skill rewriter. Rewrite the supplied SKILL.md into a better version. "
    "Return only a complete SKILL.md with all required sections."
)


def rewrite_skill(
    skill_path: Path | str,
    reflection_markdown: str,
    hqs_report: HQSReport,
    llm_client: LLMClient | None = None,
    extra_metadata: dict[str, Any] | None = None,
) -> RewrittenSkill:
    candidate = propose_skill_rewrite(
        skill_path,
        reflection_markdown,
        hqs_report,
        llm_client=llm_client,
    )
    return write_rewrite_candidate(skill_path, candidate, hqs_report, extra_metadata=extra_metadata)


def propose_skill_rewrite(
    skill_path: Path | str,
    reflection_markdown: str,
    hqs_report: HQSReport,
    llm_client: LLMClient | None = None,
) -> RewriteCandidate:
    resolved_skill_path = Path(skill_path).resolve()
    old_markdown = resolved_skill_path.read_text(encoding="utf-8")
    old_validation = validate_skill(old_markdown)
    if not old_validation.valid:
        raise ValueError(f"Cannot rewrite invalid Skill: {old_validation.to_dict()}")

    next_version_label = next_version(resolved_skill_path)
    model_attempted = False
    model_error = None
    rewrite_mode = "local"
    new_markdown = ""

    if llm_client:
        model_attempted = True
        try:
            candidate = _strip_markdown_fence(
                llm_client.complete(
                    _build_rewrite_prompt(old_markdown, reflection_markdown, hqs_report, next_version_label),
                    system_prompt=SKILL_REWRITE_SYSTEM_PROMPT,
                )
            )
            if validate_skill(candidate).valid:
                new_markdown = candidate.rstrip() + "\n"
                rewrite_mode = "model"
            else:
                rewrite_mode = "local_after_invalid_model"
        except Exception as exc:
            model_error = f"{exc.__class__.__name__}: {exc}"
            rewrite_mode = "local_after_model_error"
            new_markdown = ""

    if not new_markdown:
        new_markdown = _local_rewrite(old_markdown, reflection_markdown, hqs_report, next_version_label)
        if model_attempted and rewrite_mode == "local":
            rewrite_mode = "local_after_invalid_model"

    validation = validate_skill(new_markdown)
    if not validation.valid:
        raise ValueError(f"Rewritten Skill failed schema validation: {validation.to_dict()}")

    return RewriteCandidate(
        markdown=new_markdown,
        validation=validation.to_dict(),
        target_version=next_version_label,
        rewrite_mode=rewrite_mode,
        model_attempted=model_attempted,
        model_error=model_error,
    )


def write_rewrite_candidate(
    skill_path: Path | str,
    candidate: RewriteCandidate,
    hqs_report: HQSReport,
    extra_metadata: dict[str, Any] | None = None,
) -> RewrittenSkill:
    resolved_skill_path = Path(skill_path).resolve()
    info = parse_skill_version_path(resolved_skill_path)
    metadata = {
        "source_skill_path": str(resolved_skill_path),
        "hqs_average": hqs_report.average_score,
        "hqs_dimensions": hqs_report.dimensions,
        "diff_path": str(info.skill_root / candidate.target_version / "diff.patch"),
        "rewrite_mode": candidate.rewrite_mode,
        "model_attempted": candidate.model_attempted,
        "model_error": candidate.model_error,
        "validation": candidate.validation,
        **(extra_metadata or {}),
    }
    written = write_next_skill_version(resolved_skill_path, candidate.markdown, metadata=metadata)
    old_markdown = resolved_skill_path.read_text(encoding="utf-8")
    diff_text = create_unified_diff(
        old_markdown,
        candidate.markdown,
        old_label=f"{info.skill_slug}/{info.version}/SKILL.md",
        new_label=f"{info.skill_slug}/{written.version}/SKILL.md",
    )
    diff_path = write_diff(written.skill_path.parent / "diff.patch", diff_text)

    return RewrittenSkill(
        skill_path=written.skill_path,
        metadata_path=written.metadata_path,
        diff_path=diff_path,
        version=written.version,
        previous_version=written.previous_version,
        validation=candidate.validation,
        rewrite_mode=candidate.rewrite_mode,
    )


def _local_rewrite(old_markdown: str, reflection_markdown: str, hqs_report: HQSReport, next_version: str) -> str:
    weak_dimensions = _weak_dimensions(hqs_report)
    result = old_markdown.rstrip()
    if weak_dimensions:
        result = _append_to_section(
            result,
            "Workflow",
            [
                "Cross-check the draft output against HQS dimensions before finalizing.",
                "Revise weak areas explicitly when task completion, structure, specificity, robustness, or risk control is low.",
            ],
        )
        result = _append_to_section(
            result,
            "Quality Criteria",
            [f"Response improves low-scoring HQS dimensions: {', '.join(weak_dimensions)}."],
        )
        result = _append_to_section(
            result,
            "Failure Modes",
            ["The Skill produces generic output that cannot be evaluated against the task set."],
        )
    result = _append_to_section(
        result,
        "Version Notes",
        [
            f"{next_version}: Evolved from task-set evaluation with average HQS {hqs_report.average_score:.2f}.",
            "Reflection guidance: " + _first_guidance_line(reflection_markdown),
        ],
    )
    return result.rstrip() + "\n"


def _append_to_section(markdown: str, section: str, bullets: list[str]) -> str:
    marker = f"## {section}"
    match = re.search(rf"^##\s+{re.escape(section)}\s*$", markdown, flags=re.MULTILINE)
    if not match:
        return markdown.rstrip() + "\n\n" + marker + "\n\n" + "\n".join(f"- {bullet}" for bullet in bullets)

    next_match = re.search(r"^##\s+.+?\s*$", markdown[match.end() :], flags=re.MULTILINE)
    insert_at = len(markdown) if not next_match else match.end() + next_match.start()
    existing_section = markdown[match.end() : insert_at]
    additions = [bullet for bullet in bullets if bullet not in existing_section]
    if not additions:
        return markdown
    insertion = "\n" + "\n".join(f"- {bullet}" for bullet in additions) + "\n"
    return markdown[:insert_at].rstrip() + insertion + "\n" + markdown[insert_at:].lstrip("\n")


def _weak_dimensions(hqs_report: HQSReport) -> list[str]:
    weak = []
    for dimension in hqs_report.dimensions:
        if not hqs_report.per_task:
            continue
        average = sum(evaluation.scores.get(dimension, 0.0) for evaluation in hqs_report.per_task) / len(
            hqs_report.per_task
        )
        if average < 4.0:
            weak.append(dimension)
    return weak


def _first_guidance_line(reflection_markdown: str) -> str:
    in_guidance = False
    for line in reflection_markdown.splitlines():
        stripped = line.strip()
        if stripped == "## Rewrite Guidance":
            in_guidance = True
            continue
        if in_guidance and stripped.startswith("- "):
            return stripped[2:]
    return "Documented deterministic Skill evolution."


def _build_rewrite_prompt(
    old_markdown: str,
    reflection_markdown: str,
    hqs_report: HQSReport,
    next_version: str,
) -> str:
    return "\n\n".join(
        [
            f"Rewrite this Skill as {next_version}. Keep every required section.",
            "Current SKILL.md:",
            old_markdown,
            "Reflection report:",
            reflection_markdown,
            "HQS JSON:",
            str(hqs_report.to_dict()),
        ]
    )


def _strip_markdown_fence(markdown: str) -> str:
    stripped = markdown.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 2 and lines[-1].strip() == "```":
            return "\n".join(lines[1:-1]).strip()
    return markdown.strip()
