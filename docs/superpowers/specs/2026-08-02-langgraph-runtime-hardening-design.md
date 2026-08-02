# LangGraph 运行时完善与测试生成扩展设计

## 1. 目标

本次改造修复当前 UI Agent 运行时中已经定义但未接入、文档承诺但实际不生效的能力，并将运行、循环、恢复统一迁移为真正的 LangGraph 工作流。

本次交付包括：

- 接通 defaults、platform、app、task、environment 和运行时 override 六层配置。
- 使用 LangGraph 编排单次任务、Loop Engineering、失败重试、退出和恢复。
- 使每个 Loop 操作的间隔、超时、重试次数和触发条件真实生效。
- 支持单次任务和 Loop 的持久化恢复及配置指纹校验。
- 接入技能锁校验、结构化事件、前后证据和脱敏日志。
- 清理重复兼容层和未接线模块。
- 建立 CI、静态检查、wheel 构建及安装验证。
- 定义未来测试脚本生成所需的领域协议和确定性 renderer，不在本次调用模型生成脚本。

所有 UI 操作继续直接执行，不引入审批节点或人工确认流程。

## 2. LangGraph 决策

采用全量 LangGraph：主任务、单次操作、循环执行、恢复，以及未来的测试脚本生成都以图或子图实现。LangGraph 和 SQLite checkpointer 保持核心依赖。

选择该方案的原因：

- 后续测试脚本生成需要多阶段处理、条件分支、试运行和自动修复。
- 单次执行和长期 Loop 可以共享持久化、错误路由和报告节点。
- checkpoint 能够提供统一的恢复模型，避免维护并行的 JSON、SQLite 和自定义 Loop checkpoint。
- 节点边界可以把平台操作、策略判断和基础设施解耦，便于独立测试。

约束：LangGraph 只负责状态转换和节点调度。ADB、CDP、WDA、HDC、RDP 和 Midscene CLI 参数构造仍由平台适配器负责，领域层不依赖 LangGraph 或平台实现。

## 3. 图结构

### 3.1 主图

`AutomationGraph` 包含以下节点：

1. `load_config`：解析分层配置并应用运行时覆盖。
2. `validate_request`：构造和校验强类型请求、LoopPlan 与指纹。
3. `prepare_run`：创建 artifact 目录、事件流和运行元数据。
4. `verify_skill_lock`：在连接设备前校验技能锁。
5. `connect_platform`：创建适配器并执行连接和健康检查。
6. `route_operation`：路由到 plan、单次操作、Loop 或未来测试生成子图。
7. `collect_reports`：发现和转换 Midscene 原生报告。
8. `finalize_run`：写入 result、manifest、最终 checkpoint 并按策略释放资源。

主图条件边必须覆盖成功、可重试错误、不可重试错误、配置错误、恢复无效和取消。

### 3.2 单次操作子图

单次操作子图将现有顺序命令拆成可恢复节点：

`prepare_operation -> capture_before -> execute -> capture_after -> record_result`

`run` 操作仍按 `connect -> health_check -> run -> screenshot` 的业务顺序执行，但每一步独立提交 checkpoint。恢复时跳过已成功提交的节点。

### 3.3 Loop 子图

Loop 子图为：

`restore_state -> observe_ui -> schedule_operations -> select_operation -> execute_operation -> record_evidence -> evaluate_exit`

`evaluate_exit` 通过条件边路由到：

- `observe_ui`：继续下一 tick。
- `execute_operation`：同一操作重试。
- `summarize_loop`：正常或异常退出。

选择优先级默认为：弹窗关闭、广告跳过、播放恢复、播放检查、切换剧集、短视频滑动、截图、报告快照。配置中的 `priority` 可覆盖默认优先级。

### 3.4 未来测试生成子图

本次只定义接口，未来子图预留以下阶段：

`parse_requirement -> generate_spec -> validate_spec -> render_script -> dry_run -> repair_or_finish`

运行时只消费经过验证的 `TestCaseSpec`，不直接依赖具体模型或 prompt。

## 4. 配置模型

CLI 新增：

- `--config-root`
- `--app`
- `--task`
- `--environment`
- 可重复的 `--override key=value`
- `--skills-lock`
- `--skills-root`（也可由 `MIDSCENE_SKILLS_ROOT` 提供）
- 保留并实现 `--resume <run_id>`

