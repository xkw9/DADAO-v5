# INFRA-105t: LLVM MC 构建

**模块**：infra
**项目里程碑**：M1 复现
**状态**：已验证
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

以**脚本**方式执行（workflow §10.2.5：必须保存真实 pipeline 退出码；裸 `| tee` 只能拿到 `tee` 的退出码，`pipefail` + `PIPESTATUS[0]` 才拿到 cmake 的。子 shell 包裹以免 `exit` 关掉调用方会话）：

```bash
cd /home/ubuntu/DADAO-v5
( set -o pipefail
  { cmake -G Ninja -B .work/build/llvm -S .work/source/llvm-project/llvm \
      -DLLVM_TARGETS_TO_BUILD=DADAO \
      -DLLVM_ENABLE_PROJECTS="" \
      -DCMAKE_BUILD_TYPE=RelWithDebInfo \
      -DLLVM_ENABLE_ASSERTIONS=ON \
      -DLLVM_USE_LINKER=lld \
      -DLLVM_PARALLEL_LINK_JOBS=1; } 2>&1 | tee .work/log/infra/INFRA-105t-cmake.log
  rc=${PIPESTATUS[0]}
  echo "cmake_rc=$rc" | tee -a .work/log/infra/INFRA-105t-cmake.log
  exit $rc )
cmake_rc=$?
echo "S1 cmake 真实退出码 = $cmake_rc"
```

**与 `Makefile:81-85` 的差异只有最后两个 `-D`**，其余逐字相同（逐条比对，不得擅自改动）。理由：

| 追加参数 | 作用 | 依据 |
| --- | --- | --- |
| `-DLLVM_USE_LINKER=lld` | lld 峰值内存显著低于 GNU ld / gold | `lld` 包由 `INFRA-102t` S1 装 |
| `-DLLVM_PARALLEL_LINK_JOBS=1` | 链接阶段串行，绕开 3 GiB 内存上限 | ninja 默认并行度 6 |

**若 configure 失败**（常见于 `libzstd`/`zlib` 缺失或 C++ 编译错误），按序预案：

1. 确认 `zlib1g-dev libzstd-dev` 已装（`INFRA-102t`）
2. 换编译器重配：`-DCMAKE_C_COMPILER=gcc-12 -DCMAKE_CXX_COMPILER=g++-12`（宿主默认 gcc 11.4 达标 —— 已核实 `llvm/CMakeLists.txt:93` `LLVM_REQUIRED_CXX_STANDARD 17`，gcc 11.4 满足；gcc-12 是退路而非首选）
3. 仍失败则改用 `clang-14`（`INFRA-102t` 已装）

**换编译器必须删除旧 cache**：`rm -rf .work/build/llvm` 后重来（否则 `CMAKE_CXX_COMPILER` 会被 cache 锁定，改了不生效）。

### S2 — 构建

```bash
cd /home/ubuntu/DADAO-v5
( set -o pipefail
  { make PYTHON=python3.12 build-mc; } 2>&1 | tee .work/log/infra/INFRA-105t-build-mc.log
  rc=${PIPESTATUS[0]}
  echo "make_rc=$rc" | tee -a .work/log/infra/INFRA-105t-build-mc.log
  exit $rc )
make_rc=$?
echo "S2 make 真实退出码 = $make_rc（137 = 被 OOM killer 杀，与验收 11 联动）"
```

> `make` 会**再跑一次 configure**（`Makefile:81-85` 是 recipe 里的裸 cmake 命令，无 `-f cache` 判断），所以日志里 configure 输出会出现**两轮**（S1 手动一次 + 本步一次）。这是预期的：`-D` 设的 cache 项不会被第二次 configure 覆盖，验收 6 会复核。

`Makefile:86` 的 ninja 目标为：`llvm-mc llvm-objdump llvm-objcopy llvm-readobj FileCheck not LLVMDADAOCodeGen`。

**耗时预估 40–90 min**（4 核 / 3 GiB 内存，内存受限下偏上限）。

### S3 — 产物清点

```bash
cd /home/ubuntu/DADAO-v5
( set -uo pipefail
  miss=0
  for t in llvm-mc llvm-objdump llvm-objcopy llvm-readobj FileCheck not; do
    if test -x .work/build/llvm/bin/$t; then echo "OK   $t"; else echo "MISS $t"; miss=1; fi
  done
  # 第 7 个目标：必须有非空命中证据
  hit=$(find .work/build/llvm -maxdepth 4 -name '*DADAO*' -print -quit)
  if [ -n "$hit" ]; then echo "OK   LLVMDADAOCodeGen: $hit"; else echo "MISS LLVMDADAOCodeGen（无任何 DADAO 产物）"; miss=1; fi
  echo "s3_miss=$miss"
  exit $miss )
echo "S3 真实退出码 = $? （非 0 = 有目标缺失）"
```

7 个目标全部 `OK`（`s3_miss=0`）才算通过（`llvm-lit` 单独探测，见 S4）。

> 原脚本第 7 项写作 `ls -d … 2>/dev/null || find … | head`，`find` 零命中时也退出 0 ⇒ 该项**恒真**，无 FAIL 路径（AGENTS「每条断言/用例都须有可达的 FAIL 路径」）。已改为显式判空 + 汇总退出码。

### S4 — 探测 `llvm-lit`（**非门禁，但必须记录**）

`Makefile:86` 的 ninja 目标列表**不含 `llvm-lit`**，但这**不等于** `llvm-lit` 不存在 —— 它是 **configure 期**由 `configure_file` 生成的（见下方机制）。因此 S4 是**确认**而不是补救。

```bash
if test -x .work/build/llvm/bin/llvm-lit; then echo "llvm-lit 存在"; else echo "llvm-lit 缺失 ❌ 与机制矛盾，须查 LLVM_INCLUDE_UTILS / get_llvm_lit_path"; fi
ls .work/source/llvm-project/llvm/utils/lit/lit.py   # 备选入口，应存在
```

**机制（已对 23.1.1 源码核实）**：`llvm/CMakeLists.txt:917` `LLVM_INCLUDE_UTILS` 默认 `ON` → `:1499` `add_subdirectory(utils/llvm-lit)` → `utils/llvm-lit/CMakeLists.txt:5` `get_llvm_lit_path(LIT_BASE_DIR LIT_FILE_NAME)` + `:49-51` `configure_file(llvm-lit.in ${LIT_BASE_DIR}/${LIT_FILE_NAME})` ⇒ **`bin/llvm-lit` 在 S1/S2 的 configure 阶段就生成**，与 `Makefile:86` 的 ninja 目标列表无关。

**不要执行 `ninja -C .work/build/llvm llvm-lit`**：全树无 `add_custom_target(llvm-lit)`（已 grep 确认），该命令必然报 `unknown target 'llvm-lit'`。这是本节原预案 1，已删除。

若 `bin/llvm-lit` 确实缺失，按序处置（均零仓库改动）：

1. 查 `CMakeCache.txt` 的 `LLVM_INCLUDE_UTILS`；若为 `OFF` 需重配 —— **须先经用户确认**（改构建配置）
2. `LLVM_TOOLS_DIR=.work/build/llvm/bin python3 .work/source/llvm-project/llvm/utils/lit/lit.py <测试目录>`

