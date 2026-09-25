# INTEG-101t: M1 测试基线复现与逐条对齐

**模块**：integ
**项目里程碑**：M1 复现
**状态**：待开始
**日期**：2026-09-25
**依赖**：`INFRA-105t`（LLVM MC）+ `INFRA-106t`（QEMU）
**决策依据**：`.xkw/knowledge/adr-1001-m1-reproduction-infra.md`

## 目标

**逐条复现 M1 六个模块里程碑记录的验收输出**，并对任何偏差给出归因。这是本轮复现的**硬门槛**——`L5`（747 条语义向量）为 M1 的核心验收。

**本任务只读不改**：不修改 `contracts/`、`tests/vectors/`、`components/`、任何 `tools/` 脚本、任何基线数字。

## 权威基线来源

| 里程碑（`.tao/`，只读） | 提供的基线 |
| --- | --- |
| `INTEG-004m` | `make check`、`lit E2E 3/3`、`check_interface_alignment 80/80` |
| `LLVM-015m`（第 2 轮） | `build-mc`、lit MC **21/21**、`check_lit_bytes 53`、`oracle 68/68`、`validate_instrinfo` |
| `QEMU-021m` | `build-qemu`、`-M ?`、**harness `747 total / 739 passed / 0 failed / 8 deferred / 0 errors`** |

> **重要更正**：`.tao/knowledge/MEMORY.md:13` 记的 harness 基线 `597/590/2/5/0` **已过期**（那是 `TESTCASES-010t`/`011t` 补 150 条向量之前）。权威基线以 `QEMU-021m` 里程碑记录为准。复现时**以 `QEMU-021m` 为准**，并把 MEMORY 的过期事实登记 `deferred.md`。

## 范围

**在范围内**：L0–L8 全部命令的执行、输出记录、与基线逐条比对、偏差归因。

**不在范围内**：修复任何失败项（发现问题只报告不改）、改基线数字、跑 gem5、跑 M2 codegen 回归。

## 执行纪律（强制）

1. 每条命令 `2>&1 | tee .work/log/<模块>/INTEG-101t-<层>-<命令名>.log`
2. **失败即停**：先判定「环境差异」还是「真回归」，**不得重试掩盖**、不得改基线迁就
3. 偏差**逐条列出 + 归因**，既不静默接受、也不静默修改期望值
4. 已知 deferred 项（`fence`，`ISS-056`，用户已裁定不计 FAIL）出现属预期，**须显式核对 deferred 计数**而不是忽略
5. 严禁在污染的工作区/二进制上得出结论（`AGENTS.md`）

---

## L0 — 仓库层门控

```bash
make PYTHON=python3.12 check 2>&1 | tee .work/log/integ/INTEG-101t-L0-check.log
```

**期望**（`INTEG-004m` 记录）：
```
repository checks: PASS
check_issues: 66 open, 8 closed (0 blocking M1-gate: 0)
```

内部含 4 个子项：`manifest-check`、`validate-vectors`、`check-spec-drift`、`check_issues`、`compileall`。

**预判现状**（2026-09-25 已实测，5/6 子项可过）：唯一阻塞是 `manifest_check.py` 的 `tomllib`（`INFRA-102t` 解决）。`check_issues` / `check_spec_drift` 已在宿主实测通过，输出分别为 `66 open, 8 closed (0 blocking M1-gate: 0)` 与 `spec drift check: PASS`。

---

## L1 — 向量层（**已可跑**）

```bash
python3.12 tools/testcases/validate_vectors.py 2>&1 | tee .work/log/integ/INTEG-101t-L1-validate_vectors.log
```

**期望**：`178/178 M1 identities covered OK (inventory sync OK; 15 data files, 747 cases; data coverage gaps: 0)`

> **2026-09-25 已在宿主实测，完全一致。**

---

## L2 — LLVM 字节 oracle

```bash
python3.12 tools/llvm/check_lit_bytes.py 2>&1 | tee .work/log/integ/INTEG-101t-L2-check_lit_bytes.log
python3.12 tools/llvm/test_encoding_oracle.py 2>&1 | tee .work/log/integ/INTEG-101t-L2-oracle.log
```

**期望**：
- `check_lit_bytes: 53 patterns OK` / `(info: 44/53 masks cover op-field only)`，exit 0
- `Results: 68 passed, 0 failed out of 68 tests`

