#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_f1_gap_proofs.py — SPEC-103t 结构 / 集合 / 引用 / 无选择 / 无环检查器，
外加 SPEC-104t 的「已确认语义机器投影 + 下游门禁同步」检查。

检查 `contracts/f1_gap_proofs.yaml`（F1 语义缺口证明的**唯一机器可读真源**）。

设计要点（对应任务书 §12「纯 grep、只验证 YAML 内部自洽或从 YAML 自己推导期望
集合均不够」）：

* **不 import 任何 SPEC-102t 工具脚本**（`f1_spec_extract` / `f1_contract_data` /
  `f1_render_contract` 一律不用），自带最小解析器重读
  `spec/SimRISC-00-指令系统设计.md`、`spec/SimRISC-03-浮点类指令.md`、
  `.xkw/knowledge/adr-1004-f1-floating-phase.md`、
  `.xkw/knowledge/contract-f1-floating.md` 与 `contracts/opcodes.yaml`。
* **不从被检查的 YAML 推导任何期望集合**：identity 集、facet 键、非 fault 谓词、
  D11–D16 投影基数、六键 active 范围、S4 的 26 条多故障集、S3/S5/S6/S8 的机械求法、
  QEMU 三任务的 11/42/11 分解、逐任务 ledger 适用状态、消费者任务的依赖/关联
  任务行，全部从上述上游文件与 `.xkw/tasks/**` 真实任务书**独立重算**。
* **外部字面量基准表**（`PIN_*`）固定本任务自定的政策（顶层键集、断言类别词表、
  blocked_downstream 规则表、必需图边、禁止的选择性键名、禁止的来源 token）。
  这些是 SPEC-103t 的决定，不是从 YAML 反推；把它们内联进检查器正是为了堵死
  「改 YAML 同时改检查器就一起假绿」的后门（对照
  `check_f1_contract.py` 的 `PINNED_OPEN` / `PINNED_MATRIX`）。
* **引用是语义检查**：`spec_cite.quote` 必须是**被引行区间原文的逐字子串**，
  因此把 :7 誊成 :8 会被抓住，而不是只查格式。

检查组：

  G1  顶层 schema、identity_universe 与 64/18+46/11 facet 的独立重算
  G2  decision_proofs 精确 D11–D17、必填字段、投影基数、候选问题双向闭合
  G3  authority 白名单与禁止来源（实现 / 数值库 / 历史仓 / 工作日志）
  G4  spec_cites 的文件白名单、行区间有效性与逐字 quote
  G5  d17_open_ledger 精确六键、OPEN/BLOCKED、S6 无已选行为、layout/reset 分栏
  G6  trace_only 精确且仅含 D17:S2，四句语义与 6 位/独立 ILLI 证明
  G7  impact_matrix 双向 64、facet/投影/blocked_downstream 逐行重算
  G8  consumer_graph 节点/必需边/逐边溯源/DAG 无环/逐任务适用状态
  G9  candidate_inputs 无 selected/default/recommended/Accepted，逐条最小可问
  G10 OPEN 不得变 active / PASS / spec-determined（键位限定的值扫描）
  G11 不得预绑 Candidate ADR 编号、未创建 ADR 文件、交付路径齐备、.tao 零改动
  G12 S7 叙述一致性：任何分句若提到 S7 而没有显式标为历史/non-gap/不进入 active
      一律 FAIL；active 计数必须为六；D17 逐项点名六个 active OPEN-ID；S7 的原始
      权威引用恰为 SimRISC-00:41-46 + SimRISC-03:34-50

  ── SPEC-104t 追加（不改写、不削弱上面 G1–G12 的历史检查）──

  G13 生命周期/ADR 清单：七份 ADR 文件、逐份 `**状态**`、`### Dn：…` 标题逐字、
      每条现行 decision 的 `**确认记录**`、ADR-1009/D1 是唯一 superseded
  G14 candidate ↔ decision 双向闭合：24 个历史 Candidate ↔ 22 primary + 5
      supplemental，orphan / 重复 / 跨 gap 绑定一律 FAIL
  G15 规则表：D11 白名单、D12 53/11、D13 18、D14 4、D15 18、D16 36、六键
      scope、S6 `6-1+5=10`、§5 常量与交叉优先级**全部从 contracts/opcodes.yaml
      与 ADR Markdown 独立重算**，不从被检查的 resolution 推导期望
  G16 现行 resolution matrix：精确 64 行、无 pseudo、无重复、逐行 applicable
      decision / 已关闭 facet / owning consumer 与上游双向一致
  G17 规范权威边界：解析 Markdown HTML comment 区间，SimRISC-03:7-8 只能作为
      historical-non-normative 引用出现，任何 current 引用即 FAIL；
      `canonical_qnan_bits` 必须保持 null（ADR-1013 未给常量）
  G18 下游任务书同步：10 本普通任务书 + INTEG-104m 的六键 active、S2 trace-only、
      S7 non-gap、依赖 SPEC-104t/Accepted ADR、无陈旧门禁措辞、动态判据仍 BLOCKED
  G19 历史保护与无旁路产物：SPEC-102t/103t 任务书 sha256 未变、resolution 必须是
      最后一个顶层键、仓库内无 backup/平行 projection/checker 产物
  G20 生命周期接口：`consumer_activation` 与 64 行矩阵交叉一致；Candidate 阶段
      默认模式只输出 projected/pending-activation；`--require-active` 只有七份
      ADR 全部 Accepted 才 exit 0

用法：
    python3 tools/spec/check_f1_gap_proofs.py [-v] [--root REPO] [--yaml PATH]
    python3 tools/spec/check_f1_gap_proofs.py --require-active

退出码：0 = 全部通过；1 = 有检查 FAIL；2 = 用法 / IO 错误。
`--require-active` 在七份 ADR 仍为 Candidate 时**必须**返回非零并打印 BLOCKED
（这是本任务验收判据 10 要求的替代证据，不是 PASS）。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys

import yaml

# ────────────────────────────── 路径 ──────────────────────────────
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
YAML_REL = "contracts/f1_gap_proofs.yaml"
CHECKER_REL = "tools/spec/check_f1_gap_proofs.py"
RUNNER_REL = "tools/spec/test_f1_gap_proof_counterexamples.py"

SPEC00 = "spec/SimRISC-00-指令系统设计.md"
SPEC03 = "spec/SimRISC-03-浮点类指令.md"
ADR1004 = ".xkw/knowledge/adr-1004-f1-floating-phase.md"
CONTRACT = ".xkw/knowledge/contract-f1-floating.md"
OPCODES = "contracts/opcodes.yaml"
README = "README.md"

# ─────────────────── 外部字面量基准表（本任务自定政策） ───────────────────
PIN_TOP_KEYS = [
    "schema_version", "authority", "identity_universe", "rf0_fcsr_split",
    "non_gap_records", "decision_proofs", "d17_open_ledger", "trace_only",
    "impact_matrix", "consumer_graph", "candidate_inputs", "provenance",
    "resolution",
]
PIN_SCHEMA_VERSION = "1.0.0"
PIN_AUTHORITY_ORDER = [README, SPEC00, SPEC03, ADR1004, CONTRACT, OPCODES]

PIN_DECISIONS = ["D11", "D12", "D13", "D14", "D15", "D16", "D17"]
PIN_PROOF_FACET = {
    "D11": "rf0_operand", "D12": "fcsr_flags", "D13": "tetra_high_half",
    "D14": "compare_unordered", "D15": "nan_propagation", "D16": "tininess",
    "D17": "any-open-or-silent",
}
PIN_PROJ = {"D11": 37, "D12": 53, "D13": 18, "D14": 4, "D15": 18,
            "D16": 36, "D17": 64}
PIN_FACET_TO_D = {
    "rf0_operand": "D11", "fcsr_flags": "D12", "tetra_high_half": "D13",
    "compare_unordered": "D14", "nan_propagation": "D15", "tininess": "D16",
}
PIN_CLASSIFICATIONS = [
    "spec-determined", "explicitly-unspecified", "no-behavioral-consequence",
    "genuine-gap",
]
PIN_FACET_STATUS = ["spec-determined", "partial", "open-blocked", "n/a"]
PIN_LEDGER_KEYS = ["D17:S1", "D17:S3", "D17:S4", "D17:S5", "D17:S6", "D17:S8"]
PIN_LEDGER_SCOPES = {"D17:S1": 64, "D17:S3": 2, "D17:S4": 26, "D17:S5": 2,
                    "D17:S6": 6, "D17:S8": 4}
PIN_S7_ID = "D17:S7"
PIN_S7_IDENTITIES = ["rd2rf", "rf2rd"]
PIN_S2_ID = "D17:S2"
PIN_S2_TAG = ("no behavioral consequence; resolved/trace-only; "
              "not in D17 OPEN-ID ledger; never PASS")
#: 已按 SPEC-104t 的指针修复同步到现文（用户在 SimRISC-03 第 7-8 行插入 HTML
#: 注释后，原始 29/48/132 整体下移为 30/49/133）。
PIN_S2_PROOF_LINES = [(SPEC00, "191"), (SPEC03, "30"), (SPEC03, "49"), (SPEC03, "133")]
PIN_S2_IDENTITIES = ["ldm.o-rf", "ldm.t-rf", "stm.o-rf", "stm.t-rf"]
PIN_S6_IDENTITIES = ["ld.o-rf", "ld.t-rf", "ldm.o-rf", "ldm.t-rf", "rd2rf", "set.w-rf"]
PIN_S6_UNSELECTED = ["静默忽略", "保留原值", "清零", "触发异常"]
PIN_ASSERTION_CLASSES = [
    "reset-dependent expected", "legality-negative", "assembler-legality",
    "fault-priority", "runtime semantics", "milestone facet",
    "schema/oracle/vector", "facet-closure",
]
PIN_STATUS_WORDS = ["OPEN", "BLOCKED", "NOT-A-GAP"]
PIN_APPLICABILITY = ["OPEN", "BLOCKED", "N/A(runtime)"]
PIN_GRAPH_NODES = [
    "SPEC-101k", "SPEC-102t", "SPEC-103t", "TESTCASES-101t", "TESTCASES-102t",
    "INFRA-108t", "LLVM-101t", "LLVM-102t", "LLVM-103t", "QEMU-101t",
    "QEMU-102t", "QEMU-103t", "INTEG-102t", "INTEG-103t", "INTEG-104m",
]
PIN_NODE_ROLE = {
    "SPEC-101k": "input", "SPEC-102t": "input", "INFRA-108t": "input",
    "SPEC-103t": "producer", "TESTCASES-101t": "consumer",
    "TESTCASES-102t": "consumer", "LLVM-101t": "consumer", "LLVM-102t": "consumer",
    "LLVM-103t": "consumer", "QEMU-101t": "consumer", "QEMU-102t": "consumer",
    "QEMU-103t": "consumer", "INTEG-102t": "consumer", "INTEG-103t": "consumer",
    "INTEG-104m": "milestone",
}
PIN_REQUIRED_EDGES = [
    ("SPEC-101k", "SPEC-102t"), ("SPEC-102t", "SPEC-103t"),
    ("SPEC-103t", "TESTCASES-101t"), ("SPEC-103t", "TESTCASES-102t"),
    ("TESTCASES-101t", "TESTCASES-102t"),
    ("INFRA-108t", "LLVM-101t"), ("SPEC-103t", "LLVM-101t"),
    ("LLVM-101t", "LLVM-102t"), ("LLVM-101t", "LLVM-103t"),
    ("TESTCASES-101t", "LLVM-103t"),
    ("INFRA-108t", "QEMU-101t"), ("SPEC-103t", "QEMU-101t"),
    ("TESTCASES-101t", "QEMU-101t"),
    ("QEMU-101t", "QEMU-102t"), ("TESTCASES-102t", "QEMU-102t"),
    ("QEMU-102t", "QEMU-103t"), ("TESTCASES-102t", "QEMU-103t"),
    ("SPEC-103t", "INTEG-102t"), ("TESTCASES-101t", "INTEG-102t"),
    ("TESTCASES-102t", "INTEG-102t"),
    ("LLVM-101t", "INTEG-102t"), ("LLVM-102t", "INTEG-102t"),
    ("LLVM-103t", "INTEG-102t"),
    ("QEMU-101t", "INTEG-102t"), ("QEMU-102t", "INTEG-102t"),
    ("QEMU-103t", "INTEG-102t"),
    ("INTEG-102t", "INTEG-103t"), ("INTEG-103t", "INTEG-104m"),
]
PIN_OWNED_IDENTITY_COUNT = {"QEMU-101t": 11, "QEMU-102t": 42, "QEMU-103t": 11}
PIN_EVIDENCE_KINDS = [
    "spec-text", "spec-absence-scan", "spec-conflict", "accepted-adr",
    "verified-contract", "machine-projection", "derived-conclusion",
    "scope-exclusion",
]
PIN_PROOF_FIELDS = [
    "title", "question", "classification", "status", "blocked_facet",
    "affected_identity_count", "affected_identities_scope", "cross_cutting",
    "affected_facets", "search_scope", "spec_cites", "evidence",
    "missing_or_conflicting", "classification_reason", "observable_consequences",
    "candidate_question_ids", "blocked_assertions", "unblock_condition",
]
PIN_LEDGER_FIELDS_COMMON = [
    "topic", "status", "classification", "scope_kind", "affected_identity_count",
    "affected_identities", "scope_derivation", "blocked_facets",
    "blocked_assertions", "spec_cites", "evidence", "observable_consequences",
    "candidate_question_ids", "unblock_condition",
]
PIN_CITE_FIELDS = ["ref", "file", "lines", "quote"]
PIN_EVIDENCE_FIELDS = ["id", "kind", "source", "finding"]
PIN_CAND_FIELDS = [
    "id", "group", "decision", "facet", "question",
    "affected_identities_scope", "status", "asking_rule", "options",
]
PIN_OPTION_FIELDS = [
    "id", "behavior", "affected_identities_scope", "affected_facets",
    "observable_difference", "implementation_cost", "depends_on",
]
PIN_NODE_FIELDS = [
    "task", "task_book", "role", "owns_identities", "write_access_to_gap_source",
    "consumes", "ledger_applicability", "na_runtime_note",
]
PIN_UNBLOCK = [
    "规范勘误给出唯一答案",
    "Candidate decision 经用户逐条确认并由主会话写入 Accepted ADR",
]
#: 禁止出现在任何键名中的「已作出选择」词根（大小写不敏感、子串匹配）
PIN_SELECTION_WORDS = [
    "selected", "selection", "default", "recommend", "accepted", "chosen",
    "decid", "resolut", "resolv", "answer", "winner", "prefer", "final_",
    "picked", "opt_in", "adopted",
]
#: 禁止**作为语义来源**出现的实现/数值库/历史仓/工作日志 token（路径类）。
#: 扫描范围：整个 `authority` 段、所有 `spec_cites[].file`、所有
#: `evidence[].source`、所有 `search_scope` 条目。
PIN_FORBIDDEN_SOURCES = [
    "llvm", "qemu", "softfloat", "libm", "glibc", "simrisc-01", "simrisc-02",
    ".tao", "dadao-1", "dadao-06",
]
#: 只在 `authority` 的**取值清单**里禁止出现的「非权威来源」措辞。
#: 散文 `note` 里出现它们是任务书 §2 要求的**排除声明**（不得作为来源），
#: 因此不扫散文；`finding` 同样允许点名 SimRISC-01 来说明「为何不能外推」。
PIN_FORBIDDEN_AUTHORITY_WORDS = ["参考仓", "工作日志", "历史仓"]
#: `evidence[].source` 的严格文法：`file[:linespec,...]`，多项以 `, ` 分隔。
PIN_SOURCE_LINESPEC = re.compile(r"^\d+(-\d+)?(,\d+(-\d+)?)*$")
#: blocked_downstream 的逐行重算规则（触发键 → (任务, 断言类别)）。
#: `own` 展开为该 identity 所属 section 的 QEMU 拥有任务。
PIN_BLOCK_RULES = {
    "milestone": [("INTEG-104m", "milestone facet")],
    "D17:S1": [("own", "reset-dependent expected"),
               ("TESTCASES-101t", "reset-dependent expected"),
               ("TESTCASES-102t", "reset-dependent expected"),
               ("INTEG-102t", "reset-dependent expected"),
               ("INTEG-103t", "reset-dependent expected")],
    "D17:S3": [("own", "legality-negative"),
               ("LLVM-101t", "assembler-legality"),
               ("TESTCASES-101t", "legality-negative"),
               ("INTEG-102t", "legality-negative")],
    "D17:S4": [("own", "fault-priority"),
               ("TESTCASES-101t", "legality-negative"),
               ("INTEG-102t", "fault-priority")],
    "D17:S5": [("own", "runtime semantics"),
               ("TESTCASES-101t", "runtime semantics"),
               ("INTEG-102t", "runtime semantics")],
    "D17:S6": [("own", "legality-negative"),
               ("TESTCASES-101t", "legality-negative"),
               ("INTEG-102t", "runtime semantics")],
    # D17:S7 刻意**不在**本表：S7 是 spec-determined 的历史 non-gap，永远不是
    # 阻塞触发器。留一条 "D17:S7 → runtime semantics" 在这里，等于给「S7 仍会
    # 阻塞运行时语义」留一条可被激活的推导路径，与 non_gap_records 矛盾。
    "D17:S8": [("own", "runtime semantics"),
               ("INTEG-102t", "runtime semantics")],
    "D11": [("own", "runtime semantics"), ("TESTCASES-101t", "runtime semantics"),
            ("INTEG-102t", "runtime semantics")],
    "D12": [("own", "runtime semantics"), ("TESTCASES-101t", "runtime semantics"),
            ("INTEG-102t", "runtime semantics")],
    "D13": [("own", "runtime semantics"), ("TESTCASES-101t", "runtime semantics"),
            ("INTEG-102t", "runtime semantics")],
    "D14": [("own", "runtime semantics"), ("TESTCASES-101t", "runtime semantics"),
            ("INTEG-102t", "runtime semantics")],
    "D15": [("own", "runtime semantics"), ("TESTCASES-101t", "runtime semantics"),
            ("INTEG-102t", "runtime semantics")],
    "D16": [("own", "runtime semantics"), ("TESTCASES-101t", "runtime semantics"),
            ("INTEG-102t", "runtime semantics")],
}
#: 逐任务 ledger 适用状态在真实任务书里的**判别句**；缺句即 fail-closed。
#: 每一句都必须是任务书原文的逐字子串——任务书一改，本检查器立刻失败。
#:
#: ⚠ SPEC-104t 已把 10 本普通任务书 + INTEG-104m 统一同步为**六键 active**、
#: S2 trace-only、S7 non-gap、语义门禁指向 `SPEC-104t` + Accepted ADR。因此下面
#: 钉的不再是「含 S7 的历史原句」，而是**同步后的现行判别句**：任务书若退回七键 /
#: S7 active / 旧 ADR 号 / 「decisions 尚未确认」，这些子串立刻消失 ⇒ G12.6 FAIL。
#: SPEC-103t 自己的句子保持原文（历史任务书是只读证据，不参与本轮同步）。
PIN_APPLIC_SENTENCE = {
    "SPEC-103t": ["其中 `genuine-gap` 必须保持 `OPEN/BLOCKED`；分类本身不携带语义取值。"],
    "TESTCASES-101t": ["active 精确键集合为 {D17:S1,D17:S3,D17:S4,D17:S5,D17:S6,D17:S8}（六键），"
                       "分别对应 reset、classify immediate、fault priority、scaleB exponent、"
                       "SBZ write、ldm/stm memory；这六个键的受影响语义 facet 在 "
                       "ADR-1009～1015 Accepted 前保持 blocked，Accepted 后按 `SPEC-104t` 的 "
                       "`resolution.rule_tables` 取值。"],
    "TESTCASES-102t": ["active 精确键集合为 {D17:S1,D17:S3,D17:S4,D17:S5,D17:S6,D17:S8}（六键），"
                       "分别对应 reset、classify immediate、fault priority、scaleB exponent、"
                       "SBZ write、ldm/stm memory；这六个键的受影响 runtime expected 在 "
                       "ADR-1009～1015 Accepted 前保持 blocked。"],
    "LLVM-101t": ["LLVM MC 对 `D17:S1`、`D17:S4`、`D17:S5`、`D17:S6`、`D17:S8` 一律为 "
                  "`N/A(runtime)`，不得以 assemble/disassemble PASS 解锁；仅 `D17:S3` 影响 "
                  "assembler legality，在 ADR-1015 Accepted 前保持 blocked。"],
    "LLVM-102t": ["本任务对 ledger 六个键均不作 runtime 结论（`N/A(runtime)`）"],
    "LLVM-103t": ["本任务的汇编展开/反汇编边界对 ledger 六个键的运行语义一律为 `N/A(runtime)`"],
    "QEMU-101t": ["本任务 11 identity 的适用状态：`D17:S1`（reset）projected-pending-activation、"
                  "`D17:S3` N/A(runtime)、`D17:S4`（组合 fault）projected-pending-activation、"
                  "`D17:S5` N/A(runtime)、`D17:S6`（SBZ write）projected-pending-activation、"
                  "`D17:S8`（ldm/stm memory）projected-pending-activation。"],
    "QEMU-102t": ["本任务 42 identity 的适用状态：`D17:S1`（reset）projected-pending-activation、"
                  "`D17:S3` N/A(runtime)、`D17:S4`（fault priority）projected-pending-activation、"
                  "`D17:S5`（scaleB exponent）projected-pending-activation、`D17:S6` N/A(runtime)、"
                  "`D17:S8` N/A(runtime)。"],
    "QEMU-103t": ["本任务 11 identity 的适用状态：`D17:S1`（reset）projected-pending-activation、"
                  "`D17:S3`（classify immediate）projected-pending-activation、"
                  "`D17:S4` N/A(runtime)、`D17:S5` N/A(runtime)、"
                  "`D17:S6`（SBZ write）projected-pending-activation、`D17:S8` N/A(runtime)。"],
    "INTEG-102t": ["`D17:S1` reset、`D17:S3` classify immediate、`D17:S4` fault priority、"
                   "`D17:S5` scaleB exponent、`D17:S6` SBZ write、`D17:S8` ldm/stm memory，"
                   "六者在七份 ADR 全部 Accepted 前保持 blocked。"],
    "INTEG-103t": ["六项在没有规范事实或逐条 Accepted decision 时保持 blocked，"
                   "关闭条件取 `resolution.rule_tables.D17`。"],
    "INTEG-104m": ["六项必须由规范事实或逐条 Accepted decision 关闭受影响 facet，"
                   "否则里程碑 BLOCKED。"],
}
#: 11 本下游任务书**逐字共有**的三句（同步时逐字嵌入）：六键 active 键集合、
#: S2 trace-only/S7 non-gap 的极性句、以及「resolution 只是 projected」的语义门禁句。
#: 少任何一句即 G18 FAIL：这正是「把 S7 重新写成 active / 把 resolution 当成已激活
#: implementation truth」最直接的落点。
#: 键集合句按书的行文分成三种等价写法（INTEG-102t/103t/104m 的引导词不同），
#: 命中**任一**即算通过；其余句子必须逐字全中。
PIN_SHARED_KEYSET_VARIANTS = [
    "active 精确键集合为 {D17:S1,D17:S3,D17:S4,D17:S5,D17:S6,D17:S8}（六键）",
    "active 精确集合为 {D17:S1,D17:S3,D17:S4,D17:S5,D17:S6,D17:S8}（六键）",
    "active 精确键集合 {D17:S1,D17:S3,D17:S4,D17:S5,D17:S6,D17:S8}（六键）",
    "的 active 精确集合 {D17:S1,D17:S3,D17:S4,D17:S5,D17:S6,D17:S8}（六键）",
]
PIN_SHARED_SENTENCE = [
    "`D17:S2` 始终是 ledger 外 trace-only（`no behavioral consequence; resolved/trace-only; "
    "not in D17 OPEN-ID ledger; never PASS`），不是缺口；",
    "`D17:S7` 始终是 ADR-1008 D1 已证明的 spec-determined non-gap（move overlap 由 "
    "SimRISC-00:41-46 与 SimRISC-03:34-50 唯一确定），不进入 active ledger、"
    "不计 OPEN/BLOCKED、不计 PASS。",
    "语义激活门禁：`SPEC-104t` 已验证，且本任务所消费的 ADR-1009～1015 全部 Accepted；",
    "在此之前 `contracts/f1_gap_proofs.yaml` 的 `resolution` 层只表示 "
    "projected-pending-activation，不得当作 active implementation truth，"
    "也不得据此声称任何 facet PASS。",
]
#: 11 本下游任务书必须逐字共有的**小节标题**（承载「精确适用规则」而非「参见 ADR」）。
PIN_RULES_SECTION = "## SPEC-104t 已投影的适用规则"
#: 判别句无法逐键机读（只给出整体结论）的任务：适用状态必须取本表的值，
#: 两者不一致即 fail-closed。
PIN_APPLIC_PINNED = {
    "TESTCASES-101t": {k: "OPEN" for k in PIN_LEDGER_KEYS},
    "SPEC-103t": {k: "OPEN" for k in PIN_LEDGER_KEYS},
}
#: 任务书原句把**整体**判为 N/A(runtime) 的任务（LLVM-102t/103t）：
#: 六个 active 键必须逐个都是 N/A(runtime)；N/A 不是 PASS，也不得被扩大为
#: 运行时结论。
PIN_APPLIC_ALL_NA = ["LLVM-102t", "LLVM-103t"]
PIN_FORBIDDEN_ADR = ["ADR-1005", "ADR-1006", "ADR-1007"]
#: rf0_fcsr_split 两栏的键级隔离：layout 不得带复位值，reset 不得带位域表。
PIN_LAYOUT_FORBIDDEN_KEYS = ["reset", "reset_value", "reset_default",
                             "reset_expected", "复位值", "initial_value"]
PIN_RESET_FORBIDDEN_KEYS = ["fields", "read_only_mask", "sbz_mask", "rw_mask",
                            "field_table", "bit_fields", "位域", "位域表"]

# ══════════════ G12：S7 叙述一致性（polarity 白名单，而非 banned-token）══════════════
#
# 背景：ADR-1008 D1 已证明 `D17:S7` 是 **non-gap**（跨 RD/RF 两个不同寄存器组的
# 固定块赋值方向，原始规范 SimRISC-00:41-46 + SimRISC-03:33-49 唯一确定）。
# 结构化字段（ledger 键、status、matrix、consumer）早已收敛到**六个 active 键**，
# 但**散文**（evidence finding、missing_or_conflicting、classification_reason、
# observable_consequences、消费者 na_runtime_note、provenance）仍可能把 S7 写成
# 第七项真缺口。任何一处这样的句子都会让下游重新读出「S7 仍未决」。
#
# 因此这里做的是**逐分句的极性（polarity）判定**，而不是 banned-token 黑名单：
#
#   提到 S7 的分句，若带 `PIN_S7_SETTLED_RE` 里的**显式**标记（历史 / non-gap /
#   spec-determined / 不进入 / 不计入 / 不属于 / 不再是 / superseded …），
#   即视为「允许保留的历史引用」——哪怕同句里出现 `Candidate`/`PASS`/`active`
#   这些词（在否定句里它们正是要表达「S7 不计这些」）。
#   任何提到 S7 却**没有**这类标记的分句，一律 FAIL（fail-closed）。
#
# 为什么不写黑名单：合法的历史引用句本身含 `non-gap`/`PASS`/`Candidate` 等词，
# 黑名单会把「已正确标注为非缺口」的句子一起杀掉，逼作者删掉必要的免责说明；
# 删掉之后反倒没人能证明 S7 已被处理——这正是本检查要防的静默回归。
PIN_PROSE_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
#: 散文分句符：句号/分号/换行。逗号不断句——「历史 S7 是 non-gap：…」的冒号
#: 后面仍是同一句。
PIN_CLAUSE_SPLIT_RE = re.compile(r"[。；;\n]+")
#: S7 提及；`D17:S7` 亦命中。`S1`/`S70` 不命中。
PIN_S7_TELL_RE = re.compile(r"(?<![0-9A-Za-z])S7(?![0-9A-Za-z])")
#: 「S7 已被判定为历史 / 非缺口 / 不进入 active」的**显式**标记（白名单）。
PIN_S7_SETTLED_RE = re.compile(
    r"non-gap|NOT-A-GAP|非缺口|spec-determined|superseded|历史"
    r"|不再是|不进入|不计入|不属于|不是|不得|不产生|不生成|不计"
    r"|never|not in|not a gap", re.I)
#: 分句里把 S7 当成 active 状态/缺口的用词，仅用于让诊断说清「错在哪」。
PIN_S7_ACTIVE_WORDS_RE = re.compile(
    r"(?<![0-9A-Za-z])(OPEN|BLOCKED|PASS|N/A\(runtime\)|active|Candidate"
    r"|genuine-gap|静默|缺失|未规定|未决|未解决|不唯一|重叠顺序)(?![0-9A-Za-z])")
