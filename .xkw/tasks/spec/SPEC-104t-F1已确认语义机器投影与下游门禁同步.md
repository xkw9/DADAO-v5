# SPEC-104t: F1 已确认语义机器投影与下游门禁同步

**模块**：spec  
**项目里程碑**：F1  
**状态**：已验证  
**依赖**：`SPEC-102t`、`SPEC-103t`（均已验证）；ADR-1008（Accepted）；ADR-1009～1015（现行 decisions 已由用户逐条确认；验收期间为 Candidate，现均为 Accepted）  
**对应里程碑**：`.xkw/tasks/integ/INTEG-104m-F1浮点闭环里程碑.md`

## 1. 问题根源

`SPEC-102t` 固定了 F1 的 64 个真实 identity、11 个 facet 与历史七键台账；`SPEC-103t` 又以原始 spec 证明当前 active `D17 OPEN-ID ledger` 只有六键 `D17:S1/S3/S4/S5/S6/S8`，S2 仅为 trace-only，S7 是历史 non-gap。两项任务的历史证据均已验证，不能回溯改写。

随后 ADR-1009～1015 已承载 D11～D17 的用户选择，所有现行 decisions 均已逐条确认，但七份 ADR 仍是 Candidate。现有 `contracts/f1_gap_proofs.yaml`、检查器和下游 F1 任务书仍主要表达“缺口尚未选择”，其中下游任务书还存在七键/S7 active、未来 ADR-1005～1007、以及“decisions 尚未确认”等陈旧口径。若不先建立机器可检查的 resolution 层并同步任务合同，下游可能继续阻塞已确认语义，或反向把 Candidate 当作已经 Accepted/实现 PASS。

另有一项必须显式纠正的 authority 边界：`spec/SimRISC-03-浮点类指令.md:7-8` 整段位于 `<!-- ... -->` HTML 注释中，是**非规范文本**。它可以作为历史发现过程的记录，但不能证明现行 rf0/SBZ 语义；ADR-1009 D2 与 ADR-1015 D6 是用户对真实缺口的选择，不是由该注释自动推出。

## 2. 目标与成功定义

本任务只完成“已确认语义的正式机器投影与任务门禁同步”，不实现浮点功能：

1. 在既有 gap proof 历史层之上增加结构化 resolution 层，完整投影 ADR-1009～1015 的 **27 条现行 decision**，并保留 ADR-1009 D1 为 superseded history；
2. 用独立 checker 验证 decision、Candidate 输入、64 identity、facet、规则优先级和消费者的双向闭合，而不是只做字符串替换；
3. 用可复原反例证明每一类关键语义关系均有可达 FAIL 路径；
4. 同步 10 本尚未执行的下游普通任务书与 `INTEG-104m`，统一为六键 active ledger、S2 trace-only、S7 non-gap，并把 `SPEC-104t`/Accepted ADR 作为语义激活门禁；
5. 保持 SPEC-102/103、`.tao`、spec、既有合约与实现历史不变。

成功只表示：Candidate 内容与用户确认被准确投影，具备独立审查证据，并为主会话后续把 ADR 置 Accepted 提供门禁。成功**不等于** ADR 已 Accepted，不等于 schema/oracle/LLVM/QEMU 已实现，也不等于任何运行时或里程碑 PASS。

## 3. 权威来源与证据层级

本任务的权威顺序固定为：

1. 根 `README.md` 的 SimRISC 0.5.3 版本声明；
2. `spec/SimRISC-00-指令系统设计.md`、`spec/SimRISC-03-浮点类指令.md` 的规范性正文；
3. Accepted ADR-1004 与 ADR-1008 的边界；
4. 已验证 `SPEC-102t`、`SPEC-103t` 及其机器产物，作为缺口、identity、facet、历史 Candidate 和消费者证据；
5. ADR-1009～1015 中已经用户逐条确认的 Candidate decisions，作为本任务待审查的 resolution 输入；只有主会话在本任务 reviewer+architect 均 Accepted 后将其置 Accepted，才成为下游可执行语义权威。

LLVM、QEMU、SoftFloat、宿主浮点/`libm`、RISC-V、参考仓和 `.tao` 实现经验均不得作为 SimRISC 语义 oracle。ADR 中提到 RISC-V/IEEE 的段落只解释选择理由；机器投影必须标明这是用户决策或规范正文，不得把兼容性理由升级为 spec 事实。

HTML 注释处理规则：checker 必须解析 Markdown HTML comment 区间；当前 resolution 的 normative citation/authority 若指向 SimRISC-03:7-8 必须 FAIL。SPEC-102/103 的历史引用可保留，但须被 resolution/provenance 明确标为 `historical-non-normative`，且不能参与现行规则证明。

## 4. 范围与非范围

### 4.1 在范围内

- ADR-1009～1015 的 27 条现行 decision 及 ADR-1009 D1 superseded 关系；
- 既有 `f1_gap_proofs.yaml` 的历史 gap/Candidate 层与新增 resolution 层；
- D11～D17、六键 active ledger、S2/S7、64 identity resolution matrix、消费者适用关系；
- 既有 SPEC checker/反例驱动器的加严；
- `SPEC-101k` 当前路线、10 本下游普通任务书与 `INTEG-104m` 的任务合同同步；
- Candidate→Accepted 生命周期与 `--require-active` 门禁。

### 4.2 不在范围内

- 新增、删减、修改任何用户语义选择；
- 将 ADR-1009～1015 改为 Accepted；
- 修改 spec、`.tao`、F1 contract、opcode/legality、schema、vector、oracle、LLVM/QEMU 实现或补丁；
- 运行 LLVM/QEMU 构建或把实现输出作为 expected；
- 改写 SPEC-102/103 任务书、完成区、历史数字、日志或审查结论；
- 把 ADR 接受、checker 绿灯或任务书同步记为运行时 PASS。

