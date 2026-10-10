#!/usr/bin/env python3
"""f1_contract_data.py — F1 浮点合约的**规范声明层**（唯一手写数据源）。

本模块只声明「**从 SimRISC-00/03 读到什么、以及读不到什么**」：
  * 每个 identity 的 facet 状态（`spec-determined` / `partial` / `open-blocked` / `n/a`）
  * 每个 identity 的 spec 明示合法性谓词与 `contracts/legality_rules.yaml` 规则 id
  * 每个 identity 的规范引用（encoding 引用来自 QFC 归属表，语义引用来自 SimRISC-03 小节）
  * D11–D17 的 identity×facet 映射，以及 **新发现的、D1–D18 之外的 spec 静默项**

明确**不在**本模块：
  * 编码（op/ha/mask/value/format/字段布局）——由 `f1_spec_extract.py` 从
    SimRISC-00 独立解析；本模块只按 identity 引用，不复制数值
  * 任何 OPEN 项的**取值**。D11–D17 一律保持 OPEN/BLOCKED（ADR-1004 已 Accepted 的
    暂缓决定），spec 静默项只登记原文与受影响 identity，**不发明结论**
  * 候选 ADR-1005/1006/1007 的 decision——它们只能是 Candidate，decision 文本由
    用户逐条确认后写；本模块只提供「证据输入」

渲染与校验：
  * `f1_render_contract.py` 渲染 `.xkw/knowledge/contract-f1-floating.md` 的
    identity 表 + D11–D17 矩阵，并给 `contracts/opcodes.yaml` 的 64 条记录加 `f1:` 块
  * `check_f1_contract.py` 反向校验已落盘的产物与本模块 + spec 一致
"""

from __future__ import annotations

# ───────────────────────── facet 词表 ─────────────────────────

#: 逐 identity 必填的 facet 键（顺序即合约与 YAML 中的呈现顺序）
FACETS = (
    "encoding",            # QFC 编码（op/ha/mask/value/字段布局）
    "format",              # 操作数格式字母 + 操作数签名
    "operands",            # 操作数名、角色、bank
    "legality",            # 规范明示的合法性/异常谓词
    "semantics",           # 指令主语义
    "rf0_operand",         # rf0 作目的/源操作数的规则           → D11
    "tetra_high_half",     # 单精结果写入 rf 后的高 32 位         → D13
    "fcsr_flags",          # rf0[4:0] 的设置/保持/清除            → D12
    "tininess",            # 下溢 tininess 时点与复合 flags       → D16
    "compare_unordered",   # 比较 unordered 写入 rd 的 NaN 位型    → D14
    "nan_propagation",     # NaN payload/符号/quieting/默认 NaN   → D15
)

#: facet 状态枚举
STATUS_SPEC = "spec-determined"   # 规范给出唯一答案
STATUS_PARTIAL = "partial"         # 规范给出部分答案，剩余部分规范未规定
STATUS_OPEN = "open-blocked"      # 规范未给唯一答案 → 阻塞，登记到 ADR-1004 D*
STATUS_NA = "n/a"                 # 该 facet 对本 identity 不适用

STATUSES = frozenset({STATUS_SPEC, STATUS_PARTIAL, STATUS_OPEN, STATUS_NA})

#: 呈现顺序（`STATUSES` 是 frozenset，无序；渲染/校验一律用本元组）
STATUS_ORDER = (STATUS_SPEC, STATUS_PARTIAL, STATUS_OPEN, STATUS_NA)

#: facet → ADR-1004 中「暂缓」的 decision 号
FACET_DECISION = {
    "rf0_operand": "D11",
    "fcsr_flags": "D12",
    "tetra_high_half": "D13",
    "compare_unordered": "D14",
    "nan_propagation": "D15",
    "tininess": "D16",
}

#: D11–D17（ADR-1004 已 Accepted 的 OPEN/BLOCKED 清单）
DECISIONS = tuple(f"D{i}" for i in range(11, 18))

# ───────────────────────── 语义分组（按 SimRISC-03 小节 + SimRISC-00 QFC） ─────────────────────────
# 分组用**裸助记符**书写；`f1_contract_data.identity_groups()` 负责与
# `f1_spec_extract.extract()` 的 64 条 identity 做集合对齐并 fail-closed 校验。

ACCESS_RF = ("ld.t", "st.t", "ld.o", "st.o", "ldm.t", "stm.t", "ldm.o", "stm.o")
BLOCK_COPY = ("rd2rf", "rf2rd")
IMM_SET = ("set.w",)
FMA = ("ftmadd", "fomadd")
CS_ASSIGN = ("cs.eq", "cs.ne", "cs.n", "cs.z", "cs.p")

CONV_F2F = ("ft2fo", "fo2ft")
CONV_F2I = ("ft2it", "ft2io", "ft2ut", "ft2uo",
            "fo2it", "fo2io", "fo2ut", "fo2uo")
CONV_I2F = ("it2ft", "io2ft", "ut2ft", "uo2ft")
CONV_I2F_O = ("it2fo", "io2fo", "ut2fo", "uo2fo")
CONV_MOVE = ("ft2ft", "fo2fo")
CONV = CONV_F2F + CONV_F2I + CONV_I2F + CONV_I2F_O + CONV_MOVE

CLS = ("ftcls", "focls")
ROOTLOG_SQRT = ("ftroot", "foroot")
ROOTLOG_LOG = ("ftlog", "folog")
ROOTLOG = ROOTLOG_SQRT + ROOTLOG_LOG

ARITH = ("ftadd", "ftsub", "ftmul", "ftdiv", "ftrem", "ftsclb",
         "foadd", "fosub", "fomul", "fodiv", "forem", "fosclb")
SGN = ("ftsgnj", "ftsgnn", "fosgnj", "fosgnn")
CMP = ("ftqcmp", "ftscmp", "foqcmp", "foscmp")

ARITH_FT = ("ftadd", "ftsub", "ftmul", "ftdiv", "ftrem", "ftsclb")
SGN_FT = ("ftsgnj", "ftsgnn")
ROOTLOG_FT = ("ftroot", "ftlog")

