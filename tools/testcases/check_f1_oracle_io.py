#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_f1_oracle_io.py — F1 oracle 独立性 / 禁止依赖的静态门控。

TESTCASES-101t 的核心约束之一：**F1 向量的期望值不得来自任何实现**。
本脚本把这条约束从「承诺」变成**可执行的**检查：静态扫描 F1 的 schema 层
代码与数据，凡出现下列情形即 FAIL（退出码 1）。

  B1 禁止 oracle：F1 相关的 .py / .yaml 不得 import 或调用实现侧事实来源
       —— ``llc``、``llvm``、``qemu``、``softfloat``、``host_fpu``；
       也不得 ``import ctypes``/``ctypes.CDLL`` 去加载宿主 libm/libc 的浮点
       函数（``sqrtf``/``fesetround``/…）。整数位型推导不需要它们。
  B2 禁止宿主浮点：F1 相关 .py 不得使用 ``float(``/``complex(``、``math.``/
       ``cmath.``/``numpy.``/``struct.unpack('f'``/``Fraction(`` 等宿主浮点/
       十进制浮点路径。注意 ``hx()`` 之类的十六进制格式化与 ``int(x, 16)``
       **不是**浮点，允许。
  B3 禁止外部数据依赖：F1 相关 .py 不得读取 ``spec/`` 下的原始规范正文来
       推导期望值（溯源引用只能是 ``spec_cite`` 字符串）。规范正文是**只读
       溯源**，语义输入只能是 ``contracts/`` + ``.xkw/knowledge/`` + ADR。
  B4 期望值必须落在白名单模块内：生成器 / validator 引用的 32/64 位期望值
       只能来自 ``f1_oracle_values.py``（手写整数推导）与合约常量，
       不得从 ``tests/vectors/f1/valid/*.yaml`` 反读（那会变成自证）。
  B5 oracle 接口可自证：``f1_oracle_values.py`` 的每个常量都能用**纯整数**
       重算回自己（位型自洽），不依赖任何运行库。

用法：
  python3 tools/testcases/check_f1_oracle_io.py           # 检查仓库
  python3 tools/testcases/check_f1_oracle_io.py --json     # 机器可读

退出码：0 = 独立；1 = 发现禁止依赖（逐条打印）。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))

# 被检查的代码/数据面：F1 schema 层 + F1 向量数据。
CODE_GLOBS = ("tools/testcases/f1_schema.py",
              "tools/testcases/f1_cases.py",
              "tools/testcases/f1_oracle_values.py",
              "tools/testcases/generate_f1_schema_fixtures.py",
              "tools/testcases/check_f1_context.py",
              "tools/testcases/check_f1_oracle_io.py",
              "tools/testcases/verify_f1_expected_values.py",
              "tools/testcases/test_f1_schema_counterexamples.py")
DATA_GLOBS = ("tests/vectors/f1/valid/*.yaml", "tests/vectors/f1/invalid/*.yaml")

# B1：实现侧事实来源（import 名 / 子串）
B1_IMPORT_PATTERNS = (
    (re.compile(r"^\s*(?:import|from)\s+llc\b", re.M), "import llc"),
    (re.compile(r"^\s*(?:import|from)\s+llvm\b", re.M), "import llvm"),
    (re.compile(r"^\s*(?:import|from)\s+qemu\b", re.M), "import qemu"),
    (re.compile(r"^\s*(?:import|from)\s+softfloat\b", re.M), "import softfloat"),
    (re.compile(r"^\s*(?:import|from)\s+host_fpu\b", re.M), "import host_fpu"),
    (re.compile(r"\bctypes\b"), "ctypes（加载宿主 libm/libc 浮点）"),
    (re.compile(r"\bsoftfloat\b", re.S), "提及 softfloat"),
)
# B2：宿主浮点 / 十进制浮点路径
B2_PATTERNS = (
    (re.compile(r"\bfloat\s*\("), "float(...)：宿主二进制浮点"),
    (re.compile(r"\bmath\.[a-z]"), "math.*：宿主 libm"),
    (re.compile(r"\bcmath\."), "cmath.*"),
    (re.compile(r"\bnumpy\b"), "numpy"),
    (re.compile(r"\bFraction\s*\("), "Fraction(...)：精确有理数（宿主浮点路径）"),
    (re.compile(r"\bDecimal\s*\("), "Decimal(...)：十进制浮点"),
    (re.compile(r"struct\.unpack\(\s*['\"][fd]"), "struct.unpack('f'/'d')：宿主浮点"),
    (re.compile(r"\bpack\(\s*['\"][fd]['\"]\s*,\s*"), "struct.pack('f'/'d')：宿主浮点"),
)
# B3：不得把 spec/ 正文当**执行输入**（只读溯源：spec/ 路径可以出现在
#     spec_cite / facet cite 这类**字符串常量**里，f1_schema.PIN_AUTHORITY_TOKENS
#     就必须列出它们；因此只查「打开/读取」，不查「提到」）
B3_PATTERNS = (
    (re.compile(r"open\(\s*[^)]*spec[/\\]"), "open(... spec/...): 规范正文只可溯源"),
    (re.compile(r"os\.path\.join\(\s*[^)]*['\"]spec['\"]"),
     "os.path.join(..., 'spec', ...): 规范正文只可溯源"),
    (re.compile(r"Path\([^)]*['\"]spec/"), "Path(... spec/...): 规范正文只可溯源"),
    (re.compile(r"\bsubprocess\b|\bos\.system\b|\bpopen\b"),
     "执行外部进程取期望值"),
)

# 本脚本自己定义了这些正则字面量，扫自己必然全红；显式排除（并在此说明）
SELF = "tools/testcases/check_f1_oracle_io.py"
# 反例注入脚本**必须**能写出被禁的字样（`math.sqrt`、`subprocess`）才能注入，
# 而且它不在 oracle 链上（它只负责跑 validator）。故 B1/B2/B3 跳过它；
# 它自己作为被测对象仍被 B4/B5 之外的规则覆盖不到，这是有意的取舍。
HARNESS = "tools/testcases/test_f1_schema_counterexamples.py"
SCAN_SKIP = (SELF, HARNESS)


def _rel(path, root):
    return os.path.relpath(path, root)


def _files(root):
    out = []
    for rel in CODE_GLOBS:
        p = os.path.join(root, rel)
        if rel not in SCAN_SKIP and os.path.exists(p):
            out.append(rel)
    import glob as _g
    for pat in DATA_GLOBS:
        for p in sorted(_g.glob(os.path.join(root, pat))):
            out.append(_rel(p, root))
    return out


def _strip_py_comments(text):
    """去掉注释与文档串，避免把「说明为什么不用 float」误判成「用了 float」。"""
    lines = []
    in_doc = False
    for line in text.splitlines():
        s = line.strip()
        if in_doc:
            if s.endswith('"""') or s.endswith("'''"):
                in_doc = False
            continue
        if s.startswith('"""') or s.startswith("'''"):
            # 单行 docstring
            if len(s) > 3 and (s.endswith('"""') or s.endswith("'''")):
                continue
            in_doc = True
            continue
        if s.startswith("#"):
            continue
        # 行内 # 注释（本仓库代码里不存在含 # 的字符串字面量需要保留）
        idx = line.find("  #")
        if idx > 0:
            line = line[:idx]
        lines.append(line)
    return "\n".join(lines)


def scan_file(root, rel, data_only=False):
    """返回 [(rule, lineno, snippet, message), ...]"""
    path = os.path.join(root, rel)
    with open(path, encoding="utf-8") as fh:
        raw = fh.read()
    text = raw if data_only else _strip_py_comments(raw)
    findings = []
    patterns = (B3_PATTERNS if data_only
                else B1_IMPORT_PATTERNS + B2_PATTERNS + B3_PATTERNS)
    for rx, msg in patterns:
        for m in rx.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            snippet = text.splitlines()[line - 1].strip()[:100]
            rule = "B3" if (rx, msg) in B3_PATTERNS else (
                "B1" if (rx, msg) in B1_IMPORT_PATTERNS else "B2")
            findings.append((rule, line, snippet, msg))
    return findings


def check_b4_whitelist(root):
    """B4：期望值只能来自 f1_oracle_values.py；生成器**不得反读**已入库数据。

    反读 = 从 ``tests/vectors/f1/`` 把已写好的期望值读回来再吐一遍。那样
    「样例通过 validator」就只是自证，与实现无关也成了空话。

    判据取**宽**的一侧，而不是只匹配 `yaml.safe_load(`：别名（`import yaml as
    _y; _y.safe_load`）和分片路径（`os.path.join(.., 'tests', 'vectors', 'f1')`）
    同样构成反读。所以本检查按「生成器里除了写输出，不许出现任何读 YAML /
    打开向量目录的行为」来写。
    """
    findings = []
    gen = os.path.join(root, "tools/testcases/"
                           "generate_f1_schema_fixtures.py")
    if not os.path.exists(gen):
        return [("B4", 0, gen, "找不到生成器，无法核对期望值来源")]
    with open(gen, encoding="utf-8") as fh:
        text = _strip_py_comments(fh.read())
    lines = text.splitlines()
    for i, line in enumerate(lines, 1):
        code = line.split("#", 1)[0]
        if not code.strip():
            continue
        bad = None
        if re.search(r"\bsafe_load\s*\(", code):
            bad = "safe_load("
        elif re.search(r"\bload_f1_doc\b", code):
            bad = "load_f1_doc"
        elif re.search(r"\bopen\s*\(", code) and '"w"' not in code and \
                "'w'" not in code:
            bad = "open(... ) 读操作（生成器只该写输出）"
        elif re.search(r"os\.listdir|os\.scandir|glob\.glob|pathlib\.Path\(",
                       code) and re.search(r"vectors|tests", code):
            bad = "遍历向量目录"
        if bad:
            findings.append(("B4", i, code.strip()[:100],
                             "生成器不得读取已入库的向量数据（否则期望值自证）：%s"
                             % bad))
    # 生成器必须从 f1_oracle_values 取期望值
    if "import f1_oracle_values" not in text and "as V" not in text:
        findings.append(("B4", 0, "", "生成器未引用 f1_oracle_values 独立 oracle"))
    return findings


def check_b5_selfconsistent(root):
    """B5：f1_oracle_values 的关键常量用纯整数自洽重算（真算，不是查表）。"""
    tc = os.path.join(root, "tools", "testcases")
    if tc not in sys.path:
        sys.path.insert(0, tc)
    for _m in list(sys.modules):
        if _m == "f1_oracle_values":
            del sys.modules[_m]
    import f1_oracle_values as V
    findings = []
    # 1.0 / 2.0 / 8.0 的 IEEE-754 双精度位型（符号+11 位指数+52 位尾数）
    def ieee64(sign, exp11, frac52):
        if not (0 < exp11 < 2047):
            return None
        return (sign << 63) | (exp11 << 52) | frac52
    if V.FO_ONE != ieee64(0, 0x3FF, 0):
        findings.append(("B5", 0, "FO_ONE", "1.0 的位型应为 0x3FF0000000000000"))
    if V.FO_TWO != ieee64(0, 0x400, 0):
        findings.append(("B5", 0, "FO_TWO", "2.0 的位型应为 0x4000000000000000"))
    # 1.0 + 2.0 = 3.0：3.0 的指数 = 0x3FF + 1 = 0x400（因为 3 = 1.5×2^1）
    if V.FO_EIGHT != ieee64(0, 0x402, 0):
        findings.append(("B5", 0, "FO_EIGHT", "8.0 = 1.0×2^3 的位型应为 0x402…"))
    # 1.0f / 2.0f 的单精度位型（符号+8 位指数+23 位尾数）
    def ieee32(sign, exp8, frac23):
        if not (0 < exp8 < 255):
            return None
        return (sign << 31) | (exp8 << 23) | frac23
    if V.FT_ONE != ieee32(0, 0x7F, 0):
        findings.append(("B5", 0, "FT_ONE", "1.0f 的位型应为 0x3F800000"))
    if V.FT_TWO != ieee32(0, 0x80, 0):
        findings.append(("B5", 0, "FT_TWO", "2.0f 的位型应为 0x40000000"))
    # tetra 装箱（D13）：高 32 位固定 0xFFFFFFFF
    if (V.EXP_FTADD_0PLUS1 >> 32) != 0xFFFFFFFF or \
            (V.EXP_FTADD_0PLUS1 & 0xFFFFFFFF) != V.FT_ONE:
        findings.append(("B5", 0, "EXP_FTADD_0PLUS1",
                         "0.0f+1.0f=1.0f 的 tetra 装箱应为 0xFFFFFFFF3F800000"))
    # 0.0f + 1.0f = 1.0f：低位必须等于 FT_ONE（纯整数恒等）
    if (V.FT_ZERO + V.FT_ONE) != V.FT_ONE:
        findings.append(("B5", 0, "FT_ZERO+FT_ONE", "0.0f+1.0f 必须 = 1.0f"))
    # D14 两个 unordered 位型必须不同且落在 NaN 空间（指数全 1、尾数非 0）
    for nm, val in (("D14_QUIET_UNORDERED", V.D14_QUIET_UNORDERED),
                    ("D14_SIGNAL_UNORDERED", V.D14_SIGNAL_UNORDERED)):
        if ((val >> 52) & 0x7FF) != 0x7FF or (val & ((1 << 52) - 1)) == 0:
            findings.append(("B5", 0, nm, "unordered 输出必须是 NaN 位型"))
    if V.D14_QUIET_UNORDERED == V.D14_SIGNAL_UNORDERED:
        findings.append(("B5", 0, "D14", "quiet / signaling unordered 位型不得相同"))
    # FCSR 域划分：ro / rw / sbz 必须两两不交且并集 = 64 位
    ro, rw, sbz = V.FCSR_RO_MASK, V.FCSR_RW_MASK, V.FCSR_SBZ_MASK
    if ro & rw or ro & sbz or rw & sbz:
        findings.append(("B5", 0, "FCSR masks", "ro/rw/sbz 三域必须两两不交"))
    if ro | rw | sbz != 0xFFFFFFFFFFFFFFFF:
        findings.append(("B5", 0, "FCSR masks", "ro|rw|sbz 必须覆盖全部 64 位"))
    # 复位值：rw 域全 0，RO 域取合约常量
    if V.FCSR_RESET_VALUE & rw:
        findings.append(("B5", 0, "FCSR_RESET_VALUE", "复位值的 rw 域必须全 0"))
    if (V.FCSR_RESET_VALUE & ro) != (V.FCSR_RO_VALUE & ro):
        findings.append(("B5", 0, "FCSR_RESET_VALUE", "复位值的 RO 域必须等于合约常量"))
    # fcsr_value 的整数可复算性
    for rm, code in (("RNE", 0), ("RTZ", 1), ("RDN", 2), ("RUP", 3)):
        for flag in ("NV", "DZ", "OF", "UF", "NX"):
            bits = 1 << ("NV DZ OF UF NX".split().index(flag))
            got = V.fcsr_value(code, bits)
            want = (V.FCSR_RO_VALUE & V.FCSR_RO_MASK) | (code << 16) | bits
            if got != want:
                findings.append(("B5", 0, "fcsr_value(%s,%s)" % (rm, flag),
                                 "与整数重算不一致：%s vs %s"
                                 % (hex(got), hex(want))))
    return findings


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument(
        "--root", default=REPO_ROOT,
        help="被扫描的仓库根；反例注入时指向 /tmp 下的合成树（AGENTS.md："
             "反例注入可在临时树操作，不必污染真实工作区）")
    args = ap.parse_args(argv)
    root = os.path.abspath(args.root)

    results = []
    files = _files(root)
    for rel in files:
        data_only = rel.endswith(".yaml")
        for f in scan_file(root, rel, data_only=data_only):
            results.append({"file": rel, "rule": f[0], "line": f[1],
                            "snippet": f[2], "message": f[3]})
    results.extend({"file": "<B4>", "rule": f[0], "line": f[1],
                    "snippet": f[2], "message": f[3]}
                   for f in check_b4_whitelist(root))
    results.extend({"file": "<B5>", "rule": f[0], "line": f[1],
                    "snippet": f[2], "message": f[3]}
                   for f in check_b5_selfconsistent(root))

    if args.json:
        print(json.dumps({"checked": files, "findings": results},
                         ensure_ascii=False, indent=1))
    else:
        print("F1 ORACLE IO: scanned %d file(s)" % len(files))
        for rel in files:
            print("  - %s" % rel)
        print("B1 forbidden-oracle / B2 host-float / B3 spec-body-read "
              "/ B4 self-proof / B5 bit-pattern self-check")
        if results:
            for r in results:
                print("VIOLATION %s %s:%d: %s  | %s"
                      % (r["rule"], r["file"], r["line"], r["message"],
                         r["snippet"]), file=sys.stderr)
            print("check_f1_oracle_io: FAILED (%d violation(s))"
                  % len(results), file=sys.stderr)
            return 1
        print("check_f1_oracle_io: OK (0 violations; F1 expectations are "
              "integer-derived and implementation-independent)")
    return 1 if results else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
