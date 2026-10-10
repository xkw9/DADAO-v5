#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""generate_f1_schema_fixtures.py — 生成 TESTCASES-101t 的 F1 最小正/反样例。

**期望值来源**：`tools/testcases/f1_oracle_values.py` 的整数位型推导（独立
oracle）。本脚本**不** import / 调用 LLVM、QEMU、SoftFloat、宿主 `float` 或
`libm`；所有 32/64 位期望值都是十六进制字面量，由手工整数推导写死在
`f1_oracle_values.py`，并由 `f1_cases.py` 的独立检查重算比对。

指令字由 `enc()` 按 `contracts/opcodes.yaml` 的字段位号**自动**组装
（不手算位偏移）；`enc()` 同时断言产出字通过 `f1_schema.encode_check`。

产物：
  tests/vectors/f1/valid/f1-schema-valid.yaml     最小**正**样例（须全绿）
  tests/vectors/f1/invalid/f1-schema-invalid.yaml 最小**反**样例（须被拒绝）

反例样例是**刻意的坏数据**，只用于证明 validator 能失败；它们与正样例分目录，
`validate_vectors.py` 只把 `valid/` 当数据校验，`invalid/` 走「必须 FAIL」门控。

用法：
  python3 tools/testcases/generate_f1_schema_fixtures.py            # 写入仓库
  python3 tools/testcases/generate_f1_schema_fixtures.py --out DIR  # 写到别处
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import copy                                        # noqa: E402

import f1_oracle_values as V                       # noqa: E402
import f1_schema as F                              # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))
DEFAULT_OUT = os.path.join(REPO_ROOT, "tests", "vectors", "f1")

_CTX = F.F1Context()


# ───────────────────────── 指令字组装 ─────────────────────────
def _bits(f):
    """返回 ``(hi, lo)``（opcodes.yaml 的 ``bits: "[hi:lo]"`` 书写序）。"""
    hi, lo = F.BITS_RE.match(str(f["bits"])).groups()
    return int(hi), int(lo)


def _base_name(name):
    for suf in ("_hi", "_mid", "_lo"):
        if name.endswith(suf) and len(name) > len(suf):
            return name[:-len(suf)]
    return name


def enc(identity, **fields):
    """按 ``contracts/opcodes.yaml`` 的字段位号组装 32 位指令字。

    传键为**基名**（``rfhb`` / ``rdhb`` / ``rfha`` / ``immu6`` / ``imms12`` /
    ``immu16`` …），复合字段自动按 ``_hi``/``_mid``/``_lo`` 切片。传 ``None``
    表示把该字段清零。产出字必须通过 ``f1_schema.encode_check``（即身份一致），
    否则直接抛错——避免写出与 identity 不符的指令字。
    """
    rec = _CTX.rec(identity)
    if rec is None:
        raise KeyError("unknown identity %r" % identity)
    by_base = {}
    for f in rec["fields"]:
        by_base.setdefault(_base_name(f["name"]), []).append(f)
    for key in fields:
        if key not in by_base:
            raise KeyError("field %r not in identity %r (have %s)"
                           % (key, identity, sorted(by_base)))
    word = int(str(rec["value"]), 16)
    for key, val in fields.items():
        parts = sorted(by_base[key], key=lambda f: _bits(f)[0], reverse=True)
        widths = [_bits(f)[0] - _bits(f)[1] + 1 for f in parts]
        total = sum(widths)
        for f in parts:                                  # 先整段清零
            hi, lo = _bits(f)
            word &= ~(((1 << (hi - lo + 1)) - 1) << lo)
        if val is None:
            continue
        if val < 0 or val >= (1 << total):
            raise ValueError("field %s: %r does not fit in %d bits"
                             % (key, val, total))
        for i, f in enumerate(parts):                    # 再逐片写入（高位在前）
            hi, lo = _bits(f)
            width = widths[i]
            shift = sum(widths[i + 1:])
            word |= ((val >> shift) & ((1 << width) - 1)) << lo
    ok, mask, value = F.encode_check(word, rec)
    if not ok:
        raise ValueError("enc(%r, **%r) = 0x%08X fails (word&0x%08X)=="
                         "(0x%08X&0x%08X)" % (identity, fields, word, mask,
                                               value, mask))
    return word & 0xFFFFFFFF


# ── 引用锚点（写进 spec_cite / facet cite，须被 _CITE_TOKEN_RE 接受） ──
C_CONTRACT = "contract-f1-floating.md"
C_SIM03 = "SimRISC-03"
C_SIM00 = "SimRISC-00"
C_OPCODES = "opcodes.yaml"
C_ADR08 = "adr-1008"
C_ADR09 = "adr-1009"
C_ADR10 = "adr-1010"
C_ADR11 = "adr-1011"
C_ADR12 = "adr-1012"
C_ADR13 = "adr-1013"
C_ADR14 = "adr-1014"
C_ADR15 = "adr-1015"

# 统一的可观测 mask：只读域（合约 §2 已知位型）+ 整个 rw 域，绝不含 SBZ 位
OBS = V.FCSR_FULL_OBSERVED_MASK
CODES = {"RNE": 0, "RTZ": 1, "RDN": 2, "RUP": 3}
FLAGBIT = {n: 1 << i for i, n in enumerate(("NV", "DZ", "OF", "UF", "NX"))}


def hx(v):
    return "0x%016X" % (v & 0xFFFFFFFFFFFFFFFF)


def hx32(v):
    return "0x%08X" % (v & 0xFFFFFFFF)


def fcsr_exp(rounding="RNE", flags=(), mask=None, value=True, **extra):
    fb = 0
    for n in flags:
        fb |= FLAGBIT[n]
    d = {"rounding_mode": rounding, "flags": sorted(set(flags))}
    if mask is not None:
        d["observed_mask"] = hx(mask)
    if value:
        d["value"] = hx(V.fcsr_value(CODES[rounding], fb))
    d.update(extra)
    return d


def facets(*pairs):
    """pairs: (facet, status, cite[, extra_dict])"""
    out = {}
    for item in pairs:
        k, st, cite = item[0], item[1], item[2]
        d = {"status": st, "cite": cite}
        if len(item) > 3 and item[3]:
            d.update(item[3])
        out[k] = d
    return out


def ledger(active=(), trace=(), nongap=()):
    return {"active_keys": sorted(active), "trace_only": sorted(trace),
            "non_gap": sorted(nongap)}


def state(rf=None, rd=None, rb=None, ra=None, fcsr=None, memory=None):
    return {"rd": rd or {}, "rb": rb or {}, "ra": ra or {}, "rf": rf or {},
            "fcsr": fcsr, "memory": memory or []}


def reg_rec(bank, index, value):
    return {"reg": {"bank": bank, "index": index, "value": hx(value)}}


def half_rec(bank, index, value64):
    """f32 两半的**独立**观测（D13：低 32 与高 32 分开断言）。"""
    return {"reg": {"bank": bank, "index": index,
                    "low32": hx32(value64 & 0xFFFFFFFF),
                    "high32": hx32((value64 >> 32) & 0xFFFFFFFF)}}


def mem(addr, value, width):
    return {"address": addr, "value": hx(value), "width": width}


def case(cid, identity, cls, word, in_state, facets_, oracle, cite, notes,
         expected_fault=None, expected_state=None, blocked_points=(),
         unspecified=(), ledger_refs=None, order=None):
    c = {
        "id": cid,
        "identity": identity,
        "insn": identity,
        "mnemonic": _CTX.rec(identity)["mnemonic"],
        "format": _CTX.rec(identity)["format"],
        "class": cls,
        "encoding": {"word": "0x%08X" % word},
        "input_state": in_state,
        "expected_fault": expected_fault,
        "expected_pc": None,
        "expected_state": expected_state,
        "status": "active",
        "facets": facets_,
        "ledger_refs": ledger_refs if ledger_refs is not None else ledger(),
        "blocked_points": list(blocked_points),
        "unspecified": list(unspecified),
        "oracle": oracle,
        "spec_cite": cite,
        "notes": notes,
    }
    if order is not None:
        c["order"] = order
    return c


