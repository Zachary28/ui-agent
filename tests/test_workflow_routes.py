from midscene_ui_agent.domain.contracts import AutomationRequest
from midscene_ui_agent.infrastructure.execution.runner import CommandResult
from midscene_ui_agent.infrastructure.persistence.checkpoint import SqliteCheckpoint
from midscene_ui_agent.interfaces.api import run


class RecordingRunner:
    def __init__(self) -> None:
        self.operations: list[str] = []

    def run(self, spec, **_kwargs):
        self.operations.append(spec.argv[3])
        return CommandResult(spec.argv, 0, "ok", "")


def test_workflow_runs_directly_without_approval(tmp_path) -> None:
    runner = RecordingRunner()
    request = AutomationRequest(
        platform="browser",
        target={"url": "https://example.test"},
        goal="take a screenshot",
        operation="screenshot",
        mode="live",
        report_dir=str(tmp_path),
        run_id="r1",
    )

    result = run(request, runner=runner)

    assert result.status == "succeeded"
    assert runner.operations == ["connect", "take_screenshot"]


def test_workflow_persists_final_result(tmp_path) -> None:
    request = AutomationRequest(
        platform="browser",
        target={"url": "https://example.test"},
        goal="take a screenshot",
        operation="screenshot",
        mode="live",
        report_dir=str(tmp_path),
        run_id="r2",
    )

    result = run(request, runner=RecordingRunner())
    checkpoint = SqliteCheckpoint(tmp_path / "checkpoints.sqlite")
    try:
        persisted = checkpoint.get("r2")
    finally:
        checkpoint.close()

    assert result.status == "succeeded"
    assert persisted["status"] == "succeeded"