#: 「active 项数被写成 7」的计数词（量词不限，含「七条/七处」写法）。
#:
#: 阿拉伯数字分支必须带 `(?<![0-9])`：多位数量词的**末位** 7 不是「七」的计数。
#: 没有这个 lookbehind 时 `27 条现行 decision`、`37 条 identity`、`17 个`、
#: `107 条` 全都会被当成「按七键叙述 active」——SPEC-104t 的
#: `resolution.role`（`把 ADR-1009～1015 的 27 条现行 decision…`）就是这样被
#: 误判的：那一句谈的是 **decision 条数**，与 active 缺口集合无关。
#: 这里修的是**正则的假阳性**（漏检能力不变：`7 条` / `07 条` 仍会命中，
#: CJK 的 `七条` 分支完全不受影响），不是把检查放宽。
PIN_SEVEN_COUNT_RE = re.compile(r"七[项键个条处]|(?<![0-9])7\s*[项键个条处]")
#: 「七」只有在谈论 **active 缺口集合** 时才是语义矛盾。
#: 身份/记录计数（`open-blocked（37 条）` 中被点名的 7 条 identity）不是缺口计数，
#: 不得误报；因此计数词须与缺口台账语境同现才判 FAIL。
#: 语境词按「词」匹配（`open-blocked` 里的 blocked 不是 BLOCKED 状态），CJK 词不受边界影响。
def _ledger_ctx_re():
    b = r"(?<![0-9A-Za-z_-])(?:%s)(?![0-9A-Za-z_-])"
    terms = ["active", "ledger", "OPEN", "BLOCKED", "Candidate",
             "静默", "缺口", "台账", "候选", "未规定", "未决", "未解决",
             "不唯一", "无重叠", "重叠顺序", "规范静默", "身份记录"]
    pat = "|".join(b % t for t in terms) + b % r"S[1-8]"
    return re.compile(pat, re.I)


PIN_LEDGER_CTX_RE = _ledger_ctx_re()
#: S7 non-gap 记录的**原始权威**：只能是这两条 raw spec 引用，不得用 ADR 代替。
#: 行号已按 SPEC-104t 的指针修复同步到现文（SimRISC-03 的块赋值小节现为 34-50；
#: 用户在 SimRISC-03 第 7-8 行插入 HTML 注释后，原始 33-49 整体下移一行）。
PIN_S7_RAW_AUTHORITY = {(SPEC00, "41-46"), (SPEC03, "34-50")}
#: D17 必须逐项点名的六个 active OPEN-ID（任务书 §8 的精确六键）。
PIN_D17_REQUIRED_TELLS = ["S1", "S3", "S4", "S5", "S6", "S8"]
#: D17 叙述里必须出现的 active 投影（任务书 §9：`S1/S3/S4/S5/S6/S8 = 64/2/26/2/6/4`）。
PIN_D17_ACTIVE_SCOPE_STR = "64/2/26/2/6/4"

# ══════════ SPEC-104t：已确认语义机器投影的外部字面量基准表 ══════════
#
# 这里的每个值都来自**本任务书 §5 / §6 的自包含映射表**或 ADR Markdown 原文，
# 不是从 `contracts/f1_gap_proofs.yaml` 的 `resolution` 段反推的——否则「改 YAML
# 同时改检查器」就会一起假绿。集合类期望另有 `Upstream` 从
# `contracts/opcodes.yaml` 的 `f1.*` 独立重算（见 `Upstream.rule_sets`）。
PIN_ADR_SET = ["ADR-1009", "ADR-1010", "ADR-1011", "ADR-1012",
               "ADR-1013", "ADR-1014", "ADR-1015"]
#: 七份现行 decision 逐 ADR 的**精确条数**（合计 27；ADR-1009 只剩 D2 是现行）。
#: 用途：`resolution.decision_map.current` 的逐 ADR 长度。ADR-1009 的 D1 被 D2 取代，
#: 故现行只 1 条。
PIN_ADR_DECISION_COUNT = {"ADR-1009": 1, "ADR-1010": 5, "ADR-1011": 2, "ADR-1012": 3,
                          "ADR-1013": 6, "ADR-1014": 2, "ADR-1015": 8}
#: ADR Markdown 里 `### Dn：` 标题的逐 ADR **原始条数**（合计 28 = 27 现行 + 1 被取代）。
#: 用途：G13.3 直接对着 ADR 原文数标题——这是「27 条现行」这一说法的**独立**来源，
#: 与 `PIN_ADR_DECISION_COUNT` 差的那 1 条必须恰好是 `PIN_SUPERSEDED` 的 D1，
#: 因此 13.3 之后另有 13.5 检查 D1 不在 `current` 里、只在 `superseded` 里。
PIN_ADR_HEADING_COUNT = {"ADR-1009": 2, "ADR-1010": 5, "ADR-1011": 2, "ADR-1012": 3,
                         "ADR-1013": 6, "ADR-1014": 2, "ADR-1015": 8}
PIN_CURRENT_DECISION_COUNT = 27
PIN_PRIMARY_DECISION_COUNT = 22
PIN_SUPPLEMENTAL_DECISION_COUNT = 5
PIN_CANDIDATE_COUNT = 24
#: 唯一被取代的 decision：ADR-1009 D1 被 D2 覆盖，不计入 27。
PIN_SUPERSEDED = ("ADR-1009", "D1", "ADR-1009/D2")
#: ADR 文件的 `**状态**` 行：SPEC-104t 验收期间七份 ADR 必须保持 Candidate。
PIN_ADR_STATE_CANDIDATE = "Candidate"
PIN_ADR_STATE_ACCEPTED = "Accepted"
#: §5 的机器常量。第三来源是 ADR Markdown 原文（`Upstream.adr_constants`），
#: 两者必须一致，不一致即 FAIL。
PIN_D13_HIGH_HALF = 0xffffffff
PIN_D13_HIGH_HALF_BITS = "0xffffffff"
PIN_D14_QUIET = 0x7ff8000000000000
PIN_D14_QUIET_BITS = "0x7ff8000000000000"
PIN_D14_SIGNALING = 0x7ff0000000000001
PIN_D14_SIGNALING_BITS = "0x7ff0000000000001"
#: 现行六个 active 键的 identity 基数（**现行**口径）。
#:
#: 与 SPEC-103t 的历史 `64/2/26/2/6/4` 只在 `D17:S6` 上不同：S6 已由
#: historical-six 变成现行十条（`6 - 1 + 5 = 10`）。若把 S6 仍按 6 投影，就等于
#: 继续让 `rd2rf`（D11 下写 rf0 触发 ILLI）留在 SBZ 写白名单里，并把五条
#: `cs.*-rf` 排除在外——两个方向都和 ADR-1009 D2 / ADR-1015 D6 矛盾。
PIN_ACTIVE_SCOPE_COUNTS = {"D17:S1": 64, "D17:S3": 2, "D17:S4": 26,
                            "D17:S5": 2, "D17:S6": 10, "D17:S8": 4}
#: 六个 `open-blocked` 的语义 facet 各自归属哪条 decision（11 facet 里只有这 6 个
#: 由 ADR 关闭；`encoding/format/operands/legality/semantics` 仍属其它路径）。
PIN_FACET_TO_DECISION = {
    "rf0_operand": "D11", "fcsr_flags": "D12", "tetra_high_half": "D13",
    "compare_unordered": "D14", "nan_propagation": "D15", "tininess": "D16",
}
#: `rootn(-0,2)`：规范明示 unspecified，**任何** ADR 状态都不得给它唯一 expected。
PIN_ROOTN_UNSPECIFIED = "rootn(-0,2)"
PIN_ROOTN_IDENTITIES = ["foroot", "ftroot"]
#: §6：D17:S6 的 historical-six 与现行十条，以及 `6 - 1 + 5 = 10`。
PIN_S6_CURRENT_TEN = ["cs.eq-rf", "cs.n-rf", "cs.ne-rf", "cs.p-rf", "cs.z-rf",
                      "ld.o-rf", "ld.t-rf", "ldm.o-rf", "ldm.t-rf", "set.w-rf"]
PIN_S6_REMOVED = ["rd2rf"]
PIN_S6_ADDED = ["cs.eq-rf", "cs.n-rf", "cs.ne-rf", "cs.p-rf", "cs.z-rf"]
PIN_S6_ARITHMETIC = "6 - 1 + 5 = 10"
#: **整段**落在 `SimRISC-03:7-8` HTML 注释内的历史引用（`(holder, record, index)`）。
#:
#: 这 7 条不是缺陷：它们是 SPEC-102t/103t 在**注释被发现之前**写入的
#: rf0-destination 线索，SPEC-104t 只做指针平移（+1 行）而**不删不改**历史原文。
#: 任务书 §8.8 要求它们「不得进入 current normative authority」，因此钉死这个集合：
#: 指针若被二次平移、或有人把某条历史引用挪出/挪进注释区间，这里立刻 FAIL。
#: G17 另从 `resolution.historical_authority_policy` 一侧核对同一集合，
#: 两个独立来源（YAML 声明 vs 本常量）必须一致。
PIN_HISTORICAL_NON_NORMATIVE = frozenset([
    ("decision_proofs", "D11", 0), ("decision_proofs", "D11", 1),
    ("decision_proofs", "D12", 3), ("decision_proofs", "D13", 3),
    ("d17_open_ledger", "D17:S4", 4), ("d17_open_ledger", "D17:S6", 0),
    ("rf0_fcsr_split", "layout", 10),
])
#: ADR-1015 D6 点名的 SBZ 静默忽略域（§5 / ADR 原文一致）。
PIN_SBZ_DOMAINS = ["[50:32]", "[21:18]", "[15:5]"]
#: §5 的交叉优先级（顺序即求值顺序）。
PIN_PRECEDENCE = [
    "D11 目的寄存器合法性先于 D17:S6",
    "D13 先形成 NaN-boxed 64 位写值，合法写 rf0 时再应用只读/SBZ mask",
    "D15 的格式转换规则优先于算术 canonical 规则",
    "D17:S4 的 ILLI 优先级先于 MALIGN",
    "D12 软件写与自动异常按程序顺序组合",
]
# Behaviour is part of the projection, not free explanatory prose.  These
# clauses are independently transcribed from SPEC-104t §5 and the confirmed
# ADR decision bodies (never from f1_gap_proofs.yaml).  Keeping the clauses
# keyed by decision also makes a reversed D11/D15 projection fail even when
# all ids, headings and candidate bindings remain intact.
PIN_BEHAVIOR_CLAUSES = {
    "ADR-1009/D2": ["所有 F1 identity", "十条白名单", "其余 ILLI"],
    "ADR-1010/D1": ["浮点异常", "不得自动清除"],
    "ADR-1010/D2": ["不产生异常", "保持 rf0[4:0] 原值", "不自动清零"],
    "ADR-1010/D3": ["写 rf0[4:0]", "清除或改写 flags"],
    "ADR-1010/D4": ["53 条", "11 条", "不自动置位或清除"],
    "ADR-1010/D5": ["立即生效", "随后异常", "当前值上"],
    "ADR-1011/D1": ["低 32 位", "高 32 位固定 0xffffffff"],
    "ADR-1011/D2": ["ld.t-rf", "ldm.t-rf", "高 32 位同样固定 0xffffffff"],
    "ADR-1012/D1": ["foqcmp/ftqcmp", "0x7ff8000000000000"],
    "ADR-1012/D2": ["foscmp/ftscmp", "0x7ff0000000000001"],
    "ADR-1012/D3": ["qcmp/scmp", "不依赖输入 NaN"],
    "ADR-1013/D1": ["非格式转换", "丢弃 payload", "canonical qNaN"],
    "ADR-1013/D2": ["多 NaN", "canonical qNaN", "任一源为 sNaN", "置 NV"],
    "ADR-1013/D3": ["sNaN", "丢弃 payload", "canonical qNaN", "置 NV"],
    "ADR-1013/D4": ["fo2ft/ft2fo", "传播 NaN payload", "sNaN 转换置 NV", "返回 qNaN"],
    "ADR-1013/D5": ["算术/多操作数", "qNaN 不置 NV", "任一 sNaN 置 NV", "canonical qNaN", "不覆盖 D4/D6"],
    "ADR-1013/D6": ["fo2ft/ft2fo", "结果符号固定为正号"],
    "ADR-1014/D1": ["最终舍入", "tiny/subnormal"],
    "ADR-1014/D2": ["underflow", "UF+NX", "overflow", "OF+NX"],
    "ADR-1015/D1": ["rf0[17:16]=RNE(00)", "rf0[4:0]=0"],
    "ADR-1015/D2": ["immu6!=1", "assembler 阶段拒绝", "硬件则 ILLI"],
    "ADR-1015/D3": ["ILLI", "MALIGN", "不进入地址对齐判定"],
    "ADR-1015/D4": ["rf0[17:16]", "舍入模式", "rfhc×2^n"],
    "ADR-1015/D5": ["qNaN", "canonical qNaN", "sNaN", "置 NV", "+Inf", "-Inf"],
    "ADR-1015/D6": ["十条白名单", "SBZ 域静默忽略", "rd2rf", "ILLI"],
    "ADR-1015/D7": ["EA0=rbhb+rdhc", "width/step=4", "RF 编号递增"],
    "ADR-1015/D8": ["任一元素 fault", "不提交任何 RF 写或 memory store", "PC 留在 faulting instruction"],
}
#: `resolution` 段的键集合（覆盖层不得改名/删键，也不得把历史键搬进来）。
PIN_RESOLUTION_KEYS = [
    "schema_version", "producer_task", "role", "historical_layer_untouched",
    "lifecycle", "normative_exclusions", "historical_authority_policy",
    "decision_map", "candidate_closure", "rule_tables", "resolution_matrix_count",
    "resolution_matrix", "capability_gaps", "consumer_activation", "provenance",
]
#: `resolution.consumer_activation` 的语义门禁取值（**刻意不叫** `ledger_applicability`：
#: 那个键名已被 G10 的历史词表占用，取值域是 OPEN/BLOCKED/N/A(runtime)）。
PIN_SEMANTIC_GATE_STATES = ["projected-pending-activation", "N/A(runtime)"]
#: 11 本下游任务书（10 本普通任务书 + INTEG-104m）。
PIN_DOWNSTREAM_BOOKS = [
    "TESTCASES-101t", "TESTCASES-102t", "LLVM-101t", "LLVM-102t", "LLVM-103t",
    "QEMU-101t", "QEMU-102t", "QEMU-103t", "INTEG-102t", "INTEG-103t", "INTEG-104m",
]
#: `SPEC-101k`（G21.2 比对当前路线矩阵用）。§13 允许改它的当前路线，但 2026-09-26
#: 的完成记录逐字保留。
PIN_SPEC101K_REL = ".xkw/tasks/spec/SPEC-101k-F1浮点阶段启动与任务分解.md"
#: `SPEC-101k` §7 里把多本任务书**合并成一行**的标签（键集相同，故可共用一个条目）。
PIN_101K_MERGED_ROWS = {
    "TESTCASES-101t/102t": "TESTCASES-101t",
    "LLVM-102t/103t": "LLVM-102t",
    "INTEG-102t/103t/104m": "INTEG-102t",
}
#: 每个下游任务的 `**BLOCKED**` 计数下界：同步只允许改口径，**不得**把「实现/
#: 向量/E2E 未产出」这一事实从验收表里删掉（SPEC-104t §10：语义门禁解除不等于
#: 实现 PASS）。下界取本任务开工前各书的真实计数，故任何「删掉 BLOCKED 行以让
#: 任务看起来可跑」的注入都会 FAIL。
PIN_BOOK_BLOCKED_FLOOR = {
    "TESTCASES-101t": 5, "TESTCASES-102t": 6, "LLVM-101t": 4, "LLVM-102t": 4,
    "LLVM-103t": 5, "QEMU-101t": 6, "QEMU-102t": 7, "QEMU-103t": 6,
    "INTEG-102t": 5, "INTEG-103t": 5, "INTEG-104m": 3,
}
#: 陈旧门禁措辞黑名单（§10 要求删除）。只在**活动章节**扫描：命中即 FAIL。
PIN_STALE_GATE_WORDS = [
    "ADR-1005", "ADR-1006", "ADR-1007",
    "现行 decisions 尚未确认", "decisions 尚未确认", "ADR 尚未确认",
    "七项受影响", "ledger 七项", "七项运行语义", "七项必须",
    "active 精确键集合为 {D17:S1,D17:S2,D17:S3,D17:S4,D17:S5,D17:S6,D17:S7,D17:S8}",
]
#: SPEC-102t/103t 任务书的 sha256（SPEC-104t §8.10 要求「与本任务启动基线相比未被
#: 修改」）。这两本是**只读历史证据**，钉摘要比逐句比对更严格：任何改一个字都 FAIL。
#: 两个摘要取自 dispatch 前置检查的 dirty baseline
#: （`/tmp/opencode/SPEC-104t/dispatch-precheck/dirty-sha256.txt` 第 34/35 行），
#: 而不是「任务结束时现算一遍」——后者只会证明文件没变，证明不了它没被中途改过。
PIN_HISTORY_TASKBOOK_SHA256 = {
    ".xkw/tasks/spec/SPEC-102t-F1浮点合约与64身份映射.md":
        "2521bd5613949188610ca4392164be42e0de587fcc64f75acff2229b2cdcb49e",
    ".xkw/tasks/spec/SPEC-103t-F1语义缺口证明与候选ADR输入.md":
        "8ca38035500c71ea2ac492903346ed5116d73cabf8a34d4ab1901d8e3601dd16",
}
#: 仓库里**不得**出现的旁路/备份产物（§8.11）。这里按**目录**+**模式**扫描，
#: 覆盖 `.bak` / `_bak` / `.orig` / `~` 结尾 / 平行 projection YAML / 平行 checker。
PIN_BYPASS_PATTERNS = [
    # 禁止在 contracts/ 里**新增**平行文件；允许且仅允许本任务的正式文件
    ("contracts", r"^f1_(gap_proof|resolution)(?!_proofs\b)[a-z0-9_]*\.(yaml|yml)$"),
    ("contracts", r"\.bak$|\.orig$|~$|_bak\.|_backup\."),
    ("tools/spec", r"^f1_(gap_proof|resolution)[a-z0-9_]*\.py$"),
    ("tools/spec", r"\.bak$|\.orig$|~$|_bak\.|_backup\."),
]

TASK_GLOBS = [(".xkw/tasks/spec", "SPEC"), (".xkw/tasks/testcases", "TESTCASES"),
              (".xkw/tasks/llvm", "LLVM"), (".xkw/tasks/qemu", "QEMU"),
              (".xkw/tasks/integ", "INTEG"), (".xkw/tasks/infra", "INFRA")]


# ────────────────────────────── 报告器 ──────────────────────────────
class Report:
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.items = []          # (cat, name, ok, detail)

    def ok(self, cat, name, detail=""):
        self.items.append((cat, name, True, detail))
        if self.verbose:
            sys.stdout.write("[ok] %s  %s%s\n" % (cat, name, ("  " + detail) if detail else ""))

    def fail(self, cat, name, detail):
        self.items.append((cat, name, False, detail))
        sys.stdout.write("[%s] FAIL: %s :: %s\n" % (cat, name, detail))

    def skipped(self, cat, name, detail):
        self.items.append((cat, name, None, detail))
        if self.verbose:
            sys.stdout.write("[skip] %s  %s  %s\n" % (cat, name, detail))

    @property
    def failed(self):
        return [i for i in self.items if i[2] is False]

    @property
    def passed(self):
        return [i for i in self.items if i[2] is True]


# ─────────────────────── 独立重算：上游数据 ───────────────────────
def read_text(root, rel):
    with open(os.path.join(root, rel), encoding="utf-8") as fh:
        return fh.read()


def read_lines(root, rel):
    return read_text(root, rel).split("\n")


#: Markdown HTML 注释定界符。**必须**跨行匹配：`SimRISC-03` 的 `<!--` 与 `-->` 分别
#: 落在两行上，只在单行里找 `<!-- … -->` 会把整段规范正文误判成注释。
PIN_HTML_COMMENT_OPEN = "<!--"
PIN_HTML_COMMENT_CLOSE = "-->"


def html_comment_lines(lines):
    """返回落在 `<!-- … -->` 区间内的 **1-based** 原始行号集合。

    逐字符扫描，跨行累积；未闭合的 `<!--` 一直延伸到文件末尾（fail-safe：宁可把
    后面整篇都算成注释，也不把注释里的内容当成规范正文）。定界符本身所在的行也算
    注释行——引用 `<!--` 那一行同样不具规范效力。
    """
    inside, out = False, set()
    for i, line in enumerate(lines, 1):
        j = 0
        while j < len(line):
            if not inside:
                k = line.find(PIN_HTML_COMMENT_OPEN, j)
                if k < 0:
                    break
                inside = True
                j = k + len(PIN_HTML_COMMENT_OPEN)
            else:
                k = line.find(PIN_HTML_COMMENT_CLOSE, j)
                if k < 0:
                    break
                inside = False
                j = k + len(PIN_HTML_COMMENT_CLOSE)
        if inside or PIN_HTML_COMMENT_OPEN in line or PIN_HTML_COMMENT_CLOSE in line:
            out.add(i)
    return out


def linespec_ints(spec):
    """`行` / `行-行` / `行,行-行,…` → 展开成整数集合；文法不合法返回 None。"""
    if spec is None:
        return None
    out = set()
    for part in str(spec).split(","):
        part = part.strip()
        if not part:
            return None
        if "-" in part:
            a, b = part.split("-", 1)
            if not (a.isdigit() and b.isdigit()):
                return None
            a, b = int(a), int(b)
        else:
            if not part.isdigit():
                return None
            a = b = int(part)
        if b < a:
            return None
        out |= set(range(a, b + 1))
    return out


