import re
class PhasePlanner:
    def plan(self, goal: str, max_steps: int = 20) -> list[str]:
        parts = [p.strip() for p in re.split(r"\n+|(?=\d+[.)]\s)", goal) if p.strip()]
        return parts[:max_steps] or [goal]
