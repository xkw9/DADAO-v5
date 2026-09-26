# 暂缓 / 备忘（Deferred / Backlog — `.xkw`）

> 本文件记录**已知但本轮不做**的项。`.tao/knowledge/deferred.md` 是原项目的登记处，**只读**；本文件只记 `.xkw` 自己的轮次产生的新发现。
> 正式工作仍走 `.xkw/tasks/`。

## infra

- **组件源 `sjtu` 已失效**（2026-09-25 实测）：`mirror.sjtu.edu.cn` 与 `mirrors.sjtug.sjtu.edu.cn` 互相 302，构成死循环。`manifests/components.lock.toml` 两个组件的 `[[component.source]]` 仍指向它。
  - **当前不阻塞**：`.cache/` 预填后 `fetch.py:47-61` 的 `sync_mirror()` 因 `has_commit()` 命中而**完全短路、不联网**。
  - **隐患**：`.cache` 若被清空，`make fetch` 会执行 `git clone --mirror`（**全量历史**，llvm-project 约 30 GB / 数小时）打到死循环 URL ⇒ 先长时间等待再失败。`clean_work.py` 只清 `.work/` 故正常流程不触发。
  - **归属**：`INFRA-107t`（后续任务，不在 M1 复现关键路径）。

- **宿主 ssh 代理隧道**：`127.0.0.1:7890` 的监听进程是 **`sshd: ubuntu@notty`（SSH 远程端口转发隧道）**，2026-09-25 已运行 7h31m，且**未设任何环境变量**（env / git config / `/etc/environment` / apt / pip / shell rc 全无 proxy）。
  - **不得当作基础设施**：外部会话，说断就断；M1 构建需连跑 1.5–3 h。
  - **本轮结论**：全程裸连。TUNA 裸连 6.08 MiB/s vs GitHub 经代理 0.87 MiB/s（实测后者 240 s 未完成 285 MiB）。

- **QEMU meson 版本**（`INFRA-106t` 的不确定项）：**已于 2026-09-26 解除**。原判「jammy apt 仅 0.61.2 ⇒ 版本差两个大版本 ⇒ 依赖 pip 下载」**不成立**——宿主实测**未安装** meson，且 `meson-1.11.1-py3-none-any.whl` **已随 QEMU 源码 vendor 在 `python/wheels/`**（`pythondeps.toml:22` 钉 `installed = "1.11.1"`）⇒ **取 meson 完全不依赖 PyPI**。真正的卡点见下一条。

- **`Makefile:8` 单一 `$(PYTHON)` 服务两类互斥需求**（2026-09-26 `INFRA-106t` 第 1、2 轮执行实测确认，**根因，非推测**）：
  - 仓库工具链（`Makefile:30` `component-enabled`、`Makefile:55` `manifest_check.py`，`tools/infra/*.py` 另有 6 处 `import tomllib`）需要 `tomllib` ⇒ **Python ≥ 3.11**；宿主只有 3.10.12 / 3.12.14。
  - QEMU 构建（`configure` → `mkvenv.py` → `pip install -e python/`，PEP 517）需要 `setuptools.build_meta`；宿主 jammy 的 `python3-setuptools 59.6.0` 是**为 3.10 构建**、`__init__.py:10` 依赖 3.12 已移除的 `distutils` ⇒ **只有 3.10 可用**。
  - ⇒ **两侧在宿主上互斥**。且绕不过去：3.10 上 `component-enabled` rc=1 ⇒ 打印 `refusing to fake success` + `exit 1`，**验收 #2 反而翻成 FAIL**。
  - **本轮处置（绕过，用户 2026-09-26 选定「方案 C」）**：`tools/infra/install_tomllib_shim.py` 给 3.10 补 `tomllib`（`tomli` + user site-packages 里的同名 shim），使 `Makefile:8` 的默认值**无需修改**、裸 `make build-qemu` 即可用。选它的理由：3.10 侧 `setuptools` 已实测可用、无需任何 pip 动作；零仓库改动、零 root。**已否决的替代**：`apt install python3.11` 与 `pip --user setuptools>=70` 给 3.12（两者都要改 `Makefile:8` 才能让裸 make 走通；前者还未经实测）；`--target /tmp` + `PYTHONPATH`（**不持久**，且实测会遮蔽 3.12 的真 stdlib tomllib）。
  - **本条是待根治项，不是已完成项**：`Makefile` 的设计缺陷仍在。正解是让 `Makefile` 为工具链与 QEMU 构建**分别选择解释器**（例如独立的 `TOML_PYTHON`），或把工具链的 `tomllib` 依赖降到 3.10（`tomli` fallback）。**归属**：独立任务，不属 `INFRA-106t`（其「不在范围内」明确含「修改 `Makefile`」）。
  - **注意 shim 的落位敏感性**：必须放 **user site-packages**（`~/.local/lib/python3.10/site-packages/`，排在 `sys.path` 的 stdlib **之后**）才安全 —— 3.10 无 stdlib `tomllib` 故命中 shim，3.11+ 真 stdlib 优先不被遮蔽。若改放 `PYTHONPATH`（排在 stdlib **之前**）则**会遮蔽 3.12 的真 tomllib**（已实测）。安装脚本会自验证这一项。

