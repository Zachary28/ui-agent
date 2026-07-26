from __future__ import annotations

from dataclasses import dataclass
from ..runtime.loop import RuntimeState


@dataclass(frozen=True)
class ExitDecision:
    should_exit: bool
    reason: str | None = None


class ExitPolicy:
    def evaluate(self, state: RuntimeState, *, max_runtime_seconds: float, max_switches: int | None = None, max_scrolls: int | None = None, target_count: int | None = None, max_consecutive_failures: int = 3) -> ExitDecision:
        if getattr(state, "cancelled", False):
            return ExitDecision(True, "CANCELLED")
        if state.elapsed_seconds >= max_runtime_seconds:
            return ExitDecision(True, "MAX_RUNTIME")
        if max_switches is not None and state.switch_count >= max_switches:
            return ExitDecision(True, "MAX_SWITCHES")
        if max_scrolls is not None and state.scroll_count >= max_scrolls:
            return ExitDecision(True, "MAX_SCROLLS")
        if target_count is not None and (state.switch_count + state.scroll_count) >= target_count:
            return ExitDecision(True, "TARGET_COUNT")
        if state.consecutive_failures >= max_consecutive_failures:
            return ExitDecision(True, "MAX_FAILURES")
        if state.no_progress_ticks >= state.max_no_progress_ticks:
            return ExitDecision(True, "NO_PROGRESS")
        return ExitDecision(False)


__all__ = ["ExitDecision", "ExitPolicy"]
