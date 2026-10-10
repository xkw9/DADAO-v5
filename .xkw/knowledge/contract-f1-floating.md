# F1 浮点合约（RF / SimRISC-03）

> **生成说明**：本文件由 `tools/spec/f1_render_contract.py` 渲染（幂等）。
> 手写散文段可直接编辑；`<!-- f1:generated:NAME -->` … `<!-- /f1:generated:NAME -->`
> 之间的内容是**机器生成**的，每次渲染整体重写，**不要手改**。
> 编码数据来自 `tools/spec/f1_spec_extract.py`（独立解析 `spec/`），
> facet / 合法性 / 引用 / 静默项来自 `tools/spec/f1_contract_data.py`；
> 两者都不从实现或现有 YAML 反推。
>
> **反向校验**：`python3 tools/spec/check_f1_contract.py` 校验本文件、
> `contracts/opcodes.yaml` 的 `f1:` 块与 `spec/` 三方一致。

## 0. 权威与版本

- **版本**：SimRISC **0.5.3**（根 `README.md`；`spec/SimRISC-00-指令系统设计.md`、
  `spec/SimRISC-03-浮点类指令.md` 头部版本一致）。
- **编码权威**：`spec/SimRISC-00-指令系统设计.md` §指令域说明 / §标识位说明 /
  §SimRISC QFC（`spec/SimRISC-00-指令系统设计.md:241`）/ §MISC-RF 指令编码
  （`spec/SimRISC-00-指令系统设计.md:343`）。
- **语义权威**：`spec/SimRISC-03-浮点类指令.md` 全部 9 个小节。
- **寄存器 / FCSR 权威**：`spec/SimRISC-00-指令系统设计.md` §浮点寄存器
  （`:66`）/ §浮点状态寄存器（`:76`）。
- **rd0 只读权威**：`spec/SimRISC-00-指令系统设计.md:55`（"其余指令目的为 rd0 时
  触发 ILLI 异常"）。SimRISC-01 不在本阶段的权威集内，故 rd0 规则引 SimRISC-00。
- **阶段边界**：`adr-1004-f1-floating-phase.md`（Accepted）。D11–D17 保持
  **OPEN/BLOCKED**，本合约不为其提供取值。
- **禁止**：从 `tools/spec/generate_opcodes.py`、既有 YAML、LLVM/QEMU 实现或
  `.tao/` 反推语义。`.tao/` 只读，且不是 F1 的权威来源。

## 1. 身份空间：64 = 18 + 46

「identity」指 `contracts/opcodes.yaml` 的 `insn` 键，即 **唯一编码槽位**，
而不是裸助记符。裸助记符在本 ISA 中**不唯一**（`ld.t` / `st.o` / `set.w` / `cs.*`
在 RD/RB/RA/RF 多个 bank 都有同名单助记符），因此本合约一律用 `insn` 消歧：

| 助记符 | 不同 bank 的 identity |
| --- | --- |
| `ld.t` | `ld.t-rd`（M1）、`ld.t-rf`（F1） |
| `st.o` | `st.o-rd`、`st.o-rb`、`st.o-ra`（M1）、`st.o-rf`（F1） |
| `set.w` | `set.w-rf`（F1） |
| `cs.eq` | `cs.eq-rf`（F1） |
| `rd2rf` / `rf2rd` | 无 bank 冲突（RF↔RD 方向唯一） |

`f1_spec_extract.canonical_identity()` 给出规则：**有 bank 后缀时取
`mnemonic-bank`，否则取 `mnemonic`**（`rd2rf`、`ftadd` 等即为裸名）。

