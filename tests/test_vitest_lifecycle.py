from midscene_ui_agent.platforms.vitest_e2e import VitestE2EAdapter

def test_vitest_init_creates_context_files(tmp_path):
    adapter=VitestE2EAdapter(); files=adapter.init(str(tmp_path),"web",ai_action_context="UI expert")
    assert (tmp_path/"vitest.config.ts").exists(); assert "UI expert" in (tmp_path/"midscene-context.ts").read_text(); assert files

def test_vitest_convert_is_idempotent(tmp_path):
    adapter=VitestE2EAdapter(); adapter.init(str(tmp_path),"android"); before=(tmp_path/"midscene-context.ts").read_text(); adapter.convert(str(tmp_path),"android"); assert (tmp_path/"midscene-context.ts").read_text()==before
