# TESTCASES-102t: F1 独立浮点 oracle 与全量向量

**模块**：testcases  
**项目里程碑**：F1  
**状态**：待开始  
**依赖**：`SPEC-102t re-Accepted`、`TESTCASES-101t`、`SPEC-103t`、`SPEC-104t` 的 `resolution` 层（ADR-1009～1015 现行 27 条 decision 的机器投影）；每个完整 OPEN-ID 仅在 `SPEC-104t` 已验证且对应 ADR-1009～1015 逐条 Accepted 后解除 BLOCKED

## 目标

实现由 testcases 拥有、从 spec/contract 独立派生的浮点 oracle、可复现生成器和 64 identity 全量向量。oracle 不得从 LLVM、QEMU、QEMU SoftFloat、宿主浮点/`libm` 或参考仓生成期望。

## 覆盖合同

64 identity 集合以 `SPEC-102t` 为唯一清单。每个 identity 必须有 encoding、legality、semantic 三类 required facet 中适用项；不适用须写理由。数值族至少系统覆盖：

- f32/f64：RNE/RTZ/RDN/RUP；精确与 inexact；±0；最小/最大 subnormal；最小 normal；最大 finite；±Inf；qNaN/sNaN。
- 转换：有/无符号 32/64 位边界、饱和、溢出、inexact、块数 1/63、0 与越界 ILLI、重叠先读后写。
- add/sub/mul/div：零、无穷、NaN、溢出/下溢、除零及 flags。
- FMA：能区分融合单次舍入与 `mul+add` 两次舍入的向量。
- remainder：能区分 IEEE nearest-even quotient 与语言 `%/fmod` 的向量。
- scaleB、root(2/3)、log(base 2/e/10) 的边界和非法 immediate。
- sign、compare、conditional assign、10 类 classify、RF load/store/set/move 与 rf0/FCSR。

任何 spec 无唯一结果（含 D11–D17、六个 active OPEN-ID、`rootn(-0,2)`）必须 blocked，不能生成伪 expected。`D17:S2` 保留为无行为后果的来源说明，`D17:S7` 属 spec-determined non-gap，二者都不凭空制造 expected。

## 交付物

- `tools/testcases/` 下独立 oracle、向量生成器、全量语义复算器及单元测试；入库向量的生成器必须随产物保留。
- `tests/vectors/isa/` 下按稳定族划分的 F1 YAML；inventory/coverage 与 validator 同步。
- facet 覆盖矩阵：64 identity × encoding/legality/semantic/IEEE edge/OPEN-ID。
- 独立全量重算命令，逐例读取 spec 派生算法输出并与已提交 expected 比对。

## 独立性要求

可使用整数/有理数/任意精度算法作为计算机制，但算法规则必须在任务内引用 spec/contract 并可审计；不得把第三方 IEEE 实现输出直接当 oracle。对 root/log 若无法构造可证明正确舍入的独立算法，则对应 facet 保持 BLOCKED，不能用宿主 `libm` 凑值。

## D17 OPEN-ID ledger 与向量状态

向量必须使用 `D17 OPEN-ID ledger` 的完整 marker，active 精确键集合为 {D17:S1,D17:S3,D17:S4,D17:S5,D17:S6,D17:S8}（六键），分别对应 reset、classify immediate、fault priority、scaleB exponent、SBZ write、ldm/stm memory；这六个键的受影响 runtime expected 在 ADR-1009～1015 Accepted 前保持 blocked。`D17:S2` 始终是 ledger 外 trace-only（`no behavioral consequence; resolved/trace-only; not in D17 OPEN-ID ledger; never PASS`），不是缺口；`D17:S7` 始终是 ADR-1008 D1 已证明的 spec-determined non-gap（move overlap 由 SimRISC-00:41-46 与 SimRISC-03:34-50 唯一确定），不进入 active ledger、不计 OPEN/BLOCKED、不计 PASS。rf0 layout/bit mask 可作为已决结构输入，但不得据此生成 `D17:S1` reset expected；不得为 `D17:S6` 预设与 `resolution.rule_tables.D17.sbz_write_silent_ignore_domains` 不同的 SBZ 写入结果。当前 ledger/blocked 标记静态检查可跑；oracle、向量与全量重算尚未产出，动态判据仍 BLOCKED。

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
| 1 | inventory 精确覆盖 64 identity，无 pseudo、无 GOLDEN 依赖 | **BLOCKED**：inventory/向量尚未生成；替代证据为 `SPEC-102t` 的 64 清单和本书排除规则 |
| 2 | 所有 active 数值 expected 逐条独立全量重算，0 mismatch；validator 绿灯不是唯一证据 | **BLOCKED**：oracle 与向量尚未实现；替代证据为独立算法约束和逐例重算要求 |
| 3 | 四舍入模式与 IEEE 类别/facet 覆盖矩阵无未解释缺口 | **BLOCKED**：覆盖矩阵尚未产出且 OPEN/S 项未关闭；替代证据为 contract 矩阵，未决项必须明确 blocked |
| 4 | FMA/remainder/scaleB 各有能击穿常见错误实现的判别向量 | **BLOCKED**：判别向量尚未产出，且 scaleB 的 S5 解释未决；替代证据为所需错误模型清单，S5 不得伪造 expected |
| 5 | root/log 的全域正确舍入 | **BLOCKED**，若独立算法或 spec 精度规则不足；替代证据为可精确证明的子集 + 缺口/候选 ADR，不得 PASS |
| 6 | D11–D17 与六个 active OPEN-ID 对应语义向量 active | **BLOCKED**：等待 `SPEC-104t` 已验证且 ADR-1009～1015 全部 Accepted、并完成 oracle/向量产出；替代证据为 blocked 用例、OPEN/S-ID 与 `resolution.resolution_matrix` 的逐行适用 decision |

## 反例门禁

逐个枚举 validator、oracle、覆盖检查器和全量重算器；至少注入：错一个 expected bit、错 rounding mode、FMA 改为两步、remainder 改为 trunc quotient、删一个 identity、把任一 D/S blocked 改 active、把 S5 的一种解释偷写成 expected。每次须证明 diff 非空、取得真实 FAIL/非零、还原；若源码/缓存参与，清缓存并重跑。所有注入只在 `/tmp/opencode/TESTCASES-102t/`。数据错值发现后当场修，不得登记为遗留。

## 完成区

由 engineer 执行后填写；记录 active/blocked/总数、逐 checker 反例和还原证据。
