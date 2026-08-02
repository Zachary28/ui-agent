def test_run_configured_builds_request_from_packaged_task(tmp_path) -> None:
    from midscene_ui_agent.interfaces.api import run_configured

    result = run_configured(
        platform="android",
        app="android.tencent-video",
        task="watch-free-series",
        overrides=["loop.exit_conditions.max_runtime_seconds=12"],
        target_overrides={"device_id": "fake"},
        report_dir=str(tmp_path),
        mode="plan",
    )

    assert result.status == "planned"
    assert (tmp_path / result.run_id / "plan.json").is_file()


def test_direct_run_api_remains_available(tmp_path) -> None:
    from midscene_ui_agent.domain.contracts import AutomationRequest
    from midscene_ui_agent.interfaces.api import run

    result = run(
        AutomationRequest(
            platform="browser",
            target={"url": "https://example.test"},
            goal="inspect",
            report_dir=str(tmp_path),
        )
    )

    assert result.status == "planned"
