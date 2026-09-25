# MEMORY — DADAO-v5 自有项目记忆（`.xkw`）

## 这是什么

在克隆来的 DADAO-v5 项目基础上做开发。`.tao/` 是原项目的交互目录，**只读参考、不改动**；自己的任务文件、知识库、流程规则全部放在 `.xkw/` 下（结构照搬 `.tao`）。

## 当前状态

- 2026-09-22：建立 `.xkw/` 骨架（`knowledge/` + `tasks/<module>/`）、`.opencode/commands/`（`plan`/`dispatch`/`complete`）。
- 三个角色 agent（architect/engineer/reviewer）定义暂存于 `/tmp/opencode/agents/`，待用户移到 `~/.config/opencode/agents/`（V2 用复数 `agents/`）。移动前 `task` 无法按名调起——命令模板已内置兜底：用 `general` 子代理 + 在 prompt 注入角色职责。

### 2026-09-25：M1 复现（`INFRA-101k` 启动）

**背景**：M1 已于 2026-09-22 达成（`.tao` 六模块里程碑全部 `里程碑`），但 **`.cache/` 与 `.work/` 是指向 `/mnt/dadao-v5/` 的符号链接且两个目标目录均为空** ⇒ 上游镜像、源码树、构建产物全部不存在，M1 成果**不可复现**。本轮目标是重建并逐条复现验收基线。

**决策**（`adr-1001`，**Accepted**，D1–D3 已逐条经用户确认）：

| 决策 | 结论 |
| --- | --- |
| D1 构建路径 | **宿主机原生构建**（Ubuntu 22.04，apt 补工具链 + deadsnakes 装 Python 3.12 作并行解释器，经 `make PYTHON=python3.12` 调用，零仓库改动）。不用 Docker / chroot |
| D2 镜像站 | **TUNA 清华**（裸连 ~6.08 MiB/s，不依赖 ssh 隧道；GitHub 经代理仅 0.87 MiB/s 实测未完成） |
| D3 清单/ADR | **不改** `manifests/` 的 `source` 字段、**不改** `.tao` 的已 `Accepted` ADR；只记录 + 开后续任务 `INFRA-107t` |

**关键实测**：TUNA/BFSU/NJU 三站的 `llvmorg-23.1.1^{}` = `6dfe1677ab8dffbc6ec13d53a1e0215d75147689`、`v11.1.1^{}` = `c3d48b7d1e89604920e5b81b91140c2ad39a1943`，与 `.tao` 的 `adr-0006`/`adr-0008` D1 锁定值**逐字符相同**；克隆所得 object 数 189,410（llvm）/ 11,630（qemu）与 `adr-0006` D2 记录**逐位一致**。

**编号与版本库约定**（2026-09-25 用户裁定）：

- `.xkw/knowledge/adr-*` 取 **`1xxx` 号段**（首个 `adr-1001`，此后递增），**不与** `.tao/knowledge/adr-*` 的 `0001`–`0011` 共享编号空间。
- `.xkw/tasks/` 同样取 **`1xx` 段**（`INFRA-101k`~`107t`、`INTEG-101t`），避开 `.tao` 已占用的 `001`–`014`。
- **`.xkw/` 纳入版本库**（不写入 `.gitignore`）：任务书与知识库随仓库提交，决策与门禁可审计。宿主侧产物（`.cache/`、`.work/`）仍由根 `.gitignore` 排除。

**任务分解**（依赖链 `102t → 103t → 104t → {105t, 106t} → INTEG-101t`；`107t` 不在关键路径）：

