# INFRA-106t: QEMU 构建

**模块**：infra
**项目里程碑**：M1 复现
**状态**：已验证
**日期**：2026-09-25
**依赖**：`INFRA-102t`（宿主工具链）、`INFRA-103t`（镜像）、`INFRA-104t`（QEMU 源码 + 8 补丁）
**决策依据**：`.xkw/knowledge/adr-1001-m1-reproduction-infra.md` D1
**建议**：与 `INFRA-105t` **串行**（宿主 4 核 / 3 GiB，并行会加剧内存压力）

## 目标

构建 `qemu-system-dadao`，使 M1 的 QEMU 侧验收（语义 harness 747 用例、E2E 冒烟）具备运行条件。

**本任务不改动仓库任何文件**（`.work/build/` 被 `.gitignore` 忽略）。

## 背景：venv 自建链是本任务的主要不确定项（原「meson 版本」判断已被下发前预检修正，见下方修正记录 B6）

浅克隆读取 `qemu v11.1.1` 的 `meson.build:1` 实测：

```meson
project('qemu', ['c'], meson_version: '>=1.5.0',
```

**下发前预检实测更正**：

- 宿主 **meson 未安装**（`meson --version` → 未安装）；原「apt 仅有 0.61.2」的前提已过时。
- `pythondeps.toml:22` 钉 `meson = { accepted = ">=1.5.0", installed = "1.11.1" }`，且 `meson-1.11.1-py3-none-any.whl` **已随源码 vendor 在 `python/wheels/`** ⇒ **取 meson 不依赖 PyPI**，原「版本差两个大版本 ⇒ 依赖 pip 下载」的风险不成立。
- 因此真正的不确定项是 **venv 能否建起来**：`configure:940` 走 `mkvenv.py create pyvenv`。
- **构建用哪个 Python 是决定性因素（第 1 轮已实证）**：`Makefile:8` 默认 `python3` = 3.10.12 可用；`python3.12` **不可用**（`setuptools` 不可导入，详见完成区第 1 轮归因）。**不要加 `PYTHON=` 覆盖。**
- **`ensurepip` 不是障碍**（更正原判断）：`mkvenv.py:959` 恒传 `system_site_packages=True`（venv 非隔离），`need_ensurepip()` 用 **`find_spec`** 判定（不执行模块），在 3.10 与 3.12 上**均为 `False`** ⇒ `check_ensurepip()` 不会被调用 ⇒ 3.10 缺 `ensurepip` 在此**不构成**必须用 3.12 的理由。
- **`[tooling]` 组**：`wheel`(0.37.1) 与 `pip`(25.0.1) 在 3.10 上满足。**`setuptools` 必须验证「可导入」而非只看版本元数据**——`59.6.0` 是 3.10 包，在 3.12 上 `find_spec` 找得到但 `import` 失败（`mkvenv.py:343-353` 因此误判为「已满足」而放弃补装）。

**本任务不手动安装 meson**，仍依赖 QEMU `configure` 自建 venv。

### 根因（本任务真正的拦路虎，2 轮执行实测确认，非推测）

**`Makefile:8` 用单一 `PYTHON ?= python3` 同时服务两类互斥需求**：

| 消费方 | 位置 | 需要 | 宿主满足情况 |
| --- | --- | --- | --- |
| 仓库工具链 | `Makefile:30` `component-enabled`、`Makefile:55` `manifest_check.py`（`tools/infra/*.py` 另有 6 处 `import tomllib`） | `tomllib` ⇒ **Python ≥ 3.11** | 3.10 ❌ / 3.12 ✅ |
| QEMU 构建 | `configure` → `mkvenv.py` → `pip install -e python/`（PEP 517） | `setuptools.build_meta` ⇒ 本宿主只有 **3.10** 的 59.6.0 可用 | 3.10 ✅ / 3.12 ❌ |

`python3.12` 侧失败的完整链条（逐环实测）：`sys.path` 含**跨版本共享**的 `/usr/lib/python3/dist-packages` ⇒ 其中 `python3-setuptools 59.6.0-1.2ubuntu0.22.04.3` 是**为 3.10 构建**、`__init__.py:10` `import distutils.core`，而 `distutils` 在 3.12 已被移除 ⇒ `import setuptools.build_meta` 失败 ⇒ `BackendUnavailable` ⇒ `build-qemu_rc=2`。且 `mkvenv.py:343-353` 的 `need_ensurepip()` 用 **`find_spec`（不执行模块）**判定「已满足」而放弃补装，`pythondeps.toml` 的 `"setuptools" = { accepted = ">=44.1.1" }` 又**无 `installed` 键**、`python/wheels/` 也**无 setuptools wheel** ⇒ 无可修之物。

**两侧在宿主上互斥，且绕不过去**：绕过 `manifest-check` 也不行 —— `Makefile:30` 的 `component-enabled` 同样 `import tomllib`，在 3.10 上 rc=1 ⇒ 会打印 `refusing to fake success` + `exit 1`，**验收 #2 反而翻成 FAIL**（第 2 轮已实测）。

**处置（用户 2026-09-26 选定「方案 C」）**：给 3.10 **补上 `tomllib`**（`tomli` + 同名 shim），而不是换 Python。理由：3.10 侧 `setuptools` 已实测可用无需任何 pip 动作；补完后 `Makefile:8` 的默认值**无需修改**，裸 `make build-qemu` 即可用；零仓库改动、零 root。见 **S0**。

> **这是绕过，不是消除**：`Makefile` 的设计缺陷（单一 `$(PYTHON)` 服务互斥需求）仍在，已登记 `.xkw/knowledge/deferred.md`。正解是让 `Makefile` 为工具链与 QEMU 构建分别选择解释器。

其它版本要求**已核对达标**（`INFRA-101k` 勘察表 + 下发前预检实测）：glib 2.72.4 ≥ 2.66 ✓、pixman 0.40.0 ≥ 0.21.8 ✓（且 `pixman` 在 `meson.build:1155` 是 `auto()`，必要时可 `--disable-pixman`）。

## 范围

**在范围内**：`make build-qemu`、机器类型清点、decodetree 产物校验、冒烟、**S0 的 `install_tomllib_shim.py`（改宿主 `~/.local` user site-packages —— 用户 2026-09-26 明确批准，方案 C）**。

**不在范围内**：修改 `Makefile`、修改 `configure` 参数、gem5、`INTEG-101t` 的 harness 执行。

## 步骤

### S0 — 宿主 `tomllib` 补齐（**第 3 轮新增的必做前置**，幂等、秒级）

第 1、2 轮均因宿主 Python 两侧互斥而失败（详见完成区第 1、2 轮）。本步补齐后，**裸 `make build-qemu`（不需任何 `PYTHON=` 覆盖）即可工作**：

```bash
cd /home/ubuntu/DADAO-v5
python3 tools/infra/install_tomllib_shim.py
echo "S0 install_tomllib_shim 真实退出码 = $?"
```

脚本做的事（细节见该文件 docstring）：把 `tomli` 装进 `~/.local/lib/python3.10/site-packages/`，并写一个 184 字节的 `tomllib.py` shim 转发到 `tomli`。**幂等**，已装则不重复动作；失败即非 0 退出。

**只验证不改动**：

```bash
python3 tools/infra/install_tomllib_shim.py --check
```

> 脚本的 7 项自验证与 **5 条已实测的反例**记录见下方「`install_tomllib_shim.py` 的可失败性已实测」。**该脚本会改宿主 `~/.local`（user site-packages）**，已由用户于 2026-09-26 明确批准（方案 C）。

### S1 — 构建

```bash
cd /home/ubuntu/DADAO-v5
mkdir -p .work/log/infra
( set -o pipefail
  { make build-qemu; } 2>&1 | tee .work/log/infra/INFRA-106t-build-qemu.log
  rc=${PIPESTATUS[0]}
  echo "build-qemu_rc=$rc" | tee -a .work/log/infra/INFRA-106t-build-qemu.log
  exit $rc )
build_qemu_rc=$?
echo "S1 build-qemu 真实退出码 = $build_qemu_rc"
```

> **不得写成裸 `make … | tee log`**：那样 `$?` 是 `tee` 的退出码，**构建失败也会是 0**，`exit 0` 判据恒真（同 `INFRA-105t` B3）。验收 #1 必须以本块落盘的 `build-qemu_rc=` 为准。
>
> **不得加 `PYTHON=` 覆盖**（第 1 轮曾用 `PYTHON=python3.12`，**已实证失败** `build-qemu_rc=2`，见完成区第 1 轮）：宿主 `python3.12` 的 `sys.path` 含**跨版本共享**的 `/usr/lib/python3/dist-packages`，其中 `python3-setuptools 59.6.0-1.2ubuntu0.22.04.3` 为 3.10 构建、`__init__.py:10` 依赖已被 3.12 移除的 `distutils` ⇒ 不可导入 ⇒ PEP 517 后端 `setuptools.build_meta` 不可用 ⇒ `BackendUnavailable` ⇒ 构建失败。
> **必须用 `Makefile:8` 的默认 `PYTHON ?= python3`**（= 3.10.12）：该版本下 `import setuptools.build_meta` **实测可用**（59.6.0 + `distutils` 在位），且 `mkvenv.py:959` 恒传 `system_site_packages=True`（venv **非隔离**）⇒ `need_ensurepip()` 在 3.10 上同样为 `False`（`find_spec` 找到 setuptools 与 pip）⇒ `check_ensurepip()` 不会被调用 ⇒ **3.10 缺 `ensurepip` 在此不构成障碍**。已用与真实 venv 完全相同的参数（`python3 -m venv --without-pip --system-site-packages`）建探针实证，并用同参数在 3.12 上**精确复现**原报错。

`Makefile:95-98` 的 configure 参数：`--target-list=dadao-softmmu --enable-tcg --disable-werror`；`Makefile:99` 随后 `make -j$(nproc)`。

**耗时预估 15–30 min**（4 核）。QEMU 只构建单一 target，比 LLVM 轻得多。

### S2 — 机器类型清点

```bash
.work/build/qemu/qemu-system-dadao -M ? 2>&1 | grep -i dadao
```

期望出现（**下发前预检已由源码级证据更正**，原记录的 `dadao-m` 是陈旧值）：

```
dadao-m1    DADAO M1 bare-metal test machine
```

> 依据：`hw/dadao/dadao-machine.c:123` 注册 `MACHINE_TYPE_NAME("dadao-m1")`；调用侧 `tools/qemu/smoke-dadao-m1.sh:26` 断言 `dadao-m1`、`:47` 使用 `-machine dadao-m1`。故**本任务一切命令行一律用 `dadao-m1`**。
> 若实际输出与 `dadao-m1` **不符**，属实现与探针的不一致，**须立即停止并如实记录**，不得改测试基线去迁就。

### S3 — decodetree 产物校验

```bash
# 判据已由第 3 轮执行后修正（B19/B20）：decodetree 的 .c.inc **不落在 target/dadao/**，
# 而在消费方静态库的 meson 私有目录。权威依据 = build.ninja 的 CUSTOM_COMMAND 规则。
# 注意：build.ninja 里的路径是【相对构建根】的，必须补 .work/build/qemu/ 前缀（B20）。
BJ=.work/build/qemu/build.ninja
REL=$(grep -o '[^ ]*decode-insn\.c\.inc[^ ]*: CUSTOM_COMMAND' "$BJ" | head -1); REL=${REL%: CUSTOM_COMMAND}
echo "build.ninja 记录的 decodetree 产物（相对构建根）= ${REL:-<无此规则>}"
ART=".work/build/qemu/${REL}"
test -s "$ART"; echo "产物存在且非空 rc=$? size=$(stat -c%s "$ART" 2>/dev/null)B"
test "$(grep -c 'trans_' "$ART" 2>/dev/null)" -ge 256; echo "trans_ 符号 >=256 rc=$?"
python3.12 -B tools/qemu/validate_decodetree.py \
  .work/source/qemu/target/dadao/insn.decode contracts/opcodes.yaml
echo "validate_decodetree 真实退出码 = $?"
```

> **判据已由下发前预检修正（B1）**：原命令 `grep -c . insn.decode` 实测 **270** ≠ 期望 256（非空行数 ≠ decode pattern 数），会让**完全正确的构建 FAIL 验收 #6**。改用 `INFRA-104t` 已确立的权威 checker `tools/qemu/validate_decodetree.py`（同一份 `contracts/opcodes.yaml`），其口径为 `YAML 记录数: 256 / decode pattern 数: 256 / 错误数: 0 / validate_decodetree: PASS`，且**有可达的 FAIL 路径**（改 `insn.decode` 一行或 `opcodes.yaml` 一条即报错非 0 退出）。
> 参考：等价的粗略计数是 `grep -cE '^[a-z]' insn.decode` = 256，但**不得**用它替代 checker（它不校验编码一致性）。

`decode-insn.c.inc` 由 meson 放在**消费方静态库 `libqemu-dadao-softmmu.a` 的私有目录** `.work/build/qemu/libqemu-dadao-softmmu.a.p/`，**不在** `.work/build/qemu/target/dadao/`（第 3 轮实测：`.work/build/qemu/target/` 整棵树 0 文件；产物 84585 B、含 512 个 `trans_` 符号，路径由 `build.ninja` 的 `CUSTOM_COMMAND` 规则权威确认）——见修正记录 **B19**。生成它的调用是 `meson.build:4` `decodetree.process('insn.decode', extra_args: '--static-decode=decode_insn')`——**这是 `INFRA-104t` 之后的产物，属本任务门禁**。

### S4 — 版本与 target 自检

```bash
.work/build/qemu/qemu-system-dadao --version | head -1
# ROM 加载通道：dadao-machine.c:134-142 要求 -bios 与 -kernel **两者都提供**，缺一即 error_report + exit(1)。
# 因此先造两个 8 字节零文件（同 tools/qemu/smoke-dadao-m1.sh:34 的做法），再从仓库根执行：
mkdir -p /tmp/opencode/INFRA-106t/s4
head -c 8 /dev/zero > /tmp/opencode/INFRA-106t/s4/rom.bin
head -c 8 /dev/zero > /tmp/opencode/INFRA-106t/s4/test.bin
( set -o pipefail
  .work/build/qemu/qemu-system-dadao -M dadao-m1 \
    -bios /tmp/opencode/INFRA-106t/s4/rom.bin \
    -kernel /tmp/opencode/INFRA-106t/s4/test.bin \
    -display none -nographic 2>&1 | head -20 )
echo "S4 退出码 = ${PIPESTATUS[0]}"
```

第一条用于记录实际构建版本；第二条**只验证 `-bios`/`-kernel` 参数校验通道能通过并进入 ROM 加载路径**。

> **已由下发前预检修正（B2/B4）**：原命令 `-M dadao-m -bios /dev/null`（a）机器名错，源码实为 `dadao-m1`；（b）**漏 `-kernel`**，而 `dadao-machine.c:140` 明确 `dadao-m1: -kernel test.bin is required` + `exit(1)` ⇒ 原命令必然停在参数校验，**达不到「验证 ROM 加载通道」的原意**。
> 零内容 ROM 的执行结果**不在本任务判据内**（属 `INTEG-101t` E2E）：本任务只要求「不出现 `is required` 参数错误」，即证明 `-M dadao-m1` 被接受且进入加载路径。

## 验收

| # | 项 | 判据 | 状态 |
| --- | --- | --- | --- |
| 1 | `build-qemu` 成功 | 日志末行含 `build-qemu: PASS`，**且** S1 落盘的 `build-qemu_rc=0`（真实 make 退出码，非 `tee` 的） | 现在可跑 |
| 2 | 未假成功 | Makefile 的 `component-enabled` 守卫未触发（日志中无 `refusing to fake success`） | 现在可跑 |
| 3 | 二进制就位 | `.work/build/qemu/qemu-system-dadao` 存在且可执行 | 现在可跑 |
| 4 | 机器类型注册 | `-M ?` 输出含 `dadao-m1`（源码 `dadao-machine.c:123` + `tools/qemu/smoke-dadao-m1.sh:26` 双重证据；**原记录的 `dadao-m` 已更正为陈旧值**） | 现在可跑 |
| 5 | decodetree 产物生成 | `build.ninja` 的 `CUSTOM_COMMAND` 规则记录 `decode-insn.c.inc` 的落盘路径；该文件存在、**非空**、且含 `trans_` 符号。**第 3 轮实测真实路径 = `.work/build/qemu/libqemu-dadao-softmmu.a.p/decode-insn.c.inc`（meson 私有目录），原写的 `target/dadao/` 恒为空 —— 已按 B19 更正** | 现在可跑 |
| 6 | decodetree 源完整 | `python3.12 -B tools/qemu/validate_decodetree.py .work/source/qemu/target/dadao/insn.decode contracts/opcodes.yaml` 退出码 0 且输出恰 1 行 `validate_decodetree: PASS`（**权威口径，`INFRA-104t` 同一 checker**；原 `grep -c . = 256` 判据实测 270，已废弃） | 现在可跑 |
| 7 | configure 用了锁定版 meson | `.work/build/qemu/pyvenv/bin/meson --version` 输出 `1.11.1`（`pythondeps.toml:22` 的 `installed` 值），证明 venv 自装链生效。**注**：venv 将是 3.10 基（`meson-1.11.1` wheel `Requires-Python: >=3.7` ⇒ 兼容）；**原判据「日志中 meson 版本 ≥ 1.5.0」不可执行**（`configure:1168` 只赋 shell 变量、不打印） | 现在可跑 |
| 8 | harness 期望的路径成立 | `tests/scripts/README.md` 约定二进制在 `.work/build/qemu/qemu-system-dadao`（验收 3 已覆盖）；`tools/qemu/min_rom_probe_*.py` 用**相对路径**（实测 `min_rom_probe_022t.py:25`、`005t.py:29` 均为 `.work/build/qemu/qemu-system-dadao`），故须从仓库根执行 | 现在可跑 |
| 9 | 仓库工作区零改动 | `git status --porcelain=v1 -uall` 与执行前**逐字节**相同。**本轮（第 3 轮）基线 = 23 路径**，快照存 `/tmp/opencode/INFRA-106t/dispatch/git-status.round3`，其 sha256 与逐路径内容 sha256 存于同目录 `task-book-fingerprint.round3`。**唯一允许的差异**是任务书「完成区」被填写。原始基线（21 路径）另存 `git-status.before` / `dirty-content-sha256.before`，用于核对**原有 21 路径内容 0 变化** | 现在可跑 |
| 10 | 语义正确性（747 用例） | —— | **BLOCKED**（属 `INTEG-101t`；替代证据：本任务只证二进制能构建并注册机器，**不构成任何语义证据**） |

