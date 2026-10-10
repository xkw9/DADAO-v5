# MEMORY — DADAO-v5 自有项目记忆（`.xkw`）

## 这是什么

在克隆来的 DADAO-v5 项目基础上做开发。`.tao/` 是原项目的交互目录，**只读参考、不改动**；自己的任务文件、知识库、流程规则全部放在 `.xkw/` 下（结构照搬 `.tao`）。

## 当前状态

- 2026-09-29：**`TESTCASES-101t` 已验证（F1 schema 与 oracle 接口冻结）**——M1 747 向量保持兼容；新增 RF/FCSR/bit-pattern/facet/六键 schema、testcases 唯一 oracle I/O、19 条正样例/53 条反样例及独立整数重算。validator、context、I/O 与 39/39 可复原反例通过；root/log 正确舍入、`rootn(-0,2)` 与 canonical qNaN 常量仍保持 BLOCKED/unspecified。审查期间唯一新增的外部汇报 `docs/progress-report-2026-09-29.md` 经用户明确排除，72 条 baseline 路径/哈希保持；最小证据返工后 reviewer 与 architect（均按用户要求使用 GPT-5.6 Luna）Accepted。下游 QEMU-101t 现获得 schema 接口前置；LLVM-101t 仍可独立推进。

- 2026-09-28：**`SPEC-104t` 已验证；ADR-1009～1015 已 Accepted**——主会话按用户授权直接完成 lifecycle 返工并跳过后续复审：G13 支持全 Candidate 与全 Accepted 两种一致状态、拒绝混合状态；Candidate/Accepted 三态临时树均已验证，新增 CE-29b；全量反例 100/100。`--require-active` 已在激活后复跑。D17 仍为六键 active，S2 trace-only、S7 Closed by spec；下游 TESTCASES/LLVM/QEMU/INTEG 仍未执行，语义 Accepted 不等于实现或 E2E PASS。

- 2026-09-28：**`/plan SPEC-104t` 已通过 architect/reviewer 交叉审查并落盘**——新任务 `SPEC-104t` 处于待开始，将在不改写 `SPEC-102t/103t` 历史证据的前提下，为 ADR-1009～1015 的 27 条已逐条用户确认 decision 建立机器 resolution 投影、独立 checker/反例和 10 本下游任务书加 `INTEG-104m` 同步。ADR 仍全为 Candidate，必须在该任务 `/complete` 双角色 Accepted 后才由主会话置 Accepted；`--require-active` 在此之前预期非零 BLOCKED。当前关键路径改为 `SPEC-103t → SPEC-104t → TESTCASES-101t`。D17 active 仍为六键，S2 trace-only、S7 Closed by spec；现行 S6 范围由历史 six 经 `6-1+5` 投影为 D11 十条 rf0 写白名单。SimRISC-03:7-8 为 HTML 注释，非当前语义 authority。

- 2026-09-28：**`SPEC-103t` 已验证，ADR-1008 已 Accepted**——94 项 proof 检查、48/48 可复原反例、raw spec 复核及 reviewer 自注入均通过；active ledger 为 S1/S3/S4/S5/S6/S8，S2 trace-only，S7 为 RD/RF non-overlap 的历史 non-gap，状态 **Closed by spec**（非运行时 PASS）。D11 消费者映射已补齐。下游任务书仍有旧七键措辞，须在各自 dispatch 前先同步。

- 2026-09-27：**ADR-1008 已建为 Candidate，D1 已由用户确认**——SimRISC-00 明示 RD/RF 是独立寄存器组，SimRISC-03 的 `rd2rf`/`rf2rd` 方向固定，故历史 `D17:S7` 是 spec-determined non-gap，不再是 active OPEN 门禁。`SPEC-102t` 不回溯改写；`SPEC-103t` 处于待返工，将以六键 active ledger（S1/S3/S4/S5/S6/S8）修正 proof、消费者映射和反例。S2 仍为 ledger 外 trace-only；旧下游七键任务书在各自 dispatch 前须另行同步。

