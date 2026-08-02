import yaml


def _spec():
    from midscene_ui_agent.domain.contracts import TestCaseSpec, TestStepSpec

    return TestCaseSpec(
        name="open_example",
        platform="browser",
        target={"url": "https://example.test"},
        steps=[TestStepSpec(action="run", prompt="Verify the page title")],
        assertions=["Page title is visible"],
    )


def test_python_renderer_is_deterministic_and_compilable() -> None:
    from midscene_ui_agent.application.generation import PythonTestRenderer

    renderer = PythonTestRenderer()
    first = renderer.render(_spec())
    second = renderer.render(_spec())

    assert first == second
    compile(first, "generated_test.py", "exec")
    assert "AutomationRequest" in first
    assert "midscene_ui_agent.interfaces.api" in first


def test_yaml_renderer_is_deterministic_and_round_trips() -> None:
    from midscene_ui_agent.application.generation import YamlTestRenderer

    renderer = YamlTestRenderer()
    first = renderer.render(_spec())
    second = renderer.render(_spec())

    assert first == second
    assert yaml.safe_load(first) == _spec().model_dump(mode="json")
    assert list(yaml.safe_load(first))[:3] == ["name", "platform", "target"]
