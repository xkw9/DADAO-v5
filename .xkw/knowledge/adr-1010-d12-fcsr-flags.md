# ADR-1010: D12 FCSR flags 更新规则

**状态**：Accepted  
**日期**：2026-09-28  
**关联**：ADR-1004 D12、`SPEC-103t`、`contracts/f1_gap_proofs.yaml` `CAND-D12-*`

## Context

SimRISC 未唯一规定 rf0[4:0] 异常 flags 的跨指令更新、保留与软件清除模型。ADR-1004 D12 因此保持 OPEN/BLOCKED。

## Decision

### D1：硬件异常 flags 采用 sticky OR

选择 `CAND-D12-UPDATE` 的 **A**：任一浮点异常对 rf0[4:0] 的对应位置位；后续无异常指令不得自动清除已置位 flags。软件清除路径另由 `CAND-D12-CLEAR` 单独决定。

**确认记录**：D1 由用户于 2026-09-28 逐条确认。

### D2：无异常执行保持既有 flags

选择 `CAND-D12-KEEP` 的 **A**：本次不产生异常的浮点指令保持 rf0[4:0] 原值，不自动清零。

**确认记录**：D2 由用户于 2026-09-28 逐条确认。

### D3：软件可直接改写 flags

选择 `CAND-D12-CLEAR` 的 **A**：写 rf0[4:0] 是软件清除或改写 flags 的路径；具体存取指令的合法性仍受各自 rf0/SBZ 门禁约束。

**确认记录**：D3 由用户于 2026-09-28 逐条确认。用户选择与 RISC-V 软件可写 `fflags` 的模型一致；RISC-V 仅为兼容性理由，不是 SimRISC 语义 authority 或 oracle。

### D4：自动 flags 更新只适用于 53 条浮点计算类 identity

选择 `CAND-D12-SCOPE` 的 **A**：53 条具有 `fcsr_flags=open-blocked` 的浮点计算/转换等 identity 按 D1、D2 自动更新 flags；11 条 RF 存取、搬移与 `set.w` 类不因搬运的位模式自动置位或清除 flags。该结论不否定 D3：合法的软件显式写 rf0[4:0] 仍可直接改写其位。

**确认记录**：D4 由用户于 2026-09-28 逐条确认。

### D5：软件写与后续异常按程序顺序组合

选择 `CAND-D12-MOVE` 的 **A**：软件对 rf0[4:0] 的合法写入立即生效；随后浮点指令产生的异常在该当前值上执行 D1 的 sticky OR。软件写不被历史硬件 flags 强制覆盖。

**确认记录**：D5 由用户于 2026-09-28 逐条确认。

## Rationale

用户选择与 RISC-V `fflags` 的 accrued/sticky 模型保持一致，便于软件预期与跨指令诊断。RISC-V 在此仅是选择后的兼容性参考，**不是** SimRISC 语义 authority、oracle 或本结论的规范证据；本结论来自用户对真实规范缺口的决策。

## Consequences

- 浮点测试 oracle 必须维护 flags 累积状态，不能把正常指令后的 flags 自动归零。
- D12 的五个当前 Candidate 输入均已逐项确认；实现投影仍须另行任务完成并验收。
- 未决 D12 面继续 OPEN/BLOCKED；本 ADR 不产生可执行实现或 PASS。

## 状态说明

2026-09-28：D1–D5 已逐条用户确认并通过 `SPEC-104t` 机器投影与反例；lifecycle 返工完成后按用户授权置 Accepted。
