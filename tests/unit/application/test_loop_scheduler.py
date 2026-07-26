from dataclasses import dataclass


class FakeClock:
    def __init__(self):
        self.now = 0.0
    def monotonic(self):
        return self.now
    def advance(self, seconds):
        self.now += seconds


def test_selector_prefers_popup_over_playback_and_never_duplicates_tick():
    from midscene_ui_agent.application.loop.scheduler import LoopScheduler
    from midscene_ui_agent.application.loop.selector import OperationSelector
    from midscene_ui_agent.domain.runtime.loop import RuntimeState
    clock = FakeClock()
    scheduler = LoopScheduler(clock=clock)
    scheduler.start(["dismiss_popup", "check_playback"], startup=["dismiss_popup"])
    state = RuntimeState()
    state.popup_detected = True
    due = scheduler.due_operations()
    assert OperationSelector().choose(due, state) == "dismiss_popup"
    assert OperationSelector().choose(due, state) is None


def test_monotonic_runtime_and_no_progress_exit_counter():
    from midscene_ui_agent.domain.runtime.loop import RuntimeState
    state = RuntimeState(max_no_progress_ticks=2)
    state.record_tick(progress_fingerprint="same")
    state.record_tick(progress_fingerprint="same")
    assert state.no_progress_ticks == 2


def test_interval_due_after_clock_advance():
    from midscene_ui_agent.application.loop.scheduler import LoopScheduler
    clock = FakeClock()
    scheduler = LoopScheduler(clock=clock, intervals={"check_playback": 5})
    scheduler.start(["check_playback"])
    assert scheduler.due_operations() == []
    clock.advance(5)
    assert scheduler.due_operations() == ["check_playback"]
