import pytest
from pydantic import ValidationError


def test_test_case_rejects_step_without_action() -> None:
    from midscene_ui_agent.domain.contracts import TestCaseSpec

    with pytest.raises(ValidationError):
        TestCaseSpec.model_validate(
            {
                "name": "login",
                "platform": "browser",
                "target": {"url": "https://example.test"},
                "steps": [{"action": "", "prompt": "Log in"}],
            }
        )


def test_test_case_requires_at_least_one_step() -> None:
    from midscene_ui_agent.domain.contracts import TestCaseSpec

    with pytest.raises(ValidationError):
        TestCaseSpec(name="empty", platform="browser", target={"url": "https://example.test"}, steps=[])


def test_test_case_contract_round_trips_json() -> None:
    from midscene_ui_agent.domain.contracts import TestCaseSpec, TestStepSpec

    spec = TestCaseSpec(
        name="open_example",
        platform="browser",
        target={"url": "https://example.test"},
        steps=[TestStepSpec(action="run", prompt="Verify the page title")],
        assertions=["Page title is visible"],
    )

    assert TestCaseSpec.model_validate_json(spec.model_dump_json()) == spec
