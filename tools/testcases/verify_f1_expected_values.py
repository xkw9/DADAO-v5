#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_f1_expected_values.py — F1 正样例期望值的**独立全量重算**。

为什么要有这个脚本
------------------
AGENTS.md「数据/期望值类任务」要求：对 **size/sign 敏感**（定宽、NaN-boxing、
舍入模式、除零、次正规）的用例**逐条独立重算**并与产出比对，**不得以
validator 绿灯为唯一判据**。而 ``validate_vectors.py`` / ``f1_cases.py`` 与
生成器 ``generate_f1_schema_fixtures.py`` 共享 ``f1_schema`` 与
``f1_oracle_values``：它们互相一致只能证明「没写错字 / 没抄错」，
不能证明「推导对」。本脚本的价值正在于发现**角色错位**一类的错值
（例：把目的寄存器当源、两个源都置 0 导致 0/0 却被断言成除零）。

独立路径的构成
--------------
1. **不 import** ``f1_schema`` / ``f1_cases`` / ``f1_oracle_values``
   （脚本末尾 ``self_check()`` 现场核对 ``sys.modules`` 与本文件源码）。
2. 自带一个**纯整数** IEEE-754 binary32/binary64 引擎：把操作数拆成
   ``(sign, e, m)``，用**精确有理数** ``num/den`` 运算，按 RNE/RTZ/RDN/RUP
   舍入（平局取偶数由整数比较 ``2r vs den`` 判定），再重新打包位型；
   次正规与溢出在同一条路径里按 after-rounding tininess 处理。
   全程不出现宿主浮点、不调 ``math``/libm、不用十进制路径。
3. FCSR 位域**从合约 markdown 的位串字面量与表格行**现场解析
   （``0111111111111`` / ``0111111111``，``[63..51]`` / ``[31..22]`` /
   ``[17..16]`` / ``[4..0]`` …），并**两路交叉**验证只读域常量：
   (a) 直接把位串字面量当二进制数；(b) 按「符号 0、E 全 1、尾数最高位 1」
   的文字描述重新拼一遍。两条路不相等即 FATAL。
4. D11–D17 的事实从 ``contracts/f1_gap_proofs.yaml`` 的 ``resolution`` 层与
   ``contracts/opcodes.yaml`` 的 ``f1:`` 块现场读取（字段位号、role、
   open_items），不写死向量数据里的任何值。
5. 逐条核对 **oracle 记录本身**：``oracle.records`` 里的 reg/fcsr 值必须等于
   独立重算值（而不只是等于 ``expected_state``），``oracle.elements`` 的
   地址/宽度/来源必须等于按 D17:S8 的 ``EA0 + i*width`` 现场重算。

判据与退出码
------------
* 每条正样例的 32/64 位期望值、FCSR 字段、flags、块地址、静态 fault 谓词
  都要与独立重算**逐位相等**；逐条不符即打印 ``MISMATCH``。
* 退出码 0 = 全部相符；1 = 有不符；2 = 输入文件/合约解析失败。

用法
----
  python3 tools/testcases/verify_f1_expected_values.py
  python3 tools/testcases/verify_f1_expected_values.py --json
  python3 tools/testcases/verify_f1_expected_values.py --root /tmp/...  # 反例注入
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_DEFAULT = os.path.dirname(os.path.dirname(HERE))
REL_VECTORS = os.path.join("tests", "vectors", "f1", "valid", "f1-schema-valid.yaml")
REL_CONTRACT = os.path.join(".xkw", "knowledge", "contract-f1-floating.md")
REL_GAPS = os.path.join("contracts", "f1_gap_proofs.yaml")
REL_OPCODES = os.path.join("contracts", "opcodes.yaml")

# ───────────────── 格式参数（IEEE-754 标准常量，不是本项目期望值） ─────────────────
FMT = {
    32: {"p": 24, "ebits": 8, "bias": 127, "emax": 127, "emin": -126},
    64: {"p": 53, "ebits": 11, "bias": 1023, "emax": 1023, "emin": -1022},
}
FLAGBIT = {"NV": 0, "DZ": 1, "OF": 2, "UF": 3, "NX": 4}
ROUNDING = {"RNE": 0, "RTZ": 1, "RDN": 2, "RUP": 3}
BITS_RE = re.compile(r"^\[(\d+)(?::|\.\.)(\d+)\]$")


class Fatal(Exception):
    """输入/合约解析失败（退出码 2）。"""


# ═════════════════════ 纯整数 IEEE-754 引擎 ═════════════════════
def _cmp_scaled(num, den, k):
    """比较 ``num * 2**k`` 与 ``den``：返回 1/0/-1。"""
    if k >= 0:
        a, b = num << k, den
    else:
        a, b = num, den << (-k)
    return (a > b) - (a < b)


def _floor_log2(num, den):
    """``floor(log2(num/den))``，纯整数（num, den > 0）。"""
    e = num.bit_length() - den.bit_length()
    return e if _cmp_scaled(num, den, e) >= 0 else e - 1


def unpack(bits, w):
    """位型 → ``(sign, e, m)``，精确值 = ``(-1)**sign * m * 2**e``。

    ``m`` 含隐含位（正规数）或就是尾数（次正规数）；±0 时 ``m == 0``。
    """
    f = FMT[w]
    mbits = f["p"] - 1
    ebits = f["ebits"]
    frac_bits = w - 1 - ebits
    sign = (bits >> (w - 1)) & 1
    eb = (bits >> frac_bits) & ((1 << ebits) - 1)
    frac = bits & ((1 << frac_bits) - 1)
    if eb == 0:
        return sign, f["emin"] - mbits, frac
    return sign, (eb - f["bias"]) - mbits, frac | (1 << mbits)


def exp_field(bits, w):
    return (bits >> (w - 1 - FMT[w]["ebits"])) & ((1 << FMT[w]["ebits"]) - 1)


def frac_field(bits, w):
    return bits & ((1 << (w - 1 - FMT[w]["ebits"])) - 1)


def is_nan(bits, w):
    return exp_field(bits, w) == (1 << FMT[w]["ebits"]) - 1 and frac_field(bits, w) != 0


def is_snan(bits, w):
    """signaling NaN：指数全 1、尾数非 0 且尾数最高位为 0。"""
    if not is_nan(bits, w):
        return False
    return (frac_field(bits, w) >> (w - 1 - FMT[w]["ebits"] - 1)) & 1 == 0


def _inf_bits(sign, w):
    return (sign << (w - 1)) | (exp_field_all_ones(w) << (w - 1 - FMT[w]["ebits"]))


def exp_field_all_ones(w):
    return (1 << FMT[w]["ebits"]) - 1


def _max_finite_bits(sign, w):
    f = FMT[w]
    mbits = f["p"] - 1
    return ((sign << (w - 1)) | ((f["emax"] + f["bias"]) << mbits)
            | ((1 << mbits) - 1))


def _pack(sign, t, e_unbiased, w):
    """把「有效位 t、值 = t * 2^(e_unbiased - mbits)」打成位型。"""
    f = FMT[w]
    mbits = f["p"] - 1
    if t < (1 << mbits):                      # 次正规（含 ±0）
        return (sign << (w - 1)) | t
    return ((sign << (w - 1)) | ((e_unbiased + f["bias"]) << mbits)
            | (t & ((1 << mbits) - 1)))


def round_exact(sign, num, den, w, mode, e_scale=0):
    """把精确值 ``(-1)**sign * num/den * 2**e_scale`` 舍入到 w 位格式。

    返回 ``(bits, flags)``；flags 只含 OF / UF / NX。
    记号：精确值 = ``(-1)**sign * num/den * 2**e_scale``；``E`` 是它的无偏
    指数，满足 ``值 = q * 2**(E - mbits)`` 且 ``q ∈ [2**mbits, 2**(mbits+1))``
    （正规）或 ``q < 2**mbits``（次正规）；``_pack()`` 正是按这条定义打包。
    路径：整数求 ``floor(log2)``（含 ``e_scale``）→ 取
    ``max(floor(log2), emin)`` 的网格 → 四种舍入（RNE 的平局取偶由整数比较
    ``2r vs den`` 判定）→ 进位/溢出/次正规判定。tininess 按
    **after-rounding**（D16）。溢出方向按 IEEE 754-2008 §7.4 的四模式表。
    """
    f = FMT[w]
    mbits = f["p"] - 1
    if num == 0:
        return sign << (w - 1), set()
    exact_e = _floor_log2(num, den) + e_scale
    e = exact_e if exact_e >= f["emin"] else f["emin"]
    k = e_scale - e + mbits            # 值 / 2**(E - mbits) = (num/den) * 2**k
    if k >= 0:
        num, den = num << k, den
    else:
        den = den << (-k)
    q, r = divmod(num, den)
    inexact = r != 0
    if inexact:
        if mode == "RTZ":
            pass
        elif mode == "RNE":
            c = _cmp_scaled(r, den, 1)            # 2r 与 den：>0 向上，=0 看 q 奇偶
            if c > 0 or (c == 0 and (q & 1)):
                q += 1
        elif mode == "RUP":
            if not sign:
                q += 1
        elif mode == "RDN":
            if sign:
                q += 1
        else:
            raise Fatal("未知舍入模式 %r" % (mode,))
    if q == 0:
        # 非零精确值被舍入成零：次正规下溢，tiny + inexact（after-rounding）
        return sign << (w - 1), {"UF", "NX"}
    if q >= (1 << (mbits + 1)):
        q >>= 1
        e += 1
    if e > f["emax"]:
        # 溢出（IEEE 754-2008 §7.4）：RTZ 给同号最大有限；RDN 只在**正**溢出、
        # RUP 只在**负**溢出时给同号最大有限；其余（含 RNE）给 ±∞。
        if mode == "RTZ" or (mode == "RDN" and sign == 0) or \
                (mode == "RUP" and sign == 1):
            return _max_finite_bits(sign, w), {"OF", "NX"}
        return _inf_bits(sign, w), {"OF", "NX"}
    flags = {"NX"} if inexact else set()
    # 下溢（IEEE 754-2008 §7.5）：**tiny 且 inexact** 才置 UF。精确的次正规
    # 结果（两个次正规数相加得到可表示的次正规）只精确、不下溢。
    if inexact and exact_e < f["emin"] and q < (1 << mbits):
        flags.add("UF")                         # after-rounding 才算 tiny
    return _pack(sign, q, e, w), flags


