# SPEC-101k: F1 浮点阶段启动与任务分解

**模块**：spec  
**项目里程碑**：F1（SimRISC-03 浮点闭环）  
**状态**：已验证  
**日期**：2026-09-26  
**决策依据**：`.xkw/knowledge/adr-1004-f1-floating-phase.md`（Accepted，D1–D18）  
**对应里程碑**：`.xkw/tasks/integ/INTEG-104m-F1浮点闭环里程碑.md`

## 1. 问题根源

M1 只闭合标量 MC→QEMU 链路；`contracts/opcodes.yaml` 中 RF/浮点记录仍保留 `excluded_m1: true`、QEMU 解码为 ILLI，M1 合约也明确排除 SimRISC-03 指令语义。F1 必须新增规范投影、独立 oracle、LLVM MC、QEMU 语义及集成证据，同时不能改写已复现的 M1 历史基线。

## 2. 目的与成功定义

从 `README.md` 锁定的 SimRISC 0.5.3 与 `spec/SimRISC-03-浮点类指令.md` 出发，闭合：

`spec/contracts → testcases 独立 oracle → LLVM MC/disassembler → QEMU → integ`

成功要求：64 个真实 identity 的 required facet（编码、合法性、汇编/反汇编、规范可唯一推出或由 Accepted ADR 固化的语义与边界）全部有证据；`set.ft`/`set.fo` 只作为 assembler pseudo；所有尚未关闭的 OPEN 均显式 BLOCKED，不能计 PASS；M1 全量回归不退化。`SPEC-103t` 已把 active ledger 收敛为 S1/S3/S4/S5/S6/S8，S2 为 trace-only，S7 为历史 non-gap；新增 `SPEC-104t` 负责把已逐条用户确认的 ADR-1009～1015 Candidate decisions 投影为机器规则并同步下游门禁，ADR 状态仍须等待该任务双角色验收后由主会话处理。

## 3. 对照关系

- **借鉴**：M1 的 contract/schema/vector/MC/QEMU harness 形状、组件锁和反例门禁。
- **差异**：F1 合约写入 `.xkw`；测试 oracle 归 `testcases`，不建立 GOLDEN；组件工作树与构建树使用 `.work/f1/**`；上游补丁从 `0009+` 追加。
- **拒绝的 legacy**：不从 `.tao` 的 M1 排除结论、LLVM、QEMU、SoftFloat、宿主 `libm` 或参考仓反推浮点语义；不复制 DADAO-0628 代码；不删除 `excluded_m1: true` 来伪装历史从未排除。

## 4. 范围

**在范围内**：RF 存取、RF↔RD、`set.w`、转换、算术/FMA、符号、比较、条件赋值、分类、rf0/FCSR，以及 pseudo `set.ft`/`set.fo`。  
**不在范围内**：LLVM CodeGen、clang、libc、Linux、gem5、Sail、特权/原子扩展；任何无法由 spec 唯一推出的语义猜测。

## 5. 64 identity 权威映射

**18 个 RF 相关 QFC/编码**：

`ld.t-rf, st.t-rf, ld.o-rf, st.o-rf, ldm.t-rf, stm.t-rf, ldm.o-rf, stm.o-rf, set.w-rf, rd2rf, rf2rd, ftmadd, fomadd, cs.eq-rf, cs.ne-rf, cs.n-rf, cs.z-rf, cs.p-rf`。

**46 个 MISC-RF**：

`ftcls, ft2fo, ft2ft, ftroot, ftlog, focls, fo2ft, fo2fo, foroot, folog, ft2it, ft2io, ft2ut, ft2uo, it2ft, io2ft, ut2ft, uo2ft, fo2it, fo2io, fo2ut, fo2uo, it2fo, io2fo, ut2fo, uo2fo, ftadd, ftsub, ftmul, ftdiv, ftrem, ftsclb, ftsgnn, ftsgnj, foadd, fosub, fomul, fodiv, forem, fosclb, fosgnn, fosgnj, ftqcmp, ftscmp, foqcmp, foscmp`。

`set.ft`/`set.fo` 不在 64 内。机器数据必须保留 `excluded_m1: true` 并增加明确 F1 scope；具体字段名由 `SPEC-102t` 定义并由检查器强制。

## 6. 硬约束与权威来源

