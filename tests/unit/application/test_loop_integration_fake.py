from midscene_ui_agent.domain.runtime.loop import RuntimeState


def test_runtime_records_attempts_and_failures():
    state = RuntimeState()
    state.record_attempt("skip_ad", success=False)
    state.record_attempt("skip_ad", success=True)
    assert state.operation_attempts["skip_ad"] == 2
    assert state.operation_failures["skip_ad"] == 1
    assert state.consecutive_failures == 0


def test_all_platforms_are_registered():
    from midscene_ui_agent.platforms.registry import default_registry

    registry = default_registry()
    assert set(registry) == {"browser", "computer", "android", "ios", "harmony", "vitest_e2e"}