#: 会产生**舍入数值结果**（可触发 OF/UF/NX）的 identity —— D16 tininess 的受影响集
D16_SET = CONV_F2F + CONV_F2I + CONV_I2F + CONV_I2F_O + ARITH + FMA + ROOTLOG
#: 会**执行浮点运算/转换/分类/比较/条件赋值**的 identity —— D12 fcsr_flags 的受影响集
D12_SET = CONV + CLS + ROOTLOG + ARITH + SGN + CMP + FMA + CS_ASSIGN
#: rf0 作操作数未被规范唯一裁定的 identity —— D11 的受影响集
D11_SET = SGN + CONV + CLS + CMP + CS_ASSIGN + BLOCK_COPY
#: 写入**单精（ft）结果**到 rf 槽位的 identity —— D13 的受影响集
D13_SET = (("fo2ft",) + CONV_I2F + CONV_MOVE[:1] + ARITH_FT + SGN_FT + ROOTLOG_FT
           + ("ld.t", "ldm.t"))
#: NaN 结果的 payload/符号/quieting 未被唯一规定 —— D15 的受影响集
D15_SET = ARITH + FMA + ROOTLOG
#: NaN 行为被部分规定（仅「传播 payload」）—— D15 的 partial 集
D15_PARTIAL = CONV_F2F
#: 比较 unordered 写入 rd 的位型未规定 —— D14 的受影响集
D14_SET = CMP

#: rf0 作**目的**被规范明示允许（rf ld/st + set.w）—— D11 判定为 spec-determined
D11_DETERMINED = ACCESS_RF + IMM_SET
#: 规范 §浮点运算指令 明确覆盖、一般 rf0→ILLI 规则可直接适用（sign 特例除外）—— D11 spec-determined
D11_SPEC_RULE = ARITH + FMA + ROOTLOG

# ───────────────────────── 合法性谓词词表 ─────────────────────────

#: 谓词 → `contracts/legality_rules.yaml` 的规则 id（None = 非 fault 规则，只在合约说明）
LEGALITY_REFS = {
    "aligned(4)": "fp_malign_rf",
    "aligned(8)": "fp_malign_rf",
    "immu6_zero_illi": "fp_block_immu6_zero",
    "immu6_1_63": "fp_block_immu6_zero",
    "block_range_overflow_illi": "fp_block_range_overflow",
    "rf_slot_overflow_illi": "fp_rf_slot_overflow",
    "rd_dest_not_rd0": "rd_dest_rd0",
    "rootn_n_in_2_3": "fp_root_invalid_n",
    "log_base_in_0_1_2": "fp_log_invalid_base",
    "rf0_dst_allowed": None,          # 写掩码规则，不是 fault；见合约 §3
    "immu6_1_for_cls": None,          # 规范未规定非法值行为 → 静默项 S3
}

LEGALITY_PREDICATES = tuple(LEGALITY_REFS)


def _merge_preds(table, mnemonics, *names):
    """**合并**（不是覆盖）一批合法性谓词。

    同一个助记符往往被**多条互相独立**的规范事实约束，例如 `ldm.t` 同时有
      * SimRISC-03:25 的 4 字节对齐（`aligned(4)`）
      * SimRISC-03:7  的「rf0 为目的允许」（`rf0_dst_allowed`）
      * SimRISC-03:29-31 的三条 ILLI 谓词

    历史缺陷：这些批次曾用 `dict.update()` **顺序写入**，后写的整段**覆盖**先写的
    结果 —— `ld.t`/`ld.o`/`ldm.t`/`ldm.o`/`stm.t`/`stm.o` 因此**静默丢掉**了
    `aligned(4)`/`aligned(8)`（以及随之而来的 `fp_malign_rf` 引用），而数据层、
    落盘 YAML、合约 md 三层**自洽地一起错**，`--check` 与三层自洽检查全绿。
    对齐事实的权威是 SimRISC-03:25（**对全部 8 条 RF 存取无条件要求**），不是
    「哪一批最后写」，所以必须累加。

    语义：按声明顺序追加，已存在的谓词不重复（去重但保序）。
    """
    for m in mnemonics:
        cur = table.setdefault(m, [])
        for n in names:
            if n not in cur:
                cur.append(n)
    return table


#: 逐助记符的 spec 明示合法性谓词（只写规范**明说**的；不写规范没说的限制）
LEGALITY_BY_MNEMONIC = {}
# SimRISC-03:25 —— 对**全部 8 条** RF 存取（tetra 4 字节 / octa 8 字节）
# 要求对齐，未对齐触发 MALIGN。**先**声明这一批，后续批次只做累加。
_merge_preds(LEGALITY_BY_MNEMONIC, ("ld.t", "st.t", "ldm.t", "stm.t"), "aligned(4)")
_merge_preds(LEGALITY_BY_MNEMONIC, ("ld.o", "st.o", "ldm.o", "stm.o"), "aligned(8)")
# SimRISC-03:7 —— rf ld/st（及 set.w）以 rf0 为目的允许（写掩码规则，非 fault）
_merge_preds(LEGALITY_BY_MNEMONIC, ("ld.t", "ld.o", "ldm.t", "ldm.o", "set.w"),
             "rf0_dst_allowed")
# SimRISC-03:29-31 —— ldm/stm 的三条 ILLI 谓词
_merge_preds(LEGALITY_BY_MNEMONIC, ("ldm.t", "stm.t", "ldm.o", "stm.o"),
             "immu6_zero_illi", "block_range_overflow_illi", "rf_slot_overflow_illi")
# SimRISC-03:48-49（块赋值）/ :132-133（格式转换）—— immu6 计数类
_merge_preds(LEGALITY_BY_MNEMONIC, BLOCK_COPY,
             "immu6_zero_illi", "block_range_overflow_illi", "immu6_1_63")
_merge_preds(LEGALITY_BY_MNEMONIC, CONV,
             "immu6_zero_illi", "block_range_overflow_illi", "immu6_1_63")
# SimRISC-00:55 —— 目的 rd 为 rd0 触发 ILLI
_merge_preds(LEGALITY_BY_MNEMONIC, CONV_F2I, "rd_dest_not_rd0")
_merge_preds(LEGALITY_BY_MNEMONIC, CLS, "immu6_1_for_cls", "rd_dest_not_rd0")
_merge_preds(LEGALITY_BY_MNEMONIC, CMP, "rd_dest_not_rd0")
# SimRISC-03:188 / :192 —— root 的 n 值、log 的底值
_merge_preds(LEGALITY_BY_MNEMONIC, ROOTLOG_SQRT, "rootn_n_in_2_3")
_merge_preds(LEGALITY_BY_MNEMONIC, ROOTLOG_LOG, "log_base_in_0_1_2")

