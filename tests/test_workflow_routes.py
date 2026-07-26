from midscene_ui_agent.application.workflows.graph import WorkflowEngine

def test_workflow_runs_directly_without_approval(tmp_path):
    calls = []; engine = WorkflowEngine(checkpoint_path=tmp_path / "c.json")
    state = engine.run("r1", connect=lambda: calls.append("connect"))
    assert state["status"] == "succeeded" and calls == ["connect"]

def test_workflow_succeeds_and_checkpoints(tmp_path):
    calls = []; engine = WorkflowEngine(checkpoint_path=tmp_path / "c.json")
    state = engine.run("r2", connect=lambda: calls.append("connect"))
    assert state["status"] == "succeeded" and calls == ["connect"]
    assert engine.checkpoint.get("r2")["status"] == "succeeded"
