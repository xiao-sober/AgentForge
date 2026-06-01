from __future__ import annotations

import re
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class SkillRequirement:
    skill_name: str
    skill_slug: str
    purpose: str
    scenario: str
    inputs: list[str]
    outputs: list[str]
    constraints: list[str]
    examples: list[str]
    workflow: list[str]
    quality_criteria: list[str]
    failure_modes: list[str]
    source_text: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def parse_requirement(input_text: str) -> SkillRequirement:
    cleaned = _normalize_input(input_text)
    if not cleaned:
        raise ValueError("Requirement input is empty.")

    user_lines = _extract_user_lines(cleaned)
    analysis_text = "\n".join(user_lines) if user_lines else cleaned
    lowered = analysis_text.lower()

    domain = _detect_domain(analysis_text, lowered)
    skill_name, skill_slug = _name_for_domain(domain, analysis_text)
    outputs = _detect_outputs(analysis_text, lowered)
    inputs = _detect_inputs(analysis_text, lowered)
    scenario = _detect_scenario(domain, analysis_text, lowered)

    purpose = _build_purpose(domain, analysis_text, outputs)
    constraints = _detect_constraints(analysis_text, lowered)
    quality_criteria = _detect_quality_criteria(domain, outputs)
    failure_modes = _default_failure_modes(domain)
    workflow = _default_workflow(domain, outputs)
    examples = _detect_examples(cleaned, analysis_text)

    return SkillRequirement(
        skill_name=skill_name,
        skill_slug=skill_slug,
        purpose=purpose,
        scenario=scenario,
        inputs=inputs,
        outputs=outputs,
        constraints=constraints,
        examples=examples,
        workflow=workflow,
        quality_criteria=quality_criteria,
        failure_modes=failure_modes,
        source_text=cleaned,
    )


