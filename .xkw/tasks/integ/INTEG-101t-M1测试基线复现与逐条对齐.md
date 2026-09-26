# INTEG-101t: M1 测试基线复现与逐条对齐

**模块**：integ
**项目里程碑**：M1 复现
**状态**：已验证
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
| `LLVM-015m`（**最终核验** `:112`） | `build-mc`、lit MC **22/22**、`check_lit_bytes 53`、`oracle 68/68`、`validate_instrinfo 0 errors, 0 warnings` |
| `QEMU-021m` | `build-qemu`、`-M ?`、**harness `747 total / 739 passed / 0 failed / 8 deferred / 0 errors`** |

> **重要更正**：`.tao/knowledge/MEMORY.md:13` 记的 harness 基线 `597/590/2/5/0` **已过期**（那是 `TESTCASES-010t`/`011t` 补 150 条向量之前）。权威基线以 `QEMU-021m` 里程碑记录为准。复现时**以 `QEMU-021m` 为准**，并把 MEMORY 的过期事实登记 `deferred.md`。

## 范围

**在范围内**：L0–L8 全部命令的执行、输出记录、与基线逐条比对、偏差归因。

**不在范围内**：修复任何失败项（发现问题只报告不改）、改基线数字、跑 gem5、跑 M2 codegen 回归。

## 执行纪律（强制）

1. 每条命令必须用**带真退出码**的块形态（**B3 纪律**，全任务统一）：

   ```bash
   ( set -o pipefail
     { <命令>; } 2>&1 | tee .work/log/integ/INTEG-101t-<层>-<命令名>.log
     echo "<名>_rc=${PIPESTATUS[0]}" | tee -a .work/log/integ/INTEG-101t-<层>-<命令名>.log )
   ```

   **禁止**裸 `cmd | tee log` 后跟 `echo "exit=$?"` —— 那样 `$?` 取的是 **`tee`** 的退出码，恒为 0，是**恒真判据**（`INFRA-106t` B3 同类缺陷，本轮预检在 L6 原块中又发现一处）。所有 `<层>-<命令名>` 块已按此形态写好，**直接照抄**。
2. **失败即停**：先判定「环境差异」还是「真回归」，**不得重试掩盖**、不得改基线迁就
3. 偏差**逐条列出 + 归因**，既不静默接受、也不静默修改期望值
4. 已知 deferred 项（`fence` / `ISS-056` / `C-27`，用户已裁定不计 FAIL）出现属预期，**须显式核对 deferred 计数 = 8 并逐条列出来源**而不是忽略
   > **P7（已改）**：原文只提「`fence` 相关 3 条」，遗漏了 `reg-cond-assign.yaml` 的 **5 条 `C-27`**。计数 8 本身正确，但来源说明不全 ⇒ engineer 核对时无法定位全部 8 条。已补全，并**要求逐条列出**。
   > 主会话预检已独立复算（`status` 字段 × `deferred_reason` 交叉统计）：**747 = 739 `active` + 8 `deferred`**，且 739 条全部无 `deferred_reason`、8 条全部有 ⇒ **两字段完全自洽**，与 `QEMU-021m` 基线吻合。
5. 严禁在污染的工作区/二进制上得出结论（`AGENTS.md`）

---

## S0 — 前置（必做，秒级）

```bash
mkdir -p .work/log/integ
ls -d .work/log/integ
```

> **P8（已改）**：预检发现 `.work/log/integ/` **不存在**，而本任务 9 层共 13 条命令全部 `tee` 到该目录 ⇒ 不先建则第一条命令就失败。已补 S0。

**只读前提核对**（不改动任何东西，只确认前序任务的产物在位）：

```bash
test -x .work/build/llvm/bin/llvm-mc    && echo "llvm-mc: OK"
test -x .work/build/llvm/bin/llvm-lit   && echo "llvm-lit: OK"
test -x .work/build/qemu/qemu-system-dadao && echo "qemu: OK"
ls -d /mnt/tao/DADAO-v5                 && echo "oracle 符号链: OK"
```

> 四项均由主会话预检实测在位。`/mnt/tao/DADAO-v5` 是 `INFRA-102t` S4 建的符号链，`tools/llvm/test_encoding_oracle.py:335` 的硬编码路径依赖它。

---

## L0 — 仓库层门控

```bash
( set -o pipefail
  { make check; } 2>&1 | tee .work/log/integ/INTEG-101t-L0-check.log
  echo "check_rc=${PIPESTATUS[0]}" | tee -a .work/log/integ/INTEG-101t-L0-check.log )
```

> **P4（已改）**：原块是裸 `| tee` 且**保留了多余的 `PYTHON=python3.12` 覆盖**。预检实测该覆盖与默认 `python3` **输出逐字节相同**（`repository checks: PASS` + `check_issues: 66 open, 8 closed`）⇒ 覆盖无害但**无收益且是反模式**（`INFRA-106t` 已两次证明 `PYTHON=` 覆盖是陷阱），已删去。同时按 B3 纪律取 `PIPESTATUS[0]`。

**期望**（`INTEG-004m` 记录）：
```
repository checks: PASS
check_issues: 66 open, 8 closed (0 blocking M1-gate: 0)
```

内部含 **5** 个子项：`manifest-check`、`validate-vectors`、`check-spec-drift`、`check_issues`、`compileall`。

> **P6（已改）**：原文写「4 个子项」却列了 5 个，计数自相矛盾。`Makefile:122` 的 `check:` 只显式依赖前 3 个（`manifest-check validate-vectors check-spec-drift`），`check_issues` 与 `compileall` 由前 3 项内部调用 ⇒ **实际 5 个**，已改正。

**预判现状**（2026-09-25 已实测，5/6 子项可过）：唯一阻塞是 `manifest_check.py` 的 `tomllib`（`INFRA-102t` 解决）。`check_issues` / `check_spec_drift` 已在宿主实测通过，输出分别为 `66 open, 8 closed (0 blocking M1-gate: 0)` 与 `spec drift check: PASS`。

---

## L1 — 向量层（**已可跑**）

```bash
( set -o pipefail
  { python3.12 tools/testcases/validate_vectors.py; } 2>&1 \
    | tee .work/log/integ/INTEG-101t-L1-validate_vectors.log
  echo "vectors_rc=${PIPESTATUS[0]}" | tee -a .work/log/integ/INTEG-101t-L1-validate_vectors.log )
```

**期望**：`178/178 M1 identities covered OK (inventory sync OK; 15 data files, 747 cases; data coverage gaps: 0)`

> **2026-09-25 已在宿主实测，完全一致。**

---

## L2 — LLVM 字节 oracle

```bash
( set -o pipefail
  { python3.12 tools/llvm/check_lit_bytes.py; } 2>&1 \
    | tee .work/log/integ/INTEG-101t-L2-check_lit_bytes.log
  echo "lit_bytes_rc=${PIPESTATUS[0]}" | tee -a .work/log/integ/INTEG-101t-L2-check_lit_bytes.log )
( set -o pipefail
  { python3.12 tools/llvm/test_encoding_oracle.py; } 2>&1 \
    | tee .work/log/integ/INTEG-101t-L2-oracle.log
  echo "oracle_rc=${PIPESTATUS[0]}" | tee -a .work/log/integ/INTEG-101t-L2-oracle.log )
```

**期望**：
- `check_lit_bytes: 53 patterns OK` / `(info: 44/53 masks cover op-field only)`，exit 0
- `Results: 68 passed, 0 failed out of 68 tests`

> `check_lit_bytes` **2026-09-25 已实测，完全一致**。`test_encoding_oracle` 需 `llvm-mc`（`INFRA-105t`），且其路径硬编码 `/mnt/tao/DADAO-v5/...`，靠 `INFRA-102t` S4 的符号链接解析。

**反例门控**（`AGENTS.md` 强制）：`check_lit_bytes` 与 oracle **都必须能被注入反例判 FAIL**。两者**读的不是同一份输入**，注入点必须分开（见 P11）。

**(a) `check_lit_bytes.py` —— 改 lit 的 `# OBJ:` 字节字面量**

```bash
# 目标：tests/lit/MC/Dadao/basic-encoding.s:10 的「# OBJ:」行第 1 个字节 59 -> 58
#   改前: # OBJ: {{[0-9a-f]+:}} 59 20 00 01{{.*}}add.si{{.*}}rd8, 1
#   改后: # OBJ: {{[0-9a-f]+:}} 58 20 00 01{{.*}}add.si{{.*}}rd8, 1
# ⚠ 2026-09-26 reviewer 更正：原块只有上面 3 行注释 + 一条跑检查器的命令，**没有任何注入命令** ——
#   照抄执行只会得到 rc=0，与「期望 rc=1」自相矛盾（`bash -n` 查不出此类语义缺口）。现补全为自包含块。
W=/tmp/opencode/INTEG-101t/dispatch/l2a; mkdir -p "$W"
S=tests/lit/MC/Dadao/basic-encoding.s
cp -a "$S" "$W/basic-encoding.s.bak"
echo "注入前 sha: $(sha256sum "$S" | cut -d' ' -f1)"
python3.12 -c 'import sys,pathlib;p=pathlib.Path(sys.argv[1]);t=p.read_text();o="# OBJ: {{[0-9a-f]+:}} 59 20 00 01{{.*}}add.si{{.*}}rd8, 1";n="# OBJ: {{[0-9a-f]+:}} 58 20 00 01{{.*}}add.si{{.*}}rd8, 1";c=t.count(o);assert c==1,f"锚点命中 {c} 次（须恰好 1 次），拒绝盲改";p.write_text(t.replace(o,n,1));print(f"injected 59->58，锚点命中 {c}")' "$S"
echo "注入后 git diff --name-only（须非空）:"; git diff --name-only -- "$S"
( set -o pipefail; python3.12 tools/llvm/check_lit_bytes.py 2>&1 | tee "$W/ce.out"; echo "ceA_litbytes_rc=${PIPESTATUS[0]}" | tee -a "$W/ce.out" )
cp -a "$W/basic-encoding.s.bak" "$S"
echo "还原后 sha（须等于注入前）: $(sha256sum "$S" | cut -d' ' -f1)"
echo "还原后 git diff --name-only（须为空）:"; git diff --name-only -- "$S"
( set -o pipefail; python3.12 tools/llvm/check_lit_bytes.py 2>&1 | tee "$W/restore.out"; echo "restore_litbytes_rc=${PIPESTATUS[0]}" | tee -a "$W/restore.out" )
```