1. 权威顺序：根规则 → `README.md`/`spec/` → Accepted ADR-1004 → F1 contract/机器数据；实现不是 oracle。
2. ADR-1004 D1–D18 全部生效；其 D11–D17 的历史 Accepted 内容只定义“先保持 OPEN/BLOCKED”的流程边界。`SPEC-103t` 已完成真实缺口证明；当前行为选择承载于 ADR-1009～1015，现行 decisions 均已逐条用户确认，但在 `SPEC-104t` reviewer+architect 均 Accepted、主会话正式置 Accepted 前仍不得作为 active 实现权威。
3. ADR-1008 已 Accepted：S7 是 RD/RF 跨组 non-gap，不进入 active、Candidate 或 PASS。当前 active D17 历史键精确为 S1/S3/S4/S5/S6/S8；S2 仅为 trace-only。不存在 ADR-1005～1007 的执行依赖。
4. IEEE 收敛必须覆盖 f32/f64、四舍入模式、flags、±0、subnormal、Inf、qNaN/sNaN、转换、单次舍入 FMA、IEEE remainder、scaleB、root/log；spec 无唯一答案时不得伪造 expected。
5. M1 `.work/source`、`.work/build`、`components/*/patches/0001`–`0008` 不改；F1 使用 `.work/f1/source/{llvm-project,qemu}`、`.work/f1/build/{llvm,qemu}`，仅追加 `0009+`。
6. QEMU 规范语义只可用 in-tree SoftFloat 与按 spec 定义的可审计 helper；宿主浮点/`libm` 不是语义或验收 oracle。

## 7. 阻塞与勘察证据

- `contracts/opcodes.yaml` 已列出上述 64 identity，但其 F1 legality/语义 facet 尚未归一化；现有 `decode: ILLI` 只表示 M1 状态。
- `.tao/knowledge/contract-isa.md` 明确把 RF 指令语义排除在 M1，仅 rf0 布局可复用为只读事实。
- ADR-1004 D11–D17 与 `SPEC-102t` 的历史台账已由 `SPEC-103t` 逐项复核：active 缺口为 S1/S3/S4/S5/S6/S8，S2 无行为后果，S7 由 ADR-1008 Closed by spec。ADR-1009～1015 的现行 decisions 已逐条用户确认；在 `SPEC-104t` 完成机器投影与独立验收、并由主会话把七份 ADR 置 Accepted 前，受影响实现仍 BLOCKED。
- 当前宿主 LLVM/QEMU 大构建有内存冲突；两组件构建必须串行。

### D17 OPEN-ID 台账与 scope/facet 状态矩阵

本轮统一 active 台账名为 **`D17 OPEN-ID ledger`**，其精确键集合为 `{D17:S1,D17:S3,D17:S4,D17:S5,D17:S6,D17:S8}`，禁止只写 `S1` 等裸号。`D17:S2` 仅作台账外来源追踪：`no behavioral consequence; resolved/trace-only; not in D17 OPEN-ID ledger; never PASS`；历史 `D17:S7` 是 spec-determined/non-gap，既不进入 active ledger，也不计 PASS。状态词固定为：`O` = 等待 Accepted ADR 激活或实现证据的 BLOCKED；`D` = 已有逐条用户确认并由 SPEC-104t 投影、但 ADR 尚未 Accepted；`A` = 规范事实或 Accepted ADR 已激活，可供相应下游实现；`R` = trace-only；`N/A(runtime)` = 该任务不作运行时语义主张。rf0 字段布局与 reset 仍须分栏。

| 任务/边界 | `D17:S1` reset | 台账外 S2 | `D17:S3` cls imm | `D17:S4` fault priority | `D17:S5` scaleB exponent | `D17:S6` SBZ write | 历史 S7 | `D17:S8` ldm/stm memory |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SPEC-102t（历史） | O | R | O | O | O | O | non-gap 覆盖解释 | O |
| SPEC-103t（gap proof） | O | R | O | O | O | O | non-gap | O |
| SPEC-104t（Candidate 投影） | D | R | D | D | D | D | non-gap | D |
| TESTCASES-101t/102t | A（ADR Accepted 后） | R | A（ADR Accepted 后） | A（ADR Accepted 后） | A（ADR Accepted 后） | A（ADR Accepted 后） | non-gap | A（ADR Accepted 后） |
| LLVM-101t | N/A(runtime) | R | A（仅 assembler legality，ADR Accepted 后） | N/A(runtime) | N/A(runtime) | N/A(runtime) | non-gap | N/A(runtime) |
| LLVM-102t/103t | N/A(runtime) | R | N/A(runtime) | N/A(runtime) | N/A(runtime) | N/A(runtime) | non-gap | N/A(runtime) |
| QEMU-101t | A（ADR Accepted 后） | R | N/A(runtime) | A（ADR Accepted 后） | N/A(runtime) | A（ADR Accepted 后） | non-gap | A（ADR Accepted 后） |
| QEMU-102t | A（ADR Accepted 后） | R | N/A(runtime) | A（ADR Accepted 后） | A（ADR Accepted 后） | N/A(runtime) | non-gap | N/A(runtime) |
| QEMU-103t | A（ADR Accepted 后） | R | A（ADR Accepted 后） | N/A(runtime) | N/A(runtime) | A（ADR Accepted 后） | non-gap | N/A(runtime) |
| INTEG-102t/103t/104m | A（ADR Accepted 后） | R | A（ADR Accepted 后） | A（ADR Accepted 后） | A（ADR Accepted 后） | A（ADR Accepted 后） | non-gap | A（ADR Accepted 后） |