# ───────────────────────── 语义引用（SimRISC-03 小节） ─────────────────────────

#: 裸助记符 → SimRISC-03 小节标题（用于 f1.spec_cite；编码引用由 QFC 归属表给出）
SEMANTIC_SECTION = {}
SEMANTIC_SECTION.update({m: "存取RF寄存器" for m in ACCESS_RF})
SEMANTIC_SECTION.update({m: "寄存器组之间块赋值" for m in BLOCK_COPY})
SEMANTIC_SECTION.update({m: "立即数常数赋值：Immediate constant" for m in IMM_SET})
SEMANTIC_SECTION.update({m: "格式转换指令" for m in CONV})
SEMANTIC_SECTION.update({m: "浮点分类指令" for m in CLS})
SEMANTIC_SECTION.update({m: "S1D1" for m in ROOTLOG})
SEMANTIC_SECTION.update({m: "S2D1" for m in ARITH})
SEMANTIC_SECTION.update({m: "浮点符号位操作指令" for m in SGN})
SEMANTIC_SECTION.update({m: "浮点比较指令" for m in CMP})
SEMANTIC_SECTION.update({m: "S3D1" for m in FMA})
SEMANTIC_SECTION.update({m: "浮点条件赋值指令" for m in CS_ASSIGN})

#: SimRISC-00 QFC 子表 → 小节标题（编码引用）
QFC_SECTION = {
    None: "SimRISC QFC",
    "MISC-AMO": "MISC-AMO 指令编码",
    "MISC-octa": "MISC-octa指令编码",
    "MISC-tetra": "MISC-tetra指令编码",
    "MISC-wyde": "MISC-wyde指令编码",
    "MISC-byte": "MISC-byte指令编码",
    "MISC-RF": "MISC-RF指令编码",
}

# ───────────────────────── 规范静默项（D1–D18 之外的新发现，不作决策） ─────────────────────────

SPEC_SILENT = (
    {
        "id": "S1",
        "topic": "rf0/FCSR 的复位值未定义",
        "quotes": [
            "spec/SimRISC-00-指令系统设计.md:82-86 给出 rf0 全部位域、舍入模式表与"
            "异常状态表，但未给出 rf0 的复位值。",
            "spec/SimRISC-00-指令系统设计.md:62 「硬件复位后 `rb0` 初值为 "
            "`cfx_power_hypv_excp_vector`」、:55 「`rd0` 固定为 0，只读」、"
            ":120 「ra0 …初始值应为 0」——同类寄存器均给了初值，rf0 没有。",
        ],
        "affected": "全部 64 个 identity（首条浮点指令执行前的 rf0 舍入模式与 flags 初始值）",
        "decision": "未决。F1 需要的「rf0/FCSR 布局和复位」中，布局可由 SimRISC-00 推出，"
                    "复位值不可推出；不发明初值。",
    },
    {
        "id": "S2",
        "topic": "「有效范围 1~63」只出现在块赋值/格式转换节，未出现在存取 RF 节"
                 "（表述不一致，但**无行为后果**）",
        "quotes": [
            "spec/SimRISC-03-浮点类指令.md:44 「`immu6` …用来指定寄存器的个数，"
            "有效范围为1~63」（寄存器组之间块赋值）、:126 「immu6 指定连续转换的"
            "寄存器数量（1-63）」（格式转换）。",
            "spec/SimRISC-03-浮点类指令.md:29-31 的 §存取RF寄存器 只列了三条 ILLI 谓词"
            "（immu6=0、任一起始寄存器+immu6>64、rfha+immu6>64），**未**复述 1~63。",
            "spec/SimRISC-00-指令系统设计.md:191 「`rrri`：…一个6位立即数在 `hd[5:0]`」"
            "——immu6 只有 6 位，编码上限即 63。",
        ],
        "affected": "ldm.t-rf、stm.t-rf、ldm.o-rf、stm.o-rf（表述层面）",
        "decision": "**不是缺口**：immu6 上限 63 由位宽唯一决定，immu6=0 另有 ILLI 规则，"
                    "故 §存取RF 与另两节的**有效范围完全一致**（1~63），无行为差异。"
                    "合约因此**不**为 ldm/stm 追加 `immu6_1_63` 谓词，"
                    "`legality` facet 也不因此记 partial。本项仅作表述不一致登记。",
    },
    {
        "id": "S3",
        "topic": "ftcls/focls 的 immu6≠1 未规定合法性",
        "quotes": [
            "spec/SimRISC-03-浮点类指令.md:270-271 只给出签名 `ftcls   rdhb, rfhc, 1`、"
            "`focls   rdhb, rfhc, 1`，未说明 immu6 取其它值时的行为。",
        ],
        "affected": "ftcls、focls",
        "decision": "未决。不发明 fault 类型。",
    },
    {
        "id": "S4",
        "topic": "多个条件同时成立时的异常优先级未规定",
        "quotes": [
            "spec/SimRISC-03-浮点类指令.md:25 「未对齐触发 MALIGN 异常」与 :29-31 的"
            " ILLI 谓词并列，未给先后；:188 「不支持的 n 值触发 ILLI 异常」与 :7 的"
            " rf0→ILLI 规则并列，也未给先后。",
        ],
        "affected": "同时满足两个以上规范的 fault 条件的所有 identity（合约 §3.2 逐条列出）",
        "decision": "未决。合约 §3.2 只列「本 identity 可触发的 fault 集合」，不排序。",
    },
    {
        "id": "S5",
        "topic": "ftsclb/fosclb 中「rfhd 取整数值」有两种读法",
        "quotes": [
            "spec/SimRISC-03-浮点类指令.md:163 「计算 `rfhc × 2^rfhd`（rfhd 取整数值）」。",
            "读法 A：rfhd 的值按整数解释（IEEE 754 scaleB 要求 b 为整数）；"
            "读法 B：对 rfhd 做截断取整。规范未说明 rfhd 非整数值时取哪种。",
        ],
        "affected": "ftsclb、fosclb",
        "decision": "未决。facet 记 partial，不发明取整方式。",
    },
    {
        "id": "S6",
        "topic": "rf0 的 SBZ 域被写入时的行为未规定",
        "quotes": [
            "spec/SimRISC-03-浮点类指令.md:7 「写只读位时静默忽略，rw 位正常写入」"
            "——只覆盖 [63..51] 与 [31..22] 两个只读域；[50..32]、[21..18]、[15..5] "
            "标为 SBZ，SBZ 被写入时的行为未写。",
            "contracts/legality_rules.yaml 现行 `sbz_nonzero` 规则把 SBZ 非零冻结为 ILLI"
            "（ADR-0004 D5.3，架构自定义）；F1 是否沿用未决。",
        ],
        "affected": "以 rf0 为目的可写的 identity：ld.t-rf、ld.o-rf、ldm.t-rf、ldm.o-rf、"
                    "set.w-rf、rd2rf（immu6 覆盖到 rf0 时）",
        "decision": "未决。合约只登记只读域掩码，SBZ 写入行为留待决策。",
    },
    {
        "id": "S7",
        "topic": "rd2rf/rf2rd 源与目的寄存器范围重叠时的读写顺序未规定",
        "quotes": [
            "spec/SimRISC-03-浮点类指令.md:126 格式转换节明示「转换按序号递增逐对进行，"
            "先读后写。重叠时行为依赖顺序，使用者应避免在同一寄存器同时出现在源和目的中」。",
            "spec/SimRISC-03-浮点类指令.md:43 块赋值节只写「将 hc 开始的 immu6 个寄存器"
            "复制到 hb 开始的 immu6 个寄存器中」，未规定重叠时的读写顺序。",
        ],
        "affected": "rd2rf、rf2rd",
        "decision": "未决。不把格式转换节的「先读后写」外推到块赋值节。",
    },
    {
        "id": "S8",
        "topic": "ldm/stm 的内存侧寻址、步长与重叠读写顺序未在 SimRISC-03 规定",
        "quotes": [
            "spec/SimRISC-03-浮点类指令.md:19-22 给出 `ldm.t rfha, rbhb, rdhc, immu6` 等"
            "签名，:25 给出对齐要求，:29-31 给出三条 ILLI 谓词——**只字未提**内存侧"
            "第 i 个元素访问哪个地址、步长是多少、rbhb+rdhc 如何组合。",
            "spec/SimRISC-03-浮点类指令.md:35 「块传输过程中不进行数据类型的转换，保持64位"
            "二进制不变，但是必需是多个连续的寄存器」只说**寄存器**连续，未说**地址**连续。",
            "对照：spec/SimRISC-01-*.md:59-61、:67 对 RD 侧 ldm/stm 明写「分别存放到以 rb2 "
            "为基址的 8 字节连续地址中」「范围包括 rdhc 时地址计算仍按原始 rdhc 进行」"
            "「装入类源/目的范围可重叠，按序号递增逐对先读后写」——但 SimRISC-01 "
            "**不在 F1 的权威集内**（§0），不能拿来替 RF 侧补齐。",
        ],
        "affected": "ldm.t-rf、ldm.o-rf、stm.t-rf、stm.o-rf",
        "decision": "未决。合约只登记签名、对齐与三条 ILLI 谓词，**不**从 SimRISC-01 "
                    "外推地址组合/步长/重叠顺序。本项只落在 `semantics` facet"
                    "（4 条 ldm/stm 记 **partial**）。`legality` facet **不**因 S2 或 "
                    "S8 记 partial：S2 已证明 §存取RF 的有效范围与另两节一致（无行为"
                    "后果，见 S2 处置），S8 缺的是**内存侧语义**、不是合法性谓词；"
                    "故这 4 条的 `legality` 仍是 spec-determined。内存侧语义缺口不在 "
                    "D11–D17 范围内，登记为 F1 实现前必须补的规范项。",
    },
)