| 任务 | 标题 | 状态 | 门禁摘要 |
| --- | --- | --- | --- |
| `INFRA-101k` | M1 复现启动与任务分解 | 待开始 | 7 项阻塞均有归属；B6 除外版本已核对 |
| `INFRA-102t` | 宿主工具链与 Python 运行时 | 待开始 | `make doctor` PASS；`manifest-check` exit 0 |
| `INFRA-103t` | 上游浅 bare 镜像预填 | 待开始 | 两镜像 `cat-file -e` 命中；object 189,410 / 11,630 |
| `INFRA-104t` | 源码拉取与补丁系列应用 | 待开始 | 两树各 9 commits；`diff --name-only` 非空 |
| `INFRA-105t` | LLVM MC 构建 | 待开始 | `build-mc: PASS` + 6 工具就位 |
| `INFRA-106t` | QEMU 构建 | 待开始 | `build-qemu: PASS` + `-M ?` 含 `dadao` |
| `INTEG-101t` | M1 测试基线复现与逐条对齐 | 待开始 | **L5 硬门槛**：`747 total, 739 passed, 0 failed, 8 deferred, 0 errors` |
| `INFRA-107t` | 组件源镜像站更正（后续） | 待开始 | 清单 + ADR 处置完成 |

**已实测通过的基线**（无需构建，宿主直接可复现）：

| 层 | 命令 | 实测输出 | 与里程碑记录 |
| --- | --- | --- | --- |
| L1 | `validate_vectors.py` | `178/178; 15 files, 747 cases; gaps: 0` | ✅ 一致 |
| L2 | `check_lit_bytes.py` | `53 patterns OK`（`44/53 masks`） | ✅ 与 `LLVM-015m` 一致 |
| L6 | `check_interface_alignment.py` | `80 项 \| PASS: 80 \| FAIL: 0 \| MANUAL: 0` | ✅ 与 `INTEG-004m` 一致 |
| L0 | `check_spec_drift.py` | `spec drift check: PASS` | ✅ |
| L0 | `check_issues.py` | `66 open, 8 closed (0 blocking M1-gate: 0)` | ✅ 与 `INTEG-004m` 一致 |

**权威基线更正**：`.tao/knowledge/MEMORY.md:13` 记的 harness `597/590/2/5/0` **已过期**（`TESTCASES-010t`/`011t` 补 150 条向量之前）。权威值以 `QEMU-021m` 为准：**`747 total / 739 passed / 0 failed / 8 deferred / 0 errors`**。

**已知遗留**：见 `deferred.md`（组件源 `sjtu` 已 302 死循环 / 3 脚本硬编码 `/mnt/tao` / `llvm-lit` 不由 Makefile 构建 / `make prepare` 非幂等）。**任务号采用 1xx 段**以避免与 `.tao` 已占用的 `001`–`014` 撞号。

<!-- 后续逐模块追加：已验收任务、里程碑、遗留项 -->

## 关键路径速查

| 路径 | 用途 |
|------|------|
| `.xkw/knowledge/workflow.md` | 自有流程规则（/plan /dispatch /complete 唯一来源） |
| `.xkw/knowledge/MEMORY.md` | 本文件（状态摘要） |
| `.xkw/knowledge/adr-1001-m1-reproduction-infra.md` | M1 复现的构建路径/镜像站/清单处置决策（**Accepted**，`1xxx` 号段） |
| `.xkw/knowledge/deferred.md` | 本轮新增的已知遗留登记 |
| `.xkw/tasks/<module>/` | 任务文件 `<PREFIX>-nnn<suffix>-描述.md`（**1xx 段**，避开 `.tao` 已占用编号） |
| `.opencode/commands/` | 三个命令（plan/dispatch/complete） |
| `.tao/` | 原项目交互目录（**只读参考，不改动**） |

## 待处置（deferred）

- 角色 agent 文件移动到位前，`/dispatch` `/complete` 用 `task` 调起 general 子代理时须在 prompt 内注入角色职责（见所属命令模板正文）；移好后改回按名调起。
- M1 复现轮的新增遗留全部登记在 `deferred.md`（组件源 `sjtu` 失效、3 脚本硬编码旧路径、`llvm-lit` 构建缺口等）。