#!/usr/bin/env python3
"""test_f1_gap_proof_counterexamples.py — SPEC-103t 验收闸门的**反例注入门控**。

本脚本证明 `check_f1_gap_proofs.py`（F1 语义缺口证明的唯一检查器）**能失败**。
对每个反例：

  1. 在 `/tmp/opencode/SPEC-104t/ce-<tag>/` 建一棵**独立临时树**（工作区快照 +
     `git init` 基线提交）。**从不**在真实仓库上注入。
  2. 基线先跑一次，必须 rc=0；再用 `-v` 跑一次，断言本反例瞄准的
     `[ok] G<n> <检查名>` 行**真的被跑到**（防止新增检查被注册成死代码）。
     逐条类检查（`applic-<节点>` 等）基线上不报错、成功时没有自己的 OK 行，
     改由 `expect_ok` 声明的**聚合 OK 行**作证。
  3. 施加一处最小注入。
   4. 断言 `git diff --name-only` **非空**（防「空注入导致注入后仍全绿」）。
      `new_file` 型注入还必须同时改动一个已跟踪文件；`git status -uall` 只作为
      越权产物被创建的诊断证据，不能替代 diff 门控。
  5. 跑检查器，断言**非零退出**且确有 `[G<n>] FAIL: <检查名> ::` 行 —— 只看退出码
     不够（一个 traceback 也返回非零），必须确认是**语义 FAIL**；并断言命中的
     **检查名**正是本反例瞄准的那一个（`expect` 命中组、`expect_name` 命中具体
     检查名），且 FAIL 明细**点名**本反例注入的对象（`expect_substr`），
     否则「一律说『不符』」的泛化断言也能蒙混过关。
  6. `git checkout -- .` + `git clean -fdq` 还原（两者都只在自建临时树里执行），
     断言工作区回到干净（`git status -uall` 空），再跑一次检查器，断言**恢复全绿**
     （rc=0）。

每个反例的注入锚点都要求**唯一命中**，命中 0 次或多次直接报错退出——宁可拒绝
执行，也不接受一次含糊的多点替换。YAML 注入一律用**结构化块手术**（按缩进层级
与键行定位整块），不用脆弱的散文锚点。

§9 各类 → 反例编号对照（历史 SPEC-103 反例与本任务 resolution 反例均覆盖）：

  §12-1  删除一个 D11–D17 proof ................ CE-1
  §12-2  删除一个七键 / 加 D17:S2 进 ledger /
          具名键降为裸 S* ........................ CE-2a / CE-2b / CE-2c
  §12-3  OPEN/BLOCKED → PASS/active/
          spec-determined ....................... CE-3a / CE-3b / CE-3c / CE-3d
  §12-4  Candidate 增加 selected/default/
          recommended/Accepted ................... CE-4a / CE-4b
  §12-5  清空 evidence / identity / facet /
          observable consequence /
          blocked assertion ...................... CE-5a…CE-5e
  §12-6  矩阵 63 行 / 重复 identity /
          混入 pseudo / 改投影 ................... CE-6a…CE-6d
  §12-7  合并 rf0 layout 与 reset /
          为 S6 选择写入动作 ...................... CE-7a / CE-7b
  §12-8  删除消费者 / 错误扩大 LLVM 运行时结论 /
          注入图环 .............................. CE-8a / CE-8b / CE-8c
  §12-9  实现 / SoftFloat / SimRISC-01
          写成语义 authority ..................... CE-9a / CE-9b / CE-9c
  §12-10 改错一条 spec citation（格式仍合法）... CE-10
  额外（§12「至少」的加固，不代替上面十条）:
          D17:S2 混进矩阵（§8「S2 唯一且 ledger 外」）CE-11
          预先绑定 Candidate ADR 编号（§11）....... CE-12
          越权产物 contracts/f1_gap_proofs_bak.yaml CE-13
          返工·S7 极性一致性（§7-返工）:
            让 Candidate 引用 S7 .................... CE-16
            让影响矩阵重新声明 S7 active .......... CE-17
            让消费者重新消费 S7 .................... CE-18
            逐项篡改六个 active 键的影响面 ....... CE-22a…CE-22f
            **纯叙述**把 D17-E5 改回「无重叠顺序（S7）」CE-23
            **纯叙述**把 D17-E2 改回「7 项规范静默（…S6, S7, S8…）」CE-24
            **纯叙述**把 SPEC-103t 消费者改回「七项…OPEN/BLOCKED」... CE-25

CE-23…CE-25 与 CE-16…CE-18 是一对：后者动的是**结构化**字段（`d17_open_ids` /
`question` / 消费者 `open_ids`），前者一个结构化字段都不动，只把散文字换回返工前
的措辞。G12 的极性白名单必须仅凭**分句语义**判 FAIL，不能靠结构化 active ID
兜底；反过来，若 G12 只扫结构化字段，这三条会全绿放过。

CE-3d 与 CE-10 是本脚本最关键的两项，两项都打「只查格式/只查枚举」这个洞：
CE-3d 把某个 `facet_status` 从 `open-blocked` 改成 `spec-determined`——取值**合法**、
枚举检查过得去，只有以 `contracts/opcodes.yaml` 的 `f1.facets` 为判据的
`facet-frozen` 抓得住；CE-10 把一条 spec 引用从 `:7` 改成 `:8`——行号**在范围内**、
文法**合法**，只有「quote 必须是所引行窗口的逐字子串」抓得住。若这两项里对应的
检查缺失，它们会全绿放过，等于声称「已冻结的 facet 没被动」和「引用格式没问题」
其实是同一件事。

用法：
    python3 tools/spec/test_f1_gap_proof_counterexamples.py [-v] [--rm-trees] [--only TAG]
退出码：0 = 全部反例「注入后 FAIL 且还原后 PASS」；1 = 有反例未被抓住。
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import time
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = REPO_ROOT
TMP_ROOT = Path("/tmp/opencode/SPEC-104t")
CHECKER = "tools/spec/check_f1_gap_proofs.py"
YAML = "contracts/f1_gap_proofs.yaml"

#: 检查器的 FAIL 行：`[G8] FAIL: dag :: …`。`(?P<cat>…)` 是**组**、
#: `(?P<name>…)` 是**具体检查名**——两者都要断言，只看组等于允许「同组里另一条
#: 检查随便报红」蒙混过关（例如注入图环却只看到 `edge-backing` 红了）。
FAIL_RE = re.compile(r"^\[(?P<cat>G\d+)\] FAIL: (?P<name>\S+) :: (?P<detail>.*)$", re.M)
#: `-v` 下的 OK 行：`[ok] G8  node-set  15 个节点全部是 …`
OK_RE = re.compile(r"^\[ok\] (?P<cat>G\d+)\s+(?P<name>\S+)", re.M)
SUMMARY_RE = re.compile(r"通过 (\d+) 项，失败 (\d+) 项")

COPY_IGNORE = shutil.ignore_patterns(".git", ".cache", ".work", "__pycache__")


# ═══════════════════════════ 注入原语 ═══════════════════════════
#
# 全部基于**行边界对齐的多行字面量**定位，不依赖散文/字段名猜测：
#   * `key_text` 必须在文件里恰好出现一次，且必须落在**行首**（前置字符是 \n 或 0）；
#   * 块尾 = 下一条缩进 ≤ 起始行缩进的**非空**行（空行归块内）；
#   * 命中 0 次或多次一律 `SystemExit` 拒绝执行——宁可拒绝，也不接受含糊的多点替换。
#
# 注入类型：
#   text            全文件逐字唯一替换
#   text_in         在 `key_text` 定位的**块内**逐字唯一替换
#   drop_block      删掉 `key_text` 定位的整块
#   dup_block       复制 `key_text` 定位的整块，紧跟其后
#   insert_after    在 `key_text` 定位的整块**之后**插入若干行
#   empty_field_in  把块内某个列表字段整体清空成 `键: []`
#   new_file        新建文件（越权产物类反例）

def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _block_end(lines, start):
    ind = _indent(lines[start])
    for j in range(start + 1, len(lines)):
        if lines[j].strip() and _indent(lines[j]) <= ind:
            return j
    return len(lines)


def _locate(text: str, key_text: str):
    """→ (start, end) 行下标。`key_text` 必须在行首且唯一出现。"""
    n = text.count(key_text)
    if n != 1:
        raise SystemExit(f"块锚点命中 {n} 次（须恰好 1 次）：{key_text[:100]!r}")
    ci = text.index(key_text)
    if ci != 0 and text[ci - 1] != "\n":
        raise SystemExit(f"块锚点未落在行首：{key_text[:100]!r}")
    start = text.count("\n", 0, ci)
    return start


def _span(lines, start):
    return start, _block_end(lines, start)


def apply_edit(tree: Path, edit) -> None:
    kind, rel = edit[0], edit[1]
    p = tree / rel
    if kind == "new_file":
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(edit[2], encoding="utf-8")
        return
    if not p.exists():
        raise SystemExit(f"注入目标不存在: {rel}")
    lines = p.read_text(encoding="utf-8").splitlines(keepends=True)
    text = "".join(lines)

    if kind == "text":
        _, _, old, new = edit
        n = text.count(old)
        if n != 1:
            raise SystemExit(f"注入锚点在 {rel} 命中 {n} 次（须恰好 1 次）。"
                             f"锚点前 90 字: {old[:90]!r}")
        p.write_text(text.replace(old, new, 1), encoding="utf-8")
        return

    if kind == "text_in":
        # 块内替换：先定位块，再在**块文本**里做唯一替换，块外同名锚点不受影响
        _, _, key_text, old, new = edit
        s = _locate(text, key_text)
        e = _block_end(lines, s)
        body = "".join(lines[s:e])
        n = body.count(old)
        if n != 1:
            raise SystemExit(f"块内锚点在 {rel} 的 {key_text[:40]!r} 块里命中 {n} 次"
                             f"（须恰好 1 次）。锚点: {old[:90]!r}")
        p.write_text(text[:text.index(key_text)]
                     + body.replace(old, new, 1)
                     + text[text.index(key_text) + len(body):], encoding="utf-8")
        return

    if kind == "drop_block":
        _, _, key_text = edit
        s = _locate(text, key_text)
        e = _block_end(lines, s)
        del lines[s:e]
        p.write_text("".join(lines), encoding="utf-8")
        return

    if kind == "dup_block":
        _, _, key_text = edit
        s = _locate(text, key_text)
        e = _block_end(lines, s)
        lines[e:e] = lines[s:e]
        p.write_text("".join(lines), encoding="utf-8")
        return

    if kind == "empty_field_in":
        # 把块内某个列表字段**整体**清空成 `键: []`：定位块 → 定位字段键行（块内
        # 唯一）→ 删掉键行本身及其后所有「空行或缩进更深」的行。
        #
        # 为什么不早先用 `text_in` 顺手替掉「键行 + 第一条」：那样只会把**后续**
        # 那几条列表项留在原地，YAML 直接解析失败，检查器以 rc=2 异常退出——
        # 反例拿到的是「输入坏了」的退出码，不是「检查器抓到了缺陷」的语义 FAIL，
        # 正是本脚本明令拒绝的那种假证据（见 `run_one` 里「异常退出不算语义 FAIL」）。
        _, _, key_text, field_line = edit
        s = _locate(text, key_text)
        e = _block_end(lines, s)
        hits = [j for j in range(s, e) if lines[j] == field_line]
        if len(hits) != 1:
            raise SystemExit(f"字段键行 {field_line.strip()!r} 在 {key_text[:40]!r} "
                             f"块内命中 {len(hits)} 次（须恰好 1 次）")
        f = hits[0]
        base = _indent(lines[f])
        g = f + 1
        # YAML 的块序列可以与它的键**同缩进**（`    evidence:` / `    - id: …`），
        # 所以「更深」不是唯一判据：同缩进但以 `- ` 开头也算本字段的续行；
        # 同缩进且不是 `- `（下一个兄弟键）就停。空行归本字段。
        while g < e and (not lines[g].strip()
                         or _indent(lines[g]) > base
                         or (_indent(lines[g]) == base
                             and lines[g].lstrip().startswith("- "))):
            g += 1
        emptied = field_line.rstrip("\n")
        assert emptied.endswith(":"), field_line
        lines[f:g] = [emptied[:-1] + ": []\n"]
        p.write_text("".join(lines), encoding="utf-8")
        return

    if kind == "insert_after":
        _, _, key_text, payload = edit
        s = _locate(text, key_text)
        e = _block_end(lines, s)
        lines[e:e] = [x + "\n" for x in payload]
        p.write_text("".join(lines), encoding="utf-8")
        return

    raise SystemExit(f"未知注入类型: {kind}")


def apply_edits(tree: Path, edits) -> None:
    for edit in edits:
        apply_edit(tree, edit)


# ═══════════════════════ 注入素材（行边界对齐的逐字字面量）═══════════════
#
# 下面每一个常量都只用**行首起、逐字**的多行字面量，不含任何散文猜测；`text_in`
# 的块锚点把注入范围锁死在**一个** identity/decision 块内，因此同名 facet 行在
# 64 行矩阵里重复 35 次也不影响唯一定位。

# ── §12-1：删掉整个 D14 proof 块（`  D14:` 缩进 2，直到下一个缩进 ≤2 的行）──
DP_D14_HEAD = "  D14:\n    title: "

# ── §12-2a：删掉整个 D17:S5 ledger 行 ───────────────────────────────────
LG_S5_HEAD = "  D17:S5:\n    topic: ftsclb/fosclb 的 scaleB 指数「rfhd 取整数值」有两种读法"

# ── §12-2b：把 D17:S2 塞进 ledger（插在 D17:S6 块之后，见 LG_S6_HEAD）────
# 注意：trace_only 里本来就有一个 `  D17:S2:`，所以裸用 `  D17:S2:` 之类仍需
# 连带 topic 行才唯一。原先这里有一个名叫 `LG_S7_ANCHOR` 的锚点，值与 LG_S6_HEAD
# 逐字相同、锚点其实也是 S6 块；返工后 S7 已是 non-gap、不在 ledger 里，那个名字
# 只会误导，故直接删除并复用 LG_S6_HEAD。
LG_S2_INJECT = [
    "  D17:S2:",
    "    topic: 「有效范围 1~63」表述不一致（无行为后果）",
    "    status: BLOCKED",
    "    classification: genuine-gap",
]

# ── §12-2c：把具名键 `D17:S5` 降级为裸 `S5` ──────────────────────────────
LG_S5_BARE_OLD = LG_S5_HEAD
LG_S5_BARE_NEW = LG_S5_HEAD.replace("  D17:S5:", "  S5:", 1)

# ── §12-3a/3b/3c：把真实未决行的状态词改掉 ───────────────────────────────
LG_S6_STATUS_OLD = ("  D17:S6:\n"
                    "    topic: rf0 的 SBZ 域被写入时的行为未规定（不指定忽略/保留/清零/异常）\n"
                    "    status: BLOCKED")
LG_S4_STATUS_OLD = ("  D17:S4:\n"
                    "    topic: 多个 fault 条件同时成立时的异常优先级未规定\n"
                    "    status: BLOCKED")
LG_S3_STATUS_OLD = ("  D17:S3:\n"
                    "    topic: ftcls/focls 的 immu6 != 1 合法性未规定\n"
                    "    status: BLOCKED")

# ── §12-3d：把矩阵 cs.eq-rf 行的 facet_status 由 open-blocked 改成 spec-determined
# 取值在 `facet_status` 词表里**合法**，所以只有「逐行比对 contracts/opcodes.yaml
# 的 f1.facets」的 `facet-frozen` 抓得住。
MTX_CS_EQ = "- identity: cs.eq-rf\n  group: rf-qfc\n  section: 浮点条件赋值指令"

# ── §12-4a/4b：给候选问题加 selected / recommended ───────────────────────
CAND_SCOPE_HEAD = "- id: CAND-D11-SCOPE\n  group: rf0-operand/high-half"
CAND_UPDATE_HEAD = "- id: CAND-D12-UPDATE\n  group: FCSR/flags/tininess"

# ── §12-5：逐项清空（五项分别一例，见 AGENTS.md「修一类」）────────────────
DP_D11_HEAD = "  D11:\n    title: rf0 一般 ILLI 规则与 sign-injection 特例的适用章节、优先级与搬移边界"
DP_D12_HEAD = ("  D12:\n    title: FCSR flags 的更新/保持/清除与数据搬移是否更新 flags")
DP_D13_HEAD = "  D13:\n    title: 单精（ft）结果或 4 字节载入写 RF 后的高 32 位"
LG_S4_HEAD = ("  D17:S4:\n"
              "    topic: 多个 fault 条件同时成立时的异常优先级未规定")
LG_S6_HEAD = ("  D17:S6:\n"
              "    topic: rf0 的 SBZ 域被写入时的行为未规定（不指定忽略/保留/清零/异常）")

# ── §12-6：矩阵形态 ──────────────────────────────────────────────────────
# 末行是 ut2ft（矩阵按 identity 排序，ut2ft 排在最后）
MTX_LAST_ROW = "- identity: ut2ft\n  group: misc-rf\n  section: 格式转换指令"
MTX_FIRST_ROW = "- identity: cs.eq-rf\n  group: rf-qfc\n  section: 浮点条件赋值指令"
MTX_FTSUB_ROW = "- identity: ftsub\n  group: misc-rf\n  section: S2D1"

# ── §12-7：rf0 layout/reset 分栏与 S6 写入动作 ───────────────────────────
RF_SPLIT_HEAD = "rf0_fcsr_split:\n  separation_rule: "
RF_RESET_HEAD = "  reset:\n    classification: genuine-gap\n    status: BLOCKED"
S6_STATE_ANCHOR = ("    write_action_state: 以上四种行为一个都未写入本文件，"
                   "四种之间的取舍留给逐 decision 裁决；本行不含任何取值字段。")

# ── return-S7-prose：把 S7 重新写成 active genuine-gap 的**旧措辞** ──────
# 这三条不是结构化字段（`d17_open_ids` / `ledger` / `non_gap_records`）的注入，
# 而是**叙述文本**注入：checker 必须在**没有任何结构化线索**的情况下，仅凭散文字
# 就判 FAIL。`new` 逐字取自 pre-repair 版本（`D17-E2` / `D17-E5` 的 finding、
# SPEC-103t 消费者的 `na_runtime_note`），即「七项」「无重叠顺序（S7）」口径。
# 锚点用 `text_in` 锁在单个块内，避免同名 evidence/consumer 段落被误伤。
S7PROSE_E2_HEAD = "    - id: D17-E2\n"
S7PROSE_E5_HEAD = "    - id: D17-E5\n"
S7PROSE_SPEC103_NODE = ("  - task: SPEC-103t\n"
                        "    task_book: .xkw/tasks/spec/SPEC-103t-F1语义缺口证明与候选ADR输入.md\n")

# 下面六条字面量**逐字**等于对应块：`_CUR` = 当前（返工后）YAML 里的块，即
# `text_in` 的 `old`（唯一命中）；`_PRE` = pre-repair 版本里的块，即 `text_in` 的
# `new`（要「恢复」回去的旧措辞）。两者都由 YAML 原文机械抽出、不手抄；三引号保留
# 真实换行与续行缩进，已断言不含 `"""` 与反斜杠，故字面量与源文件严格等价。
# （**不要**把 `_CUR`/`_PRE` 读成「old/new」：方向相反，见上一行。）
S7PROSE_E5_CUR = """    - id: D17-E5
      kind: spec-text
      source: spec/SimRISC-03-浮点类指令.md:164,20,36
      finding: 「rfhd 取整数值」有两种读法（S5）；块赋值的跨寄存器组方向已由原始规范唯一确定（历史 S7 记为 spec-determined，不进入 active ledger）；ldm/stm 只给签名与对齐、只说「多个连续的寄存器」未说地址连续（S8）。"""

S7PROSE_E5_PRE = """    - id: D17-E5
      kind: spec-text
      source: spec/SimRISC-03-浮点类指令.md:164,43,20,36
      finding: 「rfhd 取整数值」有两种读法（S5）；块赋值只说「将 hc 开始的 immu6 个寄存器复制到 hb 开始」无重叠顺序（S7）；ldm/stm 只给签名与对齐、只说「多个连续的寄存器」未说地址连续（S8）。"""

S7PROSE_E2_CUR = """    - id: D17-E2
      kind: spec-absence-scan
      source: spec/SimRISC-00-指令系统设计.md; spec/SimRISC-03-浮点类指令.md
      finding: 逐节扫描 SimRISC-03 的全部 11 个小节（存取RF寄存器 / 寄存器组之间块赋值 / 立即数常数赋值 / 格式转换指令 / 浮点运算指令 S2D1,S3D1,S1D1 / 浮点符号位操作指令 / 浮点比较指令
        / 浮点条件赋值指令 / 浮点分类指令 / set.ft-set.fo 伪指令）与 SimRISC-00 的寄存器章节：得到 6 项 active 规范静默（S1, S3, S4, S5, S6, S8）、1 项表述不一致但无行为后果的
        trace-only 项（S2），以及 1 项已被原始规范证明为 spec-determined 的历史项（S7，见 D17-E7 与 non_gap_records.D17:S7）。历史 S7 不计入 active 静默项。"""

S7PROSE_E2_PRE = """    - id: D17-E2
      kind: spec-absence-scan
      source: spec/SimRISC-00-指令系统设计.md; spec/SimRISC-03-浮点类指令.md
      finding: 逐节扫描 SimRISC-03 的全部 11 个小节（存取RF寄存器 / 寄存器组之间块赋值 / 立即数常数赋值 / 格式转换指令 / 浮点运算指令 S2D1,S3D1,S1D1 / 浮点符号位操作指令 / 浮点比较指令 / 浮点条件赋值指令 / 浮点分类指令 / set.ft-set.fo 伪指令）与 SimRISC-00 的寄存器章节：得到 7 项规范静默（S1, S3, S4, S5, S6, S7, S8）与 1 项表述不一致但无行为后果（S2）。"""

S7PROSE_NOTE_CUR = """    na_runtime_note: 本任务不关闭任何 OPEN：六项 active 静默项在证据完整后仍为 OPEN/BLOCKED；ledger 外两项分别是不计 PASS 的 trace-only（S2）与历史
      non-gap（S7）。"""

S7PROSE_NOTE_PRE = """    na_runtime_note: 本任务不关闭任何 OPEN：七项在证据完整后仍为 OPEN/BLOCKED。"""

# ── SPEC-104t §9 resolution 反例锚点 ───────────────────────────────────────
RES_D11_HEAD = "    - id: ADR-1009/D2\n"
RES_D11_RULE_HEAD = "    D11:\n      rf0_read: all-f1-identities-allowed\n"
RES_D12_RULE_HEAD = "    D12:\n      flags_bits: '[4:0]'\n"
RES_D13_RULE_HEAD = "    D13:\n      tetra_high_half_bits: '0xffffffff'\n"
RES_D14_RULE_HEAD = "    D14:\n      quiet_unordered_bits: '0x7ff8000000000000'\n"
RES_D15_RULE_HEAD = "    D15:\n      canonical_qnan_bits: null\n"
RES_D16_RULE_HEAD = "    D16:\n      tininess_detection: after-rounding\n"
RES_D17_RULE_HEAD = "    D17:\n      active_keys: [D17:S1, D17:S3, D17:S4, D17:S5, D17:S6, D17:S8]\n"
RES_S6_HEAD = "    s6_scope_relation:\n      historical_six:"
RES_MATRIX_FIRST = "  - identity: cs.eq-rf\n    owning_consumer: QEMU-103t\n"
RES_NORM_HEAD = "  - id: NE-01\n    file: spec/SimRISC-03-浮点类指令.md\n"
RES_GATE_HEAD = "    - task: TESTCASES-101t\n      task_book:"

# ── §12-8：消费者图 ──────────────────────────────────────────────────────
GRAPH_QEMU101_NODE_HEAD = ("  - task: QEMU-101t\n"
                           "    task_book: .xkw/tasks/qemu/QEMU-101t-F1-RF状态存取搬移与setw.md")
GRAPH_FIRST_EDGE = ("  - from: SPEC-101k\n    to: SPEC-102t\n    basis: dependency-line")
LLVM101_NODE_HEAD = ("  - task: LLVM-101t\n"
                     "    task_book: .xkw/tasks/llvm/LLVM-101t-F1-RF寄存器与真实指令MC.md")

# ── §12-9：实现 / SoftFloat / SimRISC-01 当语义权威 ──────────────────────
AUTH_SEM_OWNER = "  semantics_owner:\n  - spec/SimRISC-00-指令系统设计.md\n" \
                 "  - spec/SimRISC-03-浮点类指令.md"
CITE_D11_Q1 = ("    - ref: spec/SimRISC-03-浮点类指令.md:8\n"
               "      file: spec/SimRISC-03-浮点类指令.md\n      lines: '8'\n"
               "      quote: 浮点运算指令的目的或任一源操作数为 rf0 时触发")
EV_D11_E3 = ("    - id: D11-E3\n      kind: spec-absence-scan\n"
             "      source: spec/SimRISC-03-浮点类指令.md\n")

# ── §12-10：把 D11 的一条 spec 引用从 :7 改成 :8 ─────────────────────────
# 行号 8 在 SimRISC-03 范围内、文法也合法，所以「引用格式/范围」两层都过得去；
# 只有「quote 必须是所引行窗口的逐字子串」抓得住。用 `text_in` 把改动锁在
# D11 块内——同一段 4 行引用在别的 decision 里也出现过，全局替换不唯一。
CITE_D11_Q2 = ("    - ref: spec/SimRISC-03-浮点类指令.md:8\n"
               "      file: spec/SimRISC-03-浮点类指令.md\n      lines: '8'\n"
               "      quote: rf ld/st 中 rf0 为目的时允许")


# ── 额外：§8「S2 唯一且 ledger 外」 / §11「不预设 ADR 编号」 / §5 越权产物 ──
# （S2 与 ADR 两项的锚点已分别改用 MTX_CS_EQ / "provenance:\n"。）
# CE-13 除创建越权未跟踪产物外，还须改动此已跟踪 YAML 行；内联注释不改变
# schema_version 的 YAML 值，使检查器可到达并报告 stray-artifact，而 diff 门控也
# 不会被未跟踪文件绕过。
STRAY_ARTIFACT = "contracts/f1_gap_proofs_bak.yaml"
SCHEMA_VERSION = "schema_version: 1.0.0\nauthority:"
SCHEMA_VERSION_WITH_CE13_COMMENT = "schema_version: 1.0.0 # CE-13 tracked mutation\nauthority:"


# ═══════════════════════ 反例定义（§9 全类别覆盖）═══════════════

COUNTEREXAMPLES = [
    # ── §12-1 ──
    {
        "tag": "1-drop-proof",
        "cat": "§12-1",
        "title": "删除一个 D11–D17 proof（整块删掉 decision_proofs.D14）",
        "expect": "G2", "expect_name": "proof-D14", "expect_substr": "D14",
        "edits": [("drop_block", YAML, DP_D14_HEAD)],
    },
    # ── §12-2 ──
    {
        "tag": "2a-drop-ledger-key",
        "cat": "§12-2a",
        "title": "删除一个七键（整块删掉 d17_open_ledger.D17:S5）",
        "expect": "G5", "expect_name": "ledger-D17:S5", "expect_substr": "D17:S5",
        "edits": [("drop_block", YAML, LG_S5_HEAD)],
    },
    {
        "tag": "2b-ledger-adds-s2",
        "cat": "§12-2b",
        "title": "把 D17:S2 加进 d17_open_ledger（它只能是 ledger 外的 trace-only）",
        "expect": "G5", "expect_name": "ledger-keys", "expect_substr": "D17:S2",
        "edits": [("insert_after", YAML, LG_S6_HEAD, LG_S2_INJECT)],
    },
    {
        "tag": "2c-ledger-bare-s5",
        "cat": "§12-2c",
        "title": "把具名键 D17:S5 降级为裸 S5（下游将失去 OPEN-ID 的 D 前缀）",
        "expect": "G5", "expect_name": "ledger-keys", "expect_substr": "S5",
        "edits": [("text", YAML, LG_S5_BARE_OLD, LG_S5_BARE_NEW)],
    },
    # ── §12-3 ──
    {
        "tag": "3a-status-pass",
        "cat": "§12-3a",
        "title": "把 OPEN/BLOCKED 改成 PASS（D17:S6 声称已通过）",
        "expect": "G10", "expect_name": "ledger-all-open", "expect_substr": "OPEN=",
        "edits": [("text", YAML, LG_S6_STATUS_OLD,
                   LG_S6_STATUS_OLD.replace("    status: BLOCKED", "    status: PASS"))],
    },
    {
        "tag": "3b-status-active",
        "cat": "§12-3b",
        "title": "把 OPEN/BLOCKED 改成 active（D17:S4 声称已生效）",
        "expect": "G10", "expect_name": "status-word", "expect_substr": "active",
        "edits": [("text", YAML, LG_S4_STATUS_OLD,
                   LG_S4_STATUS_OLD.replace("    status: BLOCKED", "    status: active"))],
    },
    {
        "tag": "3c-status-spec-determined",
        "cat": "§12-3c",
        "title": "把 ledger 行的 status 改成 spec-determined（枚举里根本没有这个值）",
        "expect": "G10", "expect_name": "status-word", "expect_substr": "spec-determined",
        "edits": [("text", YAML, LG_S3_STATUS_OLD,
                   LG_S3_STATUS_OLD.replace("    status: BLOCKED",
                                            "    status: spec-determined"))],
    },
    {
        "tag": "3d-facet-open-to-determined",
        "cat": "§12-3d",
        "title": ("把矩阵 cs.eq-rf 行的 facet_status 由 open-blocked 改成 spec-determined"
                  "（取值合法，须靠 facet-frozen 逐行比对 opcodes.yaml 抓）"),
        "expect": "G10", "expect_name": "facet-frozen", "expect_substr": "cs.eq-rf",
        "edits": [("text_in", YAML, MTX_CS_EQ,
                   "    rf0_operand: open-blocked", "    rf0_operand: spec-determined")],
    },
    # ── §12-4 ──
    {
        "tag": "4a-candidate-selected",
        "cat": "§12-4a",
        "title": "给候选问题加 selected: A（把待裁决问题偷偷定案）",
        "expect": "G9", "expect_name": "cand-selection-key", "expect_substr": "CAND-D11-SCOPE",
        "edits": [("insert_after", YAML, CAND_SCOPE_HEAD, ["  selected: A"])],
    },
    {
        "tag": "4b-candidate-recommended",
        "cat": "§12-4b",
        "title": "给另一个候选问题加 recommended: B（把备选之一标成推荐）",
        "expect": "G9", "expect_name": "cand-selection-key", "expect_substr": "CAND-D12-UPDATE",
        "edits": [("insert_after", YAML, CAND_UPDATE_HEAD, ["  recommended: B"])],
    },
    # ── §12-5 ──
    {
        "tag": "5a-empty-evidence",
        "cat": "§12-5a",
        "title": "清空 D11 的 evidence 列表（缺口没有证据）",
        "expect": "G2", "expect_name": "proof-D11", "expect_substr": "evidence",
        "edits": [("empty_field_in", YAML, DP_D11_HEAD, "    evidence:\n")],
    },
    {
        "tag": "5b-empty-identity",
        "cat": "§12-5b",
        "title": "清空 D17:S4 的 affected_identities（受影响范围不给了）",
        "expect": "G5", "expect_name": "ledger-D17:S4", "expect_substr": "affected_identities",
        "edits": [("empty_field_in", YAML, LG_S4_HEAD, "    affected_identities:\n")],
    },
    {
        "tag": "5c-empty-facet",
        "cat": "§12-5c",
        "title": "清空 D17:S6 的 blocked_facets（被压的是哪一面不给了）",
        "expect": "G5", "expect_name": "ledger-D17:S6", "expect_substr": "blocked_facets",
        "edits": [("empty_field_in", YAML, LG_S6_HEAD, "    blocked_facets:\n")],
    },
    {
        "tag": "5d-empty-observable",
        "cat": "§12-5d",
        "title": "清空 D12 的 observable_consequences（缺口看不出可观测后果）",
        "expect": "G2", "expect_name": "proof-D12", "expect_substr": "observable_consequences",
        "edits": [("empty_field_in", YAML, DP_D12_HEAD, "    observable_consequences:\n")],
    },
    {
        "tag": "5e-empty-blocked-assertion",
        "cat": "§12-5e",
        "title": "清空 D13 的 blocked_assertions（没有任何下游断言被阻塞）",
        "expect": "G2", "expect_name": "proof-D13", "expect_substr": "blocked_assertions",
        "edits": [("empty_field_in", YAML, DP_D13_HEAD, "    blocked_assertions:\n")],
    },
    # ── §12-6 ──
    {
        "tag": "6a-matrix-63-rows",
        "cat": "§12-6a",
        "title": "impact_matrix 变成 63 行（整块删掉最后一行 ut2ft）",
        "expect": "G7", "expect_name": "matrix-count", "expect_substr": "64 行",
        "edits": [("drop_block", YAML, MTX_LAST_ROW)],
    },
    {
        "tag": "6b-matrix-dup-identity",
        "cat": "§12-6b",
        "title": "impact_matrix 出现重复 identity（整行复制 cs.eq-rf）",
        "expect": "G7", "expect_name": "matrix-dup", "expect_substr": "cs.eq-rf",
        "edits": [("dup_block", YAML, MTX_FIRST_ROW)],
    },
    {
        "tag": "6c-matrix-pseudo",
        "cat": "§12-6c",
        "title": "impact_matrix 混入 pseudo 指令 set.ft（伪指令不计入 64）",
        "expect": "G7", "expect_name": "matrix-pseudo", "expect_substr": "set.ft",
        "edits": [("insert_after", YAML, MTX_FIRST_ROW,
                   ["- identity: set.ft", "  group: pseudo", "  section: 伪指令"])],
    },
    {
        "tag": "6d-matrix-projection",
        "cat": "§12-6d",
        "title": "改变 37/53/18/4/18/36/64 投影（从 ftsub 的 open_decisions 删掉 D13）",
        "expect": "G7", "expect_name": "matrix-projection", "expect_substr": "D13 的矩阵投影",
        "edits": [("text_in", YAML, MTX_FTSUB_ROW,
                   "  open_decisions:\n  - D12\n  - D13\n  - D15\n  - D16\n",
                   "  open_decisions:\n  - D12\n  - D15\n  - D16\n")],
    },
    # ── §12-7 ──
    {
        "tag": "7a-merge-layout-reset",
        "cat": "§12-7a",
        "title": "合并 rf0 layout 与 reset（只留 layout 栏，删掉整个 reset 栏）",
        "expect": "G5", "expect_name": "layout-reset-split", "expect_substr": "reset",
        "edits": [("drop_block", YAML, RF_RESET_HEAD)],
    },
    {
        "tag": "7b-s6-choose-write-action",
        "cat": "§12-7b",
        "title": "为 S6 选择写入动作（加一个 write_action_selected: 静默忽略）",
        "expect": "G5", "expect_name": "s6-chosen-behaviour", "expect_substr": "D17:S6",
        "edits": [("insert_after", YAML, S6_STATE_ANCHOR,
                   ["    write_action_selected: 静默忽略"])],
    },
    # ── §12-8 ──
    {
        "tag": "8a-drop-consumer-node",
        "cat": "§12-8a",
        "title": "删除一个消费者节点（整个 QEMU-101t 节点块）",
        "expect": "G8", "expect_name": "node-set", "expect_substr": "QEMU-101t",
        "edits": [("drop_block", YAML, GRAPH_QEMU101_NODE_HEAD)],
    },
    {
        "tag": "8b-widen-llvm-runtime",
        "cat": "§12-8b",
        "title": ("错误扩大 LLVM 的运行时结论（把 LLVM-101t 的 D17:S1 由 N/A(runtime) "
                  "改成 OPEN —— assemble/disassemble PASS 不得解锁）"),
        "expect": "G8", "expect_name": "applic-LLVM-101t", "expect_substr": "N/A(runtime)",
        "expect_ok": "applicability",
        "edits": [("text_in", YAML, LLVM101_NODE_HEAD,
                   "      D17:S1: N/A(runtime)\n      D17:S3: OPEN",
                   "      D17:S1: OPEN\n      D17:S3: OPEN")],
    },
    {
        "tag": "8c-graph-cycle",
        "cat": "§12-8c",
        "title": ("注入图环（加一条 QEMU-101t → SPEC-102t 的 taskbook-mention 回边，"
                  "闭合 QEMU-101t→SPEC-102t→SPEC-103t→QEMU-101t；backing 与 28 条"
                  "必需边检查都合法，只有 DAG 检查能抓）"),
        "expect": "G8", "expect_name": "dag", "expect_substr": "环",
        "edits": [("insert_after", YAML, GRAPH_FIRST_EDGE, [
            "  - from: QEMU-101t",
            "    to: SPEC-102t",
            "    basis: taskbook-mention",
            "    backing: SPEC-102t 任务书正文中提到 `QEMU-101t`",
        ])],
    },
    # ── §12-9 ──
    {
        "tag": "9a-implementation-as-authority",
        "cat": "§12-9a",
        "title": "把实现写成语义 authority（semantics_owner 加入 QEMU 补丁树）",
        "expect": "G3", "expect_name": "authority-forbidden", "expect_substr": "qemu",
        "edits": [("text", YAML, AUTH_SEM_OWNER,
                   AUTH_SEM_OWNER + "\n  - components/qemu/patches/0001-simriscv-fp.patch")],
    },
    {
        "tag": "9b-softfloat-as-authority",
        "cat": "§12-9b",
        "title": "把 SoftFloat 写成语义 authority（D11 的一条 spec_cites 改引 SoftFloat 源文件）",
        "expect": "G3", "expect_name": "cite-forbidden", "expect_substr": "softfloat",
        "edits": [("text_in", YAML, DP_D11_HEAD, CITE_D11_Q1,
                   "    - ref: components/llvm-project/patches/softfloat-reference.c:7\n"
                   "      file: components/llvm-project/patches/softfloat-reference.c\n"
                   "      lines: '7'\n"
                   "      quote: 浮点运算指令的目的或任一源操作数为 rf0 时触发")],
    },
    {
        "tag": "9c-simrisc01-as-authority",
        "cat": "§12-9c",
        "title": "把 SimRISC-01 写成语义 authority（D11-E3 的 evidence 改引 SimRISC-01）",
        "expect": "G3", "expect_name": "evidence-forbidden", "expect_substr": "simrisc-01",
        "edits": [("text_in", YAML, DP_D11_HEAD, EV_D11_E3,
                   "    - id: D11-E3\n      kind: spec-absence-scan\n"
                   "      source: spec/SimRISC-01-*.md\n")],
    },
    # ── §12-10 ──
    {
        "tag": "10-cite-off-by-one",
        "cat": "§12-10",
        "title": ("把 D11 的一条 spec 引用从 :7 改成 :8（行号在范围内、文法合法，"
                  "只有 quote 子串核对抓得住）"),
        "expect": "G4", "expect_name": "cite-quote-mismatch", "expect_substr": "quote 不是",
        "edits": [("text_in", YAML, DP_D11_HEAD, CITE_D11_Q2,
                    CITE_D11_Q2.replace("SimRISC-03-浮点类指令.md:8\n",
                                        "SimRISC-03-浮点类指令.md:7\n", 1)
                             .replace("      lines: '8'\n", "      lines: '7'\n", 1))],
    },
    # ── 额外加固（§12「至少包括」的加固，不代替上面十条）──
    {
        "tag": "11-s2-leaks-into-matrix",
        "cat": "额外·§8",
        "title": "把 D17:S2 混进 impact_matrix 的 d17_open_ids（它不是 ledger 键）",
        "expect": "G6", "expect_name": "s2-leak", "expect_substr": "D17:S2",
        "edits": [("text_in", YAML, MTX_CS_EQ,
                   "  d17_open_ids:\n  - D17:S1\n  d17_fallback: true",
                   "  d17_open_ids:\n  - D17:S1\n  - D17:S2\n  d17_fallback: true")],
    },
    {
        "tag": "12-adr-number-prebound",
        "cat": "额外·§11",
        "title": "预先绑定 Candidate ADR 编号（在 provenance 里写下 ADR-1005）",
        "expect": "G11", "expect_name": "adr-binding", "expect_substr": "ADR-1005",
        "edits": [("insert_after", YAML, "  provenance:\n", ["    candidate_adr_number: ADR-1005"])],
    },
    {
        "tag": "13-stray-artifact",
        "cat": "额外·§5",
        "title": ("越权产物（在 contracts/ 下另建 f1_gap_proofs_bak.yaml；同时对"
                  "已跟踪 YAML 作无语义内联注释改动，以满足 diff 门控）"),
        "expect": "G11", "expect_name": "stray-artifact", "expect_substr": "f1_gap_proofs_bak.yaml",
        "edits": [
            ("new_file", STRAY_ARTIFACT, "# 越权产物，反例注入用\nschema_version: 0\n"),
            ("text", YAML, SCHEMA_VERSION, SCHEMA_VERSION_WITH_CE13_COMMENT),
        ],
    },
    # ── Return repair: S7 is historical non-gap and D11 consumer coverage is exact. ──
    {
        "tag": "14-s7-missing-non-gap",
        "cat": "return-S7", "title": "删除 S7 historical non-gap 记录",
        "expect": "G5", "expect_name": "s7-non-gap", "expect_substr": "S7",
        "edits": [("drop_block", YAML, "  D17:S7:\n    topic: rd2rf/rf2rd 固定跨寄存器组 RF→RD / RD→RF 块赋值方向（历史 non-gap）")],
    },
    {
        "tag": "15-s7-wrong-status",
        "cat": "return-S7", "title": "把 S7 NOT-A-GAP 改成 OPEN",
        "expect": "G5", "expect_name": "s7-non-gap", "expect_substr": "OPEN",
        "edits": [("text", YAML, "  D17:S7:\n    topic: rd2rf/rf2rd 固定跨寄存器组 RF→RD / RD→RF 块赋值方向（历史 non-gap）\n    classification: spec-determined\n    status: NOT-A-GAP", "  D17:S7:\n    topic: rd2rf/rf2rd 固定跨寄存器组 RF→RD / RD→RF 块赋值方向（历史 non-gap）\n    classification: spec-determined\n    status: OPEN")],
    },
    {
        "tag": "16-s7-candidate-leak",
        "cat": "return-S7", "title": "让 Candidate 引用 S7",
        "expect": "G5", "expect_name": "s7-leak", "expect_substr": "candidate",
        "edits": [("text_in", YAML, "- id: CAND-D17-S8\n  group: D17-silent-ldmstm-memory", "  question: ldm/stm 的内存侧第 i 个元素访问哪个地址、步长是多少、重叠读写顺序是什么？", "  question: ldm/stm 的内存侧第 i 个元素访问哪个地址、步长是多少、重叠读写顺序是什么？ D17:S7")],
    },
    {
        "tag": "17-s7-matrix-leak",
        "cat": "return-S7", "title": "让矩阵重新声明 S7 active",
        "expect": "G5", "expect_name": "s7-leak", "expect_substr": "matrix",
        "edits": [("text_in", YAML, MTX_CS_EQ, "  d17_open_ids:\n  - D17:S1\n  d17_fallback: true", "  d17_open_ids:\n  - D17:S1\n  - D17:S7\n  d17_fallback: true")],
    },
    {
        "tag": "18-s7-consumer-leak",
        "cat": "return-S7", "title": "让 consumer 重新消费 S7",
        "expect": "G5", "expect_name": "s7-leak", "expect_substr": "consumer",
        "edits": [("text_in", YAML, LLVM101_NODE_HEAD, "      - D17:S3", "      - D17:S7\n      - D17:S3")],
    },
    {
        "tag": "19-d11-llvm-mapping-missing",
        "cat": "return-D11", "title": "删除 D11→LLVM-101 assembler-legality 映射",
        "expect": "G8", "expect_name": "d11-consumers", "expect_substr": "LLVM-101t",
        "edits": [("text_in", YAML, LLVM101_NODE_HEAD, "      decisions:\n      - D11\n      - D17", "      decisions:\n      - D17")],
    },
    {
        "tag": "20-d11-testcases-mapping-missing",
        "cat": "return-D11", "title": "删除 D11→TESTCASES-102 schema/oracle/vector 映射",
        "expect": "G8", "expect_name": "d11-consumers", "expect_substr": "TESTCASES-102t",
        "edits": [("text_in", YAML, "  - task: TESTCASES-102t\n    task_book: .xkw/tasks/testcases/TESTCASES-102t-F1独立浮点oracle与全量向量.md", "      decisions:\n      - D11\n      - D12", "      decisions:\n      - D12")],
    },
    {
        "tag": "21-d11-integ-mapping-missing",
        "cat": "return-D11", "title": "删除 D11→INTEG-103 runtime semantics 映射",
        "expect": "G8", "expect_name": "d11-consumers", "expect_substr": "INTEG-103t",
        "edits": [("text_in", YAML, "  - task: INTEG-103t\n    task_book: .xkw/tasks/integ/INTEG-103t-F1端到端闭环与M1不变回归.md", "      decisions:\n      - D11\n      - D12", "      decisions:\n      - D12")],
    },
    # Each active scope is independently re-derived from opcodes/contract.
    *[
        {"tag": f"22{suffix}-scope-{key}", "cat": "return-scope",
         "title": f"篡改 {key} active scope count", "expect": "G5",
         "expect_name": f"ledger-{key}", "expect_substr": "affected_identity_count",
         "edits": [("text_in", YAML, head, f"    affected_identity_count: {count}",
                    "    affected_identity_count: 0")]}
        for suffix, key, count, head in (
            ("a", "D17:S1", 64, "  D17:S1:\n    topic:"),
            ("b", "D17:S3", 2, "  D17:S3:\n    topic:"),
            ("c", "D17:S4", 26, LG_S4_HEAD),
            ("d", "D17:S5", 2, LG_S5_HEAD),
            ("e", "D17:S6", 6, LG_S6_HEAD),
            ("f", "D17:S8", 4, "  D17:S8:\n    topic:"),
        )
    ],
    # ── return-S7-prose：纯**叙述**注入，结构化字段一个都不动 ─────────────
    # 三条分别覆盖 D17 proof 的 evidence finding、D17 proof 的 evidence 枚举、
    # 以及 consumer 的 `na_runtime_note`，证明 G12 的极性白名单不是靠结构化
    # active ID 兜底，而是逐分句判语义。
    {
        "tag": "23-s7-e5-gap-prose",
        "cat": "return-S7-prose",
        "title": "把 D17-E5 的 finding 改回旧措辞「无重叠顺序（S7）」（S7 又是 active 缺口）",
        "expect": "G12", "expect_name": "s7-unsettled-mention",
        "expect_ok": "s7-unsettled-mention",
        "expect_substr": "无重叠顺序（S7）",
        "edits": [("text_in", YAML, S7PROSE_E5_HEAD, S7PROSE_E5_CUR, S7PROSE_E5_PRE)],
    },
    {
        "tag": "24-s7-e2-seven-enum",
        "cat": "return-S7-prose",
        "title": "把 D17-E2 的 finding 改回旧措辞「7 项规范静默（S1, S3, S4, S5, S6, S7, S8）」",
        "expect": "G12", "expect_name": "s7-unsettled-mention",
        "expect_ok": "s7-unsettled-mention",
        "expect_substr": "S6, S7, S8",
        "edits": [("text_in", YAML, S7PROSE_E2_HEAD, S7PROSE_E2_CUR, S7PROSE_E2_PRE)],
    },
    {
        "tag": "25-s7-consumer-seven-prose",
        "cat": "return-S7-prose",
        "title": "把 SPEC-103t 消费者的 na_runtime_note 改回旧措辞「七项在证据完整后仍为 OPEN/BLOCKED」",
        "expect": "G12", "expect_name": "active-count-six",
        "expect_ok": "active-count-six",
        "expect_substr": "七项在证据完整后仍为 OPEN/BLOCKED",
        "edits": [("text_in", YAML, S7PROSE_SPEC103_NODE, S7PROSE_NOTE_CUR, S7PROSE_NOTE_PRE)],
    },
    # ── SPEC-104t §9 resolution categories ──
    {"tag": "26-delete-current-decision", "cat": "§9-1",
     "title": "删除现行 ADR-1009/D2 decision",
     "expect": "G14", "expect_name": "decision-counts", "expect_substr": "现行 decision",
     "edits": [("drop_block", YAML, RES_D11_HEAD)]},
    {"tag": "27-reactivate-superseded-d1", "cat": "§9-1",
     "title": "把 ADR-1009/D1 从 superseded 重新放入 current",
     "expect": "G13", "expect_name": "superseded-singleton", "expect_substr": "D1",
     "edits": [("text", YAML, "    current:\n", "    current:\n    - id: ADR-1009/D1\n      adr: ADR-1009\n      decision: D1\n") ]},
    {"tag": "28-confirmation-record-missing", "cat": "§9-2",
     "title": "删除一条 decision 的确认记录",
     "expect": "G13", "expect_name": "decision-heading-verbatim", "expect_substr": "确认记录",
     "edits": [("text", ".xkw/knowledge/adr-1009-d11-rf0-operand-rules.md", "**确认记录**：D2 由用户于 2026-09-28 逐条确认。", "确认记录缺失。\n")]},
    {"tag": "29-fake-accepted", "cat": "§9-2",
     "title": "伪造 YAML 投影时点的 ADR 已 Accepted（实时 ADR 状态仍 Candidate）",
     "expect": "G13", "expect_name": "lifecycle-fields", "expect_substr": "Accepted",
     "edits": [("text", YAML, "  adr_state_observed_in_this_file: Candidate\n", "  adr_state_observed_in_this_file: Accepted\n")]},
    {"tag": "29b-mixed-adr-lifecycle", "cat": "lifecycle-post-activation",
     "title": "仅把一份 ADR 置 Accepted，制造 Candidate/Accepted 混合生命周期",
     "expect": "G13", "expect_name": "adr-state-lifecycle", "expect_ok": "adr-state-candidate", "expect_substr": "不得混合",
     "edits": [("text", ".xkw/knowledge/adr-1009-d11-rf0-operand-rules.md",
                "**状态**：Candidate", "**状态**：Accepted")]},
    {"tag": "30-current-html-authority", "cat": "§9-3",
     "title": "把注释段标为 current authority",
     "expect": "G17", "expect_name": "normative-exclusion", "expect_substr": "normative",
     "edits": [("text_in", YAML, RES_NORM_HEAD, "    normative: false\n", "    normative: true\n")]},
    {"tag": "31-candidate-cross-gap", "cat": "§9-4",
     "title": "把 Candidate 绑定到错误 gap",
     "expect": "G14", "expect_name": "candidate-closure", "expect_substr": "跨 gap",
     "edits": [("text_in", YAML, "    - candidate_id: CAND-D11-MOVE\n", "      gap: D11\n", "      gap: D12\n")]},
    {"tag": "32-d11-whitelist-missing", "cat": "§9-5",
     "title": "D11 白名单删除一项",
     "expect": "G15", "expect_name": "rule-set-recomputed", "expect_substr": "D11",
     "edits": [("text_in", YAML, RES_D11_RULE_HEAD, "      rf0_write_whitelist: [cs.eq-rf, cs.n-rf, cs.ne-rf, cs.p-rf, cs.z-rf, ld.o-rf, ld.t-rf, ldm.o-rf, ldm.t-rf, set.w-rf]\n", "      rf0_write_whitelist: [cs.eq-rf]\n")]},
    {"tag": "33-d12-not-sticky", "cat": "§9-6",
     "title": "D12 sticky OR 改为覆盖",
     "expect": "G15", "expect_name": "rule-semantics", "expect_substr": "sticky-OR",
     "edits": [("text_in", YAML, RES_D12_RULE_HEAD, "      hardware_update: sticky-OR\n", "      hardware_update: overwrite\n")]},
    {"tag": "34-d13-high-half", "cat": "§9-7",
     "title": "D13 NaN-boxing 高半部翻位",
     "expect": "G15", "expect_name": "rule-semantics", "expect_substr": "0xffffffff",
     "edits": [("text_in", YAML, RES_D13_RULE_HEAD, "      tetra_high_half_bits: '0xffffffff'\n", "      tetra_high_half_bits: '0xfffffffe'\n")]},
    {"tag": "35-d14-class-swap", "cat": "§9-8",
     "title": "D14 qcmp/scmp 类别互换",
     "expect": "G15", "expect_name": "rule-set-recomputed", "expect_substr": "D14",
     "edits": [("text_in", YAML, RES_D14_RULE_HEAD, "      quiet_class: [foqcmp, ftqcmp]\n", "      quiet_class: [foscmp, ftscmp]\n")]},
    {"tag": "36-d15-sign", "cat": "§9-9",
     "title": "D15 转换 NaN 保留负号",
     "expect": "G15", "expect_name": "rule-semantics", "expect_substr": "positive",
     "edits": [("text_in", YAML, RES_D15_RULE_HEAD, "      conversion_result_sign: positive\n", "      conversion_result_sign: input-sign\n")]},
     {"tag": "37-d15-conversion-payload", "cat": "§9-9",
      "title": "D15 转换丢弃 payload",
      "expect": "G13", "expect_name": "decision-behavior", "expect_substr": "ADR-1013/D4",
      "edits": [("text_in", YAML, "    - id: ADR-1013/D4\n",
                  "      behavior: fo2ft/ft2fo 按 SimRISC-03 规范正文传播 NaN payload；sNaN 转换置 NV 并返回 qNaN；覆盖早先 canonical-discard 选择\n",
                  "      behavior: fo2ft/ft2fo 丢弃 NaN payload；sNaN 转换置 NV 并返回 qNaN\n")]},
     {"tag": "38-d15-conversion-snan-nv", "cat": "§9-9",
      "title": "D15 转换漏 sNaN NV/qNaN",
      "expect": "G13", "expect_name": "decision-behavior", "expect_substr": "ADR-1013/D4",
      "edits": [("text_in", YAML, "    - id: ADR-1013/D4\n",
                  "      behavior: fo2ft/ft2fo 按 SimRISC-03 规范正文传播 NaN payload；sNaN 转换置 NV 并返回 qNaN；覆盖早先 canonical-discard 选择\n",
                  "      behavior: fo2ft/ft2fo 按 SimRISC-03 规范正文传播 NaN payload；sNaN 转换不置 NV 并返回 qNaN\n")]},
     {"tag": "39-d15-conversion-sign-positive", "cat": "§9-9",
      "title": "D15 转换结果保留负号",
      "expect": "G13", "expect_name": "decision-behavior", "expect_substr": "ADR-1013/D6",
      "edits": [("text_in", YAML, "    - id: ADR-1013/D6\n",
                  "      behavior: fo2ft/ft2fo 的 NaN 转换结果符号固定为正号\n",
                  "      behavior: fo2ft/ft2fo 的 NaN 转换结果符号保留输入符号\n")]},
     {"tag": "67-d15-arithmetic-canonical", "cat": "§9-9",
      "title": "D15 算术传播 payload/符号",
      "expect": "G13", "expect_name": "decision-behavior", "expect_substr": "ADR-1013/D1",
      "edits": [("text_in", YAML, "    - id: ADR-1013/D1\n",
                  "      behavior: 非格式转换的单 NaN 算术输入丢弃 payload 与符号，返回 canonical qNaN\n",
                  "      behavior: 非格式转换的单 NaN 算术输入传播 payload 与符号，返回 canonical qNaN\n")]},
     {"tag": "68-d15-arithmetic-qnan-nv", "cat": "§9-9",
      "title": "D15 算术 qNaN 错置 NV",
      "expect": "G13", "expect_name": "decision-behavior", "expect_substr": "ADR-1013/D5",
      "edits": [("text_in", YAML, "    - id: ADR-1013/D5\n",
                  "      behavior: 算术/多操作数中 qNaN 不置 NV、任一 sNaN 置 NV，结果均 canonical qNaN；不覆盖 D4/D6 的转换规则\n",
                  "      behavior: 算术/多操作数中 qNaN 置 NV、任一 sNaN 置 NV，结果均 canonical qNaN；不覆盖 D4/D6 的转换规则\n")]},
     {"tag": "69-d15-arithmetic-snan-nv", "cat": "§9-9",
      "title": "D15 算术漏 sNaN NV",
      "expect": "G13", "expect_name": "decision-behavior", "expect_substr": "ADR-1013/D5",
      "edits": [("text_in", YAML, "    - id: ADR-1013/D5\n",
                  "      behavior: 算术/多操作数中 qNaN 不置 NV、任一 sNaN 置 NV，结果均 canonical qNaN；不覆盖 D4/D6 的转换规则\n",
                  "      behavior: 算术/多操作数中 qNaN 不置 NV、任一 sNaN 不置 NV，结果均 canonical qNaN；不覆盖 D4/D6 的转换规则\n")]},
    {"tag": "37-d16-before-rounding", "cat": "§9-10",
     "title": "D16 tininess 改为舍入前",
     "expect": "G15", "expect_name": "rule-set-recomputed", "expect_substr": "after-rounding",
     "edits": [("text_in", YAML, RES_D16_RULE_HEAD, "      tininess_detection: after-rounding\n", "      tininess_detection: before-rounding\n")]},
    {"tag": "38-d17-priority", "cat": "§9-11",
     "title": "D17 ILLI/MALIGN 优先级互换",
     "expect": "G15", "expect_name": "d17-rule-table", "expect_substr": "ILLI",
     "edits": [("text_in", YAML, RES_D17_RULE_HEAD, "      fault_priority: [ILLI, MALIGN]\n", "      fault_priority: [MALIGN, ILLI]\n")]},
    {"tag": "39-s6-current-six", "cat": "§9-12",
     "title": "S6 退回 historical-six",
     "expect": "G15", "expect_name": "s6-scope-relation", "expect_substr": "current",
     "edits": [("text_in", YAML, RES_S6_HEAD, "      current_ten: [cs.eq-rf, cs.n-rf, cs.ne-rf, cs.p-rf, cs.z-rf, ld.o-rf, ld.t-rf, ldm.o-rf, ldm.t-rf, set.w-rf]\n", "      current_ten: [ld.o-rf, ld.t-rf, ldm.o-rf, ldm.t-rf, rd2rf, set.w-rf]\n")]},
    {"tag": "40-ldm-base", "cat": "§9-13",
     "title": "ldm/stm 基址改变",
     "expect": "G15", "expect_name": "rule-semantics", "expect_substr": "EA0",
     "edits": [("text_in", YAML, RES_D17_RULE_HEAD, "      ldm_stm_base: EA0 = rbhb + rdhc\n", "      ldm_stm_base: EA0 = rbhb\n")]},
    {"tag": "41-matrix-owner", "cat": "§9-14",
     "title": "resolution matrix owning consumer 错绑",
     "expect": "G16", "expect_name": "matrix-owner", "expect_substr": "cs.eq-rf",
     "edits": [("text_in", YAML, RES_MATRIX_FIRST, "    owning_consumer: QEMU-103t\n", "    owning_consumer: QEMU-101t\n")]},
    {"tag": "42-downstream-stale", "cat": "§9-15",
     "title": "下游任务书恢复七键陈旧门禁",
     "expect": "G18", "expect_name": "book-no-stale-gate", "expect_substr": "TESTCASES-101t",
     "edits": [("text", ".xkw/tasks/testcases/TESTCASES-101t-F1浮点schema与oracle接口冻结.md", "active 精确键集合为 {D17:S1,D17:S3,D17:S4,D17:S5,D17:S6,D17:S8}（六键）", "active 精确键集合为 {D17:S1,D17:S2,D17:S3,D17:S4,D17:S5,D17:S6,D17:S7,D17:S8}")]},
    {"tag": "43-history-mutate", "cat": "§9-16",
     "title": "历史 SPEC-103 任务书发生修改",
     "expect": "G19", "expect_name": "history-taskbook-digest", "expect_substr": "SPEC-103t",
     "edits": [("text", ".xkw/tasks/spec/SPEC-103t-F1语义缺口证明与候选ADR输入.md", "# SPEC-103t", "# SPEC-103t (mutated)")]},
]


# ═══════════════════════════ 临时树 ═══════════════════════════

class TimeoutResult:
    """CompletedProcess-shaped result for a bounded command."""

    def __init__(self, cmd, stdout, stderr):
        self.args = cmd
        self.returncode = 124
        self.stdout = stdout or ""
        self.stderr = stderr or ""


def _tree_diagnostics(tree: Path) -> str:
    """Filesystem-only diagnostics; never follows a repository link silently."""
    if not tree.exists():
        return f"tree_exists=false path={tree}"
    links = []
    same_inode = []
    try:
        source_stat = SOURCE_ROOT.stat()
    except OSError as exc:
        return f"tree={tree} source_stat_error={exc!r}"
    for p in tree.rglob("*"):
        try:
            st = p.lstat()
            if p.is_symlink():
                links.append(f"{p} -> {os.readlink(p)}")
            if p.is_file():
                # A hardlink/reflink cannot be distinguished portably from stat;
                # equal device+inode is the unsafe case we must reject.
                if (st.st_dev, st.st_ino) == (source_stat.st_dev, source_stat.st_ino):
                    same_inode.append(str(p))
        except OSError as exc:
            links.append(f"{p}: {exc!r}")
    return (f"tree={tree} tree_dev_ino={(tree.stat().st_dev, tree.stat().st_ino)} "
            f"symlinks={links[:8]} same_inode={same_inode[:8]}")


def sh(cmd, cwd, *, case="<setup>", stage="subprocess", timeout=30.0,
       emit_timeout=True):
    """Run every child with a stage-specific bound and captured diagnostics."""
    try:
        return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True,
                              timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        out = (exc.stdout or "")
        err = (exc.stderr or "")
        if emit_timeout:
            print(f"[TIMEOUT] case={case} stage={stage} timeout={timeout}s")
            print(f"  command={subprocess.list2cmdline(cmd)}")
            print(f"  stdout={out!r}")
            print(f"  stderr={err!r}")
            status = sh(["git", "-c", "core.quotePath=false", "status",
                         "--porcelain", "--untracked-files=all"], cwd,
                        case=case, stage="timeout-diagnostic-status", timeout=5,
                        emit_timeout=False)
            print(f"  target_tree_status_rc={status.returncode} "
                  f"status={status.stdout!r}{status.stderr!r}")
            print(f"  nested_temp_symlink_diagnostics={_tree_diagnostics(cwd)}")
        return TimeoutResult(cmd, out, err)


def build_tree(tag: str) -> Path:
    tree = TMP_ROOT / f"ce-{tag}"
    try:
        tree.relative_to(SOURCE_ROOT)
    except ValueError:
        pass
    else:
        raise SystemExit(f"[{tag}] refusing nested temporary tree under source root: {tree}")
    if tree.exists():
        shutil.rmtree(tree)
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    # symlinks=False is intentional: the source snapshot must contain bytes,
    # never links into the real repository or another nested worktree.
    shutil.copytree(SOURCE_ROOT, tree, ignore=COPY_IGNORE, symlinks=False)
    for cmd in (["git", "init", "-q", "-b", "main"],
                ["git", "config", "user.email", "ce@localhost"],
                ["git", "config", "user.name", "counterexample"],
                ["git", "config", "commit.gpgsign", "false"]):
        r = sh(cmd, tree, case=tag, stage="build-tree-config", timeout=30)
        if r.returncode != 0:
            raise SystemExit(f"[{tag}] {' '.join(cmd)} 失败: {(r.stdout + r.stderr)[:300]}")
    for cmd in (["git", "add", "-A"],
                ["git", "commit", "-q", "--no-verify", "-m", "ce baseline"]):
        r = sh(cmd, tree, case=tag, stage="build-tree-commit", timeout=60)
        if r.returncode != 0:
            raise SystemExit(f"[{tag}] {' '.join(cmd)} 失败: {(r.stdout + r.stderr)[:300]}")
    # Validate the complete copied tree, not merely its top-level directory.
    links = [p for p in tree.rglob("*") if p.is_symlink()]
    if links:
        raise SystemExit(f"[{tag}] unsafe symlink(s) in temporary tree: {links[:8]}")
    ignored_parts = {".git", ".cache", ".work", "__pycache__"}
    source_files = {p.relative_to(SOURCE_ROOT): p for p in SOURCE_ROOT.rglob("*")
                    if p.is_file() and not any(part in ignored_parts
                                               for part in p.relative_to(SOURCE_ROOT).parts)}
    # The explicit inode check catches hardlinks; byte-copying is validated by
    # requiring every copied regular file to have a distinct device+inode.
    for rel, src in source_files.items():
        dst = tree / rel
        if dst.exists() and dst.is_file():
            ss, ds = src.stat(), dst.stat()
            if (ss.st_dev, ss.st_ino) == (ds.st_dev, ds.st_ino):
                raise SystemExit(f"[{tag}] unsafe shared inode: {rel}")
    return tree


def run_checker(tree: Path, verbose: bool = False) -> dict:
    cmd = [sys.executable, CHECKER]
    if verbose:
        cmd.append("-v")
    r = sh(cmd, tree, case=tree.name.removeprefix("ce-"),
           stage="checker-verbose" if verbose else "checker", timeout=30)
    out = r.stdout + r.stderr
    fails = list(FAIL_RE.finditer(out))
    okmarks = sorted({(m.group("cat"), m.group("name")) for m in OK_RE.finditer(out)})
    m = SUMMARY_RE.search(out)
    return {
        "rc": r.returncode,
        "cats": sorted({m2.group("cat") for m2 in fails}),
        "names": sorted({m2.group("name") for m2 in fails}),
        "fail_lines": [m2.group(0).strip() for m2 in fails],
        "details": [m2.group("detail") for m2 in fails],
        "okmarks": okmarks,
        "summary": (f"，通过 {m.group(1)} 项 / 失败 {m.group(2)} 项" if m else ""),
        "out": out,
    }


def changed_paths(tree: Path):
    r = sh(["git", "-c", "core.quotePath=false", "diff", "--name-only"], tree,
           case=tree.name.removeprefix("ce-"), stage="changed-paths", timeout=10)
    return [x for x in r.stdout.splitlines() if x.strip()]


def dirty_paths(tree: Path):
    r = sh(["git", "-c", "core.quotePath=false", "status", "--porcelain",
            "--untracked-files=all"], tree, case=tree.name.removeprefix("ce-"),
           stage="dirty-paths", timeout=10)
    return [x for x in r.stdout.splitlines() if x.strip()]


def restore_tree(tree: Path, tag: str) -> bool:
    """Restore one case before any return, including diagnostic failures."""
    tree.resolve().relative_to(TMP_ROOT.resolve())
    r = sh(["git", "checkout", "--", "."], tree, case=tag,
           stage="restore-checkout", timeout=30)
    c = sh(["git", "clean", "-fdq"], tree, case=tag,
           stage="restore-clean", timeout=30)
    left = dirty_paths(tree)
    print(f"  还原:   git checkout rc={r.returncode}，git clean rc={c.returncode} "
          f"（清掉未跟踪注入文件）")
    print(f"          残留脏文件 {len(left)}: {left[:5]}")
    return r.returncode == 0 and c.returncode == 0 and not left


def preflight_anchors(ces) -> list:
    """**在建任何临时树之前**逐条验证注入锚点在**真实仓库**的当前文件里唯一命中。

    这一步是为了在花几分钟建 13 棵 8.6 MB 的树之前就把「锚点写错 / 锚点不唯一」
    全部暴露出来。`apply_edit` 本身也会拒执行，两处校验是独立的：这里验证的是
    「这份反例清单在当前仓库上可用」，那里验证的是「树里的改动确实落到了预期位置」。
    """
    cache, bad = {}, []
    for ce in ces:
        for edit in ce["edits"]:
            kind = edit[0]
            if kind == "new_file":
                tgt = SOURCE_ROOT / edit[1]
                if tgt.exists():
                    bad.append(f"CE-{ce['tag']}: new_file 目标 {edit[1]} 已存在")
                continue
            rel = edit[1]
            if rel not in cache:
                p = SOURCE_ROOT / rel
                if not p.exists():
                    bad.append(f"CE-{ce['tag']}: 注入目标不存在 {rel}")
                    cache[rel] = None
                else:
                    cache[rel] = p.read_text(encoding="utf-8")
            text = cache[rel]
            if text is None:
                continue
            try:
                if kind == "text":
                    if text.count(edit[2]) != 1:
                        bad.append(f"CE-{ce['tag']}: text 锚点命中 "
                                   f"{text.count(edit[2])} 次（须 1）: {edit[2][:70]!r}")
                elif kind in ("drop_block", "dup_block", "insert_after"):
                    _locate(text, edit[2])
                elif kind == "empty_field_in":
                    s = _locate(text, edit[2])
                    lines = text.splitlines(keepends=True)
                    e = _block_end(lines, s)
                    n = sum(1 for j in range(s, e) if lines[j] == edit[3])
                    if n != 1:
                        bad.append(f"CE-{ce['tag']}: empty_field_in 字段键行 {edit[3]!r} "
                                   f"在 {edit[2][:40]!r} 块内命中 {n} 次（须 1）")
                elif kind == "text_in":
                    s = _locate(text, edit[2])
                    lines = text.splitlines(keepends=True)
                    body = "".join(lines[s:_block_end(lines, s)])
                    if body.count(edit[3]) != 1:
                        bad.append(f"CE-{ce['tag']}: text_in 块内锚点命中 "
                                   f"{body.count(edit[3])} 次（须 1）: {edit[3][:70]!r}")
                else:
                    bad.append(f"CE-{ce['tag']}: 未知注入类型 {kind}")
            except SystemExit as exc:
                bad.append(f"CE-{ce['tag']}: {exc}")
    return bad


# ═══════════════════════════ 主流程 ═══════════════════════════

def run_one(ce: dict, verbose: bool) -> bool:
    tag, expect, expect_name = ce["tag"], ce["expect"], ce["expect_name"]
    exp_sub = ce.get("expect_substr", "")
    # 逐条类（`matrix-row-*` / `applic-<节点>` / `node-*` / `cand-*`）在基线上
    # **一条都不报错**，因此成功时**不会**有属于自己的 OK 行；它们共享同一分支
    # 的聚合 OK 行（`matrix-rows` / `applicability` / `node-detail` /
    # `cand-detail`）。`expect_ok` 就是声明「用哪一条聚合 OK 行来证明本反例瞄准
    # 的这段代码**真的跑过**」，而 FAIL 侧仍然只认 `expect_name`。
    expect_ok = ce.get("expect_ok", expect_name)
    print(f"\n{'─' * 78}\nCE-{tag} [{ce['cat']}]: {ce['title']}\n{'─' * 78}")
    ok = True
    tree = build_tree(tag)
    print(f"  临时树: {tree}   检查器: {CHECKER}")

    # ── 基线必须先绿 ──
    base = run_checker(tree)
    if base["rc"] != 0:
        print(f"  [FAIL] 基线就不绿（rc={base['rc']}），本反例无说服力：\n"
              f"         {base['out'][-500:]}")
        restore_tree(tree, tag)
        return False
    print(f"  基线:   rc=0{base['summary']}")

    # ── 基线里本反例瞄准的检查必须真的**跑过**（`-v` 取 OK 行）──
    if (expect, expect_ok) not in base["okmarks"]:
        # FAIL: 该检查**成功时**才写 OK 行；只跑过但不 OK 的基线不可信。
        vb = run_checker(tree, verbose=True)
        base["okmarks"] = vb["okmarks"]
        if (expect, expect_ok) not in base["okmarks"]:
            print(f"  [FAIL] 基线里没有 [ok] {expect} {expect_ok} 这一行 —— "
                  f"本反例瞄准的检查要么没被执行、要么基线就没过")
            restore_tree(tree, tag)
            return False
    witness = (f"[ok] {expect} {expect_ok}"
               if expect_ok == expect_name
               else f"[ok] {expect} {expect_ok}（{expect_name} 所在分支的聚合 OK 行）")
    print(f"  基线组: {witness} 确实被跑到 ✓")

    # ── 注入 ──
    try:
        apply_edits(tree, ce["edits"])
    except SystemExit as exc:
        print(f"  [FAIL] 注入脚本拒绝执行: {exc}")
        restore_tree(tree, tag)
        return False
    # `git diff --name-only` 是**每一个**反例的强制门控；不允许拿未跟踪文件
    # `git status` 的非空结果替代它。new_file 型反例必须另有一个已跟踪编辑。
    ch = changed_paths(tree)
    dy = dirty_paths(tree)
    print(f"  git diff --name-only → {len(ch)} 个: {ch}")
    print(f"  git status -uall      → {len(dy)} 个: {dy[:6]}")
    if not ch:
        print("  [FAIL] diff 门控失败：git diff --name-only 为空；每个反例必须改动已跟踪文件")
        restore_tree(tree, tag)
        return False

    # ── 注入后必须 FAIL，且命中的**具体检查名**就是本反例瞄准的那一个 ──
    bad = run_checker(tree)
    print(f"  注入后: rc={bad['rc']}{bad['summary']}")
    print(f"          FAIL 组={bad['cats']}  检查名={bad['names']}")
    if bad["rc"] == 0:
        print("  [FAIL] 注入后仍全绿 → 检查器对该缺陷不敏感")
        return False
    if not bad["names"]:
        print(f"  [FAIL] 非零退出但无语义 FAIL 行（异常退出不算语义 FAIL）：\n"
              f"         {bad['out'][-500:]}")
        return False
    for ln in bad["fail_lines"][:5]:
        print(f"           {ln[:150]}")
    if expect not in bad["cats"]:
        print(f"  [FAIL] 期望 FAIL 组 {expect!r}，实际 {bad['cats']} —— "
              f"抓到的不是本反例瞄准的那一组检查")
        ok = False
    if expect_name not in bad["names"]:
        print(f"  [FAIL] 期望 FAIL 检查名 {expect_name!r}，实际 {bad['names']} —— "
              f"同组内另一条检查报红不算数")
        ok = False

    # ── 目标检查的明细必须**点名**本反例注入的对象（不许泛化断言蒙混）──
    if bad["rc"] != 0 and exp_sub:
        per_name = {}
        for m2 in FAIL_RE.finditer(bad["out"]):
            per_name.setdefault(m2.group("name"), []).append(m2.group("detail"))
        blob = "\n".join(per_name.get(expect_name) or bad["details"])
        if exp_sub in blob:
            print(f"  点名:   [{expect_name}] 的明细含 {exp_sub!r} ✓")
        else:
            print(f"  [FAIL] [{expect_name}] 的 FAIL 明细**未**点名 {exp_sub!r} —— "
                  f"诊断不具体，无法确认抓到的是本反例那一处")
            ok = False

    # ── 还原（必须回到干净）──
    # `git checkout -- .` 只还原**已跟踪**文件；`new_file` 型注入造的是未跟踪文件，
    # 必须再 `git clean -fd` 才能真正复原。两者都只在本脚本自建的临时树里执行
    # （tree 必在 TMP_ROOT 之下，见下方断言），**从不**在真实仓库上跑。
    if not restore_tree(tree, tag):
        print("  [FAIL] 还原不彻底")
        ok = False

    # ── 还原后必须重新全绿 ──
    again = run_checker(tree)
    print(f"  还原后: rc={again['rc']}{again['summary']}")
    if again["rc"] != 0:
        print(f"  [FAIL] 还原后仍不绿：\n         {again['out'][-500:]}")
        ok = False

    print(f"  → CE-{tag}: {'PASS（能失败且可复原）' if ok else 'FAIL'}")
    return ok


def add_generic_behavior_counterexamples() -> None:
    """Create one official, named reversal case for every projected behavior.

    The checker owns the independent clause inventory; this loop deliberately
    does not copy expected text from the YAML.  Each generated case edits one
    tracked behavior field to an explicit reversal marker, and therefore proves
    that every current/supplemental behavior has a reachable named FAIL path.
    """
    sys.path.insert(0, str(SOURCE_ROOT / "tools/spec"))
    import check_f1_gap_proofs as checker  # noqa: WPS433
    text = (SOURCE_ROOT / YAML).read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    for ident in checker.PIN_BEHAVIOR_CLAUSES:
        anchor = "    - id: %s\n" % ident
        start = _locate(text, anchor)
        end = _block_end(lines, start)
        behavior_lines = [line for line in lines[start:end]
                          if line.startswith("      behavior: ")]
        if len(behavior_lines) != 1:
            raise SystemExit("%s behavior 锚点不是恰好一处" % ident)
        old = behavior_lines[0]
        tag = "behavior-reversal-" + ident.replace("/", "-")
        COUNTEREXAMPLES.append({
            "tag": tag, "cat": "behavior-audit",
            "title": "%s behavior 反向注入" % ident,
            "expect": "G13", "expect_name": "decision-behavior",
            "expect_substr": ident,
            "edits": [("text_in", YAML, anchor, old,
                       "      behavior: REVERSED %s\n" % ident)],
        })


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="F1 缺口证明检查器反例注入门控")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--rm-trees", action="store_true", help="跑完删除临时树")
    ap.add_argument("--only", default=None, help="只跑 tag 前缀匹配的反例")
    ap.add_argument("--source-root", type=Path, default=REPO_ROOT,
                    help="独立、字节复制的 source tree（默认真实仓库）")
    args = ap.parse_args(argv)

    global SOURCE_ROOT
    SOURCE_ROOT = args.source_root.resolve()
    if not SOURCE_ROOT.is_dir() or SOURCE_ROOT == TMP_ROOT.resolve():
        raise SystemExit(f"invalid source root: {SOURCE_ROOT}")

    add_generic_behavior_counterexamples()
    ces = [c for c in COUNTEREXAMPLES
           if not args.only or c["tag"].startswith(args.only)]

    t0 = time.time()
    print("=" * 78)
    print("test_f1_gap_proof_counterexamples: 反例注入门控")
    print(f"  仓库   : {SOURCE_ROOT}")
    print(f"  临时树 : {TMP_ROOT}/ce-<tag>/（每项一棵，互不复用）")
    print(f"  反例数 : {len(ces)}")
    print("=" * 78)

    # ── 锚点预检：先在**真实仓库**上逐条验证唯一命中，再花时间建树 ──
    bad = preflight_anchors(ces)
    if bad:
        print(f"\n  [FAIL] 锚点预检失败 {len(bad)} 条（不建任何临时树）：")
        for b in bad:
            print(f"         {b}")
        return 1
    print(f"  锚点预检: {len(ces)} 个反例的全部锚点在真实仓库里唯一命中 ✓\n")

    results = []
    for ce in ces:
        try:
            results.append((ce["tag"], ce["cat"], run_one(ce, args.verbose)))
        except SystemExit as exc:
            print(f"  [FAIL] 注入脚本异常: {exc}")
            results.append((ce["tag"], ce["cat"], False))

    npass = sum(1 for _, _, o in results if o)
    print(f"\n{'=' * 78}\n汇总：")
    for tag, cat, o in results:
        print(f"  {'PASS' if o else 'FAIL'}  CE-{tag:<26} [{cat}]")
    print(f"  {npass}/{len(results)} 个反例被成功抓住（注入后 FAIL + 还原后 PASS）")
    print(f"  用时 {time.time() - t0:.1f}s")
    print("=" * 78)

    if args.rm_trees:
        for tag, _c, _o in results:
            shutil.rmtree(TMP_ROOT / f"ce-{tag}", ignore_errors=True)
        print(f"  已清理临时树: {TMP_ROOT}/ce-*")

    return 0 if npass == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
