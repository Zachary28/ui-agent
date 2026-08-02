"""Default lifecycle nodes used by the automation graph skeleton."""
from __future__ import annotations

from ...domain.runtime.graph import AutomationGraphState


def prepare_run(state: AutomationGraphState) -> dict[str, str]:
    return {"phase": "prepare_run", "status": state.get("status", "running")}


def execute_route(state: AutomationGraphState) -> dict[str, str]:
    return {"phase": "execute_route", "status": state.get("status", "running")}


def finalize_run(state: AutomationGraphState) -> dict[str, str]:
    status = state.get("status")
    return {
        "phase": "finalize_run",
        "status": "succeeded" if status in {None, "running"} else status,
    }


__all__ = ["prepare_run", "execute_route", "finalize_run"]
