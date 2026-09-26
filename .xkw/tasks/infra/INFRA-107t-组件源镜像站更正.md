# INFRA-107t: 组件源镜像站更正

**模块**：infra
**项目里程碑**：**后续**（不在 M1 复现关键路径上）
**状态**：待开始
**日期**：2026-09-25
**依赖**：无（可与 M1 复现并行）
**来源**：`.xkw/knowledge/adr-1001-m1-reproduction-infra.md` D3 的登记项
**优先级**：低 —— 但**属已知隐患**，`.cache` 一旦清空即会触发
**规划门禁**：**BLOCKED**——须先执行 `/plan INFRA-107t`，逐条确认镜像选择与 ADR-1003 decisions

## 目标

修正 `manifests/components.lock.toml` 中两个组件的 `[[component.source]]`（现为已失效的 `sjtu`），并按 `adr-authoring.md` 处置 `.tao` 中已 `Accepted` 的 `adr-0006` D2 / `adr-0008` D2。

**本任务会改动仓库文件**（`manifests/`），与 M1 复现轮的「工作区零改动」原则**故意分离**——复现结果不应被元数据变更干扰。

## 问题

`manifests/components.lock.toml:17-19` 与 `:29-31`：

```toml
[[component.source]]
name = "sjtu"
url = "https://mirror.sjtu.edu.cn/git/llvm-project.git"
```

**实测（2026-09-25）该源已失效**：

```
mirror.sjtu.edu.cn/git/llvm-project.git/info/refs
  → 302 → mirrors.sjtug.sjtu.edu.cn/git/llvm-project.git/info/refs
  → 302 → mirror.sjtu.edu.cn/...        ← 跳回，死循环
```

### 为何这是隐患（而非当前阻塞）

`tools/infra/fetch.py:47-61` 的 `sync_mirror()` 在镜像已含锁定 commit 时**短路不联网**（`has_commit()` → `skipping fetch`）。M1 复现轮由 `INFRA-103t` 预填镜像 ⇒ 该失效源**不会被触及**（`adr-1001` D3 的核心依据）。

**但**：若 `.cache/<name>.git` 被清空，`sync_mirror()` 会走 `git clone --mirror` —— **全量历史**（非浅克隆）。对 llvm-project 约 **30 GB / 数小时**，且目标 URL 是上述死循环 ⇒ **先长时间等待再失败**。

`tools/infra/clean_work.py` 只清 `.work/`、不清 `.cache/`，故正常流程不触发；但手工清理或换机即会踩到。

## 范围

**在范围内**：修正两个 `source` 条目、处置对应 ADR 决策、补充防止全量克隆退化的说明。

**不在范围内**：改动 `repository` 字段（那是**规范上游身份**，ADR-0005 D1 明确其语义不变，**不得**因网络问题改它）、改动 `fetch.py` 的 `--mirror` 语义（属另一个任务）、任何构建/测试改动。

## 步骤

### S1 — 候选替代源（仅作 `/plan INFRA-107t` 的确认依据）

2026-09-25 实测**四个可用候选**，且 `llvmorg-23.1.1^{}` / `v11.1.1^{}` 三站结果**逐字符相同**：

| 候选 | 裸连 | 实测吞吐 | 备注 |
| --- | --- | --- | --- |
| **TUNA** `mirrors.tuna.tsinghua.edu.cn/git/` | ✅ | **~6.08 MiB/s**（285 MiB / <100 s 完成） | `adr-1001` D2 已选 |
| BFSU `mirrors.bfsu.edu.cn/git/` | ✅ | 未实测（ref 协商 16 s） | 备选 |
| NJU `mirror.nju.edu.cn/git/` | ✅ | 未实测（ref 协商 20 s） | 备选 |
| GitHub（`repository`） | ❌ 裸连超时 | 经代理 0.87 MiB/s，实测未完成 | 对照项 |
| SJTUG `mirrors.sjtug.sjtu.edu.cn/git/` | ❌（302 循环） | — | 已失效 |

本表是候选站实测与替代证据，**不构成镜像选择**。执行本任务前须先运行独立的 `/plan INFRA-107t`，由主会话逐条取得用户确认。

### S2 — 修正清单

对 `llvm-project` 与 `qemu` 两个组件，把 `[[component.source]]` 的 `name`/`url` 改为裁定结果（`name` 须为组件内唯一的小写标识，如 `tuna`）。

`repository` 字段**保持不动**（`adr-0005` D1：`repository` = 规范上游身份，语义不变）。

