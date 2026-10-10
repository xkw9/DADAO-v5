# DADAO-v5 进展汇报（2026-09-29）

## 一句话概览

项目的标量 M1 已完成并已在当前宿主复现；当前正进入 F1 浮点闭环。浮点规范与
语义决策已经冻结，测试接口实现已完成、正等待独立验收；LLVM、QEMU 和端到端闭环
尚未开始。

## 项目目标

DADAO-v5 的目标不是让单一组件“能编译”，而是在 SimRISC 0.5.3 规范约束下建立
可验证的工具链与模拟器闭环：规范规则、独立测试数据、LLVM、QEMU 和集成测试应使用
一致的接口；期望值不能由实现反推；每个验收检查器都必须有真实可达的失败反例。

当前 F1 的目标是闭合 SimRISC-03 的 64 个真实浮点 identity：

```text
spec/contracts → 独立测试 oracle/vector → LLVM MC/disassembler → QEMU → 集成回归
```

F1 不包含 LLVM CodeGen、clang、libc、Linux、gem5、Sail、特权或原子扩展。

## 已完成的工作

### M1 标量基线

- 原始项目的 M1 已完成；`.xkw` 又完成了从镜像、源码补丁到 LLVM/QEMU 构建和集成
  测试的复现。
- 当前已复现的集成基线为：**747 条用例，739 通过、0 失败、8 条明确暂缓、0 错误**。
- LLVM MC 与 QEMU 均已构建可用；M1 的源码树、构建树和 `0001`–`0008` 补丁被保护，
  F1 工作只能在隔离的 `.work/f1/**` 中追加 `0009+` 补丁。

| 任务 | 完成内容 |
| --- | --- |
| `INFRA-101k` | 定义 M1 复现范围、依赖与任务分解，不改写历史 M1 成果。 |
| `INFRA-102t` | 准备宿主工具链与 Python 运行时，完成环境和 manifest 检查。 |
| `INFRA-103t` | 预填 LLVM/QEMU 浅 bare 镜像，验证锁定 commit、对象完整性和离线短路。 |
| `INFRA-104t` | 从本地镜像离线重建源码树，忠实应用两组件各 8 个 M1 补丁。 |
| `INFRA-105t` | 构建 LLVM MC，确认 DADAO target 注册、工具和 `llvm-lit` 可用。 |
| `INFRA-106t` | 构建 QEMU 11.1.1，确认 `qemu-system-dadao` 与 `dadao-m1` 机器可用。 |
| `INTEG-101t` | 重跑 L0–L8 的 20 条检查命令，确认 M1 基线零偏差。 |

`INFRA-107t`（组件镜像站更正）已规划但尚未开始；它是独立治理工作，不在 M1/F1
功能闭环的关键路径上。

### F1 浮点阶段的规范与基础设施

- F1 启动任务 `SPEC-101k`、浮点合约与 64 个真实 instruction identity 映射
  `SPEC-102t`、缺口证明 `SPEC-103t`、语义机器投影 `SPEC-104t` 均已验证。
- `INFRA-108t` 已建立 F1 隔离工作树、补丁序列和 M1 保护门禁。
- F1 范围是 SimRISC-03 的 **64 个真实 identity**（18 个 RF/QFC + 46 个 MISC-RF）；
  `set.ft` 与 `set.fo` 是汇编伪指令，不计入 64。
- ADR-1004、ADR-1008 和 ADR-1009～ADR-1015 均已 Accepted。此前未定的浮点语义已被
  投影为可机读规则，不能再由 LLVM 或 QEMU 实现自行解释。

| 任务 | 完成内容 |
| --- | --- |
| `SPEC-101k` | 划定 F1 范围、64 identity、模块边界、依赖图、文件所有权与资源冲突。 |
| `INFRA-108t` | 建立 `.work/f1/**` 隔离树、补丁编号和重放门禁，保护 M1 工作树。 |
| `SPEC-102t` | 建立 F1 合约、64 identity 映射、编码/合法性/source 投影与初始缺口台账。 |
| `SPEC-103t` | 逐项证明语义缺口，确认 RD/RF 不重叠，D17 台账收敛为六个 active 键。 |
| `SPEC-104t` | 将 27 条经用户确认的 ADR decision 投影为机器规则，并同步下游门禁。 |

D17 当前的 active 语义键为 `S1/S3/S4/S5/S6/S8`；`S2` 只是 trace-only 来源记录，
`S7` 已由规范证明不是缺口。二者都不能被统计为运行时 PASS。

### F1 测试接口实现

`TESTCASES-101t` 已完成实现并处于**待验收**状态，主要产出包括：

- 兼容既有 M1 向量的 schema 扩展，增加 RF、rf0/FCSR、浮点位型、异常、facet 和
  blocked 语义表达；
- 独立 oracle I/O 文档、正反样例、schema fixture 生成器和 validator；
- 纯整数位型的期望值重算器，以及 41 条已知答案测试和 400 次独立位精确重算；
- 39 项反例注入门控。任务记录称所有注入都在临时树中完成并可恢复。

