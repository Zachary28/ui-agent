from __future__ import annotations
from abc import ABC, abstractmethod
from ..domain.contracts import AutomationRequest
from ..infrastructure.execution.runner import CommandSpec

class PlatformAdapter(ABC):
    package: str
    @abstractmethod
    def command(self, request: AutomationRequest, operation: str | None = None) -> CommandSpec: ...
    def _operation(self, request, operation): return self.command(request, operation)
    def connect(self, request): return self._operation(request,"connect")
    def health_check(self, request): return self._operation(request,"health_check")
    def screenshot(self, request): return self._operation(request,"screenshot")
    def launch(self, request): return self._operation(request,"launch")
    def execute(self, request): return self._operation(request,"run")
    def verify(self, request): return self._operation(request,"assert")
    def tap_locate(self, request): return self._operation(request,"tap_locate")
    def report(self, request): return self._operation(request,"report")
    def disconnect(self, request): return self._operation(request,"disconnect")
    def close(self, request): return self._operation(request,"close")