- 2026-09-27：**`SPEC-103t` 规划可执行性已修订**——`SPEC-102t=已验证` 的状态漂移已同步到 `SPEC-101k`；`SPEC-103t` 现自包含地规定 `contracts/f1_gap_proofs.yaml`、SPEC checker/反例、64 identity 影响矩阵与无环消费者映射。D11–D17 和七项 D17 OPEN-ID 仍只产生无选择的 Candidate 输入；S2 保持 ledger 外 trace-only。本轮仅更新任务书和路线摘要，无 ADR decision、实现或提交。

- 2026-09-27：**`SPEC-102t` 已验证（F1 合约、64 identity 与 D17 ledger）**——64=18+46、pseudo 排除、编码/legality/source 投影和 8 条 RF 对齐/MALIGN 规则均由 spec 独立核对；D17 ledger 精确包含 `D17:S1,S3,S4,S5,S6,S7,S8`，全为 BLOCKED，S2 仅为 ledger 外 trace-only。`d17_open_ids` 已投影到 64 条机器记录，74 项合约检查、119 引用/32 语义锚点、36/36 可复原反例、编码/QFC 校验均通过；reviewer 与 architect 均 Accepted，审查 baseline 45 路径/哈希一致。未选择运行语义、未创建或修改 ADR；下一关键任务为 `SPEC-103t`（缺口逐键证明与 Candidate 输入）。

- 2026-09-27：**F1 D17 门禁规划已修订（`SPEC-101k` 保持已验证）**——`SPEC-102t` 仍为 **待返工**，须返工后重新经 reviewer+architect Accepted 才满足下游依赖。`SPEC-103t` 将产出精确包含 `D17:S1,S3,S4,S5,S6,S7,S8` 的 OPEN-ID ledger；S2 仅作“no behavioral consequence”的台账外来源追踪，不得记 PASS。TESTCASES/QEMU/INTEG 按适用 facet 消费该 ledger；LLVM MC 仅对运行期行为 N/A，不能据此解锁语义。已移除不存在的 `TESTCASES-103t` 路线引用；本轮未选择语义、未创建/修改 ADR、未执行实现或提交。

- 2026-09-27：**`INFRA-108t` 已验证（F1 隔离基线）**——建立 `.work/f1/source/{llvm-project,qemu}`（各 M1 8-patch 头、clean）和 F1 build 入口；M1 `.work/source/**`、`.work/build/**` 与两组件 `0001`–`0008` 的 18 条 hash 均受门禁保护，F1 仅支持未来连续 `0009+`。`make f1-check` 32/32、离线 replay、M1 entrypoint 4/4 均通过；F1 完整功能构建维持 BLOCKED（无实现补丁，QEMU 离线缺 subprojects）。reviewer 独立注入 0008 改写、错基线、跳号、M1 build 泄漏、dirty tree 与 source/build/root 路径逃逸，均真实 FAIL 并还原复绿；用户授权本任务省略 architect 交叉复核。下一关键任务为 `SPEC-102t`（合约与 64 identity 映射）或按依赖并行推进 `TESTCASES-101t` 的准备工作。

- 2026-09-26：**F1 浮点阶段已规划（`SPEC-101k` 已验证）**——ADR-1004 D1–D18 已逐条确认；architect 已落盘 15 本 F1 任务书，reviewer 按 workflow §9 审计 **Accepted**。范围是 SimRISC-03 的 64 个真实 identity（18 RF/QFC + 46 MISC-RF）与 `set.ft`/`set.fo` pseudo；独立 oracle 属 `testcases`，不设 GOLDEN 模块。F1 使用 `.work/f1/**` 隔离树，仅从 LLVM/QEMU M1 `0001`–`0008` 后追加 `0009+`，M1 树/构建产物受保护。D11–D17 的未唯一语义保持 OPEN/BLOCKED，未来 `ADR-1005`～`1007` 仅 Candidate；`INTEG-104m` 在 64 identity required facets 闭合并保持 M1 `747/739/0/8/0` 回归后才可达成。下一动作是 `/dispatch INFRA-108t` 前的四项预检与用户确认。

