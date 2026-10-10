# QEMU-101t: F1 RF 状态、存取、搬移与 `set.w`

**模块**：qemu  
**项目里程碑**：F1  
**状态**：待开始  
**依赖**：`SPEC-102t re-Accepted`、`SPEC-103t` 的 `D17 OPEN-ID ledger` 阻塞表、`SPEC-104t` 的 `resolution` 层、`TESTCASES-101t`、`INFRA-108t`；本任务所消费的 ADR-1009（D11）、ADR-1010（D12）、ADR-1011（D13）、ADR-1015（D17:S1/S4/S6/S8）必须在 `SPEC-104t` 已验证后逐份 Accepted 才实现对应行为

## 目标

在 QEMU DADAO target 建立 64×64-bit RF 状态及 testcases 定义的 RF/FCSR 观测接口，实现 11 个基础 identity：`ld.t-rf, st.t-rf, ld.o-rf, st.o-rf, ldm.t-rf, stm.t-rf, ldm.o-rf, stm.o-rf, set.w-rf, rd2rf, rf2rd`。组件 patch 从 QEMU `0009+` 追加，M1 0001–0008 不变。

## 语义合同

- 数据/指令均按现有大端模型；tetra 4 字节对齐，octa 8 字节对齐，错误触发 MALIGN。
- 块数 `immu6=1..63`，任一开始寄存器 + count 不得超过 64；0/越界 ILLI。`ldm/stm` 的内存侧地址与步长按 `resolution.rule_tables.D17.ldm_stm_*`（EA0=`rbhb+rdhc`、第 i 项地址 `EA0+i×width`、`.t`=4 与 `.o`=8、RF 编号递增、任一元素 fault 整条不提交且 PC 留在 faulting instruction）实现；`rd2rf`/`rf2rd` 的跨寄存器组块赋值方向是 ADR-1008 D1 证明的 spec-determined non-gap，不是缺口，但重叠顺序不得由本任务自行发明：写向固定为 RF←RD，读向固定为 RD←RF。
- `set.w` 仅改目标 16-bit wyde，其余 48 位保持。
- rf0 为 FCSR；字段布局按 contract 建模。复位值取 `resolution.rule_tables.D17.reset_rounding_mode=RNE`（`rf0[17:16]=00`）与 `reset_flags=0`；SBZ 位非零写入取 `sbz_write_silent_ignore_domains=['[50:32]','[21:18]','[15:5]']` 的静默忽略，且**仅**对 D11 十条写白名单生效，其余域按各自规则。D12 flags 更新/保持/清除取 sticky OR、无异常保持、合法软件写立即生效。在 `SPEC-104t` 已验证且相应 ADR Accepted 之前，上述取值一律 blocked，本任务只建立布局/可观测接口和 blocked vectors。
- tetra 写 RF 高 32 位取 `resolution.rule_tables.D13.tetra_high_half_bits=0xffffffff`，且只作用于 `write_scope` 中的 `ld.t-rf` 与 `ldm.t-rf`（本任务 11 identity 内的全部适用项）；在 ADR-1011 Accepted 前，对依赖高半部取值的断言保持 BLOCKED，实现不得偷选语义。
- QEMU 必须消费 TESTCASES-101t schema/dump 接口，不可定义平行 `expected_rf` 格式。

## D17 OPEN-ID ledger 与运行时 scope

`D17 OPEN-ID ledger` 的 active 精确键集合为 {D17:S1,D17:S3,D17:S4,D17:S5,D17:S6,D17:S8}（六键）。本任务 11 identity 的适用状态：`D17:S1`（reset）projected-pending-activation、`D17:S3` N/A(runtime)、`D17:S4`（组合 fault）projected-pending-activation、`D17:S5` N/A(runtime)、`D17:S6`（SBZ write）projected-pending-activation、`D17:S8`（ldm/stm memory）projected-pending-activation。`D17:S2` 始终是 ledger 外 trace-only（`no behavioral consequence; resolved/trace-only; not in D17 OPEN-ID ledger; never PASS`），不是缺口；`D17:S7` 始终是 ADR-1008 D1 已证明的 spec-determined non-gap（move overlap 由 SimRISC-00:41-46 与 SimRISC-03:34-50 唯一确定），不进入 active ledger、不计 OPEN/BLOCKED、不计 PASS。rf0 layout/mask 是现在可消费的结构 facet，但不能替代 `D17:S1` reset 或 `D17:S6` 的语义门禁。当前 11 identity 清单、补丁边界和 marker 静态核对可跑；任何 QEMU 语义/动态向量仍 BLOCKED 于实现及适用 decision。

## 交付物

QEMU `0009+` patch、必要的仓库侧最小 ROM probe/harness 扩展和 11 identity 向量回放。RF/FCSR dump 应以整数 bit-pattern 输出；不得经过宿主 float 格式化。

## SPEC-104t 已投影的适用规则

语义激活门禁：`SPEC-104t` 已验证，且本任务所消费的 ADR-1009～1015 全部 Accepted；在此之前 `contracts/f1_gap_proofs.yaml` 的 `resolution` 层只表示 projected-pending-activation，不得当作 active implementation truth，也不得据此声称任何 facet PASS。

本任务拥有 11 个 identity（`ld.o-rf,ld.t-rf,ldm.o-rf,ldm.t-rf,rd2rf,rf2rd,set.w-rf,st.o-rf,st.t-rf,stm.o-rf,stm.t-rf`），在 `resolution.resolution_matrix` 中 `owning_consumer` 均为 `QEMU-101t`。精确适用规则：

