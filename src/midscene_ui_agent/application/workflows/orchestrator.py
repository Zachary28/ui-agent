from __future__ import annotations
import json, uuid
import os
from functools import partial
from pathlib import Path
from ...domain.contracts import AutomationRequest, AutomationResult, Artifact, ExitReason, RunFingerprints
from ...domain.policies.resume import ResumeInvalid, validate_resume
from ...infrastructure.execution.runner import CommandRunner
from ...platforms.registry import default_registry
from ...infrastructure.reporting.reports import write_result, build_manifest
from ...infrastructure.evidence.events import Event
from ...infrastructure.persistence.checkpoint import SqliteCheckpoint
from ..loop.controller import LoopWorkflow
from ..graphs.automation import build_automation_graph
from ..graphs.single_operation import build_single_operation_graph
from ..nodes.execution import execute_operation_step
from ...infrastructure.persistence.langgraph import sqlite_checkpointer
from ...infrastructure.config.resolver import ConfigResolver
from ...infrastructure.config.resources import default_skill_lock_path
from ..services.skills import SkillCatalog
from ..nodes.lifecycle import finalize_run
from ...platforms.base import ExecutionContext
from ..nodes.reporting import finalize_graph_reports


def _request_fingerprints(request: AutomationRequest) -> RunFingerprints:
    payload = request.model_dump(mode="json")
    lock = default_skill_lock_path()
    return RunFingerprints(
        config_hash=ConfigResolver.canonical_hash(payload),
        profile_hash=ConfigResolver.canonical_hash(
            {
                "platform": request.platform,
                "app_uri": request.target.app_uri,
                "url": request.target.url,
            }
        ),
        loop_plan_hash=ConfigResolver.canonical_hash(payload.get("loop") or {}),
        skill_lock_hash=ConfigResolver.canonical_hash(lock.read_text(encoding="utf-8")),
        target_fingerprint=ConfigResolver.canonical_hash(request.target.model_dump(mode="json")),
    )

def _event(root: Path, run_id: str, kind: str, message: str) -> None:
    Event(kind=kind,message=message,run_id=run_id).write(root/"events.jsonl")

