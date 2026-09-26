---
description: 只读启动或恢复 DADAO-v5 的 .xkw 工作上下文
---

严格按 `.xkw/knowledge/workflow.md` 的 **§5 通用启动快照、§6 /xkw-start** 执行。

目标范围（可为空、模块名或任务 ID）：$ARGUMENTS

- 从 `.xkw/README.md` 开始，按固定顺序读取；`.tao/` 只读且仅按目标展开。
- 生成仓库/dirty baseline、目标解析、路线与状态、依赖/冲突、漂移/阻塞和下一动作建议。
- 本命令严格只读：不得改文件、改状态、调执行子代理、安装依赖或自动链入 `/plan` `/dispatch` `/complete`。
- 目标歧义或状态冲突时，一次只问一个问题。
