from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentforge.common.file_store import write_json, write_text
from agentforge.common.llm_client import LLMClient, LLMProviderError
from agentforge.common.trace import trace_timestamp, write_trace
from agentforge.skill_evolver.task_loader import Task, TaskSet
from agentforge.skill_evolver.version_manager import parse_skill_version_path
from agentforge.skill_generator.skill_schema import validate_skill
from agentforge.workflows import WorkflowRunner


@dataclass(frozen=True)
class TaskOutput:
    task_id: str
    input: str
    output: str
    output_path: Path | None = None
    error: str | None = None
    output_contract: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "input": self.input,
            "output": self.output,
            "output_path": str(self.output_path) if self.output_path else None,
            "error": self.error,
            "output_contract": self.output_contract,
        }


@dataclass(frozen=True)
class SkillRunResult:
    skill_path: Path
    run_dir: Path
    outputs: list[TaskOutput]
    result_path: Path
    trace_path: Path
    mode: str
    run_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_path": str(self.skill_path),
            "run_dir": str(self.run_dir),
            "outputs": [output.to_dict() for output in self.outputs],
            "result_path": str(self.result_path),
            "trace_path": str(self.trace_path),
            "mode": self.mode,
            "run_id": self.run_id,
        }


SKILL_RUN_SYSTEM_PROMPT = (
    "你是 AgentForge 的 Skill 执行器。请根据提供的 SKILL.md 处理任务输入。"
    "必须遵循 Skill 的工作流和约束。只返回 Markdown，并使用以下固定英文输出契约："
    "# Skill Run Output, ## Task, ## Applied Skill, ## Result, ## Assumptions and Gaps。"
    "正文内容默认使用中文；如果任务或 Skill 明确要求其他语言，则跟随该要求。"
    "不要输出思维链、供应商诊断信息或隐藏系统文本。"
)


def run_skill(
    skill_path: Path | str,
    input_text: str,
    project_root: Path | str = ".",
    llm_client: LLMClient | None = None,
) -> SkillRunResult:
    taskset = TaskSet(
        name="single_input",
        description="Single Skill execution from CLI input.",
        tasks=[Task(task_id="input", input=input_text, criteria=[], metadata={})],
    )
    return run_skill_on_taskset(skill_path, taskset, project_root=project_root, llm_client=llm_client)


def run_skill_on_taskset(
    skill_path: Path | str,
    taskset: TaskSet,
    project_root: Path | str = ".",
    llm_client: LLMClient | None = None,
) -> SkillRunResult:
    root = Path(project_root).resolve()
    resolved_skill_path = Path(skill_path).resolve()
    if not resolved_skill_path.exists():
        raise ValueError(f"Skill not found: {resolved_skill_path}")

    skill_markdown = resolved_skill_path.read_text(encoding="utf-8")
    validation = validate_skill(skill_markdown)
    if not validation.valid:
        raise ValueError(f"Skill failed schema validation: {validation.to_dict()}")

    info = parse_skill_version_path(resolved_skill_path)
    return run_skill_markdown_on_taskset(
        skill_markdown=skill_markdown,
        skill_path=resolved_skill_path,
        skill_slug=info.skill_slug,
        version=info.version,
        taskset=taskset,
        project_root=root,
        llm_client=llm_client,
    )


