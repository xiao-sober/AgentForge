from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Intent:
    intent_type: str
    query: str
    requires_skill: bool
    needs_skill_generation: bool
    skill_hint: str | None
    confidence: float
    reasons: list[str]
    task_type: str | None = None
    task_input: dict[str, Any] = field(default_factory=dict)
    task_options: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent_type": self.intent_type,
            "query": self.query,
            "requires_skill": self.requires_skill,
            "needs_skill_generation": self.needs_skill_generation,
            "skill_hint": self.skill_hint,
            "confidence": self.confidence,
            "reasons": self.reasons,
            "task_type": self.task_type,
            "task_input": self.task_input,
            "task_options": self.task_options,
        }


def parse_intent(user_input: str) -> Intent:
    raw_query = user_input.strip()
    query = " ".join(raw_query.split())
    if not query:
        return Intent(
            intent_type="empty",
            query="",
            requires_skill=False,
            needs_skill_generation=False,
            skill_hint=None,
            confidence=1.0,
            reasons=["empty_input"],
        )

    lowered = query.lower()
    reasons: list[str] = []
    skill_hint = _detect_skill_hint(lowered)

    if _contains_any(
        lowered,
        [
            "generate skill",
            "generate a skill",
            "create skill",
            "create a skill",
            "build a skill",
            "make a skill",
            "write a skill",
            "new skill",
            "skill.md",
        ],
    ) or _contains_any(
        query, ["生成 Skill", "创建 Skill", "新 Skill", "生成一个 Skill", "生成一个Skill"]
    ) or _matches_chinese_skill_generation(query):
        reasons.append("explicit_skill_generation")
        return Intent(
            intent_type="generate_skill",
            query=query,
            requires_skill=False,
            needs_skill_generation=True,
            skill_hint=skill_hint,
            confidence=0.95,
            reasons=reasons,
            task_type="skill_generate",
            task_input={"input": query},
        )

    if _is_skill_evolution_request(lowered, query):
        task_options = _skill_evolution_options(query)
        return Intent(
            intent_type="evolve_skill",
            query=query,
            requires_skill=True,
            needs_skill_generation=False,
            skill_hint=skill_hint,
            confidence=0.85,
            reasons=["explicit_skill_evolution"],
            task_type="skill_evolve",
            task_input={},
            task_options=task_options,
        )

    if _contains_any(lowered, ["list skills", "show skills"]) or _contains_any(query, ["列出 Skill", "查看 Skill"]):
        return Intent(
            intent_type="inspect_skills",
            query=query,
            requires_skill=False,
            needs_skill_generation=False,
            skill_hint=skill_hint,
            confidence=0.9,
            reasons=["inspect_skills"],
        )

    if _is_trace_inspection_request(lowered, query):
        return Intent(
            intent_type="inspect_traces",
            query=query,
            requires_skill=False,
            needs_skill_generation=False,
            skill_hint=skill_hint,
            confidence=0.8,
            reasons=["inspect_traces"],
            task_type="trace_diagnosis",
            task_input=_trace_diagnosis_input(query),
        )

    if _is_memory_query_request(lowered):
        return Intent(
            intent_type="query_memory",
            query=query,
            requires_skill=False,
            needs_skill_generation=False,
            skill_hint=skill_hint,
            confidence=0.85,
            reasons=["query_memory"],
        )

    reserved_task_type = None if skill_hint and "skill" in lowered else _reserved_task_type(lowered)
    if reserved_task_type:
        return Intent(
            intent_type="reserved_task",
            query=query,
            requires_skill=False,
            needs_skill_generation=False,
            skill_hint=skill_hint,
            confidence=0.7,
            reasons=[f"reserved_{reserved_task_type}"],
            task_type=reserved_task_type,
            task_input={"input": raw_query},
        )

    skill_action = _contains_any(
        lowered,
        [
            "review",
            "analyze",
            "evaluate",
            "summarize",
            "rewrite",
            "design",
            "test",
            "run skill",
            "use skill",
        ],
    ) or _contains_any(query, ["分析", "评估", "审查", "复盘", "总结", "设计", "测试", "优化"])
    if skill_action:
        reasons.append("task_action_detected")
        return Intent(
            intent_type="run_skill",
            query=query,
            requires_skill=True,
            needs_skill_generation=False,
            skill_hint=skill_hint,
            confidence=0.75,
            reasons=reasons,
            task_type="skill_run",
            task_input={"input": query},
            task_options={"skill_slug": skill_hint} if skill_hint else {},
        )

    return Intent(
        intent_type="chat",
        query=query,
        requires_skill=False,
        needs_skill_generation=False,
        skill_hint=skill_hint,
        confidence=0.6,
        reasons=["fallback_chat"],
    )


def _detect_skill_hint(lowered: str) -> str | None:
    tokens = set(_tokens(lowered))
    api_terms = {"api", "endpoint", "json", "schema", "contract", "response"}
    ui_terms = {"ui", "ux", "dashboard", "screenshot", "layout", "screen", "page"}
    if tokens & api_terms:
        return "api_design_skill"
    if tokens & ui_terms or "user interface" in lowered:
        return "ui_review_skill"
    if tokens & {"test", "pytest"} or "unit test" in lowered:
        return "testing_skill"
    return None


def _is_trace_inspection_request(lowered: str, original: str) -> bool:
    normalized = lowered.replace("_", " ")
    if re.search(r"\b(list|show|inspect|view|open|read|find|diagnose)\s+(the\s+)?(latest\s+)?traces?\b", normalized):
        return True
    if re.search(r"\btraces?\s+(list|viewer|detail|details|inspection|summary)\b", normalized):
        return True
    if re.fullmatch(r"\s*traces?\s*", normalized):
        return True
    if re.search(r"\btrace\s+[A-Za-z0-9_.-]+\.json\b", normalized):
        return True
    return _contains_any(original, ["查看 trace", "打开 trace", "查看日志", "查看轨迹"])


