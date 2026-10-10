# SPEC-103t: F1 语义缺口证明与候选 ADR 输入

**模块**：spec  
**项目里程碑**：F1  
**状态**：已验证  
**依赖**：`SPEC-102t`（已验证）；ADR-1004（Accepted，D11–D17 的 Accepted 内容仅为 OPEN/BLOCKED，不是语义取值）；ADR-1008（Candidate，D1 已由用户确认，整体尚未 Accepted）

## 1. 问题根源与目标

`SPEC-102t` 已把 SimRISC-03 的 64 个真实 identity、11 个 facet、ADR-1004 D11–D17 影响矩阵及历史七键 `D17 OPEN-ID ledger` 固定下来，但它只证明“存在未决面”，没有为每一项提供可供用户逐条裁决的、机器可检查的完整证据包。ADR-1008 D1 已进一步证明 S7 是 non-gap；本任务须将当前 active 门禁收敛为六键，而不改写 `SPEC-102t` 历史。若下游直接消费实现习惯、SoftFloat 默认值或含糊的自然语言，就会把 OPEN 静默变成 active expected 或运行时语义。

本任务只做两件事：

1. 对 D11–D17、D17 六键 active ledger，以及 S2/S7 两项历史追踪逐项证明“规范已唯一规定 / 明示不要求 / 无行为后果 / 确无唯一答案”中的哪一类，并保留可复核证据；
2. 对确无唯一答案者形成**无选择**的最小 Candidate decision 输入、64 identity 影响矩阵和无环消费者门禁。

成功不等于关闭缺口。成功是：证据、影响和候选问题完整且可机检，所有尚未获用户逐 decision 确认的行为仍为 OPEN/BLOCKED。

## 2. 权威来源与证据规则

权威顺序固定为：根 `README.md` 的 SimRISC 0.5.3 → `spec/SimRISC-00-指令系统设计.md` 与 `spec/SimRISC-03-浮点类指令.md` → `.xkw/knowledge/adr-1004-f1-floating-phase.md` 的 Accepted 边界 → 已验证的 `.xkw/knowledge/contract-f1-floating.md` 与 `contracts/opcodes.yaml` 投影。

- `spec/` 原文决定语义；contract/机器数据用于完整性和已验证映射，不得反向覆盖 spec。
- LLVM、QEMU、SoftFloat、宿主浮点/`libm`、参考仓及 `.tao/` 只能说明实现代价或历史，不得证明规范答案。
- 每个证明记录必须包含精确 `spec_cites`、原文要点、缺失或冲突点、分类理由、受影响 identity/facet、可观测后果及最小候选问题；“全文没写”必须给出已搜索章节/术语范围，不能只有一句断言。
- `rootn(-0,2)` 等规范明示“不作具体要求”的情形必须与“规范沉默而需决策”分开；前者不得伪造唯一 expected，也不得偷换成 Candidate 语义选择。

## 3. 范围与非范围

**在范围内**：D11–D16 的六个既有 OPEN facet、D17 兜底证明、六项 active `D17:S1/S3/S4/S5/S6/S8` 行为缺口、ledger 外 `D17:S2` trace-only 与 `D17:S7` spec-determined/non-gap 追踪、64 identity 逐行影响、候选问题及下游门禁。

**不在范围内**：选择任一语义；创建、修改或接受 ADR；改 contract、opcode/legality 数据、测试 schema/vector/oracle、LLVM/QEMU、组件补丁、实现代码、状态摘要或里程碑；把实现可行性当作规范结论；关闭任何 OPEN。

## 4. 输入基线与固定集合

- identity 集必须与已验证 contract 精确相等：**64 = 18 rf-qfc + 46 misc-rf**；`set.ft`/`set.fo` 为 pseudo，计数为 0。
- facet 键固定为 contract §5.1 的 11 键；不得另造同义 facet 绕过现有 OPEN。
- D11–D17 的既有受影响规模是校验基线，不是本任务可改的语义结论：`37/53/18/4/18/36/64`。
- D17 active ledger 精确六键见 §8；S2 与 S7 均不进入 active ledger。S2 是 ledger 外 trace-only，S7 是 ledger 外 spec-determined/non-gap 历史追踪。
- rf0/FCSR **layout、位号、只读域与可观测 mask** 已由 spec 唯一确定；rf0 **reset value** 未定。两者必须始终分栏。

如执行时上述集合与 `SPEC-102t` 已验证产物不一致，应 fail-closed 报依赖漂移，不得在本任务内修上游。

## 5. 交付物、允许路径与所有权

未来 `/dispatch SPEC-103t` 仅允许修改或新建：

1. `contracts/f1_gap_proofs.yaml` —— **本任务唯一机器可读 source of truth**；证据分类、Candidate 输入、64 影响矩阵和消费者图均以此文件为准；
2. `tools/spec/check_f1_gap_proofs.py` —— SPEC 模块拥有的结构、集合、引用、无选择和无环检查器；
3. `tools/spec/test_f1_gap_proof_counterexamples.py` —— SPEC 模块拥有的反例驱动器；
4. 本任务文件的 `## 14. 完成区` —— 只填写真实产出、命令、退出码、日志、反例、还原和 dirty baseline 证据；
5. `.work/log/spec/SPEC-103t-*.log` —— gitignored 的真实运行日志。

