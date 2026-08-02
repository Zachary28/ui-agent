"""Leaf runtime types shared by contracts and checkpoint state."""

from enum import StrEnum


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


__all__ = ["ExitReason"]
