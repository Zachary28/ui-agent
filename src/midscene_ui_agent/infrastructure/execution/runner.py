from __future__ import annotations
import os, subprocess, threading, hashlib, shutil
from dataclasses import dataclass, field
from pathlib import Path
from ...domain.errors import ErrorCode, UiAgentError
from ..evidence.redaction import redact, summarize_argv

@dataclass(frozen=True)
class CommandSpec:
    argv: list[str]; cwd: str | None = None; env: dict[str, str] = field(default_factory=dict)
    timeout_seconds: int = 300; session_id: str = "local"; sensitive_indexes: set[int] = field(default_factory=set)

@dataclass
class CommandResult:
    argv: list[str]; returncode: int; stdout: str; stderr: str; timed_out: bool = False

class CommandRunner:
    _locks: dict[str, threading.Lock] = {}; _guard = threading.Lock()
    def __init__(self, artifact_root: str | Path = "artifacts") -> None: self.artifact_root = Path(artifact_root)
    def run(self, spec: CommandSpec, *, run_id: str = "adhoc", event_id: str = "command") -> CommandResult:
        key = hashlib.sha256(spec.session_id.encode()).hexdigest()
        with self._guard: lock = self._locks.setdefault(key, threading.Lock())
        with lock:
            argv=list(spec.argv)
            if argv and os.name == "nt" and not Path(argv[0]).suffix:
                argv[0]=shutil.which(argv[0]+".cmd") or shutil.which(argv[0]) or argv[0]
            try:
                process = subprocess.Popen(argv, shell=False, text=True, encoding="utf-8", errors="replace", stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=spec.cwd, env={**os.environ, **spec.env})
            except FileNotFoundError as exc: raise UiAgentError(ErrorCode.DEPENDENCY_NOT_FOUND, str(exc)) from exc
            try: stdout, stderr = process.communicate(timeout=spec.timeout_seconds); timed_out = False
            except subprocess.TimeoutExpired:
                process.terminate()
                try: stdout, stderr = process.communicate(timeout=1)
                except subprocess.TimeoutExpired: process.kill(); stdout, stderr = process.communicate()
                timed_out = True
            self._write_logs(run_id, event_id, stdout, stderr)
            if timed_out: raise UiAgentError(ErrorCode.TIMEOUT, "command timed out: " + " ".join(summarize_argv(spec.argv, spec.sensitive_indexes)), retryable=True)
            return CommandResult(summarize_argv(spec.argv, spec.sensitive_indexes), process.returncode, stdout, stderr)
    def _write_logs(self, run_id: str, event_id: str, stdout: str, stderr: str) -> None:
        for stream, text in (("stdout", stdout), ("stderr", stderr)):
            path = self.artifact_root / run_id / stream / f"{event_id}.log"; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(redact(text), encoding="utf-8")