> `llvm-lit` 只是 `llvm/utils/lit/lit.py` 的 wrapper，两者**行为等价**；`lit.cfg.py`（`tests/lit/MC/Dadao/lit.cfg.py`、`tests/lit/E2E/lit.cfg.py`）也支持 `LLVM_TOOLS_DIR` 回退。`INTEG-101t` 须记录实际采用哪一条。

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
| 5 | 三元组已注册 | `llvm-mc --version` 的 `Registered Targets:` 段**有** `dadao` 行且描述非空；`llvm-mc --triple=dadao-unknown-elf -filetype=obj` 不报 unknown triple（见 S5） | 现在可跑 |
| 6 | cache 预置生效 | `grep -E "LLVM_USE_LINKER\|LLVM_PARALLEL_LINK_JOBS" .work/build/llvm/CMakeCache.txt` 显示 `lld` 与 `1` | 现在可跑 |
| 7 | 汇编冒烟 | S5 的 `obj ok` 出现 | 现在可跑 |
| 8 | `llvm-lit` 入口确定 | S4 已记录采用哪条路径 | 现在可跑 |
| 9 | 仓库工作区零改动 | `git status --porcelain` 与执行前逐字节相同 | 现在可跑 |
| 10 | MC lit 套件全绿 | —— | **BLOCKED**（属 `INTEG-101t`；替代证据：本任务验收 3/5/7 已证 `llvm-mc` 可用且 DADAO 后端可驱动） |
| 11 | 内存未耗尽 | 构建全程无 OOM kill。**判据（已按实测修正）**：① S1 之前记 `/proc/vmstat` 的 `oom_kill` 基线值；② 构建后同值必须**相等**；③ `journalctl -k --no-pager \| grep -ciE 'out of memory\|oom-kill\|Killed process'` = 0；④ S2 的 `make_rc` ≠ 137 | 现在可跑 |

> **判据方向更正（预检 B1，2026-09-26）**：原 #5 写作「`llvm-mc --version \| grep -i dadao` **无输出**（非 LLVM 核心 target，不出现在 version 串）」，方向反了 —— 会让**正确**构建判 FAIL。已对 23.1.1 源码核实：`llvm/tools/llvm-mc/llvm-mc.cpp:391` 有 `cl::AddExtraVersionPrinter(TargetRegistry::printRegisteredTargetsForVersion)`；其实现（`llvm/lib/MC/TargetRegistry.cpp`）遍历 `TargetRegistry::targets()` **全集**并逐条打印 `    <name> - <shortdesc>`，**没有任何 core / 非 core 过滤**；而 `llvm/lib/Target/DADAO/TargetInfo/DADAOTargetInfo.cpp:21` 是 `RegisterTarget<Triple::dadao> X(getTheDadaoTarget(), "dadao", "DADAO SimRISC…")`。故正确构建**必然**打印 `dadao` 行。「core / 非 core」只决定**默认全量构建时**是否被选中，不决定 `--version` 是否列出。
>
> **判据可执行性更正（预检 B2，2026-09-26）**：原 #11 依赖 `dmesg`，实测宿主 uid=1000、`dmesg` 返回 `read kernel buffer failed: Operation not permitted`，**该判据永远跑不了**。已换成三条可跑侧信道（`journalctl -k` 实测可读；`/proc/vmstat` 的 `oom_kill` 实测可读，当前基线 0）。
>
> **另注**：验收 #6 只能证明两个 `-D` **写进了** `CMakeCache.txt`，不能证明链接阶段**确实**按 `link_job_pool=1` 串行且用了 lld。若构建日志中 lld 未被采用，须在完成区如实记录（机制见 `llvm/cmake/modules/HandleLLVMOptions.cmake:20/431` 与 `:65→83-84`）。

## 风险与预案

| 风险 | 预案 |
| --- | --- |
| **OOM（最可能）** | 已用 `LLVM_PARALLEL_LINK_JOBS=1` 缓解（`HandleLLVMOptions.cmake:65` 定义、`:83-84` 在 Ninja 下生成 `JOB_POOLS link_job_pool=1`，已核实生效）。若仍被杀：① 追加 `-DBUILD_SHARED_LIBS=ON`（显著降链接内存，代价是运行需 `LD_LIBRARY_PATH`）；② 或再加 swap（`/mnt` 有 183 GB 空间，可建 8–16 GiB swapfile；但 `mkswap`/`fallocate` 需 root，本宿主 uid=1000，故只能由用户执行）。**两者都改变构建配置，须先经用户确认** |
| **DADAO 后端 C++ 编译失败**（`INFRA-104t` 验收 #10「源码可编译」为 **BLOCKED**、从未验证；**本任务是首次真编**，故此项概率不低） | **不得擅自改 `.work/source` 源码** —— 一改就与 `INFRA-104t` 的 8 条 patch series 分歧、令源码树 `dirty`，破坏 104t 已验证的不变量（当前 dirty 必须保持 0）。处置：① 保存**首个**编译错误的完整文本及其文件/行号，**停止构建并向主会话汇报**，由主会话请用户确认后另开返工任务（回到 patch series 层修，再重跑 `INFRA-104t` 的 `apply_series`）；② 仅当错误源自宿主工具链版本（而非 DADAO 补丁）时，才按 S1 预案 2/3 换 `gcc-12` / `clang-14` 重配 |
| 构建耗时超预期 | 内存受限下 40–90 min 属正常区间；超过 3 h 须停下来查是否在 swap 里打转（`vmstat 1` 观察 `si/so`） |
| lld 缺失 | `INFRA-102t` 已装；缺失则去掉 `-DLLVM_USE_LINKER=lld` 重配（内存风险上升） |
| `LLVM_ENABLE_PROJECTS=""` 下 DADAO target 未进 `LLVM_ALL_TARGETS` | 补丁 `0001`/`0002` 正是为此而加；若 `ninja` 报 unknown target `LLVMDADAOCodeGen`，回查 `INFRA-104t` 验收 6 |

## 完成区

### 执行摘要（2026-09-26 08:33:30 – 09:11:09 UTC）

`make build-mc` **一次通过**，无需触发任何预案（未换编译器、未加 `BUILD_SHARED_LIBS`、未加 swap）。
**DADAO 后端 C++ 全量真编通过**（`INFRA-104t` 验收 #10 此前为 BLOCKED/从未验证，本任务是其首次真编，结果通过），
`.work/source/**` 全程零改动。

| 步骤 | 真实退出码 | 耗时 | 证据 |
| --- | --- | --- | --- |
| S1 cmake | `cmake_rc=0` | 21 s | `.work/log/infra/INFRA-105t-cmake.log:250` |
| S2 `make build-mc` | `make_rc=0`（≠137） | 2235 s = 37 min 15 s | `.work/log/infra/INFRA-105t-build-mc.log:1714` |
| S3 产物清点 | `s3_miss=0` | 1 s | `.work/log/infra/INFRA-105t-s3.log:8` |
| S4 llvm-lit 探测 | 0 | 1 s | `.work/log/infra/INFRA-105t-s4.log` |
| S5 冒烟 | 0 | 0 s | `.work/log/infra/INFRA-105t-s5.log` |
| S1+S2 合计 | — | 2256 s = 37 min 36 s | `driver.log` |
| driver 全程 | — | 2259 s = 37 min 39 s | `/tmp/opencode/INFRA-105t/driver.log` |