<!-- f1:generated:identity-table -->
| identity (`insn`) | mnemonic | format | group | op | ha (minor) | mask | value | SimRISC-03 小节 | 操作数（归一化） |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `cs.eq-rf` | `cs.eq` | `rrrr` | rf-qfc | `0x5E` | — | `0xFF000000` | `0x5E000000` | `浮点条件赋值指令` | `rdha, rdhb, rfhc, rfhd` |
| `cs.n-rf` | `cs.n` | `rrrr` | rf-qfc | `0x61` | — | `0xFF000000` | `0x61000000` | `浮点条件赋值指令` | `rdha, rfhb, rfhc, rfhd` |
| `cs.ne-rf` | `cs.ne` | `rrrr` | rf-qfc | `0x5F` | — | `0xFF000000` | `0x5F000000` | `浮点条件赋值指令` | `rdha, rdhb, rfhc, rfhd` |
| `cs.p-rf` | `cs.p` | `rrrr` | rf-qfc | `0x65` | — | `0xFF000000` | `0x65000000` | `浮点条件赋值指令` | `rdha, rfhb, rfhc, rfhd` |
| `cs.z-rf` | `cs.z` | `rrrr` | rf-qfc | `0x63` | — | `0xFF000000` | `0x63000000` | `浮点条件赋值指令` | `rdha, rfhb, rfhc, rfhd` |
| `fo2fo` | `fo2fo` | `orri` | misc-rf | `0x44` | `0xA` | `0xFFFC0000` | `0x44280000` | `格式转换指令` | `ha, rfhb, rfhc, immu6` |
| `fo2ft` | `fo2ft` | `orri` | misc-rf | `0x44` | `0x9` | `0xFFFC0000` | `0x44240000` | `格式转换指令` | `ha, rfhb, rfhc, immu6` |
| `fo2io` | `fo2io` | `orri` | misc-rf | `0x44` | `0x39` | `0xFFFC0000` | `0x44E40000` | `格式转换指令` | `ha, rdhb, rfhc, immu6` |
| `fo2it` | `fo2it` | `orri` | misc-rf | `0x44` | `0x38` | `0xFFFC0000` | `0x44E00000` | `格式转换指令` | `ha, rdhb, rfhc, immu6` |
| `fo2uo` | `fo2uo` | `orri` | misc-rf | `0x44` | `0x3B` | `0xFFFC0000` | `0x44EC0000` | `格式转换指令` | `ha, rdhb, rfhc, immu6` |
| `fo2ut` | `fo2ut` | `orri` | misc-rf | `0x44` | `0x3A` | `0xFFFC0000` | `0x44E80000` | `格式转换指令` | `ha, rdhb, rfhc, immu6` |
| `foadd` | `foadd` | `orrr` | misc-rf | `0x44` | `0x18` | `0xFFFC0000` | `0x44600000` | `S2D1` | `ha, rfhb, rfhc, rfhd` |
| `focls` | `focls` | `orri` | misc-rf | `0x44` | `0x8` | `0xFFFC0000` | `0x44200000` | `浮点分类指令` | `ha, rdhb, rfhc, immu6` |
| `fodiv` | `fodiv` | `orrr` | misc-rf | `0x44` | `0x1B` | `0xFFFC0000` | `0x446C0000` | `S2D1` | `ha, rfhb, rfhc, rfhd` |
| `folog` | `folog` | `orri` | misc-rf | `0x44` | `0xF` | `0xFFFC0000` | `0x443C0000` | `S1D1` | `ha, rfhb, rfhc, immu6` |
| `fomadd` | `fomadd` | `rrrr` | rf-qfc | `0x57` | — | `0xFF000000` | `0x57000000` | `S3D1` | `rfha, rfhb, rfhc, rfhd` |
| `fomul` | `fomul` | `orrr` | misc-rf | `0x44` | `0x1A` | `0xFFFC0000` | `0x44680000` | `S2D1` | `ha, rfhb, rfhc, rfhd` |
| `foqcmp` | `foqcmp` | `orrr` | misc-rf | `0x44` | `0x28` | `0xFFFC0000` | `0x44A00000` | `浮点比较指令` | `ha, rdhb, rfhc, rfhd` |
| `forem` | `forem` | `orrr` | misc-rf | `0x44` | `0x1C` | `0xFFFC0000` | `0x44700000` | `S2D1` | `ha, rfhb, rfhc, rfhd` |
| `foroot` | `foroot` | `orri` | misc-rf | `0x44` | `0xE` | `0xFFFC0000` | `0x44380000` | `S1D1` | `ha, rfhb, rfhc, immu6` |
| `fosclb` | `fosclb` | `orrr` | misc-rf | `0x44` | `0x1D` | `0xFFFC0000` | `0x44740000` | `S2D1` | `ha, rfhb, rfhc, rfhd` |
| `foscmp` | `foscmp` | `orrr` | misc-rf | `0x44` | `0x29` | `0xFFFC0000` | `0x44A40000` | `浮点比较指令` | `ha, rdhb, rfhc, rfhd` |
| `fosgnj` | `fosgnj` | `orrr` | misc-rf | `0x44` | `0x1F` | `0xFFFC0000` | `0x447C0000` | `浮点符号位操作指令` | `ha, rfhb, rfhc, rfhd` |
| `fosgnn` | `fosgnn` | `orrr` | misc-rf | `0x44` | `0x1E` | `0xFFFC0000` | `0x44780000` | `浮点符号位操作指令` | `ha, rfhb, rfhc, rfhd` |
| `fosub` | `fosub` | `orrr` | misc-rf | `0x44` | `0x19` | `0xFFFC0000` | `0x44640000` | `S2D1` | `ha, rfhb, rfhc, rfhd` |
| `ft2fo` | `ft2fo` | `orri` | misc-rf | `0x44` | `0x1` | `0xFFFC0000` | `0x44040000` | `格式转换指令` | `ha, rfhb, rfhc, immu6` |
| `ft2ft` | `ft2ft` | `orri` | misc-rf | `0x44` | `0x2` | `0xFFFC0000` | `0x44080000` | `格式转换指令` | `ha, rfhb, rfhc, immu6` |
| `ft2io` | `ft2io` | `orri` | misc-rf | `0x44` | `0x31` | `0xFFFC0000` | `0x44C40000` | `格式转换指令` | `ha, rdhb, rfhc, immu6` |
| `ft2it` | `ft2it` | `orri` | misc-rf | `0x44` | `0x30` | `0xFFFC0000` | `0x44C00000` | `格式转换指令` | `ha, rdhb, rfhc, immu6` |
| `ft2uo` | `ft2uo` | `orri` | misc-rf | `0x44` | `0x33` | `0xFFFC0000` | `0x44CC0000` | `格式转换指令` | `ha, rdhb, rfhc, immu6` |
| `ft2ut` | `ft2ut` | `orri` | misc-rf | `0x44` | `0x32` | `0xFFFC0000` | `0x44C80000` | `格式转换指令` | `ha, rdhb, rfhc, immu6` |
| `ftadd` | `ftadd` | `orrr` | misc-rf | `0x44` | `0x10` | `0xFFFC0000` | `0x44400000` | `S2D1` | `ha, rfhb, rfhc, rfhd` |
| `ftcls` | `ftcls` | `orri` | misc-rf | `0x44` | `0x0` | `0xFFFC0000` | `0x44000000` | `浮点分类指令` | `ha, rdhb, rfhc, immu6` |
| `ftdiv` | `ftdiv` | `orrr` | misc-rf | `0x44` | `0x13` | `0xFFFC0000` | `0x444C0000` | `S2D1` | `ha, rfhb, rfhc, rfhd` |
| `ftlog` | `ftlog` | `orri` | misc-rf | `0x44` | `0x7` | `0xFFFC0000` | `0x441C0000` | `S1D1` | `ha, rfhb, rfhc, immu6` |
| `ftmadd` | `ftmadd` | `rrrr` | rf-qfc | `0x56` | — | `0xFF000000` | `0x56000000` | `S3D1` | `rfha, rfhb, rfhc, rfhd` |
| `ftmul` | `ftmul` | `orrr` | misc-rf | `0x44` | `0x12` | `0xFFFC0000` | `0x44480000` | `S2D1` | `ha, rfhb, rfhc, rfhd` |
| `ftqcmp` | `ftqcmp` | `orrr` | misc-rf | `0x44` | `0x20` | `0xFFFC0000` | `0x44800000` | `浮点比较指令` | `ha, rdhb, rfhc, rfhd` |
| `ftrem` | `ftrem` | `orrr` | misc-rf | `0x44` | `0x14` | `0xFFFC0000` | `0x44500000` | `S2D1` | `ha, rfhb, rfhc, rfhd` |
| `ftroot` | `ftroot` | `orri` | misc-rf | `0x44` | `0x6` | `0xFFFC0000` | `0x44180000` | `S1D1` | `ha, rfhb, rfhc, immu6` |
| `ftsclb` | `ftsclb` | `orrr` | misc-rf | `0x44` | `0x15` | `0xFFFC0000` | `0x44540000` | `S2D1` | `ha, rfhb, rfhc, rfhd` |
| `ftscmp` | `ftscmp` | `orrr` | misc-rf | `0x44` | `0x21` | `0xFFFC0000` | `0x44840000` | `浮点比较指令` | `ha, rdhb, rfhc, rfhd` |
| `ftsgnj` | `ftsgnj` | `orrr` | misc-rf | `0x44` | `0x17` | `0xFFFC0000` | `0x445C0000` | `浮点符号位操作指令` | `ha, rfhb, rfhc, rfhd` |
| `ftsgnn` | `ftsgnn` | `orrr` | misc-rf | `0x44` | `0x16` | `0xFFFC0000` | `0x44580000` | `浮点符号位操作指令` | `ha, rfhb, rfhc, rfhd` |
| `ftsub` | `ftsub` | `orrr` | misc-rf | `0x44` | `0x11` | `0xFFFC0000` | `0x44440000` | `S2D1` | `ha, rfhb, rfhc, rfhd` |
| `io2fo` | `io2fo` | `orri` | misc-rf | `0x44` | `0x3D` | `0xFFFC0000` | `0x44F40000` | `格式转换指令` | `ha, rfhb, rdhc, immu6` |
| `io2ft` | `io2ft` | `orri` | misc-rf | `0x44` | `0x35` | `0xFFFC0000` | `0x44D40000` | `格式转换指令` | `ha, rfhb, rdhc, immu6` |
| `it2fo` | `it2fo` | `orri` | misc-rf | `0x44` | `0x3C` | `0xFFFC0000` | `0x44F00000` | `格式转换指令` | `ha, rfhb, rdhc, immu6` |
| `it2ft` | `it2ft` | `orri` | misc-rf | `0x44` | `0x34` | `0xFFFC0000` | `0x44D00000` | `格式转换指令` | `ha, rfhb, rdhc, immu6` |
| `ld.o-rf` | `ld.o` | `rrii` | rf-qfc | `0x26` | — | `0xFF000000` | `0x26000000` | `存取RF寄存器` | `rfha, rbhb, imms12_hi, imms12_lo` |
| `ld.t-rf` | `ld.t` | `rrii` | rf-qfc | `0x16` | — | `0xFF000000` | `0x16000000` | `存取RF寄存器` | `rfha, rbhb, imms12_hi, imms12_lo` |
| `ldm.o-rf` | `ldm.o` | `rrri` | rf-qfc | `0x3E` | — | `0xFF000000` | `0x3E000000` | `存取RF寄存器` | `rfha, rbhb, rdhc, immu6` |
| `ldm.t-rf` | `ldm.t` | `rrri` | rf-qfc | `0x2E` | — | `0xFF000000` | `0x2E000000` | `存取RF寄存器` | `rfha, rbhb, rdhc, immu6` |
| `rd2rf` | `rd2rf` | `orri` | rf-qfc | `0x40` | `0x3D` | `0xFFFC0000` | `0x40F40000` | `寄存器组之间块赋值` | `ha, rfhb, rdhc, immu6` |
| `rf2rd` | `rf2rd` | `orri` | rf-qfc | `0x40` | `0x3E` | `0xFFFC0000` | `0x40F80000` | `寄存器组之间块赋值` | `ha, rdhb, rfhc, immu6` |
| `set.w-rf` | `set.w` | `rwii` | rf-qfc | `0x4F` | — | `0xFF000000` | `0x4F000000` | `立即数常数赋值：Immediate constant` | `rfha, wpN, immu16_hi, immu16_mid, immu16_lo` |
| `st.o-rf` | `st.o` | `rrii` | rf-qfc | `0x27` | — | `0xFF000000` | `0x27000000` | `存取RF寄存器` | `rfha, rbhb, imms12_hi, imms12_lo` |
| `st.t-rf` | `st.t` | `rrii` | rf-qfc | `0x17` | — | `0xFF000000` | `0x17000000` | `存取RF寄存器` | `rfha, rbhb, imms12_hi, imms12_lo` |
| `stm.o-rf` | `stm.o` | `rrri` | rf-qfc | `0x3F` | — | `0xFF000000` | `0x3F000000` | `存取RF寄存器` | `rfha, rbhb, rdhc, immu6` |
| `stm.t-rf` | `stm.t` | `rrri` | rf-qfc | `0x2F` | — | `0xFF000000` | `0x2F000000` | `存取RF寄存器` | `rfha, rbhb, rdhc, immu6` |
| `uo2fo` | `uo2fo` | `orri` | misc-rf | `0x44` | `0x3F` | `0xFFFC0000` | `0x44FC0000` | `格式转换指令` | `ha, rfhb, rdhc, immu6` |
| `uo2ft` | `uo2ft` | `orri` | misc-rf | `0x44` | `0x37` | `0xFFFC0000` | `0x44DC0000` | `格式转换指令` | `ha, rfhb, rdhc, immu6` |
| `ut2fo` | `ut2fo` | `orri` | misc-rf | `0x44` | `0x3E` | `0xFFFC0000` | `0x44F80000` | `格式转换指令` | `ha, rfhb, rdhc, immu6` |
| `ut2ft` | `ut2ft` | `orri` | misc-rf | `0x44` | `0x36` | `0xFFFC0000` | `0x44D80000` | `格式转换指令` | `ha, rfhb, rdhc, immu6` |

合计 **64 = 18（QFC/相关 rf-qfc）+ 46（MISC-RF）**。

`set.ft` / `set.fo` 是**伪指令**（`spec/SimRISC-03-浮点类指令.md:62`），出现在 64 条 identity 中的计数为 **0**；它们不进入本表，也不分配编码。
<!-- /f1:generated:identity-table -->

**编码说明**（供后续模块按需引用，均为规范字面）：

- QFC 主表条目（rf-qfc 中的 16 条）：`mask = 0xFF000000`，`value = op << 24`。
- MISC-RF 子表条目（46 条）：`op = 0x44`（子表指针），经 §标识位说明展开为
  `mask = 0xFFFC0000`，`value = (0x44 << 24) | (ha << 18)`，`ha` 为 minor-opcode。
- `rd2rf`（`0x40 / ha=0x3D`）与 `rf2rd`（`0x40 / ha=0x3E`）在 QFC 主表的
  MISC-octa 子表行中，取 minor-opcode 掩码。

## 2. rf0 / FCSR

`rf0` 是浮点状态寄存器（FCSR），64 位，布局如下（`spec/SimRISC-00-指令系统设计.md:78-86`，
由 `f1_spec_extract.parse_fcsr_layout()` 独立解析）：

<!-- f1:generated:fcsr-layout -->
| 位域 | 规范描述 | F1 处置 |
| --- | --- | --- |
| `[63..51]` | 0111 1111 1111 1（只读，写无效；其值为fo格式下的Quiet NaN，即符号位为0，E为全1，尾数最高位为1） | **只读**，写静默忽略（SimRISC-03:7） |
| `[50..32]` | SBZ（Should Be Zero） | SBZ，写入行为**未规定** → 静默项 **S6** |
| `[31..22]` | 0111 1111 11（只读，写无效；其值为ft格式下的Quiet NaN，即符号位为0，E为全1，尾数最高位为1） | **只读**，写静默忽略（SimRISC-03:7） |
| `[21..18]` | SBZ（Should Be Zero） | SBZ，写入行为**未规定** → 静默项 **S6** |
| `[17..16]` | 舍入模式（Rounding Mode） | 舍入模式，见 §2，4 种模式 |
| `[15..5]` | SBZ（Should Be Zero） | SBZ，写入行为**未规定** → 静默项 **S6** |
| `[4..0]` | 异常状态（Accured exception） | 异常状态，见 §6 `fcsr_flags`（**D12 OPEN**） |

舍入模式（`rf0[17:16]`，`spec/SimRISC-00-指令系统设计.md:90-95`）：

