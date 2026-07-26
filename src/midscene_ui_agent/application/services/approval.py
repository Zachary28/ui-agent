from __future__ import annotations
import hashlib, json
from pathlib import Path
from ...domain.contracts import AutomationRequest
def fingerprint(request: AutomationRequest) -> str:
    payload=request.model_dump(exclude={"mode","run_id"}); return hashlib.sha256(json.dumps(payload,sort_keys=True,default=str).encode()).hexdigest()
def write_pending(root: Path, request: AutomationRequest) -> None:
    (root/"approval.json").write_text(json.dumps({"run_id":request.run_id,"fingerprint":fingerprint(request),"operation":request.operation},indent=2),encoding="utf-8")
def validate_pending(root: Path, request: AutomationRequest) -> bool:
    path=root/"approval.json"
    if not path.exists(): return False
    data=json.loads(path.read_text(encoding="utf-8")); return data.get("run_id")==request.run_id and data.get("fingerprint")==fingerprint(request)
