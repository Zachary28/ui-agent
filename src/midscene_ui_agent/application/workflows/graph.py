from .planner import PhasePlanner
from ...domain.runtime.state import RunState
from ...infrastructure.persistence.checkpoint import DurableWorkflow
from pathlib import Path
from ...infrastructure.persistence.checkpoint import JsonCheckpoint

def runtime_checkpointer(path):
    """Prefer official LangGraph SqliteSaver, with stdlib fallback for lean installs."""
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver
        return SqliteSaver.from_conn_string(str(path))
    except (ImportError, AttributeError):
        from ...infrastructure.persistence.checkpoint import SqliteCheckpoint
        return SqliteCheckpoint(path)

class WorkflowEngine:
    """Serializable lifecycle router used by API and as a LangGraph-compatible node core."""
    def __init__(self, checkpoint_path="artifacts/checkpoints.json"):
        self.checkpoint=JsonCheckpoint(Path(checkpoint_path))
    def run(self, run_id, *, approval_required=False, approved=False, cancelled=False, connect=None):
        if cancelled:
            state={"run_id":run_id,"status":"cancelled"}; self.checkpoint.put(run_id,state); return state
        if approval_required and not approved:
            state={"run_id":run_id,"status":"needs_confirmation","interrupt_reason":"approval"}; self.checkpoint.put(run_id,state); return state
        if approved:
            previous=self.checkpoint.get(run_id)
            if not previous or previous.get("status")!="needs_confirmation":
                state={"run_id":run_id,"status":"resume_invalid"}; self.checkpoint.put(run_id,state); return state
        if connect: connect()
        state={"run_id":run_id,"status":"succeeded"}; self.checkpoint.put(run_id,state); return state
class AgentGraph:
    """Small dependency-light graph facade; LangGraph is used when available by callers."""
    def __init__(self, context): self.context=context
    def invoke(self, state: RunState) -> RunState:
        state.setdefault("phases", PhasePlanner().plan(state["request"]["goal"], state["request"].get("max_steps",20)))
        state.setdefault("steps", []); state.setdefault("artifacts", []); state["status"]="planned"
        return state
def build_graph(context): return AgentGraph(context)

def build_langgraph(context):
    """Compile the same deterministic lifecycle with LangGraph when installed."""
    try:
        from langgraph.graph import StateGraph, START, END
    except ImportError:
        return AgentGraph(context)
    def plan(state):
        state.setdefault("phases", PhasePlanner().plan(state["request"]["goal"], state["request"].get("max_steps",20)))
        state["status"] = "planned"; return state
    graph=StateGraph(RunState); graph.add_node("plan", plan); graph.add_edge(START,"plan"); graph.add_edge("plan",END)
    return graph.compile()
