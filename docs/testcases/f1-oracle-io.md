# F1 oracle I/O 接口（TESTCASES-101t 冻结）

> 本文是 **TESTCASES-101t** 交付的接口冻结件。`tests/vectors/schema.md` 的 F1 章节
> 描述**数据形状**；本文描述**接口边界**：谁能提供期望值、以什么形式提供、哪些点
> 本任务**拒绝**给出唯一答案，以及后继任务（`TESTCASES-102t` 全量向量、
> `QEMU-101t`、`INTEG-102t`）可以直接依赖什么。

## 1. 一句话接口

```
F1 向量 = (identity, encoding, 预置状态)  --[F1 oracle]-->  期望状态 | "无唯一期望"
```

oracle 的**唯一**合法形态是 **32/64 位整数位型**（`0x` 开头的 hex 字符串）、
FCSR 域值、48 位有效地址，以及 `ILLI` / `MALIGN` 两个字面 fault。
**不存在**任何以「浮点字面量」形式出现的期望值：`3.0` 不合法，只有
`0x4008000000000000` 合法。

理由（不是风格偏好）：F1 的期望值必须能由**独立的第二路重算**判定。如果 oracle
的输入是十进制浮点，判定就得引入宿主 FPU/libm/SoftFloat，那就不再是独立 oracle。

## 2. 分层

| 层 | 位置 | 职责 | 允许读实现侧吗 |
|----|------|------|----------------|
| 事实层 | `tools/testcases/f1_schema.py`（`F1Context`） | 从合约 `contract-f1-floating.md`、`contracts/f1_gap_proofs.yaml` 的 `resolution` 层、Accepted ADR-1008…1015 **重算** FCSR 布局 / 64 identity / D11 白名单 / D17 台账，并与字面量钉死值比对 | 否 |
| 判定层 | `tools/testcases/f1_cases.py` | 逐 case / 逐树的机械判定（schema + 已激活 ADR 规则） | 否 |
| oracle 值层 | `tools/testcases/f1_oracle_values.py` | 32/64 位期望位型与 FCSR 域常量的**手写整数**来源 | 否 |
| 生成器 | `tools/testcases/generate_f1_schema_fixtures.py` | 造样例，**只写不读**向量数据（B4） | 否 |
| 独立重算 | `tools/testcases/verify_f1_expected_values.py` | 第二路：自带纯整数 IEEE-754 引擎，**不 import** 上面任何模块 | 否 |
| 门控 | `tools/testcases/check_f1_oracle_io.py` | B1–B5 静态扫描，证伪「独立性」承诺 | — |
| 反例门控 | `tools/testcases/test_f1_schema_counterexamples.py` | 38 条注入反例，证伪「检查器有 FAIL 路径」 | — |

## 3. oracle 的四种形态

| `oracle.kind` | 语义 | 何时用 |
|---------------|------|--------|
| `order` | 有唯一顺序语义，给出逐记录期望 | 绝大多数 F1 case |
| `block` | 块赋值，另给 `elements[]` 几何 | `ldm.*-rf` / `stm.*-rf` |
| `unordered` | 源/目的跨组重叠，**读写顺序未决** | `rd2rf` / `rf2rd`（`D17:S7` 已证明跨组不 alias，故此形态用于表达「重叠编号 ≠ alias」） |
| `open` | **断言「不存在唯一期望值」** | blocked facet 带 `open_ids`、`blocked_points` 非空、或 `unspecified` 非空 |

`open` 是接口的一部分，不是「留空」。它带四条硬约束（`O1`）：

1. `records: []`；
2. **不得**有 `expected_state` / `expected_fault`；
3. **不得**声明 `order`（没有可钉的观测顺序）；
4. **必须**给出理由：blocked facet 带 `open_ids`，或 `blocked_points`/`unspecified` 非空。

第 4 条是关键：否则「本任务不知道」与「本任务忘了写」在数据上不可区分，
下游无法判断该 case 是不是一个**未完成的**向量。

## 4. 本任务**拒绝**给出唯一答案的点（BLOCKED）

| 标记 | 范围 | 为什么不能给 | 允许写什么 |
|------|------|--------------|------------|
| `D15:canonical_qnan_bits` | 任何 qNaN **输入**的 18 条运算 identity | ADR-1013 未给 64 位 canonical qNaN 常量；`rule_tables.D15.canonical_qnan_bits` 是 `null` | 允许断言 `flags: [NV]`（IEEE 754 §7.2：qNaN 输入不置 NV、sNaN 输入置 NV——**这两条恰好是已激活值**）；**不允许**断言目的寄存器的位型 |
| `CAP-01:root-log-correct-rounding` | `foroot` / `ftroot` 的正确舍入 | root/log 的独立正确舍入算法是**能力缺口**（`resolution.capability_gaps.CAP-01 = BLOCKED`），不是 ADR 投影能解除的语义选择 | 允许断言编码、合法性、静态 fault；不允许断言结果位型 |
| `rootn(-0,2)` | `foroot` / `ftroot`，指数 = −0 | 规范**明示「不做具体要求」** | 只能用 `unspecified: [rootn(-0,2)]` + `oracle.kind: open`；**任何** bank 都不许断言 |
| `D17:S1`…`D17:S8`（6 个 active 键） | 逐 identity 的 facet 级 | 见 `schema.md` 的 ledger 表 | 只能出现在 `ledger_refs.active_keys` 与 blocked facet 的 `open_ids` |
| `D17:S2` | 来源追踪 | ledger 外，**无行为后果** | 只能出现在 `ledger_refs.trace_only`；永不阻塞、永不计 PASS |
| `D17:S7` | `rd2rf` / `rf2rd` | ADR-1008 D1 证明跨组不 alias，非真实缺口 | 只能出现在 `ledger_refs.non_gap` |

