from .._cli import MidsceneCliAdapter
class BrowserAdapter(MidsceneCliAdapter):
    package = "@midscene/web@1"
    def command(self, request, operation=None):
        spec = super().command(request, operation); t=request.target
        if t.cdp: spec.argv.extend(["--cdp", t.cdp])
        if t.bridge: spec.argv.extend(["--bridge"])
        for h in t.extra_http_headers: spec.argv.extend(["--extra-http-header", h])
        return spec
