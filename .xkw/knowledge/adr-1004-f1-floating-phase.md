# ADR-1004: F1 浮点阶段范围、边界与规划门禁

**状态**：Accepted  
**日期**：2026-09-26  
**关联**：`SPEC-101k`、`INTEG-104m`；`.tao/` 仅作只读历史基线

## Context

M1 已完成标量 MC→QEMU 闭环，但 SimRISC-03 的 RF/浮点指令仍以 M1 范围外处理。F1 要在保留 M1 可复现基线的前提下扩展该闭环。规范版本唯一来源为根 `README.md` 与 `spec/`；`DADAO-0628` 当前不在工作树，且无论是否可用都只可作内容溯源，非执行依赖。

## Decision

### D1：完整 SimRISC-03 范围

F1 覆盖 64 个真实浮点 identity（46 个 MISC-RF、18 个 RF 相关编码）：RF 存取、RF↔RD、`set.w`、转换、算术/FMA、符号、比较、条件赋值、分类与 rf0/FCSR。`set.ft`/`set.fo` 为附加汇编伪指令，不计入 64。

### D2：仅扩展 M1 闭环

范围为 `spec/contracts → testcases 独立 oracle → LLVM MC/disassembler → QEMU → integ`；不含 LLVM CodeGen、clang、libc 或 Linux。

### D3：独立 oracle 属于 testcases

不新建 `golden` 模块或 `GOLDEN-*` 任务。独立 oracle、向量、生成器和语义重算均由 `testcases` 拥有，不得从 LLVM、QEMU 或参考仓生成期望。

### D4：保留 M1 历史标记并增加 F1 scope

`.tao` 保持只读；F1 新合约置于 `.xkw`。机器可读数据保留 `excluded_m1: true` 的历史含义，并新增明确 F1 范围标记；不得以删除历史标记改写 M1。

### D5：完整 IEEE 边界是 F1 收敛要求

F1 最终验收要求由 spec 可导出的 f32/f64 舍入、flags、±0、subnormal、Inf、NaN、转换、FMA、remainder、scaleB、root/log 行为；普通数值冒烟不能替代。规范未给唯一结果时按 D17 阻塞，不伪造期望。

### D6：冻结 M1 基线并追加补丁

保留 M1 组件锁和 `0001`–`0008` 补丁。LLVM/QEMU F1 仅从 `0009+` append；仓库侧测试、向量和工具不进入上游补丁。

### D7：QEMU 语义实现约束

QEMU 使用 in-tree SoftFloat 与可审计、按 spec 定义的 helper；宿主浮点与 `libm` 不得作为规范语义或验收 oracle。

### D8：spec 是唯一语义来源

不从 LLVM、QEMU、SoftFloat、宿主库或参考仓反推规范行为。

### D9：F1 使用隔离工作树

保持 M1 `.work/source`、`.work/build` 可复现。F1 使用 `.work/f1/source/{llvm-project,qemu}` 和 `.work/f1/build/{llvm,qemu}`，从 M1 8-patch 头建立并追加 F1 补丁。

### D10：testcases 拥有 RF/FCSR 测试接口

`TESTCASES-101t` 冻结向后兼容 M1 的 schema、oracle I/O、RF/FCSR 状态和观测契约；QEMU 只消费实现，不能自行定义平行接口。

### D11：rf0 操作数冲突暂缓

一般 rf0→ILLI 规则与 sign-injection 特例的优先级为 OPEN/BLOCKED，待需要时另行 ADR。

### D12：FCSR flags 暂缓

异常 flags 的 sticky/覆盖、清除及无异常保留规则为 OPEN/BLOCKED。

### D13：tetra RF 高半部暂缓

单精结果写入后 RF 槽位高 32 位行为为 OPEN/BLOCKED。

### D14：unordered compare 位型暂缓

比较 unordered 写入 RD 的 qNaN/sNaN 精确位型为 OPEN/BLOCKED。

### D15：NaN 传播细节暂缓

多操作数 NaN 的 payload、符号、quieting 与默认 NaN 选择为 OPEN/BLOCKED。

### D16：tininess/复合 flags 暂缓

tininess 检测时点及 UF/OF/NX 组合规则为 OPEN/BLOCKED。

### D17：未精确定义的细节在 SPEC 阶段逐项处理

所有 SimRISC-03 未给唯一答案的细节先登记 OPEN/BLOCKED；需要实现或验证时，先由 SPEC 证明真实缺口，再新建 ADR 并逐条取得用户确认。

### D18：pseudo 输出规则

assembler 接受 `set.ft`/`set.fo` 的 spec 定义形式并展开；disassembler 只打印真实硬件指令，绝不将指令序列折叠为 pseudo。

## Consequences

- F1 全量里程碑必须等待所有 64 identity 的 required facet 闭合；OPEN 不得记 PASS。
- SPEC 必须区分 spec 明示事实与真实缺口；未来语义 ADR 均为 Candidate，未经逐条确认不得 Accepted。
- 当前 M1 产物、补丁与 baseline 受保护；LLVM/QEMU 构建因宿主资源必须串行。

## Confirmation record

D1–D18 均由用户在本会话逐条确认；D11–D17 的确认结论是暂缓/OPEN，而非语义取值的 Accepted 决定。
