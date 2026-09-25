# INFRA-106t: QEMU 构建

**模块**：infra
**项目里程碑**：M1 复现
**状态**：待开始
**日期**：2026-09-25
**依赖**：`INFRA-104t`
**决策依据**：`.xkw/knowledge/adr-1001-m1-reproduction-infra.md` D1
**建议**：与 `INFRA-105t` **串行**（宿主 4 核 / 3 GiB，并行会加剧内存压力）

## 目标

构建 `qemu-system-dadao`，使 M1 的 QEMU 侧验收（语义 harness 747 用例、E2E 冒烟）具备运行条件。

**本任务不改动仓库任何文件**（`.work/build/` 被 `.gitignore` 忽略）。

## 背景：meson 版本是本任务的主要不确定项

浅克隆读取 `qemu v11.1.1` 的 `meson.build:1` 实测：

```meson
project('qemu', ['c'], meson_version: '>=1.5.0',
```

而 Ubuntu 22.04（jammy）apt 仅有 **meson 0.61.2** ⇒ 版本差两个大版本。**本任务不手动安装 meson**，依赖 QEMU `configure` 自建 venv 并按 `pythondeps.toml` 自动 pip 安装锁定版本（`pypi.org` 裸连实测 200 可达）。

其它版本要求**已核对达标**（`INFRA-101k` 勘察表）：glib 2.72 ≥ 2.66 ✓、pixman 0.40 ≥ 0.21.8 ✓（且 `pixman` 在 `meson.build:1155` 是 `auto()`，必要时可 `--disable-pixman`）。

## 范围

**在范围内**：`make build-qemu`、机器类型清点、decodetree 产物校验、冒烟。

**不在范围内**：修改 `Makefile`、修改 `configure` 参数、gem5、`INTEG-101t` 的 harness 执行。

## 步骤

### S1 — 构建

```bash
cd /home/ubuntu/DADAO-v5
make PYTHON=python3.12 build-qemu 2>&1 | tee .work/log/infra/INFRA-106t-build-qemu.log
```

`Makefile:95-98` 的 configure 参数：`--target-list=dadao-softmmu --enable-tcg --disable-werror`；`Makefile:99` 随后 `make -j$(nproc)`。

**耗时预估 15–30 min**（4 核）。QEMU 只构建单一 target，比 LLVM 轻得多。

### S2 — 机器类型清点

```bash
.work/build/qemu/qemu-system-dadao -M ? 2>&1 | grep -i dadao
```

期望出现（`.tao/knowledge/` 的 M1 记录）：

```
dadao-m    DADAO M bare-metal test machine
```

> 记录用 M1 的输出为 `dadao-m`；若为其它名字（如 `dadao-m1`）属实现演进差异，**须如实记录并归因**，不得改测试基线去迁就。

### S3 — decodetree 产物校验

```bash
ls .work/build/qemu/target/dadao/*.c.inc 2>/dev/null
grep -c . .work/source/qemu/target/dadao/insn.decode   # decodetree 源，期望 256 patterns
```

`target/dadao/decode-insn.c.inc` 由 meson 在本阶段生成（`meson.build` 中 `decodetree.process('insn.decode', extra_args: '--static-decode=decode_insn')`）——**这是 `INFRA-104t` 之后的产物，属本任务门禁**。

### S4 — 版本与 target 自检

```bash
.work/build/qemu/qemu-system-dadao --version | head -1
.work/build/qemu/qemu-system-dadao -M dadao-m -bios /dev/null -display none -nographic 2>&1 | head -5
```

第一条用于记录实际构建版本；第二条验证 ROM 加载通道能启动（失败无妨，完整启动流程由 `INTEG-101t` 的 E2E 覆盖）。

## 验收

| # | 项 | 判据 | 状态 |
| --- | --- | --- | --- |
| 1 | `build-qemu` 成功 | 日志末行 `build-qemu: PASS`，exit 0 | 现在可跑 |
| 2 | 未假成功 | Makefile 的 `component-enabled` 守卫未触发 | 现在可跑 |
| 3 | 二进制就位 | `.work/build/qemu/qemu-system-dadao` 存在且可执行 | 现在可跑 |
| 4 | 机器类型注册 | `-M ?` 输出含 `dadao` 机器（M1 记录为 `dadao-m`） | 现在可跑 |
| 5 | decodetree 产物生成 | `.work/build/qemu/target/dadao/*.c.inc` 存在（`decode-insn.c.inc`） | 现在可跑 |
| 6 | decodetree 源完整 | `insn.decode` 含 256 patterns | 现在可跑 |
| 7 | configure 用了新 meson | 日志中 meson 版本 ≥ 1.5.0（证明 venv 自装机制生效，而非 apt 的 0.61.2） | 现在可跑 |
| 8 | harness 期望的路径成立 | `tests/scripts/README.md` 约定二进制在 `.work/build/qemu/qemu-system-dadao`（验收 3 已覆盖）；`tools/qemu/min_rom_probe_*.py` 用**相对路径**（如 `min_rom_probe_022t.py:25`、`005t.py:29`），故须从仓库根执行 | 现在可跑 |
| 9 | 仓库工作区零改动 | `git status --porcelain` 与执行前逐字节相同 | 现在可跑 |
| 10 | 语义正确性（747 用例） | —— | **BLOCKED**（属 `INTEG-101t`；替代证据：本任务只证二进制能构建并注册机器，**不构成任何语义证据**） |

## 风险与预案

| 风险 | 预案 |
| --- | --- |
| **`configure` 报 meson 版本不足** | 查日志确认是「apt 0.61.2 被直接使用」还是「venv 自装失败」。前者：查 `pythondeps.toml` 钉的版本并手动 `pip install`；后者：查 PyPI 连通性与 pip 版本（宿主 pip 22.0.2 偏旧，必要时用 `python3.12 -m ensurepip --upgrade`）。**任一处置都须先经用户确认**（会改宿主 Python 环境） |
| `configure` 缺 pixman/glib | 已装；若 `--disable-pixman` 可解，**须先经用户确认**（改变构建配置） |
| `make -j4` OOM | QEMU 单 target 内存压力远低于 LLVM；若仍异常，改为 `make -C .work/build/qemu -j2`（**先经用户确认**，因为偏离 `Makefile:99`） |
| 构建报错指向补丁 | **立即停止并报告**。不得手工改 `.work/source` 下的代码绕过——那会让验收跑在被污染的源码上（`AGENTS.md`「不得在污染的工作区上得出验收结论」） |

## 完成区

（待执行后填写：`build-qemu` 真实输出、meson 实际版本、耗时 + 上述 9 项逐条结论）
