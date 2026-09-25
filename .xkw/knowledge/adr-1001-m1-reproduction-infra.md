# ADR-1001: M1 复现的构建路径、镜像站与清单处置

**状态**：Accepted
**日期**：2026-09-25
**关联**：`INFRA-101k`~`INFRA-107t`、`INTEG-101t`；`.tao/knowledge/adr-0006-llvm-baseline`、`adr-0008-qemu-baseline`（均**只读参考**）

> **编号说明**：`.xkw/knowledge/adr-*` 采用 **`1xxx` 号段**（首个为 `adr-1001`，此后递增），与 `.tao/knowledge/adr-*` 的 `0001`–`0011` **不共享编号空间**，避免跨树引用歧义与撞号。

## Context（背景）

M1 已于 2026-09-22 达成（6/6 模块里程碑），但**成果不可复现**——`.cache/` 与 `.work/` 是指向 `/mnt/dadao-v5/` 的符号链接，而两个目标目录**均为空**：上游镜像、源码树、构建产物全部不存在。

2026-09-25 勘察确认 7 项阻塞（详见 `INFRA-101k` 的勘察表）。其中 3 项需要决策：

1. **构建路径**：`containers/dev` 基于 Ubuntu 24.04（自带 python3.12 + meson 1.3），宿主机是 Ubuntu 22.04（Python 3.10 无 `tomllib`、meson 0.61.2 低于 QEMU 11.1.1 要求的 1.5.0），且无 Docker。
2. **镜像站**：清单 `manifests/components.lock.toml` 两个组件的 `[[component.source]]` 均为 `name = "sjtu"`，实测该源**已失效**。
3. **清单/ADR 处置**：改 `source` 字段会触及 `.tao` 中已 `Accepted` 的 `adr-0006` D2 与 `adr-0008` D2。

### 关键实测数据（2026-09-25）

**代理**：宿主 `127.0.0.1:7890` 有监听，但身份是 **`sshd: ubuntu@notty`（SSH 远程端口转发隧道，已运行 7h31m）**，且**未设任何环境变量**（env / git config / `/etc/environment` / apt / pip / shell rc 全部无 proxy）。故裸连与经代理须分别评测。

| 源 | 裸连 | 经代理 |
| --- | --- | --- |
| `github.com` | ❌ 443 超时 | ✅ 200（2.8 s） |
| `mirrors.tuna/bfsu/nju` | ✅ 快 | ✅（绕路，无收益） |
| `mirror.sjtu.edu.cn`（清单所配） | ❌ 超时 | ⚠️ **302 → `mirrors.sjtug.sjtu.edu.cn` → 再 302 回前者，死循环** |

**吞吐对比**（`git clone --bare --depth 1`，llvm-project 285 MiB 量级）：

| 源 | 方式 | 结果 |
| --- | --- | --- |
| TUNA | 裸连 | **284.61 MiB / 189,410 objects / <100 s / ~6.08 MiB/s ✅ 完成** |
| GitHub（规范上游） | 经代理 | 240 s 仅 210 MiB，**0.87 MiB/s，未完成（timeout）** |

**基线一致性**（TUNA / BFSU / NJU 三站结果完全相同）：

- `refs/tags/llvmorg-23.1.1^{}` = `6dfe1677ab8dffbc6ec13d53a1e0215d75147689` —— 与 `adr-0006` D1 锁定 commit **逐字符相同**
- `refs/tags/v11.1.1^{}` = `c3d48b7d1e89604920e5b81b91140c2ad39a1943` —— 与 `adr-0008` D1 锁定 commit **逐字符相同**
- 克隆所得 object 数 **189,410**（llvm）/ **11,630**（qemu）—— 与 `adr-0006` D2 记录的数字**逐位一致**

**版本要求核对**（避免选错路径）：cmake 3.22 ≥ 3.20 ✓；glib 2.72 ≥ 2.66 ✓；pixman 0.40 ≥ 0.21.8 ✓；LLVM 23.1.1 的 `LLVM_REQUIRED_CXX_STANDARD` = **17**、`GCC_MIN` = **7.4** ✓（宿主 gcc 11.4 达标）；但 QEMU 11.1.1 `meson.build:1` 要求 `meson_version: '>=1.5.0'`，jammy apt 仅 0.61.2 ✗。

## Decision（决策）

### D1：构建路径 = 宿主机原生构建

不用 Docker、不用 chroot。在 Ubuntu 22.04 上用 apt 补齐工具链；Python 3.12 经 deadsnakes PPA 装为**并行解释器**，不覆盖系统 `python3`。

- 一切经 Makefile 已有的 `PYTHON ?=` 旋钮调用：`make PYTHON=python3.12 …` ⇒ **零仓库改动**
- meson 不手动安装：交由 QEMU `configure` 自建 venv 按 `pythondeps.toml` 自动 pip 安装

### D2：镜像站 = TUNA（裸连）

`.cache/llvm-project.git` 与 `.cache/qemu.git` 均从 `https://mirrors.tuna.tsinghua.edu.cn/git/` 按 `adr-0006` D2 / `adr-0008` D2 的原始方式预填（**浅 bare、非 treeless**，保证 worktree 可离线重建）。

理由排序：① 6.08 MiB/s 比 GitHub 经代理快约 **7 倍**；② **不依赖那条 ssh 隧道**（外部会话，说断就断，而构建要跑 1.5–3 h）；③ commit 与 object 数已对 `adr-0006`/`adr-0008` 逐一验证。

