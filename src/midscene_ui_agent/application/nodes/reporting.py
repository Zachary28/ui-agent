"""Graph-facing final result and report generation."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ...domain.contracts import Artifact, AutomationRequest, AutomationResult, StepResult
from ...domain.runtime.graph import AutomationGraphState
from ...infrastructure.execution.runner import CommandRunner
from ...infrastructure.reporting.reports import (
    build_manifest,
    convert_native_report,
    discover_native_report,
    write_result,
)


_REPORT_PACKAGES = {
    "browser": "@midscene/web@1",
    "computer": "@midscene/computer@1",
    "android": "@midscene/android@1",
    "ios": "@midscene/ios@1",
    "harmony": "@midscene/harmony@1",
}


def finalize_graph_reports(
    state: AutomationGraphState,
    *,
    request: AutomationRequest,
    root: Path,
    runner: CommandRunner,
    fingerprints: dict[str, str],
) -> dict[str, Any]:
    secondary = list(state.get("secondary_errors", []))
    artifacts = [Artifact.model_validate(item) for item in state.get("artifacts", [])]
    steps = [StepResult.model_validate(item) for item in state.get("steps", [])]

    if state.get("route") != "loop":
        native = discover_native_report(root / "work")
        if native:
            artifacts.append(Artifact(kind="report", path=str(native.relative_to(root))))
            package = _REPORT_PACKAGES.get(request.platform)
            if package and request.operation not in {"init", "convert", "create", "update"}:
                try:
                    converted = convert_native_report(
                        package,
                        native,
                        root / "report",
                        runner,
                        run_id=state["run_id"],
                    )
                    artifacts.extend(
                        Artifact(kind="report", path=str(path.relative_to(root)))
                        for path in converted
                        if path.is_file()
                    )
                except Exception as exc:
                    secondary.append(f"REPORT_GENERATION_FAILED: {exc}")

    error = state.get("error") or next((step.message for step in steps if step.status == "failed"), None)
    result = AutomationResult(
        run_id=state["run_id"],
        status=state.get("status", "failed"),
        steps=steps if state.get("route") != "loop" else [],
        artifacts=artifacts,
        error=error,
        secondary_errors=secondary,
        loop_summary=state.get("loop_summary") if state.get("route") == "loop" else None,
        exit_reason=state.get("exit_reason"),
    )
    result_path = write_result(result, root)
    manifest_path = build_manifest(
        result,
        request,
        root,
        thread_id=state.get("thread_id", state["run_id"]),
        fingerprints=fingerprints,
        graph_phase=state.get("phase", "finalize_run"),
    )
    return {
        "result_payload": result.model_dump(mode="json"),
        "result_path": str(result_path),
        "manifest_path": str(manifest_path),
        "artifacts": [artifact.model_dump(mode="json") for artifact in artifacts],
        "secondary_errors": secondary,
    }


__all__ = ["finalize_graph_reports"]
