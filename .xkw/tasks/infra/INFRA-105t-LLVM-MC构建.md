# INFRA-105t: LLVM MC 构建

**模块**：infra
**项目里程碑**：M1 复现
**状态**：待开始
**日期**：2026-09-25
**依赖**：`INFRA-104t`
**解决阻塞**：B7（内存仅 3 GiB）
**决策依据**：`.xkw/knowledge/adr-1001-m1-reproduction-infra.md` D1

## 目标

构建 `llvm-mc` 及其配套工具，使 M1 的 LLVM 侧验收（lit 字节 oracle、MC lit 套件、instrinfo 校验）具备运行条件。

**本任务不改动仓库任何文件**（`.work/build/` 被 `.gitignore` 忽略）。

## 背景：本任务的最大风险是内存

宿主实测：**4 核 / 3 GiB RAM（可用约 1 GiB）+ 20 GiB swap**。`Makefile:80-87` 的 `build-mc` 用 `RelWithDebInfo` + assertions，`ninja` 默认并行度为 `nproc + 2 = 6` ⇒ 并行链接 6 个 RelWithDebInfo 目标极易 OOM（swapper 抖动，构建可能从 60 分钟拖到数小时甚至被杀）。

`Makefile` 的 cmake 参数是**硬编码**的（无 `?=` 旋钮可加参数），而 AGENTS 约定 Makefile 是稳定接口。**解法**：先手动执行一次**逐字相同**的 cmake 命令、只多加两个降内存参数预置 CMake cache；之后 `make build-mc` 会复用该 cache（`-D` 设置的 cache 项不会被后续 configure 覆盖），**命令记录仍是 `make build-mc`**。

## 范围

**在范围内**：预置 CMake cache、`make build-mc`、产物清点、`llvm-lit` 可用性探测。

**不在范围内**：修改 `Makefile`、构建 clang/LLVM 后端（`LLVM_ENABLE_PROJECTS=""` 已限制）、`INTEG-101t` 的 lit 执行。

## 步骤

### S1 — 预置 CMake cache（降内存）

```bash
cd /home/ubuntu/DADAO-v5
cmake -G Ninja -B .work/build/llvm -S .work/source/llvm-project/llvm \
  -DLLVM_TARGETS_TO_BUILD=DADAO \
  -DLLVM_ENABLE_PROJECTS="" \
  -DCMAKE_BUILD_TYPE=RelWithDebInfo \
  -DLLVM_ENABLE_ASSERTIONS=ON \
  -DLLVM_USE_LINKER=lld \
  -DLLVM_PARALLEL_LINK_JOBS=1 2>&1 | tee .work/log/infra/INFRA-105t-cmake.log
```

**与 `Makefile:81-85` 的差异只有最后两个 `-D`**，其余逐字相同（逐条比对，不得擅自改动）。理由：

| 追加参数 | 作用 | 依据 |
| --- | --- | --- |
| `-DLLVM_USE_LINKER=lld` | lld 峰值内存显著低于 GNU ld / gold | `lld` 包由 `INFRA-102t` S1 装 |
| `-DLLVM_PARALLEL_LINK_JOBS=1` | 链接阶段串行，绕开 3 GiB 内存上限 | ninja 默认并行度 6 |

**若 configure 失败**（常见于 `libzstd`/`zlib` 缺失或 C++ 编译错误），按序预案：

1. 确认 `zlib1g-dev libzstd-dev` 已装（`INFRA-102t`）
2. 换编译器重配：`-DCMAKE_C_COMPILER=gcc-12 -DCMAKE_CXX_COMPILER=g++-12`（宿主默认 gcc 11.4 理论达标——LLVM 23 的 `LLVM_REQUIRED_CXX_STANDARD` = 17、`GCC_MIN` = 7.4；gcc-12 是退路而非首选）
3. 仍失败则改用 `clang-14`（`INFRA-102t` 已装）

**换编译器必须删除旧 cache**：`rm -rf .work/build/llvm` 后重来（否则 `CMAKE_CXX_COMPILER` 会被 cache 锁定，改了不生效）。

### S2 — 构建

```bash
make PYTHON=python3.12 build-mc 2>&1 | tee .work/log/infra/INFRA-105t-build-mc.log
```

`Makefile:86` 的 ninja 目标为：`llvm-mc llvm-objdump llvm-objcopy llvm-readobj FileCheck not LLVMDADAOCodeGen`。

**耗时预估 40–90 min**（4 核 / 3 GiB 内存，内存受限下偏上限）。

### S3 — 产物清点

```bash
for t in llvm-mc llvm-objdump llvm-objcopy llvm-readobj FileCheck not; do
  test -x .work/build/llvm/bin/$t && echo "OK   $t" || echo "MISS $t"
done
ls -d .work/build/llvm/lib/Target/DADAOCodeGen 2>/dev/null || \
  find .work/build/llvm -name "*DADAO*" -maxdepth 4 | head
```

