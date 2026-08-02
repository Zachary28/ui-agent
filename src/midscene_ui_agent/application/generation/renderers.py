"""Deterministic renderers for generated test-case contracts."""

from __future__ import annotations

import json
import re

import yaml

from ...domain.contracts import TestCaseSpec


def _test_function_name(name: str) -> str:
    normalized = re.sub(r"[^0-9A-Za-z_]+", "_", name).strip("_").lower() or "generated"
    if normalized[0].isdigit():
        normalized = f"case_{normalized}"
    return f"test_{normalized}"


class PythonTestRenderer:
    format = "python"

    def render(self, spec: TestCaseSpec) -> str:
        payload = json.dumps(
            spec.model_dump(mode="json"),
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        function_name = _test_function_name(spec.name)
        return (
            "import json\n\n"
            "from midscene_ui_agent.domain.contracts import AutomationRequest\n"
            "from midscene_ui_agent.interfaces.api import run\n\n\n"
            f"TEST_CASE = json.loads({payload!r})\n\n\n"
            f"def {function_name}():\n"
            '    expected_status = "planned" if TEST_CASE["mode"] == "plan" else "succeeded"\n'
            '    for index, step in enumerate(TEST_CASE["steps"], start=1):\n'
            '        target = {**TEST_CASE["target"], **step["target_overrides"]}\n'
            "        request = AutomationRequest(\n"
            '            platform=TEST_CASE["platform"],\n'
            "            target=target,\n"
            '            goal=step["prompt"],\n'
            '            acceptance=[*TEST_CASE["assertions"], *step["acceptance"]],\n'
            '            operation=step["action"],\n'
            '            mode=TEST_CASE["mode"],\n'
            "        )\n"
            "        result = run(request)\n"
            '        assert result.status == expected_status, f"step {index}: {result.status}"\n'
        )


class YamlTestRenderer:
    format = "yaml"

    def render(self, spec: TestCaseSpec) -> str:
        return yaml.safe_dump(spec.model_dump(mode="json"), sort_keys=False, allow_unicode=True)


__all__ = ["PythonTestRenderer", "YamlTestRenderer"]