| 编码 | 助记符 | 含义 |
| --- | --- | --- |
| `00` | `RNE` | Round to Nearest, ties to Even |
| `01` | `RTZ` | Round towards Zero |
| `10` | `RDN` | Round Down (towards -inf) |
| `11` | `RUP` | Round Up (towards +inf) |

异常状态位（`rf0[4..0]`，`spec/SimRISC-00-指令系统设计.md:99-105`）：

| Bit | 助记符 | 含义 |
| --- | --- | --- |
| `0` | `NV` | Invalid Operation |
| `1` | `DZ` | Divide by Zero |
| `2` | `OF` | Overflow |
| `3` | `UF` | Underflow |
| `4` | `NX` | Inexact |

> `NV`/`DZ`/`OF`/`UF`/`NX` 的**置位语义**（sticky OR vs 整体写入）、**清除路径**、以及 **tininess** 检测时点，规范均未规定 → `fcsr_flags` / `tininess` facet 为 **OPEN/BLOCKED**（D12 / D16）。本合约**不**提供取值。
<!-- /f1:generated:fcsr-layout -->

### 2.1 `set.w` 的 wyde-position 映射（**规范唯一确定**）

`set.w rfha, wpN, immu16` **只设置 16 位，其余 48 位不变**
（`spec/SimRISC-03-浮点类指令.md:59`）。哪 16 位由 `wpN` 决定：

<!-- f1:generated:setw-wp -->
| wyde-position | 命中的 rf 位段 | 说明 |
| --- | --- | --- |
| `wp0` | `[15:0]` | immu16_lo 所在的 16 位段 |
| `wp1` | `[31:16]` | immu16 段；**rf0 的舍入模式 rf0[17:16] 在此段** |
| `wp2` | `[47:32]` | immu16 段 |
| `wp3` | `[63:48]` | immu16 段 |

> 编码侧：`wpN` 在 `hb[5:4]`，`00=wp0, 01=wp1, 10=wp2, 11=wp3`（`spec/SimRISC-00-指令系统设计.md:199`）；`immu16` 拆成 `hb[3:0]` + `hc[5:0]` + `hd[5:0]`。
<!-- /f1:generated:setw-wp -->

**该映射是规范唯一确定的，不是缺口**，推导只靠规范自带的两个伪指令示例：

- `spec/SimRISC-03-浮点类指令.md:73-77`：`set.fo rf1, 0x3FF0000000000000` 展开为
  `set.w rf1, wp3, 0x3FF0` + wp2/wp1/wp0 各 `0x0000`。`0x3FF0` 是常量的**高** 16 位
  ⇒ `wp3` ↔ `[63:48]`。
- `spec/SimRISC-03-浮点类指令.md:68-70`：`set.ft rf1, 0x3F800000` 展开为
  `set.w rf1, wp1, 0x3F80` + `set.w rf1, wp0, 0x0000`。`0x3F80` 是常量的**高** 16 位
  ⇒ `wp1` ↔ `[31:16]`、`wp0` ↔ `[15:0]`；余下 `wp2` ↔ `[47:32]`。

自洽性交叉验证：`spec/SimRISC-00-指令系统设计.md:88`「舍入模式的设置单独放在 `wp1`
中」——舍入模式是 `rf0[17:16]`，落在 `wp1` 的 `[31:16]` 段内 ✓。

因此单精（tetra）需 **2 条** `set.w`、双精（octa）需 **4 条** `set.w`
（`spec/SimRISC-03-浮点类指令.md:60`），与上表一致。

**只读 / 可写**（`spec/SimRISC-03-浮点类指令.md:7`）："rf0 = FCSR。rf ld/st 中 rf0
为目的时允许，**写只读位时静默忽略，rw 位正常写入**。"

- 只读域 = `[63..51]` + `[31..22]`（两个只读 NaN 位型）。
- rw 域 = `[50..32]`（SBZ）、`[21..18]`（SBZ）、`[17..16]`（舍入模式）、
  `[15..5]`（SBZ）、`[4..0]`（异常状态）。
- **SBZ 被写入时的行为规范未写**（静默项 S6 = 台账 `D17:S6`，`BLOCKED`）。既有
  `contracts/legality_rules.yaml` 的 `sbz_nonzero` 规则把 SBZ 非零冻结为 ILLI
  （ADR-0004 D5.3，**架构自定义**，**非** F1 结论）；F1 是否沿用**未决**。
  「忽略 / 保留 / 清零 / 触发异常」四者**一个都不许**被本合约选定。
  本合约**不**用 fault 规则编码该缺口。
- **rf0 的复位值规范未给**（静默项 S1 = 台账 `D17:S1`，`BLOCKED`）。同类寄存器
  `rb0`、`ra0` 都给了初值，rf0 没有。上表的**字段布局与可观测 mask**是
  spec-determined、现在可核对；**复位值不可推出**，且**不得**由「布局已知」推出
  「复位已知」。本合约**不发明初值**。
- 舍入模式由 `wp1` 设置（`spec/SimRISC-00-指令系统设计.md:88`"舍入模式的设置单独放在
  wp1 中，程序可以直接用 setw 指令进行设置"），共 4 种：`RNE`/`RTZ`/`RDN`/`RUP`。
- 浮点指令**不触发异常**，始终按 IEEE 754 返回结果（NaN/Inf 等），
  只写 `rf0[4:0]`（`spec/SimRISC-00-指令系统设计.md:107`）。

## 3. 合法性、fault 与异常优先级

本节**只**登记规范明说的限制。规范未说的限制**不**新增 fault 规则
（见 §7 静默项）。

<!-- f1:generated:legality -->
### 3.1 谓词词表（只含规范**明说**的限制）

| 谓词 | `legality_rules.yaml` 规则 id | 规范依据 |
| --- | --- | --- |
| `aligned(4)` | `fp_malign_rf` | `ld.t`/`st.t`/`ldm.t`/`stm.t` 需 4 字节对齐（SimRISC-03:25） |
| `aligned(8)` | `fp_malign_rf` | `ld.o`/`st.o`/`ldm.o`/`stm.o` 需 8 字节对齐（SimRISC-03:25） |
| `immu6_zero_illi` | `fp_block_immu6_zero` | `immu6` = 0 触发 ILLI（SimRISC-03:29/48/132） |
| `immu6_1_63` | `fp_block_immu6_zero` | 「有效范围为 1~63」（SimRISC-03:44 块赋值、:126 格式转换）；immu6=0 另有独立 ILLI 规则，1~63 是**范围声明**而非独立 fault 条件 |
| `block_range_overflow_illi` | `fp_block_range_overflow` | 任一起始寄存器 + immu6 > 64 触发 ILLI（SimRISC-03:30/49/133） |
| `rf_slot_overflow_illi` | `fp_rf_slot_overflow` | `rfha + immu6 > 64`（超出 rf63）触发 ILLI（SimRISC-03:31） |
| `rd_dest_not_rd0` | `rd_dest_rd0` | 目的 `rd` 字段为 rd0 触发 ILLI（SimRISC-00:55，rd0 固定为 0 只读） |
| `rootn_n_in_2_3` | `fp_root_invalid_n` | n 只支持 2/3，其它值触发 ILLI（SimRISC-03:188） |
| `log_base_in_0_1_2` | `fp_log_invalid_base` | 底只支持 2/e/10（immu6 = 2/1/0），其它值触发 ILLI（SimRISC-03:192） |
| `rf0_dst_allowed` | —（非 fault） | rf0 为目的在 rf ld/st 中**允许**（SimRISC-03:7）；这是写掩码规则，不是 fault，故 `legality_refs` 为空 |
| `immu6_1_for_cls` | —（非 fault） | `ftcls`/`focls` 的 immu6 签名固定为 `1`（SimRISC-03:270-271）；取其它值的行为规范未规定 → 静默项 S3 = 台账 `D17:S3`，`BLOCKED`（未决，本合约不指定行为），故 `legality_refs` 为空 |

> **只用 `ld`/`st` 风格 fault 规则去编码 spec 静默项是错的**：
> rf0 的 SBZ 域被写入时的行为（静默项 S6 = 台账 `D17:S6`，`BLOCKED`）**不是**合法性规则，既没有 fault 类型也没有 `spec_cite`，因此**未**新增规则，只在 §6.2 台账与 §7 登记。

### 3.2 逐 identity 的 fault 集合（**不排序**）

> 规范未规定「多个 fault 条件同时成立」时的优先级（静默项 S4 = 台账 `D17:S4`，`BLOCKED`）。下表按**集合**列出本 identity **可以**触发的 fault，**不表达先后**。该表**不**是优先级表：排序规则未决前，**任何** identity 的 fault 先后都**未决**。

