from typer.testing import CliRunner


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