- **`doctor.py` 不检查 QEMU 依赖**：`.tao/knowledge/deferred.md` 已登记。`INFRA-102t` S1 手工装了 `libglib2.0-dev`/`libpixman-1-dev`/`libfdt-dev`/`pkg-config`，但**没有任何脚本会检查它们** ⇒ 换机复现时容易漏装。本轮沿用 `.tao` 的登记，不重复登记；根治（扩展 `doctor.py` 的 QEMU 依赖面）属独立议题。

- **`INFRA-104t` 一次性自审 harness 不入库**（2026-09-26 经用户确认）：该任务书里 15 个 checker（`s0.sh`、`snapshot_cache.py`、`check_subjects.py`、`check_llvm_all_targets.py`、`verify_outputs.py`、`verify_repo_baseline.py` 等）**已随任务书入库**——它们逐字嵌在 `INFRA-104t` 任务书的代码块中（engineer 验证 15/15 字节一致），任务书是入 git 的文件，脚本本体因此已在非易失位置。真正只存在于 `/tmp/opencode/INFRA-104t/` 的是**一次性自审 harness**（11 组 A–K）与两个额外检查器（`verify_transcription.py`、`reverify-aggregate.sh`），其服务的日志在 `.work/log/infra/`，而 `.work/` 被 `.gitignore` 整体忽略、本身不入库。
  - **判据**：项目规则以「产物是否入库」为准 —— 既然这些日志不入库，其生成器无强制入库义务。
  - **结论**：**不入库**，不落 `tools/infra/`，也不落 `.work/INFRA-104t/`。若将来 `INFRA-105t`/`106t` 需要同类 decodetree/CMake/Subject 结构门禁，届时按当轮需要重新实现并随产物入库，不复用本轮 `/tmp` 副本。

- **QEMU 构建依赖网络**（`INFRA-106t` 第 3 轮实测，2026-09-26）：`configure` 阶段从 gitlab 拉了 `keycodemapdb` 等 **3 个 subproject** 到 `.work/source/qemu/subprojects/`。`meson-1.11.1` wheel 是 vendor 的（不需 PyPI），但 **subprojects 不是** ⇒ **离线环境无法重建 QEMU**，须另行预填。这是 `INFRA-103t` 上游镜像议题在 QEMU 侧的延伸；`fetch.py` 当前只处理 `manifests/components.lock.toml` 里的组件，**不覆盖 QEMU 的 subprojects**。
  - **归属**：`INFRA-107t`（镜像/预填）或 `INTEG-101t`（若重装机器）。**本轮不阻塞**（网络可用）。

- **零内容 ROM 下 `qemu-system-dadao` 以 SIGFPE 退出**（`INFRA-106t` 第 3 轮实测，主会话独立复现）：`-M dadao-m1 -bios <8B零> -kernel <8B零> -display none -nographic` ⇒ 打印 `QEMU 11.1.1 monitor … (qemu)`（**机器已启动**）后退出码 **136 = 128+8 = SIGFPE**。
  - **不是**构建缺陷、**不是**参数问题（`is required` 出现 0 次；3 组阳性对照均正确报错）。
  - 对照：**0 字节** ROM 则在加载阶段被拒（`could not load ROM image …: empty file`，exit 1）。
  - **归属**：`INTEG-101t`。这是**语义层**的第一个真实观察点，**不得**在 `INFRA-106t` 语境下被当成任何正确性证据。