- 2026-09-25：**OpenAI/Codex 接入完成**——ChatGPT 订阅经 `chatgpt-headless` 设备码登录（`auth list` = OpenAI stored）；端到端实测 `gpt-5.5` / `gpt-5.6-sol` / `gpt-6-astra` 均 OK；`gpt-5.3-codex*` 已对 ChatGPT 账号退役勿用。
  - **网络前提**：服务器直连 OpenAI 被墙，须经 `127.0.0.1:7890` 代理；**后台服务必须带 `HTTPS_PROXY` env 启动**（重启脚本留档 `/tmp/opencode/restart-svc.sh`，日志 `/tmp/opencode/svc-restart.log`）。启动方法：退出全部 TUI → `pkill -f 'opencode serve --service'` → 带 env 启动 `opencode`。
  - **模型分配与降级**：见 `workflow.md`「模型分配与降级」——architect/reviewer=`openai/gpt-5.6-sol`、engineer=`opencode/big-pickle`（审查与代码必须不同模型），不可用时降级 free 模型。
  - **调起测试通过**（API 逐项核实 agent+model 路由）；教训：**agent frontmatter 的 `description` 值以反引号等 YAML 保留指示符开头时必须加引号**，否则整个 frontmatter 解析失败、`mode: subagent` 静默回落为 primary，报 `cannot run as a subagent`（reviewer 实际踩坑）。
- 2026-09-25：**`.xkw` 启动与工作流优化完成（ADR-1002 Accepted，D1–D9 已逐条确认）**——新增 `.xkw/README.md` 统一入口、`knowledge/milestones.md` 自有路线图、只读 `/xkw-start`/`/xkw-status`、所有变更命令的统一启动快照与 fail-closed 状态门禁；现有 `/plan`/`/dispatch`/`/complete` 薄化，以 `workflow.md` 为唯一流程规则源。
- 2026-09-25：三个角色 agent 已存在于 `~/.config/opencode/agents/`；本仓新增 `.opencode/agents/{architect,engineer,reviewer}.md` 项目级优化定义（OpenCode V2 项目定义优先），DADAO 专用角色规则随仓库审计。全局文件按项目规则未修改，后续可由用户删除或泛化。
- 2026-09-26：**`INFRA-106t` 已验证（L3 构建层 · QEMU）**——`make build-qemu` 一次通过（`build-qemu_rc=0`、144 s、2359/2359 ninja 步）。产物 `qemu-system-dadao` 34.8 MB、`QEMU 11.1.1`、`-M ?` 注册 `dadao-m1`；venv `Python 3.10.12` + `meson 1.11.1`（vendor wheel，不需 PyPI）。验收 **9 PASS / 1 BLOCKED**（#10 语义 747 用例属 `INTEG-101t`）。
  - **宿主 Python 两侧互斥（3 轮执行才定位的真根因）**：`Makefile:8` 单一 `$(PYTHON)` 同时服务「工具链需 `tomllib`（≥3.11）」与「QEMU 需 3.10 的 `setuptools`（jammy 的 `python3-setuptools 59.6.0` 依赖 3.12 已移除的 `distutils`）」⇒ **3.10/3.12 各缺一半、互斥且绕不过去**。方案 C（用户选定）：`tools/infra/install_tomllib_shim.py` 给 3.10 装 `tomli` + user site-packages 里的 184 B `tomllib.py` shim，使**裸 `make build-qemu` 无需任何 `PYTHON=` 覆盖**即通过；已入库并成为任务书 S0 必做前置。**shim 必须放 user site（`sys.path` 里排在 stdlib 之后）**，放 `PYTHONPATH`（排在 stdlib 之前）会**遮蔽 3.12 的真 stdlib tomllib**（已实测）。
  - **第 3 轮成功靠的是新增 S0，不是改 `Makefile`**：前两轮分别死于 3.12 的 `BackendUnavailable` 与 3.10 缺 `tomllib`。`Makefile` 设计缺陷**未消除**，已登记 `deferred.md`。
