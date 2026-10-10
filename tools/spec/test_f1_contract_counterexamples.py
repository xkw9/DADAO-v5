#!/usr/bin/env python3
"""test_f1_contract_counterexamples.py — SPEC-102t 验收闸门的**反例注入门控**。

本脚本证明两个校验器 **能失败**：`check_f1_contract.py`（合约/编码自洽闸门）与
`check_f1_citations.py`（spec 行号引用闸门）。对每个反例：

  1. 在 `/tmp/opencode/SPEC-102t/ce-<tag>/` 建一棵**独立临时树**（工作区快照 +
     `git init` 基线提交）。**从不**在真实仓库上注入。
  2. 施加一处最小注入。
  3. 断言 `git diff --name-only` **非空**（防「空注入导致注入后仍全绿」）。
  4. 跑校验器，断言**非零退出**且确有 `[X] FAIL` 行 —— 只看退出码不够，
     一个 traceback 也返回非零，必须确认是**语义 FAIL**；并断言 FAIL 的
     **类别**就是本反例瞄准的那一个；若反例带 `expect_substr`，还要断言 FAIL
     明细**点名了那条 identity / 那个宽度**（否则「一律说『对齐不符』」的
     泛化断言也能蒙混过关）。
  5. `git checkout -- .` 还原，断言工作区回到干净（`git status --porcelain` 空），
     再跑一次校验器，断言**恢复全绿**（rc=0）。

反例清单（27 项，对应 AGENTS.md「验证脚本必须能失败」）：

  CE-1 删除一个目标 identity               注入层 spec        期望 A 组 FAIL
  CE-2 在 spec QFC 表中重复一个 identity      注入层 spec        期望 A 组 FAIL
  CE-3 改错目标 identity 的编码（ha）        注入层 YAML        期望 C 组 FAIL
  CE-4 移除一个目标 identity 的 F1 scope    注入层 YAML        期望 B 组 FAIL
  CE-5 把一个 OPEN facet 改成 determined    注入层 数据+重渲染  期望 D 组 FAIL
  CE-6 给非 FP 的 cfx 记录加 F1 scope       注入层 YAML        期望 B 组 FAIL
  CE-7 在合约层重复一条记录                  注入层 YAML        期望 B 组 FAIL
  CE-8 把一条 spec 引用誊错一行（:128→:129） 注入层 合约 md      期望 锚点未命中
  CE-9 把主张行的引用换成邻行（:191→:192）  注入层 合约 md      期望 锚点未命中
  CE-10 把 §6.1「对应 facet」整列打回退化值   注入层 渲染器+重渲染 期望 F 组 FAIL
  CE-11..CE-18 逐条抹掉 8 条 RF 存取的**对齐谓词**（每条一个用例）
              注入层 数据+重渲染  期望 C 组 FAIL（且 FAIL 行必须点名该 identity
              与应有宽度 —— 数据层/落盘 YAML/合约 md 三层**自洽地一起错**，
              57 项旧检查全绿，只有以 spec 原句为判据的 C6/C8 能抓住）
  CE-19 把某条的对齐宽度改成错值（4↔8）     注入层 数据+重渲染  期望 C 组 FAIL
  CE-20 让 S8 重新声称「legality 因 S2 记 partial」（**真实缺陷**）
              注入层 数据+重渲染  期望 H 组 FAIL
  CE-21 把 §5.4 钉死汇总表的 partial 数改错   注入层 合约 md      期望 H 组 FAIL
  CE-22 抹掉 spec 的对齐原句                 注入层 spec        期望 C 组 fail-closed
  CE-23 把 §4.8 facet 断言的静默项编号誊错   注入层 渲染器+重渲染 期望 H 组 FAIL
  CE-24 把 §4.8 facet 断言改成 spec-determined（判据消失）
              注入层 渲染器+重渲染 期望 H 组 fail-closed
  CE-25 把 S3 的受影响集缩小（只留 ftcls）  注入层 数据+重渲染 期望 H 组 FAIL
              （专打 H1b 的**反向**核对：正向仍成立，但 `focls` 的实际 partial
              变成「无人认领」；不反向核对的话这一条会全绿放过）
  CE-26 断言点名不存在的静默项 S9         注入层 渲染器+重渲染 期望 H 组 FAIL
  CE-27 断言的 facet 名誊错（legalty）     注入层 渲染器+重渲染 期望 H 组 FAIL

CE-5 是本脚本最关键的一项：它把某个 `open-blocked` facet **自洽地**改成
`spec-determined`（连同 open_items、opcodes.yaml、合约 md 一起重新渲染，全程
内部一致），用来堵死「各层互相印证所以假绿」的漏洞。只有检查器内部
`PINNED_OPEN` / `PINNED_MATRIX` 这张**外部字面量基准表**能抓住它。

CE-11..CE-19 走的正是**第二次**「自洽地错」：CE-5 那一版检查器有
`PINNED_OPEN` 兜底，但谓词**集合**没有任何外部基准，一次顺序 `dict.update()`
覆盖就让 6 条 identity 静默丢掉 SimRISC-03:25 要求的 `aligned(4)`/`aligned(8)`，
57 项全绿。现在 C6/C8 以 **spec 原句**为判据，故这 9 个用例逐条必须 FAIL。
CE-20/CE-21/CE-23..CE-27 走的是第三条路：md 的**手写散文**（§7.1 处置、§5.4 汇总表、
§4.8 表格行）不在渲染器的**数据**推导路径上，`--check` 只能保证「md = 渲染器输出」，
管不了「这句散文说的是不是真的」，只能靠 H 组「叙述 ↔ facet 表」对账。
CE-24 专门打**判据消失**这一支：把断言改成 spec-determined 后 CLAIM_RE 命中数变 0，
若 H1b 不 fail-closed 就会因「无断言 ⇒ 无矛盾」而**空转放行**。

CE-9 证明 `check_f1_citations.py` 第 3 层的 (b) 侧（**md 侧主张必须引到该坐标**）
不是摆设：注入后 spec 侧关键词**仍然命中**（SimRISC-00:192 同样含 `hd[5:0]`），
只有「主张段落是否还引 :191」这一条能抓住它 —— 第 1/2 层（范围检查）全绿。

CE-8 与 CE-10 各揭穿过一个**本任务真实发生过的检查器漏洞**：
CE-8 前，(b) 侧按「段落」匹配，而 §4.1 表格 6 行都引 `:128`，把其中一行誊成
`:129` 时其余 5 行仍满足条件 → 假绿；改为**按 markdown 块**（表格行各自成块）
匹配后抓住。CE-10 前，§6.1「对应 facet」整列退化成「（D17 兜底）」而 F 组查不到；
补 F9 后抓住。两者都曾先让反例**真的漏过去**，再回头修检查器。

YAML 注入一律用**结构化记录手术**（按 `- insn:` 定位记录块），不用文本锚点 ——
锚点容易猜错字段（ftsub 的 tetra_high_half 其实是 open-blocked 而非 n/a），
猜错就会变成空注入或注错地方。

用法：
    python3 tools/spec/test_f1_contract_counterexamples.py [-v] [--rm-trees]
退出码：0 = 全部反例「注入后 FAIL 且还原后 PASS」；1 = 有反例未被抓住。
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TMP_ROOT = Path("/tmp/opencode/SPEC-102t")
CHECKER = "tools/spec/check_f1_contract.py"
CITATIONS = "tools/spec/check_f1_citations.py"
RENDERER = "tools/spec/f1_render_contract.py"

#: 每种校验器的 FAIL 行正则：`(?P<cat>…)` 捕获的就是**类别** —— 反例的
#: "expect" 必须逐字等于它。只断言「非零退出」不够：一个 traceback 也是非零，
#: 一个范围越界也能凑合蒙混；必须确认是**本反例瞄准的那一类**语义 FAIL。
CHECKERS = {
    "contract": {
        "path": CHECKER,
        "fail_re": re.compile(r"^\s*\[(?P<cat>[A-I])\] FAIL.*$", re.M),
        "sum_re": re.compile(r"通过 (\d+) 项，失败 (\d+) 项"),
        "detail_re": None,          # FAIL 行自带明细，无需再摘
    },
    "citations": {
        "path": CITATIONS,
        "fail_re": re.compile(r"^\[FAIL\]\s*(?P<cat>[^\s:：]+)[^\n]*[:：]", re.M),
        "sum_re": None,
        # FAIL 头只说「N 条」，指认是哪条主张要看下面的明细行
        "detail_re": re.compile(r"^\s+- \S.*$", re.M),
    },
}

#: 不复制进临时树的目录（与本任务无关；.git 必须排除以便 git init）
COPY_IGNORE = shutil.ignore_patterns(".git", ".cache", ".work", "__pycache__")

SPEC00 = "spec/SimRISC-00-指令系统设计.md"
SPEC03 = "spec/SimRISC-03-浮点类指令.md"
DATA = "tools/spec/f1_contract_data.py"
OPC = "contracts/opcodes.yaml"
CONTRACT_MD = ".xkw/knowledge/contract-f1-floating.md"

# ── CE-11..CE-19：数据层「逐条抹掉 / 改错一个对齐谓词」 ──
#
# 注入点选在合法性谓词声明块的**末尾**追加一行收窄：
#   * 这样数据层照常 import 成功，不会以 ValueError/NameError 崩掉；
#   * 改完再 `--check` 重渲染，于是 opcodes.yaml 与合约 md **跟着一起错**，
#     三层内部完全自洽 —— D6/B/E/G 全部照样绿；
#   * 因此只有「以 spec 原句为判据」的 C6/C8 会红，且 FAIL 行必须点名
#     **具体 identity + 应有宽度**（由 `expect_substr` 机器断言）。
LAST_PRED_DECL = '_merge_preds(LEGALITY_BY_MNEMONIC, ROOTLOG_LOG, "log_base_in_0_1_2")\n'

# ── CE-25：S3 的受影响集被**缩小**（只留 ftcls）—— 正向仍成立（ftcls 确是
# partial），但 `focls` 的实际 partial 变成「无人认领」；专打 H1b 的**反向**核对
# （「漏写一条 partial 照样绿」这个后门）。
# 必须**同时**改 `SPEC_SILENT_MNEMONICS` 与 S3 的 `affected` 散文并重渲染：
# 只改前者会让 H3（§7.1 点名集合 ↔ 数据层）先红，测的就不是反向那一支了。
S3_MNEMONICS_OLD = '    "S3": ("ftcls", "focls"),'
S3_MNEMONICS_NEW = '    "S3": ("ftcls",),'
S3_AFFECTED_OLD = '        "affected": "ftcls、focls",'
S3_AFFECTED_NEW = '        "affected": "ftcls",'

# ── CE-11..CE-19 相关：8 条 RF 存取的 (助记符, identity, 应有宽度) ──
#: 顺序 = 规范原句里两组各自的顺序
ALIGN_TARGETS = (
    ("ld.t", "ld.t-rf", 4), ("st.t", "st.t-rf", 4),
    ("ldm.t", "ldm.t-rf", 4), ("stm.t", "stm.t-rf", 4),
    ("ld.o", "ld.o-rf", 8), ("st.o", "st.o-rf", 8),
    ("ldm.o", "ldm.o-rf", 8), ("stm.o", "stm.o-rf", 8),
)

#: 逐条**收窄**某一条 identity 的对齐谓词集合（去掉 `aligned(...)`）。
#: 收窄而不是替换整个列表：这样其余批次的谓词（rf0_dst_allowed、三条 ILLI…）
#: 仍然在，注入**只**缺对齐这一件事实，诊断才干净。
def _drop_align_line(mnem: str) -> str:
    return (f'LEGALITY_BY_MNEMONIC["{mnem}"] = [p for p in '
            f'LEGALITY_BY_MNEMONIC["{mnem}"] if not p.startswith("aligned(")]\n')


#: 把某条的对齐宽度改**错**（4↔8）—— 谓词还在，宽度错。
def _wrong_width_line(mnem: str, good: int) -> str:
    bad = 8 if good == 4 else 4
    return (f'LEGALITY_BY_MNEMONIC["{mnem}"] = ["aligned({bad})" if p == '
            f'"aligned({good})" else p for p in LEGALITY_BY_MNEMONIC["{mnem}"]]\n')


#: CE-11..CE-18：逐条抹掉 8 条 RF 存取的**对齐谓词**，一个 identity 一例。
#: 每例的 `expect_substr` 都是该条 identity 的**完整 identity 名**，
#: 迫使 C6 的诊断必须点名「谁缺了、应是多少字节」。
ALIGN_DROP_CES = [
    {
        "tag": f"1{idx}-drop-align-{mnem.replace('.', '-')}",
        "title": f"逐条抹掉 {insn} 的对齐谓词（{mnem} 应 aligned({w})）",
        "expect": "C",
        "rerender": True,
        "expect_substr": insn,
        "edits": [("text", DATA, LAST_PRED_DECL,
                   LAST_PRED_DECL + _drop_align_line(mnem))],
    }
    for idx, (mnem, insn, w) in enumerate(ALIGN_TARGETS, start=1)
]

# ── CE-19：把 `ldm.t` 的 4 字节对齐**改错**成 8 字节（谓词在、宽度错）──
WIDTH_WRONG_MNEM, WIDTH_WRONG_INSN, WIDTH_WRONG_GOOD = "ldm.t", "ldm.t-rf", 4

# ── CE-20：让 S8 重新声称「`legality` facet 因 S2 记 partial」（真实缺陷） ──
S8_DECISION_OLD = (
    '        "decision": "未决。合约只登记签名、对齐与三条 ILLI 谓词，**不**从 SimRISC-01 "\n'
    '                    "外推地址组合/步长/重叠顺序。本项只落在 `semantics` facet"\n'
    '                    "（4 条 ldm/stm 记 **partial**）。`legality` facet **不**因 S2 或 "\n'
    '                    "S8 记 partial：S2 已证明 §存取RF 的有效范围与另两节一致（无行为"\n'
    '                    "后果，见 S2 处置），S8 缺的是**内存侧语义**、不是合法性谓词；"\n'
    '                    "故这 4 条的 `legality` 仍是 spec-determined。内存侧语义缺口不在 "\n'
    '                    "D11–D17 范围内，登记为 F1 实现前必须补的规范项。",\n'
)
# 这正是缺陷**修复前**的原文（与 S2 的「legality 也不因此记 partial」直接矛盾）
S8_DECISION_NEW = (
    '        "decision": "未决。合约只登记签名、对齐与三条 ILLI 谓词，**不**从 SimRISC-01 "\n'
    '                    "外推地址组合/步长/重叠顺序。`legality` facet 因 S2 记 partial，"\n'
    '                    "但内存侧语义缺口不在 D11–D17 范围内，登记为 F1 实现前必须补的规范项。",\n'
)

# ── CE-21：把 §5.4 钉死汇总表的 legality partial 数改错（手写散文，不在生成区）──
SUMMARY_ROW_OLD = "| `legality` | 0 | 2 | 62 spec-determined |"
SUMMARY_ROW_NEW = "| `legality` | 0 | 4 | 60 spec-determined |"

# ── CE-23/24：H1b 的两支（模板手写的「静默项 Sn → facet 记 partial」断言）──
# 注入点在**渲染器 TEMPLATE**（§4.8 表格行），重渲染后 md 与渲染器仍自洽，
# 于是 G 组（--check）照样绿，只有以**实际 facet 归属**为判据的 H1b 会红。
CLS_CLAIM_OLD = "| 静默项 **S3** → `legality` 记 **partial** |"
# CE-23：把静默项编号誊错（S3 → S2）—— S2 点名的 4 条 ldm/stm 的 legality
#         实为 spec-determined，正向核对必须点名报出。
CLS_CLAIM_WRONG_SID = "| 静默项 **S2** → `legality` 记 **partial** |"
# CE-24：把断言整个改成 spec-determined —— CLAIM_RE 命中数变 0，
#         H1b 必须 fail-closed 报「判据消失」，不得因「无断言 = 无矛盾」而放行。
CLS_CLAIM_GONE = "| 静默项 **S3** → `legality` 记 spec-determined |"
# CE-26：点名一个**不存在的静默项** S9 —— 断言引用的静默项必须真实存在。
CLS_CLAIM_BAD_SID = "| 静默项 **S9** → `legality` 记 **partial** |"
# CE-27：把 facet 名誊成一个不存在的 facet 名 —— 11 个 facet 之外的名字必须报出。
CLS_CLAIM_BAD_FACET = "| 静默项 **S3** → `legalty` 记 **partial** |"

# ── CE-28..CE-36：D17 OPEN-ID ledger 的 I 组台账核对 ──
#
# 这一组专打「下游门禁台账」本身。D/H 组都看不到它：台账少一行、多一个 `D17:S2`、
# 某行被写成 `PASS`/`active`、消费者被清空、受影响 identity 写错或漏掉、facet 写错、
# `D17:S2` 的 trace-only 注记被削短 —— 上述每一样在改动前都能让 68 项旧检查全绿。
# 注入一律打在**数据层** `f1_contract_data.py` 再重渲染，走的是真实成因
# （md 与 opcodes.yaml 跟着一起错、三层内部自洽），而不是手改 md 糊弄。

#: CE-28：把 S5 整行从 D17_LEDGER 里删掉。`D17_LEDGER_IDS` 仍列着 `D17:S5`，
#: 故渲染出的引言会与表格自相矛盾 —— I1 必须同时报出「6 行 ≠ 7 行」与「缺 D17:S5」。
D17_S5_ROW = (
    '    {\n'
    '        "id": "D17:S5",\n'
    '        "silent": "S5",\n'
    '        "status": "BLOCKED",\n'
    '        "topic": "`ftsclb`/`fosclb` 的 scaleB 指数「`rfhd` 取整数值」有两种读法",\n'
    '        "spec_cite": "SimRISC-03:163",\n'
    '        "affected": ("ids", "ftsclb", "fosclb"),\n'
    '        "affected_text": None,\n'
    '        "facet": "semantics",\n'
    '        "consumers": ("SPEC-103t", "TESTCASES-101t", "TESTCASES-102t",\n'
    '                      "QEMU-102t", "INTEG-102t", "INTEG-103t", "INTEG-104m"),\n'
    '    },\n'
)

#: CE-29：给台账**加一行 `D17:S2`**。S2 只能是 ledger 外的来源追踪，
#: 一旦混进表格，它就会被下游当成第 8 个待关闭键。
D17_S2_ROW_INJECT = (
    '    {\n'
    '        "id": "D17:S2",\n'
    '        "silent": "S2",\n'
    '        "status": "BLOCKED",\n'
    '        "topic": "「有效范围 1~63」表述不一致（无行为后果）",\n'
    '        "spec_cite": "SimRISC-03:44",\n'
    '        "affected": ("ids", "ldm.t", "ldm.o", "stm.t", "stm.o"),\n'
    '        "affected_text": None,\n'
    '        "facet": "legality",\n'
    '        "consumers": ("SPEC-103t",),\n'
    '    },\n'
)
D17_S3_ROW_HEAD = '    {\n        "id": "D17:S3",\n'

#: CE-30 / CE-31：把一条**真实未决**行的状态词改掉。
#:   PASS  → 语义上「已通过」，是最危险的固化信号；
#:   active → 语义上「已生效」，同样把未决说成了已决。
D17_S6_STATUS_OLD = ('        "id": "D17:S6",\n        "silent": "S6",\n'
                     '        "status": "BLOCKED",\n')
D17_S4_STATUS_OLD = ('        "id": "D17:S4",\n        "silent": "S4",\n'
                     '        "status": "BLOCKED",\n')

#: CE-32：把 S7 的下游消费者**清空**（下游于是收不到任何关闭提醒）。
#: 锚点必须覆盖**整行 S7 块**：那串 consumers 字面量 S6/S7/S8 三行完全一样，
#: 只锚 consumers 段会命中 3 次（注入脚本会直接报「须恰好 1 次」而拒绝执行 ——
#: 宁可拒绝，也不接受一次含糊的多点替换）。
D17_S7_ROW = (
    '    {\n'
    '        "id": "D17:S7",\n'
    '        "silent": "S7",\n'
    '        "status": "BLOCKED",\n'
    '        "topic": "`rd2rf`/`rf2rd` 源与目的范围**重叠**时的读写顺序未规定",\n'
    '        "spec_cite": "SimRISC-03:43 / SimRISC-03:126",\n'
    '        "affected": ("ids", "rd2rf", "rf2rd"),\n'
    '        "affected_text": None,\n'
    '        "facet": "semantics",\n'
    '        "consumers": ("SPEC-103t", "TESTCASES-101t", "TESTCASES-102t",\n'
    '                      "QEMU-101t", "INTEG-102t", "INTEG-103t", "INTEG-104m"),\n'
    '    },\n'
)
D17_S7_ROW_NO_CONSUMERS = D17_S7_ROW.replace(
    '        "consumers": ("SPEC-103t", "TESTCASES-101t", "TESTCASES-102t",\n'
    '                      "QEMU-101t", "INTEG-102t", "INTEG-103t", "INTEG-104m"),\n',
    '        "consumers": (),\n')

#: CE-33：把 S3 的受影响 identity **缩小**（漏掉 `focls`）。
#: CE-34：把 S5 的受影响 identity **清空**（点名与范围都不给）。
#: CE-35：把 S5 的被阻塞 facet 改成另一个真实存在的 facet 名 —— 「名字合法」不等于
#:         「压对的那一面」，所以只查 11-facet 成员资格抓不到它。
D17_S3_AFFECTED_OLD = '        "affected": ("ids", "ftcls", "focls"),'
D17_S3_AFFECTED_NEW = '        "affected": ("ids", "ftcls"),'
D17_S5_AFFECTED_OLD = '        "affected": ("ids", "ftsclb", "fosclb"),'
D17_S5_AFFECTED_EMPTY = '        "affected": ("ids",),'
D17_S5_FACET_OLD = ('        "affected": ("ids", "ftsclb", "fosclb"),\n'
                    '        "affected_text": None,\n'
                    '        "facet": "semantics",\n')
D17_S5_FACET_NEW = ('        "affected": ("ids", "ftsclb", "fosclb"),\n'
                    '        "affected_text": None,\n'
                    '        "facet": "tininess",\n')

#: CE-36：削短 `D17:S2` 的 ledger 外注记（去掉「不在 ledger 内」这一句）。
#: 只留「无行为后果 / resolved / never PASS」而**不再声明它不在台账内** ——
#: 下游就可能把它当成第 8 个待关闭键。4 个必被子句缺一即 FAIL。
D17_S2_NOTE_OLD = ('D17_S2_TRACE_NOTE = ("no behavioral consequence; '
                   'resolved/trace-only; "\n'
                   '                     "not in D17 OPEN-ID ledger; never PASS")')
D17_S2_NOTE_NEW = ('D17_S2_TRACE_NOTE = ("no behavioral consequence; '
                   'resolved/trace-only; "\n'
                   '                     "never PASS")')

#: CE-28..CE-36 的 I 组反例（全部注入数据层 + 重渲染）。
D17_LEDGER_CES = [
    {
        "tag": "28-ledger-drop-s5-row",
        "title": "把 D17:S5 整行从台账里删掉（6 行 ≠ 7 行、且缺 D17:S5）",
        "expect": "I",
        "expect_strict": True,
        "expect_substr": "D17:S5",
        "rerender": True,
        "edits": [("text", DATA, D17_S5_ROW, "")],
    },
    {
        "tag": "29-ledger-add-s2-row",
        "title": "给台账加一行 D17:S2（它只能是 ledger 外注记）",
        "expect": "I",
        "expect_strict": True,
        "expect_substr": "D17:S2",
        "rerender": True,
        "edits": [("text", DATA, D17_S3_ROW_HEAD,
                   D17_S2_ROW_INJECT + D17_S3_ROW_HEAD)],
    },
    {
        "tag": "30-ledger-status-pass",
        "title": "把 D17:S6 的状态从 BLOCKED 改成 PASS（把未决说成已通过）",
        "expect": "I",
        "expect_strict": True,
        "expect_substr": "D17:S6",
        "rerender": True,
        "edits": [("text", DATA, D17_S6_STATUS_OLD,
                   D17_S6_STATUS_OLD.replace('"BLOCKED"', '"PASS"'))],
    },
    {
        "tag": "31-ledger-status-active",
        "title": "把 D17:S4 的状态从 BLOCKED 改成 active（把未决说成已生效）",
        "expect": "I",
        "expect_strict": True,
        "expect_substr": "D17:S4",
        "rerender": True,
        "edits": [("text", DATA, D17_S4_STATUS_OLD,
                   D17_S4_STATUS_OLD.replace('"BLOCKED"', '"active"'))],
    },
    {
        "tag": "32-ledger-empty-consumers",
        "title": "把 D17:S7 的下游消费者清空（下游收不到关闭提醒）",
        "expect": "I",
        "expect_strict": True,
        "expect_substr": "D17:S7",
        "rerender": True,
        "edits": [("text", DATA, D17_S7_ROW, D17_S7_ROW_NO_CONSUMERS)],
    },
    {
        "tag": "33-ledger-affected-shrunk",
        "title": "把 D17:S3 的受影响 identity 缩小（漏掉 focls）",
        "expect": "I",
        "expect_strict": True,
        "expect_substr": "D17:S3",
        "rerender": True,
        "edits": [("text", DATA, D17_S3_AFFECTED_OLD, D17_S3_AFFECTED_NEW)],
    },
    {
        "tag": "34-ledger-affected-missing",
        "title": "把 D17:S5 的受影响 identity 清空（点名与范围都不给）",
        "expect": "I",
        "expect_strict": True,
        "expect_substr": "D17:S5",
        "rerender": True,
        "edits": [("text", DATA, D17_S5_AFFECTED_OLD, D17_S5_AFFECTED_EMPTY)],
    },
    {
        "tag": "35-ledger-wrong-facet",
        "title": "把 D17:S5 的被阻塞 facet 改成 tininess（名字合法但压错了面）",
        "expect": "I",
        "expect_strict": True,
        "expect_substr": "D17:S5",
        "rerender": True,
        "edits": [("text", DATA, D17_S5_FACET_OLD, D17_S5_FACET_NEW)],
    },
    {
        "tag": "36-s2-trace-note-truncated",
        "title": "削短 D17:S2 的 ledger 外注记（去掉「不在 ledger 内」）",
        "expect": "I",
        "expect_strict": True,
        "expect_substr": "not in D17 OPEN-ID ledger",
        "rerender": True,
        "edits": [("text", DATA, D17_S2_NOTE_OLD, D17_S2_NOTE_NEW)],
    },
]

# ── CE-22：抹掉 spec 的对齐原句（判据消失 → 独立解析必须 fail-closed）──
# **替换而不是删行**：保持行数不变，spec 其余行号不位移。
# 替换文本保留了「对齐要求：」这个段头，所以 `independent_alignment()` 仍能找到
# 那一句、但句子里既没有「需 N 字节对齐」也没有 MALIGN —— 命中的是
# 「原句未点名 MALIGN」这条 fail-closed 分支，随后 C 组其余项全部跳过
# （`return`），**不会**退化成「判据缺失就当没要求」而放行。
SPEC03_ALIGN_OLD = ("对齐要求：`ld.o`/`st.o`/`ldm.o`/`stm.o` 需 8 字节对齐，"
                    "`ld.t`/`st.t`/`ldm.t`/`stm.t` 需 4 字节对齐。"
                    "未对齐触发 MALIGN 异常。")
SPEC03_ALIGN_NEW = "对齐要求：已被本反例抹除。"

# ── CE-8：把 §4.1「整型饱和值」那一行的引用誊错一行 ──
CITE_128_OLD = "| 浮点→整数遇 NaN/Inf/超范围返回**整型饱和值**（最大/最小）并置 NV | :128 |"
CITE_128_NEW = "| 浮点→整数遇 NaN/Inf/超范围返回**整型饱和值**（最大/最小）并置 NV | :129 |"

# ── CE-9：把 §4.1 那条注的 SimRISC-00:191 换成邻行 192 ──
CITE_191_OLD = "6 位字段宽度唯一决定（`SimRISC-00:191`）"
CITE_191_NEW = "6 位字段宽度唯一决定（`SimRISC-00:192`）"

# ── CE-10：把渲染器里 FACET_DECISION 的 items() 解包顺序写反 ──
# FACET_DECISION = {facet: decision}，正确写法是 `for facet, dec in ...`。
# 写反后 facet_of 的键变成 facet 名，`dec in facet_of` 恒假，§6.1「对应 facet」
# 整列落到 else 的「（D17 兜底）」。这正是本任务实际踩过的坑。
FACET_LOOP_OK = ("    for facet, dec in D.FACET_DECISION.items():\n"
                 "        facet_of[dec] = facet")
FACET_LOOP_BUG = ("    for dec, facet in D.FACET_DECISION.items():\n"
                  "        facet_of[dec] = facet")

# ── spec MISC-RF 表中 100-xxx 行（ftqcmp / ftscmp）──
RF_ROW_100 = ("| 100-xxx   | ftqcmp-orrr | ftscmp-orrr |             |             |"
              "             |             |             |             |")
# 抹掉 ftqcmp 单元格（保留 ftscmp）→ identity 数 64 → 63
RF_ROW_100_NO_FTQCMP = (
    "| 100-xxx   |             | ftscmp-orrr |             |             |"
    "             |             |             |             |")

# ── CE-5：把 uo2ft 从 D11 开口「裁定」为 spec-determined ──
# 刻意**不改** d11 集合本身，于是数据层的基数自检（"D11": (d11, 37)）照样通过 ——
# 制造一个「内部完全自洽、却偷偷固化了 ADR-1004 D11 开口」的产物。
D11_BRANCH_OLD = """        # rf0 作操作数（D11）
        if insn in d11:
            f["rf0_operand"] = STATUS_OPEN
        elif insn in {insn_of[m] for m in D11_SPEC_RULE} or insn in (
                {insn_of[m] for m in D11_DETERMINED}):
            f["rf0_operand"] = STATUS_SPEC
        else:
            raise ValueError(f"{insn}: rf0_operand 未归类（覆盖漏洞）")"""

D11_BRANCH_NEW = """        # rf0 作操作数（D11）
        if insn in d11 and insn != insn_of["uo2ft"]:
            f["rf0_operand"] = STATUS_OPEN
        elif insn in {insn_of[m] for m in D11_SPEC_RULE} or insn in (
                {insn_of[m] for m in D11_DETERMINED}):
            f["rf0_operand"] = STATUS_SPEC
        elif insn in d11:
            f["rf0_operand"] = STATUS_SPEC
        else:
            raise ValueError(f"{insn}: rf0_operand 未归类（覆盖漏洞）")"""

# ── CE-6：给非 FP 的 cfx 记录（cfx2rd-crrr）硬塞一个 f1: 块 ──
CFX_F1_BLOCK = """  f1:
    in_scope: true
    group: misc-rf
    section: S1D1
    format: crrr
    operands:
    - cfxcode
    - cghb
    - rchc
    - rdhd
    legality_predicates: []
    legality_refs: []
    encoding_cite: SimRISC-00 §SimRISC QFC
    semantics_cite: SimRISC-03 §S1D1
    facets:
      encoding: spec-determined
      format: spec-determined
      operands: spec-determined
      legality: spec-determined
      semantics: spec-determined
      rf0_operand: spec-determined
      tetra_high_half: n/a
      fcsr_flags: n/a
      tininess: n/a
      compare_unordered: n/a
      nan_propagation: n/a
    open_items: []
    notes: []
