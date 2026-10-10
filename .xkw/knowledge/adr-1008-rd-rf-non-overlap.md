# ADR-1008: RD/RF 块赋值不存在同组重叠

**状态**：Accepted  
**日期**：2026-09-27  
**关联**：`.xkw/knowledge/adr-1004-f1-floating-phase.md` D17、`.xkw/tasks/spec/SPEC-102t-F1浮点合约与64身份映射.md`、`.xkw/tasks/spec/SPEC-103t-F1语义缺口证明与候选ADR输入.md`

## Context

`SPEC-102t` 的 D17 OPEN-ID ledger 曾将 `D17:S7` 记为 `rd2rf`/`rf2rd` 源、目的范围重叠时的读写顺序缺口。该登记须与原始规范的寄存器组定义及两条指令的固定操作数银行重新核对。

SimRISC-00 §寄存器规定用户可见寄存器分为四组、每组各 64 个：数据寄存器是 `rd0`–`rd63`，浮点寄存器是 `rf0`–`rf63`（`spec/SimRISC-00-指令系统设计.md:41-46`）。相同索引的 `rdN` 与 `rfN` 属于不同架构寄存器组。

SimRISC-03 §寄存器组之间块赋值的指令形式固定为 `rf2rd rdhb, rfhc, immu6` 与 `rd2rf rfhb, rdhc, immu6`，语义为将 `hc` 起的 `immu6` 个寄存器复制到 `hb` 起的寄存器（`spec/SimRISC-03-浮点类指令.md:33-49`）。两条指令分别只在 RF→RD 或 RD→RF 之间传送，未提供同组源、目的操作数形式。

因此，格式转换指令中同一寄存器组的范围重叠及读写顺序问题，不能外推到这两条跨组块赋值指令。`rf0` 的合法性/优先级仍由 ADR-1004 D11 的 OPEN/BLOCKED 门禁处理；本 ADR 不决定其行为。

## Decision

### D1：RD/RF 跨组块赋值不具有同组重叠

`rd2rf` 和 `rf2rd` 的源、目的分别属于 RD 与 RF 两个不同寄存器组。即使两侧编号范围在数值上相交，也不表示同一架构寄存器被同时读取和写入；这两条指令不存在同组范围重叠的读写顺序问题。

因此，`D17:S7` 不构成需要选择“先读后写 / 先写后读 / ILLI”等运行时语义的真实缺口。后续 F1 消费者不得把 `D17:S7` 作为 active OPEN 门禁、Candidate 语义选择或 PASS 计数来源；其历史登记保留为可追溯事实，不改写 `SPEC-102t` 的既有交付物。

**闭合状态**：`Closed by spec`。这表示原始规范已证明 S7 不存在待补齐的语义，不表示运行时测试或实现的 PASS，也不解除其余 D11–D16 或 D17 active 项的门禁。

**确认记录**：D1 由用户于 2026-09-27 逐条确认。ADR 整体仍为 Candidate，未经规划审查不得置为 Accepted。

## Rationale

- RD/RF 分组是 SimRISC-00 明示的架构事实，而非实现惯例。
- 两条块赋值指令的操作数银行由 SimRISC-03 的汇编形式固定。
- 将不同银行的相同编号误判为 alias 会凭空制造读写顺序和 ILLI 方案，违反 ADR-1004 D17“先证明真实缺口”的约束。

## Consequences

- `SPEC-103t` 返工须将 S7 改列为 spec-determined/non-gap 证据，并在 YAML、检查器、反例和 64 identity 影响矩阵中移除其 active OPEN/consumer 投影。
- D17 active ledger 的后续消费集合变为 `D17:S1,D17:S3,D17:S4,D17:S5,D17:S6,D17:S8`；`D17:S2` 仍仅为 ledger 外 trace-only。
- D11、D12、D13、D14、D15、D16 及其余 D17 项保持 OPEN/BLOCKED；本 ADR 不产生任何运行时 expected 或实现许可。
- `SPEC-102t` 的已验证历史不回溯改写；下游以本 ADR 与经返工验收的 `SPEC-103t` 作为 S7 的覆盖解释。

## 状态说明

本 ADR 以 Candidate 创建。D1 已取得用户逐条确认；`SPEC-103t` 返工经独立 reviewer 与 architect 复核其规范引用、影响边界和下游门禁后，主会话于 2026-09-28 置为 Accepted。
