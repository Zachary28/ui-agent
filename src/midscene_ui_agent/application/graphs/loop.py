"""Checkpointable Loop Engineering LangGraph subgraph."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from ...domain.contracts import ExitReason, LoopPlan
from ...domain.policies.exit import ExitPolicy
from ...domain.policies.resume import IDEMPOTENT_OPERATIONS, resume_action
from ...domain.policies.retry import RetryPolicy
from ...domain.runtime.graph import JsonObject, LoopGraphState
from ...domain.runtime.loop import RuntimeState
from ...infrastructure.persistence.langgraph import CheckpointerHandle
from ..loop.scheduler import scheduled_operations
from ..loop.selector import OperationSelector


@dataclass(frozen=True)
class LoopGraphServices:
    clock: Callable[[], float]
    wait: Callable[[float], None]
    observe: Callable[[LoopGraphState], Mapping[str, Any]]
    execute: Callable[[str, float, int, LoopGraphState], Mapping[str, Any]]
    verify_effect: Callable[[str, str, LoopGraphState], bool] | None = None
    record_evidence: Callable[[str, Mapping[str, Any], LoopGraphState], list[str]] | None = None


def _runtime_state(state: LoopGraphState, plan: LoopPlan) -> RuntimeState:
    return RuntimeState(
        max_no_progress_ticks=plan.exit_conditions.max_no_progress_ticks,
        current_tick=int(state.get("tick", 0)),
        elapsed_seconds=float(state.get("elapsed_seconds", 0)),
        popup_detected=bool(state.get("popup_detected", False)),
        ad_detected=bool(state.get("ad_detected", False)),
        stalled=bool(state.get("stalled", False)),
        no_progress_ticks=int(state.get("no_progress_ticks", 0)),
        consecutive_failures=int(state.get("consecutive_failures", 0)),
        operation_attempts=dict(state.get("operation_attempts", {})),
        operation_failures=dict(state.get("operation_failures", {})),
        last_progress_fingerprint=state.get("last_progress_fingerprint"),
        switch_count=int(state.get("switch_count", 0)),
        scroll_count=int(state.get("scroll_count", 0)),
        cancelled=bool(state.get("cancelled", False)),
    )


def build_loop_graph(
    *,
    services: LoopGraphServices,
    checkpointer: CheckpointerHandle | None = None,
    inherit_checkpointer: bool = False,
):
    if checkpointer is not None and inherit_checkpointer:
        raise ValueError("checkpointer and inherit_checkpointer cannot both be supplied")
    retry_policy = RetryPolicy()
    selector = OperationSelector()

    def initialize_loop(state: LoopGraphState) -> dict[str, Any]:
        plan = LoopPlan.model_validate(state["plan"])
        now = services.clock()
        enabled = [name for name, config in plan.operations.items() if config.enabled]
        return {
            "started_at": state.get("started_at", now),
            "tick": state.get("tick", 0),
            "enabled_operations": enabled,
            "next_due": {
                name: now + (plan.operations[name].interval_seconds or plan.defaults.interval_seconds)
                for name in enabled
            },
            "fired_triggers": list(state.get("fired_triggers", [])),
            "operation_attempts": dict(state.get("operation_attempts", {})),
            "operation_successes": dict(state.get("operation_successes", {})),
            "operation_failures": dict(state.get("operation_failures", {})),
            "operation_messages": dict(state.get("operation_messages", {})),
            "evidence_refs": list(state.get("evidence_refs", [])),
            "consecutive_failures": state.get("consecutive_failures", 0),
            "no_progress_ticks": state.get("no_progress_ticks", 0),
            "switch_count": state.get("switch_count", 0),
            "scroll_count": state.get("scroll_count", 0),
            "target_count": state.get("target_count", 0),
            "status": "running",
        }

    def observe_ui(state: LoopGraphState) -> dict[str, Any]:
        observation: JsonObject = dict(services.observe(state))
        message = str(observation.get("message", ""))
        lowered = message.lower()
        updates: dict[str, Any] = {
            "observation": observation,
            "popup_detected": bool(observation.get("popup_detected", "popup" in lowered)),
            "ad_detected": bool(observation.get("ad_detected", "advertisement" in lowered or " ad " in f" {lowered} ")),
            "stalled": bool(observation.get("stalled", False)),
            "login_required": bool(observation.get("login_required", "login required" in lowered)),
            "purchase_required": bool(observation.get("purchase_required", "purchase required" in lowered)),
            "device_unreachable": not bool(observation.get("reachable", True)),
            "model_error": bool(observation.get("model_error", False)),
            "cancelled": bool(observation.get("cancelled", state.get("cancelled", False))),
        }
        fingerprint = observation.get("fingerprint")
        if fingerprint:
            previous = state.get("last_progress_fingerprint")
            updates["no_progress_ticks"] = int(state.get("no_progress_ticks", 0)) + 1 if previous == fingerprint else 0
            updates["last_progress_fingerprint"] = str(fingerprint)
        return updates

    def schedule_operations(state: LoopGraphState) -> dict[str, Any]:
        plan = LoopPlan.model_validate(state["plan"])
        due, updates = scheduled_operations(plan, dict(state), now=services.clock())
        preview = _runtime_state({**state, **updates}, plan)
        decision = ExitPolicy().evaluate(
            preview,
            max_runtime_seconds=plan.exit_conditions.max_runtime_seconds,
            max_switches=plan.exit_conditions.max_switches,
            max_scrolls=plan.exit_conditions.max_scrolls,
            target_count=plan.exit_conditions.target_count,
            max_consecutive_failures=plan.exit_conditions.max_consecutive_failures,
        )
        if decision.should_exit:
            return {**updates, "due_operations": [], "exit_reason": decision.reason}
        return {**updates, "due_operations": due}

    def select_operation(state: LoopGraphState) -> dict[str, Any]:
        plan = LoopPlan.model_validate(state["plan"])
        runtime = _runtime_state(state, plan)
        priorities = {name: config.priority for name, config in plan.operations.items()}
        selected = selector.choose(list(state.get("due_operations", [])), runtime, priorities)
        return {
            "selected_operation": selected,
            "operation_id": f"tick-{int(state.get('tick', 0)) + 1}:{selected}" if selected else None,
            "selected_attempt": 0 if selected else state.get("selected_attempt", 0),
        }

    def execute_operation(state: LoopGraphState) -> dict[str, Any]:
        plan = LoopPlan.model_validate(state["plan"])
        operation = state["selected_operation"]
        config = plan.operations[operation]
        attempt = int(state.get("selected_attempt", 0)) + 1
        timeout = float(config.timeout_seconds or plan.defaults.timeout_seconds)
        effect_verified = False
        operation_id = str(state.get("operation_id", ""))
        if services.verify_effect is not None and operation not in IDEMPOTENT_OPERATIONS:
            effect_verified = services.verify_effect(operation, operation_id, state)
        if resume_action(operation, effect_verified) == "complete":
            outcome: JsonObject = {
                "succeeded": True,
                "message": "effect already verified",
                "metadata": {"effect_verified": True},
            }
        else:
            outcome = dict(services.execute(operation, timeout, attempt, state))
        attempts = dict(state.get("operation_attempts", {}))
        attempts[operation] = attempts.get(operation, 0) + 1
        messages = dict(state.get("operation_messages", {}))
        messages[operation] = str(outcome.get("message", ""))
        return {
            "last_outcome": outcome,
            "last_operation": operation,
            "selected_attempt": attempt,
            "operation_attempts": attempts,
            "operation_messages": messages,
        }

    def record_evidence(state: LoopGraphState) -> dict[str, Any]:
        if services.record_evidence is None or not state.get("selected_operation"):
            return {}
        refs = services.record_evidence(state["selected_operation"], state.get("last_outcome", {}), state)
        return {"evidence_refs": [*state.get("evidence_refs", []), *refs]}

    def evaluate_exit(state: LoopGraphState) -> dict[str, Any]:
        plan = LoopPlan.model_validate(state["plan"])
        operation = state.get("selected_operation")
        outcome = state.get("last_outcome", {}) if operation else {}
        updates: dict[str, Any] = {"elapsed_seconds": max(0.0, services.clock() - float(state["started_at"]))}
        reason = retry_policy.exit_reason(str(outcome.get("reason", ""))) if outcome else None
        if reason is None:
            if state.get("login_required"):
                reason = ExitReason.LOGIN_REQUIRED
            elif state.get("purchase_required"):
                reason = ExitReason.PURCHASE_REQUIRED
            elif (
                state.get("popup_detected")
                and plan.exit_conditions.stop_on_unhandled_popup
                and not any(
                    config.enabled and (name == "dismiss_popup" or config.on_popup)
                    for name, config in plan.operations.items()
                )
            ):
                reason = ExitReason.UNHANDLED_POPUP
            elif state.get("device_unreachable") and plan.exit_conditions.stop_on_device_unreachable:
                reason = ExitReason.DEVICE_UNREACHABLE
            elif state.get("model_error") and plan.exit_conditions.stop_on_model_error:
                reason = ExitReason.MODEL_ERROR
        if reason is not None:
            updates["exit_reason"] = reason
            return updates

        if operation and outcome:
            config = plan.operations[operation]
            succeeded = bool(outcome.get("succeeded", False))
            attempt = int(state.get("selected_attempt", 0))
            if not succeeded and retry_policy.should_retry(
                attempt=attempt,
                max_attempts=int(config.max_attempts or plan.defaults.max_attempts),
                reason=str(outcome.get("reason", "")),
            ):
                updates["retry_pending"] = True
                return updates
            updates["retry_pending"] = False
            successes = dict(state.get("operation_successes", {}))
            failures = dict(state.get("operation_failures", {}))
            if succeeded:
                successes[operation] = successes.get(operation, 0) + 1
                updates["consecutive_failures"] = 0
                updates["switch_count"] = int(state.get("switch_count", 0)) + int(operation == "switch_episode")
                updates["scroll_count"] = int(state.get("scroll_count", 0)) + int(operation == "scroll_feed")
                updates["target_count"] = int(state.get("target_count", 0)) + int(operation in {"switch_episode", "scroll_feed"})
            else:
                failures[operation] = failures.get(operation, 0) + 1
                updates["consecutive_failures"] = int(state.get("consecutive_failures", 0)) + 1
            updates["operation_successes"] = successes
            updates["operation_failures"] = failures
            updates["tick"] = int(state.get("tick", 0)) + 1
            updates["selected_operation"] = None
            updates["selected_attempt"] = 0
            next_due = dict(state.get("next_due", {}))
            next_due[operation] = services.clock() + float(config.interval_seconds or plan.defaults.interval_seconds)
            updates["next_due"] = next_due

        runtime = _runtime_state({**state, **updates}, plan)
        decision = ExitPolicy().evaluate(
            runtime,
            max_runtime_seconds=plan.exit_conditions.max_runtime_seconds,
            max_switches=plan.exit_conditions.max_switches,
            max_scrolls=plan.exit_conditions.max_scrolls,
            target_count=plan.exit_conditions.target_count,
            max_consecutive_failures=plan.exit_conditions.max_consecutive_failures,
        )
        if decision.should_exit:
            updates["exit_reason"] = decision.reason
        else:
            services.wait(plan.defaults.min_operation_interval_seconds)
        return updates

    def summarize_loop(state: LoopGraphState) -> dict[str, Any]:
        operations = {
            name: {
                "attempts": state.get("operation_attempts", {}).get(name, 0),
                "successes": state.get("operation_successes", {}).get(name, 0),
                "failures": state.get("operation_failures", {}).get(name, 0),
            }
            for name in state.get("enabled_operations", [])
        }
        failure_reasons = {
            ExitReason.MAX_FAILURES,
            ExitReason.NO_PROGRESS,
            ExitReason.DEVICE_UNREACHABLE,
            ExitReason.MODEL_ERROR,
            ExitReason.LOGIN_REQUIRED,
            ExitReason.PURCHASE_REQUIRED,
            ExitReason.UNHANDLED_POPUP,
        }
        exit_reason = state.get("exit_reason")
        status = "cancelled" if exit_reason == ExitReason.CANCELLED else "failed" if exit_reason in failure_reasons else "succeeded"
        return {
            "status": status,
            "loop_summary": {
                "ticks": state.get("tick", 0),
                "elapsed_seconds": state.get("elapsed_seconds", 0),
                "operations": operations,
            },
        }

    def route_after_select(state: LoopGraphState) -> Literal["execute", "evaluate"]:
        return "execute" if state.get("selected_operation") else "evaluate"

    def route_after_evaluation(state: LoopGraphState) -> Literal["continue", "retry", "exit"]:
        if state.get("exit_reason"):
            return "exit"
        if state.get("retry_pending"):
            return "retry"
        return "continue"

    builder = StateGraph(LoopGraphState)
    builder.add_node("initialize_loop", initialize_loop)
    builder.add_node("observe_ui", observe_ui)
    builder.add_node("schedule_operations", schedule_operations)
    builder.add_node("select_operation", select_operation)
    builder.add_node("execute_operation", execute_operation)
    builder.add_node("record_evidence", record_evidence)
    builder.add_node("evaluate_exit", evaluate_exit)
    builder.add_node("summarize_loop", summarize_loop)
    builder.add_edge(START, "initialize_loop")
    builder.add_edge("initialize_loop", "observe_ui")
    builder.add_edge("observe_ui", "schedule_operations")
    builder.add_edge("schedule_operations", "select_operation")
    builder.add_conditional_edges("select_operation", route_after_select, {"execute": "execute_operation", "evaluate": "evaluate_exit"})
    builder.add_edge("execute_operation", "record_evidence")
    builder.add_edge("record_evidence", "evaluate_exit")
    builder.add_conditional_edges(
        "evaluate_exit",
        route_after_evaluation,
        {"continue": "observe_ui", "retry": "execute_operation", "exit": "summarize_loop"},
    )
    builder.add_edge("summarize_loop", END)
    saver = True if inherit_checkpointer else checkpointer.saver if checkpointer is not None else None
    return builder.compile(checkpointer=saver)


__all__ = ["LoopGraphServices", "build_loop_graph"]
