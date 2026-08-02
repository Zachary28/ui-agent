from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from midscene_ui_agent.domain.contracts import LoopPlan


@dataclass
class FakeRuntime:
    now: float = 0.0
    observations: list[dict] = field(default_factory=lambda: [{}])
    responses: dict[str, list[dict]] = field(default_factory=dict)
    calls: list[tuple[str, float, int]] = field(default_factory=list)

    def monotonic(self) -> float:
        return self.now

    def wait(self, seconds: float) -> None:
        self.now += max(seconds, 0.1)

    def observe(self, state) -> dict:
        del state
        return self.observations.pop(0) if len(self.observations) > 1 else self.observations[0]

    def execute(self, operation: str, timeout: float, attempt: int, state) -> dict:
        del state
        self.calls.append((operation, timeout, attempt))
        queue = self.responses.get(operation, [])
        return queue.pop(0) if queue else {"succeeded": True, "message": f"{operation}:{len(self.calls)}"}


def _run(runtime: FakeRuntime, payload: dict):
    from midscene_ui_agent.application.graphs.loop import LoopGraphServices, build_loop_graph

    plan = LoopPlan.model_validate(payload)
    graph = build_loop_graph(
        services=LoopGraphServices(
            clock=runtime.monotonic,
            wait=runtime.wait,
            observe=runtime.observe,
            execute=runtime.execute,
        )
    )
    return graph.invoke({"run_id": "r1", "plan": plan.model_dump(mode="json")}, {"recursion_limit": 500})


def test_operation_uses_its_timeout_and_retries() -> None:
    runtime = FakeRuntime(
        responses={
            "skip_ad": [
                {"succeeded": False, "reason": "command_failed"},
                {"succeeded": False, "reason": "command_failed"},
                {"succeeded": True, "message": "skipped"},
            ]
        }
    )

    result = _run(
        runtime,
        {
            "defaults": {"min_operation_interval_seconds": 0.1},
            "exit_conditions": {"max_runtime_seconds": 0.1},
            "operations": {
                "skip_ad": {
                    "enabled": True,
                    "startup": True,
                    "max_attempts": 3,
                    "timeout_seconds": 4,
                    "interval_seconds": 1,
                }
            },
        },
    )

    assert result["loop_summary"]["operations"]["skip_ad"]["attempts"] == 3
    assert [call[1] for call in runtime.calls] == [4, 4, 4]


@pytest.mark.parametrize(
    ("field", "value", "reason", "operation"),
    [
        ("max_switches", 2, "max_switches", "switch_episode"),
        ("max_scrolls", 2, "max_scrolls", "scroll_feed"),
        ("target_count", 2, "target_count", "switch_episode"),
    ],
)
def test_count_limits_route_to_exact_exit_reason(field: str, value: int, reason: str, operation: str) -> None:
    runtime = FakeRuntime()
    operation_payload = {"enabled": True, "startup": True, "interval_seconds": 0.1}
    if operation == "switch_episode":
        operation_payload["strategy"] = "next_episode"
    else:
        operation_payload["scroll_limit"] = 3

    result = _run(
        runtime,
        {
            "defaults": {"min_operation_interval_seconds": 0.1},
            "exit_conditions": {"max_runtime_seconds": 10, field: value},
            "operations": {operation: operation_payload},
        },
    )

    assert result["exit_reason"] == reason


def test_login_required_exits_without_consuming_failure_budget() -> None:
    runtime = FakeRuntime(responses={"check_playback": [{"succeeded": False, "reason": "login required"}]})

    result = _run(
        runtime,
        {
            "exit_conditions": {"max_runtime_seconds": 10},
            "operations": {"check_playback": {"enabled": True, "startup": True}},
        },
    )

    assert result["exit_reason"] == "login_required"
    assert result["consecutive_failures"] == 0


@pytest.mark.parametrize(
    ("config", "observation", "advance"),
    [
        ({"startup": True}, {}, 0),
        ({"on_popup": True}, {"popup_detected": True}, 0),
        ({"on_ad": True}, {"ad_detected": True}, 0),
        ({"on_stall": True}, {"stalled": True}, 0),
        ({"at_runtime": 2}, {}, 2),
    ],
)
def test_configured_triggers_schedule_operation(config: dict, observation: dict, advance: float) -> None:
    runtime = FakeRuntime(now=advance, observations=[observation])
    result = _run(
        runtime,
        {
            "defaults": {"min_operation_interval_seconds": 0.1},
            "exit_conditions": {"max_runtime_seconds": advance + 0.1},
            "operations": {"screenshot": {"enabled": True, "interval_seconds": 100, **config}},
        },
    )

    assert runtime.calls[0][0] == "screenshot"
    assert result["loop_summary"]["operations"]["screenshot"]["successes"] == 1