**主会话预检已实证**（`/tmp/opencode/INTEG-101t/dispatch/l2-ce2*.out`）：

```
  basic-encoding.s:10: word=0x58200001 — no match in opcodes.yaml
  N (52) != independent count (53)
rc=1
```

真实运行为 `check_lit_bytes: 53 patterns OK`（rc=0）⇒ **反例输出 ≠ 真实输出，有区分力**。

> **注意**：必须改 **`# OBJ:` 行里的字节**。改同一文件的普通注释行（如 `# add.si rd8, 1 (riii format, op=0x59, …)`）**不会**让检查器失败 —— 该脚本只读 `# OBJ:` 行。这是一次**隐蔽的空注入**：`git diff` 非空、文件确实被改，但检查器根本不读那处。主会话第一次就踩了这个坑（diff 4 行、rc 仍为 0），**注入有效性必须同时满足「diff 非空」+「反例输出 ≠ 真实输出」两条**。

**(b) `test_encoding_oracle.py` —— 改 `/tmp` 副本的 `TESTS`（禁止改仓库脚本）**

`tools/` 在本任务中**只读**（范围规定），且该脚本的输入是**脚本内的 `TESTS` 字面量**（`tools/llvm/test_encoding_oracle.py:59`）+ 现场调用 `llvm-mc` 汇编 ⇒ **结构上无法用仓库文件注入**。正确做法是复制到 `/tmp` 合成树后注入（`workflow.md` §11.2-4 允许）：

```bash
W=/tmp/opencode/INTEG-101t/dispatch/oracle-synth; mkdir -p "$W"
cp tools/llvm/test_encoding_oracle.py "$W/oracle_a.py"
# 把第 1 处 encode_xxxx() 的第 1 参数改 1 位（op 字段），例：encode_rrrr(0x50, …) -> (0x51, …)
# ⚠ 2026-09-26 reviewer 更正：原块只 cp 出副本，**没有任何改写副本的命令** —— 照抄执行
#   跑的是未注入的副本，必得 rc=0，与「期望 rc=1，且恰好 1 条 FAIL」自相矛盾。现补全为自包含块。
python3.12 -c 'import sys,pathlib;p=pathlib.Path(sys.argv[1]);t=p.read_text();o="encode_rrrr(0x50, 8, 0, 0, 0)";n="encode_rrrr(0x51, 8, 0, 0, 0)";c=t.count(o);assert c==1,f"锚点命中 {c} 次（须恰好 1 次），拒绝盲改";p.write_text(t.replace(o,n,1));print(f"injected op 0x50->0x51，锚点命中 {c}")' "$W/oracle_a.py"
echo "副本 vs 仓库原件 diff（须非空）:"; diff tools/llvm/test_encoding_oracle.py "$W/oracle_a.py"
echo "仓库原件 sha（注入前后须不变）: $(sha256sum tools/llvm/test_encoding_oracle.py | cut -d' ' -f1)"
( set -o pipefail; python3.12 "$W/oracle_a.py" 2>&1 | tee "$W/ce.out"; echo "ceB_oracle_rc=${PIPESTATUS[0]}" | tee -a "$W/ce.out" )
```

**主会话预检已实证**（`oracle-a3.out`）：

```
  Encoding mismatch: expected 51200000, got 50200000
  Results: 67 passed, 1 failed out of 68 tests
rc=1
```

