"""Compatibility wrapper that executes Loop plans through the LangGraph subgraph."""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Any

from ...domain.contracts import AutomationRequest, ExitReason, LoopPlan
from ...infrastructure.execution.runner import CommandRunner
from ...platforms.base import ExecutionContext
from ..graphs.loop import LoopGraphServices, build_loop_graph
from ..services.handlers import (
    AdHandler,
    EpisodeSwitcher,
    FeedScroller,
    GenericOperationHandler,
    PlaybackController,
    PopupHandler,
)


@dataclass(frozen=True)
class LoopResult:
    status: str
    exit_reason: ExitReason | None
    loop_summary: dict[str, Any]
    state: dict[str, Any]


class LoopWorkflow:
    def __init__(
        self,
        adapter,
        *,
        request: AutomationRequest | None = None,
        runner=None,
        run_id: str = "loop",
        clock=None,
        checkpointer=None,
    ):
        self.adapter = adapter
        self.request = request
        self.runner = runner or CommandRunner()
        self.run_id = run_id
        self.clock = clock or time
        self.checkpointer = checkpointer
        self.cancel_event = Event()
        self._artifact_root = Path(".")

    def cancel(self) -> None:
        self.cancel_event.set()

    def run(self, plan: LoopPlan, *, artifact_root: str | Path) -> LoopResult:
        graph = self.build_graph(artifact_root=artifact_root)
        minimum = plan.defaults.min_operation_interval_seconds
        recursion_limit = max(1000, int(plan.exit_conditions.max_runtime_seconds / minimum) * 8 + 100)
        config: dict[str, Any] = {"recursion_limit": recursion_limit}
        if self.checkpointer is not None:
            config["configurable"] = {"thread_id": self.run_id}
        state = graph.invoke(
            {
                "run_id": self.run_id,
                "plan": plan.model_dump(mode="json"),
                "cancelled": self.cancel_event.is_set(),
            },
            config,
        )
        return self.result_from_state(state)

    def build_graph(self, *, artifact_root: str | Path, inherit_checkpointer: bool = False):
        self._artifact_root = Path(artifact_root)
        self._artifact_root.mkdir(parents=True, exist_ok=True)
        return build_loop_graph(
            services=LoopGraphServices(
                clock=self._now,
                wait=self._wait,
                observe=self._observe,
                execute=self._execute,
                verify_effect=self._verify_effect,
            ),
            checkpointer=self.checkpointer,
            inherit_checkpointer=inherit_checkpointer,
        )

    @staticmethod
    def result_from_state(state: dict[str, Any]) -> LoopResult:
        return LoopResult(
            status=str(state.get("status", "failed")),
            exit_reason=state.get("exit_reason"),
            loop_summary=dict(state.get("loop_summary", {})),
            state=dict(state),
        )

    def _now(self) -> float:
        return self.clock.monotonic() if hasattr(self.clock, "monotonic") else self.clock()

    def _wait(self, seconds: float) -> None:
        if hasattr(self.clock, "advance"):
            self.clock.advance(seconds)
        else:
            self.cancel_event.wait(seconds)

    def _context(self, operation: str, timeout: float) -> ExecutionContext:
        if self.request is None:
            raise RuntimeError("platform execution context requires an automation request")
        return ExecutionContext(
            request=self.request,
            runner=self.runner,
            run_id=self.run_id,
            event_id=f"loop:{operation}",
            cwd=self._artifact_root,
            timeout_seconds=timeout,
        )

    def _observe(self, state) -> dict[str, Any]:
        if self.cancel_event.is_set():
            return {"cancelled": True}
        if self.request is None or not hasattr(self.adapter, "observe"):
            return {}
        observation = self.adapter.observe(self._context("observe", self.request.timeout_seconds))
        return {
            "reachable": observation.reachable,
            "fingerprint": observation.fingerprint,
            "message": observation.message,
        }

    def _execute(self, operation: str, timeout: float, attempt: int, state) -> dict[str, Any]:
        del attempt
        context = self._context(operation, timeout) if self.request is not None else None
        plan = LoopPlan.model_validate(state["plan"])
        if operation == "dismiss_popup":
            prompt = plan.popup_prompts[0] if plan and plan.popup_prompts else "Close the ordinary popup"
            outcome = PopupHandler(self.adapter, context=context).handle(prompt)
        elif operation == "skip_ad":
            prompt = plan.ad_prompts[0] if plan and plan.ad_prompts else "Skip or close the advertisement"
            outcome = AdHandler(self.adapter, context=context).skip(prompt)
        elif operation == "play_video":
            outcome = PlaybackController(self.adapter, context=context).play()
        elif operation == "check_playback":
            outcome = PlaybackController(self.adapter, context=context).check()
        elif operation == "recover_playback":
            outcome = PlaybackController(self.adapter, context=context).recover()
        elif operation == "switch_episode":
            config = plan.operations[operation] if plan else None
            params = config.params if config else {}
            outcome = EpisodeSwitcher(self.adapter, context=context).switch(
                strategy=(config.strategy if config else None) or params.get("strategy", "next_episode"),
                require_free=bool(params.get("require_free", False)),
                category=params.get("category"),
            )
        elif operation == "scroll_feed":
            outcome = FeedScroller(self.adapter, context=context).scroll_once()
        else:
            outcome = GenericOperationHandler(self.adapter, context=context).execute(
                operation,
                f"Execute safe UI operation {operation}",
            )
        return {
            "succeeded": outcome.succeeded,
            "message": outcome.message,
            "reason": outcome.reason,
            "artifacts": outcome.artifacts,
            "metadata": outcome.metadata,
        }

    def _verify_effect(self, operation: str, operation_id: str, state) -> bool:
        del state
        if self.request is None or not hasattr(self.adapter, "verify_effect"):
            return False
        config = self.request.loop.operations.get(operation) if self.request.loop else None
        timeout = config.timeout_seconds if config and config.timeout_seconds else self.request.timeout_seconds
        return bool(self.adapter.verify_effect(operation, operation_id, self._context(operation, timeout)))


__all__ = ["LoopResult", "LoopWorkflow"]