7 个目标全部 `OK` 才算通过（`llvm-lit` 单独探测，见 S4）。

### S4 — 探测 `llvm-lit`（**非门禁，但必须记录**）

`Makefile:86` 的 ninja 目标列表**不含 `llvm-lit`**，而 `tests/lit/*/lit.cfg.py:28-30` 优先读 `config.llvm_tools_dir`（`llvm-lit` 才会设），其次 `LLVM_TOOLS_DIR` 环境变量。

```bash
test -x .work/build/llvm/bin/llvm-lit && echo "llvm-lit 存在" || echo "llvm-lit 缺失（预期，Makefile 不构建它）"
ls .work/source/llvm-project/llvm/utils/lit/lit.py   # 备选入口，应存在
```

若缺失，二选一（**优先第一项**，零仓库改动）：

1. `ninja -C .work/build/llvm llvm-lit`（生成物，仍不改动仓库）
2. `LLVM_TOOLS_DIR=.work/build/llvm/bin python3 .work/source/llvm-project/llvm/utils/lit/lit.py <测试目录>`

> `llvm-lit` 本身只是 `llvm/utils/lit/lit.py` 的 wrapper，两者**行为等价**；`lit.cfg.py` 也支持 `LLVM_TOOLS_DIR` 回退。`INTEG-101t` 须记录实际采用哪一条。

### S5 — 冒烟（不属验收，仅提前暴露路径问题）

```bash
.work/build/llvm/bin/llvm-mc --version
.work/build/llvm/bin/llvm-mc --triple=dadao-unknown-elf -filetype=obj \
  -o /tmp/opencode/INFRA-105t/smoke.o tests/lit/MC/Dadao/basic-encoding.s && echo "obj ok"
```

## 验收

| # | 项 | 判据 | 状态 |
| --- | --- | --- | --- |
| 1 | `build-mc` 成功 | 日志末行 `build-mc: PASS`，exit 0 | 现在可跑 |
| 2 | 未假成功 | Makefile 的 `component-enabled` 守卫未触发（未出现 `refusing to fake success`） | 现在可跑 |
| 3 | 6 个工具就位 | `llvm-mc`/`llvm-objdump`/`llvm-objcopy`/`llvm-readobj`/`FileCheck`/`not` 全部可执行 | 现在可跑 |
| 4 | DADAO 后端已构建 | `LLVMDADAOCodeGen` 目标产物存在（`find` 可见） | 现在可跑 |
| 5 | 三元组已注册 | `llvm-mc --version \| grep -i dadao` **无输出**（非 LLVM 核心 target，不出现在 version 串）；`llvm-mc --triple=dadao-unknown-elf` 不报 unknown triple | 现在可跑 |
| 6 | cache 预置生效 | `grep -E "LLVM_USE_LINKER\|LLVM_PARALLEL_LINK_JOBS" .work/build/llvm/CMakeCache.txt` 显示 `lld` 与 `1` | 现在可跑 |
| 7 | 汇编冒烟 | S5 的 `obj ok` 出现 | 现在可跑 |
| 8 | `llvm-lit` 入口确定 | S4 已记录采用哪条路径 | 现在可跑 |
| 9 | 仓库工作区零改动 | `git status --porcelain` 与执行前逐字节相同 | 现在可跑 |
| 10 | MC lit 套件全绿 | —— | **BLOCKED**（属 `INTEG-101t`；替代证据：本任务验收 3/5/7 已证 `llvm-mc` 可用且 DADAO 后端可驱动） |
| 11 | 内存未耗尽 | 构建全程无 OOM kill（`dmesg`/退出码 137 检查） | 现在可跑 |

## 风险与预案

| 风险 | 预案 |
| --- | --- |
| **OOM（最可能）** | 已用 `LLVM_PARALLEL_LINK_JOBS=1` 缓解。若仍被杀：① 追加 `-DBUILD_SHARED_LIBS=ON`（显著降链接内存，代价是运行需 `LD_LIBRARY_PATH`）；② 或再加 swap（`/mnt` 有 186 GB 空间，可建 8–16 GiB swapfile）。**两者都改变构建配置，须先经用户确认** |
| 构建耗时超预期 | 内存受限下 40–90 min 属正常区间；超过 3 h 须停下来查是否在 swap 里打转（`vmstat 1` 观察 `si/so`） |
| lld 缺失 | `INFRA-102t` 已装；缺失则去掉 `-DLLVM_USE_LINKER=lld` 重配（内存风险上升） |
| `LLVM_ENABLE_PROJECTS=""` 下 DADAO target 未进 `LLVM_ALL_TARGETS` | 补丁 `0001`/`0002` 正是为此而加；若 `ninja` 报 unknown target `LLVMDADAOCodeGen`，回查 `INFRA-104t` 验收 6 |

## 完成区

（待执行后填写：configure 与 `build-mc` 真实输出、耗时、峰值内存观测 + 上述 11 项逐条结论）
