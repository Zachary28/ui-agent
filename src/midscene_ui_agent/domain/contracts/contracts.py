"""Public, platform-neutral request and result contracts."""
from __future__ import annotations

import re
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Platform = Literal["browser", "computer", "android", "ios", "harmony", "vitest_e2e"]
Operation = Literal["run", "connect", "health_check", "screenshot", "assert", "launch", "raw", "tap_locate", "list_displays", "report", "disconnect", "close", "debug", "convert", "create", "update", "init"]


class ReferenceImage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    source: str

    @model_validator(mode="after")
    def valid_source(self) -> "ReferenceImage":
        if not self.name.strip() or not self.source.strip():
            raise ValueError("reference image name and source are required")
        return self


class Target(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str | None = None
    browser_mode: Literal["puppeteer", "cdp", "bridge"] | None = None
    cdp: str | None = None
    bridge: bool = False
    extra_http_headers: list[str] = Field(default_factory=list)
    reference_images: list[ReferenceImage] = Field(default_factory=list)
    convert_http_image2_base64: bool = False
    device_id: str | None = None
    use_scrcpy: bool = False
    app_uri: str | None = None
    display_id: str | int | None = None
    wda_host: str | None = None
    wda_port: int | None = None
    session_id: str | None = None
    host: str | None = None
    username: str | None = None
    password_env: str | None = None
    rdp_port: int | None = None
    domain: str | None = None
    security_protocol: str | None = None
    admin_session: bool = False
    desktop_width: int | None = None
    desktop_height: int | None = None
    headless: bool = False
    ignore_certificate: bool = False
    project_dir: str | None = None
    vitest_platform: Literal["web", "android", "ios"] | None = None
    ai_action_context: dict[str, Any] = Field(default_factory=dict)

    @field_validator("extra_http_headers")
    @classmethod
    def headers_are_name_value(cls, values: list[str]) -> list[str]:
        if any(":" not in item or not item.split(":", 1)[0].strip() for item in values):
            raise ValueError("extra_http_headers must be Name:Value")
        return values


class AutomationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    platform: Platform
    target: Target
    goal: str = Field(min_length=1)
    acceptance: list[str] = Field(default_factory=list)
    operation: Operation = "run"
    mode: Literal["plan", "live"] = "plan"
    max_steps: int = Field(default=20, ge=1)
    max_retries: int = Field(default=2, ge=0)
    timeout_seconds: int = Field(default=300, ge=1)
    report_dir: str = "./artifacts"
    run_id: str | None = None
    variables: dict[str, Any] = Field(default_factory=dict)
    raw_command: str | None = None
    raw_method: str | None = None
    raw_endpoint: str | None = None
    locate: dict[str, Any] | None = None
    test_name: str | None = None
    case_name: str | None = None
    deep_think: bool = False
    deep_locate: bool = False
    install_dependencies: bool = False
    loop: "LoopPlan | None" = None

    @field_validator("run_id")
    @classmethod
    def safe_run_id(cls, value: str | None) -> str | None:
        if value is not None and not re.fullmatch(r"[A-Za-z0-9._-]+", value):
            raise ValueError("run_id contains unsafe characters")
        return value

    @model_validator(mode="after")
    def valid_for_platform(self) -> "AutomationRequest":
        t, op = self.target, self.operation
        if self.platform == "browser":
            modes = int(bool(t.cdp)) + int(t.bridge) + int(t.browser_mode == "puppeteer")
            if t.cdp and t.bridge:
                raise ValueError("cdp and bridge cannot be combined")
            if not t.url and not t.cdp and not t.bridge:
                raise ValueError("browser requires url, cdp, or bridge")
            if t.browser_mode in {"cdp", "bridge"} and not (t.cdp if t.browser_mode == "cdp" else t.bridge):
                raise ValueError("explicit browser mode requires its connection target")
            if op == "launch": raise ValueError("browser launch is unsupported")
        elif self.platform in {"android", "harmony"} and op in {"connect", "health_check", "run", "screenshot", "assert", "launch", "raw", "tap_locate", "disconnect"} and not t.device_id:
            raise ValueError("device_id is required")
        if self.platform == "vitest_e2e":
            if op not in {"run", "create", "update", "debug", "convert", "init"}: raise ValueError("unsupported Vitest operation")
            if not t.project_dir or not t.vitest_platform: raise ValueError("Vitest requires project_dir and vitest_platform")
            if op in {"update", "debug"} and not self.test_name: raise ValueError("test_name is required")
        elif op in {"debug", "convert", "create", "update", "init"}:
            raise ValueError("Vitest lifecycle operations are Vitest-only")
        if self.platform == "ios" and op == "connect" and not (t.wda_host and t.wda_port):
            raise ValueError("iOS connect requires wda_host and wda_port")
        if op == "raw":
            if self.platform in {"android", "harmony"} and not self.raw_command: raise ValueError("raw_command is required")
            if self.platform == "ios" and not (self.raw_method and self.raw_endpoint): raise ValueError("iOS raw requires method and endpoint")
        if op == "tap_locate" and not self.locate: raise ValueError("locate payload is required")
        if op == "launch" and self.platform in {"android", "ios", "harmony"} and not t.app_uri: raise ValueError("app_uri is required")
        return self


class Artifact(BaseModel):
    kind: Literal["screenshot", "report", "log", "plan", "result", "other"]
    path: str
    description: str | None = None


class StepResult(BaseModel):
    phase: str
    status: Literal["succeeded", "failed", "planned", "skipped"]
    message: str = ""
    artifacts: list[Artifact] = Field(default_factory=list)


class AutomationResult(BaseModel):
    run_id: str
    status: Literal["succeeded", "failed", "planned", "needs_confirmation", "cancelled"]
    steps: list[StepResult] = Field(default_factory=list)
    artifacts: list[Artifact] = Field(default_factory=list)
    error: str | None = None
    secondary_errors: list[str] = Field(default_factory=list)
    loop_summary: dict[str, Any] | None = None
    exit_reason: str | None = None


# Import after the request model is declared to avoid a circular import when
# callers import ``loop_contracts`` directly.  Pydantic then resolves the
# forward reference to the concrete LoopPlan type.
from .loop_contracts import LoopPlan

AutomationRequest.model_rebuild()

__all__ = [
    "Platform", "Operation", "ReferenceImage", "Target", "AutomationRequest",
    "Artifact", "StepResult", "AutomationResult",
]
