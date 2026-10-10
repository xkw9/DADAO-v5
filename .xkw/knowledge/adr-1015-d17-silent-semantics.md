# ADR-1015: D17 未精确定义细节

**状态**：Accepted  
**日期**：2026-09-28  
**关联**：ADR-1004 D17、ADR-1008、`SPEC-103t`、`contracts/f1_gap_proofs.yaml` `CAND-D17-*`

## Context

D17 的当前 active 缺口为 S1/S3/S4/S5/S6/S8；S2 是 trace-only，S7 已 Closed by spec。

## Decision

### D1：rf0/FCSR 复位状态

选择 `CAND-D17-S1` 的 **A**：复位后 rf0[17:16] 为 RNE（`00`），rf0[4:0] flags 全清。rf0 的只读 NaN 位与 SBZ 域仍按既有 spec 规则处理。

**确认记录**：D1 由用户于 2026-09-28 逐条确认。

### D2：classify 的非 1 immediate 在汇编期拒绝、硬件期 ILLI

对 `CAND-D17-S3` 采用用户明确的 A′：assembler 对 `ftcls`/`focls` 的 `immu6 != 1` 拒绝编码；若该机器码仍由手写、链接或其它非 assembler 路径到达硬件，则运行时触发 ILLI。汇编期拒绝不改变硬件非法编码的异常语义。

**确认记录**：D2 由用户于 2026-09-28 逐条确认。

### D3：多 fault 时 ILLI 优先于 MALIGN

选择 `CAND-D17-S4` 的 **A**：多个 fault 谓词同时成立时先判 ILLI，再判 MALIGN；非法编码或操作数不得触发地址侧对齐判定。

**确认记录**：D3 由用户于 2026-09-28 逐条确认。

### D4：scaleB 指数按 rf0 舍入模式转换为整数

对 `CAND-D17-S5` 采用用户明确的细化规则：将浮点 `rfhd` 按 `rf0[17:16]` 当前舍入模式转换为整数 `n`，再计算 `rfhc × 2^n`；该舍入模式也继续控制最终浮点结果的舍入。

**确认记录**：D4 由用户于 2026-09-28 逐条确认；NaN/Inf 的规则由 D5 补充。

### D5：scaleB 非有限指数

`rfhd=qNaN` 时直接返回 D15 的 canonical qNaN 且指数分类本身不置 flags；`rfhd=sNaN` 时按 D15 置 NV 并返回 canonical qNaN；`rfhd=+Inf` 时指数视为 `+Inf`；`rfhd=-Inf` 时比例因子 `2^-Inf` 视为 `0`。随后 `rfhc × 2^n`（`-Inf` 情形即 `rfhc × 0`）的浮点乘法按 IEEE 规则独立确定结果与 flags。

**确认记录**：D5 由用户于 2026-09-28 逐条确认。

### D6：rf0 SBZ 写入静默忽略

选择 `CAND-D17-S6` 的 **A**：仅当 D11 白名单允许以 rf0 为目的时，`ld.t-rf`、`ld.o-rf`、`ldm.t-rf`、`ldm.o-rf`、`set.w-rf`、`cs.eq-rf`、`cs.ne-rf`、`cs.n-rf`、`cs.z-rf`、`cs.p-rf` 写 rf0 的 SBZ 域 `[50:32]`、`[21:18]`、`[15:5]` 才静默忽略对应写入位；其它可写域按各自规则处理。`rd2rf → rf0` 不在白名单，按 D11 触发 ILLI，不进入本规则。

**确认记录**：D6 由用户于 2026-09-28 逐条确认。

### D7：RF ldm/stm 与 RD 多寄存器存取对齐

对 `CAND-D17-S8` 选择 A，并由用户明确将 RF 多寄存器存取与 RD 的明示内存侧规则对齐：第 0 项有效地址为 `rbhb + rdhc`；第 i 项访问 `EA(0) + i × width`，`.t` 宽度/步长为 4 字节，`.o` 为 8 字节；RF 寄存器按序号递增。对齐要求和范围 ILLI 谓词继续适用既有 SimRISC-03 规则，D3 的 ILLI 优先级亦适用。

**确认记录**：D7 由用户于 2026-09-28 逐条确认。RD 多寄存器条款仅为用户选择的对齐参照，不是 SimRISC-03 的语义 authority；未由该条款明示的部分访问提交/异常原子性不在本 decision 中新增。

### D8：RF ldm/stm fault 为精确异常

任一元素触发 fault 时，整条 RF `ldm/stm` 指令不提交任何目标 RF 写入或内存 store 写入，PC 停在 faulting instruction；不保留此前元素的部分架构状态。

**确认记录**：D8 由用户于 2026-09-28 逐条确认。

## Rationale

D3 未采用 `.tao` M1 测试机的 MMIO 优先级；该内容不是 F1 语义 authority。D8 是用户选择与 `.tao` ADR-0004 的 RD 多寄存器精确异常模型对齐的结果；`.tao` 仅为对齐参照，不是 SimRISC-03 语义 authority 或 oracle。

用户选择确定的初始舍入和异常状态，使首条浮点指令可独立构造和验证。

## Consequences

- reset-dependent expected 可有确定起点。
- 当前六项 active D17 的 Candidate 输入与 S8 fault 提交模型均已逐项处理。

## 状态说明

2026-09-28：D1–D8 已逐条用户确认并通过 `SPEC-104t` 对六键 active scope、S6 current-ten、优先级及 RF ldm/stm 规则的机器投影与反例；lifecycle 返工完成后按用户授权置 Accepted。