| identity | 可触发 fault 集合（无序） | spec 明示谓词 | legality facet |
| --- | --- | --- | --- |
| `cs.eq-rf` | （无 fault 条件） | — | spec-determined |
| `cs.n-rf` | （无 fault 条件） | — | spec-determined |
| `cs.ne-rf` | （无 fault 条件） | — | spec-determined |
| `cs.p-rf` | （无 fault 条件） | — | spec-determined |
| `cs.z-rf` | （无 fault 条件） | — | spec-determined |
| `fo2fo` | ILLI | `immu6_zero_illi`, `block_range_overflow_illi`, `immu6_1_63` | spec-determined |
| `fo2ft` | ILLI | `immu6_zero_illi`, `block_range_overflow_illi`, `immu6_1_63` | spec-determined |
| `fo2io` | ILLI | `immu6_zero_illi`, `block_range_overflow_illi`, `immu6_1_63`, `rd_dest_not_rd0` | spec-determined |
| `fo2it` | ILLI | `immu6_zero_illi`, `block_range_overflow_illi`, `immu6_1_63`, `rd_dest_not_rd0` | spec-determined |
| `fo2uo` | ILLI | `immu6_zero_illi`, `block_range_overflow_illi`, `immu6_1_63`, `rd_dest_not_rd0` | spec-determined |
| `fo2ut` | ILLI | `immu6_zero_illi`, `block_range_overflow_illi`, `immu6_1_63`, `rd_dest_not_rd0` | spec-determined |
| `foadd` | （无 fault 条件） | — | spec-determined |
| `focls` | ILLI | `immu6_1_for_cls`, `rd_dest_not_rd0` | partial |
| `fodiv` | （无 fault 条件） | — | spec-determined |
| `folog` | ILLI | `log_base_in_0_1_2` | spec-determined |
| `fomadd` | （无 fault 条件） | — | spec-determined |
| `fomul` | （无 fault 条件） | — | spec-determined |
| `foqcmp` | ILLI | `rd_dest_not_rd0` | spec-determined |
| `forem` | （无 fault 条件） | — | spec-determined |
| `foroot` | ILLI | `rootn_n_in_2_3` | spec-determined |
| `fosclb` | （无 fault 条件） | — | spec-determined |
| `foscmp` | ILLI | `rd_dest_not_rd0` | spec-determined |
| `fosgnj` | （无 fault 条件） | — | spec-determined |
| `fosgnn` | （无 fault 条件） | — | spec-determined |
| `fosub` | （无 fault 条件） | — | spec-determined |
| `ft2fo` | ILLI | `immu6_zero_illi`, `block_range_overflow_illi`, `immu6_1_63` | spec-determined |
| `ft2ft` | ILLI | `immu6_zero_illi`, `block_range_overflow_illi`, `immu6_1_63` | spec-determined |
| `ft2io` | ILLI | `immu6_zero_illi`, `block_range_overflow_illi`, `immu6_1_63`, `rd_dest_not_rd0` | spec-determined |
| `ft2it` | ILLI | `immu6_zero_illi`, `block_range_overflow_illi`, `immu6_1_63`, `rd_dest_not_rd0` | spec-determined |
| `ft2uo` | ILLI | `immu6_zero_illi`, `block_range_overflow_illi`, `immu6_1_63`, `rd_dest_not_rd0` | spec-determined |
| `ft2ut` | ILLI | `immu6_zero_illi`, `block_range_overflow_illi`, `immu6_1_63`, `rd_dest_not_rd0` | spec-determined |
| `ftadd` | （无 fault 条件） | — | spec-determined |
| `ftcls` | ILLI | `immu6_1_for_cls`, `rd_dest_not_rd0` | partial |
| `ftdiv` | （无 fault 条件） | — | spec-determined |
| `ftlog` | ILLI | `log_base_in_0_1_2` | spec-determined |
| `ftmadd` | （无 fault 条件） | — | spec-determined |
| `ftmul` | （无 fault 条件） | — | spec-determined |
| `ftqcmp` | ILLI | `rd_dest_not_rd0` | spec-determined |
| `ftrem` | （无 fault 条件） | — | spec-determined |
| `ftroot` | ILLI | `rootn_n_in_2_3` | spec-determined |
| `ftsclb` | （无 fault 条件） | — | spec-determined |
| `ftscmp` | ILLI | `rd_dest_not_rd0` | spec-determined |
| `ftsgnj` | （无 fault 条件） | — | spec-determined |
| `ftsgnn` | （无 fault 条件） | — | spec-determined |
| `ftsub` | （无 fault 条件） | — | spec-determined |
| `io2fo` | ILLI | `immu6_zero_illi`, `block_range_overflow_illi`, `immu6_1_63` | spec-determined |
| `io2ft` | ILLI | `immu6_zero_illi`, `block_range_overflow_illi`, `immu6_1_63` | spec-determined |
| `it2fo` | ILLI | `immu6_zero_illi`, `block_range_overflow_illi`, `immu6_1_63` | spec-determined |
| `it2ft` | ILLI | `immu6_zero_illi`, `block_range_overflow_illi`, `immu6_1_63` | spec-determined |
| `ld.o-rf` | MALIGN | `aligned(8)`, `rf0_dst_allowed` | spec-determined |
| `ld.t-rf` | MALIGN | `aligned(4)`, `rf0_dst_allowed` | spec-determined |
| `ldm.o-rf` | ILLI、MALIGN | `aligned(8)`, `rf0_dst_allowed`, `immu6_zero_illi`, `block_range_overflow_illi`, `rf_slot_overflow_illi` | spec-determined |
| `ldm.t-rf` | ILLI、MALIGN | `aligned(4)`, `rf0_dst_allowed`, `immu6_zero_illi`, `block_range_overflow_illi`, `rf_slot_overflow_illi` | spec-determined |
| `rd2rf` | ILLI | `immu6_zero_illi`, `block_range_overflow_illi`, `immu6_1_63` | spec-determined |
| `rf2rd` | ILLI | `immu6_zero_illi`, `block_range_overflow_illi`, `immu6_1_63` | spec-determined |
| `set.w-rf` | （无 fault 条件） | `rf0_dst_allowed` | spec-determined |
| `st.o-rf` | MALIGN | `aligned(8)` | spec-determined |
| `st.t-rf` | MALIGN | `aligned(4)` | spec-determined |
| `stm.o-rf` | ILLI、MALIGN | `aligned(8)`, `immu6_zero_illi`, `block_range_overflow_illi`, `rf_slot_overflow_illi` | spec-determined |
| `stm.t-rf` | ILLI、MALIGN | `aligned(4)`, `immu6_zero_illi`, `block_range_overflow_illi`, `rf_slot_overflow_illi` | spec-determined |
| `uo2fo` | ILLI | `immu6_zero_illi`, `block_range_overflow_illi`, `immu6_1_63` | spec-determined |
| `uo2ft` | ILLI | `immu6_zero_illi`, `block_range_overflow_illi`, `immu6_1_63` | spec-determined |
| `ut2fo` | ILLI | `immu6_zero_illi`, `block_range_overflow_illi`, `immu6_1_63` | spec-determined |
| `ut2ft` | ILLI | `immu6_zero_illi`, `block_range_overflow_illi`, `immu6_1_63` | spec-determined |
<!-- /f1:generated:legality -->

## 4. 语义归一化（逐条 `SimRISC-03`，只记规范明说的）

本节把「必须归一化的规则」里的**语义**部分逐条落成事实。规范未唯一规定的一律
指向 §5 的 facet 状态与 §6 的 D* 矩阵，**不在此处**给取值；规范明确「不做要求」
的归入 §7.2 附注。

### 4.1 格式转换（22 条，`§格式转换指令`）

| 规则 | 规范依据 | F1 处置 |
| --- | --- | --- |
| 浮点→浮点溢出返回 ±Inf 并置 OF | :128 | spec-determined |
| 浮点→浮点下溢按舍入模式处理并置 UF | :128 | spec-determined |
| NaN 传播 payload | :128 | payload 传播 spec-determined；quieting/符号/饱和方向 → **D15 OPEN** |
| 整数→浮点可能 inexact（精度损失） | :128 | 是否置 NX → **D12 OPEN** |
| 浮点→整数遇 NaN/Inf/超范围返回**整型饱和值**（最大/最小）并置 NV | :128 | spec-determined |
| sNaN 作算术输入置 NV 并返回 qNaN | :128 | spec-determined |
| 源/目的范围可重叠，按序号递增逐对**先读后写** | :126 | spec-determined |
| `immu6`=0 → ILLI；任一起始寄存器 + `immu6` > 64 → ILLI | :132、:133 | `fp_block_immu6_zero` / `fp_block_range_overflow` |

> `immu6` 的上限 63 由 6 位字段宽度唯一决定（`SimRISC-00:191`），不是额外 fault 条件
> —— 见 §7 静默项 **S2** 及其 **ledger 外**注记 §6.3。

### 4.2 二源一目的运算（`§S2D1`）

| 规则 | 规范依据 | F1 处置 |
| --- | --- | --- |
| 硬件先读全部源操作数再写结果，源被目的覆盖前其值已捕获 | :159、:211 | spec-determined |
| `ftrem`/`forem` = IEEE 754 remainder：`rfhc − n × rfhd`，n 取最接近 `rfhc/rfhd` 的整数、**平局取偶数** | :161 | spec-determined |
| 除数为零/Inf/NaN 时遵循 IEEE 754 | :161 | 置哪些 flag → **D12 OPEN** |
| `ftsclb`/`fosclb` = IEEE 754 scaleB：`rfhc × 2^rfhd` | :163 | 指数解释见 **S5**（两种读法）→ `semantics` 记 **partial** |
| scaleB 的舍入模式由 rf0 控制 | :163 | 模式选择 spec-determined；tininess → **D16 OPEN** |

### 4.3 融合乘加（`§S3D1`，`ftmadd`/`fomadd`）

| 规则 | 规范依据 | F1 处置 |
| --- | --- | --- |
| `rfha = rfhb × rfhc + rfhd` | :174 | spec-determined |
| 融合乘加为**单次舍入**（标准 FMA） | :174 | spec-determined |
| 硬件先读全部源操作数再写结果 | :174 | spec-determined |

### 4.4 root / log（`§S1D1`）

| 规则 | 规范依据 | F1 处置 |
| --- | --- | --- |
| `ftroot`/`foroot` = `rootn(x, n)`，n 在 `immu6`；支持 n=`2`（平方根）、`3`（立方根） | :188 | `fp_root_invalid_n`；合法集合 spec-determined |
| 不支持的 n → ILLI | :188 | `fp_root_invalid_n` |
| `rootn(-0, 2)` 的结果规范**不做具体要求** | :190 | §7.2 附注（非缺口） |
| `ftlog`/`folog` = 对数，base 在 `immu6`；`0`=log10、`1`=自然对数 e、`2`=log2 | :192 | `fp_log_invalid_base`；**`immu6=0` 合法** |
| 不支持的底值 → ILLI | :192 | `fp_log_invalid_base` |
| S1D1 先读源再写结果 | :194 | spec-determined |

### 4.5 符号位操作（`§浮点符号位操作指令`，`ft|fosgnj|ftsgnn`）

| 规则 | 规范依据 | F1 处置 |
| --- | --- | --- |
| `ftsgnj`/`fosgnj` = `copySign(rfhc, rfhd)`：取 rfhc 除符号位外的全部位 + rfhd 的符号位 | :208 | spec-determined |
| `ftsgnn`/`fosgnn` = 上述结果与 rfhd 符号位**取反**后组合 | :209 | spec-determined |
| `rfhd` = rf0 时 `ftsgnj`/`fosgnj` = `abs(rfhc)` | :215 | spec-determined，但与 §3.1 的 rf0 一般规则**冲突** → **D11 OPEN** |
| `rfhd` = rf0 时 `ftsgnn`/`fosgnn` = `-abs(rfhc)` | :216 | 同上 → **D11 OPEN** |
| `rfhc` = `rfhd` 时分别为 `copy` / `negate` | :217、:218 | spec-determined |

