def test_run_operation_checkpoints_each_step(tmp_path) -> None:
    from midscene_ui_agent.application.graphs.single_operation import build_single_operation_graph
    from midscene_ui_agent.infrastructure.persistence.langgraph import sqlite_checkpointer

    calls: list[str] = []

    def execute(state, operation):
        calls.append(operation)
        return {"phase": operation, "status": "succeeded", "message": operation}

    with sqlite_checkpointer(tmp_path / "single.sqlite") as checkpointer:
        graph = build_single_operation_graph(executor=execute, checkpointer=checkpointer)
        config = {"configurable": {"thread_id": "r1"}}
        result = graph.invoke(
            {"run_id": "r1", "thread_id": "r1", "request": {"operation": "run"}},
            config=config,
        )
        history = list(graph.get_state_history(config))

    assert calls == ["connect", "health_check", "run", "screenshot"]
    assert [step["phase"] for step in result["steps"]] == calls
    assert result["status"] == "succeeded"
    assert len(history) >= 5


def test_failed_step_stops_later_ui_actions() -> None:
    from midscene_ui_agent.application.graphs.single_operation import build_single_operation_graph

    calls: list[str] = []

    def execute(state, operation):
        calls.append(operation)
        status = "failed" if operation == "run" else "succeeded"
        return {"phase": operation, "status": status, "message": f"{operation} result"}

    graph = build_single_operation_graph(executor=execute)
    result = graph.invoke({"run_id": "r1", "request": {"operation": "run"}})

    assert calls == ["connect", "health_check", "run"]
    assert result["status"] == "failed"
    assert result["error"] == "run result"


def test_failed_step_without_message_stops_later_ui_actions() -> None:
    from midscene_ui_agent.application.graphs.single_operation import build_single_operation_graph

    calls: list[str] = []

    def execute(state, operation):
        calls.append(operation)
        status = "failed" if operation == "health_check" else "succeeded"
        return {"phase": operation, "status": status, "message": ""}

    graph = build_single_operation_graph(executor=execute)
    result = graph.invoke({"run_id": "r1", "request": {"operation": "run"}})

    assert calls == ["connect", "health_check"]
    assert result["status"] == "failed"
    assert result["error"] == "operation failed"


def test_ui_action_connects_before_operation() -> None:
    from midscene_ui_agent.application.graphs.single_operation import build_single_operation_graph

    calls: list[str] = []
    graph = build_single_operation_graph(
        executor=lambda state, operation: calls.append(operation)
        or {"phase": operation, "status": "succeeded", "message": ""}
    )

    graph.invoke({"request": {"operation": "screenshot"}})

    assert calls == ["connect", "screenshot"]


def test_single_operation_subgraph_runs_inside_main_graph(tmp_path) -> None:
    from midscene_ui_agent.application.graphs.automation import build_automation_graph
    from midscene_ui_agent.application.graphs.single_operation import build_single_operation_graph
    from midscene_ui_agent.infrastructure.persistence.langgraph import sqlite_checkpointer

    calls: list[str] = []
    single = build_single_operation_graph(
        executor=lambda state, operation: calls.append(operation)
        or {"phase": operation, "status": "succeeded", "message": ""}
    )
    with sqlite_checkpointer(tmp_path / "main.sqlite") as checkpointer:
        graph = build_automation_graph(execution_graph=single, checkpointer=checkpointer)
        result = graph.invoke(
            {"run_id": "r1", "thread_id": "r1", "request": {"operation": "screenshot"}},
            config={"configurable": {"thread_id": "r1"}},
        )

    assert calls == ["connect", "screenshot"]
    assert result["status"] == "succeeded"
    assert result["phase"] == "finalize_run"


def test_fresh_run_reusing_run_id_does_not_duplicate_checkpointed_steps(tmp_path) -> None:
    from midscene_ui_agent.domain.contracts import AutomationRequest
    from midscene_ui_agent.infrastructure.execution.runner import CommandResult
    from midscene_ui_agent.interfaces.api import run

    operations = ["connect", "health_check", "run", "screenshot"]

    class FakeRunner:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def run(self, spec, *, run_id, event_id):
            self.calls.append(event_id)
            return CommandResult(spec.argv, 0, "", "")

    runner = FakeRunner()
    request = AutomationRequest(
        platform="browser",
        target={"url": "http://example.test"},
        goal="inspect",
        operation="run",
        mode="live",
        report_dir=str(tmp_path),
        run_id="r1",
    )

    first = run(request, runner=runner)
    second = run(request, runner=runner)

    assert [step.phase for step in first.steps] == operations
    assert [step.phase for step in second.steps] == operations
    assert runner.calls == operations * 2


