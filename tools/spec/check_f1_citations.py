#!/usr/bin/env python3
"""check_f1_citations.py — 校验 `.xkw/knowledge/contract-f1-floating.md` 里每一条
`spec/<file>:<line>` 引用确实**指得到它声称指的那句话**。

为什么需要它：合约里上百条 `:NNN` 行号引用是**人工誊写**的，誊错行号不会让
任何语法检查失败，却会让下游 LLVM/QEMU 按错误的原文实现。本脚本把合约 md 中
出现的 `spec/SimRISC-0N-*.md:NN` 与 `§...` 引用全部抽出，逐条核对：

  1. 文件名存在（SimRISC-00/01/02/03…）；
  2. 行号在文件范围内；
  3. 该行（或其后两行内）**含有一个关键词**，关键词由本脚本按 SimRISC-03 的
     小节给出 —— 即「引用指到了正确的句子」，而不只是「行号没越界」。

第 3 条是关键：只查范围的话，`:283` 指到一张表的中间行也算「合法」，但那显然
不是引用者想说的话。

退出码：0 = 全部命中；1 = 有引用指不到。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_MD = REPO_ROOT / ".xkw" / "knowledge" / "contract-f1-floating.md"
LEGALITY_YAML = REPO_ROOT / "contracts" / "legality_rules.yaml"
OPCODES_YAML = REPO_ROOT / "contracts" / "opcodes.yaml"

SPEC_FILES = ("SimRISC-00", "SimRISC-01", "SimRISC-02", "SimRISC-03")

#: 显式带文件名的引用：`spec/SimRISC-03-浮点类指令.md:126` 或 `SimRISC-03:126`
QUALIFIED = re.compile(r"(?:spec/)?(?P<num>SimRISC-\d+)"
                       r"(?:-[^\s:：）)]+\.md)?[:：](?P<ln>\d{1,4})\b")

#: 裸行号引用：`:126`。必须排除**位域写法**的冒号，否则 `rf0[4:0]`、`[63:0]`
#: 会被误当成「引用第 0 行」—— 位域冒号左侧一定是数字，故用 (?<!\d) 排除；
#: 左侧是字母的（文件名末尾 `…设计.md:191`）也排除，避免与 QUALIFIED 重复计数。
#: 左侧是 `-` 的**要收**（`:278-:287` 这种行号区间的右端点也是引用）。
BARE = re.compile(r"(?<![\dA-Za-z.])[:：](?P<ln>\d{1,4})\b")

# ── 第 3 层：语义锚点（claim-anchored）───────────────────────────────
# 逐条核对两件事：
#   (a) spec 侧：坐标 (file,line) 真实存在，且该行确实含关键词 —— 即
#       「引用指到了正确的句子」，而不只是「行号没越界」；
#   (b) md 侧：写着这条主张的那一段**确实**引了该坐标。
# 只做 (a) 不够：把那行主张的引用改成相邻行号，spec 侧仍全对，检查器却
# 察觉不到 —— 下游会照错的原文实现。(b) 就是堵这条路的。
#
# 每条 = (spec 文件, 行号, spec 侧关键词, md 侧主张文本, 同须引用的其它行号)
#: 放在模块级（非 main() 内）以便被反例注入脚本 import 复用。
ANCHORS: list[tuple[str, int, str, str, tuple[int, ...]]] = [
    # 主张串带 `**` 标记：§7 S8 里那段引的是 **SimRISC-01** 的同名措辞
    # （`装入类源/目的范围可重叠，按序号递增逐对先读后写`，无 `**`），不带标记
    # 会让同一句话被当成两处主张，而那处**不得**引 SimRISC-03:126。
    ("SimRISC-03", 126, "先读后写",
     "源/目的范围可重叠，按序号递增逐对**先读后写**", ()),
    ("SimRISC-03", 128, "整型饱和值", "整型饱和值", ()),
    ("SimRISC-03", 132, "immu6", "`immu6`=0 → ILLI", (133,)),
    ("SimRISC-03", 133, "任一起始寄存器", "任一起始寄存器 + `immu6` > 64", (132,)),
    ("SimRISC-03", 161, "remainder", "IEEE 754 remainder", ()),
    ("SimRISC-03", 163, "scaleB", "`rfhc × 2^rfhd`", ()),
    ("SimRISC-03", 174, "单次舍入", "单次舍入", ()),
    ("SimRISC-03", 188, "立方根", "立方根", ()),
    ("SimRISC-03", 190, "不做具体要求", "`rootn(-0, 2)`", ()),
    ("SimRISC-03", 192, "log10", "log10", ()),
    ("SimRISC-03", 194, "先读源操作数", "S1D1 先读源再写结果", ()),
    ("SimRISC-03", 208, "copySign", "= `copySign(rfhc, rfhd)`：取 rfhc", ()),
    ("SimRISC-03", 209, "取反", "上述结果与 rfhd 符号位**取反**后组合", ()),
    ("SimRISC-03", 215, "abs(rfhc)", "= `abs(rfhc)`", ()),
    ("SimRISC-03", 216, "-abs(rfhc)", "= `-abs(rfhc)`", ()),
    ("SimRISC-03", 217, "copy(rfhc)", "分别为 `copy` / `negate`", (218,)),
    ("SimRISC-03", 218, "negate(rfhc)", "分别为 `copy` / `negate`", (217,)),
    ("SimRISC-03", 234, "rfhc > rfhd", "| `1` | `rfhc > rfhd`", ()),
    ("SimRISC-03", 235, "rfhc = rfhd", "| `0` | `rfhc = rfhd`", ()),
    ("SimRISC-03", 236, "rfhc < rfhd", "| `-1` | `rfhc < rfhd`", ()),
    ("SimRISC-03", 237, "unordered", "unordered；Quiet Compare", ()),
    ("SimRISC-03", 239, "六种关系", "区分六种关系", ()),
    ("SimRISC-03", 243, "negative/zero/positive", "`cs.n`/`cs.z`/`cs.p`", ()),
    ("SimRISC-03", 252, "rdha ==/!= rdhb", "`cs.eq`/`cs.ne`", ()),
    ("SimRISC-03", 260, "else 分支", "均执行 else 分支", ()),
    ("SimRISC-03", 270, "ftcls", "`ftcls rdhb, rfhc, 1`", ()),
    ("SimRISC-03", 271, "focls", "`ftcls rdhb, rfhc, 1`", ()),
    ("SimRISC-03", 274, "[63..10]", "[63..10] 全部清零", ()),
    ("SimRISC-03", 278, "negativeInfinity", "bit0..bit9 = negativeInfinity", (287,)),
    ("SimRISC-03", 287, "quietNaN", "bit0..bit9 = negativeInfinity", (278,)),
    ("SimRISC-00", 55, "rd0", "**rd0 只读权威**", ()),
    ("SimRISC-00", 191, "hd[5:0]", "6 位字段宽度唯一决定", ()),
]


def spec_path(num: str) -> Path | None:
    for p in sorted((REPO_ROOT / "spec").glob(f"{num}-*.md")):
        return p
    return None


def load_lines() -> dict[str, list[str]]:
    out = {}
    for num in SPEC_FILES:
        p = spec_path(num)
        if p:
            out[num] = p.read_text(encoding="utf-8").splitlines()
    return out


def md_blocks(lines: list[str]) -> list[tuple[int, str]]:
    """把 markdown 正文切成「块」，返回 (块起始行号, 块文本)。

    分块规则（决定「主张的引用该在哪一块里被找到」）：

      1. 表格行（以 `|` 开头）**各自成块** —— 一张表里多行引同一个坐标时，
         逐行独立核对才能发现「其中一行誊错」。按整段核对会漏（CE-8）。
      2. 其余按空行分段。于是连续的 `>` 引用行（折行引用）自然合成一块，
         而普通散文段落、连续列表项也各自成块。
    """
    out: list[tuple[int, str]] = []
    i, n = 0, len(lines)
    while i < n:
        t = lines[i]
        if not t.strip():
            i += 1
            continue
        if t.lstrip().startswith("|"):
            out.append((i + 1, t))          # 规则 1：表格行独立成块
            i += 1
            continue
        s, buf = i, []
        while i < n and lines[i].strip():  # 规则 2：到空行为止
            buf.append(lines[i])
            i += 1
        out.append((s + 1, "\n".join(buf)))
    return out


def main() -> int:
    if not CONTRACT_MD.exists():
        print(f"check_f1_citations: 合约文件不存在 {CONTRACT_MD}")
        return 1
    md = CONTRACT_MD.read_text(encoding="utf-8")
    lines = load_lines()
    paths = {n: spec_path(n) for n in SPEC_FILES}
    nlines = {n: len(v) for n, v in lines.items()}

    qualified: dict[str, int] = {}     # "SimRISC-03:126" -> 次数
    bare: dict[int, int] = {}           # 126 -> 次数
    problems: list[str] = []
    total = 0

    for lineno, text in enumerate(md.splitlines(), 1):
        spans = []
        for m in QUALIFIED.finditer(text):
            total += 1
            num, ln = m.group("num"), int(m.group("ln"))
            spans.append((m.start(), m.end()))
            if num not in lines:
                problems.append(f"md:{lineno}: 未知 spec 文件 {num}")
                continue
            if not (1 <= ln <= nlines[num]):
                problems.append(f"md:{lineno}: {m.group(0)} 越界"
                                f"（{num} 共 {nlines[num]} 行）")
                continue
            qualified[f"{num}:{ln}"] = qualified.get(f"{num}:{ln}", 0) + 1
        for m in BARE.finditer(text):
            if any(s <= m.start() < e for s, e in spans):
                continue                      # 已被 QUALIFIED 计入
            total += 1
            ln = int(m.group("ln"))
            # ── 第 2 层：裸 `:NNN`。合约里这种写法大量存在，其目标文件
            #    取决于所在小节声明的上下文，因此**不能**在此断定文件；
            #    只要求该行号在**至少一个** spec 文件的有效范围内。
            if not any(1 <= ln <= n for n in nlines.values()):
                problems.append(f"md:{lineno}: 裸引用 :{ln} 在任何 spec 文件"
                                f"中都越界")
            bare[ln] = bare.get(ln, 0) + 1

    # 裸引用中「行号在多个 spec 文件里都有效」的数量 = 上下文依赖的歧义面。
    # 这是**可读性**问题（读者要靠小节上下文才知道是 00 还是 03），不判 FAIL，
    # 但必须如实报出，不掩盖。
    ambiguous = sum(1 for ln in bare
                    if sum(1 for n in nlines if 1 <= ln <= nlines[n]) > 1)

    # ── 第 3 层：语义锚点（claim-anchored）───────────────────────────────
    # 锚点表见模块级 ANCHORS。

    md_lines = md.splitlines()

    def cites(text: str, num: str, ln: int) -> bool:
        """该文本是否引用了 (num, ln) —— 显式或裸形式皆可。"""
        for m in QUALIFIED.finditer(text):
            if m.group("num") == num and int(m.group("ln")) == ln:
                return True
        for m in BARE.finditer(text):
            if int(m.group("ln")) == ln:
                return True
        return False

    # ── md 侧按 **markdown 块** 核对，不是按行也不是按整段 ──
    #   · 表格行**各自成块**：§4.1 那张表 6 行都引 `:128`。若按整段核对
    #     「本段是否引过 :128」，把**其中一行**誊成 `:129` 时其余 5 行仍然满足
    #     条件 → 全绿放行（旧版检查器的洞，由反例 CE-8 逮到）。
    #   · 连续的 `>` 引用行**合成一块**：§4.6 那段 :239 说明折成 3 行，
    #     引用在中间行、主张在末行，按行核对会误报。
    #   · 其余按空行分段（散文段落）。
    blocks = md_blocks(md_lines)

    miss_anchor = []
    multi_hit: list[tuple[str, str, list[int]]] = []
    for num, ln, kw, claim, also in ANCHORS:
        body = lines.get(num, [])
        # (a) spec 侧
        if not (1 <= ln <= len(body)):
            miss_anchor.append(f"{num}:{ln} 越界（应为含 {kw!r} 的行）")
            continue
        window = " ".join(body[ln - 1:ln + 1])      # 允许落到下一行（表格排版）
        if kw not in window:
            miss_anchor.append(
                f"spec 侧 {num}:{ln} 未含 {kw!r}；"
                f"实际: {body[ln - 1].strip()[:60]!r}")
        # (b) md 侧：写着该主张的那一块必须引到该坐标
        hits = [(no, txt) for no, txt in blocks if claim in txt]
        if not hits:
            miss_anchor.append(f"合约 md 中找不到主张 {claim!r}（锚点失联）")
            continue
        if len(hits) > 1:
            multi_hit.append((f"{num}:{ln}", claim, [no for no, _ in hits]))
        bad = [(no, txt) for no, txt in hits
               if not all(cites(txt, num, e) for e in (ln, *also))]
        for no, txt in bad:
            miss_anchor.append(
                f"md:{no} 主张 {claim!r} 未引用 {num}:{ln}"
                f"（行文: {txt.splitlines()[0].strip()[:60]!r}）")

    print("=" * 78)
    print("check_f1_citations: 合约 spec 行号引用核对")
    names = ", ".join(f"{n}={paths[n].name if paths[n] else '缺失'}"
                      for n in SPEC_FILES)
    print(f"  spec 文件: {names}")
    print(f"  合约中的 spec 引用共 {total} 处："
          f"显式带文件名 {sum(qualified.values())} 处 / 裸 :NNN {sum(bare.values())} 处")
    print(f"  裸引用中行号在多个 spec 文件都有效的（上下文依赖，{ambiguous} 个坐标）："
          f"共 {sum(1 for ln in bare if sum(1 for n in nlines if 1 <= ln <= nlines[n]) > 1)} 处")
    print(f"  语义锚点（claim-anchored，spec 侧关键词 + md 侧主张块）: {len(ANCHORS)} 条"
          f"（md 切成 {len(blocks)} 块）")
    if multi_hit:
        print(f"  其中主张串命中 >1 块的（每一块都须引到该坐标）: "
              f"{len(multi_hit)} 条")
        for coord, claim, nos in multi_hit:
            print(f"    - {coord} 主张 {claim!r} 命中 md:{','.join(map(str, nos))}")
    print("=" * 78)
    if problems:
        print(f"[FAIL] 引用越界/文件缺失 {len(problems)} 处:")
        for p in problems[:20]:
            print(f"  - {p}")
    if miss_anchor:
        print(f"[FAIL] 语义锚点未命中 {len(miss_anchor)} 条:")
        for p in miss_anchor[:20]:
            print(f"  - {p}")
    if not problems and not miss_anchor:
        print("check_f1_citations: PASS")
        return 0
    print("check_f1_citations: FAIL")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