清单注释须能定位到 `.xkw/knowledge/adr-1003-component-source-mirror.md`；只有镜像选择与 ADR-1003 decisions 经 `/plan INFRA-107t` 逐条确认后，才能写入具体镜像结论。

### S3 — 先完成独立 `/plan`，再允许 `/dispatch`

本任务当前保持 **BLOCKED**。唯一合法的 ADR 处置路线是新增：

`.xkw/knowledge/adr-1003-component-source-mirror.md`

`.xkw/knowledge/adr-1002-xkw-startup-workflow.md` 已占用 `adr-1002` 且为 Accepted，不得复用该编号。`.tao/knowledge/adr-0006-llvm-baseline.md` 与 `.tao/knowledge/adr-0008-qemu-baseline.md` 始终只读，不修改、不原地标注 `Superseded`；新 ADR 负责记录当前 `.xkw` 路线下的镜像站变更、实测依据、与历史决策的对应关系及后续约束。

在执行本任务前，必须先单独运行 `/plan INFRA-107t`。该 `/plan` 阶段由主会话一次只确认一个问题，逐条取得以下确认：

1. llvm-project 与 qemu 的目标镜像选择；
2. ADR-1003 中每个 proposed decision；
3. 新 ADR 与只读 `.tao/knowledge/adr-0006`、`adr-0008` 的对应和取代关系；
4. 清单注释及防退化约束。

确认完成后，主会话在 `.xkw/knowledge/` 落盘 ADR-1003，同步更新本任务，把依赖这些决策的验收项由 BLOCKED 改为“现在可跑”。只有该规划门禁完成后，才允许 `/dispatch INFRA-107t`。

不得在 `/dispatch` 阶段首次确认 ADR decisions；dispatch 只能执行已经通过 `/plan` 确认并落盘的任务书与 ADR。

### S4 — 补充防退化说明

在清单的注释里写明：`.cache/` 需**浅 bare 预填充**（`git clone --bare --depth 1 --branch <tag>`），否则 `make fetch` 会退化为全量 `--mirror` 克隆（30 GB / 数小时）。避免后来者误删 `.cache` 后直接 `make fetch`。

该注释须与 ADR-1003 经用户确认的 decisions 一致。

## 验收

| # | 项 | 判据 | 状态 |
| --- | --- | --- | --- |
| 1 | 清单已修正 | 两个组件的 `source[0]` 指向经用户裁定的可用镜像 | **BLOCKED**（须先 `/plan INFRA-107t` 确认镜像；替代证据：候选站实测、锁定 commit 对照与 ADR-1001 的本轮 TUNA 决策） |
| 2 | `repository` 未被动 | 两处 `repository` 仍为 `https://github.com/…` | 现在可跑 |
| 3 | `manifest-check` 通过 | `make PYTHON=python3.12 manifest-check` exit 0 | **BLOCKED**（最终清单依赖镜像选择；替代证据：checker 能力已由 `INFRA-102t` 验证） |
| 4 | ADR-1003 已落盘 | 每个 decision 均有 `/plan INFRA-107t` 的逐条用户确认记录 | **BLOCKED**（尚未执行独立 `/plan`；替代证据：编号、模板与唯一合法落点已确定） |
| 5 | 清单与 ADR-1003 一致 | 任意读者从清单能定位到对应的 ADR 决策 | **BLOCKED**（依赖验收 1/4；替代证据：固定路径与交叉引用要求已写入任务书） |
| 6 | 防退化说明已写 | 清单注释含「浅 bare 预填充」要求 | 现在可跑 |
| 7 | `make fetch` 仍不联网 | 在 `INFRA-103t` 预填的镜像上执行 `make fetch`，输出仍为 `skipping fetch` | 现在可跑 |
| 8 | 未擅自改动 `fetch.py` | `--mirror` 语义未变（属独立议题） | 现在可跑 |
| 9 | `.tao/` 零改动 | 相对启动 baseline 无新增 `.tao` diff | 现在可跑 |

## 风险

| 风险 | 预案 |
| --- | --- |
| 改动清单使 M1 复现结果与「原始环境」产生差异 | 本任务与复现轮**分离**；若在复现完成前执行，须在 `INTEG-101t` 完成区注明执行时点 |
| 新增 ADR 时 decision 未逐条确认 | 违反 `AGENTS.md`。**必须**先逐条问用户、拿到确认再写 |
| 任何 `.tao/` 改动 | 违反 workflow 不变量；立即停止，不存在本任务内授权例外 |

## 完成区

（待独立 `/plan INFRA-107t` 解除 BLOCKED 后执行；完成区须记录镜像站裁定、清单 diff、ADR-1003 decisions 的逐条确认及上述 9 项结论）