## 5. 27 条现行 decision 的自包含映射

下表是本任务必须逐条结构化投影的完整集合。若执行中发现还需要任何新选择，必须 fail-closed 返回规划，不得由 engineer 补充。

| ADR | 现行 decision | 必须投影的精确行为 |
| --- | --- | --- |
| ADR-1009 | D2 | 所有 F1 identity 均允许读取 rf0；以 rf0 为目的的写入白名单精确为 `ld.t-rf,ld.o-rf,ldm.t-rf,ldm.o-rf,set.w-rf,cs.eq-rf,cs.ne-rf,cs.n-rf,cs.z-rf,cs.p-rf` 十条；其它具有 RF destination 的 identity 写 rf0 均 ILLI。D1 只保留为被 D2 覆盖的 superseded history，不计入 27 条。 |
| ADR-1010 | D1 | 硬件异常 flags 更新为 sticky OR。 |
| ADR-1010 | D2 | 本次无异常时保持既有 rf0[4:0]，不得自动清零。 |
| ADR-1010 | D3 | 合法的软件写 rf0[4:0] 可直接清除或改写 flags。 |
| ADR-1010 | D4 | 自动 flags 更新精确适用于历史 `fcsr_flags=open-blocked` 的 53 条 identity；11 条 RF 存取/搬移/`set.w` 类不因搬运位模式自动置位或清除。 |
| ADR-1010 | D5 | 合法软件写立即生效；后续异常在当前值上 sticky OR，历史硬件 flags 不强制覆盖软件写值。 |
| ADR-1011 | D1 | ft 运算、转换和符号位指令写 RF 时，低 32 位为 ft 位型，高 32 位固定 `0xffffffff`。 |
| ADR-1011 | D2 | `ld.t-rf`、`ldm.t-rf` 同样使用 64 位 NaN-boxing，高 32 位固定 `0xffffffff`。 |
| ADR-1012 | D1 | `foqcmp`、`ftqcmp` unordered 路径写 RD 为 `0x7ff8000000000000`。 |
| ADR-1012 | D2 | `foscmp`、`ftscmp` unordered 路径写 RD 为 `0x7ff0000000000001`。 |
| ADR-1012 | D3 | qNaN/sNaN 输出仅由 qcmp/scmp 指令类别决定，不依赖输入 NaN quiet/signaling 类别。 |
| ADR-1013 | D1 | 非格式转换的单 NaN 算术输入丢弃输入 payload/符号，返回 canonical qNaN。 |
| ADR-1013 | D2 | 多 NaN 输入仍返回 canonical qNaN；任一源为 sNaN 则置 NV，与输入顺序/payload/符号无关。 |
| ADR-1013 | D3 | 单个 sNaN 算术输入返回 canonical qNaN 并置 NV。 |
| ADR-1013 | D4 | `fo2ft`、`ft2fo` 按 SimRISC-03 规范正文传播 NaN payload；sNaN 转换置 NV 并返回 qNaN。该条覆盖早先 canonical-discard 选择。 |
| ADR-1013 | D5 | 算术/多操作数中 qNaN 不置 NV、任一 sNaN 置 NV，结果均 canonical qNaN；不得覆盖 D4/D6 的格式转换规则。 |
| ADR-1013 | D6 | `fo2ft`、`ft2fo` 的 NaN 转换结果符号固定为正号。 |
| ADR-1014 | D1 | tininess 在最终舍入后检测。 |
| ADR-1014 | D2 | underflow 同时置 `UF+NX`；overflow 同时置 `OF+NX`。 |
| ADR-1015 | D1 | 复位后 rf0[17:16]=RNE(`00`)，rf0[4:0]=0；只读 NaN 位与 SBZ 域仍按各自规则。 |
| ADR-1015 | D2 | `ftcls/focls immu6!=1` 在 assembler 阶段拒绝；非 assembler 路径到达硬件则 ILLI。 |
| ADR-1015 | D3 | 多 fault 同时成立时 ILLI 优先于 MALIGN；非法编码/操作数不进入地址对齐判定。 |
| ADR-1015 | D4 | scaleB 将浮点 `rfhd` 按当前 rf0[17:16] 舍入模式转换为整数 n，再计算 `rfhc×2^n`；同一舍入模式也控制最终结果舍入。 |
| ADR-1015 | D5 | scaleB：指数 qNaN 返回 canonical qNaN 且指数分类本身不置 flags；sNaN 置 NV 并返回 canonical qNaN；+Inf 视为 +Inf 指数；-Inf 令比例因子为 0，后续乘法按浮点规则决定结果/flags。 |
| ADR-1015 | D6 | 仅 D11 十条写白名单在写 rf0 时对 SBZ 域 `[50:32]`,`[21:18]`,`[15:5]` 静默忽略；其它域按各自规则。`rd2rf→rf0` 先按 D11 ILLI，不进入本规则。 |
| ADR-1015 | D7 | RF ldm/stm：EA0=`rbhb+rdhc`；第 i 项地址=`EA0+i×width`；`.t` width/step=4，`.o`=8；RF 编号递增。 |
| ADR-1015 | D8 | RF ldm/stm 任一元素 fault 时整条指令不提交任何 RF 写或 memory store，PC 留在 faulting instruction。 |

交叉优先级必须一并机器化：D11 目的合法性先于 D17:S6；D13 先形成 NaN-boxed 64 位写值，合法写 rf0 时再应用只读/SBZ mask；D15 的格式转换规则优先于算术 canonical 规则；D17:S4 的 ILLI 优先级先于 MALIGN；D12 软件写与自动异常按程序顺序组合。

