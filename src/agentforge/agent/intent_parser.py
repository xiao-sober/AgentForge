from __future__ import annotations

import re
from dataclasses import dataclass
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent_type": self.intent_type,
            "query": self.query,
            "requires_skill": self.requires_skill,
            "needs_skill_generation": self.needs_skill_generation,
            "skill_hint": self.skill_hint,
            "confidence": self.confidence,
            "reasons": self.reasons,
        }


def parse_intent(user_input: str) -> Intent:
    query = " ".join(user_input.strip().split())
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
    if re.search(r"\b(list|show|inspect|view|open|read|find)\s+(the\s+)?(latest\s+)?traces?\b", normalized):
        return True
    if re.search(r"\btraces?\s+(list|viewer|detail|details|inspection|summary)\b", normalized):
        return True
    if re.fullmatch(r"\s*traces?\s*", normalized):
        return True
    if re.search(r"\btrace\s+[A-Za-z0-9_.-]+\.json\b", normalized):
        return True
    return _contains_any(original, ["查看 trace", "打开 trace", "查看日志", "查看轨迹"])


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
