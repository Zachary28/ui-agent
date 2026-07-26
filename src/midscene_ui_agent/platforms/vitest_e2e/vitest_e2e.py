from __future__ import annotations
from pathlib import Path
from ...domain.contracts import AutomationRequest
from ...domain.errors import ErrorCode, UiAgentError
from ...infrastructure.execution.runner import CommandSpec
from ..base import PlatformAdapter

class VitestE2EAdapter(PlatformAdapter):
    """Safe lifecycle command builder; mutations remain graph-gated."""
    package = "vitest"
    def init(self, project_dir: str, platform: str, *, ai_action_context: str = "") -> list[Path]:
        if platform not in {"web","android","ios"}: raise UiAgentError(ErrorCode.VALIDATION_ERROR, f"invalid Vitest platform: {platform}")
        root=Path(project_dir); root.mkdir(parents=True,exist_ok=True)
        files={"vitest.config.ts":"import { defineConfig } from 'vitest/config';\nexport default defineConfig({ test: { include: ['e2e/**/*.test.ts'] } });\n", "midscene-context.ts":f"export const platform = {platform!r};\nexport const aiActionContext = {ai_action_context!r};\n"}
        written=[]
        for name,content in files.items():
            path=root/name
            if not path.exists(): path.write_text(content,encoding="utf-8"); written.append(path)
        return written
    def convert(self, project_dir: str, platform: str, *, ai_action_context: str = "") -> list[Path]:
        return self.init(project_dir,platform,ai_action_context=ai_action_context)
    def create(self, project_dir: str, name: str, prompt: str, *, update: bool = False) -> Path:
        project=Path(project_dir); project.mkdir(parents=True,exist_ok=True); test_dir=project/"e2e"; test_dir.mkdir(exist_ok=True); path=test_dir/f"{name}.test.ts"
        if path.exists() and not update: raise UiAgentError(ErrorCode.COMMAND_FAILED, f"test already exists: {path}")
        content=self.render_case(name,prompt); tmp=path.with_suffix(path.suffix+".tmp"); tmp.write_text(content,encoding="utf-8"); tmp.replace(path); return path
    def update_case(self, project_dir: str, name: str, prompt: str) -> Path:
        project=Path(project_dir); matches=list(project.rglob("*.test.ts"))
        for path in matches:
            text=path.read_text(encoding="utf-8"); start=f"// ui-agent:case {name}:start"; end=f"// ui-agent:case {name}:end"
            if start in text and end in text:
                a,b=text.index(start),text.index(end)+len(end); replacement=self.render_case(name,prompt).rstrip(); tmp=path.with_suffix(path.suffix+".tmp"); tmp.write_text(text[:a]+replacement+text[b:],encoding="utf-8"); tmp.replace(path); return path
        raise UiAgentError(ErrorCode.COMMAND_FAILED, f"case marker not found: {name}")
    def command(self, request: AutomationRequest, operation: str | None = None) -> CommandSpec:
        op = operation or request.operation; project = Path(request.target.project_dir or ".")
        if op == "run": argv = ["pnpm", "vitest", "run"]
        elif op == "debug": argv = ["pnpm", "vitest", "run", "-t", request.test_name or ""]
        elif op in {"init", "convert", "create", "update"}: argv = ["ui-agent-vitest", op, "--platform", request.target.vitest_platform or ""]
        else: raise UiAgentError(ErrorCode.UNSUPPORTED_OPERATION, op)
        return CommandSpec(argv, cwd=str(project), timeout_seconds=request.timeout_seconds, session_id=f"vitest:{project.resolve()}:{request.target.vitest_platform}")
    def render_case(self, name: str, goal: str) -> str:
        if any(bad in goal for bad in ("aiTap(", "aiInput(", "aiAssert(", "aiQuery(", "aiWaitFor(")):
            raise UiAgentError(ErrorCode.COMMAND_FAILED, "generated test must use aiAct prompts")
        return f"// ui-agent:case {name}:start\nit('{name}', async () => {{ await aiAct('{goal}'); }});\n// ui-agent:case {name}:end\n"
