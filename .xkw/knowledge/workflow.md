# Workflow — DADAO-v5 自有开发流程（`.xkw`）

> 本文件是 `/xkw-start`、`/xkw-status`、`/plan`、`/dispatch`、`/complete` 的**流程规则唯一来源**。
> `.opencode/commands/` 只提供薄入口，`.opencode/agents/` 只约束角色；不得在三处复制并演化不同版本的流程。
> `.tao/` 是克隆项目的只读基线，**不得修改**；全局与项目根 `AGENTS.md` 始终优先。

## 1. 入口与规则层级

统一入口是 `.xkw/README.md`。出现冲突时按以下优先级处理：

1. 系统/用户指令与根 `AGENTS.md`；
2. 根 `README.md` 的规范版本、`spec/`、Accepted contract/ADR、`contracts/`；
3. 本 workflow；
4. 目标任务书；
5. `milestones.md`、`MEMORY.md`、`changelog.md`、`deferred.md` 等摘要/记录。

摘要与真实文件或真实命令输出冲突时，不得用摘要覆盖事实；须报告并按流程修正状态漂移。

## 2. 目录与职责

```text
.xkw/
├── README.md                  # 自有流程统一入口
├── tasks/<module>/            # <PREFIX>-nnn<suffix>-描述.md
└── knowledge/
    ├── workflow.md            # 本文件，流程唯一规则源
    ├── MEMORY.md              # 当前状态摘要
    ├── milestones.md          # 自有路线、依赖、关键路径
    ├── changelog.md           # 已验收成果与经确认的流程变更
    ├── deferred.md            # 结论性遗留，不代替任务
    ├── adr-*.md               # 自有决策
    └── contract-*.md          # 自有合约（按需）

.opencode/
├── commands/                  # 命令薄入口
└── agents/                    # 项目级角色定义
```

- `.xkw/` 与 `.opencode/` 均纳入版本库。
- `.cache/`、`.work/` 是宿主侧产物并由根 `.gitignore` 排除。
- `.tao/`、参考仓库只读；引用参考仓库时标注“内容溯源，非执行必需”。

## 3. 编号与状态机

模块和前缀沿用 `.tao/README.md`：`infra=INFRA`、`spec=SPEC`、`testcases=TESTCASES`、`golden=GOLDEN`、`llvm=LLVM`、`qemu=QEMU`、`integ=INTEG`、`gem5=GEM5`、`sail=SAIL`。

`.xkw` 使用独立号段（ADR-1001）：

| 类别 | `.xkw` 号段 | 首个 | `.tao` 已占用 |
| --- | --- | --- | --- |
| 任务 | `1xx` | `INFRA-101k` / `INTEG-101t` | 各模块 `001` 起 |
| ADR | `1xxx` | `adr-1001` | `adr-0001`~`0011` |

跨树引用必须写完整路径前缀，禁止只写裸编号。

状态机：

- `k` 启动任务：`待开始 → 已验证`。规划审查通过、必要 ADR decisions 已确认、下游任务书已落盘后即完成；**不等待实现任务完成**。
- `t` 普通任务：`待开始 → 待验收 → 已验证`；验收失败转 `待返工`，返工后再回 `待验收`。
- `m` 里程碑：`待开始 → 里程碑`；存在未处置跨模块影响时不得收尾。

## 4. 角色与模型

| 角色 | 主模型 | 降级模型 |
| --- | --- | --- |
| architect | `openai/gpt-5.6-sol` | `opencode/nemotron-3-ultra-free` |
| reviewer | `openai/gpt-5.6-luna` | `opencode/nemotron-3-ultra-free` |
| engineer | `opencode/big-pickle` | `opencode/mimo-v2.6-flash-free` |

- 规划/审查与代码必须使用不同模型，防止同模型自证。
- 角色不变量见 `.opencode/agents/*.md`；本文件定义阶段流程。
- 模型不可用仅指明确的网络、429/403、额度、停用等调用错误。此时主会话可按表降级**一次**并登记；空返回不属于模型不可用，按“子代理异常”处理。
- OpenAI 网络需要代理时，先报告服务环境问题；不得把外部 SSH 隧道默认为项目基础设施。

## 5. 通用启动快照（所有流程前置）

### 5.1 完整读取顺序

首次进入、切换模块或长时间中断后恢复：

