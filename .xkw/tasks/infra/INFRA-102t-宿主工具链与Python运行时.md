# INFRA-102t: 宿主工具链与 Python 运行时

**模块**：infra
**项目里程碑**：M1 复现
**状态**：已验证
**日期**：2026-09-25
**依赖**：无
**决策依据**：`.xkw/knowledge/adr-1001-m1-reproduction-infra.md` D1（D1 已确认：宿主机原生构建）
**解决阻塞**：B2（缺工具链）、B3（无 `tomllib`）、B5（旧路径）、B6（meson，预置）

## 目标

在 Ubuntu 22.04 宿主上补齐构建与测试所需的全部依赖，使 `make doctor` 通过、`make PYTHON=python3.12 manifest-check` 退出 0、Python 3.12 可导入 PyYAML，并使仓库内引用旧路径的脚本可运行。

**本任务的宿主环境操作不改动仓库任何文件。**按 `/dispatch` 流程回填本任务书的状态与完成区属于流程元数据更新，不计入宿主操作的“零仓库改动”。

## 范围

**在范围内**：

1. apt 安装构建依赖
2. deadsnakes PPA 安装 Python 3.12（**并行解释器，不覆盖系统 `python3`**）
3. 建宿主兼容符号链接 `/mnt/tao/DADAO-v5 → /home/ubuntu/DADAO-v5`
4. 确认 Python 3.12 的 `tomllib` 与 PyYAML 可用、`make doctor` PASS

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

# 下游 `make PYTHON=python3.12 check` 的 check_issues.py 等脚本需要 PyYAML。
# Jammy 的 python3-yaml 只供系统 Python 3.10 使用，因此为并行的 3.12
# 安装用户级 PyYAML 6.x，不改动系统 Python。
python3.12 -m ensurepip --user --upgrade
python3.12 -m pip install --user 'PyYAML>=6,<7'
```

**关键约束**：

- **不得**改动 `/usr/bin/python3` 指向（保持 3.10），以免影响宿主其它程序
- 一切调用经 `Makefile:8` 已有的 `PYTHON ?= python3` 旋钮：`make PYTHON=python3.12 …`
- PyYAML 只安装到当前用户的 Python 3.12 user site；不得给系统 Python 3.10 升级或卸载 `python3-yaml`
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
sudo mkdir -p /mnt/tao
if [ -e /mnt/tao/DADAO-v5 ] || [ -L /mnt/tao/DADAO-v5 ]; then
  test "$(readlink -f /mnt/tao/DADAO-v5)" = /home/ubuntu/DADAO-v5
else
  sudo ln -s /home/ubuntu/DADAO-v5 /mnt/tao/DADAO-v5
fi
```

**为何用符号链接而非改脚本**：① 与原始环境完全一致，复现结果不受路径差异干扰；② 避免在复现轮次里夹带代码改动（工作区零改动原则）。根治（改为从 `__file__` 推导）登记 `deferred.md`。

> **注意**：`test_encoding_oracle.py` 只检查完整的 `llvm-mc` 路径，不能区分“兼容符号链接缺失”和“`llvm-mc` 尚未构建”；因此本步骤只用 `readlink -f` 与经兼容路径读取仓库文件来验收。`llvm-mc` 可用性明确推迟到 `INFRA-105t`。

## 验收

| # | 项 | 判据 | 状态 |
| --- | --- | --- | --- |
| 1 | `python3 tools/infra/doctor.py` | 输出 `doctor: PASS (native build path available)`，exit 0 | 现在可跑 |
| 2 | `make PYTHON=python3.12 manifest-check` | exit 0，无 `ModuleNotFoundError` | 现在可跑 |
| 3 | Python 3.12 运行时模块 | `python3.12 -c "import tomllib, yaml; print(yaml.__version__)"` exit 0，PyYAML 主版本为 6 | 现在可跑 |
| 4 | 系统 `python3` 仍为 3.10 | `python3 -V` → `Python 3.10.x` | 现在可跑 |
| 5 | `/mnt/tao/DADAO-v5` 符号链接存在且可解析 | `readlink -f /mnt/tao/DADAO-v5` 精确输出 `/home/ubuntu/DADAO-v5`；`test -r /mnt/tao/DADAO-v5/contracts/opcodes.yaml` exit 0 | 现在可跑 |
| 6 | 关键工具就位 | `command -v cmake ninja clang lld python3.12` 全部有输出 | 现在可跑 |
| 7 | 宿主操作未污染仓库 | engineer 开始时保存真实 `git status --porcelain=v1`；宿主安装与符号链接完成后、回填任务书前须与其**逐字节相同**。最终只允许本任务书因状态与完成区回填而新增修改，原有用户改动须原样保留 | 现在可跑 |
| 8 | LLVM MC 工具可用性 | `test_encoding_oracle.py` 能找到 `llvm-mc` | **BLOCKED**（llvm-mc 属 `INFRA-105t`；替代证据：验收 5 只验证旧路径能精确解析到仓库并读取已存在文件，不验证二进制存在） |

