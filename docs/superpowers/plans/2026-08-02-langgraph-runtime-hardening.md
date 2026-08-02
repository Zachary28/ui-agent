# LangGraph Runtime Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the partially connected runtime with a real LangGraph main graph and Loop subgraph, make configuration, retries, evidence, skill locks and resume semantics effective, and add stable contracts for future test-script generation.

**Architecture:** A typed `AutomationGraphState` drives the top-level graph and delegates deterministic work to single-operation and Loop subgraphs. Platform-specific commands remain behind `PlatformAdapter`; LangGraph SQLite checkpoints use `run_id` as `thread_id`, while configuration and target fingerprints prevent invalid resumes. Future test generation consumes and produces domain contracts without coupling model logic to the runtime.

**Tech Stack:** Python 3.11+, Pydantic v2, LangGraph 1.2, SQLite checkpointer, PyYAML, Typer, pytest, Ruff, mypy, build.

---

## File Structure

New files and responsibilities:

- `src/midscene_ui_agent/domain/contracts/runtime.py`: resolved configuration, fingerprints and normalized exit reasons.
- `src/midscene_ui_agent/domain/contracts/test_cases.py`: stable test-generation contracts.
- `src/midscene_ui_agent/domain/runtime/graph.py`: serializable LangGraph state definitions.
- `src/midscene_ui_agent/domain/policies/retry.py`: retry classification and attempt policy.
- `src/midscene_ui_agent/domain/policies/resume.py`: operation idempotency and resume validation.
- `src/midscene_ui_agent/application/graphs/automation.py`: top-level graph assembly.
- `src/midscene_ui_agent/application/graphs/single_operation.py`: deterministic operation subgraph.
- `src/midscene_ui_agent/application/graphs/loop.py`: interval-driven Loop subgraph.
- `src/midscene_ui_agent/application/nodes/config.py`: configuration loading and request construction.
- `src/midscene_ui_agent/application/nodes/lifecycle.py`: run preparation, skill validation and finalization.
- `src/midscene_ui_agent/application/nodes/execution.py`: platform execution, timeout and evidence nodes.
- `src/midscene_ui_agent/application/nodes/reporting.py`: graph-facing report nodes.
- `src/midscene_ui_agent/application/generation/contracts.py`: generator and renderer protocols.
- `src/midscene_ui_agent/application/generation/renderers.py`: deterministic Python and YAML renderers.
- `src/midscene_ui_agent/infrastructure/config/resources.py`: source/wheel configuration discovery.
- `src/midscene_ui_agent/infrastructure/persistence/langgraph.py`: SQLite saver lifecycle.

Existing files modified:

- `src/midscene_ui_agent/domain/contracts/contracts.py`
- `src/midscene_ui_agent/domain/contracts/loop_contracts.py`
- `src/midscene_ui_agent/domain/contracts/__init__.py`
- `src/midscene_ui_agent/domain/policies/exit.py`
- `src/midscene_ui_agent/domain/runtime/__init__.py`
- `src/midscene_ui_agent/infrastructure/config/resolver.py`
- `src/midscene_ui_agent/infrastructure/evidence/collector.py`
- `src/midscene_ui_agent/infrastructure/reporting/reports.py`
- `src/midscene_ui_agent/platforms/base.py`
- `src/midscene_ui_agent/platforms/_cli.py`
- `src/midscene_ui_agent/application/workflows/orchestrator.py`
- `src/midscene_ui_agent/interfaces/cli.py`
- `src/midscene_ui_agent/interfaces/api.py`
- `pyproject.toml`

Removed after migration:

- `src/midscene_ui_agent/adapters/`
- `src/midscene_ui_agent/application/workflows/graph.py`
- `src/midscene_ui_agent/application/loop/controller.py`
- `src/midscene_ui_agent/infrastructure/persistence/loop_checkpoint.py`
- `src/midscene_ui_agent/domain/policies/safety.py`

## Task 1: Normalize Runtime Contracts and Exit Semantics

**Files:**
- Create: `src/midscene_ui_agent/domain/contracts/runtime.py`
- Create: `src/midscene_ui_agent/domain/runtime/graph.py`
- Modify: `src/midscene_ui_agent/domain/contracts/contracts.py`
- Modify: `src/midscene_ui_agent/domain/contracts/loop_contracts.py`
- Modify: `src/midscene_ui_agent/domain/contracts/__init__.py`
- Modify: `src/midscene_ui_agent/domain/runtime/__init__.py`
- Test: `tests/unit/domain/test_runtime_contracts.py`

- [ ] **Step 1: Write failing contract tests**

