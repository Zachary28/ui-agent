from __future__ import annotations

import time
from pathlib import Path
from threading import Event

from ...domain.contracts import LoopPlan
from ...domain.contracts.runtime_types import ExitReason
from ...domain.policies.exit import ExitPolicy
from ...domain.runtime.loop import RuntimeState
from .scheduler import LoopScheduler
from .selector import OperationSelector
from ..services.handlers import AdHandler, EpisodeSwitcher, FeedScroller, GenericOperationHandler, PlaybackController, PopupHandler


class LoopWorkflow:
    def __init__(self, adapter, *, clock=None):
        self.adapter = adapter
        self.clock = clock or time
        self.cancel_event = Event()

    def cancel(self) -> None:
        self.cancel_event.set()

    def run(self, plan: LoopPlan, *, artifact_root: str | Path) -> object:
        root = Path(artifact_root)
        root.mkdir(parents=True, exist_ok=True)
        enabled = [name for name, config in plan.operations.items() if config.enabled]
        if not enabled:
            enabled = ["check_playback"]
        intervals = {name: plan.operations[name].interval_seconds or plan.defaults.interval_seconds for name in enabled if name in plan.operations}
        scheduler = LoopScheduler(clock=self.clock, intervals=intervals)
        # Establish initial UI state before interval-driven repetitions.
        startup = list(enabled)
        scheduler.start(enabled, startup=startup)
        state = RuntimeState(max_no_progress_ticks=plan.exit_conditions.max_no_progress_ticks)
        started = scheduler.started_at
        operations = {}
        exit_reason = None
        while True:
            state.elapsed_seconds = scheduler.runtime_elapsed()
            if self.cancel_event.is_set():
                state.cancelled = True
            decision = ExitPolicy().evaluate(state, max_runtime_seconds=plan.exit_conditions.max_runtime_seconds, max_consecutive_failures=plan.exit_conditions.max_consecutive_failures)
            due = scheduler.due_operations()
            selected = OperationSelector().choose(due, state)
            if selected:
                outcome = self._execute(selected, plan)
                operations.setdefault(selected, {"attempts": 0, "successes": 0})["attempts"] += 1
                if outcome.succeeded:
                    operations[selected]["successes"] += 1
                state.record_attempt(selected, success=outcome.succeeded)
                state.selected_operation_id = None
                scheduler.mark_attempt(selected, success=outcome.succeeded)
                state.record_tick(progress_fingerprint=outcome.message or selected)
            elif decision.should_exit:
                exit_reason = decision.reason
                break
            else:
                if self.cancel_event.wait(0.01):
                    state.cancelled = True
        return type("LoopResult", (), {"status": "cancelled" if exit_reason == ExitReason.CANCELLED else "succeeded", "exit_reason": exit_reason, "loop_summary": {"ticks": state.current_tick, "elapsed_seconds": state.elapsed_seconds, "operations": operations}})()

    def _execute(self, operation: str, plan: LoopPlan):
        if operation == "dismiss_popup":
            return PopupHandler(self.adapter).handle(plan.popup_prompts[0] if plan.popup_prompts else "Close the ordinary popup")
        if operation == "skip_ad":
            return AdHandler(self.adapter).skip(plan.ad_prompts[0] if plan.ad_prompts else None or "Skip or close the advertisement")
        if operation == "play_video":
            return PlaybackController(self.adapter).play()
        if operation == "check_playback":
            return PlaybackController(self.adapter).check()
        if operation == "recover_playback":
            return PlaybackController(self.adapter).recover()
        config = plan.operations.get(operation)
        params = config.params if config else {}
        if operation == "switch_episode":
            return EpisodeSwitcher(self.adapter).switch(strategy=config.strategy or params.get("strategy", "next_episode"), require_free=params.get("require_free", False), category=params.get("category"))
        if operation == "scroll_feed":
            return FeedScroller(self.adapter).scroll_once()
        return GenericOperationHandler(self.adapter).execute(operation, f"Execute safe UI operation {operation}")


__all__ = ["LoopWorkflow"]
