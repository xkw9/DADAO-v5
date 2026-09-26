# INFRA-101k: M1 复现启动与任务分解

**模块**：infra
**项目里程碑**：M1 复现（非新增 M1 工作）
**状态**：已验证
**日期**：2026-09-25
**决策依据**：`.xkw/knowledge/adr-1001-m1-reproduction-infra.md`（**Accepted**，D1–D3 已逐条确认）
**关联**：`.tao/knowledge/milestones.md`（M1 = 达成，只读参考）

## 目标

使 DADAO-v5 的 M1 成果**可复现**：在当前宿主上重建 `.cache/`（上游镜像）与 `.work/`（源码树 + 构建产物），重新构建 `llvm-mc` 与 `qemu-system-dadao`，并逐条复现 M1 六个模块里程碑记录的验收输出。

**本任务只做「澄清目标 + 分解任务」**，交付下列任务书；不改动任何代码或配置。

## 背景：为什么 M1 不可复现

M1 于 2026-09-22 达成（`SPEC-011m`/`TESTCASES-012m`/`INFRA-014m`/`LLVM-015m`/`QEMU-021m`/`INTEG-004m` 全部 `里程碑`），但 **`.cache/` 与 `.work/` 是指向 `/mnt/dadao-v5/` 的符号链接，而两个目标目录均为空** —— 上游镜像、源码树、构建产物全部不存在。

## 勘察结论（2026-09-25 实测）

| # | 阻塞项 | 实测证据 | 归属 |
| --- | --- | --- | --- |
| B1 | `.cache/` `.work/` 为空 | `ls .cache` → 空 | `INFRA-103t` / `INFRA-104t` |
| B2 | 缺 cmake / ninja / clang / meson / glib-dev / pixman-dev | `make doctor` → `FAIL; missing required tools: cmake` | `INFRA-102t` |
| B3 | Python 3.10 无 `tomllib`，6 个 infra 脚本全崩 | `manifest_check.py` → `ModuleNotFoundError: tomllib` | `INFRA-102t` |
| B4 | 清单所配 `sjtu` 源失效 | 302 死循环（详见 `adr-1001` Context） | `INFRA-103t`（规避）/ `INFRA-107t`（根治） |
| B5 | 3 个脚本硬编码旧路径 `/mnt/tao/DADAO-v5` | `test_encoding_oracle.py` → `llvm-mc not found at /mnt/tao/...` | `INFRA-102t`（符号链接绕过） |
| B6 | QEMU 11.1.1 要求 `meson >= 1.5.0`，jammy 仅 0.61.2 | `meson.build:1`（浅克隆读取） | `INFRA-102t` / `INFRA-106t` |
| B7 | 内存仅 3 GiB（可用约 1 GiB）+ 20 GiB swap，4 核 | `free -g` / `nproc` | `INFRA-105t` |

### 版本要求核对（jammy 22.04 现状 vs 要求）

| 组件 | 要求 | 宿主现状 | 结论 |
| --- | --- | --- | --- |
| cmake | ≥ 3.20.0（llvm/CMakeLists.txt:2） | 3.22.1（apt） | ✓ |
| glib | ≥ 2.66.0（qemu meson.build:1058） | 2.72.4（apt） | ✓ |
| pixman | ≥ 0.21.8（qemu meson.build:1156） | 0.40.0（apt） | ✓ |
| C++ 标准 | C++17（llvm/CMakeLists.txt:93） | gcc 11.4 支持 | ✓ |
| GCC | ≥ 7.4（CheckCompilerVersion.cmake:7） | 11.4 | ✓ |
| meson | **≥ 1.5.0**（qemu meson.build:1） | 0.61.2（apt） | **✗** → 交 QEMU `configure` 自建 venv 自动装 |
| Python | ≥ 3.11（`tomllib`） | 3.10.12 | **✗** → deadsnakes 装 3.12 并行解释器 |

### 代理勘察

宿主 `127.0.0.1:7890` 有监听，身份为 **`sshd: ubuntu@notty`（SSH 远程端口转发隧道）**，且未设任何环境变量。经代理后 `github.com` 可达（200），但 llvm-project 浅克隆仅 **0.87 MiB/s**；TUNA 裸连 **6.08 MiB/s**。**结论：全程裸连，不使用代理。**

## 范围

**在范围内**：宿主工具链安装、镜像预填、源码拉取与打补丁、两个组件构建、M1 验收输出逐条复现。

**不在范围内**：修改 `manifests/`、修改 `.tao/`（只读）、修改 `components/*/patches/`、修改任何 `contracts/` 或 `tests/vectors/`、修复 `fence`（`ISS-056`，已裁定 deferred）、M2 工作。

