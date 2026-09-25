# INFRA-103t: 上游浅 bare 镜像预填

**模块**：infra
**项目里程碑**：M1 复现
**状态**：待开始
**日期**：2026-09-25
**依赖**：`INFRA-102t`
**决策依据**：`.xkw/knowledge/adr-1001-m1-reproduction-infra.md` D2（TUNA，已确认）
**解决阻塞**：B1（`.cache/` 为空）、B4（清单所配 `sjtu` 源失效）

## 目标

在 `.cache/` 预填 `llvm-project.git` 与 `qemu.git` 两个**浅 bare 镜像**，各含 `manifests/components.lock.toml` 锁定的 commit，使 `make fetch` 能在**完全离线**的前提下重建 `.work/source/`。

**本任务不改动仓库任何文件**（`.cache/` 被 `.gitignore` 忽略）。

## 背景：为什么不直接 `make fetch`

`tools/infra/fetch.py:47-61` 的 `sync_mirror()` 在 `.cache/<name>.git` **不存在**时会执行 `git clone --mirror` —— **全量历史**，非浅克隆。对 llvm-project 而言是约 30 GB / 数小时，且清单所配的 `sjtu` 源已 302 死循环 ⇒ 必然长时间等待后失败。

`.tao/knowledge/adr-0006` D2 / `adr-0008` D2（只读参考）记录的原始做法正是**浅 bare 预填充**：`git clone --bare --depth 1 --branch <tag>`，且明确「**非 treeless**，worktree 可离线重建」。本任务照此执行。

## 范围

**在范围内**：`git clone --bare --depth 1` × 2、锁定 commit 与 object 数校验。

**不在范围内**：修改 `manifests/components.lock.toml`、修改 `.tao/` 的 ADR、unshallow、完整历史克隆、gem5（`enabled = false`）。

## 步骤

### S1 — 预填 LLVM

```bash
cd /home/ubuntu/DADAO-v5
git clone --bare --depth 1 --branch llvmorg-23.1.1 \
  https://mirrors.tuna.tsinghua.edu.cn/git/llvm-project.git \
  .cache/llvm-project.git
```

实测基线（2026-09-25 同命令预跑）：**284.61 MiB / 189,410 objects / <100 s / ~6.08 MiB/s**。

### S2 — 预填 QEMU

```bash
git clone --bare --depth 1 --branch v11.1.1 \
  https://mirrors.tuna.tsinghua.edu.cn/git/qemu.git \
  .cache/qemu.git
```

`.tao/knowledge/adr-0008` D2 记录：51.78 MiB / 11,630 objects / 4.1 s。

### S3 — 校验锁定 commit

```bash
git -C .cache/llvm-project.git cat-file -e 6dfe1677ab8dffbc6ec13d53a1e0215d75147689^{commit}
git -C .cache/qemu.git        cat-file -e c3d48b7d1e89604920e5b81b91140c2ad39a1943^{commit}
git -C .cache/llvm-project.git rev-parse HEAD
git -C .cache/qemu.git        rev-parse HEAD
```

两个 commit 取自 `manifests/components.lock.toml` 的 `commit` 字段（**唯一权威**，勿从 ADR 抄）。`HEAD` 应分别等于它们（浅克隆的默认分支即该 tag 的 commit）。

### S4 — 校验 object 数与浅层标志

```bash
git -C .cache/llvm-project.git count-objects -v
git -C .cache/qemu.git        count-objects -v
```

- `count` 应为 **189,410**（llvm）/ **11,630**（qemu）
- 存在 `shallow` 文件即证明是浅克隆（`ls .cache/<name>.git/shallow`）

### S5 — 确认 `make fetch` 会短路（**关键**）

```bash
python3.12 tools/infra/manifest_check.py      # 先过门禁
COMPONENT_SOURCE_LLVM-PROJECT=canonical python3.12 tools/infra/fetch.py   # 干跑，观察不联网
```

期望输出含 `already has 6dfe1677ab8; skipping fetch` / `already has c3d48b7d1e89; skipping fetch`（`fetch.py:57`）。**这一步是本任务的核心价值** —— 证明清单里那个失效的 `sjtu` 源不会被触及。

> 注：`COMPONENT_SOURCE_LLVM-PROJECT` 变量名含连字符，shell 中不易 export；此处仅为**干跑观测**，正式执行由 `INFRA-104t` 的 `make prepare` 承担（预填已就位时 `sync_mirror` 无论选哪个源都会短路）。

## 验收

| # | 项 | 判据 | 状态 |
| --- | --- | --- | --- |
| 1 | 两镜像存在 | `ls -d .cache/llvm-project.git .cache/qemu.git` | 现在可跑 |
| 2 | 锁定 commit 命中 | 两条 `cat-file -e <commit>^{commit}` 均 exit **0** | 现在可跑 |
| 3 | HEAD 等于锁定 commit | 两条 `rev-parse HEAD` 与 `manifests/components.lock.toml` 的 `commit` **逐字符相同** | 现在可跑 |
| 4 | object 数符合 ADR 记录 | llvm **189,410** / qemu **11,630** | 现在可跑 |
| 5 | 确为浅克隆 | `.cache/<name>.git/shallow` 存在 | 现在可跑 |
| 6 | 确为非 treeless（worktree 可离线重建） | 镜像内有完整 blob（非 `--filter=blob:none`）；由 `INFRA-104t` 验收 2 实证 | 现在可跑（间接） |
| 7 | `fetch.py` 不联网 | S5 输出含 `skipping fetch` | 现在可跑 |
| 8 | 磁盘占用 | `.cache/` 合计 < 1 GiB | 现在可跑 |
| 9 | 仓库工作区零改动 | `git status --porcelain` 与执行前逐字节相同 | 现在可跑 |
| 10 | 完整历史可用性 | —— | **不适用**（本就是浅镜像；ADR 已声明该边界） |

## 风险与预案

| 风险 | 预案 |
| --- | --- |
| TUNA 临时不可达 | 已测备用：BFSU（`mirrors.bfsu.edu.cn/git/`）、NJU（`mirror.nju.edu.cn/git/`）均可达且 tag SHA **完全相同**（实测三站 `llvmorg-23.1.1^{}` 与 `v11.1.1^{}` 逐字符一致）。换源须先经用户确认（`mirrors.md`） |
| 浅镜像上 `git fetch origin <commit>` 被拒 | 属 `INFRA-104t` 风险，不在本任务；预案见该任务书 S3 |
| 磁盘不足 | `.cache/` 落 `/mnt`（剩余 186 GB），充裕 |

## 完成区

（待执行后填写：两条 clone 的真实耗时/体积/object 数 + 上述 9 项逐条结论）
