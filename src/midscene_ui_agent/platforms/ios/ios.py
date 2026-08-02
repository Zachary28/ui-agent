from .._cli import MidsceneCliAdapter


class IOSAdapter(MidsceneCliAdapter):
    package = "@midscene/ios@1"

    def command(self, request, operation=None):
        spec = super().command(request, operation)
        t = request.target
        if t.wda_host:
            spec.argv.extend(["--wda-host", t.wda_host])
        if t.wda_port:
            spec.argv.extend(["--wda-port", str(t.wda_port)])
        if request.raw_method:
            spec.argv.extend(["--method", request.raw_method])
        if request.raw_endpoint:
            spec.argv.extend(["--endpoint", request.raw_endpoint])
        if t.session_id:
            spec.argv.extend(["--session-id", t.session_id])
        return spec
