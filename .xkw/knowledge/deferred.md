# 暂缓 / 备忘（Deferred / Backlog — `.xkw`）

> 本文件记录**已知但本轮不做**的项。`.tao/knowledge/deferred.md` 是原项目的登记处，**只读**；本文件只记 `.xkw` 自己的轮次产生的新发现。
> 正式工作仍走 `.xkw/tasks/`。

## infra

- **组件源 `sjtu` 已失效**（2026-09-25 实测）：`mirror.sjtu.edu.cn` 与 `mirrors.sjtug.sjtu.edu.cn` 互相 302，构成死循环。`manifests/components.lock.toml` 两个组件的 `[[component.source]]` 仍指向它。
  - **当前不阻塞**：`.cache/` 预填后 `fetch.py:47-61` 的 `sync_mirror()` 因 `has_commit()` 命中而**完全短路、不联网**。
  - **隐患**：`.cache` 若被清空，`make fetch` 会执行 `git clone --mirror`（**全量历史**，llvm-project 约 30 GB / 数小时）打到死循环 URL ⇒ 先长时间等待再失败。`clean_work.py` 只清 `.work/` 故正常流程不触发。
  - **归属**：`INFRA-107t`（后续任务，不在 M1 复现关键路径）。

- **宿主 ssh 代理隧道**：`127.0.0.1:7890` 的监听进程是 **`sshd: ubuntu@notty`（SSH 远程端口转发隧道）**，2026-09-25 已运行 7h31m，且**未设任何环境变量**（env / git config / `/etc/environment` / apt / pip / shell rc 全无 proxy）。
  - **不得当作基础设施**：外部会话，说断就断；M1 构建需连跑 1.5–3 h。
  - **本轮结论**：全程裸连。TUNA 裸连 6.08 MiB/s vs GitHub 经代理 0.87 MiB/s（实测后者 240 s 未完成 285 MiB）。

- **QEMU meson 版本**（`INFRA-106t` 的不确定项）：QEMU 11.1.1 `meson.build:1` 要求 `meson_version: '>=1.5.0'`，jammy apt 仅 0.61.2。**不手动安装**，依赖 `configure` 自建 venv 按 `pythondeps.toml` 自动 pip 装。若失败需改宿主 Python 环境 ⇒ **须先经用户确认**。

- **`doctor.py` 不检查 QEMU 依赖**：`.tao/knowledge/deferred.md` 已登记。`INFRA-102t` S1 手工装了 `libglib2.0-dev`/`libpixman-1-dev`/`libfdt-dev`/`pkg-config`，但**没有任何脚本会检查它们** ⇒ 换机复现时容易漏装。本轮沿用 `.tao` 的登记，不重复登记；根治（扩展 `doctor.py` 的 QEMU 依赖面）属独立议题。

## llvm / 跨模块

- **3 个脚本硬编码旧仓库路径**（2026-09-25 发现）：

  | 文件 | 行 | 内容 |
  | --- | --- | --- |
  | `tools/llvm/gen_m1_asm.py` | 169 | `open('/mnt/tao/DADAO-v5/contracts/opcodes.yaml')` |
  | `tools/llvm/test_m1_asm.py` | 24 | `llvm_mc = '/mnt/tao/DADAO-v5/.work/build/llvm/bin/llvm-mc'` |
  | `tools/llvm/test_encoding_oracle.py` | 335 | 同上 |

  仓库已从 `/mnt/tao/DADAO-v5` 移至 `/home/ubuntu/DADAO-v5`。
  - **本轮处置**：`INFRA-102t` S4 建宿主符号链接 `/mnt/tao/DADAO-v5 → /home/ubuntu/DADAO-v5` 绕过（与原环境一致，仓库零改动）。
  - **根治**：改为从 `__file__` 推导仓库根。**未排期**。

- **`.tao/knowledge/MEMORY.md:13` 的 harness 基线已过期**：记的是 `597/590/2/5/0`（`TESTCASES-010t`/`011t` 补 150 条向量**之前**）。权威基线是 `QEMU-021m` 里程碑记录的 **`747 total / 739 passed / 0 failed / 8 deferred / 0 errors`**。
  - **本轮处置**：`INTEG-101t` 以 `QEMU-021m` 为准；`.tao/` 只读故不改。
  - **影响面**：任何引用 597/590 的文档或记忆都需按此更正。

## 流程 / 约定

- **`.xkw` 任务号采用 1xx 段**（`INFRA-101k`~`107t`、`INTEG-101t`）：`.tao/tasks/` 已占用 `INFRA-001k`~`014m` / `INTEG-001k`~`004m` 且**只读**，同号会导致跨树引用歧义（如 `.xkw` 的 `INFRA-002t` 与 `.tao` 的 `INFRA-002t-仓库与构建骨架` 内容完全不同）。三位编号、模块内递增的约定不变。

- **`.xkw/knowledge/adr-*` 采用 `1xxx` 号段**（用户 2026-09-25 裁定）：首个为 `adr-1001`，此后递增；**不与** `.tao/knowledge/adr-*` 的 `0001`–`0011` 共享编号空间。原按「接最大值 `0011` 之后」拟的 `adr-0012` 已改号作废——两棵树编号空间分离比共享更不易撞号。同理 `.xkw/tasks/` 采用 `1xx` 段避开 `.tao` 已占用的 `001`–`014`。

- **`llvm-lit` 不由 `Makefile` 构建**：`Makefile:87` 的 ninja 目标列表不含 `llvm-lit`，而 `tests/lit/*/lit.cfg.py:28-30` 优先读 `config.llvm_tools_dir`（`llvm-lit` 才会设）。本轮用 `ninja llvm-lit` 或 `LLVM_TOOLS_DIR` + `llvm/utils/lit/lit.py` 兜底（`INFRA-105t` S4 记录实际采用哪条）。根治（把 `llvm-lit` 加进 `build-mc` 目标列表）属独立议题。

- **`make prepare` 非幂等**：`.tao/knowledge/deferred.md` 已登记。对全新工作树不触发；重复执行会报 `HEAD is not its base commit`，应 `make clean-work` 后重来，**不得手工 reset 掩盖**。
