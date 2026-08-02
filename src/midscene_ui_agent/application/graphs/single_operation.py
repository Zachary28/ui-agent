"""Checkpointable deterministic single-operation workflow."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from ...domain.runtime.graph import AutomationGraphState, JsonObject
from ...infrastructure.persistence.langgraph import CheckpointerHandle

StepExecutor = Callable[[AutomationGraphState, str], Mapping[str, Any]]


def operation_steps(operation: str) -> list[str]:
    if operation == "run":
        return ["connect", "health_check", "run", "screenshot"]
    if operation in {"screenshot", "assert", "launch", "tap_locate"}:
        return ["connect", operation]
    return [operation]


def build_single_operation_graph(
    *,
    executor: StepExecutor,
    checkpointer: CheckpointerHandle | None = None,
):
    def prepare(state: AutomationGraphState) -> dict[str, Any]:
        request = state.get("request", {})
        operation = str(request.get("operation", "run"))
        resume = state.get("resume", False)
        return {
            "operation_steps": operation_steps(operation),
            "step_index": state.get("step_index", 0) if resume else 0,
            "steps": list(state.get("steps", [])) if resume else [],
            "error": state.get("error") if resume else None,
            "phase": "prepare_operation",
            "status": "running",
        }

    def execute_step(state: AutomationGraphState) -> dict[str, Any]:
        index = state.get("step_index", 0)
        operation = state["operation_steps"][index]
        step: JsonObject = dict(executor(state, operation))
        status = str(step.get("status", "failed"))
        updates: dict[str, Any] = {
            "steps": [*state.get("steps", []), step],
            "step_index": index + 1,
            "phase": operation,
        }
        if status != "succeeded":
            updates["status"] = "failed"
            updates["error"] = str(step.get("message") or "operation failed")
        return updates

    def finish(state: AutomationGraphState) -> dict[str, Any]:
        return {
            "phase": "single_operation_complete",
            "status": "failed" if state.get("error") else "succeeded",
        }

    def route(state: AutomationGraphState) -> Literal["execute", "finish"]:
        if state.get("error"):
            return "finish"
        if state.get("step_index", 0) >= len(state.get("operation_steps", [])):
            return "finish"
        return "execute"

    builder = StateGraph(AutomationGraphState)
    builder.add_node("prepare_operation", prepare)
    builder.add_node("execute_step", execute_step)
    builder.add_node("finish_operation", finish)
    builder.add_edge(START, "prepare_operation")
    builder.add_conditional_edges(
        "prepare_operation", route, {"execute": "execute_step", "finish": "finish_operation"}
    )
    builder.add_conditional_edges(
        "execute_step", route, {"execute": "execute_step", "finish": "finish_operation"}
    )
    builder.add_edge("finish_operation", END)
    saver = checkpointer.saver if checkpointer is not None else None
    return builder.compile(checkpointer=saver)


__all__ = ["StepExecutor", "operation_steps", "build_single_operation_graph"]