# 常用 facet 组合（每个 identity 只声明**非 n/a** 的 facet）
F_ENC = ("encoding", "active", "%s §1 identity-table；%s" % (C_CONTRACT, C_OPCODES))
F_FMT = ("format", "active", "%s §1" % C_CONTRACT)
F_OPS = ("operands", "active", "%s §1" % C_CONTRACT)
F_LEG = ("legality", "active", "%s §3.1" % C_CONTRACT)
F_SEM = ("semantics", "active", "%s §4" % C_CONTRACT)
F_RF0 = ("rf0_operand", "active", "%s D11；%s D2" % (C_CONTRACT, C_ADR09))
F_HI32 = ("tetra_high_half", "active", "%s D1；%s" % (C_CONTRACT, C_ADR11))
F_FCSR = ("fcsr_flags", "active", "%s D1；%s" % (C_CONTRACT, C_ADR10))
F_TINY = ("tininess", "active", "%s D1；%s" % (C_CONTRACT, C_ADR14))
F_NAN = ("nan_propagation", "active", "%s D1；%s" % (C_CONTRACT, C_ADR13))
F_ORD = ("compare_unordered", "active", "%s D2；%s" % (C_ADR12, C_CONTRACT))


# ═══════════════════════════ 正 样 例 ═══════════════════════════
def valid_cases():
    out = []

    # 1 ── RF 索引 + 基本语义 + fcsr 完整可断言（foadd：1.0 + 2.0 = 3.0）
    # 编码 orrr：rfhb[17:12]=dst=rf1、rfhc[11:6]=源1=rf2、rfhd[5:0]=源2=rf3
    out.append(case(
        "f1-foadd-basic-rf-index", "foadd", "semantic",
        enc("foadd", rfhb=1, rfhc=2, rfhd=3),
        state(rf={"rf1": hx(V.FO_ZERO), "rf2": hx(V.FO_ONE),
                  "rf3": hx(V.FO_TWO)},
              fcsr=fcsr_exp("RNE", (), value=False, **{"from_reset": True})),
        facets(F_ENC, F_FMT, F_OPS, F_LEG, F_SEM, F_RF0, F_FCSR, F_TINY,
               F_NAN),
        {"kind": "order", "records": [reg_rec("rf", 1, V.EXP_FOADD_1PLUS2),
                                      {"fcsr": fcsr_exp("RNE", (), mask=OBS)}]},
        "%s §4.2 两源一目的运算（rfhb 目的、rfhc/rfhd 两源）；%s D5"
        % (C_SIM03, C_CONTRACT),
        "foadd rf1,rf2,rf3 = 1.0 + 2.0 = 3.0（0x%016X）：rfhb 给出目的 rf1、"
        "rfhc 给出源 1.0、rfhd 给出源 2.0，1+2=3（3.0 = 1.5×2^1，指数 0x400、"
        "尾数最高位 1）。rf 索引 1/2/3 全是合法 rf 索引（rf0..rf63）。"
        "rf0 用 D17:S1 复位取值（RNE + flags 全 0）" % V.EXP_FOADD_1PLUS2,
        expected_state=state(rf={"rf1": hx(V.EXP_FOADD_1PLUS2)},
                             fcsr=fcsr_exp("RNE", (), mask=OBS)),
        ledger_refs=ledger(active=["D17:S1", "D17:S4"]), order="none"))

    # 2 ── FCSR：非默认舍入模式 RTZ 可观测 + 除零 DZ（IEEE 754 §7.2）
    out.append(case(
        "f1-ftdiv-rounding-rtz-dz", "ftdiv", "boundary",
        enc("ftdiv", rfhb=1, rfhc=2, rfhd=3),
        state(rf={"rf1": hx32(V.FT_ZERO), "rf2": hx32(V.FT_ONE),
                  "rf3": hx32(V.FT_ZERO)},
              fcsr=fcsr_exp("RTZ", (), value=False)),
        facets(F_ENC, F_FMT, F_OPS, F_LEG, F_SEM, F_RF0, F_HI32, F_FCSR,
               F_TINY, F_NAN),
        {"kind": "order", "records": [
            half_rec("rf", 1, V.EXP_FTDIV_BY_ZERO),
            {"fcsr": fcsr_exp("RTZ", ("DZ",), mask=OBS)}]},
        "%s §4.2（rfhc=被除数、rfhd=除数）；%s §2「按 IEEE 754 设置 rf0[4:0]」"
        % (C_SIM03, C_CONTRACT),
        "ftdiv rf1,rf2,rf3：rf2 = 1.0f（被除数）、rf3 = 0.0f（除数），属"
        "「有限非零数除以零」。IEEE 754 §7.2 规定结果是无限精确结果正确舍入后"
        "的值，而 ±∞ 本身可表示且精确 → **四种舍入模式一律 ±∞**（本例取 RTZ，"
        "结果仍与 RNE 相同）；§7.4 的 inexact 不成立 → 只置 DZ，不置 NX；"
        "除零也**不是** overflow，故 D16 的 OF+NX 配对不适用。"
        "tetra 装箱后 rf1 = 0x%016X（高 32 位 0xFFFFFFFF 是 D13）。"
        "本例另证 rf0[17:16]=RTZ 可观测且被保留（observed_mask 覆盖整个 rw 域）"
        % V.EXP_FTDIV_BY_ZERO,
        expected_state=state(rf={"rf1": hx(V.EXP_FTDIV_BY_ZERO)},
                             fcsr=fcsr_exp("RTZ", ("DZ",), mask=OBS)),
        ledger_refs=ledger(active=["D17:S1", "D17:S4"]), order="none"))

    # 3 ── f32 高半部 D13：两半独立观测
    out.append(case(
        "f1-ftadd-tetra-high-half-d13", "ftadd", "semantic",
        enc("ftadd", rfhb=1, rfhc=2, rfhd=3),
        state(rf={"rf1": hx32(V.FT_ZERO), "rf2": hx32(V.FT_ONE),
                  "rf3": hx32(V.FT_ZERO)},
              fcsr=fcsr_exp("RNE", (), value=False, **{"from_reset": True})),
        facets(F_ENC, F_FMT, F_OPS, F_LEG, F_SEM, F_RF0, F_HI32, F_FCSR,
               F_TINY, F_NAN),
        {"kind": "order", "records": [
            half_rec("rf", 1, V.EXP_FTADD_0PLUS1),
            {"fcsr": fcsr_exp("RNE", (), mask=OBS)}]},
        "%s §4.2；%s D1（高半部固定 0xFFFFFFFF）" % (C_SIM03, C_ADR11),
        "ftadd rf1,rf2,rf3 = 0.0f + 1.0f = 1.0f = 0x3F800000；D13 规定 tetra "
        "写 rf 的高 32 位固定 0xFFFFFFFF → 64 位 0xFFFFFFFF3F800000。本例用 "
        "low32/high32 **两半独立**观测（oracle 记录与 expected_state 交叉核对）",
        expected_state=state(rf={"rf1": hx(V.EXP_FTADD_0PLUS1)},
                             fcsr=fcsr_exp("RNE", (), mask=OBS)),
        ledger_refs=ledger(active=["D17:S1", "D17:S4"]), order="none"))

    # 4 ── 异常 ILLI（rd2rf → rf0，D11 明确 ILLI）
    out.append(case(
        "f1-rd2rf-rf0-illi-d11", "rd2rf", "legality",
        enc("rd2rf", rfhb=0, rdhc=3, immu6=1),
        state(rd={"rd3": hx(0x0000000000000001)},
              fcsr=fcsr_exp("RNE", (), value=False, **{"from_reset": True})),
        facets(F_ENC, F_FMT, F_OPS,
               ("legality", "active",
                "%s §3.1 rf0_dst_allowed；%s D2" % (C_CONTRACT, C_ADR09)),
               ("semantics", "blocked", "%s §6.2 D17:S6" % C_CONTRACT,
                {"open_ids": ["D17:S6"], "rule": "rf0 的 SBZ 域写入行为"}),
               F_RF0, F_FCSR),
        {"kind": "order",
         "records": [{"fault": {"type": "ILLI", "pc": "0xFFFF00000010"}}]},
        "%s D2（rf0 写白名单十条不含 rd2rf）；%s §3.1" % (C_ADR09, C_CONTRACT),
        "rd2rf rf0（目的 rfhb=0）, 源 rd3, immu6=1：目的 rf0 不在十条白名单内"
        " → D11 明确 ILLI；整条不提交任何 rf 写（fault 记录是最后一条，"
        "且不带任何 reg/mem/fcsr 记录）",
        expected_fault="ILLI", expected_state=None,
        ledger_refs=ledger(active=["D17:S1", "D17:S4", "D17:S6"]), order="none"))

    # 5 ── 异常 MALIGN（ld.t-rf 4 字节不对齐）
    out.append(case(
        "f1-ldt-rf-malign", "ld.t-rf", "legality",
        enc("ld.t-rf", rfha=1, rbhb=1, imms12=0),
        state(rb={"rb1": hx(0xFFFF00000002)},
              fcsr=fcsr_exp("RNE", (), value=False, **{"from_reset": True}),
              memory=[mem("0xFFFF00000002", 0, 4)]),
        facets(F_ENC, F_FMT, F_OPS,
               ("legality", "active",
                "%s §3.1 aligned(4)（SimRISC-03:25）" % C_CONTRACT),
               ("semantics", "active", "%s §存取RF寄存器" % C_SIM03),
               F_RF0, F_HI32, F_FCSR),
        {"kind": "order",
         "records": [{"fault": {"type": "MALIGN", "pc": "0xFFFF00000010"}}]},
        "%s §3.1 aligned(4)；%s D3（ILLI 先于 MALIGN）" % (C_CONTRACT, C_ADR15),
        "ld.t-rf rf1, rb1, 0：rb1 = 0xFFFF00000002（% 4 = 2）+ imms12 = 0 → "
        "4 字节不对齐 → MALIGN。本例无任何静态 ILLI 谓词成立，故走 MALIGN 分支",
        expected_fault="MALIGN", expected_state=None,
        ledger_refs=ledger(active=["D17:S1", "D17:S4", "D17:S6"]), order="none"))

    # 6 ── D17:S4 优先级：ftcls immu6≠1 → 静态 ILLI，优先于任何对齐判定
    out.append(case(
        "f1-ftcls-immu6-neq1-illi-priority", "ftcls", "legality",
        enc("ftcls", rdhb=1, rfhc=1, immu6=2),
        state(rb={"rb1": hx(0xFFFF00000002)}, rf={"rf1": hx32(V.FT_ONE)},
              fcsr=fcsr_exp("RNE", (), value=False, **{"from_reset": True})),
        facets(F_ENC, F_FMT, F_OPS,
               ("legality", "active",
                "%s D2：immu6≠1 非 assembler 路径到硬件即 ILLI" % C_ADR15),
               ("semantics", "active", "%s §4.8" % C_CONTRACT),
               F_FCSR),
        {"kind": "order",
         "records": [{"fault": {"type": "ILLI", "pc": "0xFFFF00000010"}}]},
        "%s D2（classify immediate）；%s D3（ILLI 先于 MALIGN）"
        % (C_ADR15, C_ADR15),
        "ftcls rd1, rf1, immu6=2：classify 的 immu6 固定为 1（S3 / ADR-1015 "
        "D2）→ 静态 ILLI；非法操作数**不进入**对齐判定（D17:S4），故即使 "
        "rb1 预置成不对齐值也仍是 ILLI 而不是 MALIGN",
        expected_fault="ILLI", expected_state=None,
        ledger_refs=ledger(active=["D17:S1", "D17:S3", "D17:S4"]), order="none"))

    # 7 ── 块操作 ldm.t：EA0 = rb2 + rd1、EA(i) = EA0 + i*4、rf 递增
    out.append(case(
        "f1-ldm-t-block-ea0-increment", "ldm.t-rf", "semantic",
        enc("ldm.t-rf", rfha=3, rbhb=2, rdhc=1, immu6=2),
        state(rd={"rd1": hx(0x0000000000000010)},
              rb={"rb2": hx(0xFFFF00001000)},
              fcsr=fcsr_exp("RNE", (), value=False, **{"from_reset": True}),
              memory=[mem("0xFFFF00001010", V.FT_ONE, 4),
                      mem("0xFFFF00001014", V.FT_TWO, 4)]),
        facets(F_ENC, F_FMT, F_OPS, F_LEG,
               ("semantics", "active",
                "%s D7/D8：EA0=rbhb+rdhc、EA(i)=EA0+i*4、rf 递增" % C_ADR15),
               F_RF0, F_HI32, F_FCSR),
        {"kind": "block", "records": [
            half_rec("rf", 3, V.tetra_boxed(V.FT_ONE)),
            half_rec("rf", 4, V.tetra_boxed(V.FT_TWO)),
            {"fcsr": fcsr_exp("RNE", (), mask=OBS)}],
            "elements": [
                {"rf": 3, "address": "0xFFFF00001010", "width": 4,
                 "value": hx(V.FT_ONE)},
                {"rf": 4, "address": "0xFFFF00001014", "width": 4,
                 "value": hx(V.FT_TWO)}]},
        "%s D7/D8；%s §存取RF寄存器" % (C_ADR15, C_SIM03),
        "ldm.t rf3, rb2, rd1, immu6=2：EA0 = 0xFFFF00001000 + 0x10 = "
        "0xFFFF00001010；EA(1) = EA0 + 1*4 = 0xFFFF00001014；rf3/rf4 递增；"
        "每元素 4 字节按 D13 装箱成 0xFFFFFFFFxxxxxxxx",
        expected_state=state(rf={"rf3": hx(V.tetra_boxed(V.FT_ONE)),
                                  "rf4": hx(V.tetra_boxed(V.FT_TWO))},
                             fcsr=fcsr_exp("RNE", (), mask=OBS)),
        ledger_refs=ledger(active=["D17:S1", "D17:S4", "D17:S6", "D17:S8"]),
        order="block-increasing"))

    # 8 ── 重叠块传输（先读后写，unordered 观测）
    out.append(case(
        "f1-ldm-t-overlap-read-before-write", "ldm.t-rf", "overlap",
        enc("ldm.t-rf", rfha=3, rbhb=2, rdhc=1, immu6=2),
        state(rd={"rd1": hx(0x0000000000000010)},
              rb={"rb2": hx(0xFFFF00001000)},
              rf={"rf3": hx32(V.FT_ZERO), "rf4": hx32(V.FT_TWO)},
              fcsr=fcsr_exp("RNE", (), value=False, **{"from_reset": True}),
              memory=[mem("0xFFFF00001010", V.FT_ONE, 4),
                      mem("0xFFFF00001014", V.FT_TWO, 4)]),
        facets(F_ENC, F_FMT, F_OPS, F_LEG,
               ("semantics", "active",
                "%s D9：块内先读后写、整块原子提交" % C_ADR15),
               F_RF0, F_HI32, F_FCSR),
        {"kind": "unordered", "records": [
            half_rec("rf", 3, V.tetra_boxed(V.FT_ONE)),
            half_rec("rf", 4, V.tetra_boxed(V.FT_TWO)),
            {"fcsr": fcsr_exp("RNE", (), mask=OBS)}],
            "elements": [
                {"rf": 3, "address": "0xFFFF00001010", "width": 4,
                 "value": hx(V.FT_ONE)},
                {"rf": 4, "address": "0xFFFF00001014", "width": 4,
                 "value": hx(V.FT_TWO)}]},
        "%s D9（重叠块传输：先读后写、整块提交）；%s D7/D8"
        % (C_ADR15, C_ADR15),
        "rf3 预置 0.0f、rf4 预置 2.0f；内存 EA0=0xFFFF00001010 放 1.0f、"
        "EA(1)=0xFFFF00001014 放 2.0f。rf4 既是块内的**目的**又被 EA(1) "
        "覆盖，构成源/目的重叠。oracle.kind=unordered：整块原子提交，重叠处"
        "的最终值与读序无关，故按集合语义观测",
        expected_state=state(rf={"rf3": hx(V.tetra_boxed(V.FT_ONE)),
                                  "rf4": hx(V.tetra_boxed(V.FT_TWO))},
                             fcsr=fcsr_exp("RNE", (), mask=OBS)),
        ledger_refs=ledger(active=["D17:S1", "D17:S4", "D17:S6", "D17:S8"]),
        order="read-before-write"))

    # 9 ── rf0 精确 mask：写 rf0 时 SBZ 域不观测（D17:S6 + D11）
    out.append(case(
        "f1-setw-rf0-sbz-mask-d17s6", "set.w-rf", "boundary",
        enc("set.w-rf", rfha=0, wpN=0, immu16=0),
        state(fcsr=fcsr_exp("RNE", (), value=False,
                            **{"from_reset": True})),
        facets(F_ENC, F_FMT, F_OPS,
               ("legality", "active",
                "%s §3.1 rf0_dst_allowed（写 rf0 合法）" % C_CONTRACT),
               ("semantics", "active",
                "%s D5：写 rf0 时对 [50:32]/[21:18]/[15:5] 静默忽略，"
                "只读域保持合约 §2 的位型" % C_ADR15),
               F_RF0, F_FCSR),
        {"kind": "order",
         "records": [{"fcsr": fcsr_exp("RNE", (), mask=OBS)}]},
        "%s D5（SBZ write）；%s D2" % (C_ADR15, C_ADR09),
        "set.w-rf rf0（rfha=0, wpN=0）, immu16=0：合法写 rf0（在十条白名单内）。"
        "只读域 [63:51]/[31:22] 按合约 §2 保持 0xFFF / 0x1FF 位型，rw 域写 0；"
        "**SBZ 域不被断言** —— observed_mask 只含只读域 + rw 域，不含任何 SBZ 位，"
        "这正是 D17:S6「写入行为未规定」的可观测边界",
        expected_state=state(fcsr=fcsr_exp("RNE", (), mask=OBS)),
        ledger_refs=ledger(active=["D17:S1", "D17:S4", "D17:S6"]), order="none"))

    # 10 ── D14 unordered 比较（foqcmp → 0x7FF8000000000000）
    out.append(case(
        "f1-foqcmp-unordered-d14", "foqcmp", "semantic",
        enc("foqcmp", rdhb=1, rfhc=1, rfhd=2),
        state(rf={"rf1": hx(V.FO_QNAN), "rf2": hx(V.FO_ONE)},
              fcsr=fcsr_exp("RNE", (), value=False, **{"from_reset": True})),
        # foqcmp 的 nan_propagation / tininess 在合约 §5.1 是 n/a → **不得声明**
        facets(F_ENC, F_FMT, F_OPS, F_LEG, F_SEM, F_RF0, F_ORD, F_FCSR),
        {"kind": "order", "unordered_case": True,
         "records": [reg_rec("rd", 1, V.D14_QUIET_UNORDERED),
                     {"fcsr": fcsr_exp("RNE", (), mask=OBS)}]},
        "%s D2（quiet 类 unordered 位型）" % C_ADR12,
        "foqcmp rd1, rf1, rf2：orrr 的 rf 字段是 rfhc[11:6]=rf1、rfhd[5:0]=rf2，"
        "rf1 = quiet NaN（0x7FF8000000000000）→ unordered；D14 规定 foqcmp 的 "
        "unordered 写 RD 0x7FF8000000000000，输出位型只由 qcmp/scmp 类别决定，"
        "与输入 NaN 的 quiet/signaling 无关。源**刻意**取 qNaN：sNaN 作操作数"
        "会按 IEEE 754 §7.2 另置 NV，而 rule_tables.D15 的「qNaN 不置 NV / "
        "sNaN 置 NV」只固定在 18 条算术 identity 上、比较类未固定 → 用 sNaN "
        "就必须断言一个未被激活的 flags 取值。foqcmp 只有两个 rf 源，不得往 "
        "input_state.rf 里塞 rf3",
        expected_state=state(rd={"rd1": hx(V.D14_QUIET_UNORDERED)},
                             fcsr=fcsr_exp("RNE", (), mask=OBS)),
        ledger_refs=ledger(active=["D17:S1", "D17:S4"]), order="none"))

    # 11 ── D12 非自动置位：ld.o-rf 装 sNaN 也不置 NV
    out.append(case(
        "f1-ldo-rf-d12-non-automatic", "ld.o-rf", "semantic",
        enc("ld.o-rf", rfha=1, rbhb=1, imms12=0),
        state(rb={"rb1": hx(0xFFFF00000000)},
              fcsr=fcsr_exp("RNE", (), value=False, **{"from_reset": True}),
              memory=[mem("0xFFFF00000000", V.FO_SNAN, 8)]),
        facets(F_ENC, F_FMT, F_OPS,
               ("legality", "active", "%s §3.1 aligned(8)" % C_CONTRACT),
               ("semantics", "active", "%s §存取RF寄存器" % C_SIM03),
               F_RF0,
               ("fcsr_flags", "active",
                "%s D1/D2：数据搬移类**非**自动置位，装载 sNaN 也不置 NV"
                % C_ADR10)),
        {"kind": "order", "records": [
            reg_rec("rf", 1, V.FO_SNAN),
            {"fcsr": fcsr_exp("RNE", (), mask=OBS)}]},
        "%s D2（non-automatic scope 含 ld.o-rf）" % C_ADR10,
        "ld.o-rf rf1, rb1, 0 从 0xFFFF00000000 装 8 字节 sNaN"
        "（0x7FF0000000000001，**不**装箱：octa 无 D13）。ld.o-rf 属 D12 "
        "非自动置位的 11 条之一 → rf0[4:0] 保持 0（自动置 NV 会被 I4 判 FAIL）",
        expected_state=state(rf={"rf1": hx(V.FO_SNAN)},
                             fcsr=fcsr_exp("RNE", (), mask=OBS)),
        ledger_refs=ledger(active=["D17:S1", "D17:S4", "D17:S6"]), order="none"))

    # 12 ── D17:S2 trace-only（ledger 外，永不 blocked、永不计 PASS）
    out.append(case(
        "f1-ldt-rf-d17s2-trace-only", "ld.t-rf", "semantic",
        enc("ld.t-rf", rfha=1, rbhb=1, imms12=0),
        state(rb={"rb1": hx(0xFFFF00000000)},
              fcsr=fcsr_exp("RNE", (), value=False, **{"from_reset": True}),
              memory=[mem("0xFFFF00000000", V.FT_ONE, 4)]),
        facets(F_ENC, F_FMT, F_OPS,
               ("legality", "active",
                "%s §6.3：D17:S2 无行为后果，**不**据此追加谓词" % C_CONTRACT),
               ("semantics", "active", "%s §存取RF寄存器" % C_SIM03),
               F_RF0, F_HI32, F_FCSR),
        {"kind": "order", "records": [
            half_rec("rf", 1, V.EXP_LDT_RF_LOAD),
            {"fcsr": fcsr_exp("RNE", (), mask=OBS)}]},
        "%s §6.3（D17:S2：no behavioral consequence; resolved/trace-only; "
        "not in D17 OPEN-ID ledger; never PASS）" % C_CONTRACT,
        "ld.t-rf rf1, rb1, 0：immu6 上限 63 由 6 位字段宽唯一决定、「有效范围 "
        "1~63」是否出现在本节**无行为后果**。D17:S2 仅在 ledger_refs.trace_only "
        "里作来源追踪：不占用 ledger 键、不是阻塞项、不得计 PASS",
        expected_state=state(rf={"rf1": hx(V.EXP_LDT_RF_LOAD)},
                             fcsr=fcsr_exp("RNE", (), mask=OBS)),
        ledger_refs=ledger(active=["D17:S1", "D17:S4", "D17:S6"],
                           trace=["D17:S2"]), order="none"))

    # 13 ── D17:S7 non-gap（ADR-1008 D1 证明唯一确定，不进 ledger）
    out.append(case(
        "f1-rf2rd-s7-spec-determined-nongap", "rf2rd", "overlap",
        enc("rf2rd", rdhb=2, rfhc=1, immu6=3),
        state(rd={"rd2": hx(0), "rd3": hx(0), "rd4": hx(0)},
              rf={"rf1": hx(0x0123456789ABCDEF), "rf2": hx(0xFEDCBA9876543210),
                  "rf3": hx(V.FO_ZERO)},
              fcsr=fcsr_exp("RNE", (), value=False, **{"from_reset": True})),
        facets(F_ENC, F_FMT, F_OPS, F_LEG,
               ("semantics", "active",
                "%s D1：源/目的范围重叠时的读写顺序由 SimRISC-00:41-46 与 "
                "SimRISC-03:34-50 唯一确定" % C_ADR08),
               F_RF0, F_FCSR),
        {"kind": "unordered", "records": [
            reg_rec("rd", 2, 0x0123456789ABCDEF),
            reg_rec("rd", 3, 0xFEDCBA9876543210),
            reg_rec("rd", 4, V.FO_ZERO)]},
        "%s D1（D17:S7 = spec-determined non-gap：move overlap 由 "
        "SimRISC-00:41-46 与 SimRISC-03:34-50 唯一确定）" % C_ADR08,
        "rf2rd rd2, rf1, immu6=3：源 rf1..rf3 写 rd2..rd4（源/目的范围重叠）。"
        "D17:S7 是 ADR-1008 D1 已证明的 spec-determined non-gap —— "
        "**不进** active ledger、**不计** OPEN/BLOCKED、**不计** PASS；"
        "它只出现在 ledger_refs.non_gap 里作对照",
        expected_state=state(rd={"rd2": hx(0x0123456789ABCDEF),
                                 "rd3": hx(0xFEDCBA9876543210),
                                 "rd4": hx(V.FO_ZERO)},
                             rf={"rf1": hx(0x0123456789ABCDEF),
                                 "rf2": hx(0xFEDCBA9876543210),
                                 "rf3": hx(V.FO_ZERO)},
                             fcsr=fcsr_exp("RNE", (), mask=OBS)),
        ledger_refs=ledger(active=["D17:S1", "D17:S4"], nongap=["D17:S7"]),
        order="read-before-write"))

    # 14 ── D16 复合 flags：上溢必同时置 OF+NX
    out.append(case(
        "f1-foadd-overflow-of-nx-d16", "foadd", "boundary",
        enc("foadd", rfhb=1, rfhc=2, rfhd=3),
        state(rf={"rf1": hx(V.FO_ZERO), "rf2": hx(V.FO_MAX_FINITE),
                  "rf3": hx(V.FO_MAX_FINITE)},
              fcsr=fcsr_exp("RNE", (), value=False, **{"from_reset": True})),
        facets(F_ENC, F_FMT, F_OPS, F_LEG, F_SEM, F_RF0, F_FCSR,
               ("tininess", "active",
                "%s D1/D2：最终舍入后检测 tininess；上溢同时置 OF+NX"
                % C_ADR14),
               F_NAN),
        {"kind": "order", "records": [
            reg_rec("rf", 1, V.EXP_FOADD_OVERFLOW),
            {"fcsr": fcsr_exp("RNE", ("OF", "NX"), mask=OBS)}]},
        "%s D2（overflow ⇒ OF+NX）" % C_ADR14,
        "foadd rf1,rf2,rf3：rf2 = rf3 = 最大有限 fo（0x7FEFFFFFFFFFFFFF），"
        "精确和 2×max 超过最大有限 → 舍入到 +Inf（0x7FF0000000000000）；"
        "D16 规定上溢**同时**置 OF+NX。把 NX 去掉会被 I5 判 FAIL；"
        "把 OF/NX 搬到 D16 scope 外的 identity 也会",
        expected_state=state(rf={"rf1": hx(V.EXP_FOADD_OVERFLOW)},
                             fcsr=fcsr_exp("RNE", ("OF", "NX"), mask=OBS)),
        ledger_refs=ledger(active=["D17:S1", "D17:S4"]), order="none"))

    # 15 ── rootn(-0,2) explicitly-unspecified（永不给唯一 expected）
    out.append(case(
        "f1-foroot-negative-zero-unspecified", "foroot", "legality",
        enc("foroot", rfhb=1, rfhc=2, immu6=2),
        state(rf={"rf1": hx(V.FO_ZERO), "rf2": hx(V.FO_NEG_ZERO)},
              fcsr=fcsr_exp("RNE", (), value=False, **{"from_reset": True})),
        facets(F_ENC, F_FMT, F_OPS,
               ("legality", "active",
                "%s §3.1 rootn_n_in_2_3（n 只支持 2/3）" % C_CONTRACT),
               ("semantics", "blocked",
                "%s §7.2 remaining_unspecified：rootn(-0,2) 规范明示不做要求"
                % C_CONTRACT,
                {"open_ids": ["D15"], "rule": "rootn(-0,2) 不得有唯一 expected"}),
               F_RF0, F_FCSR, F_TINY,
               ("nan_propagation", "blocked",
                "%s §7.2；canonical_qnan_bits 在 ADR-1013 未给 64 位常量"
                % C_CONTRACT,
                {"open_ids": ["D15"], "rule": "canonical_qnan_bits = null"})),
        # oracle.kind=open：显式声明「本 case **不**给唯一期望值」，
        # 并用 blocked_points/unspecified 说明原因。
        {"kind": "open", "records": []},
        "%s §7.2（rootn(-0,2) = explicitly-unspecified）；%s §3.1 "
        "rootn_n_in_2_3" % (C_CONTRACT, C_CONTRACT),
        "foroot rf1, rf2, immu6=2：n=2 合法，被开方数 rf2 = -0.0"
        "（0x8000000000000000，仅符号位 1）——正是 rootn(-0,2) 这个规范明示"
        "「不做具体要求」的点 → oracle.kind=open，**不生成**唯一 expected"
        "（expected_state 为 null、expected_fault 为 null、oracle.records 为空）。"
        "rf1 是目的寄存器，orri 只有 rfhb/rfhc 两个 rf 操作数 + immu6，"
        "不得再往 input_state.rf 里塞指令不存在的 rf。root/log 的独立正确舍入"
        "算法属 CAP-01，仍 BLOCKED；canonical_qnan_bits 保持 null，下游不得代填",
        expected_fault=None, expected_state=None,
        blocked_points=["D15:canonical_qnan_bits",
                        "CAP-01:root-log-correct-rounding"],
        unspecified=["rootn(-0,2)"],
        ledger_refs=ledger(active=["D17:S1", "D17:S4"]), order=None))

    # 16 ── D15 能力缺口：canonical qNaN 未定 → 不得代填
    out.append(case(
        "f1-foadd-canonical-qnan-blocked", "foadd", "semantic",
        enc("foadd", rfhb=1, rfhc=2, rfhd=3),
        state(rf={"rf1": hx(V.FO_ZERO), "rf2": hx(V.FO_SNAN),
                  "rf3": hx(V.FO_ONE)},
              fcsr=fcsr_exp("RNE", (), value=False, **{"from_reset": True})),
        facets(F_ENC, F_FMT, F_OPS, F_LEG,
               ("semantics", "blocked",
                "%s D1：算术丢弃 payload 与符号返回 canonical qNaN，"
                "但 canonical qNaN 的 64 位常量未给" % C_CONTRACT,
                {"open_ids": ["D15"], "rule": "canonical_qnan_bits = null"}),
               F_RF0, F_FCSR, F_TINY,
               ("nan_propagation", "blocked",
                "%s §7.2；%s D1" % (C_CONTRACT, C_ADR13),
                {"open_ids": ["D15"], "rule": "canonical_qnan_bits = null"})),
        {"kind": "order",
         "records": [{"fcsr": fcsr_exp("RNE", ("NV",), mask=OBS)}]},
        "%s D1（丢弃 payload/符号返回 canonical qNaN；sNaN 输入置 NV）；"
        "resolution.rule_tables.D15.canonical_qnan_bits = null" % C_CONTRACT,
        "foadd rf1,rf2,rf3：**源** rf2 = sNaN（0x7FF0000000000001，指数全 1、"
        "尾数最高位 0）→ 结果是 canonical qNaN 且置 NV（rf3 = 1.0、rf1 = 0 只是"
        "让另一路源保持普通数）。sNaN 必须在**源**上：放进目的寄存器 rf1 是"
        "常见错值来源，期望值与 notes 照样自洽，但真实操作数里根本没有 NaN。"
        "但 ADR-1013 **未给出** canonical qNaN 的 64 位常量"
        "（rule_tables.canonical_qnan_bits = null，下游不得代填）→ 本例只断言 "
        "rf0 的 NV flag，**不断言** rf1 的 64 位结果。若代填 0x7FF8000000000000 "
        "就等于伪造常量，会被 blocked_points 门控拦下",
        expected_state=state(fcsr=fcsr_exp("RNE", ("NV",), mask=OBS)),
        blocked_points=["D15:canonical_qnan_bits"],
        ledger_refs=ledger(active=["D17:S1", "D17:S4"]), order="none"))

    # 17 ── D17:S5 blocked facet（facet 级 blocked + 具名 OPEN-ID）
    out.append(case(
        "f1-fosclb-d17s5-blocked-facet", "fosclb", "legality",
        enc("fosclb", rfhb=1, rfhc=2, rfhd=3),
        state(rf={"rf1": hx(V.FO_ONE), "rf2": hx(V.FO_TWO),
                  "rf3": hx(0x0000000000000003)},
              fcsr=fcsr_exp("RNE", (), value=False, **{"from_reset": True})),
        facets(F_ENC, F_FMT, F_OPS, F_LEG,
               ("semantics", "blocked",
                "%s D6：scaleB 指数 n 由 rf0[17:16] 当前舍入模式把 rfhd "
                "取整后得到" % C_ADR15,
                {"open_ids": ["D17:S5"],
                 "rule": "rfhd 按 rf0[17:16] 舍入成整数 n 后算 rfhc×2^n"}),
               F_RF0, F_FCSR),
        {"kind": "open", "records": []},
        "%s D6（scaleB）；%s §6.2 D17:S5" % (C_ADR15, C_CONTRACT),
        "fosclb rf1,rf2,rf3：orrr 的三个 rf 字段分别是 rfhb[17:12]=目的 rf1、"
        "rfhc[11:6]=被缩放的源 rf2=1.0、**rfhd[5:0]=指数 n 的来源 rf3=3**——"
        "指数在 rfhd，不存在 rf4 这个操作数。fosclb 的 semantics facet 由 "
        "D17:S5 压住 → facet 级 blocked 并指向具名 OPEN-ID `D17:S5`。"
        "本例**只**验证 blocked facet 的表达能力："
        "semantics facet blocked 时用 oracle.kind=open 声明「无唯一 "
        "expected」（expected_state / expected_fault 皆 null、records 为空），"
        "而同一 identity 的 encoding/format/operands/legality/rf0_operand/"
        "fcsr_flags facet 仍可 active 并各自带 cite —— 正是「同一 identity "
        "编码 facet active 而未决语义 facet blocked」",
        expected_fault=None, expected_state=None,
        blocked_points=[],
        ledger_refs=ledger(active=["D17:S1", "D17:S4", "D17:S5"]), order=None))

    # 18 ── ldm 块 element fault → 整条不提交（D17:S8）
    out.append(case(
        "f1-ldm-t-element-fault-no-commit", "ldm.t-rf", "legality",
        enc("ldm.t-rf", rfha=3, rbhb=2, rdhc=1, immu6=2),
        state(rd={"rd1": hx(0x0000000000000010)},
              rb={"rb2": hx(0xFFFF00001002)},
              rf={"rf3": hx32(V.FT_TWO), "rf4": hx32(V.FT_TWO)},
              fcsr=fcsr_exp("RNE", (), value=False, **{"from_reset": True}),
              memory=[mem("0xFFFF00001012", V.FT_ONE, 4),
                      mem("0xFFFF00001016", V.FT_TWO, 4)]),
        facets(F_ENC, F_FMT, F_OPS,
               ("legality", "active", "%s §3.1 aligned(4)" % C_CONTRACT),
               ("semantics", "active",
                "%s D7：任一元素 fault 时整条不提交任何 RF 写或 memory store、"
                "PC 留在 faulting instruction" % C_ADR15),
               F_RF0, F_HI32, F_FCSR),
        {"kind": "block",
         "records": [{"fault": {"type": "MALIGN", "pc": "0xFFFF00000010"}}],
         "elements": [
             {"rf": 3, "address": "0xFFFF00001012", "width": 4,
              "value": hx(V.FT_ONE)},
             {"rf": 4, "address": "0xFFFF00001016", "width": 4,
              "value": hx(V.FT_TWO)}]},
        "%s D7（fault commit = none）" % C_ADR15,
        "ldm.t rf3, rb2, rd1, immu6=2：EA0 = 0xFFFF00001002 + 0x10 = "
        "0xFFFF00001012（% 4 = 2）→ 第 0 个元素不对齐 → MALIGN。D17:S8 规定"
        "整条不提交任何 rf 写（预置的 rf3/rf4 保持 2.0f）、无 memory store、"
        "PC 不前进。oracle 保留 elements（地址仍按 EA0+i*width 给出）但 "
        "records 只有一条 fault 且它是最后一条",
        expected_fault="MALIGN", expected_state=None,
        ledger_refs=ledger(active=["D17:S1", "D17:S4", "D17:S6", "D17:S8"]),
        order="block-increasing"))

    # 19 ── ldm 块「先读后写」用 rd2rf 表达重叠（S7 语义的 rf 侧同构）
    out.append(case(
        "f1-rd2rf-overlap-read-before-write", "rd2rf", "overlap",
        enc("rd2rf", rfhb=2, rdhc=1, immu6=3),
        state(rd={"rd1": hx(0x1111111111111111), "rd2": hx(0x2222222222222222),
                  "rd3": hx(0x3333333333333333)},
              rf={"rf2": hx(0xAAAAAAAAAAAAAAAA), "rf3": hx(0xBBBBBBBBBBBBBBBB),
                  "rf4": hx(0xCCCCCCCCCCCCCCCC)},
              fcsr=fcsr_exp("RNE", (), value=False, **{"from_reset": True})),
        facets(F_ENC, F_FMT, F_OPS, F_LEG,
               ("semantics", "active",
                "%s D1：源/目的范围重叠的读写顺序由规范唯一确定" % C_ADR08),
               F_RF0, F_FCSR),
        {"kind": "unordered", "records": [
            reg_rec("rf", 2, 0x1111111111111111),
            reg_rec("rf", 3, 0x2222222222222222),
            reg_rec("rf", 4, 0x3333333333333333)]},
        "%s D1（D17:S7 spec-determined non-gap）" % C_ADR08,
        "rd2rf rf2, rd1, immu6=3：源 rd1..rd3 写 rf2..rf4，源/目的**重叠**"
        "（rd2/rf3、rd3/rf4）。先读后写语义唯一确定（ADR-1008 D1），"
        "因此重叠处的最终值与读序无关，按 unordered 集合语义观测；"
        "rf2..rf4 都不是 rf0，故 D11 不介入",
        expected_state=state(rd={"rd1": hx(0x1111111111111111),
                                 "rd2": hx(0x2222222222222222),
                                 "rd3": hx(0x3333333333333333)},
                             rf={"rf2": hx(0x1111111111111111),
                                 "rf3": hx(0x2222222222222222),
                                 "rf4": hx(0x3333333333333333)},
                             fcsr=fcsr_exp("RNE", (), mask=OBS)),
        ledger_refs=ledger(active=["D17:S1", "D17:S4"], nongap=["D17:S7"]),
        order="read-before-write"))

    return out


