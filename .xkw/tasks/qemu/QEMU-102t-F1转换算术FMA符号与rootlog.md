# QEMU-102t: F1 转换、算术/FMA、符号与 root/log

**模块**：qemu  
**项目里程碑**：F1  
**状态**：待开始  
**依赖**：`SPEC-102t re-Accepted`、`QEMU-101t`、`TESTCASES-102t`、`SPEC-104t` 的 `resolution` 层；本任务所消费的 ADR-1009（D11）、ADR-1010（D12）、ADR-1011（D13）、ADR-1013（D15）、ADR-1014（D16）、ADR-1015（D17:S1/S4/S5）必须在 `SPEC-104t` 已验证后逐份 Accepted 才解除对应 facet

## 目标

实现 42 个 identity：20 个格式/整数转换，12 个二元算术，2 个 FMA，4 个 root/log，4 个 sign-injection；使用 QEMU in-tree SoftFloat 与按 spec 定义、可审计 helper。宿主浮点和 `libm` 不得成为语义或 oracle。

## identity 清单

- 转换 20：`ft2fo ft2ft fo2ft fo2fo ft2it ft2io ft2ut ft2uo it2ft io2ft ut2ft uo2ft fo2it fo2io fo2ut fo2uo it2fo io2fo ut2fo uo2fo`。
- 算术 12：`ftadd ftsub ftmul ftdiv ftrem ftsclb foadd fosub fomul fodiv forem fosclb`。
- FMA 2：`ftmadd fomadd`。
- root/log 4：`ftroot ftlog foroot folog`。
- sign 4：`ftsgnj ftsgnn fosgnj fosgnn`。

## 硬约束

- f32/f64 均支持 RNE/RTZ/RDN/RUP；整数转换宽度/符号/饱和与 NV；FMA 必须单次舍入；remainder 使用 nearest-even quotient 而非 fmod；scaleB 按 spec。
- root 仅 n=2/3；log immediate 0/1/2 对应 10/e/2（并覆盖非法值 ILLI）；`rootn(-0,2)` 无唯一 expected，保持 BLOCKED。
- 一般浮点运算出现 rf0 operand 应 ILLI，但 sign-injection 的 rfhd=rf0 特例与一般规则冲突按 D11 OPEN；不得自行裁决。
- flags 取 D12 sticky OR / 无异常保持 / 合法软件写立即生效；tininess 取 D16 最终舍入后检测且 underflow 置 `UF+NX`、overflow 置 `OF+NX`；NaN 取 D15 算术 canonical qNaN 与 `fo2ft`/`ft2fo` 的 payload 传播（结果符号固定为正）。rf0 复位取 D17:S1（`rf0[17:16]=00`、`rf0[4:0]=0`）、多 fault 优先级取 D17:S4（ILLI 先于 MALIGN）、`ftsclb`/`fosclb` 指数取 D17:S5。上述取值在相应 ADR Accepted 之前一律 blocked，不得默认、也不得声称未决位、初始化、复合异常或 scaleB 解释正确。

## 交付物

QEMU `0009+` patch、helper/SoftFloat glue、42 identity 的 testcases 向量回放和定向 probe。若 in-tree SoftFloat 无直接 root3/log，helper 算法必须由 spec 可审计地定义并由独立 oracle 验证；能力不足则相应 identity 保持 BLOCKED，而不是调用宿主 `libm`。

## D17 OPEN-ID ledger 与运行时 scope

`D17 OPEN-ID ledger` 的 active 精确键集合为 {D17:S1,D17:S3,D17:S4,D17:S5,D17:S6,D17:S8}（六键）。本任务 42 identity 的适用状态：`D17:S1`（reset）projected-pending-activation、`D17:S3` N/A(runtime)、`D17:S4`（fault priority）projected-pending-activation、`D17:S5`（scaleB exponent）projected-pending-activation、`D17:S6` N/A(runtime)、`D17:S8` N/A(runtime)。ledger 完整键必须进入 facet 报告，不得退化为裸 `S*`；`D17:S2` 始终是 ledger 外 trace-only（`no behavioral consequence; resolved/trace-only; not in D17 OPEN-ID ledger; never PASS`），不是缺口；`D17:S7` 始终是 ADR-1008 D1 已证明的 spec-determined non-gap（move overlap 由 SimRISC-00:41-46 与 SimRISC-03:34-50 唯一确定），不进入 active ledger、不计 OPEN/BLOCKED、不计 PASS。rf0 layout 可消费而 reset 仍受 ADR-1015 门禁；已投影数值子集 PASS 不解锁任何 blocked facet。当前 identity/scope 静态检查可跑；42 identity 动态语义和受影响边界均 BLOCKED 于实现、向量和对应 decision。

## SPEC-104t 已投影的适用规则

语义激活门禁：`SPEC-104t` 已验证，且本任务所消费的 ADR-1009～1015 全部 Accepted；在此之前 `contracts/f1_gap_proofs.yaml` 的 `resolution` 层只表示 projected-pending-activation，不得当作 active implementation truth，也不得据此声称任何 facet PASS。