def run_skill_markdown_on_taskset(
    skill_markdown: str,
    skill_path: Path | str,
    skill_slug: str,
    version: str,
    taskset: TaskSet,
    project_root: Path | str = ".",
    llm_client: LLMClient | None = None,
) -> SkillRunResult:
    root = Path(project_root).resolve()
    resolved_skill_path = Path(skill_path).resolve()
    validation = validate_skill(skill_markdown)
    if not validation.valid:
        raise ValueError(f"Skill failed schema validation: {validation.to_dict()}")

    run_service = WorkflowRunner.for_task(
        root,
        workflow_id="skill_run_workflow",
        task_type="skill_run",
        steps=["load_skill", "load_taskset", "run_task", "write_result"],
    )
    run_id = run_service.start_run(
        task_type="skill_run",
        title=f"Run Skill: {skill_slug} {version}",
        input_data={"skill_path": str(resolved_skill_path), "taskset": taskset.to_dict()},
    )
    run_dir = root / "runs" / skill_slug / version / trace_timestamp()
    output_dir = run_dir / "outputs"
    write_json(run_dir / "taskset.json", taskset.to_dict())
    write_text(run_dir / "skill_snapshot.md", skill_markdown)

    steps: list[dict[str, Any]] = [
        {
            "name": "load_skill",
            "status": "completed",
            "path": str(resolved_skill_path),
            "validation": validation.to_dict(),
        },
        {"name": "load_taskset", "status": "completed", "task_count": len(taskset.tasks)},
    ]
    run_service.record_step(run_id, steps[0], 1)
    run_service.record_step(run_id, steps[1], 2)
    errors: list[dict[str, Any]] = []
    outputs: list[TaskOutput] = []
    mode = "model" if llm_client else "local"

    for task in taskset.tasks:
        output = ""
        error = None
        output_contract: dict[str, Any] | None = None
        try:
            output, output_contract = _run_single_task(skill_markdown, task, llm_client=llm_client)
            status = "completed"
        except Exception as exc:
            status = "failed"
            error = str(exc)
            errors.append({"task_id": task.task_id, "error_type": exc.__class__.__name__, "message": str(exc)})
            if llm_client is not None:
                steps.append(
                    {
                        "name": "run_task",
                        "status": status,
                        "task_id": task.task_id,
                        "output_path": None,
                        "output_contract": None,
                    }
                )
                run_service.record_step(run_id, steps[-1], len(steps))
                run_service.fail_run(
                    run_id,
                    {"error_type": exc.__class__.__name__, "message": str(exc), "task_id": task.task_id},
                    output_data={"run_dir": _relative_or_absolute(run_dir, root), "mode": mode, "errors": errors},
                )
                failure_trace_path = write_trace(
                    project_root=root,
                    trace_type="skill_execution",
                    input_data={"skill_path": str(resolved_skill_path), "taskset": taskset.to_dict()},
                    output={"run_dir": _relative_or_absolute(run_dir, root), "result_path": None},
                    steps=steps,
                    artifacts=[{"type": "run_directory", "path": _relative_or_absolute(run_dir, root)}],
                    errors=errors,
                )
                run_service.record_run(
                    task_type="skill_run",
                    title=f"Run Skill: {skill_slug} {version}",
                    input_data={"skill_path": str(resolved_skill_path), "taskset": taskset.to_dict()},
                    output_data={
                        "run_dir": _relative_or_absolute(run_dir, root),
                        "result_path": None,
                        "mode": mode,
                        "errors": errors,
                    },
                    trace_path=failure_trace_path,
                    status="failed",
                    run_id=run_id,
                    steps=steps,
                    artifacts=[{"type": "run_directory", "path": _relative_or_absolute(run_dir, root)}],
                )
                raise LLMProviderError(
                    f"Provider Skill execution failed for task '{task.task_id}': {exc}"
                ) from exc
            output = _local_fallback_output(skill_markdown, task, execution_error=str(exc))
            output_contract = _output_contract_report(output, repaired=False, source="local_fallback_after_error")

        output_path = write_text(output_dir / f"{_safe_filename(task.task_id)}.md", output)
        outputs.append(
            TaskOutput(
                task_id=task.task_id,
                input=task.input,
                output=output,
                output_path=output_path,
                error=error,
                output_contract=output_contract,
            )
        )
        steps.append(
            {
                "name": "run_task",
                "status": status,
                "task_id": task.task_id,
                "output_path": str(output_path),
                "output_contract": output_contract,
            }
        )
        run_service.record_step(run_id, steps[-1], len(steps))
        run_service.update_run(
            run_id,
            "running",
            {
                "run_dir": _relative_or_absolute(run_dir, root),
                "mode": mode,
                "completed_tasks": len(outputs),
                "total_tasks": len(taskset.tasks),
            },
        )

    result_payload = {
        "skill": {
            "skill_slug": skill_slug,
            "version": version,
            "skill_path": str(resolved_skill_path),
        },
        "taskset": taskset.to_dict(),
        "mode": mode,
        "provider": llm_client.metadata() if llm_client else None,
        "outputs": [output.to_dict() for output in outputs],
    }
    result_path = write_json(run_dir / "run_result.json", result_payload)
    trace_path = write_trace(
        project_root=root,
        trace_type="skill_execution",
        input_data={"skill_path": str(resolved_skill_path), "taskset": taskset.to_dict()},
        output={"run_dir": _relative_or_absolute(run_dir, root), "result_path": _relative_or_absolute(result_path, root)},
        steps=steps,
        artifacts=[
            {"type": "run_result", "path": _relative_or_absolute(result_path, root)},
            {"type": "run_directory", "path": _relative_or_absolute(run_dir, root)},
        ],
        errors=errors,
    )
    run_id = run_service.record_run(
        task_type="skill_run",
        title=f"Run Skill: {skill_slug} {version}",
        input_data={"skill_path": str(resolved_skill_path), "taskset": taskset.to_dict()},
        output_data={
            "run_dir": _relative_or_absolute(run_dir, root),
            "result_path": _relative_or_absolute(result_path, root),
            "mode": mode,
            "output_count": len(outputs),
            "errors": errors,
        },
        trace_path=trace_path,
        status="failed" if errors else "completed",
        run_id=run_id,
        steps=steps,
        artifacts=[
            {"type": "run_result", "path": _relative_or_absolute(result_path, root)},
            {"type": "run_directory", "path": _relative_or_absolute(run_dir, root)},
        ],
    )

    return SkillRunResult(
        skill_path=resolved_skill_path,
        run_dir=run_dir,
        outputs=outputs,
        result_path=result_path,
        trace_path=trace_path,
        mode=mode,
        run_id=run_id,
    )