- 2026-09-22：建立 `.xkw/` 骨架（`knowledge/` + `tasks/<module>/`）、`.opencode/commands/`（`plan`/`dispatch`/`complete`）。

### 2026-09-25：M1 复现（`INFRA-101k` 启动）

**背景**：M1 已于 2026-09-22 达成（`.tao` 六模块里程碑全部 `里程碑`），但 **`.cache/` 与 `.work/` 是指向 `/mnt/dadao-v5/` 的符号链接且两个目标目录均为空** ⇒ 上游镜像、源码树、构建产物全部不存在，M1 成果**不可复现**。本轮目标是重建并逐条复现验收基线。

**决策**（`adr-1001`，**Accepted**，D1–D3 已逐条经用户确认）：

| 决策 | 结论 |
| --- | --- |
| D1 构建路径 | **宿主机原生构建**（Ubuntu 22.04，apt 补工具链 + deadsnakes 装 Python 3.12 作并行解释器，经 `make PYTHON=python3.12` 调用，零仓库改动）。不用 Docker / chroot |
| D2 镜像站 | **TUNA 清华**（裸连 ~6.08 MiB/s，不依赖 ssh 隧道；GitHub 经代理仅 0.87 MiB/s 实测未完成） |
| D3 清单/ADR | **不改** `manifests/` 的 `source` 字段、**不改** `.tao` 的已 `Accepted` ADR；只记录 + 开后续任务 `INFRA-107t` |

**关键实测**：TUNA/BFSU/NJU 三站的 `llvmorg-23.1.1^{}` = `6dfe1677ab8dffbc6ec13d53a1e0215d75147689`、`v11.1.1^{}` = `c3d48b7d1e89604920e5b81b91140c2ad39a1943`，与 `.tao` 的 `adr-0006`/`adr-0008` D1 锁定值**逐字符相同**；克隆所得 object 数 189,410（llvm）/ 11,630（qemu）与 `adr-0006` D2 记录**逐位一致**。

**编号与版本库约定**（2026-09-25 用户裁定）：

- `.xkw/knowledge/adr-*` 取 **`1xxx` 号段**（首个 `adr-1001`，此后递增），**不与** `.tao/knowledge/adr-*` 的 `0001`–`0011` 共享编号空间。
- `.xkw/tasks/` 同样取 **`1xx` 段**（`INFRA-101k`~`107t`、`INTEG-101t`），避开 `.tao` 已占用的 `001`–`014`。
- **`.xkw/` 纳入版本库**（不写入 `.gitignore`）：任务书与知识库随仓库提交，决策与门禁可审计。宿主侧产物（`.cache/`、`.work/`）仍由根 `.gitignore` 排除。

**任务分解**（依赖链 `102t → 103t → 104t → {105t, 106t} → INTEG-101t`；`107t` 不在关键路径）：