- **`INTEG-101t:114` 的陈旧机器名 `dadao-m`**：`INFRA-106t` 三轮实测真值均为 **`dadao-m1`**（`-M ?` 输出、源码 `hw/dadao/dadao-machine.c:123`、`tools/qemu/smoke-dadao-m1.sh:26/:47`）。该处**越界未改**（属 `INTEG-101t`），派发前须先更正，否则 `INTEG-101t` 的验收会因机器名不存在而假失败。
  - **✅ 已就地更正（2026-09-26，任务书预检修正 P5）**：同时把判据从「`-M ?` 含 `dadao`」收紧为**精确机器名 `dadao-m1`**。收紧有实效：实测 `grep -qw 'dadao-m'` rc=1，而旧的子串判据 `grep -q 'dadao-m'` 会被 `dadao-m1` 平凡满足、也会被 `dadao-mfoo` 之类骗过。`INTEG-101t` 已 `已验证`，`dadao-m1` 实测成立。

- **`Makefile` 的 `build-mc: PASS` / `build-qemu: PASS` 不验产物**（2026-09-26 `INTEG-101t` reviewer 发现，**未修**）：两个目标的收尾都是**构建命令之后无条件 `@echo`**，**不检查产物是否存在 / 非空 / 可执行**（`Makefile:87`、`:98`）。只有当构建命令本身非 0 时 make 才会中止（故「不伪造失败」成立），但「构建返回 0 而产物缺失/0 字节」会照样打印 `PASS`。
  - **与 `INFRA-106t` B21 同类**（那次是判据只查存在性，0 字节产物通过；这次是判据根本不查产物）。
  - **不影响 `INTEG-101t` 结论**：其验收 #6 另有 `qemu-system-dadao -M ?` 必须列出 `dadao-m1` 一步，那一步**确实验产物存在且可运行**（reviewer C9 反例：查 `dadao-m2` rc=1、二进制不存在 rc=127）。故 #6 整条不空。
  - **待办（未做）**：`Makefile` 在 `INTEG-101t` 的禁改范围内，修它属独立任务。建议加 `-test -x`/`-size +0` 校验，或让收尾改为校验具体产物路径。**须经用户确认后执行。**

- **`tests/lit/E2E/` 三个 smoke 测试无输出校验**（2026-09-26 `INTEG-101t` reviewer 实测，**未修**）：`smoke_add.test` / `smoke_arith.test` / `smoke_jump.test` 各 3 条 `# RUN:`（`llvm_mc` → `llvm_objcopy` → `qemu -M dadao-m1`），但 **0 个 `FileCheck`、0 个 `# CHECK`/`ASSERT`/`EXPECT`** ⇒ lit 只验「整条 RUN 流水线退出 0」，**不验 add/jump/arith 的运算结果**。
  - **性质**：纯 smoke / 覆盖证据（证明工具链能汇编、QEMU 能起机并跑完），**不得当作语义正确性证据**。语义由 L5 硬门槛（`run_qemu_test.py` 747 条向量）承担。
  - **有牙齿的部分**：reviewer 把 RUN 行里的 `-M dadao-m1` 改成 `-M dadao-mX` ⇒ `Passed: 2 (66.67%)`、rc=1（见任务书 R.3 C12）。即「能跑通」这一侧是实的，缺的只是「结果对不对」。
  - **待办（未做）**：若要让 L7 承载语义，须引入 `.s` + FileCheck 期望或读回寄存器/内存。**须经用户确认后执行。**

## llvm / 跨模块

- **3 个脚本硬编码旧仓库路径**（2026-09-25 发现）：

  | 文件 | 行 | 内容 |
  | --- | --- | --- |
  | `tools/llvm/gen_m1_asm.py` | 169 | `open('/mnt/tao/DADAO-v5/contracts/opcodes.yaml')` |
  | `tools/llvm/test_m1_asm.py` | 24 | `llvm_mc = '/mnt/tao/DADAO-v5/.work/build/llvm/bin/llvm-mc'` |
  | `tools/llvm/test_encoding_oracle.py` | 335 | 同上 |

  仓库已从 `/mnt/tao/DADAO-v5` 移至 `/home/ubuntu/DADAO-v5`。
  - **本轮处置**：`INFRA-102t` S4 建宿主符号链接 `/mnt/tao/DADAO-v5 → /home/ubuntu/DADAO-v5` 绕过（与原环境一致，仓库零改动）。
  - **根治**：改为从 `__file__` 推导仓库根。**未排期**。