`D` 不等于 Accepted 或 PASS；只有七份 ADR 在 SPEC-104t 双角色验收后由主会话置 Accepted，表中的条件式 `A` 才成为实现输入。任何 `A` 也只覆盖对应 facet，不得覆盖实现/build/E2E 证据。所有下游任务以 `SPEC-104t=已验证`、相应 ADR=Accepted 和自身真实能力依赖为共同前置。

## 8. 任务分解

| 任务 | 交付物 | 真实能力依赖 | 验收摘要 |
| --- | --- | --- | --- |
| `SPEC-102t` | F1 合约、64 映射与机器 scope | ADR-1004、spec | 64=18+46；合法性/来源/OPEN 可机检 |
| `SPEC-103t` | 缺口证明与 Candidate decision 输入 | `SPEC-102t` | D11–D17 + S1–S8 逐项证据；不创建/接受 ADR |
| `SPEC-104t` | 27 条已确认 decision 的机器投影、checker/反例与下游任务合同同步 | `SPEC-102t`,`SPEC-103t`、ADR-1008、已确认的 ADR-1009～1015 Candidate | 历史/当前分层；HTML 注释 authority；六键与 S6 6→10；Candidate 阶段不提前 active |
| `TESTCASES-101t` | M1 兼容 schema、oracle I/O、RF/FCSR 观测契约 | `SPEC-104t`、相应 Accepted ADR | schema 反例门禁、无 GOLDEN、消费已激活规则 |
| `TESTCASES-102t` | 独立 oracle、生成器、全量向量 | `TESTCASES-101t`,`SPEC-104t`、相应 Accepted ADR | IEEE facet 覆盖；逐条独立重算；能力缺口仍 blocked |
| `INFRA-108t` | F1 隔离树、0009+ 编排与构建入口 | M1 8-patch 头 | M1 哈希不变；离线可重建 |
| `LLVM-101t` | RF 寄存器与 64 条真实指令 MC | `SPEC-104t`,`INFRA-108t`、适用 Accepted ADR | 编码/解析/打印；0009+；只消费 assembler legality |
| `LLVM-102t` | 64 identity lit 与独立字节 oracle | `LLVM-101t` | 64/64；错字节真实 FAIL |
| `LLVM-103t` | `set.ft/set.fo` pseudo | `LLVM-101t` | D18 展开；反汇编不折叠 |
| `QEMU-101t` | RF 状态、存取/搬移/`set.w` | `SPEC-104t`,`TESTCASES-101t`,`INFRA-108t`、适用 Accepted ADR | 11 identity；D11/S1/S4/S6/S8 精确规则 |
| `QEMU-102t` | 转换、算术/FMA、符号、root/log | `QEMU-101t`,`TESTCASES-102t`,`SPEC-104t`、适用 Accepted ADR | SoftFloat/helper；D11～D16/S1/S4/S5 精确规则 |
| `QEMU-103t` | 比较、条件赋值、分类、FCSR 回归 | `QEMU-102t`,`TESTCASES-102t`,`SPEC-104t`、适用 Accepted ADR | 比较位型、flags、S1/S3/S6 全测（S4/S5/S8 对本任务为 `N/A(runtime)`） |
| `INTEG-102t` | F1 跨模块接口对齐 | 上述 contract/schema/MC/QEMU | 64 facet 矩阵、零平行接口 |
| `INTEG-103t` | MC→QEMU E2E + M1 回归 | LLVM/QEMU/testcases 全部实现 | 64 required facet + M1 747 基线 |
| `INTEG-104m` | F1 里程碑核验 | 全部任务已验证、OPEN 清零或范围经新 ADR 调整 | 只核验，不补实现 |

## 9. 依赖图、关键路径与冲突

