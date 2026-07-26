from __future__ import annotations
from typing import Any, TypedDict

class RunState(TypedDict, total=False):
    request: dict[str, Any]
    # Present for loop runs; one-shot requests continue to use the existing
    # state shape unchanged.
    loop: dict[str, Any]
    loop_metadata: dict[str, Any]
    current_operation: str | None
    run_id: str
    phases: list[str]
    current_index: int
    steps: list[dict[str, Any]]
    attempts: dict[str, int]
    status: str
    error: str | None
    secondary_errors: list[str]
    artifacts: list[dict[str, Any]]