### 4.6 比较（`§浮点比较指令`，4 条）

| rdhb 结果 | 含义 | 规范依据 |
| --- | --- | --- |
| `1` | `rfhc > rfhd` | :234 |
| `0` | `rfhc = rfhd` | :235 |
| `-1` | `rfhc < rfhd` | :236 |
| NaN | unordered；Quiet Compare → qNaN（符号位 0）、Signaling Compare → sNaN（符号位 0） | :237 |

> unordered 的**位型**未规定（只说「是 NaN」），4 条的 `compare_unordered` facet 均为
> **OPEN/BLOCKED**（**D14**）。:239 给出「按整型看 qNaN/sNaN 为正数、故可用零与负数条件
> 区分六种关系」的使用方式，属事实记录，不构成位型取值。

### 4.7 条件赋值（`§浮点条件赋值指令`，5 条 `cs.*`）

| 规则 | 规范依据 | F1 处置 |
| --- | --- | --- |
| 第一类 `cs.n`/`cs.z`/`cs.p`：`if (rdha is negative/zero/positive) rfhb = rfhc; else rfhb = rfhd` | :243 | spec-determined |
| 第二类 `cs.eq`/`cs.ne`：`if (rdha ==/!= rdhb) rfhc = rfhd` | :252 | spec-determined |
| 比较结果为 NaN 时 `cs.eq` 与 `cs.ne` **均执行 else 分支**（NaN ≠ 1 且 NaN ≠ 0） | :260 | spec-determined |

> 目的字段是 `rf`（rfhc / rfhb）而非 `rd`，故 `rd_dest_not_rd0` 规则**不**适用（见 §3.1）。

### 4.8 分类（`ftcls`/`focls`）

| 规则 | 规范依据 | F1 处置 |
| --- | --- | --- |
| 设置 rdhb 中相应类别位，**其他位清零，包括 [63..10] 全部清零** | :274 | spec-determined |
| 10 个类别位 bit0..bit9 = negativeInfinity / negativeNormal / negativeSubnormal / negativeZero / positiveZero / positiveSubnormal / positiveNormal / positiveInfinity / signalingNaN / quietNaN | :278-:287 | spec-determined |
| `immu6` 固定为 1（指令形式即 `ftcls rdhb, rfhc, 1`）；`immu6`≠1 的合法性未规定 | :270、:271 | 静默项 **S3** → `legality` 记 **partial** |

## 5. facet 词表

逐 identity 的 11 个 facet 及其状态枚举。

<!-- f1:generated:facet-table -->
### 5.1 facet 键（11 个，逐 identity 必填）

| facet | 含义 | 阻塞时的 ADR-1004 decision |
| --- | --- | --- |
| `encoding` | QFC 编码（op / ha / mask / value / 字段布局） | — |
| `format` | 操作数格式字母 + 操作数签名 | — |
| `operands` | 操作数名、角色、bank | — |
| `legality` | 规范明示的合法性 / 异常谓词 | — |
| `semantics` | 指令主语义 | — |
| `rf0_operand` | rf0 作目的 / 源操作数的规则 | `D11` |
| `tetra_high_half` | 单精（ft）结果写入 rf 后的高 32 位 | `D13` |
| `fcsr_flags` | rf0[4:0] 的设置 / 保持 / 清除 | `D12` |
| `tininess` | 下溢 tininess 检测时点与复合 flags | `D16` |
| `compare_unordered` | 比较 unordered 写入 rd 的 NaN 位型 | `D14` |
| `nan_propagation` | NaN 的 payload / 符号 / quieting / 默认 NaN | `D15` |

### 5.2 facet 状态枚举（4 个）

| 状态 | 含义 |
| --- | --- |
| `spec-determined` | 规范给出唯一答案，可直接实现 |
| `partial` | 规范给出部分答案，剩余部分规范未规定 → 记为 partial + note |
| `open-blocked` | 规范未给唯一答案 → **OPEN/BLOCKED**，登记到 ADR-1004 的对应 D* |
| `n/a` | 该 facet 对本 identity 不适用 |

### 5.3 强制不变量（由 `tools/spec/check_f1_contract.py` 逐 identity 校验）

| 状态 | 不变量 |
| --- | --- |
| `spec-determined` | `open_items` 必须为空 |
| `partial` | `notes` 必须非空 |
| `open-blocked` | `open_items` 必须非空，且该 facet 必须出现在 §6 对应 D* 列 |
| `n/a` | 该 facet **不**出现在 §6 的任何 D* 列 |

> 状态词表刻意**不含** `PASS` 字样，便于「OPEN 被改成 PASS」的反例注入被检查器捕获。
<!-- /f1:generated:facet-table -->

### 5.4 facet 归属的钉死基准（防「自洽地把 OPEN 改成 determined」）

§5.3 的四条不变量只能保证各层**内部自洽**。若有人把某个 `open-blocked` 改成
`spec-determined`，并顺手清空 `open_items`、再重新渲染 `opcodes.yaml` 与本文件，
那么数据层与落盘层完全一致，§5.3 全部照样成立 —— 各层互相印证反而会**假绿**，
而这正是 ADR-1004 D11–D17 最忌讳的「把开口偷偷固化」。

故本合约的 OPEN/partial **归属**在 `tools/spec/check_f1_contract.py` 内部另有一张
**字面量基准表**（`PINNED_OPEN` / `PINNED_PARTIAL` / `PINNED_MATRIX`，共 166 个
open + 12 个 partial，D11–D17 列为 37/53/18/4/18/36/64）。改
`f1_contract_data.py` 的推导结果而不同步这张表，检查器会**点名 identity + facet**
报错（检查项 D7/D8）。反例注入 `test_f1_contract_counterexamples.py` 的
CE-5 即针对该路径。

| facet | open-blocked | partial | 其余 |
| --- | --- | --- | --- |
| `rf0_operand` | 37 | 0 | 27 spec-determined |
| `fcsr_flags` | 53 | 0 | 11 spec-determined |
| `tetra_high_half` | 18 | 0 | 46 n/a |
| `compare_unordered` | 4 | 0 | 60 n/a |
| `nan_propagation` | 18 | 2 | 44 n/a |
| `tininess` | 36 | 0 | 28 n/a |
| `legality` | 0 | 2 | 62 spec-determined |
| `semantics` | 0 | 8 | 56 spec-determined |
| `encoding` / `format` / `operands` | 0 | 0 | 64 spec-determined（恒定） |

## 6. D11–D17 受影响矩阵

<!-- f1:generated:d-matrix -->
逐 identity × facet 的阻塞矩阵。单元格列出该 identity 在该 D* 下的**受阻 facet**；`-` 表示该 identity 不在该 D* 的受影响集内。

