#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""f1_cases.py — TESTCASES-101t 的 F1 向量**逐 case** 校验引擎。

只消费 `f1_schema.F1Context` 的事实层（合约 + `resolution` 投影 + Accepted ADR），
**不** import / 调用 LLVM、QEMU、SoftFloat、宿主浮点或 libm：所有判定都是
64 位整数的位运算、掩码、取模与精确枚举比较。

一个 F1 case 的必填顶层字段（定义见 `tests/vectors/schema.md` 的 F1 章节）：

    id, identity, insn, mnemonic, format, class, encoding.word,
    input_state{rf,rd,rb,ra,fcsr,memory}, expected_state|expected_fault,
    facets{facet: {status, cite[, rule, open_ids]}},
    ledger_refs{active_keys, trace_only, non_gap},
    blocked_points, unspecified, oracle{kind, order, records[, elements]},
    spec_cite, status

校验分组（与 schema.md 的「F1 校验项」一一对应）：

  A. 身份与字段     A1 identity ∈ 64 集 / A2 identity==insn / A3 insn+format 一致
                    A4 class / A5 status / A6 spec_cite 非空且引权威文件
  B. 编码           B1 word 是 ≤32 位 hex / B2 (word&mask)==(value&mask)
  C. RF 状态        C1 rf 键形如 rf0..rf63 / C2 值为 64 位 hex
                    C3 rf0 只能经 fcsr 表达（状态互斥）/ C4 rd0/rb0 禁止
  D. FCSR           D1 rounding_mode 枚举 / D2 flags 子集且无重复
                    D3 observed_mask ⊇ rw 域且不声称 SBZ 位
                    D4 value 独立重算比对 / D5 from_reset 必须 RNE+空 flags
  E. 互斥与状态     E1 fault ⟺ state 二选一 / E2 fault 时 pc 为 null
                    E3 active facet 不得带 open_ids / E4 blocked facet 必须带
  F. facet/台账     F1 facet 键合法且不得声明 n/a 项 / F2 gate 未开时 active 受限
                    F3 active_keys ⊆ identity 的 d17_open_ids
                    F4 S2/S7 永不进 active_keys/blocked_points/open_ids
                    F5 trace_only/non_gap 只含 S2/S7
  G. blocked/unspec G1 blocked_points 词表 / G2 unspecified 词表与 identity 归属
                    G3 unspecified 非空则不得有唯一 expected
  H. 内存/块        H1 address 48 位有效 / H2 width ∈ {1,2,4,8} 且与助记符一致
                    H3 对齐：MALIGN ⟺ 地址不对齐（D17:S4 优先级：ILLI 先于 MALIGN）
                    H4 块：EA0+i*width、rf 递增、元素数 == immu6
  I. 已激活 ADR 规则 I1 D11 rf0 目的白名单（rd2rf→rf0 必 ILLI）
                    I2 D13 tetra 高 32 位 == 0xffffffff
                    I3 D14 unordered 位型 / I4 D12 自动 vs 非自动
                    I5 D16 UF⇒NX、OF⇒NX，且非 D16 identity 不得置 OF/UF
                    I6 D17:S3 ftcls/focls immu6≠1 ⇒ ILLI
