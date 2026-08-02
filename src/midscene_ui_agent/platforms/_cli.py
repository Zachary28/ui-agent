from __future__ import annotations
from ..domain.contracts import AutomationRequest
from ..infrastructure.execution.runner import CommandSpec
from .base import PlatformAdapter


class MidsceneCliAdapter(PlatformAdapter):
    package = ""
    command_name = ""

    def command(self, request: AutomationRequest, operation: str | None = None) -> CommandSpec:
        op = operation or request.operation
        args = ["npx", "-y", self.package, self.operation_name(op)]
        t = request.target
        if t.device_id:
            args.extend(["--deviceId", t.device_id])
        if t.url:
            args.extend(["--url", t.url])
        if t.app_uri and op == "launch":
            args.extend(["--uri", t.app_uri])
        if t.display_id is not None:
            args.extend(["--displayId", str(t.display_id)])
        if request.deep_think:
            args.append("--deep-think")
        if request.deep_locate:
            args.append("--deep-locate")
        if op in {"run", "assert"}:
            args.extend(["--prompt", request.goal])
        if op == "raw" and request.raw_command:
            args.extend(["--command", request.raw_command])
        if op == "tap_locate" and request.locate:
            import json

            args.extend(["--locate", json.dumps(request.locate)])
        for image in t.reference_images:
            args.extend(["--image", image.source, "--image-name", image.name])
        if t.convert_http_image2_base64:
            args.extend(["--convertHttpImage2Base64", "true"])
        return CommandSpec(args, timeout_seconds=request.timeout_seconds, session_id=self.session_key(request))

    def operation_name(self, operation):
        return {
            "run": "act",
            "health_check": "take_screenshot",
            "screenshot": "take_screenshot",
            "tap_locate": "tap",
        }.get(operation, operation)

    def session_key(self, request: AutomationRequest) -> str:
        return f"{request.platform}:{request.target.device_id or request.target.url or 'local'}"
