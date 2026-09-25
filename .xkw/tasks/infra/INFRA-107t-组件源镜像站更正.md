# INFRA-107t: 组件源镜像站更正

**模块**：infra
**项目里程碑**：**后续**（不在 M1 复现关键路径上）
**状态**：待开始
**日期**：2026-09-25
**依赖**：无（可与 M1 复现并行）
**来源**：`.xkw/knowledge/adr-1001-m1-reproduction-infra.md` D3 的登记项
**优先级**：低 —— 但**属已知隐患**，`.cache` 一旦清空即会触发

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

### S1 — 确认替代源（须先经用户确认，`mirrors.md`）

2026-09-25 实测**四个可用候选**，且 `llvmorg-23.1.1^{}` / `v11.1.1^{}` 三站结果**逐字符相同**：

| 候选 | 裸连 | 实测吞吐 | 备注 |
| --- | --- | --- | --- |
| **TUNA** `mirrors.tuna.tsinghua.edu.cn/git/` | ✅ | **~6.08 MiB/s**（285 MiB / <100 s 完成） | `adr-1001` D2 已选 |
| BFSU `mirrors.bfsu.edu.cn/git/` | ✅ | 未实测（ref 协商 16 s） | 备选 |
| NJU `mirror.nju.edu.cn/git/` | ✅ | 未实测（ref 协商 20 s） | 备选 |
| GitHub（`repository`） | ❌ 裸连超时 | 经代理 0.87 MiB/s，实测未完成 | 对照项 |
| SJTUG `mirrors.sjtug.sjtu.edu.cn/git/` | ❌（302 循环） | — | 已失效 |

### S2 — 修正清单

对 `llvm-project` 与 `qemu` 两个组件，把 `[[component.source]]` 的 `name`/`url` 改为裁定结果（`name` 须为组件内唯一的小写标识，如 `tuna`）。

`repository` 字段**保持不动**（`adr-0005` D1：`repository` = 规范上游身份，语义不变）。

### S3 — 处置 ADR（**逐条经用户确认，不得自行决定**）

`.tao/knowledge/adr-0006` D2 与 `adr-0008` D2 均为 `Accepted`，且都写死了 `name = "sjtu"`。按 `adr-authoring.md`「决策变更时**新增 ADR 或标注 `Superseded`**，不直接改写已 `Accepted` 的决策」，三选一**由用户裁定**：

| 选项 | 做法 | 适用 |
| --- | --- | --- |
| A（推荐） | 在 `.xkw/knowledge/` 新增 ADR（**编号 `adr-1002`**，取 `1xxx` 号段递增），**记录镜像站变更 + 本次实测数据**，并在其中注明 `.tao` 的 `adr-0006`/`adr-0008` D2 对应点已被取代；`.tao/` 因只读约束**不改动** | 避免破坏只读约束；跨树引用靠新 ADR 说明 |
| B | 解除 `.tao/` 只读，改写 `adr-0006`/`adr-0008` D2 并标 `Superseded` | 保持单树一致，但违反 `workflow.md` 的 `.tao/` 只读约定 |
| C | 维持 ADR 原文不动，只在清单加注释指向新 ADR | 改动最小，但 ADR 与清单的描述仍不一致 |

> 无论选哪个，**ADR 的每个 decision 都须逐条与用户确认后才可写入**（`AGENTS.md`「ADR decision 逐条确认」）。
>
> 编号约定：`.xkw/knowledge/adr-*` 取 **`1xxx` 号段**（`adr-1001` 已用，故下一个是 `adr-1002`），与 `.tao` 的 `0001`–`0011` 分离（`adr-1001` 的「编号说明」与 `deferred.md` 已记录该约定）。

### S4 — 补充防退化说明

在清单的注释里写明：`.cache/` 需**浅 bare 预填充**（`git clone --bare --depth 1 --branch <tag>`），否则 `make fetch` 会退化为全量 `--mirror` 克隆（30 GB / 数小时）。避免后来者误删 `.cache` 后直接 `make fetch`。

## 验收

| # | 项 | 判据 | 状态 |
| --- | --- | --- | --- |
| 1 | 清单已修正 | 两个组件的 `source[0]` 指向经用户裁定的可用镜像 | 现在可跑 |
| 2 | `repository` 未被动 | 两处 `repository` 仍为 `https://github.com/…` | 现在可跑 |
| 3 | `manifest-check` 通过 | `make PYTHON=python3.12 manifest-check` exit 0 | 现在可跑 |
| 4 | ADR 已按裁定处置 | 新 ADR 或原地标注已落盘，**每个 decision 有用户确认记录** | 现在可跑 |
| 5 | 清单与 ADR 一致 | 任意读者从清单能定位到对应的 ADR 决策 | 现在可跑 |
| 6 | 防退化说明已写 | 清单注释含「浅 bare 预填充」要求 | 现在可跑 |
| 7 | `make fetch` 仍不联网 | 在 `INFRA-103t` 预填的镜像上执行 `make fetch`，输出仍为 `skipping fetch` | 现在可跑 |
| 8 | 未擅自改动 `fetch.py` | `--mirror` 语义未变（属独立议题） | 现在可跑 |

## 风险

| 风险 | 预案 |
| --- | --- |
| 改动清单使 M1 复现结果与「原始环境」产生差异 | 本任务与复现轮**分离**；若在复现完成前执行，须在 `INTEG-101t` 完成区注明执行时点 |
| 新增 ADR 时 decision 未逐条确认 | 违反 `AGENTS.md`。**必须**先逐条问用户、拿到确认再写 |
| 擅自解除 `.tao/` 只读 | 违反 `.xkw/knowledge/workflow.md`。选选项 B 须用户明确授权 |

## 完成区

（待执行后填写：镜像站裁定结果、清单 diff、ADR 处置方式与用户确认记录、上述 8 项逐条结论）
