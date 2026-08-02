from __future__ import annotations
import json, uuid
from functools import partial
from pathlib import Path
from ...domain.contracts import AutomationRequest, AutomationResult, Artifact, StepResult
from ...infrastructure.execution.runner import CommandRunner
from ...platforms.registry import default_registry
from ...infrastructure.reporting.reports import write_result, build_manifest, discover_native_report, convert_native_report
from ...infrastructure.evidence.events import Event
from ...infrastructure.persistence.checkpoint import SqliteCheckpoint
from ..loop.controller import LoopWorkflow
from ..graphs.automation import build_automation_graph
from ..graphs.single_operation import build_single_operation_graph
from ..nodes.execution import execute_operation_step
from ...infrastructure.persistence.langgraph import sqlite_checkpointer

def _event(root: Path, run_id: str, kind: str, message: str) -> None:
    Event(kind=kind,message=message,run_id=run_id).write(root/"events.jsonl")

def run(request: AutomationRequest, *, runner: CommandRunner | None = None, adapters=None, resume: bool = False) -> AutomationResult:
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
    execute_step=partial(
        execute_operation_step,
        adapter=adapter,
        request=request,
        runner=command_runner,
        run_id=run_id,
        work_dir=root/"work",
        write_event=partial(_event,root,run_id),
    )
    single_graph=build_single_operation_graph(executor=execute_step)
    with sqlite_checkpointer(Path(request.report_dir)/"langgraph.sqlite") as graph_checkpointer:
        graph=build_automation_graph(execution_graph=single_graph,checkpointer=graph_checkpointer)
        graph_state=graph.invoke(
            {"run_id":run_id,"thread_id":run_id,"request":request.model_dump(mode="json"),"mode":request.mode,"route":"single","resume":resume},
            config={"configurable":{"thread_id":run_id}},
        )
    steps=[StepResult.model_validate(step) for step in graph_state.get("steps",[])]
    status=graph_state.get("status","failed")
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
