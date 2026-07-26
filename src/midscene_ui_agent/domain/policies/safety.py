def classify_risk(goal: str) -> str:
    value = goal.lower()
    if any(word in value for word in ("pay", "purchase", "buy", "delete", "send", "submit", "grant", "disable", "remove")): return "high"
    if any(word in value for word in ("edit", "change", "update", "settings", "profile")): return "medium"
    return "low"