SPEC_SILENT_IDS = tuple(s["id"] for s in SPEC_SILENT)

# ───────────────────────── D17 OPEN-ID ledger（下游门禁输入，**不等于语义已决**）─────────────────────────
#
# 权威来源（**不是**本模块自创）：
#   * `.xkw/tasks/spec/SPEC-101k-*.md` §「D17 OPEN-ID 台账与 scope/facet 状态矩阵」
#     —— 给出台账名 `D17 OPEN-ID ledger`、精确键集合、状态词 `O`/`A`/`R`/`N/A(runtime)`
#        以及「rf0 字段布局/可观测 mask 是 `A`、复位值是 `D17:S1 = O`，两者不得合并」。
#   * `.xkw/tasks/spec/SPEC-102t-*.md` §「后续任务消费要求」—— 给出 ledger 精确键集合、
#     `D17:S2` 的 ledger 外注记、以及 layout/reset、SBZ 写入必须分栏的要求。
#
# 硬边界（AGENTS.md「Spec-first」+ ADR-1004 D17 + 任务书「不得把 OPEN 写成确定规则」）：
#   * 本 ledger **只登记**「规范未给唯一答案」这一事实、受影响面与下游消费者；
#     **不**给出任何行为取值、expected、fault 顺序或 decision 结论；
#   * `status` 只能是 `OPEN` / `BLOCKED`。`PASS` / `active` / `spec-determined` /
#     `resolved` 一律非法（后者只在 `D17:S2` 的 trace-only 注记里作为**描述词**出现）；
#   * `facet` 指向**被该项阻塞的合约 facet**（11 个之一）。它**不**、也**不得**改动任何
#     identity 的 facet 状态归属 —— 归属由 `PINNED_OPEN` / `PINNED_PARTIAL` 钉死
#     （见 `check_f1_contract.py` 的 D7）。ledger 记「未决项」，facet 记「规范明说规则
#     的归属」，两者正交：例如 `D17:S6`（SBZ 写入）落在 `legality` 面，但这 6 条的
#     `legality` 谓词本身仍是 spec-determined —— 谓词是规范明说的，**写入行为**不是。
#   * `closure` 是**占位符**，由 `SPEC-103t` 逐键证明 + 用户逐 decision 确认后回填。
#     本任务**不**回填，也**不**预设取值。

#: ledger 行的合法状态词（顺序即渲染顺序）
D17_LEDGER_STATUSES = ("OPEN", "BLOCKED")

#: ledger 的**精确**键集合。`D17:S2` 刻意缺席 —— 它只是 ledger 外的来源追踪。
D17_LEDGER_IDS = ("D17:S1", "D17:S3", "D17:S4", "D17:S5",
                  "D17:S6", "D17:S7", "D17:S8")