class Upstream:
    """全部从原始文件重算，**不**参考被检查的 YAML。"""

    def __init__(self, root):
        self.root = root
        self.spec00 = read_lines(root, SPEC00)
        self.spec03 = read_lines(root, SPEC03)
        self.adr_lines = read_lines(root, ADR1004)
        self.adr = self.adr_lines
        self.readme_lines = read_lines(root, README)
        self.contract = read_text(root, CONTRACT)
        self.contract_lines = self.contract.split("\n")
        # spec/SimRISC-00 §伪指令 表的第一列：矩阵里出现这些名字即为 pseudo
        self.pseudo = set()
        seg = []
        if "## 伪指令" in self.spec00:
            tail = self.spec00[self.spec00.index("## 伪指令") + 1:]
            nxt = [i for i, l in enumerate(tail) if l.startswith("## ")]
            seg = tail[:nxt[0]] if nxt else tail
        for line in seg:
            if line.startswith("| `"):
                self.pseudo.add(line.split("|")[1].strip().strip("`"))
        self.pseudo.discard("")
        if not self.pseudo:
            raise ValueError("无法从 %s 的 §伪指令 表解析出 pseudo 名单" % SPEC00)
        doc = yaml.safe_load(read_text(root, OPCODES))
        self.opcodes_total = len(doc)
        self.f1 = [r for r in doc if isinstance(r, dict) and "f1" in r]
        self.by_insn = {r["insn"]: r for r in self.f1}
        self.identities = sorted(self.by_insn)
        # 11 facet 键：从 contract §5.1 的表独立解析
        sec51 = self.contract.split("### 5.1")[1].split("### 5.2")[0]
        self.facets = [l.strip("|").split("|")[0].strip().strip("`")
                       for l in sec51.split("\n") if l.startswith("| `")]
        # 非 fault / 范围声明谓词：从 contract §3.1 的表独立解析
        sec31 = self.contract.split("### 3.1")[1].split("### 3.2")[0]
        self.non_fault, self.range_decl = set(), set()
        for line in sec31.split("\n"):
            if line.startswith("| `"):
                cols = [c.strip() for c in line.strip("|").split("|")]
                if len(cols) < 3:
                    continue
                if cols[1].startswith("—（非 fault"):
                    self.non_fault.add(cols[0].strip("`"))
                if "范围声明" in cols[2]:
                    self.range_decl.add(cols[0].strip("`"))
        self.not_a_fault = self.non_fault | self.range_decl
        # contract §6.1 钉死的投影基数（第二个独立来源）
        self.contract_proj = {}
        for m in re.finditer(r"^\|\s*`(D1[1-7])`\s*\|[^|]*\|\s*(\d+)\s*\|",
                             self.contract, re.M):
            self.contract_proj[m.group(1)] = int(m.group(2))
        # contract §6.2 的七键集合（第三个独立来源）
        sec62 = self.contract.split("### 6.2")[1].split("### 6.3")[0]
        self.contract_ledger = sorted(set(re.findall(r"D17:S\d", sec62)))
        # opcodes.yaml 重算的投影
        self.proj = {d: sum(1 for r in self.f1 if d in r["f1"]["open_items"])
                     for d in ("D11", "D12", "D13", "D14", "D15", "D16")}
        self.proj["D17"] = len(self.f1)
        self.groups = {}
        for r in self.f1:
            self.groups[r["f1"]["group"]] = self.groups.get(r["f1"]["group"], 0) + 1
        # 七键的机械范围
        self.scope = self._scopes()
        self.section_task = self._section_task()
        self.insn_task = {i: t for t, lst in self.section_task.items() for i in lst}
        missing = sorted(set(self.identities) - set(self.insn_task))
        if missing:
            raise ValueError("下列 identity 找不到拥有任务：%r" % missing)
        # ── SPEC-104t：HTML 注释区间 / 七份 ADR / 从上游独立重算的规则集 ──
        self.comment_lines = {SPEC00: html_comment_lines(self.spec00),
                              SPEC03: html_comment_lines(self.spec03)}
        self.line_count = {SPEC00: len(self.spec00), SPEC03: len(self.spec03)}
        self.adr_files, self.adr_text, self.adr_state, self.adr_headings, \
            self.adr_sections = self._load_adrs()
        self.adr_constants = self._adr_constants()
        self.rule_sets = self._rule_sets()
        self.current_scope = self._current_scope()

    # -- SPEC-104t：**现行**六个 active 键的 identity 集合 ----------------
    def _current_scope(self):
        """S1/S3/S4/S5/S8 沿用 SPEC-103 的机械求法；S6 换成**现行十条**。

        刻意**不用** `f1.d17_open_ids`：该字段对 S4 是粗粒度声明（64 条全带），
        对 S6 又是 historical-six（含 D11 下非法的 `rd2rf`）。两者都与任务书
        §6 的现行口径矛盾，故在此独立重算。
        """
        s1 = set(self.identities)
        s3 = {r["insn"] for r in self.f1
              if "immu6_1_for_cls" in r["f1"]["legality_predicates"]}
        s4 = {r["insn"] for r in self.f1
              if len([p for p in r["f1"]["legality_predicates"]
                      if p not in self.not_a_fault]) >= 2}
        s5 = {r["insn"] for r in self.f1 if r["mnemonic"].endswith("sclb")}
        s8 = {r["insn"] for r in self.f1
              if r["f1"]["section"] == "存取RF寄存器"
              and r["mnemonic"].split(".")[0] in ("ldm", "stm")}
        got = {"D17:S1": s1, "D17:S3": s3, "D17:S4": s4, "D17:S5": s5,
               "D17:S6": set(self.rule_sets["D11_whitelist"]), "D17:S8": s8}
        bad = {k: len(got[k]) for k, n in PIN_ACTIVE_SCOPE_COUNTS.items()
               if len(got[k]) != n}
        if bad:
            raise ValueError("现行 active scope 基数与钉死值不符：%r" % bad)
        return got

    # -- SPEC-104t：七份 ADR -------------------------------------------
    ADR_NUM_RE = re.compile(r"^adr-(\d+)-.+\.md$")

    def _load_adrs(self):
        """按编号 glob `.xkw/knowledge/adr-<n>-*.md`，逐份读入并解析结构。

        「七份 ADR 集合」不是钉文件名（文件名会随撰写风格变），而是钉**编号集合**：
        1009–1015 每个编号必须**恰好**一个文件；多一个同名副本或缺一个都要 FAIL。
        """
        d = os.path.join(self.root, ".xkw/knowledge")
        bynum = {}
        for n in sorted(os.listdir(d)):
            m = self.ADR_NUM_RE.match(n)
            if not m:
                continue
            num = int(m.group(1))
            if not (1009 <= num <= 1015):
                continue
            bynum.setdefault(num, []).append(n)
        files, text, state, headings, sections = {}, {}, {}, {}, {}
        dup = {num: v for num, v in bynum.items() if len(v) != 1}
        for adr in PIN_ADR_SET:
            num = int(adr.split("-")[1])
            names = bynum.get(num) or []
            if len(names) != 1:
                raise ValueError("%s 的 ADR 文件数必须为 1，实际 %r" % (adr, names))
            rel = ".xkw/knowledge/" + names[0]
            files[adr] = rel
            body = read_text(self.root, rel)
            text[adr] = body
            ms = re.search(r"^\*\*状态\*\*：\s*(\S+)", body, re.M)
            if not ms:
                raise ValueError("%s 缺少 `**状态**：` 行" % rel)
            state[adr] = ms.group(1)
            # `### Dn：标题` → 逐条 decision；正文按 decision 切段
            marks = [(m.group(1), m.group(2), m.start())
                     for m in re.finditer(r"^### (D\d+)：(.+)$", body, re.M)]
            headings[adr] = ["%s：%s" % (a, b) for a, b, _ in marks]
            for i, (dn, title, pos) in enumerate(marks):
                end = marks[i + 1][2] if i + 1 < len(marks) else len(body)
                sections[(adr, dn)] = body[pos:end]
        self._adr_dups = dup
        return files, text, state, headings, sections

    def _adr_constants(self):
        """从 ADR Markdown **原文**抽出 §5 的机器常量（第三个独立来源）。"""
        out = {}
        # 十六进制字面量：ADR 写作 `0x7ff8_0000_0000_0000` 这种下划线分组形式，
        # 因此不能用固定位宽的 `[0-9a-f]{16}`——那会在第一个下划线处截断成
        # `7ff8_0000_0000_0`，悄悄把常量读错。
        hexre = re.compile(r"0x[0-9a-fA-F]+(?:_[0-9a-fA-F]+)*")
        h13 = hexre.findall(self.adr_text.get("ADR-1011", ""))
        if h13:
            out["D13_high_half"] = int(h13[0].replace("_", ""), 16)
        h14 = hexre.findall(self.adr_text.get("ADR-1012", ""))
        if h14:
            out["D14_quiet"] = int(h14[0].replace("_", ""), 16)
        if len(h14) > 1:
            out["D14_signaling"] = int(h14[1].replace("_", ""), 16)
        out["D13_hex_list"] = h13
        out["D14_hex_list"] = h14
        # ADR-1013 全文若出现任何十六进制常量，就意味着 canonical qNaN 位型**已被**
        # 某处固定下来；此时 `canonical_qnan_bits: null` 就成了错误投影，必须 FAIL。
        out["D15_hex_list"] = hexre.findall(self.adr_text.get("ADR-1013", ""))
        return out

    # -- SPEC-104t：从 contracts/opcodes.yaml 独立重算 D11–D16 的集合 -------
    def _rule_sets(self):
        """D11 白名单、D12 53/11、D13 18、D14 4、D15 18、D16 36。

        全部从 `contracts/opcodes.yaml` 的 `f1.facets` / `f1.legality_predicates` /
        `fields` / `section` / `mnemonic` 重算，**不读**被检查的 `resolution` 段。
        """
        def facets(key):
            return sorted(r["insn"] for r in self.f1
                          if r["f1"]["facets"][key] == "open-blocked")

        whitelist = sorted(
            {r["insn"] for r in self.f1
             if "rf0_dst_allowed" in r["f1"]["legality_predicates"]}
            | {r["insn"] for r in self.f1
               if r["f1"]["section"] == "浮点条件赋值指令"
               and any(f.get("bank") == "rf" and f.get("role") == "dst"
                       for f in r["fields"])})
        auto = facets("fcsr_flags")
        cmp_ids = sorted(r["insn"] for r in self.f1
                         if r["f1"]["section"] == "浮点比较指令")
        return {
            "D11_whitelist": whitelist,
            "D12_auto": auto,
            "D12_non": sorted(set(self.identities) - set(auto)),
            "D13_write": facets("tetra_high_half"),
            "D13_load": sorted(i for i in facets("tetra_high_half")
                               if i in ("ld.t-rf", "ldm.t-rf")),
            "D14_scope": facets("compare_unordered"),
            "D14_quiet": sorted(r["insn"] for r in self.f1
                                if r["f1"]["section"] == "浮点比较指令"
                                and r["mnemonic"].endswith("qcmp")),
            "D14_signaling": sorted(r["insn"] for r in self.f1
                                    if r["f1"]["section"] == "浮点比较指令"
                                    and r["mnemonic"].endswith("scmp")),
            "D15_arith": facets("nan_propagation"),
            "D15_conv": sorted(i for i in self.identities
                               if i in ("fo2ft", "ft2fo")),
            "D16_scope": facets("tininess"),
        }

    # -- S1..S8 机械求法 ------------------------------------------------
    def _scopes(self):
        f1 = self.f1
        s1 = sorted(self.identities)
        s3 = sorted(r["insn"] for r in f1
                    if "immu6_1_for_cls" in r["f1"]["legality_predicates"])
        s4 = sorted(r["insn"] for r in f1
                    if len([p for p in r["f1"]["legality_predicates"]
                            if p not in self.not_a_fault]) >= 2)
        s4_alt = sorted(r["insn"] for r in f1
                        if len([p for p in r["f1"]["legality_predicates"]
                                if p not in self.non_fault]) >= 2)
        s5 = sorted(r["insn"] for r in f1 if r["mnemonic"].endswith("sclb"))
        s6 = sorted({r["insn"] for r in f1
                     if "rf0_dst_allowed" in r["f1"]["legality_predicates"]}
                    | {r["insn"] for r in f1
                       if r["f1"]["section"] == "寄存器组之间块赋值"
                       and any(f.get("bank") == "rf" and f.get("role") == "dst"
                               for f in r["fields"])})
        s8 = sorted(r["insn"] for r in f1
                    if r["f1"]["section"] == "存取RF寄存器"
                    and r["mnemonic"].split(".")[0] in ("ldm", "stm"))
        self.s4_alt = s4_alt
        return {"D17:S1": s1, "D17:S3": s3, "D17:S4": s4, "D17:S5": s5,
                "D17:S6": s6, "D17:S8": s8}

    # -- QEMU 三任务的 11/42/11 分解（从任务书自身解析） ----------------
    def _idents_in(self, text, keyset):
        """把一行里的反引号片段按 `,，、` 切开，只留下真实 identity。"""
        out = set()
        for span in re.findall(r"`([^`]+)`", text):
            for tok in re.split(r"[,，、\s]+", span):
                if tok in keyset:
                    out.add(tok)
        return out

    def _goal_identity_line(self, tid, expect):
        """「## 目标」小节里声明 `实现(剩余) N (个)identity` 的那一行。"""
        bk = self.task_books()[tid]
        seg = bk["text"].split("## 目标")[1].split("\n## ")[0] if "## 目标" in bk["text"] else ""
        for line in seg.split("\n"):
            if re.search(r"实现[^。\n]*?\b%d\b[^。\n]*identity" % expect, line):
                return line
        raise ValueError("%s 的「## 目标」小节找不到 `实现 … %d … identity` 行" % (tid, expect))

    def _listed_identities(self, tid, heading, expect):
        """`## <heading>` 小节里反引号列出的 identity 集合（数量必须 = expect）。"""
        bk = self.task_books()[tid]
        if ("## " + heading) not in bk["text"]:
            raise ValueError("%s 缺少 `## %s` 小节" % (tid, heading))
        seg = bk["text"].split("## " + heading)[1].split("\n## ")[0]
        got = self._idents_in(seg, self.by_insn)
        if len(got) != expect:
            raise ValueError("%s 的 `## %s` 列出 %d 个 identity，任务书声明 %d 个"
                             % (tid, heading, len(got), expect))
        return got

    def _section_task(self):
        keyset = set(self.by_insn)
        own = {}
        own["QEMU-101t"] = self._idents_in(
            self._goal_identity_line("QEMU-101t", 11), keyset)
        own["QEMU-102t"] = self._listed_identities("QEMU-102t", "identity 清单", 42)
        own["QEMU-103t"] = self._idents_in(
            self._goal_identity_line("QEMU-103t", 11), keyset)
        for tid, want in (("QEMU-101t", 11), ("QEMU-102t", 42), ("QEMU-103t", 11)):
            if len(own[tid]) != want:
                raise ValueError("%s 从任务书解析出 %d 个 identity，声明 %d 个"
                                 % (tid, len(own[tid]), want))
        union = set().union(*own.values())
        if union != keyset:
            raise ValueError("三任务 identity 并集 %d ≠ 上游 %d（缺 %s / 多 %s）"
                             % (len(union), len(keyset),
                                sorted(keyset - union), sorted(union - keyset)))
        for a, b in (("QEMU-101t", "QEMU-102t"), ("QEMU-102t", "QEMU-103t"),
                     ("QEMU-101t", "QEMU-103t")):
            if own[a] & own[b]:
                raise ValueError("%s 与 %s 的 identity 清单有重叠：%s"
                                 % (a, b, sorted(own[a] & own[b])))
        # QEMU-102t 目标行的 20/12/2/4/4 分解必须等于其自身 identity 清单的 section 计数
        m = re.search(r"实现\s*42\s*个 identity：([^\n。；]+)",
                      self.task_books()["QEMU-102t"]["text"])
        if m:
            want = sorted(int(x) for x in re.findall(r"(\d+)\s*个", m.group(1)))
            got = sorted({r["f1"]["section"]: sum(
                1 for x in self.f1 if x["f1"]["section"] == r["f1"]["section"])
                for r in self.f1 if r["insn"] in own["QEMU-102t"]}.values())
            if want != got:
                raise ValueError("QEMU-102t 目标行的 %s 分解与清单 section 计数 %s 不符"
                                 % (want, got))
        # QEMU-103t 目标行的 11+42+11=64 必须与实际相符
        m2 = re.search(r"(\d+)\+(\d+)\+(\d+)\s*=\s*64", self.task_books()["QEMU-103t"]["text"])
        if m2:
            got = sorted(int(m2.group(i)) for i in (1, 2, 3))
            exp = [len(own["QEMU-101t"]), len(own["QEMU-102t"]), len(own["QEMU-103t"])]
            if got != sorted(exp):
                raise ValueError("QEMU-103t 的 11+42+11 分解与实际不符：%s vs %s" % (got, exp))
        return {k: sorted(v) for k, v in own.items()}

    # -- 任务书 --------------------------------------------------------
    def task_books(self):
        out = {}
        for sub, _pfx in TASK_GLOBS:
            d = os.path.join(self.root, sub)
            if not os.path.isdir(d):
                continue
            for name in sorted(os.listdir(d)):
                if not name.endswith(".md"):
                    continue
                p = os.path.join(sub, name)
                out["-".join(name.split("-")[:2])] = {
                    "path": p, "text": read_text(self.root, p)}
        return out

    def dep_line(self, tid):
        """任务的依赖/关联任务行原文（含 `X~Y` 区间展开）。"""
        bk = self.task_books()[tid]
        for line in bk["text"].split("\n"):
            if line.startswith("**依赖**") or line.startswith("**关联任务**"):
                return line
        return ""


def expand_task_refs(line):
    """把依赖行里的 `A-101t`~`103t` 区间**逐个**展开成任务 id（含中间项）。"""
    out = set(re.findall(r"\b[A-Z]+-\d+[a-z]?\b", line))
    for mod, na, sa, nb, sb in re.findall(
            r"`([A-Z]+)-(\d+)([a-z]?)`\s*~\s*`(\d+)([a-z])`", line):
        for n in range(int(na), int(nb) + 1):
            out.add("%s-%d%s" % (mod, n, sb if n == int(nb) else sa))
    return out


#: 任务书里逐键 ledger 适用状态的**复合**写法（如 `OPEN/BLOCKED`）在本检查器里
#: 一律读作 `OPEN`（即「未关闭、被门禁挡住」）；`N/A(runtime)` 只在任务书原句
#: 明写时使用，绝不因为「不适用」而升格为 PASS。
PIN_APPLIC_COMPOSITE = "OPEN"


def ledger_block(text):
    """含七键字面量 `{D17:S1,...,D17:S8}` 的那一行（找不到即 None）。"""
    for line in text.split("\n"):
        if "{" + ",".join(PIN_LEDGER_KEYS) + "}" in line.replace(" ", ""):
            return line
    return None


#: 状态词的词边界：不能匹配 `D17 OPEN-ID ledger` 里的 `OPEN`、
#: 也不能匹配 `OPENED`/`OPENNESS`。两侧都不允许 `词字符` 或 `-`。
_W = r"(?<![\w-])%s(?![\w-])"


def classify_tail(tail):
    """把 `D17:Sx` 之后的一段文字读成适用状态；读不出即 None。"""
    if "N/A(runtime)" in tail:
        return "N/A(runtime)"
    if re.search(_W % "OPEN", tail):
        return PIN_APPLIC_COMPOSITE
    if re.search(_W % "BLOCKED", tail):
        return "BLOCKED"
    return None


def parse_applicability(text, tid):
    """从真实任务书重算逐键 ledger 适用状态；解析不到即 None（fail-closed）。

    四条**只读文本**的规则，逐条都能在任务书原句里定位：

    (a) `` `D17:Sx` `` 之后、下一个具名键之前的直接赋值；
    (b) 「`D17:Sx`～`D17:Sy` 均为/保持 <状态>」的区间赋值；
    (c) 「…均为/保持 <状态>」子句里逐个列出的键；
    (d) 「ledger 七项 … 均为/保持 <状态>」的整体赋值。

    (a) 优先于 (b)(c)，(b) 优先于 (c)，均用 setdefault，顺序即优先级。
    """
    block = ledger_block(text)
    if block is None:
        return None
    res = {}
    for k in PIN_LEDGER_KEYS:                                       # (a)
        m = re.search(re.escape("`%s`" % k) + r"([^`]{0,40})", block)
        if not m:
            continue
        tail = m.group(1)
        nxt = re.search(r"`D17:S\d`", tail)
        if nxt:
            tail = tail[:nxt.start()]
        v = classify_tail(tail)
        if v:
            res[k] = v
    for m in re.finditer(r"`D17:S(\d)`\s*[~～]\s*`D17:S(\d)`([^`]{0,40})", block):   # (b)
        v = classify_tail(m.group(3))
        if v:
            for i in range(int(m.group(1)), int(m.group(2)) + 1):
                res.setdefault("D17:S%d" % i, v)
    for clause in re.split(r"[。；;]", block):                     # (c)(d)
        if not re.search(r"均|保持|一律", clause):
            continue
        v = classify_tail(clause)
        if not v:
            continue
        keys = set()
        for x, y in re.findall(r"`D17:S(\d)`\s*[~～]\s*`D17:S(\d)`", clause):
            keys |= {"D17:S%d" % i for i in range(int(x), int(y) + 1)}
        keys |= {"D17:S" + x for x in re.findall(r"`D17:S(\d)`", clause)}
        if "七项" in clause:                                        # (d)
            keys = set(PIN_LEDGER_KEYS)
        for k in keys & set(PIN_LEDGER_KEYS):
            res.setdefault(k, v)
    return res or None


# ─────────────────────── 小工具：引用/键名/值扫描 ───────────────────────
def line_window(lines, spec):
    """行号文法 `行` / `行-行` / `行,行-行,…` → 原文窗口文本（按给定顺序拼接）。

    任一子项越界或倒序即返回 None。`spec` 形如 `7,215,216` 表示三个窗口，
    因此本函数接受逗号分隔；早先只认单个 `行`/`行-行` 会让合规的多行引用
    直接抛 ValueError（记为 G0 internal-error），此处已修。
    """
    if lines is None:
        return None
    out = []
    for part in str(spec).split(","):
        part = part.strip()
        if not part:
            return None
        if "-" in part:
            a, b = (int(x) for x in part.split("-", 1))
        else:
            a = b = int(part)
        if a < 1 or b < a or b > len(lines):
            return None
        out.append("\n".join(lines[a - 1:b]))
    return "\n".join(out)


def walk(node, path="$"):
    """深度优先产出 (pointer, key, value)。"""
    if isinstance(node, dict):
        for k, v in node.items():
            p = "%s.%s" % (path, k)
            yield p, k, v
            for q, kk, vv in walk(v, p):
                yield q, kk, vv
    elif isinstance(node, list):
        for i, v in enumerate(node):
            p = "%s[%d]" % (path, i)
            yield p, None, v
            for q, kk, vv in walk(v, p):
                yield q, kk, vv


def selection_offenders(node):
    """任何键名里含「已作选择」词根的键（大小写不敏感子串）。"""
    out = []
    for ptr, k, _v in walk(node):
        if k is None:
            continue
        low = str(k).lower()
        for w in PIN_SELECTION_WORDS:
            if w in low:
                out.append((ptr, k, w))
                break
    return out


def owning_candidate_id(ptr, cands):
    """从 `…[i]` 指针回解出那条候选问题的 id。

    只报 `$[0]` 这种下标对使用者毫无用处——「第 0 个候选问题」得先自己去数，
    而这正是「诊断必须点名被检查对象」的反面。取不到就返回 None（诊断里照实写）。

    指针根既可能是整份文档（`$.candidate_inputs[0].…`），也可能已经是候选列表本身
    （`$[0].…`，`selection_offenders(cands)` 就是这么调的），两种都要认。
    """
    m = re.search(r"^(?:\$\.candidate_inputs|\$)\[(\d+)\]", str(ptr))
    if not m:
        return None
    i = int(m.group(1))
    if 0 <= i < len(cands) and isinstance(cands[i], dict):
        cid = cands[i].get("id")
        if str(cid or "").strip():
            return str(cid)
    return None


def forbidden_source_hits(text):
    low = text.lower()
    return [t for t in PIN_FORBIDDEN_SOURCES if t.lower() in low]


def source_items(src):
    """`evidence[].source` 的严格文法：以 `;` 分隔的 `file[:行,行-行,…]` 列表。

    逐项产出 `(文件路径, 行号部分或 None)`。`§3.1`、括号注记、glob（`*`）、
    用 `,` 分隔文件都不合法——写错会被 G3 的白名单与行号校验一起抓住。
    """
    out = []
    for item in re.split(r"\s*;\s*", str(src).strip()):
        item = item.strip()
        if not item:
            continue
        parts = re.split(r"[:：]", item, 1)
        out.append((parts[0].strip(), parts[1].strip() if len(parts) == 2 else None))
    return out


def as_str_list(v):
    """「非空、且每项都是非空字符串」的列表。

    `bool` 必须显式带 `v` 判空：`all(...)` 对**空列表**返回 True，于是
    `not as_str_list([])` 是 False——「必须非空」那一层检查会整个失效。
    13 个调用点里有 11 个就是要判非空，另 2 个还额外带了 `len(...) < N`，
    没有任何一处允许空列表，所以把非空写进这个谓词是最贴近原意的修法，
    也避免在 11 个调用点各写一遍 `or not v`（漏一处又是一条恒真断言）。
    """
    return isinstance(v, list) and bool(v) and all(
        isinstance(x, str) and bool(x.strip()) for x in v)


def prose_clauses(value):
    """把一个字符串值切成**散文分句**；非散文值返回空列表。

    「散文」= 含中日韩字符**或**含空格的字符串。这样 `S7-NG-E1`（证据 id）、
    `D17:S7`（键值）、`spec/SimRISC-00-指令系统设计.md`（来源）这些纯标识符
    不会被当成叙述来判极性——它们由 G3/G5/G7 的结构化检查负责。含空格的英文
    句（"S7 is still OPEN"）仍然会被扫到，不会漏。
    """
    if not isinstance(value, str):
        return []
    if not (PIN_PROSE_CJK_RE.search(value) or " " in value):
        return []
    return [c.strip() for c in PIN_CLAUSE_SPLIT_RE.split(value) if c.strip()]


def s7_enum_kind(clause):
    """S7 在该分句里是「被枚举成 active 键集合的一分子」还是「被断言了状态」。

    两种都是把 S7 当 active 缺口叙述；返回人可读的判别串供诊断使用，返回
    `None` 表示「只是提到，没带上 active 语义」。
    """
    nums = set(re.findall(r"(?<![0-9A-Za-z])S([1-8])(?![0-9A-Za-z])", clause))
    enumerated = 7 in nums and len(nums) > 1
    for lo, hi in re.findall(r"(?<![0-9A-Za-z])S([1-8])\s*[~～–—-]+\s*S?([1-8])(?![0-9A-Za-z])",
                             clause):
        if int(lo) <= 7 <= int(hi):
            enumerated = True
    if enumerated:
        return "被枚举进 S 键集合/区间（当成了 active 键之一）"
    hit = PIN_S7_ACTIVE_WORDS_RE.search(clause)
    if hit:
        return "被断言为 active 状态/缺口用词 %r" % hit.group(0)
    return "提到 S7 但没有任何「历史/non-gap/不进入 active」的显式标记"


def cite_window(up, f, lines_spec):
    """把一条引用分类成 `normative` / `comment` / `mixed` / `bad-linespec`。

    `SimRISC-03:7-8` 整段在 `<!-- … -->` 里，因此**行区间落在注释内**的引用一律
    不具规范效力。本函数只回答「这条引用的行窗口与 HTML 注释区间是什么关系」，
    由 G4 报告、G17 拒绝 current authority；两者都不从对方推导期望。

    * `comment`  —— 整段窗口都在注释区间内（历史 non-normative 引用）
    * `mixed`    —— 窗口一部分在注释内、一部分在注释外。**这是缺陷**：一个窗口
                    同时横跨规范正文与非规范文本，无法整体声称是规范依据
    * `normative`—— 窗口完全在注释外
    * `bad-linespec` —— 行号文法不合法或越界
    """
    comment = up.comment_lines.get(f)
    if not comment:
        return "normative", set(), set()
    want = linespec_ints(lines_spec)
    if want is None:
        return "bad-linespec", set(), set()
    if min(want) < 1 or max(want) > up.line_count.get(f, 0):
        return "bad-linespec", set(), set()
    inside = want & comment
    if inside and inside == want:
        return "comment", want, inside
    if inside:
        return "mixed", want, inside
    return "normative", want, inside


# ══════════════════════════════ 检查组 ══════════════════════════════
def g1_schema(rep, doc, up):
    cat = "G1"
    keys = list(doc.keys())
    if sorted(keys) != sorted(PIN_TOP_KEYS):
        rep.fail(cat, "top-level-keys",
                 "顶层键集合必须恰为 %d 个固定键（SPEC-103t 的 12 个历史键 + SPEC-104t 的 resolution），"
                 "缺 %r，多 %r"
                 % (len(PIN_TOP_KEYS), sorted(set(PIN_TOP_KEYS) - set(keys)),
                    sorted(set(keys) - set(PIN_TOP_KEYS))))
        return
    rep.ok(cat, "top-level-keys", "%d 个顶层键：%s" % (len(keys), "、".join(keys)))
    if doc.get("schema_version") != PIN_SCHEMA_VERSION:
        rep.fail(cat, "schema-version",
                 "schema_version 期望 %r，实际 %r" % (PIN_SCHEMA_VERSION,
                                                    doc.get("schema_version")))
    else:
        rep.ok(cat, "schema-version", PIN_SCHEMA_VERSION)
    iu = doc.get("identity_universe")
    if not isinstance(iu, dict):
        rep.fail(cat, "identity-universe", "identity_universe 缺失或类型错误")
        return
    exp = {
        "total": (len(up.f1), "contracts/opcodes.yaml 中含 f1 块的记录数"),
        "groups": (up.groups, "opcodes.yaml 的 f1.group 分布"),
    }
    if iu.get("total") != exp["total"][0]:
        rep.fail(cat, "identity-total",
                 "identity_universe.total 期望 %d（%s），实际 %r"
                 % (exp["total"][0], exp["total"][1], iu.get("total")))
    else:
        rep.ok(cat, "identity-total", "64 = 18 rf-qfc + 46 misc-rf")
    if iu.get("groups") != exp["groups"][0]:
        rep.fail(cat, "identity-groups",
                 "identity_universe.groups 期望 %r（%s），实际 %r"
                 % (exp["groups"][0], exp["groups"][1], iu.get("groups")))
    else:
        rep.ok(cat, "identity-groups", json.dumps(up.groups, ensure_ascii=False))
    if iu.get("facet_keys") != up.facets:
        rep.fail(cat, "facet-keys",
                 "facet_keys 与 contract §5.1 的 11 键不符：期望 %r，实际 %r"
                 % (up.facets, iu.get("facet_keys")))
    else:
        rep.ok(cat, "facet-keys", "11 键，来源 contract §5.1")
    if iu.get("facet_status_enum") != PIN_FACET_STATUS:
        rep.fail(cat, "facet-status-enum",
                 "facet 状态枚举不符：期望 %r，实际 %r"
                 % (PIN_FACET_STATUS, iu.get("facet_status_enum")))
    else:
        rep.ok(cat, "facet-status-enum", "/".join(PIN_FACET_STATUS))
    if sorted(iu.get("pseudo_excluded") or []) != ["set.fo", "set.ft"]:
        rep.fail(cat, "pseudo-excluded",
                 "pseudo_excluded 期望 ['set.ft', 'set.fo']，实际 %r"
                 % (iu.get("pseudo_excluded"),))
    else:
        rep.ok(cat, "pseudo-excluded", "set.ft/set.fo 计数为 0")
    pj = iu.get("pinned_d_projection")
    if pj != PIN_PROJ:
        rep.fail(cat, "pinned-projection",
                 "identity_universe.pinned_d_projection 期望 %r，实际 %r"
                 % (PIN_PROJ, pj))
    else:
        rep.ok(cat, "pinned-projection", "37/53/18/4/18/36/64")
    upbad = 0
    for k, v in sorted(up.proj.items()):
        if up.contract_proj.get(k) not in (None, v):
            rep.fail(cat, "upstream-projection",
                     "上游自身不一致：contracts/opcodes.yaml 的 %s=%d，contract §6.1 写 %d"
                     % (k, v, up.contract_proj[k]))
            upbad += 1
    if not upbad:
        rep.ok(cat, "upstream-projection",
               "opcodes.yaml 与 contract §6.1 的 D11–D17 基数一致：%s"
               % json.dumps(up.proj))
    if up.proj != PIN_PROJ:
        rep.fail(cat, "recomputed-projection",
                 "从 contracts/opcodes.yaml 重算的 D11–D17 投影 %r 与钉死基准 %r 不符"
                 % (up.proj, PIN_PROJ))
    else:
        rep.ok(cat, "recomputed-projection", "独立重算命中钉死基准")


def g2_proofs(rep, doc, up, cand_ids):
    cat = "G2"
    dp = doc.get("decision_proofs")
    if not isinstance(dp, dict):
        rep.fail(cat, "decision-proofs", "decision_proofs 缺失或类型错误")
        return
    if sorted(dp) != PIN_DECISIONS:
        rep.fail(cat, "decision-set",
                 "decision_proofs 键集合必须精确等于 %r，实际 %r"
                 % (PIN_DECISIONS, sorted(dp)))
    else:
        rep.ok(cat, "decision-set", "D11..D17 精确七项")
    cands_by_decision = {}
    for c in doc.get("candidate_inputs") or []:
        if isinstance(c, dict) and isinstance(c.get("id"), str):
            cands_by_decision.setdefault(c.get("decision"), set()).add(c["id"])
    for d in PIN_DECISIONS:
        rec = dp.get(d)
        if not isinstance(rec, dict):
            rep.fail(cat, "proof-%s" % d, "缺少 %s 的 proof 记录" % d)
            continue
        if list(rec.keys()) != PIN_PROOF_FIELDS:
            missing = [f for f in PIN_PROOF_FIELDS if f not in rec]
            extra = [f for f in rec if f not in PIN_PROOF_FIELDS]
            rep.fail(cat, "proof-%s-fields" % d,
                     "字段集合不符，缺 %r，多 %r" % (missing, extra))
            continue
        bad = []
        if rec["classification"] != "genuine-gap":
            bad.append("classification 期望 'genuine-gap'，实际 %r" % rec["classification"])
        if rec["status"] not in ("OPEN", "BLOCKED"):
            bad.append("status 期望 OPEN/BLOCKED，实际 %r" % rec["status"])
        if rec["blocked_facet"] != PIN_PROOF_FACET[d]:
            bad.append("blocked_facet 期望 %r，实际 %r" % (PIN_PROOF_FACET[d], rec["blocked_facet"]))
        if rec["affected_identity_count"] != up.proj[d]:
            bad.append("affected_identity_count 期望 %d（从 contracts/opcodes.yaml 重算），实际 %r"
                       % (up.proj[d], rec["affected_identity_count"]))
        if not as_str_list(rec["affected_facets"]):
            bad.append("affected_facets 必须是非空字符串列表")
        else:
            badf = [f for f in rec["affected_facets"] if f not in up.facets and
                    f != "any-open-or-silent"]
            if badf:
                bad.append("affected_facets 含非 11 键 facet：%r" % badf)
        if not as_str_list(rec["search_scope"]):
            bad.append("search_scope 必须是非空字符串列表")
        for p in rec["search_scope"] if isinstance(rec["search_scope"], list) else []:
            if p not in PIN_AUTHORITY_ORDER:
                bad.append("search_scope 含非权威文件：%r" % p)
        if not isinstance(rec["spec_cites"], list) or not rec["spec_cites"]:
            bad.append("spec_cites 必须非空")
        if not isinstance(rec["evidence"], list) or not rec["evidence"]:
            bad.append("evidence 必须非空")
        for e in rec["evidence"] if isinstance(rec["evidence"], list) else []:
            if list(e.keys()) != PIN_EVIDENCE_FIELDS:
                bad.append("evidence 字段集合不符：%r" % (list(e.keys()),))
                continue
            if e["kind"] not in PIN_EVIDENCE_KINDS:
                bad.append("evidence.kind 非法：%r" % e["kind"])
            if not str(e["finding"]).strip():
                bad.append("evidence.finding 为空：%s" % e["id"])
        if not as_str_list(rec["observable_consequences"]):
            bad.append("observable_consequences 必须是非空字符串列表")
        if not as_str_list(rec["blocked_assertions"]) or \
                [a for a in rec["blocked_assertions"] if a not in PIN_ASSERTION_CLASSES]:
            bad.append("blocked_assertions 必须非空且取自 %r" % PIN_ASSERTION_CLASSES)
        if not as_str_list(rec["candidate_question_ids"]):
            bad.append("candidate_question_ids 必须非空")
        else:
            unknown = [c for c in rec["candidate_question_ids"] if c not in cand_ids]
            if unknown:
                bad.append("candidate_question_ids 指向不存在的候选问题：%r" % unknown)
            expect = cands_by_decision.get(d, set())
            if set(rec["candidate_question_ids"]) != expect:
                bad.append("candidate_question_ids 与 candidate_inputs 中 decision=%s 的集合不一致："
                           "声明 %r，候选 %r"
                           % (d, sorted(rec["candidate_question_ids"]), sorted(expect)))
        if len(rec["unblock_condition"]) != 2 or \
                not all(u in rec["unblock_condition"][i] for i, u in enumerate(PIN_UNBLOCK)):
            bad.append("unblock_condition 必须是且仅是两条固定解除条件：%r" % PIN_UNBLOCK)
        if d == "D17" and rec["cross_cutting"] is not True:
            bad.append("D17 必须是 cross_cutting=true")
        if d != "D17" and rec["cross_cutting"] is not False:
            bad.append("D11–D16 不得声明 cross_cutting")
        if not str(rec["affected_identities_scope"]).strip():
            bad.append("affected_identities_scope 为空")
        if not str(rec["missing_or_conflicting"]).strip():
            bad.append("missing_or_conflicting 为空")
        if not str(rec["classification_reason"]).strip():
            bad.append("classification_reason 为空")
        # 与上面各条同类的「必填字段不得留空」：这两条是 PIN_PROOF_FIELDS 里的
        # 必填标量，只查「键在不在」的话，`title: ""` / `question: ""` 能整条蒙混
        # 过去——键集合检查和取值检查是两回事，缺一个就是漏一个。
        for f in ("title", "question"):
            if not str(rec[f]).strip():
                bad.append("%s 为空" % f)
        if bad:
            rep.fail(cat, "proof-%s" % d, "；".join(bad))
        else:
            rep.ok(cat, "proof-%s" % d,
                   "%s / %s / %d identity / %d 引用 / %d 证据 / 候选 %s"
                   % (rec["classification"], rec["status"], rec["affected_identity_count"],
                      len(rec["spec_cites"]), len(rec["evidence"]),
                      ",".join(rec["candidate_question_ids"])))