def test_after_operation_trigger_and_configurable_priority() -> None:
    runtime = FakeRuntime(
        responses={
            "screenshot": [{"succeeded": False, "reason": "login_required"}],
        }
    )
    result = _run(
        runtime,
        {
            "defaults": {"min_operation_interval_seconds": 0.1},
            "exit_conditions": {"max_runtime_seconds": 10},
            "operations": {
                "play_video": {"enabled": True, "startup": True, "priority": 20},
                "check_playback": {"enabled": True, "startup": True, "priority": 1},
                "screenshot": {"enabled": True, "after_operation": ["play_video"], "priority": 30},
            },
        },
    )

    assert [call[0] for call in runtime.calls[:2]] == ["play_video", "screenshot"]
    assert result["exit_reason"] == "login_required"


def test_loop_subgraph_runs_inside_main_graph(tmp_path) -> None:
    from midscene_ui_agent.application.graphs.automation import build_automation_graph
    from midscene_ui_agent.application.graphs.loop import LoopGraphServices, build_loop_graph
    from midscene_ui_agent.infrastructure.persistence.langgraph import sqlite_checkpointer

    runtime = FakeRuntime()
    plan = LoopPlan.model_validate(
        {
            "defaults": {"min_operation_interval_seconds": 0.1},
            "exit_conditions": {"max_runtime_seconds": 0.1},
            "operations": {"screenshot": {"enabled": True, "startup": True}},
        }
    )
    loop_graph = build_loop_graph(
        services=LoopGraphServices(
            clock=runtime.monotonic,
            wait=runtime.wait,
            observe=runtime.observe,
            execute=runtime.execute,
        )
    )
    with sqlite_checkpointer(tmp_path / "main.sqlite") as checkpointer:
        graph = build_automation_graph(execution_graph=loop_graph, checkpointer=checkpointer)
        result = graph.invoke(
            {
                "run_id": "r1",
                "thread_id": "r1",
                "route": "loop",
                "plan": plan.model_dump(mode="json"),
            },
            config={"configurable": {"thread_id": "r1"}, "recursion_limit": 500},
        )

    assert runtime.calls[0][0] == "screenshot"
    assert result["phase"] == "finalize_run"
    assert result["exit_reason"] == "max_runtime"


@pytest.mark.parametrize(
    ("observation", "reason"),
    [
        ({"purchase_required": True}, "purchase_required"),
        ({"reachable": False}, "device_unreachable"),
        ({"model_error": True}, "model_error"),
        ({"popup_detected": True}, "unhandled_popup"),
        ({"cancelled": True}, "cancelled"),
    ],
)
def test_observation_exit_conditions_map_to_normalized_reason(observation: dict, reason: str) -> None:
    runtime = FakeRuntime(observations=[observation])

    result = _run(
        runtime,
        {
            "defaults": {"min_operation_interval_seconds": 0.1},
            "exit_conditions": {"max_runtime_seconds": 10},
            "operations": {},
        },
    )

    assert result["exit_reason"] == reason


def test_exhausted_operations_exit_at_consecutive_failure_limit() -> None:
    runtime = FakeRuntime(
        responses={
            "check_playback": [
                {"succeeded": False, "reason": "command_failed"},
                {"succeeded": False, "reason": "command_failed"},
            ]
        }
    )

    result = _run(
        runtime,
        {
            "defaults": {"min_operation_interval_seconds": 0.1},
            "exit_conditions": {"max_runtime_seconds": 10, "max_consecutive_failures": 2},
            "operations": {
                "check_playback": {
                    "enabled": True,
                    "startup": True,
                    "max_attempts": 1,
                    "interval_seconds": 0.1,
                }
            },
        },
    )

    assert result["exit_reason"] == "max_failures"
    assert result["consecutive_failures"] == 2


def test_repeated_observation_fingerprint_exits_for_no_progress() -> None:
    runtime = FakeRuntime(observations=[{"fingerprint": "same"}])

    result = _run(
        runtime,
        {
            "defaults": {"min_operation_interval_seconds": 0.1},
            "exit_conditions": {"max_runtime_seconds": 10, "max_no_progress_ticks": 2},
            "operations": {},
        },
    )

    assert result["exit_reason"] == "no_progress"