| 任务 | 标题 | 状态 | 门禁摘要 |
| --- | --- | --- | --- |
| `INFRA-101k` | M1 复现启动与任务分解 | **已验证** | 规划、ADR-1001 与 7 个下游任务已落盘；按 ADR-1002 D3/D6 校正状态 |
| `INFRA-102t` | 宿主工具链与 Python 运行时 | **已验证** | `make doctor` PASS；`manifest-check` exit 0；Python 3.12 + PyYAML 6.0.3；旧路径兼容链接就位 |
| `INFRA-103t` | 上游浅 bare 镜像预填 | **已验证** | TUNA 浅 bare 镜像；object 189,410 / 11,630；本地短路不联网 |
| `INFRA-104t` | 源码拉取与补丁系列应用 | **已验证** | 两树各 9 commits（`base_to_head=8`/`total=9`/`shallow=true`）；`diff --name-only` 36/31 非空 |
| `INFRA-105t` | LLVM MC 构建 | **已验证** | `make build-mc` PASS（`[1553/1553]`，2235 s）；6 工具 + `bin/llvm-lit` 就位；`dadao` 已注册 |
| `INFRA-106t` | QEMU 构建 | **已验证** | `build-qemu: PASS`（rc=0 / 144 s）；`qemu-system-dadao` 34.8 MB / QEMU 11.1.1；`-M ?` 精确注册 `dadao-m1` |
| `INTEG-101t` | M1 测试基线复现与逐条对齐 | **已验证** | L0–L8 共 20 条命令全 `rc=0`、与基线**零偏差**；**L5 硬门槛**：`747 total, 739 passed, 0 failed, 8 deferred, 0 errors` + `harness_rc=0`（≈118 s），独立复算 `747 = 739 + 8`；13 个检查器全部有实测 FAIL 路径 |
| `INFRA-107t` | 组件源镜像站更正（后续） | 待开始 | BLOCKED：先 `/plan INFRA-107t` 逐条确认镜像与 ADR-1003 decisions；清单与新 ADR 一致，`.tao` 只读 |

**`INFRA-102t` 验收结论（2026-09-25）**：reviewer 与 architect 均为 **Accepted**。Ubuntu 22.04 宿主已补齐 LLVM/QEMU M1 构建依赖；deadsnakes Python 3.12.14 作为并行解释器安装，用户级 PyYAML 6.0.3 可用，系统 `python3` 保持 3.10.12；`/mnt/tao/DADAO-v5` 精确解析到 `/home/ubuntu/DADAO-v5`。`doctor` 与 `manifest-check` 均 exit 0。reviewer 对 doctor、manifest checker、综合验收脚本分别注入反例，真实得到 exit 1 / 1 / 7，且注入非空、还原后临时树干净。`llvm-mc` 可用性按用户确认保持 BLOCKED，交由 `INFRA-105t`，不计为本任务失败。

**`INFRA-103t` 验收结论（2026-09-26）**：reviewer 与 architect 均为 **Accepted**。`.cache/llvm-project.git` 与 `.cache/qemu.git` 已按 ADR-1001 D2 从 TUNA 预填为浅 bare 镜像，HEAD 精确命中 manifest 锁值，对象总数分别为 189,410 / 11,630；无 alternates、partial-clone 元数据或缺失对象，`fsck` 通过。`sync_mirror()` 在禁网桩下精确输出两条 `skipping fetch`，未创建 `.work/source`。reviewer 对 18 类判据注入非空反例并得到真实非零退出，合成树还原 clean、真实验收复绿且 dirty baseline 未变。端到端源码树重建仍归 `INFRA-104t`；失效 `sjtu` 源治理仍归 BLOCKED 的 `INFRA-107t`，均不回溯本任务。

**`INFRA-104t` 验收结论（2026-09-26）**：reviewer 职责**由主会话代行**（`workflow.md` §11.2 已声明偏差），architect 交叉复核 **Accepted**、0 BLOCKER。`.work/source/{llvm-project,qemu}` 各 9 commits（`base_to_head=8`、`total=9`、`shallow=true`、origin 为本地绝对路径、工作树洁净）；`Applying:` 16 次、两组件各 `applied 8 patches`，两条 `skipping fetch` 各 ×1、`cloned`/`updated (incremental)` 各 0，全程零联网。产物：LLVM 四 `.td` + 四目录且 `active_blocks=1 bare_DADAO=1`，QEMU `insn.decode` 274 行且 `validate_decodetree` 256/256/0/PASS；`diff --name-only` 36/31 非空。**证据强于原声明**：主会话用本地 mirror + 同一 series 在 `/tmp` 离线重建，16 个 commit 的 **tree SHA / author / author-date / subject 链完全一致**（commit SHA 本身因 `git am` 写入当前时间作 committer date 而不同，属预期）。反例注入共 **80 例**全部由预期报错命中并带 green 对照，另含转写 checker 1 例；覆盖表见任务书 §9.5.1。**验收 #10（源码可编译）维持 BLOCKED**，由 `INFRA-105t`/`INFRA-106t` 承担，结构与重放证据不得当作可编译性。

