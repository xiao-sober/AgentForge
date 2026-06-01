from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentforge.common.file_store import write_json, write_text
from agentforge.common.llm_client import LLMClient
from agentforge.common.trace import write_trace
from agentforge.skill_evolver.hqs_evaluator import HQSReport, evaluate_taskset, write_hqs_report
from agentforge.skill_evolver.reflector import build_reflection_report
from agentforge.skill_evolver.rewriter import RewriteCandidate, RewrittenSkill, propose_skill_rewrite, write_rewrite_candidate
from agentforge.skill_evolver.skill_runner import SkillRunResult, run_skill_markdown_on_taskset, run_skill_on_taskset
from agentforge.skill_evolver.task_loader import TaskSet, load_taskset
from agentforge.skill_evolver.version_manager import parse_skill_version_path


@dataclass(frozen=True)
class EvolutionIteration:
    iteration: int
    skill_path: Path
    run_result: SkillRunResult
    hqs_report: HQSReport
    hqs_report_path: Path
    reflection_path: Path
    candidate: RewriteCandidate | None
    candidate_path: Path | None
    candidate_run_result: SkillRunResult | None
    candidate_hqs_report: HQSReport | None
    candidate_hqs_report_path: Path | None
    candidate_improvement: float | None
    decision: str
    rewritten_skill: RewrittenSkill | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "iteration": self.iteration,
            "skill_path": str(self.skill_path),
            "run_result": self.run_result.to_dict(),
            "hqs_report": self.hqs_report.to_dict(),
            "hqs_report_path": str(self.hqs_report_path),
            "reflection_path": str(self.reflection_path),
            "candidate": self.candidate.to_dict() if self.candidate else None,
            "candidate_path": str(self.candidate_path) if self.candidate_path else None,
            "candidate_run_result": self.candidate_run_result.to_dict() if self.candidate_run_result else None,
            "candidate_hqs_report": self.candidate_hqs_report.to_dict() if self.candidate_hqs_report else None,
            "candidate_hqs_report_path": str(self.candidate_hqs_report_path) if self.candidate_hqs_report_path else None,
            "candidate_improvement": self.candidate_improvement,
            "decision": self.decision,
            "rewritten_skill": self.rewritten_skill.to_dict() if self.rewritten_skill else None,
        }


@dataclass(frozen=True)
class EvolutionResult:
    taskset: TaskSet
    iterations: list[EvolutionIteration]
    final_skill_path: Path
    trace_path: Path
    stop_reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "taskset": self.taskset.to_dict(),
            "iterations": [iteration.to_dict() for iteration in self.iterations],
            "final_skill_path": str(self.final_skill_path),
            "trace_path": str(self.trace_path),
            "stop_reason": self.stop_reason,
        }


