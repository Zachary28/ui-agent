"""Retry and blocking-exit classification for Loop operations."""
from __future__ import annotations

import re

from ..contracts.runtime_types import ExitReason


_BLOCKING_REASONS = {
    "login_required": ExitReason.LOGIN_REQUIRED,
    "purchase_required": ExitReason.PURCHASE_REQUIRED,
    "device_unreachable": ExitReason.DEVICE_UNREACHABLE,
    "model_error": ExitReason.MODEL_ERROR,
    "unhandled_popup": ExitReason.UNHANDLED_POPUP,
    "cancelled": ExitReason.CANCELLED,
}


class RetryPolicy:
    @staticmethod
    def _normalize(reason: str | None) -> str:
        return re.sub(r"[^a-z0-9]+", "_", (reason or "").strip().lower()).strip("_")

    def exit_reason(self, reason: str | None) -> ExitReason | None:
        return _BLOCKING_REASONS.get(self._normalize(reason))

    def should_retry(self, *, attempt: int, max_attempts: int, reason: str | None) -> bool:
        return self.exit_reason(reason) is None and attempt < max_attempts


__all__ = ["RetryPolicy"]