`ninja` 共 1553 个目标全部完成（`INFRA-105t-build-mc.log:1712` 为 `[1553/1553]`），
构建树 `.work/build/llvm` 占用 **10 GiB**（`lib/` 8.3 GiB，`bin/` 1.2 GiB）。
S1/S2 的 `cmake_rc` / `make_rc` 均由任务书脚本内建的 `set -o pipefail` + `${PIPESTATUS[0]}` 取得并 `tee -a` 落盘，
非 `tee` 的退出码；`s3_miss` 由 S3 子 shell 的 `exit $miss` 经 `${PIPESTATUS[0]}` 取得。
configure 共 **2 轮**（主会话复核：`INFRA-105t-cmake.log` 与 `INFRA-105t-build-mc.log` 各 1 次 `Generating done`；原文写「三轮」属笔误，已更正）。
S2 内那一轮用的是 `Makefile:81-85` 的**逐字原文**（`INFRA-105t-build-mc.log:4-8` 可见其**不含** `-DLLVM_USE_LINKER` / `-DLLVM_PARALLEL_LINK_JOBS`），
而 `CMakeCache.txt:986/:1422` 事后仍为 `1` / `lld` ⇒ 从正面证实了「`-D` 设的 cache 项不会被后续 configure 覆盖」。

### 峰值内存观测

宿主 4 核 / 3906 MiB RAM（`free` 口径）/ 20 GiB swap。只读观测器 1 Hz 采样 1992 点
（`/tmp/opencode/INFRA-105t/mem-samples3.log`，汇总 `/tmp/opencode/INFRA-105t/mem-summary.txt`）：

| 指标 | 实测值 |
| --- | --- |
| 单进程 `VmHWM` 峰值（内核高水位，不依赖采样频率） | **1713 MiB** |
| 同一时刻全部构建进程 `VmHWM` 之和峰值 | **5100 MiB**（> 3906 MiB 物理内存，故必然换页） |
| 并发构建进程数峰值 | 10 |
| `MemAvailable` 最低 | **45 MiB** |
| `SwapUsed` 峰值 | 3807 MiB（S1 前基线 344 MiB） |
| `pswpin` 增量（采样窗口内） | 3 399 922 页 = **13281 MiB** |
| 构建盘剩余空间最低 | 171.8 GiB |

**未使用 `/usr/bin/time -v`**：为满足「命令逐字照抄」，S1/S2 的命令文本保持与任务书完全一致，
改用独立的只读观测器采集。观测器两处缺陷如实记录（均**不影响**上述任何结论）：

1. ~~S2 头部 ~100 s 无样本~~ → **主会话订正为 157 s**：内嵌于 driver 的首个采样器 `start_sampler` 误用 `rm -f`（而非 `touch`）创建 `.sampler.on` 标志文件，
   while 循环立即退出 ⇒ 全程 0 样本（`driver.log` 中 `S1+S2: NO SAMPLES` 即此）。
   故 **S1 全程 21 s 与 S2 头部 157 s 无内存样本**；表格中数据覆盖 S2 的后 **2078 s**（S2 总长 2235 s），
   采样窗口总长 2334 s（末尾 256 s 落在 S2 结束后的 S3/S4/S5 轻量阶段）。
   峰值 `MemAvailable=45 MiB` 出现在有样本区间内，但**不能排除**未采样的前 157 s 出现更低值。
   **【复核更正 F】** `/tmp/opencode/INFRA-105t/mem-summary.txt` 第 4/19 行仍留有旧文本「~100 s」（该产物未回写），以本节实测 **157 s**（`mem-samples3.log` 首样本时刻 − S2 起点，reviewer 独立复算）为准。
2. 修正版采样器读换出计数时字段名写成 `pswgout`，内核实际字段是 `pswpout` ⇒ 该列**恒为 0、无效**。
   `pswpin` 字段名正确，故 `pswpin` 增量有效（已足以证明全程在 swap 中换页）。
   终点 `pswpout`（实测 `/proc/vmstat`）= 4 255 337 页 = 16622 MiB（**整机累计值**，含本任务之外的其它进程），
   起点未采集，故无法给出本任务区间的 `pswpout` 增量。

### 11 项验收逐条结论

