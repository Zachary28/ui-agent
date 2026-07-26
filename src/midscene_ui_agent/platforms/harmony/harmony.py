from .._cli import MidsceneCliAdapter
class HarmonyAdapter(MidsceneCliAdapter):
    package = "@midscene/harmony@1"
    def command(self, request, operation=None):
        spec=super().command(request, operation)
        if ("--deviceId" not in spec.argv) and request.target.device_id: spec.argv.extend(["--deviceId", request.target.device_id])
        return spec
