"""Runtime configuration and normalized exit contracts."""
from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

class ExitReason(StrEnum):
    COMPLETED = "completed"
    MAX_RUNTIME = "max_runtime"
    MAX_SWITCHES = "max_switches"
    MAX_SCROLLS = "max_scrolls"
    TARGET_COUNT = "target_count"
    MAX_FAILURES = "max_failures"
    NO_PROGRESS = "no_progress"
    DEVICE_UNREACHABLE = "device_unreachable"
    MODEL_ERROR = "model_error"
    LOGIN_REQUIRED = "login_required"
    PURCHASE_REQUIRED = "purchase_required"
    UNHANDLED_POPUP = "unhandled_popup"
    CANCELLED = "cancelled"
    RESUME_INVALID = "resume_invalid"


class RunFingerprints(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    config_hash: str
    profile_hash: str
    loop_plan_hash: str
    skill_lock_hash: str
    target_fingerprint: str


# Imported after the independent contracts above so this module and
# ``loop_contracts`` remain safe to import directly.
from .contracts import AutomationRequest  # noqa: E402


class ResolvedRunConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request: AutomationRequest
    fingerprints: RunFingerprints


__all__ = ["ExitReason", "RunFingerprints", "ResolvedRunConfig"]
