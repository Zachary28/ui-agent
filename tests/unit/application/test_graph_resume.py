from __future__ import annotations

import hashlib

from midscene_ui_agent.domain.contracts import AutomationRequest, RunFingerprints
from midscene_ui_agent.infrastructure.execution.runner import CommandResult


class RecordingRunner:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def run(self, spec, *, run_id, event_id):
        del run_id
        self.calls.append(event_id)
        return CommandResult(spec.argv, 0, "ok", "")


def _fingerprints(seed: str) -> RunFingerprints:
    return RunFingerprints(
        config_hash=f"config-{seed}",
        profile_hash=f"profile-{seed}",
        loop_plan_hash=f"loop-{seed}",
        skill_lock_hash=f"skill-{seed}",
        target_fingerprint=f"target-{seed}",
    )


def _request(tmp_path) -> AutomationRequest:
    return AutomationRequest(
        platform="browser",
        target={"url": "https://example.test"},
        goal="inspect",
        operation="run",
        mode="live",
        report_dir=str(tmp_path),
        run_id="r1",
    )


def test_resume_skips_completed_single_operation(tmp_path) -> None:
    from midscene_ui_agent.interfaces.api import run

    runner = RecordingRunner()
    request = _request(tmp_path)

    first = run(request, runner=runner, fingerprints=_fingerprints("same"))
    resumed = run(request, runner=runner, fingerprints=_fingerprints("same"), resume=True)

    assert first.status == "succeeded"
    assert resumed.status == "succeeded"
    assert runner.calls == ["connect", "health_check", "run", "screenshot"]


def test_resume_rejects_changed_fingerprint_before_connect(tmp_path) -> None:
    from midscene_ui_agent.interfaces.api import run

    runner = RecordingRunner()
    request = _request(tmp_path)
    run(request, runner=runner, fingerprints=_fingerprints("old"))
    runner.calls.clear()

    result = run(request, runner=runner, fingerprints=_fingerprints("changed"), resume=True)

    assert result.status == "resume_invalid"
    assert result.exit_reason == "resume_invalid"
    assert runner.calls == []


def test_non_idempotent_resume_uses_effect_verification() -> None:
    from midscene_ui_agent.domain.policies.resume import resume_action

    assert resume_action("switch_episode", effect_verified=True) == "complete"
    assert resume_action("switch_episode", effect_verified=False) == "retry"
    assert resume_action("screenshot", effect_verified=True) == "retry"


def test_direct_request_uses_raw_skill_lock_hash(tmp_path) -> None:
    from midscene_ui_agent.application.workflows.orchestrator import _request_fingerprints
    from midscene_ui_agent.infrastructure.config.resources import default_skill_lock_path

    expected = hashlib.sha256(default_skill_lock_path().read_bytes()).hexdigest()

    assert _request_fingerprints(_request(tmp_path)).skill_lock_hash == expected


def test_interrupted_single_operation_resumes_at_next_checkpoint(tmp_path) -> None:
    from midscene_ui_agent.application.graphs.single_operation import build_single_operation_graph
    from midscene_ui_agent.infrastructure.persistence.langgraph import sqlite_checkpointer

    calls: list[str] = []
    with sqlite_checkpointer(tmp_path / "single.sqlite") as checkpointer:
        graph = build_single_operation_graph(
            executor=lambda state, operation: (
                calls.append(operation) or {"phase": operation, "status": "succeeded", "message": "ok"}
            ),
            checkpointer=checkpointer,
        )
        config = {"configurable": {"thread_id": "r1"}}
        graph.invoke(
            {"run_id": "r1", "request": {"operation": "run"}},
            config=config,
            interrupt_after=["execute_step"],
        )
        resumed = graph.invoke(None, config=config)

    assert calls == ["connect", "health_check", "run", "screenshot"]
    assert resumed["status"] == "succeeded"


def test_loop_resume_verifies_non_idempotent_effect_before_execution(tmp_path) -> None:
    from midscene_ui_agent.application.graphs.loop import LoopGraphServices, build_loop_graph
    from midscene_ui_agent.infrastructure.persistence.langgraph import sqlite_checkpointer

    now = 0.0
    calls: list[str] = []
    verifications: list[tuple[str, str]] = []

    def clock() -> float:
        return now

    def wait(seconds: float) -> None:
        nonlocal now
        now += seconds

    services = LoopGraphServices(
        clock=clock,
        wait=wait,
        observe=lambda state: {},
        execute=lambda operation, timeout, attempt, state: calls.append(operation) or {"succeeded": True},
        verify_effect=lambda operation, operation_id, state: verifications.append((operation, operation_id)) or True,
    )
    plan = {
        "defaults": {"min_operation_interval_seconds": 0.1},
        "exit_conditions": {"max_runtime_seconds": 10, "max_switches": 1},
        "operations": {
            "switch_episode": {
                "enabled": True,
                "startup": True,
                "strategy": "next_episode",
            }
        },
    }
    with sqlite_checkpointer(tmp_path / "loop.sqlite") as checkpointer:
        graph = build_loop_graph(services=services, checkpointer=checkpointer)
        config = {"configurable": {"thread_id": "r1"}, "recursion_limit": 500}
        graph.invoke(
            {"run_id": "r1", "plan": plan},
            config=config,
            interrupt_before=["execute_operation"],
        )
        resumed = graph.invoke(None, config=config)

    assert verifications == [("switch_episode", "tick-1:switch_episode")]
    assert calls == []
    assert resumed["exit_reason"] == "max_switches"
