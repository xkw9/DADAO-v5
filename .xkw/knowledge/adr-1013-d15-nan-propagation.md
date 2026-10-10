# ADR-1013: D15 NaN 传播

**状态**：Accepted  
**日期**：2026-09-28  
**关联**：ADR-1004 D15、`SPEC-103t`、`contracts/f1_gap_proofs.yaml` `CAND-D15-*`

## Context

SimRISC 未唯一规定 NaN payload、符号、quieting 和多 NaN 选择。D15 保持 OPEN/BLOCKED。

## Decision

### D1：单 NaN 输入返回 canonical qNaN

选择 `CAND-D15-SINGLE` 的 **B**：单个 NaN 源操作数的结果丢弃输入 payload 与符号，返回固定 canonical Quiet NaN；sNaN 的异常 flags 仍由相应 flags 规则处理。

**确认记录**：D1 由用户于 2026-09-28 逐条确认。

### D2：多个 NaN 输入保持 canonical qNaN，并对任一 sNaN 置 NV

对 `CAND-D15-MULTI` 选择固定默认 NaN 的 C 路径，并确认只要任一源为 sNaN 即置 NV；结果仍为 D1 的 canonical qNaN，与输入顺序、payload 和符号无关。

**确认记录**：D2 由用户于 2026-09-28 逐条确认。

### D3：sNaN 单输入返回 canonical qNaN 并置 NV

选择 `CAND-D15-SNAN-IN` 的 **B**：sNaN 算术输入丢弃其 payload 与符号，返回 canonical qNaN，同时置 NV。

**确认记录**：D3 由用户于 2026-09-28 逐条确认。

### D4：NaN 格式转换传播 payload

按 SimRISC-03:129 的明确规则，`fo2ft`、`ft2fo` 传播 NaN payload；sNaN 转换同时置 NV 并返回 qNaN。该条覆盖此前 canonical-discard 选择；转换后 NaN 符号由 D6 明确规定。

**确认记录**：用户先确认 canonical 方案；architect 复核发现其与当前 SimRISC-03:129 的明文 payload 传播规则冲突。按用户“按 architect 结论修订”的指示，于 2026-09-28 更正为 spec 规则。

### D5：NaN flags 与混合操作数规则

在算术和多操作数运算中，任一 qNaN 输入返回 canonical qNaN 且不置 NV；任一 sNaN 输入返回 canonical qNaN 且置 NV。混合普通数、qNaN、sNaN 时，结果始终 canonical qNaN，NV 仅由是否存在至少一个 sNaN 决定。本条不覆盖 D4/D6 的 `fo2ft`/`ft2fo` 转换规则。

**确认记录**：D5 由用户于 2026-09-28 逐条确认。

### D6：NaN 格式转换结果固定为正号

在 `fo2ft`、`ft2fo` 的 NaN 转换中，payload 按 SimRISC-03:129 传播，结果 NaN 符号固定为正号；sNaN 仍按 D4 置 NV 并返回 qNaN。

**确认记录**：D6 由用户于 2026-09-28 逐条确认。

## Rationale

用户选择与 RISC-V canonical NaN 模型一致，以取得跨实现确定性。RISC-V 仅为兼容性理由，不是 SimRISC 语义 authority 或 oracle。

## Consequences

- 单 NaN 输入不需要 payload/符号传播 oracle。
- 当前 D15 Candidate 输入及 mixed-NaN flags 均已逐项确认；转换 NaN 的 payload 按 spec 传播、符号按 D6 固定为正。

## 状态说明

2026-09-28：D1–D6 已逐条用户确认；`SPEC-104t` 对算术与转换 NaN 的 payload、canonical、符号与 NV 规则均有机器投影与反例；lifecycle 返工完成后按用户授权置 Accepted。