**备选路径 (b')**：把 `/tmp` 副本的 `llvm_mc = '…'` 指向一个吐错字节的桩（证明**端到端链路**有牙齿，而不只是比较逻辑）。预检已实证 rc=1 且输出与真实运行不同。

> **P11（已改）**：原反例门控只写「临时改 `basic-encoding.s` 里的一个期望字节 → **脚本**应报 FAIL」，措辞暗示**两个脚本都吃这个注入**。实测**不成立**：注入后 `check_lit_bytes` rc=1，但 `test_encoding_oracle` **仍 rc=0**（`68 passed, 0 failed`）—— 因为它不读 lit 的 `.s`。若 engineer 只做一次注入就宣称「两个脚本都验证过」，那是**假覆盖**。现拆成 (a)/(b) 两条独立注入路径，并把「恰好 1 条 FAIL」作为 (b) 的额外判据（防止注入过宽导致 68 条全 FAIL 而掩盖单点敏感性）。

**(c) 还原与复绿（两者都必须）**

1. `cp -a` 备份 → 注入 → 记录 `git diff --name-only` **非空** → 跑 → 记录 rc 与**完整输出**；
2. 还原后 `git status --porcelain -- tests/ tools/` 必须**不含**该路径（或 sha256 与备份一致）；
3. **重跑该层命令确认复绿**，且**必须重跑 `llvm-lit tests/lit/MC/Dadao/`** —— 改 `.s` 同时被 `check_lit_bytes` 与 lit MC 读，只复跑前者不足以证明工作区干净；
4. **反例输出必须与真实运行输出不同**（防空证据）。仅 `rc≠0` 不够。
  > **P10（已改）**：原文「还原须含重建，见 L3」有误导。本层改的是 `.s` **源文件**：`check_lit_bytes.py` 直接读它、`test_encoding_oracle.py` 由 `llvm-mc` **现场汇编**该 `.s` ⇒ **不触及任何已构建二进制，无需重建**。「还原须含重建」只适用于改动了会进二进制的源（QEMU C 源码、`contracts/` 编码表等），见 L3/L4。若两者都无法失败，则该层证据不成立，须记录。

---

## L3 — LLVM MC lit 套件

```bash
( set -o pipefail
  { .work/build/llvm/bin/llvm-lit tests/lit/MC/Dadao/ -v; } 2>&1 \
    | tee .work/log/integ/INTEG-101t-L3-lit-mc.log
  echo "lit_mc_rc=${PIPESTATUS[0]}" | tee -a .work/log/integ/INTEG-101t-L3-lit-mc.log )
( set -o pipefail
  { python3.12 tools/llvm/validate_instrinfo.py; } 2>&1 \
    | tee .work/log/integ/INTEG-101t-L3-instrinfo.log
  echo "instrinfo_rc=${PIPESTATUS[0]}" | tee -a .work/log/integ/INTEG-101t-L3-instrinfo.log )
```

**期望**（`LLVM-015m` **最终核验**，`:112`；**不是**第 2 轮的 21 —— 见修正记录 **P2**）：
```
Total Discovered Tests: 22
  Passed: 22 (100.00%)
```
及 `validate_instrinfo`：`=== Result: 0 errors, 0 warnings ===`。

> 若 `bin/llvm-lit` 缺失，按 `INFRA-105t` S4 记录的第二条路径执行，**并在日志中注明用了哪条**。

---

## L4 — QEMU 核心

```bash
( set -o pipefail
  { make build-qemu; } 2>&1 | tee .work/log/integ/INTEG-101t-L4-build-qemu.log
  echo "build-qemu_rc=${PIPESTATUS[0]}" | tee -a .work/log/integ/INTEG-101t-L4-build-qemu.log )
( set -o pipefail
  { .work/build/qemu/qemu-system-dadao -M ?; } 2>&1 | tee .work/log/integ/INTEG-101t-L4-machines.log
  echo "machines_rc=${PIPESTATUS[0]}" | tee -a .work/log/integ/INTEG-101t-L4-machines.log )
```

**期望**：`build-qemu: PASS` + `build-qemu_rc=0`；`-M ?` 含 **`dadao-m1`（DADAO M1 bare-metal test machine）**。

> **P1（BLOCKER，已改）**：原命令是 `make PYTHON=python3.12 build-qemu`。该覆盖在 `INFRA-106t` 第 1 轮**已实测失败**（`build-qemu_rc=2`，`BackendUnavailable` —— 3.12 的 `setuptools` 不可导入）；且 `Makefile:95-98` 会**重跑 `configure`**，重跑即重建 venv ⇒ **不仅必 FAIL，还可能破坏 `INFRA-106t` 已产出的可用构建**。现改为**裸 `make build-qemu`**（`Makefile:8` 的 `PYTHON ?= python3` 默认值，S0 的 shim 已使其可用），并按 B3 纪律取 `PIPESTATUS[0]`。
> **P5（事实错误，已改）**：原期望写 `dadao-m`（DADAO M bare-metal test machine）。**权威源 `QEMU-021m:45` 记的就是 `dadao-m1   DADAO M1 bare-metal test machine`**；`INFRA-106t` 三轮实测、`-M ?` 实际输出、以及 harness 自身 `tests/scripts/run_qemu_test.py:262` 的 `-machine dadao-m1` **三方一致**。`dadao-m` 是陈旧值。

---

## L5 — 语义 harness（**M1 硬门槛**）

```bash
cd /home/ubuntu/DADAO-v5 || exit 99   # 必须从仓库根：脚本用相对路径定位 .work/build/qemu/
( set -o pipefail
  { python3.12 tests/scripts/run_qemu_test.py tests/vectors/isa/ --batch; } 2>&1 \
    | tee .work/log/integ/INTEG-101t-L5-harness-batch.log
  echo "harness_rc=${PIPESTATUS[0]}" | tee -a .work/log/integ/INTEG-101t-L5-harness-batch.log )
```

> **P4（已改）**：原块虽是 9 层中**唯一**记录了真退出码的（`PIPESTATUS[0]`），但形态与其余各层不一致、且 `cd` 失败不中止。现统一为纪律 #1 的 `( set -o pipefail … )` 形态，退出码字段名统一为 `harness_rc`（原为 `exit`）。**退出码语义不变**。

**期望**（`QEMU-021m` 权威基线）：
```
747 total, 739 passed, 0 failed, 8 deferred, 0 errors
```

**逐条核对要求**（不得只看汇总）：

1. **真实退出码**须记录。若 passed 数对但退出码为 1，属不一致，须查明。
2. **`deferred` 计数 = 8** 须核对来源。**8 条 = `misc.yaml` 的 3 条 `fence`（`ISS-056`，用户 2026-09-21 裁定不计 FAIL）+ `reg-cond-assign.yaml` 的 5 条（`deferred_reason: C-27`）**；须**逐条列出**核对。若 deferred 数 ≠ 8，须列出具体是哪几条、为何与基线不同。
3. **独立复算**：从 `tests/vectors/isa/*.yaml` 独立统计 **active（非 deferred）用例数**，与 `747 − 8 = 739` 比对吻合方可确认「无凑绿」（`AGENTS.md`「独立全量重算」，**不是抽样**）。
4. 若出现 failed：**逐条列出** 编号 / 身份 / 期望 vs 实际，并判定属「环境差异」还是「真回归」。**不得**直接改向量或改 QEMU 源码使其变绿。

**耗时预估**：747 条串行执行，单条 QEMU 启动约 0.1–0.3 s ⇒ 约 2–5 min；若大量超时（`ADR-0004` D3 的 9 s 上限）则按超时数 × 9 s 估。

---

## L6 — 跨模块接口对齐

```bash
( set -o pipefail
  { python3.12 tools/integ/check_interface_alignment.py; } 2>&1 \
    | tee .work/log/integ/INTEG-101t-L6-interface.log
  echo "interface_rc=${PIPESTATUS[0]}" | tee -a .work/log/integ/INTEG-101t-L6-interface.log )
```

> **P3（BLOCKER，已改）**：原块是 `python3.12 … | tee log` 紧跟 `echo "exit=$?"` —— `$?` 取的是 **`tee` 的退出码**（恒为 0），脚本失败也会报 `exit=0` ⇒ **恒真判据**。与 `INFRA-106t` 的 B3 同一类缺陷。

**期望**（`INTEG-004m`）：
```
总计: 80 项 | PASS: 80 | FAIL: 0 | MANUAL: 0
```

> **2026-09-25 已在宿主实测，完全一致**（该脚本只读仓库文件，不需要构建产物）。

---

## L7 — E2E 端到端

```bash
( set -o pipefail
  { .work/build/llvm/bin/llvm-lit tests/lit/E2E/ -v; } 2>&1 \
    | tee .work/log/integ/INTEG-101t-L7-lit-e2e.log
  echo "lit_e2e_rc=${PIPESTATUS[0]}" | tee -a .work/log/integ/INTEG-101t-L7-lit-e2e.log )
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
  ( set -o pipefail
    { python3.12 "$p"; } 2>&1 \
      | tee ".work/log/integ/INTEG-101t-L8-$(basename "$p" .py).log"
    echo "probe_rc=${PIPESTATUS[0]}" | tee -a ".work/log/integ/INTEG-101t-L8-$(basename "$p" .py).log" )
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
| 3 | L2 字节 oracle | `53 patterns OK` + `68 passed, 0 failed out of 68` | ✅ **现在可跑**（**P9**：原写「oracle 待 `INFRA-105t`」已过期——`INFRA-105t` 已完成，主会话预检实跑 rc=0，两项输出与基线逐字一致） |
| 4 | L2 反例门控 | **`check_lit_bytes` 与 `test_encoding_oracle` 各至少 1 条**注入反例实证 FAIL（两条注入路径必须分开，见 P11），且**均已还原**（`git status` 证据） | 现在可跑。⚠ 判据原写「至少 1 条」会把 **P11** 架空——只注 (a) 也达标，而 oracle 并不读 lit 的 `.s` |
| 5 | L3 MC lit | **`22/22 (100%)`** + `instrinfo 0 errors, 0 warnings` | ✅ **现在可跑**。⚠ 判据原写 `21/21` 是**陈旧中间值**，已按 **P2** 更正为 `22/22` |
| 6 | L4 QEMU 核心 | `build-qemu: PASS` + `build-qemu_rc=0` + `-M ?` 含 **`dadao-m1`** | ✅ **现在可跑**。⚠ 判据已按 **P5** 收紧为精确机器名（原来只写「含 `dadao`」，会被 `dadao-m`/`dadao-mfoo` 之类骗过）；命令已按 **P1** 去掉致命的 `PYTHON=python3.12` 覆盖 |
| 7 | **L5 硬门槛** | `747 total, 739 passed, 0 failed, 8 deferred, 0 errors` + 真实退出码 + 独立复算 active=739 | 现在可跑（`INFRA-106t` 后） |
| 8 | L6 接口对齐 | `80/80 PASS, 0 FAIL` | **已实测通过** |
| 9 | L7 E2E | `3/3 (100%)` | 现在可跑（`INFRA-105t`+`106t` 后） |
| 10 | L8 探针 | 各探针用例数与任务书一致，CTL 自检有效 | 现在可跑（`INFRA-106t` 后） |
| 11 | 偏差已归因 | 任何与基线不符处均有逐条归因，无静默接受 | 现在可跑 |
| 12 | 工作区未污染 | `git status --porcelain` 与任务开始时逐字节相同（含反例注入后的还原证据） | 现在可跑 |
| 13 | 日志留存 | 每条命令的完整输出在 `.work/log/integ/INTEG-101t-*.log` | 现在可跑 |

---

## 预检记录（2026-09-26，主会话 `/dispatch` §10.1 四项预检）

> 本节由主会话在派发前写入，记录预检发现的 **P1–P11** 全部修正及其证据。
> 证据落盘 `/tmp/opencode/INTEG-101t/dispatch/`。

### 预检 1：任务书内部一致性 —— 发现 2 处 BLOCKER

| # | 级别 | 位置 | 缺陷 | 证据 |
| --- | --- | --- | --- | --- |
| **P1** | **BLOCKER** | L4 | `make PYTHON=python3.12 build-qemu`。该覆盖在 `INFRA-106t` **第 1 轮已实测失败**（`build-qemu_rc=2`，`BackendUnavailable`）。更严重：`Makefile:95` 的 `configure` 是**无条件执行**的（无 `config.status` 短路）⇒ 复跑会**重跑 configure、重建 venv**，可能**破坏 `INFRA-106t` 已产出的可用构建** | `INFRA-106t` 完成区第 1 轮；`make -n build-qemu` 干跑输出 |
| **P3** | **BLOCKER**（B3 类） | L6 | `python3.12 … \| tee log` 紧跟 `echo "exit=$?"` ⇒ `$?` 取的是 **`tee`** 的退出码（恒 0）⇒ **恒真判据** | 与 `INFRA-106t` B3 同类缺陷，本轮预检在 L6 又发现一处 |
| **P6** | 需修正 | L0 | 「内部含 **4** 个子项」却列了 **5** 个，计数自相矛盾 | 文本；`Makefile:122` 的 `check:` 显式依赖 3 个，另 2 个由其内部调用 |
| **P10** | 需澄清 | L2 | 「还原须含重建，见 L3」有误导：改 `.s` **不触及任何已构建二进制**（`check_lit_bytes` 直接读、`test_encoding_oracle` 现场汇编）⇒ 无需重建 | 依赖分析 |
| **P11** | **BLOCKER** | L2 | 反例门控措辞暗示**两个脚本吃同一个注入**。实测**不成立**：注入 lit `.s` 后 `check_lit_bytes` rc=1，但 `test_encoding_oracle` **仍 rc=0**（不读 lit `.s`，输入是脚本内 `TESTS` 字面量 + 现场 `llvm-mc`）⇒ 只做一次注入就宣称「两个都验过」是**假覆盖** | `l2-ce2-oracle.out` rc=0 vs `l2-ce2-litbytes.out` rc=1 |
| **P4** | 需修正 | L0/L1/L2/L3/L5/L7/L8 | 全部用裸 `\| tee`；**9 层里只有 L5 记录了真退出码**。已按纪律 #1 统一为 `( set -o pipefail … PIPESTATUS[0] )` | 逐块扫描 |

### 预检 2：依赖链实际可用性 —— 全部在位

| 依赖 | 状态 |
| --- | --- |
| `.work/build/llvm/bin/llvm-mc`（23.1.1）/ `llvm-lit`（lit 23.1.1dev） | ✅ |
| `.work/build/qemu/qemu-system-dadao`（34.8 MB） | ✅ |
| `tools/{testcases,llvm,integ,qemu}/` 全部被引用脚本 | ✅ 逐个 `-f` 核实 |
| `tests/vectors/isa/` 15 个 yaml / `tests/lit/MC/Dadao/` / `tests/lit/E2E/` | ✅ |
| 9 个 `min_rom_probe_*.py` + 对应 9 份 `.tao` 任务书（L8 比对用例数用） | ✅ 全部在位 |
| `/mnt/tao/DADAO-v5` 符号链（`test_encoding_oracle.py:335` 硬编码路径依赖它） | ✅ 存在 |
| `.work/log/integ/` | ❌ **不存在** ⇒ 已补 **S0**（P8） |
| QEMU 5 个 subproject 缓存 + `gitlab.com:443` 连通（`configure` 需拉） | ✅ 决定 L4 可跑 |

### 预检 3：验收可执行性 —— 13 项**全部「现在可跑」**，并已实跑复核

预检把**每层的快速只读部分真跑了一遍**（只读，不改仓库），基线逐字对得上：

| 层 | 实跑输出 | 基线 | 判定 |
| --- | --- | --- | --- |
| L0 | `repository checks: PASS` + `check_issues: 66 open, 8 closed (0 blocking M1-gate: 0)`，`check_rc=0` | 同 | ✅ 一致 |
| L1 | `validate_vectors: 178/178 M1 identities covered OK (inventory sync OK; 15 data files, 747 …)` | `178/178; 747 cases; gaps: 0` | ✅ 一致 |
| L2 | `check_lit_bytes: 53 patterns OK`；`Results: 68 passed, 0 failed out of 68 tests` | 同 | ✅ 一致 |
| L3 | `=== Result: 0 errors, 0 warnings ===` | 同 | ✅ 一致 |
| L4 | 不预跑（会重跑 `configure`），但 `INFRA-106t` 第 3 轮已实证裸 `make build-qemu` rc=0 | `build-qemu: PASS` | ✅ 现在可跑 |
| L5 | 端到端冒烟 `2 total, 2 passed, 0 failed, 0 deferred, 0 errors`，rc=0 | — | ✅ 非假通过（见下） |
| L6 | `总计: 80 项 \| PASS: 80 \| FAIL: 0 \| MANUAL: 0` | `80/80` | ✅ 一致 |
| L7 | `llvm-lit --show-tests` 发现 **3** 个 E2E 测试 | `3/3` | ✅ 一致 |

**L5「非假通过」的独立证明**（本轮新增，不接受「跑出 2 passed 就算数」）：

- **移走 `qemu-system-dadao` 后重跑 ⇒ `Error: qemu-system-dadao not found`，rc=1** ⇒ harness 确实会因 QEMU 缺失而失败，`2 passed` **不是**空转。
- **单次 QEMU 启动实测 ~8.6 ms**（10 次平均 0.086 s）⇒ 2 条用例 0.079 s 合理，非「秒出假结果」。
- **`--dump` 模式确实连不上 QMP**（`WARNING: QMP connect+cont failed: timed out` → `INCONCLUSIVE`）⇒ harness 的 QMP 通路是活的，会在失败时报出来。
- 任务书估时「单条 0.1–0.3 s ⇒ 约 2–5 min」**与实测相符**。⚠ **2026-09-26 更正本条**：先前据上一行的 8.6 ms 推出「实算约 10–30 s、任务书偏保守」是**错的** —— 8.6 ms 只是**单次 QEMU 进程启动**，不含 harness 每条的 YAML 解析 / 编码 / 状态比对。执行后主会话实测全量 **117.6 s / 747 条 = 157 ms/条**，落在 0.1–0.3 s 内。判据不含耗时，此条仅供估时参考。

**L5「独立复算」已由主会话完成**（验收 #7 要求 engineer 独立重算一次，此处是主会话的交叉核对）：

```
747 = 739 active + 8 deferred
739 条：全部 status=active 且【无】deferred_reason
  8 条：全部 status=deferred 且【有】deferred_reason   ⇒ 两字段完全自洽
  8 条 = misc.yaml 的 3 条 fence（ISS-056）+ reg-cond-assign.yaml 的 5 条（C-27）
```

与 `QEMU-021m` 的 `747 total / 739 passed / 0 failed / 8 deferred / 0 errors` 吻合。**任务书原只提「fence 3 条」，遗漏 5 条 `C-27` ⇒ P7。**

### 预检 4：与 `spec/` / `contracts/` / `tests/vectors/` 一致性 —— 发现 2 处基线陈旧

| # | 级别 | 位置 | 缺陷 | 证据 |
| --- | --- | --- | --- | --- |
| **P2** | **BLOCKER** | 权威基线表 + L3 期望 | 基线写 `lit MC 21/21` 并注明出自「`LLVM-015m` **第 2 轮**」。**那是陈旧中间值**：`LLVM-015m` **最终核验**（`:112`，`LLVM-014t` 加了 `e_flags.s` 之后）记的是 **`Total Discovered Tests: 22` / `Passed: 22`**。演进链：`17`（`LLVM-011t` RA 前）→ `21`（`LLVM-011t` 加 RA 测试）→ **`22`**（`LLVM-014t` 加 `e_flags.s`） | `llvm-lit tests/lit/MC/Dadao/ --show-tests` 实测发现 **22** 个；`ls *.s` = 22 个 |
| **P5** | 事实错误 | L4 期望 + 验收 #6 | 写 `-M ?` 含 `dadao-m`（DADAO M bare-metal test machine）。**权威源 `QEMU-021m:45` 记的就是 `dadao-m1   DADAO M1 bare-metal test machine`**；`INFRA-106t` 三轮实测、`-M ?` 实际输出、harness 自身 `run_qemu_test.py:262` 的 `-machine dadao-m1` **三方一致** | 三方一致 |
| — | 判据偏弱 | 验收 #6 | 判据只写「`-M ?` 含 `dadao`」⇒ 会被 `dadao-m` / `dadao-mfoo` 之类骗过 | 已收紧为精确匹配 `dadao-m1` |

**保持不变的基线（逐条核实通过）**：`INTEG-004m` 的 `E2E 3/3`、`80/80`、`repository checks: PASS`、`66 open, 8 closed`；`LLVM-015m` 的 `check_lit_bytes 53`、`oracle 68/68`、`instrinfo 0/0`；`QEMU-021m` 的 `747/739/0/8/0`。

### 预检自身的失误（如实记录，均当场改正后重做）

预检共产生 **4 处无效反例/无效比较**，全部由「反例输出必须与真实输出不同」这条自检抓出：

| # | 失误 | 症状 | 改正 |
| --- | --- | --- | --- |
| 1 | 改 `basic-encoding.s` 的**普通注释行**（`# … op=0x59 …`） | `git diff` 非空（4 行）但两个脚本都 rc=0 ⇒ **隐蔽的空注入** | 改 `# OBJ:` 行的字节字面量 ⇒ `check_lit_bytes` rc=1 |
| 2 | 「防空证据」比较时**忘了先还原**，两次运行都在注入状态下 | 反例与「真实」输出当然相同 ⇒ 误判「无区分力」 | 先还原跑真值、再注入跑反例 ⇒ 确认有区分力 |
| 3 | oracle 注入脚本 `int('0x50') ^ 1`（十进制解析十六进制字面量） | 脚本**自己崩了**，文件未改 ⇒ rc=0 | 改 `hex(int(old,16) ^ 1)` ⇒ rc=1、恰好 1 条 FAIL |
| 4 | 汇总行给**无效的路径 A** 打了 ✅（脚本崩了、rc=0 却被打勾） | 汇总输出与真实 rc 矛盾 | 汇总改为**由实测 rc 直接生成**，并对 `rc==0` 的注入显式打 ❌ |

> 第 3、4 两项与 `INFRA-106t` 的 B20、reviewer 的 4 处无效反例**同源**：
> **反例的「构造手法」本身有缺陷时，反例无效；而汇总/断言若不 derives 自实测 rc，就会把无效反例粉饰成有效。**
> ⇒ 已把两条固化为本任务的强制判据：
> **(i) 注入有效性 = `git diff --name-only` 非空 且 反例输出 ≠ 真实输出**（两条都满足才算数）；
> **(ii) 任何汇总/判据行必须由实测 rc 生成，禁止手写 ✅。**

### 派发前状态

- 任务书 448 行（含本预检记录）；14 个 ```bash 围栏，其中 **13 个是实操块**（全部 `bash -n` 通过），另 1 个是纪律 #1 的模板块（含 `<命令>` 占位符，`bash -n` 失败属预期）。
- `git diff --numstat` = `+104 / -30`；30 行被删**逐行核对**（见下）**全部有对应的 P 编号更正记录，无内容实质丢失**。
- 预检期间仓库 baseline **未被污染**：23 条既有 dirty 路径的**逐路径内容 sha256 全部不变**、0 增 0 消；我注入过的 5 个文件（`basic-encoding.s` / `test_encoding_oracle.py` / `check_lit_bytes.py` / `opcodes.yaml` / `qemu-system-dadao`）**全部已复原**且不在 dirty 集内。
- 30 行被删内容的分类：P2（#1、12–15、29）、纪律#1（#2）、P7（#3、23）、P1/P4（#4）、P6（#5）、P3/P4（#6–8、10–11、16–17、19–22、24–27）、P10（#9）、P5（#18）、验收状态更新（#28、#30）。

## 完成区

**执行日期**：2026-09-26（engineer 实际执行）
**执行范围**：只读复现。**唯一被修改的文件是本任务书本「完成区」段**；`contracts/`、`tests/vectors/`、`components/`、任何 `tools/` 脚本、`.tao/`、`manifests/`、`Makefile`、`components.lock.toml`、`.work/source/` **一个字节都未改**。
**命令块**：9 层 13 个实操块全部按纪律 #1 的 `( set -o pipefail … ${PIPESTATUS[0]} )` 形态**原样照抄**执行，未改任何命令、未加任何 `PYTHON=` 覆盖。
**日志**：`.work/log/integ/INTEG-101t-*.log` 共 **20** 个（13 个实操块中 S0 不 tee；L2/L3/L4 各含 2 条命令，L8 循环按探针分文件 ⇒ 20 条实际命令各 1 个日志）。

### 0. dirty baseline 保护（开工门禁 + 收工核对）

派发 baseline 三件套已在 `/tmp/opencode/INTEG-101t/dispatch/`。开工与收工各重算一次：

| 项 | 开工 | 收工 | 判定 |
| --- | --- | --- | --- |
| `git -c core.quotepath=false status --porcelain=v1 -uall` | 24 路径 | 24 路径 | `diff` **逐字节相同** |
| 24 条 dirty 路径的**内容 sha256** | 24 条 | 24 条 | 排序后 `diff` **全等**：0 变、0 增、0 消 |
| 任务书 sha256（写完成区前） | `3b3d14ac…dceb5` | `3b3d14ac…dceb5` | 未动 |

`git diff --name-only -- tests/ tools/qemu/ tools/llvm/ contracts/ tests/vectors/ components/` 收工时**输出为空**。
`.work/source/qemu` 源码树 `git status -uall` = **0 changed path**（L4 未在源码树产生任何改动）。
`make build-qemu` 前后 QEMU 二进制指纹**完全相同**：`2f5acf4508c0dbe36c17a0d9cac2db8ed7cf2e4d4ed0e2649ecfea3763d7ee36`（`ninja: no work to do.` ⇒ 重建是真空操作，未损坏 `INFRA-106t` 产物）。
**本任务新增的仓库内路径：0 个。** 全部合成产物在 `/tmp/opencode/INTEG-101t/`（`exec/` 证据 + `dispatch/oracle-synth/` 反例副本），仓库内与 `~/` 无遗留。

### 1. S0 — 前置

```
$ mkdir -p .work/log/integ ; ls -d .work/log/integ
.work/log/integ
$ test -x .work/build/llvm/bin/llvm-mc    && echo "llvm-mc: OK"      → llvm-mc: OK
$ test -x .work/build/llvm/bin/llvm-lit   && echo "llvm-lit: OK"     → llvm-lit: OK
$ test -x .work/build/qemu/qemu-system-dadao && echo "qemu: OK"       → qemu: OK
$ ls -d /mnt/tao/DADAO-v5 && echo "oracle 符号链: OK"                → /mnt/tao/DADAO-v5 / oracle 符号链: OK
```

`.work` → `/mnt/dadao-v5/.work`（172G 可用）。**P8 的缺失目录已补齐，第一条命令未因目录不存在而失败。**

### 2. L0–L8 逐层实测 vs 基线（全部 20 条命令 `rc=0`）

| 层 | 命令 | **实测 `_rc`** | 真实汇总行（原文） | 基线 | 判定 | 日志 |
| --- | --- | --- | --- | --- | --- | --- |
| **L0** | `make check` | `check_rc=0` | `repository checks: PASS` + `check_issues: 66 open, 8 closed (0 blocking M1-gate: 0)` | 同（`INTEG-004m`） | ✅ **一致** | `INTEG-101t-L0-check.log` |
| **L1** | `validate_vectors.py` | `vectors_rc=0` | `validate_vectors: 178/178 M1 identities covered OK (inventory sync OK; 15 data files, 747 cases; data coverage gaps: 0)` | `178/178; 747 cases; gaps: 0` | ✅ **一致** | `INTEG-101t-L1-validate_vectors.log` |
| **L2a** | `check_lit_bytes.py` | `lit_bytes_rc=0` | `check_lit_bytes: 53 patterns OK` / `(info: 44/53 masks cover op-field only)` | 同（`LLVM-015m`） | ✅ **一致** | `INTEG-101t-L2-check_lit_bytes.log` |
| **L2b** | `test_encoding_oracle.py` | `oracle_rc=0` | `Results: 68 passed, 0 failed out of 68 tests` | 同（`LLVM-015m`） | ✅ **一致** | `INTEG-101t-L2-oracle.log` |
| **L3a** | `llvm-lit tests/lit/MC/Dadao/ -v` | `lit_mc_rc=0` | `Total Discovered Tests: 22` / `Passed: 22 (100.00%)` | **`22/22`**（P2 更正值） | ✅ **一致** | `INTEG-101t-L3-lit-mc.log` |
| **L3b** | `validate_instrinfo.py` | `instrinfo_rc=0` | `=== Result: 0 errors, 0 warnings ===` | 同 | ✅ **一致** | `INTEG-101t-L3-instrinfo.log` |
| **L4a** | `make build-qemu` | `build-qemu_rc=0` | `build-qemu: PASS`（末行前一行 `ninja: no work to do.`） | `build-qemu: PASS` | ✅ **一致** | `INTEG-101t-L4-build-qemu.log` |
| **L4b** | `qemu-system-dadao -M ?` | `machines_rc=0` | `dadao-m1             DADAO M1 bare-metal test machine` | **精确名 `dadao-m1`**（P5） | ✅ **一致** | `INTEG-101t-L4-machines.log` |
| **L5** | `run_qemu_test.py tests/vectors/isa/ --batch` | `harness_rc=0` | `Results: 747 total, 739 passed, 0 failed, 8 deferred, 0 errors` | `QEMU-021m` 同 | ✅ **一致（硬门槛通过）** | `INTEG-101t-L5-harness-batch.log` |
| **L6** | `check_interface_alignment.py` | `interface_rc=0` | `总计: 80 项 \| PASS: 80 \| FAIL: 0 \| MANUAL: 0` | `80/80`（`INTEG-004m`） | ✅ **一致** | `INTEG-101t-L6-interface.log` |
| **L7** | `llvm-lit tests/lit/E2E/ -v` | `lit_e2e_rc=0` | `Total Discovered Tests: 3` / `Passed: 3 (100.00%)` | `3/3`（`INTEG-004m`） | ✅ **一致** | `INTEG-101t-L7-lit-e2e.log` |
| **L8** | 9 个 `min_rom_probe_*.py` | 9 × `probe_rc=0` | 见 §6 逐条表 | 各自任务书 | ✅ **9/9 一致** | `INTEG-101t-L8-min_rom_probe_{005t,006t,008t,009t,010t,011t,012t,013t,022t}.log` |

**9 层、20 条命令，`rc` 全为 0；与基线逐条比对无一偏差。** 未出现任何「passed 数对但退出码非 0」的不一致（L5 逐条要求 1）。

**L0 的 5 个子项（P6 修正后的计数）——实测可见证据**：`manifest validation: PASS`、`validate_vectors: 178/178 …`、`spec drift check: PASS`（含 `── 结果: 检查 3 个合约，排除 1 个，错误 0 个 ──`）、`check_issues: 66 open, 8 closed (0 blocking M1-gate: 0)`、汇总 `repository checks: PASS`。
其中 `compileall`（`Makefile:124` `@$(PYTHON) -m compileall -q tools`）带 `-q` **不打印任何 PASS 行**；其通过的证据是 `make` 能走到 `repository checks: PASS` 这一行（recipe 任一步非 0 即中止）。其 `.pyc` 副作用落在 `tools/*/__pycache__/`，经 `git status --ignored` 确认全部为 `!!`（已忽略），**不进入 dirty 集**。

**L4 说明（已知风险已排除）**：`Makefile:95` 的 `configure` 确实**无条件重跑**了（日志可见 `mkvenv: Creating non-isolated virtual environment`、`mkvenv: installing meson==1.11.1, pycotap==1.3.1`、5 个 subproject 全部 `Subproject … finished`），但**未触发任何网络拉取失败**、未损坏既有构建：最终 `ninja: no work to do.`，QEMU 二进制 sha256 前后一致（`2f5acf…7ee36`）。**P1 的 BLOCKER 修正（去掉 `PYTHON=python3.12`）是必要的**：本次用的正是 `Makefile:8` 的 `PYTHON ?= python3` 默认值（日志首行 `python determined to be '/usr/bin/python3'` / `python version: Python 3.10.12`）。

### 3. L5 硬门槛专章

**完整日志（全文 4 行，无 TIMEOUT / 无逐条 FAIL 行）**：

```
Running batch tests from tests/vectors/isa/...

Results: 747 total, 739 passed, 0 failed, 8 deferred, 0 errors
harness_rc=0
```

- **真实退出码 `harness_rc=0`**（`${PIPESTATUS[0]}` 取自 `python3.12` 本体，非 `tee`）。基线要求「passed 数对但退出码为 1 属不一致」——**未发生**。
- `0 failed` / `0 errors` ⇒ 无需逐条列 failed 编号；`0 errors` 同时排除 harness 自身加载/超时类错误。
- 日志中**无任何 `TIMEOUT` 行** ⇒ 未触及 `ADR-0004` D3 的 9 s 上限。
- 未单独计时（不重复执行 L5 以免违反「不得重试掩盖」）。任务书 §L5 的「约 2–5 min」与预检的「约 10–30 s」都只是**预估**，本轮**不据此下任何结论**。

**deferred 计数 = 8 的逐条来源核对**（判据要求逐条列出）：

| # | 文件 | 序号（1-based） | `insn` | `mnemonic` | `deferred_reason` |
| --- | --- | --- | --- | --- | --- |
| 1 | `tests/vectors/isa/misc.yaml` | **#4** | `fence` | `fence` | `fence 实现缺失（ISS-056）：trans_fence 为 ILLI 桩，nop/SBZ 语义未实现；用户 2026-09-21 裁定 deferred` |
| 2 | `tests/vectors/isa/misc.yaml` | **#5** | `fence` | `fence` | 同上（ISS-056） |
| 3 | `tests/vectors/isa/misc.yaml` | **#6** | `fence` | `fence` | 同上（ISS-056） |
| 4 | `tests/vectors/isa/reg-cond-assign.yaml` | **#16** | `cs.n-rd` | `cs.n` | `C-27` |
| 5 | `tests/vectors/isa/reg-cond-assign.yaml` | **#17** | `cs.z-rd` | `cs.z` | `C-27` |
| 6 | `tests/vectors/isa/reg-cond-assign.yaml` | **#18** | `cs.p-rd` | `cs.p` | `C-27` |
| 7 | `tests/vectors/isa/reg-cond-assign.yaml` | **#19** | `cs.eq-rd` | `cs.eq` | `C-27` |
| 8 | `tests/vectors/isa/reg-cond-assign.yaml` | **#20** | `cs.ne-rd` | `cs.ne` | `C-27` |

**`3 fence（ISS-056） + 5 C-27 = 8`**，与任务书 P7 补全后的说明、与 harness 报出的 `8 deferred` **计数吻合**。`misc.yaml` 6 条中 #1–#3（`swym-iiii`×2、`illi`）为 `active`；`reg-cond-assign.yaml` 20 条中 #1–#15 为 `active`、`#16–#20` 为 `deferred`。
**口径说明（不夸大证据强度）**：harness 的 `--batch` 汇总**不逐条列举**是哪 8 条 deferred；身份级一致性由「harness 报 8」＋「向量文件侧全量枚举出的 8 条身份」两侧计数相等 + 上表穷举得出，**不是**来自 harness 侧的 per-case 清单。

### 4. L5 独立全量复算（自己写脚本，**全量非抽样**）

脚本 `/tmp/opencode/INTEG-101t/exec/recompute_active.py`（不入库：一次性分析产物，按 `AGENTS.md` 置 `/tmp/opencode/INTEG-101t/`），输出 `/tmp/opencode/INTEG-101t/exec/recompute_active.out`，`recompute_rc=0`。
**不读 harness 任何输出**，直接 `yaml.safe_load` 解析 `tests/vectors/isa/*.yaml`；**同时处理两种顶层形态**（裸 `list` 与带 `cases` 键的 `dict`），非 `list`/`dict` 形态会显式 `TypeError` 退出而非静默跳过。
本轮实测 **15 个文件顶层全部为 `list`**（`shapes: list: 15 file(s)`），故 dict 分支未被实际触发——该分支为按任务书提醒所写的防御性代码，**不作为「已验证 dict 形态」的证据**。

逐文件全量枚举（15/15 文件，无遗漏）：

```
file                         shape         cases  active  deferred
ctrl-br.yaml                 list             40      40         0
ctrl-call.yaml               list              9       9         0
ctrl-jump.yaml               list              6       6         0
ctrl-ret.yaml                list              2       2         0
mem-ra.yaml                  list             22      22         0
mem-rb.yaml                  list             24      24         0
mem-rd.yaml                  list            126     126         0
misc.yaml                    list              6       3         3
reg-arith.yaml               list            187     187         0
reg-compare.yaml             list             33      33         0
reg-cond-assign.yaml         list             20      15         5
reg-imm-block.yaml           list             46      46         0
reg-logic.yaml               list             64      64         0
reg-shift-extend.yaml        list            160     160         0
reserved.yaml                list              2       2         0
```

`status` 分布（穷尽交叉表，验证两字段自洽）：

```
status='active'     n= 739  deferred_reason present=   0 absent= 739
status='deferred'   n=   8  deferred_reason present=   8 absent=   0
```

**739 条 active 全部无 `deferred_reason`；8 条 deferred 全部有 `deferred_reason` ⇒ 两字段完全自洽，无「标 active 却带 reason」或「标 deferred 却无 reason」的错值。**

算术闭合：`total 747 = active 739 + deferred 8`；脚本三项断言 `total==747` / `active==739` / `deferred==8` 全 `YES`，与任务书目标 `747 − 8 = 739` **吻合**。
⇒ **无凑绿**：739 是从 747 个 YAML 条目独立数出来的，不是从 harness 的 `739 passed` 抄回来的；harness 与独立复算两条独立路径得同一数字。

### 5. L2 反例实证（两条独立注入路径，P11）

**注入有效性双判据**（任务书「预检自身的失误」固化的 (i)：`git diff --name-only` 非空 **且** 反例输出 ≠ 真实输出）：两条均满足；`rc≠0` 单独不作数。

**(a) `check_lit_bytes.py` —— 改 lit 的 `# OBJ:` 字节字面量**（`tests/lit/MC/Dadao/basic-encoding.s:10`，第 1 个字节 `59`→`58`）

- 注入前 `cp -a` 备份：`/tmp/opencode/INTEG-101t/exec/basic-encoding.s.bak`，sha256 `4d9b8be040257d684f64bb714d1ac63493cf9d92fdd0a8993d5a7541a7e2d4df`。
- `git diff --name-only` **非空**，且只含目标文件（`tests/lit/MC/Dadao/basic-encoding.s`），diff 精确为 1 行、正是 `# OBJ:` 行（`index fb3b020..57d255a`）：

  ```
  -# OBJ: {{[0-9a-f]+:}} 59 20 00 01{{.*}}add.si{{.*}}rd8, 1
  +# OBJ: {{[0-9a-f]+:}} 58 20 00 01{{.*}}add.si{{.*}}rd8, 1
  ```

- **反例输出（`/tmp/opencode/INTEG-101t/exec/ceA-litbytes.out`，rc=1）**：

  ```
    basic-encoding.s:10: word=0x58200001 — no match in opcodes.yaml
    N (52) != independent count (53)
  ceA_litbytes_rc=1
  ```

- **与真实运行的差异**：`diff` 真实 vs 反例 **rc=1（非零 ⇒ 不同）**。真实为 `check_lit_bytes: 53 patterns OK` + `lit_bytes_rc=0`；反例为 `no match in opcodes.yaml` + `N (52) != independent count (53)` + rc=1。**有区分力。**
- **P11 同步实证（同一注入下 oracle 仍绿）**：同一次注入下 `test_encoding_oracle.py` 输出 `Results: 68 passed, 0 failed out of 68 tests`、**`ceA_oracle_rc=0`**（`ceA-oracle.out`）⇒ 两个脚本**不吃同一个输入**，故 (b) 的独立注入路径是必需的，不是冗余。

**(b) `test_encoding_oracle.py` —— 改 `/tmp` 副本的 `TESTS`（仓库原件零字节改动）**

- 副本：`cp tools/llvm/test_encoding_oracle.py /tmp/opencode/INTEG-101t/dispatch/oracle-synth/oracle_a.py`（任务书指定路径）。
- 注入：`TESTS` 第 1 条 `encode_rrrr(0x50, 8, 0, 0, 0)` → `encode_rrrr(0x51, 8, 0, 0, 0)`（op 字段改 1 位；`assert count==1` 保证只改 1 处）。
- **注入有效性证据（与 (a) 形式不同，如实说明）**：本条注入刻意**全部落在 `/tmp`** ⇒ 仓库 `git diff --name-only` **必然为空**，这是「仓库原件不许动」的正确结果，不是空注入。等价证据是：副本与原件的 `diff` **非空且仅 1 行**（`diff_rc=1`），且**仓库原件 sha256 在注入前后完全相同**（`d9436d26720d69bb82685061d4d093c7313298d733fc15795eda9d569e41ac13` ⇒ `…`），`git status --porcelain -- tools/llvm/` 为空。
- **反例输出（`/tmp/opencode/INTEG-101t/exec/ceB-oracle.out`，rc=1）**：

  ```
  FAIL: add.uo rd8, rd0, rd0, rd0
    Expected: 51200000
    Encoding mismatch: expected 51200000, got 50200000

  Results: 67 passed, 1 failed out of 68 tests

  Failed tests:
    add.uo rd8, rd0, rd0, rd0
  ceB_oracle_rc=1
  ```

- **额外判据「恰好 1 条 FAIL」满足**：`67 passed, 1 failed` ⇒ 单点敏感，未出现 68 条全 FAIL 掩盖单点敏感性。
- **与真实运行的差异**：`diff` 真实 vs 反例 **rc=1（非零 ⇒ 不同）**（真实 `68 passed, 0 failed` + `oracle_rc=0`）。**有区分力。**

**(c) 还原与复绿（两者都做，含 `llvm-lit`）**

| 步骤 | 证据 |
| --- | --- |
| (a) 还原 | `cp -a` 备份回位；还原后 sha256 `4d9b8be0…d4df` = 备份 sha256（**逐字节一致**）；`git status --porcelain -- tests/ tools/` **不含**该路径；`git diff --name-only -- tests/ tools/` **为空** |
| (a) 复跑 `check_lit_bytes` | `check_lit_bytes: 53 patterns OK` + `restore_litbytes_rc=0` |
| (a) **复跑 `llvm-lit tests/lit/MC/Dadao/`**（L2(c)-3 强制，因 `.s` 同时被 lit 读） | `Total Discovered Tests: 22` / `Passed: 22 (100.00%)` + `restore_lit_mc_rc=0` |
| (b) 复跑仓库原件 oracle | `Results: 68 passed, 0 failed out of 68 tests` + `restore_oracle_rc=0` |

**P10 澄清在本轮得到证实**：本层改的是 `.s` **源文件**，`check_lit_bytes.py` 直接读它、`test_encoding_oracle.py` 由 `llvm-mc` 现场汇编该 `.s` ⇒ **不触及任何已构建二进制，无需重建**。L4 的 QEMU 二进制 sha256 前后一致（`2f5acf…7ee36`）从旁证「本层还原未污染二进制」。
（复绿证据文件：`/tmp/opencode/INTEG-101t/exec/ceA-restore-litbytes.out`、`ceA-restore-lit.log`、`ceB-restore-oracle.out`；L2 还原后的 `llvm-lit` 结果与 §2 的 L3 正式日志 `22/22` 相互印证。）

### 6. L8 探针逐条（9/9，判据：用例数 vs 任务书 + CTL 自检有效性）

| 探针 | 对应任务 | **实测主用例** | 任务书记录 | 一致 | **实测 CTL** | CTL 语义判定 |
| --- | --- | --- | --- | --- | --- | --- |
| `min_rom_probe_005t.py` | `QEMU-005t` | `20/20 passed, 0 failed` | 探针 20/20（`:116`,`:119`） | ✅ | `0 PASS, 1 FAIL` → `Probe detection: OK` | ✅ 故意错期望 → 报 FAIL = 探针有牙齿 |
| `min_rom_probe_006t.py` | `QEMU-006t` | `34/34 passed, 0 failed` | 34 用例 + 3 CTL（`:104`,`:152`） | ✅ | `3 FAIL` → `Probe: OK` | ✅ |
| `min_rom_probe_008t.py` | `QEMU-008t` | `38/38 passed, 0 failed` | 38 测试 + 3 CTL（`:133`,`:143`） | ✅ | `3 FAIL` → `Probe: OK` | ✅ |
| `min_rom_probe_009t.py` | `QEMU-009t` | `12/12 passed, 0 failed` | 12 测试 + 2 CTL（`:89`,`:92`） | ✅ | `2 FAIL` → `All self-checks failed as expected` | ✅ |
| `min_rom_probe_010t.py` | `QEMU-010t` | `28/28 passed, 0 failed` | 28/28 + CTL 6/6（`:99`） | ✅ | `6 FAIL` → `Probe: OK` | ✅ |
| `min_rom_probe_011t.py` | `QEMU-011t` | `28/28 passed, 0 failed` | 28/28（`:103`,`:104`） | ✅ | `0 PASS, 1 FAIL` → `Probe detection: OK` | ✅ |
| `min_rom_probe_012t.py` | `QEMU-012t` | `13/13 passed, 0 failed` | 13/13 + CTL 3/3（`:105`,`:138`） | ✅ | `3 FAIL` → `Probe: OK` | ✅ |
| `min_rom_probe_013t.py` | `QEMU-013t` | `22/22 passed, 0 failed` | 22/22（`:57`） | ✅ | `2 FAIL` → `Probe: OK` | ✅ |
| `min_rom_probe_022t.py` | `QEMU-022t` | `3/3 passed, 0 failed` | 022t 探针 `3/3`（`:300`,`:384`） | ✅ | `CTL1`+`CTL2` 均 `FAIL` → `Probe: OK` | ✅ |

9 个探针 `probe_rc` **全为 0**，`Overall: PASS`。
**CTL 自检有效性判读**：所有探针的 CTL 都是**故意写错期望值**，`FAIL` 才是正确结果。实测 **9/9 探针的 CTL 全部报 FAIL**、`Main results` 全部 0 failed ⇒ 结论是「**探针正确（能区分错误）**」，**不是**「探针失效」。逐条抽样核对：9 个探针的首条 CTL 分别是 `st.o PASS but expect ILLI` / `ext.ub=7 but expect UNDI` / `st.o PASS but expect MALIGN` / `st.o PASS but expect ILLI` / `ldm.o-rb PASS but expect ILLI` / `div.uo 100/7=14 but expect UNDI` / `st.o PASS but expect ILLI` / `st.o PASS but expect ILLI` / `st.o PASS but expect TIMEOUT` —— 均**期望值与合法值不同** ⇒ FAIL 路径可达，无恒真断言。
**覆盖 ≠ 语义**：L8 只证明「实现存在且基本行为正确」，**不构成 L5 的替代证据**；硬门槛是 L5（§3/§4）。

### 7. 偏差归因表

**与基线不符处：0 条。** 9 层 20 条命令全部 `rc=0` 且汇总行与权威基线逐字一致。以下 3 条是**执行中发现的记录性问题**，均**不构成结果偏差**，如实登记但**未自行改判据**：

| # | 位置 | 现象 | 归因 | 处置 |
| --- | --- | --- | --- | --- |
| N1 | `.tao/tasks/qemu/QEMU-022t-TB续接缺陷修复.md:197` | 该行写 `**测试结果**：通过 10/10`，易被误读为「022t 探针 10 个用例」 | **口径混淆**：`10/10` 是**整个任务**的验证检查项计数（验收表 1–10），**不是探针用例数**。同文件 `:300`/`:384` 明确记 `022t 探针 3/3 PASS` | **非偏差**。实测探针 `3/3` 与权威记录 `:300/:384` 一致。**未改任务书、未改基线**；建议主会话裁决时把 `:197` 的口径在 `.tao` 侧标注（`.tao` 只读，本任务不改） |
| N2 | L0 `compileall` 子项 | `compileall -q tools` **不打印任何 PASS 行**，该子项无直接可观测输出 | `Makefile:124` 带 `-q`（quiet） | **非偏差**。通过证据：`make` 走到了 `repository checks: PASS`（recipe 任一步非 0 即中止）；`.pyc` 副作用全为 gitignored。**未放宽判据** |
| N3 | L5 耗时 | 任务书估「约 2–5 min」，预检估「约 10–30 s」 | 二者均为**预估**；本轮**未单独计时**（不重复执行 L5） | **不据此下任何结论**。判据只含 `747/739/0/8/0` + 真实退出码 + 独立复算，**均不依赖耗时** |

**未做的事（遵守范围纪律）**：未修改任何判据/期望值；未改 `contracts/`、`tests/vectors/`、任何 `tools/` 脚本；未改基线数字；未把任何 FAIL 改绿；未重试掩盖任何失败（本轮**无任何命令失败**，故无失败判定）；未执行任何 `git add/restore/checkout/stash/commit/push/clean`（git 全程只读）；未跑 gem5 / M2 codegen 回归。

### 8. 结论

- **L5 硬门槛通过**：`747 total, 739 passed, 0 failed, 8 deferred, 0 errors`，`harness_rc=0`，与 `QEMU-021m` 权威基线**逐字一致**；deferred 8 条已逐条定位（`misc.yaml` #4/#5/#6 `fence` ISS-056 + `reg-cond-assign.yaml` #16–#20 `C-27`）；**独立全量复算** `747 = 739 active + 8 deferred`，739 与 `747−8` 吻合，两字段自洽，**无凑绿**。
- **L0–L4、L6、L7 全部与基线一致**，含 P2 更正后的 **`22/22`**、P5 收紧后的精确机器名 **`dadao-m1`**。
- **L2 反例门控成立**：(a)(b) 两条独立路径均 `rc=1` **且**反例输出 ≠ 真实输出（`diff` rc 均为 1），(b) 满足「恰好 1 条 FAIL」；两条均已还原（sha256 + `git status` 双证据）并复绿，`.s` 改动**无需重建**（P10）。
- **L8 9/9 探针用例数与任务书一致，CTL 自检 9/9 有效**（全部报 FAIL = 探针正确）。
- **工作区未污染**：收工 `git status` 与 24 路径 baseline **逐字节相同**，24 条 dirty 内容 sha256 **全等**，任务书完成区之外零字节改动，`.work/source/` 0 改动，QEMU 二进制指纹未变。
- **13 项验收判据逐条对照**：#1 L0 ✅ / #2 L1 ✅ / #3 L2 ✅ / #4 L2 反例 ✅ / #5 L3 `22/22`+`0/0` ✅ / #6 L4 `PASS`+rc0+`dadao-m1` ✅ / #7 **L5 硬门槛 ✅** / #8 L6 `80/80` ✅ / #9 L7 `3/3` ✅ / #10 L8 ✅ / #11 偏差已归因 ✅（0 条偏差 + 3 条记录性问题） / #12 工作区未污染 ✅ / #13 日志留存 ✅（20 个）。
- **本任务新增仓库内路径：0 个。** 状态转换（`待开始 → 待验收`）由主会话负责。

---

## 验收记录（reviewer = 主会话，2026-09-26）

> 用户指定：本任务 `/complete` 由**主会话直接充当 reviewer**，**不做 architect 交叉复核**（`workflow.md` §11.3 跳过）。

### R.0 baseline 三件套（§11.1-2）与审查后比对（§11.1-3）

`/tmp/opencode/INTEG-101t/reviewer/baseline/`：`git-status.pre`（24 路径）、`dirty-content-sha256.pre`（24 条）、`task-book.pre.md`（672 行 / sha `ed5b732dff9f76fe`）。

审查后重算：

| 项 | pre | post | 判定 |
| --- | --- | --- | --- |
| 路径集 | 24 | 24 | 消失 0 / 新增 0 |
| dirty 内容 sha256 | 24 条 | 24 条 | **23 条未变，1 条变化 = 本任务书** |
| 新增未跟踪文件 | 13 | 13 | 无新增 |

**如实声明**：任务书**完成区之外**本轮有字节变化——是 **reviewer（我）自己的 5 处授权修正**（3 处预检记录纠错 + 2 个反例块补全，见 R.2），**不是污染**。§11.2-7 明确允许 reviewer 当场修正任务书事实记录；§11.1-3 的「完成区外变化即作废」针对的是**子代理擅自改动**，两者须合读。此处 5 处改动逐条列明、可复现、且都由我执行，故结论有效。

**6 个被注入过的文件全部已还原**（`git diff --name-only` 逐项为空）：`tests/lit/MC/Dadao/basic-encoding.s`、`tools/llvm/test_encoding_oracle.py`、`contracts/opcodes.yaml`、`tests/vectors/isa/reg-arith.yaml`、`.tao/knowledge/contract-isa.md`、`tests/lit/E2E/smoke_add.test`。QEMU 二进制 sha256 `2f5acf45…7ee36` 前后一致。

### R.1 独立复跑（§11.2-1，不采信 engineer 数字）

从任务书**原文提取** 13 个 bash 块（`bash -n` 13/14 通过，第 14 块是含 `<命令>` 占位符的纪律模板），逐块 `bash -c` 复跑，**11 个非注入块 rc 全 0**，输出与基线**逐字一致**：

```
L0  repository checks: PASS   + 66 open, 8 closed (0 blocking)   rc=0   2.6s
L1  178/178 … 747 cases; gaps: 0                               rc=0   1.8s
L2  53 patterns OK + 68 passed, 0 failed                        rc=0   0.6s
L3  22/22 (100.00%) + 178 defs / 0 errors                       rc=0   1.0s
L4  build-qemu: PASS + dadao-m1                                 rc=0  25.4s
L5  747 total, 739 passed, 0 failed, 8 deferred, 0 errors       rc=0  90.8s
L6  总计: 80 项 | PASS: 80                                      rc=0   1.3s
L7  3/3 (100.00%)                                               rc=0   0.2s
L8  9 探针 Overall: PASS                                         rc=0   2.5s
```

**独立复算**（我自己写、只读 `tests/vectors/isa/*.yaml`、不读 harness 任何输出）：`status` 取值分布 = `{'active': 739, 'deferred': 8}`，合计 747 ⇒ `747 = 739 + 8`，与 engineer 的复算路径互相独立、数字一致。

**耗时定案**（原 N3 悬案）：我复跑 L5 实耗 **117.6 s / 747 条 = 157 ms/条**，engineer 侧由日志 mtime 推得 ≤89 s。⇒ 任务书 `:254`「单条 0.1–0.3 s ⇒ 约 2–5 min」**正确**；我预检时写的 `:399`「按 8.6 ms/条实算约 10–30 s、任务书偏保守」**是错的**（8.6 ms 只是单次 QEMU 进程启动，不含 YAML 解析/编码/比对），已就地更正。

### R.2 我对任务书的 5 处修正（§11.2-7）

| # | 位置 | 缺陷 | 处置 |
| --- | --- | --- | --- |
| **F1** | 验收 #4 | 原写「**至少 1 条**注入反例」——只做 (a) 也达标，而 oracle 并不读 lit 的 `.s`（P11 已实证），**判据把 P11 架空** | 收紧为「`check_lit_bytes` 与 `test_encoding_oracle` **各至少 1 条**」 |
| **F2** | L6 期望块 | 汇总行下方多一个**游离的 `0`**（真实日志只有 `总计: 80 项 \| PASS: 80 \| FAIL: 0 \| MANUAL: 0`） | 删除 |
| **F3** | 预检 `:399` | 「8.6 ms/条 ⇒ 10–30 s、任务书偏保守」——**事实错误** | 就地更正为 157 ms/条 实测，并注明 8.6 ms 的适用范围 |
| **F4** | **块 136**（L2 反例 a） | 块内**只有注释描述注入，没有任何注入命令** ⇒ 照抄执行只得 `rc=0`，与块内「期望 rc=1」**自相矛盾**。`bash -n` 查不出此类语义缺口 | 补全为自包含块：备份 → 注入（锚点命中数 `assert == 1`，拒绝盲改） → `git diff --name-only` 证据 → 跑 → 还原 + sha 回位 + 复绿 |
| **F5** | **块 171**（L2 反例 b） | 块内只 `cp` 出副本，**没有改写副本的命令** ⇒ 跑的是未注入副本，必得 `rc=0`，与「期望 rc=1，且恰好 1 条 FAIL」自相矛盾 | 补全为自包含块：cp → 注入（`assert == 1`） → 副本 diff 证据 → 仓库原件 sha 证据 → 跑 |

> F4/F5 是**本轮 reviewer 的主要发现**：engineer 靠注释人工完成了注入（其结果与证据经我复核为真），但**任务书本身不可直接照抄执行**。修正后我**亲自执行两个块**，均按预期产出 `rc=1`。

### R.3 检查器枚举与逐个反例（§11.2-2）

| # | 检查器 | 判据 | 注入手段 | **实测 rc** | 反例输出（真实） |
| --- | --- | --- | --- | --- | --- |
| C1 | `make check` | `repository checks: PASS` | 改 `.tao/knowledge/contract-isa.md` 版本 `0.5.3`→`0.5.9` | **2** | `版本不匹配 … 合约版本 0.5.9 ≠ README 0.5.3`；`spec drift check: FAIL`；`make: *** [Makefile:134: check-spec-drift] Error 1` |
| C2 | `make check`（另一子项） | 同上 | 改 `reg-arith.yaml` 的 `insn` | **2** | `make: *** [Makefile:130: validate-vectors] Error 1` |
| C3 | `validate_vectors.py` | `178/178 … gaps: 0` | `insn: add.uo-rd`→`add.uoXX-rd` | **1** | `DATA COVERAGE GAP: (add.uo-rd, rrrr) declares 'encoding' … but no active encoding case found` |
| C4 | `check_lit_bytes.py` | `53 patterns OK` | `basic-encoding.s:10` 的 `# OBJ:` 字节 `59`→`58` | **1** | `word=0x58200001 — no match in opcodes.yaml` / `N (52) != independent count (53)` |
| C5 | `test_encoding_oracle.py` | `68 passed, 0 failed` | `/tmp` 副本 `encode_rrrr(0x50,…)`→`(0x51,…)` | **1** | `expected 51200000, got 50200000` / `67 passed, 1 failed out of 68`（**恰好 1 条 ⇒ 单点敏感**） |
| C6 | `llvm-lit tests/lit/MC/Dadao/` | `22/22` | `basic-encoding.s` **真实指令行** `add.si rd8, 1`→`rd8, 2` | **1** | `Passed: 21 (95.45%) / Failed: 1` |
| C7 | `validate_instrinfo.py` | `0 errors, 0 warnings` | `contracts/opcodes.yaml` 的 `mnemonic: ld.ub`→`ld.ubX` | **1** | `=== Result: 1 errors, 0 warnings ===` |
| C8 | `make build-qemu` | `build-qemu: PASS` + rc=0 | `PYTHON=/nonexistent/python3` 令 configure 失败 | **2** | `make: *** [Makefile:55: manifest-check] Error 127`；**`build-qemu: PASS` 出现 0 次 ⇒ 不伪造成功** |
| C9 | `qemu -M ?` | 含 `dadao-m1` | 查不存在的 `dadao-m2` / 二进制不存在 | **1 / 127** | 判据有牙齿；另实测 `grep -qw 'dadao-m'` rc=1 ⇒ P5 的收紧确有作用 |
| C10 | `run_qemu_test.py --batch`（**硬门槛**） | `747/739/0/8/0` + rc=0 | `/tmp` 副本 `ctrl-call.yaml[1].expected_state.ra.ra63` `0x…004`→`0x…005` | **1** | `747 total, 738 passed, 1 failed, 8 deferred` / `FAIL ctrl-call.yaml[1]`（**恰好 1 条 ⇒ 单点敏感**） |
| C11 | `check_interface_alignment.py` | `80/80` | 追加一条 `# OBJ:` 行 ⇒ 53→54 | **1** | `期望 53 patterns，实际 54` / `总计: 80 项 \| PASS: 78 \| FAIL: 2` |
| C12 | `llvm-lit tests/lit/E2E/` | `3/3` | `smoke_add.test` 的 **RUN 行** `-M dadao-m1`→`-M dadao-mX` | **1** | `Passed: 2 (66.67%)` / `FAIL: DADAO-E2E :: smoke_add.test` |
| C13 | 9 × `min_rom_probe_*.py` | 各任务书用例数 | 探针**内置 CTL**（故意写错期望） | 9×`0` | 005t `0 PASS, 1 FAIL`→`Probe detection: OK`；008t `3 FAIL`；011t `0 PASS, 1 FAIL`（我亲自复跑 3 个确认，其余 6 个 engineer 报告与日志一致） |

**13/13 检查器全部有可达的 FAIL 路径**，无一「两支写同一结果」或恒真断言（对 6 个 checker 脚本全文件 grep 恒真模式，命中 0）。

**C8 的诚实边界**：该反例在 `manifest-check` 就中止，**未触达 `ninja` 本身失败**的路径。「ninja 非 0 ⇒ recipe 中止 ⇒ 不打印 PASS」是 make 语义的**代码级论证**，非实测。此判据另有 C9（`-M ?` 验产物）兜底，故 #6 整条不空。

### R.4 我注入失败 / 判无效并撤销的反例（如实登记）

| # | 我的反例 | 现象 | 判定 |
| --- | --- | --- | --- |
| V1 | L7：追加 `# INJECTED-BOGUS-RUN-NOT-A-COMMENT` 注释行 | lit 不读注释 ⇒ `3/3 PASS` rc=0；`git diff` 却非空 | **隐蔽空注入，撤销**。这正是本任务书 `:153` 自己警告的坑，**我本人踩了**。重做见 C12 |
| V2 | L0：改 `contracts/opcodes.yaml` 首行版本注释 `0.5.3`→`0.5.4` | `spec drift check: PASS` rc=0 | **打错靶点**（版本取自 `contract-isa.md` 与 `README`，不读 yaml 注释头）。撤销，重做见 C1 |
| V3 | L5 反例第 1 次：`expected_state` 用 `key: 0x…` 正则匹配 | 脚本 `TypeError` ⇒ 零注入；所谓「输出不同」只差 `Running batch tests from /tmp/…` 路径回显 | **空注入，撤销** |
| V4 | L5 反例第 2 次：按 `isinstance(v,int)` 找期望值 | `expected_state` 实为嵌套 `{ra:{reg:hex}, rd:{…}, rb:{…}, memory:[…]}` ⇒ 又零注入 | **空注入，撤销**。第三次按真实结构重做，见 C10 |

**教训与已落地的门控**：C10 的注入点必须选**嵌套 dict 里的 hex 字符串**（`expected_state.ra.ra63`）；选顶层标量会静默零注入。有效性双判据（`git diff` 非空 **且** 输出 ≠ 真实输出）在本轮**两次抓出我的无效反例**，证明该门控有效。

### R.5 同类缺陷全文件排查（§11.2-3）

- **恒真断言**：6 个 checker 脚本全文件扫描 `assert True` / `check(x, True)` / `== True)` / `if True:`，命中 **0**。
- **覆盖脚本不读输入**：`check_lit_bytes.py` 经确认**只读 `# OBJ:` 行**（`OBJ_LITERAL_RE`）⇒ 改同文件普通注释行不会让它失败。这是**已知且已在任务书 `:153` 记录**的陷阱，非新缺陷。
- **不验产物的 PASS**：`Makefile` 的 `build-mc: PASS` / `build-qemu: PASS` 是**构建命令之后无条件 `echo`**，不检查产物是否存在/非空 ⇒ **与 `INFRA-106t` B21 同类**。`Makefile` 在本任务禁改范围 ⇒ **登记 `deferred.md`，不在本任务修**。`INTEG-101t` 验收 #6 因另有 C9（`-M ?` 验产物并列出 `dadao-m1`）而**不空**。
- **纯覆盖无语义**：L7 三个 E2E 各 3 条 `RUN`、**0 个 `FileCheck`、0 个断言** ⇒ 只验「汇编+objcopy+QEMU 流水线退出 0」，**不验 add/jump/arith 的结果**。L7 是 smoke/覆盖证据，**不得当作语义证据**；语义由 L5 硬门槛承担。
- **探针分支极性**：C13 的 3 个探针 CTL 全部**故意写错期望并确认报 FAIL**，非恒真。

### R.6 结论

**Accepted。**

依据：13 项验收判据**逐条**由 reviewer 独立复跑复核通过（不接受 engineer 汇报数字）；13 个检查器**逐个**有实测可达的 FAIL 路径；硬门槛 L5 既有独立复算（`747 = 739 + 8`）又有单点敏感反例（`738/1 failed`）；工作区 6 个注入文件全部还原、24 路径 baseline 仅任务书 1 条变化且系 reviewer 授权修正。

engineer 的执行**无越界**：未改任何判据/期望值、未改基线数字、未把 FAIL 改绿、未重试掩盖、未执行任何 `git add/restore/checkout/stash/commit/push/clean`；N1/N2/N3 三条记录性问题**如实登记而未自行放宽判据**，处理得当。

**遗留（已登记 `deferred.md`，不在本任务修）**：
1. `Makefile` 的 `build-mc: PASS` / `build-qemu: PASS` 不验产物（与 `INFRA-106t` B21 同类）。
2. L7 三个 E2E 无输出校验（覆盖非语义）。
3. `INFRA-105t` S3 第 7 项判据过弱 —— ✅ **已由用户 2026-09-26 裁决为 defer（不修）**，不追溯修改已 `已验证` 任务的任务书（见 `milestones.md` §12 第 5 项与 `deferred.md` 同条）。