## 6. D17 历史六条与现行十条关系

SPEC-103 历史 `D17:S6` 机械 scope 为六条：`ld.t-rf,ld.o-rf,ldm.t-rf,ldm.o-rf,set.w-rf,rd2rf`。该集合必须保留为“缺口发现时的 historical-six”，不能被删改成十条以伪装历史。

ADR-1009 D2 与 ADR-1015 D6 叠加后的**现行有效 scope**是十条写白名单：

`ld.t-rf,ld.o-rf,ldm.t-rf,ldm.o-rf,set.w-rf,cs.eq-rf,cs.ne-rf,cs.n-rf,cs.z-rf,cs.p-rf`。

变化必须由 checker 显式证明：历史六条中的 `rd2rf` 因 D11 非法而移出；五条 `cs.*-rf` 因 D11 允许写 rf0 而加入，故 `6 - 1 + 5 = 10`。不得把 historical-six 当作当前实现 scope，也不得回写 SPEC-103 历史证据。

D17 当前 active 历史键仍精确为 `D17:S1,D17:S3,D17:S4,D17:S5,D17:S6,D17:S8`；本任务的 resolution 层须为六键逐项关联 ADR-1015 的关闭规则。S2 始终为 `no behavioral consequence` 的 ledger 外 trace-only；S7 始终为 ADR-1008 证明的 spec-determined/non-gap；二者都不是 PASS。

## 7. 机器投影合同

`contracts/f1_gap_proofs.yaml` 继续保存 SPEC-103 的 gap proof、Candidate 输入、历史影响矩阵和 provenance；本任务在其上增加独立且具名的 resolution namespace，不得通过删除历史 proof/OPEN/Candidate 来制造“从未存在缺口”的假象。新增结构至少包括：

- lifecycle：逐条用户确认已完成、ADR 当前状态、激活必须要求七份 ADR 全部 Accepted；
- normative exclusions：SimRISC-03:7-8 HTML 注释不可作现行 authority；
- ADR/decision map：七份 ADR、27 条现行 decision、ADR-1009 D1 superseded、24 个历史 Candidate ID 与 supplemental decisions 的双向映射；
- rule tables：D11～D17 的结构化常量、集合、状态转换、优先级与适用条件；
- 64 行 current resolution matrix：每个 identity 的适用 decision、已关闭 facet、仍属 explicitly-unspecified/能力 BLOCKED 的部分及 owning consumer；
- consumer activation：Candidate 阶段只表示 projected/reviewable；Accepted 后才是 active implementation input。

24 个历史 Candidate 输入不得丢失或因 ADR 新增细化项而重复计数。ADR 中不直接对应单一 Candidate option 的细化决策（至少 D14-D3、D15-D5/D6、D17-D5/D8）必须作为具名 supplemental decisions 关联到所属 gap 与可观察后果。

`rootn(-0,2)` 继续是 `explicitly-unspecified`，不能因所有 ADR Accepted 而获得唯一 expected。root/log 独立正确舍入算法等实现能力问题也不得被 resolution checker 冒充为已完成。

## 8. Checker 要求

更新 `tools/spec/check_f1_gap_proofs.py`，但保留并继续执行 SPEC-103 的历史 proof 检查。新增检查必须真正解析 YAML、ADR Markdown、spec HTML comment 区间、contract/opcodes 与任务书当前路线，至少覆盖：

1. 七份 ADR 集合、状态和 decision 标题精确；现行 27 条、superseded D1 与确认记录完整；
2. 24 Candidate 与现行/supplemental decisions 双向闭合，无 orphan/重复/偷选；
3. D11 写白名单、D12 53/11、D13 18、D14 4、D16 36、六键历史 scope 与 64 identity 均从上游独立重算，不从被检查 resolution 自己推导期望；
4. D17:S6 historical-six/current-ten 的 `6-1+5=10` 关系；
5. §5 的常量、状态转换和交叉优先级；
6. current resolution matrix 精确 64 行、无 pseudo、无重复、适用 decision/facet/consumer 双向一致；
7. S2/S7 不进入 active、Candidate、blocking 或 PASS；
8. SimRISC-03:7-8 不能进入 current normative authority；
9. 10 本下游 taskbook 与 `INTEG-104m` 的活动合同均为六键、S7 non-gap、引用 SPEC-104t，并无 ADR-1005～1007 或“decisions 尚未确认”的陈旧门禁；
10. SPEC-102/103 历史任务书、完成区与本任务启动基线相比未被修改；
11. 禁止旁路 contract、backup 或实现产物。

生命周期接口必须区分两件事：

- 默认模式验证“Candidate 内容、用户确认与投影正确”，在 ADR 仍 Candidate 时可以 exit 0，但输出不得声称 active/Accepted；
- `--require-active` 只有 ADR-1009～1015 全部为 Accepted 时才 exit 0。本任务 reviewer 结束前它必须给出明确 BLOCKED/非零；该非零是预期替代证据，不能写成 PASS。主会话在双角色 Accepted 后改变 ADR 状态并须重新运行该模式。

禁止仅以 grep/固定字符串替换证明语义；字符串扫描只能用于发现陈旧措辞，不能代替集合推导、状态转换、identity 投影和 ADR 内容核对。

## 9. 反例门禁

更新 `tools/spec/test_f1_gap_proof_counterexamples.py`，保留 SPEC-103 既有反例能力，并新增至少下列类别：