```python
from pydantic import ValidationError
import pytest

from midscene_ui_agent.domain.contracts import ExitReason, LoopPlan, RunFingerprints


def test_loop_exit_limits_are_strongly_typed():
    plan = LoopPlan.model_validate({
        "exit_conditions": {
            "max_runtime_seconds": 60,
            "max_switches": 2,
            "max_scrolls": 3,
            "target_count": 4,
        }
    })
    assert plan.exit_conditions.max_switches == 2
    assert plan.exit_conditions.max_scrolls == 3
    assert plan.exit_conditions.target_count == 4


def test_runtime_result_supports_resume_invalid():
    from midscene_ui_agent.domain.contracts import AutomationResult
    result = AutomationResult(run_id="r1", status="resume_invalid", exit_reason=ExitReason.RESUME_INVALID)
    assert result.status == "resume_invalid"


def test_fingerprints_require_all_runtime_hashes():
    with pytest.raises(ValidationError):
        RunFingerprints(config_hash="a", profile_hash="b")
```

- [ ] **Step 2: Run tests and verify RED**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/unit/domain/test_runtime_contracts.py -v`

Expected: collection fails because `ExitReason` and `RunFingerprints` do not exist and Loop exit limits are rejected.

- [ ] **Step 3: Add normalized contracts and graph state**

Implement the public contract shape:

```python
class ExitReason(StrEnum):
    COMPLETED = "completed"
    MAX_RUNTIME = "max_runtime"
    MAX_SWITCHES = "max_switches"
    MAX_SCROLLS = "max_scrolls"
    TARGET_COUNT = "target_count"
    MAX_FAILURES = "max_failures"
    NO_PROGRESS = "no_progress"
    DEVICE_UNREACHABLE = "device_unreachable"
    MODEL_ERROR = "model_error"
    LOGIN_REQUIRED = "login_required"
    PURCHASE_REQUIRED = "purchase_required"
    UNHANDLED_POPUP = "unhandled_popup"
    CANCELLED = "cancelled"
    RESUME_INVALID = "resume_invalid"


