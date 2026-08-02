"""Thin user-facing API facade delegating to application workflows."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

from ..application.workflows.orchestrator import run as run_workflow
from ..domain.contracts import AutomationRequest, AutomationResult, RunFingerprints
from ..infrastructure.execution.runner import CommandRunner
from ..application.nodes.config import resolve_run_config
from ..infrastructure.config.resolver import ConfigResolver
from ..infrastructure.persistence.langgraph import sqlite_checkpointer


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


def run_configured(
    *,
    platform: str,
    app: str,
    task: str,
    environment: str | None = None,
    overrides: list[str] | None = None,
    config_root: str | Path | None = None,
    skills_root: str | Path | None = None,
    skills_lock: str | Path | None = None,
    target_overrides: dict | None = None,
    resume_id: str | None = None,
    mode: str = "plan",
    operation: str = "run",
    report_dir: str | None = None,
    run_id: str | None = None,
    goal: str | None = None,
    runner: CommandRunner | None = None,
    adapters=None,
) -> AutomationResult:
    _load_environment()
    configured = resolve_run_config(
        platform=platform,
        app=app,
        task=task,
        environment=environment,
        overrides=overrides,
        config_root=config_root,
        target_overrides=target_overrides,
        mode="live" if resume_id else mode,
        operation=operation,
        report_dir=report_dir,
        run_id=resume_id or run_id,
        skill_lock_path=skills_lock,
        goal=goal,
    )
    return run(
        configured.request,
        runner=runner,
        adapters=adapters,
        resume=resume_id is not None,
        fingerprints=configured.fingerprints,
        skills_root=skills_root,
        skills_lock=skills_lock,
    )


def resume_run(
    resume_id: str,
    *,
    report_dir: str | Path = "./artifacts",
    skills_root: str | Path | None = None,
    skills_lock: str | Path | None = None,
    target_overrides: dict | None = None,
    goal: str | None = None,
    runner: CommandRunner | None = None,
    adapters=None,
) -> AutomationResult:
    database = Path(report_dir) / "langgraph.sqlite"
    if not database.is_file():
        raise ValueError(f"checkpoint not found for run id: {resume_id}")
    config = {"configurable": {"thread_id": resume_id}}
    with sqlite_checkpointer(database) as checkpointer:
        checkpoint = checkpointer.saver.get_tuple(config)
    if checkpoint is None:
        raise ValueError(f"checkpoint not found for run id: {resume_id}")
    values = checkpoint.checkpoint.get("channel_values", {})
    if not values.get("request") or not values.get("fingerprints"):
        raise ValueError(f"checkpoint metadata is incomplete for run id: {resume_id}")
    stored_request = AutomationRequest.model_validate(values["request"])
    target = stored_request.target.model_dump(mode="json")
    target.update(target_overrides or {})
    request = AutomationRequest.model_validate(
        {
            **stored_request.model_dump(mode="json"),
            "target": target,
            "goal": goal.strip() if goal and goal.strip() else stored_request.goal,
            "run_id": resume_id,
            "report_dir": str(report_dir),
            "mode": "live",
        }
    )
    fingerprints = RunFingerprints.model_validate(values["fingerprints"])
    fingerprint_updates = {}
    if target_overrides:
        fingerprint_updates["target_fingerprint"] = ConfigResolver.canonical_hash(target)
    if goal and goal.strip() and goal.strip() != stored_request.goal:
        fingerprint_updates["config_hash"] = ConfigResolver.canonical_hash(
            {"previous": fingerprints.config_hash, "goal": goal.strip()}
        )
    if skills_lock is not None:
        fingerprint_updates["skill_lock_hash"] = hashlib.sha256(Path(skills_lock).read_bytes()).hexdigest()
    if fingerprint_updates:
        fingerprints = fingerprints.model_copy(update=fingerprint_updates)
    return run(
        request,
        runner=runner,
        adapters=adapters,
        resume=True,
        fingerprints=fingerprints,
        skills_root=skills_root,
        skills_lock=skills_lock,
    )

__all__ = ["run", "run_configured", "resume_run"]
