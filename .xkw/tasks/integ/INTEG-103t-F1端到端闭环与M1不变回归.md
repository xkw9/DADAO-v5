# INTEG-103t: F1 端到端闭环与 M1 不变回归

**模块**：integ  
**项目里程碑**：F1  
**状态**：待开始  
**依赖**：`SPEC-102t re-Accepted`、`INTEG-102t`、`SPEC-104t` 的 `resolution` 层（ADR-1009～1015 现行 27 条 decision）；七份 ADR 全部 Accepted 后语义门禁解除，另需 LLVM/QEMU F1 构建与 active vectors 可用

## 目标

执行 assembler→object/raw bytes→QEMU→RF/RD/FCSR/memory 观测的 F1 端到端闭环，同时完整复跑 M1 权威基线。最终按 64 identity required facet 报告 active PASS 与真实 BLOCKED，绝不把 OPEN 或普通数值 smoke 当 F1 全量收敛。

## 执行环境

- LLVM：`.work/f1/source/llvm-project` + `.work/f1/build/llvm`。
- QEMU：`.work/f1/source/qemu` + `.work/f1/build/qemu`。
- 两树均从 M1 8-patch 头出发，仅有 0009+ F1 patch；M1 `.work/source`、`.work/build` 不变。
- 因宿主内存限制，LLVM/QEMU rebuild 和大型测试串行；日志写 `.work/log/integ/INTEG-103t-*`。

## 端到端范围

1. 64 identity 每个至少一个 LLVM 编码→QEMU 执行→testcases oracle 比对路径；LLVM 不参与 expected 生成。
2. 全量 active vectors 覆盖 f32/f64 四舍入、flags、±0、subnormal、Inf、NaN、转换、FMA、remainder、scaleB、root/log；D11–D17、六个 active OPEN-ID 或其它无唯一答案的 case 保持 BLOCKED，`D17:S2` 仅保留来源追踪、`D17:S7` 属 spec-determined non-gap。
3. `set.ft/set.fo` 另做 pseudo E2E：验证展开的真实序列在 QEMU 达到预期 RF bit-pattern，且 objdump 只显示真实指令。
4. M1 回归的权威门槛至少保持 `747 total / 739 passed / 0 failed / 8 deferred / 0 errors`；F1 新增用例须单独报数，不能改变/吞并 M1 基线计数。
5. M1 MC lit、spec drift、vector validator、interface checker、QEMU harness 和 repository checks 均复跑。

### D17 OPEN-ID ledger 的 E2E 状态

最终报告必须逐键列出 `D17 OPEN-ID ledger` 的 active 精确集合 {D17:S1,D17:S3,D17:S4,D17:S5,D17:S6,D17:S8}（六键）；六项在没有规范事实或逐条 Accepted decision 时保持 blocked，关闭条件取 `resolution.rule_tables.D17`。`D17:S2` 始终是 ledger 外 trace-only（`no behavioral consequence; resolved/trace-only; not in D17 OPEN-ID ledger; never PASS`），不是缺口；`D17:S7` 始终是 ADR-1008 D1 已证明的 spec-determined non-gap（move overlap 由 SimRISC-00:41-46 与 SimRISC-03:34-50 唯一确定），不进入 active ledger、不计 OPEN/BLOCKED、不计 PASS。rf0 layout 的 E2E 可观测性不等于 `D17:S1` reset PASS；任何 SBZ 结果与 `sbz_write_silent_ignore_domains` 不一致即 FAIL。当前 M1 基线可跑；F1 runtime/E2E 与 ledger 关闭仍 BLOCKED。

## SPEC-104t 已投影的适用规则

语义激活门禁：`SPEC-104t` 已验证，且本任务所消费的 ADR-1009～1015 全部 Accepted；在此之前 `contracts/f1_gap_proofs.yaml` 的 `resolution` 层只表示 projected-pending-activation，不得当作 active implementation truth，也不得据此声称任何 facet PASS。

`SPEC-104t` 的 `resolution.resolution_matrix` 逐行给出 64 个 identity 的 owning consumer、适用 decision 与已关闭 facet；本任务必须按下列**投影规则**执行，而不是「参见 ADR」自行取义：

