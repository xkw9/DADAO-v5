# QEMU-103t: F1 比较、条件赋值、分类与 FCSR 回归

**模块**：qemu  
**项目里程碑**：F1  
**状态**：待开始  
**依赖**：`SPEC-102t re-Accepted`、`QEMU-102t`、`TESTCASES-102t`、`SPEC-104t` 的 `resolution` 层；本任务所消费的 ADR-1009（D11）、ADR-1010（D12）、ADR-1012（D14）、ADR-1015（D17:S1/S3/S4）必须在 `SPEC-104t` 已验证后逐份 Accepted 才解除相关 BLOCKED

## 目标

实现剩余 11 identity 并完成 FCSR 横切回归：比较 `ftqcmp ftscmp foqcmp foscmp`，RF 条件赋值 `cs.n-rf cs.z-rf cs.p-rf cs.eq-rf cs.ne-rf`，分类 `ftcls focls`。使 QEMU 总映射达到 11+42+11=64。

## 语义合同

- ordered compare 写 RD：大于 1、等于 0、小于 -1；unordered 的精确 RD 位型取 `resolution.rule_tables.D14`：`foqcmp`/`ftqcmp` 写 `0x7ff8000000000000`、`foscmp`/`ftscmp` 写 `0x7ff0000000000001`，且只由 qcmp/scmp 指令类别决定，不依赖输入 NaN 的 quiet/signaling 类别（`input_class_dependent: false`）。在 ADR-1012 Accepted 前保持 blocked。
- quiet/signaling compare 对 sNaN/qNaN 的 NV 行为仅按已决 contract；不得从 SoftFloat 默认行为反推。
- `cs.n/z/p` 按 rdha 符号/零/正选择两个 RF 源；`cs.eq/ne` 按两个 RD 比较选择 RF 值；必须先读后写且 bitwise copy，不做数值转换。
- `ftcls/focls` 仅置 10 类中的一位，bits[63:10]=0；覆盖 ±Inf、±normal、±subnormal、±0、sNaN、qNaN。
- FCSR sticky/覆盖、清除/保留、tininess/复合 flags 和 NaN 传播仍受 D12/D15/D16 门禁；rf0 复位 S1、`ftcls/focls immu6≠1` 合法性 S3 也不得从 QEMU/SoftFloat 默认行为反推；多 fault 优先级 S4 对本任务 11 条 identity 为 `N/A(runtime)`（见下节与规则表），不得把它写成本任务的 runtime 主张，其取值同样不得反推。

## 交付物

QEMU `0009+` patch、11 identity 向量回放、比较/分类定向 probe、FCSR 跨 QEMU-101/102/103 的回归矩阵。不得在 QEMU 自建与 TESTCASES-101t 不兼容的 RF/FCSR 接口。

## D17 OPEN-ID ledger 与运行时 scope

`D17 OPEN-ID ledger` 的 active 精确键集合为 {D17:S1,D17:S3,D17:S4,D17:S5,D17:S6,D17:S8}（六键）。本任务 11 identity 的适用状态：`D17:S1`（reset）projected-pending-activation、`D17:S3`（classify immediate）projected-pending-activation、`D17:S4` N/A(runtime)、`D17:S5` N/A(runtime)、`D17:S6`（SBZ write）projected-pending-activation、`D17:S8` N/A(runtime)。ledger 完整 marker 必须出现在 FCSR/分类 facet 报告；`D17:S2` 始终是 ledger 外 trace-only（`no behavioral consequence; resolved/trace-only; not in D17 OPEN-ID ledger; never PASS`），不是缺口；`D17:S7` 始终是 ADR-1008 D1 已证明的 spec-determined non-gap（move overlap 由 SimRISC-00:41-46 与 SimRISC-03:34-50 唯一确定），不进入 active ledger、不计 OPEN/BLOCKED、不计 PASS。rf0 layout 已知不代表 `D17:S1` reset 已知。当前 11+42+11 分解和 marker 静态核对可跑；比较/分类/FCSR 动态结果仍 BLOCKED 于实现、向量与适用 decision。

## SPEC-104t 已投影的适用规则

语义激活门禁：`SPEC-104t` 已验证，且本任务所消费的 ADR-1009～1015 全部 Accepted；在此之前 `contracts/f1_gap_proofs.yaml` 的 `resolution` 层只表示 projected-pending-activation，不得当作 active implementation truth，也不得据此声称任何 facet PASS。

本任务拥有 11 个 identity（`cs.eq-rf,cs.n-rf,cs.ne-rf,cs.p-rf,cs.z-rf,focls,foqcmp,foscmp,ftcls,ftqcmp,ftscmp`），在 `resolution.resolution_matrix` 中 `owning_consumer` 均为 `QEMU-103t`。精确适用规则：

