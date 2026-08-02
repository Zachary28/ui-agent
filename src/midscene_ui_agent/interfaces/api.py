"""Thin user-facing API facade delegating to application workflows."""
from __future__ import annotations

import os
from pathlib import Path

from ..application.workflows.orchestrator import run as run_workflow
from ..domain.contracts import AutomationRequest, AutomationResult, RunFingerprints
from ..infrastructure.execution.runner import CommandRunner


def _load_environment() -> None:
    """Load .env, falling back to the documented example for local setup."""
    path = Path(".env")
    if not path.exists():
        path = Path(".env.example")
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def run(
    request: AutomationRequest,
    *,
    runner: CommandRunner | None = None,
    adapters=None,
    resume: bool = False,
    fingerprints: RunFingerprints | None = None,
    skills_root: str | Path | None = None,
    skills_lock: str | Path | None = None,
) -> AutomationResult:
    _load_environment()
    return run_workflow(
        request,
        runner=runner,
        adapters=adapters,
        resume=resume,
        fingerprints=fingerprints,
        skills_root=skills_root,
        skills_lock=skills_lock,
    )

__all__ = ["run"]
