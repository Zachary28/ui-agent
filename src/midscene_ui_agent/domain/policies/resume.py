"""Fingerprint validation and operation idempotency decisions for graph resume."""

from __future__ import annotations

from typing import Literal

from ..contracts import RunFingerprints


IDEMPOTENT_OPERATIONS = frozenset(
    {"connect", "health_check", "screenshot", "assert", "check_playback", "report_snapshot"}
)


class ResumeInvalid(ValueError):
    pass


def validate_resume(expected: RunFingerprints, actual: RunFingerprints) -> None:
    if expected != actual:
        raise ResumeInvalid("runtime fingerprint mismatch")


def resume_action(operation: str, effect_verified: bool) -> Literal["retry", "complete"]:
    if operation in IDEMPOTENT_OPERATIONS:
        return "retry"
    return "complete" if effect_verified else "retry"


__all__ = ["IDEMPOTENT_OPERATIONS", "ResumeInvalid", "validate_resume", "resume_action"]
