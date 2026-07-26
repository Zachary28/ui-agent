# Midscene UI Agent (Python)

统一的 Python/LangGraph 入口，调用官方 `@midscene/*@1` CLI，覆盖 Browser、Computer、Android、iOS、HarmonyOS 和 Vitest Midscene E2E。

## 部署

需要 Python 3.11+、Node.js 18+、npm/npx；Vitest 还需要 pnpm。安装：

```powershell
cd ui-agent-python
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

在 `.env` 中配置 `MIDSCENE_MODEL_API_KEY`、`MIDSCENE_MODEL_NAME`、`MIDSCENE_MODEL_BASE_URL`、`MIDSCENE_MODEL_FAMILY`，并确保对应平台的 ADB、WDA、HDC、RDP 或浏览器调试端点可用。

## 使用

默认 `plan` 模式只生成计划；执行真实操作时使用 `--mode live`，高风险操作需要人工审批。

```powershell
midscene-ui-agent run --platform browser --url https://example.com --goal "verify the page is loaded"
midscene-ui-agent run --platform computer --goal "take a screenshot"
midscene-ui-agent run --platform android --device-id emulator-5554 --goal "open settings"
midscene-ui-agent run --platform ios --goal "open settings"
midscene-ui-agent run --platform harmony --device-id 0123456789ABCDEF --goal "open settings"
midscene-ui-agent run --platform vitest_e2e --goal "test login"
```

运行结果写入 `artifacts/<run_id>/plan.json` 或 `result.json`。生产环境应固定 `skills.lock.json`，并在运行前校验技能文件哈希；不要把 API key、Cookie、WDA session 或 HTTP header 值写入日志。

## Loop Engineering

Use the layered files under `config/` and `docs/loop-runbook.md` for repeated
playback, popup/ad dismissal, episode switching, short-video scrolling, resume,
exit conditions, artifacts, and gated Web/Android verification. Every operation
has an independently configurable interval.
