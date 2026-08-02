import json
from midscene_ui_agent.infrastructure.persistence.checkpoint import JsonCheckpoint
from midscene_ui_agent.infrastructure.persistence.checkpoint import DurableWorkflow

def test_json_checkpoint_roundtrip(tmp_path):
    saver=JsonCheckpoint(tmp_path/"checkpoint.json"); saver.put("r1", {"status":"paused"}); assert saver.get("r1")["status"]=="paused"

def test_workflow_retries_retryable_operation():
    calls=[]
    def operation():
        calls.append(1)
        if len(calls)<3: raise RuntimeError("retryable")
        return "ok"
    result=DurableWorkflow(max_retries=2).execute(operation)
    assert result=="ok" and len(calls)==3
