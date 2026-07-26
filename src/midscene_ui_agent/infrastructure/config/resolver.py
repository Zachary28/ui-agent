"""Layered, deterministic YAML configuration resolution."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml


class ConfigResolver:
    """Resolve defaults, platform, profile, task and runtime overrides."""

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()

    def resolve(self, *, platform: str, app: str, task: str, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        result = self._load_required(self.root / "defaults.yaml")
        result = self._merge(result, self._load_required(self.root / "platforms" / f"{platform}.yaml"))
        result = self._merge(result, self._load_profile(app))
        result = self._merge(result, self._load_required(self.root / "tasks" / f"{task}.yaml"))
        if overrides:
            result = self._merge(result, copy.deepcopy(overrides))
        return result

    def _load_profile(self, profile: str) -> dict[str, Any]:
        path = self.root / "apps" / f"{profile}.yaml"
        if not path.exists():
            # Permit profiles represented as apps/<platform>/<name>.yaml.
            path = self.root / "apps" / (profile.replace(".", "/") + ".yaml")
        return self._load_required(path)

    def _load_required(self, path: Path, stack: tuple[Path, ...] = ()) -> dict[str, Any]:
        path = path.resolve()
        if not path.is_relative_to(self.root):
            raise ValueError(f"configuration path escapes root: {path}")
        if not path.is_file():
            raise FileNotFoundError(path)
        if path in stack:
            raise ValueError(f"configuration extends cycle: {path}")
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            raise ValueError(f"configuration must be a mapping: {path}")
        parent = data.pop("extends", None)
        if parent:
            parent_path = self._resolve_extends(path, str(parent))
            data = self._merge(self._load_required(parent_path, stack + (path,)), data)
        return data

    def _resolve_extends(self, child: Path, parent: str) -> Path:
        raw = Path(parent)
        variants = [raw] if raw.suffix else [raw, Path(f"{parent}.yaml")]
        candidates = [base / item for base in (child.parent, self.root) for item in variants]
        for candidate in candidates:
            candidate = candidate.resolve()
            if candidate.is_file() and candidate.is_relative_to(self.root):
                return candidate
        raise FileNotFoundError(f"extended configuration not found: {parent}")

    @classmethod
    def _merge(cls, base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        result = copy.deepcopy(base)
        for key, value in override.items():
            if isinstance(value, dict) and set(value) == {"append", "values"} and value.get("append") is True:
                previous = result.get(key, [])
                if not isinstance(previous, list) or not isinstance(value["values"], list):
                    raise ValueError(f"append merge requires lists at {key}")
                result[key] = previous + copy.deepcopy(value["values"])
            elif isinstance(value, dict) and isinstance(result.get(key), dict):
                result[key] = cls._merge(result[key], value)
            else:
                result[key] = copy.deepcopy(value)
        return result

    @staticmethod
    def canonical_hash(value: Any) -> str:
        payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @classmethod
    def fingerprints(cls, resolved: dict[str, Any], *, profile: str | None = None, skill_lock_hash: str | None = None) -> dict[str, str]:
        loop = resolved.get("loop", {})
        return {
            "config_hash": cls.canonical_hash(resolved),
            "profile_hash": cls.canonical_hash({"profile": profile, "app": resolved.get("app", {})}),
            "loop_plan_hash": cls.canonical_hash(loop),
            "skill_lock_hash": skill_lock_hash or "",
        }


__all__ = ["ConfigResolver"]