除以上路径外一律禁止修改。尤其不得改 `.xkw/knowledge/**`、其它任务书、`contracts/opcodes.yaml`、`contracts/legality_rules.yaml`、`spec/**`、`tests/**`、组件或 ADR。检查器和反例脚本随入库 YAML 一并保留，不能只存在于 `/tmp`。

## 6. `contracts/f1_gap_proofs.yaml` 最小合同

YAML 顶层至少包含并由检查器精确校验：

- `schema_version`、`authority`、`identity_universe`；
- `decision_proofs`：精确 D11–D17；
- `d17_open_ledger`：精确六键；
- `trace_only`：精确且仅含 `D17:S2`；
- `non_gap_records`：精确且仅含历史 `D17:S7`；
- `impact_matrix`：精确 64 个 identity，每个恰好一行；
- `consumer_graph`：任务节点、消费的 decision/OPEN-ID/facet/assertion 与有向边；
- `candidate_inputs`：候选问题、互斥备选及各自可观测后果，但没有 selected/default/recommended/accepted 值。

每个 proof/ledger 记录必须有非空、类型受限的 `classification`、`status`、`spec_cites`、`evidence`、`affected_identities` 或明确横切范围、`affected_facets`、`observable_consequences`、`candidate_question_ids` 与 `blocked_assertions`。引用必须落在允许的规范/Accepted ADR；实现路径不能进入 authority/evidence。

允许的证明分类固定为：`spec-determined`、`explicitly-unspecified`、`no-behavioral-consequence`、`genuine-gap`。其中 `genuine-gap` 必须保持 `OPEN/BLOCKED`；分类本身不携带语义取值。

## 7. D11–D17 精确证明要求

`decision_proofs` 键集合必须**精确等于** `{D11,D12,D13,D14,D15,D16,D17}`，逐项要求如下：

| ID | 必须证明的问题 | 已知受阻 facet/范围 | Candidate 输入最低要求 |
| --- | --- | --- | --- |
| D11 | rf0 一般 ILLI 与 sign-injection `abs/-abs` 特例、规则适用章节及 rd2rf/rf2rd 边界是否冲突 | `rf0_operand`，37 identity | 分开一般规则范围、特例优先级、搬移边界；不得选择优先级 |
| D12 | flags 是 sticky 还是覆盖、无异常保持、软件清除及数据搬移是否更新 flags | `fcsr_flags`，53 identity | 每个更新/保持/清除问题独立可逐条询问 |
| D13 | ft 结果或载入写 RF 后高 32 位 | `tetra_high_half`，18 identity | 保留/清零/其它方案只列后果，不选值 |
| D14 | unordered compare 写 RD 的 qNaN/sNaN 精确位型 | `compare_unordered`，4 identity | quiet/signaling 两类位型与可观测整数比较后果 |
| D15 | NaN payload、符号、quieting、多 NaN 选择与默认 NaN | `nan_propagation`，18 open + 2 partial | 按单源/多源/sNaN/转换拆最小问题 |
| D16 | tininess 时点及 UF/OF/NX 复合规则 | `tininess`，36 identity | 舍入前/后等备选及 flags 可观测后果，不推荐 |
| D17 | 证明兜底不是单一语义值，并完整关联六键 active ledger、S2 trace 与 S7 non-gap | 64 identity 横切 | 每个 active 键各自独立问题；D17 不得用一个总选择关闭六项 |

D11–D16 每项须保持与 contract 的 identity/facet 基数一致；若进一步细分，只能把既有集合分区，不能静默增删。D17 的 64 行表示“存在任一 OPEN/静默面的总追踪”，不表示每个 identity 同时命中七个 S 项。

## 8. D17 六键 active ledger、S2/S7 历史追踪

`d17_open_ledger` 的键集合必须逐字符精确等于：

`{D17:S1,D17:S3,D17:S4,D17:S5,D17:S6,D17:S8}`。

| OPEN-ID | 主题 | 精确范围/约束 |
| --- | --- | --- |
| `D17:S1` | rf0/FCSR reset | `all-64` 横切；layout/mask 不得并入；状态 OPEN/BLOCKED |
| `D17:S3` | classify immediate | 仅 `ftcls`,`focls` 的 `immu6 != 1` legality；不得发明 fault |
| `D17:S4` | multi-fault priority | 从 contract §3.2 的 fault 集合机械求出同时可满足两个以上谓词的 identity/断言；不得把表格顺序当优先级 |
| `D17:S5` | scaleB exponent | 仅 `ftsclb`,`fosclb` 的指数解释；两种读法及后果均列出但不选 |
| `D17:S6` | rf0 SBZ write | 精确六条 `ld.t-rf`,`ld.o-rf`,`ldm.t-rf`,`ldm.o-rf`,`set.w-rf`,`rd2rf`；忽略/保留/清零/异常均不得成为已选行为 |
| `D17:S8` | ldm/stm memory semantics | 精确 `ldm.t-rf`,`ldm.o-rf`,`stm.t-rf`,`stm.o-rf`；地址组合、步长、顺序和重叠均保持未决，不得从 SimRISC-01 外推 |

六行 active ledger 的 `status` 只允许 OPEN/BLOCKED，受影响集合不得为空，且必须有至少一个下游阻塞断言。`D17:S2` 必须单独位于 `trace_only`，精确语义为：`no behavioral consequence; resolved/trace-only; not in D17 OPEN-ID ledger; never PASS`。它须以 6 位 `immu6` 上限和 `immu6=0` 独立 ILLI 规则证明无行为差异；不得进入 ledger、Candidate 问题、active expected 或 PASS 计数。