def _trace_diagnosis_input(query: str) -> dict[str, Any]:
    run_id_match = re.search(r"\brun_[A-Za-z0-9_:-]+\b", query)
    if run_id_match:
        return {"run_id": run_id_match.group(0)}
    trace_match = re.search(r"\b([A-Za-z0-9_.-]+\.json)\b", query)
    if trace_match:
        return {"trace_file": trace_match.group(1)}
    return {"latest": True}


def _is_skill_evolution_request(lowered: str, original: str) -> bool:
    normalized = lowered.replace("_", " ")
    if re.search(r"\b(evolve|improve|rewrite|reinforce|optimi[sz]e)\s+(a\s+)?skills?\b", normalized):
        return True
    if re.search(r"\bskills?\s+(evolution|rewrite|reinforcement|improvement)\b", normalized):
        return True
    return _contains_any(original, ["演进 Skill", "改进 Skill", "优化 Skill", "重写 Skill", "强化 Skill"])


def _skill_evolution_options(query: str) -> dict[str, Any]:
    options: dict[str, Any] = {}
    skill_match = re.search(r"\b(skills[/\\][^\s\"']*SKILL\.md)\b", query)
    if skill_match:
        options["skill_path"] = skill_match.group(1)
    taskset_match = re.search(r"\b(tasksets[/\\][^\s\"']*\.(?:json|ya?ml))\b", query)
    if taskset_match:
        options["taskset_path"] = taskset_match.group(1)
    max_iterations_match = re.search(r"\bmax[_ -]?iterations\s*[:=]\s*(\d+)\b", query, flags=re.IGNORECASE)
    if max_iterations_match:
        options["max_iterations"] = int(max_iterations_match.group(1))
    return options


def _reserved_task_type(lowered: str) -> str | None:
    normalized = lowered.replace("_", " ")
    action_terms_zh = [
        "\u5206\u6790",
        "\u5ba1\u67e5",
        "\u68c0\u67e5",
        "\u8bc4\u5ba1",
        "\u8bca\u65ad",
        "\u8c03\u8bd5",
        "\u603b\u7ed3",
        "\u63d0\u53d6",
        "\u6e05\u7406",
    ]
    if _contains_any(
        normalized,
        [
            "\u4ee3\u7801",
            "\u6e90\u7801",
            "\u4ed3\u5e93",
            "\u9879\u76ee",
            "\u6a21\u5757",
            "\u51fd\u6570",
            "\u811a\u672c",
            "\u524d\u7aef",
            "\u540e\u7aef",
        ],
    ) and _contains_any(normalized, action_terms_zh):
        return "code_analysis"
    if _contains_any(
        normalized,
        [
            "\u6587\u6863",
            "\u6587\u4ef6",
            "\u62a5\u544a",
            "\u6587\u7ae0",
            "\u8bba\u6587",
            "\u8bf4\u660e",
        ],
    ) and _contains_any(normalized, action_terms_zh):
        return "document_analysis"
    if _contains_any(
        normalized,
        [
            "\u6570\u636e",
            "\u6570\u636e\u96c6",
            "\u8868\u683c",
            "\u7535\u5b50\u8868\u683c",
        ],
    ) and _contains_any(normalized, action_terms_zh):
        return "data_analysis"
    if re.search(r"\b(code|source|repository|repo|python|typescript|javascript|module|function)\b", normalized) and _contains_any(
        normalized, action_terms_zh
    ):
        return "code_analysis"
    if re.search(r"\b(document|pdf|docx|markdown|report|article|paper)\b", normalized) and _contains_any(
        normalized, action_terms_zh
    ):
        return "document_analysis"
    if re.search(r"\b(data|dataset|csv|excel|spreadsheet|jsonl|table)\b", normalized) and _contains_any(
        normalized, action_terms_zh
    ):
        return "data_analysis"
    if re.search(r"\b(code|source|repository|repo|python|typescript|javascript|module|function)\b", normalized) and re.search(
        r"\b(analyze|analyse|review|inspect|debug|diagnose)\b",
        normalized,
    ):
        return "code_analysis"
    if re.search(r"\b(document|pdf|docx|markdown|report|article|paper)\b", normalized) and re.search(
        r"\b(analyze|analyse|review|summarize|extract|inspect)\b",
        normalized,
    ):
        return "document_analysis"
    if re.search(r"\b(data|dataset|csv|excel|spreadsheet|jsonl|table)\b", normalized) and re.search(
        r"\b(analyze|analyse|summarize|inspect|profile|clean)\b",
        normalized,
    ):
        return "data_analysis"
    return None


def _is_memory_query_request(lowered: str) -> bool:
    normalized = lowered.replace("_", " ")
    if re.search(r"\b(what|show|list|summarize|query|search|inspect|retrieve)\b.*\b(memory|memories|episodic|semantic|remembered|remember)\b", normalized):
        return True
    if re.search(r"\b(memory|memories|episodic|semantic)\b.*\b(about|for|query|summary|status|recent|dry runs?)\b", normalized):
        return True
    if re.search(r"\bwhat\s+do\s+you\s+(remember|know)\b", normalized):
        return True
    return False


def _matches_chinese_skill_generation(text: str) -> bool:
    return bool(re.search(r"(生成|创建|新建|制作|做).{0,40}Skill", text, flags=re.IGNORECASE))


def _contains_any(text: str, needles: list[str]) -> bool:
    return any(needle in text for needle in needles)


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9_]+", text.lower())
