# INTEG-102t: F1 跨模块接口与 64 facet 对齐

**模块**：integ  
**项目里程碑**：F1  
**状态**：待开始  
**依赖**：`SPEC-102t re-Accepted`、`SPEC-103t`、`SPEC-104t` 的 `resolution` 层（ADR-1009～1015 现行 27 条 decision）、`TESTCASES-101t`、`TESTCASES-102t`、`LLVM-101t`~`103t`、`QEMU-101t`~`103t`；七份 ADR 必须在 `SPEC-104t` 已验证后全部 Accepted 才解除语义门禁

## 目标

独立核对 spec contract、机器编码、testcases schema/oracle/vectors、LLVM MC 和 QEMU 对同一 64 identity/facet 的名称、编码、operand、合法性与可观测语义完全对齐。发现不一致必须退回唯一所有者，不在 INTEG 私建修正规则。

## 固定集合

- 18：`ld.t-rf st.t-rf ld.o-rf st.o-rf ldm.t-rf stm.t-rf ldm.o-rf stm.o-rf set.w-rf rd2rf rf2rd ftmadd fomadd cs.eq-rf cs.ne-rf cs.n-rf cs.z-rf cs.p-rf`。
- 46：`ftcls ft2fo ft2ft ftroot ftlog focls fo2ft fo2fo foroot folog ft2it ft2io ft2ut ft2uo it2ft io2ft ut2ft uo2ft fo2it fo2io fo2ut fo2uo it2fo io2fo ut2fo uo2fo ftadd ftsub ftmul ftdiv ftrem ftsclb ftsgnn ftsgnj foadd fosub fomul fodiv forem fosclb fosgnn fosgnj ftqcmp ftscmp foqcmp foscmp`。
- pseudo：`set.ft,set.fo` 单列，不进入 64；assembler 展开，disassembler 不折叠。

## 交付物

`docs/` 下 F1 interface alignment 报告、`tools/integ/` 下结构化 checker，以及 64×facet 矩阵。每行至少含 contract citation、opcode/mask/value、LLVM asm/disasm、test vector/oracle、QEMU trans/semantic、状态 active/BLOCKED/NA 和 OPEN/S-ID。

## 对齐规则

- `excluded_m1: true` 在所有视图保留历史含义，F1 scope 明确；不能用删除标记对齐。
- TESTCASES 是 oracle/schema 接口所有者；LLVM/QEMU 不得出现平行 RF/FCSR 字段。
- QEMU trans 存在只证明覆盖，不证明语义；语义列必须由独立 vector/harness 证据填充。
- D11–D17 与六个 active OPEN-ID 未由规范事实或逐条 Accepted decision 关闭的 facet 必须在所有消费者一致 BLOCKED；`D17:S2` 单列为无行为后果的来源差异，`D17:S7` 单列为 spec-determined non-gap。任一实现偷选语义均为 FAIL，不是“领先完成”；语义承载方固定为 ADR-1009～1015，不得预设其它 ADR 编号。
- LLVM/QEMU patch 只允许 0009+；M1 0001–0008 与 M1 工作树哈希不变。

### D17 OPEN-ID ledger 对齐

矩阵中的 `D17 OPEN-ID ledger` 必须逐项使用完整键，其 active 精确集合为 {D17:S1,D17:S3,D17:S4,D17:S5,D17:S6,D17:S8}（六键）：`D17:S1` reset、`D17:S3` classify immediate、`D17:S4` fault priority、`D17:S5` scaleB exponent、`D17:S6` SBZ write、`D17:S8` ldm/stm memory，六者在七份 ADR 全部 Accepted 前保持 blocked。`D17:S2` 始终是 ledger 外 trace-only（`no behavioral consequence; resolved/trace-only; not in D17 OPEN-ID ledger; never PASS`），不是缺口；`D17:S7` 始终是 ADR-1008 D1 已证明的 spec-determined non-gap（move overlap 由 SimRISC-00:41-46 与 SimRISC-03:34-50 唯一确定），不进入 active ledger、不计 OPEN/BLOCKED、不计 PASS。rf0 layout/mask 单列为 spec-determined，不得与 `D17:S1` reset 合并；任一消费者规定的 SBZ 动作与 `rule_tables.D17.sbz_write_silent_ignore_domains` 不一致即 FAIL。当前跨任务 marker/dependency 静态核对可跑；64×facet 动态对齐仍 BLOCKED 于全部上游产物。

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

## 验收

| # | 判据 | 可执行性 |
| --- | --- | --- |
| 1 | checker 报 identity 64/64、pseudo 2 单列、无重名/缺失/额外项 | **BLOCKED**：跨模块 checker 和下游产物尚未完成；替代证据为 SPEC 64 清单与 pseudo 排除规则 |
| 2 | 64 行编码/operand/合法性在 contract、LLVM、QEMU、vectors 间零 mismatch | **BLOCKED**：LLVM/QEMU/vectors 尚未完成；替代证据为唯一所有者和字段映射合同 |
| 3 | 每个 required facet 有独立证据或明确 BLOCKED+OPEN/S-ID；覆盖不冒充语义 | **BLOCKED**：矩阵尚未产出；替代证据为 `SPEC-103t` 阻塞表要求和本书状态词表 |
| 4 | RF/FCSR schema 只有 TESTCASES-101t 定义的一套 | **BLOCKED**：schema 尚未冻结且消费者尚未实现；替代证据为 ADR-1004 D10 和单一所有权规则 |
| 5 | 所有 OPEN/S facet 对齐为 active | **BLOCKED**：等待对应 decisions 逐条 Accepted 与下游实现；替代证据为跨模块一致 BLOCKED，不能替代最终关闭 |

## 反例门禁

checker 必须能分别抓住：LLVM opcode 偏 1、QEMU trans 缺一条、vector identity 拼错、pseudo 混入 64、某消费者将任一 OPEN/S 项标 PASS、漏掉 S1–S8 一行、平行 `expected_rf` 字段。每次在 `/tmp/opencode/INTEG-102t/` 合成树证明 diff 非空、真实非零、还原 clean、复绿。若反例涉及组件源，恢复后重建对应二进制；静态 checker 不能代替重建后的动态证据。

## 完成区

由 engineer 执行后填写；记录 64×facet 汇总、mismatch、BLOCKED 与逐 checker 反例。