`D17:S7` 必须单独位于 `non_gap_records`，精确为 `spec-determined`、`NOT-A-GAP`、`in_active_ledger: false`、空 Candidate 集及 `pass_counted: false`。其证据必须独立引用 SimRISC-00 的 RD/RF 不同寄存器组（:41-46）与 SimRISC-03 的固定 RF→RD/RD→RF 块赋值方向（:33-49）；不得以 ADR-1008 Candidate 代替原始规范证明。`rd2rf`/`rf2rd` 可保留 `non_gap_refs: [D17:S7]`，但 S7 不得进入 active IDs、blocked assertions、consumer applicability 或 PASS 汇总。ADR-1008 不在本任务修改范围。

## 9. 64 identity 影响矩阵与断言门禁

`impact_matrix` 必须与 contract 的 64 identity 集合双向相等、无重复、无空行。每行至少记录：

- `identity`；
- 命中的 D11–D17 与 `D17:S*`（可为空但须显式）；
- 受影响 facet 及其状态；
- 可立即消费的 spec-determined facet；
- 被阻塞的下游任务和**具名断言类别**（如 legality-negative、reset-dependent expected、fault-priority、runtime semantics、milestone facet）；
- 解除条件：规范勘误给出唯一答案，或相应 Candidate decision 经用户逐条确认并由主会话写入 Accepted ADR。

矩阵必须保证：D11–D16 投影基数仍为 `37/53/18/4/18/36`，D17 总追踪为 64；active ledger 的投影精确为 `S1/S3/S4/S5/S6/S8 = 64/2/26/2/6/4`，历史 S7 范围为 2 而 active scope 为 0；rf0 layout 可标 `spec-determined/now-runnable`，但同一 identity 的 reset 仍可被 `D17:S1` 阻塞。OPEN 只阻塞命中的 facet/断言，不得把编码等已决 facet一并冻结，也不得用已决 facet 的绿灯覆盖 OPEN。

## 10. 消费者映射、依赖与冲突

`consumer_graph` 必须是 DAG，至少表达以下方向，禁止任何下游反向定义本 YAML：

```text
SPEC-102t(已验证输入) → SPEC-103t(f1_gap_proofs producer)
SPEC-103t → TESTCASES-101t → TESTCASES-102t
SPEC-103t → LLVM-101t → {LLVM-102t, LLVM-103t}
{SPEC-103t, TESTCASES-101t, INFRA-108t} → QEMU-101t
{QEMU-101t, TESTCASES-102t} → QEMU-102t → QEMU-103t
{SPEC-103t, TESTCASES-102t, LLVM-101t..103t, QEMU-101t..103t}
  → INTEG-102t → INTEG-103t → INTEG-104m
```

- TESTCASES 消费 blocked 表达与已决语义，拥有 schema/oracle/vector，不得编辑 gap 真源。
- D11 至少必须映射到 `LLVM-101t` 的 `assembler-legality`、`TESTCASES-102t` 的 `schema/oracle/vector` 与 `runtime semantics`、以及 `INTEG-103t` 的 `runtime semantics`；缺任一映射即 FAIL。LLVM-101t 仍消费 `D17:S3` 的 assembler-legality 门禁；其它运行时 gap 为 `N/A(runtime)`，N/A 不是 PASS。LLVM-102t/103t 不选择运行语义。
- QEMU 按任务适用 facet 消费六键 active ledger 和 D11–D16；不得用 SoftFloat 默认行为关闭缺口。S7 只作历史 non-gap，不得被消费者提升回 OPEN。
- INTEG 汇总矩阵，不回写上游定义；`INTEG-104m` 只核验所有 required facet 的闭合证据。

文件所有权无共享写冲突：本任务独占 §5 三个入库交付路径；下游只读消费。资源上本任务仅作文本/YAML/Python 静态检查，不需要 LLVM/QEMU 构建；不得启动大构建。关键路径为 `SPEC-103t → TESTCASES-101t → TESTCASES-102t → QEMU-* → INTEG-*`；LLVM 支路在依赖满足后可与 testcases 的非共享文件工作并行，但 LLVM/QEMU 真构建仍须串行。

## 11. Candidate decision 与 ADR 门禁

每个 `genuine-gap` 必须形成最小、可单独询问的问题；一个问题只处理一个可观察选择。每个备选项写清行为、受影响 identity/facet、测试可观测差异、实现/兼容代价和与其它问题的依赖，但字段中不得出现选择、默认、推荐或 Accepted 结论。S7 不是 genuine-gap，必须没有 Candidate 输入。

候选可按 rf0/高半部、FCSR/flags/tininess、compare/NaN 及 D17 各静默项分组，但**不得**预先绑定或创建 `ADR-1005`～`ADR-1007`，也不得假定未来 ADR 数量。是否创建 Candidate ADR、编号、以及每条 decision 的保留/修改/否决，均由主会话一次一个问题征得用户确认；未经确认不得写 `Accepted`，本任务本身也不因证据完整而解除任何行为门禁。

## 12. 检查器、反例与还原责任

