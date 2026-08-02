"""Stable contracts exchanged by future test-script generators."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .contracts import Operation, Platform


class TestStepSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    action: Operation
    prompt: str = Field(min_length=1)
    target_overrides: dict[str, Any] = Field(default_factory=dict)
    acceptance: list[str] = Field(default_factory=list)


class TestCaseSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    platform: Platform
    target: dict[str, Any]
    steps: list[TestStepSpec] = Field(min_length=1)
    assertions: list[str] = Field(default_factory=list)
    mode: Literal["plan", "live"] = "live"


__all__ = ["TestCaseSpec", "TestStepSpec"]