def evolve_skill(
    skill_path: Path | str,
    taskset_path: Path | str,
    project_root: Path | str = ".",
    max_iterations: int = 3,
    target_hqs: float = 5.0,
    min_improvement: float = 0.01,
    llm_client: LLMClient | None = None,
) -> EvolutionResult:
    if max_iterations < 1:
        raise ValueError("max_iterations must be at least 1.")
    root = Path(project_root).resolve()
    taskset = load_taskset(taskset_path)
    current_skill_path = Path(skill_path).resolve()
    iterations: list[EvolutionIteration] = []
    artifacts: list[dict[str, str]] = []
    steps: list[dict[str, Any]] = [
        {"name": "load_taskset", "status": "completed", "path": str(taskset_path), "task_count": len(taskset.tasks)}
    ]
    stop_reason = "max_iterations"

    for iteration_number in range(1, max_iterations + 1):
        run_result = run_skill_on_taskset(current_skill_path, taskset, project_root=root, llm_client=llm_client)
        hqs_report = evaluate_taskset(taskset, run_result)
        hqs_report_path = write_hqs_report(run_result.run_dir / "hqs_report.json", hqs_report)
        reflection_markdown = build_reflection_report(taskset, hqs_report)
        reflection_path = write_text(run_result.run_dir / "reflection.md", reflection_markdown)

        evaluation_trace_path = write_trace(
            project_root=root,
            trace_type="skill_evaluation",
            input_data={"skill_path": str(current_skill_path), "run_result_path": str(run_result.result_path)},
            output={"hqs_report_path": _relative_or_absolute(hqs_report_path, root), "average_hqs": hqs_report.average_score},
            steps=[{"name": "evaluate_taskset", "status": "completed", "task_count": len(taskset.tasks)}],
            artifacts=[{"type": "hqs_report", "path": _relative_or_absolute(hqs_report_path, root)}],
            errors=[],
        )

        rewritten_skill = None
        steps.append(
            {
                "name": "iteration_evaluate",
                "status": "completed",
                "iteration": iteration_number,
                "average_hqs": hqs_report.average_score,
                "run_dir": str(run_result.run_dir),
            }
        )
        artifacts.extend(
            [
                {"type": "run_result", "path": _relative_or_absolute(run_result.result_path, root)},
                {"type": "hqs_report", "path": _relative_or_absolute(hqs_report_path, root)},
                {"type": "reflection", "path": _relative_or_absolute(reflection_path, root)},
                {"type": "trace", "path": _relative_or_absolute(evaluation_trace_path, root)},
            ]
        )

        if hqs_report.average_score >= target_hqs:
            stop_reason = "target_hqs_reached"
            iterations.append(
                _iteration(
                    iteration_number,
                    current_skill_path,
                    run_result,
                    hqs_report,
                    hqs_report_path,
                    reflection_path,
                    decision="target_hqs_reached",
                )
            )
            break

        candidate = propose_skill_rewrite(
            current_skill_path,
            reflection_markdown,
            hqs_report,
            llm_client=llm_client,
        )
        candidate_path = write_text(run_result.run_dir / "candidate" / "SKILL.md", candidate.markdown)
        candidate_run_result = _evaluate_candidate(
            current_skill_path=current_skill_path,
            candidate=candidate,
            candidate_path=candidate_path,
            taskset=taskset,
            project_root=root,
            llm_client=llm_client,
        )
        candidate_hqs_report = evaluate_taskset(taskset, candidate_run_result)
        candidate_hqs_report_path = write_hqs_report(candidate_run_result.run_dir / "hqs_report.json", candidate_hqs_report)
        candidate_improvement = round(candidate_hqs_report.average_score - hqs_report.average_score, 2)
        write_json(
            run_result.run_dir / "candidate" / "decision.json",
            {
                "candidate": candidate.to_dict(),
                "current_hqs": hqs_report.average_score,
                "candidate_hqs": candidate_hqs_report.average_score,
                "candidate_improvement": candidate_improvement,
                "min_improvement": min_improvement,
            },
        )

        artifacts.extend(
            [
                {"type": "candidate_skill", "path": _relative_or_absolute(candidate_path, root)},
                {"type": "candidate_run_result", "path": _relative_or_absolute(candidate_run_result.result_path, root)},
                {"type": "candidate_hqs_report", "path": _relative_or_absolute(candidate_hqs_report_path, root)},
            ]
        )

        if candidate_hqs_report.average_score < hqs_report.average_score:
            stop_reason = "candidate_rejected_regression"
            decision = "rejected_regression"
            steps.append(
                {
                    "name": "candidate_rejected",
                    "status": "completed",
                    "iteration": iteration_number,
                    "current_hqs": hqs_report.average_score,
                    "candidate_hqs": candidate_hqs_report.average_score,
                    "reason": stop_reason,
                }
            )
            iterations.append(
                _iteration(
                    iteration_number,
                    current_skill_path,
                    run_result,
                    hqs_report,
                    hqs_report_path,
                    reflection_path,
                    candidate=candidate,
                    candidate_path=candidate_path,
                    candidate_run_result=candidate_run_result,
                    candidate_hqs_report=candidate_hqs_report,
                    candidate_hqs_report_path=candidate_hqs_report_path,
                    candidate_improvement=candidate_improvement,
                    decision=decision,
                )
            )
            break

        if candidate_improvement < min_improvement:
            stop_reason = "minimum_improvement_not_met"
            decision = "rejected_minimum_improvement_not_met"
            steps.append(
                {
                    "name": "candidate_rejected",
                    "status": "completed",
                    "iteration": iteration_number,
                    "current_hqs": hqs_report.average_score,
                    "candidate_hqs": candidate_hqs_report.average_score,
                    "candidate_improvement": candidate_improvement,
                    "min_improvement": min_improvement,
                    "reason": stop_reason,
                }
            )
            iterations.append(
                _iteration(
                    iteration_number,
                    current_skill_path,
                    run_result,
                    hqs_report,
                    hqs_report_path,
                    reflection_path,
                    candidate=candidate,
                    candidate_path=candidate_path,
                    candidate_run_result=candidate_run_result,
                    candidate_hqs_report=candidate_hqs_report,
                    candidate_hqs_report_path=candidate_hqs_report_path,
                    candidate_improvement=candidate_improvement,
                    decision=decision,
                )
            )
            break

        rewritten_skill = write_rewrite_candidate(
            current_skill_path,
            candidate,
            hqs_report,
            extra_metadata={
                "taskset": taskset.to_dict(),
                "run_result_path": str(run_result.result_path),
                "hqs_report_path": str(hqs_report_path),
                "reflection_path": str(reflection_path),
                "candidate_run_result_path": str(candidate_run_result.result_path),
                "candidate_hqs_report_path": str(candidate_hqs_report_path),
                "candidate_hqs_average": candidate_hqs_report.average_score,
                "candidate_improvement": candidate_improvement,
                "accepted": True,
            },
        )
        steps.append(
            {
                "name": "accept_candidate",
                "status": "completed",
                "iteration": iteration_number,
                "current_hqs": hqs_report.average_score,
                "candidate_hqs": candidate_hqs_report.average_score,
                "candidate_improvement": candidate_improvement,
                "new_skill_path": str(rewritten_skill.skill_path),
            }
        )
        artifacts.extend(
            [
                {"type": "skill", "path": _relative_or_absolute(rewritten_skill.skill_path, root)},
                {"type": "version_metadata", "path": _relative_or_absolute(rewritten_skill.metadata_path, root)},
                {"type": "diff", "path": _relative_or_absolute(rewritten_skill.diff_path, root)},
            ]
        )

        iterations.append(
            EvolutionIteration(
                iteration=iteration_number,
                skill_path=current_skill_path,
                run_result=run_result,
                hqs_report=hqs_report,
                hqs_report_path=hqs_report_path,
                reflection_path=reflection_path,
                candidate=candidate,
                candidate_path=candidate_path,
                candidate_run_result=candidate_run_result,
                candidate_hqs_report=candidate_hqs_report,
                candidate_hqs_report_path=candidate_hqs_report_path,
                candidate_improvement=candidate_improvement,
                decision="accepted",
                rewritten_skill=rewritten_skill,
            )
        )
        current_skill_path = rewritten_skill.skill_path
    else:
        stop_reason = "max_iterations"

    trace_output = {
        "final_skill_path": _relative_or_absolute(current_skill_path, root),
        "stop_reason": stop_reason,
        "iterations": [iteration.to_dict() for iteration in iterations],
    }
    trace_path = write_trace(
        project_root=root,
        trace_type="skill_evolution",
        input_data={
            "initial_skill_path": str(skill_path),
            "taskset_path": str(taskset_path),
            "max_iterations": max_iterations,
            "target_hqs": target_hqs,
            "min_improvement": min_improvement,
            "candidate_gate": {
                "reject_regression": True,
                "min_improvement": min_improvement,
            },
        },
        output=trace_output,
        steps=steps,
        artifacts=artifacts,
        errors=[],
    )

    return EvolutionResult(
        taskset=taskset,
        iterations=iterations,
        final_skill_path=current_skill_path,
        trace_path=trace_path,
        stop_reason=stop_reason,
    )