1. 删除任一现行 decision，或把 ADR-1009 D1 重新激活；
2. 删除确认记录、伪造 Accepted、或使 `--require-active` 在 Candidate 时误绿；
3. 把 SimRISC-03:7-8 标为 current normative authority；
4. 24 Candidate/27 decision/supplemental 映射缺失、重复或跨 gap 错绑；
5. D11 白名单删一条、加一条或错误保留 `rd2rf`；
6. D12 sticky OR 改覆盖、无异常改清零、53/11 scope 改错；
7. D13 NaN-boxing 高半部翻一位或 `.t` load 不装箱；
8. D14 两个常量改错，或 qcmp/scmp 映射互换；
9. D15 算术/转换规则互相吞并、payload 不传播、转换结果保留负号或漏 sNaN NV；
10. D16 改为 before-rounding，或 UF/OF 漏 NX；
11. ILLI/MALIGN 优先级互换；scaleB 固定截断、错处理 NaN/Inf；
12. S6 退回 historical-six、包含非法 `rd2rf`，或漏任一 `cs.*-rf`；
13. ldm/stm 基址、步长、编号递增或 fault 原子性改变；
14. resolution matrix 63 行、重复、混入 pseudo、错 owning consumer；
15. 任一下游任务书恢复七键、S7 active、旧 ADR 号或“未确认”措辞；
16. 修改 SPEC-102/103 历史完成区/数字；创建旁路/backup 文件。

每个反例只允许在 `/tmp/opencode/SPEC-104t/` 的独立合成 git 树中执行：基线先绿 → 唯一锚点注入 → `git diff --name-only` 非空 → 命中目标检查名且真实非零 → 还原 → 临时树 clean → 复绿。异常 traceback、空注入、仅有 untracked status 或同组其它检查偶然报红均不算有效证据。reviewer 必须枚举所有实际 checker 并亲自注入，不得只复述 engineer 汇总。

## 10. 下游任务书同步清单

必须同步以下 **10 本普通任务书**：

1. `.xkw/tasks/testcases/TESTCASES-101t-F1浮点schema与oracle接口冻结.md`
2. `.xkw/tasks/testcases/TESTCASES-102t-F1独立浮点oracle与全量向量.md`
3. `.xkw/tasks/llvm/LLVM-101t-F1-RF寄存器与真实指令MC.md`
4. `.xkw/tasks/llvm/LLVM-102t-F1全量MClit与独立字节oracle.md`
5. `.xkw/tasks/llvm/LLVM-103t-setft-setfo伪指令与反汇编边界.md`
6. `.xkw/tasks/qemu/QEMU-101t-F1-RF状态存取搬移与setw.md`
7. `.xkw/tasks/qemu/QEMU-102t-F1转换算术FMA符号与rootlog.md`
8. `.xkw/tasks/qemu/QEMU-103t-F1比较条件分类与FCSR回归.md`
9. `.xkw/tasks/integ/INTEG-102t-F1跨模块接口与64facet对齐.md`
10. `.xkw/tasks/integ/INTEG-103t-F1端到端闭环与M1不变回归.md`

并同步里程碑任务书：

11. `.xkw/tasks/integ/INTEG-104m-F1浮点闭环里程碑.md`

每本任务书必须：使用六键 active 集合；把 S2/S7 分别标为 trace-only/non-gap 且不计 PASS；加入 `SPEC-104t` 和相应 Accepted ADR 作为语义依赖；删除活动章节中的七键/S7 active、ADR-1005～1007、以及“现行 decisions 尚未确认”措辞；写入本任务相关的精确适用规则，而不是只说“参见 ADR”。

同步不得把动态验收改成现在可跑：schema/oracle/vector、LLVM/QEMU 实现/build、E2E 和里程碑仍按真实能力 BLOCKED。ADR Accepted 只解除语义选择门禁，不提供实现 PASS。

## 11. 精确允许与禁止路径

### 11.1 未来 `/dispatch SPEC-104t` 唯一允许修改

1. `contracts/f1_gap_proofs.yaml`
2. `tools/spec/check_f1_gap_proofs.py`
3. `tools/spec/test_f1_gap_proof_counterexamples.py`
4. `.xkw/tasks/spec/SPEC-101k-F1浮点阶段启动与任务分解.md`
5. §10 列出的 10 本下游普通任务书
6. `.xkw/tasks/integ/INTEG-104m-F1浮点闭环里程碑.md`
7. 本任务文件的 `## 16. 完成区`
8. `.work/log/spec/SPEC-104t-*.log`（gitignored）

### 11.2 明确禁止修改

- `.xkw/knowledge/**`，包括 ADR、MEMORY、milestones、changelog、contract；
- `.xkw/tasks/spec/SPEC-102t-F1浮点合约与64身份映射.md`；
- `.xkw/tasks/spec/SPEC-103t-F1语义缺口证明与候选ADR输入.md`；
- 除 §11.1 明列外的全部 `.xkw/tasks/**`；
- `.tao/**`、`spec/**`、`README.md`；
- `contracts/opcodes.yaml`、`contracts/legality_rules.yaml` 及除 `f1_gap_proofs.yaml` 外的 `contracts/**`；
- `tests/**`、`components/**`、`.work/f1/**`、`.work/source/**`、`.work/build/**`、`Makefile` 与任何实现文件；
- 新建平行 projection YAML/checker、backup 文件或其它旁路产物；
- git add/restore/checkout/stash/commit/reset/clean 等会改变真实仓库或索引的操作。

主会话只有在 `/complete` 双角色 Accepted 后，才可另行更新 ADR-1009～1015 状态及 `.xkw/knowledge/{MEMORY,milestones,changelog}.md`；该后处理不是 engineer 的允许范围。

## 12. 依赖、文件所有权、冲突与资源

### 12.1 真实能力依赖

当前真实具备：SPEC-102/103 已验证；64 identity、11 facet、24 Candidate、六键 active scope、S2/S7 结论、15 节点/28 边历史 DAG 与现有 Python/PyYAML 检查能力均已有证据；七份 ADR 文件存在且现行 decisions 有逐条确认记录。

