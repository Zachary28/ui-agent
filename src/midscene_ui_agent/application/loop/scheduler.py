from __future__ import annotations

import time
from threading import Event
from typing import Callable


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


__all__ = ["LoopScheduler"]