### D3：不改清单 `source`、不动 `.tao` 的 ADR，只记录 + 后续任务

**不改** `manifests/components.lock.toml` 的 `[[component.source]]`（仍为 `sjtu`），**不改** `.tao/knowledge/adr-0006` D2 与 `adr-0008` D2（`.tao/` 按 `workflow.md` 只读）。

理由：预填后 `fetch.py` 的 `sync_mirror` 因 `has_commit()` 命中而**完全短路、不联网**，故 `source` 字段**不影响本次复现**，仅为打印值。改动会引入与复现无关的变更、且触及已 `Accepted` 的决策。

**已登记的潜在陷阱**（不在本次修复）：`.cache` 若被清空，`make fetch` 会执行 `git clone --mirror`（**全量历史**，LLVM 约 30 GB）打到那个 302 死循环 URL 上 ⇒ 先长时间等待再失败。归属 `INFRA-107t`。

**记录去向**：因 `.tao/` 只读，本次实测结论记入**本 ADR** 与 `.xkw/knowledge/deferred.md`，**不改** `.tao/knowledge/mirrors.md`。

## Rationale（理由）

**为什么 D1 选原生而非容器**：`containers/dev` 虽是最贴近原始环境的路径，但装 Docker 属系统级改动、且 `.work`/`.cache` 是指向 `/mnt` 的符号链接，容器内需额外挂载否则悬空。实测 jammy 22.04 的全部版本要求**除 meson 外均已满足**，而 meson 由 QEMU 自带机制解决 ⇒ 容器带来的额外保真度收益，不足以抵偿系统级改动与符号链接复杂度。

**为什么 D2 不用 GitHub**：GitHub 经代理仅 0.87 MiB/s（285 MiB 需 >5 min 且实测未完成），且依赖一条随时可能断的 SSH 隧道；TUNA 裸连 6.08 MiB/s 且 commit 已验证。**快 7 倍 + 不依赖外部会话**两点叠加，决定性。

**为什么 D3 选"只记录"**：`adr-authoring.md` 规定「决策变更时新增 ADR 或标注 `Superseded`，不直接改写已 `Accepted` 的决策」。而本次**并未真正变更**获取途径——预填后的实际获取途径由 `.cache` 镜像决定，与 `source` 字段无关。改动 `source` 属于"顺手修"，会引入两个额外风险面（清单与 ADR 不一致、`.tao` 只读约束）。按"复现优先、变更隔离"处理，把真实问题（`source` 已失效）转为显式后续任务 `INFRA-107t`。

## Consequences（影响）

1. **宿主被改动**（一次性、系统级）：apt 新增构建依赖 + deadsnakes PPA + `python3.12` + 兼容符号链接 `/mnt/tao/DADAO-v5`。**仓库工作区零改动**。
2. **`.cache/` 落地两个浅 bare 镜像**（约 285 MiB + 52 MiB）；`.work/` 落地源码树与构建产物（约 20 GB），均位于 `/mnt`（剩余 186 GB）。
3. **构建内存受限**：宿主仅 3 GiB RAM（可用约 1 GiB）+ 20 GiB swap、4 核。`INFRA-105t` 须以降内存参数预置 CMake cache。
4. **`INFRA-107t` 为已知遗留**：清单 `source` 仍是失效的 `sjtu`；`INFRA-107t` 须一并处置 `.tao` 的 `adr-0006` D2 / `adr-0008` D2（新增 ADR 或标 `Superseded`，逐条经用户确认）。
5. **`INFRA-102t` 登记第二项遗留**：3 个脚本硬编码旧仓库路径 `/mnt/tao/DADAO-v5`（`tools/llvm/gen_m1_asm.py:169`、`tools/llvm/test_m1_asm.py:24`、`tools/llvm/test_encoding_oracle.py:335`）。本次以宿主兼容符号链接绕过（与原环境一致），根治方案为改为从 `__file__` 推导。
6. **`.xkw` 任务号采用 1xx 段**（`INFRA-101k`~`107t`、`INTEG-101t`）：`.tao` 已占用 `INFRA-001k`~`014m` / `INTEG-001k`~`004m` 且只读，同号会导致跨树引用歧义。
7. **`.xkw/` 纳入版本库**（用户裁定，不写入 `.gitignore`）：任务书与知识库随仓库提交，决策与门禁可审计。宿主侧产物（`.cache/`、`.work/`）仍由根 `.gitignore` 排除。

## 状态说明

- **Candidate**（2026-09-25）：落盘时置 `Candidate`，D1 / D2 / D3 已由用户**逐条确认**（构建路径 → 宿主机原生；镜像站 → TUNA；清单/ADR → 不改只记录）。
- **Accepted**（2026-09-25）：经用户复核裁定**置 `Accepted`**。同时裁定两项配套约定：① 本 ADR 落盘时曾用编号 `0012`，经用户裁定**改号为 `1001`**（`.xkw` 改用 `1xxx` 号段，此后递增，**不与 `.tao` 的 `0001`–`0011` 共享编号空间**）；② **`.xkw/` 纳入版本库**（不写入 `.gitignore`），其任务书与知识库随仓库提交、可审计。
- 决策变更时新增 ADR 或标注 `Superseded`，不直接改写已 `Accepted` 的决策。
