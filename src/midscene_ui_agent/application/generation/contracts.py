"""Protocols for model-backed test generation and deterministic rendering."""

from __future__ import annotations

from typing import Any, Mapping, Protocol

from ...domain.contracts import TestCaseSpec


class TestScriptGenerator(Protocol):
    def generate(self, requirement: str, capabilities: Mapping[str, Any]) -> TestCaseSpec: ...


class TestScriptRenderer(Protocol):
    format: str

    def render(self, spec: TestCaseSpec) -> str: ...


__all__ = ["TestScriptGenerator", "TestScriptRenderer"]