- **`.tao/knowledge/MEMORY.md:13` 的 harness 基线已过期**：记的是 `597/590/2/5/0`（`TESTCASES-010t`/`011t` 补 150 条向量**之前**）。权威基线是 `QEMU-021m` 里程碑记录的 **`747 total / 739 passed / 0 failed / 8 deferred / 0 errors`**。
  - **本轮处置**：`INTEG-101t` 以 `QEMU-021m` 为准；`.tao/` 只读故不改。
  - **影响面**：任何引用 597/590 的文档或记忆都需按此更正。

## 流程 / 约定

- **`.xkw` 任务号采用 1xx 段**（`INFRA-101k`~`107t`、`INTEG-101t`）：`.tao/tasks/` 已占用 `INFRA-001k`~`014m` / `INTEG-001k`~`004m` 且**只读**，同号会导致跨树引用歧义（如 `.xkw` 的 `INFRA-002t` 与 `.tao` 的 `INFRA-002t-仓库与构建骨架` 内容完全不同）。三位编号、模块内递增的约定不变。

- **`.xkw/knowledge/adr-*` 采用 `1xxx` 号段**（用户 2026-09-25 裁定）：首个为 `adr-1001`，此后递增；**不与** `.tao/knowledge/adr-*` 的 `0001`–`0011` 共享编号空间。原按「接最大值 `0011` 之后」拟的 `adr-0012` 已改号作废——两棵树编号空间分离比共享更不易撞号。同理 `.xkw/tasks/` 采用 `1xx` 段避开 `.tao` 已占用的 `001`–`014`。

- **`llvm-lit` 不由 `Makefile` 构建**：`Makefile:87` 的 ninja 目标列表不含 `llvm-lit`，而 `tests/lit/*/lit.cfg.py:28-30` 优先读 `config.llvm_tools_dir`（`llvm-lit` 才会设）。本轮用 `ninja llvm-lit` 或 `LLVM_TOOLS_DIR` + `llvm/utils/lit/lit.py` 兜底（`INFRA-105t` S4 记录实际采用哪条）。根治（把 `llvm-lit` 加进 `build-mc` 目标列表）属独立议题。
  - **✅ 2026-09-26 `INFRA-105t` 已实证澄清（前半条保留作历史）**：`bin/llvm-lit` **确实会由 configure 生成** —— `llvm/CMakeLists.txt:917` `LLVM_INCLUDE_UTILS` 默认 ON → `:1499 add_subdirectory(utils/llvm-lit)` → `utils/llvm-lit/CMakeLists.txt:5,49-51` `get_llvm_lit_path(...)` + `configure_file(llvm-lit.in ...)`。全树无 `add_custom_target(llvm-lit)`，故 `ninja llvm-lit` 会报 `unknown target`（**原兜底预案是错的，已删**）。实测 `.work/build/llvm/bin/llvm-lit` 2005 B、`lit 23.1.1dev`、rc=0，**无需 `lit.py` 兜底**。
  - **仍待办**：`Makefile:86` 的 ninja 目标列表不含 `llvm-lit`，故**增量重建时不会被重新生成**（`rm bin/llvm-lit` 后跑 `make build-mc` 不会补回，需重跑 cmake）。根治仍属独立议题。

- **`make prepare` 非幂等**：`.tao/knowledge/deferred.md` 已登记。对全新工作树不触发；重复执行会报 `HEAD is not its base commit`，应 `make clean-work` 后重来，**不得手工 reset 掩盖**。