## 风险与预案

| 风险 | 预案 |
| --- | --- |
| **`configure` 报 meson 版本不足 / venv 建不起来** | **先看日志区分两类**：(a) 误用了系统 meson（宿主实测**未安装** meson，故只可能是 venv 自装失败）；(b) venv/pip 侧失败。处置顺序：查 `.work/build/qemu/pyvenv/` 是否生成 → 查 `pyvenv/bin/python --version` **是否为 3.10**（若是 3.12 则 `setuptools` 不可导入，见完成区第 1 轮归因）→ 查 `python/wheels/meson-1.11.1-py3-none-any.whl` 是否在位（**meson 已 vendor，通常不需联网**）。**任何 `pip install` / 改宿主 Python 环境的处置都须先经用户确认**。**禁止**加 `PYTHON=` 覆盖、改 `pythondeps.toml` 或手工塞 meson 到 PATH（会污染 venv 语义，使验收 #7 失效） |
| `configure` 缺 pixman/glib | 下发前预检实测已齐备（glib 2.72.4、pixman 0.40.0，`pkg-config` 可查）；若仍缺，若 `--disable-pixman` 可解，**须先经用户确认**（改变构建配置） |
| `make -j4` OOM | QEMU 单 target 内存压力远低于 LLVM（105t 曾把 `MemAvailable` 压到 45 MiB）；若仍异常，改为 `make -C .work/build/qemu -j2`（路径经核实正确：`Makefile:13` `QEMU_BUILD ?= .work/build/qemu`；**先经用户确认**，因为偏离 `Makefile:99`） |
| 构建报错指向补丁 | **立即停止并报告**。不得手工改 `.work/source` 下的代码绕过——那会让验收跑在被污染的源码上（`AGENTS.md`「不得在污染的工作区上得出验收结论」） |

## 下发前预检修正记录（2026-09-26，主会话 `/dispatch` 四项预检）

四项预检结论：①内部一致性**不通过**（3 个 BLOCKER）；②依赖链**通过**（能力实测齐备，依赖字段不全已补）；③验收可执行性 **6 项现在可跑 / 3 项判据有缺陷（#1/#6/#7，均已修）/ 1 项 BLOCKED（#10）**；④与 spec/vectors 一致**通过**。
取证存档：`/tmp/opencode/INFRA-106t/dispatch/precheck-evidence.txt`；dirty 基线：`…/dispatch/git-status.before`、`…/dispatch/dirty-content-sha256.before`。

| # | 级别 | 位置 | 缺陷 | 处置 |
| --- | --- | --- | --- | --- |
| B1 | BLOCKER | S3、验收 #6 | `grep -c . insn.decode` 实测 **270** ≠ 期望 256 ⇒ 正确构建必然 FAIL | 已改用 `validate_decodetree.py` 权威口径（rc=0 + 恰 1 行 PASS） |
| B2 | BLOCKER | S2、S4、验收 #4 | 机器名 `dadao-m` 与源码不符（实为 `dadao-m1`）⇒ S4 命令必然失败 | S2 期望块 / S4 命令 / 验收 #4 均改为 `dadao-m1`，附源码与 smoke 脚本双重证据 |
| B3 | BLOCKER | S1、验收 #1 | 裸 `\| tee` 使 `$?` 为 `tee` 退出码 ⇒ `exit 0` 判据恒真 | S1 改为 `( set -o pipefail; … PIPESTATUS[0] )` 并落盘 `build-qemu_rc=`；验收 #1 明确以该值为准 |
| B4 | 需修正 | S4 | 漏 `-kernel`，而 `dadao-machine.c:140` 两者皆必需 ⇒ 必然停在参数校验 | 补 `-kernel`，用两个 8 字节零文件（同 `smoke-dadao-m1.sh:34`） |
| B5 | 需修正 | 验收 #7 | 判据不可执行：`configure:1168` 只赋 shell 变量不打印；「apt 0.61.2」前提过时 | 改判 `.work/build/qemu/pyvenv/bin/meson --version` = `1.11.1` |
| B6 | 需修正 | 背景段 | 「主要不确定项 = meson 版本」判断过时：wheel 已 vendor，不依赖 PyPI | 背景段重写为「venv 自建链」。**其中两处结论在第 1 轮执行中被证伪，见 B11/B12** |
| B7 | 需修正 | 风险表 | 「宿主 pip 22.0.2 偏旧」失实（`python3.12 -m pip` = 25.0.1） | 风险表重写，去掉 apt/pip 假设，加「禁止改 `pythondeps.toml`」 |
| B8 | 需修正 | 完成区 | 写「9 项」实为 10 项 | 已改为 10 项 |
| B9 | 需修正 | 依赖 | 只写 `INFRA-104t` | 补 `INFRA-102t`（glib/pixman 实测齐备）、`INFRA-103t`（镜像） |
| B10 | 登记不改 | `INTEG-101t:114` | 下游任务书同样带陈旧 `dadao-m` | **本次不改**（越出本任务书范围），登记待 `INTEG-101t` 规划时处置 |

### 第 1 轮执行后新增的修正（B11–B14，主会话复核 engineer 报告后当场修）

第 1 轮 engineer 执行 S1 得 `build-qemu_rc=2`（6 秒失败，`meson`/`ninja` 从未启动）。**不是** OOM（`oom_kill=0`）、**不是**补丁问题。主会话独立复核（未采信子代理报告）后确认根因，并**承认预检阶段的两处结论是错的**：

| # | 级别 | 位置 | 缺陷 | 处置 |
| --- | --- | --- | --- | --- |
| B11 | **BLOCKER（预检误判）** | 背景段第 3 条 | 我写「系统 `python3`（3.10）**无** `ensurepip` ⇒ `PYTHON=python3.12` 是**硬前提**」——**错**。`mkvenv.py:959` 恒传 `system_site_packages=True`（venv 非隔离），`need_ensurepip()` 用 **`find_spec`**（不执行模块）判定，3.10 上 `find_spec(setuptools)=True, find_spec(pip)=True` ⇒ `need_ensurepip=False` ⇒ `check_ensurepip()` 不会被调用。**3.10 缺 `ensurepip` 在此根本不构成障碍** | 背景段已改写为「`ensurepip` 不是障碍」并给出 `mkvenv.py:959` / `find_spec` 依据 |
| B12 | **BLOCKER（预检误判）** | 背景段第 4 条 | 我写「`[tooling]` 组 **python3.12 已满足**（setuptools 59.6.0 / wheel 0.37.1 / pip 25.0.1），无需补装」——**错**。我**只看了版本元数据就下结论**，未验证可导入性。实测 `python3.12 -c "import setuptools.build_meta"` 失败：`/usr/lib/python3/dist-packages/setuptools/__init__.py:10` `import distutils.core` → `ModuleNotFoundError: No module named 'distutils'`（3.12 已移除 `distutils`，而该包为 3.10 构建） | 背景段改为「必须验证可导入而非只看版本元数据」，并说明 `mkvenv.py:343-353` 因此误判为「已满足」而放弃补装 |
| B13 | 需修正 | S1 | S1 带 `PYTHON=python3.12` ⇒ **必然失败** | S1 改为 `make build-qemu`（用 `Makefile:8` 默认 `python3` = 3.10.12），并加「不得加 `PYTHON=` 覆盖」的告警 |
| B14 | 需修正 | 验收 #7 | 判据 `.work/build/qemu/pyvenv/bin/meson --version` = `1.11.1` 仍成立，但需注明 **venv 将改为 3.10 基** | 判据保留，补充说明 3.10 venv 下 meson 仍为 `1.11.1`（wheel `Requires-Python: >=3.7`） |

**B13 的可行性已由主会话独立实证**（不只采信 engineer 的探针）：用与真实 venv **完全相同**的参数 `python3 -m venv --without-pip --system-site-packages` 建探针 ⇒
- 3.10：`import setuptools.build_meta` **OK**（59.6.0）、`distutils` 可用、`need_ensurepip=False`
- 3.12：**精确复现** `ModuleNotFoundError: No module named 'distutils'`
- `meson-1.11.1` wheel `Requires-Python: >=3.7` ⇒ 3.10 可跑

⇒ Q1（去 `PYTHON=` 覆盖）**不需要** `pip install`、**不需要**动宿主 Python 环境、**不需要**改 `configure` 参数、**不需要**降 `-j`。探针建于 `/tmp/opencode/INFRA-106t/`，用后即删；两棵源码树 dirty 始终为 0。

**教训登记**：预检判定「某 Python 包已满足」时，**必须验证 `import` 可用，不能只读 `importlib.metadata` 版本号**——`mkvenv.py` 自身就栽在这一点上（`find_spec` vs 真导入），预检不应重复同一错误。

### 第 2 轮执行后新增的修正（B15–B18，主会话复核 engineer 报告后当场修）

第 2 轮去掉 `PYTHON=python3.12` 覆盖、改用默认 `python3`（3.10.12）后，**失败点前移且方向相反**：`make: *** [Makefile:55: manifest-check] Error 1`，`manifest_check.py:6 import tomllib` → `ModuleNotFoundError`。**主会话独立复核确认根因，并承认第 1 轮的 B13 修法（去 `PYTHON=` 覆盖）本身不足以成立**——它只解决了 QEMU 一侧，漏了 `Makefile` 自身对 `$(PYTHON)` 的两处使用。

| # | 级别 | 位置 | 缺陷 | 处置 |
| --- | --- | --- | --- | --- |
| B15 | **BLOCKER（我漏检）** | S1、背景段 | 第 1 轮我把矛盾归为「3.10 缺 ensurepip」，改用 3.12；**未检查 `Makefile:30`/`:55` 自身也用 `$(PYTHON)` 且需 `tomllib`（≥3.11）** ⇒ 两个解释器各缺一半能力，**在宿主上互斥** | 背景段新增「根因」小节，给出两侧能力矩阵与完整失败链；S0 补齐 3.10 的 `tomllib` |
| B16 | 需修正 | S1 | S1 块未含 S0 前置，直接跑会失败 | 新增 **S0** 步骤（幂等、秒级）+ `--check` 只验证模式 |
| B17 | 需修正 | 验收 #9 | 基线引用写死 21 路径 / 旧 sha256，第 2 轮后已失效 | 改为引用本轮快照文件 `git-status.round3` + `task-book-fingerprint.round3`（避免与任务书自身改动循环依赖） |
| B18 | 需修正 | 范围 | 用户批准的 S0 会改宿主 `~/.local`（user site-packages），原「不在范围内」未涵盖 | 已在 **S0** 内显式标注「已由用户于 2026-09-26 明确批准（方案 C）」 |

**B15/B16 的方案已由主会话完整实证**（先验证、后落库，不靠推断）：

| 实测项 | 结果 |
| --- | --- |
| `make manifest-check`（`$(PYTHON)`=python3=3.10 + shim） | rc=0，`manifest validation: PASS` |
| `component-enabled(qemu)`（`Makefile:30`） | rc=0（守卫放行） |
| 3.10 非隔离 venv 内 `import setuptools.build_meta` | OK 59.6.0（QEMU 侧未受损） |
| 3.12 的 `tomllib.__file__` | `/usr/lib/python3.12/tomllib/__init__.py`（**真 stdlib，未被 shim 遮蔽**） |
| 3.12 非隔离 venv **无** `PYTHONPATH` | `ModuleNotFoundError: No module named 'distutils'`（**精确复现第 1 轮失败**） |
| 3.12 非隔离 venv **有** `PYTHONPATH=/tmp/…/pylibs`（方案 B 变体） | OK 84.0.0 —— **但已否决**：不持久，且 shim 放 PYTHONPATH 会遮蔽 3.12 的真 tomllib |
| 仓库 `git status` sha256 | 全程未变 |

**shim 落位为何是 user site-packages 而非 PYTHONPATH**：`sys.path` 顺序为 `stdlib` → `lib-dynload` → **`~/.local/…/site-packages`** → 全局 site-packages。user site 排在 stdlib **之后** ⇒ 3.10（stdlib 无 tomllib）命中 shim，3.11+（stdlib 有 tomllib）真 stdlib 优先、不被遮蔽。反之 PYTHONPATH 排在 stdlib **之前**，**实测会遮蔽 3.12 的真 tomllib**（已注入反例 D 证实），故不用该变体。

**教训登记**：跨组件（工具链 vs 第三方构建）的环境修复，须**穷举所有消费方**再选方案；只验证一侧会得出「已实证可用」的错误结论（第 1 轮即如此）。

### `install_tomllib_shim.py` 的可失败性已实测（`AGENTS.md`「验证脚本必须能失败」）

该脚本是 S0 的门禁，7 项自验证若只会报 PASS 则毫无意义。已在**真实宿主**上逐项注入反例并全部复原（复原证据：shim sha256 `84ba9296…` 一致、`manifests/` 变更路径数 0）：

| 反例 | 注入方式 | 退出码 | 命中的 FAIL 项 |
| --- | --- | --- | --- |
| **A** | `mv` 走 shim | **1** | 4 项：`import tomllib` / `tomllib 来自 shim` / `manifest-check rc=2` / `component-enabled rc=1` |
| **B** | `mv` 走 `tomli` 包 | **1** | 同上 4 项 |
| **C** | shim 改成语法错误（`def broken(:`） | **1** | 同上 4 项 |
| **D** | `PYTHONPATH=<user-site>` 遮蔽 3.12 | **1** | 1 项：`python3.12 的 stdlib tomllib 未被 shim 遮蔽` |
| **E** | `components.lock.toml` 全部 `enabled=false` | **1** | 1 项：`component-enabled(qemu) rc=1` |
| 复原后回归 | — | **0** | `RESULT: OK (7/7 passed)` |

未做的反例及原因：QEMU 侧「3.10 venv 内 `setuptools.build_meta` 可导入」一项未单独注入（其检测路径与 A/B/C 同为 `import`，A/B/C 已证该 import 失败会使脚本整体 rc=1）；如需补做，把坏 `setuptools.py` 注入探针 venv 的 `PYTHONPATH` 即可。

取证：`/tmp/opencode/INFRA-106t/{shim-install.out,chk.out,shim.pristine}`。

**如实记录一次过程中的自身失误**：编写脚本时曾用 `subprocess.run(["command","-v",cand])` 试图执行 shell 内建 `command`，会抛 `FileNotFoundError`；**在实跑前**改为 `shutil.which` 并删掉未用的 `os`/`textwrap` 导入，故未造成实际失败。教训：验证脚本须**先 `py_compile` + 实跑**再入库。

**预检中已排除的疑似 BLOCKER**（记录以免重复排查）：`dadao-softmmu` 曾疑为缺失目录导致 `--target-list` 无法解析；实为 **target-list 名字**而非目录，`configs/targets/dadao-softmmu.mak:1` 提供 `TARGET_ARCH=dadao`，可正常解析。

**预检中核实为正确、未改动的条目**：风险预案 `make -C .work/build/qemu -j2` 路径（`Makefile:13`）、验收 #2/#3/#5/#8、`dadao-softmmu` 可解析、glib 2.72.4 / pixman 0.40.0 达标、`.work/source/qemu` HEAD `5c3535f` dirty=0 且 8 补丁相对锁定 base `c3d48b7d`。

### 验收 #6 判据的「可失败性」已实测（`AGENTS.md`「验证脚本必须能失败」）

新判据依赖 `tools/qemu/validate_decodetree.py`。为避免「只会报 PASS 的脚本不是证据」，下发前已在 `insn.decode` / `opcodes.yaml` 的**临时副本**上注入反例（真实源码树与 `contracts/` 全程 0 改动，事后 `git status` 复核）：

| 注入 | diff 非空 | 退出码 | 期望 | 实测输出 |
| --- | --- | --- | --- | --- |
| 原文件 + 原 yaml | — | **0** | PASS | `YAML 256 / patterns 256 / 错误 0` |
| 删 1 条 pattern（第 19 行 `ld_ub_rd`） | ✅ | **1** | FAIL | `ERROR: YAML 有但 decode 缺: ld.ub-rd → trans_ld_ub_rd` |
| 改 `opcodes.yaml` 1 条 `mask` 为 `0x7f` | ✅ | **1** | FAIL | `yaml mask=0x0000007F …` vs `decode pattern=00010000…` |
| 只保留后 128/256 条 pattern | ✅ | **1** | FAIL | `ERROR: YAML 有但 decode 缺: foscmp → trans_foscmp` |
| 改 1 条 pattern **名**（`ld_ub_rd`→`ld_ub_rd_X`） | ✅ | **1** | FAIL | 同时报 `YAML 有但 decode 缺` + `decode 有但 YAML 缺: ld_ub_rd_X (line 19)` |
| 改 1 条 pattern **编码 1 bit**（`00010000`→`00010010`） | ✅ | **1** | FAIL | `yaml: mask=0xFF000000 value=0x10000000` vs `decode: pattern=00010010` |

⇒ 该 checker **双向完整性、名字、编码**三类缺陷均可捕获，验收 #6 不是恒真断言。

> **如实记录两次空注入**：预检过程中另有 2 次注入因 `sed`/`awk` 模式未匹配而**未改动文件**（`sed '5s/0x/0x1/'` 落在注释行、`grep -v '^add\.si'` 匹配 0 行、`awk NR==16` 落在注释行），退出码自然是 0，**不构成任何证据，已作废**。上表 5 条均已逐条确认 diff 非空。取证：`/tmp/opencode/INFRA-106t/dispatch/r{1,2,4,5,6}.out`、`m*.decode` 副本。

### 第 3 轮执行后新增的修正（B19，主会话复核 engineer 报告后当场修）

第 3 轮**构建成功**（`build-qemu_rc=0`、144 秒），但验收 **#5 报 FAIL**。engineer **拒绝改判据**、如实报 FAIL 并给出真实产物位置 —— 处置正确。主会话**独立复核确认这是任务书缺陷，不是工作缺陷**，与 B1 同类（正确构建必然 FAIL 判据）。

