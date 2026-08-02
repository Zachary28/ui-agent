"""JSON-serializable state contracts for checkpointed runtime graphs."""

from __future__ import annotations

from typing import TypeAlias, TypedDict

from ..contracts.runtime_types import ExitReason


JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]


class LoopStateFields(TypedDict, total=False):
    plan: JsonObject
    tick: int
    current_tick: int
    started_at: float
    tick_started_at: float
    last_checkpoint_at: float
    elapsed_seconds: float
    due_operations: list[str]
    enabled_operations: list[str]
    next_due: dict[str, float]
    fired_triggers: list[str]
    selected_operation: str | None
    selected_attempt: int
    retry_pending: bool
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
    current_operation_id: str | None
    observation: JsonObject
    last_outcome: JsonObject
    last_operation: str | None
    operation_messages: dict[str, str]
    loop_summary: JsonObject
    status: str
    exit_reason: ExitReason | None
    cancelled: bool


class LoopGraphState(LoopStateFields, total=False):
    run_id: str


class AutomationGraphState(LoopStateFields, total=False):
    run_id: str
    thread_id: str
    request: JsonObject
    config: JsonObject
    mode: str
    route: str
    resume: bool
    phase: str
    operation_steps: list[str]
    step_index: int
    steps: list[JsonObject]
    artifacts: list[JsonObject]
    fingerprints: dict[str, str]
    error: str | None
    secondary_errors: list[str]
    release_attempted: bool
    resources_released: bool
    resource_release_state: JsonObject
    artifact_root: str
    report_path: str
    result_path: str
    manifest_path: str
    events_path: str
    result_payload: JsonObject


__all__ = [
    "JsonScalar",
    "JsonValue",
    "JsonObject",
    "LoopStateFields",
    "AutomationGraphState",
    "LoopGraphState",
]