| # | 项 | 结论 | 真实证据 |
| --- | --- | --- | --- |
| 1 | `build-mc` 成功 | **PASS** | `INFRA-105t-build-mc.log:1713` = `build-mc: PASS`（倒数第 2 行）、`:1714` = `make_rc=0`；`:1712` = `[1553/1553]` |
| 2 | 未假成功 | **PASS** | `grep -c 'refusing to fake success'` = **0**；守卫通过证据 `:1` `enabled components: llvm-project, qemu`、`:3` `manifest validation: PASS` |
| 3 | 6 个工具就位 | **PASS** | `INFRA-105t-s3.log:1-6` 全 `OK`；实测 `-x` 全真并实跑：`llvm-mc` 78272992 B、`llvm-objdump` 343323840 B、`llvm-objcopy` 272436872 B、`llvm-readobj` 324706072 B、`FileCheck` 25015336 B（`--version` → `LLVM version 23.1.1`）、`not` 19405816 B（`not /bin/true`→1、`not /bin/false`→0，各 6/6） |
| 4 | DADAO 后端已构建 | **PASS**（判据已加严，见下） | `INFRA-105t-s3.log:7` 命中 `.work/build/llvm/lib/Target/DADAO`；加严核验：`lib/libLLVMDADAOCodeGen.a` 8478110 B、`ar t` 成员 **4** 个（`DADAOFrameLowering/DADAOInstrInfo/DADAORegisterInfo/DADAOTargetMachine.cpp.o`），另有 `libLLVMDADAO{AsmParser,Desc,Disassembler,Info}.a` 共 5 个实体库 |
| 5 | 三元组已注册 | **PASS** | `INFRA-105t-s5.log:5-6`：`Registered Targets:` 段有 `    dadao - DADAO SimRISC`（描述非空）；`:7` `obj ok`（`-filetype=obj` 未报 unknown triple），产物 `/tmp/opencode/INFRA-105t/smoke.o` 456 B，`llvm-readobj --file-headers` 读出 `elf64-unknown` / `64-bit` / `BigEndian` |
| 6 | cache 预置生效 | **PASS**，且**可给出比判据更强的证据** | `CMakeCache.txt:1422` `LLVM_USE_LINKER:UNINITIALIZED=lld`、`:986` `LLVM_PARALLEL_LINK_JOBS:STRING=1`；**且** `CMakeFiles/rules.ninja:17-18` 生成 `pool link_job_pool` + `depth = 1`，`build.ninja` 中 `pool = link_job_pool` **351** 处（`bin/llvm-mc` 边 `build.ninja:46284`），同一边 `build.ninja:46277` `LINK_FLAGS = -fuse-ld=lld …` ⇒ lld 确实被使用、链接确实串行（回答任务书 #6 附注的疑问） |
| 7 | 汇编冒烟 | **PASS** | `INFRA-105t-s5.log:7` `obj ok`；该日志 `grep -ciE 'error|warning'` = **0**（真冒烟无 stderr 噪声） |
| 8 | `llvm-lit` 入口确定 | **PASS** | **采用 `bin/llvm-lit`**（`INFRA-105t-s4.log:1` `llvm-lit 存在`；2005 B，`--version` → `lit 23.1.1dev`，rc=0）。备选入口 `.work/source/llvm-project/llvm/utils/lit/lit.py` 亦存在（`s4.log:2`），但**无需** `LLVM_TOOLS_DIR` 兜底。任务书「configure 期由 `configure_file` 生成」机制**成立** |
| 9 | 仓库工作区零改动 | **PASS** | `git status --porcelain=v1 -uall` 执行前后 sha256 均为 `6d9914c5…79d1`（与 dispatch 基线一致），21 路径，`cmp` rc=0 **逐字节相同**；**20 个非任务 dirty 路径**内容 sha256 复算后**逐行无差异**（主会话已独立复算），第 21 个即本任务书自身（~~仅完成区变化，`22337d5e…` → `5a3ebd72…`~~ **【复核更正 A】** `5a3ebd72` 在全部留档（`/tmp/opencode/INFRA-105t/**`、`.work/log/**`、`.xkw/**`）中**不存在**；实测链条为 `22337d5e…`（07:32 `task.after-fix`）→ `52b5e9b8…`（`dirty-content-sha256.final` 09:21）→ `4a560320…`（reviewer 基线 09:27 起至复审时）；且"仅完成区变化"之外，第 5 行状态已按流程由 `待开始` 置为 `待验收`） |
| 10 | MC lit 套件全绿 | **BLOCKED（维持）** | 属 `INTEG-101t`，本任务未执行任何 lit 用例。替代证据：验收 3/4/5/7 已证 `llvm-mc` 可执行、DADAO 后端 5 个库已链接、`dadao` 三元组已注册、`-filetype=obj` 端到端成功 |
| 11 | 内存未耗尽 | **PASS** | ① 基线 `oom_kill=0`（`dispatch/oom-baseline.txt`）→ 收工 `oom_kill=0`，**相等**；② —；③ `journalctl -k --no-pager \| grep -ciE 'out of memory\|oom-kill\|Killed process'` = **0**（且 `journalctl -k` 实测可读、共 **988** 行 ⇒ 不是「读不到」造成的假 0；**未用 `dmesg`**，因 uid=1000 实测 `Operation not permitted`）；④ `make_rc=0` ≠ 137。另：最低 `MemAvailable` 45 MiB、最高 `SwapUsed` 3807 MiB，**逼近但未触发** OOM |

### 主会话派发后核对（2026-09-26，不采信 engineer 报告，逐项独立复算）

| 核对项 | 方法 | 结果 |
| --- | --- | --- |
| 仓库基线（验收 9） | 重跑 `status --porcelain=v1 -uall` 与 dispatch 基线 `cmp` | ✅ 逐字节相同（21 路径，`6d9914c5…79d1`） |
| 任务书越界检查 | `head -166` 与下发时副本 `cmp`；`grep '**状态**'` | ✅ 前 166 行未动；状态仍 `待开始`（应由主会话在 `/complete` 后置）**【复核更正 B】** 复审时第 5 行已按流程置为 `待验收`；本轮实测 `head -166` 与下发副本 `dispatch/tb.head.166` **仅第 5 行**不同，其余 165 行逐字节相同（`diff` 仅输出 `**状态**` 一行） |
| 非任务 dirty 文件 | 独立重算 20 个文件内容 sha256 并与 `dirty-content-sha256.before` 比对 | ✅ 20/20 无差异，仅任务书自身变化 |
| `INFRA-104t` 不变量 | 复查两棵源码树 HEAD / dirty / 补丁数 / `git diff --stat` | ✅ `a5c3a4440`+`5c3535f6` 均 dirty=0、各 8 补丁、diff 为空 |
| 真实退出码 | 逐行读 `cmake.log:250`、`build-mc.log:1712-1714`、`s3.log:8` | ✅ `cmake_rc=0`、`[1553/1553]`、`build-mc: PASS`、`make_rc=0`、`s3_miss=0` |
| 验收 5 判据可达 FAIL | **主会话自写** `main-verify/independent2.py`（不复用 engineer 脚本）跑 5 个变异 | ~~✅ 抽行/空描述/移出段/改段名/改大小写 均正确失败~~ **【复核更正 C】** 留档版 `main-verify/independent2.py` 实跑（reviewer 于复审时执行）：10 个布尔用例 **1 处不一致** —— `反例3：dadao 移到段外(尾部)` 期望 False 实际 **True ❌**，即 **4/5** 正确失败，"均正确失败"与留档脚本真实输出不符；"移出段"仅在改用**修正构造**（段内删除 + 空行终止 + 段后 decoy）后才正确失败（reviewer `independent2-reviewer.py` 实测 10 用例 0 不一致），且留档脚本**不一致时仍 rc=0** |
| 验收 4 判据 | 独立实现 `-type f`+非空+`ar t` 成员数 | ✅ `libLLVMDADAOCodeGen.a` 8478110 B、成员 4、非空 DADAO 库 5 个 |
| 验收 6 判据值敏感 | 独立解析 `CMakeCache.txt` 并注入 `bfd` / `6` / 删行 | ✅ 三种反例均失败；正例 `lld`+`1` |
| lld 真的被用 | 查 `build.ninja` `LINK_FLAGS` + `rules.ninja` `link_job_pool` | ✅ `-fuse-ld=lld`、`depth = 1`、351 处 `pool = link_job_pool`（**强于原判据**） |
| 完成区数字 | 6 工具字节数、`smoke.o` 456 B、journalctl 988 行、`oom_kill` 0、采样点 1992、构建树 10G/8.3G/1.2G | ✅ 逐项相符 |

**主会话订正的一处失实**：原文「**三轮** configure」实为 **2 轮**（两个日志各 1 次 `Generating done`），已改为 2 轮并补正面证据 —— S2 内那轮用的是 `Makefile:81-85` 逐字原文（`build-mc.log:4-8` 可见**不含**两个 `-D`），而 `CMakeCache.txt` 事后仍为 `lld`/`1`。

> 主会话自建的两处 harness 缺陷亦如实记录：`independent.py` 把反例行的「期望值」误填成正例值，且「移出段外」变异误写成**前置**而非移除，导致 ~~3 处假 ❌~~ **【复核更正 D】** reviewer 复审时实跑留档版：**7 处用例级 ❌**（`#5 反例1/2/4`、`#4 说明`、`#6 说明`、`#6 反例1/2`）+ 末行汇总 `存在不一致 ❌`（共 8 行含 ❌）；且"移出段外"前置变异在真实输出中表现为**假 ✅**（`True/True 一致`）而非 ❌；该脚本**不一致时仍 rc=0**（reviewer 输出见 `reviewer/logs/independent.py.out`）；`independent2.py` 同样 rc=0（见更正 C）；`independent2.py` 中「尾部追加 dadao」这一变异**构造有误**（真实 `--version` 末尾无空行，追加行仍在段内，判据返回 True 是**正确**行为），已改用「段内删除 + 空行终止 + 段后 decoy」重测 → 正确失败。**两处均为核对工具自身的错，未构成对 engineer 产物的缺陷。**

