from __future__ import annotations

import time
from threading import Event
from typing import Any, Callable

from ...domain.contracts import LoopPlan


class LoopScheduler:
    def __init__(self, *, clock: Callable[[], float] | object | None = None, intervals: dict[str, float] | None = None):
        self.clock = clock or time
        self.intervals = intervals or {}
        self.started_at = 0.0
        self.last_attempt: dict[str, float] = {}
        self.next_due: dict[str, float] = {}
        self.operations: list[str] = []
        self._selected_tick: int | None = None
        self._tick = 0

    def _now(self) -> float:
        return self.clock.monotonic() if hasattr(self.clock, "monotonic") else self.clock()

    def start(self, operations: list[str], *, startup: list[str] | None = None) -> None:
        self.started_at = self._now()
        self.operations = list(dict.fromkeys(operations))
        startup_set = set(startup or ())
        self.next_due = {name: self.started_at if name in startup_set else self.started_at + self.intervals.get(name, 5) for name in self.operations}

    def due_operations(self) -> list[str]:
        now = self._now()
        return [name for name in self.operations if now >= self.next_due.get(name, now)]

    def mark_attempt(self, operation: str, *, success: bool = False) -> None:
        now = self._now()
        self.last_attempt[operation] = now
        self.next_due[operation] = now + self.intervals.get(operation, 5)
        self._tick += 1
        self._selected_tick = self._tick

    def runtime_elapsed(self) -> float:
        return max(0.0, self._now() - self.started_at)

    def wait_until_next_due(self, cancel: Event | None = None, poll_seconds: float = 0.25) -> bool:
        cancel = cancel or Event()
        while not self.due_operations():
            if cancel.wait(poll_seconds):
                return False
        return True


def scheduled_operations(plan: LoopPlan, state: dict[str, Any], *, now: float) -> tuple[list[str], dict[str, Any]]:
    """Return due operations and JSON updates for one deterministic scheduling pass."""
    elapsed = max(0.0, now - float(state.get("started_at", now)))
    fired = set(state.get("fired_triggers", []))
    next_due = dict(state.get("next_due", {}))
    last_operation = state.get("last_operation")
    due: list[str] = []
    for name, config in plan.operations.items():
        if not config.enabled:
            continue
        triggers: list[str] = []
        if config.startup and f"startup:{name}" not in fired:
            triggers.append(f"startup:{name}")
        if config.on_popup and state.get("popup_detected"):
            triggers.append(f"popup:{name}:{state.get('tick', 0)}")
        if config.on_ad and state.get("ad_detected"):
            triggers.append(f"ad:{name}:{state.get('tick', 0)}")
        if config.on_stall and state.get("stalled"):
            triggers.append(f"stall:{name}:{state.get('tick', 0)}")
        if config.at_runtime is not None and elapsed >= config.at_runtime and f"runtime:{name}" not in fired:
            triggers.append(f"runtime:{name}")
        if last_operation in config.after_operation and f"after:{last_operation}:{name}:{state.get('tick', 0)}" not in fired:
            triggers.append(f"after:{last_operation}:{name}:{state.get('tick', 0)}")
        interval_due = now >= float(next_due.get(name, now + (config.interval_seconds or plan.defaults.interval_seconds)))
        if triggers or interval_due:
            due.append(name)
            fired.update(triggers)
    return due, {"elapsed_seconds": elapsed, "fired_triggers": sorted(fired), "next_due": next_due}


__all__ = ["LoopScheduler", "scheduled_operations"]
