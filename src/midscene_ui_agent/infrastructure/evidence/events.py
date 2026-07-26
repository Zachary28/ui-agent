from __future__ import annotations
import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from .redaction import redact

@dataclass
class Event:
    kind: str; message: str; run_id: str; timestamp: str = ""
    def __post_init__(self):
        if not self.timestamp: self.timestamp=datetime.now(timezone.utc).isoformat()
    def write(self, path: str | Path):
        p=Path(path); p.parent.mkdir(parents=True,exist_ok=True)
        with p.open("a",encoding="utf-8") as f: f.write(json.dumps({**asdict(self),"message":redact(self.message)})+"\n")
