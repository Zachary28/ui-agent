from pathlib import Path

from midscene_ui_agent.domain.contracts import AutomationRequest
from midscene_ui_agent.infrastructure.execution.runner import CommandResult
from midscene_ui_agent.platforms.base import ExecutionContext
from midscene_ui_agent.platforms.registry import default_registry


class FakeRunner:
    def __init__(self) -> None:
        self.calls = []

    def run(self, spec, *, run_id="adhoc", event_id="command") -> CommandResult:
        self.calls.append((spec, run_id, event_id))
        return CommandResult(spec.argv, 0, "screen changed", "")


def test_every_platform_supports_graph_runtime_protocol() -> None:
    for adapter in default_registry().values():
        assert callable(adapter.command)
        assert callable(adapter.execute_prompt)
        assert callable(adapter.observe)
        assert callable(adapter.verify_effect)
        assert callable(adapter.release)


def test_execute_prompt_uses_injected_runner_and_context(tmp_path: Path) -> None:
    from midscene_ui_agent.platforms.browser import BrowserAdapter

    request = AutomationRequest.model_validate(
        {"platform": "browser", "target": {"url": "https://example.test"}, "goal": "initial"}
    )
    runner = FakeRunner()
    context = ExecutionContext(
        request=request,
        runner=runner,
        run_id="r1",
        event_id="tick-1",
        cwd=tmp_path,
        timeout_seconds=12,
    )

    outcome = BrowserAdapter().execute_prompt("Verify the title", context)

    assert outcome.succeeded is True
    assert outcome.message == "screen changed"
    spec, run_id, event_id = runner.calls[0]
    assert spec.argv[-2:] == ["--prompt", "Verify the title"]
    assert spec.cwd == str(tmp_path)
    assert spec.timeout_seconds == 12
    assert (run_id, event_id) == ("r1", "tick-1:run")


def test_observe_and_verify_effect_are_structured(tmp_path: Path) -> None:
    from midscene_ui_agent.platforms.android import AndroidAdapter

    request = AutomationRequest.model_validate(
        {"platform": "android", "target": {"device_id": "fake"}, "goal": "watch"}
    )
    runner = FakeRunner()
    context = ExecutionContext(request=request, runner=runner, run_id="r1", cwd=tmp_path)
    adapter = AndroidAdapter()

    observation = adapter.observe(context)
    verified = adapter.verify_effect("switch_episode", "op-7", context)

    assert observation.reachable is True
    assert observation.fingerprint
    assert verified is True
    assert [call[2] for call in runner.calls] == ["observe:screenshot", "verify:assert"]