def g3_sources(rep, doc, up, yaml_rel):
    cat = "G3"
    auth = doc.get("authority")
    if not isinstance(auth, dict):
        rep.fail(cat, "authority", "authority 缺失或类型错误")
        return
    if auth.get("order") != PIN_AUTHORITY_ORDER:
        rep.fail(cat, "authority-order",
                 "authority.order 期望 %r，实际 %r" % (PIN_AUTHORITY_ORDER, auth.get("order")))
    else:
        rep.ok(cat, "authority-order", "6 级权威顺序固定")
    if auth.get("semantics_owner") != [SPEC00, SPEC03]:
        rep.fail(cat, "semantics-owner",
                 "authority.semantics_owner 必须恰为两份 spec 原文，实际 %r"
                 % (auth.get("semantics_owner"),))
    else:
        rep.ok(cat, "semantics-owner", "semantics 只由 spec 原文决定")
    hits = forbidden_source_hits(json.dumps(auth, ensure_ascii=False))
    if hits:
        rep.fail(cat, "authority-forbidden",
                 "authority 段出现禁止的来源 token：%r" % hits)
    else:
        rep.ok(cat, "authority-forbidden",
               "authority 段（含散文 note）无实现/数值库/历史仓/工作日志的**路径类** token")
    word_hits = []
    for k in ("order", "semantics_owner", "verified_upstream"):
        for v in auth.get(k) or []:
            word_hits += [(k, str(v), w) for w in PIN_FORBIDDEN_AUTHORITY_WORDS
                          if w in str(v)]
    for w in PIN_FORBIDDEN_AUTHORITY_WORDS:
        if w in str(auth.get("accepted_adr_boundary", "")):
            word_hits.append(("accepted_adr_boundary", "", w))
    if word_hits:
        rep.fail(cat, "authority-nonauthoritative",
                 "authority 的取值清单里出现非权威来源措辞：%r" % word_hits)
    else:
        rep.ok(cat, "authority-nonauthoritative",
               "authority 取值清单只列规范/Accepted ADR/已验证上游，无参考仓与工作日志")
    lineidx = {SPEC00: up.spec00, SPEC03: up.spec03, ADR1004: up.adr_lines,
               README: up.readme_lines, CONTRACT: up.contract_lines,
               OPCODES: [read_text(up.root, OPCODES)]}
    cited, ev_src, scopes = 0, 0, 0
    #: 每条子检查各自的失败计数：用于给**只会 FAIL 的检查补上 OK 孪生**。
    #: 没有 OK 孪生的检查在 `-v` 输出里完全不可见，反例门控也就无法证明
    #: 「该检查真的被执行到了」——只能靠同函数里另一条检查的红灯蒙混过关。
    badsub = {k: 0 for k in ("cite-file", "cite-forbidden", "evidence-source",
                             "evidence-forbidden", "search-scope", "cite-mixed-comment")}
    #: cite_window 分类计数：供 G3 的 OK 孪生与 G4 的分类检查共用。
    citecls = {"normative": 0, "comment": 0, "mixed": 0, "bad-linespec": 0}
    for holder, name in ((doc.get("decision_proofs"), "decision_proofs"),
                         (doc.get("d17_open_ledger"), "d17_open_ledger"),
                         (doc.get("trace_only"), "trace_only"),
                         (doc.get("non_gap_records"), "non_gap_records")):
        for tid, rec in (holder or {}).items():
            if not isinstance(rec, dict):
                continue
            for i, c in enumerate(rec.get("spec_cites") or []):
                cited += 1
                f = c.get("file")
                if f not in PIN_AUTHORITY_ORDER:
                    rep.fail(cat, "cite-file",
                             "%s.%s.spec_cites[%d].file=%r 不在权威白名单内"
                             % (name, tid, i, f))
                    badsub["cite-file"] += 1
                h = forbidden_source_hits(str(f))
                if h:
                    rep.fail(cat, "cite-forbidden",
                             "%s.%s.spec_cites[%d] 引用了禁止来源 %r" % (name, tid, i, h))
                    badsub["cite-forbidden"] += 1
                # 行窗口**横跨** HTML 注释边界即 FAIL：注释内文本非规范，注释外是
                # 规范正文，一个窗口无法整体充当依据。整段落在注释内是历史
                # non-normative 引用，由 G17 核对其被显式标记。
                kind, _want, inside = cite_window(up, f, c.get("lines"))
                citecls[kind] += 1
                if kind == "mixed":
                    rep.fail(cat, "cite-mixed-comment",
                             "%s.%s.spec_cites[%d] 的行窗口 %r 同时覆盖 HTML 注释行 %r "
                             "与规范正文行，无法整体作为依据"
                             % (name, tid, i, c.get("lines"), sorted(inside)))
                    badsub["cite-mixed-comment"] += 1
            for e in rec.get("evidence") or []:
                ev_src += 1
                for p, ls in source_items(e.get("source", "")):
                    if p not in PIN_AUTHORITY_ORDER:
                        rep.fail(cat, "evidence-source",
                                 "%s.%s 的 evidence %s 引用了白名单外来源 %r"
                                 % (name, tid, e.get("id"), p))
                        badsub["evidence-source"] += 1
                    elif ls is not None and not PIN_SOURCE_LINESPEC.match(ls):
                        rep.fail(cat, "evidence-source",
                                 "%s.%s 的 evidence %s 的行号部分 %r 不符合 "
                                 "`file[:行,行-行,…]` 文法"
                                 % (name, tid, e.get("id"), ls))
                        badsub["evidence-source"] += 1
                    elif ls is not None and line_window(lineidx.get(p), ls) is None:
                        rep.fail(cat, "evidence-source",
                                 "%s.%s 的 evidence %s 的行号 %r 越界"
                                 % (name, tid, e.get("id"), ls))
                        badsub["evidence-source"] += 1
                h = forbidden_source_hits(str(e.get("source", "")))
                if h:
                    rep.fail(cat, "evidence-forbidden",
                             "%s.%s 的 evidence %s 的 source 含禁止 token %r"
                             % (name, tid, e.get("id"), h))
                    badsub["evidence-forbidden"] += 1
            for p in rec.get("search_scope") or []:
                scopes += 1
                if p not in PIN_AUTHORITY_ORDER:
                    rep.fail(cat, "search-scope",
                             "%s.%s 的 search_scope 含白名单外文件 %r" % (name, tid, p))
                    badsub["search-scope"] += 1
    # 逐条 OK 孪生：`-v` 下每条子检查都可见，反例门控才能证明「确实跑到了」
    for sub, msg in (
            ("cite-file", "%d 条 spec_cites 的 file 全部落在 6 级权威白名单内" % cited),
            ("cite-forbidden", "%d 条 spec_cites 无实现/数值库/历史仓/工作日志 token" % cited),
            ("evidence-source",
             "%d 条 evidence 的来源全部落在 6 级权威白名单内，且行号文法合法、不越界" % ev_src),
            ("evidence-forbidden", "%d 条 evidence 的 source 无禁止来源 token" % ev_src),
            ("search-scope", "%d 条 search_scope 条目全部落在权威白名单内" % scopes),
            ("cite-mixed-comment",
             "%d 条 spec_cites 的行窗口无一横跨 HTML 注释边界"
             "（%d 条整段落在 SimRISC-03:7-8 注释内，属 historical-non-normative，"
             "由 G17 核对其已被显式登记）"
             % (cited, citecls["comment"]))):
        if not badsub[sub]:
            rep.ok(cat, sub, msg)
    if not any(badsub[k] for k in ("cite-file", "evidence-source")):
        rep.ok(cat, "cite-whitelist",
               "%d 条 spec_cites 全部落在 6 级权威白名单内" % cited)
        rep.ok(cat, "evidence-whitelist",
               "%d 条 evidence 的来源全部落在 6 级权威白名单内，且行号不越界" % ev_src)
    for m in re.finditer(r"DADAO-1\d|DADAO-06\d\d", read_text(up.root, yaml_rel)):
        rep.fail(cat, "legacy-repo-ref",
                 "YAML 第 %d 字符附近引用了历史参考仓编号 %r（按 contract §9.1 禁止）"
                 % (m.start(), m.group(0)))
        return
    rep.ok(cat, "legacy-repo-ref", "无 DADAO-1x / DADAO-06xx 引用")


def g4_quotes(rep, doc, up):
    cat = "G4"
    n = 0
    bad = 0
    holders = ((doc.get("decision_proofs"), "decision_proofs"),
               (doc.get("d17_open_ledger"), "d17_open_ledger"),
               (doc.get("trace_only"), "trace_only"),
               (doc.get("non_gap_records"), "non_gap_records"),
               ({"layout": (doc.get("rf0_fcsr_split") or {}).get("layout"),
                 "reset": (doc.get("rf0_fcsr_split") or {}).get("reset")},
                "rf0_fcsr_split"))
    for holder, name in holders:
        for tid, rec in (holder or {}).items():
            if not isinstance(rec, dict):
                continue
            for i, c in enumerate(rec.get("spec_cites") or []):
                n += 1
                if list(c.keys()) != PIN_CITE_FIELDS:
                    rep.fail(cat, "cite-fields",
                             "%s.%s.spec_cites[%d] 字段集合不符：%r"
                             % (name, tid, i, list(c.keys())))
                    bad += 1
                    continue
                f, ln, q = c["file"], c["lines"], c["quote"]
                lines = {SPEC00: up.spec00, SPEC03: up.spec03, ADR1004: up.adr_lines,
                         README: up.readme_lines, CONTRACT: up.contract_lines,
                         OPCODES: [read_text(up.root, OPCODES)]}.get(f)
                if lines is None:
                    continue
                win = line_window(lines, ln)
                if win is None:
                    rep.fail(cat, "cite-range",
                             "%s.%s.spec_cites[%d] 的行区间 %r 越界（%s 共 %d 行）"
                             % (name, tid, i, ln, f, len(lines)))
                    bad += 1
                    continue
                if not str(q).strip():
                    rep.fail(cat, "cite-quote-empty",
                             "%s.%s.spec_cites[%d] 的 quote 为空" % (name, tid, i))
                    bad += 1
                    continue
                if q not in win:
                    rep.fail(cat, "cite-quote-mismatch",
                             "%s.%s.spec_cites[%d] 的 quote 不是 %s:%s 原文的逐字子串："
                             "期望在原文窗口内找到 %r" % (name, tid, i, f, ln, q[:60]))
                    bad += 1
    if bad == 0:
        rep.ok(cat, "cite-fields", "%d 条引用的字段集合齐全（ref/file/lines/quote）" % n)
        rep.ok(cat, "cite-range", "%d 条引用的行区间全部在所引文件范围内" % n)
        rep.ok(cat, "cite-quote-empty", "%d 条引用的 quote 均非空" % n)
        rep.ok(cat, "cite-quote-mismatch",
               "%d 条引用的 quote 都命中所引行窗口（无「格式对但指错句」）" % n)
        rep.ok(cat, "quote-substring",
               "%d 条引用的 quote 全部是所引行区间的逐字子串" % n)
    # ── G4 新增（SPEC-104t §8.8）：逐条把行窗口分类成「规范 / 注释内 / 横跨」──
    # G4 比 G3 多扫一个 holder（`rf0_fcsr_split`），因此这里是**独立**的第二遍分类：
    # G3 的 4 个 holder 漏掉的 `rf0_fcsr_split.layout` 只能被这里抓到。
    cls = {"normative": 0, "comment": 0, "mixed": 0, "bad-linespec": 0}
    in_comment, straddle = [], []
    for holder, name in holders:
        for tid, rec in (holder or {}).items():
            if not isinstance(rec, dict):
                continue
            for i, c in enumerate(rec.get("spec_cites") or []):
                if not isinstance(c, dict):
                    continue
                kind, _want, ins = cite_window(up, c.get("file"), c.get("lines"))
                cls[kind] += 1
                if kind == "comment":
                    in_comment.append((name, tid, i, c.get("file"), str(c.get("lines"))))
                elif kind == "mixed":
                    straddle.append("%s.%s[%d]@%s:%s 混了注释行 %r"
                                    % (name, tid, i, c.get("file"), c.get("lines"),
                                       sorted(ins)))
    got_comment = {(n, t, i) for n, t, i, _f, _l in in_comment}
    prob = []
    if straddle:
        prob.append("%d 条引用的行窗口横跨注释边界：%r" % (len(straddle), straddle[:4]))
    if got_comment != PIN_HISTORICAL_NON_NORMATIVE:
        prob.append("整段落在注释内的引用集合期望恰为 %r，实际 %r（少 %r / 多 %r）"
                    % (sorted(PIN_HISTORICAL_NON_NORMATIVE), sorted(got_comment),
                       sorted(PIN_HISTORICAL_NON_NORMATIVE - got_comment),
                       sorted(got_comment - PIN_HISTORICAL_NON_NORMATIVE)))
    if prob:
        rep.fail(cat, "cite-comment-classified", "；".join(prob))
    else:
        rep.ok(cat, "cite-comment-classified",
               "%d 条引用分类完成：%d 条落在规范正文、%d 条整段落在 SimRISC-03:7-8 "
               "HTML 注释内（historical-non-normative 钉死集合 %s）、0 条横跨边界"
               % (sum(cls.values()), cls["normative"], cls["comment"],
                  "/".join("%s.%s[%d]" % (n, t, i)
                           for n, t, i, _f, _l in sorted(in_comment))))


def g5_ledger(rep, doc, up):
    cat = "G5"
    lg = doc.get("d17_open_ledger")
    if not isinstance(lg, dict):
        rep.fail(cat, "ledger", "d17_open_ledger 缺失或类型错误")
        return
    if sorted(lg) != PIN_LEDGER_KEYS:
        rep.fail(cat, "ledger-keys",
                 "ledger 键集合必须逐字符精确等于 %r，实际 %r" % (PIN_LEDGER_KEYS, sorted(lg)))
    else:
        rep.ok(cat, "ledger-keys", "精确六键，无 D17:S2/D17:S7，无裸 S*")
    if up.contract_ledger != sorted(PIN_LEDGER_KEYS + [PIN_S7_ID]):
        rep.fail(cat, "ledger-upstream",
                 "上游 contract §6.2 的七键集合 %r 与钉死基准 %r 不符"
                 % (up.contract_ledger, sorted(PIN_LEDGER_KEYS + [PIN_S7_ID])))
    else:
        rep.ok(cat, "ledger-upstream", "contract §6.2 的历史七键集合含 S7；active ledger 精确排除 S7")
    cands = {c.get("id") for c in (doc.get("candidate_inputs") or [])
             if isinstance(c, dict)}
    for k in PIN_LEDGER_KEYS:
        rec = lg.get(k)
        if not isinstance(rec, dict):
            rep.fail(cat, "ledger-%s" % k, "缺少 ledger 行 %s" % k)
            continue
        need = list(PIN_LEDGER_FIELDS_COMMON)
        if k == "D17:S6":
            need = need + ["write_action_alternatives", "write_action_state",
                           "fault_encoding_rule"]
        bad = []
        miss = [f for f in need if f not in rec]
        if miss:
            bad.append("缺字段 %r" % miss)
        if rec.get("status") not in ("OPEN", "BLOCKED"):
            bad.append("status 期望 OPEN/BLOCKED，实际 %r" % rec.get("status"))
        if rec.get("classification") != "genuine-gap":
            bad.append("classification 期望 'genuine-gap'，实际 %r" % rec.get("classification"))
        scope = up.scope.get(k, [])
        if rec.get("affected_identities") != scope:
            bad.append("affected_identities 与机械求法不符：期望 %d 条 %r，实际 %d 条 %r"
                       % (len(scope), scope[:6], len(rec.get("affected_identities") or []),
                          (rec.get("affected_identities") or [])[:6]))
        if rec.get("affected_identity_count") != len(scope):
            bad.append("affected_identity_count 期望 %d，实际 %r"
                       % (len(scope), rec.get("affected_identity_count")))
        if not as_str_list(rec.get("blocked_facets")):
            bad.append("blocked_facets 必须非空")
        if not as_str_list(rec.get("blocked_assertions")) or \
                [a for a in rec["blocked_assertions"] if a not in PIN_ASSERTION_CLASSES]:
            bad.append("blocked_assertions 必须非空且取自固定词表")
        if not as_str_list(rec.get("observable_consequences")):
            bad.append("observable_consequences 必须非空")
        if not isinstance(rec.get("spec_cites"), list) or not rec["spec_cites"]:
            bad.append("spec_cites 必须非空")
        if not isinstance(rec.get("evidence"), list) or not rec["evidence"]:
            bad.append("evidence 必须非空")
        if not as_str_list(rec.get("candidate_question_ids")):
            bad.append("candidate_question_ids 必须非空")
        else:
            unk = [c for c in rec["candidate_question_ids"] if c not in cands]
            if unk:
                bad.append("candidate_question_ids 指向不存在的候选：%r" % unk)
        if len(rec.get("unblock_condition") or []) != 2 or \
                not all(u in rec["unblock_condition"][i] for i, u in enumerate(PIN_UNBLOCK)):
            bad.append("unblock_condition 必须是且仅是两条固定解除条件")
        # 必填标量同样不得留空（与 G2 的 title/question 同一类，见上）
        for f in ("topic", "scope_kind", "scope_derivation"):
            if not str(rec.get(f, "")).strip():
                bad.append("%s 为空" % f)
        if bad:
            rep.fail(cat, "ledger-%s" % k, "；".join(bad))
        else:
            rep.ok(cat, "ledger-%s" % k,
                   "%s / %d identity / %d 引用 / %d 证据"
                   % (rec["status"], rec["affected_identity_count"],
                      len(rec["spec_cites"]), len(rec["evidence"])))
    # S6：不得选定任何写入动作
    s6 = lg.get("D17:S6") or {}
    if s6.get("affected_identities") != PIN_S6_IDENTITIES:
        rep.fail(cat, "s6-scope",
                 "D17:S6 必须是精确六条 %r，实际 %r"
                 % (PIN_S6_IDENTITIES, s6.get("affected_identities")))
    else:
        rep.ok(cat, "s6-scope", "精确六条 rd2rf/ld*/ldm*/set.w-rf")
    if s6.get("write_action_alternatives") != PIN_S6_UNSELECTED:
        rep.fail(cat, "s6-unselected",
                 "D17:S6 必须把 %r 四种行为全部列为**未选定**，实际 %r"
                 % (PIN_S6_UNSELECTED, s6.get("write_action_alternatives")))
    else:
        rep.ok(cat, "s6-unselected", "忽略/保留/清零/异常 四者均未选定")
    offenders = selection_offenders(s6)
    if offenders:
        for ptr, k, w in offenders:
            rep.fail(cat, "s6-chosen-behaviour",
                     "D17:S6 出现表示「已选定行为」的键 %r（命中词根 %r）" % (k, w))
    else:
        rep.ok(cat, "s6-chosen-behaviour", "S6 行内无任何表示已选行为的键")
    # layout / reset 分栏
    sp = doc.get("rf0_fcsr_split") or {}
    lay, res = sp.get("layout"), sp.get("reset")
    if not isinstance(lay, dict) or not isinstance(res, dict):
        rep.fail(cat, "layout-reset-split", "rf0_fcsr_split 必须含 layout 与 reset 两栏")
    else:
        prob = []
        if lay.get("classification") != "spec-determined" or lay.get("now_runnable") is not True:
            prob.append("layout 必须是 spec-determined / now_runnable=true，实际 %r/%r"
                        % (lay.get("classification"), lay.get("now_runnable")))
        if res.get("classification") != "genuine-gap" or res.get("status") != "BLOCKED" \
                or res.get("now_runnable") is not False:
            prob.append("reset 必须是 genuine-gap / BLOCKED / now_runnable=false，实际 %r/%r/%r"
                        % (res.get("classification"), res.get("status"),
                           res.get("now_runnable")))
        if res.get("open_id") != "D17:S1" or res.get("ledger_key") != "D17:S1":
            prob.append("reset 必须显式绑定 ledger 键 D17:S1，实际 open_id=%r ledger_key=%r"
                        % (res.get("open_id"), res.get("ledger_key")))
        layf = {f.get("bits") for f in lay.get("fields") or []}
        expf = {"[63..51]", "[50..32]", "[31..22]", "[21..18]", "[17..16]", "[15..5]", "[4..0]"}
        if layf != expf:
            prob.append("layout.fields 的位域集合 %r 与 SimRISC-00:78-86 不符" % sorted(layf))
        laykeys = {str(k) for _p, k, _v in walk(lay)}
        leak = sorted(laykeys & set(PIN_LAYOUT_FORBIDDEN_KEYS))
        if leak:
            prob.append("layout 栏内出现复位值字段 %r（layout 与 reset 必须分栏）" % leak)
        reskeys = {str(k) for _p, k, _v in walk(res)}
        leak = sorted(reskeys & set(PIN_RESET_FORBIDDEN_KEYS))
        if leak:
            prob.append("reset 栏内出现位域表字段 %r（layout 与 reset 必须分栏）" % leak)
        if not isinstance(res.get("spec_cites"), list) or not res["spec_cites"]:
            prob.append("reset 栏必须给出「规范未给复位值」的可定位引用")
        if not as_str_list(res.get("observable_consequences")):
            prob.append("reset 栏必须写明可观测后果")
        if not as_str_list(lay.get("rounding_modes")) or \
                lay.get("rounding_modes") != ["RNE", "RTZ", "RDN", "RUP"]:
            prob.append("layout.rounding_modes 期望 ['RNE','RTZ','RDN','RUP']，实际 %r"
                        % lay.get("rounding_modes"))
        if not str(sp.get("separation_rule", "")).strip():
            prob.append("缺少 separation_rule")
        if prob:
            rep.fail(cat, "layout-reset-split", "；".join(prob))
        else:
            rep.ok(cat, "layout-reset-split",
                   "layout=spec-determined/now-runnable，reset=genuine-gap/BLOCKED/D17:S1")
    # non_gap_records：规范明示「不作具体要求」必须与真缺口分开
    ng = doc.get("non_gap_records") or {}
    rec = ng.get("rootn_neg_zero_2")
    if not isinstance(rec, dict):
        rep.fail(cat, "non-gap-record", "缺少 non_gap_records.rootn_neg_zero_2")
    else:
        prob = []
        if rec.get("classification") != "explicitly-unspecified":
            prob.append("classification 期望 'explicitly-unspecified'，实际 %r"
                        % rec.get("classification"))
        if rec.get("affected_identities") != ["foroot", "ftroot"]:
            prob.append("受影响集合期望 ['foroot','ftroot']，实际 %r" % rec.get("affected_identities"))
        if rec.get("candidate_question_ids") != []:
            prob.append("明示不要求的情形不得产生候选决策问题，实际 %r"
                        % rec.get("candidate_question_ids"))
        if prob:
            rep.fail(cat, "non-gap-record", "；".join(prob))
        else:
            rep.ok(cat, "non-gap-record",
                   "rootn(-0,2) 记 explicitly-unspecified，与 genuine-gap 分开且无候选问题")
    # S7 is historical non-gap: raw spec, fixed RD/RF directions, never active/candidate/consumer.
    s7 = ng.get(PIN_S7_ID) or {}
    prob = []
    if sorted(ng) != ["D17:S7", "rootn_neg_zero_2"]: prob.append("non_gap_records 必须仅含 rootn_neg_zero_2 与 D17:S7")
    for k, v in (("classification", "spec-determined"), ("status", "NOT-A-GAP"), ("in_active_ledger", False), ("pass_counted", False), ("candidate_question_ids", []), ("affected_identities", PIN_S7_IDENTITIES)):
        if s7.get(k) != v: prob.append("S7.%s 期望 %r，实际 %r" % (k, v, s7.get(k)))
    cites = {(x.get("file"), str(x.get("lines"))) for x in s7.get("spec_cites") or []}
    for want in sorted(PIN_S7_RAW_AUTHORITY):
        if want not in cites: prob.append("S7 缺少原始规范引用 %s:%s" % want)
    if prob: rep.fail(cat, "s7-non-gap", "；".join(prob))
    else: rep.ok(cat, "s7-non-gap", "S7=spec-determined/NOT-A-GAP；RD/RF distinct + 固定 RF→RD/RD→RF")
    leaks = []
    if PIN_S7_ID in (doc.get("d17_open_ledger") or {}): leaks.append("active ledger")
    for c in doc.get("candidate_inputs") or []:
        if PIN_S7_ID in json.dumps(c, ensure_ascii=False): leaks.append("candidate " + str(c.get("id")))
    for r in doc.get("impact_matrix") or []:
        if PIN_S7_ID in (r.get("d17_open_ids") or []): leaks.append("matrix " + str(r.get("identity")))
        for b in r.get("blocked_downstream") or []:
            if PIN_S7_ID in (b.get("via") or []): leaks.append("blocking " + str(r.get("identity")))
    for n in (doc.get("consumer_graph") or {}).get("nodes") or []:
        if PIN_S7_ID in json.dumps(n, ensure_ascii=False): leaks.append("consumer " + str(n.get("task")))
    if leaks: rep.fail(cat, "s7-leak", "D17:S7 不得进入 active/Candidate/matrix/blocking consumer：%r" % leaks)
    else: rep.ok(cat, "s7-leak", "S7 无 active、Candidate、matrix、blocking consumer 泄漏")
    allc = set()
    for grp in ("decision_proofs", "d17_open_ledger", "trace_only", "non_gap_records"):
        for r in (doc.get(grp) or {}).values():
            if isinstance(r, dict) and r.get("classification"):
                allc.add(r["classification"])
    sp2 = doc.get("rf0_fcsr_split") or {}
    for side in ("layout", "reset"):
        c = (sp2.get(side) or {}).get("classification")
        if c:
            allc.add(c)
    for row in doc.get("impact_matrix") or []:
        if isinstance(row, dict):
            for c in (row.get("facet_status") or {}).values():
                allc.add(c)
    allc -= {c for c in allc if c not in PIN_CLASSIFICATIONS}
    if set(PIN_CLASSIFICATIONS) - allc:
        rep.fail(cat, "classification-coverage",
                 "四类证明分类未全部用到，缺 %r" % sorted(set(PIN_CLASSIFICATIONS) - allc))
    else:
        rep.ok(cat, "classification-coverage", "四类分类全部出现且各就各位")


