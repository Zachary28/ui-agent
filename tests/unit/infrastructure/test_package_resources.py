import subprocess
import sys
import zipfile
from pathlib import Path

import pytest


def test_default_config_root_contains_runtime_resources() -> None:
    from midscene_ui_agent.infrastructure.config import default_config_root, default_skill_lock_path

    root = default_config_root()

    assert (root / "defaults.yaml").is_file()
    assert (root / "schemas" / "app-profile.schema.json").is_file()
    assert (root / "schemas" / "loop-plan.schema.json").is_file()
    assert default_skill_lock_path().is_file()


def test_built_wheel_contains_runtime_resources(tmp_path: Path) -> None:
    project_root = Path(__file__).parents[3]
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            ".",
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            str(tmp_path),
        ],
        cwd=project_root,
        check=True,
        capture_output=True,
        text=True,
    )
    wheel = next(tmp_path.glob("midscene_ui_agent-*.whl"))
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())

    assert "midscene_ui_agent/config/defaults.yaml" in names
    assert "midscene_ui_agent/config/schemas/app-profile.schema.json" in names
    assert "midscene_ui_agent/config/schemas/loop-plan.schema.json" in names
    assert "midscene_ui_agent/config/skills.lock.json" in names


@pytest.mark.parametrize(
    "app,task",
    [
        ("android.bilibili", "short-video-loop"),
        ("android.tencent-video", "switch-episodes"),
        ("android.tencent-video", "watch-free-series"),
    ],
)
def test_bundled_android_tasks_resolve(app: str, task: str) -> None:
    from midscene_ui_agent.application.nodes.config import resolve_run_config

    configured = resolve_run_config(
        platform="android",
        app=app,
        task=task,
        target_overrides={"device_id": "fake"},
    )

    assert configured.request.goal
    assert configured.request.loop is not None
