---
description: xkw 启动快照与四项预检后下发 engineer
---

严格按 `.xkw/knowledge/workflow.md` 的 **§5 通用启动快照、§10 /dispatch** 执行。

目标任务：$ARGUMENTS

- 先读取 `.xkw/README.md`，唯一定位任务并保存 dirty baseline。
- 只接受 `待开始/待返工`；状态非法、依赖不可用、目标歧义时 fail-closed。
- 完成四项预检，把结论和任务书全文交用户确认；确认前不得调 engineer。
- engineer prompt 必须包含任务路径、baseline、修改边界、日志、临时目录和自审要求。
- 返回异常、模型降级、状态转换严格按 workflow，不自行重试或提交。

最终汇报使用 workflow 规定的 `/dispatch` 输出格式。
