# INFRA-104t: 源码拉取与补丁系列应用

**模块**：infra
**项目里程碑**：M1 复现
**状态**：待开始
**日期**：2026-09-25
**依赖**：`INFRA-103t`
**解决阻塞**：B1（`.work/source/` 为空）
**决策依据**：`.xkw/knowledge/adr-1001-m1-reproduction-infra.md` D3（不改清单 `source`，靠预填镜像短路）

## 目标

从 `.cache/` 的浅 bare 镜像**离线**重建 `.work/source/{llvm-project,qemu}` 工作树，并把 `components/*/patches/series` 各 8 个补丁用 `git am` 忠实重放到锁定基线之上。

**本任务不改动仓库任何文件**（`.work/` 被 `.gitignore` 忽略）。

## 背景：为什么不直接 `make fetch`

`tools/infra/fetch.py:47-61` 的 `sync_mirror()` 在镜像已含锁定 commit 时**短路不联网**（`has_commit()` → 打印 `skipping fetch`），随后从**本地**镜像克隆工作树：

```
git clone --no-checkout <本地镜像> .work/source/<name>
git fetch --no-tags origin <commit>     # ← 风险点，见「风险与预案」
git checkout --detach <commit>
```

`INFRA-103t` 预填后，失效的 `sjtu` 源**不会被触及**（`adr-1001` D3 的核心依据）。

`tools/infra/apply_series.py:32-40` 强制要求工作树 HEAD **恰好**等于锁定基线才肯应用，否则拒绝（fail-closed，防错基线打补丁）。

## 范围

**在范围内**：`make prepare`（= `fetch` + `apply-series`）、HEAD 与 commit 数校验、补丁应用结果校验。

**不在范围内**：构建（属 `INFRA-105t`/`106t`）、修改 `components/*/patches/`、unshallow、改 `.cache/`。

## 步骤

### S1 — 执行 prepare

```bash
cd /home/ubuntu/DADAO-v5
make PYTHON=python3.12 prepare 2>&1 | tee .work/log/infra/INFRA-104t-prepare.log
```

**预期**：`fetch` 阶段对两个组件各打印一行 `already has <commit-prefix>; skipping fetch`（证明未联网），随后 `apply-series` 逐个 `git am` 8 个补丁。

### S2 — 校验基线与补丁数

```bash
git -C .work/source/llvm-project log --oneline | wc -l   # 期望 9 = 1 基线 + 8 补丁
git -C .work/source/qemu        log --oneline | wc -l    # 期望 9
git -C .work/source/llvm-project rev-parse HEAD          # 期望 d3ee023… 之外的最后一个补丁 commit（非基线）
git -C .work/source/llvm-project rev-list --count HEAD   # 浅克隆下同样为 9
```

补丁标题应与 `components/llvm-project/patches/series` 与 `components/qemu/patches/series` 的 8 个文件一一对应。

### S3 — 校验补丁产物落地

LLVM 侧（补丁 `0001`–`0008` 引入）：

```bash
ls .work/source/llvm-project/llvm/lib/Target/DADAO/
# 期望含：DADAO.td DADAOInstrFormats.td DADAOInstrInfo.td DADAORegisterInfo.td
#         AsmParser/ Disassembler/ MCTargetDesc/ MCTableGen/
grep -n DADAO .work/source/llvm-project/llvm/CMakeLists.txt   # 0001/0002：LLVM_ALL_TARGETS 注册
```

QEMU 侧（补丁 `0001`–`0008` 引入/修改）：

```bash
ls .work/source/qemu/target/dadao/     # 期望含 insn.decode translate.c helper.c cpu.c meson.build …
ls .work/source/qemu/hw/dadao/         # 期望含 dadao-machine.c
wc -l .work/source/qemu/target/dadao/insn.decode   # decodetree 源，256 patterns
```

> `target/dadao/decode-insn.c.inc` 由 meson 在 `build-qemu` 时生成，**本任务不校验**（归 `INFRA-106t`）。

### S4 — 校验打补丁相对基线的真实差异

```bash
git -C .work/source/llvm-project diff --stat 6dfe1677ab8dffbc6ec13d53a1e0215d75147689 HEAD
git -C .work/source/qemu        diff --stat c3d48b7d1e89604920e5b81b91140c2ad39a1943 HEAD
```

两条命令的 `git diff --name-only` **必须非空**——若为空说明补丁实际未生效（对照 `AGENTS.md`「注入有效性」教训：空 diff 不得当作成功）。

## 验收

| # | 项 | 判据 | 状态 |
| --- | --- | --- | --- |
| 1 | `make prepare` 成功 | exit 0，无 `refusing to apply patches` | 现在可跑 |
| 2 | fetch 未联网 | 日志含两个组件各一条 `skipping fetch` | 现在可跑 |
| 3 | 基线正确 | `apply-series` 未报 `HEAD … is not its base commit` | 现在可跑 |
| 4 | commit 数 = 9 | 两树 `git log --oneline \| wc -l` 均 **9** | 现在可跑 |
| 5 | 补丁与 series 一致 | 8 个补丁标题与 `series` 文件逐条对应，无 `git am` 冲突痕迹 | 现在可跑 |
| 6 | LLVM 产物落地 | `llvm/lib/Target/DADAO/` 含 4 个 `.td` + 4 个子目录；`llvm/CMakeLists.txt` 含 `DADAO` | 现在可跑 |
| 7 | QEMU 产物落地 | `target/dadao/insn.decode` 存在且含 256 patterns；`hw/dadao/dadao-machine.c` 存在 | 现在可跑 |
| 8 | 差异非空 | 两条 `git diff --name-only` 均非空 | 现在可跑 |
| 9 | 仓库工作区零改动 | `git status --porcelain` 与执行前逐字节相同 | 现在可跑 |
| 10 | 源码可编译 | —— | **BLOCKED**（属 `INFRA-105t`/`106t`；替代证据：验收 8 已证补丁生效，编译问题在下游任务暴露） |

## 风险与预案

| 风险 | 预案 |
| --- | --- |
| **`git fetch origin <commit>` 在浅本地镜像上被拒**（`uploadpack.allowAnySHA1InWant` 未开） | 退化预案：跳过该步，直接 `git -C .work/source/<name> checkout --detach <锁定commit>`。浅克隆的默认 HEAD 即该 tag 的 commit，对象已在本地，无需 fetch。**先确认 `rev-parse HEAD` 已等于锁定 commit 再决定是否动手**，不要盲目改脚本 |
| `git am` 冲突 | **立即停止并报告**，不得手工解冲突后继续（会破坏补丁忠实性，`apply_series.py` 的设计前提是忠实重放） |
| `make prepare` 非幂等（`.tao/knowledge/deferred.md` 已登记） | 对全新工作树**不触发**；若重复执行报 `HEAD is not its base commit`，应先 `make clean-work` 再重来，**不得**手工 reset 掩盖 |
| 磁盘 | `.work/source` 约 2 GB，落 `/mnt`（剩余 186 GB），充裕 |

## 完成区

（待执行后填写：`make prepare` 真实输出 + 上述 9 项逐条结论）