| 规则 | `resolution` 投影位置 | 本任务 11 identity 的精确取值 |
| --- | --- | --- |
| D11 rf0 读 | `rule_tables.D11.rf0_read` | 11 个 identity 全部允许以 rf0 为源 |
| D11 rf0 写 | `rule_tables.D11.rf0_write_whitelist` | 白名单命中 5 条：`ld.o-rf,ld.t-rf,ldm.o-rf,ldm.t-rf,set.w-rf`；`rd2rf` 写 rf0 明确 ILLI（`rule_tables.D11.rd2rf_to_rf0`）；`rf2rd`/`st.*-rf`/`stm.*-rf` 不以 rf0 为目的 |
| S6 范围关系 | `rule_tables.s6_scope_relation` | SPEC-103t 历史六条 `6-1+5=10`：移出 `rd2rf`、加入五条 `cs.*-rf`；历史六条本身不得被改写成十条来伪装历史 |
| D12 flags | `rule_tables.D12.non_automatic_scope` | 本任务 11 个 identity **全部**属非自动置位集合（`non_automatic_scope_count=11`），搬运位模式不得自动置位或清除 rf0[4:0] |
| D13 高半部 | `rule_tables.D13.write_scope` / `load_scope` | 适用 2 条：`ld.t-rf`、`ldm.t-rf`，高 32 位固定 `0xffffffff` |
| D17:S1 reset | `rule_tables.D17.reset_*` | 11 条全适用：`rf0[17:16]=00`（RNE）、`rf0[4:0]=0` |
| D17:S4 fault | `rule_tables.D17.fault_priority` | 适用 6 条：`ldm.o-rf,ldm.t-rf,rd2rf,rf2rd,stm.o-rf,stm.t-rf`（本任务 11 条中 fault 谓词 >= 2 的子集）；ILLI 优先于 MALIGN，非法编码/操作数不进入对齐判定 |
| D17:S6 SBZ | `rule_tables.D17.sbz_write_silent_ignore_domains` | 适用 5 条：`ld.o-rf,ld.t-rf,ldm.o-rf,ldm.t-rf,set.w-rf`（现行十条白名单中属本任务的 5 条）；`rd2rf` 已按 D11 判 ILLI，不在现行 scope 内；命中时对 `[50:32]`、`[21:18]`、`[15:5]` 静默忽略 |
| D17:S8 ldm/stm | `rule_tables.D17.ldm_stm_*` | 适用 4 条：`ldm.o-rf,ldm.t-rf,stm.o-rf,stm.t-rf`；EA0=`rbhb+rdhc`、地址 `EA0+i×width`、`.t`=4/`.o`=8、RF 编号递增、fault 时整条不提交且 PC 留在 faulting instruction |

语义选择门禁解除**不等于**实现 PASS：QEMU F1 实现/build 尚未产出，全部动态判据保持 BLOCKED。

## 验收

| # | 判据 | 可执行性 |
| --- | --- | --- |
| 1 | 11 identity 的 active 向量全部通过，RF/RD/memory 可独立回读 | **BLOCKED**：QEMU F1 尚未实现；替代证据为 11 identity 清单、已投影/未激活 facet 分栏和 schema 合同 |
| 2 | 4/8 对齐、count 0/63/越界、末端 rf63 均有正反例；地址步长按 D17:S8 投影验证、块赋值方向按 spec-determined non-gap 验证 | **BLOCKED**：实现与向量尚未产出；替代证据为已决 legality 谓词与 blocked 用例要求 |
| 3 | rf0 layout/可观测 mask 符合 contract；复位、SBZ 非零写入与 flags 行为按 ADR-1015/ADR-1010 投影验证 | layout/mask 静态合同现在可跑；运行时复位、SBZ 与 flags **BLOCKED**：等待 `SPEC-104t` 已验证且 ADR-1010/ADR-1015 Accepted、并完成实现；替代证据为 `resolution.rule_tables` 的分栏合同和 blocked vectors |
| 4 | M1 747 基线零新增失败；QEMU patch 仅 0009+ | M1 基线与当前补丁边界现在可跑；F1 变更后的“零新增失败” **BLOCKED** 于实现，替代证据为冻结 hash/series 门禁 |
| 5 | tetra 写高半部精确值 | **BLOCKED**：等待 ADR-1011 Accepted 与实现；替代证据为低 32 位与可观测 mask、blocked 用例 |
| 6 | rf0 作为 sign source 的优先级 | **BLOCKED**：属 QEMU-102t，且需 ADR-1009 Accepted 后按十条写白名单判定；替代证据为 OPEN-ID 和不依赖该形式的基础状态接口，本任务不声称 PASS |

## 反例、还原与重建

枚举 decoder checker、probe、vector runner、dump checker。注入：把一条 trans 恢复 ILLI、去掉 MALIGN、允许 count=0、写坏 `set.w` 其余位、把 `D17:S1`/`D17:S4`/`D17:S6`/`D17:S8` 的 blocked 偷改 active；待 ADR-1015 Accepted 后，再注入与 `resolution.rule_tables.D17.ldm_stm_*` 相反的地址/步长/编号实现，以及与 `sbz_write_silent_ignore_domains` 相反的 SBZ 实现。每次先证明 diff 非空并真实 FAIL。注入只在 `/tmp/opencode/QEMU-101t/` 隔离树；恢复源码后必须重建 `qemu-system-dadao`，再跑反例对应正例和 M1 smoke，防止陈旧二进制。探针写入值须回读验证，分支目标/极性须全文件逐条核对并做“只改 expected → FAIL”。

## 完成区

由 engineer 执行后填写；记录 11 identity、patch、异常、M1 回归、反例和重建。
