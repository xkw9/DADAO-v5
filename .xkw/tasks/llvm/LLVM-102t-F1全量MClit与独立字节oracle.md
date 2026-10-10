# LLVM-102t: F1 全量 MC lit 与独立字节 oracle

**模块**：llvm  
**项目里程碑**：F1  
**状态**：待开始  
**依赖**：`SPEC-102t re-Accepted`、`LLVM-101t`、`SPEC-104t` 的 `resolution` 层；本任务对全部 ledger 键一律 `N/A(runtime)`，不消费任何运行语义

## 目标

为 64 个真实 identity 建立强模板 assemble/disassemble lit、独立字节 oracle 和覆盖门禁。测试 expected bytes 从 spec/contracts 独立计算，不从 `llvm-mc` 输出回填。

## 交付物

- F1 MC lit：每个 identity 至少一个 canonical 正例；共享 mnemonic 的 bank 消歧；边界 immediate、寄存器与 negative tests。
- 扩展 `tools/llvm/check_lit_bytes.py` / `test_encoding_oracle.py`（或建立单一明确工具）识别 F1 scope，逐条计算 `op/ha/fields` 的大端 4 字节。
- 覆盖矩阵精确为 64/64，不把 `set.ft/set.fo` 计入；pseudo 测试归 LLVM-103t。
- disassembler round-trip 只接受 canonical 真实指令文本，不能把多指令序列折叠。

## 边界

本任务只证明 MC 编码/打印，不证明运行语义。`contracts/opcodes.yaml` 是机器输入但不是 validator 绿灯的唯一 oracle；至少对 QFC、MISC-RF、rrrr/rrii/rrri/rwii/orri/orrr 各族手工/独立公式复算。

`D17 OPEN-ID ledger` 的 active 精确键集合为 {D17:S1,D17:S3,D17:S4,D17:S5,D17:S6,D17:S8}（六键）。本任务对 ledger 六个键均不作 runtime 结论（`N/A(runtime)`）；`D17:S2` 始终是 ledger 外 trace-only（`no behavioral consequence; resolved/trace-only; not in D17 OPEN-ID ledger; never PASS`），不是缺口；`D17:S7` 始终是 ADR-1008 D1 已证明的 spec-determined non-gap（move overlap 由 SimRISC-00:41-46 与 SimRISC-03:34-50 唯一确定），不进入 active ledger、不计 OPEN/BLOCKED、不计 PASS。lit/oracle PASS 只覆盖 encoding/printing，不能解锁 reset、分类 legality、fault priority、scaleB、SBZ 或内存语义。开工须以 `SPEC-102t re-Accepted` 为前置。当前 M1 回归可跑；F1 lit/build 判据仍 BLOCKED。

## SPEC-104t 已投影的适用规则

语义激活门禁：`SPEC-104t` 已验证，且本任务所消费的 ADR-1009～1015 全部 Accepted；在此之前 `contracts/f1_gap_proofs.yaml` 的 `resolution` 层只表示 projected-pending-activation，不得当作 active implementation truth，也不得据此声称任何 facet PASS。

本任务**唯一**的语义消费是「64 个 identity 的编码与打印」这一层，对应 `resolution.resolution_matrix` 的 64 行（`mc_encoding_consumer` 含 LLVM-102t）与 `consumer_activation` 中 LLVM-102t 的 `ledger_gate_projection`（六个 active 键全部 `N/A(runtime)`）。

不得从 lit/oracle 推出运行结论的具体边界：

| `resolution` 规则 | 本任务的结论 |
| --- | --- |
| `rule_tables.D11.rf0_write_whitelist`（十条） | 只证明 rf0 目的形式可被编码；白名单外形式是 assembler 负例，不在本任务范围 |
| `rule_tables.D13.tetra_high_half`（`0xffffffff`） | 只与 RF 写值语义有关，本任务 `N/A(runtime)` |
| `rule_tables.D12` / `D14` / `D15` / `D16` | 纯运行语义，本任务 `N/A(runtime)` |
| `rule_tables.D17` 的 `D17:S1`/`S3`/`S4`/`S5`/`S6`/`S8` | 除 `D17:S3` 的 assembler 拒绝由 LLVM-101t 消费外，本任务一律 `N/A(runtime)` |
| `D17:S2`（trace-only）与 `D17:S7`（spec-determined non-gap） | 不进 marker，不生成 lit 期望 |

开工须以 `SPEC-102t re-Accepted` 为前置；动态判据按实现/build 真实能力保持 BLOCKED。

## 验收

| # | 判据 | 可执行性 |
| --- | --- | --- |
| 1 | 覆盖 checker 报 64/64、无重复、无 pseudo 混入 | **BLOCKED**：F1 lit/checker 尚未产出；替代证据为 SPEC 64 清单与 pseudo 排除规则 |
| 2 | lit 全绿，且每个 `# OBJ` 字节由独立 oracle 复算 0 mismatch | **BLOCKED**：依赖 LLVM-101t 的 F1 build 与本任务 oracle；替代证据为独立计算公式要求 |
| 3 | assemble→disassemble→assemble 的 4 字节逐项相同 | **BLOCKED**：依赖 F1 assembler/disassembler；替代证据为 canonical round-trip 合同 |
| 4 | M1 MC lit 与既有独立 oracle全绿且计数无退化 | 现在可跑：当前 M1 基线可重跑；任务完成时仍须在 F1 变更后重跑，旧日志不能替代 |
| 5 | QEMU 语义正确 | **BLOCKED**：不属于 MC；替代证据仅为编码/打印，语义归 QEMU/INTEG |

## 反例门禁

对所有 checker 分别注入：改一条 `# OBJ` bit、删一 identity、将 F1 opcode 指向另一合法 identity、让 disassembler 打错误 bank、把 pseudo 混入 64。每次证明注入非空并取得真实非零；特别防止 oracle 与 lit 共读同一 expected 而同错。MC 测试只证明 encoding/printing，不得把 D11–D17 或六个 active OPEN-ID 的运行语义标 PASS，也不得把 `D17:S2`/`D17:S7` 写成 lit 期望。注入在 `/tmp/opencode/LLVM-102t/`。若动 LLVM 源，恢复后必须重建并复绿；只动 lit 数据也须证明对象文件重新生成而非复用陈旧缓存。

## 完成区

由 engineer 执行后填写；给出 64/64、lit、round-trip、M1 回归和逐 checker 反例输出。
