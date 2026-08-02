from __future__ import annotations

import os
from pathlib import Path
import shutil

import pytest

from midscene_ui_agent.domain.contracts import AutomationRequest
from midscene_ui_agent.infrastructure.execution.runner import CommandRunner
from midscene_ui_agent.interfaces.api import _load_environment, run

pytestmark = pytest.mark.integration


def _chrome_available() -> bool:
    candidates = [shutil.which("chrome"), shutil.which("google-chrome"), shutil.which("chromium")]
    for variable in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        root = os.getenv(variable)
        if root:
            candidates.append(str(Path(root) / "Google" / "Chrome" / "Application" / "chrome.exe"))
    return any(candidate and Path(candidate).exists() for candidate in candidates)


class InterruptAfterFirstCommand:
    def __init__(self, delegate: CommandRunner) -> None:
        self.delegate = delegate
        self.calls = 0

    def run(self, spec, *, run_id: str, event_id: str):
        self.calls += 1
        if self.calls == 2:
            raise RuntimeError("simulated integration interruption")
        return self.delegate.run(spec, run_id=run_id, event_id=event_id)


def test_browser_public_page_resumes_after_interruption(tmp_path: Path) -> None:
    if os.getenv("UI_AGENT_RUN_INTEGRATION") != "1":
        pytest.skip("set UI_AGENT_RUN_INTEGRATION=1 to enable browser integration")
    _load_environment()
    if not os.getenv("MIDSCENE_MODEL_API_KEY") or not os.getenv("MIDSCENE_MODEL_NAME"):
        pytest.skip("Midscene model configuration is unavailable")
    if not _chrome_available():
        pytest.skip("Chrome executable not found")

    request = AutomationRequest(
        platform="browser",
        target={"url": "https://example.com"},
        goal="Capture the public example page without entering any data",
        operation="screenshot",
        mode="live",
        report_dir=str(tmp_path),
        run_id="browser-integration-resume",
    )
    interrupted_runner = InterruptAfterFirstCommand(CommandRunner(tmp_path))

    with pytest.raises(RuntimeError, match="simulated integration interruption"):
        run(request, runner=interrupted_runner)
    result = run(request, runner=CommandRunner(tmp_path), resume=True)

    assert interrupted_runner.calls == 2
    assert result.status == "succeeded"
    assert (tmp_path / "langgraph.sqlite").is_file()
