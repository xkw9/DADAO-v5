# INTEG-104m: F1 浮点闭环里程碑

**模块**：integ  
**项目里程碑**：F1  
**状态**：待开始  
**目标**：确认 SimRISC-03 的 64 个真实浮点 identity 已在不破坏 M1 的前提下闭合 spec/contracts→testcases→LLVM MC/disassembler→QEMU→integ。  
**关联任务**：`SPEC-101k`~`104t`、`TESTCASES-101t`~`102t`、`INFRA-108t`、`LLVM-101t`~`103t`、`QEMU-101t`~`103t`、`INTEG-102t`~`103t`；语义门禁为 `SPEC-104t` 的 `resolution` 层（ADR-1009～1015 现行 27 条 decision），七份 ADR 全部 Accepted 后才解除
**前置门禁**：`SPEC-102t re-Accepted`（返工后 reviewer+architect Accepted，且由主会话重新置 `已验证`）、`SPEC-104t` 已验证且七份 ADR-1009～1015 全部 Accepted（由主会话在双角色 Accepted 后置状态并复跑 `python3 tools/spec/check_f1_gap_proofs.py --require-active` 取绿灯）

## 里程碑边界

只核验，不补实现、不改 contract/schema/组件补丁。LLVM CodeGen、clang、libc、Linux 不属于 F1。`set.ft/set.fo` 是附加 pseudo，不计入 64；assembler 展开、disassembler 只打印真实指令。

## 硬门槛

1. 64 = 18 个 RF 相关编码 + 46 个 MISC-RF；每个 required facet 有真实 PASS 证据，无遗漏、重复或 pseudo 混入。
2. TESTCASES 独立 oracle 是唯一 expected 所有者；不存在 GOLDEN 模块，也不从 LLVM/QEMU/SoftFloat/宿主库/参考仓生成 expected。
3. f32/f64、四舍入模式、flags、±0、subnormal、Inf、NaN、转换、FMA、remainder、scaleB、root/log 的 spec 可唯一推出部分全部闭合；普通数值 smoke 不足以过门。
4. ADR-1009～1015 的 27 条现行 decision 全部 Accepted，且 `SPEC-104t` 的 `resolution` 层给出的 D11～D17、六个 active OPEN-ID 取值全部完成实现与独立验证，或由新的 Accepted ADR 明确调整 F1 范围；`D17:S2` 的“无行为后果”证明与 `D17:S7` 的 spec-determined non-gap 证明保持可追踪。Candidate 输入或 Candidate ADR 本身不能解锁里程碑；任何 blocked facet 绝不计 PASS。
5. M1 `0001`–`0008`、M1 工作树/构建入口不变；F1 隔离于 `.work/f1/**` 且 patch 仅 0009+。
6. M1 权威回归精确保持 `747 total / 739 passed / 0 failed / 8 deferred / 0 errors`，并复跑 MC/spec/vector/interface/repository 门禁。
7. reviewer 对每个实际 checker 主动注入非空反例，取得真实 FAIL；还原源码后重建并最终复绿；审查前后 dirty baseline 三件套逐字节一致。

8. 具名 `D17 OPEN-ID ledger` 的 active 精确键集合 {D17:S1,D17:S3,D17:S4,D17:S5,D17:S6,D17:S8}（六键）均有最终状态与证据：六项必须由规范事实或逐条 Accepted decision 关闭受影响 facet，否则里程碑 BLOCKED。`D17:S2` 始终是 ledger 外 trace-only（`no behavioral consequence; resolved/trace-only; not in D17 OPEN-ID ledger; never PASS`），不是缺口；`D17:S7` 始终是 ADR-1008 D1 已证明的 spec-determined non-gap（move overlap 由 SimRISC-00:41-46 与 SimRISC-03:34-50 唯一确定），不进入 active ledger、不计 OPEN/BLOCKED、不计 PASS。rf0 layout PASS 不得代替 `D17:S1` reset，且任一消费者规定的 SBZ 行为与 `resolution.rule_tables.D17.sbz_write_silent_ignore_domains` 不一致即 BLOCKED。

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
| 1 | 所有关联 `t` 已由 reviewer+architect Accepted 并由主会话置 `已验证` | **BLOCKED**：当前均未执行；替代证据为任务依赖图 |
| 2 | 64×required-facet 全绿、无 blocked facet | **BLOCKED**：等待七份 ADR Accepted、实现与独立验证；任何 D11–D17 或六个 active OPEN-ID 行为缺口存在即不得置里程碑 |
| 3 | M1 基线与冻结哈希不变 | 现在可跑（最终核验时必须重跑，不能沿用旧日志） |
| 4 | F1 全量 E2E/IEEE 边界与反例门禁 | **BLOCKED**：等待 `INTEG-103t`；替代证据不能替代最终动态运行 |
| 5 | 跨模块影响与 deferred 均已处置 | 现在可盘点；未处置影响出现时必须后移本里程碑或新增正式任务 |

## k↔m 对照

本文件与 `SPEC-101k` 一一对应：`k` 以规划、ADR-1004 和 15 本任务书落盘为收敛；本 `m` 以全部实现、独立验证、D11–D17 与六个 active OPEN-ID 行为缺口清零和 M1 不退化为收敛。只有主会话可在双角色 Accepted 后把状态从 `待开始` 置为 `里程碑`。

## 反例与最终证据要求

最终 reviewer 必须枚举所有检查器、shell 判据和 oracle，不能只复述 INTEG-103t 摘要。反例只能在 `/tmp/opencode/INTEG-104m/reviewer/` 隔离树；先证 diff 非空、取得 FAIL、还原、重建、复绿，并证明真实仓库 baseline 未变。architect 交叉复核原始日志、反例有效性、spec/ADR、跨模块影响后只给 `Accepted` 或 `Needs Revision`。

## 完成区

仅由最终里程碑流程填写；初始为空。
