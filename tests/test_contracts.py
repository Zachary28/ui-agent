from midscene_ui_agent import __version__
import pytest
from pydantic import ValidationError
from midscene_ui_agent.domain.contracts import AutomationRequest


def test_package_version_is_stable() -> None:
    assert __version__ == "0.1.0"


def test_request_accepts_every_first_release_platform() -> None:
    targets = {
        "browser": {"url": "http://127.0.0.1:4173"},
        "computer": {},
        "android": {"device_id": "emulator-5554"},
        "ios": {},
        "harmony": {"device_id": "0123456789ABCDEF"},
        "vitest_e2e": {"project_dir": "tests/fixture", "vitest_platform": "web"},
    }
    for platform, target in targets.items():
        assert AutomationRequest(platform=platform, target=target, goal="verify").platform == platform


def test_connection_and_direct_operation_validation() -> None:
    with pytest.raises(ValidationError):
        AutomationRequest(platform="browser", target={}, goal="open")
    with pytest.raises(ValidationError):
        AutomationRequest(platform="browser", target={"url": "x", "cdp": "ws://x", "bridge": True}, goal="x")
    with pytest.raises(ValidationError):
        AutomationRequest(platform="android", target={"device_id": "emulator"}, goal="raw", operation="raw")
    with pytest.raises(ValidationError):
        AutomationRequest(platform="vitest_e2e", target={"project_dir": "x"}, goal="create", operation="create")


def test_safety_and_evidence_contract_fields():
    request = AutomationRequest(platform="browser", target={"url": "http://x"}, goal="verify", acceptance=["success"])
    assert request.acceptance == ["success"]
    assert request.target.ai_action_context == {}


def test_ios_explicit_wda_requires_endpoint():
    with pytest.raises(ValidationError):
        AutomationRequest(platform="ios", target={}, goal="inspect", operation="connect")