def run(
    request: AutomationRequest,
    *,
    runner: CommandRunner | None = None,
    adapters=None,
    resume: bool = False,
    fingerprints: RunFingerprints | None = None,
    skills_root: str | Path | None = None,
    skills_lock: str | Path | None = None,
) -> AutomationResult:
    run_id=request.run_id or uuid.uuid4().hex; root=Path(request.report_dir)/run_id; root.mkdir(parents=True,exist_ok=True); (root/"work").mkdir(exist_ok=True)
    checkpoint=SqliteCheckpoint(Path(request.report_dir)/"checkpoints.sqlite")
    checkpoint.put(run_id,{"status":"running","platform":request.platform,"operation":request.operation})
    plan={"platform":request.platform,"operation":request.operation,"goal":request.goal}
    if request.mode == "plan":
        (root/"plan.json").write_text(json.dumps(plan,indent=2),encoding="utf-8")
        _event(root,run_id,"plan",request.goal)
        result=AutomationResult(run_id=run_id,status="planned",artifacts=[Artifact(kind="plan",path="plan.json")]); checkpoint.put(run_id,result.model_dump()); write_result(result,root); build_manifest(result,request,root); checkpoint.close(); return result
    effective_fingerprints = fingerprints or _request_fingerprints(request)
    resolved_skills_root = Path(skills_root) if skills_root is not None else Path(os.environ["MIDSCENE_SKILLS_ROOT"]) if os.environ.get("MIDSCENE_SKILLS_ROOT") else None
    resolved_skills_lock = Path(skills_lock) if skills_lock is not None else default_skill_lock_path() if resolved_skills_root is not None else None

    def verify_skills(state):
        del state
        if resolved_skills_lock is not None and resolved_skills_root is None:
            return {"phase": "verify_skill_lock", "status": "failed", "error": "skills root is required when a skill lock is supplied"}
        if resolved_skills_root is None:
            return {"phase": "verify_skill_lock", "status": "running"}
        try:
            SkillCatalog(resolved_skills_root).verify_platform_lock(resolved_skills_lock, request.platform)
        except Exception as exc:
            return {"phase": "verify_skill_lock", "status": "failed", "error": str(exc)}
        return {"phase": "verify_skill_lock", "status": "running"}

    def finalize_graph(state):
        updates = dict(finalize_run(state))
        secondary = list(state.get("secondary_errors", []))
        exit_conditions = request.loop.exit_conditions if request.loop is not None else None
        should_release = (
            bool(exit_conditions.close_browser_on_exit) if request.platform == "browser" and exit_conditions
            else False if request.platform == "browser"
            else bool(exit_conditions.disconnect_on_exit) if exit_conditions
            else True
        )
        if state.get("phase") == "verify_skill_lock" and state.get("error"):
            should_release = False
        if not should_release or not hasattr(adapter, "release"):
            updates.update(release_attempted=False, resources_released=False, secondary_errors=secondary)
        else:
            updates["release_attempted"] = True
            try:
                outcome = adapter.release(
                    ExecutionContext(
                        request=request,
                        runner=command_runner,
                        run_id=run_id,
                        event_id="finalize:release",
                        cwd=root / "work",
                        timeout_seconds=request.timeout_seconds,
                    )
                )
                updates["resources_released"] = bool(outcome.succeeded)
                if not outcome.succeeded:
                    secondary.append(f"RESOURCE_RELEASE_FAILED: {outcome.message}")
            except Exception as exc:
                updates["resources_released"] = False
                secondary.append(f"RESOURCE_RELEASE_FAILED: {exc}")
            updates["secondary_errors"] = secondary
        combined = {**state, **updates}
        updates.update(
            finalize_graph_reports(
                combined,
                request=request,
                root=root,
                runner=command_runner,
                fingerprints=effective_fingerprints.model_dump(mode="json"),
            )
        )
        return updates
    adapter=(adapters or default_registry())[request.platform]; command_runner=runner or CommandRunner(Path(request.report_dir)); steps=[]
    loop_workflow = None
    if request.loop is not None:
        loop_workflow = LoopWorkflow(
            adapter,
            request=request,
            runner=command_runner,
            run_id=run_id,
        )
        execution_graph = loop_workflow.build_graph(artifact_root=root, inherit_checkpointer=True)
        route = "loop"
    else:
        execute_step=partial(
            execute_operation_step,
            adapter=adapter,
            request=request,
            runner=command_runner,
            run_id=run_id,
            work_dir=root/"work",
            write_event=partial(_event,root,run_id),
        )
        execution_graph=build_single_operation_graph(executor=execute_step, inherit_checkpointer=True)
        route = "single"
    with sqlite_checkpointer(Path(request.report_dir)/"langgraph.sqlite") as graph_checkpointer:
        graph=build_automation_graph(
            execution_graph=execution_graph,
            services={"verify": verify_skills, "finalize": finalize_graph},
            checkpointer=graph_checkpointer,
        )
        graph_input = {
            "run_id":run_id,
            "thread_id":run_id,
            "request":request.model_dump(mode="json"),
            "mode":request.mode,
            "route":route,
            "resume":resume,
            "fingerprints": effective_fingerprints.model_dump(mode="json"),
        }
        if request.loop is not None:
            graph_input["plan"] = request.loop.model_dump(mode="json")
            graph_input["cancelled"] = loop_workflow.cancel_event.is_set()
        graph_config={"configurable":{"thread_id":run_id}, "recursion_limit": 100000}
        if resume:
            snapshot = graph.get_state(graph_config)
            try:
                if not snapshot.values or not snapshot.values.get("fingerprints"):
                    raise ResumeInvalid("checkpoint not found or missing fingerprints")
                validate_resume(
                    RunFingerprints.model_validate(snapshot.values["fingerprints"]),
                    effective_fingerprints,
                )
            except ResumeInvalid as exc:
                final = AutomationResult(
                    run_id=run_id,
                    status="resume_invalid",
                    exit_reason=ExitReason.RESUME_INVALID,
                    error=str(exc),
                )
                checkpoint.put(run_id, final.model_dump())
                write_result(final, root)
                build_manifest(
                    final,
                    request,
                    root,
                    thread_id=run_id,
                    fingerprints=effective_fingerprints.model_dump(mode="json"),
                    graph_phase="finalize_run",
                )
                checkpoint.close()
                return final
            graph_state=graph.invoke(None, config=graph_config)
        else:
            graph_checkpointer.saver.delete_thread(run_id)
            graph_state=graph.invoke(graph_input, config=graph_config)
    final = AutomationResult.model_validate(graph_state["result_payload"])
    checkpoint.put(run_id, final.model_dump())
    checkpoint.close()
    return final
