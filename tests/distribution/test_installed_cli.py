from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest


def test_installed_wheel_exposes_configured_and_resume_options(tmp_path: Path) -> None:
    wheel_site = os.getenv("UI_AGENT_WHEEL_SITE")
    if not wheel_site:
        pytest.skip("UI_AGENT_WHEEL_SITE is set by the installed-wheel smoke job")

    environment = os.environ.copy()
    environment["PYTHONPATH"] = wheel_site
    completed = subprocess.run(
        [sys.executable, "-m", "midscene_ui_agent.interfaces.cli", "run", "--help"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    for option in ("--app", "--task", "--override", "--resume"):
        assert option in completed.stdout
