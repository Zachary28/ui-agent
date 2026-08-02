import json
import importlib

import pytest
from pydantic import ValidationError

from midscene_ui_agent.domain.contracts import (
    AutomationRequest,
    AutomationResult,
    ExitReason,
    LoopPlan,
    ResolvedRunConfig,
    RunFingerprints,
)
from midscene_ui_agent.domain.runtime import AutomationGraphState, LoopGraphState


def test_loop_exit_limits_are_strongly_typed() -> None:
    plan = LoopPlan.model_validate(
        {
            "exit_conditions": {
                "max_runtime_seconds": 60,
                "max_switches": 2,
                "max_scrolls": 3,
                "target_count": 4,
            }
        }
    )

    assert plan.exit_conditions.max_switches == 2
    assert plan.exit_conditions.max_scrolls == 3
    assert plan.exit_conditions.target_count == 4


def test_runtime_result_supports_resume_invalid() -> None:
    result = AutomationResult(
        run_id="r1",
        status="resume_invalid",
        exit_reason=ExitReason.RESUME_INVALID,
    )

    assert result.status == "resume_invalid"
    assert result.exit_reason == ExitReason.RESUME_INVALID


def test_runtime_result_rejects_unknown_exit_reason() -> None:
    with pytest.raises(ValidationError):
        AutomationResult(run_id="r1", status="failed", exit_reason="totally_invalid")


def test_exit_reason_has_the_public_runtime_values() -> None:
    assert {reason.value for reason in ExitReason} == {
        "completed",
        "max_runtime",
        "max_switches",
        "max_scrolls",
        "target_count",
        "max_failures",
        "no_progress",
        "device_unreachable",
        "model_error",
        "login_required",
        "purchase_required",
        "unhandled_popup",
        "cancelled",
        "resume_invalid",
    }


def test_fingerprints_require_all_runtime_hashes() -> None:
    with pytest.raises(ValidationError):
        RunFingerprints(config_hash="a", profile_hash="b")


def test_fingerprints_reject_empty_runtime_hashes() -> None:
    with pytest.raises(ValidationError):
        RunFingerprints(
            config_hash="",
            profile_hash="",
            loop_plan_hash="",
            skill_lock_hash="",
            target_fingerprint="",
        )


def test_fingerprints_are_frozen() -> None:
    fingerprints = _fingerprints()

    with pytest.raises(ValidationError):
        fingerprints.config_hash = "changed"


def test_resolved_run_config_contains_validated_request_and_fingerprints() -> None:
    config = ResolvedRunConfig(
        request={
            "platform": "browser",
            "target": {"url": "https://example.test"},
            "goal": "inspect",
        },
        fingerprints=_fingerprints(),
    )

    assert isinstance(config.request, AutomationRequest)
    assert config.fingerprints.target_fingerprint == "target"


def test_resolved_run_config_rejects_non_json_request_values() -> None:
    with pytest.raises(ValidationError, match="JSON-serializable"):
        ResolvedRunConfig(
            request={
                "platform": "browser",
                "target": {"url": "https://example.test"},
                "goal": "inspect",
                "variables": {"bad": object()},
            },
            fingerprints=_fingerprints(),
        )


@pytest.mark.parametrize(
    "module_name",
    [
        "midscene_ui_agent.domain.contracts.contracts",
        "midscene_ui_agent.domain.contracts.loop_contracts",
        "midscene_ui_agent.domain.contracts.runtime",
        "midscene_ui_agent.domain.runtime.graph",
    ],
)
def test_public_contract_modules_import_independently(module_name: str) -> None:
    assert importlib.import_module(module_name)


def test_graph_states_have_json_serializable_checkpoint_shapes() -> None:
    automation_state: AutomationGraphState = {
        "run_id": "r1",
        "thread_id": "r1",
        "request": {"platform": "browser", "goal": "inspect"},
        "config": {"request": {"goal": "inspect"}},
        "operation_steps": ["run"],
        "steps": [{"phase": "execute", "status": "succeeded"}],
        "artifacts": [{"kind": "report", "path": "result.json"}],
        "fingerprints": _fingerprints().model_dump(mode="json"),
        "resource_release_state": {"adapter": "released"},
        "report_path": "report.html",
    }
    loop_state: LoopGraphState = {
        "tick": 2,
        "elapsed_seconds": 4.5,
        "due_operations": ["check_playback"],
        "selected_operation": "check_playback",
        "operation_id": "r1:2:check_playback",
        "operation_attempts": {"check_playback": 1},
        "operation_successes": {"check_playback": 1},
        "operation_failures": {"check_playback": 0},
        "switch_count": 1,
        "scroll_count": 2,
        "target_count": 3,
        "evidence_refs": ["screenshots/tick-2.png"],
        "exit_reason": ExitReason.COMPLETED.value,
        "cancelled": False,
    }

    assert json.loads(json.dumps(automation_state))["run_id"] == "r1"
    assert json.loads(json.dumps(loop_state))["operation_id"] == "r1:2:check_playback"


def _fingerprints() -> RunFingerprints:
    return RunFingerprints(
        config_hash="config",
        profile_hash="profile",
        loop_plan_hash="loop",
        skill_lock_hash="skills",
        target_fingerprint="target",
    )