| identity | D11 | D12 | D13 | D14 | D15 | D16 | D17 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `cs.eq-rf` | `rf0_operand` | `fcsr_flags` | - | - | - | - | `any-open-or-silent` |
| `cs.n-rf` | `rf0_operand` | `fcsr_flags` | - | - | - | - | `any-open-or-silent` |
| `cs.ne-rf` | `rf0_operand` | `fcsr_flags` | - | - | - | - | `any-open-or-silent` |
| `cs.p-rf` | `rf0_operand` | `fcsr_flags` | - | - | - | - | `any-open-or-silent` |
| `cs.z-rf` | `rf0_operand` | `fcsr_flags` | - | - | - | - | `any-open-or-silent` |
| `fo2fo` | `rf0_operand` | `fcsr_flags` | - | - | - | - | `any-open-or-silent` |
| `fo2ft` | `rf0_operand` | `fcsr_flags` | `tetra_high_half` | - | - | `tininess` | `any-open-or-silent` |
| `fo2io` | `rf0_operand` | `fcsr_flags` | - | - | - | `tininess` | `any-open-or-silent` |
| `fo2it` | `rf0_operand` | `fcsr_flags` | - | - | - | `tininess` | `any-open-or-silent` |
| `fo2uo` | `rf0_operand` | `fcsr_flags` | - | - | - | `tininess` | `any-open-or-silent` |
| `fo2ut` | `rf0_operand` | `fcsr_flags` | - | - | - | `tininess` | `any-open-or-silent` |
| `foadd` | - | `fcsr_flags` | - | - | `nan_propagation` | `tininess` | `any-open-or-silent` |
| `focls` | `rf0_operand` | `fcsr_flags` | - | - | - | - | `any-open-or-silent` |
| `fodiv` | - | `fcsr_flags` | - | - | `nan_propagation` | `tininess` | `any-open-or-silent` |
| `folog` | - | `fcsr_flags` | - | - | `nan_propagation` | `tininess` | `any-open-or-silent` |
| `fomadd` | - | `fcsr_flags` | - | - | `nan_propagation` | `tininess` | `any-open-or-silent` |
| `fomul` | - | `fcsr_flags` | - | - | `nan_propagation` | `tininess` | `any-open-or-silent` |
| `foqcmp` | `rf0_operand` | `fcsr_flags` | - | `compare_unordered` | - | - | `any-open-or-silent` |
| `forem` | - | `fcsr_flags` | - | - | `nan_propagation` | `tininess` | `any-open-or-silent` |
| `foroot` | - | `fcsr_flags` | - | - | `nan_propagation` | `tininess` | `any-open-or-silent` |
| `fosclb` | - | `fcsr_flags` | - | - | `nan_propagation` | `tininess` | `any-open-or-silent` |
| `foscmp` | `rf0_operand` | `fcsr_flags` | - | `compare_unordered` | - | - | `any-open-or-silent` |
| `fosgnj` | `rf0_operand` | `fcsr_flags` | - | - | - | - | `any-open-or-silent` |
| `fosgnn` | `rf0_operand` | `fcsr_flags` | - | - | - | - | `any-open-or-silent` |
| `fosub` | - | `fcsr_flags` | - | - | `nan_propagation` | `tininess` | `any-open-or-silent` |
| `ft2fo` | `rf0_operand` | `fcsr_flags` | - | - | - | `tininess` | `any-open-or-silent` |
| `ft2ft` | `rf0_operand` | `fcsr_flags` | `tetra_high_half` | - | - | - | `any-open-or-silent` |
| `ft2io` | `rf0_operand` | `fcsr_flags` | - | - | - | `tininess` | `any-open-or-silent` |
| `ft2it` | `rf0_operand` | `fcsr_flags` | - | - | - | `tininess` | `any-open-or-silent` |
| `ft2uo` | `rf0_operand` | `fcsr_flags` | - | - | - | `tininess` | `any-open-or-silent` |
| `ft2ut` | `rf0_operand` | `fcsr_flags` | - | - | - | `tininess` | `any-open-or-silent` |
| `ftadd` | - | `fcsr_flags` | `tetra_high_half` | - | `nan_propagation` | `tininess` | `any-open-or-silent` |
| `ftcls` | `rf0_operand` | `fcsr_flags` | - | - | - | - | `any-open-or-silent` |
| `ftdiv` | - | `fcsr_flags` | `tetra_high_half` | - | `nan_propagation` | `tininess` | `any-open-or-silent` |
| `ftlog` | - | `fcsr_flags` | `tetra_high_half` | - | `nan_propagation` | `tininess` | `any-open-or-silent` |
| `ftmadd` | - | `fcsr_flags` | - | - | `nan_propagation` | `tininess` | `any-open-or-silent` |
| `ftmul` | - | `fcsr_flags` | `tetra_high_half` | - | `nan_propagation` | `tininess` | `any-open-or-silent` |
| `ftqcmp` | `rf0_operand` | `fcsr_flags` | - | `compare_unordered` | - | - | `any-open-or-silent` |
| `ftrem` | - | `fcsr_flags` | `tetra_high_half` | - | `nan_propagation` | `tininess` | `any-open-or-silent` |
| `ftroot` | - | `fcsr_flags` | `tetra_high_half` | - | `nan_propagation` | `tininess` | `any-open-or-silent` |
| `ftsclb` | - | `fcsr_flags` | `tetra_high_half` | - | `nan_propagation` | `tininess` | `any-open-or-silent` |
| `ftscmp` | `rf0_operand` | `fcsr_flags` | - | `compare_unordered` | - | - | `any-open-or-silent` |
| `ftsgnj` | `rf0_operand` | `fcsr_flags` | `tetra_high_half` | - | - | - | `any-open-or-silent` |
| `ftsgnn` | `rf0_operand` | `fcsr_flags` | `tetra_high_half` | - | - | - | `any-open-or-silent` |
| `ftsub` | - | `fcsr_flags` | `tetra_high_half` | - | `nan_propagation` | `tininess` | `any-open-or-silent` |
| `io2fo` | `rf0_operand` | `fcsr_flags` | - | - | - | `tininess` | `any-open-or-silent` |
| `io2ft` | `rf0_operand` | `fcsr_flags` | `tetra_high_half` | - | - | `tininess` | `any-open-or-silent` |
| `it2fo` | `rf0_operand` | `fcsr_flags` | - | - | - | `tininess` | `any-open-or-silent` |
| `it2ft` | `rf0_operand` | `fcsr_flags` | `tetra_high_half` | - | - | `tininess` | `any-open-or-silent` |
| `ld.o-rf` | - | - | - | - | - | - | `any-open-or-silent` |
| `ld.t-rf` | - | - | `tetra_high_half` | - | - | - | `any-open-or-silent` |
| `ldm.o-rf` | - | - | - | - | - | - | `any-open-or-silent` |
| `ldm.t-rf` | - | - | `tetra_high_half` | - | - | - | `any-open-or-silent` |
| `rd2rf` | `rf0_operand` | - | - | - | - | - | `any-open-or-silent` |
| `rf2rd` | `rf0_operand` | - | - | - | - | - | `any-open-or-silent` |
| `set.w-rf` | - | - | - | - | - | - | `any-open-or-silent` |
| `st.o-rf` | - | - | - | - | - | - | `any-open-or-silent` |
| `st.t-rf` | - | - | - | - | - | - | `any-open-or-silent` |
| `stm.o-rf` | - | - | - | - | - | - | `any-open-or-silent` |
| `stm.t-rf` | - | - | - | - | - | - | `any-open-or-silent` |
| `uo2fo` | `rf0_operand` | `fcsr_flags` | - | - | - | `tininess` | `any-open-or-silent` |
| `uo2ft` | `rf0_operand` | `fcsr_flags` | `tetra_high_half` | - | - | `tininess` | `any-open-or-silent` |
| `ut2fo` | `rf0_operand` | `fcsr_flags` | - | - | - | `tininess` | `any-open-or-silent` |
| `ut2ft` | `rf0_operand` | `fcsr_flags` | `tetra_high_half` | - | - | `tininess` | `any-open-or-silent` |

### 6.1 各 D* 的受影响规模

| decision | 对应 facet | 受影响 identity 数 | 状态 |
| --- | --- | --- | --- |
| `D11` | `rf0_operand` | 37 | **OPEN/BLOCKED** |
| `D12` | `fcsr_flags` | 53 | **OPEN/BLOCKED** |
| `D13` | `tetra_high_half` | 18 | **OPEN/BLOCKED** |
| `D14` | `compare_unordered` | 4 | **OPEN/BLOCKED** |
| `D15` | `nan_propagation` | 18 | **OPEN/BLOCKED** |
| `D16` | `tininess` | 36 | **OPEN/BLOCKED** |
| `D17` | （D17 兜底） | 64 | **OPEN/BLOCKED** |

> **全部 7 列都非空**：`D11`–`D17` 每个都至少有一条受影响 identity，且没有任何一条被写成确定值。本合约**不**为 OPEN 项提供取值；取值必须由用户逐 decision 确认后另行写 ADR。
<!-- /f1:generated:d-matrix -->

### 6.2 `D17 OPEN-ID ledger`（交给下游的具名门禁台账）

<!-- f1:generated:d17-ledger -->
**`D17 OPEN-ID ledger`** 是本合约交给下游的**具名门禁台账**：精确键集合固定为

> {`D17:S1`,`D17:S3`,`D17:S4`,`D17:S5`,`D17:S6`,`D17:S7`,`D17:S8`}

共 **7** 行，每行一个 OPEN-ID。下表逐行给出：**状态**、**受影响 identity / 范围**、**被阻塞的合约 facet**、**下游消费者任务**与**关闭证据占位符**。

| OPEN-ID | 状态 | 主题（**不含任何取值**） | 受影响 identity / 范围 | 被阻塞 facet | 下游消费者任务 | 关闭证据（占位，未回填） |
| --- | --- | --- | --- | --- | --- | --- |
| `D17:S1` | BLOCKED | rf0/FCSR **复位值**未规定（布局/可观测 mask **不**并入本项） | `all-64`：全部 64（首条浮点指令执行前的 rf0 舍入模式与 flags 初始值） | `fcsr_flags` | `SPEC-103t`、`TESTCASES-101t`、`TESTCASES-102t`、`QEMU-101t`、`QEMU-102t`、`QEMU-103t`、`INTEG-102t`、`INTEG-103t`、`INTEG-104m` | 占位：待 `SPEC-103t` 逐键证明 + 用户逐 decision 确认后回填（本任务不填取值、不选方案） |
| `D17:S3` | BLOCKED | `ftcls`/`focls` 的 `immu6`≠1（classify immediate）合法性未规定 | `ftcls`、`focls` | `legality` | `SPEC-103t`、`TESTCASES-101t`、`TESTCASES-102t`、`LLVM-101t`、`QEMU-103t`、`INTEG-102t`、`INTEG-103t`、`INTEG-104m` | 占位：待 `SPEC-103t` 逐键证明 + 用户逐 decision 确认后回填（本任务不填取值、不选方案） |
| `D17:S4` | BLOCKED | 多个 fault 条件同时成立时的**异常优先级**未规定 | `multi-fault`：同时满足两个以上规范 fault 谓词的所有 identity（逐条见 §3.2） | `legality` | `SPEC-103t`、`TESTCASES-101t`、`TESTCASES-102t`、`QEMU-101t`、`QEMU-102t`、`QEMU-103t`、`INTEG-102t`、`INTEG-103t`、`INTEG-104m` | 占位：待 `SPEC-103t` 逐键证明 + 用户逐 decision 确认后回填（本任务不填取值、不选方案） |
| `D17:S5` | BLOCKED | `ftsclb`/`fosclb` 的 scaleB 指数「`rfhd` 取整数值」有两种读法 | `ftsclb`、`fosclb` | `semantics` | `SPEC-103t`、`TESTCASES-101t`、`TESTCASES-102t`、`QEMU-102t`、`INTEG-102t`、`INTEG-103t`、`INTEG-104m` | 占位：待 `SPEC-103t` 逐键证明 + 用户逐 decision 确认后回填（本任务不填取值、不选方案） |
| `D17:S6` | BLOCKED | rf0 的 **SBZ 域被写入**时的行为未规定（**不指定**忽略/保留/清零/异常） | `ld.t-rf`、`ld.o-rf`、`ldm.t-rf`、`ldm.o-rf`、`set.w-rf`、`rd2rf` | `legality` | `SPEC-103t`、`TESTCASES-101t`、`TESTCASES-102t`、`QEMU-101t`、`INTEG-102t`、`INTEG-103t`、`INTEG-104m` | 占位：待 `SPEC-103t` 逐键证明 + 用户逐 decision 确认后回填（本任务不填取值、不选方案） |
| `D17:S7` | BLOCKED | `rd2rf`/`rf2rd` 源与目的范围**重叠**时的读写顺序未规定 | `rd2rf`、`rf2rd` | `semantics` | `SPEC-103t`、`TESTCASES-101t`、`TESTCASES-102t`、`QEMU-101t`、`INTEG-102t`、`INTEG-103t`、`INTEG-104m` | 占位：待 `SPEC-103t` 逐键证明 + 用户逐 decision 确认后回填（本任务不填取值、不选方案） |
| `D17:S8` | BLOCKED | `ldm`/`stm` 的**内存侧**寻址、步长与重叠读写顺序未规定 | `ldm.t-rf`、`ldm.o-rf`、`stm.t-rf`、`stm.o-rf` | `semantics` | `SPEC-103t`、`TESTCASES-101t`、`TESTCASES-102t`、`QEMU-101t`、`INTEG-102t`、`INTEG-103t`、`INTEG-104m` | 占位：待 `SPEC-103t` 逐键证明 + 用户逐 decision 确认后回填（本任务不填取值、不选方案） |

