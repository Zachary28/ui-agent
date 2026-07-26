from pathlib import Path
from midscene_ui_agent.domain.contracts import AutomationRequest
from midscene_ui_agent.interfaces.api import run
from midscene_ui_agent.adapters.vitest_e2e import VitestE2EAdapter
from midscene_ui_agent.infrastructure.reporting.reports import discover_native_report

def test_plan_writes_manifest_and_result(tmp_path):
    result=run(AutomationRequest(platform="browser",target={"url":"http://example.test"},goal="inspect",report_dir=str(tmp_path)))
    assert result.status=="planned"; assert (tmp_path/result.run_id/"manifest.json").exists()

def test_vitest_marker_create_and_update(tmp_path):
    adapter=VitestE2EAdapter(); path=adapter.create(str(tmp_path),"login","verify login")
    assert "aiAct" in path.read_text(); adapter.update_case(str(tmp_path),"login","verify success"); assert "verify success" in path.read_text()

def test_live_commands_use_isolated_work_directory(tmp_path):
    class FakeRunner:
        def __init__(self): self.specs=[]
        def run(self,spec,**kwargs):
            self.specs.append(spec)
            from midscene_ui_agent.infrastructure.execution.runner import CommandResult
            return CommandResult(spec.argv,0,"","" )
    fake=FakeRunner(); q=AutomationRequest(platform="android",target={"device_id":"x"},goal="screenshot",operation="screenshot",mode="live",report_dir=str(tmp_path))
    run(q,runner=fake)
    assert fake.specs[0].cwd.endswith("\\work") or fake.specs[0].cwd.endswith("/work")

def test_discover_native_report_is_run_scoped(tmp_path):
    report=tmp_path/"midscene_run"/"report"/"one"; report.mkdir(parents=True); (report/"index.html").write_text("<html>")
    assert discover_native_report(tmp_path)==report/"index.html"

def test_ui_operations_connect_before_action(tmp_path):
    class FakeRunner:
        def __init__(self): self.ops=[]
        def run(self,spec,**kwargs):
            self.ops.append(spec.argv[3]); from midscene_ui_agent.infrastructure.execution.runner import CommandResult; return CommandResult(spec.argv,0,"","")
    fake=FakeRunner(); q=AutomationRequest(platform="browser",target={"url":"http://x"},goal="inspect",operation="screenshot",mode="live",report_dir=str(tmp_path))
    run(q,runner=fake); assert fake.ops==["connect","take_screenshot"]

def test_api_loads_model_environment_without_overriding(monkeypatch, tmp_path):
    env=tmp_path/".env"; env.write_text("MIDSCENE_MODEL_NAME=test-model\n",encoding="utf-8")
    monkeypatch.chdir(tmp_path); monkeypatch.delenv("MIDSCENE_MODEL_NAME",raising=False)
    from midscene_ui_agent.interfaces.api import _load_environment
    _load_environment(); assert __import__('os').environ["MIDSCENE_MODEL_NAME"]=="test-model"
