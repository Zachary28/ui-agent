from midscene_ui_agent.graph import runtime_checkpointer
from midscene_ui_agent.checkpoint import SqliteCheckpoint

def test_runtime_checkpointer_has_durable_fallback(tmp_path):
    saver=runtime_checkpointer(tmp_path/"c.sqlite")
    assert saver is not None
    if isinstance(saver,SqliteCheckpoint): saver.close()