#: ledger **外**的 `D17:S2` 来源追踪注记。逐字渲染，4 个子句缺一不可，
#: 由 `check_f1_contract.py` 的 I3 逐子句核对。
D17_S2_TRACE_NOTE = ("no behavioral consequence; resolved/trace-only; "
                     "not in D17 OPEN-ID ledger; never PASS")

#: `D17_S2_TRACE_NOTE` 的 4 个必被子句（fail-closed 判据，逐条核对）：
#: ①无行为后果 ②已解决/仅溯源 ③不在 ledger 内 ④永不记 PASS。
D17_S2_TRACE_CLAUSES = (
    "no behavioral consequence",
    "resolved/trace-only",
    "not in D17 OPEN-ID ledger",
    "never PASS",
)

#: 关闭证据占位符（**逐字**渲染、逐字核对；本任务不回填任何取值）
D17_CLOSURE_PLACEHOLDER = ("占位：待 `SPEC-103t` 逐键证明 + 用户逐 decision 确认后回填"
                           "（本任务不填取值、不选方案）")

#: 受影响范围的两种**合法**写法：
#:   * `("ids", 裸助记符, ...)` —— 显式点名。存**裸助记符**（与
#:     `SPEC_SILENT_MNEMONICS` 同一命名空间，便于 H3 逐键核对），渲染时由
#:     `f1_render_contract.region_d17_ledger(ex)` 经 `spec/` 独立解析出的
#:     助记符→identity 表换成 64 条 identity 里的**实名**。空列表**非法**。
#:   * `("scope", "all-64" | "multi-fault")` —— 范围式，与 §7.1 的「**受影响**」行同义。
#: 刻意**不**为 S4 编造一个 identity 列表：S4 的范围是「同时满足两个以上规范 fault
#: 谓词」这一**条件**（§7.1 S4 与 `SPEC_SILENT_MNEMONICS["S4"] == "ALL"` 已经这样登记，
#: H3 会核对），把它收窄成某个具体清单就是发明。
D17_LEDGER = (
    {
        "id": "D17:S1",
        "silent": "S1",
        "status": "BLOCKED",
        "topic": "rf0/FCSR **复位值**未规定（布局/可观测 mask **不**并入本项）",
        "spec_cite": "SimRISC-00:82 / SimRISC-00:86 / SimRISC-03:7",
        "affected": ("scope", "all-64"),
        "affected_text": "全部 64（首条浮点指令执行前的 rf0 舍入模式与 flags 初始值）",
        "facet": "fcsr_flags",
        "consumers": ("SPEC-103t", "TESTCASES-101t", "TESTCASES-102t",
                      "QEMU-101t", "QEMU-102t", "QEMU-103t",
                      "INTEG-102t", "INTEG-103t", "INTEG-104m"),
    },
    {
        "id": "D17:S3",
        "silent": "S3",
        "status": "BLOCKED",
        "topic": "`ftcls`/`focls` 的 `immu6`≠1（classify immediate）合法性未规定",
        "spec_cite": "SimRISC-03:270 / SimRISC-03:271",
        "affected": ("ids", "ftcls", "focls"),
        "affected_text": None,          # None = 由 id 列表自动渲染
        "facet": "legality",
        "consumers": ("SPEC-103t", "TESTCASES-101t", "TESTCASES-102t",
                      "LLVM-101t", "QEMU-103t",
                      "INTEG-102t", "INTEG-103t", "INTEG-104m"),
    },
    {
        "id": "D17:S4",
        "silent": "S4",
        "status": "BLOCKED",
        "topic": "多个 fault 条件同时成立时的**异常优先级**未规定",
        "spec_cite": "SimRISC-03:25 / SimRISC-03:29 / SimRISC-03:7",
        "affected": ("scope", "multi-fault"),
        "affected_text": "同时满足两个以上规范 fault 谓词的所有 identity（逐条见 §3.2）",
        "facet": "legality",
        "consumers": ("SPEC-103t", "TESTCASES-101t", "TESTCASES-102t",
                      "QEMU-101t", "QEMU-102t", "QEMU-103t",
                      "INTEG-102t", "INTEG-103t", "INTEG-104m"),
    },
    {
        "id": "D17:S5",
        "silent": "S5",
        "status": "BLOCKED",
        "topic": "`ftsclb`/`fosclb` 的 scaleB 指数「`rfhd` 取整数值」有两种读法",
        "spec_cite": "SimRISC-03:163",
        "affected": ("ids", "ftsclb", "fosclb"),
        "affected_text": None,
        "facet": "semantics",
        "consumers": ("SPEC-103t", "TESTCASES-101t", "TESTCASES-102t",
                      "QEMU-102t", "INTEG-102t", "INTEG-103t", "INTEG-104m"),
    },
    {
        "id": "D17:S6",
        "silent": "S6",
        "status": "BLOCKED",
        "topic": "rf0 的 **SBZ 域被写入**时的行为未规定（**不指定**忽略/保留/清零/异常）",
        "spec_cite": "SimRISC-03:7 / SimRISC-00:83",
        "affected": ("ids", "ld.t", "ld.o", "ldm.t", "ldm.o",
                     "set.w", "rd2rf"),
        "affected_text": None,
        "facet": "legality",
        "consumers": ("SPEC-103t", "TESTCASES-101t", "TESTCASES-102t",
                      "QEMU-101t", "INTEG-102t", "INTEG-103t", "INTEG-104m"),
    },
    {
        "id": "D17:S7",
        "silent": "S7",
        "status": "BLOCKED",
        "topic": "`rd2rf`/`rf2rd` 源与目的范围**重叠**时的读写顺序未规定",
        "spec_cite": "SimRISC-03:43 / SimRISC-03:126",
        "affected": ("ids", "rd2rf", "rf2rd"),
        "affected_text": None,
        "facet": "semantics",
        "consumers": ("SPEC-103t", "TESTCASES-101t", "TESTCASES-102t",
                      "QEMU-101t", "INTEG-102t", "INTEG-103t", "INTEG-104m"),
    },
    {
        "id": "D17:S8",
        "silent": "S8",
        "status": "BLOCKED",
        "topic": "`ldm`/`stm` 的**内存侧**寻址、步长与重叠读写顺序未规定",
        "spec_cite": "SimRISC-03:25 / SimRISC-03:35",
        "affected": ("ids", "ldm.t", "ldm.o", "stm.t", "stm.o"),
        "affected_text": None,
        "facet": "semantics",
        "consumers": ("SPEC-103t", "TESTCASES-101t", "TESTCASES-102t",
                      "QEMU-101t", "INTEG-102t", "INTEG-103t", "INTEG-104m"),
    },
)