1. `AGENTS.md`；
2. `.tao/README.md`、`.tao/knowledge/MEMORY.md`（只读基线）；
3. `.xkw/README.md`；
4. 本 workflow；
5. `.xkw/knowledge/MEMORY.md`、`milestones.md`；
6. 当前模块 `k` 与目标任务；
7. 按目标读取相关 ADR/contract/deferred/spec；禁止无目标遍历全部 `.tao/tasks/`。

### 5.2 每次行动前的最小快照

`/plan`、`/dispatch`、`/complete` 都必须先核对：

1. 仓库根、当前分支与 `git status --porcelain=v1 --untracked-files=all`；保存 dirty baseline，区分既有用户改动。
2. 目标唯一匹配；多匹配、零匹配或编号歧义时停止并一次问一个问题。
3. 目标状态是否允许当前动作。
4. `MEMORY`、`milestones`、`k`、目标任务间是否漂移。
5. 依赖是否真实具备，不能只看“已验证”标签。
6. BLOCKED、deferred、ADR 待确认项与跨模块影响。
7. 预期修改范围和禁止触碰路径。

关键入口缺失、目标歧义、状态不合法或将覆盖既有用户改动时一律 **fail-closed**，不得“先做再补记录”。

## 6. `/xkw-start`：完整只读启动

输入：可选模块名或任务 ID。

行为：

1. 执行 §5.1 完整读取；有目标时只展开相关模块和任务。
2. 建立 dirty baseline，但不写文件、不改状态、不调执行子代理。
3. 对照 `.tao` 只读基线与 `.xkw` 当前状态，报告差异，不自动修正。
4. 输出当前里程碑、依赖图、关键路径、文件冲突/资源冲突、BLOCKED/deferred/ADR 项。
5. 根据状态建议下一动作：`/plan`、`/dispatch`、`/complete` 或先澄清。

固定输出：

- 入口与仓库快照；
- 目标解析；
- 当前路线与状态；
- 漂移/阻塞/风险；
- 推荐下一动作。

## 7. `/xkw-status`：轻量只读刷新

输入：可选模块名。

只读取 `.xkw/README.md`、本 workflow、MEMORY、milestones、目标模块任务头、deferred 与 git status；除非发现冲突需溯源，否则不重读大体量 `.tao/MEMORY.md`。

输出：

- 各任务状态计数及异常状态；
- 当前可下发任务、待验收任务、BLOCKED 任务；
- 关键路径与下一任务；
- dirty baseline 和状态漂移。

本命令不得自动改状态或写知识文件。

## 8. 启动任务 `k` 的合同

模块或里程碑首次规划必须创建/更新一个 `k`，至少包含：

1. 问题根源；
2. 目的与成功定义；
3. 对照关系：借鉴、差异、拒绝的 legacy；
4. 范围与不在范围内；
5. 硬约束与权威来源；
6. 阻塞/勘察证据；
7. 任务分解表（交付物、依赖、验收摘要）；
8. 依赖图、关键路径、文件冲突与资源冲突；
9. 分解理由与串并行建议；
10. 验收项（现在可跑/BLOCKED + 替代证据）；
11. `k↔m` 或本轮收敛条件；
12. 完成区/规划审查记录。

`k` 只规划不实现。reviewer 审查通过、用户确认必要 ADR decisions、任务书和 milestones 落盘后，由主会话置 `已验证`。

## 9. `/plan` 流程

1. 完成 §5 启动快照；读取目标相关的 `.xkw` 状态与必要 `.tao` 只读经验。
2. 判断是新模块/里程碑启动（须 `k`）还是现有路线调整。
3. 用 architect 规划：
   - 只做规划，不写实现；
   - 任务书自包含；
   - 逐项给出目标/范围/约束/验收；
   - 依赖能力实查；
   - 分析目标文件所有权、共享文件、资源限制和串并行；
   - 验收逐条标“现在可跑”或“BLOCKED（原因 + 替代证据）”。
4. 用 reviewer 交叉审查草案的内部一致性、依赖、可执行性、spec/vectors 一致性和 ADR 判据。
5. 涉及 ADR 时，主会话提出 decisions，**一次只向用户确认一个 decision**。未经逐条确认不得写 Accepted。
6. 审查通过后，architect 可仅将规划任务书落盘至 `.xkw/tasks/**`；主会话更新 ADR、milestones 与 MEMORY，并在 `k` 满足 §8 后置 `已验证`。
7. 核对最终 diff 只含规划范围，不覆盖启动时既有用户改动。