合并顺序固定为：

`defaults -> platform -> app profile -> task -> environment -> CLI/API override`

运行时 override 使用点路径，例如 `loop.operations.skip_ad.interval_seconds=2`。值先按 JSON 解析，解析失败时作为字符串。未知字段由 Pydantic 的 `extra="forbid"` 拒绝。

解析结果为 `ResolvedRunConfig`：

- `request: AutomationRequest`
- `loop_plan: LoopPlan | None`
- `config_hash`
- `profile_hash`
- `loop_plan_hash`
- `skill_lock_hash`
- `target_fingerprint`

任务配置中的目标统一使用 `goal.prompt` 作为传给 Midscene 的自然语言目标；`goal.category`、`goal.require_free` 等结构化字段转换为 Loop 操作参数。旧任务文件在迁移时补齐 `goal.prompt`，不在运行时隐式猜测目标文本。

所有配置文件和 JSON schema 必须作为 Python package data 打入 wheel。源代码运行和 wheel 安装后的默认配置定位规则必须一致。

## 5. 状态与恢复

### 5.1 状态模型

`AutomationGraphState` 保存：

- run_id、thread_id、请求和解析后的配置。
- 当前阶段、待执行步骤、已完成步骤和操作结果。
- 平台标识、artifact 根目录、事件和报告路径。
- 指纹集合、错误、最终状态和资源释放状态。

`LoopGraphState` 保存：

- 当前 tick、累计运行时间和上次 checkpoint 时间。
- due 操作、选中操作、唯一 operation_id。
- 每操作尝试/成功/失败次数。
- 连续失败、无进展 tick、播放进度指纹。
- 切集次数、滑动次数、目标完成数。
- 弹窗、广告、停滞、登录、付费和设备状态。
- 证据引用、退出原因和取消状态。

图状态不得保存适配器实例、子进程句柄、设备连接对象、密钥、Cookie 或截图二进制数据。

### 5.2 Checkpoint

使用 LangGraph SQLite checkpointer，`thread_id` 等于 run_id。自定义 checkpoint 仅保留用于非图元数据时才允许存在；旧 `LoopCheckpoint` 和重复的工作流 checkpoint 实现删除。

每个产生外部副作用的节点在执行前写入 `operation_id` 和 intent，成功后写入 completion。恢复时：

- 查询、截图和状态检查可以直接重试。
- 切集、滑动、点击和启动应用先通过平台观察验证效果。
- 已观察到目标效果时补记 completion，不重复操作。
- 未观察到效果时按剩余重试次数执行。

### 5.3 指纹校验

恢复前必须匹配 config、profile、loop plan、skill lock 和 target 指纹。任一不一致返回 `RESUME_INVALID`，且不得连接或操作设备。

## 6. 调度、重试和退出

每项操作独立使用：

- `interval_seconds`
- `timeout_seconds`
- `max_attempts`
- `priority`
- startup、on_popup、on_ad、on_stall、at_runtime 和 after_operation 触发条件

超时在执行节点边界实施。失败分类为可重试和不可重试；重试不绕过操作间隔下限，并记录每次尝试。

退出条件全部接入条件边：

- 最大运行时间。
- 最大切集数、最大滑动数和目标数量。
- 最大连续失败数。
- 最大无进展 tick。
- 设备不可达、模型错误、登录要求、付费要求和未处理弹窗。
- 用户取消。

退出原因使用领域枚举的统一值，不混用当前的大写字符串和小写 Literal。登录和付费阻断应保留原始原因，不能退化为 `max_failures`。

## 7. 证据、日志和报告

每次操作写入：

- 结构化开始、成功、失败、重试和退出事件。
- 配置允许时的操作前后截图。
- 脱敏后的命令摘要、stdout 和 stderr。
- Midscene 原生 HTML 及转换后的 Markdown/数据报告。

`EvidenceCollector` 通过图节点接入，不由 handler 自行决定目录结构。manifest 包含配置指纹、图阶段、checkpoint thread_id、Loop 汇总和退出原因。

技能锁在 `connect_platform` 前强制验证。技能根目录来自 `--skills-root` 或 `MIDSCENE_SKILLS_ROOT`；锁文件不存在、根目录缺失、hash 不一致或技能文件缺失均产生明确错误，不连接设备。

