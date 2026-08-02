"""Graph node boundary for platform execution."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any, Literal

from ...domain.contracts import AutomationRequest, StepResult
from ...domain.errors import UiAgentError
from ...domain.runtime.graph import AutomationGraphState, JsonObject
from ...platforms.base import CommandExecutor, ExecutionContext, OperationOutcome, PlatformAdapter

EventWriter = Callable[[str, str], None]


def execute_prompt(adapter: PlatformAdapter, prompt: str, context: ExecutionContext) -> OperationOutcome:
    return adapter.execute_prompt(prompt, context)


def execute_operation_step(
    state: AutomationGraphState,
    operation: str,
    *,
    adapter: PlatformAdapter,
    request: AutomationRequest,
    runner: CommandExecutor,
    run_id: str,
    work_dir: Path,
    write_event: EventWriter,
) -> JsonObject:
    """Execute one deterministic operation for the single-operation graph."""
    del state
    status: Literal["succeeded", "failed"]
    try:
        if request.platform == "vitest_e2e" and operation in {"create", "update"}:
            lifecycle_adapter: Any = adapter
            if operation == "create":
                path = lifecycle_adapter.create(
                    request.target.project_dir,
                    request.case_name or request.test_name or "ui-agent-case",
                    request.goal,
                )
            else:
                path = lifecycle_adapter.update_case(
                    request.target.project_dir,
                    request.test_name or request.case_name or "",
                    request.goal,
                )
            message = str(path)
            status = "succeeded"
        else:
            spec = replace(adapter.command(request, operation), cwd=str(work_dir))
            command_result = runner.run(spec, run_id=run_id, event_id=operation)
            message = command_result.stderr or command_result.stdout
            status = "succeeded" if command_result.returncode == 0 else "failed"
    except UiAgentError as exc:
        message = f"{exc.code}: {exc}"
        status = "failed"
        write_event("error", message)
    else:
        write_event(operation, message)

    return StepResult(phase=operation, status=status, message=message).model_dump(mode="json")


__all__ = ["EventWriter", "execute_operation_step", "execute_prompt"]
