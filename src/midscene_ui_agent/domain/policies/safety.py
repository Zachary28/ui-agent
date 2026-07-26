from ..contracts import Target
def classify_risk(goal: str) -> str:
    value = goal.lower()
    if any(word in value for word in ("pay", "purchase", "buy", "delete", "send", "submit", "grant", "disable", "remove")): return "high"
    if any(word in value for word in ("edit", "change", "update", "settings", "profile")): return "medium"
    return "low"
def requires_approval(platform: str, target: Target, goal: str, operation: str = "run", mode: str = "live") -> bool:
    return classify_risk(goal) == "high" or bool(target.cdp or target.bridge or target.host) or operation in {"raw", "create", "update", "init", "convert"} or (mode == "live" and classify_risk(goal) != "low")
