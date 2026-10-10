# LLVM-103t: `set.ft`/`set.fo` 伪指令与反汇编边界

**模块**：llvm  
**项目里程碑**：F1  
**状态**：待开始  
**依赖**：`SPEC-102t re-Accepted`、`LLVM-101t`；`TESTCASES-101t` 的 RF bit-pattern 接口；`SPEC-104t` 的 `resolution` 层；本任务对全部 ledger 键一律 `N/A(runtime)`

## 目标

落实 ADR-1004 D18：assembler 接受 spec 定义的 `set.ft`/`set.fo` 形式并展开；disassembler 永远只打印真实硬件指令，不将序列折叠成 pseudo。pseudo 不计入 64 identity。

## 必须支持的形式与展开

- `set.ft rfD, imm32`：非零按高到低/规范示例展开为两个 `set.w`（wp1、wp0）；零展开为 `rd2rf rfD, rd0, 1`。
- `set.fo rfD, imm64`：非零展开为四个 `set.w`（wp3、wp2、wp1、wp0）；零展开为 `rd2rf rfD, rd0, 1`。
- `set.ft rfD, rdS` / `set.fo rfD, rdS`：`rd2rf rfD, rdS, 1`。
- `set.ft rfD, rfS`：`ft2ft rfD, rfS, 1`；`set.fo rfD, rfS`：`fo2fo rfD, rfS, 1`。

立即数按 bit-pattern 装载，不经宿主浮点文本解析。若接受额外浮点字面量需另有 spec/ADR，不在本任务默认范围。

## 交付物

LLVM `0009+` 中 pseudo/parser/expansion 与 lit；独立展开检查器验证真实指令数量、顺序、wpN 和字节。不得新增真实 opcode，不得给 disassembler 添加 alias folding。

## D17 OPEN-ID ledger 与 pseudo 边界

`D17 OPEN-ID ledger` 的完整 marker：active 精确键集合为 {D17:S1,D17:S3,D17:S4,D17:S5,D17:S6,D17:S8}（六键）。本任务的汇编展开/反汇编边界对 ledger 六个键的运行语义一律为 `N/A(runtime)`；`D17:S2` 始终是 ledger 外 trace-only（`no behavioral consequence; resolved/trace-only; not in D17 OPEN-ID ledger; never PASS`），不是缺口；`D17:S7` 始终是 ADR-1008 D1 已证明的 spec-determined non-gap（move overlap 由 SimRISC-00:41-46 与 SimRISC-03:34-50 唯一确定），不进入 active ledger、不计 OPEN/BLOCKED、不计 PASS。展开字节 PASS 不证明 reset、SBZ、内存或 fault 原子性行为。涉及 `rd2rf`/`rf2rd` 的展开只证明 emitted sequence；其运行结果受 `resolution.rule_tables.D11`（`rd2rf→rf0` 为 ILLI）与 D17:S1/S4 门禁约束。开工必须等待 `SPEC-102t re-Accepted`。当前形式清单可静态核对，LLVM 实现/build/E2E 仍 BLOCKED。

## SPEC-104t 已投影的适用规则

语义激活门禁：`SPEC-104t` 已验证，且本任务所消费的 ADR-1009～1015 全部 Accepted；在此之前 `contracts/f1_gap_proofs.yaml` 的 `resolution` 层只表示 projected-pending-activation，不得当作 active implementation truth，也不得据此声称任何 facet PASS。

`set.ft`/`set.fo` 是 pseudo、不计入 64 identity；本任务只消费 `resolution.resolution_matrix` 的编码层，对全部 ledger 键的运行语义一律 `N/A(runtime)`。展开后落到真实指令时必须遵守：

| 规则 | 对展开序列的约束 |
| --- | --- |
| `rule_tables.D11.rf0_write_whitelist` | 展开出的 RF 目的寄存器若为 rf0，只有十条白名单 identity 合法；展开不得为非法 rf0 目的形式「挑一条能跑的白名单路径」 |
| `rule_tables.D13.tetra_high_half` | 展开不得读写 f32 高半部；高半部取值属运行语义，`N/A(runtime)` |
| `rule_tables.D17` 的 `D17:S3` | `ftcls/focls immu6!=1` 由 assembler 拒绝，非本任务范围 |
| `D17:S2` / `D17:S7` | 不进 marker；`rd2rf`/`rf2rd` 的块赋值方向是 ADR-1008 D1 证明的 spec-determined non-gap，展开可依赖该唯一方向，但不得据此声称任何 facet PASS |

反汇编边界不变：disassembler 永远只打印真实硬件指令，永不把序列折叠成 pseudo。

## 验收

| # | 判据 | 可执行性 |
| --- | --- | --- |
| 1 | 上述 8 类形式逐项展开为规定的 1/2/4 条真实指令及正确字节 | **BLOCKED**：pseudo 尚未实现；替代证据为 ADR-1004 D18 与本书逐形式展开合同 |
| 2 | object 反汇编只出现 `set.w/rd2rf/ft2ft/fo2fo`，不出现 `set.ft/set.fo` | **BLOCKED**：依赖 LLVM-101t/本任务 build；替代证据为禁止 alias-fold 的静态边界 |
| 3 | 64 identity 覆盖计数保持 64，pseudo 单列为 2 | **BLOCKED**：覆盖 checker 尚未产出；替代证据为 SPEC 64 清单和 pseudo 2 的独立计数 |
| 4 | 非法宽度/寄存器组合/超界立即数稳定拒绝 | **BLOCKED**：parser/负例尚未实现；替代证据为固定语法范围，未决运行语义不得混入诊断 |
| 5 | pseudo 的运行语义 | **BLOCKED**：QEMU 对展开后真实指令尚未实现；`rd2rf→rf0` 的 ILLI 与六个 active OPEN-ID 的取值都不得在 MC 层断言，替代证据为逐字节展开与 MC round-trip |

## 反例、还原与重建

注入“wp 顺序反转”“零仍展开多条”“ft 错用 fo2fo”“disassembler alias-fold”为 pseudo，逐项真实 FAIL。注入在 `/tmp/opencode/LLVM-103t/`，先证 diff 非空；恢复源码后重新构建 `llvm-mc/objdump` 并复绿。全文件排查任何 alias printer，不能只测一个样例。

## 完成区

由 engineer 执行后填写；记录展开字节、反汇编文本、负例和重建证据。
