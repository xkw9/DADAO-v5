# TESTCASES-101t: F1 浮点 schema 与 oracle 接口冻结

**模块**：testcases  
**项目里程碑**：F1  
**状态**：已验证  
**依赖**：`SPEC-102t`、`SPEC-103t`、`SPEC-104t`（均已验证）及其 F1 合约/`D17 OPEN-ID ledger`/`resolution` 层；ADR-1009～1015 的现行 27 条 decision 均已 Accepted。schema/validator 的表达能力冻结不等于运行时语义 PASS；任何 active 语义取值必须来自 `SPEC-104t` 的已激活投影。

## 目标

冻结向后兼容 M1 的向量 schema、独立 oracle I/O、RF/FCSR 初始/期望状态与观测契约。接口由 testcases 单一拥有；QEMU/LLVM 只能消费，不能定义平行格式。按 ADR-1004 D3，不创建 `golden` 模块或任何 `GOLDEN-*` 任务。

## 输入与固定范围

权威输入为 `.xkw/knowledge/contract-f1-floating.md` 与 64 identity 映射。64 = 18 个 RF 相关编码 + 46 个 MISC-RF；`set.ft/set.fo` 是 LLVM pseudo，不是运行语义 identity。M1 现有 747 条向量/schema 必须继续可读，既有字段语义不得静默改变。

## 交付物

1. 扩展 `tests/vectors/schema.yaml`（或现有唯一 schema）以表达：
   - `input_state.rf` / `expected_state.rf` 的 64 位 bit-pattern；
   - rf0/FCSR 的 rounding mode、flags 与可观测 mask；
   - f32 结果低 32 位与高 32 位的独立观测能力，不预断 D13；
   - 预期异常（ILLI/MALIGN 等）、内存宽度与块操作；
   - 每例 `identity`、facet、spec citation、`active|blocked` 及 OPEN/S-ID；同一 identity 的编码 facet 可 active 而未决语义 facet blocked。
2. 定义稳定 oracle I/O：输入/输出均以整数 bit-pattern/精确枚举表示；禁止以宿主 float 的文本舍入结果作为接口。
3. 扩展 validator：M1 兼容性、RF 索引、FCSR mask、状态互斥、64 identity 合法集合；六个 active OPEN-ID（D17:S1/S3/S4/S5/S6/S8）在 ADR-1009～1015 Accepted 前的 facet 一律不得 active；`D17:S2` 只作可追踪的无行为后果说明，不制造 blocked expected；`D17:S7` 属 spec-determined non-gap，不进 ledger。
4. 写接口文档和最小正/反样例；所有生成器/检查器放 `tools/testcases/`。

## 硬约束

- 期望只能来自 spec/已 Accepted F1 contract；不能调用 LLVM/QEMU/SoftFloat/宿主 `libm` 生成 expected。
- 六个 active OPEN-ID（D17:S1/S3/S4/S5/S6/S8）在 `SPEC-104t` 已验证且相应 ADR-1009～1015 Accepted 前的 facet 必须 `blocked` 并指向结构化 OPEN/S-ID；`D17:S2` 是 ledger 外 trace-only，`D17:S7` 是 ADR-1008 D1 证明的 spec-determined non-gap，二者都不得计 coverage PASS。语义承载方固定为 ADR-1009～1015，不得预设其它 ADR 编号。
- schema 必须允许先读后写、重叠块传输、rf0 精确 mask、f32/f64 bit-pattern、四舍入模式与五 flags。
- QEMU dump/harness 若需改变，必须实现此接口；不得反过来修改 schema 迎合实现。

## D17 OPEN-ID ledger 与 facet 状态

Schema 必须能显式承载 `D17 OPEN-ID ledger`：active 精确键集合为 {D17:S1,D17:S3,D17:S4,D17:S5,D17:S6,D17:S8}（六键），分别对应 reset、classify immediate、fault priority、scaleB exponent、SBZ write、ldm/stm memory；这六个键的受影响语义 facet 在 ADR-1009～1015 Accepted 前保持 blocked，Accepted 后按 `SPEC-104t` 的 `resolution.rule_tables` 取值。当前七份 ADR 均已 Accepted，故本任务按该已激活取值实现。`D17:S2` 始终是 ledger 外 trace-only（`no behavioral consequence; resolved/trace-only; not in D17 OPEN-ID ledger; never PASS`），不是缺口；`D17:S7` 始终是 ADR-1008 D1 已证明的 spec-determined non-gap（move overlap 由 SimRISC-00:41-46 与 SimRISC-03:34-50 唯一确定），不进入 active ledger、不计 OPEN/BLOCKED、不计 PASS。rf0 layout/mask 的 schema 表达现在可实现；`D17:S1` reset expected 采用 ADR-1015 的 Accepted 取值；表达能力 PASS 不得被解释为运行时语义 PASS。开工前必须核对 `SPEC-102t`、`SPEC-103t`、`SPEC-104t` 均已验证，以及 ADR-1009～1015 均 Accepted；当前仅依赖文本与 marker 的静态核对现在可跑，schema/validator 动态验收仍按下表 BLOCKED。

## SPEC-104t 已投影的适用规则

