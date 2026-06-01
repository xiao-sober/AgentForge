from __future__ import annotations

import re
from dataclasses import dataclass


REQUIRED_SECTIONS = [
    "Purpose",
    "When to Use",
    "Inputs",
    "Outputs",
    "Workflow",
    "Constraints",
    "Quality Criteria",
    "Failure Modes",
    "Examples",
    "Version Notes",
]


@dataclass(frozen=True)
class SkillValidationResult:
    valid: bool
    missing_sections: list[str]
    unexpected_sections: list[str]
    has_title: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "valid": self.valid,
            "missing_sections": self.missing_sections,
            "unexpected_sections": self.unexpected_sections,
            "has_title": self.has_title,
        }


def extract_sections(markdown: str) -> list[str]:
    return [match.group(1).strip() for match in re.finditer(r"^##\s+(.+?)\s*$", markdown, flags=re.MULTILINE)]


def validate_skill(markdown: str) -> SkillValidationResult:
    has_title = re.search(r"^#\s+.+\S\s*$", markdown, flags=re.MULTILINE) is not None
    sections = extract_sections(markdown)
    section_set = set(sections)
    missing_sections = [section for section in REQUIRED_SECTIONS if section not in section_set]
    unexpected_sections = [section for section in sections if section not in REQUIRED_SECTIONS]
    return SkillValidationResult(
        valid=has_title and not missing_sections,
        missing_sections=missing_sections,
        unexpected_sections=unexpected_sections,
        has_title=has_title,
    )