当前不具备：七份 ADR 的 Accepted 状态、下游 schema/oracle/vector、LLVM/QEMU F1 实现/build 和 E2E。后者均不得成为本任务 PASS 条件。

### 12.2 所有权与文件冲突

- SPEC-104t 独占三个机器产物和本轮任务书同步；执行期间不得并行 dispatch 任何会写这些路径的任务。
- 10 本下游任务书及 `INTEG-104m` 在本任务完成前不得并行执行，否则任务合同会与执行基线竞态。
- SPEC-102/103 和 `.xkw/knowledge/contract-f1-floating.md` 是历史证据，只读；当前 resolution 通过覆盖层解释历史，不回写历史。
- 启动 dirty baseline 位于 `/tmp/opencode/SPEC-104t/plan-baseline`，共 58 条路径。dispatch 前须生成 NUL-safe status、逐路径 SHA256 与任务书副本；授权路径若本已 dirty，只能在当前内容上做最小增量，禁止用 HEAD/旧副本覆盖。

### 12.3 资源冲突与串并行

本任务只运行 Markdown/YAML/Python 静态检查，不启动 LLVM/QEMU 构建。反例树统一放 `/tmp/opencode/SPEC-104t/`；可为节省磁盘串行复用临时树，但每例必须重新证明 clean baseline、非空注入、还原和复绿。

本任务必须串行完成后，下游才能按新合同 dispatch。其后 LLVM MC 支路可与 TESTCASES 的非共享文件工作逻辑并行；QEMU 仍依赖 testcases，LLVM/QEMU 的重内存 build 在当前宿主上必须串行。

## 13. 路线、关键路径与 k↔m

```text
SPEC-101k → SPEC-102t（历史合约，已验证）
           → SPEC-103t（gap proof，已验证）
           → SPEC-104t（确认语义机器投影与任务同步）
               ├→ TESTCASES-101t → TESTCASES-102t
               ├→ LLVM-101t → {LLVM-102t, LLVM-103t}
INFRA-108t ────┼→ QEMU-101t → QEMU-102t → QEMU-103t
               └→ {全部 F1 产物} → INTEG-102t → INTEG-103t → INTEG-104m
```

关键路径：`SPEC-104t → TESTCASES-101t → TESTCASES-102t → QEMU-101t → QEMU-102t → QEMU-103t → INTEG-102t → INTEG-103t → INTEG-104m`。ADR-1009～1015 的 Accepted 状态是 SPEC-104t 完成后的主会话激活门禁，不得提前写进本任务产物。

`SPEC-101k` 保持已验证，但其当前路线、任务表、依赖图、验收与 `k↔m` 须加入 SPEC-104t；2026-09-26 完成记录原文不得改。`INTEG-104m` 只有在 64 required facet 的实现/独立验证闭合、七份 ADR 已 Accepted、S2/S7 口径保持、M1 回归不退化且跨模块影响全部处置后才能置里程碑。

## 14. Candidate 生命周期与 ADR 门禁

1. ADR-1009～1015 的现行 decisions 已逐条用户确认，本任务不得再次选择、推荐、改写或新增 decision。
2. 本任务执行和 reviewer 验收期间，七份 ADR 必须保持 Candidate；机器产物只能称 `confirmed/projected/pending-activation`，不得称 Accepted/active implementation truth。
3. reviewer 必须审查实际投影、反例、HTML 注释 authority、历史保护及下游同步；architect 再交叉复核。
4. 只有 reviewer 与 architect 均给出 Accepted 后，主会话才能将七份 ADR 改为 Accepted，并更新 MEMORY/milestones/changelog。
5. 主会话状态转换后必须运行 checker `--require-active`；未获得该绿灯不得 dispatch 消费语义的下游任务。
6. 若任一 ADR decision 在执行中显得不足、冲突或需细化，本任务结论必须 Needs Revision；不得在 YAML/checker/任务书中暗增选择。

## 15. 验收与可执行性

| # | 判据 | 可执行性 |
| --- | --- | --- |
| 1 | `SPEC-102t`/`SPEC-103t` 已验证；64 identity、11 facet、24 Candidate、六键 active/S2/S7 历史基线可复核 | **现在可跑**：现有 task/contract/opcodes/checker 只读核对 |
| 2 | ADR-1009～1015 文件齐全，27 条现行 decision 与 ADR-1009 D1 superseded 关系准确，每条现行 decision 有用户确认记录 | **现在可跑**：逐 ADR 解析与人工对照 |
| 3 | SimRISC-03:7-8 被识别为 HTML 注释且不参与 current authority | **现在可跑**：原始 Markdown comment-range 解析；错误引用反例 |
| 4 | resolution namespace 具备 §7 全部内容，24 Candidate/27 decision/supplemental 双向闭合 | **现在可跑（产出后）**：checker + reviewer 独立逐 decision 对照 |
| 5 | D11 白名单、D12 53/11、D13 18、D14 4、D16 36、六键 scope、S6 `6-1+5=10` 与 64 行 matrix 均由上游独立重算一致 | **现在可跑（产出后）**：结构化解析，不需组件构建 |
| 6 | §5 全部状态转换、常量、优先级和特殊规则都有非空定向反例，目标语义 FAIL/非零、还原 clean、复绿 | **现在可跑（产出后）**：仅 Python/YAML/Markdown 临时树 |
| 7 | 10 本下游任务书与 `INTEG-104m` 均为六键、S2 trace-only、S7 non-gap、依赖 SPEC-104t/Accepted ADR，且动态判据仍按能力 BLOCKED | **现在可跑（同步后）**：任务书 parser + 陈旧措辞反例 |
| 8 | SPEC-102/103 历史任务书/完成区/数字、`.tao/**`、spec、contracts/tools 禁止路径及启动时其它 dirty 内容未变 | **现在可跑**：前后 status + 58 条逐路径 SHA256；任一越界即 FAIL |
| 9 | 默认 checker 在 Candidate 阶段验证投影而不声称 active | **现在可跑（产出后）** |
| 10 | `--require-active` 在七份 ADR 仍 Candidate 时成功 | **BLOCKED（且当前必须非零）**：替代证据为明确 pending-activation 报告；只有双角色 Accepted 后由主会话改状态再复跑 |
| 11 | ADR-1009～1015 已 Accepted，MEMORY/milestones/changelog 已沉淀 | **BLOCKED**：只允许 `/complete` 双角色 Accepted 后由主会话处理；本任务不得代写 |
| 12 | schema/oracle/vector、LLVM/QEMU F1 实现和动态验证完成 | **BLOCKED**：下游尚未执行；替代证据为同步后的自包含合同、依赖和规则表，不得记 PASS |
| 13 | F1 64×required-facet/E2E、root/log 能力和 `INTEG-104m` 达成 | **BLOCKED**：等待全部下游与 M1 回归；Candidate/ADR/checker 绿灯均不能替代 |

