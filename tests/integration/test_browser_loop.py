import os
import shutil
import pytest

pytestmark = pytest.mark.integration

def test_browser_loop_public_fixture():
    if os.getenv("UI_AGENT_RUN_INTEGRATION") != "1":
        pytest.skip("set UI_AGENT_RUN_INTEGRATION=1 to enable browser integration")
    if not os.getenv("MIDSCENE_MODEL_API_KEY"):
        pytest.skip("MIDSCENE_MODEL_API_KEY is not configured")
    if not shutil.which("chrome") and not shutil.which("google-chrome"):
        pytest.skip("Chrome executable not found")
    assert True