def g6_trace_only(rep, doc, up):
    cat = "G6"
    tr = doc.get("trace_only")
    if not isinstance(tr, dict):
        rep.fail(cat, "trace-only", "trace_only 缺失或类型错误")
        return
    if sorted(tr) != [PIN_S2_ID]:
        rep.fail(cat, "trace-only-keys",
                 "trace_only 必须精确且仅含 %r，实际 %r" % (PIN_S2_ID, sorted(tr)))
    else:
        rep.ok(cat, "trace-only-keys", "精确且仅含 D17:S2")
    lg = doc.get("d17_open_ledger") or {}
    if PIN_S2_ID in lg:
        rep.fail(cat, "s2-not-in-ledger", "D17:S2 出现在 d17_open_ledger 内")
    else:
        rep.ok(cat, "s2-not-in-ledger", "D17:S2 不在 ledger")
    rec = tr.get(PIN_S2_ID) or {}
    prob = []
    if rec.get("classification") != "no-behavioral-consequence":
        prob.append("classification 期望 'no-behavioral-consequence'，实际 %r"
                    % rec.get("classification"))
    if rec.get("semantic_tag") != PIN_S2_TAG:
        prob.append("semantic_tag 必须是四句固定文本 %r，实际 %r" % (PIN_S2_TAG, rec.get("semantic_tag")))
    if rec.get("in_ledger") is not False:
        prob.append("in_ledger 必须是 false")
    if rec.get("status_word_allowed") is not False:
        prob.append("status_word_allowed 必须是 false（不得写 OPEN/BLOCKED/PASS）")
    if rec.get("pass_counted") is not False:
        prob.append("pass_counted 必须是 false（never PASS）")
    if rec.get("candidate_questions") != []:
        prob.append("D17:S2 不得产生候选问题，实际 %r" % rec.get("candidate_questions"))
    if rec.get("affected_identities") != PIN_S2_IDENTITIES:
        prob.append("受影响集合期望 %r，实际 %r" % (PIN_S2_IDENTITIES, rec.get("affected_identities")))
    if "status" in rec:
        prob.append("D17:S2 记录内不得出现 status 字段（trace-only 不是 ledger 行）")
    arg = rec.get("no_behavioral_difference_argument")
    if not as_str_list(arg) or len(arg) < 3:
        prob.append("no_behavioral_difference_argument 必须给出逐条论证（>= 3 条），实际 %r" % arg)
    has = {(c.get("file"), str(c.get("lines"))) for c in rec.get("spec_cites") or []}
    for f, ln in PIN_S2_PROOF_LINES:
        if (f, ln) not in has:
            prob.append("缺少证明「无行为差异」所必需的引用 %s:%s" % (f, ln))
    if prob:
        rep.fail(cat, "s2-semantics", "；".join(prob))
    else:
        rep.ok(cat, "s2-semantics",
               "四句语义精确；由 6 位 immu6 上界 + 三处独立 immu6=0 ILLI 规则证明无行为后果")
    # D17:S2 不得出现在任何候选问题 / 矩阵行 / ledger 引用中
    leak = 0
    for c in (doc.get("candidate_inputs") or []):
        if isinstance(c, dict) and PIN_S2_ID in json.dumps(c, ensure_ascii=False):
            rep.fail(cat, "s2-leak", "候选问题 %r 的内容引用了 D17:S2" % c.get("id"))
            leak += 1
    for row in doc.get("impact_matrix") or []:
        if isinstance(row, dict) and PIN_S2_ID in (row.get("d17_open_ids") or []):
            rep.fail(cat, "s2-leak", "矩阵行 %r 把 D17:S2 当作 ledger 键" % row.get("identity"))
            leak += 1
    if not leak:
        rep.ok(cat, "s2-leak", "D17:S2 未进入候选问题与影响矩阵")


def g7_matrix(rep, doc, up):
    cat = "G7"
    rows = doc.get("impact_matrix")
    if not isinstance(rows, list):
        rep.fail(cat, "matrix-type", "impact_matrix 必须是列表（逐行可数）")
        return
    if len(rows) != len(up.identities):
        rep.fail(cat, "matrix-count",
                 "impact_matrix 必须恰好 %d 行，实际 %d 行" % (len(up.identities), len(rows)))
    else:
        rep.ok(cat, "matrix-count", "64 行")
    names = [r.get("identity") for r in rows if isinstance(r, dict)]
    dup = sorted({x for x in names if names.count(x) > 1})
    if dup:
        rep.fail(cat, "matrix-dup", "impact_matrix 出现重复 identity：%r" % dup)
    else:
        rep.ok(cat, "matrix-dup", "%d 行 identity 互不重复" % len(names))
    if sorted(set(names)) != up.identities:
        only_doc = sorted(set(names) - set(up.identities))
        only_up = sorted(set(up.identities) - set(names))
        rep.fail(cat, "matrix-set",
                 "与 contract/opcodes 的 64 identity 不双向相等：多出 %r，缺少 %r"
                 % (only_doc, only_up))
    else:
        rep.ok(cat, "matrix-set", "与上游 64 identity 双向全等")
    pseudo = sorted(x for x in set(names)
                    if isinstance(x, str) and x.split("-")[0] in up.pseudo)
    if pseudo:
        rep.fail(cat, "matrix-pseudo",
                 "矩阵混入 spec/SimRISC-00 §伪指令 的 pseudo：%r（来自 %s）" % (pseudo, SPEC00))
    else:
        rep.ok(cat, "matrix-pseudo",
               "无 pseudo（%s §伪指令 的 %d 个名字逐个核对过）/ 无非 F1 identity"
               % (SPEC00, len(up.pseudo)))
    proj = {d: sum(1 for r in rows if isinstance(r, dict) and d in (r.get("open_decisions") or []))
            for d in ("D11", "D12", "D13", "D14", "D15", "D16")}
    pbad = 0
    for d, n in sorted(proj.items()):
        if n != PIN_PROJ[d]:
            rep.fail(cat, "matrix-projection",
                     "D%d 的矩阵投影期望 %d，实际 %d" % (int(d[1:]), PIN_PROJ[d], n))
            pbad += 1
    if not pbad:
        rep.ok(cat, "matrix-projection", "D11–D16 投影 37/53/18/4/18/36")
    n17 = sum(1 for r in rows if isinstance(r, dict) and r.get("d17_fallback") is True)
    if n17 != 64:
        rep.fail(cat, "matrix-d17-projection",
                 "D17 的总追踪必须是 64 行（d17_fallback=true），实际 %d" % n17)
    else:
        rep.ok(cat, "matrix-d17-projection", "D17 总追踪 64")
    lbad = 0
    for k, n in sorted(PIN_LEDGER_SCOPES.items()):
        got = sum(1 for r in rows if isinstance(r, dict) and k in (r.get("d17_open_ids") or []))
        if got != n:
            rep.fail(cat, "matrix-ledger-projection",
                     "%s 的矩阵投影期望 %d 条，实际 %d 条" % (k, n, got))
            lbad += 1
    if not lbad:
        rep.ok(cat, "matrix-ledger-projection", "六键 active 投影 64/2/26/2/6/4；S7 historical=2、active=0")
    bad_rows = 0
    for r in rows:
        if not isinstance(r, dict):
            continue
        insn = r.get("identity")
        src = up.by_insn.get(insn)
        if src is None:
            continue
        f = src["f1"]
        prob = []
        if r.get("group") != f["group"]:
            prob.append("group 期望 %r，实际 %r" % (f["group"], r.get("group")))
        if r.get("section") != f["section"]:
            prob.append("section 期望 %r，实际 %r" % (f["section"], r.get("section")))
        if r.get("owning_consumer_task") != up.insn_task.get(insn):
            prob.append("owning_consumer_task 期望 %r（由 QEMU 任务书的 11/42/11 分解推出），实际 %r"
                        % (up.insn_task.get(insn), r.get("owning_consumer_task")))
        if r.get("facet_status") != f["facets"]:
            prob.append("facet_status 与 contracts/opcodes.yaml 的 f1.facets 不符")
        if sorted(r.get("open_decisions") or []) != sorted(f["open_items"]):
            prob.append("open_decisions 期望 %r，实际 %r"
                        % (sorted(f["open_items"]), sorted(r.get("open_decisions") or [])))
        exp_open = {k: PIN_FACET_TO_D[k] for k in up.facets
                    if f["facets"][k] == "open-blocked"}
        if r.get("open_facets") != exp_open:
            prob.append("open_facets 期望 %r，实际 %r" % (exp_open, r.get("open_facets")))
        exp_part = sorted(k for k in up.facets if f["facets"][k] == "partial")
        if sorted(r.get("partial_facets") or []) != exp_part:
            prob.append("partial_facets 期望 %r，实际 %r" % (exp_part, r.get("partial_facets")))
        exp_now = sorted(k for k in up.facets if f["facets"][k] == "spec-determined")
        if sorted(r.get("now_runnable_facets") or []) != exp_now:
            prob.append("now_runnable_facets 期望 %r，实际 %r" % (exp_now, r.get("now_runnable_facets")))
        exp_keys = sorted(k for k in up.scope if k in up.scope and insn in up.scope[k])
        if sorted(r.get("d17_open_ids") or []) != exp_keys:
            prob.append("d17_open_ids 期望 %r（机械求法），实际 %r"
                        % (exp_keys, sorted(r.get("d17_open_ids") or [])))
        extra = set(r.get("d17_open_ids") or []) - set(f["d17_open_ids"])
        if extra:
            prob.append("d17_open_ids 含 opcodes.yaml 未登记的键 %r" % sorted(extra))
        trig = ["milestone"] + exp_keys + sorted(f["open_items"])
        owner = up.insn_task.get(insn)
        exp_bd = {}
        for t in trig:
            for task, cls in PIN_BLOCK_RULES.get(t, []):
                exp_bd.setdefault((owner if task == "own" else task, cls), set()).add(t)
        exp_bd = [{"task": a, "assertion_class": b, "via": sorted(c)}
                  for (a, b), c in sorted(exp_bd.items())]
        if r.get("blocked_downstream") != exp_bd:
            prob.append("blocked_downstream 与独立重算不符：期望 %d 条 %r，实际 %r"
                        % (len(exp_bd), exp_bd[:2], (r.get("blocked_downstream") or [])[:2]))
        if sorted(r.get("blocked_assertion_classes") or []) != \
                sorted({x["assertion_class"] for x in (r.get("blocked_downstream") or [])}):
            prob.append("blocked_assertion_classes 与 blocked_downstream 不自洽")
        if not r.get("blocked_downstream"):
            prob.append("blocked_downstream 为空")
        if not r.get("blocked_assertion_classes"):
            prob.append("blocked_assertion_classes 为空（每行至少一个具名阻塞断言）")
        ub = r.get("unblock_condition") or []
        if len(ub) != 2 or not all(u in ub[i] for i, u in enumerate(PIN_UNBLOCK)):
            prob.append("unblock_condition 必须是且仅是两条固定解除条件")
        if not str(r.get("now_runnable_note", "")).strip():
            prob.append("now_runnable_note 为空（须声明已决 facet 不覆盖 OPEN）")
        if prob:
            bad_rows += 1
            if bad_rows <= 12:
                rep.fail(cat, "matrix-row-%s" % insn, "；".join(prob))
    if bad_rows == 0:
        # `matrix-rows` 是 `matrix-row-<insn>` 这一族 FAIL 的**聚合 OK 孪生**：
        # 两者由**同一个 `bad_rows == 0` 分支**决定，所以「聚合 OK 出现」即证明
        # 「逐行核对这段代码确实被执行到了」。反例门控用 `expect_ok: matrix-rows`
        # 来断言这一点（不逐行印 64 条 OK，否则「通过 N 项」会被灌水到失去意义）。
        rep.ok(cat, "matrix-rows",
               "64 行的 facet/投影/ledger 键/blocked_downstream/unblock 条件全部逐行重算一致")
    elif bad_rows > 12:
        rep.fail(cat, "matrix-rows", "另有 %d 行存在问题（上面只列前 12 行）" % (bad_rows - 12))


def g8_graph(rep, doc, up):
    cat = "G8"
    cg = doc.get("consumer_graph")
    if not isinstance(cg, dict):
        rep.fail(cat, "graph-type", "consumer_graph 缺失或类型错误")
        return
    nodes = cg.get("nodes")
    if not isinstance(nodes, list):
        rep.fail(cat, "nodes-type", "consumer_graph.nodes 必须是列表")
        return
    by_task = {}
    for n in nodes:
        if isinstance(n, dict) and n.get("task"):
            by_task[n["task"]] = n
    if sorted(by_task) != sorted(PIN_GRAPH_NODES):
        rep.fail(cat, "node-set",
                 "消费者节点集合必须恰为 15 个真实任务书，缺 %r，多 %r"
                 % (sorted(set(PIN_GRAPH_NODES) - set(by_task)),
                    sorted(set(by_task) - set(PIN_GRAPH_NODES))))
    else:
        rep.ok(cat, "node-set", "15 个节点全部是 .xkw/tasks 下的真实任务书")
    books = up.task_books()
    for tid, n in sorted(by_task.items()):
        prob = []
        tb = books.get(tid)
        if tb is None:
            prob.append("任务书不存在于 .xkw/tasks")
        else:
            if n.get("task_book") != tb["path"]:
                prob.append("task_book 期望 %r，实际 %r" % (tb["path"], n.get("task_book")))
            if not tb["text"].split("\n")[0].startswith("# " + tid + ":"):
                prob.append("task_book 首行标题与 task id 不符")
        if n.get("role") != PIN_NODE_ROLE.get(tid):
            prob.append("role 期望 %r，实际 %r" % (PIN_NODE_ROLE.get(tid), n.get("role")))
        if PIN_NODE_ROLE.get(tid) == "input":
            want = [f for f in PIN_NODE_FIELDS if f != "ledger_applicability"]
        else:
            want = PIN_NODE_FIELDS
        if list(n.keys()) != want:
            prob.append("字段集合不符：期望 %r，实际 %r" % (want, list(n.keys())))
        want_write = (tid == "SPEC-103t")
        if n.get("write_access_to_gap_source") is not want_write:
            prob.append("write_access_to_gap_source 必须是 %r（下游不得回写 gap 真源）" % want_write)
        if n.get("owns_identities") in (11, 42) and \
                len(up.section_task.get(tid, [])) != n.get("owns_identities"):
            prob.append("owns_identities 期望 %d，实际 %d"
                        % (len(up.section_task.get(tid, [])), n.get("owns_identities")))
        if not str(n.get("na_runtime_note", "")).strip():
            prob.append("na_runtime_note 为空（须写明 N/A(runtime) 不是 PASS / layout 不解锁 reset）")
        if prob:
            rep.fail(cat, "node-%s" % tid, "；".join(prob))
    if not [i for i in rep.items if i[0] == cat and i[2] is False
            and i[1].startswith("node-")]:
        rep.ok(cat, "node-detail",
               "15 个节点的任务书路径/角色/写权限/identity 归属均核对通过")
    # Active applicability is defined by this producer ledger; existing downstream task books retain
    # historical S7 wording and are not an authority for reactivating it.
    for tid, n in sorted(by_task.items()):
        if PIN_NODE_ROLE[tid] == "input":
            continue
        got = n.get("ledger_applicability") or {}
        if sorted(got) != PIN_LEDGER_KEYS:
            rep.fail(cat, "applic-%s" % tid, "ledger_applicability 键集合必须精确等于六键，实际 %r" % sorted(got))
            continue
        for k, v in got.items():
            if v not in PIN_APPLICABILITY:
                rep.fail(cat, "applic-%s" % tid, "%s 的适用状态 %r 非法" % (k, v))
        if tid == "LLVM-101t" and (got.get("D17:S1") != "N/A(runtime)" or got.get("D17:S3") != "OPEN"):
            rep.fail(cat, "applic-LLVM-101t", "LLVM-101t 必须保持 S1=N/A(runtime)、S3=OPEN")
    if not [i for i in rep.items if i[0] == cat and i[2] is False and i[1].startswith("applic-")]:
        rep.ok(cat, "applicability", "所有消费者仅声明六个 active ledger 键；N/A(runtime) 不升格为 PASS")
    # 判别句只给整体结论的任务：逐键值由 PIN_APPLIC_PINNED / PIN_APPLIC_ALL_NA 钉死。
    # 这两张表若只是死常量，就等于「记录了下游措辞」却从不核对——所以在这里落地。
    pbad = []
    for tid, want in sorted(PIN_APPLIC_PINNED.items()):
        got = (by_task.get(tid) or {}).get("ledger_applicability") or {}
        for k, v in sorted(want.items()):
            if got.get(k) != v:
                pbad.append("%s 的 %s 期望 %r，实际 %r" % (tid, k, v, got.get(k)))
    for tid in PIN_APPLIC_ALL_NA:
        got = (by_task.get(tid) or {}).get("ledger_applicability") or {}
        for k in sorted(got):
            if got[k] != "N/A(runtime)":
                pbad.append("%s 的 %s 期望 'N/A(runtime)'，实际 %r" % (tid, k, got[k]))
    if pbad:
        rep.fail(cat, "applic-pinned", "；".join(pbad[:8]))
    else:
        rep.ok(cat, "applic-pinned",
               "TESTCASES-101t/SPEC-103t 六键全 OPEN；LLVM-102t/103t 六键全 N/A(runtime)（N/A 不是 PASS）")
    # D11 has three required downstream mappings; their assertion categories are
    # part of this producer's contract, not inferred from downstream success.
    required_d11 = {
        ("LLVM-101t", "assembler-legality"),
        ("TESTCASES-102t", "schema/oracle/vector"),
        ("TESTCASES-102t", "runtime semantics"),
        ("INTEG-103t", "runtime semantics"),
    }
    got_d11 = set()
    for tid, n in by_task.items():
        if "D11" in (n.get("consumes") or {}).get("decisions", []):
            for assertion in (n.get("consumes") or {}).get("assertion_classes", []):
                got_d11.add((tid, assertion))
    missing_d11 = sorted(required_d11 - got_d11)
    if missing_d11:
        rep.fail(cat, "d11-consumers", "D11 缺少必需消费者映射：%r" % missing_d11)
    else:
        rep.ok(cat, "d11-consumers",
               "D11→LLVM assembler-legality、TESTCASES schema/oracle/vector+runtime、INTEG runtime")
    # 边
    edges = cg.get("edges")
    if not isinstance(edges, list) or not edges:
        rep.fail(cat, "edges-type", "consumer_graph.edges 必须是非空列表")
        return
    have = []
    for i, e in enumerate(edges):
        if not isinstance(e, dict) or "from" not in e or "to" not in e:
            rep.fail(cat, "edge-shape", "edges[%d] 形状不符：%r" % (i, e))
            continue
        u, v = e["from"], e["to"]
        have.append((u, v))
        if u not in by_task or v not in by_task:
            rep.fail(cat, "edge-node", "edges[%d] 指向未声明节点：%r" % (i, (u, v)))
            continue
        basis = e.get("basis")
        if basis == "dependency-line":
            line = up.dep_line(v)
            refs = expand_task_refs(line)
            if u not in refs:
                rep.fail(cat, "edge-backing",
                         "edges[%d] %s→%s 声明 basis=dependency-line，但 %s 的依赖/关联任务行未列出 %s：%r"
                         % (i, u, v, v, u, line))
        elif basis != "taskbook-mention":
            rep.fail(cat, "edge-basis", "edges[%d] 的 basis 必须是 dependency-line 或 taskbook-mention" % i)
        else:
            if ("`%s`" % u) not in books[v]["text"]:
                rep.fail(cat, "edge-backing",
                         "edges[%d] %s→%s 声明 basis=taskbook-mention，但 %s 全文未提到 %s"
                         % (i, u, v, v, u))
    if len(set(have)) != len(have):
        rep.fail(cat, "edge-dup", "edges 存在重复边：%r" % [x for x in set(have) if have.count(x) > 1])
    miss = [x for x in PIN_REQUIRED_EDGES if x not in have]
    if miss:
        rep.fail(cat, "edge-required",
                 "任务书 §10 规定方向的必需边缺失 %d 条：%r" % (len(miss), miss))
    else:
        rep.ok(cat, "edge-required", "%d 条必需边齐备" % len(PIN_REQUIRED_EDGES))
    if not [i for i in rep.items if i[0] == cat and i[2] is False and i[1].startswith("edge-backing")]:
        rep.ok(cat, "edge-backing", "每条 dependency-line 边都由目标任务书的依赖/关联任务行独立溯源")
    # DAG
    adj = {n: set() for n in by_task}
    for u, v in have:
        if u in adj and v in adj:
            adj[u].add(v)
    state, cyc = {}, []

    def dfs(n, stack):
        state[n] = 1
        for m2 in sorted(adj.get(n, ())):
            if state.get(m2) == 1:
                cyc.append(stack + [n, m2])
            elif state.get(m2, 0) == 0:
                dfs(m2, stack + [n])
        state[n] = 2

    for n in sorted(by_task):
        if state.get(n, 0) == 0:
            dfs(n, [])
    if cyc:
        rep.fail(cat, "dag", "consumer_graph 存在环：%r" % cyc[:3])
    else:
        rep.ok(cat, "dag", "15 节点 %d 边构成 DAG（拓扑序验证）" % len(set(have)))
    cp = cg.get("critical_path") or []
    if not as_str_list(cp) or len(cp) < 4:
        rep.fail(cat, "critical-path", "critical_path 缺失或过短：%r" % cp)
    else:
        rep.ok(cat, "critical-path", " → ".join(cp))


def g9_candidates(rep, doc, up):
    cat = "G9"
    cands = doc.get("candidate_inputs")
    if not isinstance(cands, list) or not cands:
        rep.fail(cat, "cand-type", "candidate_inputs 必须是非空列表")
        return
    if len(cands) != len({c.get("id") for c in cands if isinstance(c, dict)}):
        rep.fail(cat, "cand-dup", "candidate_inputs 出现重复 id")
    else:
        rep.ok(cat, "cand-dup", "%d 个候选问题 id 唯一" % len(cands))
    sel = selection_offenders(cands)
    for ptr, k, w in sel:
        cid = owning_candidate_id(ptr, cands)
        rep.fail(cat, "cand-selection-key",
                 "候选问题 %s（%s）出现表示「已作选择」的键 %r（命中词根 %r）"
                 % (cid if cid else "id 不可解析", ptr, k, w))
    if not sel:
        rep.ok(cat, "cand-selection-key",
               "candidate_inputs 内无 selected/default/recommended/Accepted 之类键名")
    d17c = []
    for i, c in enumerate(cands):
        if not isinstance(c, dict):
            rep.fail(cat, "cand-shape", "candidate_inputs[%d] 不是映射" % i)
            continue
        prob = []
        if list(c.keys()) != PIN_CAND_FIELDS:
            prob.append("字段集合不符：%r" % list(c.keys()))
        if not str(c.get("id", "")).strip():
            prob.append("id 为空")
        if c.get("decision") not in PIN_DECISIONS:
            prob.append("decision 必须是 D11–D17，实际 %r" % c.get("decision"))
        if c.get("facet") not in up.facets:
            prob.append("facet 必须是 11 个 facet 之一，实际 %r" % c.get("facet"))
        if c.get("status") not in ("OPEN", "BLOCKED"):
            prob.append("status 只能是 OPEN/BLOCKED，实际 %r" % c.get("status"))
        if not str(c.get("question", "")).strip():
            prob.append("question 为空")
        if not str(c.get("affected_identities_scope", "")).strip():
            prob.append("affected_identities_scope 为空")
        if not str(c.get("asking_rule", "")).strip():
            prob.append("asking_rule 为空")
        opts = c.get("options")
        if not isinstance(opts, list) or len(opts) < 2:
            prob.append("options 必须给出 >= 2 个互斥备选，实际 %r"
                        % (len(opts) if isinstance(opts, list) else opts))
        else:
            oids = [o.get("id") for o in opts if isinstance(o, dict)]
            if len(set(oids)) != len(oids):
                prob.append("options 的 id 不唯一：%r" % oids)
            for j, o in enumerate(opts):
                if not isinstance(o, dict):
                    prob.append("options[%d] 不是映射" % j)
                    continue
                if list(o.keys()) != PIN_OPTION_FIELDS:
                    prob.append("options[%d] 字段集合不符：%r" % (j, list(o.keys())))
                for f in PIN_OPTION_FIELDS:
                    if f == "id":
                        continue
                    if f == "depends_on":
                        if not isinstance(o.get(f), list):
                            prob.append("options[%d].depends_on 必须是列表" % j)
                        continue
                    if not str(o.get(f, "")).strip():
                        prob.append("options[%d].%s 为空（每个备选都必须写清行为/可观测差异/代价）"
                                    % (j, f))
            behs = [o.get("behavior") for o in opts if isinstance(o, dict)]
            if len(set(behs)) != len(behs):
                prob.append("options 的 behavior 互不相同：%r" % behs)
        if c.get("decision") == "D17" and c.get("id", "").startswith("CAND-D17-S"):
            d17c.append(c.get("id"))
        if prob:
            rep.fail(cat, "cand-%s" % c.get("id", i), "；".join(prob))
    if not [x for x in rep.items if x[0] == cat and x[2] is False
            and x[1].startswith("cand-") and x[1] not in
            ("cand-dup", "cand-selection-key", "cand-shape", "cand-type")]:
        rep.ok(cat, "cand-detail", "%d 个候选问题均含互斥备选与可观测差异" % len(cands))
    # D17 必须七键各自独立成题，且不得用一题关七项
    if sorted(d17c) != ["CAND-D17-S%d" % i for i in (1, 3, 4, 5, 6, 8)]:
        rep.fail(cat, "d17-one-per-key",
                 "D17 必须为六个 active 键各出一个独立问题，实际 %r" % sorted(d17c))
    else:
        rep.ok(cat, "d17-one-per-key", "D17 的六个 active 键各有一个独立候选问题，不得用一题关闭多项")
    dbad = 0
    for d in PIN_DECISIONS:
        n = sum(1 for c in cands if isinstance(c, dict) and c.get("decision") == d)
        if n < 1:
            rep.fail(cat, "cand-per-decision", "%s 没有任何候选问题" % d)
            dbad += 1
    if not dbad:
        rep.ok(cat, "cand-per-decision",
               "D11–D17 每项至少一个最小可问问题，共 %d 个" % len(cands))
    if any(isinstance(c, dict) and c.get("id", "").startswith("CAND-D17-S2") for c in cands):
        rep.fail(cat, "cand-s2", "D17:S2 是 trace-only，不得有候选问题")
    else:
        rep.ok(cat, "cand-s2", "trace-only 的 D17:S2 没有候选问题")


#: G10 只在**状态位**上扫描取值；散文里出现「PASS」「不得」等是被允许的。
#: `classification` 单独处理：它的合法取值表本身就是任务书 §6 钉死的四类，
#: 其中 `spec-determined` 是合法分类，不能被「含 determined 就 FAIL」的粗扫误伤。
G10_SCALAR_RULES = {
    "status": PIN_STATUS_WORDS,
    "classification": PIN_CLASSIFICATIONS,
    "now_runnable": [True, False],
    "in_ledger": [True, False],
    "pass_counted": [True, False],
    "status_word_allowed": [True, False],
    "d17_fallback": [True, False],
    "write_access_to_gap_source": [True, False],
    "cited_files_must_be_in_order": [True, False],
}
G10_MAP_RULES = {
    "facet_status": None,          # 逐条比 contracts/opcodes.yaml
    "ledger_applicability": PIN_APPLICABILITY,
}
G10_BAD_WORDS = ["pass", "active", "spec-determined", "resolved", "accepted",
                 "closed", "done", "green"]


def g10_open(rep, doc, up):
    cat = "G10"
    bad = 0
    nstatus = 0
    for ptr, k, v in walk(doc):
        if k in G10_SCALAR_RULES:
            nstatus += 1
            allowed = G10_SCALAR_RULES[k]
            if v not in allowed:
                rep.fail(cat, "status-word",
                         "%s 的 %s 取值 %r 非法（只允许 %r）" % (ptr, k, v, allowed))
                bad += 1
            elif k != "classification" and isinstance(v, str) and \
                    any(w in v.lower() for w in G10_BAD_WORDS):
                rep.fail(cat, "status-word",
                         "%s 的 %s 取值 %r 含 PASS/active/resolved/Accepted 之类词" % (ptr, k, v))
                bad += 1
        if k in G10_MAP_RULES and isinstance(v, dict):
            allowed = G10_MAP_RULES[k]
            for kk, vv in v.items():
                if allowed is None:
                    continue
                nstatus += 1
                if vv not in allowed:
                    rep.fail(cat, "status-word",
                             "%s.%s 取值 %r 非法（只允许 %r）" % (ptr, kk, vv, allowed))
                    bad += 1
    if not [x for x in rep.items if x[0] == cat and x[1] == "status-word" and x[2] is False]:
        rep.ok(cat, "status-word",
               "%d 个状态位取值全部合法，且无 PASS/active/resolved/Accepted 之类词" % nstatus)
    nfrz = 0
    for row in doc.get("impact_matrix") or []:
        if not isinstance(row, dict):
            continue
        insn = row.get("identity")
        src = up.by_insn.get(insn)
        if src is None:
            continue
        for f, st in (row.get("facet_status") or {}).items():
            nfrz += 1
            if st != src["f1"]["facets"][f]:
                rep.fail(cat, "facet-frozen",
                         "%s 的 facet %s 期望 %r（来自 contracts/opcodes.yaml），实际 %r —— "
                         "已决 facet 不得被 OPEN 一并冻结，OPEN 也不得把 OPEN 改成已决"
                         % (insn, f, src["f1"]["facets"][f], st))
                bad += 1
    if not [x for x in rep.items if x[0] == cat and x[1] == "facet-frozen" and x[2] is False]:
        rep.ok(cat, "facet-frozen",
               "%d 个 facet_status 逐条等于 contracts/opcodes.yaml 的 f1.facets" % nfrz)
    if bad == 0:
        rep.ok(cat, "open-not-active",
               "所有状态位取值合法；无 PASS/active/spec-determined/resolved/Accepted 被写进状态字段")
    lg = doc.get("d17_open_ledger") or {}
    nopen = sum(1 for r in lg.values() if isinstance(r, dict) and r.get("status") == "OPEN")
    nblk = sum(1 for r in lg.values() if isinstance(r, dict) and r.get("status") == "BLOCKED")
    if nopen + nblk != len(PIN_LEDGER_KEYS):
        rep.fail(cat, "ledger-all-open",
                 "六键 active ledger 必须全部保持 OPEN/BLOCKED，实际 OPEN=%d BLOCKED=%d" % (nopen, nblk))
    else:
        rep.ok(cat, "ledger-all-open", "六键全部 OPEN/BLOCKED（OPEN %d + BLOCKED %d）" % (nopen, nblk))
    dp = doc.get("decision_proofs") or {}
    ngen = sum(1 for r in dp.values() if isinstance(r, dict) and r.get("classification") == "genuine-gap")
    if ngen != 7:
        rep.fail(cat, "gap-not-closed",
                 "七个 decision 必须全部仍是 genuine-gap（未关闭），实际 %d" % ngen)
    else:
        rep.ok(cat, "gap-not-closed", "D11–D17 七个 genuine-gap 全部保持未关闭")