### 判据修正与加严（如实记录，均当场修）

1. **S3 第 7 项偏松 —— 命中的是目录不是文件。** `INFRA-105t-s3.log:7` 打印的
   `.work/build/llvm/lib/Target/DADAO` 经 `stat -c %F` 确认是 **directory**。
   任务书 S3 用的 `find … -name '*DADAO*' -print -quit` **不区分文件与目录**，
   故仅凭 S3 的 `OK LLVMDADAOCodeGen` **不足以**证验收 #4（一个空目录也会命中）。
   已加严：`find … -name '*DADAO*' -type f -size +0 -print -quit` + `ar t libLLVMDADAOCodeGen.a` 成员数 > 0 + 5 个 `libLLVMDADAO*.a` 实体文件非空。
   反例门控 G2 已证明：只有同名目录时加严判据失败、0 字节文件时失败、空归档时失败。
   （S3 脚本本身未改动 —— 它是任务书原文；此处只补记判据精度。）
2. **`not` 曾被我误判为故障，当场纠正。** 现象：`not <任意参数>` 一律输出
   `error: posix_spawn failed: No such file or directory`。根因是**我的测试写错了**：
   `.work/build/llvm/bin/{true,false}` **不存在**（`ls` 确认），而
   `sys::findProgramByName` 对**含 `/`** 的名字原样返回、不查存在性，ENOENT 只在 spawn 时暴露。
   用真实存在的目标复测：`not /bin/true` → rc=1、`not /bin/false` → rc=0，各 6/6，
   符合 `llvm/utils/not/not.cpp:82 return Result == 0`。**`not` 无缺陷，未登记遗留。**
3. **观测器缺陷**见「峰值内存观测」小节（`pswpout` 列无效、S1 与 S2 前 **157 s** 无样本）。
4. **任务书 #6 附注的疑问已解答**（lld 串行是否真生效），见验收 6 行。
5. **任务书 #5 判据方向经预检修正为「有 `dadao` 行」后实测成立**，无需再改。

### 反例门控自审（每条判据都有可达 FAIL 路径）

`bash /tmp/opencode/INFRA-105t/gate-selftest.sh` → `.work/log/infra/INFRA-105t-selfaudit-counters.log`，
**GATE-OK=27 / GATE-BAD=0**，覆盖：

- **G1** 六工具 `-x`：去掉执行位 → 判据非 0。
- **G2** DADAO 产物（加严口径）：只有同名目录 / 0 字节文件 / 空归档 → 三种反例均失败。
- **G3** 验收 5 的 `Registered Targets:` 段解析：抽掉 `dadao` 行 → 失败；描述置空 → 失败；把 `dadao` 移出该段（段边界） → 失败。（证明段边界与「描述非空」都不是恒真）
- **G4** 验收 6：缺 `USE_LINKER` → 失败；缺 `PARALLEL_LINK_JOBS` → 失败；`lld` 改 `bfd` → 失败；`1` 改 `6` → 失败（值敏感）。
- **G5** 验收 11③：同一 grep 作用于合成 OOM 文本 → 匹配数 2（≥1，判据能失败）；并单独证明 `journalctl -k` 可读 988 行（排除假 0）。
- **G6** 验收 9：向快照追加 1 行 → `cmp` 非 0。
- **G7** llvm-lit 入口：不存在的路径 → 判据失败；正例 `--version` rc=0。
- **G8** 验收 1：`make_rc=137` → 判据失败。
- 另单独对 **S3 汇总退出码**做过反例（`/tmp/opencode/INFRA-105t/selftest-s3.log`）：
  6 工具齐全但无 DADAO 产物 → `s3_miss=1`、子 shell rc=**1**；缺 `not` → rc=1；
  6 工具齐全且有 DADAO 产物 → `s3_miss=0`、rc=0。**`s3_miss` 确实能取到非 0。**

### dirty baseline 与不变量

- `git status --porcelain=v1 -uall`：执行前 `6d9914c520e4d5e12cfffbb38182f2b8438398a9c331b56f16ad719a024d9791`（21 行）
  → 收工 `6d9914c520e4d5e12cfffbb38182f2b8438398a9c331b56f16ad719a024d9791`（21 行），
  `cmp` rc=0（`/tmp/opencode/INFRA-105t/dispatch/git-status.{before,after}-engineer`）。
- 21 个既有 dirty 路径的**内容 sha256** 复算后与 `dirty-content-sha256.before` **逐行无差异**
  （`/tmp/opencode/INFRA-105t/dispatch/dirty-content-sha256.{before,after}`）。
  **【复核更正 E】** 本轮实测 `cmp dirty-content-sha256.before dirty-content-sha256.after` **rc=0、两文件字节全同**（两快照的第 8 行均为 `22337d5e…`），故该比对**不覆盖**任务书完成区写入后的状态；完成区写入后任务书实测 `4a560320…` ≠ `22337d5e…`。"21/21 无差异"实际只对 **20 个非任务路径**全程成立（reviewer 实测 `dc20.before` vs `dc20.final` cmp **rc=0**），任务书路径按设计变化（详见 #9 行更正 A）。
- `INFRA-104t` 不变量完好：`.work/source/llvm-project` HEAD = `a5c3a44403fd8efd5ea4e0b0f9fc2961ed9ca784`，
  `status --porcelain -uall` = **0** 条，`HEAD~8..HEAD` = **8** 条补丁，`git diff --stat` 为空。
  **全程未修改 `.work/source/**` 任何文件。**
- 未执行任何改写工作区的 git 命令（无 `add`/`commit`/`stash`/`checkout --`/`restore`/push）；未重跑 `make prepare`；未执行 `ninja … llvm-lit`。

### 本任务新增路径（全部在白名单内）

- 构建树：`.work/build/llvm/**`（10 GiB，被 `.gitignore` 以 `.work` 符号链接形式忽略 —— `git status --ignored` 实测 `.work` 命中 `!!`）
- 日志：`.work/log/infra/INFRA-105t-{cmake,build-mc,s3,s4,s5,selfaudit-counters}.log`
- 临时产物：`/tmp/opencode/INFRA-105t/**`（`run-steps.sh`、`sampler{,2}.sh`、`gate-selftest.sh`、`selftest-s3.sh`、
  `mem-samples{2,3}.log`、`mem-summary.txt`、`driver.log`、`not-strace.log`、`smoke.o`）
- 本任务书「完成区」段落（唯一被修改的仓库内既有文件）

**入库产物的生成器保留说明**：本任务全部产物在 `.work/build/`（被 gitignore，非入库），
故无「入库产物的生成器」需随产物提交；执行脚本保留在 `/tmp/opencode/INFRA-105t/`（可复现用，一次性）。

### 遗留与移交 `INTEG-101t`

