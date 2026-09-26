---
description: 只读刷新 .xkw 任务、依赖、阻塞与工作区状态
---

严格按 `.xkw/knowledge/workflow.md` 的 **§5.2 最小快照、§7 /xkw-status** 执行。

目标模块（可为空）：$ARGUMENTS

- 输出任务状态计数、可下发/待验收/BLOCKED、关键路径、下一任务、dirty baseline 和状态漂移。
- 除非发现冲突需溯源，不重读整个 `.tao/knowledge/MEMORY.md`。
- 本命令严格只读，不自动修正任何状态或知识文件。