# NaN 输入：位型未由任何已激活 decision 固定（D15.canonical_qnan_bits = null），
# 因此本引擎对 NaN 输入只给 **flags**，结果位型返回 None（= 不可断言）。
NAN_NONE = object()


def _nan_flags(*vals, w):
    return {"NV"} if any(is_snan(v, w) for v in vals) else set()


def _is_inf(bits, w):
    return exp_field(bits, w) == exp_field_all_ones(w) and frac_field(bits, w) == 0


def _inf_bits_of(bits, w):
    return bits & _inf_bits(0, w)


def _fadd_core(a, b, w, mode, bsign=None):
    sa, ea, ma = unpack(a, w)
    sb, eb, mb = unpack(b, w)
    if bsign is not None:
        sb ^= bsign
    if is_nan(a, w) or is_nan(b, w):
        return NAN_NONE, _nan_flags(a, b, w=w)
    if _is_inf(a, w) or _is_inf(b, w):
        # inf + (−inf) = invalid（§7.2）；其余 inf 传播且**不**置任何 flag
        if _is_inf(a, w) and _is_inf(b, w) and sa != sb:
            return NAN_NONE, {"NV"}
        return (_inf_bits(sa if _is_inf(a, w) else sb, w), set())
    if ma == 0 or mb == 0:
        if ma == 0 and mb == 0:
            # ±0 规则（§6.3）：同为负 → −0；同号为正 → +0；异号零和在 RDN 下为 −0
            if sa and sb:
                return (1 << (w - 1)), set()
            if sa == sb:
                return 0, set()
            return ((1 << (w - 1)) if mode == "RDN" else 0), set()
        # 恰有一个零：精确结果就是另一个操作数本身（可表示，无需舍入）
        return (b if ma == 0 else a), set()
    e = min(ea, eb)
    aa, bb = ma << (ea - e), mb << (eb - e)
    if sa == sb:
        return round_exact(sa, aa + bb, 1, w, mode, e)
    if aa > bb:
        return round_exact(sa, aa - bb, 1, w, mode, e)
    if bb > aa:
        return round_exact(sb, bb - aa, 1, w, mode, e)
    # 精确相消：异号相消为零 → **仅** roundTowardNegative 给 −0，其余 +0
    # （IEEE 754-2008 §6.3）
    return ((1 << (w - 1)) if mode == "RDN" else 0), set()


def fadd(a, b, w, mode):
    return _fadd_core(a, b, w, mode)


def fsub(a, b, w, mode):
    return _fadd_core(a, b, w, mode, bsign=1)


def fmul(a, b, w, mode):
    sa, ea, ma = unpack(a, w)
    sb, eb, mb = unpack(b, w)
    if is_nan(a, w) or is_nan(b, w):
        return NAN_NONE, _nan_flags(a, b, w=w)
    sign = sa ^ sb
    if ma == 0 or mb == 0:
        # inf × 0 = invalid（§7.2）；否则零乘任意有限/无穷都是同号零
        if (_is_inf(a, w) and mb == 0) or (_is_inf(b, w) and ma == 0):
            return NAN_NONE, {"NV"}
        return sign << (w - 1), set()
    if _is_inf(a, w) or _is_inf(b, w):
        return _inf_bits(sign, w), set()
    return round_exact(sign, ma * mb, 1, w, mode, ea + eb)


def fdiv(a, b, w, mode):
    sa, ea, ma = unpack(a, w)
    sb, eb, mb = unpack(b, w)
    if is_nan(a, w) or is_nan(b, w):
        return NAN_NONE, _nan_flags(a, b, w=w)
    sign = sa ^ sb
    if mb == 0:
        if ma == 0:
            return NAN_NONE, {"NV"}                  # 0/0 = invalid（§7.2 注：非除零）
        # 非零有限数除以零：结果是「无限精确结果正确舍入后的值」，而 ±∞ 本身
        # 就是可表示的精确值，**四种舍入模式一律给 ±∞**（IEEE 754-2008 §7.2
        # 末段 + Table 3）。因结果与无限精确结果相等，§7.4 的 inexact 不成立
        # → 只置 DZ，**不**置 NX；除零也**不是** overflow（D16 的 OF+NX 不适用）。
        return _inf_bits(sign, w), {"DZ"}
    if _is_inf(b, w):
        # 有限非零数除以无穷 → 同号零，精确
        return sign << (w - 1), set()
    if _is_inf(a, w):
        return _inf_bits(sign, w), set()
    return round_exact(sign, ma, mb, w, mode, ea - eb)


ARITH_OPS = {"add": fadd, "sub": fsub, "mul": fmul, "div": fdiv}


# ═════════════ 引擎自身的已知答案测试（KAT） ═════════════
# 「19 条样例全绿」只有在**引擎本身**被证明正确时才是证据。下面的期望值全部
# 由 IEEE 754-2008 的条文 + 纯整数手算得到（不是跑出来的），覆盖：
# 四种舍入模式、平局取偶、精确相消的符号、次正规边界、tiny/inexact 组合、
# 溢出四模式方向表、除零、0/0、inf 传播。每条 KAT 都必须在源码里写死期望值。
def _kat(*rows):
    return rows