```text
SPEC-101k → SPEC-102t → SPEC-103t → SPEC-104t ──┐
                                  └→ TESTCASES-101t → TESTCASES-102t ─┐
M1 8-patch head → INFRA-108t ─→ LLVM-101t → {LLVM-102t,LLVM-103t} ─┤
                               └→ QEMU-101t → QEMU-102t → QEMU-103t ─┤
                                                                     └→ INTEG-102t → INTEG-103t → INTEG-104m
```

- **关键路径**：SPEC-102t → SPEC-103t → SPEC-104t/ADR-1009～1015 Accepted 激活 → TESTCASES-101t → TESTCASES-102t → QEMU-101t → QEMU-102t → QEMU-103t → INTEG-102t → INTEG-103t → INTEG-104m。
- **文件所有权**：SPEC 拥有 `.xkw` F1 contract 与 `contracts/` scope/legality；TESTCASES 拥有 schema、oracle、向量与生成器；LLVM/QEMU 只拥有各自 `0009+` patch、组件测试/工具；INTEG 拥有矩阵/E2E。
- **共享文件冲突**：`contracts/opcodes.yaml` 只由 SPEC-102t 改；schema 只由 TESTCASES-101t 改；LLVM 和 QEMU series/manifest 各自单写者；集成任务不得回写上游定义。
- **宿主资源冲突**：LLVM 与 QEMU build 均重内存，必须串行；文档、向量生成和静态检查可并行，但不得并改共享文件。

## 10. 分解理由与串并行建议

先冻结规范与接口，防止 LLVM/QEMU 各自定义语义；将 oracle 和实现分离以保持独立性；把 pseudo 从真实 identity 分开以落实 D18；把基础 RF 状态与复杂 IEEE 语义分开，便于反例定位。`LLVM-102t` 与 `LLVM-103t` 可逻辑并行；QEMU 三任务按状态→算术→比较/FCSR 串行；任何真实 build 均按宿主限制串行。

## 11. 验收

| # | 判据 | 可执行性 |
| --- | --- | --- |
| 1 | 本书具备 workflow §8 的根源、目的、对照、范围、约束、证据、任务表、图、冲突、验收、k↔m | 现在可跑：文本逐项核对 |
| 2 | 64 映射精确为 18+46，pseudo 不计数 | 现在可跑：对照 spec 与 `contracts/opcodes.yaml` |
| 3 | 当前 F1 路线新增 `SPEC-104t`：本 `k`、`INFRA-108t`、`SPEC-102t`、`SPEC-103t` 为已验证，`SPEC-104t` 与后续任务为待开始；历史 2026-09-26 的“15 本”记录不回写 | 现在可跑：路径/头部/本轮调整记录核对；不作普通任务状态转换 |
| 4 | ADR-1004 D1–D18 均被下游约束消费 | 现在可跑：逐 decision 追踪 |
| 5 | 64 identity 的实现和 IEEE 全边界绿 | **BLOCKED**：下游尚未执行；替代证据为 SPEC-104t 机器规则、任务分解和能力 BLOCKED 清单，不能替代动态结果 |
| 6 | ADR-1009～1015 语义激活 | **BLOCKED**：decisions 已逐条确认，但须 `SPEC-104t` reviewer+architect Accepted 后由主会话置 ADR Accepted，并复跑 `--require-active`；Candidate 投影不得当 PASS |

## 12. k↔m 收敛条件

本 `k` 的 2026-09-26 原始收敛条件和完成记录保持历史有效；本轮路线调整不重开其状态。新增收敛链为：`SPEC-104t` 完成 27 条机器投影与 11 本下游任务书同步，双角色 Accepted 后由主会话激活 ADR-1009～1015。对应 `INTEG-104m` 仅在 64 identity required facet 全闭合、六键受影响行为已有 Accepted ADR 且实现/独立验证完成、S2/S7 不被误计 PASS、M1 回归不退化、所有跨模块影响已处置时，才可由主会话置 `里程碑`。

## 13. 完成区

### `/plan` 收尾（2026-09-26）

- ADR-1004 D1–D18 已由用户逐条确认；D11–D17 均按 Accepted ADR 的明确记录保持 OPEN/BLOCKED，不写入未经确认的语义取值。
- architect 已落盘本书及 14 本下游任务书，仅写入 `.xkw/tasks/**`；reviewer 已按 workflow §9 对实际任务书审计并给出 **Accepted**。
- 任务书审计确认：64 identity = 18 RF/QFC + 46 MISC-RF，无重复；独立 oracle 全归 `TESTCASES-*`，无 GOLDEN 模块；`set.ft/set.fo` 不计入 64，且反汇编不折叠。
- M1 保护基线已记录：LLVM `a5c3a44403fd8efd5ea4e0b0f9fc2961ed9ca784` / tree `0e058573eb70da9e57db6995d6caef6bbe8985da`；QEMU `5c3535f66892868a5829a1b0a242866da6d98e08` / tree `4a14d56ce4ecfc6f5edd2f2d181ec6628844233b`。F1 仅可在 `.work/f1/**` 追加 `0009+`。
- 满足 workflow §8 的规划合同，主会话将本 `k` 置为 **已验证**；所有普通 F1 任务仍为 `待开始`，未自动下发。