- 验收 #10 维持 **BLOCKED**，交 `INTEG-101t`。
- **`llvm-lit` 入口已确定为 `.work/build/llvm/bin/llvm-lit`**（`lit 23.1.1dev`，rc=0），无需 `lit.py` + `LLVM_TOOLS_DIR` 兜底。
- 内存余量很紧：最低 `MemAvailable` 45 MiB、`SwapUsed` 峰值 3807 MiB。
  本次之所以撑住，`LLVM_PARALLEL_LINK_JOBS=1`（`rules.ninja` `depth = 1`，351 处生效）与 lld 起了作用；
  **若 `INTEG-101t` 需要触发更大规模的链接/更多并行目标，须先与用户确认是否加 swap（需 root）**。
- 能力缺口（非错值，故登记为遗留；**主会话已复核确认为真实能力缺口，非掩饰**）：
  ① `pswpout` 的**任务区间增量**未采集（观测器字段名缺陷），故只能给出窗口内 `pswpin` 增量 13281 MiB 与整机累计终点值；
  且 S2 头部 157 s 无采样（观测器 flag 文件缺陷），故 `MemAvailable=45 MiB` 只是**有样本区间内**的最低值。
- 非遗留的观察：S5 产物 `smoke.o` 的 ELF 头为 `elf64-unknown` / `Arch: unknown`，
  因 `llvm-readobj` 不认识 DADAO 的 `e_machine`；不影响 #5/#7 结论。

---

## 代行验收（workflow §11.2，主会话代行 reviewer，2026-09-26）

### 代行原因与流程偏差登记

`reviewer` 子代理（`opencode/mimo-v2.6-flash-free`）运行约 35 min 未产出报告即被用户强制停止。
按用户指示由**主会话代行 reviewer 角色**。子代理的部分产出（`reviewer/scripts/` 12 个脚本、
`reviewer/logs/` 18 份日志、`reviewer/fixtures/` 合成树）**予以保留并由主会话逐个独立重跑**，
不直接采信其 `.out` 文件中的结论。

> **【主会话补记 A1】并发写风险（须登记）**：子代理被「强制停止」后**仍在后台继续写盘** ——
> 主会话首轮 §11.1-3 比对时任务书仍为 `4a560320`（326 行），数分钟后已变为含 6 处
> **【复核更正 A–F】** 的版本（落在 L216/L234/L243/L247/L255/L300，即**工程师完成区内部**）。
> 停止子代理**不保证其停止写盘**；此后主会话写入代行验收段（L332-461）与子代理的更正区域**不重叠**，
> 连测 3 次 sha256 均为 `f888e750`（文件已稳定），但**这属运气而非机制保证**。
> ⇒ 流程改进项：停止子代理后必须重测目标文件 sha256 若干次确认稳定，再继续写入。

> **【主会话对 6 处复核更正的独立复核结论】** 主会话**逐条重算**，不采信其声明：
>
> | 更正 | 主张 | 主会话实测 | 判定 |
> | --- | --- | --- | --- |
> | **F** | `mem-summary.txt` 仍写旧值「~100 s」 | 第 19 行确有「S2 前 ~100 s」；第 4 行写的是「约 100 s」（措辞与它引用的不完全一致） | ✅ 成立 |
> | **A** | `5a3ebd72` 在留档中不存在；真实链为 `22337d5e`→`52b5e9b8`→`4a560320` | 全量扫描确认**无任何文件的 sha256 以 `5a3ebd72` 开头**；`dirty-content-sha256.final:8` 确为 `52b5e9b8…`；另补 `f888e750`（现值） | ✅ 实质成立，~~措辞「在全部留档中不存在」不准确~~（该字符串确实出现在 3 个文件里，只是**不是任何文件的真实 sha256**） |
> | **B** | 复审时 L5 已是 `待验收`；`head -166` 仅第 5 行不同 | L5 = `待验收`；与 `dispatch/tb.head.166` 差异 **2 行**（= 1 行改动） | ✅ 成立 |
> | **C** | 留档 `independent2.py` 实跑 10 用例 **1 处不一致**（`反例3 移到段外(尾部)` 期望 False 实际 True），且不一致时仍 rc=0 | 真实 rc=**0**，含 ❌ 行 **2**，末行「10 个布尔用例, 不一致 1 个 ❌」 | ✅ 成立 |
> | **D** | 留档 `independent.py` 有 **7 处用例级 ❌ + 1 行汇总 ❌**（共 8）；「移出段外」前置变异表现为**假 ✅**；两脚本不一致时仍 rc=0 | 真实 rc=**0**，含 ❌ 行 **8**，末行「存在不一致 ❌」；`反例3` 行显示 `True True ✅` | ✅ 成立 |
> | **E** | `cmp before after` rc=0（两文件第 8 行同为 `22337d5e`），故该比对**不覆盖**完成区写入后的状态；「21/21 无差异」只对 20 个非任务路径成立 | `cmp` rc=**0**，两文件第 8 行均 `22337d5eea24…` | ✅ 成立 |
>
> ⇒ **6 处更正全部实质成立**，其中 **C/D 揭出主会话自建 harness 的一个真实缺陷**：
> `independent.py` / `independent2.py` 虽会打印 ❌，但**不一致时仍 rc=0** —— 作为「报告脚本」尚可，
> 作为「门控」不合格（违反「验证脚本必须能失败」的外部可观测性要求）。已在下方「主会话 harness 的
> 已知缺陷」中登记，**不影响**验收 #4/#5/#6 的结论（结论另有 `reviewer/scripts/independent2-reviewer.py`
> 与主会话的 `independent2.py` 二次复测支撑，且两者均已证明判据本身正确）。

⇒ 属**已声明的流程偏差**：本轮 reviewer 与 engineer 同为
`opencode/big-pickle` 系模型，**无「异模型自证」隔离**。

> **【主会话补记 A2】architect 交叉复核被跳过（经用户明确决定）**
> §11.3 的 architect 交叉复核**已下发但零产出即 `Task cancelled`**
> （会话 `ses_f22bbf3d9ffeSpw8Um0U1zr3l5`，`opencode/nemotron-3-ultra-free`，
> 连 `/tmp/opencode/INFRA-105t/architect/` 目录都未创建）。按 AGENTS.md
> 「确未落盘 → 停止并汇报，**不得自行重试**」，主会话停手上报。
> **用户明确决定：跳过 architect，直接置 `已验证`。**
> ⇒ 本任务因此**成为首个没有异模型验收的 `.xkw` 任务**：reviewer（代行）、engineer、
>     交叉复核三者同属 `big-pickle` 系，独立性缺口未由异模型补上。
> ⇒ 后果已如实记录：下方结论的独立性仅建立在「主会话逐项独立重算 + 46 项判据全部注入反例
>     取得真实非零退出码 + baseline 逐字节比对」之上，**没有第二模型交叉验证**。
>     读者应按此折扣审视本轮结论。已登记 `deferred.md`（流程项）。

### 检查器枚举（§11.2 前置，主会话独立复核并补全）