**规范原文**逐条见 §7.1 的 `#### S1`…`#### S8` 各段（那里逐句引用 `spec/SimRISC-00*` / `spec/SimRISC-03*` 原句）；本 ledger **不复制**原文，只登记「规范未给唯一答案」这一事实。

### 6.3 ledger 外的 `D17:S2`（**非 ledger 行**）

> **`D17:S2` 不在 ledger 内**，仅作来源追踪：`no behavioral consequence; resolved/trace-only; not in D17 OPEN-ID ledger; never PASS`

「有效范围 1~63」只出现在块赋值（`SimRISC-03:44`）与格式转换（`:126`）节，未出现在 §存取RF寄存器（`:29-31`）；但 `immu6` 上限 63 由 6 位字段宽度（`SimRISC-00:191`）唯一决定、`immu6`=0 另有独立 ILLI 谓词，故两节的有效范围**实际一致**、**无行为后果**。因此 `D17:S2` **不占用** ledger 键、**不是**阻塞项、**不得**计 PASS，也**不得**据它给任何 identity 追加谓词。

### 6.4 读法约定（防止 ledger 被当成语义已决）

1. ledger 的 `状态` 列**只允许** `OPEN` / `BLOCKED` 两个词。`PASS` / `active` / `spec-determined` / `resolved` 在未关闭前一律**非法**（`resolved` 只允许出现在 `D17:S2` 的 trace-only 注记里，而它不是 ledger 行）。
2. 「被阻塞 facet」只表示**该项未决所压住的那一面**，**不改动** §5.4 与 `contracts/opcodes.yaml` 里任何 identity 的 facet 状态归属（归属由 `check_f1_contract.py` 的 `PINNED_OPEN` / `PINNED_PARTIAL` 钉死）。
3. **layout 与 reset 必须分栏**：rf0/FCSR 的**字段布局、位号与可观测 mask** 是 spec-determined、现在可核对的 `A` 面（§2 表格）；**复位值**是 `D17:S1 = O`。不得用「布局已知」推出「复位已知」，也不得用 `A` 覆盖同一 identity 上仍为 `O` 的面。
4. `D17:S6` **不指定**任何 SBZ 写入动作：「忽略 / 保留 / 清零 / 触发异常」四者**一个都不许**被本合约、机器数据或任何消费者选定。
5. 关闭证据是**占位符**。本任务**不**回填取值、**不**选方案、**不**创建 ADR；由 `SPEC-103t` 逐键证明并经用户逐 decision 确认后，才可改写 `状态` 列。
6. 「下游消费者任务」列的是**消费**本台账结论的任务。本合约的**生产者**（`SPEC-102t`，即本文件自身）按构造**不**出现在该列里；`SPEC-101k` 矩阵中与 `SPEC-103t` 合并成一行的那一格，在本表里只体现为 `SPEC-103t`。

> 机器可读侧的同一台账落在 `contracts/opcodes.yaml` 每条 F1 记录的 `f1.d17_open_ids`（逐 identity 列出命中的 ledger 键，**永不含** `D17:S2`）。
<!-- /f1:generated:d17-ledger -->

## 7. 规范静默项（D1–D18 之外的新发现）

<!-- f1:generated:silent -->
以下 8 项是 **D1–D18 之外新发现**的规范静默项。它们**只登记原文与受影响范围**，**不作出 decision**；不因此改动任何 facet 的 OPEN 状态，也不新增 fault 规则。

| 编号 | 主题 | 受影响 identity / 范围 |
| --- | --- | --- |
| **S1** | rf0/FCSR 的复位值未定义 | 全部 64 个 identity（首条浮点指令执行前的 rf0 舍入模式与 flags 初始值） |
| **S2** | 「有效范围 1~63」只出现在块赋值/格式转换节，未出现在存取 RF 节（表述不一致，但**无行为后果**） | ldm.t-rf、stm.t-rf、ldm.o-rf、stm.o-rf（表述层面） |
| **S3** | ftcls/focls 的 immu6≠1 未规定合法性 | ftcls、focls |
| **S4** | 多个条件同时成立时的异常优先级未规定 | 同时满足两个以上规范的 fault 条件的所有 identity（合约 §3.2 逐条列出） |
| **S5** | ftsclb/fosclb 中「rfhd 取整数值」有两种读法 | ftsclb、fosclb |
| **S6** | rf0 的 SBZ 域被写入时的行为未规定 | 以 rf0 为目的可写的 identity：ld.t-rf、ld.o-rf、ldm.t-rf、ldm.o-rf、set.w-rf、rd2rf（immu6 覆盖到 rf0 时） |
| **S7** | rd2rf/rf2rd 源与目的寄存器范围重叠时的读写顺序未规定 | rd2rf、rf2rd |
| **S8** | ldm/stm 的内存侧寻址、步长与重叠读写顺序未在 SimRISC-03 规定 | ldm.t-rf、ldm.o-rf、stm.t-rf、stm.o-rf |

### 7.1 原文与处置

#### S1 — rf0/FCSR 的复位值未定义

- spec/SimRISC-00-指令系统设计.md:82-86 给出 rf0 全部位域、舍入模式表与异常状态表，但未给出 rf0 的复位值。
- spec/SimRISC-00-指令系统设计.md:62 「硬件复位后 `rb0` 初值为 `cfx_power_hypv_excp_vector`」、:55 「`rd0` 固定为 0，只读」、:120 「ra0 …初始值应为 0」——同类寄存器均给了初值，rf0 没有。

**受影响**：全部 64 个 identity（首条浮点指令执行前的 rf0 舍入模式与 flags 初始值）

**处置**：未决。F1 需要的「rf0/FCSR 布局和复位」中，布局可由 SimRISC-00 推出，复位值不可推出；不发明初值。

#### S2 — 「有效范围 1~63」只出现在块赋值/格式转换节，未出现在存取 RF 节（表述不一致，但**无行为后果**）

- spec/SimRISC-03-浮点类指令.md:44 「`immu6` …用来指定寄存器的个数，有效范围为1~63」（寄存器组之间块赋值）、:126 「immu6 指定连续转换的寄存器数量（1-63）」（格式转换）。
- spec/SimRISC-03-浮点类指令.md:29-31 的 §存取RF寄存器 只列了三条 ILLI 谓词（immu6=0、任一起始寄存器+immu6>64、rfha+immu6>64），**未**复述 1~63。
- spec/SimRISC-00-指令系统设计.md:191 「`rrri`：…一个6位立即数在 `hd[5:0]`」——immu6 只有 6 位，编码上限即 63。

**受影响**：ldm.t-rf、stm.t-rf、ldm.o-rf、stm.o-rf（表述层面）

**处置**：**不是缺口**：immu6 上限 63 由位宽唯一决定，immu6=0 另有 ILLI 规则，故 §存取RF 与另两节的**有效范围完全一致**（1~63），无行为差异。合约因此**不**为 ldm/stm 追加 `immu6_1_63` 谓词，`legality` facet 也不因此记 partial。本项仅作表述不一致登记。

#### S3 — ftcls/focls 的 immu6≠1 未规定合法性

- spec/SimRISC-03-浮点类指令.md:270-271 只给出签名 `ftcls   rdhb, rfhc, 1`、`focls   rdhb, rfhc, 1`，未说明 immu6 取其它值时的行为。

**受影响**：ftcls、focls

**处置**：未决。不发明 fault 类型。

#### S4 — 多个条件同时成立时的异常优先级未规定

- spec/SimRISC-03-浮点类指令.md:25 「未对齐触发 MALIGN 异常」与 :29-31 的 ILLI 谓词并列，未给先后；:188 「不支持的 n 值触发 ILLI 异常」与 :7 的 rf0→ILLI 规则并列，也未给先后。

**受影响**：同时满足两个以上规范的 fault 条件的所有 identity（合约 §3.2 逐条列出）

**处置**：未决。合约 §3.2 只列「本 identity 可触发的 fault 集合」，不排序。

#### S5 — ftsclb/fosclb 中「rfhd 取整数值」有两种读法

- spec/SimRISC-03-浮点类指令.md:163 「计算 `rfhc × 2^rfhd`（rfhd 取整数值）」。
- 读法 A：rfhd 的值按整数解释（IEEE 754 scaleB 要求 b 为整数）；读法 B：对 rfhd 做截断取整。规范未说明 rfhd 非整数值时取哪种。

**受影响**：ftsclb、fosclb

**处置**：未决。facet 记 partial，不发明取整方式。

#### S6 — rf0 的 SBZ 域被写入时的行为未规定

- spec/SimRISC-03-浮点类指令.md:7 「写只读位时静默忽略，rw 位正常写入」——只覆盖 [63..51] 与 [31..22] 两个只读域；[50..32]、[21..18]、[15..5] 标为 SBZ，SBZ 被写入时的行为未写。
- contracts/legality_rules.yaml 现行 `sbz_nonzero` 规则把 SBZ 非零冻结为 ILLI（ADR-0004 D5.3，架构自定义）；F1 是否沿用未决。

**受影响**：以 rf0 为目的可写的 identity：ld.t-rf、ld.o-rf、ldm.t-rf、ldm.o-rf、set.w-rf、rd2rf（immu6 覆盖到 rf0 时）

**处置**：未决。合约只登记只读域掩码，SBZ 写入行为留待决策。

#### S7 — rd2rf/rf2rd 源与目的寄存器范围重叠时的读写顺序未规定

- spec/SimRISC-03-浮点类指令.md:126 格式转换节明示「转换按序号递增逐对进行，先读后写。重叠时行为依赖顺序，使用者应避免在同一寄存器同时出现在源和目的中」。
- spec/SimRISC-03-浮点类指令.md:43 块赋值节只写「将 hc 开始的 immu6 个寄存器复制到 hb 开始的 immu6 个寄存器中」，未规定重叠时的读写顺序。

**受影响**：rd2rf、rf2rd

**处置**：未决。不把格式转换节的「先读后写」外推到块赋值节。

#### S8 — ldm/stm 的内存侧寻址、步长与重叠读写顺序未在 SimRISC-03 规定