任何空集合、只打印 PASS、异常 traceback、把 BLOCKED 计成功、用实现行为证明语义或用旧日志替代当前真实输出的结果均不满足验收。

## 16. 完成区

### engineer 实测记录（2026-09-28）

- 产出：`contracts/f1_gap_proofs.yaml`（保留历史层并增加末尾 `resolution` namespace）；`tools/spec/check_f1_gap_proofs.py`（G1–G21，含跨行 HTML comment、Candidate 生命周期、规则字段逐项校验）；`tools/spec/test_f1_gap_proof_counterexamples.py`（临时树根改为 `/tmp/opencode/SPEC-104t/`，覆盖本节全部反例类别）。下游 10 本普通任务书、`SPEC-101k` 与 `INTEG-104m` 的同步内容已存在于当前授权版本，未在本轮重复改写；ADR-1009～1015 均保持 Candidate，任务状态未改。
- 默认 checker：`set -o pipefail; python3 tools/spec/check_f1_gap_proofs.py` → `rc=0`，`通过 138 项，失败 0 项，跳过 0 项`；输出含 `PENDING ACTIVATION`，未声称 active/Accepted/PASS。日志：`.work/log/spec/SPEC-104t-check-default-final.log`。
- active gate：`set -o pipefail; python3 tools/spec/check_f1_gap_proofs.py --require-active` → 预期 `rc=3`，实测 7 份 ADR 为 Candidate、`0/7 Accepted`，明确输出 `ACTIVE GATE: BLOCKED`；日志：`.work/log/spec/SPEC-104t-check-require-active-final.log`。
- 独立验证：`python3 -m compileall -q tools/spec` → `rc=0`（`.work/log/spec/SPEC-104t-compileall.log`）；`python3 tools/spec/check_f1_contract.py` → `通过 74 项，失败 0 项，PASS`（`.work/log/spec/SPEC-104t-contract-check.log`）。
- 反例：全量驱动器实测 `66/66 个反例被成功抓住（注入后 FAIL + 还原后 PASS）`，每例临时树均位于 `/tmp/opencode/SPEC-104t/ce-*`，包含 §9-1～§9-16 及历史保护/S2/S7/authority 反例；日志：`.work/log/spec/SPEC-104t-counterexamples-full.log`。resolution 专项复跑也为 `rc=0`，日志：`.work/log/spec/SPEC-104t-counterexamples-resolution.log`。
- 反例还原：全量输出逐例记录 `git checkout rc=0`、`git clean rc=0`、`残留脏文件 0`、还原后 `rc=0`；临时树已清理。`ADR-1009/D1` superseded、historical-six 与 current-ten `6-1+5=10`、S2 trace-only、S7 non-gap 均由 checker/反例覆盖。
- 范围/基线：启动 NUL status 为 59 条记录；最终仍为 59 条。启动基线 59 条逐路径 SHA256 中，仅本任务允许的 `tools/spec/check_f1_gap_proofs.py` 与 `tools/spec/test_f1_gap_proof_counterexamples.py` 两条哈希发生变化；其它既有 dirty 内容未变。比对日志：`.work/log/spec/SPEC-104t-baseline-compare.log`、`.work/log/spec/SPEC-104t-baseline-hash-final.log`。`git diff --check` 的唯一报错是启动时既有 `spec/SimRISC-03-浮点类指令.md:7` trailing whitespace（HTML comment 起始行），未触碰；日志：`.work/log/spec/SPEC-104t-diff-check.log`。
- BLOCKED/遗留：ADR 尚未 Accepted，故 `--require-active` 维持 BLOCKED；schema/oracle/vector、LLVM/QEMU、E2E、里程碑与实现能力仍按任务书保持 BLOCKED。状态转换、ADR Candidate→Accepted 与知识沉淀由主会话 `/complete` 负责。

### `/complete` 结论（2026-09-28：Needs Revision）

