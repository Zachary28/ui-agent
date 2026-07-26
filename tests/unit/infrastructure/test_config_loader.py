import pytest


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_resolution_order_and_operation_deep_merge(tmp_path):
    from midscene_ui_agent.infrastructure.config.resolver import ConfigResolver

    _write(tmp_path / "defaults.yaml", """
loop:
  defaults: {interval_seconds: 5, min_operation_interval_seconds: 1}
  operations:
    check_playback: {enabled: true, max_attempts: 2}
""")
    _write(tmp_path / "platforms" / "android.yaml", """
extends: defaults
platform: android
loop:
  operations: {check_playback: {timeout_seconds: 9}}
""")
    _write(tmp_path / "apps" / "android.tencent-video.yaml", """
extends: platforms/android.yaml
id: android.tencent-video
loop:
  operations: {switch_episode: {enabled: true, strategy: next_episode, interval_seconds: 300}}
""")
    _write(tmp_path / "tasks" / "watch-free-series.yaml", """
profile: android.tencent-video
loop:
  operations: {switch_episode: {interval_seconds: 120}}
""")
    resolved = ConfigResolver(tmp_path).resolve(
        platform="android", app="android.tencent-video", task="watch-free-series",
        overrides={"loop": {"operations": {"switch_episode": {"interval_seconds": 60}}}},
    )
    assert resolved["loop"]["operations"]["check_playback"]["timeout_seconds"] == 9
    assert resolved["loop"]["operations"]["check_playback"]["max_attempts"] == 2
    assert resolved["loop"]["operations"]["switch_episode"]["interval_seconds"] == 60


def test_secret_values_are_env_references_and_hash_is_stable(tmp_path, monkeypatch):
    from midscene_ui_agent.infrastructure.config.resolver import ConfigResolver

    _write(tmp_path / "defaults.yaml", "credentials: {model_api_key_env: MIDSCENE_MODEL_API_KEY}\n")
    _write(tmp_path / "platforms" / "browser.yaml", "extends: defaults\nplatform: browser\n")
    _write(tmp_path / "apps" / "browser.test.yaml", "extends: platforms/browser.yaml\nid: browser.test\n")
    _write(tmp_path / "tasks" / "short.yaml", "profile: browser.test\n")
    monkeypatch.setenv("MIDSCENE_MODEL_API_KEY", "must-not-be-written")
    value = ConfigResolver(tmp_path).resolve(platform="browser", app="browser.test", task="short")
    assert "must-not-be-written" not in repr(value)
    assert ConfigResolver.canonical_hash(value) == ConfigResolver.canonical_hash(value)


def test_unknown_profile_and_invalid_override_are_rejected(tmp_path):
    from midscene_ui_agent.infrastructure.config.resolver import ConfigResolver
    _write(tmp_path / "defaults.yaml", "{}\n")
    with pytest.raises(FileNotFoundError):
        ConfigResolver(tmp_path).resolve(platform="android", app="missing", task="missing")