### `/plan` 路线调整（2026-09-28，SPEC-104t）

- 本条只记录当前 F1 路线调整；上方 2026-09-26 完成记录逐字保留，不追溯改写其“15 本任务书”等历史数字，本 `k` 状态继续为 **已验证**。
- reviewer 已审查并接受新增 `SPEC-104t` 的规划：在 SPEC-102/103 历史证据之上投影 ADR-1009～1015 的 27 条现行、已逐条用户确认但仍为 Candidate 的 decisions；不新增选择、不提前写 Accepted。
- 当前 active D17 ledger 为六键 `D17:S1/S3/S4/S5/S6/S8`；S2 为 trace-only，S7 为 ADR-1008 证明的历史 non-gap。SimRISC-03:7-8 是 HTML 注释、非现行语义 authority。
- 路线新增 `SPEC-104t`，位于 `SPEC-103t` 与全部语义消费者之间；其任务合同要求同步 10 本下游普通任务书和 `INTEG-104m`，并证明 D17:S6 从 historical-six 经 `6-1+5` 得到 current-ten。
- ADR-1009～1015 的 Candidate→Accepted、`.xkw/knowledge/{MEMORY,milestones,changelog}.md` 更新仍只由主会话在 SPEC-104t reviewer+architect 均 Accepted 后处理；本轮规划未修改任何知识文件、ADR、contract、tool、实现或历史任务证据。

### `/dispatch SPEC-104t` 执行记录（2026-09-28）

- `contracts/f1_gap_proofs.yaml` 已在 SPEC-103 历史层之上**追加**具名 `resolution` 覆盖层（顶层第 13 个键，位于末尾），投影 ADR-1009～1015 的 27 条现行 decision，ADR-1009 D1 保留为唯一 `superseded`（ADR 原文 28 条 `### Dn：` 标题 − D1 = 27）；24 个历史 Candidate 与 27 条现行/supplemental 双向闭合，历史 12 个顶层键与 SPEC-103 原文未被回写。
- §7 的 D17 状态矩阵与 §8 任务表中 `QEMU-103t` 一行已按 `resolution_matrix` 重算值修正：其逐键 runtime 适用为 S1/S3/S6（S4/S5/S8 为 `N/A(runtime)`）。原因：`D17:S4` 的机械 scope 是「剔除非 fault/范围声明谓词后剩余 fault 谓词 >= 2」的 **26** 条（不是 `contracts/opcodes.yaml` 里 `f1.d17_open_ids` 的粗粒度 64），`D17:S6` 的现行 scope 是 ADR-1009 D2 + ADR-1015 D6 叠加后的**十条**（`6 - 1 + 5 = 10`），其中五条 `cs.*-rf` 归 `QEMU-103t`、五条 RF 存取/搬移/`set.w` 归 `QEMU-101t`。
- 10 本下游普通任务书与 `INTEG-104m` 已统一为六键 active ledger、S2=ledger 外 trace-only、S7=ADR-1008 D1 证明的 spec-determined non-gap（都不计 OPEN/BLOCKED/PASS），依赖行显式引用 `SPEC-104t`，并写入本任务相关的精确适用规则而非「参见 ADR」；各书 `**BLOCKED**` 计数保持在同步前基线下界，schema/oracle/vector、LLVM/QEMU 实现与 E2E 仍按真实能力 BLOCKED。
- `python3 tools/spec/check_f1_gap_proofs.py` 默认模式 137 项全通过并输出 pending-activation 标记；`--require-active` 在七份 ADR 仍为 Candidate 时退出码 3（预期替代证据，不得记 PASS）。
- 本轮**未**修改 `.xkw/knowledge/**`、SPEC-102/103 任务书、`spec/**`、`.tao/**`、`contracts/opcodes.yaml`/`legality_rules.yaml`、`tests/**`、`components/**` 与任何实现文件；ADR Candidate→Accepted 与 MEMORY/milestones/changelog 沉淀仍只由主会话在 `/complete` 双角色 Accepted 后处理。上方 2026-09-26 完成记录与 2026-09-28 `/plan` 记录逐字未改。