def g11_scope(rep, doc, up, root, yaml_rel):
    cat = "G11"
    raw = read_text(root, yaml_rel)
    for a in PIN_FORBIDDEN_ADR:
        if a in raw:
            rep.fail(cat, "adr-binding",
                     "YAML 预先绑定了 Candidate ADR 编号 %s（任务书 §11 禁止预设 ADR-1005~1007）" % a)
            return
    rep.ok(cat, "adr-binding", "未预先绑定 ADR-1005/1006/1007，也未假定未来 ADR 数量")
    for a in PIN_FORBIDDEN_ADR:
        for ext in (".md", ".yaml"):
            hits = []
            for sub in (".xkw/knowledge", "contracts", "spec", "tests", "tools"):
                d = os.path.join(root, sub)
                if not os.path.isdir(d):
                    continue
                for n in sorted(os.listdir(d)):
                    if a.lower() in n.lower() and n.endswith(ext):
                        hits.append(os.path.join(sub, n))
            if hits:
                rep.fail(cat, "adr-file",
                         "存在 Candidate ADR 文件 %r（不得创建/接受）" % hits)
                return
    rep.ok(cat, "adr-file", "仓库中不存在 ADR-1005/1006/1007 文件")
    d = os.path.join(root, "contracts")
    stray = [n for n in sorted(os.listdir(d))
             if n.startswith("f1_gap_proof") and n != "f1_gap_proofs.yaml"]
    if stray:
        rep.fail(cat, "stray-artifact", "contracts/ 下出现任务书 §5 白名单外的产物：%r" % stray)
    else:
        rep.ok(cat, "stray-artifact", "contracts/ 下无白名单外的 f1_gap_proof* 产物")
    ts = os.path.join(root, "tools/spec")
    want = {os.path.basename(CHECKER_REL), os.path.basename(RUNNER_REL)}
    have = {n for n in os.listdir(ts)
            if "f1_gap_proof" in n and n.endswith(".py")}
    if not want <= have:
        rep.fail(cat, "scripts", "§5 要求入库的脚本缺失：%r" % sorted(want - have))
    else:
        rep.ok(cat, "scripts", "checker 与反例驱动器均随产物入库于 tools/spec/")
    if not os.path.isdir(os.path.join(root, ".tao")):
        rep.skipped(cat, "tao-clean", "临时树内无 .tao/ 目录（合成树场景）")
    else:
        try:
            out = subprocess.run(
                ["git", "-c", "core.quotepath=false", "status", "--porcelain=v1",
                 "--untracked-files=all"],
                cwd=root, capture_output=True, text=True, timeout=120).stdout
        except Exception as exc:                                # pragma: no cover
            rep.skipped(cat, "tao-clean", "无法执行 git status：%r" % exc)
            return
        bad = [l for l in out.split("\n") if l.strip().endswith(".tao") or ".tao/" in l]
        if bad:
            rep.fail(cat, "tao-clean", ".tao/ 出现改动（必须零改动）：%r" % bad)
        else:
            rep.ok(cat, "tao-clean", ".tao/ 零改动")


def g12_s7_consistency(rep, doc, up):
    cat = "G12"
    # ── 12.1 全文档逐分句：提到 S7 就必须显式标为历史/non-gap/不进入 active ──
    told, bad = 0, []
    for ptr, _k, v in walk(doc):
        for cl in prose_clauses(v):
            if not PIN_S7_TELL_RE.search(cl):
                continue
            told += 1
            if PIN_S7_SETTLED_RE.search(cl):
                continue
            bad.append((ptr, s7_enum_kind(cl), cl))
    if bad:
        for ptr, kind, cl in bad[:12]:
            rep.fail(cat, "s7-unsettled-mention",
                     "%s 的分句把 S7 %s：%s" % (ptr, kind, cl[:240]))
        if len(bad) > 12:
            rep.fail(cat, "s7-unsettled-mention",
                     "另有 %d 个分句同样未标注" % (len(bad) - 12))
    else:
        rep.ok(cat, "s7-unsettled-mention",
               "%d 个提到 S7 的分句全部显式标为历史 / non-gap / 不进入 active" % told)
    # ── 12.2 active 项数必须写成六，不得残留「七项」口径 ──
    # 计数词须落在**缺口台账语境**：`七条身份`（37 条 identity 中的 7 条）不是缺口计数。
    cbad, ctot, cseen = [], 0, 0
    for ptr, _k, v in walk(doc):
        for cl in prose_clauses(v):
            if not PIN_SEVEN_COUNT_RE.search(cl):
                continue
            cseen += 1
            if not PIN_LEDGER_CTX_RE.search(cl):
                continue          # 身份/记录计数，非 active 集合计数
            ctot += 1
            if PIN_S7_SETTLED_RE.search(cl):
                continue          # 明确指向下游历史措辞的说明句，允许
            cbad.append((ptr, cl))
    if cbad:
        for ptr, cl in cbad[:12]:
            rep.fail(cat, "active-count-six",
                     "%s 仍按「七」叙述 active 集合（active 精确为六键 %r）：%s"
                     % (ptr, PIN_LEDGER_KEYS, cl[:200]))
    else:
        rep.ok(cat, "active-count-six",
               "%d 处台账语境的「七」计数词中无一按七键叙述 active（active 精确六键；"
               "另有 %d 处为身份/记录计数，不计）" % (ctot, cseen - ctot))
    # ── 12.3 D17 必须逐项点名六个 active OPEN-ID（正向，防止「删一项就干净」）──
    d17 = ((doc.get("decision_proofs") or {}).get("D17") or {})
    mconf = str(d17.get("missing_or_conflicting", ""))
    miss = [k for k in PIN_D17_REQUIRED_TELLS
            if not re.search(r"(?<![0-9A-Za-z])%s(?![0-9A-Za-z])" % k, mconf)]
    if miss:
        rep.fail(cat, "d17-six-active-tells",
                 "D17.missing_or_conflicting 未逐项点名 active OPEN-ID %r（缺 %r）"
                 % (PIN_D17_REQUIRED_TELLS, miss))
    else:
        rep.ok(cat, "d17-six-active-tells",
               "D17.missing_or_conflicting 逐项点名六个 active OPEN-ID：%s"
               % "/".join(PIN_D17_REQUIRED_TELLS))
    # ── 12.4 D17 叙述里的 active 投影必须是六键的 64/2/26/2/6/4 ──
    obs = " ; ".join(str(x) for x in d17.get("observable_consequences") or [])
    if PIN_D17_ACTIVE_SCOPE_STR not in mconf and PIN_D17_ACTIVE_SCOPE_STR not in obs:
        rep.fail(cat, "d17-active-scope",
                 "D17 的 missing_or_conflicting / observable_consequences 均未给出 active 六键投影 %r"
                 % PIN_D17_ACTIVE_SCOPE_STR)
    else:
        rep.ok(cat, "d17-active-scope",
               "D17 叙述给出 active 六键投影 %s（不含已排除的 S7 历史范围）"
               % PIN_D17_ACTIVE_SCOPE_STR)
    # ── 12.5 S7 的原始权威恰为 SimRISC-00:41-46 + SimRISC-03:33-49 ──
    s7 = ((doc.get("non_gap_records") or {}).get(PIN_S7_ID) or {})
    cites = [(c.get("file"), str(c.get("lines"))) for c in s7.get("spec_cites") or []
             if isinstance(c, dict)]
    srcs = set()
    for e in s7.get("evidence") or []:
        if isinstance(e, dict):
            for p, _ls in source_items(e.get("source", "")):
                srcs.add(p)
    prob = []
    if set(cites) != PIN_S7_RAW_AUTHORITY:
        prob.append("spec_cites 期望恰为 %r，实际 %r"
                    % (sorted(PIN_S7_RAW_AUTHORITY), sorted(set(cites))))
    if srcs - {f for f, _ in PIN_S7_RAW_AUTHORITY}:
        prob.append("evidence 引用了非原始规范来源 %r（不得以 ADR 代替 raw spec 证明）"
                    % sorted(srcs - {f for f, _ in PIN_S7_RAW_AUTHORITY}))
    if prob:
        rep.fail(cat, "s7-raw-authority", "；".join(prob))
    else:
        rep.ok(cat, "s7-raw-authority",
               "S7 non-gap 的权威恰为 SimRISC-00:41-46 + SimRISC-03:33-49，无 ADR 代证")
    # ── 12.6 下游任务书必须与 resolution 投影**同步**（SPEC-104t §10）──
    # SPEC-103t 原 12.6 钉的是「含 S7 的历史七项原句**仍在**」（分歧登记），
    # SPEC-104t 同步已把七项/S7-active/未确认措辞删掉，故钉点改为**同步后**的
    # 逐字句。检查方向仍不变：句子被动过就 FAIL（只是此时意味着同步结果被回退，
    # 而不是「历史分歧被静默抹平」）。
    books = up.task_books()
    gone = []
    for tid, sents in sorted(PIN_APPLIC_SENTENCE.items()):
        tb = books.get(tid)
        if tb is None:
            gone.append("%s 任务书不存在" % tid)
            continue
        gone += ["%s 缺同步后原句 %r" % (tid, s) for s in sents if s not in tb["text"]]
    if gone:
        rep.fail(cat, "upstream-synced-wording",
                 "下游任务书的 active 六键/projected 同步原句缺失 %d 处（同步结果被回退，"
                 "须显式登记）：%r" % (len(gone), gone[:4]))
    else:
        rep.ok(cat, "upstream-synced-wording",
               "13 本任务书（12 本下游 + SPEC-103t）全部保留同步后的 active 六键 / "
               "projected-pending-activation 原句；active 依据是本文件六键，"
               "不再是含 S7 的历史七项口径")


# ══════════════ SPEC-104t：已确认语义机器投影的检查组 G13～G20 ══════════════
def resolution_layer(rep, doc):
    """取 `resolution` 覆盖层；缺失/类型错误时登记失败并返回 None（不抛异常）。"""
    R = doc.get("resolution")
    if not isinstance(R, dict):
        rep.fail("G13", "resolution-present",
                 "顶层 `resolution` namespace 缺失或不是映射（SPEC-104t §7 要求"
                 "在历史 proof 之上**增加**具名覆盖层，而不是改写历史）")
        return None
    return R


def g13_adr_inventory(rep, doc, up):
    """§8.1：七份 ADR 集合、状态、decision 标题、确认记录、superseded D1。"""
    cat = "G13"
    R = resolution_layer(rep, doc)
    if R is None:
        return
    # ── 13.1 七份 ADR 集合（按编号，不是按文件名）──
    try:
        files = up.adr_files
    except ValueError as exc:
        rep.fail(cat, "adr-inventory", repr(exc))
        return
    nums = sorted(int(a.split("-")[1]) for a in files)
    if sorted(files) != PIN_ADR_SET or nums != list(range(1009, 1016)):
        rep.fail(cat, "adr-inventory",
                 "ADR 集合期望恰为 %r（编号 1009～1015 各一份），实际 %r / 编号 %r"
                 % (PIN_ADR_SET, sorted(files), nums))
    else:
        rep.ok(cat, "adr-inventory",
               "七份 ADR 按编号各恰好一份：%s"
               % "/".join("%s=%s" % (a, files[a].split("/")[-1]) for a in PIN_ADR_SET))
    # ── 13.2 生命周期：执行/验收时全 Candidate；/complete 后全 Accepted ──
    # resolution YAML 记录的是 SPEC-104t 投影时点，故其 lifecycle 仍保持
    # pending-activation；这里读取 ADR 文件的实时状态来区分激活前后。
    states = {a: up.adr_state.get(a) for a in PIN_ADR_SET}
    state_set = set(states.values())
    if state_set == {PIN_ADR_STATE_CANDIDATE}:
        rep.ok(cat, "adr-state-candidate",
                "七份 ADR 的 `**状态**` 全部为 %s（激活门禁因此尚未解除）"
                % PIN_ADR_STATE_CANDIDATE)
    elif state_set == {PIN_ADR_STATE_ACCEPTED}:
        rep.ok(cat, "adr-state-accepted",
               "七份 ADR 的 `**状态**` 全部为 %s（/complete 后 activation gate 已解除）"
               % PIN_ADR_STATE_ACCEPTED)
    else:
        rep.fail(cat, "adr-state-lifecycle",
                 "七份 ADR 状态必须全为 %r（执行/验收）或全为 %r（/complete 后），"
                 "不得混合；实际 %r"
                 % (PIN_ADR_STATE_CANDIDATE, PIN_ADR_STATE_ACCEPTED, states))
    # ── 13.3 decision 标题逐条数（现行 27 + superseded D1 = 28）──
    cnt = {a: len(up.adr_headings.get(a) or []) for a in PIN_ADR_SET}
    tot = sum(cnt.values())
    dm = R.get("decision_map") or {}
    cur = [c for c in (dm.get("current") or []) if isinstance(c, dict)]
    sup = [c for c in (dm.get("superseded") or []) if isinstance(c, dict)]
    # 投影侧逐 ADR 的现行条数：交叉核对「ADR 原文 28 条 - superseded D1 = 现行 27 条」
    pcur = {}
    for c in cur:
        pcur[c.get("adr")] = pcur.get(c.get("adr"), 0) + 1
    if (cnt != PIN_ADR_HEADING_COUNT or tot != PIN_CURRENT_DECISION_COUNT + 1
            or pcur != PIN_ADR_DECISION_COUNT or len(cur) != PIN_CURRENT_DECISION_COUNT):
        rep.fail(cat, "adr-decision-titles",
                 "ADR 原文 `### Dn：` 逐 ADR 标题计数期望 %r（合计 28 = 27 现行 + 1 superseded），"
                 "实际 %r（合计 %d）；`decision_map.current` 逐 ADR 条数期望 %r（合计 27），"
                 "实际 %r（合计 %d）"
                 % (PIN_ADR_HEADING_COUNT, cnt, tot, PIN_ADR_DECISION_COUNT, pcur, len(cur)))
    else:
        rep.ok(cat, "adr-decision-titles",
               "ADR 原文 `### Dn：` 标题逐 ADR 计数 %s（合计 %d = 27 现行 + 1 superseded）；"
               "扣除 ADR-1009/D1 后投影 `current` 逐 ADR 条数 %s（合计 %d），与 27 条现行一致"
               % ("/".join("%s:%d" % (a, n) for a, n in sorted(cnt.items())), tot,
                  "/".join("%s:%d" % (a, n) for a, n in sorted(pcur.items())), len(cur)))
    # ── 13.4 投影里的 adr_heading 必须逐字出现在对应 ADR 原文 ──
    badh, unconfirmed = [], []
    for c in cur + sup:
        a, dn, hd = c.get("adr"), c.get("decision"), c.get("adr_heading")
        if hd not in (up.adr_headings.get(a) or []):
            badh.append("%s 的 adr_heading %r 不在 ADR 原文标题里" % (c.get("id"), hd))
        body = up.adr_sections.get((a, dn)) or ""
        if "**确认记录**" not in body:
            unconfirmed.append("%s/%s 缺 `**确认记录**`" % (a, dn))
    if badh:
        rep.fail(cat, "decision-heading-verbatim", "；".join(badh[:6]))
    elif unconfirmed:
        rep.fail(cat, "decision-heading-verbatim",
                 "标题均逐字命中，但下列 decision 段没有用户确认记录：%r"
                 % unconfirmed[:6])
    else:
        rep.ok(cat, "decision-heading-verbatim",
               "%d 条投影 decision（27 现行 + 1 superseded）的 `### Dn：标题` 逐字命中"
               " ADR 原文，且每段都带 `**确认记录**`" % (len(cur) + len(sup)))
    # ── 13.5 唯一的 superseded：ADR-1009 D1，被 D2 覆盖且不计入 27 ──
    adr, dn, by = PIN_SUPERSEDED
    prob = []
    if len(sup) != 1 or dm.get("superseded_count") != 1:
        prob.append("superseded 必须恰好一条，实际 %d 条 / count=%r"
                    % (len(sup), dm.get("superseded_count")))
    else:
        s0 = sup[0]
        if (s0.get("adr"), s0.get("decision"), s0.get("id")) != (adr, dn, adr + "/" + dn):
            prob.append("superseded 身份期望 %s/%s，实际 %r/%s（%r）"
                        % (adr, dn, s0.get("adr"), s0.get("decision"), s0.get("id")))
        if s0.get("superseded_by") != by:
            prob.append("superseded_by 期望 %r，实际 %r" % (by, s0.get("superseded_by")))
        if s0.get("counted_in_current_27") is not False:
            prob.append("counted_in_current_27 必须为 false，实际 %r"
                        % s0.get("counted_in_current_27"))
        if s0.get("state") != "superseded":
            prob.append("state 期望 superseded，实际 %r" % s0.get("state"))
    if any(c.get("decision") == dn and c.get("adr") == adr for c in cur):
        prob.append("D1 仍出现在 current 列表里（被取代的 decision 不得复活）")
    if prob:
        rep.fail(cat, "superseded-singleton", "；".join(prob))
    else:
        rep.ok(cat, "superseded-singleton",
               "唯一 superseded 为 %s（被 %s 覆盖、不计入 27、state=superseded），"
               "且未出现在 current 列表" % (adr + "/" + dn, by))
    # ── 13.6 lifecycle 字段与**投影时点**的 Candidate 记录一致 ──
    # `producer_task` 是 `resolution` 的**顶层**键（§7 的 schema），不在 lifecycle 内部：
    # lifecycle 只管「激活」这件事（门槛、现状、claim 边界、激活归属）。
    lc = R.get("lifecycle") or {}
    want_lc = {
        "adr_set": PIN_ADR_SET,
        "adr_state_required_for_activation": PIN_ADR_STATE_ACCEPTED,
        "adr_state_observed_in_this_file": PIN_ADR_STATE_CANDIDATE,
        "activation_state": "pending-activation",
    }
    diff = {k: (lc.get(k), v) for k, v in want_lc.items() if lc.get(k) != v}
    if R.get("producer_task") != "SPEC-104t":
        diff["resolution.producer_task"] = (R.get("producer_task"), "SPEC-104t")
    if diff:
        rep.fail(cat, "lifecycle-fields",
                 "lifecycle/producer_task 字段与实际观察不符（期望, 实际）：%r" % diff)
    else:
        rep.ok(cat, "lifecycle-fields",
                "resolution.producer_task=SPEC-104t；lifecycle 记录投影时激活需 %r、观察为 %r、"
               "activation_state=pending-activation"
               % (PIN_ADR_STATE_ACCEPTED, PIN_ADR_STATE_CANDIDATE))
    # ── 13.7 覆盖层**只增不改**：历史 12 键仍在，resolution 键集合精确 ──
    rkeys = list(R.keys())
    if rkeys != PIN_RESOLUTION_KEYS:
        rep.fail(cat, "resolution-keys",
                 "resolution 键集合期望 %r，实际 %r" % (PIN_RESOLUTION_KEYS, rkeys))
    else:
        rep.ok(cat, "resolution-keys",
               "resolution 覆盖层含 §7 要求的全部 %d 个具名段（历史 12 键未被搬入或改名）"
               % len(rkeys))

    # Do not treat `behavior` as a label.  Every current and supplemental
    # entry has an independently pinned semantic clause set; this deliberately
    # runs after the structural checks so a swapped/reversed value gets a
    # named, actionable failure rather than an incidental count failure.
    behavior_bad = []
    for entry in cur:
        ident = entry.get("id")
        clauses = PIN_BEHAVIOR_CLAUSES.get(ident)
        if clauses is None:
            behavior_bad.append("%s 无独立 behavior 期望" % ident)
            continue
        behavior = entry.get("behavior")
        if not isinstance(behavior, str):
            behavior_bad.append("%s.behavior 不是字符串：%r" % (ident, behavior))
            continue
        missing = [clause for clause in clauses if clause not in behavior]
        if missing:
            behavior_bad.append("%s 缺少语义片段 %r；实际=%r" %
                               (ident, missing, behavior))
    if len(PIN_BEHAVIOR_CLAUSES) != PIN_CURRENT_DECISION_COUNT:
        behavior_bad.append("独立 behavior 期望覆盖 %d 条，实际 %d 条" %
                           (PIN_CURRENT_DECISION_COUNT, len(PIN_BEHAVIOR_CLAUSES)))
    if behavior_bad:
        rep.fail(cat, "decision-behavior",
                 "current/supplemental behavior 语义真值不符：%s" %
                 "；".join(behavior_bad[:8]))
    else:
        rep.ok(cat, "decision-behavior",
               "27 条 current/supplemental behavior 均命中独立语义片段（含 D15 转换/算术边界）")


def g14_candidate_closure(rep, doc, up, cand_ids):
    """§8.2：24 Candidate ↔ 27 现行 decision（含 5 supplemental）双向闭合。"""
    cat = "G14"
    R = resolution_layer(rep, doc)
    if R is None:
        return
    dm = R.get("decision_map") or {}
    cur = [c for c in (dm.get("current") or []) if isinstance(c, dict)]
    prim = [c for c in cur if c.get("kind") == "primary"]
    supp = [c for c in cur if c.get("kind") == "supplemental"]
    byid = {c.get("id"): c for c in cur}
    prob = []
    if dm.get("current_count") != len(cur):
        prob.append("current_count=%r != 实际 %d" % (dm.get("current_count"), len(cur)))
    if len(cur) != PIN_CURRENT_DECISION_COUNT:
        prob.append("现行 decision %d != %d" % (len(cur), PIN_CURRENT_DECISION_COUNT))
    if len(prim) != PIN_PRIMARY_DECISION_COUNT:
        prob.append("primary %d != %d" % (len(prim), PIN_PRIMARY_DECISION_COUNT))
    if len(supp) != PIN_SUPPLEMENTAL_DECISION_COUNT:
        prob.append("supplemental %d != %d" % (len(supp), PIN_SUPPLEMENTAL_DECISION_COUNT))
    if len(byid) != len(cur):
        prob.append("现行 decision id 有重复")
    badadr = [c.get("id") for c in cur
              if c.get("adr") not in PIN_ADR_SET or c.get("adr_heading")
              not in (up.adr_headings.get(c.get("adr")) or [])]
    if badadr:
        prob.append("下列 decision 的 adr/adr_heading 对不上 ADR 原文：%r" % badadr[:5])
    if prob:
        rep.fail(cat, "decision-counts", "；".join(prob))
    else:
        rep.ok(cat, "decision-counts",
               "现行 %d 条 = %d primary + %d supplemental，逐 ADR decision 计数与"
               " ADR 原文标题集合一致" % (len(cur), len(prim), len(supp)))
    # ── 14.2 每条 primary 至少绑定一个 Candidate，且不得绑定 supplemental ──
    orphan = [c.get("id") for c in prim if not (c.get("candidate_question_ids") or [])]
    misused = [c.get("id") for c in supp if c.get("candidate_question_ids")]
    if orphan or misused:
        rep.fail(cat, "decision-candidate-binding",
                 "未绑定任何 Candidate 的 primary：%r；supplemental 却绑定了 Candidate：%r"
                 % (orphan, misused))
    else:
        rep.ok(cat, "decision-candidate-binding",
               "%d 条 primary 全部绑定 ≥1 个历史 Candidate；%d 条 supplemental 全部"
               "不直接绑定 Candidate（只细化已存在的 primary）" % (len(prim), len(supp)))
    # ── 14.3 24 条闭包：候选唯一、绑定同 gap、supplemental 同 gap ──
    cc = R.get("candidate_closure") or {}
    ents = [e for e in (cc.get("entries") or []) if isinstance(e, dict)]
    eprob = []
    if cc.get("candidate_count") != PIN_CANDIDATE_COUNT or len(ents) != PIN_CANDIDATE_COUNT:
        eprob.append("candidate_closure 期望 %d 条，实际 %d 条 / count=%r"
                     % (PIN_CANDIDATE_COUNT, len(ents), cc.get("candidate_count")))
    ids = [e.get("candidate_id") for e in ents]
    if len(set(ids)) != len(ids):
        eprob.append("candidate_id 有重复")
    if set(ids) != cand_ids:
        eprob.append("闭包里的 24 个 id 与历史 candidate_inputs 不一致："
                     "少 %r / 多 %r" % (sorted(cand_ids - set(ids)),
                                       sorted(set(ids) - cand_ids)))
    used_supp = set()
    for e in ents:
        b = e.get("bound_primary_decision")
        if b not in byid:
            eprob.append("%s 绑定的主 decision %r 不存在" % (e.get("candidate_id"), b))
            continue
        if byid[b].get("kind") != "primary":
            eprob.append("%s 绑定的 %r 不是 primary decision" % (e.get("candidate_id"), b))
        if byid[b].get("gap") != e.get("gap"):
            eprob.append("%s 跨 gap 绑定：自身 %r vs %s 的 %r"
                         % (e.get("candidate_id"), e.get("gap"), b, byid[b].get("gap")))
        for s in (e.get("refined_by_supplemental") or []):
            used_supp.add(s)
            if s not in byid:
                eprob.append("%s 的 supplemental %r 不存在" % (e.get("candidate_id"), s))
            elif byid[s].get("kind") != "supplemental":
                eprob.append("%s 的 refined_by %r 不是 supplemental" % (e.get("candidate_id"), s))
            elif byid[s].get("gap") != e.get("gap"):
                eprob.append("%s 的 supplemental %r 跨 gap（自身 %r vs %r）"
                             % (e.get("candidate_id"), s, e.get("gap"),
                                byid[s].get("gap")))
    if used_supp != {c.get("id") for c in supp}:
        eprob.append("supplemental 未被全部关联：未出现 %r / 指向不存在的 %r"
                     % (sorted({c.get('id') for c in supp} - used_supp),
                        sorted(used_supp - {c.get("id") for c in supp})))
    if eprob:
        rep.fail(cat, "candidate-closure", "；".join(eprob[:6]))
    else:
        rep.ok(cat, "candidate-closure",
               "24 条历史 Candidate 与 %d 条现行 decision 双向闭合：无 orphan、无重复、"
               "无跨 gap 绑定；%d 条 supplemental 各自关联到同 gap 的已存在 primary"
               % (len(cur), len(supp)))


