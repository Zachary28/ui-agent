import json


def test_manifest_contains_loop_summary_and_exit_reason(tmp_path):
    from midscene_ui_agent.domain.contracts import AutomationResult, AutomationRequest
    from midscene_ui_agent.infrastructure.reporting.reports import build_manifest
    request = AutomationRequest.model_validate({"platform": "android", "target": {"device_id": "fake"}, "goal": "watch"})
    result = AutomationResult(run_id="r1", status="succeeded", loop_summary={"ticks": 2}, exit_reason="max_runtime")
    path = build_manifest(result, request, tmp_path)
    data = json.loads(path.read_text())
    assert data["loop_summary"] == {"ticks": 2}
    assert data["exit_reason"] == "max_runtime"


def test_native_report_discovery_accepts_any_html(tmp_path):
    from midscene_ui_agent.infrastructure.reporting.reports import discover_native_report
    report = tmp_path / "midscene_run" / "report"
    report.mkdir(parents=True)
    (report / "native-result.html").write_text("<html></html>")
    assert discover_native_report(tmp_path).name == "native-result.html"
