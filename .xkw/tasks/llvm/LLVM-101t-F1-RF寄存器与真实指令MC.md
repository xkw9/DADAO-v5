# LLVM-101t: F1 RF 寄存器与真实指令 MC

**模块**：llvm  
**项目里程碑**：F1  
**状态**：待开始  
**依赖**：`SPEC-102t re-Accepted`、`SPEC-103t` 的 `D17 OPEN-ID ledger` 阻塞表、`SPEC-104t` 的 `resolution` 层、`INFRA-108t`；assembler legality 只消费 ADR-1015 D2（`D17:S3`）与 ADR-1009 D2（`D11`）在对应 ADR Accepted 后的投影

## 目标

在 LLVM DADAO MC 层加入 rf0–rf63 寄存器及 64 个真实硬件 identity 的解析、编码、反汇编打印；不含 CodeGen。所有组件改动从 LLVM `0009+` append，M1 `0001`–`0008` 不变。

## 64 identity

QFC/相关 18：`ld.t-rf st.t-rf ld.o-rf st.o-rf ldm.t-rf stm.t-rf ldm.o-rf stm.o-rf set.w-rf rd2rf rf2rd ftmadd fomadd cs.eq-rf cs.ne-rf cs.n-rf cs.z-rf cs.p-rf`。  
MISC-RF 46：`ftcls ft2fo ft2ft ftroot ftlog focls fo2ft fo2fo foroot folog ft2it ft2io ft2ut ft2uo it2ft io2ft ut2ft uo2ft fo2it fo2io fo2ut fo2uo it2fo io2fo ut2fo uo2fo ftadd ftsub ftmul ftdiv ftrem ftsclb ftsgnn ftsgnj foadd fosub fomul fodiv forem fosclb fosgnn fosgnj ftqcmp ftscmp foqcmp foscmp`。

## 范围与所有权

- 修改 `.work/f1/source/llvm-project/llvm/lib/Target/DADAO/` 中 MC/TableGen/AsmParser/Disassembler 所需文件，并生成 `components/llvm/patches/0009+`。
- 寄存器类与 operand parser 必须区分 rd/rb/rf/ra；同 mnemonic 的 `ld.t/ld.o/...` 由寄存器类消歧。
- 编码来自 `contracts/opcodes.yaml` 的 F1 scope，但必须由独立字节 oracle 再核对，不能 LLVM 自证。
- 此任务不实现 `set.ft/set.fo` pseudo（归 LLVM-103t）、不做 CodeGen、不定义浮点语义。

## 合法性与诊断

assembler 应拒绝错误寄存器组、越界寄存器、格式错误和 contract **已确定**的 immediate 非法形式；运行期数据相关异常不应伪装成 assembler 错误。`rf0` 可作普通源 operand；`rf0` 作目的 operand 是否合法按 `resolution.rule_tables.D11.rf0_write_whitelist`（十条）判定，白名单外的 RF destination 形式是ILLI 负例而不是接受项。`ftcls/focls immu6≠1` 按 `resolution.rule_tables.D17.classify_immediate`（assembler 阶段拒绝）判定。S1、S4～S6、S8 与全部数值语义不属于 MC 可证明范围，只须保持可追踪的 BLOCKED/NA，不能由 LLVM 行为填空。

## D17 OPEN-ID ledger 与 LLVM 边界

`D17 OPEN-ID ledger` 的完整 marker：active 精确键集合为 {D17:S1,D17:S3,D17:S4,D17:S5,D17:S6,D17:S8}（六键），分别对应 reset、classify immediate、fault priority、scaleB exponent、SBZ write、ldm/stm memory。LLVM MC 对 `D17:S1`、`D17:S4`、`D17:S5`、`D17:S6`、`D17:S8` 一律为 `N/A(runtime)`，不得以 assemble/disassemble PASS 解锁；仅 `D17:S3` 影响 assembler legality，在 ADR-1015 Accepted 前保持 blocked。`D17:S2` 始终是 ledger 外 trace-only（`no behavioral consequence; resolved/trace-only; not in D17 OPEN-ID ledger; never PASS`），不是缺口；`D17:S7` 始终是 ADR-1008 D1 已证明的 spec-determined non-gap（move overlap 由 SimRISC-00:41-46 与 SimRISC-03:34-50 唯一确定），不进入 active ledger、不计 OPEN/BLOCKED、不计 PASS。rf0 layout/register encoding 可在 `SPEC-102t re-Accepted` 后实现，但 reset/SBZ/运行时行为不在 LLVM 所有权内。当前补丁边界/hash 静态核对可跑，MC 动态验收仍 BLOCKED 于实现/build。

