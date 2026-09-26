# .xkw — DADAO-v5 自有交互入口

`.xkw/` 是当前自有开发流程的**唯一可写交互目录**；`.tao/` 是克隆项目留下的历史基线与工程经验，始终只读。

流程决策见 `.xkw/knowledge/adr-1002-xkw-startup-workflow.md`，规范细则见 `.xkw/knowledge/workflow.md`。

## 新会话读取顺序

首次进入、切换模块或长时间中断后恢复时，按以下顺序读取：

1. 根 `AGENTS.md`：仓库硬规则。
2. `.tao/README.md` 与 `.tao/knowledge/MEMORY.md`：原项目结构和只读基线。
3. **本文件**：确认 `.xkw` 自有入口与信息分流。
4. `.xkw/knowledge/workflow.md`：当前流程唯一规则源。
5. `.xkw/knowledge/MEMORY.md`：当前执行状态摘要。
6. `.xkw/knowledge/milestones.md`：当前路线、依赖、关键路径。
7. 当前模块的 `k` 启动任务与目标任务书。
8. 仅按目标需要读取相关 ADR、contract、deferred、spec 或 `.tao` 任务；禁止无目标遍历全部 `.tao/tasks/`。

推荐入口：`/xkw-start [模块或任务ID]`。仅需刷新状态时使用 `/xkw-status [模块]`。

## 信息来源与职责

| 信息 | 权威位置 | 说明 |
| --- | --- | --- |
| 仓库硬规则 | `AGENTS.md` | 最高优先级 |
| 原始规范 | `spec/`、根 `README.md` | 规范版本唯一来源仍是根 README |
| 已归一化技术契约 | `.tao/knowledge/contract-*.md`、`contracts/` | 只读使用；不得从实现反推 |
| 自有流程 | `.xkw/knowledge/workflow.md` | 五个项目命令的唯一规则源 |
| 自有决策 | `.xkw/knowledge/adr-*.md` | decision 必须逐条经用户确认 |
| 当前路线 | `.xkw/knowledge/milestones.md` | 仅记录 `.xkw` 自有轮次和依赖 |
| 当前状态摘要 | `.xkw/knowledge/MEMORY.md` | 摘要，不替代任务书或 ADR |
| 正式工作 | `.xkw/tasks/<module>/` | 任务书必须自包含 |
| 结论性遗留 | `.xkw/knowledge/deferred.md` | 不是任务；要实施必须转正式任务 |
| 已验证变更 | `.xkw/knowledge/changelog.md` | 已验收成果与经用户确认的流程变更 |

若摘要与权威文件冲突，以根规则、spec/contracts、Accepted ADR、目标任务书和真实命令输出为准，并登记状态漂移。

## 角色与命令

主会话是协调者，负责用户确认、状态转换、ADR decision 门禁和最终知识沉淀。

| 角色 | 入口 | 职责 |
| --- | --- | --- |
| architect | `/plan`、`/complete` 交叉复核 | 规划、依赖/冲突分析；不写实现 |
| engineer | `/dispatch` | 按已确认任务书实现、自审、填写完成区 |
| reviewer | `/complete` | 独立验收、主动注入反例、给出结论 |

| 命令 | 用途 | 是否可写 |
| --- | --- | --- |
| `/xkw-start [模块或任务ID]` | 完整项目启动与恢复快照 | 否 |
| `/xkw-status [模块]` | 轻量任务/依赖/dirty 状态刷新 | 否 |
| `/plan <目标>` | 创建或调整启动任务与任务分解 | 是 |
| `/dispatch <任务ID>` | 四项预检、用户确认后下发 engineer | 是 |
| `/complete <任务ID>` | reviewer 验收、architect 复核、知识沉淀 | 是 |

命令模板位于 `.opencode/commands/`；项目级角色定义位于 `.opencode/agents/`。二者只作入口和角色约束，不复制 workflow 的完整规则。

## 任务状态机

- `k` 启动任务：`待开始 → 已验证`。规划审查通过、必要 ADR decisions 已确认、下游任务书落盘后即完成，不等待实现任务结束。
- `t` 普通任务：`待开始 → 待验收 → 已验证`，验收失败则 `待返工`。
- `m` 里程碑：`待开始 → 里程碑`；有未处置跨模块影响时不得收尾。

编号空间与详细门禁见 `knowledge/workflow.md`。

## 启动报告最小格式

`/xkw-start` 必须输出：

1. 仓库根、分支、dirty baseline（区分既有用户改动）。
2. 目标模块/任务及唯一匹配结果。
3. 当前里程碑、关键路径、依赖和可并行/冲突关系。
4. `k/t/m` 状态是否合法，是否存在 MEMORY/任务/路线图漂移。
5. BLOCKED/deferred/ADR 待确认项。
6. 推荐下一动作：`/plan`、`/dispatch`、`/complete` 或先澄清；不得自动执行。

## 不变量

- `.tao/` 只读，参考仓库只读且不得成为执行依赖。
- Spec-first、Independent oracle、Component lock。
- 修改前保护既有用户改动；所有提交先经用户确认。
- 复杂验证留日志，临时产物只进 `/tmp/opencode/<任务ID>/`。
- 验证脚本必须有可达 FAIL 路径；覆盖不等于语义。
