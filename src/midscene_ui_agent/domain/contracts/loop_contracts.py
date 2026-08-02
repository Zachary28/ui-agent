"""Validated, platform-neutral contracts for long-running automation loops."""

from __future__ import annotations

import json
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .runtime_types import ExitReason


OperationName = Literal[
    "dismiss_popup",
    "skip_ad",
    "play_video",
    "switch_episode",
    "scroll_feed",
    "check_playback",
    "recover_playback",
    "screenshot",
    "assert_state",
    "navigate_back",
    "report_snapshot",
]
Trigger = Literal["interval", "startup", "on_popup", "on_ad", "on_stall", "at_runtime", "after_operation"]


class LoopDefaults(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timeout_seconds: float = Field(default=30, gt=0)
    max_attempts: int = Field(default=3, ge=1)
    interval_seconds: float = Field(default=5, ge=0)
    min_operation_interval_seconds: float = Field(default=1, gt=0)
    evidence: bool = True


class OperationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    interval_seconds: float | None = Field(default=None, ge=0)
    timeout_seconds: float | None = Field(default=None, gt=0)
    max_attempts: int | None = Field(default=None, ge=1)
    priority: int = 0
    startup: bool = False
    on_popup: bool = False
    on_ad: bool = False
    on_stall: bool = False
    at_runtime: float | None = Field(default=None, ge=0)
    after_operation: list[OperationName] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)
    # Common operation-specific constraints. They are mirrored in params for
    # convenient YAML/API use, while remaining strongly typed when supplied.
    strategy: str | None = None
    target_count: int | None = Field(default=None, ge=1)
    scroll_limit: int | None = Field(default=None, ge=1)
    duration_seconds: float | None = Field(default=None, gt=0)
    prompt: str | None = None

    @field_validator("params")
    @classmethod
    def params_are_json_serializable(cls, value: dict[str, Any]) -> dict[str, Any]:
        try:
            json.dumps(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("params must be JSON-serializable") from exc
        return value


class ExitConditions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_runtime_seconds: float = Field(default=1800, gt=0)
    max_switches: int | None = Field(default=None, ge=1)
    max_scrolls: int | None = Field(default=None, ge=1)
    target_count: int | None = Field(default=None, ge=1)
    max_consecutive_failures: int = Field(default=3, ge=1)
    max_no_progress_ticks: int = Field(default=5, ge=1)
    stop_on_device_unreachable: bool = True
    stop_on_model_error: bool = True
    stop_on_login_required: bool = True
    stop_on_unhandled_popup: bool = True
    disconnect_on_exit: bool = True
    close_browser_on_exit: bool = False
    reasons: list[ExitReason] = Field(default_factory=list)


_UNSAFE_PROMPT_RE = re.compile(
    r"login|log\s*in|sign\s*up|register|phone|mobile|password|passcode|payment|pay\b|purchase|buy\b|membership|subscribe|\bsubmit\b|登录|註冊|注册|手机号|手机号码|密码|支付|付款|购买|購買|会员|會員|开通|開通|提交",
    re.IGNORECASE,
)


def _validate_safe_prompt(value: str) -> str:
    if _UNSAFE_PROMPT_RE.search(value):
        raise ValueError(
            "prompts must not instruct login, phone, password, payment, purchase, or membership submission"
        )
    return value


class LoopPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    defaults: LoopDefaults = Field(default_factory=LoopDefaults)
    operations: dict[OperationName, OperationConfig] = Field(default_factory=dict)
    exit_conditions: ExitConditions = Field(default_factory=ExitConditions)
    popup_prompts: list[str] = Field(default_factory=list)
    ad_prompts: list[str] = Field(default_factory=list)

    @field_validator("popup_prompts", "ad_prompts")
    @classmethod
    def prompts_are_safe(cls, values: list[str]) -> list[str]:
        for value in values:
            _validate_safe_prompt(value)
        return values

    @model_validator(mode="after")
    def validate_operations(self) -> "LoopPlan":
        minimum = self.defaults.min_operation_interval_seconds
        for name, config in self.operations.items():
            if config.interval_seconds is None:
                config.interval_seconds = self.defaults.interval_seconds
            if config.timeout_seconds is None:
                config.timeout_seconds = self.defaults.timeout_seconds
            if config.max_attempts is None:
                config.max_attempts = self.defaults.max_attempts
            if config.interval_seconds < minimum:
                raise ValueError(
                    f"operation {name} interval_seconds must be >= min_operation_interval_seconds ({minimum})"
                )

            if config.prompt is not None:
                _validate_safe_prompt(config.prompt)
            if name == "switch_episode" and config.enabled:
                strategy = config.strategy or config.params.get("strategy")
                target_count = (
                    config.target_count if config.target_count is not None else config.params.get("target_count")
                )
                if not strategy and not target_count:
                    raise ValueError("enabled switch_episode requires strategy or target_count")
                if target_count is not None and (not isinstance(target_count, int) or target_count <= 0):
                    raise ValueError("switch_episode target_count must be positive")
            if name == "scroll_feed" and config.enabled:
                limit = config.scroll_limit if config.scroll_limit is not None else config.params.get("scroll_limit")
                duration = (
                    config.duration_seconds
                    if config.duration_seconds is not None
                    else config.params.get("duration_seconds")
                )
                if (limit is None or limit <= 0) and (duration is None or duration <= 0):
                    raise ValueError("enabled scroll_feed requires a positive scroll_limit or duration_seconds")
        return self


class LoopRequest(BaseModel):
    """A request whose execution is explicitly governed by a loop plan."""

    model_config = ConfigDict(extra="forbid")

    platform: Literal["browser", "computer", "android", "ios", "harmony", "vitest_e2e"]
    target: Any
    goal: str = Field(min_length=1)
    loop: LoopPlan
    acceptance: list[str] = Field(default_factory=list)
    mode: Literal["plan", "live"] = "plan"


__all__ = [
    "OperationName",
    "Trigger",
    "ExitReason",
    "LoopDefaults",
    "OperationConfig",
    "ExitConditions",
    "LoopPlan",
    "LoopRequest",
]
