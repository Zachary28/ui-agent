from __future__ import annotations

import json
import hashlib

from midscene_ui_agent.domain.contracts import AutomationRequest, RunFingerprints
from midscene_ui_agent.infrastructure.execution.runner import CommandResult
from midscene_ui_agent.infrastructure.execution.runner import CommandSpec
from midscene_ui_agent.platforms.base import OperationOutcome


class RecordingRunner:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def run(self, spec, *, run_id, event_id):
        del run_id
        self.calls.append(event_id)
        return CommandResult(spec.argv, 0, "ok", "")


def _request(tmp_path) -> AutomationRequest:
    return AutomationRequest(
        platform="browser",
        target={"url": "https://example.test"},
        goal="inspect",
        operation="screenshot",
        mode="live",
        report_dir=str(tmp_path),
        run_id="r1",
    )


def _fingerprints() -> RunFingerprints:
    return RunFingerprints(
        config_hash="config",
        profile_hash="profile",
        loop_plan_hash="loop",
        skill_lock_hash="skills",
        target_fingerprint="target",
    )


def test_skill_lock_failure_happens_before_platform_connect(tmp_path) -> None:
    from midscene_ui_agent.interfaces.api import run

    skills_root = tmp_path / "skills"
    skill_file = skills_root / "browser" / "SKILL.md"
    skill_file.parent.mkdir(parents=True)
    skill_file.write_text("---\nname: browser\n---\n", encoding="utf-8")
    lock = tmp_path / "skills.lock.json"
    lock.write_text(
        json.dumps(
            {
                "browser": {
                    "files": [
                        {
                            "relative_path": "browser/SKILL.md",
                            "sha256": hashlib.sha256(skill_file.read_bytes()).hexdigest(),
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    skill_file.write_text("changed", encoding="utf-8")
    runner = RecordingRunner()

    result = run(
        _request(tmp_path),
        runner=runner,
        skills_root=skills_root,
        skills_lock=lock,
        fingerprints=_fingerprints(),
    )

    assert result.status == "failed"
    assert "skill lock mismatch" in (result.error or "")
    assert runner.calls == []


def test_single_operation_captures_before_and_after_evidence() -> None:
    from midscene_ui_agent.application.graphs.single_operation import build_single_operation_graph

    evidence: list[tuple[str, str, str]] = []
    graph = build_single_operation_graph(
        executor=lambda state, operation: {"phase": operation, "status": "succeeded", "message": "ok"},
        capture_evidence=lambda operation, operation_id, phase, state: evidence.append(
            (operation, operation_id, phase)
        )
        or f"{operation_id}-{phase}.jpeg",
    )

    result = graph.invoke({"run_id": "r1", "request": {"operation": "screenshot"}})

    assert [item[2] for item in evidence] == ["before", "after", "before", "after"]
    assert evidence[0][1] == "step-0:connect"
    assert evidence[2][1] == "step-1:screenshot"
    assert result["evidence_refs"] == [
        "step-0:connect-before.jpeg",
        "step-0:connect-after.jpeg",
        "step-1:screenshot-before.jpeg",
        "step-1:screenshot-after.jpeg",
    ]


def test_manifest_contains_graph_metadata(tmp_path) -> None:
    from midscene_ui_agent.interfaces.api import run

    result = run(_request(tmp_path), runner=RecordingRunner(), fingerprints=_fingerprints())
    manifest = json.loads((tmp_path / result.run_id / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["thread_id"] == result.run_id
    assert manifest["fingerprints"]["config_hash"] == "config"
    assert manifest["graph_phase"] == "finalize_run"


def test_release_failure_is_secondary_and_does_not_replace_success(tmp_path) -> None:
    from midscene_ui_agent.interfaces.api import run

    class ReleaseFailingAdapter:
        def command(self, request, operation=None):
            return CommandSpec(["fake", operation or request.operation])

        def release(self, context):
            return OperationOutcome(False, "disconnect failed")

    request = AutomationRequest(
        platform="android",
        target={"device_id": "fake"},
        goal="inspect",
        operation="screenshot",
        mode="live",
        report_dir=str(tmp_path),
        run_id="release-failure",
    )

    result = run(
        request,
        runner=RecordingRunner(),
        adapters={"android": ReleaseFailingAdapter()},
        fingerprints=_fingerprints(),
    )

    assert result.status == "succeeded"
    assert result.secondary_errors == ["RESOURCE_RELEASE_FAILED: disconnect failed"]


def test_loop_writes_before_and_after_evidence_snapshots(tmp_path) -> None:
    from midscene_ui_agent.interfaces.api import run

    class PromptAdapter:
        def execute_prompt(self, prompt):
            return "playing"

    request = AutomationRequest(
        platform="android",
        target={"device_id": "fake"},
        goal="watch",
        mode="live",
        report_dir=str(tmp_path),
        run_id="loop-evidence",
        loop={
            "defaults": {"min_operation_interval_seconds": 0.1},
            "exit_conditions": {"max_runtime_seconds": 0.1},
            "operations": {"check_playback": {"enabled": True, "startup": True}},
        },
    )

    result = run(
        request,
        runner=RecordingRunner(),
        adapters={"android": PromptAdapter()},
        fingerprints=_fingerprints(),
    )

    evidence = sorted((tmp_path / result.run_id / "evidence").glob("*.json"))
    assert result.status == "succeeded"
    assert result.loop_summary["operations"]["check_playback"]["successes"] == 1
    assert [json.loads(path.read_text(encoding="utf-8"))["phase"] for path in evidence] == ["after", "before"]