def _run_single_task(skill_markdown: str, task: Task, llm_client: LLMClient | None = None) -> tuple[str, dict[str, Any]]:
    if llm_client:
        prompt = "\n\n".join(
            [
                "待执行的 SKILL.md：",
                skill_markdown,
                "任务输入：",
                task.input,
                "输出契约：",
                "- 只返回 Markdown。",
                "- 必须以 '# Skill Run Output' 开头。",
                "- 必须包含 '## Task'、'## Applied Skill'、'## Result' 和 '## Assumptions and Gaps'。",
                "- 这些契约标题必须保持英文，正文内容默认使用中文。",
                "- 不要包含供应商诊断、思维链或隐藏系统文本。",
                "- 不要编造超出任务输入和 Skill 约束的事实。",
            ]
        )
        raw_output = llm_client.complete(prompt, system_prompt=SKILL_RUN_SYSTEM_PROMPT)
        return _normalize_provider_task_output(raw_output, skill_markdown, task)
    output = _local_fallback_output(skill_markdown, task)
    return output, _output_contract_report(output, repaired=False, source="local")


def _local_fallback_output(skill_markdown: str, task: Task, execution_error: str | None = None) -> str:
    title = _extract_title(skill_markdown)
    workflow = _extract_section_lines(skill_markdown, "Workflow")
    constraints = _extract_section_lines(skill_markdown, "Constraints")
    criteria = _extract_section_lines(skill_markdown, "Quality Criteria")
    task_terms = ", ".join(_keywords(task.input)[:6]) or "the supplied task"
    insufficient_context = _is_insufficient_context(task.input, title)

    lines = [
        "# Skill Run Output",
        "",
        "## Task",
        "",
        task.input.strip(),
        "",
        "## Applied Skill",
        "",
        f"- {title}",
        "",
        "## Result",
        "",
    ]
    if insufficient_context:
        lines.extend(
            [
                f"- Restated intent: review the task about {task_terms}.",
                "- Available context is insufficient for a concrete UI diagnosis.",
                "- Needed input: screenshot, page description, visible layout details, data density, interaction states, or target user goal.",
                "- Local result: no specific UI issue is asserted because the provided input does not describe the actual interface.",
            ]
        )
    else:
        lines.extend(
            [
                f"- Restated intent: handle the task about {task_terms}.",
                "- Recommended approach: follow the Skill workflow and return a structured, evidence-based result.",
                "- Actionable output: identify concrete findings, explain why they matter, and list next steps.",
            ]
        )
    lines.extend(
        [
            "",
            "## Workflow Used",
            "",
        ]
    )
    lines.extend(_limit_bullets(workflow, fallback=["Restate the task.", "Apply the Skill workflow.", "Return structured results."]))
    lines.extend(["", "## Constraints Observed", ""])
    lines.extend(_limit_bullets(constraints, fallback=["Do not invent facts beyond the task input."]))
    lines.extend(["", "## Quality Checks", ""])
    lines.extend(_limit_bullets(criteria, fallback=["Output is specific, structured, and actionable."]))
    lines.extend(["", "## Assumptions and Gaps", ""])
    lines.append("- This deterministic local runner does not call a model; it records a transparent baseline output.")
    if execution_error:
        lines.append(f"- Model execution failed, so this fallback output was used: {execution_error}")
    return "\n".join(lines).rstrip() + "\n"