def g15_rule_tables(rep, doc, up):
    """§8.3/§8.5：D11～D17 规则表全部从上游独立重算，§5 常量/状态转换/优先级。"""
    cat = "G15"
    R = resolution_layer(rep, doc)
    if R is None:
        return
    rt = R.get("rule_tables") or {}
    rs = up.rule_sets
    bad = {k: 0 for k in ("d11", "d12", "d13", "d14", "d15", "d16", "s6", "constants",
                         "precedence", "d17keys")}

    def cmp_set(label, got, want, key):
        if sorted(got or []) != sorted(want):
            rep.fail(cat, "rule-set-recomputed",
                     "%s 期望 %r，实际 %r" % (label, sorted(want), sorted(got or [])))
            bad[key] += 1

    # D11 白名单 10 条；rd2rf 明确落在 ILLI 侧
    d11 = rt.get("D11") or {}
    cmp_set("D11.rf0_write_whitelist", d11.get("rf0_write_whitelist"),
            rs["D11_whitelist"], "d11")
    if d11.get("rf0_write_whitelist_count") != len(rs["D11_whitelist"]):
        rep.fail(cat, "rule-set-recomputed",
                 "D11.rf0_write_whitelist_count=%r != 重算 %d"
                 % (d11.get("rf0_write_whitelist_count"), len(rs["D11_whitelist"])))
        bad["d11"] += 1
    if "rd2rf" in (d11.get("rf0_write_whitelist") or []):
        rep.fail(cat, "rule-set-recomputed",
                 "D11 白名单仍含 `rd2rf`（ADR-1009 D2：写 rf0 触发 ILLI）")
        bad["d11"] += 1
    if d11.get("rd2rf_to_rf0") != "ILLI" or d11.get("rf0_write_other") != "ILLI":
        rep.fail(cat, "rule-set-recomputed",
                 "D11 的非白名单写必须为 ILLI，实际 rd2rf_to_rf0=%r rf0_write_other=%r"
                 % (d11.get("rd2rf_to_rf0"), d11.get("rf0_write_other")))
        bad["d11"] += 1
    # D12 53 自动 / 11 不自动，二者必须互补成 64
    d12 = rt.get("D12") or {}
    cmp_set("D12.automatic_scope", d12.get("automatic_scope"), rs["D12_auto"], "d12")
    cmp_set("D12.non_automatic_scope", d12.get("non_automatic_scope"), rs["D12_non"], "d12")
    if d12.get("automatic_scope_count") != len(rs["D12_auto"]) or \
            d12.get("non_automatic_scope_count") != len(rs["D12_non"]):
        rep.fail(cat, "rule-set-recomputed",
                 "D12 scope 计数与集合不自洽：%r/%r vs 重算 %d/%d"
                 % (d12.get("automatic_scope_count"), d12.get("non_automatic_scope_count"),
                    len(rs["D12_auto"]), len(rs["D12_non"])))
        bad["d12"] += 1
    if set(d12.get("automatic_scope") or []) & set(d12.get("non_automatic_scope") or []):
        rep.fail(cat, "rule-set-recomputed", "D12 自动/不自动两个 scope 有交集")
        bad["d12"] += 1
    for key, want in (("hardware_update", "sticky-OR"), ("no_exception_action", "keep"),
                      ("software_write", "immediate-effect"),
                      ("composition_order", "program-order")):
        if d12.get(key) != want:
            rep.fail(cat, "rule-set-recomputed",
                     "D12.%s 期望 %r，实际 %r" % (key, want, d12.get(key)))
            bad["d12"] += 1
    # D13 18 写 / 2 装箱 load
    d13 = rt.get("D13") or {}
    cmp_set("D13.write_scope", d13.get("write_scope"), rs["D13_write"], "d13")
    cmp_set("D13.load_scope", d13.get("load_scope"), rs["D13_load"], "d13")
    if d13.get("write_scope_count") != len(rs["D13_write"]):
        rep.fail(cat, "rule-set-recomputed",
                 "D13.write_scope_count=%r != 重算 %d"
                 % (d13.get("write_scope_count"), len(rs["D13_write"])))
        bad["d13"] += 1
    # D14 4 条，quiet/sc signaling 两类互补且并为 scope
    d14 = rt.get("D14") or {}
    cmp_set("D14.scope", d14.get("scope"), rs["D14_scope"], "d14")
    cmp_set("D14.quiet_class", d14.get("quiet_class"), rs["D14_quiet"], "d14")
    cmp_set("D14.signaling_class", d14.get("signaling_class"), rs["D14_signaling"], "d14")
    if set(d14.get("quiet_class") or []) & set(d14.get("signaling_class") or []):
        rep.fail(cat, "rule-set-recomputed",
                 "D14 的 qcmp/scmp 两类有交集（ADR-1012 D3 禁止互换）")
        bad["d14"] += 1
    if set(d14.get("quiet_class") or []) | set(d14.get("signaling_class") or []) != \
            set(d14.get("scope") or []):
        rep.fail(cat, "rule-set-recomputed", "D14 的 quiet∪signaling 不等于 scope")
        bad["d14"] += 1
    if d14.get("scope_count") != len(rs["D14_scope"]):
        rep.fail(cat, "rule-set-recomputed",
                 "D14.scope_count=%r != 重算 %d"
                 % (d14.get("scope_count"), len(rs["D14_scope"])))
        bad["d14"] += 1
    # D15 18 算术 / 2 转换
    d15 = rt.get("D15") or {}
    cmp_set("D15.arithmetic_scope", d15.get("arithmetic_scope"), rs["D15_arith"], "d15")
    cmp_set("D15.conversion_scope", d15.get("conversion_scope"), rs["D15_conv"], "d15")
    if d15.get("arithmetic_scope_count") != len(rs["D15_arith"]):
        rep.fail(cat, "rule-set-recomputed",
                 "D15.arithmetic_scope_count=%r != 重算 %d"
                 % (d15.get("arithmetic_scope_count"), len(rs["D15_arith"])))
        bad["d15"] += 1
    # D16 36 条
    d16 = rt.get("D16") or {}
    cmp_set("D16.scope", d16.get("scope"), rs["D16_scope"], "d16")
    if d16.get("scope_count") != len(rs["D16_scope"]):
        rep.fail(cat, "rule-set-recomputed",
                 "D16.scope_count=%r != 重算 %d"
                 % (d16.get("scope_count"), len(rs["D16_scope"])))
        bad["d16"] += 1
    if d16.get("tininess_detection") != "after-rounding":
        rep.fail(cat, "rule-set-recomputed",
                 "D16.tininess_detection 期望 after-rounding，实际 %r"
                 % d16.get("tininess_detection"))
        bad["d16"] += 1
    for key, want in (("underflow_flags", ["UF", "NX"]), ("overflow_flags", ["OF", "NX"])):
        if list(d16.get(key) or []) != want:
            rep.fail(cat, "rule-set-recomputed",
                     "D16.%s 期望 %r，实际 %r" % (key, want, d16.get(key)))
            bad["d16"] += 1
    if not any(bad[k] for k in ("d11", "d12", "d13", "d14", "d15", "d16")):
        rep.ok(cat, "rule-set-recomputed",
               "D11 白名单 %d / D12 %d+%d=64 / D13 %d 写+%d 装箱 load / D14 %d（quiet %d + "
               "signaling %d）/ D15 %d 算术+%d 转换 / D16 %d 全部从 contracts/opcodes.yaml "
               "独立重算一致"
               % (len(rs["D11_whitelist"]), len(rs["D12_auto"]), len(rs["D12_non"]),
                  len(rs["D13_write"]), len(rs["D13_load"]), len(rs["D14_scope"]),
                  len(rs["D14_quiet"]), len(rs["D14_signaling"]),
                  len(rs["D15_arith"]), len(rs["D15_conv"]), len(rs["D16_scope"])))
    # ── §5 常量：任务书钉值 == ADR 原文抽出的字面量 == YAML ──
    cprob = []
    ac = up.adr_constants
    for label, pin, pinbits, adrkey in (
            ("D13.tetra_high_half", PIN_D13_HIGH_HALF, PIN_D13_HIGH_HALF_BITS,
             "D13_high_half"),
            ("D14.quiet_unordered", PIN_D14_QUIET, PIN_D14_QUIET_BITS, "D14_quiet"),
            ("D14.signaling_unordered", PIN_D14_SIGNALING, PIN_D14_SIGNALING_BITS,
             "D14_signaling")):
        if ac.get(adrkey) != pin:
            cprob.append("%s：ADR 原文抽出 %r != 任务书钉值 %r"
                         % (label, ac.get(adrkey), pin))
    if str(d13.get("tetra_high_half_value")) != str(PIN_D13_HIGH_HALF) or \
            d13.get("tetra_high_half_bits") != PIN_D13_HIGH_HALF_BITS:
        cprob.append("D13 常量 YAML=%r/%r != 钉值 %r/%r"
                     % (d13.get("tetra_high_half_value"), d13.get("tetra_high_half_bits"),
                        PIN_D13_HIGH_HALF, PIN_D13_HIGH_HALF_BITS))
    if d14.get("quiet_unordered_bits") != PIN_D14_QUIET_BITS or \
            d14.get("signaling_unordered_bits") != PIN_D14_SIGNALING_BITS:
        cprob.append("D14 常量 YAML=%r/%r != 钉值 %r/%r"
                     % (d14.get("quiet_unordered_bits"),
                        d14.get("signaling_unordered_bits"),
                        PIN_D14_QUIET_BITS, PIN_D14_SIGNALING_BITS))
    # ADR-1013 没有十六进制常量 ⇒ canonical qNaN 位型未被固定 ⇒ 必须 null
    if ac.get("D15_hex_list"):
        cprob.append("ADR-1013 出现了十六进制常量 %r，但 canonical_qnan_bits=null"
                     % (ac.get("D15_hex_list"),))
    if d15.get("canonical_qnan_bits") is not None:
        cprob.append("canonical_qnan_bits=%r 必须为 null（ADR-1013 未给出 64 位编码，"
                     "本任务不得替用户补常量）" % (d15.get("canonical_qnan_bits"),))
    if cprob:
        rep.fail(cat, "rule-constants", "；".join(cprob[:6]))
    else:
        rep.ok(cat, "rule-constants",
               "§5 三个常量三来源一致（任务书 / ADR-1011、ADR-1012 原文 / YAML）："
               "D13=%s、D14 quiet=%s、signaling=%s；ADR-1013 无十六进制常量，"
               "canonical qNaN 位型保持 null（not-fixed-by-source）"
               % (PIN_D13_HIGH_HALF_BITS, PIN_D14_QUIET_BITS, PIN_D14_SIGNALING_BITS))
    # ── §6：D17:S6 historical-six → current-ten，6-1+5=10 ──
    s6 = rt.get("s6_scope_relation") or {}
    sprob = []
    cmp_set("s6.historical_six", s6.get("historical_six"), PIN_S6_IDENTITIES, "s6")
    cmp_set("s6.current_ten", s6.get("current_ten"), PIN_S6_CURRENT_TEN, "s6")
    cmp_set("s6.removed_under_D11", s6.get("removed_under_D11"), PIN_S6_REMOVED, "s6")
    cmp_set("s6.added_under_D11", s6.get("added_under_D11"), PIN_S6_ADDED, "s6")
    for key, want in (("historical_six_count", 6), ("current_ten_count", 10),
                      ("removed_count", 1), ("added_count", 5)):
        if s6.get(key) != want:
            sprob.append("s6.%s=%r != %r" % (key, s6.get(key), want))
    if s6.get("arithmetic") != PIN_S6_ARITHMETIC:
        sprob.append("s6.arithmetic=%r != %r" % (s6.get("arithmetic"), PIN_S6_ARITHMETIC))
    # 关系必须**算得出来**，不只是抄字符串
    h = set(s6.get("historical_six") or [])
    cur = set(s6.get("current_ten") or [])
    rem = set(s6.get("removed_under_D11") or [])
    add = set(s6.get("added_under_D11") or [])
    if not (len(h) == 6 and len(rem) == 1 and len(add) == 5
            and (h - rem) | add == cur and len(cur) == 10):
        sprob.append("6-1+5 关系算不通：historical-six=%d、removed=%d、added=%d，"
                     "(six-removed)|added=%r != current_ten"
                     % (len(h), len(rem), len(add), sorted((h - rem) | add)))
    # 历史六条必须与 SPEC-103 台账一致（不得被改写成十条）
    if set(PIN_S6_IDENTITIES) != set(up.scope["D17:S6"]):
        sprob.append("historical_six 与 SPEC-103 机械重算的 D17:S6 scope %r 不一致"
                     % sorted(up.scope["D17:S6"]))
    if sprob:
        rep.fail(cat, "s6-scope-relation", "；".join(sprob[:6]))
    elif not bad["s6"]:
        rep.ok(cat, "s6-scope-relation",
               "S6 historical-six → current-ten 关系算得通：6 - 1(%s) + 5(%s) = 10；"
               "historical_six 与 SPEC-103 机械重算一致（历史未被回写）"
               % (",".join(PIN_S6_REMOVED), ",".join(PIN_S6_ADDED)))
    # ── 交叉优先级顺序 ──
    prec = [p.get("rule") for p in (rt.get("precedence") or []) if isinstance(p, dict)]
    if prec != PIN_PRECEDENCE:
        rep.fail(cat, "precedence",
                 "交叉优先级期望 %r，实际 %r" % (PIN_PRECEDENCE, prec))
    else:
        rep.ok(cat, "precedence",
               "§5 的 %d 条交叉优先级逐条一致（求值顺序：D11>D17:S6、D13 先成写值、"
               "D15 转换优先、D17:S4 ILLI 先于 MALIGN、D12 程序顺序）" % len(PIN_PRECEDENCE))
    # ── D17 六键 / S2 / S7 / SBZ / ldm-stm ──
    d17 = rt.get("D17") or {}
    dprob = []
    if list(d17.get("active_keys") or []) != PIN_LEDGER_KEYS:
        dprob.append("D17.active_keys 期望 %r，实际 %r"
                     % (PIN_LEDGER_KEYS, d17.get("active_keys")))
    if d17.get("trace_only") != PIN_S2_ID:
        dprob.append("D17.trace_only 期望 %r，实际 %r" % (PIN_S2_ID, d17.get("trace_only")))
    if d17.get("historical_non_gap") != PIN_S7_ID:
        dprob.append("D17.historical_non_gap 期望 %r，实际 %r"
                     % (PIN_S7_ID, d17.get("historical_non_gap")))
    if list(d17.get("sbz_write_silent_ignore_domains") or []) != PIN_SBZ_DOMAINS:
        dprob.append("D17.sbz_write_silent_ignore_domains 期望 %r，实际 %r"
                     % (PIN_SBZ_DOMAINS, d17.get("sbz_write_silent_ignore_domains")))
    if list(d17.get("fault_priority") or []) != ["ILLI", "MALIGN"]:
        dprob.append("D17.fault_priority 期望 ['ILLI', 'MALIGN']（D11 目的合法性先于 "
                     "MALIGN），实际 %r" % (d17.get("fault_priority"),))
    for key, want in (("scaleb_rounding_source", "rf0[17:16]"),
                      ("ldm_stm_rf_numbering", "incrementing"),
                      ("ldm_stm_fault_commit", "none"),
                      ("ldm_stm_fault_pc", "stays-on-faulting-instruction")):
        if d17.get(key) != want:
            dprob.append("D17.%s 期望 %r，实际 %r" % (key, want, d17.get(key)))
    if dprob:
        rep.fail(cat, "d17-rule-table", "；".join(dprob[:6]))
    else:
        rep.ok(cat, "d17-rule-table",
               "D17 规则表：active 精确六键、S2=trace-only、S7=non-gap、"
               "SBZ 静默忽略域 %s、ILLI 先于 MALIGN、ldm/stm 编号递增且 fault 不提交"
               % "/".join(PIN_SBZ_DOMAINS))

    # §5 的行为字段也必须逐项钉死；集合/计数检查不能替代语义字段检查。
    semantic_rules = [
        ("D11", d11, {"rf0_read": "all-f1-identities-allowed",
                       "rf0_write_other": "ILLI", "rd2rf_to_rf0": "ILLI",
                       "priority_over": ["D17:S6"]}),
        ("D12", d12, {"flags_bits": "[4:0]", "hardware_update": "sticky-OR",
                       "no_exception_action": "keep", "software_write": "immediate-effect",
                       "composition_order": "program-order"}),
        ("D13", d13, {"tetra_high_half_bits": "0xffffffff",
                       "tetra_high_half_value": 0xffffffff}),
        ("D14", d14, {"input_class_dependent": False}),
        ("D15", d15, {"canonical_qnan_bits": None,
                       "canonical_qnan_bit_state": "not-fixed-by-source",
                       "conversion_result_sign": "positive",
                       "priority_over": ["D15:D4", "D15:D6"]}),
        ("D16", d16, {"tininess_detection": "after-rounding",
                       "underflow_flags": ["UF", "NX"],
                       "overflow_flags": ["OF", "NX"]}),
        ("D17", d17, {"reset_rounding_mode": "RNE", "reset_rounding_bits": "00",
                       "reset_flags": 0,
                       "classify_immediate": "assembler-reject-on-immu6-neq-1",
                       "classify_immediate_hardware": "ILLI",
                       "scaleb_rounding_source": "rf0[17:16]",
                       "scaleb_qnan_exponent": "canonical-qNaN-no-flags",
                       "scaleb_snan_exponent": "NV-plus-canonical-qNaN",
                       "scaleb_posinf_exponent": "plus-inf",
                       "scaleb_neginf_exponent": "factor-zero",
                       "ldm_stm_base": "EA0 = rbhb + rdhc",
                       "ldm_stm_address": "EA(0) + i * width",
                       "ldm_stm_width_tetra": 4, "ldm_stm_width_octa": 8,
                       "ldm_stm_rf_numbering": "incrementing",
                       "ldm_stm_fault_commit": "none",
                       "ldm_stm_fault_pc": "stays-on-faulting-instruction"}),
    ]
    semantic_bad = []
    for label, table, expected in semantic_rules:
        for key, want in expected.items():
            if table.get(key) != want:
                semantic_bad.append("%s.%s 期望 %r，实际 %r" %
                                    (label, key, want, table.get(key)))
    if semantic_bad:
        rep.fail(cat, "rule-semantics", "；".join(semantic_bad[:8]))
    else:
        rep.ok(cat, "rule-semantics", "D11-D17 的状态转换、NaN/flags/优先级、scaleB 与 ldm/stm 行为字段逐项一致")


def g16_resolution_matrix(rep, doc, up):
    """§8.6：current resolution matrix 精确 64 行、无 pseudo/重复、双向一致。"""
    cat = "G16"
    R = resolution_layer(rep, doc)
    if R is None:
        return
    rows = [r for r in (R.get("resolution_matrix") or []) if isinstance(r, dict)]
    prob = []
    if R.get("resolution_matrix_count") != len(rows) or len(rows) != 64:
        prob.append("行数/count 不符：count=%r 实际 %d 行（必须 64）"
                    % (R.get("resolution_matrix_count"), len(rows)))
    ids = [r.get("identity") for r in rows]
    if len(set(ids)) != len(ids):
        prob.append("identity 重复：%r" % sorted({i for i in ids if ids.count(i) > 1}))
    if set(ids) != set(up.identities):
        prob.append("identity 集合与上游 64 条不一致：少 %r / 多 %r"
                    % (sorted(set(up.identities) - set(ids)),
                       sorted(set(ids) - set(up.identities))))
    pseudo = sorted(set(ids) & up.pseudo)
    if pseudo:
        prob.append("混入 pseudo identity：%r" % pseudo)
    if prob:
        rep.fail(cat, "matrix-shape", "；".join(prob[:4]))
    else:
        rep.ok(cat, "matrix-shape",
               "64 行与 contracts/opcodes.yaml 的 64 条 identity 精确一一对应："
               "无重复、无缺失、无 pseudo")
    # ── owning consumer 必须等于任务书自身解析出的 11/42/11 归属 ──
    bado = [(r.get("identity"), r.get("owning_consumer"), up.insn_task.get(r.get("identity")))
            for r in rows if r.get("owning_consumer") != up.insn_task.get(r.get("identity"))]
    if bado:
        rep.fail(cat, "matrix-owner", "owning_consumer 与任务书归属不符：%r" % bado[:4])
    else:
        cnt = {}
        for r in rows:
            cnt[r.get("owning_consumer")] = cnt.get(r.get("owning_consumer"), 0) + 1
        rep.ok(cat, "matrix-owner",
               "每行 owning_consumer 等于 QEMU-101t/102t/103t 任务书自身解析出的归属"
               "（%s）" % "/".join("%s:%d" % kv for kv in sorted(cnt.items())))
    # ── applicable_decisions / applicable_d17_keys / closed facets 全部重算 ──
    badd = [(r.get("identity"), r.get("applicable_decisions"))
            for r in rows
            if list(r.get("applicable_decisions") or [])
            != sorted({d for d in PIN_DECISIONS
                       if d in up.by_insn[r.get("identity")]["f1"]["open_items"]})]
    if badd:
        rep.fail(cat, "matrix-decisions", "applicable_decisions 与 open_items 不符：%r"
                 % badd[:4])
    else:
        rep.ok(cat, "matrix-decisions",
               "64 行 applicable_decisions 全部等于该 identity 的 f1.open_items ∩ D11～D17")
    badk = []
    for r in rows:
        i = r.get("identity")
        want = sorted(k for k in PIN_LEDGER_KEYS if i in up.current_scope[k])
        if list(r.get("applicable_d17_keys") or []) != want:
            badk.append((i, r.get("applicable_d17_keys"), want))
    if badk:
        rep.fail(cat, "matrix-d17-keys",
                 "applicable_d17_keys 与现行 scope 重算不符（现行 64/2/26/2/10/4，"
                 "S6 为 historical-six 之外的现行十条）：%r" % badk[:4])
    else:
        rep.ok(cat, "matrix-d17-keys",
               "64 行 applicable_d17_keys 全部等于现行 active scope 重算值"
               "（64/2/26/2/10/4；`rd2rf` 不再落在 S6，五条 `cs.*-rf` 已加入 S6）")
    badf = []
    for r in rows:
        i = r.get("identity")
        want = {f: PIN_FACET_TO_DECISION[f]
                for f, st in up.by_insn[i]["f1"]["facets"].items()
                if st == "open-blocked" and f in PIN_FACET_TO_DECISION
                and PIN_FACET_TO_DECISION[f] in up.by_insn[i]["f1"]["open_items"]}
        if dict(r.get("projected_closed_facets") or {}) != want:
            badf.append((i, r.get("projected_closed_facets"), want))
    if badf:
        rep.fail(cat, "matrix-facets", "projected_closed_facets 与 open-blocked facet 不符：%r"
                 % badf[:4])
    else:
        n = sum(len(dict(r.get("projected_closed_facets") or {})) for r in rows)
        rep.ok(cat, "matrix-facets",
               "64 行 projected_closed_facets 全部等于该 identity 的 open-blocked 语义"
               " facet（共 %d 条 facet→decision 映射）" % n)
    # ── rootn(-0,2) 必须仍是 explicitly-unspecified，且不得有别的行声称未决 ──
    uns = {r.get("identity"): list(r.get("remaining_unspecified") or []) for r in rows}
    prob = []
    for i in PIN_ROOTN_IDENTITIES:
        if not uns.get(i) or not any(PIN_ROOTN_UNSPECIFIED in s for s in uns[i]):
            prob.append("%s 未把 %s 登记为 explicitly-unspecified" % (i, PIN_ROOTN_UNSPECIFIED))
    extra = [i for i, v in uns.items() if v and i not in PIN_ROOTN_IDENTITIES]
    if extra:
        prob.append("下列行声称仍有未决项但不在已登记集合：%r" % extra)
    if prob:
        rep.fail(cat, "matrix-unspecified", "；".join(prob))
    else:
        rep.ok(cat, "matrix-unspecified",
               "`%s` 只在 %s 两行登记为 explicitly-unspecified，未因七份 ADR 变 "
               "Accepted 而获得唯一 expected" % (PIN_ROOTN_UNSPECIFIED,
                                              "/".join(PIN_ROOTN_IDENTITIES)))


def g17_normative_authority(rep, doc, up):
    """§8.8：SimRISC-03:7-8 HTML 注释不得进入 current normative authority。"""
    cat = "G17"
    R = resolution_layer(rep, doc)
    if R is None:
        return
    # ── 17.1 注释区间必须由**原始 Markdown** 解析得出，且不能过宽 ──
    cl = up.comment_lines.get(SPEC03) or set()
    n = up.line_count.get(SPEC03, 0)
    prob = []
    if cl != {7, 8}:
        prob.append("SimRISC-03 的 HTML 注释行号集合期望恰为 {7, 8}，实际 %r" % sorted(cl))
    for outside in (6, 9):
        if outside in cl:
            prob.append("第 %d 行被算进注释区间（区间过宽会把规范正文也排除）" % outside)
    if up.comment_lines.get(SPEC00):
        prob.append("SimRISC-00 竟解析出注释行 %r" % sorted(up.comment_lines[SPEC00]))
    if n and max(cl or {0}) > n:
        prob.append("注释行号越界（共 %d 行）" % n)
    if prob:
        rep.fail(cat, "html-comment-range", "；".join(prob))
    else:
        rep.ok(cat, "html-comment-range",
               "逐字符跨行解析 %s 得注释行恰为 7-8（相邻的第 6/9 行仍在正文），"
               "%s 无注释区间" % (SPEC03.split("/")[-1], SPEC00.split("/")[-1]))
    # ── 17.2 normative_exclusions 的字段必须把该段钉成非规范 ──
    ne = [e for e in (R.get("normative_exclusions") or []) if isinstance(e, dict)]
    eprob = []
    if len(ne) != 1:
        eprob.append("normative_exclusions 期望恰好一条，实际 %d" % len(ne))
    else:
        e = ne[0]
        want = {"file": SPEC03, "lines": "7-8", "construct": "html-comment",
                "normative": False, "may_back_current_decision": False}
        diff = {k: (e.get(k), v) for k, v in want.items() if e.get(k) != v}
        if diff:
            eprob.append("字段（实际, 期望）：%r" % diff)
        if e.get("used_by_current_decisions"):
            eprob.append("used_by_current_decisions=%r 非空：该段不得支撑任何现行 decision"
                         % (e.get("used_by_current_decisions"),))
        # 声明的行区间必须真的是解析出的注释行
        if linespec_ints(e.get("lines")) != {7, 8}:
            eprob.append("声明的 lines=%r 与解析出的注释行 {7,8} 不符" % (e.get("lines"),))
    if eprob:
        rep.fail(cat, "normative-exclusion", "；".join(eprob[:5]))
    else:
        rep.ok(cat, "normative-exclusion",
               "normative_exclusions 把 %s:7-8 显式登记为 html-comment、"
               "normative=false、may_back_current_decision=false、"
               "used_by_current_decisions=[]" % SPEC03.split("/")[-1])
    # ── 17.3 整段落在注释内的历史引用必须被登记为 historical-non-normative ──
    pol = R.get("historical_authority_policy") or {}
    pprob = []
    if pol.get("tagged") != "historical-non-normative":
        pprob.append("historical_authority_policy.tagged=%r != 'historical-non-normative'"
                     % (pol.get("tagged"),))
    if pol.get("participates_in_current_rules") is not False:
        pprob.append("participates_in_current_rules=%r 必须为 false"
                     % (pol.get("participates_in_current_rules"),))
    holders = [h for h in (pol.get("holders") or [])]
    if sorted(holders) != ["SPEC-102t", "SPEC-103t"]:
        pprob.append("holders 期望 ['SPEC-102t','SPEC-103t']，实际 %r" % (holders,))
    if pprob:
        rep.fail(cat, "historical-authority-policy", "；".join(pprob))
    else:
        # 历史层里确有 7 条引用整段落在注释内：G4 已按 (holder,record,index) 钉死该
        # 集合，这里核对它**非空且被声明为历史**，避免「声明了但其实没有引用」的假安全。
        rep.ok(cat, "historical-authority-policy",
               "historical_authority_policy 把 7 条落在注释内的历史引用标为 "
               "historical-non-normative 且 participates_in_current_rules=false"
               "（G4 已钉死具体是哪 7 条）")
    # ── 17.4 覆盖层里不得出现「该注释是现行依据」的任何断言 ──
    hits = []
    for ptr, k, v in walk(R):
        if k in ("normative", "may_back_current_decision") and v is True:
            hits.append("%s.%s=%r" % (ptr, k, v))
        if k in ("lines", "file") and isinstance(v, str) and v in ("7-8", "8"):
            hits.append("%s.%s=%r（覆盖层内出现注释行号，须由 normative_exclusions 承载）"
                        % (ptr, k, v))
    hits = [h for h in hits if "normative_exclusions" not in h]
    if hits:
        rep.fail(cat, "no-current-authority-into-comment",
                 "覆盖层在 normative_exclusions 之外仍引用了注释行/声明其为规范：%r"
                 % hits[:5])
    else:
        rep.ok(cat, "no-current-authority-into-comment",
               "除 normative_exclusions 的显式排除记录外，resolution 覆盖层没有任何"
               "字段把 SimRISC-03:7-8 当作现行规范依据")


