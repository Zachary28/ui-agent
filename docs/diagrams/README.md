# 架构示意图

使用 PlantUML 绘制的系统架构示意图，放在在线预览工具或 VS Code PlantUML 插件中查看。

## 图表列表

| 文件 | 说明 |
|------|------|
| `01-architecture.puml` | **系统架构图** - DDD 分层架构：Interfaces → Application → Domain + Infrastructure + Platforms + Config |
| `02-single-task.puml` | **单次任务时序图** - plan 模式生成计划 vs live 模式真实执行全流程 |
| `03-loop-engineering.puml` | **循环播放时序图** - LoopWorkflow 主循环：调度 → 优先级选择 → 执行 → 退出判断 |
| `04-config-layering.puml` | **配置分层图** - defaults → platform → app → task → CLI 五层叠加合并 |

## 查看方式

**在线预览（推荐）：**
1. 打开 https://www.plantuml.com/plantuml/uml/
2. 复制 `.puml` 文件内容粘贴到编辑器
3. 自动生成 SVG/PNG

**VS Code 插件：**
安装 "PlantUML" 扩展 (jebbs.plantuml)，按 `Alt+D` 预览。

**命令行导出 PNG：**
```powershell
# 需要先安装 Java 和 plantuml.jar
java -jar plantuml.jar docs/diagrams/*.puml
```