def _normalize_provider_task_output(raw_output: str, skill_markdown: str, task: Task) -> tuple[str, dict[str, Any]]:
    raw = raw_output.strip()
    if not raw:
        raise ValueError("Provider returned empty task output.")
    if _provider_output_contract_valid(raw):
        output = raw.rstrip() + "\n"
        return output, _output_contract_report(output, repaired=False, source="provider")

    title = _extract_title(skill_markdown)
    repaired = "\n".join(
        [
            "# Skill Run Output",
            "",
            "## Task",
            "",
            task.input.strip(),
            "",
            "## Applied Skill",
            "",
            f"- {title}",
            "",
            "## Result",
            "",
            raw,
            "",
            "## Assumptions and Gaps",
            "",
            "- Provider output did not fully match the AgentForge output contract, so it was wrapped without changing its content.",
            "- Treat unsupported details as unverified unless they are grounded in the task input.",
        ]
    ).rstrip() + "\n"
    return repaired, _output_contract_report(repaired, repaired=True, source="provider")


def _provider_output_contract_valid(markdown: str) -> bool:
    required = ["# Skill Run Output", "## Task", "## Applied Skill", "## Result", "## Assumptions and Gaps"]
    return all(section in markdown for section in required)


def _output_contract_report(output: str, repaired: bool, source: str) -> dict[str, Any]:
    missing = [
        section
        for section in ["# Skill Run Output", "## Task", "## Applied Skill", "## Result", "## Assumptions and Gaps"]
        if section not in output
    ]
    return {
        "source": source,
        "valid": not missing,
        "repaired": repaired,
        "missing_sections": missing,
        "contract": "skill_run_output.v1",
    }


def _extract_title(markdown: str) -> str:
    for line in markdown.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return "Untitled Skill"


def _extract_section_lines(markdown: str, section: str) -> list[str]:
    lines = markdown.splitlines()
    collected: list[str] = []
    in_section = False
    for line in lines:
        if line.strip() == f"## {section}":
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if in_section and line.strip():
            collected.append(line.strip())
    return collected


def _limit_bullets(lines: list[str], fallback: list[str], limit: int = 5) -> list[str]:
    selected = lines[:limit] if lines else fallback
    result = []
    for line in selected:
        cleaned = line.lstrip("-0123456789. ").strip()
        if cleaned:
            result.append(f"- {cleaned}")
    return result


def _keywords(text: str) -> list[str]:
    normalized = "".join(char.lower() if char.isalnum() else " " for char in text)
    stopwords = {"the", "and", "for", "with", "this", "that", "from", "into", "about", "please"}
    result: list[str] = []
    for token in normalized.split():
        if len(token) >= 3 and token not in stopwords and token not in result:
            result.append(token)
    return result


def _is_insufficient_context(input_text: str, skill_title: str) -> bool:
    lowered = input_text.lower()
    ui_request = any(word in lowered for word in ["ui", "ux", "dashboard", "layout", "screen", "page", "form"])
    if not ui_request and "ui" not in skill_title.lower():
        return False
    concrete_terms = {
        "screenshot",
        "image",
        "chart",
        "table",
        "sidebar",
        "button",
        "form",
        "modal",
        "label",
        "contrast",
        "dense",
        "crowded",
        "kpi",
        "navigation",
        "error",
        "validation",
        "state",
        "metrics",
        "data",
    }
    tokens = set(_keywords(input_text))
    has_concrete_detail = bool(tokens & concrete_terms)
    return len(tokens) <= 6 and not has_concrete_detail


def _safe_filename(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value.strip())
    return cleaned or "task"


def _relative_or_absolute(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)
