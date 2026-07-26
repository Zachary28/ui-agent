import os
import shutil
import subprocess
import pytest

pytestmark = pytest.mark.integration

def test_android_loop_public_fixture():
    if os.getenv("UI_AGENT_RUN_INTEGRATION") != "1":
        pytest.skip("set UI_AGENT_RUN_INTEGRATION=1 to enable Android integration")
    if not os.getenv("MIDSCENE_MODEL_API_KEY"):
        pytest.skip("MIDSCENE_MODEL_API_KEY is not configured")
    adb = shutil.which("adb")
    if not adb:
        pytest.skip("adb executable not found")
    devices = subprocess.run([adb, "devices"], capture_output=True, text=True, check=False).stdout
    if "AGYJUT3628001141\tdevice" not in devices:
        pytest.skip("AGYJUT3628001141 is not connected")
    assert True