#: ledger 行的完整字段集合（渲染与检查共用；少一个字段即视为声明不完整）
D17_LEDGER_FIELDS = ("id", "silent", "status", "topic", "spec_cite",
                     "affected", "affected_text", "facet", "consumers")


def d17_ledger_by_silent():
    """`{S 编号: ledger 行}`。ledger 外项（S2）刻意不在其中。"""
    return {row["silent"]: row for row in D17_LEDGER}


def d17_ledger_ids_for(mnemonics):
    """某条 identity（按裸助记符）命中的 ledger 键集合（不含 `D17:S2`）。"""
    ms = set(mnemonics)
    return sorted(row["id"] for row in D17_LEDGER
                  if row["affected"][0] == "scope"
                  or (ms & set(row["affected"][1:])))

# ───────────────────────── 候选 ADR 的证据输入（只能 Candidate） ─────────────────────────
#
# 硬约束（AGENTS.md + ADR-1004 D17）：ADR-1005/1006/1007 只能是 **Candidate**。
# 本节只提供「证据输入」：相互冲突的原文、受影响 identity/facet、最小决策问题。
# **不含任何 decision 取值**——decision 必须由用户逐条确认后另行写 ADR。
# ADR-1005~1007 文件**不得**在本任务或任何 SPEC 任务中创建/标记 Accepted。

CANDIDATE_ADRS = (
    {
        "id": "ADR-1005",
        "title": "rf0 操作数冲突与 tetra 高半部",
        "covers": ("D11", "D13"),
        "conflicts": (
            "SimRISC-03:7「浮点运算指令的目的或任一源操作数为 rf0 时触发 **ILLI** 异常」"
            "vs SimRISC-03:215-216「当rfhd为rf0时，ftsgnj和fosgnj实现了 `abs(rfhc)` 操作／"
            "ftsgnn和fosgnn实现了 `-abs(rfhc)` 操作」——后者要求 rfhd=rf0 产生结果，"
            "前者要求同一编码触发 ILLI。",
            "SimRISC-03:7 的「浮点运算指令」在 SimRISC-03 的章节结构里只明确覆盖 "
            "§浮点运算指令（S2D1/S3D1/S1D1）；§格式转换指令、§浮点分类指令、"
            "§浮点比较指令、§浮点条件赋值指令、§寄存器组之间块赋值是否被该规则覆盖，"
            "规范未说明。",
            "SimRISC-03:7「rf ld/st 中 rf0 为目的时允许」只点名 rf ld/st；"
            "rd2rf/rf2rd 以 rf0 为目的或来源时的行为，两条规则都没点名。",
            "SimRISC-00:73「rf寄存器字长64位，当存放单精32位数据时，只使用低32位，"
            "**高32位不做特殊规定**」——单精结果写入 rf 后的高 32 位无规范答案。",
        ),
        "questions": (
            "Q5.1 rf0→ILLI 一般规则的适用范围是「§浮点运算指令 的 22 条」，"
            "还是「SimRISC-03 全部 64 条」？",
            "Q5.2 sign-injection 特例（rfhd=rf0 → abs/-abs）与 rf0→ILLI 一般规则冲突时，"
            "哪条优先？特例只对 ftsgnj/fosgnj/ftsgnn/fosgnn 生效，还是所有指令？",
            "Q5.3 rd2rf/rf2rd 目的或来源为 rf0 时，是允许（像 rf ld/st）还是 ILLI？",
            "Q5.4 写单精（ft）结果到 rf 槽位时，高 32 位是保留原值、清零，"
            "还是写入默认 NaN 位型？该规则是否也适用于 ld.t-rf/ldm.t-rf 的 4 字节载入？",
        ),
    },
    {
        "id": "ADR-1006",
        "title": "FCSR flags 的 sticky/清除与 tininess/复合 flags",
        "covers": ("D12", "D16"),
        "conflicts": (
            "SimRISC-00:86 只声明 [4..0] 是「异常状态（Accured exception）」；"
            "SimRISC-00:107「浮点指令执行后，异常状态位（NV/DZ/OF/UF/NX）由硬件按 "
            "IEEE 754 标准设置到 rf0[4:0]」——未说明是「置位（sticky OR）」还是"
            "「按本次结果整体写入」。",
            "规范全文没有「清除」条款：没有说明后续不产生异常的指令是否保留旧 flags，"
            "也没有说明软件如何（能否）清除 flags。",
            "SimRISC-03:7 说 rf0 的 rw 位「正常写入」，因此 ld/st/set.w 写 rf0 可直接改 "
            "flags；但「硬件自动置位」与「软件直接写入」的叠加顺序未规定。",
            "tininess（SimRISC-03:128 只说「下溢按舍入模式处理（设置 UF）」）的检测时点"
            "（舍入前/舍入后/仅精确下溢）未规定；UF/OF/NX 的复合置位规则也未规定。",
        ),
        "questions": (
            "Q6.1 rf0[4:0] 的硬件更新语义是 sticky OR（只置位不清零）还是每次整体写入？",
            "Q6.2 无异常指令执行后 flags 是否保持原值？",
            "Q6.3 flags 是否存在软件清除路径（`set.w`/ld/st 写 rf0 是否算清除）？",
            "Q6.4 tininess 检测时点：舍入前 / 舍入后 / 仅当结果精确且次正规？",
            "Q6.5 UF 与 NX、OF 与 NX 的复合置位组合规则？",
            "Q6.6 哪 53 条 identity 属于「浮点指令」（受 flags 规则约束）？"
            "数据搬移类（rf ld/st/ldm/stm、set.w、rd2rf/rf2rd）是否完全不受影响？",
        ),
    },
    {
        "id": "ADR-1007",
        "title": "比较 unordered 位型与 NaN 传播",
        "covers": ("D14", "D15"),
        "conflicts": (
            "SimRISC-03:237「NaN：unordered，Quiet Compare的结果为qNaN（符号位为0），"
            "Signaling Compare的结果为sNaN（符号位为0）」——只固定符号位为 0，"
            "指数/尾数（payload）位型未给。",
            "SimRISC-00:80/:82 给出 rf0 的 fo/ft 位型为「符号位为0，E为全1，尾数最高位为1」"
            "的 qNaN；规范未声明比较 unordered 的 NaN 是否等于该默认 NaN。",
            "SimRISC-03:128 只对浮点→浮点转换说「NaN 传播 payload」，对多操作数运算"
            "（ftadd/ftmul/… 与 ftmadd/fomadd）未说 payload/符号/quieting 的选择规则。",
            "SimRISC-03:128「sNaN 作为算术输入时设置 NV 并返回 qNaN」——"
            "「返回 qNaN」未指定是 quieting 后的输入 NaN 还是默认 qNaN。",
        ),
        "questions": (
            "Q7.1 unordered 比较写入 rd 的 qNaN/sNaN 精确位型（E 与 payload）？"
            "是否等于 rf0 中的默认 NaN 位型？",
            "Q7.2 多操作数运算中出现多个 NaN 时的选择规则（第一个？quiet 优先？符号？）？",
            "Q7.3 sNaN 输入时返回的 qNaN 是 quieting 后的输入 NaN，还是默认 qNaN？",
            "Q7.4 哪些 18 条 identity 的 NaN 行为受阻（ARITH 12 + FMA 2 + root/log 4）？"
            "「NaN 传播 payload」是否适用于 fo2ft/ft2fo（partial）？",
        ),
    },
)

