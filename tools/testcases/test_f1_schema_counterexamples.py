#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_f1_schema_counterexamples.py — F1 冻结 schema 的**反例门控**自证。

AGENTS.md「验证脚本反例门控」：凡用于验收的检查器，必须能对**注入的反例**
失败。只跑一遍见 PASS 不算证据。本脚本逐条做：

  1. 建一棵**临时树**（``/tmp/opencode/TESTCASES-101t/reviewer/inject/``，见
     任务书「反例、还原与记录」），把
     ``contracts/`` + ``.xkw/knowledge/`` + ``tools/testcases/*.py`` 软链/复制
     过去，把 ``tests/vectors/f1/`` **复制**进去；
  2. 对每一类反例，在临时树上注入一处缺陷；
  3. 断言 validator / checker **非零退出**且报出**预期**的规则编号；
  4. 删除临时树、断言仓库工作区 ``git status`` 与注入前**逐字相同**。

为什么在临时树注入：真实工作区有 59 条用户既有改动，在其上注入再「还原」
一旦漏还原就会污染别人的基线（``QEMU-008t``/``QEMU-011t`` 的教训）。临时树
注入天然满足「不得在污染的工作区上得出验收结论」。

反例类别（每条都对应一个检查组；缺一条即视为该组无 FAIL 路径）：

  V1  rf 索引越界（rf64）                       → C1
  V2  rf 键形非法（rf1a）                        → C1
  V3  rf 值非 64 位 hex（'3.0'）                → C2
  V4  rf0 被双写进 rf bank                       → C3
  V5  非法 flag 名（XX / 大小写 Nv）             → D2
  V6  from_reset 却非 RNE                        → D5
  V7  observed_mask 吞掉 rw 域                    → D3
  V8  observed_mask 宣称 SBZ 位                  → D3
  V9  fcsr.value 与独立重算不符                  → D4
  V10 input 侧断言 fcsr.value                    → D6
  V11 fault 与 expected_state 并存               → E1
  V12 active facet 却带 open_ids                 → E3
  V13 blocked facet 缺 open_ids                  → E4
  V14 缺 facet cite / cite 不指名 authority      → F1
  V15 未知 identity / identity≠insn             → A1 / A2
  V16 active_keys 里塞 D17:S2 或 D17:S7          → F3
  V17 blocked_points 不在词表                    → G1
  V18 unspecified 点却给出唯一 expected          → G3
  V19 源寄存器未预置                             → H5
  V20 块 EA 写错                                 → H4
  V21 编码与 identity 不符                       → B2
  V22 oracle 与 expected_state 不一致            → O4
  V23 半观测缺 high32                            → O3
  V24 oracle.kind 未知                          → O1
  V25 缺顶层字段                                 → TOP-LEVEL
  V26 顶层 status 非 active                      → A5
  V27 语义值改错：D14 unordered 位型               → I3
  V28 语义值改错：D13 tetra 高半部                → I2
  V29 语义值改错：D12 非自动置位                  → I4
  V30 semantics blocked 却断言目的寄存器          → I8
  V31 合法编码却期望 ILLI（S3）                  → I7
  V32 树级：D17:S2 失去可追踪性                   → TREE
  V33 树级：重复 case id                          → DUPLICATE case id
  V34 ADR 门禁：--adr-gate closed                → F2
  V35 oracle 独立性：注入 math.sqrt              → B2
  V36 oracle 独立性：注入伪造的期望值常量          → B5
  V37 oracle 独立性：生成器反读向量数据            → B4
  V38 独立重算：自洽但错误的期望值（YAML 自身一致，
     validator 静态检查查不出）                   → MISMATCH
  V39 文档门禁：schema.md 里的冻结词条被删        → G-DOC

（编号与 `INJECTIONS` / `plan` / `oracle_io_plan` / `recompute_plan` /
`doc_plan` 的 tag 一致，运行时逐条打印实际顺序。）
`V34` 用 `--adr-gate closed` 走**不注入数据、只关门禁**的路径；`V38` 跑的是
`verify_f1_expected_values.py`（纯整数 IEEE-754 独立重算器）；`V39` 跑的是
`check_f1_context.py`（含 G-DOC 文档门禁）；其余都在临时树上改一处，并逐条用
树内文件 sha256 变化**证明注入非空**。

用法：
  python3 tools/testcases/test_f1_schema_counterexamples.py
  python3 tools/testcases/test_f1_schema_counterexamples.py --keep   # 保留临时树

退出码：0 = 全部反例都被拒且工作区未变；1 = 有反例**未被拒**（= 检查器有洞）
或工作区被污染。
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

TMP_BASE = os.path.join("/tmp/opencode/TESTCASES-101t", "reviewer", "inject")
REL_F1 = os.path.join("tests", "vectors", "f1")
REL_TC = os.path.join("tools", "testcases")

CODE_FILES = ("f1_schema.py", "f1_cases.py", "f1_oracle_values.py",
              "generate_f1_schema_fixtures.py", "check_f1_context.py",
              "check_f1_oracle_io.py", "verify_f1_expected_values.py")
GEN = "generate_f1_schema_fixtures.py"


# ─────────────────────────── 临时树 ───────────────────────────
def build_tree(dst):
    """搭一棵可独立运行的合成树（只复制，不软链——软链会让注入改到真仓库）。"""
    shutil.copytree(os.path.join(REPO, REL_TC), os.path.join(dst, REL_TC))
    for name in os.listdir(os.path.join(dst, REL_TC)):
        if name not in CODE_FILES and name != "validate_vectors.py":
            p = os.path.join(dst, REL_TC, name)
            if os.path.isfile(p):
                os.remove(p)
    shutil.copytree(os.path.join(REPO, "contracts"),
                    os.path.join(dst, "contracts"))
    kd = os.path.join(dst, ".xkw", "knowledge")
    os.makedirs(kd, exist_ok=True)
    for name in os.listdir(os.path.join(REPO, ".xkw", "knowledge")):
        if name.startswith("adr-") or name.startswith("contract-f1"):
            shutil.copy2(os.path.join(REPO, ".xkw", "knowledge", name),
                         os.path.join(kd, name))
    tv = os.path.join(dst, "tests", "vectors")
    os.makedirs(tv, exist_ok=True)
    # inventory.md + isa/*.yaml 是 M1 侧：validate_vectors.py 启动时要求它们存在，
    # 否则 M1 覆盖门控会先于 F1 报错，反例门控就测不到 F1。
    shutil.copy2(os.path.join(REPO, "tests", "vectors", "inventory.md"),
                 os.path.join(tv, "inventory.md"))
    shutil.copytree(os.path.join(REPO, "tests", "vectors", "isa"),
                    os.path.join(tv, "isa"))
    shutil.copytree(os.path.join(REPO, REL_F1), os.path.join(dst, REL_F1))
    # 两份冻结文档：G-DOC 门禁要读它们（缺文件会报「无法读取」而不是
    # 「缺词条」，那样反例注入的证据会变弱，所以照原样复制过来）。
    shutil.copy2(os.path.join(REPO, "tests", "vectors", "schema.md"),
                 os.path.join(tv, "schema.md"))
    os.makedirs(os.path.join(dst, "docs", "testcases"), exist_ok=True)
    shutil.copy2(os.path.join(REPO, "docs", "testcases", "f1-oracle-io.md"),
                 os.path.join(dst, "docs", "testcases", "f1-oracle-io.md"))
    return dst


def run_validator(tree, gate="auto"):
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        [sys.executable, os.path.join(tree, REL_TC, "validate_vectors.py"),
         "--adr-gate", gate],
        capture_output=True, text=True, env=env, cwd=tree)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def run_oracle_io(tree):
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        [sys.executable, os.path.join(REPO, REL_TC, "check_f1_oracle_io.py"),
         "--root", tree],
        capture_output=True, text=True, env=env, cwd=REPO)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def run_expected(tree):
    """在临时树上跑**独立重算器** verify_f1_expected_values.py。

    注意：用的是**临时树里那份**脚本（`REPO/REL_TC/...` 那份属于真实工作区，
    反例注入不得改它），且必须显式给 ``--root``——脚本的默认 root 是按
    ``__file__`` 推的，脱离仓库后不存在。
    """
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        [sys.executable, os.path.join(tree, REL_TC,
                                      "verify_f1_expected_values.py"),
         "--root", tree],
        capture_output=True, text=True, env=env, cwd=tree)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def run_context(tree):
    """在临时树上跑事实层自检 `check_f1_context.py`（含 G-DOC 文档门禁）。"""
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        [sys.executable, os.path.join(tree, REL_TC, "check_f1_context.py"),
         "--root", tree],
        capture_output=True, text=True, env=env, cwd=tree)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def git_status(repo=REPO):
    p = subprocess.run(["git", "status", "--porcelain=v1",
                        "--untracked-files=all"],
                       capture_output=True, text=True, cwd=repo)
    return p.stdout


def _tree_hashes(tree):
    """临时树里所有文件的 sha256（用于「注入是否真的改了东西」的自证）。"""
    import hashlib
    out = {}
    for base, _dirs, files in os.walk(tree):
        for f in files:
            p = os.path.join(base, f)
            rel = os.path.relpath(p, tree)
            with open(p, "rb") as fh:
                out[rel] = hashlib.sha256(fh.read()).hexdigest()
    return out


# ─────────────────────────── 注入器 ───────────────────────────
def _yaml_load(path):
    import yaml
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _yaml_dump(path, data):
    """回写 YAML。**必须**保住十六进制字符串的引号。

    `yaml.dump` 会把 `'0x3FF0…'` 写成裸的 `0x3FF0…`，YAML 再读回来就成了
    **整数**——于是注入的「反例」被一堆 C2（值不是 hex 字符串）淹没，真正的
    目标规则编号反而看不见了。所以凡是长得像数字/hex 的字符串一律单引号。
    """
    import re as _re
    import yaml

    class D(yaml.SafeDumper):
        pass

    _AMBIG = _re.compile(r"^(0x[0-9A-Fa-f]+|[-+]?[0-9][0-9_]*(\.[0-9_]*)?"
                         r"([eE][-+]?[0-9]+)?|0o[0-7]+|0b[01]+|"
                         r"null|Null|NULL|~|true|false|yes|no|on|off)$")

    def _str(dumper, s):
        if _AMBIG.match(s):
            return dumper.represent_scalar("tag:yaml.org,2002:str", s,
                                           style="'")
        return dumper.represent_scalar("tag:yaml.org,2002:str", s)

    D.add_representer(str, _str)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("# injected counterexample (TESTCASES-101t self-test)\n")
        yaml.dump(data, fh, Dumper=D, allow_unicode=True, sort_keys=False,
                  default_flow_style=False, width=100)


def _valid_path(tree):
    return os.path.join(tree, REL_F1, "valid", "f1-schema-valid.yaml")


def _edit_case(tree, cid, fn):
    """在 valid/ 树里就地改一条正样例（临时树内，退出即删）。"""
    p = _valid_path(tree)
    cases = _yaml_load(p)
    hit = [c for c in cases if c.get("id") == cid]
    if len(hit) != 1:
        raise AssertionError("case %r not uniquely found (%d)" % (cid, len(hit)))
    fn(hit[0])
    _yaml_dump(p, cases)


F_S2 = "D17:S2"
A = "f1-foadd-basic-rf-index"
DIV = "f1-ftdiv-rounding-rtz-dz"
FOQCMP = "f1-foqcmp-unordered-d14"
FTADD = "f1-ftadd-tetra-high-half-d13"
LDO = "f1-ldo-rf-d12-non-automatic"
FTCLS = "f1-ftcls-immu6-neq1-illi-priority"
FOROOT = "f1-foroot-negative-zero-unspecified"
LDT = "f1-ldt-rf-malign"
LDMBLK = "f1-ldm-t-block-ea0-increment"

# (编号, 说明, 期望出现在输出里的规则标记, 注入函数)
INJECTIONS = [
    ("V1", "rf 索引越界 rf64", "C1",
     lambda t: _edit_case(t, A, lambda c: c["input_state"]["rf"].update(
         {"rf64": "0x3FF0000000000000"}))),
    ("V2", "rf 键形非法 rf1a", "C1",
     lambda t: _edit_case(t, A, lambda c: c["input_state"]["rf"].update(
         {"rf1a": "0x3FF0000000000000"}))),
    ("V3", "rf 值非 64 位 hex", "C2",
     lambda t: _edit_case(t, A, lambda c: c["input_state"]["rf"].update(
         {"rf2": "3.0"}))),
    ("V4", "rf0 被双写进 rf bank", "C3",
     lambda t: _edit_case(t, A, lambda c: c["expected_state"]["rf"].update(
         {"rf0": "0x7FF800007FC00000"}))),
    ("V5", "非法 flag 名 XX", "D2",
     lambda t: _edit_case(t, DIV, lambda c: c["expected_state"]["fcsr"].update(
         {"flags": ["DZ", "XX"]}))),
    ("V6", "from_reset 却非 RNE", "D5",
     lambda t: _edit_case(t, A, lambda c: c["input_state"]["fcsr"].update(
         {"rounding_mode": "RUP", "from_reset": True}))),
    ("V7", "observed_mask 吞掉 rw 域", "D3",
     lambda t: _edit_case(t, A, lambda c: c["expected_state"]["fcsr"].update(
         {"observed_mask": "0xFFF8000000000000"}))),
    ("V8", "observed_mask 宣称 SBZ 位", "D3",
     lambda t: _edit_case(t, A, lambda c: c["expected_state"]["fcsr"].update(
         {"observed_mask": "0xFFFFFFFFFFFFFFFF"}))),
    ("V9", "fcsr.value 与重算不符", "D4",
     lambda t: _edit_case(t, DIV, lambda c: c["expected_state"]["fcsr"].update(
         {"value": "0x7FF800007FC10000"}))),
    ("V10", "input 侧断言 fcsr.value", "D6",
     lambda t: _edit_case(t, A, lambda c: c["input_state"]["fcsr"].update(
         {"value": "0x7FF800007FC00000"}))),
    ("V11", "fault 与 expected_state 并存", "E1",
     lambda t: _edit_case(t, LDT, lambda c: c.update(
         {"expected_state": {"rd": {}, "rb": {}, "ra": {}, "rf": {},
                             "fcsr": None, "memory": []}}))),
    ("V12", "active facet 带 open_ids", "E3",
     lambda t: _edit_case(t, A, lambda c: c["facets"]["encoding"].update(
         {"open_ids": ["D17:S1"]}))),
    ("V13", "blocked facet 缺 open_ids", "E4",
     lambda t: _edit_case(t, "f1-fosclb-d17s5-blocked-facet",
                           lambda c: c["facets"]["semantics"].pop("open_ids"))),
    ("V14", "facet cite 不指名 authority", "F1",
     lambda t: _edit_case(t, A, lambda c: c["facets"]["encoding"].update(
         {"cite": "see the spec"}))),
    ("V15", "identity 与 insn 不一致", "A2",
     lambda t: _edit_case(t, A, lambda c: c.update({"insn": "fomul"}))),
    ("V16", "active_keys 塞 D17:S2", "F3",
     lambda t: _edit_case(t, A, lambda c: c["ledger_refs"]["active_keys"].append(
         "D17:S2"))),
    ("V17", "blocked_points 不在词表", "G1",
     lambda t: _edit_case(t, A, lambda c: c["blocked_points"].append(
         "D99:invented"))),
    ("V18", "unspecified 点却给唯一 expected", "G3",
     lambda t: _edit_case(t, FOROOT, lambda c: c.update(
         {"expected_state": {"rd": {}, "rb": {}, "ra": {},
                             "rf": {"rf1": "0x3FF0000000000000"},
                             "fcsr": None, "memory": []}}))),
    ("V19", "源寄存器未预置", "H5",
     lambda t: _edit_case(t, A, lambda c: c["input_state"]["rf"].pop("rf2"))),
    ("V20", "块 EA 写错", "H4",
     lambda t: _edit_case(t, LDMBLK, lambda c: c["oracle"]["elements"][1].update(
         {"address": "0xFFFF00000030"}))),
    ("V21", "编码与 identity 不符", "B2",
     lambda t: _edit_case(t, A, lambda c: c["encoding"].update(
         {"word": "0x44640000"}))),
    ("V22", "oracle 与 expected_state 不一致", "O4",
     lambda t: _edit_case(t, A, lambda c: c["oracle"]["records"][0].update(
         {"reg": {"bank": "rf", "index": 1,
                  "value": "0x4020000000000001"}}))),
    ("V23", "半观测缺 high32", "O3",
     lambda t: _edit_case(t, FTADD, lambda c: c["oracle"]["records"][0][
         "reg"].pop("high32"))),
    ("V24", "oracle.kind 未知", "O1",
     lambda t: _edit_case(t, A, lambda c: c["oracle"].update(
         {"kind": "whatever"}))),
    ("V25", "缺顶层字段", "TOP-LEVEL",
     lambda t: _edit_case(t, A, lambda c: c.pop("ledger_refs"))),
    ("V26", "status 非 active", "A5",
     lambda t: _edit_case(t, A, lambda c: c.update({"status": "retired"}))),
    ("V27", "语义值改错：D14 unordered 位型", "I3",
     lambda t: _edit_case(t, FOQCMP, lambda c: c["expected_state"]["rd"].update(
         {"rd1": "0x7FF0000000000001"}))),
    ("V28", "语义值改错：D13 tetra 高半部", "I2",
     lambda t: _edit_case(t, FTADD, lambda c: c["expected_state"]["rf"].update(
         {"rf1": "0x000000003F800000"}))),
    ("V29", "语义值改错：D12 非自动置位", "I4",
     lambda t: _edit_case(t, LDO, lambda c: c["expected_state"]["fcsr"].update(
         {"flags": ["NV"]}))),
    ("V30", "semantics blocked 却断言目的寄存器", "I8",
     lambda t: _edit_case(t, "f1-foadd-canonical-qnan-blocked",
                           lambda c: c["expected_state"].update(
                               {"rf": {"rf1": "0x7FF8000000000000"}}))),
]


def _inject_v31_legal_encoding_illI(tree):
    """V31：把 ftcls 的 immu6 改成合法的 1，但 case 仍期望 ILLI。"""
    _edit_case(tree, FTCLS, lambda c: c["encoding"].update(
        {"word": "0x44001041"}))


def _inject_v32_drop_s2_trace(tree):
    """V32：抽掉唯一的 D17:S2 trace_only 引用 → 树级不可追踪。"""
    p = _valid_path(tree)
    cases = _yaml_load(p)
    for c in cases:
        lr = c.get("ledger_refs") or {}
        if F_S2 in (lr.get("trace_only") or []):
            lr["trace_only"] = []
    _yaml_dump(p, cases)


def _inject_v33_duplicate_id(tree):
    """V33：整树里出现两个同 id 的 case。"""
    p = _valid_path(tree)
    cases = _yaml_load(p)
    import copy
    cases.append(copy.deepcopy(cases[0]))
    _yaml_dump(p, cases)


def _inject_v34_math_sqrt(tree):
    """V34：oracle 独立层里混入宿主 libm。"""
    p = os.path.join(tree, REL_TC, "f1_oracle_values.py")
    with open(p, encoding="utf-8") as fh:
        text = fh.read()
    text = text.replace("# ── 64 位（fo/octa）位型 ──",
                        "import math\n\n_SQRT_HOST = math.sqrt(2.0)\n\n"
                        "# ── 64 位（fo/octa）位型 ──", 1)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(text)


def _inject_v35_fake_constant(tree):
    """V35：把 FO_ONE 的位型改成错的（伪造期望值）。"""
    p = os.path.join(tree, REL_TC, "f1_oracle_values.py")
    with open(p, encoding="utf-8") as fh:
        text = fh.read()
    text = text.replace("FO_ONE = 0x3FF0000000000000",
                        "FO_ONE = 0x3FF0000000000001", 1)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(text)


def _inject_v36_generator_selfproof(tree):
    """V36：生成器改成反读已入库的向量数据（期望值自证）。"""
    p = os.path.join(tree, REL_TC, GEN)
    with open(p, encoding="utf-8") as fh:
        text = fh.read()
    anchor = "import f1_schema as F"
    assert anchor in text, "生成器锚点行变了，注入会变空操作"
    i = text.index(anchor)
    eol = text.index("\n", i) + 1
    text = (text[:eol] + "import yaml as _y\n"
            "_SELF = _y.safe_load(open(os.path.join(\n"
            "    os.path.dirname(os.path.abspath(__file__)),\n"
            "    '..', '..', 'tests', 'vectors', 'f1', 'valid',\n"
            "    'f1-schema-valid.yaml')))\n" + text[eol:])
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(text)


def _inject_v38_wrong_expected_value(tree):
    """V38：把 1.0+2.0 的期望值改错，且让 YAML **自身保持自洽**。

    这是最强的一条反例：`expected_state.rf.rf1` 与 `oracle.records[0].reg.value`
    一起改成同一个错值，所以
      * validator 的 O4（oracle ↔ expected_state 一致性）查不出来；
      * I2/I3/I4（D13 装箱 / D14 位型 / D12 flag）也管不到 64 位 foadd 的
        算术结果本身。
    唯一能抓住它的是 `verify_f1_expected_values.py` 里的**纯整数 IEEE-754
    重算**（1.0 + 2.0 = 3.0 = 0x4008000000000000）。
    """

    def _mutate(c):
        c["expected_state"]["rf"]["rf1"] = "0x4008000000000001"
        c["oracle"]["records"][0]["reg"]["value"] = "0x4008000000000001"

    _edit_case(tree, A, _mutate)


def _inject_v39_strip_frozen_term(tree):
    """V39：从 schema.md 里删掉一个冻结词条（`D17:S5`）。

    文档门禁的判据是「字面量必须出现」。文件在但接口词条被删，与文件根本不存在
    一样是**没有交付接口**。这一条同时证明 G-DOC 不是「文件存在即绿」。
    """
    p = os.path.join(tree, "tests", "vectors", "schema.md")
    with open(p, encoding="utf-8") as fh:
        text = fh.read()
    n = text.count("D17:S5")
    assert n >= 2, "锚点词条在 schema.md 出现 %d 次，注入会变空操作" % n
    # 必须**全部**替换：只改第一处，词条仍在文档里，门禁当然还是绿的——
    # 那正是「门禁有洞」而不是「注入生效」。
    text = text.replace("D17:S5", "D17:Sx")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(text)


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", action="store_true",
                    help="保留临时树（调试用；默认退出前删除）")
    args = ap.parse_args(argv)

    baseline = git_status()
    results = []
    # 每次运行用**独立**子目录：并发/被中断的另一次运行不会把本轮的 base 删掉
    # （共享 base 会被上一次运行的收尾 rmtree 掀掉，报 FileNotFoundError）。
    os.makedirs(TMP_BASE, exist_ok=True)
    tmp_parent = tempfile.mkdtemp(prefix="run-", dir=TMP_BASE)

    plan = [(tag, desc, marker, fn, "auto") for tag, desc, marker, fn
            in INJECTIONS]
    plan += [
        ("V31", "合法编码却期望 ILLI（S3）", "I7",
         _inject_v31_legal_encoding_illI, "auto"),
        ("V32", "D17:S2 失去可追踪性", "TREE", _inject_v32_drop_s2_trace,
         "auto"),
        ("V33", "重复 case id", "DUPLICATE case id", _inject_v33_duplicate_id,
         "auto"),
        ("V34", "ADR 门禁关闭（--adr-gate closed）", "F2", None, "closed"),
    ]
    oracle_io_plan = [
        ("V35", "oracle 层混入宿主 math.sqrt", "B2", _inject_v34_math_sqrt),
        ("V36", "伪造的期望值常量", "B5", _inject_v35_fake_constant),
        ("V37", "生成器反读向量数据（自证）", "B4",
         _inject_v36_generator_selfproof),
    ]
    recompute_plan = [
        ("V38", "自洽但错误的期望值（独立重算抓）", "MISMATCH",
         _inject_v38_wrong_expected_value),
    ]
    doc_plan = [
        ("V39", "冻结词条被删（G-DOC 文档门禁）", "G-DOC",
         _inject_v39_strip_frozen_term),
    ]

    print("F1 COUNTEREXAMPLE SELF-TEST")
    print("  temp tree base : %s" % tmp_parent)
    print("  repo baseline  : %d git-status line(s)" % len(
        baseline.splitlines()))
    print("  cases to prove : %d validator + %d oracle-io + %d recompute"
          " + %d doc" % (len(plan), len(oracle_io_plan), len(recompute_plan),
                         len(doc_plan)))
    print("")

    # ── 干净树必须全绿（否则「注入后变红」不能证明任何事） ──
    clean = tempfile.mkdtemp(prefix="clean-", dir=tmp_parent)
    try:
        shutil.rmtree(clean)
        build_tree(clean)
        rc, out = run_validator(clean)
        if rc != 0:
            print("FATAL: 干净临时树上的 validator 就不绿（rc=%d），"
                  "反例门控无意义：" % rc)
            print(out[-2000:])
            return 1
        print("[0/…] clean tree: validator rc=0  (baseline for injection)")
        rc0, out0 = run_oracle_io(clean)
        if rc0 != 0:
            print("FATAL: 干净树上的 check_f1_oracle_io 就不绿（rc=%d）" % rc0)
            print(out0[-2000:])
            return 1
        print("[0/…] clean tree: check_f1_oracle_io rc=0")
        rce, oute = run_expected(clean)
        if rce != 0:
            print("FATAL: 干净树上的 verify_f1_expected_values 就不绿（rc=%d）"
                  % rce)
            print(oute[-2000:])
            return 1
        print("[0/…] clean tree: verify_f1_expected_values rc=0")
        rcc, outc = run_context(clean)
        if rcc != 0:
            print("FATAL: 干净树上的 check_f1_context 就不绿（rc=%d）" % rcc)
            print(outc[-2000:])
            return 1
        print("[0/…] clean tree: check_f1_context rc=0")
    finally:
        if not args.keep:
            shutil.rmtree(clean, ignore_errors=True)

    total = len(plan) + len(oracle_io_plan) + len(recompute_plan) \
        + len(doc_plan)
    done = 0
    for tag, desc, marker, fn, gate in plan:
        tree = tempfile.mkdtemp(prefix="t-", dir=tmp_parent)
        try:
            shutil.rmtree(tree)
            build_tree(tree)
            before = _tree_hashes(tree)
            if fn is not None:
                fn(tree)
            after = _tree_hashes(tree)
            changed = sorted(k for k in set(before) | set(after)
                             if before.get(k) != after.get(k))
            rc, out = run_validator(tree, gate=gate)
            done += 1
            hit = marker in out
            # 注入有效性：文件必须真的变了，否则「注入后仍全绿」是空注入
            effective = (fn is None) or bool(changed)
            ok = (rc != 0) and hit and effective
            results.append((tag, desc, rc, marker, hit, ok))
            print("[%2d/%d] %-4s %-42s rc=%d  marker %-18s %s%s"
                  % (done, total, tag, desc[:42], rc, marker,
                     "OK" if ok else "*** NOT REJECTED ***",
                     "" if effective else "  [EMPTY INJECTION: %s]"
                     % (changed or "no file changed")))
            if not ok:
                tail = [l for l in out.splitlines()
                        if marker in l or "FAILED" in l][:4]
                for l in tail:
                    print("        | %s" % l[:150])
        finally:
            if not args.keep:
                shutil.rmtree(tree, ignore_errors=True)

    for tag, desc, marker, fn in oracle_io_plan:
        tree = tempfile.mkdtemp(prefix="o-", dir=tmp_parent)
        try:
            shutil.rmtree(tree)
            build_tree(tree)
            before = _tree_hashes(tree)
            fn(tree)
            after = _tree_hashes(tree)
            changed = sorted(k for k in set(before) | set(after)
                             if before.get(k) != after.get(k))
            rc, out = run_oracle_io(tree)
            done += 1
            hit = marker in out
            ok = (rc != 0) and hit and bool(changed)
            results.append((tag, desc, rc, marker, hit, ok))
            print("[%2d/%d] %-4s %-42s rc=%d  marker %-18s %s%s"
                  % (done, total, tag, desc[:42], rc, marker,
                     "OK" if ok else "*** NOT REJECTED ***",
                     "" if changed else "  [EMPTY INJECTION]"))
            if not ok:
                for l in [l for l in out.splitlines() if "VIOLATION" in l][:3]:
                    print("        | %s" % l[:150])
        finally:
            if not args.keep:
                shutil.rmtree(tree, ignore_errors=True)

    for tag, desc, marker, fn in recompute_plan:
        tree = tempfile.mkdtemp(prefix="r-", dir=tmp_parent)
        try:
            shutil.rmtree(tree)
            build_tree(tree)
            before = _tree_hashes(tree)
            fn(tree)
            after = _tree_hashes(tree)
            changed = sorted(k for k in set(before) | set(after)
                             if before.get(k) != after.get(k))
            rc, out = run_expected(tree)
            done += 1
            hit = marker in out
            ok = (rc != 0) and hit and bool(changed)
            results.append((tag, desc, rc, marker, hit, ok))
            print("[%2d/%d] %-4s %-42s rc=%d  marker %-18s %s%s"
                  % (done, total, tag, desc[:42], rc, marker,
                     "OK" if ok else "*** NOT REJECTED ***",
                     "" if changed else "  [EMPTY INJECTION]"))
            if not ok:
                for l in [l for l in out.splitlines()
                          if marker in l or "FAILED" in l][:3]:
                    print("        | %s" % l[:150])
            else:
                # 附带证据：这类缺陷 validator 的静态检查抓不到（rc=0），
                # 只有独立重算能抓——否则「多跑一个脚本」没有意义。
                vrc, _ = run_validator(tree)
                print("        · 同树 validator rc=%d（静态检查查不出，"
                      "由独立重算器兜住）" % vrc)
        finally:
            if not args.keep:
                shutil.rmtree(tree, ignore_errors=True)

    for tag, desc, marker, fn in doc_plan:
        tree = tempfile.mkdtemp(prefix="d-", dir=tmp_parent)
        try:
            shutil.rmtree(tree)
            build_tree(tree)
            before = _tree_hashes(tree)
            fn(tree)
            after = _tree_hashes(tree)
            changed = sorted(k for k in set(before) | set(after)
                             if before.get(k) != after.get(k))
            rc, out = run_context(tree)
            done += 1
            hit = marker in out
            ok = (rc != 0) and hit and bool(changed)
            results.append((tag, desc, rc, marker, hit, ok))
            print("[%2d/%d] %-4s %-42s rc=%d  marker %-18s %s%s"
                  % (done, total, tag, desc[:42], rc, marker,
                     "OK" if ok else "*** NOT REJECTED ***",
                     "" if changed else "  [EMPTY INJECTION]"))
            if not ok:
                for l in [l for l in out.splitlines()
                          if "G-DOC" in l][:3]:
                    print("        | %s" % l[:150])
        finally:
            if not args.keep:
                shutil.rmtree(tree, ignore_errors=True)

    if not args.keep:
        shutil.rmtree(tmp_parent, ignore_errors=True)
        # 顺手回收本脚本自己建的一级 base（只删**空**目录：并发运行的另一次
        # 不会因此丢数据，而任务书要求「必须清理」）。
        try:
            os.rmdir(TMP_BASE)
            os.rmdir(os.path.dirname(TMP_BASE))
        except OSError:
            pass

    after = git_status()
    same = (after == baseline)
    print("")
    print("repo git status unchanged after %d injections: %s"
          % (len(results), "YES" if same else "NO"))
    if not same:
        import difflib
        for l in list(difflib.unified_diff(baseline.splitlines(),
                                           after.splitlines(),
                                           lineterm=""))[:20]:
            print("  %s" % l)

    n_bad = [r for r in results if not r[5]]
    print("RESULT: %d/%d counterexamples rejected with the expected rule "
          "marker" % (len(results) - len(n_bad), len(results)))
    if n_bad or not same:
        print("test_f1_schema_counterexamples: FAILED", file=sys.stderr)
        return 1
    print("test_f1_schema_counterexamples: OK (every acceptance checker has a "
          "real FAIL path; repo working tree untouched)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
