# Test Vector Schema

本文件描述**两棵**互不干扰的向量树：

| 树 | 范围 | 语义输入 | 章节 |
|----|------|----------|------|
| `tests/vectors/isa/*.yaml` | M1 整数指令 | `contract-isa.md` + `contracts/opcodes.yaml` + `contracts/legality_rules.yaml` + ADR-0004 | 上文（`# 字段` … `# 校验`） |
| `tests/vectors/f1/{valid,invalid}/*.yaml` | F1 浮点指令 | `.xkw/knowledge/contract-f1-floating.md` + `contracts/f1_gap_proofs.yaml` 的 `resolution` 层 + Accepted ADR-1008…1015 | [F1 浮点向量 schema](#f1-浮点向量-schema) |

两棵树的所有字段与语义期望值都**独立派生自**锁定的规范与合约，
**不得**从 LLVM 汇编输出、QEMU 运行结果或实现侧 FPU（SoftFloat 等）反推。

`isa/*.yaml` 每个文件是一个 YAML 列表，每个元素是一条 test case。

## 字段

### 必填字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `mnemonic` | string | 0.5.3 助记符（对应 `contracts/opcodes.yaml` 的 `mnemonic`） |
| `insn` | string | opcode 身份（对应 `contracts/opcodes.yaml` 的 `insn`；**单独不唯一**） |
| `format` | string | 指令格式；与 `insn` 组成覆盖率主键 `(insn, format)`（唯一） |
| `class` | string | 向量类别：`encoding` / `legality` / `semantic` / `boundary` / `overlap` |
| `encoding` | object | 见下「`encoding` 子结构」 |
| `input_state` | object | 执行前的寄存器/内存状态（仅列相关字段；可为空对象 `{}`） |
| `spec_cite` | string | 语义/合法性来源（规范章节；测试机约定引用 ADR-0004 章节）。**非空字符串** |

### 可选 / 条件字段

| 字段 | 类型 | 条件 | 说明 |
|------|------|------|------|
| `expected_state` | object 或 null | active `semantic`/`boundary`/`overlap` 必填；`encoding`/`legality` 及 deferred 必须为 `null` | 执行后的寄存器/内存状态 |
| `expected_pc` | string 或 null | 可选（本任务中）；`legality`/`encoding` 不得为非 null | 执行后 PC（`rb0`）的期望值，48-bit 有效地址 hex |
| `expected_fault` | string 或 null | 可选 | `null` / `ILLI` / `UNDI` / `MALIGN` / `IALIGN` / `RASOF` / `RASUF` / `UNMAPPED` |
| `status` | string | 可选，默认 `active` | `active` / `deferred` |
| `deferred_reason` | string | `status=deferred` 时必填（非空） | 暂缓原因（如 `"C-27"`） |
| `notes` | string | 可选 | 人类可读备注（如 `shamt = rd<k>`、PC 地址来源） |

### `encoding` 子结构

| 字段 | 类型 | 说明 |
|------|------|------|
| `encoding.word` | string | 完整 32-bit 指令字（hex，`≤ 0xFFFFFFFF`）；须满足 `(word & mask) == value` |
| `encoding.reserved` | boolean | **仅限保留编码 case**（`class: legality`、`expected_fault: UNDI`）。`true` = 该 word 是 QFC 主表 / MISC 子表的空白单元格（reserved），**无** `(insn, format)` 身份。缺省或 `false` = 正常编码 |

#### 保留编码 case（`encoding.reserved: true`）

保留编码（QFC 主表 / MISC 子表空白单元格）**无** `(insn, format)` 身份
（`contracts/opcodes.yaml` 只含已定义编码），故无法满足检查 7/8。
方案 A（`TESTCASES-008t`，已裁定）以 `encoding.reserved: true` 显式标记。

```yaml
- class: legality
  encoding:
    word: "0x08040001"       # 非全零；QFC 主表空白单元格
    reserved: true           # 显式声明：保留编码
  mnemonic: null             # 无已定义助记符
  insn: null                 # 无身份
  format: null               # 无格式
  input_state: {}
  expected_state: null
  expected_pc: null
  expected_fault: UNDI
  status: active
  spec_cite: "SimRISC-00 §SimRISC QFC; contract-isa §2.9/§8.2"
  notes: "QFC 主表 op=0x08（0000-1xxx 整行 reserved）"
```

**字段约束**（`encoding.reserved: true` 时）：

| 约束 | 说明 |
|------|------|
| `class` 必须为 `legality` | 保留编码 case 只能是 fault 期望 |
| `expected_fault` 必须为 `UNDI` | 保留编码触发 UNDI（§8.2），**不是** ILLI |
| `status` 必须为 `active` | 保留编码 case 不可 deferred |
| `word` 不得为 `0x00000000` | 全零字 = `illi` → ILLI（§8.3），非 UNDI |
| `mnemonic` / `insn` 为 `null` | 无已定义身份 |
| `format` 可为 `null` 或字符串 | 可选，用于定位子表 |
| `notes` 非空 | 须给出该 word 在 QFC/子表中的具体位置作为 reserved 依据 |
| `spec_cite` 非空 | 须引用 SimRISC-00 QFC / contract-isa §2.9/§8.2 |

**与 ILLI 的区分**：

| 场景 | fault | 依据 |
|------|-------|------|
| QFC/子表空白单元格（reserved 编码） | **UNDI** | §2.9/§8.2 |
| 全零字 `0x00000000`（`illi 0`） | **ILLI** | §8.3 |
| 已定义编码 + 非法操作数/SBZ 违规 | **ILLI** | §9.1 |
| M1 排除但已定义的编码（RF/cfx/LR-SC） | **ILLI** | ADR-0004 D5.1 |

## 状态字段约定

### `input_state` / `expected_state`

- `rd` / `rb` / `ra`：键为架构寄存器名（`rd1`…`rd63` / `rb1`…`rb63` / `ra0`…`ra63`），
  值为 64 位 hex 字符串。
- **不得出现 `rd0` / `rb0` 条目**：`rd0` 恒零、`rb0` 为 PC（ADR-0004 D6.5），
  预置无意义且会误触发 ILLI。
- `memory`：元素为 `{address, value}`；`address` 为 48-bit 有效地址
  （`≤ 0xffff_ffff_ffff`，即 `bits[63:48]=0`）。
- **`input_state.memory[].value` 契约**（ADR-0009 补注续二）：`value` 表示
  「`address` 处存放的 **N 字节值**」，N = 被测向量的**访存宽度**（由 mnemonic
  推导：`b`→1、`w`→2、`t`→4、`o`→8；`stm.*`/`ldm.*` 按元素宽度）。
  harness 以宽度 N 的 store（`st.b`/`st.w`/`st.t`/`st.o`）将 `value` 的低 N
  字节写到 `address`。大端下 `value=0x42` + `st.b` → `address` 处写入 `0x42`；
  `st.o` 则写入 `00 00 00 00 00 00 00 42`（`0x42` 在 `address+7`）。

```yaml
- mnemonic: ld.ub
  insn: ld.ub-rd
  format: rrii
  class: semantic
  encoding:
    word: "0x10041000"      # ld.ub rd1, rb1, 0（rdha=1、rbhb=1、imms12=0）
  input_state:
    rd:
      rd1: "0x0000000000000001"
    rb:
      rb1: "0x0000ffff00000000"
    memory:
      - address: "0x0000ffff00000000"
        value: "0x0000000000000002"
  expected_state:
    rd:
      rd1: "0x0000000000000002"
    rb: {}
    ra: {}
    memory: []
  expected_pc: null
  expected_fault: null
  status: active
  deferred_reason: null
  spec_cite: "SimRISC-01 §存取RD寄存器"
  notes: ""
```

### 内存地址范围（ADR-0004 D1）

- RAM 窗口：`[0xffff_0000_0000, 0xffff_00ff_ffff]`（16 MiB）。
- `semantic` 类的 `memory` 地址**必须**落在 RAM 窗口内（validator 阻断校验）。
- `legality` 类可表达 unmapped（`expected_fault: UNMAPPED`）等越界地址，不受此限。
- 非 RAM 地址（ROM `0xffff_ffff_0000`–`0xffff_ffff_ffff`、Exit port
  `0xffff_8000_0000`–`0xffff_8000_0007`）须显式引用 ADR-0004 章节。

### `expected_pc`（本版新增）

- 语义：**该指令 retire 后 `rb0` 的期望值**（48-bit 有效地址 hex；`null`/缺省表示不断言 PC）。
- 与 `expected_state` **正交**：寄存器/内存效果用 `expected_state` 表达，PC 效果用
  `expected_pc` 表达（`expected_state` 不预置 `rb0`，见上）。
- `rb0` 在执行时等于**当前指令地址**（ADR-0004 D6.5），故相对跳转目标 = 当前地址 +
  `(imm<<2)`，PC 效果可计算、非自由变量。
- 规则：
  - `class: semantic` / `boundary` / `overlap` 且指令改变 PC（`br.*` taken、`jump`、
    `call`、`ret`）时**应**给出 `expected_pc`；该**存在性**要求由 `TESTCASES-005t`
    （`ctrl-br`）/`006t`（`ctrl-jump`/`ctrl-call`/`ctrl-ret`）随数据一并强制。
  - `expected_pc` 出现（非 null）时须为 48-bit 有效地址。
  - `class: legality` / `encoding` **不得**带非 null `expected_pc`（与 `expected_state` 同规则）。
  - `status: deferred` 时 `expected_pc` 必须为 `null`。
- 本任务只落 schema + validator 支持，不改数据。

## class 定义

| class | expected_state | expected_pc | expected_fault | 用途 |
|-------|---------------|-------------|----------------|------|
| `encoding` | `null` | `null` | `null` | `word` 与 `opcodes.yaml` 的 mask/value 一致，且**可解码执行无 fault** |
| `legality` | `null` | `null` | 非 null | **所有 fault 期望的 case**：静态非法（rd0/rb0/immu6=0/shamt 越界等 → ILLI/UNDI）与动态 fault（MALIGN/IALIGN/RASOF/RASUF/除零/INT_MIN÷−1/unmapped） |
| `semantic` | 必填 | 改变 PC 时必填 | `null` | 正常执行后寄存器/内存/PC 状态正确 |
| `boundary` | 必填 | 改变 PC 时必填 | `null` 或 `ILLI` | 边界值（signed-min / signed-max / zero / carry / overflow） |
| `overlap` | 必填或 `null` | 改变 PC 时必填 | `null` 或 `ILLI` | src=dst、双目的、多寄存器范围重叠 |

### `encoding` 类对恒 fault 指令的豁免（F6）

`encoding` 类的定义是「**可解码执行无 fault**」，因此**恒 fault 指令无法构造
`encoding` case**：

- **`illi`**（`oiii`）：恒触发 ILLI（`contract-isa.md` §8.2/§9.1；全零字
  `0x00000000` 即 `illi 0` → ILLI，§8.3，**不是** UNDI）。故 `illi` **豁免**
  `encoding`（及 `semantic`）类，其覆盖率由 `legality` active
  （`expected_fault: ILLI`）满足；inventory 显式记 `—`。

**例外（理由不同，不得混同）**：`ret-riii` 亦无 `encoding` case，但**并非**恒 fault
——`ret` 的返回目标依赖 harness 布局、单指令不可构造。其理由与处置见
`TESTCASES-006t`；inventory 显式记 `—` 并注明理由。

### `status=deferred` 规则

- `expected_state` / `expected_pc` 必须为 `null`；
- `deferred_reason` 必须为非空字符串；
- C-27（条件赋值快照）的 `overlap` case 必须出现在 `inventory.md` 中，**不得静默缺席**。

## Fault 类型

| Fault | 含义 | 来源 |
|-------|------|------|
| `ILLI` | 非法指令 | `contract-isa.md` §9.1 |
| `UNDI` | 保留编码 | §8.2 |
| `MALIGN` | 内存访问非对齐 | §9 |
| `IALIGN` | 取指非对齐 | §9 |
| `RASOF` | RegRAS 溢出 | §9.2 |
| `RASUF` | RegRAS 下溢 | §9.2 |
| `UNMAPPED` | 地址未映射（测试机约定，退出码 `0x87`） | ADR-0004 D5.8 |

## 覆盖率要求

- **M1 scope**：`contracts/opcodes.yaml` 中 `excluded_m1 != true` 的 **178 条**。
  不得排除 RA 存取/块赋值或 `swym`/`illi`/`fence`。
- **主键 `(insn, format)`**（等价机器键 `(op, ha)`，`op = value>>24`、
  `ha = (value>>18)&0x3f`）。`insn` 单独不唯一（20 组 `orrr`/`orri` 共享 `insn`），
  **必须**带 `format`。
- 每个 M1 身份 `(insn, format)` 至少 1 条对应 class 的 case；算术/移位类还需
  `boundary`；条件赋值 `overlap` 按 C-27 deferred。
- 覆盖率与 `inventory.md` 机械同步：`inventory.md` 的 M1 行集必须与
  `opcodes.yaml` 的 M1 身份集一致（无缺、无多、无重复）——由
  `tools/testcases/validate_vectors.py` 校验。

## 文件组织（方案 A：按运算族分，bank 混在文件内）

```
tests/vectors/isa/
  reg-arith.yaml          reg-logic.yaml          reg-shift-extend.yaml
  reg-compare.yaml        reg-cond-assign.yaml    reg-imm-block.yaml
  mem-rd.yaml             mem-rb.yaml             mem-ra.yaml
  ctrl-br.yaml            ctrl-jump.yaml          ctrl-call.yaml
  ctrl-ret.yaml           misc.yaml
```

## 校验

`tools/testcases/validate_vectors.py` 对上述字段、class/fault 取值、`(insn, format)`
存在性与 mask/value 一致性、`expected_pc`、`inventory` 同步、覆盖率等做机械校验；
有错误时 `exit(1)` 并列出文件 + case 序号。完整语义期望值重算属 golden model
模块（见 `.tao/knowledge/deferred.md`），不在 schema validator 能力内。

---

# F1 浮点向量 schema

本章节描述 `tests/vectors/f1/`。F1 与 M1 是**两棵独立的树**：F1 不复用 M1 的
`(insn, format)` 覆盖率主键、不进 `inventory.md`、不改 M1 已固化的 747 条向量。

**语义输入只有三处**（其余一律不得作为语义依据）：

1. `.xkw/knowledge/contract-f1-floating.md`（SPEC-102t，含 §2 FCSR 布局、§3 合法性、
   §4 语义、§5 facet、§6 D-矩阵与 OPEN-ID 台账、§7 静默项）；
2. `contracts/f1_gap_proofs.yaml` 的 `resolution` 层（`rule_tables` / `capability_gaps` /
   `consumer_activation`）；
3. `.xkw/knowledge/adr-1004-f1-floating-phase.md` … `adr-1015-*`（Accepted 的
   ADR-1008…1015）。

`spec/` 只能作为**只读溯源**出现在 `spec_cite` / facet `cite` 字符串里，**不得**被任何
F1 脚本读成执行输入（检查项 B3）。**不得**从 LLVM、QEMU、SoftFloat、宿主浮点或 libm
反推期望值（B1/B2）。

## 文件组织

```
tests/vectors/f1/
  valid/f1-schema-valid.yaml       # 正样例：每条必须**零** error
  invalid/f1-schema-invalid.yaml   # 反样例：每条必须**至少**一个 error（must-FAIL）
```

两棵目录的**同一套** `validate_f1_case()` 判定。反样例不是「另一份 schema」，
而是「同一判定必须能失败」的证据（AGENTS.md 反例门控）。

反样例 id 约定：`neg-<N#>-<被改坏的正样例 id>`（如 `neg-N53-f1-foadd-basic-rf-index`）。
`N#` 是全局递增序号，**不得**复用；后缀必须指向真实存在的正样例 id，便于溯源。
反样例**故意**不满足「树级 id 唯一」不变量（一条被改坏的 base 会与正样例重名），
因此该不变量只在 `valid/` 上强制，注入侧由临时树自测覆盖。

## case 必填字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | 全树唯一、非空。`f1-<identity>-<要点>`（反样例见上） |
| `identity` | string | F1 identity（64 条之一，取自 `contracts/opcodes.yaml`）；**必须**与 `insn` 逐字相同 |
| `insn` | string | 同上（A2） |
| `mnemonic` | string | 助记符 |
| `format` | string | `orrr`/`orri`/`rrrr`/`rrii`（取自 `opcodes.yaml`） |
| `class` | string | `encoding` / `legality` / `semantic` / `boundary` / `overlap` |
| `encoding` | object | 仅 `{word}` |
| `input_state` | object | `{rd, rb, ra, rf, fcsr, memory}` |
| `facets` | object | 11 个 facet 键的**子集**（见下） |
| `ledger_refs` | object | `{active_keys, trace_only, non_gap}` 三个列表 |
| `blocked_points` | list | 案例级未决点（词表见下） |
| `unspecified` | list | 规范明示「不做具体要求」的点（词表见下） |
| `oracle` | object | `{kind, records[, elements][, order][, unordered_case]}` |
| `spec_cite` | string | 非空，且须命中权威文件名（`SimRISC-0*` / `contract-f1-floating` / `adr-10xx` / `opcodes.yaml` / `f1_gap_proofs` / `schema.md`） |
| `status` | string | **只能** `active`。F1 不接受 `deferred`（未决点走 `blocked` facet / `blocked_points`，不走 M1 的 `deferred`） |

条件字段：

| 字段 | 类型 | 条件 |
|------|------|------|
| `expected_state` | object 或缺省 | `expected_fault` 为空时必填（`{rd,rb,ra,rf,fcsr,memory}`） |
| `expected_fault` | string 或缺省 | F1 只允许 `ILLI` / `MALIGN` |
| `expected_pc` | 恒 `null`/缺省 | F1 无任何 identity 改变 PC；给了非 null 即 E2 |
| `order` | string | 可选：`none` / `read-before-write` / `block-increasing` |
| `deferred_reason` | 恒缺省 | F1 无 `deferred` |

## 编码字段与角色

F1 的编码判定式与 M1 **不同**：

```
(word & mask) == (value & mask)          # F1：minor_op 在 ha[23:18]，mask=0xFFFC0000
(word & mask) == value                   # M1（保持不变）
```

即 F1 允许 `ha[23:18]`（minor_op）与 `value` 的对应位不同——`value` 只固定
`op[31:24]`，`orrr` 类再额外固定 `ha[25:24]`（`0xFFFC0000` 掩码保留了这两位）。
F1 的 role 分配（取自 `contracts/opcodes.yaml` 的 `f1.fields`）：

| 形态 | 字段（位域） |
|------|--------------|
| `orrr` / `orri` / `rrrr` 运算与比较 | `ha[23:18]`=`minor_op`；**目的**=`rfhb`/`rdhb[17:12]`；第一源=`rfhc`/`rdha[11:6]`；第二源=`rfhd[5:0]` |
| `ld.*-rf` / `ldm.*-rf` / `st.*-rf` / `stm.*-rf` | `rfha[23:18]`=目的 rf；`rbhb[17:12]`=基址 rb；`imms12_hi[11:6]`+`imms12_lo[5:0]`=12 位有符号位移 |
| `ldm.*-rf`（块） | 另加 `rdhc[11:6]`=偏移 rd；`immu6[5:0]`=元素/寄存器**个数** |
| `set.w-rf` | `rfha[23:18]`、`wpN[17:16]`=写权限、`immu16_hi/mid/lo`=16 位立即数 |
| `rd2rf` / `rf2rd` | `rfhb`+`rdhc`+`immu6` / `rdhb`+`rfhc`+`immu6` |
| 比较（`ftqcmp`/`ftscmp`/`foqcmp`/`foscmp`） | `rdhb[17:12]`=结果 rd（0/1） |
| `ftcls` / `focls` | `rdhb`、`rfhc`、`immu6` |

`immu6` 是**个数**（不是 `个数-1`）。`immu6 = 0` → 静态 ILLI（D17:S2 的独立谓词）。

## 状态子结构

- `input_state` / `expected_state` 各有 `rd` / `rb` / `ra` / `rf` / `memory` 五个 bank，
  缺省 `{}`（**不得**写成 `null`，C0）。
- rf 键形 `rf0`…`rf63`（C1，`rf64`/`rf1a` 非法）；值为 **16 位以内**的 64 位 hex 字符串
  （C2，`"3.0"` 非法）。
- **不得出现 `rd0` / `rb0`**（C4）：`rd0` 恒零、`rb0` 是 PC。
- `rf0` 是 FCSR 的**架构视图**，只能经 `fcsr` 表达：`state.rf.rf0` 出现即 C3
  （状态互斥）。
- `memory[]` 元素为 `{address, value, width}`；`address` 是 48 位有效地址
  （H1），`semantic` 类必须落在 RAM 窗口 `[0xffff_0000_0000, 0xffff_00ff_ffff]`；
  `width ∈ {1,2,4,8}` 且与助记符一致（H2，`.t`→4 / `.o`→8）。

### `fcsr` 子结构

| 字段 | 出现侧 | 说明 |
|------|--------|------|
| `rounding_mode` | 双侧 | `RNE`/`RTZ`/`RDN`/`RUP`（rf0[17:16]）。D5：给 `from_reset: true` 就**必须**是 `RNE` 且 flags 为空 |
| `flags` | 双侧 | `NV`/`DZ`/`OF`/`UF`/`NX` 的子集，**无重复**（D2）。D12：sticky OR，不自动清零 |
| `from_reset` | input | 布尔；声明「这是首条浮点指令执行前」 |
| `observed_mask` | **仅** expected | D3：`⊇` rw 域 `0x000000000003001F`、`∩` SBZ 域 `0x0007ffff003cffe0` = ∅、`⊆` RO∪rw |
| `value` | **仅** expected | D4：`(ro_value & ro_mask) \| (rounding << 16) \| flags`，`ro_value=0x7ff800007fc00000` |

**D6**：`input_state.fcsr` **不得**断言 `value` 或 `observed_mask`——输入 FCSR 的
**取值是未决项**（D17:S1：复位值未规定），只有**布局与可观测 mask**是 spec-determined
（合约 §6.4 第 3 条）。这与 `fcsr.value = RO 常量 + rw 字段 + SBZ=0` 并不矛盾：
后者是 *expected* 侧的合法表达。

## `facets`

11 个 facet 键（缺一即视为未声明，**不得**声明 `n/a` 项）：

| facet | 承载 decision | ADR |
|-------|---------------|-----|
| `encoding` / `format` / `operands` / `legality` / `semantics` | —（spec-determined） | — |
| `rf0_operand` | D11 | ADR-1009 |
| `fcsr_flags` | D12 | ADR-1010 |
| `tetra_high_half` | D13 | ADR-1011 |
| `compare_unordered` | D14 | ADR-1012 |
| `nan_propagation` | D15 | ADR-1013 |
| `tininess` | D16 | ADR-1014 |

每个 facet 是 `{status, cite[, rule][, open_ids]}`：

- `status ∈ {active, blocked}`（**只有**这两值；`n/a` 不是状态，是「不得声明」）。
- `cite` 非空且必须指名权威文件（F1）。
- `active` ⇒ **不得**带 `open_ids`、**不得**带 `rule`（E3）。
- `blocked` ⇒ **必须**带非空 `open_ids`（E4），取自
  `{D17:S1, D17:S3, D17:S4, D17:S5, D17:S6, D17:S8, D11…D16}`。
  `D17:S2`（trace-only）与 `D17:S7`（spec-determined non-gap）**永不**出现在任何
  阻塞位置（F4）。
- `rule` 只在 `blocked` 时出现，登记「激活后取值从哪来」（例如 D15 的
  `rule_tables.D15`），**不是**运行时期望值。

## `ledger_refs`（D17 OPEN-ID 台账）

| 列表 | 允许内容 | 语义 |
|------|----------|------|
| `active_keys` | `{D17:S1, D17:S3, D17:S4, D17:S5, D17:S6, D17:S8}` 的子集，且**必须**是本 identity 的 `d17_open_ids` 成员 | 该 case 被哪些未决项压住 |
| `trace_only` | 只能是 `["D17:S2"]` | ledger 外的来源追踪，**永不**计 PASS、**永不**阻塞 |
| `non_gap` | 只能是 `["D17:S7"]` | ADR-1008 D1 证明的 spec-determined non-gap |

**六个 active 键**是权威集合。有两处上游只读数据仍按 7 键叙述，validator 一律按
六键消费，并把差异登记出来（**不静默吞掉**）：

| 上游 | 现状 | 消费侧处置 |
|------|------|------------|
| `contract-f1-floating.md` §6.2 表格与正文 | 写「共 7 行」，含 `D17:S7` 状态 `BLOCKED` | 不改写（只读输入）；以 ADR-1008 D1 + `f1_gap_proofs.yaml` 的六键为准 |
| `contracts/opcodes.yaml` 的 `f1.d17_open_ids` | `rd2rf` / `rf2rd` 仍列 `D17:S7` | `d17_active_keys_for()` 按**钉死六键取交集**后返回；`d17_opcodes_divergences()` 逐条登记，`check_f1_context.py` 打印 `NOTE divergence` |

详见 `docs/testcases/f1-oracle-io.md` 的「只读分歧登记」。

各 active 键压住哪一面（`PIN_D17_FACET`）：

| OPEN-ID | 主题（不含取值） | 被阻塞 facet |
|---------|------------------|--------------|
| `D17:S1` | rf0/FCSR **复位值**未规定（布局/可观测 mask 不并入） | `fcsr_flags` |
| `D17:S3` | `ftcls`/`focls` 的 `immu6`≠1 合法性未规定 | `legality` |
| `D17:S4` | 多 fault 条件同时成立时的**优先级**未规定 | `legality` |
| `D17:S5` | `ftsclb`/`fosclb` 的 scaleB 指数「`rfhd` 取整数值」有两种读法 | `semantics` |
| `D17:S6` | 写 rf0 的 **SBZ 域**时的行为未规定（不指定忽略/保留/清零/异常） | `legality` |
| `D17:S8` | `ldm`/`stm` 的内存侧寻址、步长与重叠读写顺序未规定 | `semantics` |

## `blocked_points` / `unspecified`

`blocked_points` 是**案例级**未决点（未决实现输入 / 能力缺口），与 facet 级
`open_ids` 不是一回事。词表**只有两项**：

| 词 | 含义 |
|----|------|
| `D15:canonical_qnan_bits` | ADR-1013 未给 64 位 canonical qNaN 常量（`rule_tables.D15.canonical_qnan_bits = null`）。**不得**编造目的寄存器位型 |
| `CAP-01:root-log-correct-rounding` | root/log 的独立正确舍入算法是能力缺口。`resolution.capability_gaps` 里 `CAP-01 = BLOCKED` |

`unspecified` 是**规范明示「不做具体要求」**的点，词表**只有一项**
`rootn(-0,2)`，且只能挂在 `foroot` / `ftroot` 上。命中时（G3）：

- `expected_state` 的**所有** bank 必须为空/null（不是「部分可断言」）；
- `oracle.records` 必须为空；
- `expected_fault` 为空时必须用 `oracle.kind: open`。

## `oracle` 文法

`kind` 四选一：

| kind | 用途 | 附加要求 |
|------|------|----------|
| `order` | 常规顺序语义 | `records` 非空；`order ∈ {none, read-before-write}` |
| `block` | `ldm`/`stm` 块赋值 | `records` 非空；`order = block-increasing`；**必须**带 `elements` |
| `unordered` | 源/目的重叠的读写顺序未决 | `records` 非空；`order = read-before-write`；可带 `unordered_case: true` |
| `open` | **断言「不存在唯一期望值」** | `records: []`；**不得**有 `expected_state`/`expected_fault`；**不得**声明 `order`；**必须**给出理由（blocked facet 带 `open_ids`，或 `blocked_points`/`unspecified` 非空） |

`open` 是「无唯一期望」的**一等形状**：F1 的 blocked / explicitly-unspecified 点
**必须**用它，而不是硬编一个值——否则「本任务不知道」与「本任务忘了写」不可区分。

`records[]` 每项**恰含一个** `reg` / `mem` / `fcsr` / `pc` / `fault`（O3）：

| 体 | 子结构 | 约束 |
|----|--------|------|
| `reg` | `{bank, index, value}` **或** `{bank, index, low32, high32}` | 二者**恰一**（半观测 = D13 tetra 的 32 位拆分；缺 `high32` 即 O3）；`bank ∈ {rf,rd,rb,ra}`；`index ∈ 0..63` |
| `mem` | `{address, value, width}` | 三个键都必须给；address 48 位有效；与 `expected_state.memory` 交叉一致（O4） |
| `fcsr` | `{rounding_mode, flags, observed_mask, value}` | 必须与 `expected_state.fcsr` **逐字一致**（O4） |
| `pc` | 48 位 hex | 保留位 |
| `fault` | `{type, pc}` | **只**在 `expected_fault` 非空时出现，且**恰一条**、**必须是最后一条**（O2）；`pc` 必须在 RAM/ROM 窗口 |

`elements[]`（仅 `kind: block`）逐元素给 `{rf, width, address[, value]}`：

- `rf == rfha + i`（rf 递增，D17:S8/ADR-1015 D7）；
- `address == EA0 + i*width`，其中 `EA0 = rb[rbhb] + rd[rdhc]`，`width` = `.t`→4 / `.o`→8；
- 元素数 **== `immu6`**（`immu6` 是个数，不是 `个数-1`）。

faulting case **不得**记录 `reg`/`mem`/`fcsr` 效果：元素 fault 时**不提交**任何
写入，PC 停在出错的指令上（D17:S8 / ADR-1015 D8）。

## F1 校验项

`tools/testcases/validate_vectors.py`（M1 全量跑完之后）在
`tests/vectors/f1/{valid,invalid}/` 上跑 `f1_cases.validate_f1_case()`。
规则编号即 error 前缀：

| 组 | 编号 | 内容 |
|----|------|------|
| 身份 | `A1`…`A6` | identity ∈ 64 集 / identity==insn / insn+format 与 `opcodes.yaml` 一致 / class 枚举 / status==active / spec_cite 非空且引权威 |
| 编码 | `B1` `B2` | word 是 ≤32 位 hex / `(word&mask)==(value&mask)` |
| RF 状态 | `C0`…`C4` | bank 非 null / rf 键形 `rf0..rf63` / 值为 64 位 hex / rf0 只能经 fcsr / 禁 rd0、rb0 |
| FCSR | `D0`…`D6` | fcsr 是 mapping / rounding_mode 枚举 / flags 子集无重复 / observed_mask 三条集合关系 / value 独立重算 / from_reset⇒RNE+空 flags / **input 侧禁断言 value 与 observed_mask** |
| 互斥 | `E1`…`E4` | fault ⟺ state 二选一 / fault 时 pc 为 null / active facet 禁 open_ids 与 rule / blocked facet 必须有 open_ids |
| facet 与台账 | `F0`…`F5` | 11 键白名单、禁声明 n/a 项、cite 指名权威（`F1`）、**ADR 门禁**（`F2`）、active_keys ⊆ identity 的 d17_open_ids（`F3`）、S2/S7 永不进阻塞位（`F4`）、trace_only/non_gap 只含 S2/S7（`F5`） |
| 阻塞/未决 | `G1`…`G3` | blocked_points 词表 / unspecified 词表与 identity 归属 / unspecified 不得有唯一期望 |
| 内存/块 | `H0`…`H5` | memory 是 list / address 48 位有效 / width 合法且与助记符一致 / **D17:S4 优先级：ILLI 先于 MALIGN**（前缀 `H3` 或 `H3/H4`）/ 块 EA0+i·width、rf 递增、元素数==immu6（H4）/ **编码里 role=src 的 rf 必须在 input 预置**（H5） |
| 已激活 ADR 规则 | `I1`…`I8` | D11 rf0 目的白名单（I1）/ D13 tetra 高 32 位 == `0xffffffff`（I2）/ D14 unordered 位型（I3）/ D12 自动 vs 非自动置位（I4）/ D16 `UF⇒NX`、`OF⇒NX` 且非 D16 identity 禁置 OF/UF（I5）/ D17:S3 classify `immu6≠1`⇒ILLI（I6）/ **合法编码却期望 ILLI 必被拒**（I7，双向静态重算）/ **semantics blocked 却断言目的寄存器必被拒**（I8，编造门） |
| oracle | `O1`…`O4` | kind 枚举与无未知键 / `open` 的四条硬约束 / faulting case 的记录形状与顺序 / records 与 `expected_state` 交叉一致 |
| 树级 | `TREE` / `DUPLICATE case id` | `valid/` 内 id 唯一；`D17:S2` 必须**可追踪**（至少一条 case 的 `trace_only` 引用它） |

### ADR 激活门禁

```
python3 tools/testcases/validate_vectors.py                 # --adr-gate auto（默认）
python3 tools/testcases/validate_vectors.py --adr-gate closed
python3 tools/testcases/validate_vectors.py --adr-gate open
```

`F1Context` 从 Accepted 的 ADR-1008…1015 重算 `gate_open`：

- `auto`：ADR-1008 必须 Accepted（它是 non-gap 前提）；ADR-1009…1015 全部 Accepted
  ⇒ `gate_open = true`；否则 `gate_open = false`。
- `closed`：强制 `gate_open = false`（用于证明门禁真的会红）。
- `open`：强制 `gate_open = true`。

`gate_open = false` 时，受 `D11`…`D16` 或 `D17:*` 压住的 facet **不得**声明
`active`（`F2`）。默认运行把 `valid/` 当正样例、`invalid/` 当 must-FAIL 反样例，
**两侧都跑**。

## F1 期望值来源与 oracle 接口

- 期望值只能来自 `tools/testcases/f1_oracle_values.py`（**纯整数**手算的 32/64 位
  位型常量 + FCSR 域常量）与合约常量；**不得**从 `tests/vectors/f1/` 反读（那会
  变成自证，检查项 B4）。
- 独立的第二路重算在 `tools/testcases/verify_f1_expected_values.py`：它自带一套
  **纯整数 IEEE-754-2008** 引擎（含 41 条手写 KAT 自证），不 import 任何项目 oracle
  模块、不用宿主浮点，用来逐条复算本 schema 断言的每一个位型/flag/块地址/静态 fault
  谓词。
- 接口细节（4 种 `oracle.kind`、逐组的 record 形状、BLOCKED 清单、只读分歧登记）
  见 `docs/testcases/f1-oracle-io.md`。

## F1 校验输出

```
validate_vectors: 178/178 M1 identities covered OK (inventory sync OK; 15 data files, 747 cases; data coverage gaps: 0)
validate_vectors: F1 19/19 vectors OK (19 valid case(s) green; 53 invalid counterexample(s) all rejected; 13 identity/identities; facets 146 active / 6 blocked; fcsr asserts 11; D13 half-observations 7; ADR gate auto)
```

第一行是 M1 的既有输出，**逐字不变**（747 条向量向后兼容）；F1 一行只在其后追加。
