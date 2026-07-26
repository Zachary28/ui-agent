from midscene_ui_agent.adapters.registry import default_registry
from midscene_ui_agent.domain.contracts import AutomationRequest

def test_all_platforms_build_required_core_commands():
    registry=default_registry(); targets={"browser":{"url":"http://x"},"computer":{},"android":{"device_id":"a"},"ios":{"wda_host":"127.0.0.1","wda_port":8100},"harmony":{"device_id":"h"}}
    for platform,target in targets.items():
        adapter=registry[platform]
        for op in ("connect","health_check","screenshot","assert","tap_locate","report","disconnect"):
            payload={"prompt":"x"} if op=="tap_locate" else None
            req=AutomationRequest(platform=platform,target=target,goal="x",operation="tap_locate" if op=="tap_locate" else op,locate=payload)
            assert adapter.command(req).argv[0:3]==["npx","-y",adapter.package]

def test_health_check_is_a_screenshot_probe():
    req=AutomationRequest(platform="android",target={"device_id":"a"},goal="health",operation="health_check")
    assert default_registry()["android"].command(req).argv[3]=="take_screenshot"

def test_run_is_natural_language_act():
    req=AutomationRequest(platform="browser",target={"url":"http://x"},goal="click submit",operation="run")
    assert default_registry()["browser"].command(req).argv[3]=="act"

def test_launch_uri_is_not_forwarded_to_connect():
    req=AutomationRequest(platform="android",target={"device_id":"a","app_uri":"tv.danmaku.bili"},goal="launch",operation="connect")
    assert "--uri" not in default_registry()["android"].command(req).argv
