class FakeAdapter:
    package = "fake"
    def __init__(self):
        self.prompts = []
    def execute_prompt(self, prompt):
        self.prompts.append(prompt)
        return "playing"


def test_loop_runtime_runs_ticks_until_runtime_limit(tmp_path):
    from midscene_ui_agent.application.services.loop_runtime import LoopRuntime
    from midscene_ui_agent.domain.contracts import LoopPlan
    plan = LoopPlan.model_validate({"defaults": {"interval_seconds": 1}, "exit_conditions": {"max_runtime_seconds": 0.01}, "operations": {"check_playback": {"enabled": True, "interval_seconds": 1}}})
    result = LoopRuntime(FakeAdapter()).run(plan, artifact_root=tmp_path)
    assert result.exit_reason == "max_runtime"
    assert result.loop_summary["ticks"] == 0


def test_loop_runtime_cancel_is_clean(tmp_path):
    from midscene_ui_agent.application.services.loop_runtime import LoopRuntime
    from midscene_ui_agent.domain.contracts import LoopPlan
    workflow = LoopRuntime(FakeAdapter())
    workflow.cancel()
    result = workflow.run(LoopPlan.model_validate({"exit_conditions": {"max_runtime_seconds": 1}, "operations": {"screenshot": {"enabled": True}}}), artifact_root=tmp_path)
    assert result.exit_reason == "cancelled"


def test_api_routes_loop_request_to_runtime(tmp_path):
    from midscene_ui_agent.interfaces.api import run
    from midscene_ui_agent.domain.contracts import AutomationRequest
    request = AutomationRequest.model_validate({
        "platform": "android", "target": {"device_id": "fake"}, "goal": "watch",
        "mode": "live", "report_dir": str(tmp_path),
        "loop": {"exit_conditions": {"max_runtime_seconds": 0.01}, "operations": {"check_playback": {"enabled": True}}},
    })
    result = run(request, adapters={"android": FakeAdapter()})
    assert result.exit_reason == "max_runtime"
    assert (tmp_path / "langgraph.sqlite").is_file()
