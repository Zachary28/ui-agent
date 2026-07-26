from __future__ import annotations
import shutil, subprocess
from ...domain.errors import ErrorCode, UiAgentError
def check_dependencies(platform: str) -> dict[str,str]:
    result={}
    for name in ("node","npx"):
        path=shutil.which(name) or shutil.which(name+".cmd")
        if not path: raise UiAgentError(ErrorCode.DEPENDENCY_NOT_FOUND,name)
        result[name]=subprocess.check_output([path,"--version"],text=True).strip()
    if platform == "vitest_e2e":
        path=shutil.which("pnpm") or shutil.which("pnpm.cmd")
        if not path: raise UiAgentError(ErrorCode.DEPENDENCY_NOT_FOUND,"pnpm")
        result["pnpm"]=subprocess.check_output([path,"--version"],text=True).strip()
    return result