- **`.opencode/agents/reviewer.md` 未限制 `shell` ⇒ prompt 级只读约束无效**（2026-09-26 `INFRA-104t` `/complete` 事故）：reviewer 角色文本要求「反例注入只在 `/tmp` 副本进行、不得触碰真实仓库」，但 frontmatter 只限制了 `edit`（及 `webfetch`），`shell` 未设 `deny`。降级模型据此在真实仓库执行 `git add` / `git restore`，把 `.xkw/knowledge/MEMORY.md` 的 9507 B 未提交内容破坏；其报告里「status SHA256 `a580c726…` 逐字节相同」一句经实测为**假**（该轮验收结论整体作废，内容已从 reviewer 自留的 dangling blob 逐字节恢复，sha256 `4163b880…`）。
  - **根因**：只读/只注入约束写在 **prompt** 里，权限层未强制。降级模型（`nemotron-3-ultra-free`）会违反自身角色文本。
  - **待办（未做）**：给 `reviewer.md`（并复查 `architect.md` / `engineer.md`）的 `shell` 加 `deny`：禁 `git add/checkout/restore/stash/commit/clean/reset`、禁写 `/home/ubuntu/DADAO-v5/**`；注入只许落在 `/tmp`。**须经用户确认后执行**。
  - **过渡办法（已用）**：`INFRA-104t` 的 reviewer 职责由主会话代行（`workflow.md` §11.2 偏差），并以「真实仓库只读 + 注入只落 `/tmp/.../accept/` + 逐条真实 exit code」硬约束执行。
  - **取证**：`/tmp/opencode/INFRA-104t/reviewer/REVIEW_REPORT.md` §5、`reviewer/injection-tests/debug_pre_hash.py:7,21-24,39-40`。
  - **事故残留已清理（2026-09-26，经用户确认）**：事故在 `.git/objects` 留下 2 个 dangling blob（`de0676c2…` 9519 B、`c7cfc180…` 9531 B）。逐字节核验确认**两者都不含独有内容** —— 都是已知正确的 `MEMORY.md`（9507 B，sha256 `4163b880…`）后追加了一行 `\n# MODIFIED\n`（分别为第 1、2 次注入标记，`diff` 只有 2 行差异）。正确内容另有 4 份副本在 `reviewer/memory-recovered/`，两个 blob 原文也已另存 `reviewer/memory-dangling-blobs/`。随后删除这 2 个 loose object 并 rmdir 变空的 fanout 目录：`count-objects` 22 → 20，`git fsck` 0 dangling/unreachable 且无任何报错，两个 OID `cat-file -e` 均失败；HEAD `69a5967…`、HEAD tree、332 个提交、reflog 全部不变，`git status` 逐字节未变（`a580c726…`），`git diff --check` rc=0，两棵源码树与两个 mirror 未受影响。
  - **✅ 已修（2026-09-26，经用户确认采纳方案 A）**：`reviewer.md` 的 `shell` 权限从「完全没写条目＝全放开」改为
    39 条规则 —— 只读 git（`status/diff/log/show/rev-parse/rev-list/merge-base/ls-remote/cat-file`）、
    字节比较（`cmp/diff/grep/sha256sum/wc/find/ls`）、解释器（`python3*/bash/sh`）放行；
    改写工作树/索引/历史的 15 个 git 子命令（`add/restore/checkout/stash/commit/clean/reset/rebase/cherry-pick/am/apply/worktree/gc/fetch/push`）**硬 deny 并排在全部 allow 之后**（规则按最后一个匹配项生效）。
    探测证据（`/tmp/opencode/INFRA-104t/perm-probe/`）：只读 4 条 allow 成功；`git stash list` / `git add --dry-run` / `git commit --dry-run` / `git push --dry-run` 4 条**全部** `Permission denied: shell`；探测后 status 逐字节相同、20 条 dirty 哈希无一变化、0 新 stash、0 新 git 对象。
    **同时把 `workflow.md` §11.1 的审查前快照升级为三件套 + 审查后强制逐字节比对**（不一致即本轮作废）—— 这才是真正的保证，权限只是减速带。
  - **⚠ 残留（已实测，不可当防护）**：`shell: * → ask` 在子代理里**不生效**（非交互 client 无人应答即放行），实测未列举的 `echo` 直接成功。所以子代理的 shell 策略实质是 **deny-list**，不是 allow-list。已写入 `workflow.md` §11.1 第 5 条。
  - **仍存在的绕过口（结构性，无法用权限规则消除）**：`bash -c '…'` / `python3 -c '…'` 内部可执行任意命令。彻底消除需 B（reviewer 零 shell，改「设计-执行」分离）或 C（给 reviewer 仓库副本沙箱），**本轮不做**。

- **`verify_repo_baseline.py` 的 `load_hashes` 对空基线未优雅失败**（2026-09-26 代行验收发现）：`raw.split(maxsplit=1)` 未防空行，基线哈希文件为空或仅含空行时抛未捕获 `ValueError: not enough values to unpack`，而非干净的 `SystemExit` 报错。行为仍 fail-closed（非零退出），真实派工基线含 19 条 dirty 故未触发。
  - **影响面**：该 checker 逐字嵌在 `INFRA-104t` 任务书 block19；`INFRA-105t`/`106t` 若复用需先补 `if not digest or not name: continue`（或改 `split(maxsplit=1)` 前判空）。**本轮不改**（改动会破坏 15 脚本转写基线，须重新声明）。