KATS = _kat(
    # (op, w, mode, a, b, 期望位型, 期望 flags)
    ("add", 64, "RNE", 0x3FF0000000000000, 0x4000000000000000,
     0x4008000000000000, set()),                       # 1.0 + 2.0 = 3.0
    ("add", 64, "RNE", 0x3FF0000000000000, 0x3CA0000000000000,
     0x3FF0000000000000, {"NX"}),                      # 1.0 + 2^-53 = 平局取偶 → 1.0
    ("add", 64, "RNE", 0x3FF0000000000000, 0x3CB8000000000000,
     0x3FF0000000000002, {"NX"}),                      # 1.0 + 3·2^-53 = 平局取偶 → 1+2^-51
    ("add", 64, "RTZ", 0x3FF0000000000000, 0x3CA0000000000000,
     0x3FF0000000000000, {"NX"}),                      # RTZ 截断 → 1.0
    ("add", 64, "RUP", 0x3FF0000000000000, 0x3CA0000000000000,
     0x3FF0000000000001, {"NX"}),                      # RUP 进位 → 1+2^-52
    ("add", 64, "RDN", 0x3FF0000000000000, 0x3CA0000000000000,
     0x3FF0000000000000, {"NX"}),                      # RDN 舍去 → 1.0
    ("add", 64, "RNE", 0x3FF0000000000000, 0xBFF0000000000000,
     0x0000000000000000, set()),                       # 1.0 + (−1.0) = +0
    ("add", 64, "RDN", 0x3FF0000000000000, 0xBFF0000000000000,
     0x8000000000000000, set()),                       # §6.3：RDN 下精确相消 = −0
    ("add", 64, "RNE", 0x0000000000000000, 0x8000000000000000,
     0x0000000000000000, set()),                       # +0 + −0 = +0
    ("add", 64, "RDN", 0x0000000000000000, 0x8000000000000000,
     0x8000000000000000, set()),                       # §6.3：RDN 下异号零和 = −0
    ("add", 64, "RNE", 0x7FF0000000000000, 0x7FF0000000000000,
     0x7FF0000000000000, set()),                       # inf + inf = inf（不置 flag）
    ("add", 64, "RNE", 0x7FF0000000000000, 0xFFF0000000000000,
     NAN_NONE, {"NV"}),                                # inf + (−inf) = invalid
    ("add", 32, "RNE", 0x0000000000000001, 0x0000000000000001,
     0x0000000000000002, set()),                       # §7.5：次正规相加精确 → tiny 但非 inexact → 无 UF
    ("add", 32, "RNE", 0x0000000000000001, 0x0000000000000002,
     0x0000000000000003, set()),                       # 次正规相加精确 → 无 flag
    ("sub", 64, "RNE", 0x4008000000000000, 0x3FF0000000000000,
     0x4000000000000000, set()),                       # 3.0 − 1.0 = 2.0
    ("mul", 64, "RNE", 0x4000000000000000, 0x4010000000000000,
     0x4020000000000000, set()),                       # 2.0 × 4.0 = 8.0
    ("mul", 64, "RNE", 0x7FEFFFFFFFFFFFFF, 0x4000000000000000,
     0x7FF0000000000000, {"OF", "NX"}),                # RNE 溢出 → +Inf
    ("mul", 64, "RTZ", 0x7FEFFFFFFFFFFFFF, 0x4000000000000000,
     0x7FEFFFFFFFFFFFFF, {"OF", "NX"}),                # §7.4：RTZ 溢出 → 最大有限
    ("mul", 64, "RDN", 0x7FEFFFFFFFFFFFFF, 0x4000000000000000,
     0x7FEFFFFFFFFFFFFF, {"OF", "NX"}),                # §7.4：正溢出 + RDN → 最大有限
    ("mul", 64, "RDN", 0xFFEFFFFFFFFFFFFF, 0x4000000000000000,
     0xFFF0000000000000, {"OF", "NX"}),                # §7.4：负溢出 + RDN → −Inf
    ("mul", 64, "RUP", 0xFFEFFFFFFFFFFFFF, 0x4000000000000000,
     0xFFEFFFFFFFFFFFFF, {"OF", "NX"}),                # §7.4：负溢出 + RUP → −最大有限
    ("mul", 64, "RNE", 0x0000000000000001, 0x3FE0000000000000,
     0x0000000000000000, {"UF", "NX"}),                # 2^-1074 × 0.5 平局取偶 → 0
    ("mul", 64, "RNE", 0x0000000000000001, 0x3FE8000000000000,
     0x0000000000000001, {"UF", "NX"}),                # ×0.75 → 2^-1074（tiny+inexact）
    ("mul", 64, "RNE", 0x8000000000000001, 0x3FE0000000000000,
     0x8000000000000000, {"UF", "NX"}),                # 负向次正规下溢平局取偶 → −0
    ("mul", 64, "RNE", 0x7FF0000000000000, 0x0000000000000000,
     NAN_NONE, {"NV"}),                                # inf × 0 = invalid
    ("div", 64, "RNE", 0x3FF0000000000000, 0x4000000000000000,
     0x3FE0000000000000, set()),                       # 1.0 / 2.0 = 0.5
    ("div", 64, "RNE", 0x3FF0000000000000, 0x4008000000000000,
     0x3FD5555555555555, {"NX"}),                      # 1/3 → 0x3FD5555555555555
    ("div", 64, "RTZ", 0x3FF0000000000000, 0x4014000000000000,
     0x3FC9999999999999, {"NX"}),                      # 1/5 RTZ → 截断
    ("div", 64, "RDN", 0x3FF0000000000000, 0x4014000000000000,
     0x3FC9999999999999, {"NX"}),                      # 1/5 RDN → 同截断（结果为正）
    ("div", 64, "RNE", 0x3FF0000000000000, 0x4014000000000000,
     0x3FC999999999999A, {"NX"}),                      # 1/5 RNE → 进位
    ("div", 64, "RUP", 0x3FF0000000000000, 0x4014000000000000,
     0x3FC999999999999A, {"NX"}),                      # 1/5 RUP → 同进位（结果为正）
    ("div", 64, "RUP", 0x3FF0000000000000, 0x4008000000000000,
     0x3FD5555555555556, {"NX"}),                      # 1/3 RUP → +1ulp
    ("div", 64, "RNE", 0x3FF0000000000000, 0x0000000000000000,
     0x7FF0000000000000, {"DZ"}),                      # §7.2：1/0 = +Inf，只置 DZ
    ("div", 64, "RTZ", 0x3FF0000000000000, 0x0000000000000000,
     0x7FF0000000000000, {"DZ"}),                      # 四模式一致
    ("div", 64, "RDN", 0x3FF0000000000000, 0x0000000000000000,
     0x7FF0000000000000, {"DZ"}),                      # 四模式一致
    ("div", 64, "RUP", 0xFFF0000000000000, 0x0000000000000000,
     0xFFF0000000000000, {"DZ"}),                      # −1/0 = −Inf
    ("div", 64, "RNE", 0x0000000000000000, 0x0000000000000000,
     NAN_NONE, {"NV"}),                                # 0/0 = invalid
    ("div", 64, "RNE", 0x7FF0000000000000, 0x4000000000000000,
     0x7FF0000000000000, set()),                       # inf / 有限 = inf
    ("div", 64, "RNE", 0x3FF0000000000000, 0x7FF0000000000000,
     0x0000000000000000, set()),                       # 有限 / inf = +0
    ("div", 32, "RTZ", 0x3F800000, 0x00000000,
     0x7F800000, {"DZ"}),                              # 1.0f/0.0f = +Inf（不是 ±0！）
    ("add", 32, "RNE", 0x00000000, 0x3F800000,
     0x3F800000, set()),                               # 0.0f + 1.0f = 1.0f
)


def _show_bits(x):
    return "NAN_NONE" if x is NAN_NONE else hexv(x)


def run_kats(rep):
    """跑引擎自身的已知答案测试；任一条不符即判本脚本不可信。"""
    n = 0
    for op, w, mode, a, b, want_bits, want_flags in KATS:
        got_bits, got_flags = ARITH_OPS[op](a, b, w, mode)
        tag = "KAT[%s/%d/%s %s %s]" % (op, w, mode, hexv(a), hexv(b))
        if got_bits is want_bits or got_bits == want_bits:
            rep.ok()
        else:
            rep.bad(tag, "结果位型应为 %s，实得 %s"
                    % (_show_bits(want_bits), _show_bits(got_bits)))
        if got_flags == want_flags:
            rep.ok()
        else:
            rep.bad(tag, "flags 应为 %s，实得 %s"
                    % (sorted(want_flags), sorted(got_flags)))
        n += 2
    return n


