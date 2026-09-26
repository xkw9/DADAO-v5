---
description: xkw 独立证伪验收、交叉复核与主会话收尾
---

严格按 `.xkw/knowledge/workflow.md` 的 **§5 通用启动快照、§11 /complete** 执行。

目标任务：$ARGUMENTS

- 先读取 `.xkw/README.md`，唯一定位任务、核对 `待验收` 并保存审查 baseline。
- reviewer 必须先枚举所有检查器/oracle，再亲自证伪、证明注入非空、还原含重建并给出真实结论。
- architect 只交叉复核 reviewer 的证据与边界。
- 任一 Needs Revision 即回 `待返工`；双 Accepted 后由主会话更新状态和知识。
- 不覆盖既有用户改动，不自行提交；ADR decisions 仍逐条确认。

最终汇报使用 workflow 规定的 `/complete` 输出格式。