`tools/spec/check_f1_gap_proofs.py` 必须真正解析 YAML，并独立读取 spec、已验证 contract 与 `contracts/opcodes.yaml` 来核对集合、引用和投影；纯 grep、只验证 YAML 内部自洽或从 YAML 自己推导期望集合均不够。至少检查：顶层 schema、D11–D17 精确集合、六键精确集合、S2 唯一且 ledger 外、S7 唯一 non-gap 且不在 active/blocked/Candidate、64 双向集合、facet/基数、非空证据/影响/断言、禁止语义选择、禁止实现来源、D11 消费者映射、消费者任务与边、DAG 无环、OPEN 不得 active/PASS、允许路径无越权产物。

`tools/spec/test_f1_gap_proof_counterexamples.py` 必须逐类注入并确认目标检查类别真实 FAIL/非零，至少包括：

1. 删除一个 D11–D17 proof；
2. 删除一个六键、加入 `D17:S2` 或 `D17:S7` 到 ledger、或把具名键降为裸 `S*`；
3. 把 OPEN/BLOCKED 改成 PASS/active/spec-determined；
4. 给任一 Candidate 项增加 selected/default/recommended/Accepted 值；
5. 清空 evidence、identity、facet、observable consequence 或 blocked assertion；
6. 令 impact matrix 变成 63 行、重复 identity、加入 pseudo/非 F1 identity，或改变 `37/53/18/4/18/36/64` 投影；
7. 合并 rf0 layout 与 reset，或为 S6 选择写入动作；
8. 删除消费者、错误扩大 LLVM 的运行时结论，或注入图环；
9. 把实现/SoftFloat/SimRISC-01 写成语义 authority；
10. 改错一条 spec citation，确保不是只检查引用格式；并至少分别反造 S7 缺失 non-gap、S7 变 genuine-gap/OPEN/PASS、S7 Candidate/矩阵/consumer 泄漏、以及 D11 到 `LLVM-101t`、`TESTCASES-102t`、`INTEG-103t` 任一映射缺失。

每个反例只能在 `/tmp/opencode/SPEC-103t/` 的独立合成 git 树中执行：基线先绿 → 注入 → `git diff --name-only` 非空 → 目标类别 FAIL 且退出非零 → 还原 → 临时树 clean → 复绿。SPEC 模块拥有两个脚本；reviewer 验收时须独立枚举并亲自注入，不得只采信自测汇总。

## 13. 验收（可执行性逐条标注）

| # | 判据 | 可执行性 |
| --- | --- | --- |
| 1 | 依赖 `SPEC-102t` 为已验证，64/11-facet/D11–D17 基线可从现有 contract 与 opcodes 复核；ADR-1008 D1 仅作 S7 返工追踪，原始 spec 是证明权威 | **现在可跑**：只读运行现有 SPEC-102 检查器或独立解析；不需构建 |
| 2 | `f1_gap_proofs.yaml` 具备 §6 全部顶层与逐项字段，且是唯一真源 | **现在可跑（本任务产出后）**：运行新 checker；无外部能力阻塞 |
| 3 | D11–D17 精确七项均有可定位证据、分类、影响与后果；仅 genuine-gap 有无选择 Candidate 输入，S2/S7 均无 Candidate，投影基数不漂移 | **现在可跑（本任务产出后）**：checker + 对 spec 原文逐项人工复核 |
| 4 | D17 active ledger 精确六键且全 OPEN/BLOCKED；S2 仅 trace-only；S7 仅 spec-determined non-gap；layout/reset 分栏；S6 无已选动作 | **现在可跑（本任务产出后）**：结构化检查与定向反例 |
| 5 | 64 identity 影响矩阵双向全等、每行非空可追踪、OPEN 不进入 active expected/PASS | **现在可跑（本任务产出后）**：独立从 contract/opcodes 重算集合与投影 |
| 6 | consumer graph 覆盖规定任务/断言且无环，LLVM N/A(runtime) 不解锁语义 | **现在可跑（本任务产出后）**：拓扑排序与集合核对 |
| 7 | 新 checker 的 §12 十类反例均有非空注入、目标 FAIL/非零、clean 还原和复绿证据 | **现在可跑（本任务产出后）**：仅 Python/YAML 临时树，不需组件构建 |
| 8 | 真实 diff 仅含 §5 允许路径，启动 dirty baseline 其它路径逐字节不变；`.tao/` 零改动 | **现在可跑**：执行前后 status + 每个既有 dirty 路径 sha256 比对 |
| 9 | 所有 genuine gap 的语义取值与 active expected 已关闭 | **BLOCKED**：本任务禁止选择语义，须后续由用户逐 decision 确认并由主会话写 Accepted ADR；替代证据为完整 proof、Candidate 输入、64 矩阵和 blocked assertions |
| 10 | 下游 TESTCASES/LLVM/QEMU/INTEG 已消费并通过运行时/E2E | **BLOCKED**：下游任务尚未执行；替代证据为无环消费者映射、逐任务断言门禁和明确解除条件，不得记 PASS |

任何“工具不存在所以跳过”、空集合、只打印 PASS 或把 BLOCKED 算作成功计数的结果均不满足验收。

## 14. 完成区

由 engineer 在实际执行、保存日志并完成自审后填写；初始为空。状态转换、ADR 处理和知识沉淀仍由主会话负责。

### 1. 交付物与边界