语义激活门禁：`SPEC-104t` 已验证，且本任务所消费的 ADR-1009～1015 全部 Accepted；在此之前 `contracts/f1_gap_proofs.yaml` 的 `resolution` 层只表示 projected-pending-activation，不得当作 active implementation truth，也不得据此声称任何 facet PASS。

`SPEC-104t` 的 `resolution.resolution_matrix` 逐行给出 64 个 identity 的 owning consumer、适用 decision 与已关闭 facet；本任务必须按下列**投影规则**执行，而不是「参见 ADR」自行取义：

| 规则 | `resolution` 投影位置 | 本任务必须表达/实现的精确内容 |
| --- | --- | --- |
| D11 rf0 读写 | `rule_tables.D11` | 全部 64 个 identity 均可读 rf0；以 rf0 为目的只有十条白名单 `ld.t-rf,ld.o-rf,ldm.t-rf,ldm.o-rf,set.w-rf,cs.eq-rf,cs.ne-rf,cs.n-rf,cs.z-rf,cs.p-rf` 合法，其它 RF destination 写 rf0 一律 ILLI（`rd2rf→rf0` 明确 ILLI）；`s6_scope_relation` 记录历史六条 `6-1+5=10` |
| D12 FCSR flags | `rule_tables.D12` | 硬件异常 sticky OR；无异常指令保持既有 rf0[4:0] 不清零；合法软件写立即生效并按程序顺序与自动异常组合；自动置位精确 53 条、非自动 11 条 |
| D13 tetra 高半部 | `rule_tables.D13` | 18 条 tetra 写 RF identity 高 32 位固定 `0xffffffff`；`ld.t-rf`/`ldm.t-rf` 同样 64 位 NaN-boxing；先形成 64 位写值，合法写 rf0 时再套只读位与 SBZ mask |
| D14 unordered 比较 | `rule_tables.D14` | `foqcmp`/`ftqcmp` unordered 写 RD `0x7ff8000000000000`；`foscmp`/`ftscmp` unordered 写 RD `0x7ff0000000000001`；输出只由 qcmp/scmp 类别决定，不依赖输入 NaN 的 quiet/signaling 类别 |
| D15 NaN 传播 | `rule_tables.D15` | 18 条算术 identity 丢弃 payload 与符号返回 canonical qNaN（qNaN 不置 NV、任一 sNaN 置 NV）；`fo2ft`/`ft2fo` 按 SimRISC-03 规范正文传播 payload、sNaN 转换置 NV 并返回 qNaN、结果符号固定为正；`canonical_qnan_bits` 在 ADR-1013 中未给出 64 位常量，本层留 `null`，下游不得代填 |
| D16 tininess/复合 flags | `rule_tables.D16` | 36 条 identity 在**最终舍入后**检测 tininess；underflow 同时置 `UF+NX`，overflow 同时置 `OF+NX` |
| D17 六个 active OPEN-ID | `rule_tables.D17` | S1 reset：`rf0[17:16]=00`（RNE）、`rf0[4:0]=0`；S3 classify immediate：`ftcls/focls immu6!=1` 在 assembler 阶段拒绝、非 assembler 路径到达硬件则 ILLI；S4 fault priority：ILLI 先于 MALIGN，非法编码/操作数不进入对齐判定；S5 scaleB：浮点 `rfhd` 按当前 rf0[17:16] 舍入成整数 n 后算 `rfhc×2^n`，同一模式也控制最终结果舍入，指数 qNaN→canonical qNaN 且指数分类不置 flags、sNaN→NV+canonical qNaN、`+Inf`→`+Inf`、`-Inf`→比例因子 0；S6 SBZ 写：仅十条白名单在写 rf0 时对 `[50:32]`/`[21:18]`/`[15:5]` 静默忽略；S8 ldm/stm：EA0=`rbhb+rdhc`、第 i 项地址 `EA0+i×width`、`.t` width/step=4 与 `.o`=8、RF 编号递增、任一元素 fault 时整条不提交任何 RF 写或 memory store 且 PC 留在 faulting instruction |
| 交叉优先级 | `precedence` | PRE-1～PRE-5：D11 目的合法性先于 D17:S6；D13 先成 64 位写值再套只读/SBZ；D15 格式转换规则优先于算术 canonical 规则；D17:S4 的 ILLI 先于 MALIGN；D12 软件写与自动异常按程序顺序组合 |

`rootn(-0,2)` 继续是 `explicitly-unspecified`（`foroot`/`ftroot` 的 `remaining_unspecified`），任何被激活都不得为它生成唯一 expected；root/log 的独立正确舍入算法与 schema/oracle/vector、LLVM MC、QEMU 实现、E2E 全部仍按真实能力 BLOCKED，ADR Accepted 只解除语义选择门禁。

## 验收