## 风险与预案

| 风险 | 预案 |
| --- | --- |
| deadsnakes PPA 不可达 | 实测 `ppa.launchpadcontent.net` 返回 200；失败则启用 S2 备用方案（须先经用户确认） |
| Python 3.12 的 ensurepip / PyYAML 用户级安装失败 | 立即停止并报告真实错误；不得改用影子 `tomllib.py`、不得污染系统 Python 3.10，替代安装方式须先经用户确认 |
| `clang` 与 `gcc-12` 冲突 | 二者可共存；`build-mc` 默认用 `cc`/`c++`，需要时在 `INFRA-105t` 显式指定 |
| 符号链接与 `.gitignore` 冲突 | `.gitignore` 已有 `/.work` 与 `/.cache` 两条；符号链接在仓库**外**（`/mnt/tao/`），不进版本库 |

## 完成区

执行日期 2026-09-25，宿主 Ubuntu 22.04.5 LTS (jammy) x86_64，5.15.0-135-generic。
**未改任何仓库源码文件**：S1/S2/S4 全部是宿主侧操作，唯一的仓库改动是本节与状态字段的回填。

### 日志（`.work/log/infra/`，`.work` 是指向 `/mnt/dadao-v5/.work` 的符号链接，在仓库外）

| 日志 | 内容 | 命令退出码 |
| --- | --- | --- |
| `INFRA-102t-apt-update.log` | `sudo apt-get update` | 0 |
| `INFRA-102t-apt-install.log` | S1 的 15 个包 | 0 |
| `INFRA-102t-ppa-add.log` | `add-apt-repository -y ppa:deadsnakes/ppa` | 0 |
| `INFRA-102t-python312-apt.log` | `apt-get install python3.12 python3.12-venv` | 0 |
| `INFRA-102t-ensurepip.log` | `python3.12 -m ensurepip --user --upgrade` | 0 |
| `INFRA-102t-pyyaml-pip.log` | `python3.12 -m pip install --user 'PyYAML>=6,<7'` | 0 |
| `INFRA-102t-symlink.log` | S4 建链 | 0 |
| `INFRA-102t-accept-all.log` | 验收 #1–#8 脚本（回填前） | 0（7/7 通过） |
| `INFRA-102t-accept-all-final.log` | 回填后重跑同一脚本（确认回填未破坏任何项、#7 仍逐字节一致） | 0（7/7 通过） |
| `INFRA-102t-independent-audit.log` | 独立复核（dpkg/stat/dpkg-query/git diff 等；A4 命令有 `NameError`，由下一份日志修正） | 0（该 shell 块未 fail-fast，不把此退出码单独作为通过证据） |
| `INFRA-102t-pyyaml-provenance.log` | PyYAML 来源与 user-site 隔离复核 | 0 |
| `INFRA-102t-git-status-gate-prebackfill.log` | 回填前的 #7 闸门 | 0 |
| `INFRA-102t-git-status-final.log` | 回填后的最终 #7 复核（基线 vs 最终） | 0 |
| `INFRA-102t-acceptance-counterexample.log` | 验证脚本反例注入（应 FAIL 证明） | 6（预期非 0） |

### 8 项验收逐条结论

**#1 `python3 tools/infra/doctor.py` — PASS。** exit 0，输出逐字为 `doctor: PASS (native build path available)`。
`required` 全 OK（git 2.34.1 / GNU Make 4.3 / cmake 3.22.1 / Python 3.10.12），`native` 全 OK（ninja 1.10.1 / Ubuntu clang 14.0.0-1ubuntu1.1），`docker MISSING`（本任务不装，且 native 路径已可用故不影响判定）。

**#2 `make PYTHON=python3.12 manifest-check` — PASS。** exit 0，输出
`enabled components: llvm-project, qemu` / `references: 2` / `manifest validation: PASS`，无 `ModuleNotFoundError`。
补充：经兼容路径 cwd（`cd /mnt/tao/DADAO-v5 && make PYTHON=python3.12 manifest-check`）同样 exit 0。

