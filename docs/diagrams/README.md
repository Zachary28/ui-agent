# 架构示意图

使用 PlantUML 绘制的系统架构示意图，放在在线预览工具或 VS Code PlantUML 插件中查看。

## 图表列表

| 文件 | 说明 |
|------|------|
| `01-architecture.puml` | **系统架构图** - 分层、主图/子图、六平台、报告和测试生成边界 |
| `02-single-task.puml` | **单操作时序图** - plan、skill 校验、操作 checkpoint、资源释放和报告 |
| `03-loop-engineering.puml` | **Loop 与恢复时序图** - 调度、优先级、退出、中断、指纹和幂等恢复 |
| `04-config-layering.puml` | **配置与 Skill Lock 图** - 六层配置、schema、指纹和运行前 skill 校验 |

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