| # | 判据 | 可执行性 |
| --- | --- | --- |
| 1 | 原 M1 747 条向量在新 schema/validator 下逐条通过且字段解释不变 | **BLOCKED**：schema 扩展尚未实现；替代证据为现有 M1 747 基线和向后兼容字段约束 |
| 2 | 正样例覆盖 RF、FCSR、f32 高半部 mask、异常、memory、blocked OPEN/S-ID | **BLOCKED**：样例尚未产出；替代证据为本书字段清单与 `SPEC-103t` 阻塞分类 |
| 3 | validator 对错 RF 索引、非法 flags、active+OPEN/S、缺 citation、未知 identity 分别真实 FAIL | **BLOCKED**：validator 尚未扩展；替代证据为反例清单，执行时必须逐类取得非零 |
| 4 | oracle I/O 不含实现依赖，并由 testcases 文档唯一声明 | **BLOCKED**：接口文档尚未产出；替代证据为 ADR-1004 D3/D10 与本书所有权边界 |
| 5 | 六个 active OPEN-ID 对应 facet 取得确定语义 | **BLOCKED**（产出前）：激活前提已满足（`SPEC-104t` 已验证、ADR-1009～1015 全部 Accepted），但 schema/validator/样例尚未产出；完成后按 `resolution.rule_tables` 验证已激活取值。`rootn(-0,2)` 仍 explicitly-unspecified，永不因 ADR 激活而取得 expected；root/log 独立正确舍入能力仍不在本任务中。 |

## 反例、还原与记录

每个实际验收 checker 都须在 `/tmp/opencode/TESTCASES-101t/reviewer/` 的合成树接受非空反例，真实非零；注入前核对 diff 非空，注入后还原并复绿。此任务不涉及组件二进制；如修改会生成缓存，必须清理并证明仓库 baseline 未变。完成区记录每个 checker 的绿灯与至少一个针对性 FAIL，不能只写摘要。

## 完成区

> 状态保持 `待开始`（状态转换由主会话负责）。以下数字全部来自 `.work/log/testcases/` 下
> 同名日志的真实输出，未做任何转述或概括。

### 1. 交付物落点

| 交付物 | 路径 | 规模 |
| --- | --- | --- |
| schema 文档（M1 原文保留 + 新增 F1 章） | `tests/vectors/schema.md` | 517 行（M1 段逐字未动） |
| oracle 接口文档（testcases 唯一声明） | `docs/testcases/f1-oracle-io.md` | 165 行，10 节 |
| 最小正样例 | `tests/vectors/f1/valid/f1-schema-valid.yaml` | 19 例 / 13 identity |
| 最小反样例 | `tests/vectors/f1/invalid/f1-schema-invalid.yaml` | 53 例，`neg-<N#>-<base-id>` |
| validator（M1 兼容 + F1 判定） | `tools/testcases/validate_vectors.py` | 新增 `validate_f1()`、`--adr-gate {auto,open,closed}` |
| 事实层（RO/RW/SBZ、ledger、doc 词表） | `tools/testcases/f1_schema.py` | `F1Context.d17_active_keys_for()` / `d17_opcodes_divergences()` |
| 判定层 A–I/O/TREE | `tools/testcases/f1_cases.py` | `static_illi` / `validate_f1_tree` |
| 独立期望值（纯整数位型） | `tools/testcases/f1_oracle_values.py` | 推导记录写在模块 docstring |
| 样例生成器 | `tools/testcases/generate_f1_schema_fixtures.py` | `--out` 输出两份 YAML |
| 独立重算器 | `tools/testcases/verify_f1_expected_values.py` | 41 条 KAT + 检查 A–K |
| 事实层/文档门检查器 | `tools/testcases/check_f1_context.py` | 含 `G-DOC`（30 词条 × 2 文档） |
| oracle I/O 扫描器 B1–B5 | `tools/testcases/check_f1_oracle_io.py` | 扫 8 个文件 |
| 反例门控 harness | `tools/testcases/test_f1_schema_counterexamples.py` | 39 条注入 |

`.tao/**`、`spec/**`、`contracts/**`、`.xkw/knowledge/**`、ADR、LLVM/QEMU 源码与
patch、`Makefile`、M1 已定语义、任务状态**均未改动**。

### 2. 绿灯（逐条真实输出）