**#3 Python 3.12 运行时模块 — PASS。** `python3.12 -c "import tomllib, yaml; print(yaml.__version__)"` exit 0，stdout `6.0.3`，主版本 6。
`yaml` 来自 `/home/ubuntu/.local/lib/python3.12/site-packages/yaml/__init__.py`（用户级），`tomllib` 来自 `/usr/lib/python3.12/tomllib/__init__.py`（stdlib）。

**#4 系统 `python3` 仍为 3.10 — PASS。** `python3 -V` → `Python 3.10.12`（匹配 `^Python 3\.10\.[0-9]+$`）；
`/usr/bin/python3 -> python3.10`，`readlink -f` = `/usr/bin/python3.10`；该符号链接 mtime 仍是 2024-08-08 12:28:21（未被触碰）。
`update-alternatives --list python3` 报 `no alternatives for python3`，即 3.12 是**并行**解释器而非接管。系统 `python3-yaml` 仍为 `5.4.1-1ubuntu1`（`install ok installed`）。

**#5 `/mnt/tao/DADAO-v5` 符号链接 — PASS。** `readlink` / `readlink -f` / `realpath` / `os.path.realpath` 四种写法一致得到 `/home/ubuntu/DADAO-v5`；
`test -r /mnt/tao/DADAO-v5/contracts/opcodes.yaml` exit 0；`cmp` 兼容路径与真实路径的 `opcodes.yaml` exit 0（123361 字节相同）；
按 `tools/llvm/gen_m1_asm.py:169` 的写法 `open('/mnt/tao/DADAO-v5/contracts/opcodes.yaml')` 实读 120675 字符、exit 0。
**未使用尚未构建的 `llvm-mc`**：`.work/build/llvm/bin/llvm-mc` 不存在（`INFRA-105t` 负责）。
任务书 S4 表中 3 处硬编码路径已逐条核对属实：`tools/llvm/gen_m1_asm.py:169`、`tools/llvm/test_m1_asm.py:24`、`tools/llvm/test_encoding_oracle.py:335`。

**#6 关键工具就位 — PASS。** `command -v` 全部有输出：
`cmake=/usr/bin/cmake`(3.22.1)、`ninja=/usr/bin/ninja`(1.10.1)、`clang=/usr/bin/clang`(Ubuntu clang version 14.0.0-1ubuntu1.1)、`lld=/usr/bin/lld`（`lld --version` 首行是通用横幅 `lld is a generic driver.`，实际版本取自 `dpkg-query`：`lld 1:14.0-55~exp2`）、`python3.12=/usr/bin/python3.12`(3.12.14)。
S1 其余包 `dpkg-query` 全为 `install ok installed`：`build-essential 12.9ubuntu3`、`gcc-12/g++-12 12.3.0-1ubuntu1~22.04.3`、`bison 2:3.8.2+dfsg-1ubuntu0.22.04.1`、`flex 2.6.4-8build2`、`zlib1g-dev 1:1.2.11.dfsg-2ubuntu9.2`、`libzstd-dev 1.4.8+dfsg-3build1`、`pkg-config 0.29.2-1ubuntu3`、`libglib2.0-dev 2.72.4-0ubuntu2.10`、`libpixman-1-dev 0.40.0-1ubuntu0.22.04.1`、`libfdt-dev 1.6.1-1`、`python3.12/python3.12-venv 3.12.14-1+jammy1`。
**未装 meson / Docker**（S3 与范围约束）：`dpkg-query` 三个包名均 `no packages found`，`command -v meson docker` 无输出。

**#7 宿主操作未污染仓库 — PASS。** 动态基线在开工第一步取得（宿主安装之前），
`git status --porcelain=v1 --untracked-files=all` = 307 字节 / md5 `6cc420d28b601c087297b5c0ec07db15`。
宿主安装与建链完成后、**回填本任务书之前**复测：`cmp` exit 0，md5 仍为 `6cc420d28b601c087297b5c0ec07db15`，`od -c` 尾部字节一致。
越界目录逐一核对为 0 差异：`Makefile`、`manifests/`、`tools/`、`.tao/` 对 HEAD 的 `git diff --name-only` 均为空行数。
最终 `git status` 与基线**逐字节相同**（`diff` exit 0）：因本任务书在基线时已因主会话预检修订而是 ` M`，回填后条目集合不变
（`sort` 后 `diff` 亦 exit 0）。回填只改内容、不新增也不删除任何 `git status` 条目：`git diff --numstat` 显示**本任务只改动本任务书这一个文件**
（`git diff --stat` 另两行 `MEMORY.md 6 +-` 与 `workflow.md 13 +++` 是主会话/用户的既有改动，本任务未触碰；
逐文件精确行数见 `INFRA-102t-git-status-final.log` 末段 AUTHORITATIVE 一节，该节在本文件定稿后生成）。
`.xkw/knowledge/MEMORY.md`、`.xkw/knowledge/workflow.md`、`.opencode/commands/*` 三类既有用户改动原样保留，未被覆盖或还原（见 `INFRA-102t-git-status-final.log`）。

