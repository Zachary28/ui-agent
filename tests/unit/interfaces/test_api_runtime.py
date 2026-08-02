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


def test_resume_run_recomputes_explicit_target_and_skill_lock_fingerprints(monkeypatch, tmp_path) -> None:
    from midscene_ui_agent.domain.contracts import AutomationRequest
    from midscene_ui_agent.interfaces.api import resume_run

    report_dir = tmp_path / "artifacts"
    report_dir.mkdir()
    (report_dir / "langgraph.sqlite").touch()
    lock = tmp_path / "skills.lock.json"
    lock.write_text('{"version": 2}', encoding="utf-8")
    checkpoint_values = {
        "request": AutomationRequest(
            platform="browser",
            target={"url": "https://old.test"},
            goal="watch",
            mode="live",
            run_id="resume-1",
            report_dir=str(report_dir),
        ).model_dump(mode="json"),
        "fingerprints": {
            "config_hash": "config-old",
            "profile_hash": "profile-old",
            "loop_plan_hash": "loop-old",
            "skill_lock_hash": "skill-old",
            "target_fingerprint": "target-old",
        },
    }

    class FakeSaver:
        def get_tuple(self, _config):
            return type("Checkpoint", (), {"checkpoint": {"channel_values": checkpoint_values}})()

    class FakeContext:
        saver = FakeSaver()

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    captured = {}
    monkeypatch.setattr("midscene_ui_agent.interfaces.api.sqlite_checkpointer", lambda _path: FakeContext())
    monkeypatch.setattr(
        "midscene_ui_agent.interfaces.api.run",
        lambda request, **kwargs: captured.update(request=request, **kwargs) or "ok",
    )

    assert (
        resume_run(
            "resume-1",
            report_dir=report_dir,
            skills_lock=lock,
            target_overrides={"url": "https://changed.test"},
        )
        == "ok"
    )
    assert captured["request"].target.url == "https://changed.test"
    assert captured["fingerprints"].target_fingerprint != "target-old"
    assert captured["fingerprints"].skill_lock_hash != "skill-old"