```
$ python3 tools/testcases/validate_vectors.py                       # EXIT=0
validate_vectors: 178/178 M1 identities covered OK (inventory sync OK; 15 data files, 747 cases; data coverage gaps: 0)
validate_vectors: F1 19/19 vectors OK (19 valid case(s) green; 53 invalid counterexample(s) all rejected; 13 identity/identities; facets 146 active / 6 blocked; fcsr asserts 11; D13 half-observations 7; ADR gate auto)

$ python3 tools/testcases/validate_vectors.py --adr-gate open       # EXIT=0
… ADR gate open)

$ make validate-vectors                                             # EXIT=0（与上面两行逐字节相同）

$ python3 tools/testcases/check_f1_context.py                       # EXIT=0
d17 active      : D17:S1,D17:S3,D17:S4,D17:S5,D17:S6,D17:S8
d17 trace_only  : D17:S2
d17 non_gap     : D17:S7
canonical_qnan  : None
unspecified pt  : rootn(-0,2)
f1 docs         : tests/vectors/schema.md + docs/testcases/f1-oracle-io.md OK (all 30 interface terms present)
F1 CONTEXT: OK (0 fact-layer errors, 0 doc-gate errors; 2 registered read-only divergence(s))

$ python3 tools/testcases/check_f1_oracle_io.py                     # EXIT=0
F1 ORACLE IO: scanned 8 file(s)
B1 forbidden-oracle / B2 host-float / B3 spec-body-read / B4 self-proof / B5 bit-pattern self-check
check_f1_oracle_io: OK (0 violations; F1 expectations are integer-derived and implementation-independent)

$ python3 tools/testcases/verify_f1_expected_values.py              # EXIT=0
verify_f1_expected_values: 19 case(s), 400 independent bit-exact recomputation(s)
  engine KAT (known-answer tests, hand-derived from IEEE 754-2008): 41/41 passed (82 bit/flag assertions)
  FCSR layout re-derived from the contract (two-way cross-check): ro=0xFFF80000FFC00000 rw=0x000000000003001F sbz=0x0007FFFF003CFFE0 ro_value=0x7FF800007FC00000
  D-scope from resolution.rule_tables: D11 whitelist=10 D12 auto=53 D13 write=18 D15 arith=18 D16=36
verify_f1_expected_values: OK (… no project oracle module imported)

$ python3 tools/testcases/test_f1_schema_counterexamples.py        # EXIT=0
repo git status unchanged after 39 injections: YES
RESULT: 39/39 counterexamples rejected with the expected rule marker

$ python3 .work/log/testcases/TESTCASES-101t-hand-recompute.py     # EXIT=0
KAT 表 41 行 / 82 断言；本脚本实际核对 41 行 KAT + 30 行 valid 样例
independent hand recompute: 71/71 agree
```

第三条路线 `TESTCASES-101t-hand-recompute.py`（连同日志留在
`.work/log/testcases/`，`.work/` 已被 `.gitignore` 排除）：`hand` 列全部是
IEEE 754-2008 条文 + 纯整数手算写死的十六进制字面量（注释里逐条写明推导，例如
`1/5` 尾数 = `2^52×3/5 = 2702159776422297 + 3/5`，余 0.6 > 1/2 故进位），
`repo` 列取自 valid YAML 与 KATS/常量表（AST `literal_eval`，不执行仓库代码）。
它与 `verify_f1_expected_values.py` 的**算法路线不同**，用来排除「同一人同一套
算法写两遍」的共因错误。

### 3. 每个 checker 的针对性 FAIL（真实非零）

| checker | 注入 | rc | 真实失败输出 | marker |
| --- | --- | --- | --- | --- |
| `validate_vectors.py` | V1 rf 索引越界 `rf64` | 1 | `C1` | C1 |
| | V2 rf 键形非法 `rf1a` | 1 | `C1` | C1 |
| | V3 rf 值非 64 位 hex | 1 | `C2` | C2 |
| | V4 rf0 被双写进 rf bank | 1 | `C3` | C3 |
| | V5 非法 flag 名 `XX` | 1 | `D2` | D2 |
| | V6 `from_reset` 却非 RNE | 1 | `D5` | D5 |
| | V7 `observed_mask` 吞掉 rw 域 | 1 | `D3` | D3 |
| | V8 `observed_mask` 宣称 SBZ 位 | 1 | `D3` | D3 |
| | V9 `fcsr.value` 与重算不符 | 1 | `D4` | D4 |
| | V10 input 侧断言 `fcsr.value` | 1 | `D6` | D6 |
| | V11 fault 与 `expected_state` 并存 | 1 | `E1` | E1 |
| | V12 active facet 带 `open_ids` | 1 | `E3` | E3 |
| | V13 blocked facet 缺 `open_ids` | 1 | `E4` | E4 |
| | V14 facet `cite` 不指名 authority | 1 | `F1` | F1 |
| | V15 identity 与 insn 不一致 | 1 | `A2` | A2 |
| | V16 `active_keys` 塞 `D17:S2` | 1 | `F3` | F3 |
| | V17 `blocked_points` 不在词表 | 1 | `G1` | G1 |
| | V18 unspecified 点却给唯一 expected | 1 | `G3` | G3 |
| | V19 源寄存器未预置 | 1 | `H5` | H5 |
| | V20 块 EA 写错 | 1 | `H4` | H4 |
| | V21 编码与 identity 不符 | 1 | `B2` | B2 |
| | V22 oracle 与 `expected_state` 不一致 | 1 | `O4` | O4 |
| | V23 半观测缺 `high32` | 1 | `O3` | O3 |
| | V24 `oracle.kind` 未知 | 1 | `O1` | O1 |
| | V25 缺顶层字段 | 1 | `TOP-LEVEL` | TOP-LEVEL |
| | V26 `status` 非 active | 1 | `A5` | A5 |
| | V27 语义值改错：D14 unordered 位型 | 1 | `I3` | I3 |
| | V28 语义值改错：D13 tetra 高半部 | 1 | `I2` | I2 |
| | V29 语义值改错：D12 非自动置位 | 1 | `I4` | I4 |
| | V30 `semantics` blocked 却断言目的寄存器 | 1 | `I8` | I8 |
| | V31 合法编码却期望 ILLI（S3） | 1 | `I7` | I7 |
| | V32 `D17:S2` 失去可追踪性 | 1 | `TREE` | TREE |
| | V33 重复 case id | 1 | `DUPLICATE case id` | DUPLICATE |
| | V34 `--adr-gate closed` | 1 | `F2` | F2 |
| | V35 oracle 层混入宿主 `math.sqrt` | 1 | `B2` | B2 |
| | V36 伪造的期望值常量 | 1 | `B5` | B5 |
| | V37 生成器反读向量数据（自证） | 1 | `B4` | B4 |
| `verify_f1_expected_values.py` | V38 自洽但错误的期望值 | 1 | `MISMATCH …`（见下） | MISMATCH |
| `check_f1_context.py` | V39 冻结词条被删（`G-DOC`） | 1 | `ERR: G-DOC …`（见下） | G-DOC |
| 手算第三路线 | 同样改错 `1.0+2.0` | 1 | `2 处 MISMATCH，69/71 agree` | MISMATCH |

