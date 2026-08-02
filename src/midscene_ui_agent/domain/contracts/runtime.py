"""Runtime configuration and normalized exit contracts."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic_core import PydanticSerializationError

from .runtime_types import ExitReason


class RunFingerprints(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    config_hash: str = Field(min_length=1)
    profile_hash: str = Field(min_length=1)
    loop_plan_hash: str = Field(min_length=1)
    skill_lock_hash: str = Field(min_length=1)
    target_fingerprint: str = Field(min_length=1)


# Imported after the independent contracts above so this module and
# ``loop_contracts`` remain safe to import directly.
from .contracts import AutomationRequest  # noqa: E402


class ResolvedRunConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request: AutomationRequest
    fingerprints: RunFingerprints

    @model_validator(mode="after")
    def request_is_json_serializable(self) -> "ResolvedRunConfig":
        try:
            self.request.model_dump_json()
        except PydanticSerializationError as exc:
            raise ValueError("resolved request must be JSON-serializable") from exc
        return self


__all__ = ["ExitReason", "RunFingerprints", "ResolvedRunConfig"]