**编造门（`I8`）**：`semantics` facet 为 `blocked` 的 case，**不得**断言目的寄存器。
`D15:canonical_qnan_bits` 为何要配 `I8`：ADR-1013 没给常量，那么「随便写一个
qNaN 位型」就是编造；`I8` 让这类编造在数据层被机械拒绝。

## 5. 期望值的三条纪律

1. **位型而非浮点字面量**。所有 32/64 位值是 `0x` hex 字符串。禁止
   `float(`/`math.`/`Decimal(`/`Fraction(`/`struct.unpack('f')`（检查项 B2）。
2. **不得反读**。生成器不得从 `tests/vectors/f1/` 读回期望值再吐一遍（检查项 B4）。
   否则「样例过 validator」只是自证。
3. **不得来自实现**。不得 import/调用 `llc` / `llvm` / `qemu` / `softfloat` /
   `host_fpu`，不得 `ctypes` 加载宿主 libm（检查项 B1）。`spec/` 正文只可作为
   `spec_cite` 字符串溯源，**不得**被脚本读成执行输入（检查项 B3）。

配套的第二路证据：`verify_f1_expected_values.py` 自带一套**纯整数** IEEE-754-2008
引擎（加减乘除 + 四种舍入模式 + 平局取偶 + 次正规 + tiny/inexact + 溢出方向表 +
inf/NaN 传播 + `0/0`），用 41 条**手写 KAT** 自证引擎本身，再对 `valid/` 的每一条
断言逐位复算。它与 `f1_oracle_values.py` **没有共享代码**——这是它作为独立 oracle 的
前提（反例 `V38`：把 `1.0+2.0=3.0` 的期望改成 `0x4008000000000001` 且让 YAML 自身
保持自洽，validator 静态检查 `rc=0` 放行，只有独立重算报 `MISMATCH`）。

## 6. 本任务在语义上做的**读法裁定**（可被后续任务挑战）

以下三条不在合约字面上，是为了让期望值**唯一可算**而做的读法裁定。每条都记了依据，
并刻意选择「不钉住未激活值」的那一侧。

### 6.1 非零有限数 ÷ 0 ⇒ ±∞，只置 DZ，**不**置 NX

IEEE 754-2008 §7.2 末段与 Table 3 规定：除零的结果是「无限精确结果正确舍入后的
值」，而 ±∞ 本身就是可表示的**精确值**，因此**四种舍入模式一律给 ±∞**
（RTZ 也不例外）。又因结果与无限精确结果相等，§7.4 的 inexact 不成立 ⇒ 只置 `DZ`。
除零也**不是** overflow，D16 的 `OF+NX` 组合不适用。

样例：`f1-ftdiv-rounding-rtz-dz`（`1.0f / 0.0f` ⇒ `0xFFFFFFFF7F800000`，`flags: [DZ]`）。

> 这条**修正**了本任务早期的一版读法（曾打算按「RTZ 截断成 ±0」并附带 `DZ+NX`）。
> 修正后那个 DZ+NX 残留项消失，不再是遗留风险。

### 6.2 比较 identity 的 unordered 样例用 **qNaN** 输入

`ftqcmp`/`ftscmp`/`foqcmp`/`foscmp` 的 `compare_unordered` facet 由 D14 承载，而
`rule_tables` 只对**18 条运算 identity**固定了「qNaN 不置 NV / sNaN 置 NV」。比较
identity 不在这 18 条里，因此若用 sNaN 作输入并断言 `NV`，就等于**钉住一个未激活的
值**。样例 `f1-foqcmp-unordered-d14` 改用 qNaN 输入，只断言 D14 已激活的 unordered
结果位型。

### 6.3 `rf_format` 由 `rule_tables.D13.write_scope` 派生，不按助记符猜

「这条指令产出的 rf 值是 tetra 还是双精度」由合约 §1 声明是**未规定**的读法问题
（`fo2ft`/`ft2fo` 属「格式转换」节）。本任务的取法：以 `D13.write_scope`
（**18 条产出 f32 值并写 rf 的 identity**）为准，而不是按助记符后缀猜。
`check_f1_context.py` 每次运行都重算该集合并与 18 交叉。

