import json
from midscene_ui_agent.contracts import AutomationRequest
from midscene_ui_agent.api import run

def test_plan_run_writes_events_jsonl(tmp_path):
    q=AutomationRequest(platform="browser",target={"url":"http://x"},goal="inspect",report_dir=str(tmp_path))
    result=run(q); events=tmp_path/result.run_id/"events.jsonl"
    assert events.exists(); rows=[json.loads(x) for x in events.read_text().splitlines()]; assert rows and rows[0]["kind"]=="plan"
