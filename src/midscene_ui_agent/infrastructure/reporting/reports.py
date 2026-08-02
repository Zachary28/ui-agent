from __future__ import annotations
import json
from pathlib import Path
from ...domain.contracts import AutomationResult, Artifact
from ..execution.runner import CommandRunner, CommandSpec
def write_result(result: AutomationResult, root: str | Path) -> Path:
    root=Path(root); root.mkdir(parents=True,exist_ok=True); path=root/"result.json"; path.write_text(result.model_dump_json(indent=2),encoding="utf-8"); return path
def build_manifest(result: AutomationResult, request, root: str | Path, *, thread_id=None, fingerprints=None, graph_phase=None) -> Path:
    root=Path(root); manifest=root/"manifest.json"
    payload={"run_id":result.run_id,"platform":request.platform,"status":result.status,"artifacts":[a.model_dump() for a in result.artifacts]}
    if result.loop_summary is not None:
        payload["loop_summary"] = result.loop_summary
    if result.exit_reason is not None:
        payload["exit_reason"] = result.exit_reason
    if thread_id is not None:
        payload["thread_id"] = thread_id
    if fingerprints is not None:
        payload["fingerprints"] = fingerprints
    if graph_phase is not None:
        payload["graph_phase"] = graph_phase
    manifest.write_text(json.dumps(payload,indent=2),encoding="utf-8"); return manifest

def discover_native_report(work: str | Path) -> Path | None:
    report_root=Path(work)/"midscene_run"/"report"
    candidates=list(report_root.rglob("*.html")) if report_root.exists() else []
    return max(candidates, key=lambda p:p.stat().st_mtime) if candidates else None

def convert_native_report(package: str, html_path: str | Path, output_dir: str | Path, runner: CommandRunner, *, run_id="report") -> list[Path]:
    output_dir=Path(output_dir); output_dir.mkdir(parents=True,exist_ok=True); html_path=str(html_path)
    for action, suffix in (("to-markdown","markdown"),("split","data")):
        result=runner.run(CommandSpec(["npx","-y",package,"report-tool","--action",action,"--htmlPath",html_path,"--outputDir",str(output_dir/suffix)], session_id=f"report:{html_path}"),run_id=run_id,event_id=f"report-{suffix}")
        if result.returncode: raise RuntimeError(result.stderr or f"report {action} failed")
    return list(output_dir.rglob("*"))
