from __future__ import annotations

from pathlib import Path


class EvidenceCollector:
    def __init__(self, root: str | Path, adapter=None):
        self.root = Path(root)
        self.adapter = adapter
        self.root.mkdir(parents=True, exist_ok=True)

    def capture_before(self, operation: str) -> str | None:
        return self._capture(operation, "before")

    def capture_after(self, operation: str) -> str | None:
        return self._capture(operation, "after")

    def _capture(self, operation: str, phase: str) -> str | None:
        if not self.adapter or not hasattr(self.adapter, "screenshot"):
            return None
        path = self.root / f"{operation}-{phase}.jpeg"
        result = self.adapter.screenshot(str(path))
        if result is False:
            return None
        return str(path)


__all__ = ["EvidenceCollector"]