| # | 级别 | 位置 | 缺陷 | 处置 |
| --- | --- | --- | --- | --- |
| B19 | **BLOCKER** | S3 块、S3 注、验收 #5 | 判据假定 decodetree 的 `.c.inc` 落在 `.work/build/qemu/target/dadao/`。**实测该目录整棵树 0 文件**；真实产物在 **meson 私有目录** `.work/build/qemu/libqemu-dadao-softmmu.a.p/decode-insn.c.inc`（84585 B、512 个 `trans_` 符号），`build.ninja` 的 `decode-insn.c.inc: CUSTOM_COMMAND` 规则权威确认。⇒ 前三轮 #5 全 FAIL，其中**第 3 轮那次是判据自身错误**（前两次另有构建未完成的原因） | 三处路径全部更正；判据加严为「`build.ninja` 记录路径 + 文件存在 + **非空** + 含 `trans_` 符号」，并以反例重验 |

> 判据来源更正：`decodetree.process()` 的输出落盘位置由 **meson 的 per-target 私有目录规则**（`*.a.p/`）决定，不沿用源码树相对路径。**教训**：判据里凡出现「构建产物路径」，必须从 `build.ninja` / `meson introspect` 之类的**构建系统权威记录**取证，不能从源码树布局外推。

| # | 级别 | 位置 | 缺陷 | 处置 |
| --- | --- | --- | --- | --- |
| **B20** | **BLOCKER（我自己引入）** | B19 更正后的验收 #5 判据脚本 | 我把 `build.ninja` 抓到的路径**直接当绝对路径**用，忘了它**相对构建根** ⇒ **判据在完全正确的构建上就报假 FAIL**；更糟的是，**反例 G/H 的输出与真实运行逐字相同 ⇒ 无区分力、属空证据**，若只看「rc≠0」会误判为反例成功。**是「反例输出必须与真实输出不同」这条自检把它抓出来的** | 判据改为 `path="$ROOT/$rel"` 补前缀；**重做全部 4 条反例（G' 0 字节 / H' 无 `trans_` / J 删文件 / I' 抹 build.ninja 规则）**，逐条确认与真实输出**不同**；S3 块同步加 `REL`/`ART` 推导 |

**B20 是 B19 的同源放大版**：B19 是「路径猜错」，B20 是「路径取对了但基准点搞错」。两者合并的教训 —— **判据里的每个路径都必须问「相对谁？」**，并用「反例输出 ≠ 真实输出」而非仅用「rc≠0」作为反例有效性的判据。

## 完成区

> 执行者：engineer 子代理，2026-09-26。**结论：S1 构建 FAIL（`build-qemu_rc=2`），10 项中 1 PASS / 4 PASS / 5 FAIL / 1 BLOCKED（#10 按任务书保持 BLOCKED）。**
> 失败点**不是** DADAO 补丁、不是 OOM，而是**宿主 Python 3.12 的 `setuptools` 不可导入**（详见 S1 归因）。
> 本次**未**改 `Makefile` / `configure` 参数 / `.work/source/**` / `-j` 并发度，**未** `pip install`，**未**动宿主 Python 环境，**未** commit/push。

### 0. 开工门禁与 dirty baseline

- 仓库根 `/home/ubuntu/DADAO-v5`，分支 `master`，HEAD `69a596798b69bfeb62a0f4b901fc4993f033cd77`（只读包装器 `/tmp/opencode/INFRA-104t/git-clean`）。
- 任务书 sha256 开工前 = `9e698275ca7908c55bf910c68375b75dc4d616c68c90ca30aa793f8ef87e52e2`、180 行、状态 `待开始` ⇒ 与 `dispatch/task-book-fingerprint.before` 一致，门禁通过。
- 开工前 status sha256 = `7fa8ecd1cf434230c5ccb3a9fda03ff3ed9ab8a63ac8283d3dfae93a30956712`（22 路径），与 `dispatch/git-status.after-fix-final` **逐字节相同**。
- 开工前**全量**重算 22 条 dirty 路径内容 sha256（不抽样）：原有 **21 路径与 `dirty-content-sha256.before` 全部一致，0 变化**；第 22 条即任务书自身。
- 源码树 `.work/source/qemu`：HEAD `5c3535f66892868a5829a1b0a242866da6d98e08`，`status --porcelain=v1 -uall` **0 行**，`diff --stat` **空** ⇒ 源码树 dirty=0 门禁通过。

### S1 — 构建：**FAIL**

严格按任务书 S1 块（`set -o pipefail` + `PIPESTATUS[0]`）执行，脚本 `/tmp/opencode/INFRA-106t/s1.sh`。

```
S1_START_utc=2026-09-26T10:51:39Z
S1_END_utc=2026-09-26T10:51:45Z
S1_SECONDS=6
S1 build-qemu 真实退出码 = 2
build-qemu_rc=2
```

日志 `.work/log/infra/INFRA-106t-build-qemu.log`（95 行）关键摘录：

```
enabled components: llvm-project, qemu
manifest validation: PASS
python determined to be '/usr/bin/python3.12'
python version: Python 3.12.14
mkvenv: Creating non-isolated virtual environment at 'pyvenv'
mkvenv: checking for meson>=1.5.0
mkvenv: checking for pycotap>=1.1.0
mkvenv: installing meson==1.11.1, pycotap==1.3.1
mkvenv: checking for qemu.qmp>=0.0.5
mkvenv: checking for setuptools>=44.1.1
mkvenv: checking for wheel>=0.34.2
mkvenv: checking for pip>=20.3.4
mkvenv: installing qemu.qmp==0.0.6
mkvenv: installing /home/ubuntu/DADAO-v5/.work/source/qemu/python
...
pip._vendor.pyproject_hooks._impl.BackendUnavailable: Cannot import 'setuptools.build_meta'
mkvenv did not complete successfully:
  File ".../python/scripts/mkvenv.py", line 689, in pip_install
subprocess.CalledProcessError: Command '['/mnt/dadao-v5/.work/build/qemu/pyvenv/bin/python3.12', '-m',
 'pip', 'install', '--disable-pip-version-check', '-q', '--find-links',
 '/home/ubuntu/DADAO-v5/.work/source/qemu/python/wheels', '--no-build-isolation', '-e',
 '/home/ubuntu/DADAO-v5/.work/source/qemu/python']' returned non-zero exit status 2.
make: *** [Makefile:92: build-qemu] Error 1
build-qemu_rc=2
```

`meson`/`ninja` 从未启动 ⇒ 无 decodetree 生成、无 `qemu-system-dadao` 链接。

#### S1 归因（只读取证，未做任何修复）

根因链，逐环均有实测：

1. `python3.12 -c "import setuptools.build_meta"` 实测失败：
   `File "/usr/lib/python3/dist-packages/setuptools/__init__.py", line 10, in <module> import distutils.core` → `ModuleNotFoundError: No module named 'distutils'`。
2. `python3.12 -c "import distutils"` 同样失败；`/usr/lib/python3.12/distutils` 不存在 ⇒ **Python 3.12 已从标准库移除 `distutils`**，而宿主 jammy 的 `python3-setuptools 59.6.0-1.2ubuntu0.22.04.3`（`dpkg -V` 校验完好）是为 Python 3.10 打的包，`__init__.py:10` 仍 `import distutils.core` ⇒ 在 3.12 上不可导入。
3. **为什么 mkvenv 没去补装 setuptools**：`pythondeps.toml:44` 只写 `"setuptools" = { accepted = ">=44.1.1" }`，**没有 `installed` 键**；`python/wheels/` 实际只有 `meson-1.11.1` / `pycotap-1.3.1` / `qemu_qmp-0.0.6` 三个 wheel，**没有 setuptools wheel** ⇒ 按设计就依赖宿主/venv 自带。
4. **为什么版本检查却通过了**：`mkvenv.py:343-353 need_ensurepip()` 用 `find_spec("setuptools")` 判定，源码注释自陈 *"Don't try to actually import them, it's fraught with danger"* 并链接 setuptools#2993。`find_spec` **不执行模块**，只看文件存在 ⇒ 误判为「已满足」。同时 `importlib.metadata.version("setuptools")` 返回 `59.6.0` ≥ 44.1.1 ⇒ `mkvenv: checking for setuptools>=44.1.1` 无 installing 行、直接跳过。
5. venv 以 `--system-site-packages` 创建（`pyvenv.cfg: include-system-site-packages = true`，`command = /usr/bin/python3.12 -m venv --without-pip --system-site-packages --clear …`）⇒ 继承上述**不可导入**的 system setuptools。
6. QEMU 自身 `python/` 包用 `--no-build-isolation -e` 安装，PEP 517 后端必须是 `setuptools.build_meta` ⇒ `BackendUnavailable` ⇒ pip 退出 2 ⇒ `mkvenv did not complete successfully` ⇒ `make … Error 1`。

**与任务书背景段/B6 的偏差（如实记录，未改判据）**：任务书写「`[tooling]` 组要求 `setuptools`/`wheel`/`pip`：**python3.12 已满足**（59.6.0 / 0.37.1 / 25.0.1），无需联网补装」。实测：

| 包 | 任务书预检值 | 实测 | 结论 |
| --- | --- | --- | --- |
| `setuptools` | 59.6.0「已满足」 | metadata=59.6.0，但 `import setuptools` **失败** | **预检误判**（只看了版本元数据，未验证可导入） |
| `wheel` | 0.37.1 | `import wheel` → 0.37.1 OK | 成立 |
| `pip` | 25.0.1 | 25.0.1（`~/.local/lib/python3.12/site-packages/pip`）OK | 成立 |

⇒ 任务书「venv 能否建起来」的不确定项确实存在，但**方向相反**：venv 建起来了、`meson 1.11.1` 也装上了，卡点是 `setuptools.build_meta` 不可导入。

**排除项（有据）**：`apt-cache policy python3.12-setuptools python3.12-distutils python3.12-pip` **全部无输出**（仓库中无这些包）⇒ apt 不是可用修法；`python3-setuptools` 的 candidate 仍是同一个坏包 59.6.0。本机无缓存的 setuptools wheel（`find ~/.cache/pip … -iname '*setuptools*'` 空）。PyPI 可达（`curl -I https://pypi.org/simple/setuptools/` → `status=200`），但**任何 `pip install` 均须用户确认，本次未执行**。

### S2 — 机器类型清点：**FAIL（127）**

```bash
( set -o pipefail; .work/build/qemu/qemu-system-dadao -M ? 2>&1 | grep -i dadao )
```

```
/bin/bash: line 2: .work/build/qemu/qemu-system-dadao: No such file or directory
S2_rc=127
ls: cannot access '.work/build/qemu/qemu-system-dadao': No such file or directory
```

未出现 `dadao-m1`。**归因**：S1 失败 ⇒ 无二进制。**源码侧 B2 更正经核实正确**：`hw/dadao/dadao-machine.c:123` 实为 `#define TYPE_DADAO_M1_MACHINE MACHINE_TYPE_NAME("dadao-m1")`，`:136` `error_report("dadao-m1: -bios rom.bin is required")`、`:140` `error_report("dadao-m1: -kernel test.bin is required")` ⇒ `dadao-m1` 与「-bios/-kernel 两者必需」均属实，与实测失败无关。

### S3 — decodetree 产物校验：checker **rc=0**，产物 `ls` **rc=2**

```
--- ls .work/build/qemu/target/dadao/*.c.inc ---
ls_rc=2
--- validate_decodetree.py ---
  YAML 记录数: 256
  decode pattern 数: 256
  错误数: 0
  OK: 所有 pattern 与 opcodes.yaml 一致
validate_decodetree: PASS
validate_decodetree 真实退出码 = 0
--- count of PASS lines --- 1
```

`.c.inc` 不存在，因为 `meson` 从未运行（S1 在 configure 的 mkvenv 阶段即中止），非 checker 问题。

### S4 — 版本与 target 自检：**FAIL（127 / 127）**

```
mkdir -p /tmp/opencode/INFRA-106t/s4   # rom.bin / test.bin 各 8 字节，已生成
--- qemu-system-dadao --version ---
/bin/bash: line 7: .work/build/qemu/qemu-system-dadao: No such file or directory
version_rc=127
--- -M dadao-m1 -bios -kernel ---
/bin/bash: line 11: .work/build/qemu/qemu-system-dadao: No such file or directory
S4 退出码 = 127
```

### 验收 10 项逐条结论

| # | 判据（原文要点） | 实际执行命令 | 真实输出摘录 | 退出码 | 结论 |
| --- | --- | --- | --- | --- | --- |
| 1 | `build-qemu` 成功：日志末行含 `build-qemu: PASS`，**且** S1 落盘 `build-qemu_rc=0` | 任务书 S1 块（`set -o pipefail` / `PIPESTATUS[0]`） | `build-qemu_rc=2`；`grep -n 'build-qemu: PASS' …` → 无匹配（grep rc=1）；`make: *** [Makefile:92: build-qemu] Error 1` | **2** | **FAIL** |
| 2 | 未假成功：日志中无 `refusing to fake success` | `grep -c 'refusing to fake success' .work/log/infra/INFRA-106t-build-qemu.log` | `0`（grep rc=1=无匹配） | 0 匹配 ⇒ 守卫**未**触发 | **PASS** |
| 3 | 二进制存在且可执行 | `test -x .work/build/qemu/qemu-system-dadao` | 不存在 | 1 | **FAIL** |
| 4 | `-M ?` 输出含 `dadao-m1` | S2 | `No such file or directory`，无 `dadao-m1` | 127 | **FAIL**（源码侧 `dadao-machine.c:123` 已核实为 `dadao-m1`；失败纯因无二进制） |
| 5 | `.work/build/qemu/target/dadao/*.c.inc` 存在 | `ls .work/build/qemu/target/dadao/*.c.inc` | 无输出 | 2 | **FAIL**（meson 未运行） |
| 6 | `validate_decodetree.py` rc=0 且输出**恰 1 行** `validate_decodetree: PASS` | `python3.12 -B tools/qemu/validate_decodetree.py .work/source/qemu/target/dadao/insn.decode contracts/opcodes.yaml` | `YAML 256 / patterns 256 / 错误数 0 / OK`；PASS 行计数 = **1** | **0** | **PASS**（与构建无关，独立成立） |
| 7 | `pyvenv/bin/meson --version` 输出 `1.11.1` | `.work/build/qemu/pyvenv/bin/meson --version` | `1.11.1` | 0 | **PASS（仅限「meson 自装链生效」这一项）**。限定：该 venv 是本次失败运行的残留，缺 QEMU `python/` 的 editable 安装，**不得**据此认为构建成功 |
| 8 | harness 期望的路径成立（相对路径 ⇒ 从仓库根执行） | 逐个取出 `min_rom_probe_*.py` 的 `QEMU` 常量并 `test -x` | 9/9 常量均为 `.work/build/qemu/qemu-system-dadao`（0 个绝对/`../` 形式）；但 9/9 `MISSING` | 1 | **FAIL**。路径**约定**已核实成立（须从仓库根执行），但该路径**当前不存在**，故不能判 PASS |
| 9 | 仓库工作区零改动 | `git-clean -c core.quotepath=false status --porcelain=v1 -uall` + 22 路径逐条内容 sha256 | status sha256 `7fa8ecd1…` 与基线**逐字节相同**（22 路径 0 差异）；原有 **21 路径内容 sha256 全部一致，0 变化** | 0 | **PASS** |
| 10 | 语义正确性（747 用例） | — | — | — | **BLOCKED**（属 `INTEG-101t`）。本任务只证构建与注册，**不构成任何语义证据**；本次构建失败，连构建证据都不成立 |

### 判据可失败性 —— 亲自注入反例的真实输出

全部注入都在 `/tmp/opencode/INFRA-106t/ce/` 的**副本**上做；`contracts/` 与 `.work/source/**` 全程 0 改动（事后复核见下）。

| 编号 | 目标判据 | 注入 | diff 非空 | 真实输出 | rc | 结论 |
| --- | --- | --- | --- | --- | --- | --- |
| **A0** | #1 `build-qemu_rc=0` | **本次真实构建失败**（非合成） | — | `build-qemu_rc=2`；无 `build-qemu: PASS` | **2** | 判据**会** FAIL，真实反例 |
| **A1b** | B3「裸 `\| tee` 恒真」陷阱 | `bash -c 'false 2>&1 \| tee log; echo $?'` | — | `裸 tee 形式 $? = 0` / `加 pipefail 后 $? = 1` / `PIPESTATUS[0] 形式 rc = 1` | — | 陷阱**真实存在**；S1 用的 `PIPESTATUS[0]` 形式确实取到真值 2 |
| **B** | #2 无 `refusing to fake success` | 往日志副本追加该串 | ✅ 1 行新增 | 注入后 `grep -c` = **1**；真实日志 = **0** | — | 有区分力 |
| **C** | #3 `test -x` | 真实路径 / 替身可执行 / 非可执行 | ✅ 新建 | 真实 **FAIL(1)**；替身 **PASS**；非可执行 **FAIL（正确拒绝）** | — | 有区分力 |
| **D** | #5 `decode-insn.c.inc` | 真实路径 / 替身文件 | ✅ 新建 | 真实 rc=**2**；替身 rc=**0** | — | 有区分力 |
| **E** | #7 `== 1.11.1` | 替身 meson 打印 `1.10.0`；再试 `1.11.1 (malicious)` | ✅ 新建 | 真实 `1.11.1` **PASS**；`1.10.0` **FAIL（正确拒绝）**；`1.11.1 (malicious)` **FAIL（正确拒绝，无宽松匹配）** | — | 有区分力 |
| **R1b** | #6 checker | 精确删 1 条 pattern（第 19 行 `ld_ub_rd`），行数 274→273 | ✅ `19d18` | `错误数: 1` / `ERROR: YAML 有但 decode 缺: ld.ub-rd → trans_ld_ub_rd` / `FAIL` | **1** | 有区分力 |
| **R2b** | #6 checker | 第 19 行编码改 1 bit `00010000`→`00010010` | ✅ `19c19` | `错误数: 1` / `ERROR: mask/value 不匹配: ld.ub-rd (line 19)` / `FAIL` | **1** | 有区分力 |
| **R3c** | #6 checker | `opcodes.yaml` 副本第 12 行 `mask: '0xFF000000'`→`'0x0000007F'` | ✅ `12c12` | `错误数: 1` / `ERROR: mask/value 不匹配: ld.ub-rd (line 19)` / `FAIL` | **1** | 有区分力 |

