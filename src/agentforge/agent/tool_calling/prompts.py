from __future__ import annotations

import json
from typing import Any


TOOL_CALLING_SYSTEM_PROMPT = (
    "You are the AgentForge Tool-Calling Planner. You cannot execute tools directly. "
    "You may choose exactly one tool from available_tools, return final_answer, or return cannot_continue. "
    "All output must be exactly one JSON object. Do not output Markdown, code fences, explanations, "
    "or chain-of-thought text."
)

TOOL_CALLING_REPAIR_SYSTEM_PROMPT = (
    "You repair AgentForge tool-calling planner output. Return exactly one JSON object and no Markdown."
)


def build_tool_calling_prompt(payload: dict[str, Any]) -> str:
    return "\n\n".join(
        [
            "Return the next AgentForge JSON decision from the user request, available tools, and observations.",
            "Allowed JSON shapes:",
            '{"type":"tool_call","tool_name":"select_skill","arguments":{}}',
            '{"type":"final_answer","content":"..."}',
            '{"type":"cannot_continue","reason":"...","needed_input":["..."]}',
            "Rules:",
            "- Return one raw JSON object only. Do not wrap JSON in Markdown code fences.",
            "- Use only tool_name values present in available_tools. Do not invent tools.",
            "- Do not request arbitrary file or shell access.",
            "- If prerequisite state is missing, call the prerequisite tool instead of guessing.",
            "- Do not call retrieve_memory_context repeatedly. Its observation contains memory previews; build_response can access the full memory_context.",
            "- Recommended normal order: retrieve_memory_context -> select_skill -> build_plan -> execute_plan -> observe_execution -> build_response -> final_answer.",
            "- Trace inspection requests: retrieve_memory_context -> inspect_latest_trace -> build_plan -> execute_plan -> build_response -> final_answer.",
            "- Memory query requests: retrieve_memory_context -> build_plan -> execute_plan -> build_response -> final_answer. Do not call inspect_latest_trace unless the user explicitly asks for trace inspection.",
            "- After build_response, final_answer is only a completion signal. Its content must use the latest observation response_preview, or state that the full response was prepared by the Harness.",
            "Current state:",
            json.dumps(payload, ensure_ascii=False, indent=2),
        ]
    )


def build_decision_repair_prompt(raw_output: str, parse_error: str, payload: dict[str, Any]) -> str:
    return "\n\n".join(
        [
            "The previous planner output was not a valid AgentForge JSON decision.",
            f"Parse error: {parse_error}",
            "Return exactly one JSON object with one of these shapes:",
            '{"type":"tool_call","tool_name":"select_skill","arguments":{}}',
            '{"type":"final_answer","content":"..."}',
            '{"type":"cannot_continue","reason":"...","needed_input":["..."]}',
            "Use only tool_name values present in available_tools. Do not use Markdown code fences.",
            "Current state:",
            json.dumps(payload, ensure_ascii=False, indent=2),
            "Invalid output to repair:",
            raw_output[:2000],
        ]
    )
