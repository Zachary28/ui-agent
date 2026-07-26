# Loop Engineering Runbook

Configuration is layered as `config/defaults.yaml` → platform → app profile → task → CLI/API overrides. Keep credentials as environment-variable names only; never put secrets, cookies, passwords, phone numbers, or WDA sessions in YAML, checkpoints, events, or reports.

Each operation can override its interval, timeout, retry limit, priority, and trigger. Popup/ad operations are limited to close, skip, later, or back. Login, purchase, payment, membership, or account-change screens terminate the loop for manual handling.

The loop exits on runtime, switch/scroll/target limits, cancellation, repeated failures, no progress, device loss, or login/purchase blockers. Resume requires matching run, target, profile, configuration, loop-plan, and skill-lock fingerprints; mismatches return `RESUME_INVALID`.

Each run writes `artifacts/<run_id>/` with result, manifest, events, loop plan, checkpoint, screenshots, command stdout/stderr, native Midscene HTML, and converted reports when available.

```powershell
$env:UI_AGENT_RUN_INTEGRATION='1'
cd ui-agent-python
.venv\Scripts\python.exe -m pytest tests/integration/test_browser_loop.py -v
$env:PATH='D:\program\scrcpy-win64-v4.1;'+$env:PATH
.venv\Scripts\python.exe -m pytest tests/integration/test_android_loop.py -v
```

Integration tests skip explicitly when Chrome, model configuration, adb, or device `AGYJUT3628001141` is unavailable. Real tests must use public/free content and must not perform login, payment, membership, or account mutations.
