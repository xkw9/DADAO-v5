# ADR-1012: D14 unordered compare NaN 位型

**状态**：Accepted  
**日期**：2026-09-28  
**关联**：ADR-1004 D14、`SPEC-103t`、`contracts/f1_gap_proofs.yaml` `CAND-D14-*`

## Context

SimRISC 未唯一规定 unordered 比较写入 RD 的 qNaN/sNaN 精确位型。D14 保持 OPEN/BLOCKED。

## Decision

### D1：qNaN 比较结果使用 canonical f64 Quiet NaN

选择 `CAND-D14-QNAN` 的 **A**：`foqcmp`、`ftqcmp` 的 unordered 路径写入 64 位 RD 时为 `0x7ff8_0000_0000_0000`（正号、指数全 1、quiet 位 1、其余 payload 为 0）。

**确认记录**：D1 由用户于 2026-09-28 逐条确认。

### D2：sNaN 比较结果使用最小非零 payload

对 `CAND-D14-SNAN` 采用用户明确位型：unordered signaling compare 写入 RD 的 sNaN 为 `0x7ff0_0000_0000_0001`，即正号、指数全 1、quiet bit 为 0、尾数最低位为 1。它不是 Infinity，且不要求与 D1 qNaN 使用相同 payload。

**确认记录**：D2 由用户于 2026-09-28 逐条确认。

### D3：q/s 位型由比较指令类别固定

`foqcmp`、`ftqcmp` 的 unordered 路径固定返回 D1 qNaN；`foscmp`、`ftscmp` 的 unordered 路径固定返回 D2 sNaN。该选择不依赖输入 NaN 是 quiet 还是 signaling。

**确认记录**：D3 由用户于 2026-09-28 逐条确认。

## Rationale

用户选择将 SimRISC-00:80 描述的 rf0 中 fo Quiet NaN 位型作为 RD 比较结果位型。该外推是用户对规范缺口的选择，不是规范自动推导。

## Consequences

- unordered qNaN 比较结果可有精确 64 位 expected。
- qNaN 与 sNaN 均有精确 64 位 expected。

## 状态说明

2026-09-28：D1、D2、D3 已逐条用户确认并通过 `SPEC-104t` 机器投影与反例；lifecycle 返工完成后按用户授权置 Accepted。
