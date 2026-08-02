from typer.testing import CliRunner

import pytest


def test_cli_builds_request_from_task_config(tmp_path) -> None:
    from midscene_ui_agent.interfaces.cli import app

    result = CliRunner().invoke(
        app,
        [
            "run",
            "--platform",
            "android",
            "--app",
            "android.tencent-video",
            "--task",
            "watch-free-series",
            "--device-id",
            "fake",
            "--mode",
            "plan",
            "--report-dir",
            str(tmp_path),
            "--override",
            "loop.exit_conditions.max_runtime_seconds=12",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "planned" in result.stdout


def test_cli_resume_requires_existing_run_id(tmp_path) -> None:
    from midscene_ui_agent.interfaces.cli import app

    result = CliRunner().invoke(
        app,
        [
            "run",
            "--resume",
            "missing",
            "--report-dir",
            str(tmp_path),
            "--config-root",
            str(tmp_path / "config"),
        ],
    )

    assert result.exit_code != 0
    assert "checkpoint" in result.output.lower()


def test_cli_resume_passes_explicit_target_overrides(monkeypatch, tmp_path) -> None:
    from midscene_ui_agent.domain.contracts import AutomationResult
    from midscene_ui_agent.interfaces.cli import app

    captured = {}
    monkeypatch.setattr(
        "midscene_ui_agent.interfaces.cli.resume_run",
        lambda resume_id, **kwargs: (
            captured.update(resume_id=resume_id, **kwargs) or AutomationResult(run_id=resume_id, status="succeeded")
        ),
    )

    result = CliRunner().invoke(
        app,
        ["run", "--resume", "run-1", "--url", "https://changed.test", "--report-dir", str(tmp_path)],
    )

    assert result.exit_code == 0
    assert captured["target_overrides"]["url"] == "https://changed.test"


def test_cli_resume_rejects_config_overrides_without_selectors(monkeypatch) -> None:
    from midscene_ui_agent.interfaces.cli import app

    monkeypatch.setattr(
        "midscene_ui_agent.interfaces.cli.resume_run",
        lambda *_args, **_kwargs: pytest.fail("resume must not silently discard config overrides"),
    )

    result = CliRunner().invoke(app, ["run", "--resume", "run-1", "--override", "goal.prompt=changed"])

    assert result.exit_code == 2
    assert "--platform, --app and --task" in result.output


def test_cli_resume_rejects_incomplete_selectors(monkeypatch) -> None:
    from midscene_ui_agent.interfaces.cli import app

    monkeypatch.setattr(
        "midscene_ui_agent.interfaces.cli.resume_run",
        lambda *_args, **_kwargs: pytest.fail("incomplete selectors must not reach resume"),
    )

    result = CliRunner().invoke(
        app,
        ["run", "--resume", "run-1", "--platform", "browser", "--url", "https://changed.test"],
    )

    assert result.exit_code == 2
    assert "--platform, --app and --task" in result.output