## 7. 只读分歧登记（**不得**在本任务修复）

| 分歧 | 甲方 | 乙方 | 本任务处置 |
|------|------|------|------------|
| D17 台账行数 | `.xkw/knowledge/contract-f1-floating.md` §6.2 表格与正文写「共 7 行」，含 `D17:S7` 状态 `BLOCKED` | `contracts/f1_gap_proofs.yaml` 的 `historical_layer.d17_open_ledger` 与 `rule_tables.D17.active_keys` 只有 **6** 键（S1/S3/S4/S5/S6/S8），S7 移入 `non_gap_records` | 以**乙方**为准（依据 ADR-1008 D1「`SPEC-103t` 返工须将 S7 改列为 spec-determined/non-gap 证据」）。甲方是 SPEC-102t 的历史交付物，**本任务无权改写**；已在 `schema.md` 与此处登记，`f1_schema.F1Context` 对三方做交叉断言 |
| `d17_open_ids` 逐 identity 投影 | `contracts/opcodes.yaml` 的 `f1.d17_open_ids` 里 `rd2rf` / `rf2rd` **仍列 `D17:S7`** | 同上乙方（六键 + non-gap） | `F1Context.d17_active_keys_for()` 按**钉死的六键取交集**再返回，不照抄 opcodes.yaml（ADR-1008 D1 明文要求后续消费者不得把 S7 当 active OPEN 门禁）。差异由 `d17_opcodes_divergences()` 逐条登记，`check_f1_context.py` 每次运行打印 `NOTE divergence`，**不静默吞掉** |

两处分歧的共同点：`contracts/` 与 `.xkw/knowledge/contract-f1-floating.md` 都是本任务
的**只读**输入，修数据的责任在 `SPEC-103t` 的返工范围，不在 `TESTCASES-101t`。

## 8. 后继任务可直接依赖什么

| 后继 | 可直接依赖 | 仍需自己解决 |
|------|------------|--------------|
| `TESTCASES-102t` | schema 判定层（`f1_cases.py`）、四种 `oracle.kind` 文法、`open` 的四条硬约束、BLOCKED 清单、本文的读法裁定 | 全量 64 identity 的向量；root/log 的正确舍入仍受 `CAP-01` 阻塞 |
| `QEMU-101t` | `expected_fault ∈ {ILLI, MALIGN}`、`expected_state` 的 bank 形状、`fault.pc` 语义 | 实现侧 `ldm`/`stm` 的 EA 推进必须与 `EA0+i*width` 一致 |
| `INTEG-102t` | `ledger_refs` 三列表的形状 | 不得把 `D17:S2`/`D17:S7` 计入 PASS |

## 9. 复现本文档所述冻结的全部检查

```bash
make validate-vectors                                        # M1 747 条 + F1 19/53 门控
python3 tools/testcases/check_f1_context.py                  # 事实层重算
python3 tools/testcases/check_f1_oracle_io.py                # B1–B5 独立性门控
python3 tools/testcases/verify_f1_expected_values.py         # 41 条 KAT + 逐条独立重算
python3 tools/testcases/test_f1_schema_counterexamples.py    # 38 条注入反例
python3 tools/testcases/validate_vectors.py --adr-gate closed   # 期望非零退出
```

日志落在 `.work/log/testcases/TESTCASES-101t-*.log`。

## 10. 冻结词条索引

`check_f1_context.py` 的**文档门禁**（规则前缀 `G-DOC`）逐条要求下面这些字面量在
**两份**文档里都出现。词条从事实层取（facet 键 / oracle 形态 / OPEN-ID / BLOCKED 点），
因此事实层改了而文档没跟着改时，脚本立刻红。

| 类别 | 冻结词条 | 数据形状见 |
|------|----------|------------|
| schema 章节锚点 | `# F1 浮点向量 schema` | `tests/vectors/schema.md` |
| oracle 形态（4） | `order` / `block` / `unordered` / `open` | 本文 §3 |
| ledger 三列表 | `active_keys` / `trace_only` / `non_gap` | 本文 §4 |
| active OPEN-ID（6） | `D17:S1` / `D17:S3` / `D17:S4` / `D17:S5` / `D17:S6` / `D17:S8` | 本文 §4 |
| ledger 外 / non-gap（2） | `D17:S2` / `D17:S7` | 本文 §4 |
| BLOCKED 点 | `D15:canonical_qnan_bits` / `CAP-01:root-log-correct-rounding` | 本文 §4 |
| 规范未决点 | `rootn(-0,2)` | 本文 §4 |
| 舍入模式（4） | `RNE` / `RTZ` / `RDN` / `RUP` | `tests/vectors/schema.md` 的 `fcsr` 子结构 |
| 异常 flag（5） | `NV` / `DZ` / `OF` / `UF` / `NX` | 同上 |
| fault（2） | `ILLI` / `MALIGN` | 同上 |