> `check_lit_bytes` **2026-09-25 已实测，完全一致**。`test_encoding_oracle` 需 `llvm-mc`（`INFRA-105t`），且其路径硬编码 `/mnt/tao/DADAO-v5/...`，靠 `INFRA-102t` S4 的符号链接解析。

**反例门控**（`AGENTS.md` 强制）：`check_lit_bytes` 与 oracle 都必须**能被注入反例判 FAIL**。至少抽 1 条做实证：临时改 `tests/lit/MC/Dadao/basic-encoding.s` 里的一个期望字节 → 脚本应报 FAIL → **立即还原并用 `git status` 确认已还原**（还原须含重建，见 L3）。若两者都无法失败，则该层证据不成立，须记录。

---

## L3 — LLVM MC lit 套件

```bash
.work/build/llvm/bin/llvm-lit tests/lit/MC/Dadao/ -v 2>&1 | tee .work/log/integ/INTEG-101t-L3-lit-mc.log
python3.12 tools/llvm/validate_instrinfo.py 2>&1 | tee .work/log/integ/INTEG-101t-L3-instrinfo.log
```

**期望**（`LLVM-015m` 第 2 轮）：
```
Total Discovered Tests: 21
  Passed: 21 (100.00%)
```
及 `validate_instrinfo`：`0 errors, 0 warnings`。

> 若 `bin/llvm-lit` 缺失，按 `INFRA-105t` S4 记录的第二条路径执行，**并在日志中注明用了哪条**。

---

## L4 — QEMU 核心

```bash
make PYTHON=python3.12 build-qemu 2>&1 | tee .work/log/integ/INTEG-101t-L4-build-qemu.log
.work/build/qemu/qemu-system-dadao -M ? 2>&1 | tee .work/log/integ/INTEG-101t-L4-machines.log
```

**期望**：`build-qemu: PASS`；`-M ?` 含 `dadao-m`（DADAO M bare-metal test machine）。

---

## L5 — 语义 harness（**M1 硬门槛**）

```bash
cd /home/ubuntu/DADAO-v5   # 必须从仓库根：脚本用相对路径定位 .work/build/qemu/
python3.12 tests/scripts/run_qemu_test.py tests/vectors/isa/ --batch 2>&1 \
  | tee .work/log/integ/INTEG-101t-L5-harness-batch.log
echo "exit=${PIPESTATUS[0]}"   # 必须记录真实退出码
```

**期望**（`QEMU-021m` 权威基线）：
```
747 total, 739 passed, 0 failed, 8 deferred, 0 errors
```

**逐条核对要求**（不得只看汇总）：

1. **真实退出码**须记录。若 passed 数对但退出码为 1，属不一致，须查明。
2. **`deferred` 计数 = 8** 须核对来源。已知 `fence` 相关 3 条因 `ISS-056` deferred（用户已裁定不计 FAIL）；若 deferred 数 ≠ 8，须列出具体是哪几条、为何与基线不同。
3. **独立复算**：从 `tests/vectors/isa/*.yaml` 独立统计 **active（非 deferred）用例数**，与 `747 − 8 = 739` 比对吻合方可确认「无凑绿」（`AGENTS.md`「独立全量重算」，**不是抽样**）。
4. 若出现 failed：**逐条列出** 编号 / 身份 / 期望 vs 实际，并判定属「环境差异」还是「真回归」。**不得**直接改向量或改 QEMU 源码使其变绿。

**耗时预估**：747 条串行执行，单条 QEMU 启动约 0.1–0.3 s ⇒ 约 2–5 min；若大量超时（`ADR-0004` D3 的 9 s 上限）则按超时数 × 9 s 估。

---

## L6 — 跨模块接口对齐

```bash
python3.12 tools/integ/check_interface_alignment.py 2>&1 | tee .work/log/integ/INTEG-101t-L6-interface.log
echo "exit=$?"
```

**期望**（`INTEG-004m`）：
```
总计: 80 项 | PASS: 80 | FAIL: 0 | MANUAL: 0
0
```

> **2026-09-25 已在宿主实测，完全一致**（该脚本只读仓库文件，不需要构建产物）。

---

## L7 — E2E 端到端

```bash
.work/build/llvm/bin/llvm-lit tests/lit/E2E/ -v 2>&1 | tee .work/log/integ/INTEG-101t-L7-lit-e2e.log
```