**本轮两处已声明的流程偏差（须知）**：

1. **任务书在完成区之外有 4 行改动** —— §6.5 的三行 `|| exit 1`（修 S1 假通过缺陷，经用户确认）与本轮「状态」字段行。故 `verify_repo_baseline.py --mode post` 以 dispatch 真基线运行会报 `task changed outside completion section`（rc=1），属**预期**；把已声明改动计入后同一 checker 报 PASS（任务书 §9.4 四段分解）。
2. **首个 reviewer 子会话的验收结论作废** —— 它对真实仓库执行 `git add`/`git restore`，破坏了 `.xkw/knowledge/MEMORY.md` 的 9507 B 未提交内容，且报告中「status 逐字节相同」为假陈述；内容已从其自留的 dangling blob 逐字节恢复。根因是 `.opencode/agents/reviewer.md` **只限制了 `edit`、未限制 `shell`**，prompt 级只读约束对降级模型无效。修复（给 reviewer/architect/engineer 的 `shell` 加 deny）**须经用户确认后执行**，已登记 `deferred.md`。

**`INFRA-105t` 验收结论（2026-09-26）**：reviewer 职责**由主会话代行**，architect 交叉复核**零产出即取消、经用户决定跳过** ⇒ 本任务是首个**无异模型验收**的 `.xkw` 任务，独立性缺口已在任务书【主会话补记 A2】与 `deferred.md` 双处如实登记，读者应据此折扣审视。

`make build-mc` **一次通过**（`cmake_rc=0` / `make_rc=0`、2235 s、`[1553/1553]`），**DADAO 后端 C++ 全量真编通过** —— 这正是 `INFRA-104t` 验收 #10 此前 BLOCKED、从未验证的项，**现已实证解除**。产物：`llvm-mc --version` 的 `Registered Targets:` 段含 `dadao - DADAO SimRISC`；6 工具不仅 `-x` 且实跑可用；`bin/llvm-lit`（2005 B，`lit 23.1.1dev`，rc=0）为 **configure 期 `configure_file` 产物**，无需 `lit.py` 兜底；`libLLVMDADAOCodeGen.a` 8478110 B / 归档成员 4 / 非空 DADAO 库 5 个。

两项**证据强于原判据**：① `LLVM_USE_LINKER=lld` + `LLVM_PARALLEL_LINK_JOBS=1` 不只写进 `CMakeCache.txt`，还实证生效 —— `build.ninja` `LINK_FLAGS = -fuse-ld=lld`、`rules.ninja` `link_job_pool` `depth = 1`、351 处 `pool = link_job_pool`；② 第二轮 configure 走 `Makefile:81-85` **逐字原文**（日志中不含两个 `-D`）而 cache 仍为 `lld`/`1`，正面证实「`-D` 设的 cache 项不被后续 configure 覆盖」。

**验收 #10（MC lit 全绿）维持 BLOCKED**，归 `INTEG-101t`，未虚报 PASS。

**⚠️ 内存余量极紧（移交 `INFRA-106t` / `INTEG-101t` 必读）**：宿主 3906 MiB RAM + 20 GiB swap，构建期间最低 `MemAvailable` **45 MiB**、`SwapUsed` 峰值 3807 MiB、窗口内 `pswpin` 增量 13281 MiB。撑住靠 `LLVM_PARALLEL_LINK_JOBS=1` + lld。**`INFRA-106t`（QEMU）必须串行于其后，且同样需串行链接；若需更大规模链接或加 swap（需 root，本宿主 uid=1000）须先经用户确认。**

