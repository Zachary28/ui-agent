from __future__ import annotations

from midscene_ui_agent.domain.runtime.loop import RuntimeState


class OperationSelector:
    PRIORITY = {
        "dismiss_popup": 100, "skip_ad": 90, "recover_playback": 80,
        "check_playback": 60, "switch_episode": 50, "scroll_feed": 40,
        "screenshot": 10, "report_snapshot": 5,
    }

    def choose(self, due: list[str], state: RuntimeState) -> str | None:
        if state.selected_operation_id is not None:
            return None
        candidates = list(due)
        if state.popup_detected and "dismiss_popup" in candidates:
            selected = "dismiss_popup"
        elif state.ad_detected and "skip_ad" in candidates:
            selected = "skip_ad"
        else:
            selected = min(candidates, key=lambda name: (-self.PRIORITY.get(name, 0), name), default=None)
        if selected:
            state.selected_operation_id = f"tick-{state.current_tick + 1}:{selected}"
        return selected


__all__ = ["OperationSelector"]
