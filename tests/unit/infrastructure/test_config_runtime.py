from pathlib import Path

import pytest


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def config_tree(tmp_path: Path) -> Path:
    _write(
        tmp_path / "defaults.yaml",
        """
schema_version: 1
loop:
  defaults: {interval_seconds: 5, min_operation_interval_seconds: 1}
  operations:
    skip_ad: {enabled: true, interval_seconds: 2}
""",
    )
    _write(
        tmp_path / "platforms" / "android.yaml",
        """
platform: android
loop:
  operations:
    skip_ad: {timeout_seconds: 9}
""",
    )
    _write(
        tmp_path / "apps" / "android" / "test.yaml",
        """
id: android.test
platform: android
app:
  package_name: com.example.video
  launch_uri: com.example.video
ui:
  popup_prompts: [Close the ordinary popup]
  ad_prompts: [Skip the advertisement]
""",
    )
    _write(
        tmp_path / "tasks" / "watch.yaml",
        """
profile: android.test
goal:
  prompt: Open a free television series and start playback
  category: television_series
  require_free: true
loop:
  operations:
    switch_episode: {enabled: true, strategy: next_episode, interval_seconds: 30}
""",
    )
    _write(
        tmp_path / "environments" / "ci.yaml",
        """
loop:
  defaults: {interval_seconds: 3}
""",
    )
    return tmp_path


def test_environment_and_point_override_are_applied_last(config_tree: Path) -> None:
    from midscene_ui_agent.infrastructure.config import ConfigResolver, parse_overrides

    resolved = ConfigResolver(config_tree).resolve(
        platform="android",
        app="android.test",
        task="watch",
        environment="ci",
        overrides=parse_overrides(
            [
                "loop.defaults.interval_seconds=7",
                "loop.operations.skip_ad.enabled=false",
            ]
        ),
    )

    assert resolved["loop"]["defaults"]["interval_seconds"] == 7
    assert resolved["loop"]["operations"]["skip_ad"]["enabled"] is False
    assert resolved["loop"]["operations"]["skip_ad"]["timeout_seconds"] == 9


def test_point_override_parses_json_then_falls_back_to_string() -> None:
    from midscene_ui_agent.infrastructure.config import parse_overrides

    assert parse_overrides(["a.enabled=true", "a.count=2", "a.label=free only"]) == {
        "a": {"enabled": True, "count": 2, "label": "free only"}
    }


def test_unknown_override_path_is_rejected(config_tree: Path) -> None:
    from midscene_ui_agent.infrastructure.config import ConfigResolver, parse_overrides

    with pytest.raises(ValueError, match="unknown override path"):
        ConfigResolver(config_tree).resolve(
            platform="android",
            app="android.test",
            task="watch",
            overrides=parse_overrides(["loop.not_a_field=1"]),
        )


def test_task_goal_builds_request_and_updates_loop_params(config_tree: Path) -> None:
    from midscene_ui_agent.application.nodes.config import resolve_run_config

    configured = resolve_run_config(
        platform="android",
        app="android.test",
        task="watch",
        config_root=config_tree,
        target_overrides={"device_id": "fake"},
    )

    assert configured.request.goal == "Open a free television series and start playback"
    assert configured.request.target.app_uri == "com.example.video"
    switch = configured.request.loop.operations["switch_episode"]
    assert switch.params["category"] == "television_series"
    assert switch.params["require_free"] is True
    assert all(configured.fingerprints.model_dump().values())
