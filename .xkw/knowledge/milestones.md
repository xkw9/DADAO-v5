# Milestones — `.xkw` 自有路线图

本文件只记录 `.xkw` 自有开发轮次与依赖；原项目里程碑见只读的 `.tao/knowledge/milestones.md`。

## 当前轮次：M1 复现

**目标**：不新增 M1 功能，在当前宿主重建缓存、源码树与构建产物，并逐层复现 `.tao` 已达成的 M1 验收基线。

| 层 | 任务 | 状态 | 门禁/说明 |
| --- | --- | --- | --- |
| 启动 | `INFRA-101k` | **已验证** | 目标、阻塞、任务分解与 ADR-1001 已确认 |
| L0 环境 | `INFRA-102t` | **已验证** | doctor / manifest / Python 运行时与兼容路径 |
| L1 镜像 | `INFRA-103t` | **已验证** | 两个浅 bare 镜像命中锁定 commit；本地短路不联网 |
| L2 源码 | `INFRA-104t` | **已验证** | 离线 fetch（两条精确 skip、零联网）+ 两套 8 补丁忠实重放；树内容级重放等价已独立证明 |
| L3 构建 | `INFRA-105t` | **已验证** | LLVM MC 工具链；`llvm-mc --version` 注册 `dadao`，6 工具 + `llvm-lit` 就位 |
| L3 构建 | `INFRA-106t` | **已验证** | QEMU 11.1.1 `qemu-system-dadao`（34.8 MB）；`-M ?` 注册 `dadao-m1`；venv `Python 3.10.12` + `meson 1.11.1`；`build-qemu_rc=0`／144 s。验收 9 PASS / 1 BLOCKED(#10 属 `INTEG-101t`) |
| L4 集成 | `INTEG-101t` | **已验证** | L0–L8 九层 20 条命令全 `rc=0`，与基线**逐条零偏差**；**硬门槛 L5 = `747 total / 739 passed / 0 failed / 8 deferred / 0 errors`，`harness_rc=0`**（约 118 s／157 ms·条），独立复算 `747 = 739 active + 8 deferred`；13 个检查器全部有实测可达 FAIL 路径。详见任务书完成区 + 验收记录 R.0–R.6 |
| 后续治理 | `INFRA-107t` | 待开始 | BLOCKED：先完成 ADR-1003 逐 decision 确认，再修正组件源；`.tao` 只读，不在复现关键路径 |

### L3（`INFRA-106t`）的跨模块影响检查 — `workflow.md` §12

`/complete` 前逐项核对上游修复、接口调整与**未处置 deferred**。结论：**5 项已识别，其中 4 项已处置或已明确归属，1 项仍待用户裁决。**

| # | 影响项 | 是否影响 L3 交付物 | 处置 |
| --- | --- | --- | --- |
| 1 | `Makefile:8` 单一 `$(PYTHON)` 服务互斥需求（工具链需 `tomllib`≥3.11 / QEMU 需 3.10 的 `setuptools`） | **否** —— QEMU 二进制已产出且验收通过 | **已处置**：方案 C 的 `tools/infra/install_tomllib_shim.py` 已入库并成为任务书 **S0** 必做前置（幂等、秒级、自验证 7 项）。换机重跑 S0 即可复现 ⇒ **可复现性有保障**。根因修复（为两类需求分别选解释器）已登记 `deferred.md`，归属独立任务 |
| 2 | QEMU `configure` 从 gitlab 拉 3 个 subproject（`keycodemapdb` 等） | **否** —— 本轮网络可用，构建已完成 | 已登记 `deferred.md`，归属 `INFRA-107t`（镜像/预填）；`fetch.py` 当前不覆盖 QEMU subprojects |
| 3 | 零内容 ROM 下 `qemu-system-dadao` 以 **SIGFPE(136)** 退出 | **否** —— 属语义层，非构建层 | 已登记并转 `INTEG-101t`；**不得**在 L3 语境下当作任何正确性证据 |
| 4 | `INTEG-101t:114` 的陈旧机器名 `dadao-m`（真值 `dadao-m1`） | **否** —— 属 L4 任务书 | 已登记；**`INTEG-101t` 派发前必须先更正**，否则该任务会因机器名不存在而假失败 |
| 5 | **`INFRA-105t` S3 第 7 项判据过弱**：`find .work/build/llvm -maxdepth 4 -name '*DADAO*' -print -quit` **不区分文件与目录**，空目录与 0 字节 `libLLVMDADAOCodeGen.a` 都会报「已构建」 | **否**（结论仍成立）—— `llvm-mc --version` 注册 `dadao`、6 工具 + `llvm-lit` 就位均已**独立实证**，不依赖该判据 | ⚠️ **仍待用户裁决**：就地修 `INFRA-105t` 任务书 vs 留给 `INTEG-101t`。已登记 `deferred.md`，**未擅自修改**（§11.2 第 7 条：reviewer 可当场修正**事实记录**，但修判据属改**规格**） |

> **如实声明**：存在 1 项未处置项（第 5 条），但它**不影响 L3 交付物的正确性**（结论有独立证据支撑），且已登记在案。故 L3 的 `INFRA-106t` 行置 `已验证`；**第 5 条的裁决仍挂账**，不应被本行的 `已验证` 掩盖。

### L4（`INTEG-101t`）的跨模块影响检查 — `workflow.md` §12

`/complete` 前逐项核对上游（`INFRA-102t`~`106t`）的修复/变更、接口调整，以及**未处置 deferred** 是否被本任务消费或改变。结论：**4 项，其中 3 项已在本任务内消化，1 项独立挂账。**

| # | 影响项 | 是否影响 L4 交付物 | 处置 |
| --- | --- | --- | --- |
| 1 | `Makefile:8` 单一 `$(PYTHON)`（tomllib vs setuptools 互斥） | **否** | **已在任务书消化**：预检修正 **P1** 去掉致命的 `PYTHON=python3.12` 覆盖，改用方案 C 的 tomllib shim。实测裸 `make build-qemu` rc=0／25.4 s。根因修复仍挂 `deferred.md`（独立任务） |
| 2 | `INTEG-101t:114` 陈旧机器名 `dadao-m` | **是（若不修则假失败）** | **已修（预检修正 P5）**：改为 `dadao-m1` 并把判据收紧为**精确机器名**。实测 `-M ?` 列出 `dadao-m1`，且 `grep -qw 'dadao-m'` rc=1 证明收紧有实效 |
| 3 | 零内容 ROM 下 QEMU 以 **SIGFPE(136)** 退出（L3 转来） | **是 —— 已被消费** | **本任务就是它的落点**：L5 硬门槛实测 747 条 `0 failed / 0 errors`，`misc.yaml` 的 `fence` 3 条 deferred 仍标注 `trans_fence` 为 ILLI 桩（ISS-056）。⇒ SIGFPE 是**已登记的已知语义缺口**，不是本轮新问题 |
| 4 | **`INFRA-105t` S3 第 7 项判据过弱**（`find -print -quit` 不分文件/目录） | **否** | ⚠️ **仍挂账**。原「留给 `INTEG-101t` 一并处置」的时机**已随本任务 `已验证` 而过去** ⇒ 现在是**独立待裁决项**（就地修 `INFRA-105t` vs 正式记为不修）。已登记 `deferred.md`，**未擅自修改**（§11.2 第 7 条：改判据属改规格） |
| 5 | `Makefile` 的 `build-mc/build-qemu: PASS` **不验产物**（本轮 reviewer 新发现，与 `INFRA-106t` B21 同类） | **否 —— 本任务判据另有兜底** | 验收 #6 除 `PASS` 外还要求 `-M ?` 列出 `dadao-m1`，**那一步确实验产物**（反例：查 `dadao-m2` rc=1 / 无二进制 rc=127）⇒ #6 不空。已登记 `deferred.md`，`Makefile` 属禁改范围故本任务不修 |

> **如实声明**：第 4 项仍待用户裁决，第 5 项为新登记待办。两者**均不影响 L4 交付物的正确性**（各有独立证据支撑：#4 靠 `llvm-mc --version` 等实证；#5 靠 `-M ?` 验产物），故 L4 行置 `已验证`，但**挂账不应被本行的 `已验证` 掩盖**。

## 依赖图与关键路径

```text
INFRA-101k
    └─ INFRA-102t → INFRA-103t → INFRA-104t
                                      ├─ INFRA-105t ─┐
                                      └─ INFRA-106t ─┴→ INTEG-101t

INFRA-107t  （独立后续治理，不阻塞 M1 复现）
```

关键路径：`102t → 103t → 104t → {105t,106t} → INTEG-101t`。

`105t` 与 `106t` 文件/逻辑上可并行，但当前宿主仅 3 GiB RAM，资源冲突使其**执行上必须串行**；这类“依赖可并行但资源不可并行”的区别须在启动任务中显式记录。

## 状态更新责任

- `/plan` 创建或调整路线、依赖和 `k↔m` 关系。
- `/dispatch` 不提前更新里程碑，只把成功执行的普通任务置 `待验收`。
- `/complete` 仅在 reviewer + architect 均 Accepted 后更新本表、MEMORY、changelog 与任务状态。
- `/xkw-start`、`/xkw-status` 只报告漂移，不自动修正。

## 原项目基线

`.tao/knowledge/milestones.md` 记录 M1 已于 2026-09-22 达成；本轮只验证其可复现性，不改变 `.tao` 状态。
