from __future__ import annotations

from pathlib import Path
from typing import Any

from agentforge.agent.skill_selector import list_available_skills
from agentforge.common.llm_client import LLMClient
from agentforge.skill_evolver.evolution_loop import evolve_skill
from agentforge.skill_evolver.skill_runner import run_skill
from agentforge.skill_generator.generator import generate_skill_from_input
from agentforge.tasks.schemas import TaskRequest, TaskResult


def handle_skill_generate_task(
    request: TaskRequest,
    project_root: Path,
    llm_client: LLMClient | None,
) -> TaskResult:
    payload = request.payload()
    input_text = _required_string(payload, "input")
    result = generate_skill_from_input(input_text, project_root=project_root, llm_client=llm_client)
    output = {
        "skill_slug": result.requirement.skill_slug,
        "skill_name": result.requirement.skill_name,
        "version": result.version,
        "skill_path": str(result.skill_path),
        "relative_skill_path": _relative_or_absolute(result.skill_path, project_root),
        "trace_path": str(result.trace_path),
        "run_id": result.run_id,
        "valid": result.validation_result.valid,
        "missing_sections": result.validation_result.missing_sections,
        "generation_mode": result.generation_mode,
    }
    return TaskResult(
        task_type=request.task_type,
        status="completed" if result.validation_result.valid else "failed",
        run_id=result.run_id,
        output=output,
        trace_path=result.trace_path,
        artifacts=[{"type": "skill", "path": output["relative_skill_path"]}],
        errors=[] if result.validation_result.valid else [{"message": "Generated Skill failed schema validation."}],
        raw_result=result,
    )


def handle_skill_run_task(
    request: TaskRequest,
    project_root: Path,
    llm_client: LLMClient | None,
) -> TaskResult:
    payload = request.payload()
    input_text = _required_string(payload, "input")
    skill_path = _resolve_skill_path(payload, project_root)
    result = run_skill(skill_path, input_text, project_root=project_root, llm_client=llm_client)
    output_text = result.outputs[0].output if result.outputs else ""
    output = {
        "skill_path": str(result.skill_path),
        "relative_skill_path": _relative_or_absolute(result.skill_path, project_root),
        "run_dir": str(result.run_dir),
        "relative_run_dir": _relative_or_absolute(result.run_dir, project_root),
        "result_path": str(result.result_path),
        "trace_path": str(result.trace_path),
        "run_id": result.run_id,
        "mode": result.mode,
        "output": output_text,
        "outputs": [item.to_dict() for item in result.outputs],
    }
    errors = [
        {"task_id": item.task_id, "message": item.error}
        for item in result.outputs
        if item.error
    ]
    return TaskResult(
        task_type=request.task_type,
        status="failed" if errors else "completed",
        run_id=result.run_id,
        output=output,
        trace_path=result.trace_path,
        artifacts=[
            {"type": "run_result", "path": _relative_or_absolute(result.result_path, project_root)},
            {"type": "run_directory", "path": _relative_or_absolute(result.run_dir, project_root)},
        ],
        errors=errors,
        raw_result=result,
    )


def handle_skill_evolve_task(
    request: TaskRequest,
    project_root: Path,
    llm_client: LLMClient | None,
) -> TaskResult:
    payload = request.payload()
    skill_path = _resolve_skill_path(payload, project_root)
    taskset_path = _resolve_taskset_path(payload, project_root)
    result = evolve_skill(
        skill_path,
        taskset_path,
        project_root=project_root,
        max_iterations=int(payload.get("max_iterations", 1)),
        target_hqs=float(payload.get("target_hqs", 5.0)),
        min_improvement=float(payload.get("min_improvement", 0.01)),
        llm_client=llm_client,
    )
    iterations = [
        {
            "iteration": iteration.iteration,
            "skill_path": str(iteration.skill_path),
            "average_hqs": iteration.hqs_report.average_score,
            "candidate_average_hqs": iteration.candidate_hqs_report.average_score
            if iteration.candidate_hqs_report
            else None,
            "candidate_improvement": iteration.candidate_improvement,
            "decision": iteration.decision,
            "quality_gate": iteration.quality_gate,
            "rewritten_skill_path": str(iteration.rewritten_skill.skill_path) if iteration.rewritten_skill else None,
            "run_dir": str(iteration.run_result.run_dir),
        }
        for iteration in result.iterations
    ]
    output = {
        "taskset": result.taskset.to_dict(),
        "final_skill_path": str(result.final_skill_path),
        "relative_final_skill_path": _relative_or_absolute(result.final_skill_path, project_root),
        "trace_path": str(result.trace_path),
        "run_id": result.run_id,
        "stop_reason": result.stop_reason,
        "iterations": iterations,
    }
    return TaskResult(
        task_type=request.task_type,
        status="completed",
        run_id=result.run_id,
        output=output,
        trace_path=result.trace_path,
        artifacts=[{"type": "skill", "path": output["relative_final_skill_path"]}],
        errors=[],
        raw_result=result,
    )


def _required_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Task requires a non-empty string field: {key}.")
    return value.strip()


def _resolve_skill_path(payload: dict[str, Any], root: Path) -> Path:
    raw_path = payload.get("skill_path")
    if isinstance(raw_path, str) and raw_path.strip():
        return _resolve_under_roots(
            root,
            Path(raw_path.strip()),
            [root / "skills", root / "examples" / "skills"],
            "Skill path must stay under skills/ or examples/skills/.",
        )

    skill_slug = _safe_path_segment(_required_string(payload, "skill_slug"), "Skill slug")
    version = payload.get("version")
    if isinstance(version, str) and version.strip():
        safe_version = _safe_path_segment(version.strip(), "Skill version")
        skill_path = root / "skills" / skill_slug / safe_version / "SKILL.md"
        if skill_path.exists():
            return skill_path
        sample_path = root / "examples" / "skills" / skill_slug / safe_version / "SKILL.md"
        if sample_path.exists():
            return sample_path
        raise ValueError(f"Skill version not found: {skill_slug}/{safe_version}")

    for skill in list_available_skills(root):
        if skill.get("skill_slug") == skill_slug:
            return Path(str(skill["latest_skill_path"]))
    raise ValueError(f"Skill not found: {skill_slug}")


def _resolve_taskset_path(payload: dict[str, Any], root: Path) -> Path:
    return _resolve_under_roots(
        root,
        Path(_required_string(payload, "taskset_path")),
        [root / "tasksets"],
        "Task set path must stay under tasksets/.",
    )


def _resolve_under_roots(root: Path, path: Path, allowed_roots: list[Path], message: str) -> Path:
    candidate = path if path.is_absolute() else root / path
    resolved = candidate.resolve()
    for allowed_root in allowed_roots:
        resolved_allowed = allowed_root.resolve()
        if resolved == resolved_allowed or resolved_allowed in resolved.parents:
            return resolved
    raise ValueError(message)


def _safe_path_segment(value: str, label: str) -> str:
    if value in {"", ".", ".."} or "/" in value or "\\" in value or Path(value).name != value:
        raise ValueError(f"{label} must be a single path segment.")
    return value


def _relative_or_absolute(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)
