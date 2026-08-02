from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RuntimeState:
    max_no_progress_ticks: int = 5
    started_at: float = 0.0
    current_tick: int = 0
    elapsed_seconds: float = 0.0
    popup_detected: bool = False
    ad_detected: bool = False
    stalled: bool = False
    no_progress_ticks: int = 0
    consecutive_failures: int = 0
    operation_attempts: dict[str, int] = field(default_factory=dict)
    operation_failures: dict[str, int] = field(default_factory=dict)
    last_progress_fingerprint: str | None = None
    switch_count: int = 0
    scroll_count: int = 0
    playback_elapsed_seconds: float = 0.0
    selected_operation_id: str | None = None
    cancelled: bool = False

    def record_tick(self, *, progress_fingerprint: str | None) -> None:
        self.current_tick += 1
        if progress_fingerprint and (
            self.last_progress_fingerprint is None or progress_fingerprint == self.last_progress_fingerprint
        ):
            self.no_progress_ticks += 1
        elif progress_fingerprint:
            self.no_progress_ticks = 0
            self.last_progress_fingerprint = progress_fingerprint
        if self.no_progress_ticks >= self.max_no_progress_ticks:
            self.stalled = True

    def record_attempt(self, operation: str, *, success: bool) -> None:
        self.operation_attempts[operation] = self.operation_attempts.get(operation, 0) + 1
        if success:
            self.consecutive_failures = 0
        else:
            self.consecutive_failures += 1
            self.operation_failures[operation] = self.operation_failures.get(operation, 0) + 1

    def snapshot(self) -> dict[str, Any]:
        return {
            "current_tick": self.current_tick,
            "elapsed_seconds": self.elapsed_seconds,
            "operation_attempts": dict(self.operation_attempts),
            "operation_failures": dict(self.operation_failures),
            "switch_count": self.switch_count,
            "scroll_count": self.scroll_count,
            "playback_elapsed_seconds": self.playback_elapsed_seconds,
            "no_progress_ticks": self.no_progress_ticks,
        }


__all__ = ["RuntimeState"]
