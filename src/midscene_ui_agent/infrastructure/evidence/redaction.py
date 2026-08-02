import re

_SECRET = re.compile(r"(?i)(password|token|cookie|authorization|api[_-]?key)\s*[:=]\s*[^\s,]+")


def redact(value: str | None) -> str:
    if value is None:
        return ""
    return _SECRET.sub(lambda m: m.group(1) + "=<redacted>", value)


def summarize_argv(argv: list[str], sensitive_indexes: set[int] | None = None) -> list[str]:
    sensitive_indexes = sensitive_indexes or set()
    result: list[str] = []
    for index, value in enumerate(argv):
        if index in sensitive_indexes or value == "--extra-http-header":
            result.append("<redacted>" if index in sensitive_indexes else value)
        elif index and argv[index - 1] == "--extra-http-header":
            result.append(value.split(":", 1)[0] + ":<redacted>")
        else:
            result.append(redact(value))
    return result