**#8 LLVM MC 工具可用性 — BLOCKED（维持不变，未按 PASS 记账）。**
`.work/build/llvm/bin/llvm-mc` 不存在，`llvm-mc` 属 `INFRA-105t` 的构建产物，本任务无法验证也未尝试构建。
替代证据即验收 #5：只用 `readlink` 系列与经兼容路径读取**已存在**的仓库文件（`opcodes.yaml` 逐字节比对通过），
不依赖 `llvm-mc` 二进制存在，故 #5 的 PASS 不构成对 #8 的冒充。

### 验证脚本反例门控（证明验收脚本会失败）

`/tmp/opencode/INFRA-102t/accept.sh` 注入 6 处错误期望（doctor 期望串、PyYAML 主版本、`Python 3.10.x` 正则、`/usr/bin/python3.10` 目标、符号链接目标、基线文件换成伪造脏基线）后重跑：
输出 `[FAIL] #1`、`[FAIL] #3`、`[FAIL] #4`×2、`[FAIL] #5`、`[FAIL] #7` 共 **6 条**，脚本退出码 **6**（非 0）。
即每条断言都有可达 FAIL 路径，不存在恒真断言。注入有效性由 `diff -u accept.sh accept-neg.sh` 确认非空；
负例脚本只写 `/tmp/opencode/INFRA-102t/now-git-status-neg.txt`，未触碰真实基线文件与仓库。

### 需要如实说明的一点（非缺陷，供 /complete 参考）

deadsnakes 的 jammy `python3.12` 把 `/usr/lib/python3/dist-packages` 纳入 `sys.path`，因此
`PYTHONNOUSERSITE=1 python3.12 -c "import yaml"` 会回落到发行版的 5.4.1；正常环境下 user-site 6.0.3 排在前面故生效（实测 exit 0、6.0.3）。
这**不影响**本任务任何验收项：用户级安装确实只落在 `/home/ubuntu/.local/lib/python3.12/site-packages`，
`/usr/lib/python3.12*` 下未新增任何 `yaml` 目录（`find -newermt` 结果为空），系统 3.10 的 `python3-yaml 5.4.1-1ubuntu1` 未升级也未卸载。

### 遗留项

无能力缺口。S2 备用方案（`tomli` + 影子 `tomllib.py`）未启用；S3 的 meson 按任务书留待 `INFRA-106t` 的 `configure` 判定。
`deferred.md` 未改动（符号链接根治、meson 判定均按任务书交由后续任务，本任务不写）。

## 审阅记录（/complete，2026-09-25）

- **reviewer：Accepted。** 独立复跑验收 #1–#7 全部通过；#8 按用户确认保持 BLOCKED，由 `INFRA-105t` 负责，替代证据有效且未冒充 PASS。
- **主动证伪：通过。** reviewer 在 `/tmp/opencode/INFRA-102t/reviewer/synthetic` 的合成 git 树中亲自注入反例：
  - `doctor.py` 注入缺失工具：`git diff --name-only` 非空，输出 `doctor: FAIL; missing required tools: reviewer_missing_tool`，exit 1；
  - `manifest_check.py` 注入非法 commit：diff 非空，输出 `enabled components require a full commit`，exit 1；
  - `accept.sh` 注入 7 项错误期望：diff 非空，输出 `7 CHECK(S) FAILED`，exit 7。
- 三轮注入还原后，临时树 `git status --porcelain` 均为空；本任务无生成物，重建要求 N/A。真实仓库状态与 engineer 基线 md5 `6cc420d28b601c087297b5c0ec07db15` 一致，禁止范围零差异。
- reviewer 当场修正完成区的软件包版本，并披露 `INFRA-102t-independent-audit.log` 的 A4 曾出现 `NameError` 且 shell 未 fail-fast；该日志退出码不再单独作为证据，PyYAML provenance 由独立 reviewer 检查承担。
- **architect：Accepted。** 交叉核对 reviewer 日志、反例非空注入/失败/还原、软件包版本与 provenance 后支持收尾。
- reviewer 日志：`.work/log/infra/INFRA-102t-review-{accept,engineer-accept,counterexamples,provenance,final-state}.log`。
- 本任务不含 ISA 数据或 ROM 探针，size/sign 全量重算、独立 ISA oracle、探针分支双向验证均 N/A；未产生新的 ADR 判据。