输出：任务文件清单、依赖/关键路径、reviewer 结论、ADR 确认记录、MEMORY/milestones 更新点。

## 10. `/dispatch` 流程

### 10.1 状态与预检

1. 完成 §5 启动快照并唯一定位目标。
2. 仅接受 `待开始` 或 `待返工`；`待验收`、`已验证`、`里程碑` 一律停止。
3. 执行四项强制预检：
   1. **任务书内部一致性**：目标/范围/约束/验收无矛盾。
   2. **依赖链实际可用性**：验证手段所需的全部前置真实具备。
   3. **验收可执行性**：逐条“现在可跑”或“BLOCKED（原因 + 替代证据）”，不得跑不了就 PASS。
   4. **与 spec/vectors 一致**：指令范围、编码和期望来源对齐 contracts/vectors；不适用时明确 N/A 原因。
4. 把预检结论和任务书全文提交用户；一次只澄清一个问题。**用户确认前不得下发**。

### 10.2 engineer 执行

1. 调 engineer；不可用时才用 general 并完整注入 engineer 职责。
2. prompt 必须包含任务路径、允许状态、dirty baseline、允许/禁止修改范围、日志和临时目录要求。
3. engineer 先执行再填写完成区；数字必须来自真实输出。
4. 数据/期望值任务须独立全量重算；validator 绿灯不是语义证据。
5. 复杂命令用 `tee` 写 `.work/log/<模块>/<任务ID>-<命令名>.log`，保存真实 pipeline 退出码。
6. 临时/合成产物只放 `/tmp/opencode/<任务ID>/`；入库产物的生成器/脚本必须一并放非易失位置。

### 10.3 返回与状态

- 正常完成：主会话核对任务完成区、输出和 git diff，将 `t` 置 `待验收`。
- `Task cancelled`/空结果：先核对完成区与 git status。产出已落盘则继续 `/complete`；未落盘则停止汇报，**不得自行重试**。
- 模型调用在执行开始前明确失败，可按 §4 降级一次；与空返回规则不同。
- 连续 ≥3 次空返回且均未落盘时，主会话可代行，但须登记 deferred，且仍必须独立 `/complete`。

输出：启动快照摘要、四项预检、用户确认、engineer 结果、diff/日志、状态变化。

## 11. `/complete` 流程

### 11.1 入口

1. 完成 §5 启动快照；目标必须唯一且状态必须为 `待验收`。
2. 建立审查前 dirty baseline，保护全部既有用户改动。**审查前快照是强制的，且必须是三件套**：
   1. `git status --porcelain=v1 --untracked-files=all` 原文；
   2. **每一条 dirty 路径的内容 sha256**（不只是路径列表——路径列表看不出「同一路径被改写」）；
   3. 任务书全文副本。
   三件套落在 `/tmp/opencode/<任务ID>/reviewer/baseline/`。缺 (2) 即视为未完成前置。
3. **审查后必须逐字节比对并留证**：重算 (1)(2) 并与审查前对比。
   - 既有 dirty 路径哈希变化、路径集变化、或任务书完成区之外的字节变化 → **本轮 reviewer 结论整体作废**，
     主会话须先按 §11.4 处理污染（可从快照恢复），再重新发起独立验收；**不得**沿用该轮任何证据。
   - 全部一致 → 把比对结果（命令与真实输出）写进验收记录，作为 baseline 未变的证据。
4. **权限不是隔离边界**：子代理的 `shell` 白名单只能降低误操作概率，解释器（`bash`/`python`）一旦放行
   即可执行任意命令。因此 reviewer 触碰真实仓库的防线是**第 2、3 条的快照**，不是权限规则；
   `workflow.md` 不接受「配置了 deny 所以安全」这种论证。
5. **`ask` 在子代理里等于 allow（2026-09-26 实测）**：对 `reviewer` 派子代理逐条探测 9 条命令，
   `shell: * → ask` **没有拦住**未列举的 `echo`（直接成功，exit 0）；而同一份配置里
   `git add/restore/commit/push/stash → deny` **确实拦住了**（`permission.rejected`）。
   原因是子代理属非交互 client，审批请求无人应答即放行。
   ⇒ 子代理的 shell 策略实际是 **deny-list**，不是 allow-list。写规则时按 deny-list 理解，
   不得把 `ask` 当成保护；真正的 allow-list 只能靠交互式主会话或 MCP/工具边界实现。