#: 非 S* 的附注：规范**明示「不做要求」**的行为，不是缺口，也不阻塞。
#: 同样只登记原文，不发明结论。
EXTRA_NOTES = {
    "rootn(-0,2)": (
        "spec/SimRISC-03-浮点类指令.md:190「在 IEEE754-2019 中特意指出，"
        "`rootn(-0, 2)` 不等于 `squareRoot(-0)`，因此，对于 `rootn(-0, 2)` 的运算结果"
        "不做具体要求」——规范明示不要求实现该结果，facet semantics 记 partial，"
        "不构成待决策缺口。"
    ),
}

#: 规范静默项编号 → 受影响的助记符（用于逐 identity 挂 note；`ALL` 表示全体）
SPEC_SILENT_MNEMONICS = {
    "S2": ("ldm.t", "stm.t", "ldm.o", "stm.o"),
    "S3": ("ftcls", "focls"),
    "S5": ("ftsclb", "fosclb"),
    "S6": ("ld.t", "ld.o", "ldm.t", "ldm.o", "set.w", "rd2rf"),
    "S7": ("rd2rf", "rf2rd"),
    "S8": ("ldm.t", "stm.t", "ldm.o", "stm.o"),
    "S1": "ALL",
    "S4": "ALL",
}

#: `set.w` 的 wyde-position → rf 位域映射。**由规范唯一确定**：
#: SimRISC-03:69-70 给出 `set.fo rf1, 0x3FF0000000000000` → `set.w rf1, wp3, 0x3FF0`
#: （0x3FF0 落在常量高 16 位），:78-79 给出 `set.ft rf1, 0x3F800000` →
#: `set.w rf1, wp1, 0x3F80` + `set.w rf1, wp0, 0x0000`（0x3F80 落在高 16 位）。
#: 两条示例共同唯一确定 wp0/wp1/wp2/wp3 = [15:0]/[31:16]/[47:32]/[63:48]，
#: 且与 SimRISC-00:88「舍入模式的设置单独放在 wp1 中」自洽（rf0[17:16] ⊂ [31:16]）。
SETW_WP_MAP = (
    ("wp0", "[15:0]", "immu16_lo 所在的 16 位段"),
    ("wp1", "[31:16]", "immu16 段；**rf0 的舍入模式 rf0[17:16] 在此段**"),
    ("wp2", "[47:32]", "immu16 段"),
    ("wp3", "[63:48]", "immu16 段"),
)

# ───────────────────────── 逐 identity 派生 ─────────────────────────

def _as_set(items):
    if items == "ALL":
        return None
    return set(items)


def identity_groups(rows):
    """把本模块的助记符分组解析成 identity 集合。

    `rows` 是 `f1_spec_extract.extract()["rows"]`（64 条）。对每条记录取
    `mnemonic` 归入分组；出现「分组里有、64 条里没有」或反之即 fail-closed。
    """
    by_mnem = {r["mnemonic"]: r["insn"] for r in rows}
    all_mnem = set(by_mnem)
    out = {}
    for name, members in (
        ("ACCESS_RF", ACCESS_RF), ("BLOCK_COPY", BLOCK_COPY), ("IMM_SET", IMM_SET),
        ("FMA", FMA), ("CS_ASSIGN", CS_ASSIGN), ("CONV", CONV), ("CLS", CLS),
        ("ROOTLOG", ROOTLOG), ("ARITH", ARITH), ("SGN", SGN), ("CMP", CMP),
    ):
        missing = set(members) - all_mnem
        if missing:
            raise ValueError(f"分组 {name} 含 64 条 identity 之外的助记符: {sorted(missing)}")
        out[name] = {by_mnem[m] for m in members}
    covered = set().union(*out.values())
    covered_mnem = {r["mnemonic"] for r in rows if r["insn"] in covered}
    if covered_mnem != all_mnem:
        raise ValueError(
            "分组未覆盖全部 64 个 identity；未覆盖: "
            f"{sorted(all_mnem - covered_mnem)}，多余: {sorted(covered_mnem - all_mnem)}")
    return out


