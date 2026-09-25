# INFRA-102t: 宿主工具链与 Python 运行时

**模块**：infra
**项目里程碑**：M1 复现
**状态**：待开始
**日期**：2026-09-25
**依赖**：无
**决策依据**：`.xkw/knowledge/adr-1001-m1-reproduction-infra.md` D1（D1 已确认：宿主机原生构建）
**解决阻塞**：B2（缺工具链）、B3（无 `tomllib`）、B5（旧路径）、B6（meson，预置）

## 目标

在 Ubuntu 22.04 宿主上补齐构建与测试所需的全部依赖，使 `make doctor` 通过、`make PYTHON=python3.12 manifest-check` 退出 0，并使仓库内引用旧路径的脚本可运行。

**本任务不改动仓库任何文件。**

## 范围

**在范围内**：

1. apt 安装构建依赖
2. deadsnakes PPA 安装 Python 3.12（**并行解释器，不覆盖系统 `python3`**）
3. 建宿主兼容符号链接 `/mnt/tao/DADAO-v5 → /home/ubuntu/DADAO-v5`
4. 确认 `tomllib` 可用、`make doctor` PASS

**不在范围内**：修改 `Makefile`、修改任何 `tools/**/*.py`、修改 `manifests/`、安装 Docker。

## 步骤

### S1 — apt 依赖

```bash
sudo apt-get update
sudo apt-get install -y \
  build-essential cmake ninja-build clang lld gcc-12 g++-12 \
  bison flex zlib1g-dev libzstd-dev pkg-config \
  libglib2.0-dev libpixman-1-dev libfdt-dev
```

各依赖对应关系（供核对，非推测）：

| 包 | 被谁需要 |
| --- | --- |
| `build-essential` `gcc-12` `g++-12` | 宿主编译器（LLVM 23 要求 C++17 / GCC ≥ 7.4） |
| `cmake` `ninja-build` | `Makefile:81` `build-mc` 的 `cmake -G Ninja` |
| `clang` | `tools/infra/doctor.py:24-25` 的 `NATIVE` 字典**硬性要求**（缺则 doctor FAIL） |
| `lld` | `INFRA-105t` 降内存链接用（`-DLLVM_USE_LINKER=lld`） |
| `bison` `flex` | `containers/dev/Dockerfile` 同款，TableGen 辅助 |
| `zlib1g-dev` `libzstd-dev` | LLVM 链接库 |
| `libglib2.0-dev` `libpixman-1-dev` `libfdt-dev` | QEMU `configure`（`deferred.md` 已登记 `doctor.py` 不查这些） |
| `pkg-config` | QEMU 依赖探测 |

### S2 — Python 3.12（并行安装）

```bash
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt-get update
sudo apt-get install -y python3.12 python3.12-venv
```

**关键约束**：

- **不得**改动 `/usr/bin/python3` 指向（保持 3.10），以免影响宿主其它程序
- 一切调用经 `Makefile:8` 已有的 `PYTHON ?= python3` 旋钮：`make PYTHON=python3.12 …`
- **零仓库改动**——不修改 `Makefile` 的 `PYTHON` 默认值

> 备用方案（deadsnakes 不可用时）：`pip install tomli` + 在 `PYTHONPATH` 放一个 `tomllib.py` 转发模块。**不推荐**——用 stdlib 同名模块做影子劫持，后续易与真实行为混淆。选此方案须先经用户确认。

### S3 — meson 说明（**本任务不装**）

QEMU 11.1.1 要求 `meson_version: '>=1.5.0'`（`meson.build:1`），jammy apt 仅 0.61.2。**不手动安装** —— QEMU `configure` 会自建 venv 并按 `pythondeps.toml` 自动 pip 安装锁定版本（`pypi.org` 裸连实测 200）。若 `INFRA-106t` 的 `configure` 报 meson 缺失，届时再单独处理并登记。

### S4 — 旧路径兼容符号链接

仓库已从 `/mnt/tao/DADAO-v5` 移至 `/home/ubuntu/DADAO-v5`，3 个脚本硬编码旧路径：

| 文件 | 行 | 内容 |
| --- | --- | --- |
| `tools/llvm/gen_m1_asm.py` | 169 | `open('/mnt/tao/DADAO-v5/contracts/opcodes.yaml')` |
| `tools/llvm/test_m1_asm.py` | 24 | `llvm_mc = '/mnt/tao/DADAO-v5/.work/build/llvm/bin/llvm-mc'` |
| `tools/llvm/test_encoding_oracle.py` | 335 | 同上 |

```bash
sudo ln -s /home/ubuntu/DADAO-v5 /mnt/tao/DADAO-v5
```

**为何用符号链接而非改脚本**：① 与原始环境完全一致，复现结果不受路径差异干扰；② 避免在复现轮次里夹带代码改动（工作区零改动原则）。根治（改为从 `__file__` 推导）登记 `deferred.md`。

> **注意**：符号链接创建后，`test_encoding_oracle.py` 的报错会从「llvm-mc not found at /mnt/tao/...」变为「llvm-mc 尚未构建」——**后者才是本步骤成功的样子**，不要误判为失败。

## 验收

| # | 项 | 判据 | 状态 |
| --- | --- | --- | --- |
| 1 | `python3 tools/infra/doctor.py` | 输出 `doctor: PASS (native build path available)`，exit 0 | 现在可跑 |
| 2 | `make PYTHON=python3.12 manifest-check` | exit 0，无 `ModuleNotFoundError` | 现在可跑 |
| 3 | `python3.12 -c "import tomllib"` | exit 0 | 现在可跑 |
| 4 | 系统 `python3` 仍为 3.10 | `python3 -V` → `Python 3.10.x` | 现在可跑 |
| 5 | `/mnt/tao/DADAO-v5` 符号链接存在且可解析 | `ls -l /mnt/tao/DADAO-v5`；`python3 tools/llvm/test_encoding_oracle.py` 不再报「not found at /mnt/tao」 | 现在可跑 |
| 6 | 关键工具就位 | `command -v cmake ninja clang lld python3.12` 全部有输出 | 现在可跑 |
| 7 | 仓库工作区零改动 | `git status --porcelain` 与执行前**逐字节相同**（基线：仅 `M .gitignore` + `?? .opencode/` + `?? .xkw/`） | 现在可跑 |
| 8 | LLVM MC 工具可用性 | `test_encoding_oracle.py` 能找到 `llvm-mc` | **BLOCKED**（llvm-mc 属 `INFRA-105t`；替代证据：验收 5 只验证路径解析，不验证二进制存在） |

## 风险与预案

| 风险 | 预案 |
| --- | --- |
| deadsnakes PPA 不可达 | 实测 `ppa.launchpadcontent.net` 返回 200；失败则启用 S2 备用方案（须先经用户确认） |
| `clang` 与 `gcc-12` 冲突 | 二者可共存；`build-mc` 默认用 `cc`/`c++`，需要时在 `INFRA-105t` 显式指定 |
| 符号链接与 `.gitignore` 冲突 | `.gitignore` 已有 `/.work` 与 `/.cache` 两条；符号链接在仓库**外**（`/mnt/tao/`），不进版本库 |

## 完成区

（待执行后填写：真实输出 + 上述 8 项逐条结论）
