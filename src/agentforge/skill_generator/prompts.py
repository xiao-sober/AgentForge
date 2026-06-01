from __future__ import annotations

import json

from agentforge.skill_generator.requirement_parser import SkillRequirement
from agentforge.skill_generator.skill_schema import REQUIRED_SECTIONS


SKILL_GENERATION_SYSTEM_PROMPT = """\
You are an AgentForge Skill author.
Return only a complete SKILL.md document in Markdown.
Do not wrap the output in a code fence.
Do not include commentary before or after the Markdown.
"""


def build_skill_generation_prompt(input_text: str, requirement: SkillRequirement) -> str:
    required_sections = "\n".join(f"- ## {section}" for section in REQUIRED_SECTIONS)
    requirement_json = json.dumps(requirement.to_dict(), ensure_ascii=False, indent=2)
    return f"""\
Create a compliant AgentForge SKILL.md from the source input and normalized requirement.

Required structure:
- # <Skill Name>
{required_sections}

Rules:
- Preserve the user's intent and constraints.
- Use concrete, reusable workflow instructions.
- Do not invent unavailable facts, tools, screenshots, or data.
- The source input is a requirement for creating a Skill, not a Skill execution example.
- Do not quote the Skill-generation request as a User Prompt in the Examples section.
- Include Skill usage examples only when the source input contains a concrete task example for the generated Skill.
- If no concrete Skill usage example is provided, state that no concrete example was provided.
- Keep the Skill provider-neutral and reusable.
- The Markdown headings must exactly match the required structure.

Normalized requirement:
```json
{requirement_json}
```

Source input:
```text
{input_text}
```
"""