**已实测通过的基线**（无需构建，宿主直接可复现）：

| 层 | 命令 | 实测输出 | 与里程碑记录 |
| --- | --- | --- | --- |
| L1 | `validate_vectors.py` | `178/178; 15 files, 747 cases; gaps: 0` | ✅ 一致 |
| L2 | `check_lit_bytes.py` | `53 patterns OK`（`44/53 masks`） | ✅ 与 `LLVM-015m` 一致 |
| L6 | `check_interface_alignment.py` | `80 项 \| PASS: 80 \| FAIL: 0 \| MANUAL: 0` | ✅ 与 `INTEG-004m` 一致 |
| L0 | `check_spec_drift.py` | `spec drift check: PASS` | ✅ |
| L0 | `check_issues.py` | `66 open, 8 closed (0 blocking M1-gate: 0)` | ✅ 与 `INTEG-004m` 一致 |

**权威基线更正**：`.tao/knowledge/MEMORY.md:13` 记的 harness `597/590/2/5/0` **已过期**（`TESTCASES-010t`/`011t` 补 150 条向量之前）。权威值以 `QEMU-021m` 为准：**`747 total / 739 passed / 0 failed / 8 deferred / 0 errors`**。**该值已于 `INTEG-101t` 实证复现**（见下）。

**`INTEG-101t` 验收结论（2026-09-26）**：reviewer 职责**由主会话代行**、**architect 交叉复核经用户指示跳过**（与 `INFRA-106t`/`105t`/`104t` 同类偏差，独立性缺口同样只建立在「主会话逐项独立重算 + 逐个注入反例取得真实非零退出码 + baseline 三件套逐字节比对」之上，读者应据此折扣审视）。

L0–L8 九层 **20 条命令全 `rc=0`**，与权威基线**逐条零偏差**。**硬门槛 L5 通过**：`747 total / 739 passed / 0 failed / 8 deferred / 0 errors`、`harness_rc=0`（reviewer 独立复跑 **117.6 s / 747 条 = 157 ms·条**；engineer 侧由日志 mtime 推得 ≤89 s）⇒ **任务书 `INTEG-101t:254` 的「0.1–0.3 s·条 ⇒ 2–5 min」估时正确**，而预检时按「单次 QEMU 启动 8.6 ms」推出的「10–30 s」是错的（8.6 ms 不含 YAML 解析/编码/比对），已就地更正。deferred 8 条逐条定位：`misc.yaml` #4–#6 `fence`（ISS-056，`trans_fence` 仍为 ILLI 桩）+ `reg-cond-assign.yaml` #16–#20 `C-27`。**独立全量复算**（只读 YAML、不读 harness 输出）确认 `status` 取值仅 `{active:739, deferred:8}`、合计 747、两字段自洽 ⇒ `747 = 739 + 8`，与 harness 路径互相独立、数字一致、无凑绿。

**reviewer 枚举 13 个检查器并逐个注入反例**，全部取得实测可达的 FAIL 路径，其中硬门槛 L5 的反例为**单点敏感**（`ctrl-call.yaml[1].expected_state.ra.ra63` 翻 1 位 ⇒ `738 passed / 1 failed`、rc=1）。**reviewer 自身 4 条无效反例如实作废重做**（V1 往 lit 追加注释行 = 隐蔽空注入；V2 spec-drift 打错靶点改到 yaml 注释头；V3/V4 `expected_state` 实为嵌套 `{ra:{reg:hex},…}` 导致两次零注入）—— 证明「`git diff --name-only` 非空 **且** 反例输出 ≠ 真实运行输出」双判据**能抓住空注入**。

