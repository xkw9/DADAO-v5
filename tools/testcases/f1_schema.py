#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""f1_schema.py — TESTCASES-101t 的 F1 向量 schema 事实层与校验引擎。

职责边界（ADR-1004 D3：testcases 单一拥有接口；QEMU/LLVM 只能消费）：

* 本模块**只**从下列权威输入派生事实，**不** import / 调用 LLVM、QEMU、
  SoftFloat、宿主浮点或 libm：
    - ``.xkw/knowledge/contract-f1-floating.md``  （规范归一化合约）
    - ``contracts/f1_gap_proofs.yaml`` 的 ``resolution`` 层（SPEC-104t 投影）
    - ``contracts/opcodes.yaml`` 的 ``f1:`` 块（机器可读同一台账）
    - ``.xkw/knowledge/adr-1008..1015.md``（Accepted 门禁，**独立读文件**）
  全部按**整数位型 / 精确枚举**处理，不出现任何宿主浮点表示。

独立重算（不是从被检查数据自推期望）：
  * 64 identity 集合：解析合约 §1 ``identity-table``，并与 ``opcodes.yaml``
    的 64 条 ``f1:`` 记录、``resolution_matrix`` 的 64 行**三方交叉**。
  * 11 个 facet 键：解析合约 §5.1 facet 表。
  * FCSR 位域：解析合约 §2 ``fcsr-layout`` 表的 ``[hi..lo]`` 范围与只读域的
    **二进制字面量**（``0111 1111 1111 1`` / ``0111 1111 11``），据此算出
    RO/SBZ/RW 掩码与 RO 常量；再与 ``f1_gap_proofs.rf0_fcsr_split.layout``
    交叉。
  * 舍入模式 4 种与异常 flags 5 位：解析合约 §2 的两张表。
  * D11–D16 的受影响 identity 集：解析合约 §6 ``d-matrix``，与
    ``resolution.rule_tables`` 的 scope 交叉。
  * D11 十条 rf0 写白名单：**从 ADR-1009 D2 正文解析** identity 名，不用
    ``rule_tables`` 里的现成列表。
  * D17 六个 active OPEN-ID：字面量钉死（PIN_D17_ACTIVE_KEYS），再与合约 §6.2
    ledger 键集合（减去 S7）、``trace_only``（S2）、``non_gap_records``
    （S7）交叉。

