from midscene_ui_agent.infrastructure.persistence.checkpoint import SqliteCheckpoint


def test_sqlite_checkpoint_roundtrip(tmp_path):
    saver = SqliteCheckpoint(tmp_path / "c.sqlite")
    saver.put("x", {"status": "paused"})
    assert saver.get("x")["status"] == "paused"
    saver.close()