# ═══════════════════════════ 反 样 例 ═══════════════════════════
def _mutate(by_id, cid, note, fn):
    """从正样例派生一条反例：只改一处，并把原因写进 notes。

    ``by_id`` 是 id→case 的索引；每次都从**未改动**的正样例深拷贝，因此任何
    两条反例之间不会互相污染（反例注入可独立复现）。反例 id 用 ``neg-<序号>``
    唯一化——若沿用 ``neg-<正样例 id>``，53 条反例会互相触发 DUPLICATE 报错，
    把「因哪一条规则被拒绝」的真信号淹掉。
    """
    tag = note.split()[0]
    c = copy.deepcopy(by_id[cid])
    c["id"] = "neg-%s-%s" % (tag, cid)
    c["notes"] = "反例 %s：%s" % (note, c["notes"])
    fn(c)
    return c


def invalid_cases(by_id):
    out = []
    A = "f1-foadd-basic-rf-index"

    out.append(_mutate(by_id, A, "N1 bad-rf-index-out-of-range",
                       lambda c: c["input_state"]["rf"].__setitem__(
                           "rf64", hx(V.FO_ONE))))
    out.append(_mutate(by_id, A, "N2 bad-rf-key-syntax",
                       lambda c: c["input_state"]["rf"].__setitem__(
                           "rf1a", hx(V.FO_ONE))))
    out.append(_mutate(by_id, A, "N3 bad-rf-value-not-hex",
                       lambda c: c["input_state"]["rf"].__setitem__(
                           "rf2", "3.0")))
    out.append(_mutate(by_id, "f1-ftdiv-rounding-rtz-dz", "N4 illegal-flag-name",
                       lambda c: c["expected_state"]["fcsr"].__setitem__(
                           "flags", ["DZ", "XX"])))
    out.append(_mutate(by_id, "f1-ftdiv-rounding-rtz-dz", "N5 bad-flag-case",
                       lambda c: c["expected_state"]["fcsr"].__setitem__(
                           "flags", ["Nv"])))
    out.append(_mutate(by_id, "f1-ftdiv-rounding-rtz-dz", "N6 duplicate-flag",
                       lambda c: c["expected_state"]["fcsr"].__setitem__(
                           "flags", ["DZ", "DZ"])))
    out.append(_mutate(by_id, "f1-fosclb-d17s5-blocked-facet",
                       "N7 active-plus-open-id",
                       lambda c: c["facets"]["semantics"].__setitem__(
                           "status", "active")))
    out.append(_mutate(by_id, "f1-fosclb-d17s5-blocked-facet",
                       "N8 blocked-without-open-ids",
                       lambda c: c["facets"]["semantics"].pop("open_ids")))
    out.append(_mutate(by_id, A, "N9 missing-facet-cite",
                       lambda c: c["facets"]["encoding"].__setitem__("cite", "")))
    out.append(_mutate(by_id, A, "N10 missing-spec-cite",
                       lambda c: c.__setitem__("spec_cite", "")))
    out.append(_mutate(by_id, A, "N11 facet-cite-names-no-authority",
                       lambda c: c["facets"]["encoding"].__setitem__(
                           "cite", "see the spec")))
    out.append(_mutate(by_id, A, "N12 unknown-identity",
                       lambda c: (c.__setitem__("identity", "foaddx"),
                                  c.__setitem__("insn", "foaddx"))))
    out.append(_mutate(by_id, A, "N13 identity-insn-mismatch",
                       lambda c: c.__setitem__("insn", "fomul")))
    out.append(_mutate(by_id, "f1-ldt-rf-malign", "N14 fault-and-state-both",
                       lambda c: c.__setitem__("expected_state", state())))
    out.append(_mutate(by_id, "f1-setw-rf0-sbz-mask-d17s6",
                       "N15 rf0-double-expressed",
                       lambda c: c["expected_state"]["rf"].__setitem__(
                           "rf0", hx(V.FCSR_RESET_VALUE))))
    out.append(_mutate(by_id, "f1-setw-rf0-sbz-mask-d17s6",
                       "N16 observed-mask-claims-sbz",
                       lambda c: c["expected_state"]["fcsr"].__setitem__(
                           "observed_mask",
                           hx(V.FCSR_FULL_OBSERVED_MASK | V.FCSR_SBZ_MASK))))
    out.append(_mutate(by_id, "f1-setw-rf0-sbz-mask-d17s6",
                       "N17 observed-mask-misses-rw-domain",
                       lambda c: c["expected_state"]["fcsr"].__setitem__(
                           "observed_mask", hx(0x1F))))
    out.append(_mutate(by_id, "f1-setw-rf0-sbz-mask-d17s6",
                       "N18 fcsr-value-wrong",
                       lambda c: c["expected_state"]["fcsr"].__setitem__(
                           "value", hx(V.fcsr_value(1, 0)))))
    out.append(_mutate(by_id, A, "N19 from-reset-not-rne",
                       lambda c: c["input_state"]["fcsr"].__setitem__(
                           "rounding_mode", "RUP")))
    out.append(_mutate(by_id, "f1-ldt-rf-d17s2-trace-only",
                       "N20 s2-forced-into-active-keys",
                       lambda c: c["ledger_refs"]["active_keys"].append(
                           "D17:S2")))
    out.append(_mutate(by_id, "f1-rf2rd-s7-spec-determined-nongap",
                       "N21 s7-forced-into-active-keys",
                       lambda c: c["ledger_refs"]["active_keys"].append(
                           "D17:S7")))
    out.append(_mutate(by_id, A, "N22 foreign-open-id",
                       lambda c: c["ledger_refs"]["active_keys"].append(
                           "D17:S8")))
    out.append(_mutate(by_id, "f1-ldt-rf-d17s2-trace-only",
                       "N23 s2-forced-into-blocked-facet",
                       lambda c: c["facets"]["legality"].update(
                           {"status": "blocked", "open_ids": ["D17:S2"]})))
    out.append(_mutate(by_id, "f1-ftadd-tetra-high-half-d13", "N24 d13-high-half",
                       lambda c: c["expected_state"]["rf"].__setitem__(
                           "rf1", hx(V.FT_ONE))))
    # N25：foqcmp 的 unordered 位型必须是 quiet 类 0x7FF8000000000000。
    # 注意不能拿 FO_QNAN 当反例——它与 D14_QUIET_UNORDERED 是**同一个**常量，
    # 那样注入是空操作、validator 必然全绿（假反例）。这里用 scmp 的
    # signaling 位型 0x7FF0000000000001，是真正不同的值。
    out.append(_mutate(by_id, "f1-foqcmp-unordered-d14", "N25 d14-wrong-bits",
                       lambda c: c["expected_state"]["rd"].__setitem__(
                           "rd1", hx(V.D14_SIGNAL_UNORDERED))))
    out.append(_mutate(by_id, "f1-foadd-overflow-of-nx-d16", "N26 of-without-nx",
                       lambda c: c["expected_state"]["fcsr"].__setitem__(
                           "flags", ["OF"])))
    out.append(_mutate(by_id, "f1-ldo-rf-d12-non-automatic",
                       "N27 of-outside-d16-scope",
                       lambda c: c["expected_state"]["fcsr"].__setitem__(
                           "flags", ["OF", "NX"])))
    out.append(_mutate(by_id, "f1-ldo-rf-d12-non-automatic",
                       "N28 d12-non-automatic-sets-nv",
                       lambda c: c["expected_state"]["fcsr"].__setitem__(
                           "flags", ["NV"])))
    out.append(_mutate(by_id, "f1-rd2rf-rf0-illi-d11", "N29 d11-wrong-fault",
                       lambda c: c.__setitem__("expected_fault", "MALIGN")))
    out.append(_mutate(by_id, "f1-ftcls-immu6-neq1-illi-priority",
                       "N30 s3-legal-encoding-but-expected-illi",
                       lambda c: c["encoding"].__setitem__("word", "0x44001041")))
    out.append(_mutate(by_id, A, "N31 encoding-wrong-identity",
                       lambda c: c["encoding"].__setitem__("word", "0x44640000")))
    out.append(_mutate(by_id, "f1-ldm-t-block-ea0-increment", "N32 block-ea-wrong",
                       lambda c: c["oracle"]["elements"][1].__setitem__(
                           "address", "0xFFFF00001018")))
    out.append(_mutate(by_id, "f1-ldm-t-block-ea0-increment",
                       "N33 block-rf-not-incrementing",
                       lambda c: c["oracle"]["elements"][1].__setitem__("rf", 5)))
    out.append(_mutate(by_id, "f1-ldm-t-block-ea0-increment",
                       "N34 block-count-vs-immu6",
                       lambda c: c["oracle"]["elements"].pop()))
    out.append(_mutate(by_id, "f1-ldt-rf-d17s2-trace-only", "N35 mem-width-wrong",
                       lambda c: c["input_state"]["memory"][0].__setitem__(
                           "width", 8)))
    out.append(_mutate(by_id, "f1-ldt-rf-malign", "N36 malign-but-aligned",
                       lambda c: (c["input_state"]["rb"].__setitem__(
                           "rb1", hx(0xFFFF00000000)),
                           c["input_state"]["memory"][0].__setitem__(
                               "address", "0xFFFF00000000"))))
    out.append(_mutate(by_id, A, "N37 oracle-disagrees-with-expected-state",
                       lambda c: c["oracle"]["records"][0]["reg"].__setitem__(
                           "value", hx(V.FO_TWO))))
    out.append(_mutate(by_id, "f1-ftadd-tetra-high-half-d13",
                       "N38 half-observation-missing-high32",
                       lambda c: c["oracle"]["records"][0]["reg"].pop("high32")))
    out.append(_mutate(by_id, "f1-foadd-canonical-qnan-blocked",
                       "N39 blocked-point-not-in-vocab",
                       lambda c: c["blocked_points"].append("D99:invented")))
    out.append(_mutate(by_id, "f1-foadd-canonical-qnan-blocked",
                       "N40 fabricated-canonical-qnan",
                       lambda c: c["expected_state"]["rf"].__setitem__(
                           "rf1", hx(V.FO_QNAN))))
    out.append(_mutate(by_id, "f1-foroot-negative-zero-unspecified",
                       "N41 unspecified-gains-unique-expected",
                       lambda c: c.__setitem__(
                           "expected_state",
                           state(rf={"rf1": hx(V.FO_ONE)}))))
    out.append(_mutate(by_id, A, "N42 na-facet-declared",
                       lambda c: c["facets"].__setitem__(
                           "compare_unordered", {"status": "active",
                                                 "cite": "x"})))
    out.append(_mutate(by_id, A, "N43 unknown-oracle-kind",
                       lambda c: c["oracle"].__setitem__("kind", "sorted")))
    out.append(_mutate(by_id, A, "N44 unknown-oracle-key",
                       lambda c: c["oracle"].__setitem__("weights", [1, 2])))
    out.append(_mutate(by_id, "f1-ldm-t-block-ea0-increment",
                       "N45 order-kind-mismatch",
                       lambda c: c["oracle"].__setitem__("kind", "order")))
    out.append(_mutate(by_id, A, "N46 bad-class",
                       lambda c: c.__setitem__("class", "performance")))
    out.append(_mutate(by_id, A, "N47 status-not-active",
                       lambda c: c.__setitem__("status", "deferred")))
    out.append(_mutate(by_id, A, "N48 expected-pc-not-null",
                       lambda c: c.__setitem__("expected_pc",
                                               "0xFFFF00000014")))
    out.append(_mutate(by_id, A, "N49 missing-top-level-field",
                       lambda c: c.pop("ledger_refs")))
    out.append(_mutate(by_id, A, "N50 src-register-not-preset",
                       lambda c: c["input_state"]["rf"].pop("rf2")))
    out.append(_mutate(by_id, "f1-ldt-rf-malign", "N51 fault-record-not-last",
                       lambda c: c["oracle"]["records"].append(
                           {"pc": "0xFFFF00000010"})))
    out.append(_mutate(by_id, "f1-ldt-rf-malign", "N52 fault-commit-not-empty",
                       lambda c: c["oracle"]["records"].insert(
                           0, reg_rec("rf", 1, V.EXP_LDT_RF_LOAD))))
    # N53：input 侧不得断言 value/observed_mask（那是 expected 侧的观测契约）。
    # 注：树级「id 唯一」不变量**不**放进本文件——放了会让
    # `validate_vectors.py` 的默认路径（invalid/ must-FAIL 门控）在健康数据上
    # 报错。它由 `tools/testcases/test_f1_schema_counterexamples.py` 在
    # /tmp 的合成树上单独反例注入。
    out.append(_mutate(by_id, A, "N53 input-fcsr-value-asserted",
                       lambda c: c["input_state"]["fcsr"].__setitem__(
                           "value", hx(V.FCSR_RESET_VALUE))))

    return out