- `contracts/f1_gap_proofs.yaml`：唯一机器可读真源；含 64（18+46）identity、D11–D17、七项 D17 ledger、ledger 外 `D17:S2`、64 行影响矩阵、25 个未选择 Candidate 输入及 15 节点/28 边消费者 DAG。
- `tools/spec/check_f1_gap_proofs.py`：独立重读 spec、已验证 F1 contract 与 `contracts/opcodes.yaml`；verbose 实测 **85 通过 / 0 失败 / 0 跳过**。
- `tools/spec/test_f1_gap_proof_counterexamples.py`：31 个临时 git 树反例全部验证为「注入后目标语义 FAIL、还原 clean、复绿」。覆盖任务书 §12 十类，以及 S2 泄漏、Candidate ADR 预绑定和越权产物三个加固项。
- 未创建或修改 ADR，未选择任何语义值；D11–D17 与七项 ledger 保持 OPEN/BLOCKED，`D17:S2` 保持 trace-only 且不计 PASS。

### 2. 实际验证

所有命令以 `set -o pipefail`、`tee` 和 `${PIPESTATUS[0]}` 记录真实退出码；完整输出在 `.work/log/spec/SPEC-103t-*.log`。

| 命令 | 退出码 | 结果 | 日志 |
| --- | ---: | --- | --- |
| `python3 tools/spec/check_f1_gap_proofs.py -v` | 0 | 85 通过，0 失败；64=18+46、D11–D17 `37/53/18/4/18/36/64`、精确七键、S2、64 行矩阵及 15 节点/28 边 DAG 均通过 | `SPEC-103t-gap-proofs-verbose.log` |
| `python3 tools/spec/test_f1_gap_proof_counterexamples.py -v --rm-trees` | 0 | **31/31** 注入被目标检查捕获；每项非空 diff/status、非零语义 FAIL、还原 clean、复绿，临时树已清理 | `SPEC-103t-counterexamples.log` |
| `python3 tools/spec/check_f1_contract.py` | 0 | 74 通过，0 失败；上游 64 identity/投影基线可用 | `SPEC-103t-upstream-contract.log` |
| `python3 tools/spec/check_f1_citations.py` | 0 | 119 处合约引用与 32 条语义锚点通过 | `SPEC-103t-upstream-citations.log` |
| `python3 tools/spec/validate_encoding.py contracts/opcodes.yaml` | 0 | 256 条记录 OK | `SPEC-103t-upstream-encoding.log` |
| `python3 tools/spec/check_qfc_coverage.py` | 0 | QFC/YAML 各 256、双向差异 0；F1 外范围 78 条一致 | `SPEC-103t-upstream-qfc.log` |
| `python3 -m compileall -q tools/spec/check_f1_gap_proofs.py tools/spec/test_f1_gap_proof_counterexamples.py` | 0 | Python 编译通过 | `SPEC-103t-compileall.log` |
| `git diff --check` | 0 | 无输出 | `SPEC-103t-git-diff-check.log` |
| 只读 evidence/count review | 0 | 所有 D11–D17/七项 ledger 均有非空引用证据；矩阵独立计数与固定基数一致 | `SPEC-103t-manual-evidence-review.log` |

### 3. 反例和还原证据

反例在 `/tmp/opencode/SPEC-103t/ce-<tag>/` 的独立 git 树执行，真实仓库未注入。十类要求均有至少一个目标 FAIL：删 proof；ledger 缺失/S2/裸键；OPEN→PASS/active/determined；Candidate 选择词；空 evidence/identity/facet/consequence/assertion；63 行/重复/pseudo/投影；layout/reset 与 S6 写入动作；消费者/LLVM runtime/环；实现/SoftFloat/SimRISC-01 authority；错误 spec 行号。完整逐项 FAIL 行、还原 clean 和复绿输出见 `SPEC-103t-counterexamples.log`。

### 4. dirty baseline

- 开工基线：`/tmp/opencode/SPEC-103t/dispatch-precheck/` 的 NUL-safe 45 条 status 与 45 个 SHA256。
- 完成区写入前复核：当前 48 条；相对基线仅新增三个允许交付路径（`contracts/f1_gap_proofs.yaml`、两个 `tools/spec/` 脚本），无基线路径缺失，**45/45 SHA256 一致**。证据：`SPEC-103t-pre-append-baseline.log`。
- 本完成区是任务书允许的 append-only 变更；状态标题仍为 `待开始`，未提交。
- 写入完成区后再次执行 `git diff --check`，退出码 0、无输出；日志：`SPEC-103t-final-git-diff-check.log`。

### 5. 返工修复记录（CE-13 diff 门控）