- reviewer 在 `/tmp/opencode/SPEC-104t/reviewer/` 独立临时树确认：将任一 current decision 的 `behavior` 反向篡改后，`check_f1_gap_proofs.py` 仍 `138/138`、`rc=0`；投影检查只核对标题/映射/确认记录，未逐项校验行为真值。
- D15 的 conversion payload 传播与 sNaN→NV、以及 arithmetic canonical/payload 与 qNaN/sNaN NV 规则均可被篡改而假绿。内置 66 个反例仅覆盖 D15 conversion result sign，不覆盖这些任务书 §9-9 要求；故上方“覆盖本节全部反例类别”不成立。
- architect 交叉复核确认上述证据及基线完整性，结论同为 **Needs Revision**。修复必须限于既有授权路径：对全部 current/supplemental `behavior` 字段按 ADR/任务书结构化真值加严 checker，补齐 D15 conversion/arithmetic payload/NV 定向反例，并全范围审计同类字段；不得新增语义、变更 ADR 状态、修改 spec/历史任务书或扩展至实现。
- reviewer 前后真实仓库 59 条 status、59 个 dirty SHA256 与任务书审查前副本一致；反例树均已清理。证据：`/tmp/opencode/SPEC-104t/reviewer/logs/{counterexamples-independent,custom-injections,independent-oracle,final-baseline-compare}.log`。

### engineer 返工实测记录（2026-09-28）

- 修复范围严格限于 `tools/spec/check_f1_gap_proofs.py`、`tools/spec/test_f1_gap_proof_counterexamples.py` 与本完成区；ADR-1009～1015 仍为 Candidate，任务状态未改。checker 新增独立 `PIN_BEHAVIOR_CLAUSES`，覆盖全部 27 条 current/supplemental `behavior`，并以具名 `G13 decision-behavior` 检查逐项验证；期望片段独立转录自本任务 §5/ADR decision body，不从 YAML 推导。D15 明确覆盖转换 payload 传播、sNaN→NV/qNaN、正号，以及算术 payload/符号丢弃、canonical qNaN、qNaN 不置 NV、sNaN 置 NV，并保留转换优先级约束。
- 默认 checker：`python3 tools/spec/check_f1_gap_proofs.py` → `rc=0`，`通过 139 项，失败 0 项，跳过 0 项`；输出 `PENDING ACTIVATION`，未声称 active/Accepted。日志：`.work/log/spec/SPEC-104t-redispatch-check-default.log`。
- active gate：`python3 tools/spec/check_f1_gap_proofs.py --require-active` → 实测 `rc=3`，`通过 139 项，失败 0 项`，明确 `ACTIVE GATE: BLOCKED`，`0/7` Accepted，七份 ADR 均 Candidate；日志：`.work/log/spec/SPEC-104t-redispatch-check-require-active.log`。
- 反例驱动器保留原 66 项，新增 6 项 D15 定向反例及 27 项逐 behavior 反向注入反例；每项均在 `/tmp/opencode/SPEC-104t/ce-*/` 独立 git 树执行，基线先绿、`git diff --name-only` 非空、命中具名 `decision-behavior` FAIL/非零、`git checkout`/`git clean` 还原 clean、还原后复绿。实测 `99/99 个反例被成功抓住`，`rc=0`；日志：`.work/log/spec/SPEC-104t-redispatch-counterexamples.log`。该记录**更正**上方历史 engineer 记录中“66/66 覆盖本节全部反例类别”的不实表述：66 项本身未覆盖本返工要求的 D15 payload/NV 与全部 behavior 真值；历史记录保留，当前 99/99 才是返工后的完整数字。
- 语法/工具验证：`python3 -m py_compile ...` `rc=0`；`python3 -m compileall -q tools/spec` `rc=0`；`python3 tools/spec/check_f1_contract.py` → `通过 74 项，失败 0 项，PASS`；日志分别为 `.work/log/spec/SPEC-104t-redispatch-compile.log`、`.work/log/spec/SPEC-104t-redispatch-compileall.log`、`.work/log/spec/SPEC-104t-redispatch-contract-check.log`。
- baseline/范围：返工前后均为 59 条 status 记录，NUL-safe 路径集完全一致；基线逐路径 SHA256 仅两个允许的 checker/反例驱动器路径变化，未发现越界变化。日志：`.work/log/spec/SPEC-104t-redispatch-baseline-compare.log`、`.work/log/spec/SPEC-104t-redispatch-baseline-status.log`。反例临时树已由 `--rm-trees` 清理。
- `git diff --check` 需结合开工基线解释：若仍报告 `spec/SimRISC-03-浮点类指令.md:7` trailing whitespace，则该项是既有 dirty baseline，未由本返工触碰；返工专属输出留存于 `.work/log/spec/SPEC-104t-redispatch-diff-check.log`。BLOCKED 仍维持：`--require-active`、schema/oracle/vector、LLVM/QEMU、E2E 与里程碑能力均未冒充 PASS。

### `/complete` 返工结论（2026-09-28：Needs Revision）

- 用户授权本轮 reviewer/architect 均使用 GPT-5.6 Luna，作为 workflow 代码/审查模型隔离的明示例外；仍使用独立安全树与逐字节 baseline。
- 27 条 `behavior` 反向注入与 7 条 D15 原子规则注入均已取得具名 G13 FAIL、还原 clean 与复绿；但 reviewer 在独立安全树运行全量 99/99 driver 时，CE-12 后无输出挂起并被终止，未取得全量完成退出码。任务书禁止把未完成驱动器计为 PASS。
- architect 复核：CE-12 自身已有此前独立注入的 G11 `adr-binding` FAIL/还原证据；本次更可能是安全树/驱动器诊断缺失而非语义 checker 缺陷，但 CE-13 及以后未覆盖用例不能据此推定通过。
- 返工仅限现有反例驱动器与完成区：为每个 subprocess 加 timeout，timeout 时记录命令、阶段、stdout/stderr 与 safe-tree 状态；排除嵌套临时树或异常 symlink；从 CE-12 补跑全部未覆盖用例并逐例给出非空注入、目标 FAIL、还原 clean、复绿。不得改 ADR、语义真值、spec、历史任务书或实现。
- 审查期间真实仓库 59 条 status、59 个 dirty SHA256 与任务书 baseline 均一致；证据：`/tmp/opencode/SPEC-104t/reviewer-return2/`。

