from __future__ import annotations

from pathlib import Path
import re


class EvidenceCollector:
    def __init__(self, root: str | Path, adapter=None, capture=None, extension: str = ".jpeg"):
        self.root = Path(root)
        self.adapter = adapter
        self.capture = capture
        self.extension = extension if extension.startswith(".") else f".{extension}"
        self.root.mkdir(parents=True, exist_ok=True)

    def capture_before(self, operation: str, *, operation_id: str | None = None) -> str | None:
        return self._capture(operation, "before", operation_id)

    def capture_after(self, operation: str, *, operation_id: str | None = None) -> str | None:
        return self._capture(operation, "after", operation_id)

    def _capture(self, operation: str, phase: str, operation_id: str | None) -> str | None:
        stable_id = re.sub(r"[^A-Za-z0-9._-]+", "-", operation_id or operation).strip("-")
        path = self.root / f"{stable_id}-{operation}-{phase}{self.extension}"
        if self.capture is not None:
            try:
                result = self.capture(operation, phase, path)
            except Exception:
                return None
            return str(path) if result is not False and path.exists() else None
        if not self.adapter or not hasattr(self.adapter, "screenshot"):
            return None
        result = self.adapter.screenshot(str(path))
        if result is False:
            return None
        return str(path)


__all__ = ["EvidenceCollector"]
