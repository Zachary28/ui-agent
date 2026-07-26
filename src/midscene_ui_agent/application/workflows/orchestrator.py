from __future__ import annotations
import json, uuid, os
from dataclasses import replace
from pathlib import Path
from ...domain.contracts import AutomationRequest, AutomationResult, Artifact, StepResult
from ...infrastructure.execution.runner import CommandRunner
from ...platforms.registry import default_registry
from ...infrastructure.reporting.reports import write_result, build_manifest, discover_native_report, convert_native_report
from ...domain.errors import UiAgentError
from ...infrastructure.evidence.events import Event
from ...infrastructure.persistence.checkpoint import SqliteCheckpoint
from ..loop.controller import LoopWorkflow

def _event(root: Path, run_id: str, kind: str, message: str) -> None:
    Event(kind=kind,message=message,run_id=run_id).write(root/"events.jsonl")

def _load_environment() -> None:
    """Load .env, falling back to the documented example for local setup."""
    path=Path(".env")
    if not path.exists(): path=Path(".env.example")
    if not path.exists(): return
    for raw in path.read_text(encoding="utf-8").splitlines():
        raw=raw.strip()
        if not raw or raw.startswith("#") or "=" not in raw: continue
        key,value=raw.split("=",1); value=value.strip().strip('"').strip("'")
        if key.strip() and key.strip() not in os.environ: os.environ[key.strip()]=value

def run(request: AutomationRequest, *, runner: CommandRunner | None = None, adapters=None, resume: bool = False) -> AutomationResult:
    _load_environment()
    run_id=request.run_id or uuid.uuid4().hex; root=Path(request.report_dir)/run_id; root.mkdir(parents=True,exist_ok=True); (root/"work").mkdir(exist_ok=True)
    checkpoint=SqliteCheckpoint(Path(request.report_dir)/"checkpoints.sqlite")
    checkpoint.put(run_id,{"status":"running","platform":request.platform,"operation":request.operation})
    plan={"platform":request.platform,"operation":request.operation,"goal":request.goal}
    if request.mode == "plan":
        (root/"plan.json").write_text(json.dumps(plan,indent=2),encoding="utf-8")
        _event(root,run_id,"plan",request.goal)
        result=AutomationResult(run_id=run_id,status="planned",artifacts=[Artifact(kind="plan",path="plan.json")]); checkpoint.put(run_id,result.model_dump()); write_result(result,root); build_manifest(result,request,root); checkpoint.close(); return result
    adapter=(adapters or default_registry())[request.platform]; command_runner=runner or CommandRunner(Path(request.report_dir)); steps=[]
    if request.loop is not None:
        loop_result = LoopWorkflow(adapter).run(request.loop, artifact_root=root)
        final = AutomationResult(
            run_id=run_id,
            status="cancelled" if loop_result.status == "cancelled" else "succeeded",
            loop_summary=loop_result.loop_summary,
            exit_reason=loop_result.exit_reason,
        )
        checkpoint.put(run_id, final.model_dump()); write_result(final, root); build_manifest(final, request, root); checkpoint.close()
        return final
    if request.platform == "vitest_e2e" and request.operation in {"create", "update"}:
        if request.operation == "create": adapter.create(request.target.project_dir, request.case_name or request.test_name or "ui-agent-case", request.goal)
        else: adapter.update_case(request.target.project_dir, request.test_name or request.case_name or "", request.goal)
    if request.operation == "run":
        operations=["connect","health_check","run","screenshot"]
    elif request.operation in {"screenshot","assert","launch","tap_locate"}:
        operations=["connect",request.operation]
    else:
        operations=[request.operation]
    for operation in operations:
        try:
            spec=adapter.command(request, operation)
            spec=replace(spec, cwd=str(root/"work"))
            result=command_runner.run(spec,run_id=run_id,event_id=operation)
        except UiAgentError as exc:
            message=f"{exc.code}: {exc}"; steps.append(StepResult(phase=operation,status="failed",message=message)); _event(root,run_id,"error",message); break
        message=result.stderr or result.stdout; step_status="succeeded" if result.returncode==0 else "failed"; steps.append(StepResult(phase=operation,status=step_status,message=message)); _event(root,run_id,operation,message)
        if result.returncode: break
    status="succeeded" if all(s.status=="succeeded" for s in steps) else "failed"
    artifacts=[]; secondary=[]; native=discover_native_report(root/"work")
    if native:
        artifacts.append(Artifact(kind="report",path=str(native.relative_to(root))))
        packages={"browser":"@midscene/web@1","computer":"@midscene/computer@1","android":"@midscene/android@1","ios":"@midscene/ios@1","harmony":"@midscene/harmony@1"}
        if request.platform in packages and request.operation not in {"init","convert","create","update"}:
            try:
                converted=convert_native_report(packages[request.platform],native,root/"report",command_runner,run_id=run_id)
                for path in converted:
                    if path.is_file(): artifacts.append(Artifact(kind="report",path=str(path.relative_to(root))))
            except Exception as exc:
                secondary.append(f"REPORT_GENERATION_FAILED: {exc}")
    error=next((s.message for s in steps if s.status=="failed"),None)
    final=AutomationResult(run_id=run_id,status=status,steps=steps,artifacts=artifacts,error=error,secondary_errors=secondary); checkpoint.put(run_id,final.model_dump()); write_result(final,root); build_manifest(final,request,root); checkpoint.close(); return final
