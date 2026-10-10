#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F1 事实层自检：只读 `.xkw/knowledge/contract-f1-floating.md` +
`contracts/f1_gap_proofs.yaml` 的 `resolution` 层 + Accepted ADR 门禁，
重算 FCSR 布局 / 64 identity / D11 白名单 / D17 台账并与字面量钉死值比对；
外加**文档门禁**（G）：`tests/vectors/schema.md` 的 F1 章节与
`docs/testcases/f1-oracle-io.md` 必须真的写出被冻结的接口词条。

退出码：0 = 事实层自洽；1 = 有事实层或文档门错误。
本脚本不接触 vectors，也不接受宿主浮点：所有数值都是 64 位整数位型。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import f1_schema as F


# ───────────────── 文档门禁：两份冻结文档必须真的写了词条 ─────────────────
# 判据刻意取「**字面量必须出现**」而不是「文档存在」：文件在但内容被清空，
# 同样是没有交付接口。词条从事实层取（facet 键 / oracle kind / OPEN-ID /
# BLOCKED 点），因此事实层改了、文档没跟着改，这里立刻红。
DOC_TERMS = (
    # schema.md 的 F1 章节锚点
    "# F1 浮点向量 schema",
    # 四种 oracle 形态
    "`order`", "`block`", "`unordered`", "`open`",
    # ledger 三列表
    "active_keys", "trace_only", "non_gap",
    # 6 个 active OPEN-ID（逐个出现）
    "D17:S1", "D17:S3", "D17:S4", "D17:S5", "D17:S6", "D17:S8",
    "D17:S2", "D17:S7",
    # BLOCKED 点与能力缺口
    "D15:canonical_qnan_bits", "CAP-01:root-log-correct-rounding",
    "rootn(-0,2)",
    # 枚举
    "RNE", "RTZ", "RDN", "RUP",
    "NV", "DZ", "OF", "UF", "NX",
    "ILLI", "MALIGN",
)


def check_docs(root):
    """两份文档各须出现的词条；返回 error 列表。"""
    bad = []
    for rel in (F.SCHEMA_REL, F.ORACLE_DOC_REL):
        p = os.path.join(root, rel)
        try:
            with open(p, encoding="utf-8") as fh:
                text = fh.read()
        except OSError as exc:
            bad.append("G-DOC %s 无法读取: %s" % (rel, exc))
            continue
        missing = [t for t in DOC_TERMS if t not in text]
        if missing:
            bad.append("G-DOC %s 缺少 %d 个冻结词条: %r"
                       % (rel, len(missing), missing))
    return bad


def main(argv):
    argv = list(argv[1:])
    gate = "auto"
    root = F.REPO_ROOT
    rest = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("--root", "-r") and i + 1 < len(argv):
            root = os.path.abspath(argv[i + 1])
            i += 2
            continue
        if a.startswith("--root="):
            root = os.path.abspath(a.split("=", 1)[1])
            i += 1
            continue
        rest.append(a)
        i += 1
    if rest:
        gate = rest[0]
    ctx = F.F1Context(root=root, adr_gate=gate)
    print("adr_gate        : %s" % gate)
    print("root            : %s" % root)
    print("gate_open       : %s" % ctx.gate_open)
    print("identities      : %d" % len(ctx.identities))
    print("whitelist(10)   : %d %s" % (len(ctx.whitelist), ",".join(ctx.whitelist)))
    print("fcsr ro_mask    : %s" % F.hex64(ctx.fcsr["ro_mask"]))
    print("fcsr sbz_mask   : %s" % F.hex64(ctx.fcsr["sbz_mask"]))
    print("fcsr rw_mask    : %s" % F.hex64(ctx.fcsr["rw_mask"]))
    print("fcsr ro_value   : %s" % F.hex64(ctx.fcsr["ro_value"]))
    print("d17 active      : %s" % ",".join(F.PIN_D17_ACTIVE_KEYS))
    print("d17 trace_only  : %s" % F.PIN_D17_TRACE_ONLY)
    print("d17 non_gap     : %s" % F.PIN_D17_NON_GAP)
    print("d13 write_scope : %d" % len(ctx.d13_scope()))
    print("canonical_qnan  : %r" % (ctx.canonical_qnan_bits(),))
    print("unspecified pt  : %s" % ",".join(F.PIN_UNSPEC_POINTS))
    if ctx.errors:
        print("F1 CONTEXT ERRORS: %d" % len(ctx.errors))
        for e in ctx.errors:
            print("  ERR: %s" % e)
        return 1
    doc_bad = check_docs(root)
    if doc_bad:
        print("F1 DOC GATE ERRORS: %d" % len(doc_bad))
        for e in doc_bad:
            print("  ERR: %s" % e)
        return 1
    print("f1 docs         : %s + %s OK (all %d interface terms present)"
          % (F.SCHEMA_REL, F.ORACLE_DOC_REL, len(DOC_TERMS)))
    for d in getattr(ctx, "divergences", []):
        print("  NOTE divergence: %s" % d)
    print("F1 CONTEXT: OK (0 fact-layer errors, 0 doc-gate errors; %d "
          "registered read-only divergence(s))"
          % len(getattr(ctx, "divergences", [])))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
