# Midscene UI Agent (Python)

基于 Python、LangGraph 和官方 `@midscene/*@1` CLI 的统一多平台 UI 自动化运行时。第一版接入 Browser、Computer、Android、iOS、HarmonyOS 与 Vitest E2E，支持单次操作、可配置 Loop Engineering、SQLite checkpoint 恢复、技能锁校验、证据与报告输出，以及未来测试脚本生成的稳定契约。

## 部署

必须安装 Python 3.11+、Node.js 18+ 和 npm/npx。无需在项目中单独安装 Midscene；运行时通过 `npx -y @midscene/<platform>@1` 获取固定主版本的官方 CLI。首次使用需要访问 npm registry。

```powershell
cd ui-agent-python
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

在 `.env` 中配置 `MIDSCENE_MODEL_API_KEY`、`MIDSCENE_MODEL_NAME`、`MIDSCENE_MODEL_BASE_URL` 和 `MIDSCENE_MODEL_FAMILY`。Android 还需 `adb`，iOS 需 WDA，HarmonyOS 需 `hdc`，Computer 需可达的 RDP，Vitest E2E 需 pnpm。

## 快速使用

默认 `--mode plan` 只生成计划，不访问 UI；`--mode live` 才执行真实操作。系统没有审批步骤，live 模式下操作会直接执行。

```powershell
# 直接请求
midscene-ui-agent run --platform browser --url https://example.com --goal "验证页面标题" --mode live
midscene-ui-agent run --platform android --device-id AGYJUT3628001141 --goal "截取当前屏幕" --operation screenshot --mode live

# 使用内置分层配置运行 Loop
midscene-ui-agent run --platform android --app android.tencent-video --task watch-free-series `
  --device-id AGYJUT3628001141 --mode live `
  --override "loop.exit_conditions.max_runtime_seconds=600"

# 恢复同一 run_id
midscene-ui-agent run --resume <run_id> --report-dir ./artifacts
```

Python 入口：

```python
from midscene_ui_agent.domain.contracts import AutomationRequest
from midscene_ui_agent.interfaces.api import run, run_configured, resume_run

result = run(AutomationRequest(
    platform="browser",
    target={"url": "https://example.com"},
    goal="验证页面标题",
    mode="live",
))
```

## 配置与产物

默认配置作为 package data 位于 `src/midscene_ui_agent/config/`，按 `defaults -> platform -> app -> task -> environment -> --override` 合并。自定义配置使用 `--config-root`。技能校验需同时提供 `--skills-root` 和 `--skills-lock`；只提供锁文件会被拒绝。

运行级 checkpoint 位于 `artifacts/langgraph.sqlite`，结果位于 `artifacts/<run_id>/`，包括 `result.json`、`manifest.json`、`events.jsonl`、`evidence/` 和 `work/`。恢复时配置、应用、Loop、skill lock 或目标指纹不一致会在连接 UI 前返回 `resume_invalid`。

完整部署、API、Loop 配置、恢复、报告与扩展说明见 [docs/使用手册.md](docs/使用手册.md)，Loop 运维要点见 [docs/loop-runbook.md](docs/loop-runbook.md)，架构图见 [docs/diagrams/README.md](docs/diagrams/README.md)。

## 验证

```powershell
python -m compileall src -q
python -m pytest -q
python -m ruff check src tests
python -m mypy src/midscene_ui_agent
python -m build
```

真实 Web/Android 测试默认跳过。显式设置 `UI_AGENT_RUN_INTEGRATION=1` 后才会操作 Chrome 或已连接设备；测试仅使用公开内容，不执行登录、购买或账户变更。
