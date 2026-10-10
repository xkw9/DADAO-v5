#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""手工推导的 F1 样例期望值（**独立 oracle**，纯整数位型推导，不调用宿主浮点）。

本模块是 TESTCASES-101t 的**独立重算基准**：这里每个 64/32 位期望值都由
整数运算 + 手写 IEEE-754 位布局推导，**不**经过 Python float、libm、SoftFloat、
LLVM 或 QEMU。`tools/testcases/generate_f1_schema_fixtures.py` 生成的样例
`expected_state` 全部引用本模块的常量；validator 再用 `f1_cases.py` 的独立
检查逐条重算（不读本模块），因此本模块与 validator 互为交叉验证。

推导记录（供审计）：

* `1.0`（fo）  = 符号 0 / 指数 0x3FF / 尾数 0  → 0x3FF0000000000000
* `2.0`（fo）  = 指数 0x400                     → 0x4000000000000000
* `3.0`（fo）  = 1.5×2^1：指数 0x3FF+1=0x400、尾数最高位 1 → 0x4008000000000000
* `8.0`（fo）  = 1.0 × 2^3，指数 0x3FF+3=0x402 → 0x4020000000000000
* `-0.0`（fo） = 仅符号位 1                     → 0x8000000000000000
* `1.0f`（ft） = 符号 0 / 指数 0x7F / 尾数 0     → 0x3F800000
* `0.0f + 1.0f = 1.0f`                           → 0x3F800000
  故 tetra 写 rf 后 64 位 = 0xFFFFFFFF_3F800000（D13 高半部固定 0xFFFFFFFF）
* `+∞`（ft）  = 符号 0 / 指数全 1 / 尾数 0       → 0x7F800000
  非零有限数除以零：IEEE 754-2008 §7.2 规定「结果是无限精确结果正确舍入后的
  值」，而 ±∞ 本身可表示且精确 → **四种舍入模式一律 ±∞**；结果与无限精确
  结果相等故 §7.4 的 inexact 不成立 → 只置 DZ，不置 NX；除零也**不是**
  overflow（D16 的 OF+NX 配对不适用）。tetra 装箱 → 0xFFFFFFFF7F800000
* `ld.t-rf` 读 4 字节 `0x3F800000` → 同样 NaN-boxing 成 0xFFFFFFFF3F800000
* `ld.o-rf` 读 8 字节 `0x3FF0000000000000` → 不装箱（octa 无 D13），原值
* `foqcmp` unordered → 0x7FF8000000000000（ADR-1012 D2 quiet 类）
* `foscmp` unordered → 0x7FF0000000000001（ADR-1012 D3 signaling 类）
* `cs.eq rf1,rf2`（rd = rf0 的 MOV 语义）→ 写 rd1 = rf1 的 64 位原值
"""

# ── 64 位（fo/octa）位型 ─────────────────────────────────────────────
FO_ONE = 0x3FF0000000000000
FO_TWO = 0x4000000000000000
FO_ZERO = 0x0000000000000000
FO_EIGHT = 0x4020000000000000          # 1.0 × 2^3
FO_THREE = 0x4008000000000000          # 1.5 × 2^1 = 1.0 + 2.0
FO_NEG_ONE = 0xBFF0000000000000
FO_NEG_ZERO = 0x8000000000000000        # 仅符号位 1（rootn 的 unspecified 点）
FO_SNAN = 0x7FF0000000000001           # signaling NaN（指数全 1、尾数最高位 0）
FO_QNAN = 0x7FF8000000000000           # quiet NaN（用于需要 NaN 输入的用例）
FO_MAX_FINITE = 0x7FEFFFFFFFFFFFFF      # 最大有限 fo；与自身相加上溢
FO_POS_INF = 0x7FF0000000000000

# D14（ADR-1012 D2/D3）固定 unordered 输出
D14_QUIET_UNORDERED = 0x7FF8000000000000     # foqcmp / ftqcmp
D14_SIGNAL_UNORDERED = 0x7FF0000000000001   # foscmp / ftscmp

# ── 32 位（ft/tetra）位型 ────────────────────────────────────────────
FT_ONE = 0x3F800000
FT_ZERO = 0x00000000
FT_TWO = 0x40000000
FT_POS_INF = 0x7F800000                # 指数全 1、尾数 0
FT_SNAN = 0x7F800001
FT_QNAN = 0x7FC00000

# D13（ADR-1011 D1）tetra 写 RF 的高 32 位
D13_HIGH32 = 0xFFFFFFFF


def tetra_boxed(ft_value):
    """tetra 结果写 rf 的 64 位 NaN-boxing 高半部（D13）。"""
    assert 0 <= ft_value <= 0xFFFFFFFF
    return (D13_HIGH32 << 32) | ft_value


# ── 期望值常量（生成器直接引用） ──────────────────────────────────────
EXP_FOADD_1PLUS2 = FO_THREE           # foadd：dst=rf1, src rf2=1.0, src rf3=2.0 → 3.0
EXP_FOSUB_3MINUS1 = FO_TWO             # fosub：rf1=3.0, rf2=1.0, rf3=0 → 2.0
EXP_FOMUL_2TIMES4 = FO_EIGHT           # fomul：rf1=2.0, rf2=4.0, rf3=0 → 8.0
EXP_FTADD_0PLUS1 = tetra_boxed(FT_ONE)  # 0.0f + 1.0f = 1.0f（tetra 装箱）
EXP_FTADD_1PLUS1 = tetra_boxed(FT_TWO)  # 1.0f + 1.0f = 2.0f
EXP_FOADD_OVERFLOW = FO_POS_INF        # 最大有限 + 最大有限 → +Inf（置 OF+NX）
EXP_LDT_RF_LOAD = tetra_boxed(FT_ONE)  # ld.t-rf 装 0x3F800000
EXP_LDO_RF_LOAD = FO_ONE               # ld.o-rf 装 0x3FF0000000000000（不装箱）
# ftdiv：dst=rf1, src rf2=1.0f, src rf3=0.0f → 非零有限数除以零 → +Inf（只置 DZ）
EXP_FTDIV_BY_ZERO = tetra_boxed(FT_POS_INF)

# ── rf0 / FCSR（合约 §2 + ADR-1015 D1） ──────────────────────────────
FCSR_RO_MASK = 0xFFF80000FFC00000
FCSR_SBZ_MASK = 0x0007FFFF003CFFE0
FCSR_RW_MASK = 0x000000000003001F
FCSR_RO_VALUE = 0x7FF800007FC00000
# ADR-1015 D1 复位：rf0[17:16]=00 (RNE)、rf0[4:0]=0 → rw 域全 0
FCSR_RESET_VALUE = FCSR_RO_VALUE
FCSR_MIN_OBSERVED_MASK = FCSR_RW_MASK  # 至少覆盖整个 rw 域
# 「可选的 RO 观测」= 合约 §2 两个只读域的位型
FCSR_FULL_OBSERVED_MASK = FCSR_RO_MASK | FCSR_RW_MASK


def fcsr_value(rounding_code, flag_bits):
    """完整可断言的 rf0 值：只读域取合约常量，rw 域取枚举，SBZ 置 0。"""
    return (FCSR_RO_VALUE & FCSR_RO_MASK) | (rounding_code << 16) | flag_bits