def test_fresh_run_reusing_failed_run_id_clears_checkpointed_error(tmp_path) -> None:
    from midscene_ui_agent.domain.contracts import AutomationRequest
    from midscene_ui_agent.infrastructure.execution.runner import CommandResult
    from midscene_ui_agent.interfaces.api import run

    class FailOnceRunner:
        def __init__(self) -> None:
            self.calls: list[str] = []
            self.failed = False

        def run(self, spec, *, run_id, event_id):
            self.calls.append(event_id)
            if event_id == "run" and not self.failed:
                self.failed = True
                return CommandResult(spec.argv, 1, "", "failed once")
            return CommandResult(spec.argv, 0, "", "")

    runner = FailOnceRunner()
    request = AutomationRequest(
        platform="browser",
        target={"url": "http://example.test"},
        goal="inspect",
        operation="run",
        mode="live",
        report_dir=str(tmp_path),
        run_id="r1",
    )

    first = run(request, runner=runner)
    second = run(request, runner=runner)

    assert first.status == "failed"
    assert second.status == "succeeded"
    assert [step.phase for step in second.steps] == ["connect", "health_check", "run", "screenshot"]
    assert second.error is None
    assert runner.calls == [
        "connect",
        "health_check",
        "run",
        "connect",
        "health_check",
        "run",
        "screenshot",
    ]


def test_fresh_run_clears_all_checkpointed_result_and_cursor_fields(tmp_path) -> None:
    from midscene_ui_agent.application.graphs.single_operation import build_single_operation_graph
    from midscene_ui_agent.infrastructure.persistence.langgraph import sqlite_checkpointer

    calls: list[str] = []

    def execute(state, operation):
        calls.append(operation)
        return {"phase": operation, "status": "succeeded", "message": "fresh"}

    with sqlite_checkpointer(tmp_path / "fresh-state.sqlite") as checkpointer:
        graph = build_single_operation_graph(executor=execute, checkpointer=checkpointer)
        config = {"configurable": {"thread_id": "r1"}}
        resumed = graph.invoke(
            {
                "run_id": "r1",
                "thread_id": "r1",
                "request": {"operation": "connect"},
                "resume": True,
                "operation_steps": ["connect"],
                "step_index": 1,
                "steps": [{"phase": "old", "status": "failed"}],
                "artifacts": [{"kind": "report", "path": "old.html"}],
                "error": "old error",
                "secondary_errors": ["old secondary error"],
                "status": "failed",
                "exit_reason": "max_runtime",
                "release_attempted": True,
                "resources_released": True,
                "resource_release_state": {"browser": "closed"},
                "report_path": "old-report",
                "result_path": "old-result.json",
                "manifest_path": "old-manifest.json",
                "events_path": "old-events.jsonl",
            },
            config=config,
        )
        result = graph.invoke(
            {
                "run_id": "r1",
                "thread_id": "r1",
                "request": {"operation": "connect"},
                "resume": False,
            },
            config=config,
        )

    assert resumed["artifacts"] == [{"kind": "report", "path": "old.html"}]
    assert resumed["secondary_errors"] == ["old secondary error"]
    assert resumed["exit_reason"] == "max_runtime"
    assert resumed["release_attempted"] is True
    assert resumed["resources_released"] is True
    assert resumed["resource_release_state"] == {"browser": "closed"}
    assert resumed["report_path"] == "old-report"
    assert resumed["result_path"] == "old-result.json"
    assert resumed["manifest_path"] == "old-manifest.json"
    assert resumed["events_path"] == "old-events.jsonl"
    assert calls == ["connect"]
    assert result["operation_steps"] == ["connect"]
    assert result["step_index"] == 1
    assert result["steps"] == [
        {"phase": "connect", "status": "succeeded", "message": "fresh"}
    ]
    assert result["artifacts"] == []
    assert result["error"] is None
    assert result["secondary_errors"] == []
    assert result["status"] == "succeeded"
    assert result["exit_reason"] is None
    assert result["release_attempted"] is False
    assert result["resources_released"] is False
    assert result["resource_release_state"] == {}
    assert result["report_path"] == ""
    assert result["result_path"] == ""
    assert result["manifest_path"] == ""
    assert result["events_path"] == ""
