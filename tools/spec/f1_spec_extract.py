#!/usr/bin/env python3
"""f1_spec_extract.py — F1 浮点 identity 的**独立规范提取器**。

定位：F1 合约与 `tools/spec/check_f1_contract.py` 的唯一编码/identity 数据源。
本模块**只**解析根 `README.md` 锁定的 SimRISC 0.5.3 规范原文：

  * `spec/SimRISC-00-指令系统设计.md` → QFC 主表 + MISC-* 子表 → (op, ha) 编码
  * `spec/SimRISC-00-指令系统设计.md` §浮点状态寄存器 → rf0/FCSR 位域布局
  * `spec/SimRISC-03-浮点类指令.md`     → 浮点 identity 助记符 + 操作数签名 +
                                          pseudo 清单

明确**不**作为来源：`tools/spec/generate_opcodes.py`、`.tao/**`、LLVM/QEMU、
SoftFloat、宿主浮点库、参考仓。编码由本模块从规范表格重新解析后与
`contracts/opcodes.yaml` 比对，因此「YAML 与 spec 一致」是独立结论，不是循环。

SimRISC-00 编码推导（与 SimRISC-00 §指令域说明 一致）：

  * 指令字 32 位，8/6/6/6/6 = op | ha | hb | hc | hd
  * `op`  = bits[7:0]；QFC 主表行头 `RRRR-R` = bits[7:3]（5 位），
            列头 `xxxx-xCCC` 的 `CCC` = bits[2:0]
  * `ha`  = bits[5:0]；MISC 子表行头 `RRR` = ha[5:3]（3 位），
            列头 `xxx-CCC` 的 `CCC` = ha[2:0]
  * 空白单元格 = reserved（UNDI），不计入 identity
  * 单元格文本 `名称-格式` 是一条具体指令；`MISC-*` 是子表指针

用法：
    python3 tools/spec/f1_spec_extract.py                 # 打印 64 identity 表
    python3 tools/spec/f1_spec_extract.py --json out.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC00 = REPO_ROOT / "spec" / "SimRISC-00-指令系统设计.md"
SPEC03 = REPO_ROOT / "spec" / "SimRISC-03-浮点类指令.md"

# SimRISC-00 §指令域说明：四种「含 o（minor-opcode）」的格式
MINOR_OPCODE_FORMATS = frozenset({"orrr", "orri", "oiii"})
# SimRISC-00 §指令域说明：rrri 的 6 位立即数在 hd[5:0]
ALL_FORMATS = frozenset({
    "rrrr", "rrri", "rrii", "riii", "iiii", "rwii",
    "orrr", "orri", "oiii", "crrr", "crii", "ciii",
})

# SimRISC-03 §浮点类指令 的 `simrisc` 代码块中，规范把一个 6 位立即数域写成
# 多个物理子域；此处按 SimRISC-00 §指令域说明 的拆分规则归一化。
IMMEDIATE_SPLITS = {
    # imms12: hc[5:0] 高 6 位 + hd[5:0] 低 6 位（rrii）
    "imms12": ["imms12_hi", "imms12_lo"],
    # immu16: hb[3:0] 高 4 位 + hc[5:0] + hd[5:0]（rwii）
    "immu16": ["immu16_hi", "immu16_mid", "immu16_lo"],
    # immu18: hb[5:0] + hc[5:0] + hd[5:0]（riii/oiii）
    "immu18": ["immu18_hi", "immu18_mid", "immu18_lo"],
}
# SimRISC-03 §浮点分类指令 把 immu6 写成字面量 `1`（唯一给出的签名），
# 归一化回字段名 immu6；此归一化是**记法**归一，不引入任何语义取值。
IMMEDIATE_LITERAL_TO_FIELD = {"1": "immu6"}


class SpecParseError(RuntimeError):
    """规范结构解析失败（fail-closed）。"""


# ───────────────────────────── markdown 表格工具 ─────────────────────────────

def _cells(line: str):
    s = line.strip()
    if not s.startswith("|"):
        return None
    s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def parse_md_table(section_lines, row_re, col_re):
    """解析一个 markdown 表格 → ({(row, col): text}, 空白单元格数, 是否成功)。

    row_re / col_re 各带一个捕获组，group(1) 是二进制串。
    """
    header = None
    sep_idx = None
    for idx, line in enumerate(section_lines):
        cs = _cells(line)
        if cs is None:
            continue
        if header is None:
            if any(col_re.match(c) for c in cs):
                header = cs
            continue
        if sep_idx is None:
            if any(c.startswith("---") for c in cs):
                sep_idx = idx
            continue
        break
    if header is None or sep_idx is None:
        return {}, 0, False

    col_vals = []
    for c in header[1:]:
        m = col_re.match(c)
        col_vals.append(int(m.group(1), 2) if m else None)

    cells, reserved = {}, 0
    for line in section_lines[sep_idx + 1:]:
        cs = _cells(line)
        if not cs:
            continue
        rm = row_re.match(cs[0])
        if rm is None:
            continue
        row_val = int(rm.group(1).replace("-", ""), 2)
        for ci, cell in enumerate(cs[1:]):
            if ci >= len(col_vals) or col_vals[ci] is None:
                continue
            if not cell:
                reserved += 1
                continue
            cells[(row_val, col_vals[ci])] = cell
    return cells, reserved, True


# ───────────────────────────── SimRISC-00 编码提取 ─────────────────────────────

ROW_MAIN = re.compile(r"^(\d{4}-\d)xxx$")
COL_MAIN = re.compile(r"^xxxx-x(\d{3})$")
ROW_SUB = re.compile(r"^(\d{3})-xxx$")
COL_SUB = re.compile(r"^xxx-(\d{3})$")
MISC_PTR = re.compile(r"^MISC-([A-Za-z0-9_-]+)$")
REGISTER_BANKS = frozenset({"rd", "rb", "rf", "ra"})


def parse_cell(text: str, where: str):
    """解析 QFC 单元格 `名称[-bank]-格式`。

    规范里两种写法并存：
      `ftmadd-rrrr`   （无 bank 限定）
      `ld.t-rf-rrii`  （显式 bank 限定，冒名前可含 `-`，如 `ld.o-ra-rrii`）
    返回 {"identity", "mnemonic", "bank", "format"}；无法解析 → SpecParseError。
    """
    parts = text.split("-")
    if len(parts) < 2:
        raise SpecParseError(f"{where}: QFC 单元格无法解析: {text!r}")
    fmt = parts[-1]
    if fmt not in ALL_FORMATS:
        raise SpecParseError(f"{where}: QFC 单元格操作数格式未知: {text!r}")
    head = parts[:-1]
    bank = head[-1] if len(head) >= 2 and head[-1] in REGISTER_BANKS else None
    mnemonic = "-".join(head[:-1]) if bank else "-".join(head)
    return {"identity": text, "mnemonic": mnemonic, "bank": bank, "format": fmt}


def _split_sections(lines):
    main_start = None
    for i, line in enumerate(lines):
        if line.strip().startswith("## SimRISC QFC"):
            main_start = i
            break
    if main_start is None:
        raise SpecParseError("SimRISC-00: 未找到 '## SimRISC QFC' 主表区段")

    main_end = None
    for i in range(main_start + 1, len(lines)):
        if lines[i].startswith("###"):
            main_end = i
            break
    if main_end is None:
        main_end = len(lines)

    sub_starts = [(i, line.strip()) for i, line in enumerate(lines)
                  if line.startswith("###") and "MISC-" in line]
    subs = {}
    for j, (i, title) in enumerate(sub_starts):
        end = sub_starts[j + 1][0] if j + 1 < len(sub_starts) else len(lines)
        if j + 1 == len(sub_starts):
            for k in range(i + 1, len(lines)):
                if lines[k].startswith("## "):
                    end = k
                    break
        m = re.search(r"MISC-[A-Za-z0-9_]+", title)
        subs[m.group(0) if m else title] = lines[i:end]
    return lines[main_start:main_end], subs


def parse_qfc(spec00_path: Path = SPEC00):
    """解析 SimRISC-00 QFC → 编码事实。

    返回 dict：
      encodings  — {(op, ha|None): {"identity","mnemonic","format","subtable"}}
      pointers   — {op: "MISC-xxx"}
      reserved   — 空白单元格总数
    """
    lines = spec00_path.read_text(encoding="utf-8").splitlines(keepends=True)
    main_lines, subs = _split_sections(lines)

    main_cells, main_reserved, ok = parse_md_table(main_lines, ROW_MAIN, COL_MAIN)
    if not ok:
        raise SpecParseError("SimRISC-00: QFC 主表未找到表头/分隔行")

    encodings, pointers, reserved = {}, {}, main_reserved
    for (row_val, col_val), text in main_cells.items():
        op = (row_val << 3) | col_val
        m = MISC_PTR.match(text)
        if m:
            pointers[op] = f"MISC-{m.group(1)}"
            continue
        cell = parse_cell(text, f"SimRISC-00 QFC 主表 @op=0x{op:02X}")
        cell["subtable"] = None
        encodings[(op, None)] = cell

    for op, name in sorted(pointers.items()):
        if name not in subs:
            raise SpecParseError(f"SimRISC-00: 主表指针 {name}@op=0x{op:02X} 无对应子表区段")
        cells, sub_reserved, ok = parse_md_table(subs[name], ROW_SUB, COL_SUB)
        if not ok:
            raise SpecParseError(f"SimRISC-00: 子表 {name} 未找到表头/分隔行")
        reserved += sub_reserved
        for (row_val, col_val), text in sorted(cells.items()):
            ha = (row_val << 3) | col_val
            cell = parse_cell(
                text, f"SimRISC-00 子表 {name} @op=0x{op:02X} ha=0x{ha:02X}")
            cell["subtable"] = name
            encodings[(op, ha)] = cell
    return {"encodings": encodings, "pointers": pointers, "reserved": reserved}


# ───────────────────────── SimRISC-03 identity 提取 ─────────────────────────

SIMRISC_BLOCK = re.compile(r"^```simrisc\s*$")
SIMRISC_HEADING = re.compile(r"^#{1,6}\s+(.*\S)\s*$")
SIMRISC_INSN = re.compile(r"^(?P<mnem>[A-Za-z_][\w.]*)(?P<ops>.*)$")


def strip_simrisc_comment(line: str) -> str:
    """去掉 `simrisc` 代码块内的行内注释（`;` 及其后内容）。

    SimRISC-03 的代码块同时使用整行注释（`; 加载单精浮点 1.0…`）和行尾注释
    （`ft2ft   rfhb, rfhc, immu6          ; 浮点寄存器间搬移`），两者都必须剥离，
    否则 `ft2ft`/`fo2fo` 会被整行丢弃，导致 identity 少 2 条。
    """
    return line.split(";", 1)[0].strip()


def _iter_simrisc_blocks(lines):
    """产出 `simrisc` 代码块的 (section 标题, 行列表)。"""
    block, in_block, section = [], False, "<top>"
    for line in lines:
        raw = line.rstrip("\n")
        if not in_block:
            hm = SIMRISC_HEADING.match(raw)
            if hm:
                section = hm.group(1)
            if SIMRISC_BLOCK.match(raw):
                in_block, block = True, []
            continue
        if raw.strip() == "```":
            yield section, block
            in_block = False
            continue
        block.append(line)
    if in_block:  # fail-loud: 未闭合代码块
        raise SpecParseError("SimRISC-03: 存在未闭合的 ```simrisc 代码块")


def parse_fp_signatures(spec03_path: Path = SPEC03):
    """从 SimRISC-03 `simrisc` 代码块提取 助记符 → 规范操作数签名。

    跳过 `### …伪指令` 小节内的代码块（那些是 pseudo 展开示例，助记符不是
    硬件指令）。返回 {mnemonic: {"operands": [token...], "section": 章节名}}。
    """
    lines = spec03_path.read_text(encoding="utf-8").splitlines(keepends=True)
    sigs: dict[str, dict] = {}
    for section, block in _iter_simrisc_blocks(lines):
        if "伪指令" in section:
            continue
        for raw in block:
            text = strip_simrisc_comment(raw)
            if not text:
                continue
            m = SIMRISC_INSN.match(text)
            if not m:
                continue
            mnem = m.group("mnem")
            ops = [t.strip() for t in m.group("ops").split(",") if t.strip()]
            if not ops:
                continue
            if mnem in sigs:
                prev = sigs[mnem]
                if prev["operands"] != ops:
                    raise SpecParseError(
                        f"SimRISC-03: 助记符 {mnem} 出现两份不同的操作数签名: "
                        f"{prev['operands']} vs {ops}")
                continue
            sigs[mnem] = {"operands": ops, "section": section}
    if not sigs:
        raise SpecParseError("SimRISC-03: 未从任何 simrisc 代码块提取到指令签名")
    return sigs


def parse_pseudo_names(spec03_path: Path = SPEC03):
    """提取 SimRISC-03 §set.ft / set.fo 伪指令 小节声明的**伪指令**名。

    权威来源是小节标题本身（`### set.ft / set.fo 伪指令`）——正文代码块里
    同时出现 `set.w` 等**硬件**指令作为展开结果，不能据正文反推 pseudo 集合。
    """
    text = spec03_path.read_text(encoding="utf-8")
    m = re.search(r"^###\s*(?P<decl>[^\n]*伪指令)\s*$", text, re.MULTILINE)
    if not m:
        raise SpecParseError("SimRISC-03: 未找到 '### …伪指令' 小节")
    names = set(re.findall(r"[A-Za-z_][\w.]*", m.group("decl")))
    names.discard("伪指令")
    if not names:
        raise SpecParseError("SimRISC-03: 伪指令小节标题未声明任何伪指令名")
    return names


# ───────────────────────────── identity 消歧与分组 ─────────────────────────────

def canonical_identity(cell: dict) -> str:
    """QFC 单元格 → F1 **identity** 名（`contracts/opcodes.yaml` 的 `insn` 键）。

    SimRISC-00 QFC 单元格写作 `<助记符>[-<bank>]-<格式>`；identity 取
    `<助记符>[-<bank>]`，即 `ld.t-rf`（bank 限定的浮点 load）、
    `cs.eq-rf`（bank 限定的浮点条件赋值）、`ftadd`（无 bank 限定的 MISC-RF 指令）。
    裸助记符在 QFC 中会被多条编码共用（`ld.t` ⊃ `ld.t-rd`/`ld.t-rf`，
    `cs.eq` ⊃ `cs.eq-rd`/`cs.eq-rf`），因此必须用 identity 消歧，不能用裸助记符。
    """
    return f"{cell['mnemonic']}-{cell['bank']}" if cell["bank"] else cell["mnemonic"]


def _resolve_identity(mnemonic: str, encodings: dict) -> tuple:
    hits = [k for k, v in encodings.items() if v["mnemonic"] == mnemonic]
    if not hits:
        raise SpecParseError(f"SimRISC-03: 助记符 {mnemonic} 在 SimRISC-00 QFC 中无编码")
    if len(hits) == 1:
        return hits[0]
    rf_hits = [k for k in hits if k[1] is None and encodings[k]["bank"] == "rf"]
    if len(rf_hits) == 1:
        return rf_hits[0]
    raise SpecParseError(
        f"SimRISC-03: 助记符 {mnemonic} 无法唯一消歧，候选 "
        + ", ".join(f"op=0x{k[0]:02X} ha={k[1]} → {encodings[k]['identity']}" for k in hits))


def normalize_operands(tokens, fields_has_minor_op: bool):
    """把 SimRISC-03 的签名 token 归一化成与 opcodes.yaml 同形的字段名列表。

    * 字面量立即数（`ftcls rdhb, rfhc, 1`）→ `immu6`（记法归一）
    * 复合立即数名（`imms12` / `immu16`）→ 按 SimRISC-00 §指令域说明 拆成子域
    * 含 minor-opcode 的格式（`orrr`/`orri`）在最前面补 `ha`
    """
    out = []
    for tok in tokens:
        if tok in IMMEDIATE_SPLITS:
            out.extend(IMMEDIATE_SPLITS[tok])
        elif tok in IMMEDIATE_LITERAL_TO_FIELD:
            out.append(IMMEDIATE_LITERAL_TO_FIELD[tok])
        else:
            out.append(tok)
    if fields_has_minor_op:
        out = ["ha"] + out
    return out


def extract(spec00_path: Path = SPEC00, spec03_path: Path = SPEC03):
    """返回 F1 identity 全量提取结果（纯 spec 输入，不读 contracts/）。"""
    qfc = parse_qfc(spec00_path)
    sigs = parse_fp_signatures(spec03_path)
    pseudos = parse_pseudo_names(spec03_path)
    encodings = qfc["encodings"]

    # pseudo 必须不是硬件指令：QFC 里不得出现 set.ft / set.fo
    hardware_mnemonics = {v["mnemonic"] for v in encodings.values()}
    for p in sorted(pseudos):
        if p in hardware_mnemonics:
            raise SpecParseError(
                f"SimRISC-03 把 {p} 声明为伪指令，但 SimRISC-00 QFC 把它当作硬件指令")

    rows = []
    for mnem in sorted(sigs):
        key = _resolve_identity(mnem, encodings)
        enc = encodings[key]
        op, ha = key
        fmt = enc["format"]
        if fmt not in ALL_FORMATS:
            raise SpecParseError(f"SimRISC-00: 未知操作数格式 {fmt!r} @{mnem}")
        group = "misc-rf" if enc["subtable"] == "MISC-RF" else "rf-qfc"
        rows.append({
            "insn": canonical_identity(enc),
            "qfc_cell": enc["identity"],
            "mnemonic": mnem,
            "format": fmt,
            "op": op,
            "ha": ha,
            "mask": 0xFF000000 if ha is None else 0xFFFC0000,
            "value": (op << 24) if ha is None else ((op << 24) | (ha << 18)),
            "subtable": enc["subtable"],
            "group": group,
            "spec_operands": sigs[mnem]["operands"],
            "spec_operands_normalized": normalize_operands(
                sigs[mnem]["operands"], fmt in MINOR_OPCODE_FORMATS),
            "spec_section": sigs[mnem]["section"],
            "minor_opcode_field": fmt in MINOR_OPCODE_FORMATS,
        })

    ids = [r["insn"] for r in rows]
    if len(set(ids)) != len(ids):
        dup = sorted({i for i in ids if ids.count(i) > 1})
        raise SpecParseError(f"SimRISC-03: identity 重复 {dup}")
    if len(ids) != 64:
        raise SpecParseError(f"F1 identity 数量为 {len(ids)}，ADR-1004 D1 要求 64")

    return {
        "qfc": qfc,
        "pseudos": sorted(pseudos),
        "rows": rows,
        "fcsr": parse_fcsr_layout(spec00_path),
        "n_identity": len(rows),
        "n_rf_qfc": sum(1 for r in rows if r["group"] == "rf-qfc"),
        "n_misc_rf": sum(1 for r in rows if r["group"] == "misc-rf"),
    }


# ───────────────────────────── rf0/FCSR 布局提取 ─────────────────────────────

FCSR_ROW = re.compile(
    r"^-\s*\[(\d+)\.\.(\d+)\]\s*[:：]\s*(?P<desc>.+?)\s*$")
RM_ROW = re.compile(r"^\|\s*(?P<code>[01]{2})\s*\|\s*`(?P<mnem>[A-Z]+)`\s*\|")
FLAG_ROW = re.compile(r"^\|\s*(?P<bit>\d)\s*\|\s*`(?P<mnem>[A-Z]+)`\s*\|")


def parse_fcsr_layout(spec00_path: Path = SPEC00):
    """解析 SimRISC-00 §浮点状态寄存器 的位域、舍入模式表与异常标志表。"""
    text = spec00_path.read_text(encoding="utf-8")
    m = re.search(r"^####\s*浮点状态寄存器\s*$", text, re.MULTILINE)
    if not m:
        raise SpecParseError("SimRISC-00: 未找到 '#### 浮点状态寄存器' 小节")
    body = text[m.end():]
    end = re.search(r"^###\s", body, re.MULTILINE)
    if end:
        body = body[:end.start()]

    layout = []
    for line in body.splitlines():
        mm = FCSR_ROW.match(line.strip())
        if mm:
            layout.append({"hi": int(mm.group(1)), "lo": int(mm.group(2)),
                           "desc": mm.group("desc")})

    rm, flags = [], []
    for line in body.splitlines():
        s = line.strip()
        m1 = RM_ROW.match(s)
        if m1 and m1.group("mnem") in {"RNE", "RTZ", "RDN", "RUP"}:
            rm.append({"code": m1.group("code"), "mnemonic": m1.group("mnem")})
            continue
        m2 = FLAG_ROW.match(s)
        if m2 and m2.group("mnem") in {"NV", "DZ", "OF", "UF", "NX"}:
            flags.append({"bit": int(m2.group("bit")), "mnemonic": m2.group("mnem")})

    if len(rm) != 4:
        raise SpecParseError(f"SimRISC-00: 舍入模式表解析出 {len(rm)} 行（期望 4）")
    if len(flags) != 5:
        raise SpecParseError(f"SimRISC-00: 异常状态表解析出 {len(flags)} 行（期望 5）")
    if sum(r["hi"] - r["lo"] + 1 for r in layout) != 64:
        raise SpecParseError(
            f"SimRISC-00: rf0 位域未覆盖 [63:0]（合计 {sum(r['hi'] - r['lo'] + 1 for r in layout)} 位）")

    return {"layout": layout, "rounding_modes": rm, "flags": flags}


# ───────────────────────────── CLI ─────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="F1 浮点 identity 的独立规范提取")
    ap.add_argument("--spec00", type=Path, default=SPEC00)
    ap.add_argument("--spec03", type=Path, default=SPEC03)
    ap.add_argument("--json", type=Path, default=None, help="把结果写入 JSON")
    args = ap.parse_args()

    try:
        res = extract(args.spec00, args.spec03)
        fcsr = parse_fcsr_layout(args.spec00)
    except SpecParseError as e:
        print(f"FATAL: {e}", file=sys.stderr)
        return 2

    print("F1 独立规范提取（仅 SimRISC-00/03，未读 contracts/、未用 generate_opcodes.py）")
    print(f"  spec00: {args.spec00}")
    print(f"  spec03: {args.spec03}")
    print()
    print(f"[QFC] 编码总数: {len(res['qfc']['encodings'])}，"
          f"reserved 空白单元格: {res['qfc']['reserved']}")
    print(f"[QFC] 子表指针: " + ", ".join(
        f"{n}@0x{o:02X}" for o, n in sorted(res['qfc']['pointers'].items())))
    print()
    print(f"[F1 identity] {res['n_identity']} = "
          f"{res['n_rf_qfc']}（rf-qfc）+ {res['n_misc_rf']}（misc-rf）")
    print(f"[pseudo] {len(res['pseudos'])}: {', '.join(res['pseudos'])}（QFC 中无编码，不计入 identity）")
    print()
    hdr = (f"{'insn':<12} {'cell':<15} {'mnem':<9} {'fmt':<5} {'group':<8} "
           f"{'op':>5} {'ha':>5} {'mask':>10} {'value':>10}")
    print(hdr)
    print("-" * len(hdr))
    for r in res["rows"]:
        ha = "  --  " if r["ha"] is None else f"0x{r['ha']:02X}"
        print(f"{r['insn']:<12} {r['qfc_cell']:<15} {r['mnemonic']:<9} {r['format']:<5} "
              f"{r['group']:<8} 0x{r['op']:02X} {ha:>5} 0x{r['mask']:08X} 0x{r['value']:08X}")
    print()
    print("[rf0/FCSR] 位域 / 舍入模式 / 异常标志（SimRISC-00 §浮点状态寄存器）")
    for d in fcsr["layout"]:
        print(f"  [{d['hi']:>2}..{d['lo']:>2}] {d['desc']}")
    print("  rounding: " + ", ".join(f"{r['code']}={r['mnemonic']}" for r in fcsr["rounding_modes"]))
    print("  flags:    " + ", ".join(f"[{f['bit']}]={f['mnemonic']}" for f in fcsr["flags"]))

    if args.json:
        payload = {
            "n_identity": res["n_identity"],
            "n_rf_qfc": res["n_rf_qfc"],
            "n_misc_rf": res["n_misc_rf"],
            "pseudos": res["pseudos"],
            "rows": res["rows"],
            "fcsr": fcsr,
        }
        args.json.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                             encoding="utf-8")
        print(f"\n[写出] {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