**如实记录本轮 2 次空注入（一律作废，不构成任何证据）**，与任务书预检阶段的 3 次同类：

- **R2**（改 1 条 pattern 编码）：`PATCH TARGET NOT FOUND`、`patch_rc=9`、`diff 非空? EMPTY(作废)`、checker `rc=0` ⇒ 作废。原因：我按 `ld.ub-rd` 找行，但 `insn.decode` 里的 pattern 名用**下划线** `ld_ub_rd`（点号只出现在 YAML），grep 匹配 0 行。
- **R3b**（改 yaml 的 mask）：`PATCH TARGET NOT FOUND`、`patch_rc=9`、`diff 非空? EMPTY(作废)`、checker `rc=0` ⇒ 作废。原因：YAML 的值带引号（`mask: '0xFF000000'`），我的正则要求引号后紧跟 `0x`，未匹配。R3c 改为 `r"(mask:\s*')0x[0-9A-Fa-f]+(')"` 后命中。

另有 **R1**（首次删 1 条）因 `grep -n '^ld\.ub-rd'` 返回空 ⇒ `n` 为空 ⇒ `sed -i "d"` 变成「删除全部行」，把 274 行清空（rc=1、256 errors）。虽非空注入，但**超出「删 1 条」的意图**，已作废并由 R1b 取代。

**反例后污染复核（还原证据）**：

```
$ git-clean -C .work/source/qemu status --porcelain=v1 -uall | wc -l
0
$ git-clean -C .work/source/qemu rev-parse HEAD
5c3535f66892868a5829a1b0a242866da6d98e08
$ git-clean -C .work/source/qemu diff --stat ; git-clean -C .work/source/qemu diff --name-only
(空)          (空)
$ sha256sum .work/source/qemu/target/dadao/insn.decode contracts/opcodes.yaml
7daf88379573980f5e38edb8164d62c34d0675c27e6243e6c9780c131a65f92b  .work/source/qemu/target/dadao/insn.decode
9cc5c711d8bad8347a34ba77976dacdb8c2b31868fcc7698dc055cbb3274769e  contracts/opcodes.yaml
```

⇒ 源码树 dirty 仍为 **0**、`git diff` 空、HEAD 未变。**本任务全程无需重建**（构建从未成功，未产生任何 `.o`/二进制，无可污染的二进制产物）。

### git status 前后对比结论

```
$ git-clean -c core.quotepath=false status --porcelain=v1 -uall | sha256sum
7fa8ecd1cf434230c5ccb3a9fda03ff3ed9ab8a63ac8283d3dfae93a30956712   （执行后）
7fa8ecd1cf434230c5ccb3a9fda03ff3ed9ab8a63ac8283d3dfae93a30956712   （dispatch/git-status.after-fix-final）
>>> status 逐字节相同 (22 路径, 0 差异)
```

22 路径**全量**内容 sha256 逐条比对（无抽样）：**原有 21 路径全部与 `dirty-content-sha256.before` 一致，0 变化**。唯一新增条目是第 22 条（任务书自身，开工时其 sha256 仍为 `9e69827…`）。填完本完成区后任务书 sha256 必然改变，那是**唯一被允许的差异**。

### 本任务在仓库内新增/修改的路径（全部在白名单内）

- `.work/log/infra/INFRA-106t-build-qemu.log`（6159 B）、`INFRA-106t-s2-machinetype.log`（245 B）、`INFRA-106t-s3-decodetree.log`（541 B）、`INFRA-106t-s4-version.log`（429 B）。
- `.work/build/qemu/`（`config-temp/`、`config.log`、`pyvenv/`）——`.gitignore` 忽略的构建残留。
- **本任务书「完成区」（唯一被修改的仓库文件）**。

`.tao/`、`manifests/`、`Makefile`、`contracts/`、`tools/`、`.xkw/knowledge/`、其它 `.xkw/tasks/**`、`.work/source/**` **一个字节都没改**。未 commit、未 push、未 `git add/stash/checkout/clean`。

### 停下等待用户确认的事项（按任务书规则，均未自行执行）

构建卡在宿主 Python 环境，**所有可行修法都超出本任务书授权**，故停在报告。**一次性只问第一个问题**：

**Q1（请先决定这一项）**：是否允许把 S1 的 `PYTHON=python3.12` 覆盖**去掉**，让 QEMU 用 `Makefile:8` 的默认 `PYTHON ?= python3`（= 3.10.12）？

依据（只读实测）：

- 任务书 B6「3.10 无 `ensurepip` ⇒ 必须带 `PYTHON=python3.12`」**不成立为决定性因素**：`python3 -c "import importlib.util as u; u.find_spec('setuptools'), u.find_spec('pip')"` → `(True, True)`，故 `mkvenv.py:343-353 need_ensurepip()` 在 **3.10 上同样返回 False**，`check_ensurepip()` **根本不会被调用**，venv 照样以 `--without-pip --system-site-packages` 创建。
- 在 `/tmp/opencode/INFRA-106t/feasibility/v310`（**仅临时目录**，未碰仓库与宿主）用与 mkvenv 相同的 flags 建的 3.10 venv：`import setuptools.build_meta` → **OK 59.6.0**（3.10 标准库仍带 `distutils`）；而真实的 3.12 venv 同一命令 → `ModuleNotFoundError: No module named 'distutils'`。
- 该选项**不需要** `pip install`、**不需要**动宿主 Python 环境、**不需要**改 `configure` 参数、**不需要**降 `-j`，只是**移除**任务书自己加的一个覆盖（回到 Makefile 默认）。代价：venv 落在 3.10，与任务书「python3.12」的记载不符，须相应修订任务书背景段/B6。

若 Q1 不可接受，备选（**每一条都需用户单独确认**，我一条都未做）：

- **Q2**：`python3.12 -m pip install --user 'setuptools>=70'`（`~/.local`，会遮蔽 system 坏包）。PyPI 实测可达（`status=200`）。属「`pip install` + 动宿主 Python 环境」，任务书明令须先确认；且会改变 `~/.local` 组成，影响面超出 `.work/`。
- **Q3**：`apt install python3.12-venv` 之外的 deadsnakes setuptools/distutils —— **已排除**：`apt-cache policy python3.12-setuptools python3.12-distutils python3.12-pip` 三者均无输出（仓库中不存在），`python3-setuptools` 的 candidate 仍是同一个坏包 59.6.0。
- **Q4**（任务书明令禁止，不建议）：改 `pythondeps.toml` 加 `installed` 键 + vendor 一个 setuptools wheel，或手工塞 meson 到 PATH —— 会污染 venv 语义使验收 #7 失效。

### 遗留 / 风险

- **能力缺口（需新任务或用户决策，非本任务可解）**：宿主 `python3.12` 无可用 `setuptools` ⇒ 只要 configure 走 3.12，`--no-build-isolation` 的 editable 安装必失败。这是**环境级阻塞**，建议由主会话决定走 Q1 还是 Q2。
- 任务书背景段与 B6 的 `setuptools 59.6.0 已满足` 结论**需按实测修订**（本次只记录，未改，因超出「只填完成区」授权）。
- 验收 #7 的 venv 是失败运行残留（缺 QEMU `python/` editable 安装），**不可**作为构建成功证据；下一次成功构建后应重新确认。
- `dadao-machine.c:123` 已核实为 `dadao-m1`，任务书 B2 的更正**正确**，无需再改；但 B10 登记的 `INTEG-101t:114` 陈旧 `dadao-m` 仍未处置（本次越界，未改）。
- 本次未触及 OOM 风险（`oom_kill=0`、构建 6 秒即在 configure 阶段失败），`make -j$(nproc)`=4 未改动、未使用。

---

## 完成区（第 2 轮，2026-09-26）

> 执行者：engineer 子代理，2026-09-26。**结论：S1 构建 FAIL（`build-qemu_rc=2`，0 秒），10 项中 1 PASS（#2 字面）/ 1 PASS（#6）/ 1 无法执行（#7）/ 5 FAIL（#1/#3/#4/#5/#8）/ 1 BLOCKED（#10 按任务书保持 BLOCKED）。**
> 本轮唯一变化：S1 由 `make PYTHON=python3.12 build-qemu` 改为 `make build-qemu`（`Makefile:8` 的 `PYTHON ?= python3` = 3.10.12），已在执行前实测确认。
> **第 1 轮结论被本轮实测推翻**：去掉 `PYTHON=` 覆盖**不能**解决问题，而是把失败点从「QEMU mkvenv 的 setuptools」前移到「Makefile 自身的 `manifest-check`」。**宿主上不存在同时满足两侧要求的 Python**（见 S1 归因表）。详见「停下等待确认」。

### 0. 开工门禁与 dirty baseline

- 仓库根 `/home/ubuntu/DADAO-v5`，分支 `master`，HEAD `69a596798b69bfeb62a0f4b901fc4993f033cd77`（只读包装器 `/tmp/opencode/INFRA-104t/git-clean`）。
- 任务书 sha256 开工前 = `15ac14d44dbb0b79b806214cf6e24069830d8e0b485d63413390ad88a5028eab`、424 行、状态 `待开始` ⇒ 与下发说明一致，**门禁通过**。
- 开工前 `git status` sha256 = `7fa8ecd1cf434230c5ccb3a9fda03ff3ed9ab8a63ac8283d3dfae93a30956712`（22 路径）⇒ 与下发基线**逐字节相同**。
- 开工前**全量**重算 22 路径内容 sha256（无抽样）：原有 **21 路径与 `dispatch/dirty-content-sha256.before` 全部一致，0 变化**（空白归一化后 `diff` 空，`diff_rc=0`）；第 22 条即任务书自身。
- 源码树 `.work/source/qemu`：HEAD `5c3535f66892868a5829a1b0a242866da6d98e08`，`status --porcelain=v1 -uall` **0 行**，`diff --stat` / `diff --name-only` 均**空** ⇒ 源码树 dirty=0 门禁通过。
- **开工前实测新前提**（非复核下发结论）：`.work/build/qemu/pyvenv/bin/python --version` → 不存在（`.work/build/qemu/` 目录本身都不存在）⇒ 与「第 1 轮残留已清、本轮全新」一致。

### S1 — 构建：**FAIL（`build-qemu_rc=2`，0 秒）**

严格按任务书 S1 块（`set -o pipefail` + `PIPESTATUS[0]`）执行，脚本 `/tmp/opencode/INFRA-106t/r2/s1.sh`，**无 `PYTHON=` 覆盖**（已用 `grep -vE '^[[:space:]]*#' | grep -E '(^|[[:space:]])PYTHON='` 确认无非注释行含该赋值；该检查**首次**误报，因模式命中了脚本自己的注释行，属典型「空/假注入」，已改用剥离注释后的模式重测）。

执行前确认 make 实际解析到的 Python（用**独立探针 makefile**，`Makefile` 本身未改）：

```
$ printf 'print-python:\n\t@echo "RESOLVED_PYTHON=[$(PYTHON)]"\n' > /tmp/opencode/INFRA-106t/r2/probe.mk
$ make -f Makefile -f /tmp/opencode/INFRA-106t/r2/probe.mk print-python
RESOLVED_PYTHON=[python3]
$ env | grep -E '^PYTHON='      → (无 PYTHON in environment)
```

```
S1_START_utc=2026-09-26T11:03:20Z
Traceback (most recent call last):
  File "/home/ubuntu/DADAO-v5/tools/infra/manifest_check.py", line 6, in <module>
    import tomllib
ModuleNotFoundError: No module named 'tomllib'
make: *** [Makefile:55: manifest-check] Error 1
build-qemu_rc=2
S1_END_utc=2026-09-26T11:03:20Z
S1_SECONDS=0
S1 build-qemu 真实退出码 = 2
```

日志 `.work/log/infra/INFRA-106t-build-qemu.log`（10 行）。`meson`/`ninja`/`configure` **从未启动**；`.work/build/qemu/` 目录**从未被创建**（`Makefile:94` 的 `mkdir -p $(QEMU_BUILD)` 在失败点之后）⇒ **零构建残留**。

#### S1 归因（只读取证，未做任何修复）——与第 1 轮的失败点**不同**且**方向相反**

宿主只有两个 Python（`/usr/bin/python3.10`、`/usr/bin/python3.12`）。两侧要求互斥：

| 解释器 | 版本 | `tomllib`（`Makefile:55` manifest-check、`Makefile:30` component-enabled） | `setuptools.build_meta`（QEMU `mkvenv`） |
| --- | --- | --- | --- |
| `/usr/bin/python3.10` | 3.10.12 | **MISSING** | **OK** |
| `/usr/bin/python3.12` | 3.12.14 | **OK** | **BROKEN**（`ModuleNotFoundError: No module named 'distutils'`） |

逐环实测：

