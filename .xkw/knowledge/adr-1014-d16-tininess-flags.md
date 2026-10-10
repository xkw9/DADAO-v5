# ADR-1014: D16 tininess 与复合 flags

**状态**：Accepted  
**日期**：2026-09-28  
**关联**：ADR-1004 D16、`SPEC-103t`、`contracts/f1_gap_proofs.yaml` `CAND-D16-*`

## Context

SimRISC 未唯一规定 tininess 检测时点及 UF/OF/NX 复合 flags。D16 保持 OPEN/BLOCKED。

## Decision

### D1：tininess 在舍入后检测

选择 `CAND-D16-TINY` 的 **A**：只有最终舍入后的结果仍为 tiny/subnormal 时，才满足 tininess 条件。

**确认记录**：用户先按说明中错置的 A/B 标签表达“舍入后”，主会话发现 Candidate 编号反置后立即更正；用户于 2026-09-28 明确确认真实 `CAND-D16-TINY` 的 A（舍入后）。

### D2：underflow/overflow 与 inexact 复合置位

选择 `CAND-D16-COMPOSITE` 的 **A**：underflow 同时置 UF+NX，overflow 同时置 OF+NX。

**确认记录**：D2 由用户于 2026-09-28 逐条确认。

## Rationale

用户选择与 IEEE 754/RISC-V 常用的 after-rounding tininess 模型一致。它们仅为兼容性理由，不是 SimRISC 语义 authority 或 oracle。

## Consequences

- UF/underflow 边界以最终舍入结果判定；UF/OF 与 NX 按 D2 复合置位。

## 状态说明

2026-09-28：D1、D2 已逐条用户确认并通过 `SPEC-104t` 机器投影与反例；lifecycle 返工完成后按用户授权置 Accepted。
