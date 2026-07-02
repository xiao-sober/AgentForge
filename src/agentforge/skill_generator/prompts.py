from __future__ import annotations

import json

from agentforge.skill_generator.requirement_parser import SkillRequirement
from agentforge.skill_generator.skill_schema import REQUIRED_SECTIONS


SKILL_GENERATION_SYSTEM_PROMPT = """\
你是 AgentForge 的 Skill 作者。
只返回一份完整的 SKILL.md Markdown 文档。
不要把输出包在代码块里。
不要在 Markdown 前后添加解释、寒暄或诊断信息。
默认使用中文编写正文内容；如果源需求明确要求其他语言，则跟随源需求。
固定章节标题必须保持英文，以便通过 AgentForge schema 校验。
"""


def build_skill_generation_prompt(input_text: str, requirement: SkillRequirement) -> str:
    required_sections = "\n".join(f"- ## {section}" for section in REQUIRED_SECTIONS)
    requirement_json = json.dumps(requirement.to_dict(), ensure_ascii=False, indent=2)
    return f"""\
请根据原始输入和归一化需求，创建一份合规的 AgentForge SKILL.md。

必须使用以下结构：
- # <Skill Name>
{required_sections}

规则：
- 保留用户的真实意图、边界和约束。
- 正文内容默认使用中文；如果源需求明确指定其他语言，则跟随源需求。
- 使用具体、可复用、可执行的工作流说明。
- 不要编造未提供的事实、工具、截图或数据。
- 原始输入是“创建 Skill 的需求”，不是 Skill 的执行样例。
- 不要在 Examples 章节把“生成 Skill 的请求”原样当成 User Prompt。
- 只有当原始输入包含该 Skill 的具体使用样例时，才写入 Skill 使用样例。
- 如果没有提供具体使用样例，请明确说明“未提供具体使用样例”。
- 保持 Skill 与模型供应商无关，并具备复用性。
- Markdown 标题必须与上述结构完全一致，标题文本保持英文。

归一化需求：
```json
{requirement_json}
```

原始输入：
```text
{input_text}
```
"""