| 规则 | `resolution` 投影位置 | 本任务 11 identity 的精确取值 |
| --- | --- | --- |
| D11 rf0 写 | `rule_tables.D11.rf0_write_whitelist` | 白名单命中 5 条 `cs.*-rf`：`cs.eq-rf,cs.ne-rf,cs.n-rf,cs.z-rf,cs.p-rf` 可写 rf0（正是 S6 范围 `6-1+5=10` 中加入的五条）；其余 6 条 `focls,ftcls,foqcmp,foscmp,ftqcmp,ftscmp` 写 RD |
| D12 flags | `rule_tables.D12.automatic_scope` | 11 条**全部**属自动置位集合，sticky OR、无异常保持、合法软件写按程序顺序叠加；条件赋值的真假两支都不得清除已置位 flags |
| D14 unordered | `rule_tables.D14` | 适用 4 条：`foqcmp`/`ftqcmp` → `0x7ff8000000000000`、`foscmp`/`ftscmp` → `0x7ff0000000000001`；`scope_count=4` |
| D17:S1 reset | `rule_tables.D17.reset_*` | 11 条全适用：`rf0[17:16]=00`（RNE）、`rf0[4:0]=0` |
| D17:S3 classify immediate | `rule_tables.D17.classify_immediate*` | 适用 2 条 `focls`、`ftcls`：`immu6!=1` 由 assembler 阶段拒绝；非 assembler 路径到达硬件则 ILLI（`classify_immediate_hardware`） |
| D17:S6 SBZ | `rule_tables.D17.sbz_write_silent_ignore_domains` | 适用 5 条：`cs.eq-rf,cs.ne-rf,cs.n-rf,cs.z-rf,cs.p-rf`（正是 S6 范围 `6-1+5=10` 中加入的五条）；命中时对 `[50:32]`、`[21:18]`、`[15:5]` 静默忽略 |
| D17:S4 fault | `rule_tables.D17.fault_priority` | 本任务 11 条均**不适用**（fault 谓词 < 2，故 `N/A(runtime)`）；规则本身仍为 ILLI 优先于 MALIGN，但不得把它算进本任务 11 条的 runtime 主张 |

实现/build/向量尚未产出，全部动态判据保持 BLOCKED；ADR Accepted 只解除语义选择门禁。

## 验收

| # | 判据 | 可执行性 |
| --- | --- | --- |
| 1 | 11 identity active vectors 全部通过；总 identity 映射 64/64 | **BLOCKED**：实现/向量尚未完成，部分 facet 仍未决；替代证据为 11+42+11 分解和 blocked 分栏 |
| 2 | compare ordered 三值、五种条件真假双向、10 类分类逐类有判别用例 | **BLOCKED**：依赖实现与独立向量；unordered/S3 未决部分保持 blocked，替代证据为已决类别清单 |
| 3 | bitwise copy、先读后写、rd0 目的/源合法性按 contract 精确处理 | **BLOCKED**：QEMU 尚未实现；替代证据为已决条件赋值合同，任何相关 OPEN/S 项单列 |
| 4 | FCSR 已决模式/flags 横跨算术、转换、比较回归，M1 无新增失败 | **BLOCKED**：依赖 QEMU-101/102/103 和向量；替代证据为 FCSR 横切矩阵要求与现有 M1 基线 |
| 5 | unordered RD 精确 NaN 位型与多 NaN 传播 | **BLOCKED**：D14/D15 对应 decisions 未 Accepted；替代证据为 unordered 检出/blocked 位型断言 |
| 6 | sticky/清除/复合 flags、复位、分类非法 immediate 与 fault priority | **BLOCKED**：等待 ADR-1010/ADR-1012/ADR-1015 Accepted 并完成实现与向量；替代证据为 `resolution.rule_tables` 的 OPEN/S 矩阵和不受影响的已投影子集 |

## 反例、还原与重建

注入 compare 极性反转、unordered 固定为 1、条件两支写同值、classify 吞掉 sign/sNaN、flags 恒清零、trans 回退 ILLI、把 S3 或任一 OPEN/S 项偷改 active。每条断言必须有可达 FAIL，禁止恒真。注入仅在 `/tmp/opencode/QEMU-103t/`，证明 diff 非空；恢复源码后重建 QEMU 并复跑 11 identity、FCSR 矩阵和 M1 smoke。探针分支全文件逐条核对“目标=分支指令地址+偏移”，并实测只改一个 expected 即 FAIL。

## 完成区

由 engineer 执行后填写；记录 11/64 计数、FCSR active/BLOCKED、反例、重建和回归。
