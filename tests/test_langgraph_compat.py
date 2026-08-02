from midscene_ui_agent.infrastructure.persistence.langgraph import sqlite_checkpointer

def test_runtime_checkpointer_is_official_sqlite_saver(tmp_path):
    handle = sqlite_checkpointer(tmp_path / "c.sqlite")
    try:
        assert handle.saver.__class__.__name__ == "SqliteSaver"
    finally:
        handle.close()