### engineer 限定返工实测记录（2026-09-28）

- 修复范围仅为 `tools/spec/test_f1_gap_proof_counterexamples.py` 与本完成区；未改变 checker 语义规则、YAML、ADR、任务状态或其它路径。driver 现对每个 subprocess/stage 使用显式 timeout；超时会输出 case、stage、精确命令、timeout、stdout/stderr、目标树 status 及临时树 symlink/inode 诊断并返回非零。临时树使用 `symlinks=False` 字节复制，拒绝嵌套 source/target、symlink 和共享 device+inode，并在每例结束后 checkout/clean/status 复核 clean。
- 根因定位：旧 reviewer 日志在 `CE-12` 标题后、甚至“临时树”行之前停止，故卡点位于 `build_tree` 快照阶段而非 CE-12 checker 语义；旧 driver 对该阶段和 subprocess 均无 timeout/阶段诊断，且保留 symlink 复制，无法区分快照/命令卡死。新 driver 将其拆分为 bounded `build-tree-*` stages；CE-12 从真实源树独立复跑 `rc=0`、用时 6.9s，注入后 G11 `adr-binding` FAIL、还原 clean、复绿。
- 全量真实源模式：`set -o pipefail; python3 tools/spec/test_f1_gap_proof_counterexamples.py --rm-trees`，`rc=0`，`99/99`，用时 `679.9s`；日志 `.work/log/spec/SPEC-104t-driver-99-real.log`。全量每例均记录非空 diff、目标语义 FAIL、还原后 `rc=0`/脏文件 0。
- 独立安全源树：由真实源逐字节复制构造 `/tmp/opencode/SPEC-104t/isolated-byte-source`，复制校验 `symlinks=0 shared_inodes=0`、`rc=0`；随后 `--source-root /tmp/opencode/SPEC-104t/isolated-byte-source --rm-trees` 全量 `rc=0`，`99/99`，用时 `677.2s`。日志 `.work/log/spec/SPEC-104t-safe-copy.log`、`.work/log/spec/SPEC-104t-driver-99-safe.log`。该运行不以真实仓库作为 source root。
- 本轮门禁：默认 checker `rc=0`（139/139，PENDING ACTIVATION）；`--require-active` 实测 `rc=3`（0/7 Accepted，BLOCKED）；`compileall rc=0`；contract check `74/74，PASS`。日志分别为 `.work/log/spec/SPEC-104t-redispatch2-check-default.log`、`.work/log/spec/SPEC-104t-redispatch2-check-require-active.log`、`.work/log/spec/SPEC-104t-redispatch2-compileall.log`、`.work/log/spec/SPEC-104t-redispatch2-contract-check.log`。
- 基线：本轮开工/收工真实仓库 dirty baseline 仍为 59 条既有记录；既有用户改动均未触碰。新增路径仅本任务允许的 driver 与本完成区；临时安全源树/反例树均在 `/tmp/opencode/SPEC-104t/`，并已通过 `--rm-trees` 清理反例树。原有 BLOCKED（ADR 尚未 Accepted、下游实现/动态能力）继续保持 BLOCKED。

### `/complete` 最终结论撤回（2026-09-28：Needs Revision）

- reviewer 与 architect 均为用户明确授权的 GPT-5.6 Luna（代码/审查模型隔离例外已记录），曾给出 **Accepted**。独立字节安全源全量反例 `99/99`、`rc=0`；27 条 behavior 与 7 条 D15 原子规则均有具名 G13 FAIL、还原 clean 与复绿；timeout、nested-tree、symlink/inode 保护均有定向反例。
- reviewer baseline `/tmp/opencode/SPEC-104t/reviewer-driver-return/baseline/` 前后 59 条 status、逐路径 SHA256 与任务书副本均一致；临时 CE 树为 0。architect 复核同意不新增语义，HTML authority、S6 `6-1+5=10`、S2/S7、历史保护与下游门禁均受覆盖。
- 但主会话按流程临时将 ADR-1009～1015 置 Accepted 后复跑 checker，G13 仍无条件要求七份 ADR 为 Candidate，导致默认/`--require-active` 都 `138/1`、`rc=1`，不能输出任务书要求的 active 绿灯。已立即撤回本次状态/知识转换，任务回到 **待返工**、ADR 回到 Candidate。返工须修复 checker 的 Candidate/Accepted 生命周期分支并以 post-activation 临时树反例证明：Candidate 默认绿 + require-active rc=3，Accepted 默认/require-active 均绿；不得改语义或新增 decision。

### 主会话代行返工与收尾（2026-09-28：用户授权跳过复审）

- 用户明确授权主会话直接修复 lifecycle 分支并跳过后续 reviewer/architect。G13 现接受全 Candidate（投影/验收）或全 Accepted（/complete 后）两种一致状态，混合/其它状态均 FAIL；YAML 的 `pending-activation` 保留为投影时点记录。
- 独立 byte-copy 临时树验证：Candidate 默认绿且 `--require-active=rc=3`；单 ADR Accepted 的混合状态命中 `G13 adr-state-lifecycle` FAIL；七份 ADR 全 Accepted 时默认及 `--require-active` 均绿。新增 CE-29b 覆盖 mixed lifecycle；全量 `100/100` 反例均为非空注入、目标 FAIL、还原 clean、复绿，日志 `.work/log/spec/SPEC-104t-lifecycle-counterexamples-full.log`。
- 用户授权下，主会话将任务置 **已验证**、ADR-1009～1015 置 Accepted；下游实现/E2E 仍为 BLOCKED，未因状态激活计为 PASS。