这代表“测试数据和接口可表达、可检查”，**不代表 LLVM/QEMU 浮点实现或端到端语义已经通过**。

任务记录中的执行证据包括：M1 747 条既有向量兼容检查、19 个 F1 正样例、53 个反样例、
39 个临时树反例注入、41 条 IEEE 已知答案测试、400 次整数位型重算，以及第三条独立
手算路线的 71 行交叉核对。这些数字仍须在 `/complete` 中由独立审查重新验证。

## 当前进行中的工作

当前关键路径停在：

```text
SPEC-104t（已验证）
  → TESTCASES-101t（待验收）
  → TESTCASES-102t（独立 oracle 与全量向量）
  → QEMU-101t → QEMU-102t → QEMU-103t
  → INTEG-102t → INTEG-103t → INTEG-104m
```

LLVM 是可并行分支：

```text
LLVM-101t → LLVM-102t、LLVM-103t
```

在实际编译时，LLVM 和 QEMU 仍必须串行，以避免宿主内存资源冲突。

## 尚未开始的主要工作

| 领域 | 后续工作 |
| --- | --- |
| 测试 | `TESTCASES-102t`：独立浮点 oracle、生成器与全量向量 |
| LLVM | `LLVM-101t`～`103t`：RF 寄存器、真实指令 MC、lit/字节 oracle、伪指令与反汇编边界 |
| QEMU | `QEMU-101t`～`103t`：RF 状态、运算/FMA、比较/条件赋值/FCSR |
| 集成 | `INTEG-102t`～`104m`：64-facet 对齐、MC→QEMU 闭环、M1 无回归和 F1 里程碑核验 |

## 后续任务规划

### 近期：完成测试数据基础

1. **`/complete TESTCASES-101t`**：独立验收已落盘的 schema/oracle 接口。重点是 M1
   向后兼容、独立期望值重算、每个 checker 的反例 FAIL 路径，以及 dirty baseline 未变。
2. **`TESTCASES-102t`**：在已冻结接口上建设全量独立浮点 oracle、生成器和向量。对
   rounding、NaN/Inf、subnormal、FCSR 等敏感结果必须逐例独立重算，不能只依赖 validator。

### 中期：LLVM 与 QEMU 实现

| 顺序 | 任务 | 计划成果 |
| --- | --- | --- |
| 1 | `LLVM-101t` | RF 寄存器和真实 F1 指令的汇编器支持；只消费汇编合法性规则。 |
| 2 | `LLVM-102t` | 64 identity 的 MC lit 和独立字节 oracle。 |
| 2 | `LLVM-103t` | `set.ft`/`set.fo` 伪指令展开及不折叠的反汇编边界。 |
| 1 | `QEMU-101t` | RF 状态、RF 存取/搬移和 `set.w`，包括适用的 rf0 与异常规则。 |
| 2 | `QEMU-102t` | 转换、算术、FMA、符号以及 root/log 的可实现部分。 |
| 3 | `QEMU-103t` | 比较、条件赋值、分类和 FCSR 回归。 |

`LLVM-102t` 与 `LLVM-103t` 可在 `LLVM-101t` 完成后逻辑并行；QEMU 必须按
101→102→103 顺序。实际 LLVM/QEMU 构建仍须串行。

### 收敛：跨模块集成

1. `INTEG-102t` 建立 64 identity 与 required facet 的跨模块接口矩阵。
2. `INTEG-103t` 跑 LLVM MC→QEMU 的端到端闭环，并重跑 M1 的 747 条基线。
3. `INTEG-104m` 只做里程碑核验，不补实现；只有所有 required facet 有证据、active 语义
   已真实实现并验证、S2/S7 未误计 PASS 且 M1 无回归时，F1 才能达成。

## 已知边界与风险

- `rootn(-0,2)` 是规范明确的未定义情形，不能制造唯一期望值。
- root/log 的独立正确舍入算法仍是能力缺口；在具备独立 oracle 前，不能把运行结果当作
  语义正确性证据。
- ADR-1013 未提供 64 位 canonical qNaN 常量；下游不得自行补造。
- M1 仍有独立治理事项：组件镜像源失效、Makefile 的构建成功提示未验证产物、部分 E2E
  smoke 没有输出断言。这些不阻塞当前 F1 规划，但应在独立任务中处理。

## 当前工作区说明

截至本报告生成前，工作区有 **72 个 dirty 路径**（14 个已跟踪修改、58 个未跟踪）。
其中包含本轮 F1 的任务、合约、工具、向量和文档产出，也可能包含用户尚未提交的工作。
后续验收或执行必须先建立内容哈希 baseline，不能覆盖或还原这些现有改动。

## 建议的下一步

优先对 **`TESTCASES-101t` 执行 `/complete`**：独立复跑验收、在临时树验证每个检查器的
反例 FAIL 路径，并确认当前 dirty baseline 未被改变。只有该任务验收通过后，才建议派发
`TESTCASES-102t`，再按依赖推进 LLVM 与 QEMU 的 F1 实现。