class RunFingerprints(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    config_hash: str
    profile_hash: str
    loop_plan_hash: str
    skill_lock_hash: str
    target_fingerprint: str


class ResolvedRunConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request: AutomationRequest
    fingerprints: RunFingerprints
```

Define `AutomationGraphState` and `LoopGraphState` as `TypedDict(total=False)` using only JSON-serializable fields. Add `max_switches`, `max_scrolls` and `target_count` to `ExitConditions`. Remove `needs_confirmation` from `AutomationResult.status` and add `resume_invalid`.

- [ ] **Step 4: Run focused and existing contract tests**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/unit/domain/test_runtime_contracts.py tests/test_contracts.py tests/test_loop_contracts.py -v`

Expected: all selected tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src/midscene_ui_agent/domain tests/unit/domain/test_runtime_contracts.py
git commit -m "feat: define typed graph runtime contracts"
```

## Task 2: Complete Layered Configuration and Package Resources

**Files:**
- Create: `src/midscene_ui_agent/infrastructure/config/resources.py`
- Modify: `src/midscene_ui_agent/infrastructure/config/resolver.py`
- Modify: `src/midscene_ui_agent/infrastructure/config/__init__.py`
- Modify: `src/midscene_ui_agent/application/nodes/config.py`
- Modify: `pyproject.toml`
- Move: `config/**` to `src/midscene_ui_agent/config/**`
- Move: `skills.lock.json` to `src/midscene_ui_agent/config/skills.lock.json`
- Test: `tests/unit/infrastructure/test_config_runtime.py`
- Test: `tests/unit/infrastructure/test_package_resources.py`

- [ ] **Step 1: Write failing tests for environment and point overrides**

```python
from midscene_ui_agent.infrastructure.config import ConfigResolver, parse_overrides


def test_environment_and_point_override_are_last(tmp_path, config_tree):
    resolved = ConfigResolver(tmp_path).resolve(
        platform="android",
        app="android.tencent-video",
        task="watch-free-series",
        environment="ci",
        overrides=parse_overrides([
            "loop.exit_conditions.max_runtime_seconds=12",
            "loop.operations.skip_ad.enabled=false",
        ]),
    )
    assert resolved["loop"]["exit_conditions"]["max_runtime_seconds"] == 12
    assert resolved["loop"]["operations"]["skip_ad"]["enabled"] is False


def test_unknown_override_path_is_rejected(tmp_path, config_tree):
    with pytest.raises(ValueError, match="unknown override path"):
        ConfigResolver(tmp_path).resolve(
            platform="android", app="android.tencent-video", task="watch-free-series",
            overrides=parse_overrides(["loop.not_a_field=1"]),
        )


def test_task_goal_prompt_builds_request_and_structured_goal_updates_loop(tmp_path, config_tree):
    configured = resolve_run_config(
        platform="android", app="android.tencent-video", task="watch-free-series",
        config_root=tmp_path, target_overrides={"device_id": "fake"},
    )
    assert configured.request.goal == "Open a free television series and start playback"
    assert configured.request.loop.operations["switch_episode"].params["require_free"] is True
```

- [ ] **Step 2: Verify RED**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/unit/infrastructure/test_config_runtime.py -v`

Expected: failure because environment and point-override APIs are missing.

- [ ] **Step 3: Implement deterministic override and resource resolution**

Add:

```python
def parse_overrides(items: list[str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"override must be key=value: {item}")
        path, raw = item.split("=", 1)
        value = json.loads(raw) if raw.strip() else ""
        cursor = result
        parts = path.split(".")
        for part in parts[:-1]:
            cursor = cursor.setdefault(part, {})
        cursor[parts[-1]] = value
    return result
```

If `json.loads` raises, use the raw string. Validate override paths against the merged mapping before applying them. Add optional environment loading after task. Use `importlib.resources.files("midscene_ui_agent").joinpath("config")` when `--config-root` is omitted.

Normalize task goals explicitly: `goal.prompt` becomes `AutomationRequest.goal`; structured values such as `goal.category` and `goal.require_free` are copied into the matching Loop operation params. Update every bundled task YAML to include a non-empty `goal.prompt` rather than inventing goal text at runtime.

Move the checked-in skill lock under package config so source and wheel runs use the same default. An explicit `--skills-lock` still overrides it. Declare package data in `pyproject.toml`:

```toml
[tool.setuptools.package-data]
midscene_ui_agent = ["config/**/*.yaml", "config/**/*.json"]
```

- [ ] **Step 4: Add and run wheel resource test**

The test builds a wheel into `tmp_path`, installs it into a temporary target with `pip --no-deps --target`, and asserts `default_config_root()/"defaults.yaml"` exists.

Run: `$env:PYTHONPATH='src'; python -m pytest tests/unit/infrastructure/test_config_runtime.py tests/unit/infrastructure/test_package_resources.py -v`

Expected: all pass.

- [ ] **Step 5: Commit**

```powershell
git add pyproject.toml config src/midscene_ui_agent/config src/midscene_ui_agent/infrastructure/config src/midscene_ui_agent/application/nodes/config.py tests/unit/infrastructure
git commit -m "feat: connect layered packaged configuration"
```

## Task 3: Establish the LangGraph Checkpointer and Main Graph Skeleton

**Files:**
- Create: `src/midscene_ui_agent/infrastructure/persistence/langgraph.py`
- Create: `src/midscene_ui_agent/application/graphs/__init__.py`
- Create: `src/midscene_ui_agent/application/graphs/automation.py`
- Create: `src/midscene_ui_agent/application/nodes/__init__.py`
- Create: `src/midscene_ui_agent/application/nodes/lifecycle.py`
- Test: `tests/unit/application/test_automation_graph.py`

- [ ] **Step 1: Write a failing graph topology test**

```python
def test_main_graph_runs_real_lifecycle_nodes(tmp_path):
    from midscene_ui_agent.application.graphs.automation import build_automation_graph
    from midscene_ui_agent.infrastructure.persistence.langgraph import sqlite_checkpointer

    calls = []
    graph = build_automation_graph(
        services={"prepare": lambda state: calls.append("prepare") or state,
                  "execute": lambda state: calls.append("execute") or state,
                  "finalize": lambda state: calls.append("finalize") or {**state, "status": "succeeded"}},
        checkpointer=sqlite_checkpointer(tmp_path / "graph.sqlite"),
    )
    result = graph.invoke(
        {"run_id": "r1", "mode": "live", "route": "single"},
        config={"configurable": {"thread_id": "r1"}},
    )
    assert calls == ["prepare", "execute", "finalize"]
    assert result["status"] == "succeeded"
```

- [ ] **Step 2: Verify RED**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/unit/application/test_automation_graph.py -v`

Expected: graph modules do not exist.

- [ ] **Step 3: Implement saver lifecycle and compiled graph**

`sqlite_checkpointer(path)` must return an entered `SqliteSaver` whose connection remains valid for graph lifetime. Wrap it in a small context-owning `CheckpointerHandle` with `saver` and `close()` instead of returning a context manager accidentally.

The main graph must use `StateGraph(AutomationGraphState)` with explicit nodes and conditional routing:

```python
builder.add_node("prepare_run", services.prepare)
builder.add_node("execute_route", services.execute)
builder.add_node("finalize_run", services.finalize)
builder.add_edge(START, "prepare_run")
builder.add_edge("prepare_run", "execute_route")
builder.add_edge("execute_route", "finalize_run")
builder.add_edge("finalize_run", END)
return builder.compile(checkpointer=checkpointer.saver)
```

No fallback graph is allowed when LangGraph import fails because LangGraph is a core dependency.

- [ ] **Step 4: Run graph and checkpoint tests**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/unit/application/test_automation_graph.py tests/test_checkpoint_graph.py tests/test_langgraph_compat.py -v`

Expected: all pass after replacing compatibility tests with real saver persistence assertions.

- [ ] **Step 5: Commit**

```powershell
git add src/midscene_ui_agent/application/graphs src/midscene_ui_agent/application/nodes src/midscene_ui_agent/infrastructure/persistence tests/unit/application/test_automation_graph.py tests/test_checkpoint_graph.py tests/test_langgraph_compat.py
git commit -m "feat: add durable LangGraph automation graph"
```

## Task 4: Expand the Platform Contract for Graph Execution

**Files:**
- Modify: `src/midscene_ui_agent/platforms/base.py`
- Modify: `src/midscene_ui_agent/platforms/_cli.py`
- Modify: all six files under `src/midscene_ui_agent/platforms/*/*.py`
- Create: `src/midscene_ui_agent/application/nodes/execution.py`
- Test: `tests/unit/platforms/test_platform_contract.py`

- [ ] **Step 1: Write failing platform contract tests**

```python
from midscene_ui_agent.platforms.registry import default_registry


def test_every_platform_supports_graph_runtime_protocol():
    for adapter in default_registry().values():
        assert callable(adapter.command)
        assert callable(adapter.execute_prompt)
        assert callable(adapter.observe)
        assert callable(adapter.verify_effect)
        assert callable(adapter.release)
```

Add a fake-runner test proving `execute_prompt` builds a Midscene `act` command and returns the command output without invoking subprocess directly in the adapter.

- [ ] **Step 2: Verify RED**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/unit/platforms/test_platform_contract.py -v`

Expected: missing graph runtime methods.

- [ ] **Step 3: Implement the protocol using injected CommandRunner**

Add methods with these stable signatures:

```python
class PlatformAdapter(ABC):
    def execute_prompt(self, prompt: str, context: ExecutionContext) -> OperationOutcome: ...
    def observe(self, context: ExecutionContext) -> Observation: ...
    def verify_effect(self, operation: str, operation_id: str, context: ExecutionContext) -> bool: ...
    def release(self, context: ExecutionContext) -> None: ...
```

`MidsceneCliAdapter` implements defaults through `CommandRunner` supplied in `ExecutionContext`. Platform subclasses only override unsupported or platform-specific behavior. Do not store live runner or request objects in graph state.

- [ ] **Step 4: Run platform and capability tests**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/unit/platforms/test_platform_contract.py tests/test_adapter_protocol.py tests/test_capabilities.py -v`

Expected: all pass with tests importing `platforms`, not `adapters`.

- [ ] **Step 5: Commit**

```powershell
git add src/midscene_ui_agent/platforms src/midscene_ui_agent/application/nodes/execution.py tests/unit/platforms tests/test_adapter_protocol.py tests/test_capabilities.py
git commit -m "feat: define graph-ready platform adapter protocol"
```

## Task 5: Migrate Single Operations to a LangGraph Subgraph

**Files:**
- Create: `src/midscene_ui_agent/application/graphs/single_operation.py`
- Modify: `src/midscene_ui_agent/application/graphs/automation.py`
- Modify: `src/midscene_ui_agent/application/nodes/execution.py`
- Modify: `src/midscene_ui_agent/application/workflows/orchestrator.py`
- Modify: `src/midscene_ui_agent/interfaces/api.py`
- Test: `tests/unit/application/test_single_operation_graph.py`

- [ ] **Step 1: Write failing operation sequence and failure-route tests**

```python
def test_run_operation_checkpoints_each_step(runtime):
    result = runtime.run(request(operation="run"))
    assert [step.phase for step in result.steps] == ["connect", "health_check", "run", "screenshot"]
    assert runtime.completed_nodes("r1") == ["connect", "health_check", "run", "screenshot"]


def test_failed_step_routes_to_reporting_without_later_ui_actions(runtime):
    runtime.adapter.fail_on = "run"
    result = runtime.run(request(operation="run"))
    assert result.status == "failed"
    assert runtime.adapter.calls == ["connect", "health_check", "run"]
    assert result.error
```

- [ ] **Step 2: Verify RED**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/unit/application/test_single_operation_graph.py -v`

Expected: current orchestrator bypasses LangGraph and no completed-node checkpoints exist.

- [ ] **Step 3: Implement the operation subgraph and thin runtime entrypoint**

Build dynamic steps from the operation, but keep graph node names stable by using a repeated `execute_step` node and state cursor:

```python
def next_step(state):
    if state.get("error") or state["step_index"] >= len(state["operation_steps"]):
        return "finish"
    return "execute"
```

The orchestrator becomes responsible only for constructing runtime dependencies, invoking the compiled graph with `thread_id=run_id`, and mapping final state to `AutomationResult`.

- [ ] **Step 4: Run single-operation regression suite**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/unit/application/test_single_operation_graph.py tests/test_result_events.py tests/test_vitest_lifecycle.py tests/test_runner_unicode.py -v`

Expected: all pass.

- [ ] **Step 5: Commit**

```powershell
git add src/midscene_ui_agent/application/graphs/single_operation.py src/midscene_ui_agent/application/graphs/automation.py src/midscene_ui_agent/application/nodes/execution.py src/midscene_ui_agent/application/workflows/orchestrator.py src/midscene_ui_agent/interfaces/api.py tests
git commit -m "feat: execute single operations through LangGraph"
```

## Task 6: Implement the Loop LangGraph Subgraph

**Files:**
- Create: `src/midscene_ui_agent/application/graphs/loop.py`
- Modify: `src/midscene_ui_agent/application/loop/scheduler.py`
- Modify: `src/midscene_ui_agent/application/loop/selector.py`
- Modify: `src/midscene_ui_agent/domain/policies/exit.py`
- Create: `src/midscene_ui_agent/domain/policies/retry.py`
- Test: `tests/unit/application/test_loop_graph.py`
- Test: `tests/unit/domain/test_loop_policies.py`

- [ ] **Step 1: Write failing tests for configured behavior**

Cover all omitted runtime semantics:

```python
def test_operation_uses_its_timeout_and_retries(loop_runtime):
    loop_runtime.adapter.fail("skip_ad", times=2)
    result = loop_runtime.run(plan(skip_ad={"max_attempts": 3, "timeout_seconds": 4}))
    assert result.operations["skip_ad"]["attempts"] == 3
    assert loop_runtime.timeouts_for("skip_ad") == [4, 4, 4]


@pytest.mark.parametrize("field,value,reason", [
    ("max_switches", 2, "max_switches"),
    ("max_scrolls", 2, "max_scrolls"),
    ("target_count", 2, "target_count"),
])
def test_count_limits_route_to_exact_exit_reason(loop_runtime, field, value, reason):
    result = loop_runtime.run(plan(exit_conditions={field: value}))
    assert result.exit_reason == reason


def test_login_required_exits_without_consuming_failure_budget(loop_runtime):
    loop_runtime.adapter.respond("login required")
    result = loop_runtime.run(plan())
    assert result.exit_reason == "login_required"
    assert result.state["consecutive_failures"] == 0
```

Also test startup/on_popup/on_ad/on_stall/at_runtime/after_operation triggers and configurable priority.

- [ ] **Step 2: Verify RED**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/unit/application/test_loop_graph.py tests/unit/domain/test_loop_policies.py -v`

Expected: current controller ignores timeout, retry, count limits and triggers.

- [ ] **Step 3: Implement deterministic nodes and conditional edges**

Nodes must be pure except `execute_operation` and evidence nodes. Use:

```python
builder.add_node("observe_ui", observe_ui)
builder.add_node("schedule_operations", schedule_operations)
builder.add_node("select_operation", select_operation)
builder.add_node("execute_operation", execute_operation)
builder.add_node("record_evidence", record_evidence)
builder.add_node("evaluate_exit", evaluate_exit)
builder.add_node("summarize_loop", summarize_loop)
builder.add_conditional_edges("evaluate_exit", route_after_evaluation, {
    "continue": "observe_ui",
    "retry": "execute_operation",
    "exit": "summarize_loop",
})
```

Use the operation configuration for timeout and attempts. Pass all count limits to `ExitPolicy`. Map handler reasons directly to normalized `ExitReason` values.

- [ ] **Step 4: Run Loop tests and existing fake integration tests**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/unit/application/test_loop_graph.py tests/unit/domain/test_loop_policies.py tests/unit/application/test_loop_scheduler.py tests/unit/application/test_loop_operations.py tests/unit/application/test_loop_integration_fake.py -v`

Expected: all pass.

- [ ] **Step 5: Commit**

```powershell
git add src/midscene_ui_agent/application/graphs/loop.py src/midscene_ui_agent/application/loop src/midscene_ui_agent/domain/policies tests/unit/application tests/unit/domain
git commit -m "feat: run Loop Engineering as a LangGraph subgraph"
```

## Task 7: Implement Fingerprinted Resume and Idempotency

**Files:**
- Create: `src/midscene_ui_agent/domain/policies/resume.py`
- Modify: `src/midscene_ui_agent/application/graphs/automation.py`
- Modify: `src/midscene_ui_agent/application/graphs/loop.py`
- Modify: `src/midscene_ui_agent/infrastructure/config/resolver.py`
- Test: `tests/unit/application/test_graph_resume.py`

- [ ] **Step 1: Write failing resume tests**

```python
def test_resume_skips_completed_single_operation(resumable_runtime):
    resumable_runtime.interrupt_after("health_check")
    resumable_runtime.run(request(run_id="r1"))
    result = resumable_runtime.resume("r1", request(run_id="r1"))
    assert result.status == "succeeded"
    assert resumable_runtime.adapter.count("connect") == 1
    assert resumable_runtime.adapter.count("health_check") == 1


def test_resume_rejects_changed_fingerprint_before_connect(resumable_runtime):
    resumable_runtime.seed_checkpoint("r1", config_hash="old")
    result = resumable_runtime.resume("r1", request(run_id="r1", goal="changed"))
    assert result.status == "resume_invalid"
    assert resumable_runtime.adapter.calls == []


def test_resume_observes_non_idempotent_effect_before_retry(resumable_runtime):
    resumable_runtime.seed_pending("r1", operation="switch_episode", operation_id="op-7")
    resumable_runtime.adapter.effect_exists = True
    resumable_runtime.resume("r1", loop_request(run_id="r1"))
    assert resumable_runtime.adapter.count("switch_episode") == 0
```

- [ ] **Step 2: Verify RED**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/unit/application/test_graph_resume.py -v`

Expected: `resume` is currently unused and no graph state validation exists.

- [ ] **Step 3: Implement fingerprint and idempotency policies**

```python
IDEMPOTENT_OPERATIONS = {"connect", "health_check", "screenshot", "assert", "check_playback", "report_snapshot"}


def validate_resume(expected: RunFingerprints, actual: RunFingerprints) -> None:
    if expected != actual:
        raise ResumeInvalid("runtime fingerprint mismatch")


def resume_action(operation: str, effect_verified: bool) -> Literal["retry", "complete"]:
    if operation in IDEMPOTENT_OPERATIONS:
        return "retry"
    return "complete" if effect_verified else "retry"
```

Validate fingerprints before `connect_platform`. Use graph checkpoint history to derive completed/pending nodes; do not add another state file.

- [ ] **Step 4: Run resume and checkpoint tests**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/unit/application/test_graph_resume.py tests/test_sqlite_checkpoint.py tests/test_checkpoint_graph.py -v`

Expected: all pass.

- [ ] **Step 5: Commit**

```powershell
git add src/midscene_ui_agent/domain/policies/resume.py src/midscene_ui_agent/application/graphs src/midscene_ui_agent/infrastructure/config/resolver.py tests/unit/application/test_graph_resume.py tests/test_sqlite_checkpoint.py tests/test_checkpoint_graph.py
git commit -m "feat: add fingerprinted graph resume semantics"
```

## Task 8: Connect Skill Lock, Evidence and Final Reporting

**Files:**
- Modify: `src/midscene_ui_agent/application/nodes/lifecycle.py`
- Modify: `src/midscene_ui_agent/application/nodes/execution.py`
- Create: `src/midscene_ui_agent/application/nodes/reporting.py`
- Modify: `src/midscene_ui_agent/infrastructure/evidence/collector.py`
- Modify: `src/midscene_ui_agent/infrastructure/reporting/reports.py`
- Test: `tests/unit/application/test_lifecycle_nodes.py`
- Test: `tests/unit/infrastructure/test_graph_reports.py`

- [ ] **Step 1: Write failing lifecycle tests**

```python
def test_skill_lock_failure_happens_before_platform_connect(runtime):
    runtime.skill_lock.write_text("{}", encoding="utf-8")
    result = runtime.run(request())
    assert result.status == "failed"
    assert "skill lock mismatch" in result.error
    assert runtime.adapter.calls == []


def test_evidence_is_captured_before_and_after_operation(runtime):
    result = runtime.run(request(operation="screenshot"))
    assert result.status == "succeeded"
    assert [e.phase for e in runtime.evidence] == ["before", "after"]


def test_manifest_contains_graph_metadata(runtime):
    result = runtime.run(request())
    manifest = json.loads((runtime.run_root / "manifest.json").read_text())
    assert manifest["thread_id"] == result.run_id
    assert manifest["fingerprints"]["config_hash"]
    assert manifest["graph_phase"] == "finalize_run"
```

- [ ] **Step 2: Verify RED**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/unit/application/test_lifecycle_nodes.py tests/unit/infrastructure/test_graph_reports.py -v`

Expected: skill verification and graph evidence are not connected.

- [ ] **Step 3: Implement lifecycle ordering and report metadata**

The main graph edge order must be `prepare_run -> verify_skill_lock -> connect_platform`. Evidence nodes call `EvidenceCollector` with stable filenames containing operation_id. Manifest writes only hash values and artifact paths, never secrets or live objects.

`verify_skill_lock` obtains the skill root from the explicit runtime option or `MIDSCENE_SKILLS_ROOT`. Supplying a lock without a valid root is a configuration error. Hash only the selected platform's required files during a run, while the separate `skills verify` command continues to verify the complete catalog.

`finalize_run` must attempt release according to `disconnect_on_exit` and `close_browser_on_exit`, append release failures to `secondary_errors`, write reports, then close owned saver/runner resources.

- [ ] **Step 4: Run lifecycle, evidence and report tests**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/unit/application/test_lifecycle_nodes.py tests/unit/infrastructure/test_graph_reports.py tests/test_result_events.py tests/unit/infrastructure/test_loop_reports.py -v`

Expected: all pass.

- [ ] **Step 5: Commit**

```powershell
git add src/midscene_ui_agent/application/nodes src/midscene_ui_agent/infrastructure/evidence src/midscene_ui_agent/infrastructure/reporting tests
git commit -m "feat: enforce skill lock evidence and graph reporting"
```

## Task 9: Wire Configuration and Resume Through CLI and API

**Files:**
- Modify: `src/midscene_ui_agent/interfaces/cli.py`
- Modify: `src/midscene_ui_agent/interfaces/api.py`
- Modify: `src/midscene_ui_agent/application/workflows/orchestrator.py`
- Test: `tests/unit/interfaces/test_cli_runtime.py`
- Test: `tests/unit/interfaces/test_api_runtime.py`

- [ ] **Step 1: Write failing CLI/API tests**

```python
def test_cli_builds_request_from_task_config(runner, config_root):
    result = runner.invoke(app, [
        "run", "--platform", "android", "--app", "android.tencent-video",
        "--task", "watch-free-series", "--config-root", str(config_root),
        "--skills-root", str(skills_root), "--skills-lock", str(lock_file),
        "--device-id", "fake", "--mode", "plan",
        "--override", "loop.exit_conditions.max_runtime_seconds=12",
    ])
    assert result.exit_code == 0
    assert "planned" in result.stdout


def test_cli_resume_requires_existing_run_id(runner, config_root):
    result = runner.invoke(app, ["run", "--resume", "missing", "--config-root", str(config_root)])
    assert result.exit_code != 0
    assert "checkpoint" in result.stdout.lower()
```

API tests exercise both `run(AutomationRequest(...))` and `run_configured(platform=..., app=..., task=...)`.

- [ ] **Step 2: Verify RED**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/unit/interfaces/test_cli_runtime.py tests/unit/interfaces/test_api_runtime.py -v`

Expected: new options and configured API do not exist.

- [ ] **Step 3: Implement explicit CLI and API entrypoints**

Keep `run(request)` for direct Python use. Add:

```python
def run_configured(*, platform: str, app: str, task: str,
                   environment: str | None = None,
                   overrides: list[str] | None = None,
                   config_root: str | Path | None = None,
                   skills_root: str | Path | None = None,
                   skills_lock: str | Path | None = None,
                   target_overrides: dict[str, Any] | None = None,
                   resume_id: str | None = None) -> AutomationResult:
    ...
```

CLI `--goal` becomes optional only when task configuration supplies a goal. `--resume` reuses checkpoint request metadata unless explicit overrides are supplied, in which case fingerprint validation decides validity.

- [ ] **Step 4: Run interface and workflow tests**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/unit/interfaces tests/test_workflow_routes.py tests/unit/application/test_loop_controller.py -v`

Expected: all pass after replacing controller assertions with graph results.

- [ ] **Step 5: Commit**

```powershell
git add src/midscene_ui_agent/interfaces src/midscene_ui_agent/application/workflows/orchestrator.py tests/unit/interfaces tests/test_workflow_routes.py tests/unit/application/test_loop_controller.py
git commit -m "feat: expose configured and resumable runtime entrypoints"
```

## Task 10: Add Test-Generation Contracts and Deterministic Renderers

**Files:**
- Create: `src/midscene_ui_agent/domain/contracts/test_cases.py`
- Modify: `src/midscene_ui_agent/domain/contracts/__init__.py`
- Create: `src/midscene_ui_agent/application/generation/__init__.py`
- Create: `src/midscene_ui_agent/application/generation/contracts.py`
- Create: `src/midscene_ui_agent/application/generation/renderers.py`
- Test: `tests/unit/application/test_script_renderers.py`
- Test: `tests/unit/domain/test_test_case_contracts.py`

- [ ] **Step 1: Write failing contract and renderer tests**

```python
def test_test_case_rejects_step_without_action():
    with pytest.raises(ValidationError):
        TestCaseSpec.model_validate({"name": "login", "platform": "browser", "steps": [{"action": ""}]})


def test_python_renderer_is_deterministic():
    spec = TestCaseSpec(
        name="open_example",
        platform="browser",
        target={"url": "https://example.com"},
        steps=[TestStepSpec(action="run", prompt="Verify the page title")],
        assertions=["Page title is visible"],
    )
    first = PythonTestRenderer().render(spec)
    second = PythonTestRenderer().render(spec)
    assert first == second
    compile(first, "generated_test.py", "exec")
    assert "AutomationRequest" in first
```

- [ ] **Step 2: Verify RED**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/unit/domain/test_test_case_contracts.py tests/unit/application/test_script_renderers.py -v`

Expected: contracts and renderers do not exist.

- [ ] **Step 3: Implement stable protocols and renderers**

```python
class TestScriptGenerator(Protocol):
    def generate(self, requirement: str, capabilities: Mapping[str, Any]) -> TestCaseSpec: ...


class TestScriptRenderer(Protocol):
    format: str
    def render(self, spec: TestCaseSpec) -> str: ...
```

Use `json.dumps(..., sort_keys=True, ensure_ascii=False)` for deterministic literals. Python output imports public interfaces only. YAML output uses `yaml.safe_dump(..., sort_keys=False, allow_unicode=True)`.

- [ ] **Step 4: Run generation tests**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/unit/domain/test_test_case_contracts.py tests/unit/application/test_script_renderers.py -v`

Expected: all pass.

- [ ] **Step 5: Commit**

```powershell
git add src/midscene_ui_agent/domain/contracts src/midscene_ui_agent/application/generation tests/unit/domain/test_test_case_contracts.py tests/unit/application/test_script_renderers.py
git commit -m "feat: define test generation contracts and renderers"
```

## Task 11: Remove Legacy Facades and Dead Runtime Code

**Files:**
- Delete: `src/midscene_ui_agent/adapters/`
- Delete: `src/midscene_ui_agent/application/workflows/graph.py`
- Delete: `src/midscene_ui_agent/application/loop/controller.py`
- Delete: `src/midscene_ui_agent/infrastructure/persistence/loop_checkpoint.py`
- Delete: `src/midscene_ui_agent/domain/policies/safety.py`
- Modify: package `__init__.py` files and affected tests
- Test: `tests/unit/test_package_boundaries.py`

- [ ] **Step 1: Change boundary tests to require canonical imports**

```python
def test_legacy_adapter_namespace_is_removed():
    assert importlib.util.find_spec("midscene_ui_agent.adapters") is None


def test_runtime_imports_only_canonical_graph_and_platform_modules():
    from midscene_ui_agent.application.graphs.automation import build_automation_graph
    from midscene_ui_agent.platforms.android import AndroidAdapter
    assert build_automation_graph and AndroidAdapter
```

- [ ] **Step 2: Verify RED**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/unit/test_package_boundaries.py -v`

Expected: legacy namespace still exists.

- [ ] **Step 3: Delete facades and update every import**

Run `rg -n "midscene_ui_agent\.adapters|workflows\.graph|LoopCheckpoint|LoopWorkflow|classify_risk" src tests` and migrate each legitimate caller before deleting files. No compatibility import remains.

- [ ] **Step 4: Run import and compile verification**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/unit/test_package_boundaries.py tests/test_adapter_protocol.py tests/test_langgraph_compat.py -v`

Run: `python -m compileall src -q`

Expected: tests pass and compile exits 0.

- [ ] **Step 5: Commit**

```powershell
git add -A src tests
git commit -m "refactor: remove legacy runtime and adapter facades"
```

## Task 12: Add Quality Gates, Documentation and Integration Coverage

**Files:**
- Modify: `pyproject.toml`
- Create: `.github/workflows/ci.yml`
- Modify: `README.md`
- Modify: `docs/使用手册.md`
- Modify: `docs/loop-runbook.md`
- Modify: `docs/diagrams/*.puml`
- Modify: `tests/integration/test_browser_loop.py`
- Modify: `tests/integration/test_android_loop.py`

- [ ] **Step 1: Add failing distribution smoke test**

Create `tests/distribution/test_installed_cli.py` that receives an installed-wheel target through `UI_AGENT_WHEEL_SITE`, launches `python -m midscene_ui_agent.interfaces.cli --help`, and validates that `--app`, `--task`, `--override` and `--resume` are documented.

Run: `$env:PYTHONPATH='src'; python -m pytest tests/distribution/test_installed_cli.py -v`

Expected: failure until wheel data and CLI options are complete.

- [ ] **Step 2: Configure tooling and CI**

Add:

```toml
[project.optional-dependencies]
dev = ["pytest==9.1.1", "ruff>=0.12,<1", "mypy>=1.16,<2", "build>=1.2,<2"]

[tool.ruff]
target-version = "py311"
line-length = 120

[tool.mypy]
python_version = "3.11"
packages = ["midscene_ui_agent"]
```

CI matrix uses Python 3.11 and 3.12 and executes compileall, pytest, Ruff, mypy and wheel build. A final job installs the wheel with dependencies and runs the CLI smoke test.

- [ ] **Step 3: Update documentation and PlantUML**

Document the real config CLI, graph nodes, resume rules, skill lock prerequisite, artifact layout, direct-execution safety implications and test-generation contracts. Remove claims that are not covered by automated or opt-in integration tests. Ensure all Markdown and YAML files are UTF-8 without BOM or mojibake.

- [ ] **Step 4: Extend opt-in integration tests**

Browser and Android tests must each cover one interruption/resume path using public/free content. They remain skipped unless `UI_AGENT_RUN_INTEGRATION=1`, model configuration exists and the required target is available.

- [ ] **Step 5: Run full verification**

```powershell
$env:PYTHONPATH='src'
python -m compileall src -q
python -m pytest -q
python -m ruff check src tests
python -m mypy src/midscene_ui_agent
python -m build
```

Expected: all commands exit 0; integration tests may skip only for documented external prerequisites.

- [ ] **Step 6: Commit**

```powershell
git add pyproject.toml .github README.md docs tests/integration tests/distribution
git commit -m "chore: add runtime quality gates and documentation"
```

## Final Verification Checklist

- [ ] Re-read `docs/superpowers/specs/2026-08-02-langgraph-runtime-hardening-design.md` and map each acceptance criterion to a passing test.
- [ ] Confirm `rg -n "midscene_ui_agent\.adapters|needs_confirmation|approval_required|--approve" src tests docs` has no runtime or documentation hits.
- [ ] Confirm `rg -n "resume: bool|resume_id" src` shows values consumed by graph restore logic, not merely passed through.
- [ ] Confirm every `OperationConfig` runtime field has a focused test.
- [ ] Confirm wheel contents include `midscene_ui_agent/config/defaults.yaml` and both schema files.
- [ ] Run the full verification commands from Task 12 with fresh output.
- [ ] Inspect `git status --short` and ensure only intentional changes remain.