- spec/SimRISC-03-浮点类指令.md:19-22 给出 `ldm.t rfha, rbhb, rdhc, immu6` 等签名，:25 给出对齐要求，:29-31 给出三条 ILLI 谓词——**只字未提**内存侧第 i 个元素访问哪个地址、步长是多少、rbhb+rdhc 如何组合。
- spec/SimRISC-03-浮点类指令.md:35 「块传输过程中不进行数据类型的转换，保持64位二进制不变，但是必需是多个连续的寄存器」只说**寄存器**连续，未说**地址**连续。
- 对照：spec/SimRISC-01-*.md:59-61、:67 对 RD 侧 ldm/stm 明写「分别存放到以 rb2 为基址的 8 字节连续地址中」「范围包括 rdhc 时地址计算仍按原始 rdhc 进行」「装入类源/目的范围可重叠，按序号递增逐对先读后写」——但 SimRISC-01 **不在 F1 的权威集内**（§0），不能拿来替 RF 侧补齐。

**受影响**：ldm.t-rf、ldm.o-rf、stm.t-rf、stm.o-rf

**处置**：未决。合约只登记签名、对齐与三条 ILLI 谓词，**不**从 SimRISC-01 外推地址组合/步长/重叠顺序。本项只落在 `semantics` facet（4 条 ldm/stm 记 **partial**）。`legality` facet **不**因 S2 或 S8 记 partial：S2 已证明 §存取RF 的有效范围与另两节一致（无行为后果，见 S2 处置），S8 缺的是**内存侧语义**、不是合法性谓词；故这 4 条的 `legality` 仍是 spec-determined。内存侧语义缺口不在 D11–D17 范围内，登记为 F1 实现前必须补的规范项。

### 7.2 非缺口附注（规范明示「不做要求」）

| 附注 | 规范依据 |
| --- | --- |
| `rootn(-0,2)` | spec/SimRISC-03-浮点类指令.md:190「在 IEEE754-2019 中特意指出，`rootn(-0, 2)` 不等于 `squareRoot(-0)`，因此，对于 `rootn(-0, 2)` 的运算结果不做具体要求」——规范明示不要求实现该结果，facet semantics 记 partial，不构成待决策缺口。 |

> 附注**不**进入 §6 的 D* 矩阵，也**不**构成待决策缺口。
<!-- /f1:generated:silent -->

## 8. 候选 ADR 证据输入

<!-- f1:generated:candidate-adr -->
> **ADR 门禁**：ADR-1005 / 1006 / 1007 只能是 **Candidate**。本节只提供**证据输入**（相互冲突的原文 + 受影响 identity/facet + 最小决策问题），**不含任何 decision 取值**。本任务**不创建**这三个 ADR 文件，**不得**由任何文件把它们标为 Accepted；每个 decision 须由用户逐条确认后另行写入。

### 候选 ADR-1005 — rf0 操作数冲突与 tetra 高半部

- **状态**：Candidate（`ADR-1005` 文件尚未创建，不得创建为 Accepted）
- **拟覆盖的 OPEN decision**：`D11`、`D13`

**相互冲突 / 不足的规范原文**：

- SimRISC-03:7「浮点运算指令的目的或任一源操作数为 rf0 时触发 **ILLI** 异常」vs SimRISC-03:215-216「当rfhd为rf0时，ftsgnj和fosgnj实现了 `abs(rfhc)` 操作／ftsgnn和fosgnn实现了 `-abs(rfhc)` 操作」——后者要求 rfhd=rf0 产生结果，前者要求同一编码触发 ILLI。
- SimRISC-03:7 的「浮点运算指令」在 SimRISC-03 的章节结构里只明确覆盖 §浮点运算指令（S2D1/S3D1/S1D1）；§格式转换指令、§浮点分类指令、§浮点比较指令、§浮点条件赋值指令、§寄存器组之间块赋值是否被该规则覆盖，规范未说明。
- SimRISC-03:7「rf ld/st 中 rf0 为目的时允许」只点名 rf ld/st；rd2rf/rf2rd 以 rf0 为目的或来源时的行为，两条规则都没点名。
- SimRISC-00:73「rf寄存器字长64位，当存放单精32位数据时，只使用低32位，**高32位不做特殊规定**」——单精结果写入 rf 后的高 32 位无规范答案。

**最小决策问题**：

- Q5.1 rf0→ILLI 一般规则的适用范围是「§浮点运算指令 的 22 条」，还是「SimRISC-03 全部 64 条」？
- Q5.2 sign-injection 特例（rfhd=rf0 → abs/-abs）与 rf0→ILLI 一般规则冲突时，哪条优先？特例只对 ftsgnj/fosgnj/ftsgnn/fosgnn 生效，还是所有指令？
- Q5.3 rd2rf/rf2rd 目的或来源为 rf0 时，是允许（像 rf ld/st）还是 ILLI？
- Q5.4 写单精（ft）结果到 rf 槽位时，高 32 位是保留原值、清零，还是写入默认 NaN 位型？该规则是否也适用于 ld.t-rf/ldm.t-rf 的 4 字节载入？

### 候选 ADR-1006 — FCSR flags 的 sticky/清除与 tininess/复合 flags

- **状态**：Candidate（`ADR-1006` 文件尚未创建，不得创建为 Accepted）
- **拟覆盖的 OPEN decision**：`D12`、`D16`

**相互冲突 / 不足的规范原文**：

- SimRISC-00:86 只声明 [4..0] 是「异常状态（Accured exception）」；SimRISC-00:107「浮点指令执行后，异常状态位（NV/DZ/OF/UF/NX）由硬件按 IEEE 754 标准设置到 rf0[4:0]」——未说明是「置位（sticky OR）」还是「按本次结果整体写入」。
- 规范全文没有「清除」条款：没有说明后续不产生异常的指令是否保留旧 flags，也没有说明软件如何（能否）清除 flags。
- SimRISC-03:7 说 rf0 的 rw 位「正常写入」，因此 ld/st/set.w 写 rf0 可直接改 flags；但「硬件自动置位」与「软件直接写入」的叠加顺序未规定。
- tininess（SimRISC-03:128 只说「下溢按舍入模式处理（设置 UF）」）的检测时点（舍入前/舍入后/仅精确下溢）未规定；UF/OF/NX 的复合置位规则也未规定。

**最小决策问题**：

- Q6.1 rf0[4:0] 的硬件更新语义是 sticky OR（只置位不清零）还是每次整体写入？
- Q6.2 无异常指令执行后 flags 是否保持原值？
- Q6.3 flags 是否存在软件清除路径（`set.w`/ld/st 写 rf0 是否算清除）？
- Q6.4 tininess 检测时点：舍入前 / 舍入后 / 仅当结果精确且次正规？
- Q6.5 UF 与 NX、OF 与 NX 的复合置位组合规则？
- Q6.6 哪 53 条 identity 属于「浮点指令」（受 flags 规则约束）？数据搬移类（rf ld/st/ldm/stm、set.w、rd2rf/rf2rd）是否完全不受影响？

### 候选 ADR-1007 — 比较 unordered 位型与 NaN 传播

- **状态**：Candidate（`ADR-1007` 文件尚未创建，不得创建为 Accepted）
- **拟覆盖的 OPEN decision**：`D14`、`D15`

**相互冲突 / 不足的规范原文**：

- SimRISC-03:237「NaN：unordered，Quiet Compare的结果为qNaN（符号位为0），Signaling Compare的结果为sNaN（符号位为0）」——只固定符号位为 0，指数/尾数（payload）位型未给。
- SimRISC-00:80/:82 给出 rf0 的 fo/ft 位型为「符号位为0，E为全1，尾数最高位为1」的 qNaN；规范未声明比较 unordered 的 NaN 是否等于该默认 NaN。
- SimRISC-03:128 只对浮点→浮点转换说「NaN 传播 payload」，对多操作数运算（ftadd/ftmul/… 与 ftmadd/fomadd）未说 payload/符号/quieting 的选择规则。
- SimRISC-03:128「sNaN 作为算术输入时设置 NV 并返回 qNaN」——「返回 qNaN」未指定是 quieting 后的输入 NaN 还是默认 qNaN。

**最小决策问题**：

- Q7.1 unordered 比较写入 rd 的 qNaN/sNaN 精确位型（E 与 payload）？是否等于 rf0 中的默认 NaN 位型？
- Q7.2 多操作数运算中出现多个 NaN 时的选择规则（第一个？quiet 优先？符号？）？
- Q7.3 sNaN 输入时返回的 qNaN 是 quieting 后的输入 NaN，还是默认 qNaN？
- Q7.4 哪些 18 条 identity 的 NaN 行为受阻（ARITH 12 + FMA 2 + root/log 4）？「NaN 传播 payload」是否适用于 fo2ft/ft2fo（partial）？

<!-- /f1:generated:candidate-adr -->

## 9. 引用与消歧约定

1. **引用只指向 `spec/SimRISC-00*` / `spec/SimRISC-03*` / `README.md` /
   `adr-1004-f1-floating-phase.md`**。**不得**引用 `DADAO-1x` 系列的任何历史参考
   仓库编号（按 `manifests/` 锁定的 commit 只作只读溯源对照，**不是** F1 的执行
   依赖，更不是语义来源）。`check_f1_contract.py` 用正则
   `DADAO-1[01]|DADAO-06\d\d` 扫描本文件、`contracts/opcodes.yaml`、
   `contracts/legality_rules.yaml`，命中即非零退出。
2. **编码引用**统一为 `SimRISC-00 §<QFC 子表>`（`f1_contract_data.QFC_SECTION`），
   **语义引用**统一为 `SimRISC-03 §<小节>`（`f1_contract_data.SEMANTIC_SECTION`）。
   两者在 `contracts/opcodes.yaml` 的 `f1.encoding_cite` / `f1.semantics_cite` 落盘。
3. **裸助记符只在语义小节引用里使用**（同小节内 bank 唯一）；机器可读处一律用 `insn`。
4. `spec_cite` 只写章节号 + 行号定位，**不**写 `.tao/knowledge/*` 路径。
5. 本合约**不含**任何「从实现反推」的内容；所有表格可由
   `tools/spec/f1_render_contract.py` 从 `spec/` 重新生成并逐字节复现。