本任务拥有 42 个 identity，在 `resolution.resolution_matrix` 中 `owning_consumer` 均为 `QEMU-102t`。精确适用规则（括号内为 `resolution` 投影位置）：

| 规则 | 本任务 42 identity 的精确取值 |
| --- | --- |
| D11 rf0 读/写（`rule_tables.D11`） | 42 个 identity 全部允许以 rf0 为源；其中 24 个以 RF 为目的，而十条写白名单不含任何一条转换/符号位/分类 identity，故这 24 条写 rf0 一律 ILLI |
| D12 flags（`rule_tables.D12`） | 42 条**全部**属 `automatic_scope`（53 条），sticky OR、无异常保持、合法软件写按程序顺序叠加 |
| D13 高半部（`rule_tables.D13`） | 适用 16 条 tetra 写 RF identity，高 32 位固定 `0xffffffff`；本任务不含 `ld.t-rf`/`ldm.t-rf`（属 QEMU-101t） |
| D15 NaN（`rule_tables.D15`） | 算术 18 条：非格式转换时丢弃 payload 与符号返回 canonical qNaN，qNaN 不置 NV、任一 sNaN 置 NV；转换 2 条 `fo2ft`/`ft2fo`：按规范正文传播 payload、sNaN 置 NV 并返回 qNaN、结果符号固定为正，且转换规则优先于算术 canonical 规则；`canonical_qnan_bits` 为 `null`，ADR-1013 未给 64 位常量，本任务不得自行编造编码 |
| D16 tininess（`rule_tables.D16`） | 适用 36 条，最终舍入后检测 tininess；underflow 置 `UF+NX`、overflow 置 `OF+NX` |
| D17:S1 / S4 / S5（`rule_tables.D17`） | S1 适用全部 42 条；S4 适用 20 条（本任务 42 条中 fault 谓词 >= 2 的子集）；S5 只适用 `ftsclb`、`fosclb` 两条，取值见下 |
| scaleB 指数（`rule_tables.D17.scaleb_*`） | 把浮点 `rfhd` 按当前 rf0[17:16] 舍入成整数 n 后算 `rfhc×2^n`，同一舍入模式也控制最终结果舍入；指数 qNaN → canonical qNaN 且指数分类本身不置 flags；sNaN → NV + canonical qNaN；`+Inf` → `+Inf` 指数；`-Inf` → 比例因子 0（后续乘法按浮点规则决定结果与 flags） |

`foroot`/`ftroot` 的 `rootn(-0,2)` 继续是 `explicitly-unspecified`，不得生成 expected；root/log 的独立正确舍入算法属能力缺口。实现/build/向量尚未产出，全部动态判据保持 BLOCKED。

## 验收

| # | 判据 | 可执行性 |
| --- | --- | --- |
| 1 | 42 identity 的所有 active vectors 通过，且按 identity/facet 报数 | **BLOCKED**：实现/向量尚未完成，部分 facet 受 D/S 门禁；替代证据为 42 identity 清单和 active/blocked 分栏要求 |
| 2 | 四舍入、±0/subnormal/Inf/NaN、转换边界、FMA 单舍入、remainder/scaleB 判别向量通过 | **BLOCKED**：依赖独立 oracle 与实现；S5 未决时 scaleB expected 必须 blocked，替代证据为其余已决 facet 的向量合同 |
| 3 | 非法 count/root/log immediate 和 rf0 已决非法形式触发精确 ILLI，无部分写 | **BLOCKED**：QEMU 尚未实现且 D11/S4 影响部分组合；替代证据为已决 legality 清单和 fault-priority blocked cases |
| 4 | 源码审计无宿主 float/`libm` 作为规范路径；M1 回归无新增失败 | **BLOCKED**：F1 源码尚未产出；替代证据为 ADR-1004 D7 和当前 M1 基线，完成时必须动态复跑 |
| 5 | sign 的 rf0 特例优先级 | **BLOCKED**：D11 对应 decision 未 Accepted；替代证据为两方案影响与 blocked vectors |
| 6 | flags/tininess/NaN、复位、多 fault 优先级与 scaleB 的精确语义 | **BLOCKED**：等待 ADR-1010/ADR-1013/ADR-1014/ADR-1015 Accepted 并完成实现与向量；替代证据为 `resolution.rule_tables` 的数值/已投影子集 + OPEN/S-ID |
| 7 | root3/log 全域正确舍入 | **BLOCKED**，若 spec/独立 oracle 不足；替代证据为可证明输入子集和能力缺口，不得用 libm PASS |

## 反例、还原与重建

至少注入：舍入模式固定 RNE、FMA 拆成 mul+add、remainder 改 fmod、subnormal flush-zero、符号位反转、非法 immediate 放行、trans 回退 ILLI、把 S5 或其它 OPEN/S 项偷改 active。每个 checker/runner 都须有自身 FAIL 路径，diff 非空。仅在 `/tmp/opencode/QEMU-102t/` 注入；恢复源码后全量重建相关 QEMU target并复绿。探针值构造后先回读，所有条件分支全文件核对落点并进行单断言反向注入。

## 完成区

由 engineer 执行后填写；active/BLOCKED 分列，记录 42 identity、四舍入/类别计数、反例、重建与 M1 回归。