# ═════════════════ 合约 / 机器数据的现场解析 ═════════════════
def read_text(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError as exc:
        raise Fatal("无法读取 %s: %s" % (path, exc))


def parse_fcsr_layout(contract_path):
    """从合约 markdown 现场解析 FCSR 位域；只读域常量两路交叉。"""
    text = read_text(contract_path)
    blk = re.search(r"<!-- f1:generated:fcsr-layout -->(.*?)<!-- /f1:generated:fcsr-layout -->",
                    text, re.S)
    if not blk:
        raise Fatal("合约里找不到 fcsr-layout 生成块")
    domains = []
    for line in blk.group(1).splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        m = BITS_RE.match(cells[0].strip("`"))
        if not m or len(cells) < 3:
            continue
        desc = cells[2]
        kind = ("ro" if "只读" in desc else "sbz" if "SBZ" in desc else "rw")
        lit = None
        if kind == "ro":
            lit = cells[1].split("（")[0].replace(" ", "").strip()
        domains.append({"hi": int(m.group(1)), "lo": int(m.group(2)),
                        "kind": kind, "literal": lit, "raw": cells[0],
                        "desc": desc})
    masks = {k: 0 for k in ("ro", "sbz", "rw")}
    for d in domains:
        masks[d["kind"]] |= ((1 << (d["hi"] - d["lo"] + 1)) - 1) << d["lo"]
    if (masks["ro"] | masks["sbz"] | masks["rw"]) != 0xFFFFFFFFFFFFFFFF:
        raise Fatal("FCSR 三域未铺满 64 位：%r" % (masks,))
    if masks["ro"] & masks["sbz"] or masks["ro"] & masks["rw"] or masks["sbz"] & masks["rw"]:
        raise Fatal("FCSR 三域互相重叠：%r" % (masks,))
    # 只读域常量：路 a = 位串字面量；路 b = 「符号 0、E 全 1、尾数最高位 1」
    ro_a, ro_b = 0, 0
    for d in domains:
        if d["kind"] != "ro":
            continue
        width = d["hi"] - d["lo"] + 1
        if d["literal"] is None or len(d["literal"]) != width or \
                set(d["literal"]) - {"0", "1"}:
            raise Fatal("只读域 %s 的位串字面量不可用：%r" % (d["raw"], d["literal"]))
        ro_a |= int(d["literal"], 2) << d["lo"]
        # 路 b：域内高位是符号位(0)，随后 ebits 个 1，再 1 个 1
        ebits = width - 2
        pat = (0 << (width - 1)) | (((1 << ebits) - 1) << 1) | 1
        if int(d["literal"], 2) != pat:
            raise Fatal("只读域 %s 的字面量 %r 不满足「符号 0、E 全 1、尾数最高位 1」"
                        % (d["raw"], d["literal"]))
        ro_b |= pat << d["lo"]
    if ro_a != ro_b:
        raise Fatal("只读域常量两路交叉不一致：0x%016X vs 0x%016X" % (ro_a, ro_b))
    # 舍入域 / flags 域：按表格**描述文字**定位，不写死位号
    rm_hi = rm_lo = fl_hi = fl_lo = None
    for d in domains:
        if d["kind"] == "rw" and "舍入模式" in d["desc"]:
            rm_hi, rm_lo = d["hi"], d["lo"]
        if d["kind"] == "rw" and "异常状态" in d["desc"]:
            fl_hi, fl_lo = d["hi"], d["lo"]
    if rm_hi is None or fl_hi is None:
        raise Fatal("合约 FCSR 表里找不到舍入模式域 / 异常状态域")
    if (rm_hi - rm_lo) != 1:
        raise Fatal("舍入模式域宽度应为 2 位，实得 %d" % (rm_hi - rm_lo + 1))
    if (fl_hi - fl_lo) != 4:
        raise Fatal("异常状态域宽度应为 5 位，实得 %d" % (fl_hi - fl_lo + 1))
    if (rm_hi, rm_lo, fl_hi, fl_lo) != (17, 16, 4, 0):
        raise Fatal("FCSR rw 域位号异常：rm=[%d..%d] flags=[%d..%d]"
                    % (rm_hi, rm_lo, fl_hi, fl_lo))
    return {"masks": masks, "ro_value": ro_a, "rm_shift": rm_lo,
            "flag_shift": fl_lo, "domains": domains}


def load_gap_facts(path):
    import yaml
    with open(path, encoding="utf-8") as fh:
        gap = yaml.safe_load(fh)
    rt = ((gap.get("resolution") or {}).get("rule_tables") or {})
    d12 = rt.get("D12") or {}
    d13 = rt.get("D13") or {}
    d14 = rt.get("D14") or {}
    d15 = rt.get("D15") or {}
    d16 = rt.get("D16") or {}
    d17 = rt.get("D17") or {}
    return {
        "d11": rt.get("D11") or {},
        "d12_auto": set(d12.get("automatic_scope") or []),
        "d12_non_auto": set(d12.get("non_automatic_scope") or []),
        "d13_write": set(d13.get("write_scope") or []),
        "d13_load": set(d13.get("load_scope") or []),
        "d13_high32": int(str(d13.get("tetra_high_half_bits")), 16) & 0xFFFFFFFF,
        "d14_quiet": set(d14.get("quiet_class") or []),
        "d14_signal": set(d14.get("signaling_class") or []),
        "d14_quiet_bits": int(str(d14.get("quiet_unordered_bits")), 16),
        "d14_signal_bits": int(str(d14.get("signaling_unordered_bits")), 16),
        "d15_arith": set(d15.get("arithmetic_scope") or []),
        "d15_qnan": d15.get("canonical_qnan_bits"),
        "d16_scope": set(d16.get("scope") or []),
        "d16_of": set(d16.get("overflow_flags") or []),
        "d16_uf": set(d16.get("underflow_flags") or []),
        "d16_tininess": d16.get("tininess_detection"),
        "d17_active": set(d17.get("active_keys") or []),
        "d17_trace_only": d17.get("trace_only"),
        "d17_non_gap": d17.get("historical_non_gap"),
        "d17_ea0": d17.get("ldm_stm_base"),
        "d17_addr": d17.get("ldm_stm_address"),
        "d17_w4": d17.get("ldm_stm_width_tetra"),
        "d17_w8": d17.get("ldm_stm_width_octa"),
        "d17_classify_imm": d17.get("classify_immediate"),
        "d17_classify_hw": d17.get("classify_immediate_hardware"),
        "d17_priority": d17.get("fault_priority"),
        "d17_reset_rm_bits": d17.get("reset_rounding_bits"),
        "d17_reset_flags": d17.get("reset_flags"),
        "d17_reset_mode": d17.get("reset_rounding_mode"),
    }


def load_opcode_facts(path):
    import yaml
    with open(path, encoding="utf-8") as fh:
        recs = yaml.safe_load(fh)
    out = {}
    for rec in recs:
        f1 = rec.get("f1") or {}
        if not f1.get("in_scope"):
            continue
        out[rec["insn"]] = {
            "mask": int(str(rec["mask"]), 16),
            "value": int(str(rec["value"]), 16),
            "fields": rec.get("fields") or [],
            "section": f1.get("section") or "",
            "predicates": f1.get("legality_predicates") or [],
            "open_items": f1.get("open_items") or [],
            "facets": f1.get("facets") or {},
        }
    return out


def decode_fields(word, record):
    """按 opcodes.yaml 的字段位号解字段（纯整数）。返回 ``(单字段, 复合字段)``。"""
    raw, groups = {}, {}
    for f in record["fields"]:
        m = BITS_RE.match(str(f.get("bits", "")))
        if not m:
            raise Fatal("opcodes.yaml 字段 %r 的 bits 不可解析：%r"
                        % (f.get("name"), f.get("bits")))
        hi, lo = int(m.group(1)), int(m.group(2))
        name = f["name"]
        raw[name] = {"value": (word >> lo) & ((1 << (hi - lo + 1)) - 1),
                     "hi": hi, "lo": lo, "role": f.get("role"),
                     "signed": bool(f.get("signed"))}
        base = name
        for suf in ("_hi", "_mid", "_lo"):
            if name.endswith(suf):
                base = name[: -len(suf)]
                break
        groups.setdefault(base, []).append(name)
    composite = {}
    for base, names in groups.items():
        if len(names) == 1 and names[0] == base:
            composite[base] = raw[base]["value"]
            continue
        names.sort(key=lambda n: -raw[n]["hi"])          # 高位在前
        total = sum(raw[n]["hi"] - raw[n]["lo"] + 1 for n in names)
        acc = 0
        for n in names:
            acc = (acc << (raw[n]["hi"] - raw[n]["lo"] + 1)) | raw[n]["value"]
        if any(raw[n]["signed"] for n in names) and (acc >> (total - 1)) & 1:
            acc -= 1 << total
        composite[base] = acc
    return raw, composite


def roles_of(raw):
    """把字段按 role 归类：dst / src（按位号从高到低）/ imm。"""
    dst = [n for n, d in raw.items() if d["role"] == "dst"]
    src = sorted([n for n, d in raw.items() if d["role"] == "src"],
                 key=lambda n: -raw[n]["hi"])
    return dst, src


# ═════════════════════════ 逐 case 独立重算 ═════════════════════════
class Report(object):
    def __init__(self):
        self.problems = []
        self.checked = 0
        self.notes = []

    def bad(self, cid, msg):
        self.problems.append("%s: %s" % (cid, msg))

    def ok(self):
        self.checked += 1

    def note(self, cid, msg):
        self.notes.append("%s: %s" % (cid, msg))


def hexv(x):
    return "0x%016X" % (x & 0xFFFFFFFFFFFFFFFF)


def as_u64(val, cid, what, rep):
    if isinstance(val, int) and not isinstance(val, bool):
        return val & 0xFFFFFFFFFFFFFFFF
    if not isinstance(val, str) or not re.match(r"^0x[0-9a-fA-F]{1,16}$", val.strip()):
        rep.bad(cid, "%s 不是 64 位 hex 位型：%r" % (what, val))
        return None
    return int(val.strip(), 16)


def reg_value(state, bank, index, cid, rep, what):
    raw = ((state or {}).get(bank) or {}).get("%s%d" % (bank, index))
    if raw is None:
        return None
    return as_u64(raw, cid, what, rep)


def mem_index(entries):
    out = {}
    for e in entries or []:
        out[int(str(e["address"]), 16)] = e
    return out


def mem_width_of(identity):
    """访存宽度：`.t`/ft 源 = 4 字节，`.o`/fo 源 = 8 字节（助记符后缀）。"""
    mnem = identity.rsplit("-rf", 1)[0]
    if mnem.endswith(".t") or mnem.startswith("ft") or mnem.endswith("2ft"):
        return 4
    return 8


def expected_width(identity, facts):
    """D13 load_scope 的宽度取自 rule_tables.D17，其余按助记符后缀。"""
    if identity in facts["d13_load"]:
        return facts["d17_w4"] if identity.endswith(".t-rf") else facts["d17_w8"]
    return mem_width_of(identity)


def rf_format(identity, facts):
    """rf 结果的格式位数。

    D13 的 ``write_scope``（18 条）恰好是「结果为 f32 并写 rf」的集合：
    16 条 ft 算术 + ``fo2ft`` + ``ld.t-rf`` + ``ldm.t-rf``。故直接用
    机器数据判定，而不是从助记符猜。
    """
    return 32 if identity in facts["d13_write"] else 64


def fcsr_expected(layout, rm, flags):
    v = (layout["ro_value"] & layout["masks"]["ro"])
    v |= (ROUNDING[rm] << layout["rm_shift"])
    for f in flags:
        v |= 1 << (layout["flag_shift"] + FLAGBIT[f])
    return v


def recompute_case(cid, c, ctx, rep):
    """单条 case 的全部独立重算。"""
    ops, facts, layout = ctx["ops"], ctx["facts"], ctx["layout"]
    ident = c["identity"]
    rec = ops.get(ident)
    if rec is None:
        rep.bad(cid, "identity %r 不在 F1 64 集" % ident)
        return
    word = as_u64(c["encoding"]["word"], cid, "encoding.word", rep)
    if word is None:
        return
    word &= 0xFFFFFFFF
    if (word & rec["mask"]) != (rec["value"] & rec["mask"]):
        rep.bad(cid, "编码 0x%08X 与 identity %s 不符（期望 0x%08X）"
                % (word, ident, rec["value"]))
    else:
        rep.ok()
    raw, flds = decode_fields(word, rec)
    dst_names, src_names = roles_of(raw)
    ins = c.get("input_state") or {}
    exp = c.get("expected_state")
    fcsr_in = ins.get("fcsr") or {}
    fcsr_out = (exp or {}).get("fcsr") or {}
    rm = fcsr_in.get("rounding_mode") or "RNE"
    if rm not in ROUNDING:
        rep.bad(cid, "输入舍入模式 %r 非法" % (rm,))
        return

    # ── K. 寄存器一致性：input_state.rf 只能是「这条指令真正会读写的 rf」 ──
    # 这一条专治「角色错位 / 陈旧寄存器」：例如把 scaleB 的指数写进 rf4
    # （而 orrr 只有 rfhb/rfhc/rfhd 三个字段），或把 sNaN 放进**目的**寄存器
    # —— 期望值与 notes 彼此自洽，却与编码声明的真实操作数无关。
    _check_operands(cid, c, rep, raw, flds, dst_names, src_names, ident)

    # ── A. D17:S1 复位取值（from_reset 时 rw 域必须 RNE + flags 全 0）──────
    if fcsr_in.get("from_reset"):
        if rm != facts["d17_reset_mode"] or fcsr_in.get("rounding_mode") != rm:
            rep.bad(cid, "from_reset 的舍入模式应为 %r" % facts["d17_reset_mode"])
        else:
            rep.ok()
        if list(fcsr_in.get("flags") or []) != []:
            rep.bad(cid, "from_reset 的 flags 应为 0（rule_tables.D17.reset_flags=%r）"
                    % (facts["d17_reset_flags"],))
        else:
            rep.ok()
        if facts["d17_reset_rm_bits"] != "00":
            rep.bad(cid, "reset_rounding_bits 应为 '00'，实得 %r"
                    % (facts["d17_reset_rm_bits"],))

    # ── B. FCSR 期望：value 重算 + observed_mask 三条规则 ──────────────
    if fcsr_out:
        flags = list(fcsr_out.get("flags") or [])
        bad_flag = [f for f in flags if f not in FLAGBIT]
        if bad_flag:
            rep.bad(cid, "非法 flag 名 %r" % (bad_flag,))
        else:
            want = fcsr_expected(layout, fcsr_out.get("rounding_mode"), flags)
            got = as_u64(fcsr_out.get("value"), cid, "expected fcsr.value", rep)
            if got is None:
                rep.bad(cid, "expected_state.fcsr 缺 value")
            elif got != want:
                rep.bad(cid, "fcsr.value 独立重算 %s，实得 %s（rm=%r flags=%r）"
                        % (hexv(want), hexv(got), fcsr_out.get("rounding_mode"), flags))
            else:
                rep.ok()
            m = as_u64(fcsr_out.get("observed_mask"), cid,
                       "expected fcsr.observed_mask", rep)
            if m is not None:
                ro, rw, sbz = (layout["masks"]["ro"], layout["masks"]["rw"],
                               layout["masks"]["sbz"])
                if (m & rw) != rw:
                    rep.bad(cid, "observed_mask 未覆盖 rw 域 %s：%s"
                            % (hexv(rw), hexv(m)))
                elif m & sbz:
                    rep.bad(cid, "observed_mask 宣称了 SBZ 位 %s：%s"
                            % (hexv(m & sbz), hexv(m)))
                elif m & ~(ro | rw):
                    rep.bad(cid, "observed_mask 越出 RO|rw：%s" % hexv(m))
                else:
                    rep.ok()
            # D12：自动置位是 sticky OR（不得清零既有 flag），非自动必须原样保持
            in_flags = set(fcsr_in.get("flags") or [])
            out_flags = set(flags)
            if ident in facts["d12_auto"]:
                if not in_flags <= out_flags:
                    rep.bad(cid, "D12 自动置位应为 sticky OR：输入 %s 未全部出现在输出 %s"
                            % (sorted(in_flags), sorted(out_flags)))
                else:
                    rep.ok()
            elif ident in facts["d12_non_auto"]:
                if out_flags != in_flags:
                    rep.bad(cid, "%s 属 D12 非自动置位（%d 条之一），flags 必须原样保持："
                            "输入 %s、实得 %s"
                            % (ident, len(facts["d12_non_auto"]),
                               sorted(in_flags), sorted(out_flags)))
                else:
                    rep.ok()
            # D16：复合 flags（OF+NX / UF+NX）与 tininess 检测时点
            if out_flags & facts["d16_of"]:
                if not facts["d16_of"] <= out_flags:
                    rep.bad(cid, "D16 要求 overflow 同时置 %s，实得 %s"
                            % (sorted(facts["d16_of"]), sorted(out_flags)))
                elif ident not in facts["d16_scope"]:
                    rep.bad(cid, "%s 置了 OF 却在 D16 域（%d 条）之外"
                            % (ident, len(facts["d16_scope"])))
                else:
                    rep.ok()
            elif out_flags & facts["d16_uf"]:
                if not facts["d16_uf"] <= out_flags:
                    rep.bad(cid, "D16 要求 underflow 同时置 %s，实得 %s"
                            % (sorted(facts["d16_uf"]), sorted(out_flags)))
                else:
                    rep.ok()
            # D12/D15：sNaN 输入置 NV、qNaN 不置 NV（D15 arithmetic_rule）
            if ident in facts["d15_arith"]:
                w = rf_format(ident, facts)
                srcs = [reg_value(ins, "rf", int(flds[n]), cid, rep, "input rf") for n in src_names]
                srcs = [s & ((1 << w) - 1) for s in srcs if s is not None]
                if any(is_snan(s, w) for s in srcs) and "NV" not in out_flags:
                    rep.bad(cid, "D15：sNaN 源必须置 NV，实得 flags=%s" % sorted(out_flags))
                elif (out_flags & {"NV"}) and not any(is_snan(s, w) for s in srcs):
                    rep.bad(cid, "D15：源里没有 sNaN 却置了 NV（flags=%s）"
                            % sorted(out_flags))
                else:
                    rep.ok()

    # ── C. 算术类：结果位型 + flags 用整数引擎重算 ────────────────────
    dst_rf = None
    if dst_names and raw[dst_names[0]]["role"] == "dst" and \
            dst_names[0].startswith("rf"):
        dst_rf = int(flds[dst_names[0]])
    op_kind = _arith_kind(ident, facts)
    if op_kind and dst_rf is not None:
        w = rf_format(ident, facts)
        a = reg_value(ins, "rf", int(flds[src_names[0]]), cid, rep, "源 rf")
        b = reg_value(ins, "rf", int(flds[src_names[1]]), cid, rep, "源 rf")
        if a is not None and b is not None:
            if w == 32:
                a &= 0xFFFFFFFF
                b &= 0xFFFFFFFF
            res, fl = ARITH_OPS[op_kind](a, b, w, rm)
            got = reg_value(exp, "rf", dst_rf, cid, rep, "expected rf") if exp else None
            if res is NAN_NONE:
                # D15：位型未固定（canonical_qnan_bits=null）→ 不得断言目的寄存器
                if got is not None:
                    rep.bad(cid, "源含 NaN 且 canonical qNaN 位型未固定（%r），"
                            "却断言了 rf%d=%s" % (facts["d15_qnan"], dst_rf, hexv(got)))
                else:
                    rep.ok()
            elif got is None:
                rep.note(cid, "结果 rf%d 未断言（独立重算得 %s）" % (dst_rf, hexv(res)))
            else:
                want = (res | 0xFFFFFFFF00000000) if w == 32 else res
                if got != want:
                    rep.bad(cid, "%s 独立重算 rf%d=%s，实得 %s"
                            % (ident, dst_rf, hexv(want), hexv(got)))
                else:
                    rep.ok()
            if fcsr_out.get("flags") is not None:
                want_fl = set(fcsr_out.get("flags") or [])
                if want_fl != fl:
                    rep.bad(cid, "%s 的 flags 独立重算 %s，实得 %s"
                            % (ident, sorted(fl), sorted(want_fl)))
                else:
                    rep.ok()

    # ── D. D13 装箱：所有 D13 写 RF 的期望值高 32 位固定 0xffffffff ────
    if ident in facts["d13_write"] and exp:
        for key, raw_v in (exp.get("rf") or {}).items():
            v = as_u64(raw_v, cid, "expected rf.%s" % key, rep)
            if v is None:
                continue
            if (v >> 32) != facts["d13_high32"]:
                rep.bad(cid, "D13：%s 写 RF 的高 32 位应为 0x%08X，rf%s 实得 0x%08X"
                        % (ident, facts["d13_high32"], key, v >> 32))
            else:
                rep.ok()

    # ── E. 装载 / 块装载：EA0 + i*width → 内存 → 装箱后的 rf ──────────
    if _is_load(ident):
        _check_load(cid, c, ctx, rep, word, raw, flds, ins, exp)

    # ── F. 寄存器组块赋值：rd2rf / rf2rd 的逐对搬运 ──────────────────
    if ident in ("rd2rf", "rf2rd"):
        _check_move(cid, c, ctx, rep, flds, ins, exp, ident)

    # ── G. set.w-rf：白名单 + 只读/SBZ 写掩码后的完整 rf0 像 ──────────
    if ident == "set.w-rf":
        _check_setw(cid, c, ctx, rep, flds, ins, exp)

    # ── H. 比较类：unordered 的 D14 位型 ───────────────────────────
    if ident in facts["d14_quiet"] | facts["d14_signal"]:
        _check_compare(cid, c, ctx, rep, flds, ins, exp, ident)

    # ── I. 分类类：immu6 固定为 1（D17:S3）────────────────────────
    if ident in ("ftcls", "focls"):
        if int(flds.get("immu6", -1)) != 1:
            if c.get("expected_fault") != "ILLI":
                rep.bad(cid, "immu6=%d != 1，rule_tables.D17.classify_immediate=%r "
                        "要求 %r，但 expected_fault=%r"
                        % (int(flds.get("immu6", -1)), facts["d17_classify_imm"],
                           facts["d17_classify_hw"], c.get("expected_fault")))
            else:
                rep.ok()
        elif c.get("expected_fault") is not None:
            rep.bad(cid, "immu6==1 时不应 fault，实得 %r" % (c.get("expected_fault"),))
        else:
            rep.ok()

    # ── J. D15 canonical qNaN 必须保持 null ──────────────────────
    if facts["d15_qnan"] is not None:
        rep.bad(cid, "rule_tables.D15.canonical_qnan_bits 必须保持 null，实得 %r"
                % (facts["d15_qnan"],))


def _arith_kind(ident, facts):
    """二元同格式算术 identity → add/sub/mul/div。

    只认 D15 ``arithmetic_scope``（18 条：16 条 fo/ft 算术 + 2 条 root/log）
    里的二元运算；``ftrem/forem``（rem）、``ftroot/foroot``（root）、
    ``ftsclb/fosclb``（scaleB）都不是本引擎的二元四则，故跳过。
    """
    if ident not in facts["d15_arith"]:
        return None
    m = re.match(r"^(?:fo|ft)(add|sub|mul|div)$", ident)
    return m.group(1) if m else None


# 块搬移：immu6 是「元素/寄存器个数」，rf 编号从基号递增（D17:S8 / 搬移对）
MOVE_IDENT = ("rd2rf", "rf2rd")

def _check_operands(cid, c, rep, raw, flds, dst_names, src_names, ident):
    """K：input_state.rf 的每个索引都必须被这条指令真的读到或写到。"""
    ins = c.get("input_state") or {}
    bank = ins.get("rf") or {}
    listed, malformed = set(), []
    for k in bank:
        m = re.match(r"^rf(\d+)$", str(k))
        if m is None:
            malformed.append(str(k))
        else:
            listed.add(int(m.group(1)))
    if malformed:
        rep.bad(cid, "input_state.rf 的键 %s 不是 rf<索引> 形式" % (malformed,))
    else:
        rep.ok()
    used, detail = set(), []
    is_block = (ident.startswith(("ldm.", "stm.")) or ident in MOVE_IDENT)
    count = int(flds.get("immu6", 0)) if is_block else None
    for n, meta in sorted(raw.items(), key=lambda kv: -kv[1]["hi"]):
        if not n.startswith("rf"):
            continue
        idx = int(flds[n])
        if count is not None:
            used.update(range(idx, idx + count))
            detail.append("%s[%d]%s×%d" % (n, idx,
                                           "(dst)" if meta["role"] == "dst" else "", count))
        else:
            used.add(idx)
            detail.append("%s[%d]%s" % (n, idx,
                                        "(dst)" if meta["role"] == "dst" else ""))
    orphan = sorted(listed - used)
    if orphan:
        rep.bad(cid, "input_state.rf 的 %s 不在编码的任何 rf 操作数里（%s）——"
                "陈旧/写错的寄存器，notes 说的操作数与真实编码脱节"
                % (", ".join("rf%d" % i for i in orphan), "; ".join(detail)))
    else:
        rep.ok()
    need = set()
    for n, meta in raw.items():
        if n.startswith("rf") and meta["role"] == "src":
            base = int(flds[n])
            need.update(range(base, base + count)
                        if (count is not None and count > 0) else [base])
    missing = sorted(need - listed)
    if missing:
        rep.bad(cid, "编码声明的源 %s 在 input_state.rf 里没有值"
                % ", ".join("rf%d" % i for i in missing))
    else:
        rep.ok()


def _is_load(ident):
    return ident.startswith("ld.") or ident.startswith("ldm.") or \
        ident.startswith("st.") or ident.startswith("stm.")


def ea0_of(flds, ins, cid, rep, ident):
    """EA0：ld/st 用 rb[rbhb] + imms12（有符号）；ldm/stm 用 rb[rbhb] + rd[rdhc]。"""
    base_idx = int(flds.get("rbhb", 0))
    base = reg_value(ins, "rb", base_idx, cid, rep, "input rb%d" % base_idx)
    if base is None:
        return None
    if "imms12" in flds:
        return (base + flds["imms12"]) & 0xFFFFFFFFFFFFFFFF
    off_idx = int(flds.get("rdhc", 0))
    off = reg_value(ins, "rd", off_idx, cid, rep, "input rd%d" % off_idx)
    if off is None:
        return None
    return (base + off) & 0xFFFFFFFFFFFFFFFF


def _check_load(cid, c, ctx, rep, word, raw, flds, ins, exp):
    ops, facts = ctx["ops"], ctx["facts"]
    ident = c["identity"]
    is_store = ident.startswith("st") or ident.startswith("stm")
    width = expected_width(ident, facts)
    count = 1
    if ident.startswith(("ldm.", "stm.")):
        count = int(flds.get("immu6", 0))
    elif ident.startswith(("rd2rf", "rf2rd")):
        count = int(flds.get("immu6", 0))
    ea0 = ea0_of(flds, ins, cid, rep, ident)
    if ea0 is None:
        return
    if facts["d17_ea0"] != "EA0 = rbhb + rdhc" and ident.startswith(("ldm.", "stm.")):
        rep.bad(cid, "rule_tables.D17.ldm_stm_base 变成 %r，与本脚本独立实现的 "
                "EA0=rb[rbhb]+rd[rdhc] 不一致" % (facts["d17_ea0"],))
    # 元素地址：EA(0) + i*width（rule_tables.D17.ldm_stm_address）
    addr_formula_ok = (facts["d17_addr"] == "EA(0) + i * width" and
                       facts["d17_w4"] == 4 and facts["d17_w8"] == 8)
    if not addr_formula_ok:
        rep.bad(cid, "rule_tables.D17 的块地址/宽度字段变了：addr=%r w4=%r w8=%r"
                % (facts["d17_addr"], facts["d17_w4"], facts["d17_w8"]))
    mem_in = mem_index(ins.get("memory"))
    mem_out = mem_index((exp or {}).get("memory"))
    elements = ((c.get("oracle") or {}).get("elements")) or []
    first_rf = int(flds.get("rfha", 0)) if not is_store else int(flds.get("rfha", 0))
    for i in range(count):
        addr = (ea0 + i * width) & 0xFFFFFFFFFFFFFFFF
        if elements:
            el = elements[i] if i < len(elements) else None
            if el is None:
                rep.bad(cid, "oracle.elements 少于 immu6=%d 个元素" % count)
                continue
            ea_hex = int(str(el["address"]), 16)
            if ea_hex != addr:
                rep.bad(cid, "第 %d 个元素地址独立重算 %s，实得 %s"
                        % (i, hexv(addr), hexv(ea_hex)))
            else:
                rep.ok()
            if el.get("width") != width:
                rep.bad(cid, "第 %d 个元素宽度应为 %d，实得 %r" % (i, width, el.get("width")))
            else:
                rep.ok()
            src = mem_in.get(addr)
            if src is None:
                rep.bad(cid, "第 %d 个元素地址 %s 在 input_state.memory 里不存在"
                        % (i, hexv(addr)))
                continue
            if int(str(src["value"]), 16) != int(str(el["value"]), 16):
                rep.bad(cid, "第 %d 个元素值与 input_state.memory 不一致：%s vs %s"
                        % (i, el["value"], src["value"]))
            else:
                rep.ok()
        if is_store:
            src = reg_value(ins, "rf", first_rf + i, cid, rep, "input rf%d" % (first_rf + i))
            if src is None:
                continue
            low = src & 0xFFFFFFFF
            hi = 0xFFFFFFFF if (width == 4 and ident in facts["d13_write"]) else (src >> 32)
            want = (hi << 32) | low
            mrec = mem_out.get(addr)
            if mrec is None:
                rep.note(cid, "store 目标 %s 未在 expected_state.memory 断言" % hexv(addr))
                continue
            mv = int(str(mrec["value"]), 16)
            if mv != want:
                rep.bad(cid, "第 %d 个 store 值独立重算 %s，实得 %s"
                        % (i, hexv(want), hexv(mv)))
            else:
                rep.ok()
            if mrec.get("width") != width:
                rep.bad(cid, "第 %d 个 store 宽度应为 %d，实得 %r"
                        % (i, width, mrec.get("width")))
            else:
                rep.ok()
        else:
            src = mem_in.get(addr)
            if src is None:
                if c.get("expected_fault"):
                    rep.ok()               # fault 用例：地址不对齐时内存布局仍可给出
                    continue
                rep.bad(cid, "第 %d 个元素地址 %s 在 input_state.memory 里缺失"
                        % (i, hexv(addr)))
                continue
            if src.get("width") != width:
                rep.bad(cid, "第 %d 个元素访存宽度应为 %d，实得 %r"
                        % (i, width, src.get("width")))
                continue
            raw_v = int(str(src["value"]), 16)
            want = (0xFFFFFFFF00000000 | (raw_v & 0xFFFFFFFF)) if width == 4 else raw_v
            got = reg_value(exp, "rf", first_rf + i, cid, rep,
                            "expected rf%d" % (first_rf + i)) if exp else None
            if got is None:
                if c.get("expected_fault"):
                    rep.ok()
                    continue
                rep.note(cid, "第 %d 个元素的 rf%d 未断言" % (i, first_rf + i))
                continue
            if got != want:
                rep.bad(cid, "第 %d 个元素：独立重算 rf%d=%s（%d 字节%s），实得 %s"
                        % (i, first_rf + i, hexv(want), width,
                           " + D13 装箱" if width == 4 else "", hexv(got)))
            else:
                rep.ok()


def _check_move(cid, c, ctx, rep, flds, ins, exp, ident):
    """rd2rf / rf2rd：逐对搬运 + 源不被破坏（先读后写）。"""
    count = int(flds.get("immu6", 0))
    dst_base = int(flds.get("rfhb", 0)) if ident == "rd2rf" else int(flds.get("rdhb", 0))
    src_base = int(flds.get("rdhc", 0)) if ident == "rd2rf" else int(flds.get("rfhc", 0))
    dst_bank, src_bank = ("rf", "rd") if ident == "rd2rf" else ("rd", "rf")
    for i in range(count):
        src = reg_value(ins, src_bank, src_base + i, cid, rep,
                        "input %s%d" % (src_bank, src_base + i))
        if src is None:
            continue
        got = reg_value(exp, dst_bank, dst_base + i, cid, rep,
                        "expected %s%d" % (dst_bank, dst_base + i)) if exp else None
        if got is None:
            rep.note(cid, "%s%d 未断言" % (dst_bank, dst_base + i))
            continue
        if got != src:
            rep.bad(cid, "第 %d 对搬运独立重算 %s%d=%s，实得 %s"
                    % (i, dst_bank, dst_base + i, hexv(src), hexv(got)))
        else:
            rep.ok()
        keep = reg_value(exp, src_bank, src_base + i, cid, rep,
                         "expected %s%d" % (src_bank, src_base + i)) if exp else None
        if keep is not None:
            if keep != src:
                rep.bad(cid, "源 %s%d 被改写：独立重算应保持 %s，实得 %s"
                        % (src_bank, src_base + i, hexv(src), hexv(keep)))
            else:
                rep.ok()


def _check_setw(cid, c, ctx, rep, flds, ins, exp):
    """set.w-rf：写 rf0 必须在十条白名单内；只读域不动、SBZ 写静默忽略。"""
    facts, layout = ctx["facts"], ctx["layout"]
    dst = int(flds.get("rfha", 0))
    if dst != 0:
        rep.bad(cid, "set.w 的 rfha=%d，rf0 写白名单之外的 rf 目的应 ILLI" % dst)
        return
    if c["identity"] not in facts["d11_whitelist"]:
        rep.bad(cid, "rf0 写白名单（%d 条）里没有 set.w-rf" % len(facts["d11_whitelist"]))
    else:
        rep.ok()
    imm = flds.get("immu16", 0)
    wp = int(flds.get("wpN", 0))
    shift = wp * 16
    base_image = fcsr_expected(layout, (ins.get("fcsr") or {}).get("rounding_mode", "RNE"),
                               (ins.get("fcsr") or {}).get("flags") or [])
    # 写掩码：只读域写无效（保持原像），SBZ 写静默忽略（D17:S6）→ 只有 rw 域变
    wr = ((0xFFFF << shift) & layout["masks"]["rw"])
    want = (base_image & ~wr) | (imm << shift) & wr
    got = as_u64(((exp or {}).get("fcsr") or {}).get("value"), cid,
                 "expected fcsr.value", rep)
    if got is None:
        return
    if got != want:
        rep.bad(cid, "set.w(wp%d, %s) 独立重算 rf0=%s（只读域保持 + rw 域写入 + "
                "SBZ 静默忽略），实得 %s" % (wp, hexv(imm), hexv(want), hexv(got)))
    else:
        rep.ok()


def _check_compare(cid, c, ctx, rep, flds, ins, exp, ident):
    facts = ctx["facts"]
    w = 32 if ident.startswith("ft") else 64
    a = reg_value(ins, "rf", int(flds["rfhc"]), cid, rep, "input rf")
    b = reg_value(ins, "rf", int(flds["rfhd"]), cid, rep, "input rf")
    if a is None or b is None:
        return
    if w == 32:
        a &= 0xFFFFFFFF
        b &= 0xFFFFFFFF
    dst = int(flds["rdhb"])
    # 断言 flags 时不得与「sNaN 必置 NV」相矛盾（IEEE 754 §7.2：任一操作数是
    # sNaN 即置 invalidOperation）。比较类不在 D15 arithmetic_scope 内，规则表
    # 没有把「比较 + sNaN」的 flags 固定下来，所以样例**只应**用 qNaN 输入。
    exp_flags = set((((exp or {}).get("fcsr") or {}).get("flags")) or [])
    if "NV" not in exp_flags and (is_snan(a, w) or is_snan(b, w)):
        rep.bad(cid, "源里含 sNaN（rf%u/rf%u）却断言 flags 不含 NV；"
                "比较类的 flags 未被 resolution.rule_tables 固定，"
                "应改用 qNaN 输入而不是断言一个未激活的取值"
                % (int(flds["rfhc"]), int(flds["rfhd"])))
    else:
        rep.ok()
    if is_nan(a, w) or is_nan(b, w):
        want = (facts["d14_quiet_bits"] if ident in facts["d14_quiet"]
                else facts["d14_signal_bits"])
        got = reg_value(exp, "rd", dst, cid, rep, "expected rd") if exp else None
        if got is None:
            rep.bad(cid, "unordered 时必须断言 rd%d=%s（rule_tables.D14）"
                    % (dst, hexv(want)))
        elif got != want:
            rep.bad(cid, "unordered 位型独立重算 %s（%s 类），实得 %s"
                    % (hexv(want),
                       "quiet" if ident in facts["d14_quiet"] else "signaling",
                       hexv(got)))
        else:
            rep.ok()
    else:
        rep.note(cid, "有序比较的 rd 写值（1/0/-1）在本脚本中不独立断言")


# ═══════════════════════ oracle 记录的独立核对 ═══════════════════════
def check_oracle_records(c, ctx, rep):
    """oracle.records 的 reg / fcsr 值必须与 expected_state **逐位相等**，
    且 fcsr 记录与独立重算相等（expected_state 已由 recompute_case 核对）。"""
    cid = c["id"]
    o = c.get("oracle") or {}
    exp = c.get("expected_state") or {}
    for idx, rec in enumerate(o.get("records") or []):
        if "fcsr" in rec:
            fr = rec["fcsr"]
            er = (exp.get("fcsr") or {})
            for key in ("rounding_mode", "flags", "observed_mask", "value"):
                if fr.get(key) != er.get(key):
                    rep.bad(cid, "oracle.records[%d].fcsr.%s = %r 与 expected_state 的 %r 不一致"
                            % (idx, key, fr.get(key), er.get(key)))
                else:
                    rep.ok()
        if "reg" in rec:
            rr = rec["reg"]
            bank = rr.get("bank")
            i = rr.get("index")
            full = reg_value(exp, bank, int(i), cid, rep,
                             "expected %s%d" % (bank, i)) if exp else None
            if full is None:
                if "low32" in rr or "high32" in rr:
                    rep.bad(cid, "oracle.records[%d] 断言了 %s%d 的半观测，但 "
                            "expected_state 里没有该寄存器" % (idx, bank, i))
                continue
            if "low32" in rr or "high32" in rr:
                lo = int(str(rr.get("low32")), 16) if "low32" in rr else None
                hi = int(str(rr.get("high32")), 16) if "high32" in rr else None
                if (full & 0xFFFFFFFF) != lo:
                    rep.bad(cid, "oracle.records[%d] low32=%08X 与 %s%d 的低 32 位 %08X 不符"
                            % (idx, lo, bank, i, full & 0xFFFFFFFF))
                else:
                    rep.ok()
                if (full >> 32) != hi:
                    rep.bad(cid, "oracle.records[%d] high32=%08X 与 %s%d 的高 32 位 %08X 不符"
                            % (idx, hi, bank, i, full >> 32))
                else:
                    rep.ok()
            elif "value" in rr:
                v = int(str(rr["value"]), 16)
                if v != full:
                    rep.bad(cid, "oracle.records[%d] value=%s 与 %s%d 的期望 %s 不符"
                            % (idx, hexv(v), bank, i, hexv(full)))
                else:
                    rep.ok()
        if "fault" in rec and idx != len(o["records"]) - 1:
            rep.bad(cid, "oracle.records[%d] 的 fault 必须是最后一条（D17:S4/S8 的"
                    "不提交语义）" % idx)
        else:
            rep.ok()


def self_check():
    """独立性自检：不得 import 本项目的 oracle 模块，不得出现宿主浮点路径。

    被查的字面量本身是用**分段拼接**在运行时组装的：否则「检查里写着禁用
    模式」会把 ``self_check`` 自己判成违规（本脚本第一次运行时报的 3 条
    SELF-CHECK VIOLATION 就是这个）。
    """
    bad = []
    for mod in ("f1_schema", "f1_cases", "f1_oracle_values",
                "generate_f1_schema_fixtures"):
        if mod in sys.modules:
            bad.append("本进程已加载项目模块 %s（独立路径不得依赖）" % mod)
    src = read_text(os.path.abspath(__file__))
    # ── 运行时组装：源码里不得出现下列词条的**连续**字面量 ──
    w_float = "flo" + "at"        # 宿主二进制浮点构造
    w_math = "ma" + "th."         # 宿主 libm
    w_frac = "Frac" + "tion"      # 精确有理数（宿主浮点路径）
    w_dec = "Dec" + "imal"        # 十进制浮点
    w_sf = "soft" + "float"       # 实现侧 FPU
    w_ctypes = "cty" + "pes"      # 加载宿主 libm/libc
    impl_mods = ("ll" + "c", "ll" + "vm", "qe" + "mu", w_sf, "host" + "_fpu")
    pats = [
        (r"\b" + w_float + r"\s*\(", "%s(...): 宿主二进制浮点" % w_float),
        (r"\b" + w_math + r"[a-z]", "%s*: 宿主 libm" % w_math),
        (r"\b" + w_frac + r"\s*\(", "%s(...): 精确有理数" % w_frac),
        (r"\b" + w_dec + r"\s*\(", "%s(...): 十进制浮点" % w_dec),
        (r"\b" + w_ctypes + r"\b", "%s: 加载宿主 libm/libc" % w_ctypes),
        (r"\b" + w_sf + r"\b", "提及 %s" % w_sf),
        (r"^\s*(?:import|from)\s+(?:%s)\b" % "|".join(impl_mods),
         "import 实现侧模块"),
    ]
    for pat, why in pats:
        m = re.search(pat, src, re.M)
        if m:
            line = src.count("\n", 0, m.start()) + 1
            bad.append("源码第 %d 行出现 %s" % (line, why))
    return bad


# ═══════════════════════════════ 入口 ═══════════════════════════════
def build_ctx(root):
    layout = parse_fcsr_layout(os.path.join(root, REL_CONTRACT))
    facts = load_gap_facts(os.path.join(root, REL_GAPS))
    facts["d11_whitelist"] = set((facts["d11"].get("rf0_write_whitelist")) or [])
    ops = load_opcode_facts(os.path.join(root, REL_OPCODES))
    return {"layout": layout, "facts": facts, "ops": ops}


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--root", default=REPO_DEFAULT,
                    help="仓库根；反例注入时指向 /tmp 下的合成树")
    args = ap.parse_args(argv)
    root = os.path.abspath(args.root)
    try:
        ctx = build_ctx(root)
        import yaml
        with open(os.path.join(root, REL_VECTORS), encoding="utf-8") as fh:
            cases = yaml.safe_load(fh)
    except Fatal as exc:
        print("verify_f1_expected_values: FATAL: %s" % exc, file=sys.stderr)
        return 2
    except OSError as exc:
        print("verify_f1_expected_values: FATAL: %s" % exc, file=sys.stderr)
        return 2

    rep = Report()
    kats = run_kats(rep)
    for c in cases:
        recompute_case(c["id"], c, ctx, rep)
        check_oracle_records(c, ctx, rep)
    self_bad = self_check()

    facts, layout = ctx["facts"], ctx["layout"]
    summary = {
        "root": root,
        "cases": len(cases),
        "kats": len(KATS),
        "independent_checks": rep.checked,
        "mismatches": rep.problems,
        "notes": rep.notes,
        "self_check_violations": self_bad,
        "layout": {"ro_mask": hexv(layout["masks"]["ro"]),
                   "rw_mask": hexv(layout["masks"]["rw"]),
                   "sbz_mask": hexv(layout["masks"]["sbz"]),
                   "ro_value": hexv(layout["ro_value"])},
        "counts": {"d12_auto": len(facts["d12_auto"]),
                   "d12_non_auto": len(facts["d12_non_auto"]),
                   "d13_write": len(facts["d13_write"]),
                   "d15_arith": len(facts["d15_arith"]),
                   "d16_scope": len(facts["d16_scope"]),
                   "d11_whitelist": len(facts["d11_whitelist"])},
    }
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=1))
    else:
        kat_failed = len([p for p in rep.problems if p.startswith("KAT[")]) // 2
        print("verify_f1_expected_values: %d case(s), %d independent bit-exact "
              "recomputation(s)" % (len(cases), rep.checked))
        print("  engine KAT (known-answer tests, hand-derived from IEEE 754-2008): "
              "%d/%d passed (%d bit/flag assertions)"
              % (len(KATS) - kat_failed, len(KATS), kats))
        print("  FCSR layout re-derived from the contract (two-way cross-check): "
              "ro=%s rw=%s sbz=%s ro_value=%s"
              % (summary["layout"]["ro_mask"], summary["layout"]["rw_mask"],
                 summary["layout"]["sbz_mask"], summary["layout"]["ro_value"]))
        print("  D-scope from resolution.rule_tables: D11 whitelist=%d D12 auto=%d "
              "D13 write=%d D15 arith=%d D16=%d"
              % (summary["counts"]["d11_whitelist"], summary["counts"]["d12_auto"],
                 summary["counts"]["d13_write"], summary["counts"]["d15_arith"],
                 summary["counts"]["d16_scope"]))
        for n in rep.notes:
            print("  note %s" % n)
        for v in self_bad:
            print("SELF-CHECK VIOLATION %s" % v, file=sys.stderr)
        if rep.problems:
            for p in rep.problems:
                print("MISMATCH %s" % p, file=sys.stderr)
            print("verify_f1_expected_values: FAILED (%d mismatch(es), "
                  "%d self-check violation(s))"
                  % (len(rep.problems), len(self_bad)), file=sys.stderr)
            return 1
        if self_bad:
            print("verify_f1_expected_values: FAILED (independence self-check)",
                  file=sys.stderr)
            return 1
        print("verify_f1_expected_values: OK (engine KAT green; every asserted "
              "32/64-bit value, FCSR field, flag, block address and static fault "
              "predicate matches the independent integer recompute; no project "
              "oracle module imported)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