## 8. 平台层

保留唯一的 `platforms/` 适配层，删除 `adapters/` 兼容 facade 并迁移测试引用。

六个平台实现统一 `PlatformAdapter` 协议：

- 构建命令。
- 执行语义 UI prompt。
- 观察 UI/播放进度。
- 检查非幂等操作效果。
- 连接、健康检查和资源释放。

平台差异只存在于适配器内部。主图和 Loop 子图不能根据平台名称拼接命令。

## 9. 测试生成扩展协议

新增：

- `TestCaseSpec`：名称、平台、目标、前置条件、步骤、断言、清理动作和标签。
- `TestStepSpec`：动作、参数、期望、超时和失败策略。
- `TestScriptGenerator` 协议：输入需求和平台能力，输出 `TestCaseSpec`。
- `TestScriptRenderer` 协议：将规范渲染为 Python、Vitest 或 YAML。

本次提供 Pydantic 校验和一个确定性的 YAML/Python renderer，确保未来生成器与运行时之间以稳定数据契约衔接。模型选择、prompt 和自动修复留到后续独立设计。

## 10. 模块迁移

新增或调整以下职责目录：

```text
application/
  graphs/          # 主图和子图装配
  nodes/           # 可独立测试的 LangGraph 节点
  generation/      # 测试生成协议与 renderer
domain/
  contracts/       # 请求、结果、Loop、测试用例
  runtime/         # 图状态
  policies/        # 退出、重试、恢复策略
infrastructure/
  config/          # 分层解析、override、包内资源定位
  persistence/     # LangGraph checkpointer 工厂和运行元数据
  evidence/        # 证据与脱敏
  reporting/       # result、manifest 和 Midscene 报告
platforms/         # 唯一多平台适配层
```

删除或替换：

- `adapters/` 兼容层。
- 单节点 `AgentGraph`、旧 `WorkflowEngine`。
- 未接线的 `LoopCheckpoint`。
- 审批移除后无调用方的风险分类函数。

## 11. 测试与 CI

采用 TDD，测试分为：

1. 节点单元测试：配置、override、指纹、路由、重试、退出、证据和技能锁。
2. 图测试：plan、单次执行、Loop、错误分支、取消和恢复。
3. 平台契约测试：六个平台满足同一协议和命令映射约束。
4. wheel 测试：构建、安装后 CLI 可用、内置配置可加载。
5. opt-in 集成测试：Browser 和 Android 的执行及恢复场景。

GitHub Actions 在 Python 3.11 和 3.12 上执行：

- `python -m compileall src`
- `pytest`
- `ruff check`
- `mypy`
- `python -m build`
- 在隔离环境安装 wheel 并执行 CLI smoke test

真实平台集成测试不在普通 CI 中执行，只在显式环境变量和凭据满足时启用。

## 12. 兼容性和迁移

- 保留 `midscene-ui-agent run` 的现有基础参数。
- Python API 继续接受直接构造的 `AutomationRequest`，并允许调用方直接传入 LoopPlan。
- `--resume` 从无效参数升级为真实恢复。
- 配置式运行是新增入口，不要求现有直接请求立即迁移。
- 删除 `midscene_ui_agent.adapters.*` 导入路径，不保留第二套平台命名空间。
- 错误码和退出原因统一后同步更新文档和报告 schema。

## 13. 验收标准

- CLI 可以仅通过 app/task 配置启动 Browser 或 Android Loop。
- CLI/API override 能覆盖任意合法配置字段，非法路径或字段明确失败。
- 每项操作的间隔、超时、重试和触发条件有自动化测试并在图中生效。
- 所有退出条件均有图路由测试，退出原因准确。
- 中断后使用同一 run_id 能恢复；指纹变化时恢复在设备连接前失败。
- 技能锁和证据采集进入真实执行链。
- 运行时只使用 `platforms/`。
- wheel 包含默认配置和 schema，安装后可加载。
- LangGraph 主图和 Loop 子图承担真实执行，而非单节点兼容包装。
- `TestCaseSpec` 和 renderer 可生成确定性的测试脚本骨架。
- 单元、图、包构建测试通过；Browser/Android 集成测试保留明确启用方式。