**reviewer 对任务书做 5 处修正 F1–F5**，其中 **F4/F5 是本轮最有价值的发现**：L2 的两个反例块（`INTEG-101t` 块 136 / 171）**只有注释描述注入、没有任何注入命令**，照抄执行只会得 `rc=0`，与块内「期望 rc=1」自相矛盾——而 `bash -n` **查不出这类语义缺口**（语法完全合法）。engineer 靠注释人工完成了注入（结果与证据经复核为真），但**任务书本身不可直接照抄执行**。已补全为自包含块（注入带 `assert 锚点命中数 == 1` 拒绝盲改 + `git diff` 证据 + 还原 + sha 回位 + 复绿），并由 reviewer 亲自执行验证得 `rc=1`。另 F1 把验收 #4 从「至少 1 条注入反例」收紧为「**两个脚本各至少 1 条**」（原措辞会把 P11 架空：oracle 并不读 lit 的 `.s`）。

**本轮新登记 2 项 deferred**：① `Makefile` 的 `build-mc: PASS` / `build-qemu: PASS` 是构建命令后**无条件 `echo`、不验产物**（与 `INFRA-106t` B21 同类；但 `INTEG-101t` 验收 #6 另有 `-M ?` 必须列出 `dadao-m1` 兜底，故该判据不空）；② `tests/lit/E2E/` 三个 smoke 各 3 条 `RUN` 但 **0 个 `FileCheck`**，只验流水线退出 0、**不验 add/jump/arith 结果**（纯覆盖，语义由 L5 承担）。**`INFRA-105t` S3 第 7 项判据过弱一项已由用户 2026-09-26 裁决为 defer（不修）**——不追溯修改已 `已验证` 任务的任务书（会破坏审计链），加严判据已存于该任务完成区。残留风险与缓解口径见 `deferred.md` 同条。**故跨模块影响检查已无未裁决项**；仍需后续独立任务处理的只有上述 ①②。

**已知遗留**：见 `deferred.md`（组件源 `sjtu` 已 302 死循环 / 3 脚本硬编码 `/mnt/tao` / `llvm-lit` 不由 Makefile 构建 / `make prepare` 非幂等 / `build-*: PASS` 不验产物 / L7 E2E 无输出校验）。**任务号采用 1xx 段**以避免与 `.tao` 已占用的 `001`–`014` 撞号。

<!-- 后续逐模块追加：已验收任务、里程碑、遗留项 -->

## 关键路径速查

| 路径 | 用途 |
|------|------|
| `.xkw/knowledge/workflow.md` | 自有流程规则（xkw-start/status + plan/dispatch/complete 唯一来源） |
| `.xkw/README.md` | 新会话统一入口、读取顺序、角色/命令速查 |
| `.xkw/knowledge/MEMORY.md` | 本文件（状态摘要） |
| `.xkw/knowledge/milestones.md` | 自有轮次、依赖图与关键路径 |
| `.xkw/knowledge/adr-1001-m1-reproduction-infra.md` | M1 复现的构建路径/镜像站/清单处置决策（**Accepted**，`1xxx` 号段） |
| `.xkw/knowledge/adr-1002-xkw-startup-workflow.md` | `.xkw` 启动、命令门禁与角色边界（**Accepted**） |
| `.xkw/knowledge/deferred.md` | 本轮新增的已知遗留登记 |
| `.xkw/tasks/<module>/` | 任务文件 `<PREFIX>-nnn<suffix>-描述.md`（**1xx 段**，避开 `.tao` 已占用编号） |
| `.opencode/commands/` | `xkw-start`/`xkw-status` + plan/dispatch/complete 薄入口 |
| `.opencode/agents/` | 项目级 architect/engineer/reviewer 角色定义 |
| `.tao/` | 原项目交互目录（**只读参考，不改动**） |

## 待处置（deferred）

- 全局 `~/.config/opencode/agents/` 仍含 DADAO 专用三角色定义；本项目已由 `.opencode/agents/` 覆盖。全局文件不在本仓修改范围，后续由用户删除或泛化。
- M1 复现轮的新增遗留全部登记在 `deferred.md`（组件源 `sjtu` 失效、3 脚本硬编码旧路径、`llvm-lit` 构建缺口等）。