def _normalize_input(input_text: str) -> str:
    lines = [line.strip() for line in input_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return "\n".join(line for line in lines if line)


def _extract_user_lines(text: str) -> list[str]:
    user_lines: list[str] = []
    for line in text.splitlines():
        match = re.match(r"^(user|用户|用戶)\s*[:：]\s*(.+)$", line, flags=re.IGNORECASE)
        if match:
            user_lines.append(match.group(2).strip())
    return user_lines


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _contains_word(text: str, words: list[str]) -> bool:
    return any(re.search(rf"\b{re.escape(word)}\b", text, flags=re.IGNORECASE) for word in words)


def _detect_domain(text: str, lowered: str) -> str:
    if _contains_word(lowered, ["ui", "ux"]) or _contains_any(lowered, ["dashboard", "screenshot"]) or _contains_any(
        text, ["界面", "页面", "网页", "截图", "后台", "管理系统", "视觉", "布局", "图表", "交互"]
    ):
        return "ui_review"
    if _contains_any(lowered, ["api", "endpoint"]) or _contains_any(text, ["接口"]):
        return "api_design"
    if _contains_any(lowered, ["test", "pytest", "unit test"]) or _contains_any(text, ["测试", "单元测试"]):
        return "testing"
    return "general"


def _name_for_domain(domain: str, text: str) -> tuple[str, str]:
    if domain == "ui_review":
        return "UI Review Skill", "ui_review_skill"
    if domain == "api_design":
        return "API Design Skill", "api_design_skill"
    if domain == "testing":
        return "Testing Skill", "testing_skill"

    phrase = _extract_candidate_name(text)
    slug = _slugify(phrase)
    if not slug.endswith("_skill"):
        slug = f"{slug}_skill"
    return phrase, slug


def _extract_candidate_name(text: str) -> str:
    patterns = [
        r"生成(?:一个|一個|一份)?(.+?)Skill",
        r"做(?:一个|一個)?(.+?)Skill",
        r"create\s+(?:a|an)?\s*(.+?)\s*skill",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            candidate = match.group(1).strip(" ，,。.")
            if candidate:
                return _title_from_text(candidate)
    return "Generated Skill"


def _title_from_text(text: str) -> str:
    ascii_words = re.findall(r"[A-Za-z0-9]+", text)
    if ascii_words:
        return " ".join(word.capitalize() for word in ascii_words[:5]) + " Skill"
    return "Generated Skill"


def _slugify(text: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", text.lower())
    if not words:
        return "generated_skill"
    return "_".join(words[:6])


def _detect_outputs(text: str, lowered: str) -> list[str]:
    outputs: list[str] = []
    output_rules = [
        ("issues", ["issue", "problem", "问题"]),
        ("reasons", ["reason", "原因"]),
        ("optimization suggestions", ["suggestion", "recommendation", "优化", "建议"]),
        ("priority", ["priority", "优先级"]),
        ("structured report", ["format", "结构", "格式", "报告"]),
        ("examples", ["example", "案例", "示例"]),
    ]
    combined = lowered + "\n" + text
    for output, keywords in output_rules:
        if _contains_any(combined, keywords):
            outputs.append(output)
    if not outputs:
        outputs.extend(["structured analysis", "actionable recommendations"])
    if "structured report" not in outputs:
        outputs.append("structured report")
    return _dedupe(outputs)


def _detect_inputs(text: str, lowered: str) -> list[str]:
    inputs: list[str] = []
    if "screenshot" in lowered or "截图" in text:
        inputs.append("screenshot")
    if _contains_any(text, ["对话", "需求", "描述"]) or _contains_any(lowered, ["conversation", "requirement", "description"]):
        inputs.append("user description")
    if _contains_any(text, ["页面", "网页", "后台", "管理系统"]) or _contains_any(lowered, ["page", "dashboard"]):
        inputs.append("page context")
    if not inputs:
        inputs.append("user requirement")
    return _dedupe(inputs)


def _detect_scenario(domain: str, text: str, lowered: str) -> str:
    if domain == "ui_review":
        if _contains_any(text, ["后台", "管理系统", "数据驾驶舱", "图表"]) or _contains_any(lowered, ["dashboard", "admin"]):
            return "B-end dashboard, admin, and management system UI review."
        return "UI review for screenshots, pages, and product interface descriptions."
    if domain == "api_design":
        return "API design and endpoint review."
    if domain == "testing":
        return "Software testing workflow design and test case improvement."
    return "Reusable task execution based on the user's requirement."


def _build_purpose(domain: str, text: str, outputs: list[str]) -> str:
    if domain == "ui_review":
        return "Analyze UI screenshots or page descriptions and produce structured, actionable improvement advice."
    if domain == "api_design":
        return "Analyze API requirements and produce clear endpoint design guidance."
    if domain == "testing":
        return "Turn testing needs into focused test plans, cases, and quality checks."
    return "Turn the user requirement into a repeatable workflow that produces " + ", ".join(outputs) + "."


def _detect_constraints(text: str, lowered: str) -> list[str]:
    constraints = [
        "Do not invent facts, UI elements, or data that are not visible or described.",
        "Prefer concrete, actionable guidance over generic advice.",
        "Preserve explicit output format requirements from the user.",
    ]
    if "优先级" in text or "priority" in lowered:
        constraints.append("Assign priorities only when there is enough evidence to compare impact.")
    if "截图" in text or "screenshot" in lowered:
        constraints.append("When screenshot details are unclear, state the uncertainty before suggesting fixes.")
    return constraints


def _detect_quality_criteria(domain: str, outputs: list[str]) -> list[str]:
    criteria = [
        "Output follows the requested structure.",
        "Advice is specific enough for the user to act on.",
        "Reasoning is tied to the provided input.",
    ]
    if domain == "ui_review":
        criteria.extend(
            [
                "Covers layout, visual hierarchy, interaction flow, and data expression when relevant.",
                "Separates symptoms, causes, recommendations, and priority labels.",
            ]
        )
    if "priority" in outputs:
        criteria.append("Priority labels reflect user impact and implementation urgency.")
    return _dedupe(criteria)


def _default_failure_modes(domain: str) -> list[str]:
    failures = [
        "Input is too vague to support a specific recommendation.",
        "The response ignores the required output structure.",
        "The response invents details that were not provided.",
    ]
    if domain == "ui_review":
        failures.append("The analysis focuses only on visual style and misses workflow or data readability issues.")
    return failures


def _default_workflow(domain: str, outputs: list[str]) -> list[str]:
    if domain == "ui_review":
        return [
            "Identify the available input: screenshot, page description, or user goal.",
            "Extract visible or described UI areas, data elements, interactions, and constraints.",
            "Analyze layout, visual hierarchy, chart readability, interaction closure, and data expression.",
            "List issues with supporting reasons and concrete optimization suggestions.",
            "Assign priority when the impact and urgency are clear.",
            "State uncertainties and ask for missing context when needed.",
        ]
    return [
        "Restate the user's goal and available context.",
        "Extract constraints, expected inputs, expected outputs, and success criteria.",
        "Execute the task using a clear step-by-step workflow.",
        "Return structured results with concrete next actions.",
        "Call out assumptions, risks, or missing information.",
    ]


def _detect_examples(cleaned: str, analysis_text: str) -> list[str]:
    examples: list[str] = []
    for line in cleaned.splitlines():
        match = re.search(r"(例如|比如|示例|案例|example|sample)\s*[:：]?\s*(.+)$", line, flags=re.IGNORECASE)
        if match:
            normalized = re.sub(
                r"^(user|用户|用戶|assistant|助手)\s*[:：]\s*",
                "",
                match.group(2),
                flags=re.IGNORECASE,
            ).strip()
            if normalized:
                examples.append(normalized)
    return examples


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result