"""

from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import f1_schema as F


# ─────────────────────────── 字面量词表 ───────────────────────────
F1_CLASSES = ("encoding", "legality", "semantic", "boundary", "overlap")
F1_STATUS = ("active",)
F1_ORACLE_KINDS = ("order", "block", "unordered", "open")
F1_CASE_TOP_REQUIRED = (
    "id", "identity", "insn", "mnemonic", "format", "class", "encoding",
    "input_state", "facets", "ledger_refs", "blocked_points", "unspecified",
    "oracle", "spec_cite", "status",
)
F1_STATE_BANKS = ("rd", "rb", "ra", "rf")
F1_MEMORY_KEYS = ("address", "value", "width")
F1_REG_BANKS = ("rf", "rd", "rb", "ra")
F1_ADDR48_MAX = 0xFFFF_FFFF_FFFF
F1_RAM_BASE = 0xFFFF_0000_0000
F1_RAM_END = 0xFFFF_00FF_FFFF
F1_ROM_BASE = 0xFFFF_FFFF_0000
F1_ROM_END = 0xFFFF_FFFF_FFFF

# D17 OPEN-ID → 合约 §6.2 登记的「被阻塞 facet」。用于 gate 关闭时判定
# 哪些 facet 不许 active（S7 是 non-gap，不在此表生效）。
PIN_D17_FACET = {
    "D17:S1": "fcsr_flags",
    "D17:S3": "legality",
    "D17:S4": "legality",
    "D17:S5": "semantics",
    "D17:S6": "legality",
    "D17:S8": "semantics",
}

_CITE_TOKEN_RE = re.compile(
    r"(SimRISC-00|SimRISC-01|SimRISC-02|SimRISC-03|contract-f1-floating|"
    r"adr-10\d\d|opcodes\.yaml|f1_gap_proofs|schema\.md)")


# ─────────────────────────── 小工具 ───────────────────────────
def _is_hex64(val):
    return isinstance(val, str) and bool(F.HEX64_RE.match(val.strip())) \
        and len(val.strip()) - 2 <= 16


def _as_u64(val):
    if isinstance(val, int):
        return val & 0xFFFFFFFFFFFFFFFF
    return int(str(val).strip(), 16) & 0xFFFFFFFFFFFFFFFF


def _is_mapping(x):
    return isinstance(x, dict)


def _reg_index(key, bank):
    """'rf12' → 12；'rb0' → 0。返回 None 表示键形非法。"""
    m = {"rf": F.RF_KEY_RE, "rd": F.RD_KEY_RE,
         "rb": F.RB_KEY_RE, "ra": F.RA_KEY_RE}[bank].match(str(key))
    return int(m.group(1)) if m else None


def _bank_of(ctx, identity, role="dst"):
    """从 opcodes.yaml 的字段表取该 identity 的目的/源 bank 与位号。"""
    rec = ctx.rec(identity) or {}
    out = []
    for f in rec.get("fields") or []:
        if f.get("role") == role and f.get("bank") in F1_REG_BANKS:
            out.append((f["name"], f.get("bank"), f.get("bits")))
    return out


def mem_width_of(ctx, identity):
    """单条 ld/st 的访存宽度：mnemonic 后缀 .t→4、.o→8。块操作走
    ``ctx.block_width``（含格式转换按源格式定宽）。"""
    info = ctx.identities.get(identity) or {}
    mnem = info.get("mnemonic", "")
    if mnem.endswith(".t"):
        return 4
    if mnem.endswith(".o"):
        return 8
    return None


def d17_facet_set(ctx, identity):
    """该 identity 的 D17 active 键所压住的 facet 集合。"""
    return {PIN_D17_FACET[k] for k in ctx.d17_active_keys_for(identity)
            if k in PIN_D17_FACET}


# ─────────────────────────── A/B：身份与编码 ───────────────────────────
def _check_identity_fields(ctx, case, err):
    ident = case.get("identity")
    if not isinstance(ident, str) or not ident:
        err.append("A1 identity missing or not a non-empty string")
        return None
    if ident not in ctx.identities:
        err.append("A1 UNKNOWN IDENTITY %r not in the 64-identity F1 set"
                   % ident)
        return None
    insn = case.get("insn")
    if insn != ident:
        err.append("A2 identity=%r but insn=%r (must be identical)"
                   % (ident, insn))
    rec = ctx.rec(ident) or {}
    for key in ("mnemonic", "format"):
        if case.get(key) != rec.get(key):
            err.append("A3 %s=%r but opcodes.yaml has %r"
                       % (key, case.get(key), rec.get(key)))
    if case.get("class") not in F1_CLASSES:
        err.append("A4 class=%r not in %r" % (case.get("class"), F1_CLASSES))
    if case.get("status") not in F1_STATUS:
        err.append("A5 status=%r not in %r (F1 case must be active; unresolved "
                   "points go in blocked_points/unspecified, not deferred)"
                   % (case.get("status"), F1_STATUS))
    cite = case.get("spec_cite")
    if not isinstance(cite, str) or not cite.strip():
        err.append("A6 spec_cite missing or empty")
    elif not _CITE_TOKEN_RE.search(cite):
        err.append("A6 spec_cite %r cites no authority file (want one of %r)"
                   % (cite, _CITE_TOKEN_RE.pattern))
    return ident if ident in ctx.identities else None


def _check_encoding(ctx, case, ident, err):
    enc = case.get("encoding")
    if not _is_mapping(enc) or "word" not in enc:
        err.append("B1 encoding.word missing")
        return None
    w = enc.get("word")
    if not (isinstance(w, str) and re.match(r"^0x[0-9a-fA-F]{1,8}$", w.strip())):
        err.append("B1 encoding.word=%r is not a <=32-bit hex string" % (w,))
        return None
    word = int(w.strip(), 16)
    if ident is None:
        return word
    rec = ctx.rec(ident) or {}
    ok, mask, value = F.encode_check(word, rec)
    if not ok:
        err.append("B2 encoding.word=0x%08X fails (word & 0x%08X) == "
                   "(value 0x%08X & 0x%08X) for identity %s"
                   % (word, mask, value, mask, ident))
    return word


# ─────────────────────────── C/D：RF 与 FCSR ───────────────────────────
def _check_reg_bank(ctx, case, state_name, err, expect_fcsr):
    st = case.get(state_name)
    if not _is_mapping(st):
        return
    for bank in F1_STATE_BANKS:
        blk = st.get(bank)
        if blk is None:
            continue
        if not _is_mapping(blk):
            err.append("C1 %s.%s is not a mapping" % (state_name, bank))
            continue
        for key, val in blk.items():
            idx = _reg_index(key, bank)
            if idx is None:
                err.append("C1 %s.%s key %r is not a valid %s index "
                           "(rf0..rf63 / rd1..rd63 / rb1..rb63 / ra0..ra63)"
                           % (state_name, bank, key, bank))
                continue
            if not (0 <= idx <= 63):
                # 键形合法但越界：所有寄存器字段都是 6 位，rf99 不可能编码出来
                err.append("C1 %s.%s key %r index %d is out of range: the field "
                           "is 6 bits wide, so only 0..63 can be encoded"
                           % (state_name, bank, key, idx))
                continue
            if bank in ("rd", "rb") and idx == 0:
                err.append("C4 %s.%s must not contain %s (rd0 is always zero, "
                           "rb0 is PC; ADR-0004 D6.5)" % (state_name, bank, key))
                continue
            if bank == "rf" and not _is_hex64(val):
                err.append("C2 %s.%s.%s=%r is not a 64-bit hex bit-pattern"
                           % (state_name, bank, key, val))
            elif bank != "rf" and not _is_hex64(val):
                err.append("C2 %s.%s.%s=%r is not a 64-bit hex bit-pattern"
                           % (state_name, bank, key, val))
            if bank == "rf" and idx == 0:
                err.append("C3 STATE EXCLUSIVITY: %s.rf.rf0 present; rf0 is "
                           "FCSR and must be expressed only via %s.fcsr"
                           % (state_name, state_name))
    if "fcsr" in st and st.get("fcsr") is not None and \
            not _is_mapping(st.get("fcsr")):
        err.append("C3 %s.fcsr is not a mapping" % state_name)
    else:
        for key in F1_STATE_BANKS:
            if key in st and st[key] is None:
                err.append("C0 %s.%s present but null; use {} or omit"
                           % (state_name, key))


def _check_fcsr(ctx, case, state_name, err, is_expected):
    st = case.get(state_name)
    if not _is_mapping(st):
        return
    fc = st.get("fcsr")
    if fc is None:
        return
    if not _is_mapping(fc):
        err.append("D0 %s.fcsr is not a mapping" % state_name)
        return
    facts = ctx.fcsr
    rm = fc.get("rounding_mode")
    if rm not in F.PIN_ROUNDING_MODES:
        err.append("D1 %s.fcsr.rounding_mode=%r not in %r (enum of rf0[17:16])"
                   % (state_name, rm, F.PIN_ROUNDING_MODES))
    flags = fc.get("flags")
    if not isinstance(flags, list):
        err.append("D2 %s.fcsr.flags must be a list (may be empty)" % state_name)
        flags = []
    else:
        seen = set()
        for f in flags:
            if f not in F.PIN_FCSR_FLAGS:
                err.append("D2 ILLEGAL FLAG %r not in %r (rf0[4:0] = "
                           "NV/DZ/OF/UF/NX)" % (f, F.PIN_FCSR_FLAGS))
            elif f in seen:
                err.append("D2 duplicate flag %r" % f)
            seen.add(f)
    mask = fc.get("observed_mask")
    if mask is not None:
        if not _is_hex64(mask):
            err.append("D3 %s.fcsr.observed_mask=%r is not a 64-bit hex mask"
                       % (state_name, mask))
        else:
            m = _as_u64(mask)
            if m & facts["rw_mask"] != facts["rw_mask"]:
                err.append("D3 observed_mask=%s misses rw bits %s (rf0[17:16] "
                           "rounding + rf0[4:0] flags must be observable)"
                           % (F.hex64(m), F.hex64(facts["rw_mask"])))
            if m & facts["sbz_mask"]:
                err.append("D3 observed_mask=%s claims SBZ bits %s; ADR-1015 D1 "
                           "leaves the SBZ write read-value unspecified, so a "
                           "vector must never assert them"
                           % (F.hex64(m), F.hex64(m & facts["sbz_mask"])))
            if m & ~(facts["ro_mask"] | facts["rw_mask"]):
                err.append("D3 observed_mask=%s claims bits outside RO|rw"
                           % F.hex64(m))
    val = fc.get("value")
    if val is not None:
        if not _is_hex64(val):
            err.append("D4 %s.fcsr.value=%r is not a 64-bit hex bit-pattern"
                       % (state_name, val))
        elif rm in F.PIN_ROUNDING_MODES and isinstance(flags, list) and \
                all(f in F.PIN_FCSR_FLAGS for f in flags):
            want = F.fcsr_expected_value(facts, rm, flags)
            got = _as_u64(val)
            if got != want:
                err.append("D4 %s.fcsr.value=%s but independent recompute gives "
                           "%s (ro=%s | rounding=%s | flags=%s)"
                           % (state_name, F.hex64(got), F.hex64(want),
                              F.hex64(facts["ro_value"]),
                              facts["rounding_modes"][rm],
                              sorted(set(flags))))
    if fc.get("from_reset"):
        if rm not in (None, "RNE"):
            err.append("D5 from_reset=true but rounding_mode=%r; ADR-1015 D1 "
                       "reset gives rf0[17:16]=00 (RNE)" % (rm,))
        if isinstance(flags, list) and flags:
            err.append("D5 from_reset=true but flags=%r; ADR-1015 D1 reset "
                       "gives rf0[4:0]=0" % (flags,))
    if not is_expected:
        # D6：input 侧只用枚举（rounding_mode / flags）或 from_reset 描述前置；
        # value/observed_mask 是 **expected 侧**的观测契约（哪些位可被 oracle
        # 读回）。若 input 侧也带一份，两份断言可能互相矛盾且 input 无从校验。
        for k in ("value", "observed_mask"):
            if fc.get(k) is not None:
                err.append("D6 %s.fcsr.%s must not be asserted: the input FCSR "
                           "state is described by rounding_mode/flags (or "
                           "from_reset); value/observed_mask are expected-side "
                           "observation contracts" % (state_name, k))


# ─────────────────────── E/F：互斥、facet、台账 ───────────────────────
def _check_exclusive(ctx, case, err):
    fault = case.get("expected_fault", None)
    exp = case.get("expected_state", None)
    if fault is not None and exp is not None:
        err.append("E1 STATE EXCLUSIVITY: expected_fault=%r and expected_state "
                   "both present; a faulting case commits nothing (D17:S8)"
                   % (fault,))
    if fault is None and not _is_mapping(exp):
        if (case.get("oracle") or {}).get("kind") != "open":
            err.append("E1 expected_fault is null so expected_state must be a "
                       "mapping (only oracle.kind=open may leave both null)")
    if fault not in (None,) + tuple(x for x in F.F1_FAULTS if x):
        err.append("E1 expected_fault=%r not in F1_FAULTS %r"
                   % (fault, F.F1_FAULTS))
    if case.get("expected_pc") is not None:
        err.append("E2 expected_pc must be null for F1 (no F1 identity changes "
                   "PC; D17:S8 keeps PC on the faulting instruction)")


def _check_facets(ctx, case, ident, err):
    facets = case.get("facets")
    if not _is_mapping(facets):
        err.append("F0 facets missing or not a mapping")
        return
    if not facets:
        err.append("F0 facets must declare at least one facet")
    rec = ctx.rec(ident) or {}
    contract_facets = ((rec.get("f1") or {}).get("facets") or {})
    d17_blocked = d17_facet_set(ctx, ident) if ident else set()
    for key, spec in facets.items():
        if key not in F.PIN_FACET_KEYS:
            err.append("F1 facet %r is not one of the 11 facet keys %r"
                       % (key, list(F.PIN_FACET_KEYS)))
            continue
        if not _is_mapping(spec):
            err.append("F1 facet %s must be a mapping" % key)
            continue
        status = spec.get("status")
        if status not in F.PIN_FACET_STATUS:
            err.append("F1 facet %s status=%r not in %r"
                       % (key, status, F.PIN_FACET_STATUS))
            continue
        cite = spec.get("cite")
        if not isinstance(cite, str) or not cite.strip():
            err.append("F1 CITATION MISSING: facet %s has no cite" % key)
        elif not _CITE_TOKEN_RE.search(cite):
            err.append("F1 facet %s cite %r names no authority file"
                       % (key, cite))
        open_ids = spec.get("open_ids")
        if status == "active":
            if open_ids:
                err.append("E3 ACTIVE+OPEN CONTRADICTION: facet %s is active but "
                           "carries open_ids=%r" % (key, open_ids))
            if spec.get("rule"):
                err.append("E3 facet %s is active; a 'rule' (activation取值) "
                           "belongs to blocked facets only" % key)
        else:
            if not isinstance(open_ids, list) or not open_ids:
                err.append("E4 BLOCKED facet %s must carry a non-empty "
                           "open_ids" % key)
            else:
                for oid in open_ids:
                    if oid not in F.PIN_OPEN_ID_VOCAB:
                        err.append("E4 facet %s open_id %r not in vocab %r"
                                   % (key, oid, list(F.PIN_OPEN_ID_VOCAB)))
                    if oid in F.PIN_NEVER_BLOCKED:
                        err.append("F4 facet %s open_id %r must never be a "
                                   "blocked/OPEN position (%s)"
                                   % (key, oid,
                                      "trace-only" if oid == F.PIN_D17_TRACE_ONLY
                                      else "spec-determined non-gap"))
        # n/a facet 不得被声明
        if contract_facets.get(key) == "n/a":
            err.append("F1 facet %s is n/a for identity %s (contract §5.1) and "
                       "must be omitted, not declared %s"
                       % (key, ident, status))
        # 激活门禁：gate 未开时，受 D* 或 D17 压住的 facet 不得 active
        if status == "active" and not ctx.gate_open:
            gov = ctx.facet_governed_by(ident, key) if ident else None
            if gov is not None:
                err.append("F2 ADR GATE CLOSED: facet %s of %s is governed by "
                           "%s (%s not Accepted) and must be blocked"
                           % (key, ident, gov, F.PIN_D_TO_ADR[gov]))
            if key in d17_blocked:
                err.append("F2 ADR GATE CLOSED: facet %s of %s is blocked by "
                           "D17 OPEN-ID(s) %s and must be blocked"
                           % (key, ident,
                              ",".join(ctx.d17_active_keys_for(ident))))


def _check_ledger(ctx, case, ident, err):
    lr = case.get("ledger_refs")
    if not _is_mapping(lr):
        err.append("F0 ledger_refs missing or not a mapping")
        return
    for key in ("active_keys", "trace_only", "non_gap"):
        if not isinstance(lr.get(key, []), list):
            err.append("F0 ledger_refs.%s must be a list" % key)
            lr[key] = []
    active = lr.get("active_keys") or []
    allowed = set(ctx.d17_active_keys_for(ident)) if ident else set()
    for oid in active:
        if oid not in F.PIN_D17_ACTIVE_KEYS:
            err.append("F3 ledger_refs.active_keys=%r not in the six active "
                       "OPEN-IDs %r" % (oid, list(F.PIN_D17_ACTIVE_KEYS)))
        elif oid in F.PIN_NEVER_BLOCKED:
            err.append("F4 %r must never appear in active_keys (%s)"
                       % (oid, "trace-only" if oid == F.PIN_D17_TRACE_ONLY
                          else "spec-determined non-gap"))
        elif ident and oid not in allowed:
            err.append("F3 active_keys %r not among identity %s's "
                       "d17_open_ids %r" % (oid, ident, sorted(allowed)))
    for oid in (lr.get("trace_only") or []):
        if oid != F.PIN_D17_TRACE_ONLY:
            err.append("F5 ledger_refs.trace_only must only ever contain %r, "
                       "got %r" % (F.PIN_D17_TRACE_ONLY, oid))
    for oid in (lr.get("non_gap") or []):
        if oid != F.PIN_D17_NON_GAP:
            err.append("F5 ledger_refs.non_gap must only ever contain %r, got "
                       "%r" % (F.PIN_D17_NON_GAP, oid))
    # blocked_points 不得含 S2/S7
    for bp in (case.get("blocked_points") or []):
        if bp in F.PIN_NEVER_BLOCKED:
            err.append("F4 blocked_points must not contain %r" % bp)


def _check_blocked_unspec(ctx, case, ident, err):
    for bp in (case.get("blocked_points") or []):
        if bp not in F.PIN_BLOCKED_POINT_VOCAB:
            err.append("G1 blocked_points entry %r not in vocab %r"
                       % (bp, list(F.PIN_BLOCKED_POINT_VOCAB)))
    uns = case.get("unspecified")
    if not isinstance(uns, list):
        err.append("G2 unspecified must be a list (may be empty)")
        uns = []
    for pt in uns:
        if pt not in F.PIN_UNSPEC_POINTS:
            err.append("G2 unspecified entry %r not in %r"
                       % (pt, list(F.PIN_UNSPEC_POINTS)))
        elif ident and ident not in F.PIN_UNSPEC_IDENTITIES:
            err.append("G2 %r is only reachable from %r, not %r"
                       % (pt, list(F.PIN_UNSPEC_IDENTITIES), ident))
    if uns:
        exp = case.get("expected_state")
        if _is_mapping(exp):
            # **所有**寄存器组都不得断言：规范明示「不做具体要求」时，任何
            # 目的寄存器取值都是编造。早期版本放过 rf，理由（rf 可以断言别的值）
            # 不成立——expected_state 是「这条 case 的唯一期望」，不是部分清单。
            for bank in F1_STATE_BANKS:
                if exp.get(bank):
                    err.append("G3 unspecified=%r: expected_state.%s must be "
                               "empty/null (an explicitly-unspecified point "
                               "admits no asserted value)" % (uns, bank))
        recs = ((case.get("oracle") or {}).get("records") or [])
        if recs:
            err.append("G3 unspecified=%r: oracle.records must be empty" % (uns,))
        if case.get("expected_fault") is None and \
                (case.get("oracle") or {}).get("kind") != "open":
            err.append("G3 unspecified=%r present so the case must NOT assert a "
                       "unique expected: use oracle.kind=open (documented as "
                       "no-unique-expected) or set expected_fault; "
                       "rootn(-0,2) is explicitly-unspecified" % (uns,))


# ─────────────────────── H：内存与块 ───────────────────────
def _memory_entries(st, err, state_name):
    mem = st.get("memory")
    if mem is None:
        return []
    if not isinstance(mem, list):
        err.append("H0 %s.memory must be a list" % state_name)
        return []
    return [m for m in mem if _is_mapping(m)]


def _check_memory(ctx, case, ident, word, err):
    width = mem_width_of(ctx, ident) if ident else None
    block = ctx.is_block_identity(ident) if ident else False
    entries = []
    for state_name in ("input_state", "expected_state"):
        st = case.get(state_name)
        if not _is_mapping(st):
            continue
        for m in _memory_entries(st, err, state_name):
            addr = m.get("address")
            if not (isinstance(addr, str) and
                    re.match(r"^0x[0-9a-fA-F]{1,12}$", str(addr).strip())):
                err.append("H1 %s.memory address=%r is not a 48-bit valid "
                           "address hex" % (state_name, addr))
                entries.append(None)
                continue
            a = int(str(addr).strip(), 16)
            if a > F1_ADDR48_MAX:
                err.append("H1 %s.memory address 0x%012X exceeds the 48-bit "
                           "valid range" % (state_name, a))
            if not _is_hex64(m.get("value")):
                err.append("H2 %s.memory value=%r is not a 64-bit hex "
                           "bit-pattern" % (state_name, m.get("value")))
            w = m.get("width")
            if w not in F.F1_MEMORY_WIDTHS:
                err.append("H2 %s.memory width=%r not in %r"
                           % (state_name, w, list(F.F1_MEMORY_WIDTHS)))
            elif width is not None and not block and w != width:
                err.append("H2 %s.memory width=%r but %s accesses %d-byte "
                           "elements" % (state_name, w, ident, width))
            entries.append((state_name, a, m.get("width"), m))
    return entries, width


def static_illi(ctx, ident, word):
    """独立重算「静态 ILLI」谓词（D11 rf0 目的非法 + D17:S3 classify immu6）。

    返回 (is_illi, reasons)。只含 spec/ADR 明确规定的静态非法操作数，
    **不含** MALIGN、SBZ、溢出等动态条件。
    """
    reasons = []
    if ident is None or word is None:
        return False, reasons
    rec = ctx.rec(ident) or {}
    fields, _ferr = F.decode_fields(word, rec)
    dst_rf0, _v = _dst_is_rf0(ctx, ident, word)
    if dst_rf0 and not ctx.rf0_write_allowed(ident):
        reasons.append("D11 rf0 destination outside the 10-identity whitelist")
    if ident in F.F1_CLASSIFY_IDS and \
            fields.get("immu6") != F.F1_CLASSIFY_IMMU6:
        reasons.append("D17:S3 classify immu6 != 1")
    if ident in F.F1_CLASSIFY_IDS or ctx.is_block_identity(ident):
        immu6 = fields.get("immu6")
        if immu6 is not None and immu6 == 0:
            reasons.append("immu6 = 0 (SimRISC-03:29/48/132)")
    return bool(reasons), reasons


def _check_alignment(ctx, case, ident, word, err):
    """D17:S4（ADR-1015 D3）：ILLI 先于 MALIGN；非法编码/操作数不进入对齐判定。"""
    if ident is None or word is None:
        return False
    rec = ctx.rec(ident) or {}
    fields, _ferr = F.decode_fields(word, rec)
    st = case.get("input_state") or {}
    rb = st.get("rb") or {}
    rd = st.get("rd") or {}
    width = mem_width_of(ctx, ident)
    block = ctx.is_block_identity(ident)
    is_illi, reasons = static_illi(ctx, ident, word)
    misaligned = False
    if width is not None and not block:
        off = fields.get("imms12")
        base = None
        for k, v in rb.items():
            if _reg_index(k, "rb") == fields.get("rbhb") and _is_hex64(v):
                base = _as_u64(v)
        if base is not None and off is not None:
            misaligned = ((base + off) % width) != 0
    elif block:
        bw = ctx.block_width(ident)
        n = fields.get("immu6")
        base = off = None
        for k, v in rb.items():
            if _reg_index(k, "rb") == fields.get("rbhb") and _is_hex64(v):
                base = _as_u64(v)
        for k, v in rd.items():
            if _reg_index(k, "rd") == fields.get("rdhc") and _is_hex64(v):
                off = _as_u64(v)
        if base is not None and off is not None and bw and n and not is_illi:
            for i in range(n):
                if ((base + off + i * bw) % bw) != 0:
                    misaligned = True
                    break
    fault = case.get("expected_fault")
    if fault == "MALIGN":
        if is_illi:
            err.append("H3/H4 D17:S4 PRIORITY: case is statically ILLI (%s) so "
                       "it must not expect MALIGN (ADR-1015 D3: ILLI precedes "
                       "MALIGN)" % "; ".join(reasons))
        elif not misaligned:
            err.append("H3 expected_fault=MALIGN but the independently "
                       "recomputed element address(es) are aligned for width %s"
                       % (width,))
    if fault is None and misaligned:
        err.append("H3 expected_fault is null but the recomputed element "
                   "address is misaligned for width %s" % (width,))
    if fault == "ILLI" and not is_illi and width is not None:
        err.append("H3 expected_fault=ILLI but no static ILLI predicate fires "
                   "for this encoding (D11 rf0 白名单 / D17:S3 classify immu6 / "
                   "rd_dest_not_rd0 / immu6=0 全部不成立) → 期望值自相矛盾")
    return misaligned


def _check_src_preset(ctx, case, ident, word, err):
    """H5：编码中 role=src 的 rf/rb/ra/rd 字段所指寄存器必须在 input_state 预置。

    这是对「操作数位型 ↔ 状态位型」的一致性检查，独立于任何实现：只按
    opcodes.yaml 的字段位号解码 word，再核对 input_state 里有对应 bank 的键。
    rf0 例外（它经 ``fcsr`` 表达，见 C3）。
    """
    if ident is None or word is None:
        return
    rec = ctx.rec(ident) or {}
    fields, _ferr = F.decode_fields(word, rec)
    st = case.get("input_state") or {}
    for f in (rec.get("fields") or []):
        if f.get("role") != "src" or f.get("bank") not in F1_REG_BANKS:
            continue
        val = fields.get(f["name"])
        if val is None:
            continue
        bank = f.get("bank")
        key = "%s%d" % (bank, val)
        if bank == "rf" and val == 0:
            continue                      # rf0 走 fcsr，不要求 rf.rf0
        if key not in (st.get(bank) or {}):
            err.append("H5 %s reads %s (encoding %s=%d) but input_state.%s has "
                       "no %r entry" % (ident, key, f["name"], val, bank, key))


def _check_block_elements(ctx, case, ident, word, err):
    """D17:S8（ADR-1015 D7/D8）：EA0=rbhb+rdhc、EA(i)=EA0+i*width、rf 递增。"""
    orc = case.get("oracle") or {}
    els = orc.get("elements")
    if els is None:
        if orc.get("kind") == "block":
            err.append("H4 oracle.kind=block requires an 'elements' list")
        return
    if not isinstance(els, list) or not els:
        err.append("H4 oracle.elements must be a non-empty list")
        return
    if not ctx.is_block_identity(ident):
        err.append("H4 oracle.elements given for non-block identity %s" % ident)
        return
    rec = ctx.rec(ident) or {}
    fields, _f = F.decode_fields(word, rec)
    width = ctx.block_width(ident)
    n = fields.get("immu6")
    rfha = fields.get("rfha")
    if width is None or n is None or rfha is None:
        err.append("H4 cannot recompute block geometry for %s" % ident)
        return
    st = case.get("input_state") or {}
    base = off = None
    for k, v in (st.get("rb") or {}).items():
        if _reg_index(k, "rb") == fields.get("rbhb") and _is_hex64(v):
            base = _as_u64(v)
    for k, v in (st.get("rd") or {}).items():
        if _reg_index(k, "rd") == fields.get("rdhc") and _is_hex64(v):
            off = _as_u64(v)
    if base is None or off is None:
        err.append("H4 block case must preset rb%s and rd%s (needed to "
                   "recompute EA0)" % (fields.get("rbhb"), fields.get("rdhc")))
        return
    ea0 = base + off
    if len(els) != n:
        err.append("H4 oracle.elements has %d entries but immu6=%d"
                   % (len(els), n))
    for i, el in enumerate(els):
        if not _is_mapping(el):
            err.append("H4 oracle.elements[%d] is not a mapping" % i)
            continue
        if el.get("rf") != rfha + i:
            err.append("H4 element %d: rf=%r but D17:S8 requires rfha+i=%d"
                       % (i, el.get("rf"), rfha + i))
        if el.get("width") != width:
            err.append("H4 element %d: width=%r but %s has width %d"
                       % (i, el.get("width"), ident, width))
        want = ea0 + i * width
        addr = el.get("address")
        if not (isinstance(addr, str) and
                re.match(r"^0x[0-9a-fA-F]{1,12}$", str(addr).strip())):
            err.append("H4 element %d: address=%r is not a 48-bit hex address"
                       % (i, addr))
        elif int(str(addr).strip(), 16) != want:
            err.append("H4 element %d: address=%s but EA0+i*width=0x%012X "
                       "(D17:S8)" % (i, str(addr).strip(), want))
        if "value" in el and not _is_hex64(el.get("value")):
            err.append("H4 element %d: value=%r is not a 64-bit hex "
                       "bit-pattern" % (i, el.get("value")))


# ─────────────────────── I：已激活 ADR 规则 ───────────────────────
def _dst_is_rf0(ctx, ident, word):
    rec = ctx.rec(ident) or {}
    fields, _f = F.decode_fields(word, rec)
    dst = [f for f in (rec.get("fields") or []) if f.get("role") == "dst"
           and f.get("bank") == "rf"]
    if not dst:
        return False, None
    name = dst[0]["name"]
    val = fields.get(name)
    return val == 0, val


def _dst_first_rf(ctx, ident, word):
    rec = ctx.rec(ident) or {}
    fields, _f = F.decode_fields(word, rec)
    for f in (rec.get("fields") or []):
        if f.get("role") == "dst" and f.get("bank") == "rf":
            return fields.get(f["name"])
    return None


def _check_activated_rules(ctx, case, ident, word, err):
    fault = case.get("expected_fault")
    exp = case.get("expected_state") or {}

    # I1 D11：rf0 作目的只在十条白名单内合法，其它必 ILLI
    if ident and word is not None:
        hit0, _v = _dst_is_rf0(ctx, ident, word)
        if hit0:
            if ctx.rf0_write_allowed(ident):
                pass
            elif fault != "ILLI":
                err.append("I1 D11: %s writes rf0 but is not in the 10-identity "
                           "whitelist %r -> expected_fault must be ILLI"
                           % (ident, sorted(ctx.whitelist)))

    # I2 D13：tetra 写 RF 的高 32 位固定 0xffffffff。
    # 注意判据是「**结果**落进 rf」而不是「是不是 load」：ft 运算（ftadd/ftdiv/…）
    # 与 ft 装载（ld.t-rf/ldm.t-rf）同样要装箱；只查 load 会漏掉 ft 运算。
    if ident and ident in ctx.d13_scope():
        hi = ctx.d13_high32()
        for key, val in (exp.get("rf") or {}).items():
            idx = _reg_index(key, "rf")
            if idx in (None, 0) or not _is_hex64(val):
                continue
            got = (_as_u64(val) >> 32) & 0xFFFFFFFF
            if got != hi:
                err.append("I2 D13: %s writes rf%d high 32 bits %s but D13 "
                           "fixes the tetra NaN-boxing high half at %s"
                           % (ident, idx, F.hex64(got), F.hex64(hi)))

    # I3 D14：unordered 比较写 RD 的固定位型
    if ident and ident in ctx.d14_scope():
        want = ctx.d14_unordered_bits(ident)
        if want is None:
            err.append("I3 D14: rule_tables has no unordered bit-pattern for %s"
                       % ident)
        for key, val in (exp.get("rd") or {}).items():
            idx = _reg_index(key, "rd")
            if idx in (None, 0) or not _is_hex64(val) or want is None:
                continue
            got = _as_u64(val)
            if got == want:
                continue
            # 只有当本例声明走 unordered 路径时才强制该位型
            if (case.get("oracle") or {}).get("unordered_case"):
                err.append("I3 D14: %s is declared unordered_case, so RD must "
                           "be the fixed unordered bit-pattern %s, got %s"
                           % (ident, F.hex64(want), F.hex64(got)))
        # 声明了 unordered 就必须真的写出该位型（不得静默写别的值）
        if (case.get("oracle") or {}).get("unordered_case") and want is not None:
            written = [ _as_u64(v) for k, v in (exp.get("rd") or {}).items()
                        if _reg_index(k, "rd") not in (None, 0)
                        and _is_hex64(v) ]
            if not written:
                err.append("I3 D14: unordered_case=true but no rd write in "
                           "expected_state.rd")
            elif want not in written:
                err.append("I3 D14: unordered_case=true but no rd write equals "
                           "the fixed unordered bit-pattern %s" % F.hex64(want))
    elif ident and (case.get("oracle") or {}).get("unordered_case"):
        err.append("I3 D14: unordered_case=true but %s is outside the 4-identity "
                   "unordered-compare scope %r"
                   % (ident, sorted(ctx.d14_scope())))

    # I4 D12：自动置位 / 非自动置位
    if ident:
        flags = ((exp.get("fcsr") or {}).get("flags"))
        if isinstance(flags, list) and set(flags) & {"NV", "DZ"}:
            if ident in ctx.d12_non_automatic():
                err.append("I4 D12: %s is a non-automatic (data-movement) "
                           "identity and must not automatically set %s"
                           % (ident, sorted(set(flags) & {"NV", "DZ"})))

    # I5 D16：tininess 在最终舍入后检测，underflow⇒UF+NX、overflow⇒OF+NX
    if ident and isinstance(((exp.get("fcsr") or {}).get("flags")), list):
        flags = set(exp["fcsr"]["flags"])
        if "UF" in flags and "NX" not in flags:
            err.append("I5 D16: UF set without NX (D16 fixes underflow as "
                       "UF+NX)")
        if "OF" in flags and "NX" not in flags:
            err.append("I5 D16: OF set without NX (D16 fixes overflow as "
                       "OF+NX)")
        if (flags & {"OF", "UF"}) and ident not in ctx.d16_scope():
            err.append("I5 D16: %s is outside the 36-identity tininess scope, "
                       "so it must not set OF/UF (got %s)"
                       % (ident, sorted(flags & {"OF", "UF"})))

    # I6 D17:S3：ftcls/focls 的 immu6 != 1
    if ident and ident in F.F1_CLASSIFY_IDS and word is not None:
        rec = ctx.rec(ident) or {}
        fields, _f = F.decode_fields(word, rec)
        if fields.get("immu6") != F.F1_CLASSIFY_IMMU6:
            if fault != "ILLI":
                err.append("I6 D17:S3: %s immu6=%r but the classify immediate "
                           "is fixed at 1; a non-assembler path reaching "
                           "hardware must be ILLI"
                           % (ident, fields.get("immu6")))

    # I7 静态 ILLI 双向核对：expected_fault='ILLI' 必须**能**由静态谓词重算
    # 出来。否则「合法编码却期望 ILLI」的样例会静默通过，等于给 oracle 开后门。
    if ident and word is not None and fault is not None:
        is_illi, reasons = static_illi(ctx, ident, word)
        if fault == "ILLI" and not is_illi:
            err.append("I7 STATIC ILLI UNJUSTIFIED: case expects ILLI but no "
                       "static predicate of %s re-computes (independent "
                       "recheck found none); the encoding is legal, so a "
                       "vector may not claim ILLI" % ident)
        elif fault == "MALIGN" and is_illi:
            err.append("I7 D17:S4: %s expects MALIGN but the static predicate(s) "
                       "%r already make it ILLI; ILLI takes precedence "
                       "(ADR-1015 D3)" % (ident, reasons))

    # I8 伪造防线：semantics facet 被 blocked 时，**不得**断言该 identity 的
    # 目的寄存器取值——那正是未决语义要决定的东西（例如 D15 的
    # canonical_qnan_bits = null：代填 0x7FF8000000000000 就是伪造常量）。
    if ident and word is not None:
        spec = (case.get("facets") or {}).get("semantics")
        if _is_mapping(spec) and spec.get("status") == "blocked" and \
                spec.get("open_ids"):
            for fname, bank, _bits in _bank_of(ctx, ident, "dst"):
                idx = F.decode_fields(word, ctx.rec(ident) or {})[0].get(fname)
                if idx is None:
                    continue
                key = "%s%d" % (bank, int(idx))
                if (exp.get(bank) or {}).get(key) is not None:
                    err.append("I8 FABRICATION GATE: semantics facet of %s is "
                               "blocked by open_ids=%r, so the destination "
                               "write %s.%s must NOT be asserted (that value is "
                               "exactly what the open point leaves unspecified)"
                               % (ident, spec.get("open_ids"), bank, key))


# ─────────────────────── oracle：稳定 I/O 记录 ───────────────────────
def _check_oracle(ctx, case, ident, word, err):
    orc = case.get("oracle")
    if not _is_mapping(orc):
        err.append("O1 oracle missing or not a mapping")
        return
    kind = orc.get("kind")
    if kind not in F1_ORACLE_KINDS:
        err.append("O1 oracle.kind=%r not in %r" % (kind, F1_ORACLE_KINDS))
    if "unordered_case" in orc and not isinstance(orc.get("unordered_case"), bool):
        err.append("O1 oracle.unordered_case must be a boolean")
    unknown = [k for k in orc
               if k not in ("kind", "order", "records", "elements",
                            "unordered_case")]
    if unknown:
        err.append("O1 oracle has unknown key(s) %r" % (unknown,))
    order = case.get("order")
    if order is not None and order not in F.F1_OBS_ORDER_KINDS:
        err.append("O1 order=%r not in %r" % (order, F.F1_OBS_ORDER_KINDS))
    if order == "block-increasing" and kind != "block":
        err.append("O1 order=block-increasing requires oracle.kind=block, "
                   "got %r" % (kind,))
    if kind == "block" and order not in (None, "block-increasing"):
        err.append("O1 oracle.kind=block requires order=block-increasing, "
                   "got %r" % (order,))
    if order == "read-before-write" and kind != "unordered":
        err.append("O1 order=read-before-write requires oracle.kind=unordered, "
                   "got %r" % (kind,))
    if kind == "open" and order is not None:
        err.append("O1 oracle.kind=open must not declare order=%r (there is no "
                   "observation ordering to pin)" % (order,))
    recs = orc.get("records")
    if not isinstance(recs, list):
        err.append("O1 oracle.records must be a list")
        return
    if kind == "open":
        # 「不声明唯一期望值」是一种**一等** oracle 形状：F1 的 blocked /
        # explicitly-unspecified 点必须用它，而不是硬编一个值。
        if recs:
            err.append("O1 oracle.kind=open must carry records: [] (it asserts "
                       "no unique expected value)")
        if case.get("expected_state") is not None or \
                case.get("expected_fault") is not None:
            err.append("O1 oracle.kind=open must NOT assert expected_state/"
                       "expected_fault (that would be a unique expected)")
        why = [k for k, sp in (case.get("facets") or {}).items()
               if _is_mapping(sp) and sp.get("status") == "blocked"
               and sp.get("open_ids")]
        if not (case.get("blocked_points") or case.get("unspecified") or why):
            err.append("O1 oracle.kind=open requires a reason: a blocked facet "
                       "with open_ids, or a blocked_points / unspecified entry; "
                       "otherwise 'no expected' is indistinguishable from a "
                       "missing vector")
        return
    fault = case.get("expected_fault")
    if fault is not None:
        faults = [r for r in recs if _is_mapping(r) and "fault" in r]
        if len(faults) != 1:
            err.append("O2 a faulting case needs exactly one 'fault' record, "
                       "got %d" % len(faults))
        else:
            fr = faults[0]["fault"]
            if not _is_mapping(fr):
                err.append("O2 fault record must be a mapping {type, pc}")
            else:
                if fr.get("type") != fault:
                    err.append("O2 oracle fault.type=%r != expected_fault=%r"
                               % (fr.get("type"), fault))
                pc = fr.get("pc")
                if not (isinstance(pc, str) and
                        re.match(r"^0x[0-9a-fA-F]{1,12}$", str(pc).strip())):
                    err.append("O2 fault.pc=%r is not a 48-bit hex address"
                               % (pc,))
                else:
                    a = int(str(pc).strip(), 16)
                    if not ((F1_RAM_BASE <= a <= F1_RAM_END) or
                            (F1_ROM_BASE <= a <= F1_ROM_END)):
                        err.append("O2 fault.pc 0x%012X is outside the RAM/ROM "
                                   "windows" % a)
        if recs[-1:] != faults:
            err.append("O2 the fault record must be the last oracle record "
                       "(D17:S8: PC stays on the faulting instruction)")
        for r in recs:
            if _is_mapping(r) and any(k in r for k in ("reg", "mem", "fcsr")):
                err.append("O2 faulting case must not record reg/mem/fcsr "
                           "effects (D17:S8 commits nothing)")
        return
    if not recs and kind != "open":
        err.append("O2 a non-faulting case needs at least one oracle record "
                   "(unless oracle.kind=open, which by definition asserts none)")
    # 记录值与 expected_state 交叉
    exp = case.get("expected_state") or {}
    for i, r in enumerate(recs):
        if not _is_mapping(r):
            err.append("O3 oracle.records[%d] is not a mapping" % i)
            continue
        keys = [k for k in r if k in ("reg", "mem", "fcsr", "pc", "fault")]
        if len(keys) != 1:
            err.append("O3 oracle.records[%d] must have exactly one of "
                       "reg/mem/fcsr/pc/fault, got %r" % (i, keys))
            continue
        k = keys[0]
        body = r[k]
        if k == "reg":
            if not _is_mapping(body) or "bank" not in body or "index" not in body:
                err.append("O3 reg record needs {bank, index, value}"
                           " or {bank, index, low32, high32}")
                continue
            bank = body.get("bank")
            idx = body.get("index")
            if bank not in F1_REG_BANKS:
                err.append("O3 reg.bank=%r not in %r" % (bank, F1_REG_BANKS))
                continue
            if not isinstance(idx, int) or idx < 0 or idx > 63:
                err.append("O3 reg.index=%r not in 0..63" % (idx,))
                continue
            has_value = "value" in body
            has_halves = ("low32" in body and "high32" in body)
            if has_value == has_halves:
                err.append("O3 reg record for %s%d needs exactly one of "
                           "'value' or ('low32'+'high32')"
                           % (bank, idx))
                continue
            if has_halves and ("low32" in body) != ("high32" in body):
                err.append("O3 f32 half observation needs BOTH low32 and "
                           "high32 (D13 independent observation)")
                continue
            if has_value and not _is_hex64(body.get("value")):
                err.append("O3 reg value=%r is not a 64-bit hex bit-pattern"
                           % (body.get("value"),))
                continue
            if has_halves:
                for half in ("low32", "high32"):
                    v = body.get(half)
                    if not (isinstance(v, str) and
                            re.match(r"^0x[0-9a-fA-F]{1,8}$", str(v).strip())):
                        err.append("O3 reg %s=%r is not a 32-bit hex"
                                   % (half, v))
            key = "%s%d" % (bank, idx)
            got = (exp.get(bank) or {}).get(key)
            if got is None:
                err.append("O4 oracle writes %s but expected_state.%s has no "
                           "such entry" % (key, bank))
            elif has_value and _is_hex64(got) and _is_hex64(body["value"]):
                if _as_u64(got) != _as_u64(body["value"]):
                    err.append("O4 oracle %s=%s disagrees with expected_state."
                               "%s.%s=%s" % (key, body["value"], bank, key, got))
            elif has_halves and _is_hex64(got):
                gv = _as_u64(got)
                lo = int(str(body["low32"]).strip(), 16) & 0xFFFFFFFF
                hi = int(str(body["high32"]).strip(), 16) & 0xFFFFFFFF
                if (gv & 0xFFFFFFFF) != lo or ((gv >> 32) & 0xFFFFFFFF) != hi:
                    err.append("O4 oracle %s halves %s/%s disagree with "
                               "expected_state.%s.%s=%s"
                               % (key, body["high32"], body["low32"], bank,
                                  key, got))
        elif k == "mem":
            if not _is_mapping(body):
                err.append("O3 mem record must be a mapping")
                continue
            addr = body.get("address")
            if not (isinstance(addr, str) and
                    re.match(r"^0x[0-9a-fA-F]{1,12}$", str(addr).strip())):
                err.append("O3 mem address=%r is not a 48-bit hex" % (addr,))
                continue
            for want in F1_MEMORY_KEYS:
                if want not in body:
                    err.append("O3 mem record missing %r" % want)
            if not _is_hex64(body.get("value")):
                err.append("O3 mem value=%r is not a 64-bit hex bit-pattern"
                           % (body.get("value"),))
            else:
                hit = None
                for m in (exp.get("memory") or []):
                    if _is_mapping(m) and m.get("address") == addr:
                        hit = m
                        break
                if hit is None:
                    err.append("O4 oracle stores memory at %s but "
                               "expected_state.memory has no such address"
                               % (addr,))
                elif _is_hex64(hit.get("value")) and \
                        _as_u64(hit["value"]) != _as_u64(body["value"]):
                    err.append("O4 oracle mem value at %s disagrees with "
                               "expected_state.memory (%s vs %s)"
                               % (addr, body["value"], hit["value"]))
        elif k == "fcsr":
            efs = exp.get("fcsr") or {}
            for want in ("rounding_mode", "flags"):
                if want in body and body[want] != efs.get(want):
                    err.append("O4 oracle fcsr.%s=%r disagrees with "
                               "expected_state.fcsr.%s=%r"
                               % (want, body[want], want, efs.get(want)))
            if "observed_mask" in body and \
                    body["observed_mask"] != efs.get("observed_mask"):
                err.append("O4 oracle fcsr.observed_mask=%r disagrees with "
                           "expected_state.fcsr.observed_mask=%r"
                           % (body["observed_mask"], efs.get("observed_mask")))
        elif k == "pc":
            pc = body
            if not (isinstance(pc, str) and
                    re.match(r"^0x[0-9a-fA-F]{1,12}$", str(pc).strip())):
                err.append("O3 pc=%r is not a 48-bit hex address" % (pc,))


# ─────────────────────────── 顶层入口 ───────────────────────────
def validate_f1_case(ctx, case):
    """返回 error 字符串列表；空列表 = 该 case 通过。"""
    err = []
    if not _is_mapping(case):
        return ["case is not a mapping"]
    for key in F1_CASE_TOP_REQUIRED:
        if key not in case:
            err.append("TOP-LEVEL FIELD MISSING: %r" % key)
    if "id" in case:
        cid = case.get("id")
        if not isinstance(cid, str) or not cid.strip():
            err.append("A1 id must be a non-empty string")
    ident = _check_identity_fields(ctx, case, err)
    word = _check_encoding(ctx, case, ident, err)
    _check_reg_bank(ctx, case, "input_state", err, True)
    _check_reg_bank(ctx, case, "expected_state", err, True)
    _check_fcsr(ctx, case, "input_state", err, False)
    _check_fcsr(ctx, case, "expected_state", err, True)
    _check_exclusive(ctx, case, err)
    _check_facets(ctx, case, ident, err)
    _check_ledger(ctx, case, ident, err)
    _check_blocked_unspec(ctx, case, ident, err)
    _check_memory(ctx, case, ident, word, err)
    _check_alignment(ctx, case, ident, word, err)
    _check_src_preset(ctx, case, ident, word, err)
    _check_block_elements(ctx, case, ident, word, err)
    _check_activated_rules(ctx, case, ident, word, err)
    _check_oracle(ctx, case, ident, word, err)
    return err


# ─────────────────────────── 文档 / 目录级 ───────────────────────────
def load_f1_doc(path):
    import yaml
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def validate_f1_tree(ctx, files):
    """校验整个 ``tests/vectors/f1/`` 树。返回 (errors, stats)。

    ``files`` 为 ``[(relpath, cases), ...]``。除逐 case 校验外，另加两条
    树级不变量：
      * ``D17:S2`` 必须**可追踪**：至少一条 case 在 ``ledger_refs.trace_only``
        里引用它（它 ledger 外、永不 blocked、永不计 PASS）。
      * ``D17:S7`` 永不进 ``active_keys``/``blocked_points``，且**不计**为
        OPEN/BLOCKED/PASS（stats 里单列，不得混入 coverage 计数）。
    """
    errors = []
    stats = {"files": 0, "cases": 0, "active_cases": 0, "blocked_facets": 0,
             "active_facets": 0, "trace_only_refs": 0, "non_gap_refs": 0,
             "identities": set(), "blocked_points": set(),
             "unspecified_points": set(), "fcsr_asserts": 0,
             "half_observations": 0, "block_cases": 0, "fault_cases": 0,
             "open_kind_cases": 0}
    seen_ids = {}
    for relpath, cases in files:
        stats["files"] += 1
        if not isinstance(cases, list):
            errors.append("%s: top level must be a YAML list of cases" % relpath)
            continue
        for i, case in enumerate(cases):
            label = "%s[%d]" % (relpath, i)
            cid = case.get("id") if _is_mapping(case) else None
            if isinstance(cid, str):
                if cid in seen_ids:
                    errors.append("%s: DUPLICATE case id %r (first seen in %s)"
                                  % (label, cid, seen_ids[cid]))
                seen_ids[cid] = label
            for e in validate_f1_case(ctx, case):
                errors.append("%s: %s" % (label, e))
            if not _is_mapping(case):
                continue
            stats["cases"] += 1
            if case.get("status") == "active":
                stats["active_cases"] += 1
            ident = case.get("identity")
            if ident in ctx.identities:
                stats["identities"].add(ident)
            if case.get("expected_fault") is not None:
                stats["fault_cases"] += 1
            for k in (case.get("blocked_points") or []):
                stats["blocked_points"].add(k)
            for k in (case.get("unspecified") or []):
                stats["unspecified_points"].add(k)
            lr = case.get("ledger_refs") or {}
            for k in (lr.get("trace_only") or []):
                if k == F.PIN_D17_TRACE_ONLY:
                    stats["trace_only_refs"] += 1
            for k in (lr.get("non_gap") or []):
                if k == F.PIN_D17_NON_GAP:
                    stats["non_gap_refs"] += 1
            facs = case.get("facets") or {}
            for fk, fv in facs.items():
                if not _is_mapping(fv):
                    continue
                if fv.get("status") == "blocked":
                    stats["blocked_facets"] += 1
                elif fv.get("status") == "active":
                    stats["active_facets"] += 1
            orc = case.get("oracle") or {}
            if orc.get("kind") == "block":
                stats["block_cases"] += 1
            elif orc.get("kind") == "open":
                stats["open_kind_cases"] += 1
            for r in (orc.get("records") or []):
                if not _is_mapping(r):
                    continue
                if "fcsr" in r and _is_mapping(r["fcsr"]):
                    stats["fcsr_asserts"] += 1
                reg = r.get("reg")
                if _is_mapping(reg) and "low32" in reg and "high32" in reg:
                    stats["half_observations"] += 1
    if stats["trace_only_refs"] == 0:
        errors.append("TREE: %s is never referenced in ledger_refs.trace_only; "
                      "D17:S2 must remain traceable (it is ledger-outside, "
                      "never blocked, never PASS)" % F.PIN_D17_TRACE_ONLY)
    return errors, stats
