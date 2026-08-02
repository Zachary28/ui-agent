import pytest


def test_exit_policy_reports_runtime_and_no_progress():
    from midscene_ui_agent.domain.policies.exit import ExitPolicy
    from midscene_ui_agent.domain.runtime.loop import RuntimeState
    state = RuntimeState(max_no_progress_ticks=2, elapsed_seconds=11)
    assert ExitPolicy().evaluate(state, max_runtime_seconds=10).reason == "max_runtime"
    state.elapsed_seconds = 1
    state.no_progress_ticks = 2
    assert ExitPolicy().evaluate(state, max_runtime_seconds=10).reason == "no_progress"


def test_exit_policy_handles_limits_and_cancel():
    from midscene_ui_agent.domain.policies.exit import ExitPolicy
    from midscene_ui_agent.domain.runtime.loop import RuntimeState
    state = RuntimeState(switch_count=3)
    assert ExitPolicy().evaluate(state, max_runtime_seconds=10, max_switches=3).reason == "max_switches"
    state.cancelled = True
    assert ExitPolicy().evaluate(state, max_runtime_seconds=10).reason == "cancelled"


def test_checkpoint_rejects_fingerprint_mismatch_without_secrets(tmp_path):
    from midscene_ui_agent.infrastructure.persistence.loop_checkpoint import LoopCheckpoint
    from midscene_ui_agent.domain.runtime.loop import RuntimeState
    cp = LoopCheckpoint(tmp_path / "checkpoint.json")
    cp.save(RuntimeState(), fingerprints={"loop_plan_hash": "a"})
    with pytest.raises(ValueError, match="RESUME_INVALID"):
        cp.restore(fingerprints={"loop_plan_hash": "b"})
    assert "must-not-be-written" not in (tmp_path / "checkpoint.json").read_text()