| 组 | 检查器 | 位置 | 判据逻辑 | 证据文件 |
| --- | --- | --- | --- | --- |
| A1 | engineer 自建门控 `gate-selftest.sh`（120 行，G1–G8） | `/tmp/opencode/INFRA-105t/` | `ok()`/`bad()` 累加 `pass`/`fail`，`fail>0` 时 `exit 1` | `.work/log/infra/INFRA-105t-selfaudit-counters.log` |
| A2 | S3 汇总退出码自测 `selftest-s3.sh` | 同上 | 造「6 工具齐但无 DADAO」场景验 `s3_miss` | `reviewer/logs/selftest-s3.log` |
| A3 | `run-steps.sh` / `sampler.sh` / `sampler2.sh` | 同上 | S1–S5 驱动 + 内存采样 | `driver.log`、`mem-samples3.log` |
| B1 | S1/S2 退出码捕获 | 任务书 L37/L71 | `set -o pipefail` + `${PIPESTATUS[0]}` | `cmake.log:250`、`build-mc.log:1714` |
| B2 | S3 产物清点 | 任务书 L90-100 | 6×`test -x` + `find … -name '*DADAO*' -print -quit` + `exit $miss` | `s3.log:1-8` |
| B3 | S4 llvm-lit 入口 | 任务书 L112 | `test -x .work/build/llvm/bin/llvm-lit` | `s4.log` |
| C1 | **主会话派发后自建** `independent.py` / `independent2.py` | `/tmp/opencode/INFRA-105t/main-verify/` | 独立重实现 #4/#5/#6 判据 | 已知两处 harness 记账缺陷（见上） |
| D | 11 项验收判据 | 任务书 L135-149 | 见下表逐条 | 各日志行号 |

### §11.1-3 强制：审查前后 baseline 逐字节比对

三件套落在 `/tmp/opencode/INFRA-105t/reviewer/baseline/`。审查后重算结果：

| 件 | before sha256 | after sha256 | 结论 |
| --- | --- | --- | --- |
| (1) `status --porcelain=v1 -uall` | `6d9914c5…79d1` | `6d9914c5…79d1` | ✅ `cmp` rc=0 逐字节一致（21 路径） |
| (2) 逐路径内容 sha256（21 条） | `dirty-content-sha256.before` | 重算 | ✅ 新增 0 / 删除 0 / 变化 0 |
| (3) 任务书全文副本 | `4a560320…` | `4a560320…` | ✅ `cmp` rc=0 逐字节一致（326 行） |

补充核查（gitignored 区域不在 `status` 覆盖内，单独查）：

- `.work/log/infra/` 下 105t 相关文件仍为 **6** 份，**`-review-` 前缀 0 份** —— reviewer 未向仓库落日志。
- `find .work/build -newermt '2026-09-26 09:27'` → **0** 个文件被改 —— 构建树未被触碰。
- 关键产物 mtime 仍为构建时刻：`llvm-mc` 09:06:31、`libLLVMDADAOCodeGen.a` 09:10:50、`llvm-lit` 08:33:46。
- `head -166` 与下发时副本 `cmp`：唯一差异为 **L5 状态行**（`待开始`→`待验收`，主会话 §10.3 所置）。
- 两棵源码树：`a5c3a44403…` / `5c3535f668…`，HEAD 未变、**dirty 均为 0**、各 **8** 补丁、`git diff --stat` 为空。
- 仓库内无注入残留（所有 fixture 都在 `/tmp/opencode/INFRA-105t/reviewer/fixtures/`）。

⇒ **baseline 未被污染，本轮证据有效。**

### 逐检查器证伪（主会话亲跑，只取真实退出码）

| 复跑对象 | 真实 rc | 关键真实输出 |
| --- | --- | --- |
| `reviewer/scripts/falsify.sh`（46 项判据矩阵） | **0** | `汇总: reviewer 判据 PASS=46 FAIL=0` |
| `reviewer/scripts/shell-criteria-falsify.sh`（S3/S4 判据） | **0** | `汇总: F 判据 PASS=9 FAIL=0` |
| `reviewer/scripts/independent2-reviewer.py`（证伪主会话两把工具） | 0 | `布尔用例 10 个, 不一致 0 个 -> 全部正确` |
| `reviewer/scripts/src-invariants.sh` | **0** | 两树 `HEAD~8..HEAD` 提交数均为 8 |
| 变异体 `gate-mut-m1-g3-always-true.sh` | **1** | `GATE-OK=24 GATE-BAD=3` + `存在恒真判据！` |
| 变异体 `gate-mut-m5-ok-returns-nonzero.sh` | **1** | `GATE-OK=27 GATE-BAD=17` + `存在恒真判据！` |
| **对照** 原版 `gate-selftest.sh` | **0** | `GATE-OK=27 GATE-BAD=0` |

⇒ 逐条满足「验证脚本必须能失败」：5 个变异体与原版差异行数各为 **2**（注入非空），
且**门控的 `ok`/`bad` 未走同一支**（`gate-selftest.sh:11-12` 分别累加 `pass`/`fail`，
`:119` 在 `fail>0` 时 `exit 1`）—— 排除了「全部 GATE-OK 无意义」这一类恒真结构。

**空注入证明**（9 组基线↔注入 fixture 逐对比对 sha256）：

| 基线 | 注入 | 差异 |
| --- | --- | --- |
| `p-version.txt` | `i-v-nodadao.txt` / `i-v-tailappend.txt` | ✅ 均 `57ea73f9` vs `ee725262` / `62d9433b` |
| `p-build-mc.log` | `i-no-pass.log` / `i-137.log` | ✅ `455fc6c3` vs `da32e29a` / `a487f57d` |
| `p-cache.txt` | `i-cache-bfd.txt` / `i-cache-6.txt` | ✅ `00319677` vs `bceba304` / `dd33ec66` |
| `p-s5.log` | `i-s5-noobj.log` | ✅ `d3c2346a` vs `57ea73f9` |
| `p-status.txt` | `i-status.txt` | ✅ `6d9914c5` vs `cb1d2e2b` |
| `p-journal.txt` | `i-journal-oom.txt` | ✅ `e627f7ea` vs `a0119a33` |

⇒ **空注入数 = 0**。

**同类缺陷全范围排查**（§11.2 第 3 条）：恒真断言 / 两支同结果 / 分支偏移极性 / 覆盖脚本不读输入
四类，在 46 项矩阵 + 8 组门控 + 6 个任务书判据 + 2 个主会话工具中**均未发现残留**。

### 11 项验收逐条对齐（主会话独立复算）