def _evaluate_candidate(
    current_skill_path: Path,
    candidate: RewriteCandidate,
    candidate_path: Path,
    taskset: TaskSet,
    project_root: Path,
    llm_client: LLMClient | None,
) -> SkillRunResult:
    info = parse_skill_version_path(current_skill_path)
    return run_skill_markdown_on_taskset(
        skill_markdown=candidate.markdown,
        skill_path=candidate_path,
        skill_slug=info.skill_slug,
        version=f"candidate_{candidate.target_version}",
        taskset=taskset,
        project_root=project_root,
        llm_client=llm_client,
    )


def _iteration(
    iteration_number: int,
    skill_path: Path,
    run_result: SkillRunResult,
    hqs_report: HQSReport,
    hqs_report_path: Path,
    reflection_path: Path,
    candidate: RewriteCandidate | None = None,
    candidate_path: Path | None = None,
    candidate_run_result: SkillRunResult | None = None,
    candidate_hqs_report: HQSReport | None = None,
    candidate_hqs_report_path: Path | None = None,
    candidate_improvement: float | None = None,
    decision: str = "evaluated",
    rewritten_skill: RewrittenSkill | None = None,
) -> EvolutionIteration:
    return EvolutionIteration(
        iteration=iteration_number,
        skill_path=skill_path,
        run_result=run_result,
        hqs_report=hqs_report,
        hqs_report_path=hqs_report_path,
        reflection_path=reflection_path,
        candidate=candidate,
        candidate_path=candidate_path,
        candidate_run_result=candidate_run_result,
        candidate_hqs_report=candidate_hqs_report,
        candidate_hqs_report_path=candidate_hqs_report_path,
        candidate_improvement=candidate_improvement,
        decision=decision,
        rewritten_skill=rewritten_skill,
    )


def _relative_or_absolute(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)