"""


# ═══════════════════════════ 反例定义 ═══════════════════════════

COUNTEREXAMPLES = [
    {
        "tag": "1-del-identity",
        "title": "删除一个目标 identity（spec MISC-RF 表中抹掉 ftqcmp）",
        "expect": "A",
        "rerender": False,
        "edits": [("text", SPEC00, RF_ROW_100, RF_ROW_100_NO_FTQCMP)],
    },
    {
        "tag": "2-dup-identity",
        "title": "在 spec 的 QFC 表中重复一个 identity（整行复制 100-xxx）",
        "expect": "A",
        "rerender": False,
        # 这一条**曾经抓不住**：extractor 的 encodings 以 (op,ha) 为键，
        # 重复的表格单元会被静默覆盖，identity 数仍是 64。补上 A 组
        # 「编码单元在 QFC 表中恰好出现一次」之后才可见。
        "edits": [("text", SPEC00, RF_ROW_100, RF_ROW_100 + "\n" + RF_ROW_100)],
    },
    {
        "tag": "3-bad-encoding",
        "title": "改错目标 identity 的编码（opcodes.yaml 中 ftadd 的 ha 改错 2 位）",
        "expect": "C",
        "rerender": False,
        "edits": [("set_field", OPC, "ftadd", "ha", "  ha: '0x10'\n", "  ha: '0x14'\n")],
    },
    {
        "tag": "4-drop-scope",
        "title": "移除一个目标 identity 的 F1 scope（删掉 ftsub 的整个 f1: 块）",
        "expect": "B",
        "rerender": False,
        "edits": [("drop_f1", OPC, "ftsub")],
    },
    {
        "tag": "5-open-to-defined",
        "title": "把一个 OPEN facet 改成 determined（uo2ft.rf0_operand 自洽固化）",
        "expect": "D",
        "rerender": True,
        "edits": [("text", DATA, D11_BRANCH_OLD, D11_BRANCH_NEW)],
    },
    {
        "tag": "6-scope-nonfp",
        "title": "给非 FP 的 cfx 记录加 F1 scope（cfx2rd-crrr）",
        "expect": "B",
        "rerender": False,
        "edits": [("add_f1", OPC, "cfx2rd-crrr", CFX_F1_BLOCK)],
    },
    {
        "tag": "7-dup-record",
        "title": "在合约层重复一条记录（opcodes.yaml 中整条复制 ftscmp）",
        "expect": "B",
        "rerender": False,
        "edits": [("dup_record", OPC, "ftscmp")],
    },
    {
        "tag": "8-cite-off-by-one",
        "title": "把一条 spec 引用誊错一行（§4.1 整型饱和值行 :128 → :129）",
        "checker": "citations",
        # 誊错一行的典型形态：`:129` 仍在 SimRISC-03 范围内，第 1/2 层
        # （文件存在 + 行号不越界）**照样全绿**；只有第 3 层 (a)「该行必须
        # 含关键词 整型饱和值」能抓住 —— 而它抓住才说明引用指错了句子。
        "expect": "语义锚点未命中",
        "rerender": False,
        "edits": [("text", CONTRACT_MD, CITE_128_OLD, CITE_128_NEW)],
    },
    {
        "tag": "9-cite-claim-drift",
        "title": "把主张行的引用换成邻行（§4.1 注 :191 → :192）",
        "checker": "citations",
        # 这一条专打第 3 层的 **(b) 侧**：SimRISC-00:192 **同样含** `hd[5:0]`，
        # 所以 spec 侧关键词检查照过；唯一能抓住的是「写着该主张的段落是否
        # 还引 :191」。若 (b) 缺失，本反例会全绿 —— 即检查器有洞。
        "expect": "语义锚点未命中",
        "rerender": False,
        "edits": [("text", CONTRACT_MD, CITE_191_OLD, CITE_191_NEW)],
    },
    {
        "tag": "10-summary-facet-column",
        "title": "把 §6.1 汇总表的「对应 facet」整列打回退化值（渲染器解包写反）",
        "checker": "contract",
        # 这条重现的是一个**真实发生过的缺陷**：渲染器把 FACET_DECISION
        # （{facet: decision}）的 items() 解包写反，致 §6.1「对应 facet」
        # 整列退化成「（D17 兜底）」。原检查器 F 组只查「D11–D17 出现且集非空」，
        # 查不到列内容错 → 假绿。注入**渲染器**再重渲染，走的是缺陷的真实成因，
        # 而不是手改 md 糊弄。
        "expect": "F",
        "rerender": True,
        "edits": [("text", RENDERER, FACET_LOOP_OK, FACET_LOOP_BUG)],
    },
] + ALIGN_DROP_CES + [
    {
        "tag": "19-align-wrong-width",
        "title": (f"把 {WIDTH_WRONG_INSN} 的对齐宽度改错（aligned"
                  f"({WIDTH_WRONG_GOOD}) → aligned("
                  f"{8 if WIDTH_WRONG_GOOD == 4 else 4})）"),
        "expect": "C",
        "rerender": True,
        "expect_substr": WIDTH_WRONG_INSN,
        "edits": [("text", DATA, LAST_PRED_DECL,
                   LAST_PRED_DECL
                   + _wrong_width_line(WIDTH_WRONG_MNEM, WIDTH_WRONG_GOOD))],
    },
    {
        "tag": "20-s8-claims-legality-partial",
        "title": "让 S8 重新声称「`legality` facet 因 S2 记 partial」（真实缺陷）",
        "expect": "H",
        "rerender": True,
        "expect_substr": "S8",
        "edits": [("text", DATA, S8_DECISION_OLD, S8_DECISION_NEW)],
    },
    {
        "tag": "21-summary-table-partial-count",
        "title": "把 §5.4 钉死汇总表的 legality partial 数改错（2 → 4）",
        "expect": "H",
        "rerender": False,
        "expect_substr": "legality",
        "edits": [("text", CONTRACT_MD, SUMMARY_ROW_OLD, SUMMARY_ROW_NEW)],
    },
    {
        "tag": "22-spec-align-sentence-gone",
        "title": "抹掉 spec 的对齐原句（判据消失 → 独立解析必须 fail-closed）",
        "expect": "C",
        "rerender": False,
        "expect_substr": "对齐原句",
        "edits": [("text", SPEC03, SPEC03_ALIGN_OLD, SPEC03_ALIGN_NEW)],
    },
    {
        "tag": "23-cls-claim-wrong-silent-id",
        "title": "把 §4.8 的 facet 断言静默项编号誊错（S3 → S2）",
        "expect": "H",
        "rerender": True,
        "rm_md_before_render": True,
        "expect_substr": "S2",
        "edits": [("text", RENDERER, CLS_CLAIM_OLD, CLS_CLAIM_WRONG_SID)],
    },
    {
        "tag": "24-cls-claim-erased",
        "title": "把 §4.8 的 facet 断言改成 spec-determined（判据消失须 fail-closed）",
        "expect": "H",
        "rerender": True,
        "rm_md_before_render": True,
        "expect_substr": "判据消失",
        "edits": [("text", RENDERER, CLS_CLAIM_OLD, CLS_CLAIM_GONE)],
    },
    {
        "tag": "25-s3-affected-shrunk",
        "title": "把 S3 的受影响集缩小成只留 ftcls（focls 的 partial 变无人认领）",
        "expect": "H",
        "rerender": True,
        "rm_md_before_render": True,
        "expect_substr": "focls",
        "edits": [("text", DATA, S3_MNEMONICS_OLD, S3_MNEMONICS_NEW),
                  ("text", DATA, S3_AFFECTED_OLD, S3_AFFECTED_NEW)],
    },
    {
        "tag": "26-cls-claim-unknown-silent-id",
        "title": "§4.8 的 facet 断言点名不存在的静默项 S9",
        "expect": "H",
        "rerender": True,
        "rm_md_before_render": True,
        "expect_substr": "S9",
        "edits": [("text", RENDERER, CLS_CLAIM_OLD, CLS_CLAIM_BAD_SID)],
    },
    {
        "tag": "27-cls-claim-unknown-facet",
        "title": "§4.8 的 facet 断言把 facet 名誊错（legality → legalty）",
        "expect": "H",
        "rerender": True,
        "rm_md_before_render": True,
        "expect_substr": "legalty",
        "edits": [("text", RENDERER, CLS_CLAIM_OLD, CLS_CLAIM_BAD_FACET)],
    },
] + D17_LEDGER_CES


# ═══════════════════════════ 临时树 ═══════════════════════════

def sh(cmd, cwd):
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)


def build_tree(tag: str) -> Path:
    tree = TMP_ROOT / f"ce-{tag}"
    if tree.exists():
        shutil.rmtree(tree)
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    shutil.copytree(REPO_ROOT, tree, ignore=COPY_IGNORE, symlinks=True)
    for cmd in (["git", "init", "-q", "-b", "main"],
                ["git", "config", "user.email", "ce@localhost"],
                ["git", "config", "user.name", "counterexample"],
                ["git", "config", "commit.gpgsign", "false"]):
        sh(cmd, tree)
    for cmd in (["git", "add", "-A"],
                ["git", "commit", "-q", "--no-verify", "-m", "ce baseline"]):
        r = sh(cmd, tree)
        if r.returncode != 0:
            raise SystemExit(f"[{tag}] {' '.join(cmd)} 失败: "
                             f"{(r.stdout + r.stderr)[:300]}")
    return tree


# ═══════════════════ 注入原语（全部要求唯一命中，否则报错退出）═══════════════════

def _record_span(lines, insn):
    """返回 (start, end) 行下标：`- insn: <insn>` 所在记录块。"""
    hits = [i for i, ln in enumerate(lines) if ln.strip() == f"- insn: {insn}"]
    if len(hits) != 1:
        raise SystemExit(f"记录 - insn: {insn} 命中 {len(hits)} 次（须恰好 1 次）")
    start = hits[0]
    nxt = [i for i, ln in enumerate(lines)
           if i > start and ln.startswith("- insn:")]
    end = nxt[0] if nxt else len(lines)
    return start, end


def apply_edit(tree: Path, edit) -> None:
    kind, rel = edit[0], edit[1]
    p = tree / rel
    if not p.exists():
        raise SystemExit(f"注入目标不存在: {rel}")
    lines = p.read_text(encoding="utf-8").splitlines(keepends=True)

    if kind == "text":
        _, _, old, new = edit
        text = "".join(lines)
        n = text.count(old)
        if n != 1:
            raise SystemExit(f"注入锚点在 {rel} 命中 {n} 次（须恰好 1 次）。"
                             f"锚点前 80 字: {old[:80]!r}")
        p.write_text(text.replace(old, new, 1), encoding="utf-8")
        return

    if kind == "set_field":
        _, _, insn, field, old, new = edit
        s, e = _record_span(lines, insn)
        body = lines[s:e]
        n = body.count(old)
        if n != 1:
            raise SystemExit(f"字段锚点 {field!r} 在记录 {insn} 内命中 {n} 次")
        body[body.index(old)] = new
        lines[s:e] = body
        p.write_text("".join(lines), encoding="utf-8")
        return

    if kind == "drop_f1":
        _, _, insn = edit
        s, e = _record_span(lines, insn)
        body = lines[s:e]
        f1 = [i for i, ln in enumerate(body) if ln.rstrip("\n") == "  f1:"]
        if len(f1) != 1:
            raise SystemExit(f"记录 {insn} 内 `  f1:` 出现 {len(f1)} 次（须恰好 1 次）")
        cut = f1[0]
        nxt = [i for i, ln in enumerate(body) if i > cut
               and re.match(r"^  [a-z_]+:", ln)]
        del body[cut:(nxt[0] if nxt else len(body))]
        lines[s:e] = body
        p.write_text("".join(lines), encoding="utf-8")
        return

    if kind == "dup_record":
        _, _, insn = edit
        s, e = _record_span(lines, insn)
        dup = lines[s:e]
        if not dup:
            raise SystemExit(f"记录 {insn} 为空，无法复制")
        lines[e:e] = dup
        p.write_text("".join(lines), encoding="utf-8")
        return

    if kind == "add_f1":
        _, _, insn, block = edit
        s, e = _record_span(lines, insn)
        body = lines[s:e]
        if any(ln.rstrip("\n") == "  f1:" for ln in body):
            raise SystemExit(f"记录 {insn} 已有 f1: 块，无法注入 add_f1")
        body = body + [block]
        lines[s:e] = body
        p.write_text("".join(lines), encoding="utf-8")
        return

    raise SystemExit(f"未知注入类型: {kind}")


def apply_edits(tree: Path, edits) -> None:
    for edit in edits:
        apply_edit(tree, edit)


# ═══════════════════════════ 跑校验器 / 查脏 ═══════════════════════════

def run_checker(tree: Path, kind: str = "contract", verbose: bool = False) -> dict:
    c = CHECKERS[kind]
    cmd = [sys.executable, c["path"]]
    if verbose:
        cmd.append("-v")
    r = subprocess.run(cmd, cwd=str(tree), capture_output=True, text=True)
    out = r.stdout + r.stderr
    hits = list(c["fail_re"].finditer(out))
    # 明细只取**首个 FAIL 头之后**的部分：头之前还有「主张串命中 >1 处」之类的
    # 说明行，混进失败明细会让人误以为也是问题项。
    cut = out.find("[FAIL]")
    tail = out[cut:] if cut >= 0 else ""
    res = {
        "rc": r.returncode,
        "cats": sorted({m.group("cat") for m in hits}),
        "fail_lines": [m.group(0).strip() for m in hits],
        "detail_lines": ([m.group(0).strip() for m in c["detail_re"].finditer(tail)]
                         if c["detail_re"] else []),
        "summary": "",
        "out": out,
    }
    if c["sum_re"]:
        m = c["sum_re"].search(out)
        if m:
            res["summary"] = f"，通过 {m.group(1)} 项 / 失败 {m.group(2)} 项"
    return res


def changed_paths(tree: Path):
    r = sh(["git", "-c", "core.quotePath=false", "diff", "--name-only"], tree)
    return [x for x in r.stdout.splitlines() if x.strip()]


def dirty_paths(tree: Path):
    r = sh(["git", "-c", "core.quotePath=false", "status", "--porcelain",
            "--untracked-files=all"], tree)
    return [x for x in r.stdout.splitlines() if x.strip()]


# ═══════════════════════════ 主流程 ═══════════════════════════

def run_one(ce: dict, verbose: bool) -> bool:
    tag, expect = ce["tag"], ce["expect"]
    kind = ce.get("checker", "contract")
    print(f"\n{'─' * 78}\nCE-{tag}: {ce['title']}\n{'─' * 78}")
    ok = True
    tree = build_tree(tag)
    print(f"  临时树: {tree}   校验器: {CHECKERS[kind]['path']}")

    # ── 基线必须先绿，否则「注入后红」没有说服力 ──
    base = run_checker(tree, kind)
    if base["rc"] != 0:
        print(f"  [FAIL] 基线就不绿（rc={base['rc']}），本反例无意义：\n"
              f"         {base['out'][-400:]}")
        return False
    print(f"  基线:   rc=0{base['summary']}")

    # ── 基线里必须真的**跑过**本反例瞄准的那一组检查（否则 expect 的 FAIL 类别
    #    永远不可能出现，「注入后 FAIL」也就无从谈起）。用 -v 跑一次拿 OK 行，
    #    断言 `[<类别>] OK` 存在 —— 这一条是「新检查确实被跑到」的唯一证据，
    #    防止新增检查项被注册成永不执行的死代码。
    if expect in "ABCDEFGHI":
        vb = run_checker(tree, kind, verbose=True)
        marks = sorted({m.group(1) for m in re.finditer(r"^\[([A-I])\] OK", vb["out"], re.M)})
        if expect not in marks:
            print(f"  [FAIL] 基线里没有 [{expect}] 组的 OK 行（实际跑到: {marks}）"
                  f"—— 本反例瞄准的检查根本没执行")
            return False
        print(f"  基线组: [-v] 跑到 {''.join(marks)}，含本反例瞄准的 [{expect}] ✓")

    # ── 注入 ──
    apply_edits(tree, ce["edits"])
    if ce.get("rm_md_before_render"):
        # 渲染器对 md 是**按 region 就地替换**的：改 TEMPLATE 不会更新已存在的 md。
        # 要让注入「走渲染器这条路」就必须先删 md 再重渲染，否则重渲染是空操作，
        # 最后只有 G 组（--check）红，H 组根本没被考验到。
        (tree / CONTRACT_MD).unlink()
        print("  已删除合约 md（渲染器对 md 是 region 就地替换，不删则重渲染是空操作）")
    if ce.get("rerender"):
        r = sh([sys.executable, RENDERER], tree)
        print(f"  重渲染: rc={r.returncode}")
        if r.returncode != 0:
            print(f"         {(r.stdout + r.stderr)[-300:]}")
            ok = False
    ch = changed_paths(tree)
    print(f"  git diff --name-only → {len(ch)} 个: {ch}")
    if not ch:
        print("  [FAIL] 空注入：注入未改动任何文件，反例无效")
        return False

    # ── 注入后必须 FAIL，且 FAIL 类别必须是本反例瞄准的那一个 ──
    bad = run_checker(tree, kind)
    print(f"  注入后: rc={bad['rc']}{bad['summary']}"
          f"  FAIL 类别={bad['cats']}  （期望 {expect}）")
    if bad["rc"] == 0:
        print("  [FAIL] 注入后仍全绿 → 校验器对该缺陷不敏感")
        return False
    if not bad["cats"]:
        print(f"  [FAIL] 非零退出但无语义 FAIL 行（异常退出不算语义 FAIL）：\n"
              f"         {bad['out'][-400:]}")
        ok = False
    else:
        for ln in bad["fail_lines"][:4]:
            print(f"           {ln[:145]}")
        for ln in bad["detail_lines"][:3]:
            print(f"           {ln[:145]}")
        if expect not in bad["cats"]:
            msg = (f"  [FAIL] 期望 FAIL 类别 {expect!r}，实际 {bad['cats']}"
                   f" —— 抓到的不是本反例瞄准的那一类检查")
            print(msg)
            if ce.get("expect_strict"):
                ok = False

    # ── FAIL 明细必须**点名**本反例瞄准的对象（不许泛化断言蒙混）──
    exp_sub = ce.get("expect_substr")
    if exp_sub and bad["rc"] != 0:
        blob = "\n".join(bad["fail_lines"] + bad["detail_lines"])
        if exp_sub in blob:
            print(f"  点名:   FAIL 明细含 {exp_sub!r} ✓")
        else:
            print(f"  [FAIL] FAIL 明细**未**点名 {exp_sub!r} —— 诊断不具体，"
                  f"无法确认抓到的是本反例那一处：\n{blob[:400]}")
            ok = False

    # ── 还原（必须回到干净） ──
    r = sh(["git", "checkout", "--", "."], tree)
    left = dirty_paths(tree)
    print(f"  还原:   git checkout rc={r.returncode}，残留脏文件 {len(left)}: {left[:5]}")
    if left:
        print("  [FAIL] 还原不彻底")
        ok = False

    # ── 还原后必须重新全绿 ──
    again = run_checker(tree, kind)
    print(f"  还原后: rc={again['rc']}{again['summary']}")
    if again["rc"] != 0:
        print(f"  [FAIL] 还原后仍不绿：\n         {again['out'][-400:]}")
        ok = False

    print(f"  → CE-{tag}: {'PASS（能失败且可复原）' if ok else 'FAIL'}")
    return ok


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="F1 合约校验器反例注入门控")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--rm-trees", action="store_true", help="跑完删除临时树")
    args = ap.parse_args(argv)

    t0 = time.time()
    print("=" * 78)
    print("test_f1_contract_counterexamples: 反例注入门控")
    print(f"  仓库   : {REPO_ROOT}")
    print(f"  临时树 : {TMP_ROOT}/ce-<tag>/（每项一棵，互不复用）")
    print(f"  反例数 : {len(COUNTEREXAMPLES)}"
          f"（contract {sum(1 for c in COUNTEREXAMPLES if c.get('checker', 'contract') == 'contract')}"
          f" / citations {sum(1 for c in COUNTEREXAMPLES if c.get('checker') == 'citations')}）")
    print("=" * 78)

    results = []
    for ce in COUNTEREXAMPLES:
        try:
            results.append((ce["tag"], run_one(ce, args.verbose)))
        except SystemExit as e:
            print(f"  [FAIL] 注入脚本异常: {e}")
            results.append((ce["tag"], False))

    npass = sum(1 for _, o in results if o)
    print(f"\n{'=' * 78}\n汇总：")
    for tag, o in results:
        print(f"  {'PASS' if o else 'FAIL'}  CE-{tag}")
    print(f"  {npass}/{len(results)} 个反例被成功抓住（注入后 FAIL + 还原后 PASS）")
    print(f"  用时 {time.time() - t0:.1f}s")
    print("=" * 78)

    if args.rm_trees:
        for tag, _ in results:
            shutil.rmtree(TMP_ROOT / f"ce-{tag}", ignore_errors=True)
        print(f"  已清理临时树: {TMP_ROOT}/ce-*")

    return 0 if npass == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
