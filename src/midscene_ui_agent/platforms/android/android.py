from .._cli import MidsceneCliAdapter


class AndroidAdapter(MidsceneCliAdapter):
    package = "@midscene/android@1"

    def command(self, request, operation=None):
        spec = super().command(request, operation)
        if "--deviceId" in spec.argv:
            i = spec.argv.index("--deviceId")
            spec.argv[i] = "--device-id"
        if request.target.use_scrcpy:
            spec.argv.extend(["--use-scrcpy"])
        return spec