- 修复范围仅为 `tools/spec/test_f1_gap_proof_counterexamples.py`：所有反例现在机器强制要求 `git diff --name-only` 非空；`git status -uall` 仅保留为未跟踪越权产物诊断，不能替代 diff 门控。
- CE-13 仍创建未跟踪的 `contracts/f1_gap_proofs_bak.yaml` 以命中 `stray-artifact`，并同时给已跟踪 `contracts/f1_gap_proofs.yaml` 的 `schema_version` 添加无语义 YAML 内联注释。因此检查器能解析至 G11，且注入期 `git diff --name-only` 实测为 1 个路径（`contracts/f1_gap_proofs.yaml`）。
- 定向复验：`python3 tools/spec/test_f1_gap_proof_counterexamples.py -v --rm-trees --only 13-stray-artifact`，退出码 0；目标 G11 `stray-artifact` 返回非零、明细点名 `f1_gap_proofs_bak.yaml`，还原后临时树 clean 且检查器恢复绿。日志：`.work/log/spec/SPEC-103t-repair-ce13.log`。
- 全量复验：`python3 tools/spec/test_f1_gap_proof_counterexamples.py -v --rm-trees`，退出码 0；**31/31** 每项均记录非空 tracked diff（最小 1 个路径）、目标语义 FAIL/非零、clean 还原与复绿（各 31 次）。日志：`.work/log/spec/SPEC-103t-repair-counterexamples.log`。
- 生产检查器未修改；`python3 tools/spec/check_f1_gap_proofs.py -v` 退出码 0（85 通过 / 0 失败 / 0 跳过），`python3 -m compileall -q tools/spec/test_f1_gap_proof_counterexamples.py` 退出码 0。日志：`.work/log/spec/SPEC-103t-repair-gap-proofs-verbose.log`、`.work/log/spec/SPEC-103t-repair-compileall.log`。
- 相对 `/tmp/opencode/SPEC-103t/redispatch-ce13-precheck/` 的 48 条 hash 基线，完成区追加前 47 条既有路径 SHA256 未变，仅反例驱动器按本返工修改；日志：`.work/log/spec/SPEC-103t-repair-pre-append-baseline.log`。未更改本任务状态，未作任何 Accepted 声明。
- 完成区追加后最终复核：48 条 status 记录与基线逐条一致；48 条 hash 路径中 46 条 SHA256 不变，仅本任务完成区与反例驱动器为允许改动；`git diff --check` 退出码 0、无输出。日志：`.work/log/spec/SPEC-103t-repair-final-baseline.log`、`.work/log/spec/SPEC-103t-repair-final-git-diff-check.log`。

### 6. 返工：S7 non-gap 与 D11 消费者映射（return evidence）

- 本次返工仅改动 `contracts/f1_gap_proofs.yaml`、两个 `tools/spec/` 脚本和本完成区；未改状态标题、未提交、未创建或修改 ADR，未作任何 Accepted 声明。此前完成区中将 S7 作为 active 缺口及其对应反例/验证陈述由本节真实证据替代。
- active ledger 现精确为 `{D17:S1,D17:S3,D17:S4,D17:S5,D17:S6,D17:S8}`，范围为 `64/2/26/2/6/4`；`D17:S2` 仍为 trace-only；`D17:S7` 是 `spec-determined` / `NOT-A-GAP` 的历史记录，`in_active_ledger: false`、无 Candidate、`pass_counted: false`。其原始权威引用为 SimRISC-00:41-46（RD/RF 为不同寄存器组）和 SimRISC-03:33-49（固定 `rf2rd` RF→RD 与 `rd2rf` RD→RF 块赋值方向）。
- Candidate 数为 24；D11..D17 仍为 `37/53/18/4/18/36/64`，D11 rf0 semantics 保持 OPEN。消费者图仍为 15 节点/28 边；D11 明确映射 LLVM-101t assembler-legality、TESTCASES-102t schema/oracle/vector 与 runtime semantics、INTEG-103t runtime semantics。
- `python3 tools/spec/check_f1_gap_proofs.py -v`：exit 0，87 通过/0 失败；日志 `.work/log/spec/SPEC-103t-return-gap-proofs-verbose.log`。
- `python3 tools/spec/test_f1_gap_proof_counterexamples.py -v --rm-trees`：exit 0，45/45 注入均有非空 tracked `git diff --name-only`、目标语义 FAIL/非零、clean restore 和复绿；含 S7 缺失/错误状态/Candidate/矩阵/consumer 泄漏、三项 D11 映射缺失和六项 active scope；日志 `.work/log/spec/SPEC-103t-return-counterexamples.log`。
- 上游复验 `check_f1_contract.py`（74/0）、`check_f1_citations.py`（PASS）、`validate_encoding.py contracts/opcodes.yaml`（256 OK）、`check_qfc_coverage.py`（双向差异 0）、`compileall` 与 `git diff --check` 均 exit 0；日志 `.work/log/spec/SPEC-103t-return-upstream-*.log`、`SPEC-103t-return-compileall.log`、`SPEC-103t-return-final-git-diff-check.log`。
- 人工 64 行/映射审计 PASS；日志 `.work/log/spec/SPEC-103t-return-manual-audit.log`。相对 `/tmp/opencode/SPEC-103t/redispatch-s7-precheck/` 的 49 个 hash 记录，返工前既有 dirty 路径仅三个允许交付文件发生变化；日志 `.work/log/spec/SPEC-103t-return-baseline-audit.log`。

### 7. 返工二：S7 叙述全字段语义一致性（当前有效结论）

**本节取代第 1–5 节全部数字与结论，也取代第 6 节。** 第 1–5 节写作时把 S7 当作 active 缺口（七项 ledger、85 通过、31/31 反例），该口径已被证伪并作废，仅作历史留档；第 6 节是上一次返工（S7 降为 non-gap）的证据，但其**验证数字已过期**（87 通过、45/45 反例），且未覆盖本轮返工要求的「S7 叙述全字段语义一致性」。本节以下述实测为准；ADR 与状态处置仍由主会话负责。

#### 7.1 本轮改动范围

