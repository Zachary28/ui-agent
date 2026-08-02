from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class OperationOutcome:
    succeeded: bool
    message: str = ""
    reason: str | None = None
    artifacts: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class _PromptHandler:
    def __init__(self, adapter, evidence=None, context=None):
        self.adapter = adapter
        self.evidence = evidence
        self.context = context

    def _run(self, prompt: str, *, reason: str | None = None) -> OperationOutcome:
        if self.evidence:
            self.evidence.capture_before(prompt)
        try:
            if self.context is None:
                response = self.adapter.execute_prompt(prompt)
            else:
                response = self.adapter.execute_prompt(prompt, self.context)
        except Exception as exc:
            return OperationOutcome(False, str(exc), "COMMAND_FAILED")
        if self.evidence:
            self.evidence.capture_after(prompt)
        text = getattr(response, "message", None) or str(response)
        succeeded = getattr(response, "succeeded", True)
        if not succeeded:
            return OperationOutcome(False, text, getattr(response, "reason", None) or "COMMAND_FAILED")
        lowered = text.lower()
        if any(marker in lowered for marker in ("login required", "please login", "登录", "sign in")):
            return OperationOutcome(False, text, "LOGIN_REQUIRED")
        if any(marker in lowered for marker in ("purchase required", "buy membership", "购买", "付费")):
            return OperationOutcome(False, text, "PURCHASE_REQUIRED")
        return OperationOutcome(True, text, reason)


class PopupHandler(_PromptHandler):
    def handle(self, prompt: str) -> OperationOutcome:
        return self._run(prompt, reason="POPUP_DISMISSED")


class AdHandler(_PromptHandler):
    def skip(self, prompt: str = "Skip the advertisement if a skip or close control is visible") -> OperationOutcome:
        return self._run(prompt, reason="AD_SKIPPED")


class PlaybackController(_PromptHandler):
    def play(self, prompt: str = "Start or resume the video, without logging in or purchasing") -> OperationOutcome:
        return self._run(prompt, reason="PLAYING")

    def check(self, prompt: str = "Check whether the video is playing and its progress has advanced") -> OperationOutcome:
        return self._run(prompt)

    def recover(self, prompt: str = "Recover playback using pause/resume or reload; do not log in or purchase") -> OperationOutcome:
        return self._run(prompt, reason="PLAYBACK_RECOVERED")


class EpisodeSwitcher(_PromptHandler):
    def switch(self, *, strategy: str = "next_episode", require_free: bool = False, category: str | None = None) -> OperationOutcome:
        free = " only select an item marked free or limited-free" if require_free else ""
        category_text = f" in category {category!r}" if category else ""
        selected = self._run(f"Select {strategy}{category_text}{free}")
        if not selected.succeeded:
            return selected
        return self._run("Verify the new video starts playing", reason="EPISODE_SWITCHED")


class FeedScroller(_PromptHandler):
    def scroll_once(self) -> OperationOutcome:
        moved = self._run("Swipe up exactly once to show the next short video")
        if not moved.succeeded:
            return moved
        return self._run("Capture a screenshot and verify the visible video marker changed", reason="FEED_SCROLLED")


class GenericOperationHandler(_PromptHandler):
    def execute(self, operation: str, prompt: str) -> OperationOutcome:
        return self._run(prompt, reason=operation.upper())


__all__ = ["OperationOutcome", "PopupHandler", "AdHandler", "PlaybackController", "EpisodeSwitcher", "FeedScroller", "GenericOperationHandler"]