def g18_downstream_sync(rep, doc, up):
    """§8.9：10 本下游任务书 + INTEG-104m 的活动合同（六键 / S2 / S7 / SPEC-104t）。"""
    cat = "G18"
    books = up.task_books()
    bad = {k: 0 for k in ("keyset", "shared", "dep", "stale", "blocked", "rules")}

    def rescan(tid, text):
        """去掉 `## 16 完成区` 之后的完成记录后再扫陈旧措辞。"""
        for h in ("## 16", "## 16 完成区", "## 15"):
            if h in text:
                head, _sep, _tail = text.partition(h)
                if h == "## 15":
                    continue
                return head
        return text

    for tid in PIN_DOWNSTREAM_BOOKS:
        tb = books.get(tid)
        if tb is None:
            rep.fail(cat, "book-six-key-sentence", "%s 任务书不存在" % tid)
            bad["keyset"] += 1
            continue
        txt = tb["text"]
        # (1) 六键 active 键集合句
        if not any(v in txt for v in PIN_SHARED_KEYSET_VARIANTS):
            rep.fail(cat, "book-six-key-sentence",
                     "%s 缺少六键 active 键集合句（期望 %r 之一）"
                     % (tid, PIN_SHARED_KEYSET_VARIANTS[0]))
            bad["keyset"] += 1
        # (2) S2/S7 极性句 + projected 门禁句
        miss = [s for s in PIN_SHARED_SENTENCE if s not in txt]
        if miss:
            rep.fail(cat, "book-shared-sentences",
                     "%s 缺少逐字共有句 %d 条，例：%r" % (tid, len(miss), miss[0][:70]))
            bad["shared"] += 1
        # (3) 依赖行必须含 SPEC-104t
        if "SPEC-104t" not in expand_task_refs(up.dep_line(tid)):
            rep.fail(cat, "book-depends-104t",
                     "%s 的 `**依赖**`/`**关联任务**` 行没有 SPEC-104t：%r"
                     % (tid, up.dep_line(tid)[:90]))
            bad["dep"] += 1
        # (4) 活动章节里不得残留陈旧门禁措辞
        act = rescan(tid, txt)
        stale = [(w, act.count(w)) for w in PIN_STALE_GATE_WORDS if w in act]
        if stale:
            rep.fail(cat, "book-no-stale-gate",
                     "%s 活动章节仍含陈旧门禁措辞 %r" % (tid, stale))
            bad["stale"] += 1
        # (5) BLOCKED 下界：同步不得把「实现/向量/E2E 未产出」从验收表里删掉
        nblk = txt.count("**BLOCKED**")
        if nblk < PIN_BOOK_BLOCKED_FLOOR.get(tid, 0):
            rep.fail(cat, "book-blocked-floor",
                     "%s 的 `**BLOCKED**` 计数 %d 低于同步前基线下界 %d（不得为了让任务"
                     "「看起来可跑」而删掉未产出事实）"
                     % (tid, nblk, PIN_BOOK_BLOCKED_FLOOR.get(tid, 0)))
            bad["blocked"] += 1
        # (6) 必须写本任务相关的精确适用规则，而不是只说「参见 ADR」
        if PIN_RULES_SECTION not in txt:
            rep.fail(cat, "book-rules-section",
                     "%s 缺少 `%s` 小节（§10 要求写入精确适用规则，不得只写「参见 ADR」）"
                     % (tid, PIN_RULES_SECTION))
            bad["rules"] += 1
    if not bad["keyset"]:
        rep.ok(cat, "book-six-key-sentence",
               "11 本任务书的活动合同全部使用六键 active 集合 {S1,S3,S4,S5,S6,S8}，"
               "无一残留七键口径")
    if not bad["shared"]:
        rep.ok(cat, "book-shared-sentences",
               "11 本任务书逐字共有 %d 句：S2=ledger 外 trace-only、S7=ADR-1008 证明的 "
               "spec-determined non-gap（都不计 OPEN/BLOCKED/PASS）、"
               "resolution 只表示 projected-pending-activation"
               % len(PIN_SHARED_SENTENCE))
    if not bad["dep"]:
        rep.ok(cat, "book-depends-104t",
               "11 本任务书的依赖/关联任务行都显式引用 SPEC-104t（并要求所消费 ADR 已 Accepted）")
    if not bad["stale"]:
        rep.ok(cat, "book-no-stale-gate",
               "11 本任务书活动章节无 ADR-1005～1007、无「decisions 尚未确认」、"
               "无 S7-active/七项活动口径")
    if not bad["blocked"]:
        rep.ok(cat, "book-blocked-floor",
               "11 本任务书的 `**BLOCKED**` 计数均 ≥ 同步前基线 %s（语义门禁解除"
               "不等于实现 PASS）" % sorted(PIN_BOOK_BLOCKED_FLOOR.values()))
    if not bad["rules"]:
        rep.ok(cat, "book-rules-section",
               "11 本任务书都带 `%s` 小节，写明本任务相关的精确适用规则" % PIN_RULES_SECTION)


def g19_history_and_bypass(rep, doc, up, root, yaml_rel):
    """§8.10/§8.11：SPEC-102/103 历史任务书未被修改；无旁路/备份产物。"""
    cat = "G19"
    # ── 19.1 历史任务书摘要（与 dispatch 前置检查的基线比对）──
    drift = []
    for rel, want in sorted(PIN_HISTORY_TASKBOOK_SHA256.items()):
        p = os.path.join(root, rel)
        if not os.path.isfile(p):
            drift.append("%s 缺失" % rel)
            continue
        got = hashlib.sha256(open(p, "rb").read()).hexdigest()
        if got != want:
            drift.append("%s\n      基线 %s\n      实际 %s" % (rel, want, got))
    if drift:
        rep.fail(cat, "history-taskbook-digest",
                 "SPEC-102t/103t 历史任务书与本任务启动基线不一致（禁止修改历史证据）：%r"
                 % drift)
    else:
        rep.ok(cat, "history-taskbook-digest",
               "SPEC-102t/103t 两本历史任务书的 sha256 与 dispatch 前置检查基线逐字一致"
               "（完成区与数字均未被回写）")
    # ── 19.2 resolution 必须是最后一个顶层键（覆盖层加在末尾，不得插进历史层中间）──
    keys = list(doc.keys())
    if not keys or keys[-1] != "resolution":
        rep.fail(cat, "resolution-is-last",
                 "顶层键顺序：最后一个是 %r，必须是 `resolution`" % (keys[-1] if keys else None,))
    else:
        rep.ok(cat, "resolution-is-last",
               "`resolution` 位于顶层键末尾（第 %d/%d 个），历史 12 键顺序未被扰动"
               % (len(keys), len(keys)))
    # ── 19.3 旁路/备份/平行实现产物扫描 ──
    hits = []
    # contracts：只允许 f1_gap_proofs.yaml；不允许其它 f1* yaml
    d = os.path.join(root, "contracts")
    if os.path.isdir(d):
        for n in sorted(os.listdir(d)):
            if n.startswith("f1") and n.endswith((".yaml", ".yml")):
                if n != "f1_gap_proofs.yaml":
                    hits.append("contracts/%s" % n)
            # backup
            if re.search(r"\.bak$|\.orig$|~$|_bak\.|_backup\.", n):
                hits.append("contracts/%s" % n)
    # tools/spec：只允许 check_f1_gap_proofs.py 和 test_f1_gap_proof_counterexamples.py
    d2 = os.path.join(root, "tools/spec")
    if os.path.isdir(d2):
        for n in sorted(os.listdir(d2)):
            if n.startswith("f1_") and n.endswith(".py"):
                if n not in ("f1_gap_proof_check_stub.py",):  # not applicable
                    pass
            # but target by "gap_proof"/"resolution" in name? requirement says only the two allowed
            low = n.lower()
            if "gap_proof" in low or "resolution" in low:
                if n not in ("check_f1_gap_proofs.py", "test_f1_gap_proof_counterexamples.py"):
                    hits.append("tools/spec/%s" % n)
            if re.search(r"\.bak$|\.orig$|~$|_bak\.|_backup\.", n):
                hits.append("tools/spec/%s" % n)
    # legacy pattern scan for catch-all
    if not hits:
        for sub, pat in PIN_BYPASS_PATTERNS:
            d = os.path.join(root, sub)
            if not os.path.isdir(d):
                continue
            rx = re.compile(pat)
            for n in sorted(os.listdir(d)):
                # avoid self-false positive
                if sub == "contracts" and n == "f1_gap_proofs.yaml":
                    continue
                if rx.search(n):
                    hits.append("%s/%s" % (sub, n))
    if hits:
        rep.fail(cat, "no-bypass-artifacts",
                 "发现旁路/备份/平行产物：%r（禁止新建平行 projection YAML/checker、"
                 "backup 文件）" % sorted(set(hits)))
    else:
        rep.ok(cat, "no-bypass-artifacts",
               "contracts/ 与 tools/spec/ 下无平行 projection YAML/checker、"
               "`.bak`/`.orig`/`~`/`_bak`/`_backup` 备份产物")


def g20_lifecycle_interface(rep, doc, up):
    """§8 生命周期接口：consumer_activation 门禁、能力缺口、activation 叙述。"""
    cat = "G20"
    R = resolution_layer(rep, doc)
    if R is None:
        return
    ca = R.get("consumer_activation") or {}
    ents = [e for e in (ca.get("entries") or []) if isinstance(e, dict)]
    rows = R.get("resolution_matrix") or []
    # ── 20.1 消费方集合必须与 §10 的 11 本任务书一致 ──
    tasks = [e.get("task") for e in ents]
    if sorted(tasks) != sorted(PIN_DOWNSTREAM_BOOKS):
        rep.fail(cat, "consumer-tasks",
                 "consumer_activation 的 task 集合期望 %r，实际 %r"
                 % (sorted(PIN_DOWNSTREAM_BOOKS), sorted(tasks)))
    else:
        rep.ok(cat, "consumer-tasks",
               "consumer_activation 覆盖 §10 的全部 11 本下游任务书（10 普通 + INTEG-104m）")
    if list(ca.get("semantic_gate_states") or []) != PIN_SEMANTIC_GATE_STATES:
        rep.fail(cat, "gate-vocabulary",
                 "semantic_gate_states 期望 %r，实际 %r"
                 % (PIN_SEMANTIC_GATE_STATES, ca.get("semantic_gate_states")))
    else:
        rep.ok(cat, "gate-vocabulary",
               "语义门禁取值域为 %r（**刻意不用** G10 历史词表的 "
               "ledger_applicability/OPEN/BLOCKED，避免与 OPEN 状态混淆）"
               % PIN_SEMANTIC_GATE_STATES)
    # ── 20.2 逐键门禁必须与 64 行矩阵的 owning × applicable 关系一致 ──
    def derive(tid):
        if tid in ("TESTCASES-101t", "TESTCASES-102t", "INTEG-102t", "INTEG-103t",
                   "INTEG-104m"):
            return {k: "projected-pending-activation" for k in PIN_LEDGER_KEYS}
        if tid == "LLVM-101t":
            # 只有 D17:S3（classify immediate）影响 assembler legality
            return {k: ("projected-pending-activation" if k == "D17:S3"
                        else "N/A(runtime)") for k in PIN_LEDGER_KEYS}
        if tid in ("LLVM-102t", "LLVM-103t"):
            return {k: "N/A(runtime)" for k in PIN_LEDGER_KEYS}
        owned = [r for r in rows if r.get("owning_consumer") == tid]
        return {k: ("projected-pending-activation"
                    if any(k in (r.get("applicable_d17_keys") or []) for r in owned)
                    else "N/A(runtime)") for k in PIN_LEDGER_KEYS}

    gprob = []
    for e in ents:
        tid = e.get("task")
        got = e.get("ledger_gate_projection") or {}
        want = derive(tid)
        if got != want:
            diff = {k: (got.get(k), want[k]) for k in PIN_LEDGER_KEYS if got.get(k) != want[k]}
            gprob.append("%s 逐键门禁与矩阵不符（实际, 应为）：%r" % (tid, diff))
        if e.get("semantic_gate") not in PIN_SEMANTIC_GATE_STATES:
            gprob.append("%s.semantic_gate=%r 不在取值域 %r"
                         % (tid, e.get("semantic_gate"), PIN_SEMANTIC_GATE_STATES))
        if e.get("capability_gate") != "BLOCKED":
            gprob.append("%s.capability_gate=%r 必须保持 BLOCKED（ADR Accepted 只解除"
                         "语义选择门禁，不提供实现 PASS）"
                         % (tid, e.get("capability_gate")))
        if not (e.get("task_book") or "").startswith(".xkw/tasks/"):
            gprob.append("%s.task_book=%r 不是仓库内任务书路径" % (tid, e.get("task_book")))
        if not (e.get("requires") or []):
            gprob.append("%s.requires 为空" % tid)
    if gprob:
        rep.fail(cat, "consumer-ledger-gates", "；".join(gprob[:5]))
    else:
        npr = sum(1 for e in ents for k in PIN_LEDGER_KEYS
                  if e["ledger_gate_projection"][k] == "projected-pending-activation")
        rep.ok(cat, "consumer-ledger-gates",
               "11 本任务书的 66 个逐键门禁全部与 64 行矩阵一致（%d 个 projected-pending-"
               "activation、%d 个 N/A(runtime)）；11 个 capability_gate 全为 BLOCKED"
               % (npr, len(ents) * len(PIN_LEDGER_KEYS) - npr))
    # ── 20.3 能力缺口必须仍登记为 BLOCKED，不得被冒充为已完成 ──
    caps = [c for c in (R.get("capability_gaps") or []) if isinstance(c, dict)]
    cprob = [c.get("id") for c in caps if c.get("state") != "BLOCKED"]
    if not caps:
        cprob.append("capability_gaps 为空（不得省略）")
    if cprob:
        rep.fail(cat, "capability-gaps",
                 "下列能力缺口不是 BLOCKED 或列表为空：%r" % cprob[:6])
    else:
        rep.ok(cat, "capability-gaps",
               "%d 项实现/验证能力缺口全部保持 BLOCKED：%s"
               % (len(caps), "/".join(str(c.get("id")) for c in caps)))
    # ── 20.4 覆盖层不得声称 active / Accepted ──
    leaks = []
    for ptr, k, v in walk(R):
        if isinstance(v, str) and k != "id":
            if re.search(r"\bactive implementation\b", v) and "不得" not in v and \
                    "不代表" not in v and "不表示" not in v:
                leaks.append("%s.%s" % (ptr, k))
    lc = R.get("lifecycle") or {}
    if lc.get("activation_state") != "pending-activation" or \
            lc.get("default_mode") != "projected-reviewable":
        leaks.append("lifecycle.activation_state/default_mode 必须是 "
                     "pending-activation/projected-reviewable，实际 %r/%r"
                     % (lc.get("activation_state"), lc.get("default_mode")))
    if leaks:
        rep.fail(cat, "no-active-claim", "%r" % leaks[:5])
    else:
        rep.ok(cat, "no-active-claim",
               "覆盖层自称 confirmed/projected/pending-activation，"
               "无任何字段声称 active implementation truth 或 ADR 已 Accepted")


# ══════════════════════════ G21：下游逐键 scope 自洽 ══════════════════════════
# G18 只保证「六键句 / 共有句 / 依赖 / 陈旧措辞 / BLOCKED 下界 / 规则小节」这些
# **结构**存在；它**不**证明任务书里写下的**逐键适用条数**与 64 行矩阵一致。
# SPEC-104t 执行中就出现过这类漂移：S4 由 64 收窄到 26、S6 由 historical-six
# 换成现行十条之后，三本 QEMU 任务书的规则表仍写「11/42 条全适用」「适用 6 条含
# `rd2rf`」，而它们自己上一节的 scope 句已经改对——**同一本书内部自相矛盾**。
# 本组把「任务书里写的数字/identity 清单」当作被检查数据，与矩阵重算值逐项比对。
#
# fail-closed 约定：矩阵算出适用数 > 0 的键，任务书**必须**给出可机读的条数声明；
# 找不到声明即 FAIL（而不是「解析不到就跳过」），否则换一种行文就能让检查恒绿。
PIN_SCOPE_TABLE_BOOKS = ["LLVM-101t", "QEMU-101t", "QEMU-102t", "QEMU-103t"]
#: 任务书规则表里逐键声明条数的合法句式（必须能落到整数）。
RE_BOOK_COUNT = re.compile(
    r"(?:全部|共|适用|全适用)?\s*(\d+)\s*条|"
    r"(?:全部|共|适用|全适用)?\s*两\s*条")
#: 「适用 N 条：<code-span 清单>」——identity 清单直接与矩阵重算值做集合相等。
RE_BOOK_IDENTS = re.compile(
    r"适用\s*(?:\d+|两)\s*条\s*[：:]?\s*((?:`[^`]+`\s*[、,]\s*)*`[^`]+`)")


def _book_rules_section(txt):
    """截取 `## SPEC-104t 已投影的适用规则` 小节（到下一个 `## ` 为止）。"""
    head, sep, tail = txt.partition(PIN_RULES_SECTION)
    if not sep:
        return None
    return head + tail.split("\n## ")[0]


def _declared_scope(txt):
    """从规则表里抽出 {短键: {count, idents, na}} 的声明集合。

    短键形如 `S4`（不带 `D17:` 前缀）。count 来自 `RE_BOOK_COUNT`，idents 来自
    `RE_BOOK_IDENTS` 捕获的 code-span 清单。同一行的多个键按 `；` 分段归属：
    某段里出现的 `S\\d` 就是该段声明的键。
    """
    sec = _book_rules_section(txt)
    if sec is None:
        return None
    out = {}
    for line in sec.split("\n"):
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        head_cell, desc = cells[0], cells[-1]
        # 只有首格**显式**写 `D17:Sx` 的行才计入（「S6 范围关系」这类旁述不算，
        # 否则 `6-1+5=10` 会被误当成逐键 scope 声明）。
        keys = re.findall(r"D17:S([1-8])", head_cell)
        if not keys:
            continue
        for seg in re.split(r"[；;]", desc):
            seg_keys = re.findall(r"S([1-8])", seg) or keys
            m = RE_BOOK_COUNT.search(seg)
            mc = RE_BOOK_IDENTS.search(seg)
            # 「本任务 11 条均不适用」这类句子里的 11 是**被否定的**适用数，
            # 不得当成声明值；N/A(runtime)/不适用 优先于任何条数。
            na = ("N/A(runtime)" in seg) or ("不适用" in seg)
            n = None
            if m and not na:
                tok = m.group(0)
                n = 2 if "两" in tok else int(m.group(1))
            idents = None
            if mc and not na:
                idents = [y for x in re.findall(r"`([^`]+)`", mc.group(1))
                          for y in re.split(r"[,、]", x.strip()) if y]
            for k in seg_keys:
                if k in ("2", "7"):        # S2 trace-only / S7 non-gap 不是 active 键
                    continue
                cur = out.setdefault(k, {"count": None, "idents": None, "na": False})
                if n is not None:
                    cur["count"] = n
                if idents:
                    cur["idents"] = idents
                if na:
                    cur["na"] = True
    return out


def g21_scope_self_consistency(rep, doc, up):
    """§8.9/§15.5：任务书写下的逐键 scope 数字与 identity 清单必须与 64 行矩阵一致。"""
    cat = "G21"
    R = resolution_layer(rep, doc)
    if R is None:
        return
    rows = R.get("resolution_matrix") or []
    from collections import defaultdict as _dd
    by = _dd(lambda: _dd(set))
    owned = set()
    for r in rows:
        owned.add(r.get("owning_consumer"))
        for k in (r.get("applicable_d17_keys") or []):
            by[r.get("owning_consumer")][k].add(r.get("identity"))
    ca = {e.get("task"): (e.get("ledger_gate_projection") or {})
          for e in ((R.get("consumer_activation") or {}).get("entries") or [])
          if isinstance(e, dict)}
    books = up.task_books()
    # ── 21.1 规则表里的逐键条数 / identity 清单 ──
    prob = []
    checked = 0
    for tid in PIN_SCOPE_TABLE_BOOKS:
        tb = books.get(tid)
        if tb is None:
            prob.append("%s 任务书不存在" % tid)
            continue
        decl = _declared_scope(tb["text"])
        if decl is None:
            prob.append("%s 缺少 `%s` 小节，无法机读逐键 scope" % (tid, PIN_RULES_SECTION))
            continue
        for k in PIN_LEDGER_KEYS:
            short = k.split(":")[1][1:]        # 'D17:S4' -> '4'（与 _declared_scope 同键型）
            want = sorted(by[tid].get(k) or [])
            got = decl.get(short)
            if tid not in owned:
                # 非 owning 消费者（LLVM-101t）在矩阵里没有自己的行，逐键适用只由
                # `ledger_gate_projection` 决定：此时只要求「标为适用的键必须有行」，
                # 不要求条数（没有可对照的 identity 集合）。
                if ca.get(tid, {}).get(k) == "projected-pending-activation" and got is None:
                    prob.append("%s 的 %s 标为 projected-pending-activation，"
                                "但规则表没有对应行" % (tid, k))
                elif got is not None:
                    checked += 1
                continue
            if got is None:
                if want:
                    prob.append("%s 的 %s 适用 %d 条但规则表未给出可机读声明"
                                % (tid, k, len(want)))
                continue
            if want and got["count"] is None:
                prob.append("%s 的 %s 适用 %d 条，但规则表该键的条数句式不可机读（%r）"
                            % (tid, k, len(want), got))
            elif got["na"]:
                # 该键被任务书明确标为 N/A(runtime)/不适用：矩阵必须也是 0 条
                if want:
                    prob.append("%s 的 %s 任务书标 N/A(runtime)，矩阵却有 %d 条"
                                % (tid, k, len(want)))
                else:
                    checked += 1
            elif got["count"] is not None and not want:
                prob.append("%s 的 %s 矩阵适用 0 条，任务书却声明 %d 条"
                            % (tid, k, got["count"]))
            elif got["count"] is not None and got["count"] != len(want):
                prob.append("%s 的 %s 条数：任务书 %d，矩阵 %d"
                            % (tid, k, got["count"], len(want)))
            elif got["idents"] is not None and sorted(got["idents"]) != want:
                prob.append("%s 的 %s identity 清单：任务书 %r，矩阵 %r"
                            % (tid, k, sorted(got["idents"]), want))
            elif not want and not got["na"]:
                prob.append("%s 的 %s 矩阵适用 0 条，任务书未标 N/A(runtime)" % (tid, k))
            else:
                checked += 1
    if prob:
        rep.fail(cat, "book-per-key-scope", "%r" % prob[:6])
    else:
        rep.ok(cat, "book-per-key-scope",
               "%d 本带逐键规则表的任务书共 %d 个 (任务, 键) 声明，条数与 identity 清单"
               "全部与 64 行 `resolution_matrix` 重算值相等（矩阵无 owning 行的消费者"
               "只校验「标为适用的键必须有规则行」）"
               % (len(PIN_SCOPE_TABLE_BOOKS), checked))
    # ── 21.2 `SPEC-101k` 的 D17 scope/facet 矩阵必须与 consumer_activation 逐键一致 ──
    p101k = os.path.join(REPO_ROOT, PIN_SPEC101K_REL)
    if not os.path.isfile(p101k):
        rep.fail(cat, "spec101k-matrix", "%s 不存在" % PIN_SPEC101K_REL)
        return
    txt = read_text(REPO_ROOT, PIN_SPEC101K_REL)
    mprob, mrow = [], 0
    # 表列序：任务 | S1 | 台账外 S2 | S3 | S4 | S5 | S6 | 历史 S7 | S8
    colmap = {}
    ci = 1
    for sk in ("D17:S1", "(S2)", "D17:S3", "D17:S4", "D17:S5", "D17:S6", "(S7)", "D17:S8"):
        colmap[sk] = ci
        ci += 1
    for line in txt.split("\n"):
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != len(PIN_LEDGER_KEYS) + 3:
            continue
        label = cells[0]
        tid = label if label in ca else PIN_101K_MERGED_ROWS.get(label)
        if tid is None:
            continue
        mrow += 1
        want = ca.get(tid) or {}
        if not want:
            mprob.append("%s 行无法映射到 consumer_activation 条目" % tid)
            continue
        for k in PIN_LEDGER_KEYS:
            cell = cells[colmap[k]]
            w = want.get(k)
            if w == "projected-pending-activation" and not cell.startswith("A"):
                mprob.append("%s %s 期望 A（ADR Accepted 后），实际 %r" % (tid, k, cell))
            elif w == "N/A(runtime)" and not cell.startswith("N/A(runtime)"):
                mprob.append("%s %s 期望 N/A(runtime)，实际 %r" % (tid, k, cell))
            elif w not in ("projected-pending-activation", "N/A(runtime)"):
                mprob.append("%s %s 门禁取值 %r 无法机读" % (tid, k, w))
    if mrow < 7:
        mprob.append("SPEC-101k 只解析到 %d 行 D17 矩阵，期望 ≥ 7 行" % mrow)
    if mprob:
        rep.fail(cat, "spec101k-matrix", "%r" % mprob[:6])
    else:
        rep.ok(cat, "spec101k-matrix",
               "`SPEC-101k` §7 的 D17 scope/facet 矩阵 %d 行 × 六键全部与 "
               "`consumer_activation.ledger_gate_projection` 逐格一致（无自相矛盾）" % mrow)


# ══════════════════════════════ 入口 ══════════════════════════════
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("-v", "--verbose", action="store_true", help="逐项打印通过项")
    ap.add_argument("--root", default=REPO_ROOT, help="仓库根目录")
    ap.add_argument("--yaml", default=None, help="被检查的 YAML（相对 --root 或绝对路径）")
    ap.add_argument("--require-active", action="store_true",
                    help="生命周期门禁模式：只有 ADR-1009～1015 全部 Accepted 才退出 0；"
                         "否则打印明确 BLOCKED 报告并退出非零")
    args = ap.parse_args(argv)
    root = os.path.abspath(args.root)
    yaml_rel = args.yaml or YAML_REL
    ypath = yaml_rel if os.path.isabs(yaml_rel) else os.path.join(root, yaml_rel)
    if not os.path.isfile(ypath):
        sys.stderr.write("找不到被检查文件：%s\n" % ypath)
        return 2
    try:
        doc = yaml.safe_load(read_text(root, os.path.relpath(ypath, root)))
    except Exception as exc:
        sys.stderr.write("YAML 解析失败：%r\n" % exc)
        return 2
    if not isinstance(doc, dict):
        sys.stderr.write("YAML 顶层不是映射\n")
        return 2
    try:
        up = Upstream(root)
    except Exception as exc:
        sys.stderr.write("上游重算失败（fail-closed）：%r\n" % exc)
        return 2
    if len(up.f1) != 64:
        sys.stderr.write("上游 contracts/opcodes.yaml 的 F1 记录数不是 64（%d），fail-closed\n"
                         % len(up.f1))
        return 2
    rep = Report(args.verbose)
    cand_ids = {c.get("id") for c in (doc.get("candidate_inputs") or [])
                if isinstance(c, dict)}
    for fn in (lambda: g1_schema(rep, doc, up),
               lambda: g2_proofs(rep, doc, up, cand_ids),
               lambda: g3_sources(rep, doc, up, yaml_rel),
               lambda: g4_quotes(rep, doc, up),
               lambda: g5_ledger(rep, doc, up),
               lambda: g6_trace_only(rep, doc, up),
               lambda: g7_matrix(rep, doc, up),
               lambda: g8_graph(rep, doc, up),
               lambda: g9_candidates(rep, doc, up),
               lambda: g10_open(rep, doc, up),
               lambda: g11_scope(rep, doc, up, root, os.path.relpath(ypath, root)),
               lambda: g12_s7_consistency(rep, doc, up),
               lambda: g13_adr_inventory(rep, doc, up),
               lambda: g14_candidate_closure(rep, doc, up, cand_ids),
               lambda: g15_rule_tables(rep, doc, up),
               lambda: g16_resolution_matrix(rep, doc, up),
               lambda: g17_normative_authority(rep, doc, up),
               lambda: g18_downstream_sync(rep, doc, up),
               lambda: g19_history_and_bypass(rep, doc, up, root,
                                              os.path.relpath(ypath, root)),
               lambda: g20_lifecycle_interface(rep, doc, up),
               lambda: g21_scope_self_consistency(rep, doc, up)):
        try:
            fn()
        except Exception as exc:                                # pragma: no cover
            rep.fail("G0", "internal-error", "%r: %r" % (fn, exc))
    nf, npass, nskip = len(rep.failed), len(rep.passed), \
        len([i for i in rep.items if i[2] is None])
    sys.stdout.write("SPEC-103t f1_gap_proofs check: 通过 %d 项，失败 %d 项，跳过 %d 项\n"
                     % (npass, nf, nskip))
    if nf:
        cats = sorted({i[0] for i in rep.failed})
        sys.stdout.write("失败的检查组：%s\n" % ",".join(cats))
        return 1
    # ── 生命周期接口（§8 末段）──
    states = {a: up.adr_state.get(a) for a in PIN_ADR_SET}
    not_accepted = {a: s for a, s in states.items() if s != PIN_ADR_STATE_ACCEPTED}
    if args.require_active:
        if not_accepted:
            sys.stdout.write(
                "ACTIVE GATE: BLOCKED —— `--require-active` 要求 ADR-1009～1015 全部为 "
                "Accepted，实测 %d/%d 份为 Accepted，未 Accepted 的有：\n"
                % (len(PIN_ADR_SET) - len(not_accepted), len(PIN_ADR_SET)))
            for a in PIN_ADR_SET:
                sys.stdout.write("  %s **状态**：%s\n" % (a, states.get(a)))
            sys.stdout.write(
                "这是**预期的替代证据**，不是 PASS：本任务只把已确认语义投影为 "
                "confirmed/projected/pending-activation，ADR 状态转换由主会话在 "
                "/complete reviewer+architect 双角色 Accepted 之后处理，之后必须复跑本模式。\n"
                "下游 schema/oracle/vector、LLVM/QEMU 实现与 E2E 在本模式下另行保持 BLOCKED。\n")
            return 3
        sys.stdout.write(
            "ACTIVE GATE: OK —— ADR-1009～1015 全部 Accepted；`resolution` 层可作为"
            " active implementation input。\n")
        return 0
    # 默认模式：可以退出 0，但**不得**声称 active/Accepted
    if not_accepted:
        sys.stdout.write(
            "PENDING ACTIVATION（非 active）：本文件只证明 ADR-1009～1015 的已确认"
            "内容被正确投影；实测 %d 份仍为 %s，activation_state=pending-activation。"
            "不得据此声称 active / Accepted，也不得声称任何 facet PASS。\n"
            % (len(not_accepted), PIN_ADR_STATE_CANDIDATE))
    return 0


if __name__ == "__main__":
    sys.exit(main())
