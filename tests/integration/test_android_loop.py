from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

import pytest

from midscene_ui_agent.domain.contracts import AutomationRequest
from midscene_ui_agent.infrastructure.execution.runner import CommandRunner
from midscene_ui_agent.interfaces.api import _load_environment, run

pytestmark = pytest.mark.integration


class InterruptAfterFirstCommand:
    def __init__(self, delegate: CommandRunner) -> None:
        self.delegate = delegate
        self.calls = 0

    def run(self, spec, *, run_id: str, event_id: str):
        self.calls += 1
        if self.calls == 2:
            raise RuntimeError("simulated integration interruption")
        return self.delegate.run(spec, run_id=run_id, event_id=event_id)


def test_android_device_resumes_after_interruption(tmp_path: Path) -> None:
    if os.getenv("UI_AGENT_RUN_INTEGRATION") != "1":
        pytest.skip("set UI_AGENT_RUN_INTEGRATION=1 to enable Android integration")
    _load_environment()
    if not os.getenv("MIDSCENE_MODEL_API_KEY") or not os.getenv("MIDSCENE_MODEL_NAME"):
        pytest.skip("Midscene model configuration is unavailable")
    adb = shutil.which("adb")
    if not adb:
        pytest.skip("adb executable not found")
    device_id = os.getenv("UI_AGENT_ANDROID_DEVICE", "AGYJUT3628001141")
    devices = subprocess.run([adb, "devices"], capture_output=True, text=True, check=False).stdout
    if f"{device_id}\tdevice" not in devices:
        pytest.skip(f"Android device {device_id} is not connected")

    request = AutomationRequest(
        platform="android",
        target={"device_id": device_id},
        goal="Capture the current screen without login, purchase, or account changes",
        operation="screenshot",
        mode="live",
        report_dir=str(tmp_path),
        run_id="android-integration-resume",
    )
    interrupted_runner = InterruptAfterFirstCommand(CommandRunner(tmp_path))

    with pytest.raises(RuntimeError, match="simulated integration interruption"):
        run(request, runner=interrupted_runner)
    result = run(request, runner=CommandRunner(tmp_path), resume=True)

    assert interrupted_runner.calls == 2
    assert result.status == "succeeded"
    assert (tmp_path / "langgraph.sqlite").is_file()