1. `build-qemu` 的**第一个前置**是 `manifest-check`（`Makefile:89`），其配方 `Makefile:55` 为 `@$(PYTHON) tools/infra/manifest_check.py`。
2. `tools/infra/manifest_check.py:6` `import tomllib`，`:15` `tomllib.load(stream)`。`tomllib` 是 **Python 3.11+ 标准库**；`tomli`（3.10 回移）**未安装**（`find_spec('tomli')` = `False`）。
3. `python3 -c "import importlib.util as u; print(u.find_spec('tomllib'))"` → `False`；`python3.12` 同命令 → `True`。⇒ 默认 `python3`（3.10.12）**必然**在 `manifest-check` 崩掉，**0 秒失败**。
4. **更严重：`绕过 `manifest-check` 也不可行。** `Makefile:90` 的 `component-enabled` 守卫展开为 `Makefile:30` 的 `$(PYTHON) -c "import tomllib,sys;…"`。实测该命令的真实退出码：

   ```
   $ python3  -c "import tomllib,sys;…" ; echo $?   →  ModuleNotFoundError: No module named 'tomllib'   ;  rc=1
   $ python3.12 -c "import tomllib,sys;…" ; echo $? →  (无输出)                                            ;  rc=0
   ```

   ⇒ 在 3.10 下即使跳过 `manifest-check`，`component-enabled` 也会返回 1 ⇒ 触发 `Makefile:91` 的 `refusing to fake success` + `exit 1`。**这会使验收 #2 反转为 FAIL。**
5. 反向确认第 1 轮的结论仍然成立且未被推翻：3.12 的 `setuptools` 仍**不可导入**（`/usr/lib/python3/dist-packages/setuptools/__init__.py:10` `import distutils.core` → 3.12 已移除 `distutils`），故 `PYTHON=python3.12` 依旧会在 `mkvenv` 阶段 `BackendUnavailable` 失败（这是第 1 轮 `build-qemu_rc=2` 的**另一条**路径，与本轮 0 秒失败互不替代）。
6. QEMU 侧 `configure:512` `if test -z "${PYTHON}"` ⇒ `configure` **确实**读环境变量 `PYTHON`。而 make 只有**来自环境或命令行**的变量才会导出给子进程；`Makefile:8` 的 `PYTHON ?= python3` 是 makefile 内赋值 ⇒ **不导出**。故 `make build-qemu`（不加覆盖）时 `configure` 会自行探测 Python（通常取 `python3` = 3.10.12，对 `setuptools` 有利）。本轮 `configure` 未运行，此条为**源码级推断，未实测**，如实标注。

**结论：这不是「换个 Python 就能过」的单点问题，而是 `Makefile` 侧（需 `tomllib` ⇒ ≥3.11）与 QEMU 侧（需可导入 `setuptools` ⇒ 本机仅 3.10 可用）的直接冲突。宿主现有两个 Python 无法同时满足。**

#### 与任务书的偏差（如实记录，未改判据）

- 下发说明与任务书 S1 注记断言「**必须**用 `Makefile:8` 的默认 `PYTHON ?= python3`（= 3.10.12）……已实证 3.10 可用」——**该断言只覆盖了 QEMU 一侧，未覆盖 `Makefile` 自身对 `$(PYTHON)` 的两处使用**（`Makefile:55`、`Makefile:30`）。实测这两处在 3.10 上必然失败。**去覆盖的修法不成立。**
- 任务书 B11/B12/B13 的方向（3.10 对 QEMU 侧更优）**仍成立**，但不足以让 `make build-qemu` 走通。下发前预检的「依赖链实际可用性」在这一点上**未通过**。
- 本轮**未**改 `Makefile` / `configure` 参数 / `.work/source/**` / `-j` 并发度，**未** `pip install`，**未**动宿主 Python 环境，**未**改 `/usr/bin/python3` 指向，**未** commit/push。

### S2 — 机器类型清点：**FAIL（127）**

```
--- S2: qemu-system-dadao -M ? | grep -i dadao ---
/tmp/opencode/INFRA-106t/r2/s2.sh: line 9: .work/build/qemu/qemu-system-dadao: No such file or directory
S2_rc=127
--- count of 'dadao-m1' occurrences in full -M ? output ---
0
--- test -x binary ---
test_x_rc=1
```

未出现 `dadao-m1`。**归因**：S1 在 `manifest-check` 即中止 ⇒ 无二进制。源码侧 B2 的更正**仍正确**（`hw/dadao/dadao-machine.c:123` `MACHINE_TYPE_NAME("dadao-m1")`、`:136`/`:140` 的 `-bios`/`-kernel` 皆必需），本轮**未**重新改动该结论。

### S3 — decodetree 产物校验：checker **rc=0**，产物 `ls` **rc=2**

```
--- ls .work/build/qemu/target/dadao/*.c.inc ---
ls: cannot access '.work/build/qemu/target/dadao/*.c.inc': No such file or directory
ls_rc=2

--- validate_decodetree.py (python3.12 -B) ---
  [结果]
  YAML 记录数: 256
  decode pattern 数: 256
  错误数: 0
  OK: 所有 pattern 与 opcodes.yaml 一致

validate_decodetree: PASS
validate_decodetree_rc=0
--- count of exact 'validate_decodetree: PASS' lines ---
1
```

`.c.inc` 不存在，因 `configure`/`meson` 从未运行（与第 1 轮同因，但本轮更早：连 `mkdir` 都没执行）。checker 结论**与构建无关，独立成立**。

### S4 — 版本与 target 自检：**FAIL（127 / 127）**

```
-rw-rw-r-- 1 ubuntu ubuntu 8 /tmp/opencode/INFRA-106t/s4/rom.bin
-rw-rw-r-- 1 ubuntu ubuntu 8 /tmp/opencode/INFRA-106t/s4/test.bin
--- qemu-system-dadao --version | head -1 ---
/tmp/opencode/INFRA-106t/r2/s4.sh: line 13: .work/build/qemu/qemu-system-dadao: No such file or directory
version_rc=127
--- -M dadao-m1 -bios rom.bin -kernel test.bin -display none -nographic ---
/tmp/opencode/INFRA-106t/r2/s4.sh: line 18: .work/build/qemu/qemu-system-dadao: No such file or directory
S4_exit_code=127
--- does output contain 'is required'? ---
0
```

> **⚠️ 最后一个 `grep -c 'is required'` = 0 是「空洞为 0」，不构成任何证据**：QEMU 进程**从未启动**，被 grep 的是 bash 的 `No such file or directory`。S4 的实质判据「`-M dadao-m1` 被接受且进入 ROM 加载路径」**未被证明**，故 S4 判 **FAIL**，**不得**据此记 PASS。

### 验收 10 项逐条结论

| # | 判据（原文要点） | 实际执行命令 | 真实输出摘录 | 退出码 | 结论 | 对比第 1 轮 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `build-qemu` 成功：日志含 `build-qemu: PASS`，**且**落盘 `build-qemu_rc=0`（真实 make 退出码，非 `tee` 的） | 任务书 S1 块（`set -o pipefail` / `PIPESTATUS[0]`），**无 `PYTHON=` 覆盖** | `build-qemu_rc=2`；`build-qemu: PASS` 计数 = **0**；`make: *** [Makefile:55: manifest-check] Error 1` | **2** | **FAIL** | 仍 FAIL，**但失败点已变**（第 1 轮 `Makefile:92` / mkvenv，本轮 `Makefile:55` / manifest-check） |
| 2 | 未假成功：日志中无 `refusing to fake success` | `grep -c 'refusing to fake success' …` | 真实日志计数 = **0** | 0 匹配 ⇒ 守卫未触发 | **PASS（仅字面）**＋**重要保留**：守卫**根本没机会运行**（在更早的前置 `manifest-check` 就中止）。且已实测：在 `python3`=3.10 下若能走到该守卫，`Makefile:30` 的 `component-enabled` 会返回 **1** ⇒ 将打印 `refusing to fake success` 并 `exit 1`。**故本项的「通过」不可解读为「守卫健康」** | 仍 PASS，但本轮附上「守卫在 3.10 下已失效」的实证 |
| 3 | 二进制存在且可执行 | `test -x .work/build/qemu/qemu-system-dadao` | 不存在 | **1** | **FAIL** | 仍 FAIL（无变化） |
| 4 | `-M ?` 输出含 `dadao-m1` | S2 | `No such file or directory`；`dadao-m1` 计数 = 0 | **127** | **FAIL** | 仍 FAIL（无变化） |
| 5 | `.work/build/qemu/target/dadao/*.c.inc` 存在 | `ls .work/build/qemu/target/dadao/*.c.inc` | 无输出 | **2** | **FAIL** | 仍 FAIL（本轮连 build 目录都未创建） |
| 6 | `validate_decodetree.py` rc=0 且输出**恰 1 行** `validate_decodetree: PASS` | `python3.12 -B tools/qemu/validate_decodetree.py .work/source/qemu/target/dadao/insn.decode contracts/opcodes.yaml` | `YAML 256 / patterns 256 / 错误数 0 / OK`；PASS 行精确计数 = **1** | **0** | **PASS**（与构建无关，独立成立） | 仍 PASS（无变化） |
| 7 | `pyvenv/bin/meson --version` 输出 `1.11.1` | `.work/build/qemu/pyvenv/bin/meson --version` | **venv 不存在**（`.work/build/qemu/` 目录本身都不存在；`pyvenv/bin/meson` 不可执行） | — | **无法执行（UNRUNNABLE）**——`configure` 从未运行 ⇒ **不记 PASS，也不记 FAIL**。下发说明的硬性前提「configure 跑完后 venv 必须是 3.10.x」**本轮无从检验** | **由第 1 轮的「PASS（仅限自装链）」降级为「无法执行」**：第 1 轮至少有失败运行的 venv 残留，本轮连 venv 都没有 |
| 8 | harness 期望的路径成立（`min_rom_probe_*.py` 用相对路径 ⇒ 从仓库根执行） | 逐个取出 9 个 `min_rom_probe_*.py` 的 `QEMU` 常量并 `test -x` | 9/9 均为 `.work/build/qemu/qemu-system-dadao`（绝对/`../` 形式 = **0**）；但 9/9 **MISSING** | 1 | **FAIL**。路径**约定**成立（须从仓库根执行），但路径**当前不存在** ⇒ 不能判 PASS | 仍 FAIL（无变化） |
| 9 | 仓库工作区零改动 | `git-clean -c core.quotepath=false status --porcelain=v1 -uall` + 22 路径逐条内容 sha256 | 见下节 | 0 | **PASS** | 仍 PASS |
| 10 | 语义正确性（747 用例） | — | — | — | **BLOCKED**（属 `INTEG-101t`）。本任务只证构建与注册，**不构成任何语义证据**；本轮构建失败，连构建证据都不成立 | 仍 BLOCKED（按任务书保持） |

**合计：1 PASS(#2 字面) / 1 PASS(#6) / 1 无法执行(#7) / 5 FAIL(#1/#3/#4/#5/#8) / 1 BLOCKED(#10)。**

### 判据可失败性 —— 亲自注入反例的真实输出（本轮重新自证，不复用第 1 轮）

全部注入都在 `/tmp/opencode/INFRA-106t/r2/ce/` 的**副本**上做；`contracts/` 与 `.work/source/**` 全程 0 改动（事后复核见下）。

| 编号 | 目标判据 | 注入 | diff 非空 | 真实输出 | rc | 结论 |
| --- | --- | --- | --- | --- | --- | --- |
| **A0** | #1 `build-qemu_rc=0` | **本轮真实构建失败**（非合成） | — | `build-qemu_rc=2`；`build-qemu: PASS` 计数 = 0 | **2** | 判据**会** FAIL，真实反例 |
| **A1** | B3「裸 `\| tee` 恒真」陷阱 | `bash -c 'false \| tee log; $?'` 三种写法对比 | — | 裸 tee 形式 `$?` = **0**（恒真陷阱真实存在）；`set -o pipefail` 形式 = **1**；`PIPESTATUS[0]` = **1** | — | 陷阱**真实存在**；S1 用的 `PIPESTATUS[0]` 形式取到真值 **2** |
| **B** | #2 无 `refusing to fake success` | 往日志副本追加该串 | ✅ **2 行** | 注入后计数 = **1**；真实日志 = **0** | — | 有区分力 |
| **C** | #3 `test -x` | 真实路径 / 替身可执行 / 非可执行 | ✅ 新建 | 真实（不存在）**rc=1**；替身可执行 **rc=0**；非可执行（`chmod 644`）**rc=1**（正确拒绝） | — | 有区分力 |
| **D** | #5 `*.c.inc` | 真实路径 / 替身 `decode-insn.c.inc` | ✅ 新建 | 真实 **rc=2**；替身 **rc=0** | — | 有区分力 |
| **E** | #7 `== 1.11.1` **比较器**的区分力 | **合成**替身 meson：`1.11.1` / `1.10.0` / `1.11.1 (malicious)` | ✅ 新建 | `1.11.1`→**PASS**；`1.10.0`→**FAIL**；`1.11.1 (malicious)`→**FAIL**（无宽松匹配） | — | 比较器有区分力。**明确标注：这是合成替身，只证明「比较器」有牙齿，不证明真实 meson 是 1.11.1**；本轮真实判据 UNRUNNABLE |
| **R1** | #6 checker | 精确删 1 条 pattern（第 19 行 `ld_ub_rd`） | ✅ `19d18`（diff_lines=2） | `错误数: 1` / `ERROR: YAML 有但 decode 缺: ld.ub-rd → trans_ld_ub_rd` / `FAIL`；PASS 行计数 = 0 | **1** | 有区分力 |
| **R2** | #6 checker | 第 19 行编码改 1 bit `00010000`→`00010010` | ✅ `19c19`（diff_lines=4） | `错误数: 1` / `ERROR: mask/value 不匹配: ld.ub-rd (line 19)` / `FAIL` | **1** | 有区分力 |
| **R3** | #6 checker | `opcodes.yaml` 副本第 12 行 `mask: '0xFF000000'`→`'0x0000007F'` | ✅ `12c12`（diff_lines=4） | `错误数: 1` / `ERROR: mask/value 不匹配: ld.ub-rd (line 19)` / `FAIL` | **1** | 有区分力 |
| **R4** | #6 checker | 改 1 条 pattern **名**（`ld_ub_rd`→`ld_ub_rdX`） | ✅ `19c19`（diff_lines=4） | `错误数: 2` / 同时报 `YAML 有但 decode 缺` + `decode 有但 YAML 缺: ld_ub_rdX (line 19)` | **1** | 有区分力（双向完整性） |
| **G1** | 「venv 必须是 3.10.x」硬性前提 | 本轮 venv 不存在 | — | `UNRUNNABLE: no venv` | — | **该前提本轮无法触发**；若下轮 venv 出现且为 3.12，**必须立即停止** |

**本轮 0 次空注入**：上表 7 处注入（R1–R4、B、C、D、E）**逐条**打印了 `diff` 行数且均 ≥ 2，无一为空。**本轮另有 1 次「假阳性检查」已作废并重测**：`grep -E '(^|[[:space:]])PYTHON=' s1.sh` 首次命中脚本**自己的注释行**（`# NO PYTHON= override …`）而误报「存在覆盖」；改为剥离注释（`grep -vE '^[[:space:]]*#'`）后重测得「无非注释行含 `PYTHON=`」，并另用探针 makefile 独立确认 `RESOLVED_PYTHON=[python3]`、环境无 `PYTHON` ⇒ 无覆盖。**该次误报不计入证据。**

**反例后污染复核（还原证据）**：

```
$ git-clean -C .work/source/qemu status --porcelain=v1 -uall | wc -l
0
$ git-clean -C .work/source/qemu rev-parse HEAD
5c3535f66892868a5829a1b0a242866da6d98e08
$ git-clean -C .work/source/qemu diff --stat   ;  git-clean -C .work/source/qemu diff --name-only
(空)                                              (空)
$ sha256sum .work/source/qemu/target/dadao/insn.decode contracts/opcodes.yaml tools/qemu/validate_decodetree.py
7daf88379573980f5e38edb8164d62c34d0675c27e6243e6c9780c131a65f92b  .work/source/qemu/target/dadao/insn.decode   （= 开工前值）
9cc5c711d8bad8347a34ba77976dacdb8c2b31868fcc7698dc055cbb3274769e  contracts/opcodes.yaml                          （= 开工前值）
f0ce306b69801eb7fe8c498918660493f7d8a5fd02eb0f862dad04f6ffdc2566  tools/qemu/validate_decodetree.py              （= 开工前值）
```

⇒ 源码树 dirty 仍为 **0**、`git diff` 空、HEAD 未变、三个关键文件 sha256 与开工前**逐字节一致**。**本任务全程无需重建**（构建从未成功，`.work/build/qemu/` 从未创建，无任何 `.o`/二进制产物可供污染）。

### git status 前后对比结论

22 路径**全量**内容 sha256 逐条比对（无抽样）：开工前 22 条中，原有 **21 路径全部与 `dispatch/dirty-content-sha256.before` 一致，0 变化**（空白归一化后 `diff` 空）。填完本完成区后**唯一被允许的变化**是任务书自身（第 22 条）的 sha256。

**任务书完整性**：本轮追加内容**一律位于第 424 行之后**，第 1 轮完成区（第 203–424 行）**逐字未动**。核对方式：追加前 sha256 = `15ac14d44dbb0b79b806214cf6e24069830d8e0b485d63413390ad88a5028eab`（424 行），与下发基线一致；追加后 `head -c` 前 424 行与 `/tmp/opencode/INFRA-106t/r2/taskbook.before-append` **逐字节相同**。

### 本任务在仓库内新增/修改的路径（全部在白名单内）

- `.work/log/infra/INFRA-106t-build-qemu.log`（10 行）、`INFRA-106t-s2-machinetype.log`、`INFRA-106t-s3-decodetree.log`、`INFRA-106t-s4-version.log`。
- `.work/build/qemu/` —— **本轮不存在**（构建在 `mkdir` 之前即中止），无构建残留。
- **本任务书「完成区」第 424 行之后**（唯一被修改的仓库文件）。

`.tao/`、`manifests/`、`Makefile`、`contracts/`、`tools/`、`.xkw/knowledge/`、其它 `.xkw/tasks/**`、`.work/source/**` **一个字节都没改**。未 commit、未 push、未 `git add/stash/checkout/clean`。

### 停下等待用户确认的事项（按任务书规则，均未自行执行）

**去 `PYTHON=` 覆盖的修法已被实测证伪。本轮不再自行变通，停在报告。一次性只问第一个问题：**

**Q1（请先决定这一项）**：宿主两个 Python 无法同时满足两侧要求（`Makefile` 侧需 `tomllib` ⇒ ≥3.11；QEMU `mkvenv` 侧需可导入 `setuptools` ⇒ 本机仅 3.10 可用）。是否允许执行 **方案 B**：给 Python 3.12 补一个可用的 `setuptools`（`python3.12 -m pip install --user 'setuptools>=70'`），然后用 `make PYTHON=python3.12 build-qemu`？

**方案 B 为何技术上可行（已实测的两条依据）**：

1. `setuptools` ≥ 60 把 `distutils` 内置为 `setuptools._distutils`，**不再依赖标准库 `distutils`**，故 3.12 上可导入（宿主现装的 59.6.0 早于该 vendoring，才会在 3.12 上崩）。`pythondeps.toml:44` 只要求 `accepted = ">=44.1.1"` ⇒ 装新版本**不违反** QEMU 的依赖声明。
2. mkvenv 建的 venv **确实能看到 `~/.local` 的包**，故 `--user` 安装对 venv 生效。实测（`/tmp` 探针，用 mkvenv 相同 flags `--without-pip --system-site-packages --clear`，探针已删）：

   ```
   ENABLE_USER_SITE = True
   user site path    = /home/ubuntu/.local/lib/python3.12/site-packages
   user site on path = True
   find_spec(pip)    = True
   pyvenv.cfg: include-system-site-packages = true
                 command = /usr/bin/python3.12 -m venv --without-pip --system-site-packages --clear …
   ```

**代价与边界（如实列出）**：属「`pip install` + 动宿主 Python 用户级环境」，任务书明令须先经用户确认；会改变 `~/.local/lib/python3.12/site-packages` 组成，影响面超出 `.work/`。**不触碰** `/usr/bin/python3` 指向（`INFRA-102t:69` 明令禁止）、**不**给系统 3.10 升级/卸载任何包、**不**改 `Makefile`、**不**改 `configure` 参数、**不**改 `-j`。

若 Q1 不可接受，备选（**每一条都需用户单独确认，我一条都未做**）：

- **Q2**：给 Python 3.10 装 `tomli` 并提供 `tomllib` 转发。`INFRA-102t:74` 已把此方案登记为「**不推荐**——用 stdlib 同名模块做影子劫持，后续易与真实行为混淆」，且同样属 `pip install` + 改宿主环境。**注意**：即使选它，也**必须**同时解决 `Makefile:30` 的 `component-enabled`，否则验收 #2 会翻成 FAIL。
- **Q3**：绕过 `manifest-check`（如 `make -o manifest-check build-qemu`）。**已实测不可行**：`Makefile:30` 的 `component-enabled` 在 3.10 上 `rc=1` ⇒ 会打印 `refusing to fake success` 并 `exit 1`，**验收 #2 反而 FAIL**。故此方案**技术上即被排除**，列出仅为说明「为何不能靠跳过前置绕过」。
- **Q4**（任务书明令禁止，不建议）：改 `Makefile` 的 `PYTHON` 默认值、改 `tools/infra/manifest_check.py` 加 `tomli` 回退、改 `pythondeps.toml`、或手工塞 meson 到 PATH —— 均越出本任务书范围，且会污染 venv 语义使验收 #7 失效。
- **Q5**（新出现，需用户裁决）：修改 `tools/infra/manifest_check.py` 等 6 个 `import tomllib` 的脚本改用 `tomli`/`tomllib` 兼容导入，或把 `Makefile:8` 默认改为 3.12 —— **均越出本任务书范围**（任务书「不在范围内：修改 `Makefile`」），但这是**唯一能同时满足两侧的干净方向**（因为它让两侧都用 3.12，而 3.12 的 `setuptools` 仍需 Q1 补齐）。**建议作为独立任务处理，而非塞进 INFRA-106t。**

### 遗留 / 风险

- **环境级阻塞（本轮新发现，性质与第 1 轮不同）**：`Makefile` 对 `$(PYTHON)` 有两处依赖（`:30`、`:55`）**要求 ≥3.11**（`tomllib`），而 QEMU `mkvenv` 在本机**要求 ≤3.10 侧的可用 `setuptools`**。这不是「选对 Python 就能过」，**必须**在宿主环境或仓库脚本上做一次性决策。
- **下发前预检的一处漏检**：预检核对了 QEMU 侧对 Python 的要求，**未核对 `Makefile` 自身对 `$(PYTHON)` 的要求**，故「去 `PYTHON=` 覆盖即可」这一结论在预检阶段就是错的。建议把「`Makefile` 中所有 `$(PYTHON)` 使用点」列为 `/dispatch` 依赖链核查的固定项。
- 验收 #7 本轮 **UNRUNNABLE**（无 venv）。下一轮一旦 `configure` 跑完，**必须**先确认 `pyvenv/bin/python --version` 为 3.10.x；若为 3.12 立即停止。
- 任务书 B2 的 `dadao-m1` 更正**仍正确**，本轮复核未被推翻；但因无二进制，**本轮未取得运行侧证据**。
- B10 登记的 `INTEG-101t:114` 陈旧 `dadao-m` 仍未处置（越界，未改）。
- 本轮未触及 OOM 风险（`build-qemu` 0 秒即在前置阶段失败，`make -j$(nproc)`=4 从未启动、未改动、未使用）。

## 完成区（第 3 轮，2026-09-26）

> **前两轮均为 FAIL**（第 1 轮 `PYTHON=python3.12` → `build-qemu_rc=2`，`BackendUnavailable`；第 2 轮默认 `python3` → `manifest-check` 缺 `tomllib`）。根因与两轮完整记录见上文「根因」小节及前两个完成区，**不得删除**。
> 本轮新增 **S0**（`install_tomllib_shim.py`，用户已批准的方案 C）后，**裸 `make build-qemu` 即可工作**，S1 不再需要任何 `PYTHON=` 覆盖。

### 0. 开工门禁与 dirty baseline

- 仓库根 `/home/ubuntu/DADAO-v5`，分支 `master`，HEAD `69a596798b69bfeb62a0f4b901fc4993f033cd77`（只读包装器 `/tmp/opencode/INFRA-104t/git-clean`）。
- 任务书 sha256 开工前 = `0337a3b6c8cd8e5a5f888b073a79802c1583b1d868f422629ffe4d5061b6cd52`、751 行、状态 `待开始` ⇒ 与下发说明给定的指纹**逐字节一致**，门禁通过。
- 开工前 `git status --porcelain=v1 -uall` sha256 = `139e3b5a306ca1d36b2cbb1161b65907c28a4e745de31b9aec522caf48029bad`（**23 路径**），与 `dispatch/git-status.round3` **逐字节相同**（`diff_rc=0`）。
- 开工前**全量**重算 23 条 dirty 路径内容 sha256（不抽样），与 `dispatch/task-book-fingerprint.round3` 的 `authorized-delta` 逐条核对：

| 相对原始 21 路径基线 | 路径 | 结论 |
| --- | --- | --- |
| 内容变化（授权 #3） | `.xkw/knowledge/deferred.md` | `131ab84d…` → `6b4e73e6…`，**主会话在下发前改的，本轮我一个字节都没动** |
| 新增路径（授权 #1） | `.xkw/tasks/infra/INFRA-106t-QEMU构建.md` | 任务书自身 |
| 新增路径（授权 #2） | `tools/infra/install_tomllib_shim.py` | 方案 C 安装器 |
| 其余 **20** 条原始路径 | — | 内容 sha256 **全部与 `dispatch/dirty-content-sha256.before` 一致，0 变化** |
| 丢弃路径 | — | **0** |

- 源码树 `.work/source/qemu`：HEAD `5c3535f66892868a5829a1b0a242866da6d98e08`，`status --porcelain=v1 -uall` **0 行**，`diff --name-only` **空** ⇒ 源码树 dirty=0 门禁通过。
- 资源：`MemAvailable` 1365028 kB / 4000688 kB、`SwapFree` 19897224 kB、`nproc`=4、`oom_kill`=0、`.work` 所在大盘 173G 可用。`.work/build/llvm`（10G）**全程未触碰**。
- 开工前 `.work/build/qemu` **不存在** ⇒ 本轮是全新 configure（`find`/`ls` 均确认）。

### S0 — 宿主 `tomllib` 补齐：**PASS（rc=0，7/7）**

```
$ python3 tools/infra/install_tomllib_shim.py
=== install_tomllib_shim ===
  [install] user site-packages = /home/ubuntu/.local/lib/python3.10/site-packages
  [install] tomli 已安装，跳过
  [install] /home/ubuntu/.local/lib/python3.10/site-packages/tomllib.py 已是目标内容，跳过
=== verify ===
  [PASS] 本解释器版本                                   3.10.12
  [PASS] /usr/bin/python3 可 import tomllib 并解析 components.lock.toml   components=3
  [PASS] tomllib 来自 user site-packages 的 shim        /home/ubuntu/.local/lib/python3.10/site-packages/tomllib.py
  [PASS] python3.12 的 stdlib tomllib 未被 shim 遮蔽     /usr/lib/python3.12/tomllib/__init__.py
  [PASS] make manifest-check（$(PYTHON)=python3）rc=0   manifest validation: PASS
  [PASS] component-enabled(qemu) rc=0（守卫须放行）      (no output)
  [PASS] 3.10 非隔离 venv 内 setuptools.build_meta 可导入（QEMU 侧未受损）  setuptools 59.6.0
RESULT: OK  (7/7 passed)
S0 install_tomllib_shim 真实退出码 = 0
```

**如实记录**：如主会话预告，本轮 S0 看到的是**「tomli 已安装，跳过」/「已是目标内容，跳过」**——shim 已由主会话在验证阶段装好，本轮**未发生任何 `pip install`**，宿主无新增包。shim 文件 sha256 开工前后一致：`84ba9296fcf6ceaa0dbcd4e8371fb80d253b8a875277c66c687b48f1b8061ec4`（与任务书「`/tmp/opencode/INFRA-106t/{…}/shim.pristine`」记录的 pristine 值相同）。这不是错误，是幂等设计的预期表现。

**构建后复验（任务书要求的额外一项）**：`python3 tools/infra/install_tomllib_shim.py --check` ⇒ `RESULT: OK (7/7 passed)`、**rc=0**，shim sha256 仍为 `84ba9296…` ⇒ **构建过程没有破坏 shim**。

### S1 — 构建：**PASS（`build-qemu_rc=0`，144 秒）**

严格按任务书 S1 块（`set -o pipefail` + `${PIPESTATUS[0]}`），脚本 `/tmp/opencode/INFRA-106t/r3/s1.sh`（副本存 `.work/log/infra/INFRA-106t-s1-script.sh`）。**无 `PYTHON=` 覆盖**，且开工前用三重证据自证：

```
S1_GUARD self_noncomment_PYTHON_assign_lines=0 (expect 0)
S1_GUARD env_PYTHON_lines=0 (expect 0)
RESOLVED_PYTHON=[python3]          # 独立探针 makefile 打印 Makefile:8 实际解析值
```

```
S1_START_utc=2026-09-26T11:20:51Z
S1_END_utc=2026-09-26T11:23:15Z
S1_SECONDS=144
MemAvailable_kB_before=1365028
MemAvailable_kB_after=1579612
oom_kill_after=0
S1 build-qemu 真实退出码 = 0
```

日志 `.work/log/infra/INFRA-106t-build-qemu.log`（3012 行，2359 个 ninja 步骤）关键摘录：

```
enabled components: llvm-project, qemu
references: 2
manifest validation: PASS
mkdir -p .work/build/qemu
cd .work/build/qemu && /home/ubuntu/DADAO-v5/.work/source/qemu/configure \
  --target-list=dadao-softmmu --enable-tcg --disable-werror
python determined to be '/usr/bin/python3'
python version: Python 3.10.12
mkvenv: Creating non-isolated virtual environment at 'pyvenv'
mkvenv: checking for meson>=1.5.0
mkvenv: installing meson==1.11.1, pycotap==1.3.1
mkvenv: checking for setuptools>=44.1.1
mkvenv: checking for wheel>=0.34.2
mkvenv: checking for pip>=20.3.4
mkvenv: installing qemu.qmp==0.0.6
mkvenv: installing /home/ubuntu/DADAO-v5/.work/source/qemu/python
...
[2359/2359] Linking target tests/qtest/netdev-socket
make[1]: Leaving directory '/mnt/dadao-v5/.work/build/qemu'
build-qemu: PASS
build-qemu_rc=0
```

**方案 C 的两个前提均被实测证实**：

1. `manifest-check`（`Makefile:55`，需 `tomllib`）在 3.10 上**通过** ⇒ shim 生效。
2. `mkvenv` 的 `pip install -e python/`（需 `setuptools.build_meta`）在 3.10 上**成功** ⇒ 日志中 `BackendUnavailable` 出现次数 = **0**（第 1 轮正是在此处失败），venv 内可见 `qemu`、`qemu.egg-link`、`qemu_qmp-0.0.6.dist-info` ⇒ editable 安装真的落盘。
3. `meson` 取自 **vendor wheel**：`mkvenv: installing meson==1.11.1`，全程**未联网取 meson**。

**硬性前提（`pyvenv` 必须是 3.10.x）已核验通过，未触发停止条件**：

```
$ .work/build/qemu/pyvenv/bin/python --version
Python 3.10.12                       (rc=0)
$ cat .work/build/qemu/pyvenv/pyvenv.cfg
home = /usr/bin
include-system-site-packages = true
version = 3.10.12
$ .work/build/qemu/pyvenv/bin/meson --version
1.11.1                               (rc=0)
```

`MemAvailable` 全程未低于 1365028 kB（结束时反而升到 1579612 kB），`oom_kill` 前后均 = **0** ⇒ 未触及 OOM 风险，`-j` 未改动（`Makefile:99` 的 `make -j$(nproc)`=4 原样使用）。构建产物 `.work/build/qemu` = 846M。

### S2 — 机器类型清点：**PASS（grep rc=0）**

```bash
( set -o pipefail; .work/build/qemu/qemu-system-dadao -M ? 2>&1 | grep -i dadao )
```

```
dadao-m1             DADAO M1 bare-metal test machine
  real grep rc=0
```

与任务书 S2 期望块**逐字符一致**（含描述串 `DADAO M1 bare-metal test machine`）。`-M ?` 全文只有 3 行（`Supported machines are:` / `dadao-m1 …` / `none  empty machine`），因为 `--target-list=dadao-softmmu` 只编了 dadao 一个 target。**B2 的 `dadao-m1` 更正正确，本轮首次取得运行侧证据**。旁证：二进制内 `strings` 命中描述串、`nm | grep -ic dadao` = 40 ⇒ 机器确为编译进二进制并注册，非输出巧合。

### S3 — decodetree 产物校验：checker **rc=0（PASS 行恰 1 行）**，产物 `ls` **rc=2（FAIL，任务书路径有误）**

```
--- ls -l .work/build/qemu/target/dadao/*.c.inc ---
ls: cannot access '.work/build/qemu/target/dadao/*.c.inc': No such file or directory
ls_rc=2
--- validate_decodetree.py (python3.12 -B) ---
  YAML 记录数: 256
  decode pattern 数: 256
  错误数: 0
  OK: 所有 pattern 与 opcodes.yaml 一致
validate_decodetree: PASS
validate_decodetree_rc=0
--- count of exact 'validate_decodetree: PASS' lines ---
1
```

**产物其实生成了，只是任务书写错了路径**（详见「与任务书的偏差」#D1）：

```
$ ls -l .work/build/qemu/libqemu-dadao-softmmu.a.p/decode-insn.c.inc
-rw-rw-r-- 1 ubuntu ubuntu 84585 Sep 26 11:21 …/decode-insn.c.inc
$ grep -c 'trans_' …/decode-insn.c.inc            → 512
$ grep -oE 'trans_(foscmp|ld_ub_rd|swym|add_si)\b' … | sort -u
trans_foscmp
trans_ld_ub_rd
$ grep -nE 'decode-insn\.c\.inc' .work/build/qemu/build.ninja | head -1
build libqemu-dadao-softmmu.a.p/decode-insn.c.inc: CUSTOM_COMMAND ../../source/qemu/target/dadao/insn.decode | …/scripts/decodetree.py
$ find .work/build/qemu/target -type f | wc -l   →  0
```

即：meson 把 `decodetree.process()` 的输出放进**消费方静态库的 private 目录** `libqemu-dadao-softmmu.a.p/`，**不是** `target/dadao/`；构建树的 `target/` 整棵树有 **0** 个文件。`target/dadao/translate.c:113` `#include "decode-insn.c.inc"` 正是取该 private 目录。

### S4 — 版本与 target 自检：**PASS（判据成立；进程以 SIGFPE 结束，属 `INTEG-101t` 范围）**

```
-rw-rw-r-- 1 ubuntu ubuntu 8 /tmp/opencode/INFRA-106t/s4/rom.bin
-rw-rw-r-- 1 ubuntu ubuntu 8 /tmp/opencode/INFRA-106t/s4/test.bin
--- qemu-system-dadao --version | head -1 ---
QEMU emulator version 11.1.1 (v11.1.1-8-g5c3535f)      (rc=0)
--- -M dadao-m1 -bios rom.bin -kernel test.bin -display none -nographic ---
QEMU 11.1.1 monitor - type 'help' for more information
(qemu) S4_exit_code=136
--- does output contain 'is required'? ---
0
```

`--version` 里的 `v11.1.1-8-g5c3535f` 与锁定 commit `5c3535f`（源码树 HEAD）**对得上**。二进制 34832720 B、ELF 64-bit pie、`test -x` rc=**0**。

**「`is required` 计数 = 0」不是空洞为 0**（第 2 轮栽过这一条），本轮补了**同机器正向对照**：

```
omit -kernel : qemu-system-dadao: dadao-m1: -kernel test.bin is required   (exit=1)
omit -bios   : qemu-system-dadao: dadao-m1: -bios rom.bin is required       (exit=1)
wrong -M     : qemu-system-dadao: unsupported machine type: "no-such-machine" (exit=1)
real (both)  : 'is required' count = 0，且已打印 monitor 提示符 (qemu) ⇒ 机器实例化完成
```

⇒ 同一台二进制、同一台机器，**参数校验失败时该模式必然被打印并 exit 1**；本次运行通过了该校验并进入 monitor，故「无 `is required`」是**有牙齿的 0**。

**如实记录**：本次运行最终以 **136 = 128+8 = SIGFPE** 结束。按任务书「零内容 ROM 的执行结果**不在本任务判据内**（属 `INTEG-101t` E2E）」，此**不影响 S4 判据**，但这是一个**真实的语义观察**，已登记到下方「遗留 / 风险」交给 `INTEG-101t`（8 字节全零 ROM = 指令 `0x00000000`）。

### 验收 10 项逐条结论

| # | 判据（原文要点） | 实际执行命令 | 真实输出摘录 | 退出码 | 结论 | 对比前两轮 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `build-qemu` 成功：日志含 `build-qemu: PASS`，**且** S1 落盘 `build-qemu_rc=0`（真实 make 退出码，非 `tee` 的） | 任务书 S1 块（`set -o pipefail` / `${PIPESTATUS[0]}`），**无 `PYTHON=` 覆盖** | 日志 3011 行 `build-qemu: PASS`、3012 行 `build-qemu_rc=0`；`s1.rc` 文件 = `0`；2359/2359 ninja 步完成 | **0** | **PASS** | **FAIL → FAIL → PASS**（第 1 轮 `BackendUnavailable`，第 2 轮 `manifest-check` 缺 `tomllib`） |
| 2 | 未假成功：日志中无 `refusing to fake success` | `grep -c 'refusing to fake success' …build-qemu.log` | 真实日志计数 = **0**（grep rc=1=无匹配） | 0 匹配 | **PASS（且本轮是实质性的）** | 第 1/2 轮为「PASS（仅字面）」+ 保留；**本轮守卫真的跑到了并放行**：`manifest validation: PASS`（日志 3 行）+ `component-enabled(qemu) rc=0`（S0 第 6 项实测），不再是「根本没机会运行」 |
| 3 | 二进制存在且可执行 | `test -x .work/build/qemu/qemu-system-dadao` | 存在，34832720 B，ELF 64-bit pie | **0** | **PASS** | **FAIL → FAIL → PASS** |
| 4 | `-M ?` 输出含 `dadao-m1` | S2 | `dadao-m1             DADAO M1 bare-metal test machine`；grep rc=0；`strings` 命中同串 | **0** | **PASS** | **FAIL → FAIL → PASS**（B2 更正确认） |
| 5 | `.work/build/qemu/target/dadao/*.c.inc` 存在（`decode-insn.c.inc`） | `ls -l .work/build/qemu/target/dadao/*.c.inc` | `No such file or directory`；`ls_rc=2`。真实产物在 `libqemu-dadao-softmmu.a.p/decode-insn.c.inc`（84585 B，512 个 `trans_`） | **2** | **FAIL（字面判据）** | 第 1/2 轮 FAIL 的原因都是「meson 从未运行」；**本轮原因完全不同：meson 正常跑完并生成了产物，是任务书写错了产物路径**（见偏差 #D1，判据缺陷类 = B1，**我未改判据**） |
| 6 | `validate_decodetree.py` rc=0 且输出**恰 1 行** `validate_decodetree: PASS` | `python3.12 -B tools/qemu/validate_decodetree.py .work/source/qemu/target/dadao/insn.decode contracts/opcodes.yaml` | `YAML 256 / patterns 256 / 错误数 0 / OK`；PASS 行精确计数 = **1** | **0** | **PASS** | PASS（无变化） |
| 7 | `pyvenv/bin/meson --version` 输出 `1.11.1` | `.work/build/qemu/pyvenv/bin/meson --version` | `1.11.1`；同时 `pyvenv/bin/python --version` = `Python 3.10.12`，`pyvenv.cfg` `version = 3.10.12` | 0 / 0 | **PASS** | 第 1 轮「PASS（仅限自装链，venv 是失败残留）」→ 第 2 轮 **UNRUNNABLE** → **本轮 PASS**（venv 来自成功构建，editable 安装已落盘） |
| 8 | harness 期望的路径成立：9 个 `min_rom_probe_*.py` 用**相对路径**（须从仓库根执行） | 逐个取出 `QEMU` 常量（**9/9 全查，无抽样**）并 `test -x` | 9/9 均为 `.work/build/qemu/qemu-system-dadao`（绝对/`../` 形式 = **0**）；仓库根 `test -x` rc=0 且 `--version` 正常输出 | **0** | **PASS** | **FAIL → FAIL → PASS** |
| 9 | 仓库工作区零改动（**唯一允许的差异是完成区**） | `git-clean … status --porcelain=v1 -uall` + **23/23 逐路径**内容 sha256 | 见下节 | **0** | **PASS** | PASS（无变化） |
| 10 | 语义正确性（747 用例） | — | — | — | **BLOCKED**（属 `INTEG-101t`） | **仍 BLOCKED**（按任务书保持）。本任务只证构建与注册，**不构成任何语义证据**；S4 观察到的 SIGFPE 亦**不得**在此记为语义结论 |

**合计：8 PASS（#1/#2/#3/#4/#6/#7/#8/#9）/ 1 FAIL（#5，任务书判据路径有误，产物实际已生成）/ 1 BLOCKED（#10）。**
**从 FAIL 变 PASS 的项：#1、#3、#4、#7（由 UNRUNNABLE 转 PASS）、#8 —— 共 5 项。**

### 判据可失败性 —— 亲自注入反例的真实输出（本轮重新自证，未复用前两轮）

全部注入都在 `/tmp/opencode/INFRA-106t/r3/ce/` 的**副本**上做；唯一例外是 **CE-S0**（必须动宿主 `~/.local`，属用户批准范围，已用 pristine 备份 + `trap … EXIT` 兜底 + sha256 复原验证）。

| 编号 | 目标判据 | 注入 | diff 非空 | 真实输出 | rc | 结论 |
| --- | --- | --- | --- | --- | --- | --- |
| **CE-1a** | B3「裸 `\| tee` 恒真」陷阱 | `false \| tee` 三种写法对比 | — | 裸 `\| tee` `$?` = **0**（恒真陷阱真实存在）；`set -o pipefail` 块 = **1**；`PIPESTATUS[0]` = **1** | — | 陷阱真实存在；S1 用的 `${PIPESTATUS[0]}` 形式取到真值 **0**（成功）而非被 `tee` 掩盖 |
| **CE-1b** | #1 checker 本身有牙齿 | 日志副本删掉 `build-qemu: PASS` 与 `build-qemu_rc=0` 两行，追加 `Error 1` + `build-qemu_rc=2` | ✅ `diff_lines=6` | 真实日志：`PASS`×1 / `rc=0`×1 ⇒ **VERDICT: PASS**；被改日志：`PASS`×0 / `rc=0`×0 ⇒ **VERDICT: FAIL** | — | 有区分力 |
| **CE-2** | #2 无 `refusing to fake success` | 日志副本追加该串一行 | ✅ `diff_lines=2` | 真实计数 = **0**；注入后 = **1** | — | 有区分力 |
| **CE-3** | #3 `test -x` | 缺失路径 / `chmod 644` 替身 / `chmod 755` 替身 | ✅ 新建 | 真实 **rc=0**；缺失 **rc=1**；存在但 644 **rc=1**（正确拒绝）；755 **rc=0** | — | 有区分力 |
| **CE-4** | #4 `-M ? \| grep -i dadao` | 打印机器表但**不含** dadao 的替身二进制 / 含 `dadao-m1` 的替身 | ✅ 新建 | 替身无 dadao：输出空、grep rc=**1**；替身有：rc=**0**；真实：rc=**0**、输出含描述串 | — | 有区分力 |
| **CE-5** | #5 `ls <dir>/*.c.inc` | 造有/无 `.c.inc` 两个临时目录 | ✅ 新建 | 有 `decode-insn.c.inc` 的目录 **rc=0**；无任何 `.c.inc` 的目录 **rc=2**；任务书路径 **rc=2**；meson 真实路径 **rc=0** | — | glob 判据本身**不是**恒真；**#5 的 FAIL 来自路径写错，不是判据失效** |
| **CE-6a** | #6 checker | 删 `insn.decode` 副本第 19 行 `ld_ub_rd` | ✅ `diff_lines=2` | `错误数: 1` / `ERROR: YAML 有但 decode 缺: ld.ub-rd → trans_ld_ub_rd` / `FAIL` | **1** | 有区分力 |
| **CE-6b** | #6 checker | 第 19 行编码改 1 bit `00010000`→`00010010` | ✅ `diff_lines=4` | `错误数: 1` / `ERROR: mask/value 不匹配: ld.ub-rd (line 19)` / `FAIL` | **1** | 有区分力 |
| **CE-6c** | #6 checker | `opcodes.yaml` 副本第 12 行 `mask '0xFF000000'`→`'0x0000007F'` | ✅ `diff_lines=4` | `错误数: 1` / `ERROR: mask/value 不匹配: ld.ub-rd (line 19)` / `FAIL` | **1** | 有区分力 |
| **CE-6d** | #6 checker | 第 19 行 pattern **改名** `ld_ub_rd`→`ld_ub_rdX` | ✅ `diff_lines=4` | `错误数: 2`，**双向**报 `YAML 有但 decode 缺` + `decode 有但 YAML 缺: ld_ub_rdX (line 19)` / `FAIL` | **1** | 有区分力（双向完整性） |
| **CE-6 回归** | #6 checker | 未改动的副本 | — | `错误数: 0` / `validate_decodetree: PASS` | **0** | 注入未污染基线 |
| **CE-7** | #7 `== 1.11.1` **比较器** | 5 个替身：`1.10.0` / `1.11.0` / `1.12.0` / `11.1.1` / `1.11.1 (malicious)` | ✅ 新建 | 真实 `1.11.1` ⇒ **PASS**；五个替身**全部 FAIL**（无宽松匹配、无前缀匹配） | — | 比较器有区分力；**明确标注：替身只证明「比较器」有牙齿，不替代真实 meson 的 `1.11.1` 实测**（真实值已单独实测） |
| **G1** | 「venv 必须是 3.10.x」硬性前提 | 替身打印 `Python 3.12.14` / `Python 3.11.2` | ✅ 新建 | 真实 `Python 3.10.12` ⇒ **PASS**；两个替身 ⇒ **FAIL → MUST STOP** | — | 前提有牙齿；**本轮未触发停止条件** |
| **CE-8** | #8 相对路径约束 | 同一相对路径在 `/tmp` 下执行 | —（真实环境，无需注入） | 仓库根 `test -x` **rc=0**、`--version` 正常；`/tmp` 下 `test -x` **rc=1**、执行 **rc=127** `No such file or directory` | 0 / 1 / 127 | 约束**真实且必要**（不是恒真） |
| **CE-9** | #9 比较器自身有牙齿 | 复制 23 条 sha 清单，把每条 hash 前 8 位改成 `deadbeef` | ✅ `diff_lines=48` | 被扰动清单：`changed_count=23`（**>0 ⇒ 比较器能发现变化**）；真实前后清单：`changed_count=0` | — | 比较器有区分力 |
| **CE-S0** | S0 `--check` rc=0 | 把 shim `mv` 到 `/tmp`（ pristine 备份 + `trap … EXIT` 兜底） | ✅ `shim present? NO_VALID_removed` | `[FAIL] 可 import tomllib` / `[FAIL] tomllib 来自 shim` / `[FAIL] manifest-check rc=2` / `[FAIL] component-enabled rc=1`；`RESULT: FAILED (3/7 passed)` | **1** | 有区分力 |
| **CE-S4** | S4「无 `is required`」 | 同一二进制省略 `-kernel` / 省略 `-bios` | —（真实环境） | 分别打印 `dadao-m1: -kernel test.bin is required` / `dadao-m1: -bios rom.bin is required`，均 exit=1；真实运行计数 = **0** | 0 vs 1 | **该 0 不是空洞为 0**（第 2 轮的教训已闭合） |

**本轮 0 次空注入**：上表 15 处注入**逐条**打印了 diff 行数或存在性标志，全部非空（`diff_lines` = 6/2/2/4/4/4/48 等，`NO_VALID`）。**如实记录 1 处标签错误并当场改正**：CE-4 初版把 `grep -ic` 写在命令替换里，标签写「real grep rc = 1」实际打印的是**匹配计数 1** 而非退出码；已用 `( set -o pipefail; … ; echo rc=${PIPESTATUS[0]} )` 重测，真实值为 **rc=0**。**该错误标签不计入证据。**

**反例后污染复核（还原证据）**：

```
$ git-clean -C .work/source/qemu status --porcelain=v1 -uall | wc -l
0
$ git-clean -C .work/source/qemu rev-parse HEAD
5c3535f66892868a5829a1b0a242866da6d98e08
$ git-clean -C .work/source/qemu diff --stat ; git-clean -C .work/source/qemu diff --name-only
(空)                    (空)
$ sha256sum .work/source/qemu/target/dadao/insn.decode contracts/opcodes.yaml tools/qemu/validate_decodetree.py
7daf88379573980f5e38edb8164d62c34d0675c27e6243e6c9780c131a65f92b  .work/source/qemu/target/dadao/insn.decode   （= 第 1、2 轮记录值）
9cc5c711d8bad8347a34ba77976dacdb8c2b31868fcc7698dc055cbb3274769e  contracts/opcodes.yaml                          （= 第 1、2 轮记录值）
f0ce306b69801eb7fe8c498918660493f7d8a5fd02eb0f862dad04f6ffdc2566  tools/qemu/validate_decodetree.py              （= 第 2 轮记录值）
```

⇒ 源码树 tracked 文件 dirty 仍为 **0**、`git diff` 空、HEAD 未变、三个关键文件 sha256 与前两轮**逐字节一致**。

**CE-S0 还原证据（宿主）**：

```
注入前 live sha256 = 84ba9296fcf6ceaa0dbcd4e8371fb80d253b8a875277c66c687b48f1b8061ec4
注入后（trap 触发）  = 84ba9296fcf6ceaa0dbcd4e8371fb80d253b8a875277c66c687b48f1b8061ec4   ← 一致
$ python3 tools/infra/install_tomllib_shim.py --check   →  RESULT: OK (7/7 passed)   rc=0
$ .work/build/qemu/qemu-system-dadao --version | head -1 →  QEMU emulator version 11.1.1 (v11.1.1-8-g5c3535f)
$ .work/build/qemu/qemu-system-dadao -M ? 2>&1 | grep -i dadao → dadao-m1 …  rc=0
$ make manifest-check                                     →  manifest validation: PASS   rc=0
```

**本任务全程无需重建**（反例只动了 `/tmp` 副本与宿主 shim，**从未改 `.work/source/**`、从未改 `contracts/`**；构建产物是在干净源码上一次性生成的，此后未被任何注入影响）。

### git status 前后对比结论（#9，全量无抽样）

```
$ git-clean -c core.quotepath=false status --porcelain=v1 -uall | sha256sum
139e3b5a306ca1d36b2cbb1161b65907c28a4e745de31b9aec522caf48029bad   （执行后）
139e3b5a306ca1d36b2cbb1161b65907c28a4e745de31b9aec522caf48029bad   （下发基线 dispatch/git-status.round3）
>>> status 逐字节相同（23 路径，0 差异）
```

- **23/23 逐路径内容 sha256 全量比对**（`join -j2 | awk '$2!=$3'`）：填完成区前 `changed_count = 0`。
- 相对**原始 21 路径**基线（`dispatch/dirty-content-sha256.before`）：**changed = 1**，即 `.xkw/knowledge/deferred.md`（`131ab84d…`→`6b4e73e6…`），**正是 `authorized-delta` #3，且是主会话在下发前改的，本轮零改动**；其余 **20** 条内容 sha256 全部不变。
- 相对原始基线**新增 2** 条：任务书（#1）与 `tools/infra/install_tomllib_shim.py`（#2），**下发时即已存在**，非本轮新增。
- **丢弃 0** 条。
- 填完本完成区后**唯一被允许的变化**是任务书自身 sha256（见文末「回填后复核」）。

**明确声明**：本轮只写了 (a) 任务书 746 行起的完成区，(b) `.work/build/qemu/**`（gitignored），(c) `.work/log/infra/INFRA-106t-*.log`（gitignored），(d) `/tmp/opencode/INFRA-106t/**`，(e) `~/.local/lib/python3.10/site-packages/`（S0 批准的宿主改动，且本轮为**幂等跳过**，只因 CE-S0 反例被短暂移动并已按 sha256 复原）。**其余路径 0 改动**；未 commit、未 push、未 `git add/stash/checkout/clean`、未改状态行、未动 `Makefile`/`configure` 参数/`-j`。

### 本任务在仓库内新增/修改的路径（全部在白名单内）

- `.work/build/qemu/**`（846M：二进制、venv、`libqemu-dadao-softmmu.a.p/decode-insn.c.inc`、ninja 产物）——`.gitignore` 忽略。
- `.work/log/infra/INFRA-106t-s0-tomllib-shim.log`、`-s0b-tomllib-shim-check.log`、`-s1-script.sh`、`INFRA-106t-build-qemu.log`、`-s2-machinetype.log`、`-s3-decodetree.log`、`-s4-version.log`、`-s5-probe-paths-and-tree.log`、`-s6-counterexamples.log`。
- **本任务书「完成区」第 746 行之后**（唯一被修改的仓库文件）。

**必须披露的一处真实副作用（`.work/source/**` 虽被任务书列为只读）**：`configure`/meson 的 wrap 机制在构建时向源码树写入了**被 qemu 仓库自身 gitignore 的**内容——`subprojects/{berkeley-softfloat-3,berkeley-testfloat-3,keycodemapdb}/`（6.5M）、`subprojects/.wraplock`、`python/qemu.egg-info/`（editable 安装产物）、若干 `__pycache__/*.pyc`。实测 `git check-ignore -v subprojects/keycodemapdb` → `subprojects/.gitignore:6:/keycodemapdb` ⇒ **全部被忽略**，`status --porcelain -uall` 仍为 **0 行**、`diff --name-only` 仍**空**、HEAD 未变。**这不是手工改源码，而是任何一次真实 QEMU 构建的必然产物**；我未对其做任何编辑，也未绕过它。

`.tao/`、`manifests/`、`Makefile`、`contracts/`、`tools/`（`install_tomllib_shim.py` 除外，且本轮**未改**）、`.xkw/knowledge/`（`deferred.md` 本轮**未改**）、其它 `.xkw/tasks/**` **一个字节都没改**。

### 与任务书的偏差（如实记录，未改判据、未改测试基线）

| 编号 | 位置 | 任务书写法 | 实测 | 处置 |
| --- | --- | --- | --- | --- |
| **D1** | S3 步骤、验收 #5 | 判据路径 `.work/build/qemu/target/dadao/*.c.inc`（并注「由 meson 在本阶段生成……**这是 `INFRA-104t` 之后的产物，属本任务门禁**」） | meson 把 `decodetree.process()` 输出放进**消费方静态库 private 目录** `libqemu-dadao-softmmu.a.p/decode-insn.c.inc`（84585 B）；构建树 `target/` 整棵树 **0** 文件 | **#5 记字面 FAIL（ls rc=2）**，同时给出产物真实位置与 `build.ninja` 证据。**缺陷类别与 B1 相同**（正确构建必然 FAIL 的判据）。**我未改判据**，建议主会话按 B1 的先例登记为 B19 并修订路径 |
| **D2** | S1 耗时预估 | 「**耗时预估 15–30 min**（4 核）」 | 实测 **144 秒** | 偏差对任务书有利（预估偏保守），不影响任何判据，仅记录 |
| **D3** | 验收 #8 | 「9 个探针用相对路径 ⇒ 须从仓库根执行」（隐含「探针存在」） | 9/9 常量确为相对路径，但**探针脚本本身本轮未执行**（执行属 `QEMU-005t`…`QEMU-013t`/`022t` 已完成任务范围） | #8 只判「路径约定成立且该路径当前可执行」，**不构成任何语义证据**；如实标注 |

### 停下等待用户确认的事项

**无。** 本轮 S0–S4 全部按任务书执行完毕，未触发 6 条「必须停下报告」中的任何一条（S0 rc=0；构建未再报 `tomllib`/`setuptools`/`distutils`；`pyvenv` 为 3.10.12；`oom_kill`=0；构建报错未指向 DADAO 补丁；无 S0 之外的 `pip install`、无改 `configure` 参数、无改 `-j`）。

**需主会话裁决的一项（不是停止条件，是判据缺陷）**：**D1 / 验收 #5 的路径**。我的处置是「如实记 FAIL + 给出产物真实位置证据」，**不自行改判据**。若主会话按 B1 先例把 #5 判据路径改为 `libqemu-dadao-softmmu.a.p/decode-insn.c.inc`（或改为「`find` 到 `decode-insn.c.inc` 且含 ≥1 个 `trans_` 符号」），则 #5 可转 PASS；**该修订属任务书范围，须由主会话执行**。

### 遗留 / 风险

- **能力缺口（非本任务可解）**：验收 #10 语义正确性（747 用例）**保持 BLOCKED**，属 `INTEG-101t`。
- **交给 `INTEG-101t` 的真实观察（本轮新发现）**：`-M dadao-m1 -bios <8B零> -kernel <8B零> -display none -nographic` 跑出 monitor 提示符后以 **SIGFPE（exit 136）** 结束。8 字节全零 ROM 的执行结果按任务书不属本任务判据，但这是**首次取得的运行侧信号**，`INTEG-101t` 的 E2E 冒烟**应把它当作第一个要查的现象**（可能与 `translate.c` 对 `0x00000000` 的处理或 CPU 复位路径有关，**本轮未做任何排查，未改任何代码**）。
- **判据缺陷**：D1（验收 #5 路径写错），待主会话修订。
- **B10 未处置项仍在**：`INTEG-101t:114` 的陈旧 `dadao-m`（本轮再次实测确认真值是 `dadao-m1`，证据在 S2 段），越界未改。
- **方案 C 是绕过不是消除**：`Makefile` 单一 `$(PYTHON)` 服务互斥需求的缺陷仍在，已登记 `.xkw/knowledge/deferred.md`（本轮**未改**该文件）。S0 依赖 `~/.local` 的持久性：若该目录被清理，需重跑 `install_tomllib_shim.py`（幂等、秒级）。
- **构建依赖网络**：`configure` 阶段从 gitlab 拉了 `keycodemapdb` 等 3 个 subproject。离线环境重建需另行准备（`INFRA-103t` 镜像议题的延伸，本次未处置）。
- OOM 风险本轮**未触及**（`MemAvailable` 最低 1365028 kB，`oom_kill`=0，`-j4` 原样使用未改）。

### 主会话补记（2026-09-26，engineer 报告后独立复核）

**结论：接受第 3 轮执行结果。构建真实成功（`build-qemu_rc=0`、144 s、2359/2359 ninja 步），验收 8 PASS / 1 PASS（B19 更正后 #5 由 FAIL 转 PASS）/ 1 BLOCKED（#10 属 `INTEG-101t`）。**

engineer 的处置**正确且可核查**：对 #5 **拒绝改判据**、如实报 FAIL 并给出真实产物位置；对 `-j4`、宿主 Python、`manifests/` 均未擅动。**未见任何虚报**。

#### 独立复核（不采信子代理自报，逐项亲自重跑）

| 验收 | 主会话亲自执行的命令 | 真实结果 | 结论 |
| --- | --- | --- | --- |
| #1 | `grep 'build-qemu: PASS\|build-qemu_rc=' .work/log/infra/INFRA-106t-build-qemu.log` | 3011 行 `build-qemu: PASS`、3012 行 `build-qemu_rc=0`；日志 3012 行 | **PASS** |
| #2 | `grep -c 'refusing to fake success'  构建日志`；再把 `lock.toml` 的 qemu 置 `enabled=false` **真跑** `make build-qemu` | 日志中计数 **0**；注入后 `rc=2` 并打印 `refusing to fake success`（反例 **K**）⇒ 守卫**实质性**、非空转 | **PASS** |
| #3 | `ls -l` + `test -x` | `-rwxrwxr-x 34832720 B`，可执行 ✅；ELF 64-bit LSB pie | **PASS** |
| #4 | `.work/build/qemu/qemu-system-dadao -M ? \| grep -i dadao` | `dadao-m1             DADAO M1 bare-metal test machine` | **PASS** |
| #5 | 见下方「B19/B20 更正后的判据」 | 3/3 PASS，**4 条反例全部 rc=1 且与真实输出不同** | **PASS**（原判据下 FAIL） |
| #6 | `python3.12 -B tools/qemu/validate_decodetree.py … insn.decode contracts/opcodes.yaml` | `rc=0`，256/256、错误 0，`validate_decodetree: PASS` **恰 1 行** | **PASS** |
| #7 | `pyvenv/bin/meson --version` / `pyvenv/bin/python --version` | `1.11.1` / `Python 3.10.12`；`pyvenv.cfg`: `version = 3.10.12`、`include-system-site-packages = true` | **PASS** |
| #8 | 逐个 grep 9 个 `tools/qemu/min_rom_probe_*.py` 的二进制引用 | 全部为相对路径 `.work/build/qemu/qemu-system-dadao`，从仓库根可解析 ✅ | **PASS** |
| #9 | 23 路径**全量**逐路径 sha256 比对 | 见下方「基线」 | **PASS** |
| #10 | —— | 语义正确性 | **BLOCKED**（属 `INTEG-101t`，本任务不构成任何语义证据） |
| S0 幂等 | 复跑 `install_tomllib_shim.py` | `tomli 已安装，跳过` / `已是目标内容，跳过` ⇒ **本轮 0 次 pip install**；`--check` 7/7；shim sha256 `84ba9296…` 与主会话验证阶段一致 ⇒ **构建未破坏 shim** | **PASS** |

**两处我复核不到、经查是我自己路径猜错，engineer 说法正确**：

1. `RESOLVED_PYTHON=[python3]` **不在构建日志里** —— 它来自**独立探针 makefile**（`/tmp/opencode/INFRA-106t/r3/probe.mk`，完成区 825 行），是我搜错了文件。任务书 S1 块**确实没有也不该有** `PYTHON=` 覆盖。
2. `qemu.egg-link` 不在 `.work/source/qemu/python/` —— 实际在 `.work/build/qemu/pyvenv/lib/python3.10/site-packages/qemu.egg-link`；`pyvenv/bin/python -c 'import qemu'` → `OK`。**engineer 表述无误。**

**方案 C 两个前提均成立**：`manifest validation: PASS` 出现在构建日志第 3 行（证明 `Makefile:30` 的 `component-enabled` 真跑了 `tomllib.load` 并放行）；`BackendUnavailable` 出现 **0** 次。

#### B19/B20 更正后的判据（`/tmp/opencode/INFRA-106t/dispatch/acc5.sh`）

真实运行 **rc=0 / 3 PASS**：`build.ninja` 规则 = `libqemu-dadao-softmmu.a.p/decode-insn.c.inc`；产物 84585 B；`trans_` 符号 **512** 个。

| 反例 | 注入 | rc | 命中 FAIL | 与真实输出不同？ |
| --- | --- | --- | --- | --- |
| **G'** | 产物截为 **0 字节** | **1** | `产物为 0 字节` + `trans_ 符号仅 0` | ✅ 有区分力 |
| **H'** | 产物内容换成无 `trans_` 的占位文本 | **1** | `trans_ 符号仅 0` | ✅ 有区分力 |
| **J** | 产物整个移走 | **1** | `产物不存在` + `trans_ 符号仅 0` | ✅ 有区分力 |
| **I'** | 从 `build.ninja` 抹掉该规则（diff 非空已确认） | **1** | `无 CUSTOM_COMMAND 规则` + `trans_ 符号仅 0` | ✅ 有区分力 |
| 复原后回归 | —— | **0** | 3 PASS | —— |

> **B20 的实录**：我第一版判据把 `build.ninja` 抓到的相对路径**当绝对路径**用，导致**在完全正确的构建上就报假 FAIL**（`产物不存在`）；更严重的是反例 G/H 的输出与真实运行**逐字相同** ⇒ **无区分力的空证据**，只看「rc≠0」会被误当成反例成功。是「**反例输出必须与真实输出不同**」这条自检把它抓出来的。此条已登记为 B20，并写入 S3 块与验收 #5。

#### 基线复核（全量，不抽样）

- 仓库根 `master` @ `69a596798b69bfeb62a0f4b901fc4993f033cd77`；**23 路径**，`git status` sha256 `139e3b5a306ca1d36b2cbb1161b65907c28a4e745de31b9aec522caf48029bad`，与本轮下发时**逐字节相同**。
- 相对**原始 21 路径**基线：内容变化**仅 1 条** = `.xkw/knowledge/deferred.md`（= `authorized-delta` #3，主会话登记 `Makefile` 根因时改的）；**消失路径 0**。
- 两棵源码树：`.work/source/qemu` HEAD 仍 `5c3535f66892868a5829a1b0a242866da6d98e08`、**tracked dirty = 0**；`.work/source/llvm-project` dirty = 0。engineer 披露的 31 项 `!!` 均为构建副产物（`python/qemu.egg-info/`、`scripts/qap` 等），在 `.gitignore` 内、**不污染 tracked 内容**。
- 任务书：engineer 只在第 3 轮完成区（746 行起）之后写入；**前 750 行**（含第 1、2 轮全部记录）**逐字节未动**。本节的 B19/B20 更正由主会话执行，同样只在完成区**之前的「修正记录」段**与 S3/验收表内，未触碰任何历史完成区。

#### S4 的 SIGFPE：主会话独立复现，确认**不是**本任务判据，但须转交

engineer 报 `-M dadao-m1 -bios <8B零> -kernel <8B零>` 退出码 **136（128+8 = SIGFPE）**。主会话复现：

| 探针 | 退出码 | 输出 | 说明 |
| --- | --- | --- | --- |
| **8 字节** ROM（`smoke-dadao-m1.sh:34` 的做法） | **136** | `QEMU 11.1.1 monitor … (qemu)`，进到 monitor 后 SIGFPE | 与 engineer 完全一致 |
| **0 字节** ROM | **1** | `could not load ROM image …: empty file` | 另一个数据点，ROM 加载前即被拒 |

S4 判据只要求「不出现 `is required` 参数错误」—— 两种情形均为 **0 次** ⇒ **PASS**。engineer 另做了 3 组阳性对照（省 `-kernel` / 省 `-bios` / 乱写机器名）均正确报 `is required` / `unsupported machine type`，证明该判据可达 FAIL。

**SIGFPE 的性质**：机器**已启动**、monitor 已出现，之后才异常 ⇒ 属**零内容程序下的 CPU 状态异常**，**不是**构建缺陷、**也不是**参数问题。本任务不据此下任何语义结论，已转交 `INTEG-101t`。

#### 状态转换

- `待开始` → **`待验收`**（主会话据上述复核结果设定；engineer 无权改状态行）。
- 剩余动作：`/complete` 走 reviewer 独立验收（`workflow.md` §11）。

### reviewer 独立验收记录（2026-09-26，主会话**代行 reviewer**，用户指定；**未走 architect 交叉复核**）

> 用户 2026-09-26 明确指示：「接下来由你代行 review，通过后直接填入已验证即可，不用 architecture 复核。」
> 本节按 `workflow.md` §11.2 逐条执行；§11.3（architect）**依用户指示跳过**，此为**已知的流程偏离**，在此登记以便追溯。

**结论：`Accepted`。**

#### §11.1-2 审查前三件套（`/tmp/opencode/INFRA-106t/reviewer/baseline/`）

| 件 | 路径 | 结果 |
| --- | --- | --- |
| (1) `git status` 原文 | `baseline/git-status.before` | 23 路径 |
| (2) **每条 dirty 路径的内容 sha256** | `baseline/dirty-content-sha256.before` | 23 条（**缺此项即前置未完成**） |
| (3) 任务书全文副本 | `baseline/task-book.before.md` | 1151 行 / 111974 B / sha `9ddb60e8…` |

#### §11.1-3 审查后逐字节比对 —— **baseline 未变**

| 项 | 结果 |
| --- | --- |
| (1) `git-status.before` vs `.after` | **逐字节相同 = True**（23 路径） |
| (2) 逐路径内容 sha256 | 变化 = **无**；新增 = **无**；消失 = **无** |
| (3) 任务书 before vs after | **逐字节相同 = True**（111974 B，sha `9ddb60e8…`） |

⇒ 未触发 §11.1-3 的「结论整体作废」条件。源码树 `.work/source/qemu` HEAD `5c3535f6…`、`llvm-project` HEAD `a5c3a444…`，**tracked dirty 均为 0**。

#### §11.2-1 检查器全量枚举（12 个）与逐项反例

`checker-inventory.txt` 落盘于 `reviewer/evidence/`。**每个检查器都由 reviewer 亲自注入反例**，不采信 engineer 汇报数字：

| # | 检查器 | 真实 rc | reviewer 注入的反例 | 反例 rc | 结论 |
| --- | --- | --- | --- | --- | --- |
| **C1** | `build-qemu: PASS` + `build-qemu_rc=0` | 0 | **R1** 日志替换为失败轮尾部 | **1** | 有牙齿 |
| **C2** | 无 `refusing to fake success` | 0 | **R2** 往日志追加该串 ／ **K** 真跑 `make build-qemu` + disable qemu | **1** ／ **2** | **守卫实质性**（非空转） |
| **C3** | `test -x` 二进制 | 0 | **R3** `chmod -x` | **1** | 有牙齿 |
| **C4** | `-M ?` 含 `dadao-m1` | 0 | **R4'** 替身输出含**陈旧名 `dadao-m`** ／ 空列表 | **1** ／ **1** | 能区分 `dadao-m` vs `dadao-m1` |
| **C5** | decodetree 产物（B19/B20 更正后） | 0 | **R5a** `trans_` 削到 **255**（恰低于阈值） | **1** | 单点边界有牙齿 |
| **C6** | `validate_decodetree.py` | 0 | **R6a'** 改 1 条编码 ／ **R6b'** 删 1 条（256→255）／ **R6c** yaml mask 改 1 位 ／ **R6d** 改 1 条名字 | **1** ×4 | 4 类错误均可达 |
| **C7** | `meson --version == 1.11.1` | 0 | **R7** 只改期望值为 `1.11.2` | **1** | 比较器敏感 |
| **C8** | 9 个 probe 用仓库相对路径 | 0 | **R8** 把 `022t` 改成 `/nonexistent/…` | **1** | 有牙齿 |
| **C9** | 23 路径全量 sha256 | 0 | 本轮注入 3 个文件后逐一比对 | 全部复原 ✅ | 不抽样 |
| **C10** | S4 无 `is required` | 0 | **阳性对照 A/B/C** 省略 `-kernel` / `-bios` / 两者 | **1** ×3 | 可达 FAIL |
| **C11** | `install_tomllib_shim.py --check` | 0 | （主会话验证阶段已做 5 条反例，全 rc=1） | 1 ×5 | 有牙齿 |
| **C12** | 源码树 tracked dirty == 0 | 0 | — | — | 事实核对 |

C10 另设 2 组**反向对照**以确认判据不误判：机器名不存在（`unsupported machine type`）rc=0、0 字节 ROM（`empty file`）rc=0 ⇒ 判据**只惩罚「缺必填参数」**，范围正确。

#### §11.2-3 「恒真断言 / 两支同结果 / 覆盖脚本不读输入」全文件排查

对 engineer 的反例脚本 `/tmp/opencode/INFRA-106t/r3/ce.sh`（142 行）做模式扫描：

- 恒真断言模式（`check(..., True)` / `[ 1 -eq 1 ]` / `assert True`）—— **0 处**
- 两支同结果 —— **0 处**；`check1()` 的 `PASS`/`FAIL` 两支异值（`ce.sh:17`）
- 覆盖脚本是否真读输入 —— `grep -c` 的 4 个目标（`build-qemu: PASS`、`build-qemu_rc=0`、`is required`、`refusing`）**全部是真实被读取的文件内容**，非存在性代替语义
- 空注入防护 —— CE-1b / CE-2 / CE-6a–d **逐条打印 `diff_lines` 与 `diff_empty`**，`YES_VOID`/`NO_VALID` 标记制度到位
- `ce.sh:119`/`123` 的 `[ … ] && PASS || FAIL`、`ce.sh:128` 的 `case "Python 3.10."*` —— 均为**两支异值**且 glob 正确，无分支极性错误

**⇒ 未发现 §11.2-3 所列同类缺陷。**

#### §11.2-9 数据/期望值类：本任务的 size/sign 敏感项

本任务**不产出数据/期望值**（无向量表、无算术结果），产物是**二进制 + 构建日志**。唯一「期望值」是 `meson == 1.11.1`（字符串等值，已由 R7 证敏感）与 `trans_ >= 256`（整数阈值，已由 R5a 在 255/256 边界证敏感）。**AGENTS.md 的「逐条独立重算」要求在此不适用**，但两个阈值均已做边界注入。

#### reviewer 新发现的一处真实弱点 → **B21**

`ce.sh:67` 的 CE-5 正例用 `: > …/decode-insn.c.inc` 造的是 **0 字节**文件。这暴露出**旧 #5 判据有两处独立缺陷**，而不只是路径错：

| | 缺陷 | 证明 |
| --- | --- | --- |
| B19 | 路径错（`target/dadao/` vs meson 私有目录） | 正确构建下 `ls` rc=2 |
| **B21** | **判据过弱**：`ls <dir>/*.c.inc` 只验**存在性**，**0 字节空产物同样 PASS** | reviewer 造 0 字节替身 → **旧判据 rc=0** |

⇒ **B19/B20 的修正同时关闭了两者**：新判据要求「`build.ninja` 记录路径 + 文件**非空** + `trans_ >= 256`」，对同一 0 字节替身 **rc=1**（命中 `产物为 0 字节` 与 `trans_ 符号仅 0` 两项）。若当初只改路径而不加「非空 + 符号数」，#5 仍会被空产物骗过。

**已登记 B21，判据现状（`S3` 块 + 验收 #5）已包含该加严，无需再改。**

#### reviewer 自身的三处失误（如实记录，均当场改正后重做）

1. **C6 的 R6a 是空注入**：我用的正则 `^[0-9A-Fa-f]{8}\s` 与 `insn.decode` 真实格式（`name  <32位binary>  @field`）不匹配，**文件未被改动**，退出码自然是 0。**作废**，改用 `^([a-z][a-z0-9._]*)\s+([01.]{32})\s+(@\S+)?` 重做为 R6a'。
2. **C6 的 R6b 误删全部 256 条**（同一正则问题），并非「删 1 条」的单点边界测试。**作废**，重做为 R6b'（256→255）。
3. **C10 的阳性对照 A/B 假通过**：我用 `-kernel ""`（空串）代替「省略该 flag」，而空串**仍算提供了该选项** ⇒ 判据 rc=0。**作废**，改用真正的参数省略（`"$@"` 数组）重做，A/B/C 全部 rc=1。
4. **C4 的第一版反例不合格**：只测了 `grep` 自身，没构造能让**被判形式** FAIL 的输入。**作废**，改用「替身输出含陈旧名 `dadao-m`」重做为 R4'。

> 这四处与 B20 同源：**反例的「构造手法」本身有缺陷时，反例无效**。四者均由「反例输出必须与真实输出不同」或「必须真省略/真改动」的自检抓出。**已把「反例 rc≠0 **且** 输出与真实运行不同」固化为本任务的反例有效性双条件。**

#### 验收 10 项最终结论（reviewer 独立判定）

| # | 判据 | 结论 | reviewer 依据 |
| --- | --- | --- | --- |
| 1 | `build-qemu` 成功 | **PASS** | C1，rc=0；反例 R1 rc=1 |
| 2 | 未假成功 | **PASS** | C2；守卫经反例 K 证明**实质性** |
| 3 | 二进制就位 | **PASS** | C3，34832720 B 可执行；反例 R3 rc=1 |
| 4 | 机器类型注册 | **PASS** | C4，`dadao-m1`；反例 R4' 能区分陈旧名 |
| 5 | decodetree 产物 | **PASS** | C5（B19/B20/B21 更正后），R5a 边界 rc=1 |
| 6 | decodetree 源完整 | **PASS** | C6，rc=0 + PASS 恰 1 行；4 类反例 rc=1 |
| 7 | meson 锁定版 | **PASS** | C7，`1.11.1`；venv `Python 3.10.12` |
| 8 | probe 相对路径 | **PASS** | C8，9/9；反例 R8 rc=1 |
| 9 | 仓库零改动 | **PASS** | C9，23 路径全量、审查前后逐字节相同 |
| 10 | 语义正确性（747 用例） | **BLOCKED** | 属 `INTEG-101t`；本任务**不构成任何语义证据** |

**9 PASS / 1 BLOCKED。#10 保持 BLOCKED 是正确处置，不得以任何构建/结构证据替代。**

#### 未处置项（不影响本任务结论，已登记）

- `Makefile:8` 单一 `$(PYTHON)` 互斥 —— 方案 C 只是**绕过**，已登记 `deferred.md`
- QEMU `configure` 需联网拉 3 个 subproject —— 已登记
- 零内容 ROM → SIGFPE(136) —— 已登记，转 `INTEG-101t`
- `INTEG-101t:114` 陈旧 `dadao-m` —— 已登记，派发前须改
- `INFRA-105t` S3 第 7 项判据过弱（`find … -print -quit` 不区分文件/目录）—— **用户尚未裁决**，不在本任务范围
