#!/usr/bin/env python3
"""check_f1_contract.py — F1 浮点合约的**独立**校验器（SPEC-102t 验收闸门）。

三方交叉校验，任何一方不一致即非零退出：

    spec/SimRISC-00* + spec/SimRISC-03*        ← 权威
              ↕  (两条互相独立的解析路径)
    tools/spec/f1_spec_extract.py  ────┐
    tools/spec/check_f1_contract.py   ──┤ (本文件内另写一套极简表格解析，
    tools/spec/f1_contract_data.py  ───┘  刻意不复用 extractor 的解析函数)
              ↕
    contracts/opcodes.yaml 的 f1: 块 + .xkw/knowledge/contract-f1-floating.md

检查项（与任务书验收 1~5 一一对应，见 `CHECKS`）：

  A 身份空间   : 64 = 18 + 46；pseudo(set.ft/set.fo) 计数 0；identity 无重复/缺失
  B scope 区分 : 恰好 64 条有 f1 块且 in_scope/excluded_m1/decode:ILLI 齐备；
                 14 条非 FP 的 excluded 记录与 178 条 M1 记录**不得**有 f1 块
  C 规范事实    : op/ha/mask/value/format/operands 与 spec 逐项独立核对
                 （两条独立解析路径互证；不信现有 YAML）；
                 **8 条 RF 存取的 4/8 字节对齐 + MALIGN 事实**由 SimRISC-03:25 原句
                 独立解析后逐条核对（数据层/落盘 YAML/合约 md 三处都要对得上）
  D facet      : 11 个 facet 齐全、状态枚举合法、4 条强制不变量、D11–D17 全非空
  E 引用       : 只引 SimRISC-00/03；无 DADAO-11；legality_refs 能在
                 legality_rules.yaml 解析且 f1_status=active；blocked 规则不得被引用
  F 合约文档   : md 与 YAML/数据一致；S1–S8、候选 ADR-1005/1006/1007 齐备；
                 未把候选 ADR 标 Accepted；ADR-1005..1007 文件不得存在
  G 可复现     : `f1_render_contract.py --check` 报告 up-to-date
  H 叙述对账   : md §7.1 静默项「处置」对 `legality`/partial 的断言、md 其它章节
                 「静默项 **Sn** → `<facet>` 记 **partial**」的正面断言、§5.4 钉死
                 汇总表、§7.1「**受影响**」点名集合，逐项与**实际 facet 归属**对账
                 （这几处都是**手写散文**，不在 `--check` 覆盖内，必须单独对账）

用法：
    python3 tools/spec/check_f1_contract.py [-v]
退出码：0 = 全部通过；1 = 有 FAIL。
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import yaml                                        # noqa: E402

import f1_contract_data as D                       # noqa: E402
import f1_spec_extract as E                        # noqa: E402

REPO_ROOT = E.REPO_ROOT
OPCODES_YAML = REPO_ROOT / "contracts" / "opcodes.yaml"
LEGALITY_YAML = REPO_ROOT / "contracts" / "legality_rules.yaml"
CONTRACT_MD = REPO_ROOT / ".xkw" / "knowledge" / "contract-f1-floating.md"
KNOWLEDGE_DIR = REPO_ROOT / ".xkw" / "knowledge"
TASKS_DIR = REPO_ROOT / ".xkw" / "tasks"
RENDERER = REPO_ROOT / "tools" / "spec" / "f1_render_contract.py"
OPCODES_SPEC00 = E.SPEC00

#: 64 之外的、**不得**获得 F1 scope 的 excluded 记录（6 cfx + 8 LR-SC）
NON_FP_EXCLUDED = (
    "cfx2rd-crrr", "cfx2rc-crrr", "cfxld-crii", "cfxst-crii",
    "escape-ciii", "trap-ciii",
    "lr_nn.o", "lr_nr.o", "lr_an.o", "lr_ar.o",
    "sc_nn.o", "sc_nr.o", "sc_an.o", "sc_ar.o",
)

#: immu6 是 **n 值 / 底值编码**而非寄存器个数，故不得套用计数类谓词
NON_COUNT_IMMU6 = ("ftroot", "foroot", "ftlog", "folog")

FORBIDDEN_CITE = re.compile(r"DADAO-1[01]|DADAO-06\d\d|DADAO-0628")

# ═══════════════════ D7 钉死值：facet 状态**归属表**（不是计数，是精确成员集）═══
#
# 为什么必须在这里、而不是只和 f1_contract_data.py 互相印证：
#   D2 四条不变量只能保证「open ⇒ 进 D* 矩阵」等**内部自洽**。若有人把某个
#   open-blocked facet 改成 spec-determined，并**顺手**清空 open_items、**重新**
#   渲染 opcodes.yaml，那么数据层与落盘层完全一致，上面所有不变量都照样成立，
#   检查器会**假绿**——而这正是 ADR-1004 D11–D17 最忌讳的「把开口偷偷固化」。
#   故把「哪些 identity 的哪个 facet 处于 open/partial」作为**本文件内的字面量**
#   钉死：改 f1_contract_data.py 的推导结果而不同步改这张表，必然被点名报错。
#
# 推导依据（每条都可回到 spec/SimRISC-00 §FCSR / spec/SimRISC-03 与
# adr-1004 D11–D17 复核，不是从实现反推）：
#   * rf0_operand   开口：凡 rf0 的取值/来源未被 §rf0 规则唯一确定的
#   * fcsr_flags    开口：凡结果会写 FCSR flag 而规范未指明写哪些 flag 的
#   * tetra_high_half开口：凡与 tetra/octa 半字拆分（高 32 位）相关的
#   * compare_unordered 开口：仅 4 条比较类（ftqcmp/ftscmp/foqcmp/foscmp）
#   * nan_propagation  开口：算术类 18 条；fo2ft/ft2fo 为 partial（搬运，无新值）
#   * tininess      开口：算术类 36 条（含 scaleB 类，故 36 > nan 的 18）
PINNED_OPEN = {
    "rf0_operand": frozenset("""
        cs.eq-rf cs.n-rf cs.ne-rf cs.p-rf cs.z-rf fo2fo fo2ft fo2io fo2it fo2uo
        fo2ut focls foqcmp foscmp fosgnj fosgnn ft2fo ft2ft ft2io ft2it ft2uo ft2ut
        ftcls ftqcmp ftscmp ftsgnj ftsgnn io2fo io2ft it2fo it2ft rd2rf rf2rd uo2fo
        uo2ft ut2fo ut2ft""".split()),
    "fcsr_flags": frozenset("""
        cs.eq-rf cs.n-rf cs.ne-rf cs.p-rf cs.z-rf fo2fo fo2ft fo2io fo2it fo2uo fo2ut
        foadd focls fodiv folog fomadd fomul foqcmp forem foroot fosclb foscmp fosgnj
        fosgnn fosub ft2fo ft2ft ft2io ft2it ft2uo ft2ut ftadd ftcls ftdiv ftlog
        ftmadd ftmul ftqcmp ftrem ftroot ftsclb ftscmp ftsgnj ftsgnn ftsub io2fo
        io2ft it2fo it2ft uo2fo uo2ft ut2fo ut2ft""".split()),
    "tetra_high_half": frozenset("""
        fo2ft ft2ft ftadd ftdiv ftlog ftmul ftrem ftroot ftsclb ftsgnj ftsgnn ftsub
        io2ft it2ft ld.t-rf ldm.t-rf uo2ft ut2ft""".split()),
    "compare_unordered": frozenset("foqcmp foscmp ftqcmp ftscmp".split()),
    "nan_propagation": frozenset("""
        foadd fodiv folog fomadd fomul forem foroot fosclb fosub ftadd ftdiv ftlog
        ftmadd ftmul ftrem ftroot ftsclb ftsub""".split()),
    "tininess": frozenset("""
        fo2ft fo2io fo2it fo2uo fo2ut foadd fodiv folog fomadd fomul forem foroot
        fosclb fosub ft2fo ft2io ft2it ft2uo ft2ut ftadd ftdiv ftlog ftmadd ftmul
        ftrem ftroot ftsclb ftsub io2fo io2ft it2fo it2ft uo2fo uo2ft ut2fo
        ut2ft""".split()),
}

PINNED_PARTIAL = {
    "legality": frozenset({"focls", "ftcls"}),          # immu6≠1 的取舍未定
    "semantics": frozenset("""foroot fosclb ftroot ftsclb
                              ldm.o-rf ldm.t-rf stm.o-rf stm.t-rf""".split()),
    "nan_propagation": frozenset({"fo2ft", "ft2fo"}),    # 纯搬运，无新值可传播
}

#: D11–D17 矩阵每列的**精确**成员数（与 PINNED_OPEN 一一对应，D17 为并集）
PINNED_MATRIX = {"D11": 37, "D12": 53, "D13": 18,
                 "D14": 4, "D15": 18, "D16": 36, "D17": 64}

CHECKS: list[tuple[str, str, bool]] = []


def check(cid, title, blocking=True):
    def deco(fn):
        CHECKS.append((cid, title, fn, blocking))
        return fn
    return deco


class Report:
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.fails: list[str] = []
        self.oks: list[str] = []

    def ok(self, cid, msg):
        self.oks.append(f"[{cid}] OK   {msg}")
        if self.verbose:
            print(f"[{cid}] OK   {msg}")

    def fail(self, cid, msg):
        self.fails.append(f"[{cid}] FAIL {msg}")

    def expect(self, cid, cond, okmsg, failmsg):
        if cond:
            self.ok(cid, okmsg)
        else:
            self.fail(cid, failmsg)
        return cond


# ═════════════════ 独立的第二条 spec 解析路径（刻意不复用 extractor） ═════════════════
#
# 目的：extractor 与 checker 各自从 spec 原文独立算出 identity/op/ha/mask/value，
# 两条路径**不共享任何解析函数**。若 extractor 写错，本路径会给出不同答案并报错。
#
# 本路径的做法（全部只读 spec/SimRISC-00 的表格文字）：
#   * QFC 主表：行头 `AAAA-Bxxx` 给出 op 的高 5 位，列头 `xxxx-xCCC` 给出低 3 位
#     → op = (int(A,2) << 4) | (int(B,2) << 3) | int(C,2)
#   * 单元格 `MISC-xxx` = 子表指针；`mnemonic-bank-format` / `mnemonic-format` = 条目
#   * MISC-* 子表：行头 `AAA-xxx` + 列头 `xxx-CCC` → ha = (int(A,2) << 3) | int(C,2)
#   * mask：QFC 条目 0xFF000000；子表条目 0xFFFC0000
#   * value：QFC = op << 24；子表 = (op << 24) | (ha << 18)

def _table_body(text, heading_re, optional=False):
    """取出某个 heading 之后、下一个 heading 之前的 markdown 表格行。"""
    m = re.search(heading_re, text, re.M)
    if not m:
        if optional:
            return []
        raise SystemExit(f"独立解析失败：spec-00 找不到段落 {heading_re}")
    tail = text[m.end():]
    nxt = re.search(r"^#{1,4}\s", tail, re.M)
    seg = tail[:nxt.start()] if nxt else tail
    return [ln.strip() for ln in seg.splitlines() if ln.strip().startswith("|")]


def _cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _is_sep(cells):
    return all(set(c) <= set("-: ") for c in cells)


def _identity_of(cell):
    """`ld.t-rf-rrii` → `ld.t-rf`；`ftmadd-rrrr` → `ftmadd`；空 → None。"""
    parts = cell.split("-")
    if len(parts) >= 2 and re.fullmatch(r"[a-z]{4}", parts[-1]):
        parts = parts[:-1]           # 去尾部 format
    if not parts or not parts[0]:
        return None
    if len(parts) >= 2 and parts[-1] in ("rd", "rb", "ra", "rf", "cs"):
        return f"{parts[0]}-{parts[-1]}"
    return parts[0]


def independent_encoding():
    """独立地从 spec/SimRISC-00 表格算出 identity → (op, ha, mask, value, format)。"""
    text = (REPO_ROOT / "spec" / "SimRISC-00-指令系统设计.md").read_text(encoding="utf-8")
    enc: dict[str, tuple] = {}

    # ── QFC 主表 ──
    rows = _table_body(text, r"^##\s*SimRISC QFC\s*$")
    if len(rows) < 3:
        raise SystemExit("独立解析失败：QFC 主表行数不足")
    cols = _cells(rows[0])[1:]                       # 形如 xxxx-x000
    for line in rows[2:]:                             # 跳过表头 + 分隔行
        cells = _cells(line)
        if _is_sep(cells) or len(cells) != len(cols) + 1:
            continue
        rh = cells[0]                                # 形如 0100-0xxx（xxx = don't care）
        m = re.fullmatch(r"([01]{4})-([01])x{3}", rh)
        if not m:
            continue
        hi = int(m.group(1) + m.group(2), 2) << 3    # op 的高 5 位
        for cell, colhead in zip(cells[1:], cols):
            cm = re.fullmatch(r"x{4}-x([01]{3})", colhead)      # xxxx-xCCC
            if not cm:
                continue
            op = hi | int(cm.group(1), 2)
            cell = cell.strip()
            if not cell:
                continue                              # reserved
            if re.fullmatch(r"MISC-[A-Za-z]+", cell):
                enc.setdefault(f"@{cell}", (op, None, 0xFF000000, op << 24, None))
                continue
            insn = _identity_of(cell)
            if insn is None:
                continue
            parts = cell.split("-")
            fmt = parts[-1] if re.fullmatch(r"[a-z]{4}", parts[-1]) else None
            enc[insn] = (op, None, 0xFF000000, op << 24, fmt)

    # ── MISC 子表 ──
    #     F1 涉及的子表：MISC-RF（0x44，46 条）与 MISC-octa（0x40，含 rd2rf/rf2rd）。
    #     全部 6 个子表都解析，identity 键天然去重。
    pointers = {v[0]: k[1:] for k, v in enc.items() if k.startswith("@")}
    if not pointers:
        raise SystemExit("独立解析失败：QFC 主表未找到任何 MISC 子表指针")

    for op, sub in sorted(pointers.items()):
        rows = _table_body(text, rf"^###\s*{re.escape(sub)}\s*指令编码\s*$",
                           optional=True)
        if not rows:
            continue                          # 该子表无独立小节（如 MISC-AMO）
        if len(rows) < 3:
            raise SystemExit(f"独立解析失败：{sub} 子表行数不足")
        cols = _cells(rows[0])[1:]                   # 形如 xxx-000
        for line in rows[2:]:
            cells = _cells(line)
            if _is_sep(cells) or len(cells) != len(cols) + 1:
                continue
            m = re.fullmatch(r"([01]{3})-x{3}", cells[0])      # AAA-xxx
            if not m:
                continue
            hi = int(m.group(1), 2) << 3
            for cell, colhead in zip(cells[1:], cols):
                cm = re.fullmatch(r"x{3}-([01]{3})", colhead)   # xxx-CCC
                if not cm:
                    continue
                ha = hi | int(cm.group(1), 2)
                cell = cell.strip()
                if not cell:
                    continue                          # reserved
                insn = _identity_of(cell)
                if insn is None:
                    continue
                parts = cell.split("-")
                fmt = parts[-1] if re.fullmatch(r"[a-z]{4}", parts[-1]) else None
                enc[insn] = (op, ha, 0xFFFC0000, (op << 24) | (ha << 18), fmt)

    keys = ("op", "ha", "mask", "value", "format")
    return {insn: dict(zip(keys, v)) for insn, v in enc.items()
            if not insn.startswith("@")}


# ═══════════ 独立的第三条解析路径：SimRISC-03 §存取RF寄存器 的对齐/MALIGN ═══════════
#
# 动机（一次真实缺陷）：`f1_contract_data.py` 曾用**顺序 `dict.update()`** 逐批写入
# 合法性谓词，后写的整段**覆盖**先写的整段，于是 `ld.t`/`ld.o`/`ldm.t`/`ldm.o`/
# `stm.t`/`stm.o` **静默丢掉**了 SimRISC-03:25 要求的 `aligned(4)`/`aligned(8)`
# （以及随之而来的 `fp_malign_rf` 引用）。而数据层、落盘 `opcodes.yaml`、合约 md
# 三层**自洽地一起错** —— 三层互证照样全绿，57 项检查 0 失败。
#
# 因此这里必须有一层**不以数据层为判据**的核对：判据是 SimRISC-03 原文那句话本身。
# 本函数只读 `spec/SimRISC-03-浮点类指令.md` 的 §存取RF寄存器 段落，**不**引用
# `f1_contract_data.LEGALITY_BY_MNEMONIC`，也不读 `contracts/*.yaml`。

ALIGN_SPEC = REPO_ROOT / "spec" / "SimRISC-03-浮点类指令.md"
ALIGN_SECTION = "## 存取RF寄存器"
ALIGN_RULE_ID = "fp_malign_rf"
ALIGN_FAULT = "MALIGN"
#: 4 字节组 / 8 字节组的**条数**（规范原文里两组各 4 条；解析结果必须满足）
ALIGN_WIDTH_SPLIT = {4: 4, 8: 4}


def _width_clauses(sentence: str, name_re: str = r"`([^`]+)`") -> dict:
    """把「`a`/`b` 需 N 字节对齐，…」这类句子解析成 {名字: N}。

    按 `，`/`；`/换行 切句；每句取 `name_re` 抽出的全部名字与该句里的
    `N 字节对齐`。同一个名字在两句里出现且宽度不同即视为解析失败
    （不静默取最后一个）。`name_re` 传 `PLAIN_NAME_RE` 时用于
    `legality_rules.yaml` 里不带反引号的纯文本描述。
    """
    out: dict = {}
    for clause in re.split(r"[，；\n]", sentence):
        names = re.findall(name_re, clause)
        wm = re.search(r"(\d+)\s*字节对齐", clause)
        if not names or not wm:
            continue
        width = int(wm.group(1))
        for n in names:
            n = n.strip()
            if n in out and out[n] != width:
                raise SystemExit(
                    f"对齐解析失败：`{n}` 同时被要求 {out[n]} 与 {width} 字节对齐")
            out[n] = width
    return out


#: 纯文本（无反引号）里的指令/identity 名，如 `ld.o-rf`、`ldm.t-rf`、`fp_malign_rf`
PLAIN_NAME_RE = r"[A-Za-z][A-Za-z0-9]*(?:[.\-][A-Za-z0-9]+)+"


def independent_alignment(rows):
    """独立解析 SimRISC-03 §存取RF寄存器 的对齐要求。

    返回 `(width_by_insn, spec_line_no, spec_sentence)`：
      * `width_by_insn` —— 规范原句里被点名要求对齐的 identity → 字节宽度
      * `spec_line_no`  —— 该原句在 spec 文件中的行号（诊断用）

    fail-closed 条件（任一命中即 `SystemExit`，由调用方报成可读的 `[C] FAIL`）：
      * 找不到 `## 存取RF寄存器` 小节
      * 小节内没有「对齐要求」原句
      * 原句未点名 8 条
      * 宽度分布不是 4 条 4 字节 + 4 条 8 字节
      * 原句没有点名 MALIGN（或点名了别的 fault）
      * 某个被点名的助记符在 64 条 identity 里**不是**恰好 1 条
    """
    text = ALIGN_SPEC.read_text(encoding="utf-8")
    lines = text.splitlines()
    try:
        start = next(i for i, ln in enumerate(lines) if ln.strip() == ALIGN_SECTION)
    except StopIteration:
        raise SystemExit(f"SimRISC-03 找不到小节 {ALIGN_SECTION}")
    stop = next((i for i in range(start + 1, len(lines))
                 if lines[i].startswith("## ")), len(lines))
    hits = [(i + 1, ln.strip()) for i, ln in enumerate(lines[start:stop], start)
            if "对齐要求" in ln]
    if len(hits) != 1:
        raise SystemExit(f"§存取RF寄存器 内的「对齐要求」原句有 {len(hits)} 句（应恰好 1 句）")
    line_no, sentence = hits[0]
    by_name = _width_clauses(sentence)
    if ALIGN_FAULT not in sentence:
        raise SystemExit(f"对齐原句（:{line_no}）未点名 {ALIGN_FAULT} 异常")
    if not by_name:
        raise SystemExit(f"对齐原句（:{line_no}）未解析出任何「需 N 字节对齐」")
    dist = {}
    for w in by_name.values():
        dist[w] = dist.get(w, 0) + 1
    if dist != ALIGN_WIDTH_SPLIT:
        raise SystemExit(f"对齐原句（:{line_no}）宽度分布 = {dist}，"
                         f"应为 {ALIGN_WIDTH_SPLIT}（4 条 4 字节 + 4 条 8 字节）")
    by_mnem = {}
    for r in rows:
        by_mnem.setdefault(r["mnemonic"], []).append(r["insn"])
    width_by_insn = {}
    for name, width in sorted(by_name.items()):
        hit = by_mnem.get(name, [])
        if len(hit) != 1:
            raise SystemExit(f"对齐原句（:{line_no}）点名的 `{name}` 在 64 条 identity 里"
                             f"对应 {len(hit)} 条（应恰好 1 条）: {hit}")
        width_by_insn[hit[0]] = width
    if len(width_by_insn) != 8:
        raise SystemExit(f"对齐原句（:{line_no}）只解析出 {len(width_by_insn)} 条 identity（应 8 条）")
    return width_by_insn, line_no, sentence


# ═════════════════ 检查项 ═════════════════

@check("A", "身份空间 64 = 18 + 46，pseudo = 0")
def chk_identity(rep, ex, decl, yaml_recs):
    rows = ex["rows"]
    spec_row_cell = {r["insn"]: r["qfc_cell"] for r in rows}
    rep.expect("A", ex["n_identity"] == 64,
               f"spec 侧 identity 总数 = {ex['n_identity']}",
               f"spec 侧 identity 总数 = {ex['n_identity']}，应为 64")
    rep.expect("A", ex["n_rf_qfc"] + ex["n_misc_rf"] == ex["n_identity"],
               f"{ex['n_rf_qfc']} + {ex['n_misc_rf']} = {ex['n_identity']}",
               f"{ex['n_rf_qfc']} + {ex['n_misc_rf']} != {ex['n_identity']}")
    rep.expect("A", ex["n_rf_qfc"] == 18 and ex["n_misc_rf"] == 46,
               f"rf-qfc = {ex['n_rf_qfc']}（应 18），misc-rf = {ex['n_misc_rf']}（应 46）",
               f"rf-qfc = {ex['n_rf_qfc']}（应 18），misc-rf = {ex['n_misc_rf']}（应 46）")

    ids = [r["insn"] for r in rows]

    # A-duplicate：**不要**在这里对 rows 做重复检测 —— 那是死代码。rows 由
    # SimRISC-03 的助记符签名逐个驱动，一一对应，且 extractor 自己已在
    # 末尾对 rows 做过重复断言（抛 SpecParseError），故本检查永远为真。
    # 真正可能重复的是**另一侧**：
    #   (a) 合约层 opcodes.yaml 里两条记录同 insn（→ B 组查）；
    #   (b) spec 的 QFC **表格单元**里同一编码条目占了两格
    #       （→ 这里查；extractor 的 encodings 以 (op,ha) 为键，会把第二格
    #         静默覆盖掉，不查就看不见了）。
    #       注意必须数**完整编码单元**（如 `fo2fo-rf-orri`、`cs.eq-rf-rrrr`）
    #       而不是裸助记符：裸助记符在 SimRISC-00 里本来就会出现两次 ——
    #       一次在 QFC 表、一次在 §伪指令 的展开说明里；且 `cs.eq` 同时存在
    #       `cs.eq-rf-rrrr` 与 `cs.eq-rd-rrrr` 两格，这正是任务书要求用
    #       `insn`（而非裸助记符）消歧的原因。
    spec00_text = OPCODES_SPEC00.read_text(encoding="utf-8")
    multi = []
    for insn in sorted(decl):
        cell = spec_row_cell[insn]
        n = len(re.findall(rf"(?<![\w.\-]){re.escape(cell)}(?![\w.\-])", spec00_text))
        if n != 1:
            multi.append(f"{insn} 的编码单元 `{cell}` 在 SimRISC-00 出现 {n} 次，"
                         f"应恰好 1 次")
    rep.expect("A", not multi,
               f"64 条的编码单元在 SimRISC-00 QFC 表中各占**恰好一个**编码格",
               f"QFC 表中编码单元重复/缺失: {multi[:6]}")

    # pseudo：set.ft / set.fo 必须是 pseudo，且不得出现在 64 里、不得占编码
    rep.expect("A", set(ex["pseudos"]) == {"set.ft", "set.fo"},
               f"pseudo = {ex['pseudos']}",
               f"pseudo 解析为 {ex['pseudos']}，应恰为 set.ft/set.fo")
    pseudo_hits = [i for i in ids if i in ("set.ft", "set.fo")]
    rep.expect("A", not pseudo_hits,
               "64 条 identity 中 pseudo 计数 = 0",
               f"pseudo 混入了 identity: {pseudo_hits}")
    yaml_insns = {r["insn"] for r in yaml_recs}
    pseudo_yaml = sorted(y for y in ("set.ft-rf", "set.fo-rf", "set.ft", "set.fo")
                         if y in yaml_insns)
    rep.expect("A", not pseudo_yaml,
               "contracts/opcodes.yaml 中无 set.ft / set.fo 记录",
               f"contracts/opcodes.yaml 出现 pseudo 记录: {pseudo_yaml}")

    # 缺失：opcodes.yaml 的 78 条 excluded_m1 中应有且仅有 64 条在 64 集合内
    excluded = [r["insn"] for r in yaml_recs if r.get("excluded_m1") is True]
    rep.expect("A", len(excluded) == 78,
               f"excluded_m1 记录数 = {len(excluded)}（应 78）",
               f"excluded_m1 记录数 = {len(excluded)}，应为 78（64 F1 + 14 非 FP）")
    missing = sorted(set(ids) - set(excluded))
    rep.expect("A", not missing,
               f"64 条 identity 全部在 opcodes.yaml 中标 excluded_m1",
               f"以下 identity 未标 excluded_m1: {missing}")


@check("B", "F1 scope 区分：64 有 / 192 无")
def chk_scope(rep, ex, decl, yaml_recs):
    by = {r["insn"]: r for r in yaml_recs}
    with_f1 = sorted(r["insn"] for r in yaml_recs if "f1" in r)
    rep.expect("B", with_f1 == sorted(decl),
               f"有 f1 块的记录 = {len(with_f1)}，且与 64 集合完全相同",
               f"有 f1 块的记录 {len(with_f1)} 条，与 64 集合不符；"
               f"多={sorted(set(with_f1)-set(decl))} 少={sorted(set(decl)-set(with_f1))}")

    dup = sorted({i for i in with_f1 if with_f1.count(i) > 1})
    rep.expect("B", not dup, "f1 scope 无重复 identity", f"f1 scope 重复: {dup}")

    bad_scope = [i for i in with_f1 if by[i].get("f1", {}).get("in_scope") is not True]
    rep.expect("B", not bad_scope,
               "64 条 f1.in_scope 全为 true",
               f"以下 f1.in_scope 不为 true: {bad_scope}")

    bad_ex = [i for i in with_f1 if by[i].get("excluded_m1") is not True]
    rep.expect("B", not bad_ex,
               "64 条全部保留 excluded_m1: true",
               f"以下 F1 记录丢了 excluded_m1: {bad_ex}")

    bad_dec = [i for i in with_f1 if by[i].get("decode") != "ILLI"]
    rep.expect("B", not bad_dec,
               "64 条 decode 全为 ILLI",
               f"以下 F1 记录 decode 不是 ILLI: {bad_dec}")

    # 非 FP 的 excluded 记录：必须**没有** f1 键
    leaked = [i for i in NON_FP_EXCLUDED if "f1" in by.get(i, {})]
    rep.expect("B", not leaked,
               f"14 条非 FP excluded 记录（6 cfx + 8 LR-SC）均无 F1 scope",
               f"以下非 FP excluded 记录被错误纳入 F1 scope: {leaked}")

    # 其余 178 条 M1 记录也不得带 f1
    m1_with_f1 = [r["insn"] for r in yaml_recs
                  if r.get("excluded_m1") is not True and "f1" in r]
    rep.expect("B", not m1_with_f1,
               f"{len(yaml_recs) - 78} 条 M1 记录均无 f1 块",
               f"以下 M1 记录带 f1 块: {m1_with_f1}")

    # 声明层与落盘层必须一致（只比对**在** 64 集合内的记录：
    # 若有记录被错误纳入 scope（不在 64 内），前面的 leak 检查已报错，
    # 这里再访问 decl[i] 只会抛 KeyError 掩盖真因）
    mism = [i for i in with_f1 if i in decl
            and (by[i]["f1"].get("group") != decl[i]["group"]
                 or by[i]["f1"].get("format") != decl[i]["format"]
                 or by[i]["f1"].get("section") != decl[i]["section"]
                 or by[i]["f1"].get("operands") != decl[i]["operands"])]
    rep.expect("B", not mism,
               "64 条 f1 块的 group/format/section/operands 与声明层一致",
               f"以下 f1 块与声明层不一致: {mism}")


@check("C", "编码与 spec 逐项独立核对（两条解析路径互证）")
def chk_encoding(rep, ex, decl, yaml_recs):
    by = {r["insn"]: r for r in yaml_recs}
    spec_row = {r["insn"]: r for r in ex["rows"]}

    # C1 extractor 路径 vs opcodes.yaml
    bad = []
    for insn, r in spec_row.items():
        rec = by.get(insn)
        if rec is None:
            bad.append(f"{insn}: 缺失")
            continue
        if rec.get("mask") != f"0x{r['mask']:08X}":
            bad.append(f"{insn}: mask {rec.get('mask')} != 0x{r['mask']:08X}")
        if rec.get("value") != f"0x{r['value']:08X}":
            bad.append(f"{insn}: value {rec.get('value')} != 0x{r['value']:08X}")
        if rec.get("op") != f"0x{r['op']:02X}":
            bad.append(f"{insn}: op {rec.get('op')} != 0x{r['op']:02X}")
        if rec.get("format") != r["format"]:
            bad.append(f"{insn}: format {rec.get('format')} != {r['format']}")
        # ha（次级 opcode）：48/64 条带次级 opcode 的记录必须有 ha，
        # 且与 spec 一致。**必须查** —— ha 不参与 mask/value 的比较，
        # 只改 ha 而不改 value 时，op/mask/value/format 四项全对，
        # 上面的检查会**全绿**（这正是 CE-3 反例注入抓到的漏洞）。
        if r["ha"] is None:
            if "ha" in rec:
                bad.append(f"{insn}: 无次级 opcode（mask 0xFF000000），"
                           f"记录不应有 ha 字段 {rec.get('ha')!r}")
        else:
            want_ha = f"0x{r['ha']:02X}"
            if rec.get("ha") != want_ha:
                bad.append(f"{insn}: ha {rec.get('ha')!r} != {want_ha}")
            # 记录**自身**的 ha 与 value/mask 自洽：value[23:18] 必须等于 ha
            try:
                v = int(rec.get("value"), 16)
            except (TypeError, ValueError):
                v = None
            if v is not None and ((v >> 18) & 0x3F) != r["ha"]:
                bad.append(f"{insn}: value 0x{v:08X} 的 [23:18]="
                           f"0x{(v >> 18) & 0x3F:02X} 与 ha {want_ha} 不自洽")
    rep.expect("C", not bad,
               f"64 条的 op/ha/mask/value/format 与 extractor 逐项一致（0 处不符）",
               f"{len(bad)} 处编码不符: " + "; ".join(bad[:6]))

    # C2 独立路径 vs extractor（防止共享解析 bug）
    try:
        indep = independent_encoding()
    except SystemExit as e:
        rep.fail("C", f"独立 spec 解析失败: {e}")
        return
    diff = []
    checked = 0
    for r in ex["rows"]:
        got = indep.get(r["insn"])
        if got is None:
            diff.append(f"{r['insn']}: 独立路径未从 QFC/MISC-RF 表解析出该 identity")
            continue
        checked += 1
        for k in ("op", "ha", "mask", "value", "format"):
            if got[k] != r[k]:
                diff.append(f"{r['insn']}.{k}: 独立 {got[k]} != extractor {r[k]}")
    rep.expect("C", not diff and checked == 64,
               f"独立解析路径与 extractor 在 {checked} 条 identity 上一致"
               f"（op/ha/mask/value/format 全部）",
               f"两条路径 {len(diff)} 处不一致 / 只覆盖 {checked} 条: "
               + "; ".join(diff[:6]))

    # C3 字段布局：opcodes.yaml 的 fields[].name 顺序 = 归一化操作数列表
    badf = []
    for insn, r in spec_row.items():
        names = [f["name"] for f in by[insn].get("fields", [])]
        if names != r["spec_operands_normalized"]:
            badf.append(f"{insn}: {names} != {r['spec_operands_normalized']}")
    rep.expect("C", not badf,
               "64 条的 fields[].name 顺序与 spec 归一化操作数一致",
               f"{len(badf)} 处字段布局不符: " + "; ".join(badf[:6]))

    # C4 immu6 语义护栏：n 值/底值编码的 4 条不得套用计数谓词
    badg = [f"{insn} 误用 immu6_zero_illi" for insn in sorted(decl)
            if spec_row[insn]["mnemonic"] in NON_COUNT_IMMU6
            and "immu6_zero_illi" in decl[insn]["legality"]]
    rep.expect("C", not badg,
               f"{'/'.join(NON_COUNT_IMMU6)} 未误用 immu6 计数谓词",
               f"以下 identity 误把 n/底值当计数: {badg}")

    # C5 ldm/stm 不得带 immu6_1_63（静默项 S2 的处置：无行为后果，故不追加）
    ldstm = [i for i in sorted(decl)
             if spec_row[i]["mnemonic"] in ("ldm.t", "stm.t", "ldm.o", "stm.o")]
    bad2 = [i for i in ldstm if "immu6_1_63" in decl[i]["legality"]]
    rep.expect("C", not bad2,
               f"{len(ldstm)} 条 ldm/stm 未被追加 immu6_1_63（符合 S2 处置）",
               f"以下 ldm/stm 被追加了 immu6_1_63: {bad2}")

    # ── C6/C7/C8：8 条 RF 存取的对齐 / MALIGN 事实（判据 = spec 原句，非数据层）──
    try:
        want_w, spec_line, spec_sentence = independent_alignment(ex["rows"])
    except SystemExit as e:
        rep.fail("C", f"独立 spec 解析失败（对齐/MALIGN）: {e}")
        return
    # 解析成功本身不是断言（解析失败已在上面 fail-closed 报出）；这里只把
    # **本次用来当判据的 spec 原句与其逐条结果**如实打印出来，便于复核。
    rep.ok("C", f"独立解析 SimRISC-03 §存取RF寄存器 的对齐原句（:{spec_line}）→ "
       + "、".join(f"{i}=aligned({w})" for i, w in sorted(want_w.items())))

    def _diag(insn, what, got, exp):
        return f"{insn}: {what} 实际 {got!r}，SimRISC-03:{spec_line} 要求 {exp!r}"

    # C6 逐 identity：谓词集合**恰好**是 {aligned(width)} ∪ 其余自有谓词，
    #    即 alignment 谓词必须在、宽度必须对、且不得多出别的 aligned(N)。
    bad6 = []
    for insn, width in sorted(want_w.items()):
        preds = decl[insn]["legality"]
        want_p = f"aligned({width})"
        aligned_here = sorted(p for p in preds if p.startswith("aligned("))
        if want_p not in preds:
            bad6.append(_diag(insn, "缺少对齐谓词", aligned_here or "（无）", want_p))
        elif aligned_here != [want_p]:
            bad6.append(_diag(insn, "对齐谓词集合", aligned_here, [want_p]))
        # 落盘层必须同样带（数据层对了、落盘层漏了同样要报）
        landed = by[insn]["f1"].get("legality_predicates") or []
        landed_align = sorted(p for p in landed if p.startswith("aligned("))
        if landed_align != [want_p]:
            bad6.append(_diag(insn, "opcodes.yaml 的对齐谓词", landed_align or "（无）",
                              [want_p]))
    rep.expect("C", not bad6,
               f"8 条 RF 存取逐条带规范要求的 4/8 字节对齐谓词（判据 = "
               f"SimRISC-03:{spec_line}，非数据层/非渲染结果）",
               f"对齐谓词与 spec 不符（{len(bad6)} 处）: " + "; ".join(bad6[:8]))

    # C7 除此之外**任何** identity 都不许有对齐谓词；且 8 条都必须引用
    #    fp_malign_rf，而该规则的 fault 必须是 MALIGN。
    extra = sorted(i for i in decl
                   if i not in want_w
                   and any(p.startswith("aligned(") for p in decl[i]["legality"]))
    rep.expect("C", not extra,
               f"其余 {len(decl) - len(want_w)} 条 identity 均无对齐谓词",
               f"以下非 RF 存取 identity 误带对齐谓词: {extra}")
    rules = {r["id"]: r for r in
             yaml.safe_load(LEGALITY_YAML.read_text(encoding="utf-8"))["rules"]}
    mrule = rules.get(ALIGN_RULE_ID)
    bad7 = []
    if mrule is None:
        bad7.append(f"legality_rules.yaml 缺规则 {ALIGN_RULE_ID}")
    elif mrule.get("fault") != ALIGN_FAULT:
        bad7.append(f"{ALIGN_RULE_ID}.fault = {mrule.get('fault')!r}，"
                    f"SimRISC-03:{spec_line} 要求 {ALIGN_FAULT}")
    for insn in sorted(want_w):
        if ALIGN_RULE_ID not in (decl[insn]["legality_refs"] or []):
            bad7.append(_diag(insn, "legality_refs 缺规则",
                              decl[insn]["legality_refs"], f"含 {ALIGN_RULE_ID}"))
        if ALIGN_RULE_ID not in (by[insn]["f1"].get("legality_refs") or []):
            bad7.append(_diag(insn, "opcodes.yaml legality_refs 缺规则",
                              by[insn]["f1"].get("legality_refs"),
                              f"含 {ALIGN_RULE_ID}"))
    rep.expect("C", not bad7,
               f"8 条全部引用 {ALIGN_RULE_ID}，且该规则 fault = {ALIGN_FAULT}"
               f"（legality_rules.yaml 逐条核对）",
               f"MALIGN 引用/规则不符（{len(bad7)} 处）: " + "; ".join(bad7[:6]))

    # C8 两处**落盘叙述**必须与 spec 原句一致：
    #    (a) 合约 md §3.2 的逐 identity fault 集合（渲染结果，容易与数据层一起错）
    #    (b) contracts/legality_rules.yaml 里 fp_malign_rf 的 description
    md = CONTRACT_MD.read_text(encoding="utf-8") if CONTRACT_MD.exists() else ""
    seg = md[md.find("### 3.2"):]
    seg = seg[:seg.find("\n### ", 1)] if "\n### " in seg else seg
    rows32 = {}
    for ln in seg.splitlines():
        m = re.match(r"^\|\s*`([\w.\-]+)`\s*\|([^|]*)\|([^|]*)\|", ln)
        if m:
            rows32[m.group(1)] = (m.group(2), m.group(3))
    bad8 = []
    for insn, width in sorted(want_w.items()):
        cell = rows32.get(insn)
        if cell is None:
            bad8.append(f"{insn}: 合约 md §3.2 无该 identity 的行")
            continue
        faults, preds = cell
        if ALIGN_FAULT not in faults:
            bad8.append(_diag(insn, "md §3.2 可触发 fault 集合", faults.strip(),
                              f"含 {ALIGN_FAULT}"))
        if f"aligned({width})" not in preds:
            bad8.append(_diag(insn, "md §3.2 的对齐谓词", preds.strip(),
                              f"aligned({width})"))
    rep.expect("C", not bad8,
               f"合约 md §3.2 的 8 行均含 {ALIGN_FAULT} 与正确宽度的 aligned(N)",
               f"md §3.2 与 spec 不符（{len(bad8)} 处）: " + "; ".join(bad8[:6]))
    if mrule is not None:
        desc_w = _width_clauses(str(mrule.get("description", "")),
                                PLAIN_NAME_RE)
        badw = {n: w for n, w in want_w.items() if desc_w.get(n) != w}
        notnamed = sorted(n for n in want_w if n not in desc_w)
        bad8b = [f"{n} 在 {ALIGN_RULE_ID}.description 里要求 {desc_w.get(n)} 字节，"
                 f"spec 要求 {w} 字节" for n, w in sorted(badw.items())]
        bad8b += [f"{n} 未出现在 {ALIGN_RULE_ID}.description 里（spec:{spec_line} "
                  f"要求 {want_w[n]} 字节对齐）" for n in notnamed]
        if ALIGN_FAULT not in str(mrule.get("description", "")):
            bad8b.append(f"{ALIGN_RULE_ID}.description 未点名 {ALIGN_FAULT}")
        rep.expect("C", not bad8b,
                   f"{ALIGN_RULE_ID}.description 逐条点名 8 条 identity 的 4/8 字节"
                   f"对齐与 {ALIGN_FAULT}（与 spec 原句一致）",
                   f"legality_rules.yaml 的 {ALIGN_RULE_ID}.description 与 spec 不符: "
                   + "; ".join(bad8b[:6]))
    else:
        rep.fail("C", f"{ALIGN_RULE_ID} 规则不存在，无法核对其 description")


@check("D", "facet 齐全 / 枚举合法 / 4 条不变量 / D11–D17 非空")
def chk_facets(rep, ex, decl, yaml_recs):
    by = {r["insn"]: r for r in yaml_recs}
    # 有 identity 缺 f1: 块时，后续每项都会 KeyError 并报「检查器自身异常」，
    # 那会**掩盖**真正的指控（scope 缺失由 B 组权威报告）。故此处明确短路。
    gap = [i for i in decl if "f1" not in by.get(i, {})]
    if gap:
        rep.fail("D", f"{len(gap)} 条 identity 缺少 f1: 块，facet 检查无法进行"
                      f"（scope 缺失详见 B 组）: {gap[:6]}")
        return
    mat = D.decisions_by_facet(decl)

    # D1 落盘 facets 齐全且枚举合法
    bad_keys, bad_enum, bad_decl = [], [], []
    for insn, d in sorted(decl.items()):
        f = by[insn]["f1"].get("facets") or {}
        if list(f) != list(D.FACETS):
            bad_keys.append(f"{insn}: {list(f)}")
        for k, v in f.items():
            if v not in D.STATUS_ORDER:
                bad_enum.append(f"{insn}.{k}={v!r}")
        if f != d["facets"]:
            bad_decl.append(insn)
    rep.expect("D", not bad_keys,
               f"64 条的 11 个 facet 齐全且顺序正确（{len(D.FACETS)} 个）",
               f"facet 键不齐/顺序错: {bad_keys[:4]}")
    rep.expect("D", not bad_enum,
               f"facet 状态值全部落在 4 个枚举内（{', '.join(D.STATUS_ORDER)}）",
               f"非法 facet 状态值: {bad_enum[:6]}")
    rep.expect("D", not bad_decl,
               "落盘 facets 与声明层逐 identity 相同",
               f"落盘 facets 与声明层不一致: {bad_decl[:6]}")

    # D2 四条强制不变量
    v_open, v_part, v_spec, v_na = [], [], [], []
    for insn, d in sorted(decl.items()):
        f = d["facets"]
        # (a) encoding/format/operands 恒为 spec-determined（这三项无任何开口）
        for k in ("encoding", "format", "operands"):
            if f[k] != D.STATUS_SPEC:
                v_spec.append(f"{insn}.{k}={f[k]}，应恒为 spec-determined")
        # (b) open_items 与「OPEN facet 集合」**双向**相等（不多不少）
        open_dec = {D.FACET_DECISION[k] for k, v in f.items()
                    if v == D.STATUS_OPEN and k in D.FACET_DECISION}
        if set(d["open_items"]) != open_dec:
            v_spec.append(f"{insn}: open_items {d['open_items']} != OPEN facet 的 "
                          f"decision 集合 {sorted(open_dec)}")
        for facet, st in f.items():
            dec = D.FACET_DECISION.get(facet)
            if st == D.STATUS_OPEN:
                if dec is None:
                    v_open.append(f"{insn}.{facet}: open 但无对应 decision")
                elif dec not in d["open_items"]:
                    v_open.append(f"{insn}.{facet}: open 但 open_items 缺 {dec}")
                elif facet not in mat.get(dec, {}).get(insn, []):
                    v_open.append(f"{insn}.{facet}: open 但不在 D{dec[1:]} 矩阵")
            elif st == D.STATUS_PARTIAL:
                if not d["notes"]:
                    v_part.append(f"{insn}.{facet}: partial 但 notes 为空")
            elif st == D.STATUS_NA:
                if dec and insn in mat.get(dec, {}):
                    v_na.append(f"{insn}.{facet}: n/a 却出现在 D{dec[1:]} 列")
    rep.expect("D", not v_open,
               "不变量：open-blocked ⇒ open_items 非空且进入对应 D* 矩阵",
               f"open-blocked 不变量被破坏: {v_open[:6]}")
    rep.expect("D", not v_part,
               "不变量：partial ⇒ notes 非空",
               f"partial 不变量被破坏: {v_part[:6]}")
    rep.expect("D", not v_spec,
               "不变量：encoding/format/operands 恒 spec-determined；"
               "open_items 与 OPEN facet 集合双向相等",
               f"spec-determined / open_items 不变量被破坏: {v_spec[:6]}")
    rep.expect("D", not v_na,
               "不变量：n/a ⇒ 不出现在任何 D* 列",
               f"n/a 不变量被破坏: {v_na[:6]}")

    # D3 落盘的 open_items / notes 与声明层一致，且取值合法
    bad_oi, bad_nt = [], []
    for insn, d in sorted(decl.items()):
        f1 = by[insn]["f1"]
        if f1.get("open_items") != d["open_items"]:
            bad_oi.append(f"{insn}: {f1.get('open_items')} != {d['open_items']}")
        if f1.get("notes") != d["notes"]:
            bad_nt.append(f"{insn}: {f1.get('notes')} != {d['notes']}")
        for o in f1.get("open_items") or []:
            if o not in D.DECISIONS:
                bad_oi.append(f"{insn}: open_item {o!r} 不在 D11–D17")
        for n in f1.get("notes") or []:
            if n not in D.SPEC_SILENT_IDS and n not in D.EXTRA_NOTES:
                bad_nt.append(f"{insn}: note {n!r} 未在数据层登记")
    rep.expect("D", not bad_oi,
               f"open_items 与声明层一致，且取值 ⊆ D11–D17（{len(D.DECISIONS)} 个）",
               f"open_items 异常: {bad_oi[:6]}")
    rep.expect("D", not bad_nt,
               f"notes 与声明层一致，且取值 ⊆ S1–S8 ∪ 附注"
               f"（{len(D.SPEC_SILENT_IDS)} + {len(D.EXTRA_NOTES)}）",
               f"notes 异常: {bad_nt[:6]}")

    # D4 D11–D17 每列非空
    counts = {dec: sum(1 for i in decl if mat.get(dec, {}).get(i)) for dec in D.DECISIONS}
    empty = [d for d, n in counts.items() if n == 0]
    rep.expect("D", not empty,
               "D11–D17 每列都非空：" +
               "、".join(f"{d}={counts[d]}" for d in D.DECISIONS),
               f"以下 D* 矩阵为空: {empty}")

    # D5 没有任何 OPEN facet 被写成确定值（词表层面）
    has_pass = [s for s in D.STATUS_ORDER if "PASS" in s]
    rep.expect("D", not has_pass,
               "facet 状态词表不含 PASS 字样（便于捕获『OPEN 改 PASS』注入）",
               f"facet 状态词表含 PASS 字样: {has_pass}")

    # D6 落盘合法性谓词与声明层一致
    bad_l = [i for i in sorted(decl)
             if by[i]["f1"].get("legality_predicates") != decl[i]["legality"]]
    rep.expect("D", not bad_l,
               "legality_predicates 与声明层逐 identity 相同",
               f"legality_predicates 不一致: {bad_l[:6]}")

    # ══ D7 钉死值核对：facet 状态**精确成员集** + D* 矩阵**精确成员数** ══
    # 这一项与 D1~D6 性质不同：它不比较「层与层是否自洽」，而是拿本文件内的
    # 字面量 PINNED_* 作**外部基准**。作用是堵死「自洽地把 open 改成 defined」
    # 这条假绿路径（见 PINNED_OPEN 上方注释）。任一 identity 的任一 facet 状态
    # 被改动而未同步这张表，都会**点名 identity + facet** 报错。
    drift = []
    for facet, want_open in sorted(PINNED_OPEN.items()):
        got_open = {i for i in decl if decl[i]["facets"][facet] == D.STATUS_OPEN}
        for i in sorted(want_open - got_open):
            drift.append(f"{i}.{facet}: 应为 {D.STATUS_OPEN}，实为 "
                         f"{decl[i]['facets'][facet]}（开口被擅自固化）")
        for i in sorted(got_open - want_open):
            drift.append(f"{i}.{facet}: 实为 {D.STATUS_OPEN}，钉死表未列（凭空开口）")
    for facet, want_partial in sorted(PINNED_PARTIAL.items()):
        got = {i for i in decl if decl[i]["facets"][facet] == D.STATUS_PARTIAL}
        for i in sorted(want_partial ^ got):
            drift.append(f"{i}.{facet}: partial 归属不符"
                         f"（钉死={i in want_partial} 实为={i in got}）")
    # encoding/format/operands 三个 facet：除 open/partial 外不得有任何开口
    for facet in ("encoding", "format", "operands", "legality", "semantics"):
        stray = {i for i in decl
                 if decl[i]["facets"][facet] == D.STATUS_OPEN}
        if facet in PINNED_OPEN or facet in PINNED_PARTIAL:
            continue
        if stray:
            drift.append(f"{facet}: 出现钉死表外的 open-blocked: {sorted(stray)[:5]}")
    # n/a 不得出现在任何钉死的 open 集内
    for facet, want_open in sorted(PINNED_OPEN.items()):
        both = sorted(want_open & {i for i in decl
                                    if decl[i]["facets"][facet] == D.STATUS_NA})
        drift += [f"{i}.{facet}: 同时被判 open 与 n/a" for i in both]
    rep.expect("D", not drift,
               f"facet 状态归属与钉死表逐项一致"
               f"（{sum(len(v) for v in PINNED_OPEN.values())} 个 open + "
               f"{sum(len(v) for v in PINNED_PARTIAL.values())} 个 partial）",
               f"facet 状态归属漂移（{len(drift)} 处）: {drift[:6]}")

    # D8 D* 矩阵每列的精确成员数
    wrong_n = {d: (n, counts[d]) for d, n in PINNED_MATRIX.items() if counts[d] != n}
    rep.expect("D", not wrong_n,
               "D11–D17 矩阵成员数与钉死表一致：" +
               "、".join(f"{d}={counts[d]}" for d in D.DECISIONS),
               f"D* 矩阵成员数与钉死表不符（钉死→实得）: {wrong_n}")


@check("E", "引用合法（无 DADAO-11 / legality_refs 可解析 / blocked 不被引用）")
def chk_refs(rep, ex, decl, yaml_recs):
    by = {r["insn"]: r for r in yaml_recs}
    # 同 chk_facets：缺 f1: 块时短路，避免 KeyError 掩盖 B 组的真因
    gap = [i for i in decl if "f1" not in by.get(i, {})]
    if gap:
        rep.fail("E", f"{len(gap)} 条 identity 缺少 f1: 块，引用检查无法进行"
                      f"（scope 缺失详见 B 组）: {gap[:6]}")
        return
    rules_doc = yaml.safe_load(LEGALITY_YAML.read_text(encoding="utf-8"))
    rules = {r["id"]: r for r in rules_doc["rules"]}

    # E1 编码/语义引用前缀
    bad = []
    for insn, d in sorted(decl.items()):
        f1 = by[insn]["f1"]
        if not str(f1.get("encoding_cite", "")).startswith("SimRISC-00 §"):
            bad.append(f"{insn}.encoding_cite={f1.get('encoding_cite')!r}")
        if not str(f1.get("semantics_cite", "")).startswith("SimRISC-03 §"):
            bad.append(f"{insn}.semantics_cite={f1.get('semantics_cite')!r}")
        if f1.get("encoding_cite") != d["encoding_cite"]:
            bad.append(f"{insn}.encoding_cite 与声明层不符")
        if f1.get("semantics_cite") != d["semantics_cite"]:
            bad.append(f"{insn}.semantics_cite 与声明层不符")
    rep.expect("E", not bad,
               "64 条的 encoding_cite=SimRISC-00 §…、semantics_cite=SimRISC-03 §…，"
               "且与声明层一致",
               f"引用异常: {bad[:6]}")

    # E2 顶层 spec_cite 与 encoding_cite 一致（本次归一化的 2 处已修）
    bad2 = [i for i in sorted(decl) if by[i].get("spec_cite") != decl[i]["encoding_cite"]]
    rep.expect("E", not bad2,
               "64 条顶层 spec_cite 与 f1.encoding_cite 一致",
               f"以下顶层 spec_cite 与 F1 编码归属不符: {bad2}")

    # E3 legality_refs 必须能在 legality_rules.yaml 解析，且规则 f1_status=active
    unres, blocked_used = [], []
    for insn, d in sorted(decl.items()):
        refs = by[insn]["f1"].get("legality_refs") or []
        if refs != d["legality_refs"]:
            unres.append(f"{insn}: legality_refs 与声明层不符")
        for rid in refs:
            r = rules.get(rid)
            if r is None:
                unres.append(f"{insn}: 规则 {rid} 在 legality_rules.yaml 中不存在")
            elif r.get("f1_status") != "active":
                blocked_used.append(f"{insn} 引用了 f1_status="
                                   f"{r.get('f1_status')!r} 的规则 {rid}")
    rep.expect("E", not unres,
               f"64 条的 legality_refs 全部可在 legality_rules.yaml 解析"
               f"（共 {len({r for d in decl.values() for r in d['legality_refs']})} 条不同规则）",
               f"legality_refs 解析失败: {unres[:6]}")
    rep.expect("E", not blocked_used,
               "没有任何 identity 引用 f1_status=blocked 的规则",
               f"以下引用了 blocked 规则: {blocked_used[:6]}")

    # E4 D11 阻塞必须真的标出来：rf0_as_operand 必须 blocked 且不被引用
    r0 = rules.get("rf0_as_operand", {})
    rep.expect("E", r0.get("f1_status") == "blocked" and r0.get("f1_decision") == "D11",
               "rf0_as_operand 标为 f1_status=blocked / f1_decision=D11（D11 仍 OPEN）",
               f"rf0_as_operand 的 F1 标注为 "
               f"f1_status={r0.get('f1_status')!r} f1_decision={r0.get('f1_decision')!r}，"
               f"应为 blocked / D11")
    rep.expect("E", "rf0_as_operand" not in
               {r for d in decl.values() for r in d["legality_refs"]},
               "D11 阻塞期间 rf0_as_operand 未被任何 identity 引用",
               "D11 阻塞期间却引用了 rf0_as_operand")

    # E5 既有 status 未被改动（纯增量）：F1 相关规则的 status 仍是原值
    expect_status = {"rd_dest_rd0": "active", "rf0_as_operand": "deferred",
                     "sbz_nonzero": "active", "fp_root_invalid_n": "deferred",
                     "fp_log_invalid_base": "deferred", "fp_malign_rf": "deferred",
                     "fp_block_immu6_zero": "deferred",
                     "fp_block_range_overflow": "deferred",
                     "fp_rf_slot_overflow": "deferred"}
    bad3 = [f"{k}={rules.get(k, {}).get('status')!r}"
            for k, v in expect_status.items() if rules.get(k, {}).get("status") != v]
    rep.expect("E", not bad3,
               f"{len(expect_status)} 条 F1 相关规则的既有 status 未被改动（纯增量）",
               f"既有 status 被改动: {bad3}")

    # E6 禁止的引用来源（DADAO-11 等）不得出现在 F1 产物里
    hay = []
    for p in (CONTRACT_MD, OPCODES_YAML, LEGALITY_YAML):
        txt = p.read_text(encoding="utf-8")
        for m in FORBIDDEN_CITE.finditer(txt):
            line = txt[:m.start()].count("\n") + 1
            hay.append(f"{p.name}:{line}: {m.group(0)}")
    rep.expect("E", not hay,
               "合约 md / opcodes.yaml / legality_rules.yaml 中无 DADAO-11 类引用",
               f"出现禁止引用: {hay[:6]}")

    # E7 legality_rules.yaml 里 f1 引用的规则 id 必须都真实存在于文件
    cited = set()
    for d in decl.values():
        cited.update(d["legality_refs"])
    miss = sorted(cited - set(rules))
    rep.expect("E", not miss,
               f"F1 引用的 {len(cited)} 条规则 id 全部存在于 legality_rules.yaml",
               f"legality_rules.yaml 缺规则: {miss}")


@check("F", "合约文档一致 / S1–S8 / 候选 ADR / 未标 Accepted")
def chk_doc(rep, ex, decl, yaml_recs):
    rep.expect("F", CONTRACT_MD.exists(),
               f"合约文件存在: {CONTRACT_MD.relative_to(REPO_ROOT)}",
               f"合约文件缺失: {CONTRACT_MD}")
    if not CONTRACT_MD.exists():
        return
    md = CONTRACT_MD.read_text(encoding="utf-8")

    # F1 64 个 identity 全部出现在 md
    missing = [i for i in sorted(decl) if f"`{i}`" not in md]
    rep.expect("F", not missing,
               f"md 中出现全部 {len(decl)} 个 identity",
               f"md 缺 {len(missing)} 个 identity: {missing[:8]}")

    # F2 静默项 S1–S8 齐备
    miss_s = [s for s in D.SPEC_SILENT_IDS if f"**{s}**" not in md and f"#### {s} " not in md]
    rep.expect("F", not miss_s,
               f"md 中 S1–S{len(D.SPEC_SILENT_IDS)} 全部登记（{len(D.SPEC_SILENT_IDS)} 项）",
               f"md 缺静默项: {miss_s}")

    # F3 候选 ADR-1005/1006/1007 齐备，且标为 Candidate
    miss_a = [a["id"] for a in D.CANDIDATE_ADRS if a["id"] not in md]
    rep.expect("F", not miss_a,
               f"md 含候选 ADR 证据输入: "
               f"{'、'.join(a['id'] for a in D.CANDIDATE_ADRS)}",
               f"md 缺候选 ADR: {miss_a}")
    bad_a = []
    for a in D.CANDIDATE_ADRS:
        seg = md[md.find(f"### 候选 {a['id']}"):]
        seg = seg[:seg.find("\n### ", 1)] if "\n### " in seg else seg
        if "状态**：Candidate" not in seg:
            bad_a.append(f"{a['id']} 未标 Candidate")
    rep.expect("F", not bad_a,
               "三个候选 ADR 在 md 中均标为 Candidate", f"候选 ADR 标注异常: {bad_a}")

    # F4 不得把候选 ADR 写成 Accepted
    #    只在同一行同时出现 ADR id 与 Accepted、且该行**不含否定词**时判 FAIL；
    #    「不得创建为 Accepted」这类**禁止性**句子必须放行，否则检查器会被自己的
    #    门禁说明误伤（假 FAIL 也是不可接受的）。
    NEG = ("不得", "不可", "禁止", "勿", "未", "非")
    bad_acc = []
    for a in D.CANDIDATE_ADRS:
        pat = re.compile(rf"{a['id']}.*Accepted|Accepted.*{a['id']}")
        for p in (CONTRACT_MD, OPCODES_YAML, LEGALITY_YAML):
            for ln in p.read_text(encoding="utf-8").splitlines():
                if pat.search(ln) and not any(n in ln for n in NEG):
                    bad_acc.append(f"{p.name}: {ln.strip()[:70]}")
    rep.expect("F", not bad_acc,
               "无任何文件把 ADR-1005/1006/1007 写成 Accepted"
               "（含否定词的禁止性说明已排除）",
               f"候选 ADR 被标 Accepted: {bad_acc[:4]}")

    # F5 ADR-1005..1007 文件不得存在
    kdir = REPO_ROOT / ".xkw" / "knowledge"
    exist = [a["id"] for a in D.CANDIDATE_ADRS
             if (kdir / f"adr-{a['id'].split('-')[1]}-{a['id']}.md").exists()
             or any(kdir.glob(f"*{a['id']}*"))]
    rep.expect("F", not exist,
               "ADR-1005/1006/1007 文件均不存在（未创建）",
               f"以下候选 ADR 文件已存在（本任务不得创建）: {exist}")

    # F6 每个 OPEN facet 在 md 的 D 矩阵里都能找到（按 decision 计数）
    mat = D.decisions_by_facet(decl)
    miss_m = [dec for dec in D.DECISIONS
              if f"`{dec}`" not in md or sum(1 for i in decl if mat[dec].get(i)) == 0]
    rep.expect("F", not miss_m,
               f"D11–D17 在 md 中全部出现且受影响集非空",
               f"md 的 D 矩阵缺: {miss_m}")

    # F7 md 不得给出 OPEN 项的取值（不得出现「决定/取值为」式的固化措辞）
    forbidden = [ln.strip() for ln in md.splitlines()
                 if re.search(r"(D1[1-7])[^\n]{0,20}(取值|答案|结论)\s*[:：=]", ln)]
    rep.expect("F", not forbidden,
               "md 未对 D11–D17 给出任何取值/结论",
               f"md 疑似给 OPEN 项定了值: {forbidden[:3]}")

    # F8 bare-mnemonic 消歧说明存在
    rep.expect("F", "裸助记符在本 ISA 中**不唯一**" in md,
               "md 含裸助记符消歧（insn）约定",
               "md 缺少 insn 消歧约定")

    # F9 §6.1 汇总表的「对应 facet」列与「受影响 identity 数」列必须逐行正确。
    #    这两列曾经整列退化成「（D17 兜底）」而**无人察觉** —— 因为 F6 只查
    #    「D11–D17 出现且集非空」，查不到「对应 facet 写错了」。此处把 facet↔decision
    #    映射与 PINNED_MATRIX 的基数一并钉死。
    inv = {v: k for k, v in D.FACET_DECISION.items()}
    seg = md[md.find("### 6.1"):]
    seg = seg[:seg.find("\n### ", 1)] if "\n### " in seg else seg
    bad_61, seen_61 = [], set()
    for ln in seg.splitlines():
        m = re.match(r"^\|\s*`(D1[1-7])`\s*\|(.+)\|\s*(\d+)\s*\|", ln)
        if not m:
            continue
        dec, facet_cell, n = m.group(1), m.group(2).strip(), int(m.group(3))
        seen_61.add(dec)
        want = f"`{inv[dec]}`" if dec in inv else "（D17 兜底）"
        if facet_cell != want:
            bad_61.append(f"{dec} 对应 facet={facet_cell!r} 应为 {want!r}")
        if n != PINNED_MATRIX[dec]:
            bad_61.append(f"{dec} 受影响数={n} 应为 {PINNED_MATRIX[dec]}")
    miss_61 = [d for d in D.DECISIONS if d not in seen_61]
    rep.expect("F", not bad_61 and not miss_61,
               "§6.1 汇总表 7 行的「对应 facet」与「受影响 identity 数」逐行正确"
               f"（D11–D16 → facet，D17 → 兜底；数与钉死表一致）",
               f"§6.1 异常: 缺行={miss_61} 错项={bad_61[:4]}")


@check("G", "可复现：f1_render_contract.py --check")
def chk_repro(rep, ex, decl, yaml_recs):
    p = subprocess.run([sys.executable, str(RENDERER), "--check"],
                       capture_output=True, text=True, cwd=str(REPO_ROOT))
    rep.expect("G", p.returncode == 0,
               f"`f1_render_contract.py --check` rc=0（产物与 spec 可复现）",
               f"`f1_render_contract.py --check` rc={p.returncode}: "
               f"{(p.stdout + p.stderr).strip()[:200]}")


# ═══════════════════ H 组：legality 归属的**叙述**与实际 facet 表一致 ═══════════════════
#
# 动机（一次真实缺陷）：S8 的「处置」写着「`legality` facet 因 S2 记 partial」，
# 而同一份 md 的 S2「处置」写着「`legality` facet 也不因此记 partial」，§5.4 的
# 钉死表也写着 legality = 0 open / 2 partial / 62 spec-determined。**同一份文件
# 自相矛盾**，且 57 项检查无一发现：facet 状态是从数据层算的，md 的散文从没被
# 拿来和 facet 表对过账。
#
# H 组的三项都是「叙述 ↔ 实际归属」的对账，不看计数：
#   H1 §7.1 每个静默项的「处置」若对 `legality` facet 作了 partial / 非 partial 的
#      断言，则该断言必须与该 S 项**点名**的 identity 的实际 `legality` 状态逐条相符；
#      点不出 identity 或读不出断言方向即 FAIL（防止「无法判读 ⇒ 放行」的假绿）。
#   H1b md 其它章节（§3/§4 表格行）里「静默项 **Sn** → `<facet>` 记 **partial**」的
#      模板手写断言：正向（断言点名的每条实为 partial）+ 反向（该 facet 的实际
#      partial 集 = 断言点名集的并集）双向核对。
#   H2 §5.4 的钉死汇总表逐行与实际 facet 状态分布对账（该表是**手写散文**，
#      不在渲染器的生成区内，`--check` 覆盖不到它）。
#   H3 §7.1 每个静默项的「**受影响**」行点名集合必须与数据层 SPEC_SILENT_MNEMONICS
#      一致 —— H1 要靠这一行确定「该 S 项说的是哪些 identity」，它错了 H1 就空转。

TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9]*(?:[.\-][A-Za-z0-9]+)*")
#: md 里的**模板手写** facet 正面断言：「静默项 **S3** → `legality` 记 **partial**」
CLAIM_RE = re.compile(r"静默项\s*\*\*(S\d+)\*\*\s*→\s*`(\w+)`\s*记\s*\*?\*?partial")


def _silent_blocks(md):
    """把 md §7.1 切成 {S编号: 该 S 项的整段文本}。"""
    seg = md[md.find("### 7.1"):]
    seg = seg[:seg.find("\n## ", 1)] if "\n## " in seg else seg
    out, cur, buf = {}, None, []
    for ln in seg.splitlines():
        m = re.match(r"^####\s+(S\d+)\s+—", ln)
        if m:
            if cur:
                out[cur] = "\n".join(buf)
            cur, buf = m.group(1), [ln]
        elif cur:
            buf.append(ln)
    if cur:
        out[cur] = "\n".join(buf)
    return out


def _affected_from_md(block, decl, insn_of_mnem, all_ids):
    """从 S 项的「**受影响**：…」行解析出它点名的 identity 集合。

    返回 `None` 表示原文写的是「全部 / 所有 identity」。无法解析出任何 identity
    时返回空集合（调用方据此判 FAIL，不当作「没约束」放行）。
    """
    m = re.search(r"\*\*受影响\*\*：(.+)", block)
    if not m:
        return set()
    line = m.group(1).split("（")[0]
    if re.search(r"全部\s*64|所有\s*identity", line):
        return None
    ids = set()
    for tok in TOKEN_RE.findall(line):
        if tok in decl:
            ids.add(tok)
        elif tok in insn_of_mnem and len(insn_of_mnem[tok]) == 1:
            ids.add(next(iter(insn_of_mnem[tok])))
    return ids


def _legality_claim(block):
    """读出该段对 `legality` facet 是否 partial 的断言方向。

    返回 `(verdict, snippet)`，`verdict` ∈ {'positive','negative'}；没有断言返回
    `(None, '')`。判读规则：看 `` `legality` `` 之后第一个「记 … partial」，
    它前面出现否定词「不」即为 negative。
    """
    for m in re.finditer(r"`legality`", block):
        win = block[m.end():m.end() + 80]
        pm = re.search(r"记\s*\**\s*partial", win)
        if not pm:
            continue
        head = win[:pm.start()]
        return ("negative" if "不" in head else "positive"), win[:pm.end()].strip()
    return None, ""


@check("H", "legality 归属：md 的静默项处置 / §5.4 汇总表与实际 facet 表对账")
def chk_legality_narrative(rep, ex, decl, yaml_recs):
    if not CONTRACT_MD.exists():
        rep.fail("H", f"合约文件缺失: {CONTRACT_MD}")
        return
    md = CONTRACT_MD.read_text(encoding="utf-8")
    insn_of_mnem = {}
    for r in ex["rows"]:
        insn_of_mnem.setdefault(r["mnemonic"], set()).add(r["insn"])
    blocks = _silent_blocks(md)
    partial_leg = {i for i in decl
                   if decl[i]["facets"]["legality"] == D.STATUS_PARTIAL}

    # H0 每个静默项都必须在 §7.1 有独立小节（否则下面的对账会漏项）
    miss_seg = [s["id"] for s in D.SPEC_SILENT if s["id"] not in blocks]
    rep.expect("H", not miss_seg,
               f"§7.1 逐项给出 S1–S{len(D.SPEC_SILENT)} 的原文与处置"
               f"（{len(blocks)} 段）",
               f"§7.1 缺静默项小节: {miss_seg}")

    # H1 「处置」对 legality/partial 的断言 ↔ 实际 facet 状态
    bad1, n_pos, n_neg = [], 0, 0
    for s in D.SPEC_SILENT:
        sid = s["id"]
        if sid not in blocks:
            continue
        verdict, snip = _legality_claim(blocks[sid])
        if verdict is None:
            continue
        ids = _affected_from_md(blocks[sid], decl, insn_of_mnem, set(decl))
        if ids is None:
            ids = set(decl)
        if not ids:
            bad1.append(f"{sid}: 处置断言了「{snip}」，但「**受影响**」行点不出任何 "
                        f"identity，无法判读该断言对谁成立")
            continue
        got = sorted(i for i in ids if i in partial_leg)
        if verdict == "positive":
            n_pos += 1
            miss = sorted(ids - partial_leg)
            if miss:
                bad1.append(f"{sid}: 处置称「{snip}」，但这 {len(ids)} 条中 "
                            f"{len(miss)} 条的 legality 实为 "
                            f"{sorted({decl[i]['facets']['legality'] for i in miss})}："
                            f"{miss[:6]}")
        else:
            n_neg += 1
            if got:
                bad1.append(f"{sid}: 处置称「{snip}」（否定），但 {got} 的 legality "
                            f"实为 partial")
    rep.expect("H", not bad1,
               f"§7.1 的 legality/partial 断言与实际归属逐条相符"
               f"（判读 {n_pos} 条肯定 + {n_neg} 条否定；实际 legality=partial 的 "
               f"{len(partial_leg)} 条 = {sorted(partial_leg)}）",
               f"§7.1 的 legality 断言与 facet 表矛盾（{len(bad1)} 处）: "
               + "; ".join(bad1[:5]))

    # H1b md **其它章节**（§3/§4 的表格行、F1 处置列）里还有一类**模板手写**的
    #    facet 断言：「静默项 **Sn** → `<facet>` 记 **partial**」。它同样不在
    #    facet 表的推导路径上（只随渲染器 TEMPLATE 走），H1 的 §7.1 对账覆盖不到，
    #    故单独双向核对：
    #      * 正向 —— 断言点名的每条 identity 在该 facet 上实为 partial；
    #      * 反向 —— 凡有正面断言的 facet，其**实际** partial 集必须**恰好**等于
    #        断言点名集的并集（漏断言某条 partial 也是错，否则「少写一条」照样绿）。
    #    只对「md 里出现过正面断言的 facet」做反向核对（未出现断言的 facet
    #    无法从散文反推归属，见完成区登记的局限）。
    claims = []
    for m in CLAIM_RE.finditer(md):
        sid, facet = m.group(1), m.group(2)
        if not any(s["id"] == sid for s in D.SPEC_SILENT):
            claims.append((sid, facet, None, f"md 断言了不存在的静默项 {sid}"))
            continue
        if facet not in D.FACETS:
            claims.append((sid, facet, None,
                           f"{sid} 断言的 `{facet}` 不是 11 个 facet 之一"))
            continue
        declared = D.SPEC_SILENT_MNEMONICS.get(sid)
        if declared == "ALL":
            ids = set(decl)
        else:
            # 助记符 → identity 必须**恰好 1 条**：0 条或多条都说明数据层与
            # identity 空间脱节，此时 `next(iter(…))` 会静默挑一条而给出看似
            # 合理的错误结论 —— 故显式报出而不是挑一个。
            amb = [m for m in declared if len(insn_of_mnem.get(m, ())) != 1]
            if amb:
                claims.append((sid, facet, None,
                               f"{sid} 的受影响助记符 {amb} 在 64 条 identity 里"
                               f"不是恰好 1 条，无法对账"))
                continue
            ids = {next(iter(insn_of_mnem[m])) for m in declared}
        miss = sorted(i for i in ids if decl[i]["facets"][facet] != D.STATUS_PARTIAL)
        if miss:
            claims.append((sid, facet, ids,
                           f"{sid} 断言「`{facet}` 记 partial」，但这 {len(ids)} 条中 "
                           f"{miss} 的 `{facet}` 实为 "
                           f"{sorted({decl[i]['facets'][facet] for i in miss})}"))
        else:
            claims.append((sid, facet, ids, None))
    bad1b = [c[3] for c in claims if c[3]]
    if not claims:
        # fail-closed：若 md 里一条这样的正面断言都没有（例如有人把 `记 **partial**`
        # 改成 `spec-determined`），下面的反向核对会**无判据可对**而空转放行 ——
        # 那正是「把断言删掉就没人发现」的后门，故显式报 FAIL。
        bad1b.append("md 中找不到任何「静默项 **Sn** → `<facet>` 记 **partial**」断言"
                     "（判据消失，必须报出而不是静默放行）")
    # 只对「有**合法**正面断言」的 facet 做反向核对：断言本身被判为非法（静默项
    # 不存在 / facet 名不在 11 个之内）时已在上面报出，若仍拿它去查
    # `decl[i]["facets"][facet]` 只会抛 KeyError，把语义 FAIL 变成 traceback 噪声。
    for facet in sorted({c[1] for c in claims if c[2] is not None}):
        claimed = set().union(*[c[2] for c in claims if c[1] == facet and c[2]])
        actual = {i for i in decl if decl[i]["facets"][facet] == D.STATUS_PARTIAL}
        if claimed != actual:
            bad1b.append(f"`{facet}`：md 正面断言点名 {len(claimed)} 条，实际 "
                         f"partial 的有 {len(actual)} 条，差集 {sorted(actual ^ claimed)}")
    rep.expect("H", not bad1b,
               f"md 其它章节的「静默项 **Sn** → `<facet>` 记 partial」断言双向相符"
               f"（正面 {len(claims)} 处，其中合法 "
               f"{sum(1 for c in claims if c[2] is not None)} 处，覆盖 facet "
               f"{sorted({c[1] for c in claims if c[2] is not None})}）",
               f"md 的 facet 正面断言与实际不符（{len(bad1b)} 处）: " + "; ".join(bad1b[:5]))

    # H2 §5.4 钉死汇总表逐行对账（手写散文，不在 --check 覆盖内）
    seg = md[md.find("### 5.4"):]
    seg = seg[:seg.find("\n## ", 1)] if "\n## " in seg else seg
    got54, bad2 = {}, []
    for ln in seg.splitlines():
        m = re.match(r"^\|\s*`(\w+)`\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s+"
                     r"(\S+)\s*\|?\s*$", ln)
        if not m:
            continue
        got54[m.group(1)] = (int(m.group(2)), int(m.group(3)),
                             int(m.group(4)), m.group(5))
    for facet in D.FACETS:
        if facet in ("encoding", "format", "operands"):
            continue
        dist = {}
        for i in decl:
            st = decl[i]["facets"][facet]
            dist[st] = dist.get(st, 0) + 1
        if facet not in got54:
            bad2.append(f"§5.4 缺 facet `{facet}` 的汇总行")
            continue
        o, pa, rest, kind = got54[facet]
        if o != dist.get(D.STATUS_OPEN, 0):
            bad2.append(f"§5.4 `{facet}` open-blocked = {o}，实际 "
                        f"{dist.get(D.STATUS_OPEN, 0)}")
        if pa != dist.get(D.STATUS_PARTIAL, 0):
            bad2.append(f"§5.4 `{facet}` partial = {pa}，实际 "
                        f"{dist.get(D.STATUS_PARTIAL, 0)}")
        if rest != len(decl) - o - pa:
            bad2.append(f"§5.4 `{facet}` 其余 = {rest}，实际 {len(decl) - o - pa}")
        others = {k: v for k, v in dist.items()
                  if k not in (D.STATUS_OPEN, D.STATUS_PARTIAL)}
        if len(others) != 1 or kind not in others or others[kind] != rest:
            bad2.append(f"§5.4 `{facet}` 其余状态 = {rest} {kind}，实际分布 {others}")
    rep.expect("H", not bad2,
               f"§5.4 钉死汇总表 {len(got54)} 行逐行与实际 facet 状态分布相符"
               f"（open/partial/其余 + 状态名）",
               f"§5.4 汇总表与实际 facet 表不符（{len(bad2)} 处）: " + "; ".join(bad2[:6]))

    # H3 §7.1「**受影响**」点名集合 ↔ 数据层 SPEC_SILENT_MNEMONICS
    bad3 = []
    for s in D.SPEC_SILENT:
        sid = s["id"]
        if sid not in blocks:
            continue
        declared = D.SPEC_SILENT_MNEMONICS.get(sid)
        # **不要**用 set.pop()：同一个助记符会出现在多个 S 项里（S2/S8、S2/S6…），
        # pop 会掏空前一个 S 项用过的集合。
        want = (None if declared == "ALL"
                else {next(iter(insn_of_mnem[m])) for m in declared})
        got = _affected_from_md(blocks[sid], decl, insn_of_mnem, set(decl))
        if want is None:
            if got is not None:
                bad3.append(f"{sid}: 数据层声明「全部 identity」，md 写的是 {sorted(got or [])}")
        elif got is None:
            bad3.append(f"{sid}: 数据层声明 {sorted(want)}，md 却写「全部/所有 identity」")
        elif got != want:
            bad3.append(f"{sid}: md 点名 {sorted(got)}，数据层声明 {sorted(want)}")
    rep.expect("H", not bad3,
               f"§7.1 各静默项「**受影响**」点名集合与数据层 SPEC_SILENT_MNEMONICS 一致"
               f"（{len(blocks)} 项）",
               f"§7.1 受影响点名集合与数据层不符（{len(bad3)} 处）: " + "; ".join(bad3[:5]))


# ═════════════════ I 组：D17 OPEN-ID ledger 的独立台账核对 ═════════════════
#
# 为什么要**独立**于渲染器再查一遍：D 组钉死的是 facet 归属、H 组钉死的是 §7.1
# 静默项散文，两者都**看不到**「下游拿到的门禁台账」本身。若没有本组，下列缺陷
# 全部会假绿：台账少一行、多一行 `D17:S2`、某行被写成 `PASS` / `active`、
# 消费者被清空、受影响 identity 写错、facet 写错、关闭证据被偷偷回填了取值。
#
# 本组的判据是**本文件里的字面量** `PINNED_D17_LEDGER`（刻意不从
# `f1_contract_data.D17_LEDGER` 导入）：改了数据层不同步这张表，检查器会点名报错。
# 解析也是**独立**的：直接从 `.xkw/knowledge/contract-f1-floating.md` 的 §6.2
# 表格读回单元格，不调用渲染器、也不复用数据层的任何函数。
#
# 权威来源：`.xkw/tasks/spec/SPEC-101k-*.md` §「D17 OPEN-ID 台账与 scope/facet
# 状态矩阵」（精确键集合、状态词 O/A、不得合并 layout 与 reset）与
# `.xkw/tasks/spec/SPEC-102t-*.md` §「后续任务消费要求」（`D17:S2` 的 ledger 外
# 注记、layout/reset 与 SBZ 写入必须分栏）。

#: 台账行的合法状态词。**顺序即期望**：`D17:S2` 不在其中（它不是 ledger 行）。
LEDGER_STATUSES = ("OPEN", "BLOCKED")

#: 精确键集合：S1、S3–S8 共 7 个。**S2 刻意缺席**。
LEDGER_IDS = ("D17:S1", "D17:S3", "D17:S4", "D17:S5",
              "D17:S6", "D17:S7", "D17:S8")

#: ledger **外**的 `D17:S2` 注记必须逐条传达的 4 件事（缺一即 FAIL）：
#: ①无行为后果 ②已解决/仅溯源 ③不在 ledger 内 ④永不记 PASS。
S2_TRACE_CLAUSES = (
    "no behavioral consequence",
    "resolved/trace-only",
    "not in D17 OPEN-ID ledger",
    "never PASS",
)

#: 关闭证据占位符（**逐字**核对：本任务一律不回填取值）。
LEDGER_CLOSURE = ("占位：待 `SPEC-103t` 逐键证明 + 用户逐 decision 确认后回填"
                  "（本任务不填取值、不选方案）")

#: `affected` 的两种合法写法。scope 行给范围关键字，ids 行给 64 条 identity 的实名。
LEDGER_SCOPES = ("all-64", "multi-fault")

#: 每行的 `facet` = **被该项未决压住的那一面**（11 个 facet 之一）。
#: 它**不**改动任何 identity 的 facet 状态归属（归属由 D7 的 PINNED_* 钉死）。
PINNED_D17_LEDGER = {
    "D17:S1": {
        "status": "BLOCKED", "facet": "fcsr_flags",
        "scope": "all-64", "ids": (),
        "consumers": ("SPEC-103t", "TESTCASES-101t", "TESTCASES-102t",
                      "QEMU-101t", "QEMU-102t", "QEMU-103t",
                      "INTEG-102t", "INTEG-103t", "INTEG-104m"),
    },
    "D17:S3": {
        "status": "BLOCKED", "facet": "legality",
        "scope": None, "ids": ("ftcls", "focls"),
        "consumers": ("SPEC-103t", "TESTCASES-101t", "TESTCASES-102t",
                      "LLVM-101t", "QEMU-103t",
                      "INTEG-102t", "INTEG-103t", "INTEG-104m"),
    },
    "D17:S4": {
        "status": "BLOCKED", "facet": "legality",
        "scope": "multi-fault", "ids": (),
        "consumers": ("SPEC-103t", "TESTCASES-101t", "TESTCASES-102t",
                      "QEMU-101t", "QEMU-102t", "QEMU-103t",
                      "INTEG-102t", "INTEG-103t", "INTEG-104m"),
    },
    "D17:S5": {
        "status": "BLOCKED", "facet": "semantics",
        "scope": None, "ids": ("ftsclb", "fosclb"),
        "consumers": ("SPEC-103t", "TESTCASES-101t", "TESTCASES-102t",
                      "QEMU-102t", "INTEG-102t", "INTEG-103t", "INTEG-104m"),
    },
    "D17:S6": {
        "status": "BLOCKED", "facet": "legality",
        "scope": None,
        "ids": ("ld.t-rf", "ld.o-rf", "ldm.t-rf", "ldm.o-rf",
                "set.w-rf", "rd2rf"),
        "consumers": ("SPEC-103t", "TESTCASES-101t", "TESTCASES-102t",
                      "QEMU-101t", "INTEG-102t", "INTEG-103t", "INTEG-104m"),
    },
    "D17:S7": {
        "status": "BLOCKED", "facet": "semantics",
        "scope": None, "ids": ("rd2rf", "rf2rd"),
        "consumers": ("SPEC-103t", "TESTCASES-101t", "TESTCASES-102t",
                      "QEMU-101t", "INTEG-102t", "INTEG-103t", "INTEG-104m"),
    },
    "D17:S8": {
        "status": "BLOCKED", "facet": "semantics",
        "scope": None,
        "ids": ("ldm.t-rf", "ldm.o-rf", "stm.t-rf", "stm.o-rf"),
        "consumers": ("SPEC-103t", "TESTCASES-101t", "TESTCASES-102t",
                      "QEMU-101t", "INTEG-102t", "INTEG-103t", "INTEG-104m"),
    },
}

#: ledger 表格的列序（渲染器按此顺序出表；解析端**不**信任渲染器，故在此钉死）。
LEDGER_COLS = ("OPEN-ID", "状态", "主题（**不含任何取值**）", "受影响 identity / 范围",
               "被阻塞 facet", "下游消费者任务", "关闭证据（占位，未回填）")

#: 候选 ADR 只允许 Candidate；本任务**不得**创建/接受其中任何一个。
CANDIDATE_ONLY_ADRS = ("ADR-1005", "ADR-1006", "ADR-1007")

#: 台账里「机器可判」的部分一律放在**反引号**里（范围关键字、identity 实名、
#: 消费者任务号），散文解释在反引号之外。解析端因此只认反引号 token，
#: 不必去猜中文散文（`全部 64（…rf0 舍入模式与 flags 初始值）` 这类说明文字
#: 里的 `rf0`/`flags` 就不会混进身份判定）。
LEDGER_CODE_RE = re.compile(r"`([^`]+)`")

#: 未关闭行里**禁止**出现的状态词（行级扫描；`resolved` 只许出现在 S2 注记里）。
LEDGER_FORBIDDEN_STATUS_RE = re.compile(r"(?<![A-Za-z])(PASS|active|resolved)"
                                        r"(?![A-Za-z])")


def _ledger_section(md, num="6.2"):
    """切出 §<num> 小节（`### <num>` 起，到下一个 `###` / `##` 为止）。"""
    m = re.search(r"^###\s+%s\b.*$" % re.escape(num), md, re.M)
    if not m:
        return None
    tail = md[m.end():]
    nxt = re.search(r"^#{2,3}\s", tail, re.M)
    return tail[:nxt.start()] if nxt else tail


def _parse_md_table(seg, want_header0):
    """独立解析 markdown 表格：返回 (表头, [数据行])；找不到表头返回 (None, [])。

    刻意**不**复用渲染器的 `table()`，也不依赖列序：按行首 `|` 切分单元格。
    """
    rows, header, started = [], None, False
    for ln in seg.splitlines():
        s = ln.strip()
        if not s.startswith("|"):
            if started and rows:
                break               # 表尾（第一个非表格行）
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if not started:
            if cells and cells[0] == want_header0:
                header, started = cells, True
            continue
        if all(set(c) <= set("-: ") for c in cells):
            continue               # 分隔行
        rows.append(cells)
    return header, rows


@check("I", "D17 OPEN-ID ledger：独立解析 §6.2 台账（键集/状态/受影响/facet/消费者/关闭证据）"
           " + 机器可读 d17_open_ids")
def chk_d17_ledger(rep, ex, decl, yaml_recs):
    # 64 条 identity 的**独立**全集（C2 已证明 extractor 与独立 spec 解析路径一致，
    # 故这里用 extractor 的 64 个 insn 作「合法 identity 名」的判据是站得住的）。
    all_ids = {r["insn"] for r in ex["rows"]}
    bad = []                        # 逐行问题清单

    # ── I0 台账小节与表格存在（判据消失 → fail-closed，不放行） ──
    md = CONTRACT_MD.read_text(encoding="utf-8") if CONTRACT_MD.exists() else None
    seg = _ledger_section(md) if md else None
    if seg is None:
        rep.fail("I", "合约文件缺少 §6.2 `D17 OPEN-ID ledger` 小节（判据消失）")
        return
    header, rows = _parse_md_table(seg, "OPEN-ID")
    if header is None:
        rep.fail("I", "§6.2 内找不到首列为 `OPEN-ID` 的台账表格（判据消失）")
        return
    if tuple(header) != LEDGER_COLS:
        rep.fail("I", f"§6.2 台账表头 = {header}，应为 {list(LEDGER_COLS)}")
        return
    rep.ok("I", f"§6.2 找到台账表格，表头 7 列与基准一致")

    # ── I1 精确键集合：恰好 7 行、无重复、无 S2、无表外键 ──
    got_ids = [r[0].strip("`") for r in rows]
    dup = sorted({i for i in got_ids if got_ids.count(i) > 1})
    if len(rows) != len(LEDGER_IDS):
        bad.append(f"台账 {len(rows)} 行，应为 {len(LEDGER_IDS)} 行")
    if dup:
        bad.append(f"台账有重复行: {dup}")
    for extra in sorted(set(got_ids) - set(LEDGER_IDS)):
        bad.append(f"台账出现表外键 `{extra}`"
                   + ("（`D17:S2` 只能作 ledger 外注记，见 §6.3）"
                      if extra == "D17:S2" else ""))
    for miss in sorted(set(LEDGER_IDS) - set(got_ids)):
        bad.append(f"台账缺键 `{miss}`")
    rep.expect("I", not bad,
               f"台账精确键集合 = {{{','.join(LEDGER_IDS)}}}（{len(rows)} 行，"
               f"无 `D17:S2`、无重复、无表外键）",
               f"台账键集合不符（{len(bad)} 处）: " + "; ".join(bad[:6]))

    # ── I2 逐行：状态词 / 禁止词 / facet / affected / 消费者 / 关闭证据 ──
    insn_of_mnem = {}
    for r in ex["rows"]:
        insn_of_mnem.setdefault(r["mnemonic"], set()).add(r["insn"])
    consumers_seen = set()
    for cells in rows:
        if len(cells) != len(LEDGER_COLS):
            bad.append(f"{cells[0] if cells else '?'}: {len(cells)} 个单元格，"
                       f"应为 {len(LEDGER_COLS)}")
            continue
        key = cells[0].strip("`")
        pin = PINNED_D17_LEDGER.get(key)
        if pin is None:
            continue                        # 键集合问题已在 I1 报出
        row_txt = " ".join(cells)

        # (a) 状态：只能是 OPEN / BLOCKED
        if cells[1] not in LEDGER_STATUSES:
            bad.append(f"{key}: 状态 = {cells[1]!r}，只允许 {list(LEDGER_STATUSES)}")
        elif cells[1] != pin["status"]:
            bad.append(f"{key}: 状态 = {cells[1]!r}，基准为 {pin['status']!r}")

        # (b) 未关闭行里不得出现 PASS / active / resolved
        for w in LEDGER_FORBIDDEN_STATUS_RE.findall(row_txt):
            bad.append(f"{key}: 未关闭行里出现禁止状态词 {w!r}")

        # (c) facet：11 个之一，且与基准一致
        facet = cells[4].strip("`")
        if facet not in D.FACETS:
            bad.append(f"{key}: 被阻塞 facet = {facet!r}，不在 11 个 facet 内")
        elif facet != pin["facet"]:
            bad.append(f"{key}: 被阻塞 facet = {facet!r}，基准为 {pin['facet']!r}")

        # (d) affected：范围式或点名式，二者之一且非空
        toks = LEDGER_CODE_RE.findall(cells[3])
        if not toks:
            bad.append(f"{key}: 「受影响 identity / 范围」为空（点名与范围都无）")
        elif pin["scope"] is not None:
            if tuple(toks) != (pin["scope"],):
                bad.append(f"{key}: 受影响 = {toks}，应为范围式 "
                           f"(`{pin['scope']}`)")
        else:
            if any(t in LEDGER_SCOPES for t in toks):
                bad.append(f"{key}: 受影响用了范围关键字 {toks}，但基准是点名式")
            unknown = [t for t in toks if t not in all_ids]
            if unknown:
                bad.append(f"{key}: 受影响含非 64 identity 的名字 {unknown}")
            elif set(toks) != set(pin["ids"]) or len(toks) != len(set(toks)):
                bad.append(f"{key}: 受影响点名 = {toks}，基准 {list(pin['ids'])}")

        # (e) 消费者：非空，且每个都必须解析到真实的任务书文件
        cons = LEDGER_CODE_RE.findall(cells[5])
        if not cons:
            bad.append(f"{key}: 下游消费者任务为空")
        else:
            if set(cons) != set(pin["consumers"]):
                bad.append(f"{key}: 消费者 = {cons}，基准 {list(pin['consumers'])}")
            for c in cons:
                consumers_seen.add(c)
                if not list(TASKS_DIR.glob(f"**/{c}-*.md")):
                    bad.append(f"{key}: 消费者 {c!r} 解析不到任务书 "
                               f"{TASKS_DIR}/**/{c}-*.md")

        # (f) 关闭证据：必须**逐字**是占位符（不得回填任何取值）
        if cells[6] != LEDGER_CLOSURE:
            bad.append(f"{key}: 关闭证据 = {cells[6][:60]!r}，"
                       f"应为占位符 {LEDGER_CLOSURE[:24]!r}…")
    rep.expect("I", not bad,
               f"{len(rows)} 行逐行核对通过：状态 ∈ {list(LEDGER_STATUSES)}、"
               f"无 PASS/active、facet ∈ 11 facet、affected 非空且与基准一致、"
               f"消费者 {len(consumers_seen)} 个全部解析到真实任务书、"
               f"关闭证据逐字为占位符",
               f"台账逐行核对不符（{len(bad)} 处）: " + "; ".join(bad[:6]))

    # ── I3 `D17:S2`：不得有 ledger 行，但 ledger 外注记必须 4 句齐全 ──
    bad3 = []
    if any(c[0].strip("`") == "D17:S2" for c in rows if c):
        bad3.append("台账里出现了 `D17:S2` 行（它只能是 ledger 外注记）")
    note = re.search(r"`D17:S2`\s*不在\s*ledger\s*内[^\n]*",
                     _ledger_section(md, "6.3") or "")
    if not note:
        bad3.append("§6.3 缺「`D17:S2` 不在 ledger 内」的注记（判据消失）")
    else:
        for cl in S2_TRACE_CLAUSES:
            if cl not in note.group(0):
                bad3.append(f"§6.3 的 `D17:S2` 注记缺子句 {cl!r}")
    rep.expect("I", not bad3,
               f"`D17:S2` 不在台账内，且 §6.3 注记 4 个必被子句齐全"
               f"（{'、'.join(S2_TRACE_CLAUSES)}）",
               f"`D17:S2` 处置不符（{len(bad3)} 处）: " + "; ".join(bad3[:5]))

    # ── I4 机器可读侧：opcodes.yaml 的 f1.d17_open_ids ──
    by = {r["insn"]: r for r in yaml_recs if "f1" in r}
    bad4 = []
    want = {}
    for key, pin in PINNED_D17_LEDGER.items():
        if pin["scope"] is not None:
            for i in sorted(all_ids):
                want.setdefault(i, []).append(key)
        else:
            for i in pin["ids"]:
                want.setdefault(i, []).append(key)
    for i in want:
        want[i].sort()
    if set(by) != set(decl):
        bad4.append(f"opcodes.yaml 带 f1 的记录 {len(by)} 条 ≠ 声明层 {len(decl)} 条")
    for insn in sorted(set(decl)):
        got = by.get(insn, {}).get("f1", {}).get("d17_open_ids")
        if got is None:
            bad4.append(f"{insn}: 缺 f1.d17_open_ids")
            continue
        if "D17:S2" in got:
            bad4.append(f"{insn}: d17_open_ids 含 `D17:S2`（永不允许）")
        unk = [x for x in got if x not in LEDGER_IDS]
        if unk:
            bad4.append(f"{insn}: d17_open_ids 含表外键 {unk}")
        if sorted(got) != want.get(insn, []):
            bad4.append(f"{insn}: d17_open_ids = {sorted(got)}，"
                        f"按基准 affected 应为 {want.get(insn, [])}")
    rep.expect("I", not bad4,
               f"opcodes.yaml {len(by)} 条 f1 记录的 `d17_open_ids` 与基准 affected "
               f"逐条一致（并集 = 精确 7 键，永不含 `D17:S2`）",
               f"机器可读台账不符（{len(bad4)} 处）: " + "; ".join(bad4[:6]))

    # ── I5 候选 ADR 不得被创建/接受（本任务只给证据输入，不选方案） ──
    made = sorted(a for a in CANDIDATE_ONLY_ADRS
                  if list(KNOWLEDGE_DIR.glob(f"adr-{a.split('-')[1]}*.md")))
    rep.expect("I", not made,
               f"候选 {'/'.join(CANDIDATE_ONLY_ADRS)} 均未创建（本任务只给证据输入，"
               f"不选方案、不写 decision）",
               f"候选 ADR 已被创建: {made} —— 本任务只登记未决事实，不得选方案")


# ═════════════════ main ═════════════════

def main(argv=None):
    ap = argparse.ArgumentParser(description="F1 浮点合约独立校验器")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)

    # spec 解析是 fail-closed 的：QFC 表与 SimRISC-03 一旦对不上（例如有人从
    # spec 表里删掉一条 identity），extractor 会直接抛 SpecParseError。这**必须**
    # 报成一条可读的 [A] FAIL，而不是裸 traceback —— 否则「spec 被改动」这种
    # 最严重的注入只表现为一个栈回溯，验收脚本无法区分「检查器自己坏了」和
    # 「合约确实坏了」。
    try:
        ex = E.extract()
        decl = D.declarations(ex["rows"])
    except Exception as e:                           # noqa: BLE001
        print("=" * 78)
        print("check_f1_contract: F1 浮点合约三方交叉校验")
        print(f"  spec 解析失败: {type(e).__name__}: {e}")
        print("=" * 78)
        print("[A] FAIL spec 解析失败：SimRISC-00 QFC 表与 SimRISC-03 助记符"
              "签名不一致，或 64 条 identity 的派生集合不完整")
        print("通过 0 项，失败 1 项")
        print("=" * 78)
        print("check_f1_contract: FAIL")
        return 1

    yaml_recs = yaml.safe_load(OPCODES_YAML.read_text(encoding="utf-8"))

    rep = Report(args.verbose)
    print("=" * 78)
    print("check_f1_contract: F1 浮点合约三方交叉校验")
    print(f"  spec 侧 identity = {ex['n_identity']} = {ex['n_rf_qfc']}(rf-qfc) "
          f"+ {ex['n_misc_rf']}(misc-rf)；pseudo = {ex['pseudos']}")
    print(f"  opcodes.yaml 记录 = {len(yaml_recs)}；"
          f"excluded_m1 = {sum(1 for r in yaml_recs if r.get('excluded_m1'))}")
    print("=" * 78)

    for cid, title, fn, _blocking in CHECKS:
        try:
            fn(rep, ex, decl, yaml_recs)
        except Exception as e:                       # noqa: BLE001
            rep.fail(cid, f"检查器自身异常: {type(e).__name__}: {e}")
    print(f"通过 {len(rep.oks)} 项，失败 {len(rep.fails)} 项")
    for line in rep.fails:
        print("  " + line)
    print("=" * 78)
    if rep.fails:
        print("check_f1_contract: FAIL")
        return 1
    print("check_f1_contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