**V38 的完整真实输出**（`.work/log/testcases/TESTCASES-101t-counterexamples-targeted.log`）：

```
注入有效性：注入前与仓库逐字节相同=True；注入后相同=False -> 注入非空=True
$ python3 verify_f1_expected_values.py
  MISMATCH f1-foadd-basic-rf-index: foadd 独立重算 rf1=0x4008000000000000，实得 0x4008000000000001
  verify_f1_expected_values: FAILED (1 mismatch(es), 0 self-check violation(s))
>>> rc=1   同树 validator rc=0（V38 的错值对静态检查不可见）
```

V38 把 `expected_state.rf.rf1` 与 `oracle.records[0].reg.value` **一起**改成同一个
错值，所以 O4 / I2 / I3 / I4 全部看不见它；只有纯整数 IEEE-754 重算抓得住。这条
正是「validator 绿灯 ≠ 期望值正确」的实证。同树 `validator rc=0` 已打印在上面。

**V39 的完整真实输出**：

```
注入有效性：注入前与仓库逐字节相同=True；注入后相同=False -> 注入非空=True
$ python3 check_f1_context.py
    ERR: G-DOC tests/vectors/schema.md 缺少 1 个冻结词条: ['D17:S5']
>>> rc=1
```

`G-DOC` 判据是「30 个冻结词条在 `tests/vectors/schema.md` **和**
`docs/testcases/f1-oracle-io.md` 两份里都必须出现」。文件在但词条被删，与文件根本
不存在一样属于「没有交付接口」。

**ADR 门禁的 FAIL**：`--adr-gate closed` 真实退出 1，共 72 条 `F2 ADR GATE CLOSED`，
末行 `validate_vectors: FAILED (72 error(s))`。覆盖 ADR-1009/1010/1011/1012/1013/
1014/1015 未 Accepted 的 facet 与 `D17:S1/S3/S4/S5/S6/S8` 六键。

**还原证据**：所有注入都在 `/tmp/opencode/TESTCASES-101t/reviewer/` 的临时树内
（harness 用 `build_tree()` 复制后原地改），harness 收尾 `rmtree`，并断言
`repo git status unchanged after 39 injections: YES`（72 行）。本任务不涉及组件二进制，
无「只还原源码未重建」的风险。事后 `ls /tmp/opencode/TESTCASES-101t/reviewer` →
`No such file or directory`，仓库 `git status` 仍为 72 行。

### 4. 验收表逐条

| # | 判据 | 结论与真实证据 |
| --- | --- | --- |
| 1 | M1 747 条逐条通过且字段解释不变 | **PASS**：`178/178 M1 identities covered OK (inventory sync OK; 15 data files, 747 cases; data coverage gaps: 0)`；`git diff -- tests/vectors/isa/ tests/vectors/inventory.md` 为空；M1 成功行逐字节未改。**BLOCKED**（不在本任务能力内）：M1 之外的历史 schema 迁移；替代证据为上面三行。 |
| 2 | 正样例覆盖 RF / FCSR / f32 高半部 / 异常 / memory / blocked OPEN-S-ID | **PASS**：19 例 / 13 identity；`facets 146 active / 6 blocked`（blocked 为 `semantics`×4 + `nan_propagation`×2，指向 `D15`×4、`D17:S6`、`D17:S5`）；`fcsr asserts 11`、`D13 half-observations 7`；facet `cite` 缺失数 = 0。 |
| 3 | validator 对错 RF 索引 / 非法 flags / active+OPEN/S / 缺 citation / 未知 identity 分别真实 FAIL | **PASS**：V1/V2（错 RF 索引与键形）、V5（非法 flag）、V12（active facet 带 open_ids）、V14（缺 citation）、V15 + V24（未知 identity / 未知 oracle.kind）各自 rc=1，marker 如上表；另有 V3/V4/V6–V11/V13/V16–V23/V25–V33 共 34 条。 |
| 4 | oracle I/O 不含实现依赖，由 testcases 文档唯一声明 | **PASS**：`check_f1_oracle_io: OK (0 violations)`，扫 8 个文件，B1 禁 oracle / B2 宿主 float / B3 读 spec 正文 / B4 自证 / B5 位型自检五组规则；接口唯一声明在 `docs/testcases/f1-oracle-io.md`（ADR-1004 D3/D10 的所有权边界）。反例 V35/V36/V37 证明 B2/B5/B4 可失败。 |
| 5 | 六个 active OPEN-ID 对应 facet 取得确定语义 | **PASS**：消费 `resolution.rule_tables`（D11 whitelist=10、D12 auto=53、D13 write=18、D15 arith=18、D16=36），六键 `D17:S1,S3,S4,S5,S6,S8` 全部在事实层有确定取值；`d17 active` 六键、`d17 trace_only: D17:S2`、`d17 non_gap: D17:S7` 三类分离。**BLOCKED**：`D15:canonical_qnan_bits` 仍为 `None`（ADR-1013 未给 64 位常量，下游不得代填）；`CAP-01:root-log-correct-rounding` 仍 `BLOCKED`；`rootn(-0,2)` 仍是唯一 `unspecified` 词条，`foroot` 用例以 `oracle.kind: open` 记录空期望。三者均**不得**取得唯一 expected，本任务未为其编造任何位型。 |

