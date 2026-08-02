"""Stable domain contracts for UI automation."""

from .contracts import (
    Platform,
    Operation,
    ReferenceImage,
    Target,
    AutomationRequest,
    Artifact,
    StepResult,
    AutomationResult,
)
from .loop import (
    OperationName,
    Trigger,
    ExitReason,
    LoopDefaults,
    OperationConfig,
    ExitConditions,
    LoopPlan,
    LoopRequest,
)
from .runtime import RunFingerprints, ResolvedRunConfig
from .test_cases import TestCaseSpec, TestStepSpec

__all__ = [
    "Platform",
    "Operation",
    "ReferenceImage",
    "Target",
    "AutomationRequest",
    "Artifact",
    "StepResult",
    "AutomationResult",
    "OperationName",
    "Trigger",
    "ExitReason",
    "LoopDefaults",
    "OperationConfig",
    "ExitConditions",
    "LoopPlan",
    "LoopRequest",
    "RunFingerprints",
    "ResolvedRunConfig",
    "TestCaseSpec",
    "TestStepSpec",
]
