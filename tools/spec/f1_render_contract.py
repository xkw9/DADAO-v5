#!/usr/bin/env python3
"""f1_render_contract.py — 渲染 F1 浮点合约与 `contracts/opcodes.yaml` 的 F1 scope 标记。

**幂等**：重复运行产出字节相同。

渲染两处产物：

1. `.xkw/knowledge/contract-f1-floating.md`
   手写散文段（不在生成标记内）原样保留；`<!-- f1:generated:NAME -->` …
   `<!-- /f1:generated:NAME -->` 之间的表格/矩阵整体重写。文件不存在时先用内置
   模板创建（散文 + 骨架标记）。

2. `contracts/opcodes.yaml`
   只在 **64 条 F1 目标记录**的 `  decode: ILLI` 行之后插入一个 `  f1:` 块；
   先无条件剥掉全部已存在的 `  f1:` 块（缩进 ≥ 2 空格的续行），再重新插入。
   **其它所有字节保持不变**——不重排、不重排字段、不改 `excluded_m1`。

数据源（唯一）：
  * 编码 / 身份 / FCSR 布局  ← `f1_spec_extract.py`（独立解析 `spec/SimRISC-00*`、`spec/SimRISC-03*`）
  * facet / 合法性 / 引用 / 静默项 / 候选 ADR 证据 ← `f1_contract_data.py`

本渲染器**不发明**任何 OPEN 取值：D11–D17 一律渲染为 `open-blocked` +
`OPEN/BLOCKED`；候选 ADR 只渲染证据输入，**不写 decision**。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import f1_contract_data as D          # noqa: E402
import f1_spec_extract as E           # noqa: E402

REPO_ROOT = E.REPO_ROOT
CONTRACT_MD = REPO_ROOT / ".xkw" / "knowledge" / "contract-f1-floating.md"
OPCODES_YAML = REPO_ROOT / "contracts" / "opcodes.yaml"

GEN_BEGIN = "<!-- f1:generated:{name} -->"
GEN_END = "<!-- /f1:generated:{name} -->"


# ───────────────────────── markdown 小工具 ─────────────────────────

def md_cell(text):
    """把可能含 `|` / 换行的文本变成安全的表格单元格。"""
    if text is None:
        return "—"
    return str(text).replace("|", "\\|").replace("\n", "<br>")


def table(header, rows):
    out = ["| " + " | ".join(md_cell(h) for h in header) + " |",
           "| " + " | ".join("---" for _ in header) + " |"]
    for r in rows:
        out.append("| " + " | ".join(md_cell(c) for c in r) + " |")
    return out


def hexs(v):
    return "—" if v is None else f"`0x{v:X}`"


# ───────────────────────── 生成区 1：身份表 ─────────────────────────

def region_identity_table(ex, decl):
    rows = []
    for r in ex["rows"]:
        d = decl[r["insn"]]
        rows.append([
            f"`{r['insn']}`",
            f"`{r['mnemonic']}`",
            f"`{r['format']}`",
            r["group"],
            hexs(r["op"]),
            hexs(r["ha"]),
            hexs(r["mask"]),
            hexs(r["value"]),
            f"`{r['spec_section']}`",
            f"`{', '.join(r['spec_operands_normalized'])}`",
        ])
    lines = table(
        ["identity (`insn`)", "mnemonic", "format", "group", "op", "ha (minor)",
         "mask", "value", "SimRISC-03 小节", "操作数（归一化）"],
        rows)
    lines += [
        "",
        f"合计 **{ex['n_identity']} = {ex['n_rf_qfc']}（QFC/相关 rf-qfc）"
        f"+ {ex['n_misc_rf']}（MISC-RF）**。",
        "",
        f"`set.ft` / `set.fo` 是**伪指令**（`spec/SimRISC-03-浮点类指令.md:62`），"
        f"出现在 64 条 identity 中的计数为 **{0}**；它们不进入本表，也不分配编码。",
    ]
    return lines


# ───────────────────────── 生成区 2：合法性 ─────────────────────────

PRED_DOC = {
    "aligned(4)": "`ld.t`/`st.t`/`ldm.t`/`stm.t` 需 4 字节对齐（SimRISC-03:25）",
    "aligned(8)": "`ld.o`/`st.o`/`ldm.o`/`stm.o` 需 8 字节对齐（SimRISC-03:25）",
    "immu6_zero_illi": "`immu6` = 0 触发 ILLI（SimRISC-03:29/48/132）",
    "block_range_overflow_illi": "任一起始寄存器 + immu6 > 64 触发 ILLI（SimRISC-03:30/49/133）",
    "rf_slot_overflow_illi": "`rfha + immu6 > 64`（超出 rf63）触发 ILLI（SimRISC-03:31）",
    "immu6_1_63": "「有效范围为 1~63」（SimRISC-03:44 块赋值、:126 格式转换）；"
                   "immu6=0 另有独立 ILLI 规则，1~63 是**范围声明**而非独立 fault 条件",
    "rd_dest_not_rd0": "目的 `rd` 字段为 rd0 触发 ILLI（SimRISC-00:55，rd0 固定为 0 只读）",
    "rootn_n_in_2_3": "n 只支持 2/3，其它值触发 ILLI（SimRISC-03:188）",
    "log_base_in_0_1_2": "底只支持 2/e/10（immu6 = 2/1/0），其它值触发 ILLI（SimRISC-03:192）",
    "rf0_dst_allowed": "rf0 为目的在 rf ld/st 中**允许**（SimRISC-03:7）；这是写掩码规则，"
                       "不是 fault，故 `legality_refs` 为空",
    "immu6_1_for_cls": "`ftcls`/`focls` 的 immu6 签名固定为 `1`（SimRISC-03:270-271）；"
                       "取其它值的行为规范未规定 → 静默项 S3 = 台账 `D17:S3`，`BLOCKED`"
                       "（未决，本合约不指定行为），故 `legality_refs` 为空",
}


def region_legality(decl):
    preds = set()
    for d in decl.values():
        preds.update(d["legality"])
    ordered = [p for p in D.LEGALITY_PREDICATES if p in preds]

    lines = ["### 3.1 谓词词表（只含规范**明说**的限制）", ""]
    rows = []
    for p in ordered:
        ref = D.LEGALITY_REFS[p]
        rows.append([f"`{p}`", f"`{ref}`" if ref else "—（非 fault）", PRED_DOC[p]])
    lines += table(["谓词", "`legality_rules.yaml` 规则 id", "规范依据"], rows)
    lines += [
        "",
        "> **只用 `ld`/`st` 风格 fault 规则去编码 spec 静默项是错的**：",
        "> rf0 的 SBZ 域被写入时的行为（静默项 S6 = 台账 `D17:S6`，`BLOCKED`）"
        "**不是**合法性规则，既没有 fault 类型也没有 `spec_cite`，因此**未**新增规则，"
        "只在 §6.2 台账与 §7 登记。",
        "",
        "### 3.2 逐 identity 的 fault 集合（**不排序**）", "",
        "> 规范未规定「多个 fault 条件同时成立」时的优先级"
        "（静默项 S4 = 台账 `D17:S4`，`BLOCKED`）。"
        "下表按**集合**列出本 identity **可以**触发的 fault，**不表达先后**。"
        "该表**不**是优先级表：排序规则未决前，**任何** identity 的 fault 先后都**未决**。",
        "",
    ]

    fault_of = {
        "aligned(4)": "MALIGN", "aligned(8)": "MALIGN",
        "immu6_zero_illi": "ILLI", "block_range_overflow_illi": "ILLI",
        "rf_slot_overflow_illi": "ILLI", "rd_dest_not_rd0": "ILLI",
        "rootn_n_in_2_3": "ILLI", "log_base_in_0_1_2": "ILLI",
    }
    rows = []
    for r in sorted(decl, key=lambda i: i):
        d = decl[r]
        faults = sorted({fault_of[p] for p in d["legality"] if p in fault_of})
        rows.append([
            f"`{r}`",
            "、".join(faults) if faults else "（无 fault 条件）",
            ", ".join(f"`{p}`" for p in d["legality"]) or "—",
            d["facets"]["legality"],
        ])
    lines += table(["identity", "可触发 fault 集合（无序）", "spec 明示谓词",
                    "legality facet"], rows)
    return lines


# ───────────────────────── 生成区 3：facet 词表 ─────────────────────────

FACET_DOC = {
    "encoding": "QFC 编码（op / ha / mask / value / 字段布局）",
    "format": "操作数格式字母 + 操作数签名",
    "operands": "操作数名、角色、bank",
    "legality": "规范明示的合法性 / 异常谓词",
    "semantics": "指令主语义",
    "rf0_operand": "rf0 作目的 / 源操作数的规则",
    "tetra_high_half": "单精（ft）结果写入 rf 后的高 32 位",
    "fcsr_flags": "rf0[4:0] 的设置 / 保持 / 清除",
    "tininess": "下溢 tininess 检测时点与复合 flags",
    "compare_unordered": "比较 unordered 写入 rd 的 NaN 位型",
    "nan_propagation": "NaN 的 payload / 符号 / quieting / 默认 NaN",
}

STATUS_DOC = {
    D.STATUS_SPEC: "规范给出唯一答案，可直接实现",
    D.STATUS_PARTIAL: "规范给出部分答案，剩余部分规范未规定 → 记为 partial + note",
    D.STATUS_OPEN: "规范未给唯一答案 → **OPEN/BLOCKED**，登记到 ADR-1004 的对应 D*",
    D.STATUS_NA: "该 facet 对本 identity 不适用",
}


def region_facet_table():
    lines = ["### 5.1 facet 键（11 个，逐 identity 必填）", ""]
    rows = [[f"`{k}`", FACET_DOC[k],
             f"`{D.FACET_DECISION[k]}`" if k in D.FACET_DECISION else "—"]
            for k in D.FACETS]
    lines += table(["facet", "含义", "阻塞时的 ADR-1004 decision"], rows)
    lines += ["", "### 5.2 facet 状态枚举（4 个）", ""]
    lines += table(["状态", "含义"], [[f"`{k}`", STATUS_DOC[k]] for k in D.STATUS_ORDER])
    lines += [
        "",
        "### 5.3 强制不变量（由 `tools/spec/check_f1_contract.py` 逐 identity 校验）", "",
        "| 状态 | 不变量 |", "| --- | --- |",
        f"| `{D.STATUS_SPEC}` | `open_items` 必须为空 |",
        f"| `{D.STATUS_PARTIAL}` | `notes` 必须非空 |",
        f"| `{D.STATUS_OPEN}` | `open_items` 必须非空，且该 facet 必须出现在"
        f" §6 对应 D* 列 |",
        f"| `{D.STATUS_NA}` | 该 facet **不**出现在 §6 的任何 D* 列 |",
        "",
        "> 状态词表刻意**不含** `PASS` 字样，便于「OPEN 被改成 PASS」的反例注入"
        "被检查器捕获。",
    ]
    return lines


# ───────────────────────── 生成区 4：D11–D17 矩阵 ─────────────────────────

def region_d_matrix(decl, mat):
    insns = sorted(decl)
    lines = [
        "逐 identity × facet 的阻塞矩阵。单元格列出该 identity 在该 D* 下的"
        "**受阻 facet**；`-` 表示该 identity 不在该 D* 的受影响集内。", "",
    ]
    header = ["identity"] + list(D.DECISIONS)
    rows = []
    for insn in insns:
        row = [f"`{insn}`"]
        for dec in D.DECISIONS:
            facs = mat.get(dec, {}).get(insn, [])
            if not facs:
                row.append("-")
            else:
                row.append(", ".join(f"`{x}`" for x in facs))
        rows.append(row)
    lines += table(header, rows)

    lines += ["", "### 6.1 各 D* 的受影响规模", ""]
    n_open = {}
    for dec in D.DECISIONS:
        n_open[dec] = sum(1 for i in insns if mat.get(dec, {}).get(i))
    facet_of = {}
    # FACET_DECISION 是 {facet: decision}，解包顺序别搞反（曾反向导致
    # 「对应 facet」整列退化成「（D17 兜底）」而无人察觉）
    for facet, dec in D.FACET_DECISION.items():
        facet_of[dec] = facet
    lines += table(
        ["decision", "对应 facet", "受影响 identity 数", "状态"],
        [[f"`{dec}`",
          f"`{facet_of[dec]}`" if dec in facet_of else "（D17 兜底）",
          n_open[dec], "**OPEN/BLOCKED**"] for dec in D.DECISIONS])
    lines += [
        "",
        "> **全部 7 列都非空**：`D11`–`D17` 每个都至少有一条受影响 identity，"
        "且没有任何一条被写成确定值。本合约**不**为 OPEN 项提供取值；"
        "取值必须由用户逐 decision 确认后另行写 ADR。",
    ]
    return lines


# ───────────────────────── 生成区 4b：D17 OPEN-ID ledger ─────────────────────────

def _affected_cell(row, mnem2insn):
    """ledger 行的「受影响 identity / 范围」单元格（显式列表或范围式）。

    `affected == ("ids", 裸助记符...)` 时经 `mnem2insn` 换成 **64 条 identity 的实名**；
    助记符查不到即抛错（不允许静默渲染成裸名或漏项）。`affected == ("scope", kw...)`
    时首部给出**机器可判**的范围关键字 `` `all-64` `` / `` `multi-fault` ``，后接人读
    说明 —— 这样检查器既能判「这是范围式还是点名式」，也不必去猜中文散文。
    """
    kind = row["affected"][0]
    if kind == "scope":
        return f"`{row['affected'][1]}`：{row['affected_text']}"
    if row["affected_text"]:
        return row["affected_text"]
    names = []
    for m in row["affected"][1:]:
        if m not in mnem2insn:
            raise SystemExit(f"ledger {row['id']} 的受影响助记符不在 64 identity 内: {m}")
        names.append(f"`{mnem2insn[m]}`")
    return "、".join(names)


def region_d17_ledger(ex):
    mnem2insn = {r["mnemonic"]: r["insn"] for r in ex["rows"]}
    lines = [
        "**`D17 OPEN-ID ledger`** 是本合约交给下游的**具名门禁台账**：精确键集合固定为",
        "",
        "> " + "{" + ",".join(f"`{i}`" for i in D.D17_LEDGER_IDS) + "}",
        "",
        f"共 **{len(D.D17_LEDGER)}** 行，每行一个 OPEN-ID。下表逐行给出：**状态**、"
        "**受影响 identity / 范围**、**被阻塞的合约 facet**、**下游消费者任务**与"
        "**关闭证据占位符**。",
        "",
    ]
    rows = []
    for row in D.D17_LEDGER:
        rows.append([
            f"`{row['id']}`",
            row["status"],
            row["topic"],
            _affected_cell(row, mnem2insn),
            f"`{row['facet']}`",
            "、".join(f"`{c}`" for c in row["consumers"]),
            D.D17_CLOSURE_PLACEHOLDER,
        ])
    lines += table(["OPEN-ID", "状态", "主题（**不含任何取值**）",
                    "受影响 identity / 范围", "被阻塞 facet",
                    "下游消费者任务", "关闭证据（占位，未回填）"], rows)
    lines += [
        "",
        "**规范原文**逐条见 §7.1 的 `#### S1`…`#### S8` 各段（那里逐句引用 "
        "`spec/SimRISC-00*` / `spec/SimRISC-03*` 原句）；本 ledger **不复制**原文，"
        "只登记「规范未给唯一答案」这一事实。",
        "",
        "### 6.3 ledger 外的 `D17:S2`（**非 ledger 行**）",
        "",
        f"> **`D17:S2` 不在 ledger 内**，仅作来源追踪：`{D.D17_S2_TRACE_NOTE}`",
        "",
        "「有效范围 1~63」只出现在块赋值（`SimRISC-03:44`）与格式转换（`:126`）节，"
        "未出现在 §存取RF寄存器（`:29-31`）；但 `immu6` 上限 63 由 6 位字段宽度"
        "（`SimRISC-00:191`）唯一决定、`immu6`=0 另有独立 ILLI 谓词，故两节的有效范围"
        "**实际一致**、**无行为后果**。因此 `D17:S2` **不占用** ledger 键、**不是**阻塞项、"
        "**不得**计 PASS，也**不得**据它给任何 identity 追加谓词。",
        "",
        "### 6.4 读法约定（防止 ledger 被当成语义已决）",
        "",
        "1. ledger 的 `状态` 列**只允许** `OPEN` / `BLOCKED` 两个词。`PASS` / `active` / "
        "`spec-determined` / `resolved` 在未关闭前一律**非法**（`resolved` 只允许出现在 "
        "`D17:S2` 的 trace-only 注记里，而它不是 ledger 行）。",
        "2. 「被阻塞 facet」只表示**该项未决所压住的那一面**，**不改动** §5.4 与 "
        "`contracts/opcodes.yaml` 里任何 identity 的 facet 状态归属（归属由 "
        "`check_f1_contract.py` 的 `PINNED_OPEN` / `PINNED_PARTIAL` 钉死）。",
        "3. **layout 与 reset 必须分栏**：rf0/FCSR 的**字段布局、位号与可观测 mask** 是 "
        "spec-determined、现在可核对的 `A` 面（§2 表格）；**复位值**是 `D17:S1 = O`。"
        "不得用「布局已知」推出「复位已知」，也不得用 `A` 覆盖同一 identity 上仍为 `O` 的面。",
        "4. `D17:S6` **不指定**任何 SBZ 写入动作：「忽略 / 保留 / 清零 / 触发异常」"
        "四者**一个都不许**被本合约、机器数据或任何消费者选定。",
        "5. 关闭证据是**占位符**。本任务**不**回填取值、**不**选方案、**不**创建 ADR；"
        "由 `SPEC-103t` 逐键证明并经用户逐 decision 确认后，才可改写 `状态` 列。",
        "6. 「下游消费者任务」列的是**消费**本台账结论的任务。本合约的**生产者**"
        "（`SPEC-102t`，即本文件自身）按构造**不**出现在该列里；"
        "`SPEC-101k` 矩阵中与 `SPEC-103t` 合并成一行的那一格，"
        "在本表里只体现为 `SPEC-103t`。",
        "",
        "> 机器可读侧的同一台账落在 `contracts/opcodes.yaml` 每条 F1 记录的 "
        "`f1.d17_open_ids`（逐 identity 列出命中的 ledger 键，**永不含** `D17:S2`）。",
    ]
    return lines


# ───────────────────────── 生成区 5：规范静默项 ─────────────────────────

def region_silent():
    lines = [
        "以下 8 项是 **D1–D18 之外新发现**的规范静默项。它们**只登记原文与"
        "受影响范围**，**不作出 decision**；不因此改动任何 facet 的 OPEN 状态，"
        "也不新增 fault 规则。", "",
    ]
    rows = []
    for s in D.SPEC_SILENT:
        rows.append([f"**{s['id']}**", s["topic"], s["affected"]])
    lines += table(["编号", "主题", "受影响 identity / 范围"], rows)
    lines += ["", "### 7.1 原文与处置", ""]
    for s in D.SPEC_SILENT:
        lines.append(f"#### {s['id']} — {s['topic']}")
        lines.append("")
        for q in s["quotes"]:
            lines.append(f"- {q}")
        lines.append("")
        lines.append(f"**受影响**：{s['affected']}")
        lines.append("")
        lines.append(f"**处置**：{s['decision']}")
        lines.append("")
    lines += ["### 7.2 非缺口附注（规范明示「不做要求」）", ""]
    lines += table(["附注", "规范依据"],
                   [[f"`{k}`", v] for k, v in D.EXTRA_NOTES.items()])
    lines += [
        "",
        "> 附注**不**进入 §6 的 D* 矩阵，也**不**构成待决策缺口。",
    ]
    return lines


# ───────────────────────── 生成区 6：候选 ADR 证据输入 ─────────────────────────

def region_candidate_adr():
    lines = [
        "> **ADR 门禁**：ADR-1005 / 1006 / 1007 只能是 **Candidate**。"
        "本节只提供**证据输入**（相互冲突的原文 + 受影响 identity/facet + "
        "最小决策问题），**不含任何 decision 取值**。"
        "本任务**不创建**这三个 ADR 文件，**不得**由任何文件把它们标为 Accepted；"
        "每个 decision 须由用户逐条确认后另行写入。", "",
    ]
    for a in D.CANDIDATE_ADRS:
        lines.append(f"### 候选 {a['id']} — {a['title']}")
        lines.append("")
        lines.append(f"- **状态**：Candidate（`{a['id']}` 文件尚未创建，不得创建为 Accepted）")
        lines.append(f"- **拟覆盖的 OPEN decision**：" +
                     "、".join(f"`{d}`" for d in a["covers"]))
        lines.append("")
        lines.append("**相互冲突 / 不足的规范原文**：")
        lines.append("")
        for c in a["conflicts"]:
            lines.append(f"- {c}")
        lines.append("")
        lines.append("**最小决策问题**：")
        lines.append("")
        for q in a["questions"]:
            lines.append(f"- {q}")
        lines.append("")
    return lines


# ───────────────────────── 合约 markdown 模板 ─────────────────────────

TEMPLATE = """# F1 浮点合约（RF / SimRISC-03）

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
<!-- /f1:generated:fcsr-layout -->

