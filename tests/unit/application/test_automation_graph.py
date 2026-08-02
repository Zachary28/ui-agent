def test_main_graph_runs_real_lifecycle_nodes(tmp_path) -> None:
    from midscene_ui_agent.application.graphs.automation import build_automation_graph
    from midscene_ui_agent.infrastructure.persistence.langgraph import sqlite_checkpointer

    calls: list[str] = []

    def prepare(state):
        calls.append("prepare")
        return {"phase": "prepare_run"}

    def execute(state):
        calls.append("execute")
        return {"phase": "execute_route"}

    def finalize(state):
        calls.append("finalize")
        return {"phase": "finalize_run", "status": "succeeded"}

    checkpointer = sqlite_checkpointer(tmp_path / "graph.sqlite")
    try:
        graph = build_automation_graph(
            services={"prepare": prepare, "execute": execute, "finalize": finalize},
            checkpointer=checkpointer,
        )
        config = {"configurable": {"thread_id": "r1"}}
        result = graph.invoke(
            {"run_id": "r1", "thread_id": "r1", "mode": "live", "route": "single"},
            config=config,
        )

        assert calls == ["prepare", "execute", "finalize"]
        assert result["status"] == "succeeded"
        assert result["phase"] == "finalize_run"
        assert checkpointer.saver.get_tuple(config) is not None
    finally:
        checkpointer.close()


def test_sqlite_checkpointer_close_is_idempotent(tmp_path) -> None:
    from midscene_ui_agent.infrastructure.persistence.langgraph import sqlite_checkpointer

    checkpointer = sqlite_checkpointer(tmp_path / "graph.sqlite")

    checkpointer.close()
    checkpointer.close()


def test_default_graph_finalizes_running_state_as_succeeded(tmp_path) -> None:
    from midscene_ui_agent.application.graphs.automation import build_automation_graph
    from midscene_ui_agent.infrastructure.persistence.langgraph import sqlite_checkpointer

    with sqlite_checkpointer(tmp_path / "graph.sqlite") as checkpointer:
        graph = build_automation_graph(checkpointer=checkpointer)
        result = graph.invoke(
            {"run_id": "r1", "thread_id": "r1"},
            config={"configurable": {"thread_id": "r1"}},
        )

    assert result["status"] == "succeeded"