- 只改三个允许交付文件 + 本完成区：`contracts/f1_gap_proofs.yaml`、`tools/spec/check_f1_gap_proofs.py`、`tools/spec/test_f1_gap_proof_counterexamples.py`。`.tao/` 零改动，未提交，未创建或修改任何 ADR（含 `.xkw/knowledge/adr-1008-rd-rf-non-overlap.md`，SHA256 与基线一致），未作任何 Accepted 声明，状态标题仍为 `待返工`。
- YAML 侧：把全部仍以「七项 / S7 是缺口」叙述的字段改成六键 active 口径。涉及 D17 的 `affected_identities_scope`、`evidence`（`D17-E2` 枚举、`D17-E5` finding、新增 `D17-E7`）、`missing_or_conflicting`、`classification_reason`、`observable_consequences`，`non_gap_records.D17:S7`（新增 `S7-NG-E3` 证据与第二条后果），以及消费者 SPEC-103t / LLVM-101t / LLVM-102t / LLVM-103t 四个节点与 `known_upstream_divergences` DIV-1、`not_done_here`。
- 检查器侧：新增 **G12** 一组 6 条检查（`s7-unsettled-mention`、`active-count-six`、`d17-six-active-tells`、`d17-active-scope`、`s7-raw-authority`、`upstream-legacy-wording`）；删除 `PIN_BLOCK_RULES["D17:S7"]`（它会重新把 S7 推成阻塞项，与 non-gap 判定自相矛盾）与死常量 `PIN_LEGACY_KEYSET_STR`；把 `PIN_APPLIC_SENTENCE` / `PIN_APPLIC_PINNED` / `PIN_APPLIC_ALL_NA` 接上真实检查（G12 `upstream-legacy-wording` 与 G8 `applic-pinned`），消除「声明了常量却没有检查消费它」的死代码。

#### 7.2 判定方法：极性白名单，不是禁用词

G12 逐**分句**（按 `[。；;\n]+` 切分）扫描全文档所有散文值，凡提及 S7 就必须带显式结算标记（历史 / non-gap / spec-determined / 不进入 / 不计入 / 不是 / 不得 / 不产生 / 不生成 / superseded / never / not in / not a gap…），否则 FAIL。

之所以不能用朴素禁用词：当前 YAML 中提到 S7 的分句共 **12** 个，其中 **9** 个含 `active` 一词，且**全部**是「不进入 active ledger」「不是 active 静默项」这类否定句——朴素禁用词会把 12 个全部误杀。实测明细见 `.work/log/spec/SPEC-103t-s7-clause-audit.log`：**无显式结算标记的分句数 = 0**。

`active-count-six` 同理不能只认「七」：全文档有 9 处「七」计数词，其中 **8 处是身份/记录计数**（`facet rf0_operand == open-blocked（37 条）` 中被点名的 7 条 identity），只有 **1 处**落在缺口台账语境且已被结算标记豁免（LLVM-101t 节点那条显式声明「下游任务书仍保留含 S7 的历史七项措辞……不构成本文件的 active 依据」）。因此该检查要求计数词与台账语境词同现（`PIN_LEDGER_CTX_RE`，按词边界匹配，避免 `open-blocked` 里的 `blocked` 被当成 `BLOCKED` 状态）才判 FAIL。调窄前该检查曾对 8 条身份计数误报，已修正。

#### 7.3 S7 原始权威（独立 oracle，非仅靠检查器绿灯）

`non_gap_records.D17:S7` 的 5 条 `spec_cites` 已逐条回读 spec 原文窗口核对，**5/5 quote 逐字命中**：SimRISC-00:41-46 列出 `- 数据寄存器 64 个：\`rd0 - rd63\`` 与 `- 浮点寄存器 64 个：\`rf0 - rf63\``（RD/RF 是两个不同寄存器组），SimRISC-03:33-49 固定 `rf2rd   rdhb, rfhc, immu6` 与 `rd2rf   rfhb, rdhc, immu6` 的操作数方向。结构化字段实测：`status='NOT-A-GAP'`、`classification='spec-determined'`、`in_active_ledger=False`、`pass_counted=False`、`candidate_question_ids=[]`、`affected_identities=['rd2rf','rf2rd']`。日志 `.work/log/spec/SPEC-103t-s7-raw-authority-oracle.log`。

> 修正记录：初稿两处叙述写了「active scope 为 0」，但该记录并无 `active_scope` 字段（实为 `in_active_ledger` / `pass_counted`），属叙述指向不存在的字段，已当场改为引用真实字段并重跑全部验证。

#### 7.4 反例：纯叙述注入（结构化字段一个都不动）

新增 3 条，均只把散文字换回返工前措辞，`d17_open_ids` / `ledger` / `non_gap_records` 等结构化字段完全不动，用来证明 G12 不是靠结构化 active ID 兜底：

| 反例 | 注入位置 | 恢复的旧措辞 | 期望命中的具体检查 | FAIL 明细点名 |
| --- | --- | --- | --- | --- |
| CE-23 | `decision_proofs.D17.evidence[4].finding` | `无重叠顺序（S7）` | `G12 s7-unsettled-mention` | `无重叠顺序（S7）` |
| CE-24 | `decision_proofs.D17.evidence[1].finding` | `7 项规范静默（S1, S3, S4, S5, S6, S7, S8）` | `G12 s7-unsettled-mention`（同时触发 `active-count-six`） | `S6, S7, S8` |
| CE-25 | `consumer_graph.nodes[2].na_runtime_note` | `七项在证据完整后仍为 OPEN/BLOCKED` | `G12 active-count-six` | `七项在证据完整后仍为 OPEN/BLOCKED` |

