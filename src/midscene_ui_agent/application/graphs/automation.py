"""Top-level durable automation graph."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from langgraph.graph import END, START, StateGraph

from ...domain.runtime.graph import AutomationGraphState
from ...infrastructure.persistence.langgraph import CheckpointerHandle
from ..nodes.lifecycle import execute_route, finalize_run, prepare_run

GraphNode = Callable[[AutomationGraphState], Mapping[str, Any]]


def build_automation_graph(
    *,
    services: Mapping[str, GraphNode] | None = None,
    checkpointer: CheckpointerHandle,
):
    nodes: dict[str, GraphNode] = {
        "prepare": prepare_run,
        "execute": execute_route,
        "finalize": finalize_run,
    }
    if services:
        unknown = set(services) - set(nodes)
        if unknown:
            raise ValueError(f"unknown automation graph services: {sorted(unknown)}")
        nodes.update(services)

    builder = StateGraph(AutomationGraphState)
    builder.add_node("prepare_run", nodes["prepare"])
    builder.add_node("execute_route", nodes["execute"])
    builder.add_node("finalize_run", nodes["finalize"])
    builder.add_edge(START, "prepare_run")
    builder.add_edge("prepare_run", "execute_route")
    builder.add_edge("execute_route", "finalize_run")
    builder.add_edge("finalize_run", END)
    return builder.compile(checkpointer=checkpointer.saver)


__all__ = ["build_automation_graph"]
