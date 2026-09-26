---
description: 按 .xkw 入口与启动任务合同规划任务
---

严格按 `.xkw/knowledge/workflow.md` 的 **§5 通用启动快照、§8 启动任务合同、§9 /plan** 执行。

规划目标：$ARGUMENTS

- 先读取 `.xkw/README.md` 并完成等价 `/xkw-start` 快照；目标为空或歧义时一次只问一个问题。
- 新模块/里程碑必须创建或更新 `k`，并按 workflow 的完整模板检查依赖、文件冲突、资源冲突和 `k↔m`。
- architect 规划、reviewer 交叉审查；必要 ADR 的 decisions 逐条交用户确认。
- 仅审查通过后落盘任务、milestones 和 MEMORY；满足合同的 `k` 置 `已验证`。
- `.tao/` 只读，保护启动时已有用户改动，不执行实现或 git commit。

最终汇报使用 workflow 规定的 `/plan` 输出格式。