三条的注入字面量由 YAML 原文机械抽出并已验证字节等价（`_CUR` 在当前 YAML 唯一命中 1 次、`_PRE` 在 pre-repair 快照唯一命中 1 次），不是手抄；`_CUR` 是当前文本、`_PRE` 是要恢复的旧文本，方向与直觉相反，已在常量定义处注明。CE-24/25 各触发 1 条 FAIL，CE-24 触发 2 条，均命中目标检查名。

#### 7.5 实测结果（本节全部数字的来源）

所有命令以 `set -o pipefail` + `${PIPESTATUS[0]}` 记录真实退出码，日志在 `.work/log/spec/`。

| 命令 | 退出码 | 结果 | 日志 |
| --- | ---: | --- | --- |
| `python3 tools/spec/check_f1_gap_proofs.py -v` | 0 | **94 通过 / 0 失败 / 0 跳过**；分组 G1..G12 = 10/8/12/5/16/4/8/9/6/5/5/6 | `SPEC-103t-f1-check-verbose.log` |
| `python3 tools/spec/test_f1_gap_proof_counterexamples.py -v --rm-trees` | 0 | **48/48** 全部抓住（注入后目标语义 FAIL + 还原 clean + 复绿），用时 293.3s | `SPEC-103t-counterexamples.log` |
| `python3 tools/spec/check_f1_contract.py` | 0 | 74 通过 / 0 失败 | `SPEC-103t-contract-invariants.log` |
| `python3 tools/spec/check_f1_citations.py` | 0 | PASS（119 处 spec 引用 / 32 条语义锚点） | `SPEC-103t-citations.log` |
| `python3 tools/spec/validate_encoding.py contracts/opcodes.yaml` | 0 | 256 条记录 OK | `SPEC-103t-encoding.log` |
| `python3 tools/spec/check_qfc_coverage.py` | 0 | 双向差异 0 | `SPEC-103t-qfc-coverage.log` |
| `python3 -m compileall -q`（两个脚本） | 0 | 编译通过 | `SPEC-103t-compileall.log` |
| `git diff --check` | 0 | 无输出 | `SPEC-103t-git-diff-check.log` |
| 未跟踪产物体检（补 `git diff --check` 覆盖不到的部分） | 0 | 三个入库产物 trailing-ws/tab/CRLF 均 0、均有末尾换行、`--check` whitespace error 0 | `SPEC-103t-untracked-diff-check.log` |
| S7 分句独立审计 | 0 | 12 个提及分句，未标记者 0 | `SPEC-103t-s7-clause-audit.log` |
| S7 spec_cites 回读核对 | 0 | 5/5 quote 逐字命中原文窗口 | `SPEC-103t-s7-raw-authority-oracle.log` |
| dirty baseline 比对 | 0 | 49 条基线：46 条 SHA256 未变、3 条变化（全在允许集）、0 消失、`.tao/` 0 改动 | `SPEC-103t-dirty-baseline.log` |

反例 48 条的分类分布（由驱动器自身 `COUNTEREXAMPLES` 解析）：§12-1..§12-10 逐类 31 条，另加 `return-S7` 5 条（S7 记录缺失/状态错误/Candidate 泄漏/矩阵泄漏/consumer 泄漏）、`return-D11` 3 条（三项消费者映射缺失）、`return-scope` 6 条（六键 active 影响面逐项篡改）、`return-S7-prose` 3 条（本轮新增的纯叙述注入），合计 48。

#### 7.6 被作废的一轮运行（如实记录）

本轮曾有一次全量反例运行报 **15/48**、退出码 1。该结果**不作为证据**，原因是我在后台跑反例的同时在真实仓库编辑 YAML，两次编辑之间 YAML 处于 `ScannerError: mapping values are not allowed here`（第 666 行）的破损窗口：日志中「基线就不绿」出现 **33** 次、`ScannerError` 出现 **33** 次，与 33 条失败一一对应，即全部失败反例都是复制到破损 YAML 的临时树。修复 YAML 后在**不触碰仓库**的前提下重跑，得到 48/48、退出码 0，上表采信的是这一轮。

#### 7.7 dirty baseline

- 基线：`/tmp/opencode/SPEC-103t/redispatch-s7-consistency-precheck/`（49 条 status + 49 个 SHA256，格式 `file <sha256> <path>`）。
- 本节写入**前**复核：当前 `git status --porcelain=v1 --untracked-files=all` 仍为 49 条；逐条 SHA256 比对为 **46 未变 / 3 变化 / 0 消失**，变化的三条恰为 `contracts/f1_gap_proofs.yaml`、`tools/spec/check_f1_gap_proofs.py`、`tools/spec/test_f1_gap_proof_counterexamples.py`，均在任务书 §5 允许集内。ADR-1008 等其余 46 条（含全部 `.tao/` 与 `.xkw/knowledge/` 既有改动）SHA256 与基线一致，未被还原、覆盖或格式化。日志 `SPEC-103t-dirty-baseline.log`。
- 本节是任务书允许的 append-only 变更，写入后该任务书自身将成为第 4 条变化路径（允许集内）；状态标题仍为 `待返工`，未提交。