def _derive(rows):
    """派生每个 identity 的 f1 声明（facets / legality / notes / 引用）。"""
    g = identity_groups(rows)
    insn_of = {r["mnemonic"]: r["insn"] for r in rows}

    def S(group):
        return g[group]

    conv = S("CONV")
    conv_f2f = {insn_of[m] for m in CONV_F2F}
    conv_i2f = {insn_of[m] for m in CONV_I2F}
    conv_move = {insn_of[m] for m in CONV_MOVE}
    arith = S("ARITH")
    arith_ft = {insn_of[m] for m in ARITH_FT}
    sgn = S("SGN")
    sgn_ft = {insn_of[m] for m in SGN_FT}
    rootlog = S("ROOTLOG")
    rootlog_ft = {insn_of[m] for m in ROOTLOG_FT}
    cls = S("CLS")
    cmp_ = S("CMP")
    fma = S("FMA")
    cs = S("CS_ASSIGN")
    access = S("ACCESS_RF")
    blockcopy = S("BLOCK_COPY")
    imm_set = S("IMM_SET")
    ldstm_multi = {insn_of[m] for m in ("ldm.t", "stm.t", "ldm.o", "stm.o")}

    d11 = {insn_of[m] for m in D11_SET}
    d12 = {insn_of[m] for m in D12_SET}
    d13 = {insn_of[m] for m in D13_SET}
    d14 = {insn_of[m] for m in D14_SET}
    d15 = {insn_of[m] for m in D15_SET}
    d15p = {insn_of[m] for m in D15_PARTIAL}
    d16 = {insn_of[m] for m in D16_SET}

    # 集合基数断言（防止「修一条漏一半」）
    expected = {
        "D11": (d11, 37), "D12": (d12, 53), "D13": (d13, 18),
        "D14": (d14, 4), "D15": (d15, 18), "D15-partial": (d15p, 2),
        "D16": (d16, 36),
    }
    for key, (st, n) in expected.items():
        if len(st) != n:
            raise ValueError(f"{key} 受影响集为 {len(st)} 条，与声明的 {n} 条不符")

    silent_notes = {}
    for s in SPEC_SILENT:
        mnems = _as_set(SPEC_SILENT_MNEMONICS[s["id"]])
        if mnems is None:
            for r in rows:
                silent_notes.setdefault(r["insn"], []).append(s["id"])
        else:
            for m in mnems:
                silent_notes.setdefault(insn_of[m], []).append(s["id"])

    decl = {}
    for r in rows:
        insn, mnem = r["insn"], r["mnemonic"]
        f = {k: STATUS_SPEC for k in FACETS}
        notes = list(silent_notes.get(insn, []))

        # rf0 作操作数（D11）
        if insn in d11:
            f["rf0_operand"] = STATUS_OPEN
        elif insn in {insn_of[m] for m in D11_SPEC_RULE} or insn in (
                {insn_of[m] for m in D11_DETERMINED}):
            f["rf0_operand"] = STATUS_SPEC
        else:
            raise ValueError(f"{insn}: rf0_operand 未归类（覆盖漏洞）")

        # 单精高半部（D13）
        f["tetra_high_half"] = STATUS_OPEN if insn in d13 else STATUS_NA

        # 异常 flags（D12）
        f["fcsr_flags"] = STATUS_OPEN if insn in d12 else STATUS_SPEC

        # tininess / 复合 flags（D16）
        f["tininess"] = STATUS_OPEN if insn in d16 else STATUS_NA

        # 比较 unordered（D14）
        f["compare_unordered"] = STATUS_OPEN if insn in d14 else STATUS_NA

        # NaN 传播（D15）
        if insn in d15:
            f["nan_propagation"] = STATUS_OPEN
        elif insn in d15p:
            f["nan_propagation"] = STATUS_PARTIAL
        else:
            f["nan_propagation"] = STATUS_NA

        # 合法性：规范只登记明说谓词。ftcls/focls 的 immu6≠1 行为未规定 → partial + S3。
        # ldm/stm **不**因 S2 记 partial（S2 已证明无行为后果，见 SPEC_SILENT["S2"]）。
        f["legality"] = STATUS_PARTIAL if insn in cls else STATUS_SPEC

        # 语义：scaleB 的「取整数值」两种读法（S5）；rootn(-0,2) 规范明示不要求；
        # ldm/stm 内存侧寻址 / 步长 / 重叠顺序未规定（S8）。
        if mnem in ("ftsclb", "fosclb"):
            f["semantics"] = STATUS_PARTIAL
            notes.append("S5")
        elif mnem in ("ftroot", "foroot"):
            f["semantics"] = STATUS_PARTIAL
            notes.append("rootn(-0,2)")
        elif insn in ldstm_multi:
            f["semantics"] = STATUS_PARTIAL
        else:
            f["semantics"] = STATUS_SPEC

        legality = list(LEGALITY_BY_MNEMONIC.get(mnem, []))
        # 去重但保持谓词声明顺序：多个谓词可映射到同一规则 id
        # （如 immu6_zero_illi 与 immu6_1_63 同属「immu6 计数范围」规则）。
        refs = list(dict.fromkeys(
            LEGALITY_REFS[p] for p in legality if LEGALITY_REFS[p]))
        open_items = sorted({FACET_DECISION[k] for k, v in f.items()
                             if v == STATUS_OPEN and k in FACET_DECISION})
        # 逐 identity 的 ledger 键（机器可读侧）：`D17:S2` 永不出现
        d17_ids = d17_ledger_ids_for([mnem])
        decl[insn] = {
            "in_scope": True,
            "identity": insn,
            "group": r["group"],
            "format": r["format"],
            "section": r["spec_section"],
            "operands": list(r["spec_operands_normalized"]),
            "semantics_cite": f"SimRISC-03 §{SEMANTIC_SECTION[mnem]}",
            "encoding_cite": f"SimRISC-00 §{QFC_SECTION[r['subtable']]}",
            "legality": legality,
            "legality_refs": refs,
            "facets": f,
            "open_items": open_items,
            "d17_open_ids": d17_ids,
            "notes": sorted(set(notes)),
        }

    # 覆盖漏洞兜底：任何 identity 都必须能被声明
    if len(decl) != len(rows):
        raise ValueError(f"声明条数 {len(decl)} != identity 条数 {len(rows)}")
    return decl


def declarations(rows):
    """对外入口：rows → {insn: f1 声明}（纯函数、可复现）。"""
    return _derive(rows)


def decisions_by_facet(decl):
    """D11–D17 的 identity×facet 矩阵：{decision: {insn: [facet,...]}}。"""
    mat = {d: {} for d in DECISIONS}
    for insn, d in decl.items():
        for facet in d["facets"]:
            if d["facets"][facet] != STATUS_OPEN:
                continue
            dec = FACET_DECISION.get(facet)
            if dec is None:
                continue
            mat[dec].setdefault(insn, []).append(facet)
    # D17 是 ADR-1004 的兜底暂缓项：所有存在 open facet 或规范静默项的 identity
    for insn, d in decl.items():
        if any(d["facets"].values()) and (
                any(v == STATUS_OPEN for v in d["facets"].values())
                or any(n in SPEC_SILENT_IDS for n in d["notes"])):
            mat["D17"].setdefault(insn, []).append("any-open-or-silent")
    return mat