本模块不含 PASS/FAIL 汇总逻辑，也不含逐 case 校验；逐 case 校验在
``f1_cases.py``（返回 error 字符串列表），由 ``validate_vectors.py`` /
``check_f1_context.py`` 决定退出码。
"""

from __future__ import annotations

import os
import re

import yaml

# ────────────────────────────── 路径 ──────────────────────────────
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONTRACT_REL = ".xkw/knowledge/contract-f1-floating.md"
GAPS_REL = "contracts/f1_gap_proofs.yaml"
OPCODES_REL = "contracts/opcodes.yaml"
SCHEMA_REL = "tests/vectors/schema.md"
ORACLE_DOC_REL = "docs/testcases/f1-oracle-io.md"
F1_VEC_DIR_REL = "tests/vectors/f1"

# 语义承载 ADR：facet → ADR（D11..D16），D17 兜底 → ADR-1015。
PIN_FACET_TO_D = {
    "rf0_operand": "D11",
    "fcsr_flags": "D12",
    "tetra_high_half": "D13",
    "compare_unordered": "D14",
    "nan_propagation": "D15",
    "tininess": "D16",
}
PIN_D_TO_ADR = {
    "D11": "ADR-1009",
    "D12": "ADR-1010",
    "D13": "ADR-1011",
    "D14": "ADR-1012",
    "D15": "ADR-1013",
    "D16": "ADR-1014",
    "D17": "ADR-1015",
}
PIN_NON_GAP_ADR = "ADR-1008"
PIN_ACTIVATION_ADRS = ("ADR-1009", "ADR-1010", "ADR-1011", "ADR-1012",
                       "ADR-1013", "ADR-1014", "ADR-1015")
PIN_NON_GAP_REQUIRED_ADR = "ADR-1008"

# D17 OPEN-ID ledger：active 精确键集合（六键），字面量钉死。
PIN_D17_ACTIVE_KEYS = ("D17:S1", "D17:S3", "D17:S4", "D17:S5", "D17:S6", "D17:S8")
PIN_D17_TRACE_ONLY = "D17:S2"     # ledger 外 trace-only，永不 blocked、永不 PASS
PIN_D17_NON_GAP = "D17:S7"        # ADR-1008 D1 证明的 spec-determined non-gap
# facet 级 blocked 时允许引用的 OPEN/S-ID 词表（六键 + D11..D16 decision id）
PIN_OPEN_ID_VOCAB = PIN_D17_ACTIVE_KEYS + ("D11", "D12", "D13", "D14", "D15", "D16")
# 永远不得出现在任何阻塞/期望位置的键
PIN_NEVER_BLOCKED = (PIN_D17_TRACE_ONLY, PIN_D17_NON_GAP)

# 案例级 blocked_points 词表（**未决实现输入 / 能力缺口**，不是 facet 级 OPEN-ID）
PIN_BLOCKED_POINT_VOCAB = (
    "D15:canonical_qnan_bits",            # ADR-1013 未给 64 位常量（rule_tables 为 null）
    "CAP-01:root-log-correct-rounding",   # resolution.capability_gaps CAP-01
)
# 规范明示「不做具体要求」的点：永不生成唯一 expected
PIN_UNSPEC_POINTS = ("rootn(-0,2)",)
PIN_UNSPEC_IDENTITIES = ("foroot", "ftroot")

# F1 允许的 fault 词表（沿用 tests/vectors/schema.md 的 M1 词表）
F1_FAULTS = (None, "ILLI", "MALIGN")
F1_BLOCK_KINDS = ("ldm.o-rf", "ldm.t-rf", "stm.o-rf", "stm.t-rf")
F1_MEMORY_WIDTHS = (1, 2, 4, 8)
F1_OBS_ORDER_KINDS = ("read-before-write", "block-increasing", "none")
# 身份 → 块操作形态的判据（由合约 §1 的 SimRISC-03 小节 + 助记符决定）
F1_BLOCK_SECTIONS = ("格式转换指令", "寄存器组之间块赋值")
F1_BLOCK_PREFIXES = ("ldm.", "stm.")
# 分类指令 immu6 固定为 1（合约 §4.8 / ADR-1015 D2）
F1_CLASSIFY_IDS = ("ftcls", "focls")
F1_CLASSIFY_IMMU6 = 1


# ─────────────────── 字面量基准（政策，不是从数据反推） ───────────────────
PIN_FACET_KEYS = (
    "encoding", "format", "operands", "legality", "semantics",
    "rf0_operand", "tetra_high_half", "fcsr_flags", "tininess",
    "compare_unordered", "nan_propagation",
)
PIN_FACET_STATUS = ("active", "blocked")
PIN_ROUNDING_MODES = ("RNE", "RTZ", "RDN", "RUP")
PIN_FCSR_FLAGS = ("NV", "DZ", "OF", "UF", "NX")
PIN_AUTHORITY_TOKENS = ("README.md", "spec/SimRISC-00-指令系统设计.md",
                        "spec/SimRISC-03-浮点类指令.md",
                        ".xkw/knowledge/adr-1004-f1-floating-phase.md",
                        ".xkw/knowledge/contract-f1-floating.md",
                        "contracts/opcodes.yaml")
PIN_D11_SCOPE_EXPECT = 37
PIN_D12_SCOPE_EXPECT = 53
PIN_D13_SCOPE_EXPECT = 18
PIN_D14_SCOPE_EXPECT = 4
PIN_D15_SCOPE_EXPECT = 18
PIN_D16_SCOPE_EXPECT = 36
PIN_RF0_WRITE_WHITELIST_N = 10

HEX64_RE = re.compile(r"^0x[0-9a-fA-F]{1,16}$")
RF_KEY_RE = re.compile(r"^rf(0|[1-9][0-9]?)$")
RD_KEY_RE = re.compile(r"^rd(0|[1-9][0-9]?)$")
RB_KEY_RE = re.compile(r"^rb(0|[1-9][0-9]?)$")
RA_KEY_RE = re.compile(r"^ra([0-9]|[1-9][0-9]?)$")
BITS_RE = re.compile(r"^\[(\d+)(?:\.\.|:)(\d+)\]$")
DECISION_RE = re.compile(r"^ADR-\d{4}/D\d+$")


# ─────────────────────────── 基础工具 ───────────────────────────
def mask_of(hi, lo):
    """[hi..lo] → 掩码。"""
    return ((1 << (hi - lo + 1)) - 1) << lo


def hex64(v):
    return "0x%016x" % (v & 0xFFFFFFFFFFFFFFFF)


def parse_hex64(val, what, errors, tag):
    """把 '0x...' 解析成 64 位整数；失败时 append error 并返回 None。"""
    if isinstance(val, int) and not isinstance(val, bool):
        if 0 <= val <= 0xFFFFFFFFFFFFFFFF:
            return val
        errors.append("%s: %s integer out of 64-bit range: %r" % (tag, what, val))
        return None
    if not isinstance(val, str) or not HEX64_RE.match(val.strip()):
        errors.append("%s: %s not a 0x-prefixed 64-bit bit pattern: %r"
                      % (tag, what, val))
        return None
    return int(val.strip(), 16)


def _md_table_rows(text, first_cell_startswith=None):
    """返回 Markdown 表格的数据行（list[list[str]]），已跳过表头/分隔行。"""
    rows = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
            continue
        if first_cell_startswith is None:
            rows.append(cells)
        elif cells and cells[0].startswith(first_cell_startswith):
            rows.append(cells)
    return rows


def _generated_block(text, name):
    m = re.search(r"<!-- f1:generated:%s -->(.*?)<!-- /f1:generated:%s -->"
                  % (re.escape(name), re.escape(name)), text, re.S)
    return m.group(1) if m else ""


def _field_value(word, fields, name):
    for f in fields:
        if f.get("name") == name:
            m = BITS_RE.match(str(f.get("bits", "")))
            if not m:
                return None
            hi, lo = int(m.group(1)), int(m.group(2))
            return (word >> lo) & ((1 << (hi - lo + 1)) - 1)
    return None


def sext(value, bits):
    if value is None:
        return None
    if value & (1 << (bits - 1)):
        return value - (1 << bits)
    return value


# ───────────────── 指令字字段解码（纯整数，不用宿主浮点） ─────────────────
_MULTI_SUFFIX = ("_hi", "_mid", "_lo")


def decode_fields(word, record):
    """把 32 位指令字解成 opcodes.yaml 的字段值（含 imms12/immu16 复合字段）。

    复合字段按 ``_hi``/``_mid``/``_lo`` 后缀归并：按位号从高到低拼回原值，
    任一片 ``signed: true`` 则对拼回后的总位宽做符号扩展。返回
    ``(fields_by_name, errors)``；``fields_by_name`` 同时给出**原始**单字段名，
    便于 case 逐位核对。
    """
    errors = []
    raw = {}
    groups = {}
    for f in record.get("fields") or []:
        m = BITS_RE.match(str(f.get("bits", "")))
        if not m:
            errors.append("opcodes.yaml field %s has unparsable bits %r"
                          % (f.get("name"), f.get("bits")))
            continue
        hi, lo = int(m.group(1)), int(m.group(2))
        raw[f["name"]] = (word >> lo) & ((1 << (hi - lo + 1)) - 1)
        name = f["name"]
        base = name
        for suf in _MULTI_SUFFIX:
            if name.endswith(suf):
                base = name[:-len(suf)]
                break
        groups.setdefault(base, []).append((hi, lo, name, bool(f.get("signed"))))
    out = dict(raw)
    for base, parts in groups.items():
        if len(parts) == 1 and parts[0][2] == base:
            out[base] = raw[base]
            continue
        parts.sort(key=lambda p: p[0], reverse=True)   # 高位在前
        total = sum(p[0] - p[1] + 1 for p in parts)
        acc = 0
        for _hi, _lo, name, _sg in parts:
            width = None
            for f in record.get("fields") or []:
                if f["name"] == name:
                    mm = BITS_RE.match(str(f.get("bits", "")))
                    width = int(mm.group(1)) - int(mm.group(2)) + 1
                    break
            acc = (acc << width) | raw[name]
        signed = any(p[3] for p in parts)
        out[base] = sext(acc, total) if signed else acc
    return out, errors


def encode_check(word, record):
    """F1 编码一致性：``(word & mask) == (value & mask)``。

    与 M1 的 ``(word & mask) == value`` 不同：F1 记录的 ``value`` 固化了
    minor-op 所在的 ``ha`` 字段（如 ``foadd`` = ``0x44600000``），而 ``mask``
    只覆盖 ``op``（``0xFF000000``），故须两侧同时取掩码后比较。
    """
    mask = int(str(record.get("mask")), 16)
    value = int(str(record.get("value")), 16)
    return ((word & mask) == (value & mask)), mask, value


# ─────────────────────── 合约事实（独立重算） ───────────────────────
def load_contract_facts(root=REPO_ROOT):
    """从 ``contract-f1-floating.md`` 独立重算 F1 schema 事实。

    返回 dict；解析失败时 ``errors`` 非空（调用方必须把它变成非零退出）。
    """
    path = os.path.join(root, CONTRACT_REL)
    errors = []
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        return {"errors": ["cannot read %s: %s" % (CONTRACT_REL, exc)]}

    # ── §1 identity 表（64 = 18 rf-qfc + 46 misc-rf）──────────────
    identities = {}
    for cells in _md_table_rows(_generated_block(text, "identity-table")):
        if not cells[0].startswith("`"):
            continue
        ident = cells[0].strip("`")
        if ident.startswith("identity"):
            continue
        if len(cells) < 10:
            errors.append("contract identity-table row too short: %r" % (cells,))
            continue
        identities[ident] = {
            "identity": ident,
            "mnemonic": cells[1].strip("`"),
            "format": cells[2].strip("`"),
            "group": cells[3].strip("`"),
            "op": cells[4].strip("`"),
            "ha": None if cells[5].strip() == "—" else cells[5].strip("`"),
            "mask": cells[6].strip("`"),
            "value": cells[7].strip("`"),
            "section": cells[8].strip("`"),
            "operands": [o.strip() for o in cells[9].split(",")],
        }
    n_rfqfc = sum(1 for v in identities.values() if v["group"] == "rf-qfc")
    n_misc = sum(1 for v in identities.values() if v["group"] == "misc-rf")
    if len(identities) != 64:
        errors.append("contract identity-table: expected 64 identities, got %d"
                      % len(identities))
    if n_rfqfc != 18 or n_misc != 46:
        errors.append("contract identity-table split: rf-qfc=%d misc-rf=%d "
                      "(expect 18/46)" % (n_rfqfc, n_misc))

    # ── §5.1 facet 键（11）───────────────────────────────────────
    facet_keys = []
    for cells in _md_table_rows(_generated_block(text, "facet-table")):
        key = cells[0].strip("`")
        if key in PIN_FACET_KEYS:
            facet_keys.append(key)
    if tuple(facet_keys) != PIN_FACET_KEYS:
        errors.append("contract facet keys: got %r, expect %r"
                      % (facet_keys, list(PIN_FACET_KEYS)))

    # ── §2 FCSR 位域 + 舍入模式 + flags ──────────────────────────
    layout = _generated_block(text, "fcsr-layout")
    domains = []           # [(hi, lo, access, ro_value_or_None)]
    for cells in _md_table_rows(layout):
        m = BITS_RE.match(cells[0].strip("`"))
        if not m or len(cells) < 3:
            continue
        hi, lo = int(m.group(1)), int(m.group(2))
        access = ("read-only" if "只读" in cells[2] else
                  "SBZ" if "SBZ" in cells[2] else "rw")
        ro_val = None
        if access == "read-only":
            lit = cells[1].split("（")[0].strip()
            lit = lit.replace(" ", "")
            try:
                ro_val = int(lit, 2)
            except ValueError:
                errors.append("contract fcsr read-only literal not binary: %r"
                              % cells[1])
        domains.append((hi, lo, access, ro_val))
    if len(domains) != 7:
        errors.append("contract fcsr-layout: expected 7 bit domains, got %d"
                      % len(domains))
    ro_mask = sum(mask_of(h, l) for h, l, a, _ in domains if a == "read-only")
    ro_val = 0
    for h, l, a, v in domains:
        if a == "read-only" and v is not None:
            ro_val |= (v << l) & mask_of(h, l)
    sbz_mask = sum(mask_of(h, l) for h, l, a, _ in domains if a == "SBZ")
    rw_mask = sum(mask_of(h, l) for h, l, a, _ in domains if a == "rw")
    if (ro_mask | sbz_mask | rw_mask) != 0xFFFFFFFFFFFFFFFF:
        errors.append("contract fcsr domains do not tile 64 bits: ro=%s sbz=%s rw=%s"
                      % (hex64(ro_mask), hex64(sbz_mask), hex64(rw_mask)))
    if (ro_mask & sbz_mask) or (ro_mask & rw_mask) or (sbz_mask & rw_mask):
        errors.append("contract fcsr domains overlap")

    rm_codes = {}
    for cells in _md_table_rows(layout):
        if len(cells) < 2:
            continue
        m = re.fullmatch(r"`([01]{2})`", cells[0])
        if m and cells[1].strip("`") in PIN_ROUNDING_MODES:
            rm_codes[cells[1].strip("`")] = int(m.group(1), 2)
    if sorted(rm_codes) != sorted(PIN_ROUNDING_MODES):
        errors.append("contract rounding-mode table: got %r, expect %r"
                      % (sorted(rm_codes), sorted(PIN_ROUNDING_MODES)))

    flag_bits = {}
    for cells in _md_table_rows(layout):
        if len(cells) < 2:
            continue
        m = re.fullmatch(r"`(\d+)`", cells[0])
        if m and cells[1].strip("`") in PIN_FCSR_FLAGS:
            flag_bits[cells[1].strip("`")] = int(m.group(1))
    if sorted(flag_bits) != sorted(PIN_FCSR_FLAGS):
        errors.append("contract fcsr flag table: got %r, expect %r"
                      % (sorted(flag_bits), sorted(PIN_FCSR_FLAGS)))
    for name, bit in flag_bits.items():
        if not (0 <= bit <= 4):
            errors.append("contract fcsr flag %s bit %d outside [4:0]" % (name, bit))

    # ── §3.1 谓词词表 / §3.2 逐 identity fault 集合 ──────────────
    m31 = re.search(r"### 3\.1 谓词词表(.*?)### 3\.2", text, re.S)
    predicates = {}
    if m31:
        for cells in _md_table_rows(m31.group(1)):
            pred = cells[0].strip("`")
            if pred and re.fullmatch(r"[A-Za-z0-9_()]+", pred):
                predicates[pred] = cells[2] if len(cells) > 2 else ""
    if len(predicates) < 9:
        errors.append("contract §3.1 predicate vocabulary: got %d entries %r"
                      % (len(predicates), sorted(predicates)))
    m32 = re.search(r"### 3\.2 逐 identity 的 fault 集合(.*?)<!-- /f1:generated:legality -->",
                    text, re.S)
    fault_sets = {}
    if m32:
        for cells in _md_table_rows(m32.group(1)):
            ident = cells[0].strip("`")
            if ident not in identities or len(cells) < 3:
                continue
            faults = [] if "无 fault" in cells[1] else [
                f.strip() for f in cells[1].split("、") if f.strip()]
            preds = [] if cells[2].strip() == "—" else [
                p.strip().strip("`") for p in cells[2].split(",") if p.strip()]
            fault_sets[ident] = {"faults": faults, "predicates": preds,
                                 "legality_facet": cells[3].strip("`")
                                 if len(cells) > 3 else ""}
    if len(fault_sets) != 64:
        errors.append("contract §3.2 fault sets: got %d identities, expect 64"
                      % len(fault_sets))

    # ── §6 D-matrix：逐 identity 的 D11..D16 受影响 facet ─────────
    dmatrix = {}
    for cells in _md_table_rows(_generated_block(text, "d-matrix")):
        ident = cells[0].strip("`")
        if ident not in identities or len(cells) < 8:
            continue
        dmatrix[ident] = {
            "D11": cells[1].strip("`"),
            "D12": cells[2].strip("`"),
            "D13": cells[3].strip("`"),
            "D14": cells[4].strip("`"),
            "D15": cells[5].strip("`"),
            "D16": cells[6].strip("`"),
            "D17": cells[7].strip("`"),
        }
    if len(dmatrix) != 64:
        errors.append("contract d-matrix: got %d identities, expect 64"
                      % len(dmatrix))

    return {
        "errors": errors,
        "identities": identities,
        "facet_keys": tuple(facet_keys),
        "fcsr": {
            "domains": domains,
            "ro_mask": ro_mask, "ro_value": ro_val,
            "sbz_mask": sbz_mask, "rw_mask": rw_mask,
            "rounding_modes": rm_codes,
            "flags": flag_bits,
        },
        "predicates": predicates,
        "fault_sets": fault_sets,
        "dmatrix": dmatrix,
    }


# ─────────────────── ADR-1009 正文解析（D11 白名单） ───────────────────
def parse_adr_d11_whitelist(root=REPO_ROOT):
    """从 ADR-1009 D2 正文解析十条 rf0 写白名单 identity（不用 rule_tables）。"""
    path = os.path.join(root, ".xkw", "knowledge",
                        "adr-1009-d11-rf0-operand-rules.md")
    errors = []
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        return [], ["cannot read ADR-1009: %s" % exc]
    m = re.search(r"###\s*D2[：:].*?(?=\n###|\n##\s)", text, re.S)
    if not m:
        return [], ["ADR-1009: cannot locate `### D2：` section"]
    body = m.group(0)
    quoted = re.findall(r"`([a-z][a-z0-9.]*-rf)`", body)
    seen, out = set(), []
    for q in quoted:
        if q not in seen:
            seen.add(q)
            out.append(q)
    if len(out) != PIN_RF0_WRITE_WHITELIST_N:
        errors.append("ADR-1009 D2: parsed %d rf0-write identities %r, expect %d"
                      % (len(out), out, PIN_RF0_WRITE_WHITELIST_N))
    return out, errors


def read_adr_states(root=REPO_ROOT):
    """读 ADR-1008..1015 的 ``**状态**：`` 字段（激活门禁，独立于 YAML）。"""
    files = {
        "ADR-1008": "adr-1008-rd-rf-non-overlap.md",
        "ADR-1009": "adr-1009-d11-rf0-operand-rules.md",
        "ADR-1010": "adr-1010-d12-fcsr-flags.md",
        "ADR-1011": "adr-1011-d13-tetra-high-half.md",
        "ADR-1012": "adr-1012-d14-unordered-compare-nan.md",
        "ADR-1013": "adr-1013-d15-nan-propagation.md",
        "ADR-1014": "adr-1014-d16-tininess-flags.md",
        "ADR-1015": "adr-1015-d17-silent-semantics.md",
    }
    states, errors = {}, []
    for adr, name in files.items():
        path = os.path.join(root, ".xkw", "knowledge", name)
        try:
            with open(path, encoding="utf-8") as fh:
                head = fh.read(4096)
        except OSError as exc:
            errors.append("cannot read %s: %s" % (name, exc))
            states[adr] = None
            continue
        m = re.search(r"\*\*状态\*\*[：:]\s*([A-Za-z\-]+)", head)
        states[adr] = m.group(1) if m else None
        if states[adr] is None:
            errors.append("%s: no `**状态**：` field found" % name)
    return states, errors


def read_decision_headings(root=REPO_ROOT):
    """读每份 ADR 的现行 decision 标题集合（``### Dn：…``）。"""
    out = {}
    for adr in ("ADR-1009", "ADR-1010", "ADR-1011", "ADR-1012",
                "ADR-1013", "ADR-1014", "ADR-1015"):
        fname = "adr-%s-%s.md" % (adr.split("-")[1],
                                  {"ADR-1009": "d11-rf0-operand-rules",
                                   "ADR-1010": "d12-fcsr-flags",
                                   "ADR-1011": "d13-tetra-high-half",
                                   "ADR-1012": "d14-unordered-compare-nan",
                                   "ADR-1013": "d15-nan-propagation",
                                   "ADR-1014": "d16-tininess-flags",
                                   "ADR-1015": "d17-silent-semantics"}[adr])
        path = os.path.join(root, ".xkw", "knowledge", fname)
        heads = set()
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                m = re.match(r"###\s*(D\d+)[：:]", line)
                if m:
                    heads.add(m.group(1))
        out[adr] = heads
    return out