### 5. 语义裁定（本次执行中确定并落到代码注释里的 IEEE-754 判据）

这些不是「实现跑出来的」，是按 IEEE 754-2008 条文手工裁定后写进
`f1_oracle_values.py` docstring 与 KAT 表注释的；每一条都有对应 KAT 行在跑：

1. **非零 ÷ 0 ⇒ ±∞，四种舍入模式一致，只置 `DZ`。** §7.2 规定结果是「无限精确结果
   正确舍入后的值」，而 ±∞ 本身精确可表示 ⇒ §7.4 的 inexact 不成立 ⇒ **不置
   `NX`**；除零也**不是** overflow（D16 的 `OF+NX` 配对不适用）⇒ 不置 `OF`。
   落地值：`0.0f` 作除数、RTZ 下 `1.0f/0.0f = 0xFFFFFFFF7F800000` + `DZ`。
2. **`0/0` 是 invalid（`NV`），不是除零。** KAT `div 64 RNE 0 0 → NAN_NONE {NV}`。
3. **溢出按舍入方向属性给结果**：RNE → ±∞；RTZ → ±最大有限；RDN 在正溢出给最大
   有限、负溢出给 −∞；RUP 在正溢出给 +∞、负溢出给 −最大有限。全部同时 `OF+NX`。
4. **underflow 必须 tiny **且** inexact 才置 `UF`**：次正规**精确**相加
   （`2^-1074 + 2^-1074 = 2^-1073`）tiny 但非 inexact ⇒ **无 `UF`**；
   `2^-1074 × 0.75` 才 `UF+NX`。
5. **精确相消的零符号**：`x + (−x)` 与 `(+0) + (−0)` 在 RNE 下都是 `+0`，只有 RDN
   下是 `−0`。
6. **平局取偶与截断方向**：`1.0 + 2^-53` 在 RNE 下保持 `1.0`（尾数最低位为偶）、
   RUP 进位到 `1+2^-52`、RTZ/RDN 截断为 `1.0`；`1.0 + 3·2^-53` 超出半 ulp，进位到
   `1+2^-51`。
7. **比较类 identity 用 qNaN 作输入**：sNaN 置 `NV` 不是这四条比较 identity 的
   **返回值**激活条件；unordered 的输出只由 qcmp/scmp 类别决定
   （`foqcmp/ftqcmp → 0x7FF8000000000000`，`foscmp/ftscmp → 0x7FF0000000000001`，
   ADR-1012 D2/D3）。

> 关于「生成器侧修正过几处期望值缺陷」：本次执行中在
> `f1_oracle_values.py` / `generate_f1_schema_fixtures.py` 侧修正的期望值缺陷，
> **逐条清单没有落盘留档**，因此完成区不写具体条数。可复核的替代证据是：YAML 一律
> 由生成器产出、从不手改；`generate_f1_schema_fixtures.py --out <tmp>` 重新生成的
> 两份 YAML 与仓库副本 **sha256 逐字节相同**（`cmp rc=0`），故任何残留错值都会同时
> 被「41 条 KAT + 400 次独立重算 + 71 行手算」这三条路线中的至少一条抓住。

### 6. 登记的只读分歧（不改只读输入，只登记 + 消费侧取交集）

`contracts/opcodes.yaml` 的 `f1.d17_open_ids` 仍把 `D17:S7` 列为 open，而 ADR-1008
D1 已把它定为 spec-determined non-gap。该文件本任务**只读**，因此：

- `F1Context.d17_active_keys_for()` 改为「`opcodes.yaml` 的 `d17_open_ids` ∩ 六键
  钉死集合」，结果恒为六键；
- `F1Context.d17_opcodes_divergences()` + `ctx.divergences` 把分歧暴露出来，
  `check_f1_context.py` 打印 2 条 `NOTE divergence`（`rd2rf` / `rf2rd`）。

```
  NOTE divergence: rd2rf: opcodes.yaml f1.d17_open_ids 仍列 D17:S7，但 ADR-1008 D1 已定为 spec-determined non-gap；消费侧按六键取交集
  NOTE divergence: rf2rd: opcodes.yaml f1.d17_open_ids 仍列 D17:S7，但 ADR-1008 D1 已定为 spec-determined non-gap；消费侧按六键取交集
F1 CONTEXT: OK (0 fact-layer errors, 0 doc-gate errors; 2 registered read-only divergence(s))
```

