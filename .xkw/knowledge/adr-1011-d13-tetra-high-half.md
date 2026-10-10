# ADR-1011: D13 单精 RF 高半部

**状态**：Accepted  
**日期**：2026-09-28  
**关联**：ADR-1004 D13、`SPEC-103t`、`contracts/f1_gap_proofs.yaml` `CAND-D13-*`

## Context

SimRISC-00:73 对存放 ft 的 64 位 RF 槽位仅规定使用低 32 位，未规定高 32 位。D13 因而为 OPEN/BLOCKED。

## Decision

### D1：ft 运算结果采用 64 位 NaN-boxing

对 `CAND-D13-WRITE` 采用用户确认的 NaN-boxing 选择：ft 运算、转换和符号位指令写入 RF 时，`rf[31:0]` 为 ft 原始位型，`rf[63:32]` 固定为全 1（`0xffffffff`）。

**确认记录**：D1 由用户于 2026-09-28 逐条确认。

### D2：4 字节载入同样采用 NaN-boxing

选择 `CAND-D13-LOAD` 的 **A**：`ld.t-rf`、`ldm.t-rf` 的低 32 位为载入的 ft 位型，高 32 位固定为 `0xffffffff`，与 D1 使用同一规则。

**确认记录**：D2 由用户于 2026-09-28 逐条确认。

## Rationale

用户选择与 RISC-V 在 FLEN=64 时的 f32 NaN-boxing 规则一致，以提供可预测的完整 64 位槽位表示。RISC-V 仅为用户选择的兼容性参考，不是 SimRISC 语义 authority 或 oracle。

## Consequences

- D13 涉及的 ft 写回可拥有确定的高半部 expected；不采用“保留原值”“清零”或 rf0 默认 NaN 位型。
- ft 运算结果与 4 字节载入共享同一 NaN-boxing helper。
- 写入普通 `rf1`–`rf63` 时直接提交 NaN-boxed 64 位值；写入 D11 白名单内的 `rf0` 时，先生成同一 NaN-boxed 写值，再应用 rf0 的只读位与 D17:S6 SBZ 静默忽略 mask，最终只提交允许写入的位。
- 实现、oracle、向量与 contract 投影仍须在后续正式任务中完成并独立验收。

## 状态说明

2026-09-28：D1、D2 已逐条用户确认并通过 `SPEC-104t` 机器投影与反例；lifecycle 返工完成后按用户授权置 Accepted。
