import pytest
from pydantic import ValidationError


def test_operation_inherits_global_interval_and_override():
    from midscene_ui_agent.domain.contracts.loop_contracts import LoopPlan

    plan = LoopPlan.model_validate({"operations": {"check_playback": {"enabled": True}}})
    assert plan.operations["check_playback"].interval_seconds == plan.defaults.interval_seconds

    overridden = LoopPlan.model_validate(
        {"defaults": {"interval_seconds": 11}, "operations": {"check_playback": {"enabled": True}}}
    )
    assert overridden.operations["check_playback"].interval_seconds == 11


def test_switch_requires_exit_target_and_rejects_unsafe_popup_prompt():
    from midscene_ui_agent.domain.contracts.loop_contracts import LoopPlan

    with pytest.raises(ValidationError):
        LoopPlan.model_validate({"operations": {"switch_episode": {"enabled": True}}})
    with pytest.raises(ValidationError):
        LoopPlan.model_validate({"popup_prompts": ["请输入手机号登录"], "operations": {}})


def test_operation_interval_and_scroll_constraints():
    from midscene_ui_agent.domain.contracts.loop_contracts import LoopPlan

    with pytest.raises(ValidationError):
        LoopPlan.model_validate(
            {
                "defaults": {"min_operation_interval_seconds": 5},
                "operations": {"check_playback": {"interval_seconds": 4}},
            }
        )
    with pytest.raises(ValidationError):
        LoopPlan.model_validate({"operations": {"scroll_feed": {"enabled": True}}})
    assert LoopPlan.model_validate({"operations": {"scroll_feed": {"enabled": True, "params": {"scroll_limit": 2}}}})
    plan = LoopPlan.model_validate(
        {"operations": {"scroll_feed": {"enabled": True, "duration_seconds": 15}}}
    )
    assert plan.operations["scroll_feed"].duration_seconds == 15


def test_operation_prompt_rejects_unsafe_prompt_and_accepts_safe_prompt():
    from midscene_ui_agent.domain.contracts.loop_contracts import LoopPlan

    with pytest.raises(ValidationError):
        LoopPlan.model_validate(
            {"operations": {"check_playback": {"enabled": True, "prompt": "log in with my account"}}}
        )
    plan = LoopPlan.model_validate(
        {"operations": {"check_playback": {"enabled": True, "prompt": "verify playback state"}}}
    )
    assert plan.operations["check_playback"].prompt == "verify playback state"


def test_automation_request_accepts_optional_loop():
    from midscene_ui_agent.domain.contracts import AutomationRequest

    request = AutomationRequest.model_validate(
        {"platform": "browser", "target": {"url": "https://example.test"}, "goal": "watch"}
    )
    assert request.loop is None