**期望**（`INTEG-004m`）：
```
Total Discovered Tests: 3
  Passed: 3 (100.00%)
```

覆盖 `tests/e2e/{smoke_arith,smoke_add,smoke_jump}.s` 三个场景，各自走「MC 汇编 → objcopy → flat → QEMU 执行 → 退出码 0x00」全链路。

---

## L8 — 回归探针（加固，非 M1 门槛）

9 个最小 ROM 探针，各自对应一个 QEMU 任务的语义验收。**从仓库根执行**（脚本用相对路径 `.work/build/qemu/qemu-system-dadao`）：

```bash
for p in tools/qemu/min_rom_probe_*.py; do
  echo "=== $p ==="
  python3.12 "$p" 2>&1 | tee ".work/log/integ/INTEG-101t-L8-$(basename "$p" .py).log"
done
```

| 探针 | 对应任务 | 覆盖 |
| --- | --- | --- |
| `min_rom_probe_005t.py` | `QEMU-005t` | RD 整数语义 |
| `min_rom_probe_006t.py` | `QEMU-006t` | RD 存取 + MALIGN |
| `min_rom_probe_008t.py` | `QEMU-008t` | 控制流 |
| `min_rom_probe_009t.py` | `QEMU-009t` | — |
| `min_rom_probe_010t.py` | `QEMU-010t` | `ldm.o-rb` |
| `min_rom_probe_011t.py` | `QEMU-011t` | 定点除/余 |
| `min_rom_probe_012t.py` | `QEMU-012t` | — |
| `min_rom_probe_013t.py` | `QEMU-013t` | — |
| `min_rom_probe_022t.py` | `QEMU-022t` | TB 续接（`gen_update_pc`） |

**要求**：每个探针的**用例数须与对应任务书记录一致**，并核对各探针自带的 **CTL 自检**（如 `022t` 的 CTL1/CTL2 反例探针）输出为「探针正确」而非「探针失效」。

> **覆盖 ≠ 语义**（`AGENTS.md`）：探针只证明「实现存在且基本行为正确」，**不构成 L5 的替代证据**。L5 才是硬门槛。

---

## 验收

| # | 项 | 判据 | 状态 |
| --- | --- | --- | --- |
| 1 | L0 仓库门控 | `repository checks: PASS` + `check_issues: 66 open, 8 closed (0 blocking M1-gate: 0)` | 现在可跑（`INFRA-102t` 后） |
| 2 | L1 向量层 | `178/178; 747 cases; gaps: 0` | **已实测通过** |
| 3 | L2 字节 oracle | `53 patterns OK` + `68 passed, 0 failed out of 68` | `check_lit_bytes` **已实测**；oracle 待 `INFRA-105t` |
| 4 | L2 反例门控 | 至少 1 条注入反例实证 FAIL，且**已还原**（`git status` 证据） | 现在可跑 |
| 5 | L3 MC lit | `21/21 (100%)` + `instrinfo 0 errors, 0 warnings` | 现在可跑（`INFRA-105t` 后） |
| 6 | L4 QEMU 核心 | `build-qemu: PASS` + `-M ?` 含 `dadao` | 现在可跑（`INFRA-106t` 后） |
| 7 | **L5 硬门槛** | `747 total, 739 passed, 0 failed, 8 deferred, 0 errors` + 真实退出码 + 独立复算 active=739 | 现在可跑（`INFRA-106t` 后） |
| 8 | L6 接口对齐 | `80/80 PASS, 0 FAIL` | **已实测通过** |
| 9 | L7 E2E | `3/3 (100%)` | 现在可跑（`INFRA-105t`+`106t` 后） |
| 10 | L8 探针 | 各探针用例数与任务书一致，CTL 自检有效 | 现在可跑（`INFRA-106t` 后） |
| 11 | 偏差已归因 | 任何与基线不符处均有逐条归因，无静默接受 | 现在可跑 |
| 12 | 工作区未污染 | `git status --porcelain` 与任务开始时逐字节相同（含反例注入后的还原证据） | 现在可跑 |
| 13 | 日志留存 | 每条命令的完整输出在 `.work/log/integ/INTEG-101t-*.log` | 现在可跑 |

## 完成区

（待执行后填写：L0–L8 逐层实际输出、与基线的比对表、偏差归因、结论）