| 规则 | `resolution` 投影位置 | 本任务必须表达/实现的精确内容 |
| --- | --- | --- |
| D11 rf0 读写 | `rule_tables.D11` | 全部 64 个 identity 均可读 rf0；以 rf0 为目的只有十条白名单 `ld.t-rf,ld.o-rf,ldm.t-rf,ldm.o-rf,set.w-rf,cs.eq-rf,cs.ne-rf,cs.n-rf,cs.z-rf,cs.p-rf` 合法，其它 RF destination 写 rf0 一律 ILLI（`rd2rf→rf0` 明确 ILLI）；`s6_scope_relation` 记录历史六条 `6-1+5=10` |
| D12 FCSR flags | `rule_tables.D12` | 硬件异常 sticky OR；无异常指令保持既有 rf0[4:0] 不清零；合法软件写立即生效并按程序顺序与自动异常组合；自动置位精确 53 条、非自动 11 条 |
| D13 tetra 高半部 | `rule_tables.D13` | 18 条 tetra 写 RF identity 高 32 位固定 `0xffffffff`；`ld.t-rf`/`ldm.t-rf` 同样 64 位 NaN-boxing；先形成 64 位写值，合法写 rf0 时再套只读位与 SBZ mask |
| D14 unordered 比较 | `rule_tables.D14` | `foqcmp`/`ftqcmp` unordered 写 RD `0x7ff8000000000000`；`foscmp`/`ftscmp` unordered 写 RD `0x7ff0000000000001`；输出只由 qcmp/scmp 类别决定，不依赖输入 NaN 的 quiet/signaling 类别 |
| D15 NaN 传播 | `rule_tables.D15` | 18 条算术 identity 丢弃 payload 与符号返回 canonical qNaN（qNaN 不置 NV、任一 sNaN 置 NV）；`fo2ft`/`ft2fo` 按 SimRISC-03 规范正文传播 payload、sNaN 转换置 NV 并返回 qNaN、结果符号固定为正；`canonical_qnan_bits` 在 ADR-1013 中未给出 64 位常量，本层留 `null`，下游不得代填 |
| D16 tininess/复合 flags | `rule_tables.D16` | 36 条 identity 在**最终舍入后**检测 tininess；underflow 同时置 `UF+NX`，overflow 同时置 `OF+NX` |
| D17 六个 active OPEN-ID | `rule_tables.D17` | S1 reset：`rf0[17:16]=00`（RNE）、`rf0[4:0]=0`；S3 classify immediate：`ftcls/focls immu6!=1` 在 assembler 阶段拒绝、非 assembler 路径到达硬件则 ILLI；S4 fault priority：ILLI 先于 MALIGN，非法编码/操作数不进入对齐判定；S5 scaleB：浮点 `rfhd` 按当前 rf0[17:16] 舍入成整数 n 后算 `rfhc×2^n`，同一模式也控制最终结果舍入，指数 qNaN→canonical qNaN 且指数分类不置 flags、sNaN→NV+canonical qNaN、`+Inf`→`+Inf`、`-Inf`→比例因子 0；S6 SBZ 写：仅十条白名单在写 rf0 时对 `[50:32]`/`[21:18]`/`[15:5]` 静默忽略；S8 ldm/stm：EA0=`rbhb+rdhc`、第 i 项地址 `EA0+i×width`、`.t` width/step=4 与 `.o`=8、RF 编号递增、任一元素 fault 时整条不提交任何 RF 写或 memory store 且 PC 留在 faulting instruction |
| 交叉优先级 | `precedence` | PRE-1～PRE-5：D11 目的合法性先于 D17:S6；D13 先成 64 位写值再套只读/SBZ；D15 格式转换规则优先于算术 canonical 规则；D17:S4 的 ILLI 先于 MALIGN；D12 软件写与自动异常按程序顺序组合 |

`rootn(-0,2)` 继续是 `explicitly-unspecified`（`foroot`/`ftroot` 的 `remaining_unspecified`），任何被激活都不得为它生成唯一 expected；root/log 的独立正确舍入算法与 schema/oracle/vector、LLVM MC、QEMU 实现、E2E 全部仍按真实能力 BLOCKED，ADR Accepted 只解除语义选择门禁。

## 判据

| # | 判据 | 可执行性 |
| --- | --- | --- |
| 1 | 64 identity E2E 路径均存在；所有 active required facet 0 FAIL/ERROR | **BLOCKED**：上游实现、向量与 F1 builds 尚未完成；替代证据为 `INTEG-102t` 矩阵合同 |
| 2 | IEEE 边界矩阵逐项闭合，ordinary-number smoke 不单独计完成 | **BLOCKED**：独立 oracle/QEMU 尚未闭合且 OPEN/S 项存在；替代证据为 blocked 矩阵，不能替代最终动态运行 |
| 3 | pseudo 展开 E2E 正确且 disassembler 不折叠 | **BLOCKED**：LLVM-103t 与对应 QEMU 真指令尚未完成；替代证据为展开/打印合同 |
| 4 | M1 权威 747/739/0/8/0 精确复现，0001–0008/M1 树哈希不变 | 现在可跑：当前 M1 基线可复验；F1 最终运行后仍必须重新复验，不能沿用当前日志 |
| 5 | D11–D17 与六个 active OPEN-ID 所有受影响 facet active | **BLOCKED**：仅在七份 ADR 全部 Accepted 且实现/向量完成后可跑；替代证据为 `resolution.resolution_matrix` 的 64 行适用 decision 与 OPEN/S-ID 清单 |
| 6 | root/log 全域正确舍入 | **BLOCKED**，若 TESTCASES-102t 独立 oracle 能力未闭合；替代证据为可证明子集和明确缺口 |

## 独立验证与反例

先枚举所有实际 checker/runner/oracle。逐个注入至少一种非空反例：错 object bit、错 RF expected bit、错 rounding mode、FMA 两步化、remainder fmod 化、QEMU trans 回 ILLI、pseudo 顺序错、M1 单例 expected 翻 bit、把任一 OPEN/S blocked 偷改 active。必须取得真实 FAIL/非零，且输出不同于未注入运行。注入只在 `/tmp/opencode/INTEG-103t/` 隔离树；还原源码后必须重建 LLVM/QEMU，再复跑对应正例和最终全量，不能用陈旧二进制。手写探针须回读操作数，条件分支全文件逐条核对并做单断言反向注入。

## 完成区

由 engineer 执行后填写；分列 M1、F1 active、F1 BLOCKED、64 facet、pseudo、反例、还原/重建及资源数据。