# ═══════════════════════════ 序列化 ═══════════════════════════
def to_yaml(cases):
    import yaml

    class Dumper(yaml.SafeDumper):
        pass

    def _str(dumper, data):
        if isinstance(data, str) and "\n" in data:
            return dumper.represent_scalar("tag:yaml.org,2002:str", data,
                                           style="|")
        return dumper.represent_scalar("tag:yaml.org,2002:str", data)

    Dumper.add_representer(str, _str)
    Dumper.add_representer(
        type(None),
        lambda d, _: d.represent_scalar("tag:yaml.org,2002:null", "null"))
    return yaml.dump(cases, Dumper=Dumper, allow_unicode=True,
                     sort_keys=False, default_flow_style=False, width=100)


HEADER = """# %s — %s
# 本文件由 tools/testcases/generate_f1_schema_fixtures.py 生成，请勿手改。
# 期望值来源：tools/testcases/f1_oracle_values.py 的**整数位型**独立推导
# （不调用 LLVM / QEMU / SoftFloat / 宿主 float / libm）。
# 指令字由 enc() 按 contracts/opcodes.yaml 的字段位号自动组装。
"""


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args(argv)
    valid = valid_cases()
    by_id = {c["id"]: c for c in valid}
    invalid = invalid_cases(by_id)
    for rel, cases, kind in (
            ("valid/f1-schema-valid.yaml", valid,
             "F1 最小正样例（validate_vectors.py 必须全绿）"),
            ("invalid/f1-schema-invalid.yaml", invalid,
             "F1 最小反样例（**刻意坏数据**；validator 必须逐条拒绝）")):
        path = os.path.join(args.out, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(HEADER % (rel, kind))
            fh.write(to_yaml(cases))
        print("wrote %s (%d cases)" % (path, len(cases)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