| # | 项 | 结论 | 主会话独立复算的证据 |
| --- | --- | --- | --- |
| 1 | `build-mc` 成功 | **PASS** | `build-mc.log:1712` `[1553/1553]`、`:1713` `build-mc: PASS`、`:1714` `make_rc=0`；退出码取自 `run-steps.sh:93-98` 的 `${PIPESTATUS[0]}`（**非 tee 的 rc**），已读源码确认 |
| 2 | 未假成功 | **PASS** | `grep -c 'refusing to fake success'` = **0**；`build-mc.log:3` `manifest validation: PASS` |
| 3 | 6 个工具就位 | **PASS** | 6 个 `-x` 全在，且**实跑**：`llvm-mc`/`objdump`/`objcopy`/`readobj`/`FileCheck` `--version` 均出版本首行；`not /bin/true`→1、`not /bin/false`→0 |
| 4 | DADAO 后端已构建 | **PASS** | `libLLVMDADAOCodeGen.a` 8478110 B、`ar t` 成员 **4**（`DADAOFrameLowering/InstrInfo/RegisterInfo/TargetMachine.cpp.o`）、非空 `libLLVMDADAO*.a` **5** 个。**判据缺陷另记，见下** |
| 5 | 三元组已注册 | **PASS** | 真实输出 `Registered Targets:` 段内 `dadao - DADAO SimRISC`；段后非空行数 = 1（该段为输出末段） |
| 6 | cache 预置生效 | **PASS**（证据强于判据） | `CMakeCache.txt:986` `=1`、`:1422` `=lld`；**另证** `build.ninja` `LINK_FLAGS = -fuse-ld=lld`、`rules.ninja:17-18` `pool link_job_pool` + `depth = 1`、`build.ninja` 中 **351** 处 `pool = link_job_pool` |
| 7 | 汇编冒烟 | **PASS** | `s5.log:7` `obj ok`；`smoke.o` 456 B；S5 日志 `error|warning` 匹配 **0** |
| 8 | `llvm-lit` 入口确定 | **PASS** | `.work/build/llvm/bin/llvm-lit` 2005 B、`-rwxr-xr-x`、`--version` → `lit 23.1.1dev` rc=0 |
| 9 | 仓库工作区零改动 | **PASS** | 见上「baseline 逐字节比对」；另独立复算 20 个非任务 dirty 文件内容 sha256 → **20/20 无差异** |
| 10 | MC lit 套件全绿 | **BLOCKED（维持）** | 属 `INTEG-101t`。**未报 PASS**。替代证据：#3/#5/#7 已证 `llvm-mc` 可用且能驱动 DADAO 后端 |
| 11 | 内存未耗尽 | **PASS** | `oom_kill` 基线 0 → 当前 **0**；`journalctl -k` 可读 **988** 行（故匹配 0 非「读不到」）、OOM 关键词匹配 **0**；`make_rc=0` ≠ 137。`dmesg` 实测不可读（uid=1000），已按修正后判据绕开 |

### 本轮验收的两项记录

**记录 1（任务书判据缺陷，不影响本次结果）—— S3 第 7 项原口径过弱**

`falsify.log` 的对照行给出**直接证据**：任务书 S3 的 `find .work/build/llvm -maxdepth 4 -name '*DADAO*' -print -quit`
**不区分文件与目录**，在两个反例下仍判「已构建」——
① 合成树 `fx4-dironly`（只有 `lib/Target/DADAO/.placeholder`）→ 原口径 **OK**；
② 0 字节的 `libLLVMDADAOCodeGen.a` → 原口径 **OK**。
这证实了 engineer 在完成区中「加严」的诊断**成立**，且加严判据**确有可达 FAIL 路径**
（`fx4-dironly` / `fx4-zerobyte` / `fx4-emptyarch` / `fx4-fewlibs` / `fx4-nomember` 五个反例全部 rc=1）。

但须如实指出：**加严判据并未写进任务书 S3 脚本**，只存在于完成区的散文字述与
`gate-selftest.sh` 的 G2 中；`s3.log:7` 记录的仍是原口径的目录命中。
⇒ **验收 #4 的结论成立**（主会话已用更强的独立判据在真实构建树上复算：5 个非空库 + 4 个归档成员），
但**任务书正文的 S3 判据本身偏弱**。修 S3 脚本属**修改任务书规格**，超出「事实记录」范围，
**须经用户确认**（记入 `deferred.md`）。

**记录 2（非缺陷，驳回 reviewer 的疑虑）—— 验收 #5 段终止条件**

`falsify.log` 的 `#5 N6`（段内删除 + 段后**不隔空行**追加 `dadao`）判据返回 **0（仍判 PASS）**。
主会话独立复核判定这**不是假阳性**：`Registered Targets:` 由
`printRegisteredTargetsForVersion` 打印，是 `llvm-mc --version` 输出的**最后一段，其后无任何内容**
（已验证段后非空行数 = 1，即 `dadao` 本身）。既然该段未终止，「段后紧邻的一行」在物理上仍属该段，
判 True 是**语义正确**的。真实缺陷形态（`dadao` 未注册）已被 N1 正确判 FAIL。
补测两个变体均正确失败：段后**隔空行**追加（N7，rc=1）、段后追加**空描述**（N8，rc=1）。
⇒ 判据的可达假阳性路径在当前输出格式下**不可达**，不构成缺陷。

> **与复核更正 C 的关系（澄清，非冲突）**：更正 C 报的「`independent2.py` 反例3 期望 False 实际 True、
> 1 处不一致」指的**正是**本记录讨论的同一个变异。二者不矛盾：C 报的是**现象**（harness 打了个 ❌），
> 本记录解释的是**成因**（该变异构造本身有误 —— 真实输出末尾无空行，被追加的行并不在段外）。
> 更正 C 的价值在于**独立复现了主会话 harness 的真实输出**（rc=0 / 2 行 ❌），从而证明该现象可复现而非笔误。

### 结论

**Accepted**（经用户决定：跳过 architect 交叉复核，见上文【主会话补记 A2】）。

理由：(1) 11 项验收 10 PASS + 1 BLOCKED（#10 维持 BLOCKED 交 `INTEG-101t`，未虚报）；
(2) 全部检查器均已**亲自注入反例并取得真实非零退出码**，注入非空已逐对比对证明，空注入数 0；
(3) baseline 三件套审查前后**逐字节一致**，源码树与构建树未被污染，无需 §11.4 污染处置；
(4) 完成区与真实输出逐条对齐 —— 本轮共发现 **7 处失实/不精确**，**均在完成区内当场更正**：
①「三轮 configure」实为 2 轮（主会话派发后核对时更正）；
②–⑦ 即子代理落盘的**【复核更正 A–F】** 6 处（主会话逐条独立复核后确认全部实质成立，见上表），
其中 A 更正了 engineer 手写的**不存在的哈希值** `5a3ebd72`、C/D/E 更正了**主会话自己**的表述与 harness；
另有 **1 处任务书判据偏弱**（下方记录 1，不影响结论）；
(5) engineer 登记的 3 处自身缺陷与 2 项能力缺口**均如实，未掩饰**。

### 主会话 harness 的已知缺陷（由复核更正 C/D 揭出，当场登记）

`/tmp/opencode/INFRA-105t/main-verify/independent.py` 与 `independent2.py`：
两者都会正确**打印** ❌ 并在末行汇总「存在不一致」，但**进程 rc 恒为 0** ——
即**无法从外部观察到失败**，不满足「验证脚本必须能失败」的外部可观测性要求。
二者性质是**核对报告**（供人读）而非**门控**（用于阻断），故其 ❌ 未被自动消费；
但若后续把它们当作门控复用，会得到假绿。**正确用法**：只读其 stdout 并检查是否含 `❌`，
或改写为 `sys.exit(1 if bad else 0)`。判据逻辑本身经 `reviewer/scripts/independent2-reviewer.py`
（10 用例 0 不一致）与主会话 `independent2.py` 二次复测确认**无误**。
