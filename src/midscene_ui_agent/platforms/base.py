from __future__ import annotations
from abc import ABC, abstractmethod
import hashlib
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Protocol

from ..domain.contracts import AutomationRequest
from ..infrastructure.execution.runner import CommandResult, CommandSpec


class CommandExecutor(Protocol):
    def run(self, spec: CommandSpec, *, run_id: str = "adhoc", event_id: str = "command") -> CommandResult: ...


@dataclass(frozen=True)
class ExecutionContext:
    request: AutomationRequest
    runner: CommandExecutor
    run_id: str
    event_id: str = "operation"
    cwd: str | Path | None = None
    timeout_seconds: float | None = None


@dataclass
class OperationOutcome:
    succeeded: bool
    message: str = ""
    reason: str | None = None
    artifacts: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Observation:
    reachable: bool
    fingerprint: str | None = None
    message: str = ""

class PlatformAdapter(ABC):
    package: str
    @abstractmethod
    def command(self, request: AutomationRequest, operation: str | None = None) -> CommandSpec: ...
    def _operation(self, request, operation): return self.command(request, operation)
    def connect(self, request): return self._operation(request,"connect")
    def health_check(self, request): return self._operation(request,"health_check")
    def screenshot(self, request): return self._operation(request,"screenshot")
    def launch(self, request): return self._operation(request,"launch")
    def execute(self, request): return self._operation(request,"run")
    def verify(self, request): return self._operation(request,"assert")
    def tap_locate(self, request): return self._operation(request,"tap_locate")
    def report(self, request): return self._operation(request,"report")
    def disconnect(self, request): return self._operation(request,"disconnect")
    def close(self, request): return self._operation(request,"close")

    def execute_prompt(self, prompt: str, context: ExecutionContext) -> OperationOutcome:
        request = context.request.model_copy(update={"goal": prompt, "operation": "run"})
        return self._execute_command(request, "run", context, event_id=f"{context.event_id}:run")

    def observe(self, context: ExecutionContext) -> Observation:
        outcome = self._execute_command(
            context.request,
            "screenshot",
            context,
            event_id="observe:screenshot",
        )
        fingerprint = hashlib.sha256(outcome.message.encode("utf-8")).hexdigest() if outcome.message else None
        return Observation(reachable=outcome.succeeded, fingerprint=fingerprint, message=outcome.message)

    def verify_effect(self, operation: str, operation_id: str, context: ExecutionContext) -> bool:
        prompt = f"Verify that {operation} for operation id {operation_id} has taken effect"
        request = context.request.model_copy(update={"goal": prompt, "operation": "assert"})
        return self._execute_command(request, "assert", context, event_id="verify:assert").succeeded

    def release(self, context: ExecutionContext) -> OperationOutcome:
        operation = "close" if context.request.platform == "browser" else "disconnect"
        return self._execute_command(context.request, operation, context, event_id=f"release:{operation}")

    def _execute_command(
        self,
        request: AutomationRequest,
        operation: str,
        context: ExecutionContext,
        *,
        event_id: str,
    ) -> OperationOutcome:
        spec = self.command(request, operation)
        updates: dict[str, Any] = {}
        if context.cwd is not None:
            updates["cwd"] = str(context.cwd)
        if context.timeout_seconds is not None:
            updates["timeout_seconds"] = context.timeout_seconds
        if updates:
            spec = replace(spec, **updates)
        result = context.runner.run(spec, run_id=context.run_id, event_id=event_id)
        message = result.stderr if result.returncode else result.stdout or result.stderr
        return OperationOutcome(
            succeeded=result.returncode == 0,
            message=message,
            metadata={"returncode": result.returncode},
        )


__all__ = [
    "CommandExecutor", "ExecutionContext", "OperationOutcome", "Observation",
    "PlatformAdapter",
]