## SPEC-104t 已投影的适用规则

语义激活门禁：`SPEC-104t` 已验证，且本任务所消费的 ADR-1009～1015 全部 Accepted；在此之前 `contracts/f1_gap_proofs.yaml` 的 `resolution` 层只表示 projected-pending-activation，不得当作 active implementation truth，也不得据此声称任何 facet PASS。

本任务只消费其中**编码与 assembler legality**这一层，运行语义一律 `N/A(runtime)`：

| 规则 | `resolution` 投影位置 | 本任务必须实现的精确内容 |
| --- | --- | --- |
| rf0 作为寄存器 | `rule_tables.D11.rf0_read` / `rf0_write_whitelist` | 全部 64 个 identity 均可把 rf0 作源 operand；十条白名单（`ld.t-rf,ld.o-rf,ldm.t-rf,ldm.o-rf,set.w-rf,cs.eq-rf,cs.ne-rf,cs.n-rf,cs.z-rf,cs.p-rf`）可作目的 operand；白名单外的 RF destination 形式是 assembler 负例（ILLI），`rd2rf→rf0` 明确属负例 |
| D17:S3 classify immediate | `rule_tables.D17.classify_immediate` | `ftcls/focls immu6!=1` 在 assembler 阶段拒绝并给稳定诊断；非 assembler 路径到达硬件才是 ILLI（`classify_immediate_hardware`），两者不得混为一谈 |
| 六个 active OPEN-ID 的 MC 归属 | `consumer_activation` 中 LLVM-101t 的 `ledger_gate_projection` | `D17:S1`/`D17:S4`/`D17:S5`/`D17:S6`/`D17:S8` 为 `N/A(runtime)`，`D17:S3` 为 `projected-pending-activation`；`D17:S2`/`D17:S7` 不在 marker 里 |

assemble/disassemble PASS 只覆盖 encoding/printing；D12～D16 与 S1/S4/S5/S6/S8 的运行语义不在 LLVM 所有权内，不得由本任务声称 PASS。

## 验收

| # | 判据 | 可执行性 |
| --- | --- | --- |
| 1 | `llvm-mc` 接受 64 identity 的代表合法形式并给出 contract 字节 | **BLOCKED**：F1 MC 尚未实现/构建；替代证据为 SPEC 的 64 encoding 清单与 `INFRA-108t` 隔离入口 |
| 2 | `llvm-objdump` 对每个真实指令打印真实 mnemonic/operand，不打印 pseudo | **BLOCKED**：decoder/printer 尚未实现；替代证据为 canonical 输出合同 |
| 3 | 错 bank、已决的错 immediate、越界语法均有负例并稳定诊断 | **BLOCKED**：parser/负例尚未实现，且 S3 未决形式不得先断言；替代证据为已决/未决 legality 分栏 |
| 4 | LLVM patch 仅 0009+，M1 0001–0008 sha256 不变 | 现在可跑：可核对当前补丁目录和 `INFRA-108t` 冻结清单；实现后必须再次核对 |
| 5 | rf0 目的合法性与 S3 形式的最终接受/拒绝 | **BLOCKED**：等待 `SPEC-104t` 已验证且 ADR-1009/ADR-1015 Accepted 后复跑；替代证据为不依赖该形式的 MC 覆盖 + 十条白名单与 S3 负例清单 |

## 反例、还原与重建

验收枚举 lit/FileCheck、字节 oracle、patch-series checker。分别注入错误 opcode、交换 rf/rd operand class、移除一条 decoder、让 printer 输出 pseudo；确认 diff 非空且真实 FAIL。注入在 `/tmp/opencode/LLVM-101t/` 的隔离树；还原源码后必须重新构建受影响 target，再复跑，不能使用注入后的陈旧二进制。最终 F1 tree clean，M1 tree/hash 不变。

## 完成区

由 engineer 执行后填写；记录 patch 编号、64 计数、负例和重建复绿。