# ─────────────────────── resolution 层（设计输入） ───────────────────────
def load_resolution(root=REPO_ROOT):
    path = os.path.join(root, GAPS_REL)
    with open(path, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    res = doc.get("resolution") or {}
    rt = res.get("rule_tables") or {}
    rows = res.get("resolution_matrix") or []
    return {
        "rule_tables": rt,
        "matrix": {r["identity"]: r for r in rows if isinstance(r, dict)
                   and "identity" in r},
        "capability_gaps": res.get("capability_gaps") or [],
        "historical_layer": {
            "rf0_fcsr_split": doc.get("rf0_fcsr_split") or {},
            "d17_open_ledger": sorted((doc.get("d17_open_ledger") or {}).keys()),
            "trace_only": sorted((doc.get("trace_only") or {}).keys()),
            "non_gap_records": sorted((doc.get("non_gap_records") or {}).keys()),
        },
    }


def load_f1_opcode_records(root=REPO_ROOT):
    with open(os.path.join(root, OPCODES_REL), encoding="utf-8") as fh:
        recs = yaml.safe_load(fh)
    out = {}
    for rec in recs:
        f1 = rec.get("f1")
        if isinstance(f1, dict) and f1.get("in_scope"):
            out[rec["insn"]] = rec
    return out


# ─────────────────────────── F1Context ───────────────────────────
class F1Context(object):
    """把合约重算、resolution 投影、opcodes 与 ADR 门禁绑在一起。"""

    def __init__(self, root=REPO_ROOT, adr_gate="auto"):
        self.root = root
        self.adr_gate = adr_gate            # auto | open | closed
        self.errors = []
        self.facts = load_contract_facts(root)
        self.errors.extend(self.facts["errors"])
        self.whitelist, wl_err = parse_adr_d11_whitelist(root)
        self.errors.extend(wl_err)
        self.adr_states, adr_err = read_adr_states(root)
        self.errors.extend(adr_err)
        self.decision_headings = read_decision_headings(root)
        self.resolution = load_resolution(root)
        self.opcodes = load_f1_opcode_records(root)
        self.divergences = self.d17_opcodes_divergences()
        self._cross_check()
        if adr_gate == "open":
            self.gate_open = True
        elif adr_gate == "closed":
            self.gate_open = False
        else:
            self.gate_open = all(
                self.adr_states.get(a) == "Accepted" for a in PIN_ACTIVATION_ADRS
            ) and self.adr_states.get(PIN_NON_GAP_REQUIRED_ADR) == "Accepted"

    # -- 便捷访问 -------------------------------------------------
    @property
    def identities(self):
        return self.facts["identities"]

    @property
    def fcsr(self):
        return self.facts["fcsr"]

    @property
    def rt(self):
        return self.resolution["rule_tables"]

    @property
    def matrix(self):
        return self.resolution["matrix"]

    def rec(self, identity):
        return self.opcodes.get(identity)

    def d17_active_keys_for(self, identity):
        """该 identity 命中的**六个** active OPEN-ID。

        `contracts/opcodes.yaml` 的 `f1.d17_open_ids` 是 SPEC-102t 的历史投影，
        `rd2rf` 那一行**仍带 `D17:S7`**；而 ADR-1008 D1 已把 S7 定为
        spec-determined non-gap，SPEC-103t 返工后的 `f1_gap_proofs.yaml` 也把它
        移出 `d17_open_ledger`。ADR-1008 D1 明文要求「后续 F1 消费者**不得**把
        `D17:S7` 作为 active OPEN 门禁」，故这里**按钉死的六键取交集**再返回，
        而不是照抄 opcodes.yaml。该只读分歧登记在
        `docs/testcases/f1-oracle-io.md` 的「只读分歧登记」，并由
        ``self.divergences`` 逐条打印，不静默吞掉。
        """
        rec = self.rec(identity) or {}
        raw = (rec.get("f1") or {}).get("d17_open_ids") or []
        return sorted(k for k in raw if k in PIN_D17_ACTIVE_KEYS)

    def d17_opcodes_divergences(self):
        """`opcodes.yaml` 的 `d17_open_ids` 与钉死六键 / non-gap 判定的分歧。"""
        out = []
        for ident in sorted(self.opcodes):
            raw = (self.rec(ident) or {}).get("f1", {}).get("d17_open_ids") or []
            extra = [k for k in raw if k not in PIN_D17_ACTIVE_KEYS]
            if not extra:
                continue
            for k in extra:
                if k == PIN_D17_TRACE_ONLY:
                    out.append("%s: opcodes.yaml f1.d17_open_ids 含 %s，违反合约 "
                               "§6.2「永不含 D17:S2」的明文承诺" % (ident, k))
                elif k == PIN_D17_NON_GAP:
                    out.append("%s: opcodes.yaml f1.d17_open_ids 仍列 %s，但 "
                               "ADR-1008 D1 已定为 spec-determined non-gap；"
                               "消费侧按六键取交集" % (ident, k))
                else:
                    out.append("%s: opcodes.yaml f1.d17_open_ids 含未知键 %s"
                               % (ident, k))
        return out

    def d_scope(self, decision):
        """由合约 §6 D-matrix 独立重算某 decision 的受影响 identity 集。"""
        return {i for i, row in self.facts["dmatrix"].items()
                if row.get(decision) and row[decision] != "-"}

    def facet_governed_by(self, identity, facet):
        """该 identity 的该 facet 是否由某个 D* 决定（否则 spec-determined）。"""
        dec = PIN_FACET_TO_D.get(facet)
        if not dec:
            return None
        return dec if identity in self.d_scope(dec) else None

    def rf0_write_allowed(self, identity):
        return identity in self.whitelist

    def d13_scope(self):
        return self.d_scope("D13")

    def d14_scope(self):
        return self.d_scope("D14")

    def d12_automatic(self):
        rt = self.rt.get("D12") or {}
        return set(rt.get("automatic_scope") or [])

    def d12_non_automatic(self):
        rt = self.rt.get("D12") or {}
        return set(rt.get("non_automatic_scope") or [])

    def d15_arithmetic(self):
        rt = self.rt.get("D15") or {}
        return set(rt.get("arithmetic_scope") or [])

    def d15_conversion(self):
        rt = self.rt.get("D15") or {}
        return set(rt.get("conversion_scope") or [])

    def d16_scope(self):
        return self.d_scope("D16")

    def d14_unordered_bits(self, identity):
        rt = self.rt.get("D14") or {}
        if identity in (rt.get("quiet_class") or []):
            return int(str(rt.get("quiet_unordered_bits")), 16)
        if identity in (rt.get("signaling_class") or []):
            return int(str(rt.get("signaling_unordered_bits")), 16)
        return None

    def d13_high32(self):
        rt = self.rt.get("D13") or {}
        v = rt.get("tetra_high_half_value")
        if v is None:
            bits = str(rt.get("tetra_high_half_bits") or "")
            try:
                v = int(bits, 16)
            except ValueError:
                return None
        return int(v) & 0xFFFFFFFF

    def canonical_qnan_bits(self):
        """ADR-1013 未给 64 位常量 → 必须保持 null（不得代填）。"""
        rt = self.rt.get("D15") or {}
        return rt.get("canonical_qnan_bits")

    def is_block_identity(self, identity):
        info = self.identities.get(identity) or {}
        sect = info.get("section", "")
        mnem = info.get("mnemonic", "")
        if sect in F1_BLOCK_SECTIONS:
            return True
        return any(mnem.startswith(p) for p in F1_BLOCK_PREFIXES)

    def block_count(self, identity, word, fields):
        info = self.identities.get(identity) or {}
        if identity in F1_CLASSIFY_IDS:
            return _field_value(word, fields, "immu6")
        if not self.is_block_identity(identity):
            return None
        return _field_value(word, fields, "immu6")

    def block_width(self, identity):
        info = self.identities.get(identity) or {}
        mnem = info.get("mnemonic", "")
        sect = info.get("section", "")
        if mnem.endswith(".t") or sect == "存取RF寄存器" and mnem.endswith(".t"):
            return 4
        if mnem.endswith(".o"):
            return 8
        if sect == "格式转换指令":
            # 源格式决定元素宽度：fo2xx/xx2fo 为 8；ft2xx/xx2ft 为 4
            return 4 if (mnem.startswith("ft") or mnem.endswith("2ft")) else 8
        return None

    def dst_fields(self, identity):
        rec = self.rec(identity) or {}
        return [f for f in (rec.get("fields") or []) if f.get("role") == "dst"]

    # -- 三方交叉 -------------------------------------------------
    def _cross_check(self):
        ids = set(self.identities)
        ops = set(self.opcodes)
        mat = set(self.matrix)
        if ids != ops:
            self.errors.append(
                "identity universe mismatch contract vs opcodes.yaml: "
                "contract-only=%r opcodes-only=%r"
                % (sorted(ids - ops)[:6], sorted(ops - ids)[:6]))
        if ids != mat:
            self.errors.append(
                "identity universe mismatch contract vs resolution_matrix: "
                "contract-only=%r matrix-only=%r"
                % (sorted(ids - mat)[:6], sorted(mat - ids)[:6]))

        rt = self.rt
        # D11 白名单三方一致
        wl_rt = set((rt.get("D11") or {}).get("rf0_write_whitelist") or [])
        if set(self.whitelist) != wl_rt:
            self.errors.append(
                "D11 rf0-write whitelist mismatch ADR-1009(%r) vs rule_tables(%r)"
                % (sorted(self.whitelist), sorted(wl_rt)))
        for ident in self.whitelist:
            rec = self.rec(ident) or {}
            if not rec:
                self.errors.append("D11 whitelist %s missing from opcodes.yaml f1 "
                                   "block" % ident)

        # D11..D16 受影响规模：合约 D-matrix vs 期望基数 vs rule_tables scope
        for dec, expect in (("D11", PIN_D11_SCOPE_EXPECT),
                            ("D12", PIN_D12_SCOPE_EXPECT),
                            ("D13", PIN_D13_SCOPE_EXPECT),
                            ("D14", PIN_D14_SCOPE_EXPECT),
                            ("D15", PIN_D15_SCOPE_EXPECT),
                            ("D16", PIN_D16_SCOPE_EXPECT)):
            got = self.d_scope(dec)
            if len(got) != expect:
                self.errors.append("contract D-matrix %s scope=%d, expect %d"
                                   % (dec, len(got), expect))
        if self.d13_scope() != set((rt.get("D13") or {}).get("write_scope") or []):
            self.errors.append("D13 scope mismatch contract D-matrix vs rule_tables")
        if self.d14_scope() != set((rt.get("D14") or {}).get("scope") or []):
            self.errors.append("D14 scope mismatch contract D-matrix vs rule_tables")
        if self.d12_automatic() != self.d_scope("D12"):
            self.errors.append("D12 automatic_scope(%d) != contract D-matrix(%d)"
                               % (len(self.d12_automatic()),
                                  len(self.d_scope("D12"))))
        if (self.d12_automatic() | self.d12_non_automatic()) != ids:
            self.errors.append("D12 automatic+non-automatic != 64 identities")
        if self.d15_arithmetic() != self.d_scope("D15"):
            self.errors.append("D15 arithmetic_scope(%d) != contract D-matrix(%d)"
                               % (len(self.d15_arithmetic()),
                                  len(self.d_scope("D15"))))
        # fo2ft/ft2fo 在合约 facet 表里是 nan_propagation=partial，故 D15 列为 `-`；
        # 它们只在 resolution 的 conversion_scope 里出现（ADR-1013 D4/D6）。
        conv = self.d15_conversion()
        if not conv or (conv & self.d_scope("D15")):
            self.errors.append("D15 conversion_scope %r must be disjoint from the "
                               "D-matrix D15 column" % (sorted(conv),))
        if self.d16_scope() != set((rt.get("D16") or {}).get("scope") or []):
            self.errors.append("D16 scope mismatch contract D-matrix vs rule_tables")

        # D17 台账：合约 ledger 键 / trace-only / non-gap 三方
        hist = self.resolution["historical_layer"]
        # SPEC-103t 返工后历史 ledger 层只保留六个 active OPEN-ID；
        # D17:S7 已降为 non_gap_records，故不得再出现在 d17_open_ledger。
        ledger6 = set(hist["d17_open_ledger"])
        if ledger6 != set(PIN_D17_ACTIVE_KEYS):
            self.errors.append("historical d17_open_ledger keys %r != pinned six"
                               % (sorted(ledger6),))
        if hist["trace_only"] != [PIN_D17_TRACE_ONLY]:
            self.errors.append("trace_only keys %r != ['%s']"
                               % (hist["trace_only"], PIN_D17_TRACE_ONLY))
        if PIN_D17_NON_GAP not in hist["non_gap_records"]:
            self.errors.append("non_gap_records lacks %s" % PIN_D17_NON_GAP)
        if set((rt.get("D17") or {}).get("active_keys") or []) != set(PIN_D17_ACTIVE_KEYS):
            self.errors.append("rule_tables.D17.active_keys %r != pinned six"
                               % ((rt.get("D17") or {}).get("active_keys"),))
        if (rt.get("D17") or {}).get("trace_only") != PIN_D17_TRACE_ONLY:
            self.errors.append("rule_tables.D17.trace_only != %s"
                               % PIN_D17_TRACE_ONLY)
        if (rt.get("D17") or {}).get("historical_non_gap") != PIN_D17_NON_GAP:
            self.errors.append("rule_tables.D17.historical_non_gap != %s"
                               % PIN_D17_NON_GAP)

        # S2 / S7 绝不可计入 active / PASS；S6 scope 6-1+5=10
        s6rel = rt.get("s6_scope_relation") or {}
        if s6rel.get("arithmetic") != "6 - 1 + 5 = 10":
            self.errors.append("s6_scope_relation.arithmetic != '6 - 1 + 5 = 10'")
        if sorted(s6rel.get("current_ten") or []) != sorted(self.whitelist):
            self.errors.append("s6_scope_relation.current_ten != D11 whitelist")

        # capability gaps
        cap_ids = {g.get("id") for g in self.resolution["capability_gaps"]}
        if "CAP-01" not in cap_ids:
            self.errors.append("resolution.capability_gaps lacks CAP-01")

        # canonical qNaN 必须保持 null
        if self.canonical_qnan_bits() is not None:
            self.errors.append("rule_tables.D15.canonical_qnan_bits must stay null "
                               "(ADR-1013 gave no 64-bit constant); got %r"
                               % (self.canonical_qnan_bits(),))

        # FCSR 布局：合约重算 vs f1_gap_proofs 历史 layout 层
        lay = ((self.resolution["historical_layer"]["rf0_fcsr_split"] or {})
               .get("layout") or {})
        for key, mine in (("read_only_mask", self.fcsr["ro_mask"]),
                          ("sbz_mask", self.fcsr["sbz_mask"]),
                          ("rw_mask", self.fcsr["rw_mask"])):
            theirs = sum(mask_of(int(h), int(l))
                         for h, l in (lay.get(key) or []))
            if theirs != mine:
                self.errors.append("FCSR %s mismatch contract=%s gap_proofs=%s"
                                   % (key, hex64(mine), hex64(theirs)))
        if sorted(lay.get("rounding_modes") or []) != sorted(PIN_ROUNDING_MODES):
            self.errors.append("gap_proofs layout.rounding_modes mismatch")

        # resolution_matrix 的 remaining_unspecified 只能落在 root/log
        for ident, row in self.matrix.items():
            for item in (row.get("remaining_unspecified") or []):
                if ident not in PIN_UNSPEC_IDENTITIES:
                    self.errors.append(
                        "resolution_matrix[%s].remaining_unspecified=%r but the "
                        "explicitly-unspecified point is only %r"
                        % (ident, item, PIN_UNSPEC_POINTS))


# ─────────────────── 整数位型工具（无宿主浮点） ───────────────────
def fcsr_rw_bits(fcsr_facts, rounding_mode, flags):
    rm = fcsr_facts["rounding_modes"][rounding_mode]
    bits = rm << 16
    for name in flags:
        bits |= 1 << fcsr_facts["flags"][name]
    return bits


def fcsr_expected_value(fcsr_facts, rounding_mode, flags):
    """完整可断言 rf0 值：只读域取规范常量，rw 域取枚举，SBZ 域置 0（don't care）。"""
    return (fcsr_facts["ro_value"] & fcsr_facts["ro_mask"]) | \
        fcsr_rw_bits(fcsr_facts, rounding_mode, flags)