同一分歧也登记在 `docs/testcases/f1-oracle-io.md` 的只读分歧表与
`tests/vectors/schema.md`。`contract-f1-floating.md` §6.2 正文写「共 7 行」，甲方
（SPEC-102t 交付物）本任务无权改写，同样只登记不静默采纳。

### 7. 额外校验项（在任务书清单之外补齐的洞）

| 编号 | 内容 | 对应反例 |
| --- | --- | --- |
| D6 | input 侧 fcsr 不得断言 `value` / `observed_mask` | V10 |
| I7 | 双向 static-ILLI 复查（合法编码不得期望 ILLI） | V31 |
| I8 | 伪造门禁：`semantics` blocked 却断言目的寄存器 | V30 |
| C1 | rf 索引必须在 `0..63`（不是只查键形） | V1 |
| I2 | D13 boxing 对**任意** D13 作用域 identity 写 rf 生效 | V28 |

### 8. dirty baseline 前后对比

| | 行数 |
| --- | --- |
| 下发时 baseline（`engineer-dispatch-baseline/git-status.txt`） | 59 |
| 当前 `git status --porcelain=v1 --untracked-files=all` | 72 |

新增 13 个路径，全部是本任务允许范围：`tests/vectors/schema.md`(M)、
`tools/testcases/validate_vectors.py`(M)、`docs/testcases/f1-oracle-io.md`、
`tests/vectors/f1/{valid,invalid}/f1-schema-*.yaml`、
`tools/testcases/{f1_schema,f1_cases,f1_oracle_values,generate_f1_schema_fixtures,
verify_f1_expected_values,check_f1_context,check_f1_oracle_io,
test_f1_schema_counterexamples}.py`。

`comm -23`（基线有、当前无）= **空**：没有一条既有用户改动被删或被还原。基线 42 个
脏文件逐一 `sha256sum -c` → 42 个 `OK`、0 个失败，即本任务**没有触碰任何既有用户
改动**（`contracts/legality_rules.yaml` 的 125 行新增属基线既有改动，见
`baseline/git-status.txt` 第 10 行）。

未 `git commit`、未 `git push`、`git stash list` 为空、无提交产生
（HEAD 仍为 `9546823`）、未调用其它 agent、未触碰其它仓库。

### 9. 遗留与风险

- **BLOCKED**：`CAP-01:root-log-correct-rounding` —— root/log 的独立正确舍入算法是
  真实能力缺口，ADR Accepted 只解除语义选择门禁，不解除算法能力。`foroot` /
  `ftroot` 只允许断言编码、合法性、静态 fault，**不允许**断言结果位型。
- **BLOCKED**：`D15:canonical_qnan_bits` —— ADR-1013 未给 64 位 canonical qNaN 常量，
  `rule_tables.D15.canonical_qnan_bits` 保持 `null`；下游不得代填。
- **BLOCKED**：`rootn(-0,2)` —— 规范明示 `explicitly-unspecified`，本任务用第四种
  oracle kind `open` 记录空期望（`f1-foroot-negative-zero-unspecified`、
  `f1-fosclb-d17s5-blocked-facet` 两例），永不取得唯一 expected。
- **BLOCKED**：验收 #1 的「M1 之外的历史 schema 迁移」不在本任务范围，见上表。
- **风险（只读输入分歧，2 处）**：`contracts/opcodes.yaml` 与
  `contract-f1-floating.md` §6.2 仍把 `D17:S7` 记作 open / 写「共 7 行」。本任务按
  ADR-1008 D1 以六键为准并登记分歧，**未**修改这两个只读输入；后续任务若要消除
  分歧须由对应上游任务（`SPEC-103t` 返工 / infra）处理。
- **能力缺口登记**：生成器侧期望值缺陷的逐条修正清单未留档（见 §5 末段说明），
  已用「重新生成 sha256 逐字节相同 + 三条独立重算路线」作为替代证据。
- 临时目录 `/tmp/opencode/TESTCASES-101t/reviewer/` 已删除；
  `/tmp/opencode/TESTCASES-101t/` 只保留 `dispatch-baseline/` 与
  `engineer-dispatch-baseline/` 两个基线目录。

### 10. 复现命令

```bash
cd <repo>
python3 tools/testcases/validate_vectors.py                        # EXIT=0
python3 tools/testcases/validate_vectors.py --adr-gate open        # EXIT=0
python3 tools/testcases/validate_vectors.py --adr-gate closed      # EXIT=1（72 errors）
make validate-vectors                                              # EXIT=0
python3 tools/testcases/check_f1_context.py                        # EXIT=0（2 NOTE divergence）
python3 tools/testcases/check_f1_oracle_io.py                      # EXIT=0
python3 tools/testcases/verify_f1_expected_values.py               # EXIT=0
python3 tools/testcases/test_f1_schema_counterexamples.py           # EXIT=0（39/39）
python3 .work/log/testcases/TESTCASES-101t-hand-recompute.py       # EXIT=0（71/71）
python3 tools/testcases/generate_f1_schema_fixtures.py --out <tmp> # 重新生成，cmp rc=0
```

