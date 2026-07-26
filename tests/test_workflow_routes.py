from midscene_ui_agent.graph import WorkflowEngine

def test_workflow_pauses_before_connection_for_approval(tmp_path):
    calls=[]; engine=WorkflowEngine(checkpoint_path=tmp_path/'c.json')
    state=engine.run('r1', approval_required=True, connect=lambda: calls.append('connect'))
    assert state['status']=='needs_confirmation' and calls==[]

def test_workflow_resume_executes_and_checkpoints(tmp_path):
    calls=[]; engine=WorkflowEngine(checkpoint_path=tmp_path/'c.json')
    engine.run('r2', approval_required=True, connect=lambda: calls.append('connect'))
    state=engine.run('r2', approved=True, connect=lambda: calls.append('connect'))
    assert state['status']=='succeeded' and calls==['connect'] and engine.checkpoint.get('r2')['status']=='succeeded'

def test_workflow_cancellation_is_terminal(tmp_path):
    state=WorkflowEngine(checkpoint_path=tmp_path/'c.json').run('r3', cancelled=True)
    assert state['status']=='cancelled'
