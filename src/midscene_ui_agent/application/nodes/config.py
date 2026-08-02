"""Resolve layered configuration into public runtime contracts."""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path
from typing import Any

from ...domain.contracts import AutomationRequest, LoopPlan, ResolvedRunConfig, RunFingerprints
from ...infrastructure.config.resolver import ConfigResolver, parse_overrides
from ...infrastructure.config.resources import default_config_root, default_skill_lock_path


def resolve_run_config(
    *,
    platform: str,
    app: str,
    task: str,
    environment: str | None = None,
    overrides: list[str] | dict[str, Any] | None = None,
    config_root: str | Path | None = None,
    target_overrides: dict[str, Any] | None = None,
    mode: str = "plan",
    operation: str = "run",
    report_dir: str | None = None,
    run_id: str | None = None,
    skill_lock_path: str | Path | None = None,
) -> ResolvedRunConfig:
    root = Path(config_root) if config_root is not None else default_config_root()
    override_mapping = parse_overrides(overrides) if isinstance(overrides, list) else overrides
    resolved = ConfigResolver(root).resolve(
        platform=platform,
        app=app,
        task=task,
        environment=environment,
        overrides=override_mapping,
    )
    goal, goal_options = _resolve_goal(resolved.get("goal"))
    loop_payload = _resolve_loop(resolved, goal_options)
    target = _resolve_target(platform, resolved.get("app", {}), target_overrides or {})
    request = AutomationRequest.model_validate(
        {
            "platform": platform,
            "target": target,
            "goal": goal,
            "operation": operation,
            "mode": mode,
            "report_dir": report_dir or resolved.get("artifacts_dir", "./artifacts"),
            "run_id": run_id,
            "loop": loop_payload,
        }
    )
    lock = Path(skill_lock_path) if skill_lock_path is not None else default_skill_lock_path()
    lock_hash = hashlib.sha256(lock.read_bytes()).hexdigest()
    fingerprints = RunFingerprints.model_validate(
        ConfigResolver.fingerprints(
            resolved,
            profile=app,
            skill_lock_hash=lock_hash,
            target=request.target.model_dump(mode="json"),
        )
    )
    return ResolvedRunConfig(request=request, fingerprints=fingerprints)


def _resolve_goal(value: Any) -> tuple[str, dict[str, Any]]:
    if isinstance(value, str) and value.strip():
        return value.strip(), {}
    if isinstance(value, dict):
        prompt = value.get("prompt")
        if isinstance(prompt, str) and prompt.strip():
            return prompt.strip(), {key: copy.deepcopy(item) for key, item in value.items() if key != "prompt"}
    raise ValueError("task configuration requires a non-empty goal.prompt")


def _resolve_loop(resolved: dict[str, Any], goal_options: dict[str, Any]) -> dict[str, Any] | None:
    raw = resolved.get("loop")
    if not isinstance(raw, dict):
        return None
    loop = copy.deepcopy(raw)
    ui = resolved.get("ui", {})
    if isinstance(ui, dict):
        loop.setdefault("popup_prompts", copy.deepcopy(ui.get("popup_prompts", [])))
        loop.setdefault("ad_prompts", copy.deepcopy(ui.get("ad_prompts", [])))
    if goal_options:
        switch = loop.setdefault("operations", {}).get("switch_episode")
        if isinstance(switch, dict):
            switch.setdefault("params", {}).update(goal_options)
    return LoopPlan.model_validate(loop).model_dump(mode="json")


def _resolve_target(platform: str, app: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    target: dict[str, Any] = {}
    if platform == "browser" and app.get("url"):
        target["url"] = app["url"]
    if platform in {"android", "ios", "harmony"} and app.get("launch_uri"):
        target["app_uri"] = app["launch_uri"]
    target.update(copy.deepcopy(overrides))
    return target


__all__ = ["resolve_run_config"]
