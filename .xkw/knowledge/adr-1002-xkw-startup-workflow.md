# ADR-1002: `.xkw` 项目启动、命令门禁与角色边界

**状态**：Accepted
**日期**：2026-09-25
**关联**：`.xkw/README.md`、`.xkw/knowledge/workflow.md`、`.opencode/commands/`、`.opencode/agents/`、`INFRA-101k`

## Context（背景）

`.tao/` 已形成成熟的入口页、模块启动任务、里程碑分层、角色协作与知识分流，但它是克隆项目的只读交互树。`.xkw/` 已拥有自有 workflow、MEMORY、任务与命令，却缺少统一入口、自有 milestones、只读启动/状态命令和统一的命令前置门禁；现有 workflow、command、agent 还存在规则重复，容易漂移。

勘察还发现两处现实漂移：`INFRA-101k` 的规划与下游任务已落盘但状态仍为“待开始”；MEMORY 仍称角色 agent 未移动，而 `~/.config/opencode/agents/` 已存在三角色文件。全局 agent 又写入了 DADAO 专用规则，不适合作为唯一落点；项目规则同时禁止直接修改仓库外文件。

OpenCode V2 官方文档确认：项目命令位于 `.opencode/commands/*.md`，项目 agent 位于 `.opencode/agents/*.md`；项目定义优先于全局同名定义，配置保存后自动重载。

## Decision（决策）

### D1：建立 `.xkw/README.md` 统一入口和固定读取顺序

新会话按 `AGENTS → .tao 只读基线 → .xkw README/workflow/MEMORY/milestones → 当前 k/任务 → 按需知识` 读取；不得无目标遍历全部 `.tao/tasks/`。

### D2：增加两个只读、命名空间化命令

新增 `/xkw-start [模块或任务ID]` 做完整启动/恢复快照，新增 `/xkw-status [模块]` 做轻量刷新。二者不得改文件、改状态、调用执行子代理或自动链入变更流程。使用 `xkw-` 前缀避免覆盖 OpenCode 通用命令。

### D3：冻结 `k` 启动任务模板与完成时点

模块/里程碑首次规划的 `k` 必须包含问题根源、目的、对照关系、范围/约束、任务表、依赖图/并行冲突、分解理由、验收与 `k↔m`。任务书经 reviewer 审查且必要 ADR decisions 已经用户确认后，`k` 即置“已验证”，不等待实现任务完成。

### D4：所有变更命令共享启动快照并 fail-closed

`/plan`、`/dispatch`、`/complete` 在行动前核对入口、唯一目标、合法状态、依赖、dirty baseline、BLOCKED/deferred。歧义、状态非法或关键知识文件缺失时停止。dispatch 仅接受“待开始/待返工”，complete 仅接受“待验收”；既有用户改动必须保护。

### D5：建立 `.xkw/knowledge/milestones.md`

自有路线图只记录 `.xkw` 轮次、依赖、关键路径和并行层；`.tao/knowledge/milestones.md` 保持只读原项目基线。plan 负责规划，complete Accepted 后更新状态。

### D6：一次性对齐当前状态

把 `INFRA-101k` 修正为“已验证”并同步 MEMORY；把角色 agent 未安装的陈旧记录改为已安装。启动/状态命令以后只报告漂移，不自动修正。

### D7：用项目级 agent 覆盖 DADAO 专用全局定义

不修改仓库外 `~/.config/opencode/agents/`；新增 `.opencode/agents/{architect,engineer,reviewer}.md`，由 OpenCode 的项目优先级覆盖/细化全局同名角色。全局文件后续由用户自行删除或泛化。

### D8：收紧角色边界，知识沉淀仍由主会话负责

architect 强制做启动模板、依赖/文件冲突/并行分析，complete 阶段只复核；engineer 强制状态与 dirty baseline、禁止改 `.tao` 和覆盖既有改动、失败即停、先得真实输出再填完成区；reviewer 先枚举全部检查器，只在临时树证伪，可修任务书事实记录但不扩范围实现。最终状态转换、ADR 门禁和知识沉淀由主会话负责。

### D9：workflow 是唯一流程规则源

commands 仅作薄入口，agents 仅写角色不变量；完整步骤只写在 `.xkw/knowledge/workflow.md`，避免三份规则漂移。

## Rationale（理由）

- 复用 `.tao` 的成熟结构，但不复制其历史状态或修改只读树。
- 把“完整启动”和“轻量刷新”分离，兼顾安全与上下文成本。
- `k` 代表规划完成而非实现完成，避免启动任务长期悬空。
- 统一 dirty baseline 与状态门禁，减少覆盖用户改动、重复执行和错误阶段下发。
- 项目级 agent 让 DADAO 规则随仓库审计，避免污染所有项目的全局角色。
- 薄命令减少重复；OpenCode 保存后自动重载，无需额外服务重启。

## Consequences（影响）

1. 新会话应优先运行 `/xkw-start`；日常刷新用 `/xkw-status`。
2. plan/dispatch/complete 会在更多前置条件上 fail-closed，换取更强的一致性。
3. 新增 README、milestones、两个命令与三个项目 agent；现有三个命令薄化。
4. `.tao` 与全局 agent 文件均不修改；全局 DADAO 专用 agent 会继续存在，但在本项目内由项目定义覆盖。
5. `INFRA-101k` 状态和 MEMORY 的 agent 记录进行一次性校正。

## 状态说明

- 2026-09-25：用户先确认生成本 ADR。
- D1–D7、D9 均逐条确认保留。
- D8 经一次澄清后最终确认：**知识沉淀仍由主会话负责**。
- 全部 decisions 确认后置 **Accepted**；后续改变任一 decision 须新增 ADR 或按授权标注 Superseded，不静默改写。
