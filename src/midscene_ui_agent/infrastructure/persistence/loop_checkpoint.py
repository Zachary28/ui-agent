from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any


class LoopCheckpoint:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def save(self, state: Any, *, fingerprints: dict[str, str], pending_operation: str | None = None) -> None:
        payload = asdict(state) if is_dataclass(state) else dict(state)
        payload.pop("selected_operation_id", None)
        self.path.write_text(json.dumps({"fingerprints": fingerprints, "state": payload, "pending_operation": pending_operation}, indent=2), encoding="utf-8")

    def restore(self, *, fingerprints: dict[str, str]) -> dict[str, Any]:
        if not self.path.exists():
            raise ValueError("RESUME_INVALID: checkpoint not found")
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if data.get("fingerprints") != fingerprints:
            raise ValueError("RESUME_INVALID: fingerprint mismatch")
        return data


__all__ = ["LoopCheckpoint"]