### 11. `/complete` reviewer 结论（2026-09-29：Needs Revision，证据作废）

- reviewer 使用 `/tmp/opencode/TESTCASES-101t/reviewer/` 独立字节复制树（`copy_symlink_count=0`、`shared_inode_count=0`），正常复跑 validator、context、oracle I/O、400 次独立重算、71/71 手算、fixture 复现、M1 747 compatibility 与 39/39 反例均通过；对 validator/oracle-I/O/recompute/context/hand-oracle 的独立非空注入分别取得 `C1`/`B2`/`MISMATCH`/`G-DOC`/`FATAL` 非零失败并还原复绿。
- 但审查后与 `/tmp/opencode/TESTCASES-101t/reviewer/baseline/` 三件套比对时，真实仓库新增基线外路径 `docs/progress-report-2026-09-29.md`；审查前 72 条路径均仍在且 72 个 SHA256 未变，任务书 SHA256 亦未变。按 `workflow.md` §11.1 路径集变化使本轮 reviewer 结论整体作废，不能沿用其 Accepted 证据。
- 主会话据 reviewer 的 **Needs Revision** 将任务置为 **待返工**，未调用 architect。返工不是实现缺陷：须待工作树稳定后重新建立 reviewer baseline，并从头进行独立验收；不得沿用本轮审查证据。

### 12. 用户授权的外部汇报排除（2026-09-29）

- 用户明确确认 `docs/progress-report-2026-09-29.md` 是与本任务无关的项目汇报，不影响本任务结论；该路径保留、不删除、不纳入本任务 diff，也不将其视为 engineer/reviewer 改动。
- 因此前 72 条 baseline 路径及其 SHA256、任务书副本均保持一致，主会话将任务恢复为 **待验收**，要求 reviewer 对同一独立证据在该单一路径已获用户批准排除的条件下重作结论；后续 architect 仍须独立交叉复核该排除边界与证据。

### 13. `/complete` architect 交叉复核（2026-09-29：Needs Revision）

- architect 确认：用户批准排除的 `docs/progress-report-2026-09-29.md` 是唯一额外路径；72 条 baseline 路径/哈希一致，字节复制树无 symlink/共享 inode，M1 entrypoints 及 39/39 反例均有有效证据。
- 但 §11 的 cleanup 记录不实：`/tmp/opencode/TESTCASES-101t/reviewer/` 实际仍包含 `repo-copy/`、`tree/`、`inject/`、生成样例与脚本；任务完成区 §9 却声称该目录已删除。此外，授权排除后的 reviewer **Accepted** 尚未作为持久验收记录写入任务书。
- 结论为 **Needs Revision**。主会话将任务置为 **待返工**；不得以现有 reviewer Accepted 收尾。返工须在不触碰实现语义的前提下清理审查临时树、生成可审计的 post-baseline SHA256 比对，并补记授权排除后的 reviewer 结论；随后重新进行 architect 交叉复核。

### 14. 最小证据返工（2026-09-29）

- 用户授权主会话仅处理证据收尾，不改实现语义：已清理 `/tmp/opencode/TESTCASES-101t/reviewer/`（`reviewer_tree_cleanup=OK`）。真实输出保存在 `.work/log/testcases/TESTCASES-101t-return-post-baseline.log`。
- post-baseline 比对：72 条 baseline 路径均仍存在；唯一新增路径为用户批准排除的 `docs/progress-report-2026-09-29.md`；除本任务书（状态转换与本完成区记录）外，baseline 内容 SHA256 无变化。未删除或改写外部汇报。
- reviewer 在该单一路径排除的用户授权下已重新给出 **Accepted**：byte-copy 审查树 `copy_symlink_count=0`、`shared_inode_count=0`；M1 747 compatibility、正常验收与 39/39 可复原反例有效；validator/oracle-I/O/recompute/context/hand-oracle 的独立非空注入分别命中 `C1`/`B2`/`MISMATCH`/`G-DOC`/`FATAL` 非零失败并复绿。
- 任务恢复为 **待验收**，只等待重新进行 architect 交叉复核；本条不改变任何 ADR decision，也不把 schema/oracle PASS 扩大为 LLVM/QEMU/E2E PASS。

### 15. `/complete` architect 复核收尾（2026-09-29：Accepted）

- architect 复核 **Accepted**：`/tmp/opencode/TESTCASES-101t/reviewer/` 已不存在；72/72 baseline 路径保留，唯一新增为用户批准排除的 `docs/progress-report-2026-09-29.md`，唯一 baseline hash 差异是任务书的授权状态/完成区更新。
- architect 确认 §14 已如实持久化 reviewer **Accepted** 与隔离、M1 747、正常 checker/oracle、39/39 非空 FAIL/还原证据；S2/S7、`rootn(-0,2)`、root/log 舍入与 canonical qNaN 能力边界未被扩大，ADR/spec/contracts/外部汇报均未改写。
- 主会话据双角色 Accepted 将任务置为 **已验证**。本任务只冻结 schema/oracle 接口与样例；LLVM/QEMU/E2E 仍未实现或验证，不计 PASS。
