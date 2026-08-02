"""JSON-serializable state contracts for checkpointed runtime graphs."""
from __future__ import annotations

from typing import TypeAlias, TypedDict

from ..contracts.runtime_types import ExitReason


JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]


class AutomationGraphState(TypedDict, total=False):
    run_id: str
    thread_id: str
    request: JsonObject
    config: JsonObject
    mode: str
    route: str
    phase: str
    operation_steps: list[JsonObject]
    step_index: int
    steps: list[JsonObject]
    artifacts: list[JsonObject]
    fingerprints: dict[str, str]
    error: str | None
    secondary_errors: list[str]
    status: str
    exit_reason: ExitReason | None
    release_attempted: bool
    resources_released: bool
    resource_release_state: JsonObject
    artifact_root: str
    report_path: str
    result_path: str
    manifest_path: str
    events_path: str


class LoopGraphState(TypedDict, total=False):
    tick: int
    current_tick: int
    started_at: float
    tick_started_at: float
    last_checkpoint_at: float
    elapsed_seconds: float
    due_operations: list[str]
    selected_operation: str | None
    operation_id: str | None
    operation_attempts: dict[str, int]
    operation_successes: dict[str, int]
    operation_failures: dict[str, int]
    consecutive_failures: int
    no_progress_ticks: int
    last_progress_fingerprint: str | None
    switch_count: int
    scroll_count: int
    target_count: int
    playback_elapsed_seconds: float
    popup_detected: bool
    ad_detected: bool
    stalled: bool
    login_required: bool
    purchase_required: bool
    device_unreachable: bool
    model_error: bool
    evidence_refs: list[str]
    exit_reason: ExitReason | None
    cancelled: bool


__all__ = [
    "JsonScalar",
    "JsonValue",
    "JsonObject",
    "AutomationGraphState",
    "LoopGraphState",
]