### 11.2 reviewer 独立验收

reviewer 必须先枚举**所有实际用于验收的脚本、检查器、shell 判据和独立 oracle**，再逐项验证：

1. 独立重跑任务验收，不采信 engineer 汇报数字。
2. 对每个检查器亲自注入反例并确认真实 FAIL/非零；不得仅复跑绿灯。
3. 全文件排查恒真断言、两支同结果、分支偏移/极性、覆盖脚本不读输入等同类缺陷。
4. 注入只能在 `/tmp/opencode/<任务ID>/reviewer/` 合成 git 树或可安全还原的临时工作树；每次须证明 `git diff --name-only` 非空。
5. 注入后还原；涉及源码/二进制时必须重建。给出临时树 clean、真实仓库 baseline 未变和复绿证据。
6. 覆盖/桩检查只证明实现存在；语义由独立 oracle 或端到端 harness 承担。
7. 完成区逐条对齐真实输出；可当场修正任务书中的事实记录，但不得替 engineer 扩范围实现。
8. 数据/期望值类任务对 size/sign 敏感用例逐条独立重算；错值当场修复，不得登记为遗留。
9. 探针分支全文件逐条核对目标，并给出“只改该断言期望 → FAIL”的输出。

结论只能是 `Accepted` 或 `Needs Revision`。

### 11.3 architect 交叉复核

architect 独立核对 reviewer 的结论、反例有效性、还原证据、依赖边界、spec/合约和跨模块影响；不重复实现、不负责最终收尾。

### 11.4 结论处理

- 任一结论 `Needs Revision`：主会话把任务置 `待返工`，列出文件/现象/证据/修复要求，等待重新 `/dispatch`。
- reviewer 与 architect 均 `Accepted`：主会话更新任务状态为 `已验证`，并沉淀 MEMORY、changelog、milestones；必要时更新 deferred。
- 知识沉淀和最终状态转换由主会话负责，不委派给子代理。
- 涉及 ADR 时仍须逐 decision 用户确认；未经确认不得写 Accepted。

输出：双角色结论、反例真实输出、还原证据、状态变化、知识沉淀点。

## 12. 里程碑与跨模块影响

- `milestones.md` 是 `.xkw` 自有路线权威；`.tao/milestones.md` 只读参考原项目基线。
- 里程碑核验前必须检查其它模块的上游修复、接口调整和未处置 deferred。
- 受影响时二选一：后移里程碑，或新增正式交互任务。
- 未处置影响存在时不得置“里程碑”。
- 区分依赖可并行、目标文件可并行和宿主资源可并行；任一不成立就明确串行。

## 13. 知识分流

- `MEMORY.md`：当前状态摘要和关键事实，不堆叠完整日志。
- `milestones.md`：路线、依赖、关键路径、状态。
- `changelog.md`：记录 `/complete` Accepted 的成果与经用户确认的流程性变更。
- `deferred.md`：已知但当前不做的结论性备忘；正式实施必须转任务。
- ADR：不可逆、跨模块、多方案、外部契约、结论固化、定位/方向。

## 14. 日志、临时目录与下载

- 日志：`.work/log/<模块>/<任务ID>-<命令名>.log`；reviewer 重跑加 `-review-`，architect 复核可加 `-architect-`。
- 命令正常执行时用 `tee`；必须保留 pipeline 中真实命令退出码。
- 临时产物：`/tmp/opencode/<任务ID>/`；不得另起 `/tmp/<其它名>`、不得放仓库根或 `~/`。
- 大文件从国外站下载前：查教育网镜像、测候选连通性/速度、含直连对照给建议，由用户选定；有 tag 默认建议浅下载但仍须确认。

## 15. OpenCode 项目定义

- 命令使用 `.opencode/commands/*.md`，agent 使用 `.opencode/agents/*.md`（OpenCode V2）。
- 命令不使用 shell 插值自动采集状态；所有检查通过正常工具权限执行，避免绕过权限流。
- 项目定义优先于全局同名定义；保存后由 OpenCode 自动重载，无需为普通修改重启服务。
- 全局 `~/.config/opencode/agents/` 不在本仓库修改范围；如含 DADAO 专用规则，建议用户后续删除或泛化。
