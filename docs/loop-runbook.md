# Loop Engineering 运行手册

## 运行模型

Loop 是嵌入主 LangGraph 的子图。每个 tick 依次观察 UI、计算到期操作、按优先级选择一个操作、执行并收集前后证据、更新计数和退出条件。只有 UI 观察、操作执行和证据采集具有副作用；调度与退出判断保持确定性，便于 checkpoint 恢复和测试。

可配置操作包括 `dismiss_popup`、`skip_ad`、`play_video`、`switch_episode`、`scroll_feed`、`check_playback`、`recover_playback`、`screenshot`、`assert_state`、`navigate_back` 和 `report_snapshot`。

每个操作均可单独配置：

```yaml
operations:
  switch_episode:
    enabled: true
    interval_seconds: 300
    timeout_seconds: 30
    max_attempts: 3
    priority: 50
    startup: false
    on_popup: false
    on_ad: false
    on_stall: false
    at_runtime: 300
    after_operation: [check_playback]
    strategy: next_episode
    params:
      require_free: true
```

触发条件可组合；同一 tick 中按 `priority` 选择。执行失败会在该操作的 `max_attempts` 内重试，并受 `timeout_seconds` 限制。非幂等操作恢复前先调用效果验证，已经生效时不会重复切集或滑动。

## 退出与资源释放

支持最大运行时间、最大切集数、最大滑动数、目标数、连续失败、无进展、取消、设备不可达、模型错误、登录界面、购买界面和无法处理的弹窗。退出后依据 `disconnect_on_exit` 或 `close_browser_on_exit` 释放资源；释放失败写入 `secondary_errors`，不覆盖主失败原因。

登录、支付、购买、会员、密码、手机号或提交账户数据不得出现在弹窗/广告 prompt 中，配置模型会直接拒绝。运行时识别到登录或购买阻塞时按退出条件结束，不会尝试绕过。

## 配置运行

```powershell
midscene-ui-agent run --platform android --app android.tencent-video --task watch-free-series `
  --device-id AGYJUT3628001141 --mode live `
  --override "loop.operations.switch_episode.interval_seconds=120" `
  --override "loop.exit_conditions.max_runtime_seconds=900"
```

优先级为 package defaults、platform、app、task、environment、CLI/API override。未知 override 路径、错误类型、selector 身份变化和不满足 Loop schema 的值会在访问 UI 前失败。

## 中断恢复

```powershell
midscene-ui-agent run --resume <run_id> --report-dir ./artifacts
```

恢复使用 `run_id` 作为 LangGraph `thread_id`。纯恢复从 SQLite checkpoint 读取请求；显式 URL、device ID、goal 或 skill lock 会重新计算对应指纹。若要修改 environment 或任意 `--override`，必须同时提供完整的 `--platform --app --task`，由配置解析器生成新指纹。任何不匹配都会返回 `resume_invalid`，且不会连接设备或浏览器。

## 诊断

- `artifacts/langgraph.sqlite`：主图和子图 checkpoint。
- `artifacts/checkpoints.sqlite`：最终结果索引。
- `artifacts/<run_id>/manifest.json`：thread ID、图阶段、指纹和产物清单。
- `artifacts/<run_id>/events.jsonl`：脱敏事件。
- `artifacts/<run_id>/evidence/`：带稳定 operation ID 的前后证据。
- `artifacts/<run_id>/work/`：Midscene 原生日志、截图与 HTML 报告。

真实集成验证：

```powershell
$env:UI_AGENT_RUN_INTEGRATION='1'
python -m pytest tests/integration/test_browser_loop.py -v
$env:UI_AGENT_ANDROID_DEVICE='AGYJUT3628001141'
python -m pytest tests/integration/test_android_loop.py -v
```

两个测试都会先制造一次进程级中断，再用相同 run ID 恢复。缺少模型、Chrome、ADB 或设备时明确跳过。