> **注**：`target/dadao/decode-insn.c.inc` 是 meson 在 `build-qemu` 阶段从 `target/dadao/insn.decode` 生成的产物，**不由 `apply-series` 产生**，故不在 `INFRA-104t` 的门禁内（归 `INFRA-106t`）。

## 约束

1. **实现工作区零改动**：下游复现任务的构建产物全部落在 `.cache/`、`.work/`（均 gitignored）与宿主 `/mnt`；除 `.xkw` 任务/知识记录外，不修改实现、配置或其它仓库文件，也不自行提交。
2. **`.tao/` 只读**（`workflow.md`）：其中的 `mirrors.md` / ADR 不改，本次结论记入 `.xkw/knowledge/`。
3. **不自行选定镜像站**（`mirrors.md`）：已由用户裁定为 TUNA（`adr-1001` D2）。
4. **失败即停**：每阶段过门禁才进下一步；失败先判定「环境差异」还是「真回归」，不重试掩盖。
5. **日志留存**：每条验证命令 `tee` 到 `.work/log/<模块>/<任务ID>-<命令名>.log`。
6. **临时产物**：`/tmp/opencode/<任务ID>/`，用完清理。

## 任务分解

| 任务 | 标题 | 依赖 | 门禁摘要 |
| --- | --- | --- | --- |
| `INFRA-102t` | 宿主工具链与 Python 运行时 | — | `make doctor` PASS；`manifest-check` exit 0 |
| `INFRA-103t` | 上游浅 bare 镜像预填 | `102t` | 两镜像 `cat-file -e` 命中；object 189,410 / 11,630 |
| `INFRA-104t` | 源码拉取与补丁系列应用 | `103t` | 两树各 9 commits；`llvm/lib/Target/DADAO/` 与 `target/dadao/insn.decode` 就位 |
| `INFRA-105t` | LLVM MC 构建 | `104t` | `build-mc: PASS` + 6 个工具就位 |
| `INFRA-106t` | QEMU 构建 | `104t` | `build-qemu: PASS` + `-M ?` 含 `dadao-m1` |
| `INTEG-101t` | M1 测试基线复现与逐条对齐 | `105t`+`106t` | L0–L8 全部执行并逐条核对；L0–L7 对齐 M1 里程碑记录，L8 为加固探针、非 M1 硬门槛 |
| `INFRA-107t` | 组件源镜像站更正（**后续，不在关键路径**） | — | 清单 + ADR 处置完成 |

`INFRA-105t` 与 `INFRA-106t` 之间无依赖，宿主 4 核 3 GiB 下**建议串行**（并行会加剧 B7 内存压力）。

## 验收

| # | 项 | 状态 |
| --- | --- | --- |
| 1 | 7 项阻塞项（B1–B7）均有归属任务，无遗漏 | 现在可跑 |
| 2 | 版本要求逐项核对（B6 除外，已列结论） | 现在可跑 |
| 3 | 代理勘察有实测数据支撑 | 现在可跑 |
| 4 | 任务分解覆盖 INFRA + INTEG，无环、依赖明确 | 现在可跑 |
| 5 | 已知遗留已登记（`source` 失效 / 硬编码路径） | 现在可跑 |
| 6 | 各 `t` 任务书内容与本分解一致 | 现在可跑（7 个下游任务书均已落盘并经用户确认） |
| 7 | 实际构建与测试结果 | **BLOCKED**（属 `INFRA-105t`/`106t`/`INTEG-101t`，本任务不涉及） |

## 完成区

### 规划完成与状态校正（2026-09-25）

- 7 项阻塞 B1–B7 均有正式归属；`INFRA-102t`~`107t` 与 `INTEG-101t` 共 7 个下游任务书已落盘。
- ADR-1001 D1–D3 已由用户逐条确认并置 Accepted；任务编号与版本库约定已同步到 workflow/MEMORY。
- 依赖链无环：`102t → 103t → 104t → {105t,106t} → INTEG-101t`，`107t` 独立后续；`105t`/`106t` 逻辑可并行但受宿主内存约束须串行。
- 原验收 6 的任务书落盘条件已满足；验收 7 明确属于下游实现，不是启动任务完成条件。
- 按 ADR-1002 D3，`k` 表示“规划审查与任务分解完成”，不等待子任务实现；按 D6 将状态由“待开始”校正为“已验证”。
- 当前路线与状态转移见 `.xkw/knowledge/milestones.md`；本次校正不修改 `.tao/`、实现、contracts 或 vectors。