### 2.1 `set.w` 的 wyde-position 映射（**规范唯一确定**）

`set.w rfha, wpN, immu16` **只设置 16 位，其余 48 位不变**
（`spec/SimRISC-03-浮点类指令.md:59`）。哪 16 位由 `wpN` 决定：

<!-- f1:generated:setw-wp -->
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
<!-- /f1:generated:d-matrix -->

### 6.2 `D17 OPEN-ID ledger`（交给下游的具名门禁台账）

<!-- f1:generated:d17-ledger -->
<!-- /f1:generated:d17-ledger -->

## 7. 规范静默项（D1–D18 之外的新发现）

<!-- f1:generated:silent -->
<!-- /f1:generated:silent -->

## 8. 候选 ADR 证据输入

<!-- f1:generated:candidate-adr -->
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
"""


# ───────────────────────── md 渲染 ─────────────────────────

def _fcsr_region(ex):
    lay = ex["fcsr"]
    lines = ["| 位域 | 规范描述 | F1 处置 |", "| --- | --- | --- |"]
    for f in lay["layout"]:
        bits = f"[{f['hi']}..{f['lo']}]"
        if "只读" in f["desc"]:
            disp = "**只读**，写静默忽略（SimRISC-03:7）"
        elif f["lo"] == 0 and f["hi"] == 4:
            disp = "异常状态，见 §6 `fcsr_flags`（**D12 OPEN**）"
        elif f["lo"] == 16 and f["hi"] == 17:
            disp = "舍入模式，见 §2，4 种模式"
        else:
            disp = "SBZ，写入行为**未规定** → 静默项 **S6**"
        lines.append(f"| `{bits}` | {f['desc']} | {disp} |")
    lines += ["", "舍入模式（`rf0[17:16]`，`spec/SimRISC-00-指令系统设计.md:90-95`）：", ""]
    rm_mean = {"RNE": "Round to Nearest, ties to Even",
               "RTZ": "Round towards Zero",
               "RDN": "Round Down (towards -inf)",
               "RUP": "Round Up (towards +inf)"}
    lines += table(["编码", "助记符", "含义"],
                   [[f"`{r['code']}`", f"`{r['mnemonic']}`", rm_mean[r["mnemonic"]]]
                    for r in lay["rounding_modes"]])
    lines += ["", "异常状态位（`rf0[4..0]`，`spec/SimRISC-00-指令系统设计.md:99-105`）：", ""]
    flag_mean = {"NV": "Invalid Operation", "DZ": "Divide by Zero",
                 "OF": "Overflow", "UF": "Underflow", "NX": "Inexact"}
    lines += table(["Bit", "助记符", "含义"],
                   [[f"`{f['bit']}`", f"`{f['mnemonic']}`", flag_mean[f["mnemonic"]]]
                    for f in lay["flags"]])
    lines += [
        "",
        "> `NV`/`DZ`/`OF`/`UF`/`NX` 的**置位语义**（sticky OR vs 整体写入）、"
        "**清除路径**、以及 **tininess** 检测时点，规范均未规定 → "
        "`fcsr_flags` / `tininess` facet 为 **OPEN/BLOCKED**（D12 / D16）。"
        "本合约**不**提供取值。",
    ]
    return lines


def _setw_wp_region():
    lines = table(["wyde-position", "命中的 rf 位段", "说明"],
                  [[f"`{wp}`", f"`{bits}`", note] for wp, bits, note in D.SETW_WP_MAP])
    lines += [
        "",
        "> 编码侧：`wpN` 在 `hb[5:4]`，`00=wp0, 01=wp1, 10=wp2, 11=wp3`"
        "（`spec/SimRISC-00-指令系统设计.md:199`）；`immu16` 拆成 "
        "`hb[3:0]` + `hc[5:0]` + `hd[5:0]`。",
    ]
    return lines


def _replace_region(text, name, body_lines):
    begin, end = GEN_BEGIN.format(name=name), GEN_END.format(name=name)
    new = begin + "\n" + "\n".join(body_lines) + "\n" + end
    i, j = text.find(begin), text.find(end)
    if i < 0 or j < 0:
        raise SystemExit(f"合约模板缺少生成区标记: {name}")
    return text[:i] + new + text[j + len(end):]


def render_md(ex, decl, mat, path=CONTRACT_MD):
    text = path.read_text(encoding="utf-8") if path.exists() else TEMPLATE
    for name, body in (
        ("identity-table", region_identity_table(ex, decl)),
        ("fcsr-layout", _fcsr_region(ex)),
        ("setw-wp", _setw_wp_region()),
        ("legality", region_legality(decl)),
        ("facet-table", region_facet_table()),
        ("d-matrix", region_d_matrix(decl, mat)),
        ("d17-ledger", region_d17_ledger(ex)),
        ("silent", region_silent()),
        ("candidate-adr", region_candidate_adr()),
    ):
        text = _replace_region(text, name, body)
    if not text.endswith("\n"):
        text += "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# ───────────────────────── opcodes.yaml 渲染 ─────────────────────────

def _yaml_list(name, items, indent="    "):
    """块序列（`[]` 空列表单独处理，便于人读与 diff）。"""
    if not items:
        return f"{indent}{name}: []\n"
    out = f"{indent}{name}:\n"
    for it in items:
        out += f"{indent}- {it}\n"
    return out


def f1_block(insn, d, indent="  "):
    """生成一个记录的 `  f1:` 块（YAML，2 空格记录级缩进）。"""
    out = f"{indent}f1:\n"
    out += f"{indent}  in_scope: true\n"
    out += f"{indent}  group: {d['group']}\n"
    out += f"{indent}  section: {yaml_str(d['section'])}\n"
    out += f"{indent}  format: {d['format']}\n"
    out += _yaml_list("operands", d["operands"], indent + "  ")
    out += _yaml_list("legality_predicates", d["legality"], indent + "  ")
    out += _yaml_list("legality_refs", d["legality_refs"], indent + "  ")
    out += f"{indent}  encoding_cite: {yaml_str(d['encoding_cite'])}\n"
    out += f"{indent}  semantics_cite: {yaml_str(d['semantics_cite'])}\n"
    out += f"{indent}  facets:\n"
    for k in D.FACETS:
        out += f"{indent}    {k}: {d['facets'][k]}\n"
    out += _yaml_list("open_items", d["open_items"], indent + "  ")
    out += _yaml_list("d17_open_ids", d["d17_open_ids"], indent + "  ")
    out += _yaml_list("notes", d["notes"], indent + "  ")
    return out


def yaml_str(s):
    """含 `§` / `：` 的标量加引号，避免 YAML 歧义。"""
    s = str(s)
    if any(ch in s for ch in ":#{}[],&*!|>'\"%@`") or s != s.strip():
        return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'
    return s


def strip_f1_blocks(text):
    """删掉全部 `  f1:` 块（`  f1:` 行 + 其后所有缩进 ≥ 4 空格的续行）。"""
    out, in_block = [], False
    for line in text.splitlines(keepends=True):
        if line.startswith("  f1:"):
            in_block = True
            continue
        if in_block:
            if line.strip() == "" or line.startswith("    "):
                continue
            in_block = False
        out.append(line)
    return "".join(out)


def render_opcodes(ex, decl, path=OPCODES_YAML):
    text = path.read_text(encoding="utf-8")
    stripped = strip_f1_blocks(text)
    out, cur = [], None
    inserted = set()
    recited = set()
    for line in stripped.splitlines(keepends=True):
        if line.startswith("- insn: "):
            cur = line[len("- insn: "):].strip()
        elif line.startswith("  spec_cite: ") and cur in decl:
            # 顶层 `spec_cite` 归一化到 spec 实际所属的 QFC 子表。
            # 只动 64 条 F1 记录；非 F1 记录（含 14 条 cfx / LR-SC）一律不碰。
            want = f"  spec_cite: {decl[cur]['encoding_cite']}\n"
            if want != line:
                recited.add(cur)
            line = want
        out.append(line)
        if line == "  decode: ILLI\n" and cur in decl and cur not in inserted:
            out.append(f1_block(cur, decl[cur]))
            inserted.add(cur)
    missing = sorted(set(decl) - inserted)
    if missing:
        raise SystemExit(f"以下 F1 identity 未找到 `  decode: ILLI` 插入点: {missing}")
    path.write_text("".join(out), encoding="utf-8")
    return sorted(inserted), sorted(recited), path


# ───────────────────────── main ─────────────────────────

def main(argv=None):
    ap = argparse.ArgumentParser(description="渲染 F1 合约与 opcodes.yaml 的 F1 scope 标记")
    ap.add_argument("--check", action="store_true",
                    help="只比对，不写盘；不一致时非零退出")
    args = ap.parse_args(argv)

    ex = E.extract()
    decl = D.declarations(ex["rows"])
    mat = D.decisions_by_facet(decl)

    problems = []
    for path, writer in ((CONTRACT_MD, render_md), (OPCODES_YAML, render_opcodes)):
        cur = path.read_text(encoding="utf-8") if path.exists() else ""
        if args.check:
            tmp = path.with_suffix(path.suffix + ".check")
            try:
                if path is OPCODES_YAML and cur:
                    # opcodes 的渲染是「相对当前内容」剥旧块再插新块，
                    # 所以先复制当前内容到临时文件再渲染。
                    tmp.write_text(cur, encoding="utf-8")
                if path is CONTRACT_MD:
                    writer(ex, decl, mat, tmp)
                else:
                    writer(ex, decl, tmp)
                new = tmp.read_text(encoding="utf-8")
            finally:
                if tmp.exists():
                    tmp.unlink()
            if new != cur:
                problems.append(str(path.relative_to(REPO_ROOT)))
        else:
            if path is CONTRACT_MD:
                writer(ex, decl, mat, path)
            else:
                writer(ex, decl, path)
            print(f"[render] {path.relative_to(REPO_ROOT)}  "
                  f"identity={ex['n_identity']}={ex['n_rf_qfc']}+{ex['n_misc_rf']}")

    if args.check:
        if problems:
            print(f"[render] NOT-UP-TO-DATE: {problems}", file=sys.stderr)
            return 1
        print("[render] up-to-date")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