- **停止子代理不保证其停止写盘**（2026-09-26 `INFRA-105t` `/complete` 发现）：reviewer 被「强制停止」后**仍在后台继续写任务书** —— 主会话首轮 §11.1-3 比对时为 `4a560320`（326 行），数分钟后已变为含 6 处 `【复核更正 A–F】` 的版本（写入位置在完成区内部，用了划掉+标注，符合 `workflow.md` §11.2 第 7 条）。与主会话随后写入的代行验收段区域不重叠、连测 3 次 sha256 稳定，**属运气而非机制保证**。
  - **待办（未做）**：`workflow.md` §11 增加一条 —— 停止/取消子代理后，**必须重测其写入目标文件的 sha256 若干次确认稳定**，再继续主会话写入；发现仍在变动应先等待或隔离。当前规则无此约束。
  - **取证**：任务书 L216/234/243/247/255/300 的 6 处 `【复核更正 A–F】`（主会话已逐条独立复核，全部实质成立，见任务书代行验收段）。

- **`INFRA-105t` 跳过 architect 交叉复核 ⇒ 首个无异模型验收的 `.xkw` 任务**（2026-09-26，经用户明确决定）：§11.3 的 architect 已下发但**零产出即 `Task cancelled`**（会话 `ses_f22bbf3d9ffeSpw8Um0U1zr3l5`，`opencode/nemotron-3-ultra-free`，连 `/tmp/opencode/INFRA-105t/architect/` 目录都未创建）。按 AGENTS.md「确未落盘 → 停止并汇报、不得自行重试」停手上报，**用户决定跳过 architect 直接置 `已验证`**。
  - **后果**：`INFRA-105t` 的 reviewer（主会话代行）、engineer 三者同属 `opencode/big-pickle` 系，「规划/审查与代码必须使用不同模型」（`workflow.md` §4）**在本任务上未被满足**。结论的独立性仅建立在「主会话逐项独立重算 + 46 项判据全部注入反例取得真实非零退出码 + baseline 三件套逐字节比对」之上。已在任务书【主会话补记 A2】与 `MEMORY.md` 双处如实登记。
  - **待办（未做）**：本轮两次子代理异常（reviewer 35 min 无报告被停止、architect 零产出取消）**均为 free 档模型 + 后台长时运行**。是否要改用非降级模型、或把长时任务拆小，**须经用户确认**（涉及 workflow §4 角色表与 ADR-1002 的模型决策，不擅自改）。
  - **未受影响的部分**：architect 为只读角色，baseline 复查确认 status 21 路径逐字节未变、20 个非任务 dirty 文件 20/20 未变、两棵源码树 dirty=0、`.work/build` 0 个文件被改 ⇒ **取消未造成污染**。

- **`INFRA-105t` 任务书 S3 第 7 项判据偏弱**（2026-09-26 代行验收发现，**未修**）：S3 的 `find .work/build/llvm -maxdepth 4 -name '*DADAO*' -print -quit` **不区分文件与目录**，实测对「只有同名空目录」和「0 字节 `libLLVMDADAOCodeGen.a`」两种反例**均判已构建**。engineer 已在完成区记录了加严判据（`-type f -size +0` + `ar t` 成员数 > 0 + 5 个非空 `.a`）并证明其有可达 FAIL 路径，但**加严判据未写进任务书 S3 脚本**，`s3.log:7` 记录的仍是原口径的目录命中。
  - **不影响本任务结论**：验收 #4 已由更强判据在真实构建树上独立复算（5 个非空库 + `libLLVMDADAOCodeGen.a` 8478110 B / 归档成员 4）。
  - **待办（未做）**：修 S3 脚本属**修改任务书规格**，超出 `workflow.md` §11.2 第 7 条「事实记录」范围，**须经用户确认**。
  - **📌 2026-09-26 `INTEG-101t` 已 `已验证`** ⇒ 原「建议与 `INTEG-101t` 一并处置」的时机已过，**此项现在是独立的待裁决项**：要么就地修 `INFRA-105t` 任务书 S3 脚本，要么正式记为「不修」。**仍未擅自改动，等用户裁决。**
