"""Graph node boundary for platform execution."""
from __future__ import annotations

from ...platforms.base import ExecutionContext, OperationOutcome, PlatformAdapter


def execute_prompt(adapter: PlatformAdapter, prompt: str, context: ExecutionContext) -> OperationOutcome:
    return adapter.execute_prompt(prompt, context)


__all__ = ["execute_prompt"]
