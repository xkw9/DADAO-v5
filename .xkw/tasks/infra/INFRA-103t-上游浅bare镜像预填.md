# INFRA-103t: 上游浅 bare 镜像预填

**模块**：infra
**项目里程碑**：M1 复现
**状态**：已验证
**日期**：2026-09-25
**依赖**：`INFRA-102t`
**决策依据**：`.xkw/knowledge/adr-1001-m1-reproduction-infra.md` D2（TUNA，已确认）
**解决阻塞**：B1（`.cache/` 为空）、B4（清单所配 `sjtu` 源失效）

## 目标

在 `.cache/` 预填 `llvm-project.git` 与 `qemu.git` 两个**浅 bare 镜像**，各含 `manifests/components.lock.toml` 锁定的 commit，使 `make fetch` 能在**完全离线**的前提下重建 `.work/source/`。

**本任务不改动仓库任何文件**（`.cache/` 被 `.gitignore` 忽略）。

## 背景：为什么不直接 `make fetch`

`tools/infra/fetch.py:47-61` 的 `sync_mirror()` 在 `.cache/<name>.git` **不存在**时会执行 `git clone --mirror` —— **全量历史**，非浅克隆。对 llvm-project 而言是约 30 GB / 数小时，且清单所配的 `sjtu` 源已 302 死循环 ⇒ 必然长时间等待后失败。

`.tao/knowledge/adr-0006` D2 / `adr-0008` D2（只读参考）记录的原始做法正是**浅 bare 预填充**：`git clone --bare --depth 1 --branch <tag>`，且明确「**非 treeless**，worktree 可离线重建」。本任务照此执行。

## 范围

**在范围内**：`git clone --bare --depth 1` × 2、锁定 commit 与 object 数校验。

**不在范围内**：修改 `manifests/components.lock.toml`、修改 `.tao/` 的 ADR、unshallow、完整历史克隆、gem5（`enabled = false`）。

## 步骤

### S1 — 预填 LLVM

```bash
cd /home/ubuntu/DADAO-v5
git clone --bare --depth 1 --branch llvmorg-23.1.1 \
  https://mirrors.tuna.tsinghua.edu.cn/git/llvm-project.git \
  .cache/llvm-project.git
```

实测基线（2026-09-25 同命令预跑）：**284.61 MiB / 189,410 objects / <100 s / ~6.08 MiB/s**。

### S2 — 预填 QEMU

```bash
git clone --bare --depth 1 --branch v11.1.1 \
  https://mirrors.tuna.tsinghua.edu.cn/git/qemu.git \
  .cache/qemu.git
```

`.tao/knowledge/adr-0008` D2 记录：51.78 MiB / 11,630 objects / 4.1 s。

### S3 — 校验锁定 commit

```bash
git -C .cache/llvm-project.git cat-file -e 6dfe1677ab8dffbc6ec13d53a1e0215d75147689^{commit}
git -C .cache/qemu.git        cat-file -e c3d48b7d1e89604920e5b81b91140c2ad39a1943^{commit}
git -C .cache/llvm-project.git rev-parse HEAD
git -C .cache/qemu.git        rev-parse HEAD
```

两个 commit 取自 `manifests/components.lock.toml` 的 `commit` 字段（**唯一权威**，勿从 ADR 抄）。`HEAD` 应分别等于它们（浅克隆的默认分支即该 tag 的 commit）。

### S4 — 校验 bare/shallow、对象总数与本地对象完整性

```bash
set -euo pipefail

clean_git() {
  env \
    -u GIT_DIR \
    -u GIT_WORK_TREE \
    -u GIT_OBJECT_DIRECTORY \
    -u GIT_ALTERNATE_OBJECT_DIRECTORIES \
    git "$@"
}

check_mirror() {
  local repo=$1
  local commit=$2
  local expected_total=$3
  local stats loose packed total partial_keys missing alternates

  test "$(clean_git -C "$repo" rev-parse --is-bare-repository)" = true
  test "$(clean_git -C "$repo" rev-parse --is-shallow-repository)" = true

  stats=$(clean_git -C "$repo" count-objects -v)
  printf '%s\n' "$stats"
  loose=$(printf '%s\n' "$stats" | awk '$1 == "count:" {print $2}')
  packed=$(printf '%s\n' "$stats" | awk '$1 == "in-pack:" {print $2}')
  test -n "$loose"
  test -n "$packed"
  total=$((loose + packed))
  test "$total" -eq "$expected_total"

  # alternates 会让对象来自仓库外部，不能证明镜像自身可离线重建。
  alternates="$repo/objects/info/alternates"
  if test -e "$alternates" || test -L "$alternates"; then
    test -f "$alternates"
    test ! -s "$alternates"
  fi

  # 仅检查仓库本地配置；无匹配的 exit 1 属正常。
  partial_keys=$(
    {
      clean_git -C "$repo" config --local --get-regexp '.*' 2>/dev/null || :
    } |
      awk '
        {
          key = tolower($1)
          if (key == "extensions.partialclone" || key ~ /^remote\..*\.promisor$/ || key ~ /^remote\..*\.partialclonefilter$/) {
            print $1
          }
        }
      '
  )
  test -z "$partial_keys"

  missing=$(
    clean_git -C "$repo" rev-list --objects --missing=print "$commit" |
      awk '$1 ~ /^\?/ {print}'
  )
  test -z "$missing"

  clean_git -C "$repo" fsck --full --no-dangling "$commit"
}

check_mirror \
  .cache/llvm-project.git \
  6dfe1677ab8dffbc6ec13d53a1e0215d75147689 \
  189410

check_mirror \
  .cache/qemu.git \
  c3d48b7d1e89604920e5b81b91140c2ad39a1943 \
  11630
```

- `count-objects -v` 的 `count` 只统计 loose objects；本任务的总对象数判据是 `count + in-pack`，应分别为 **189,410**（llvm）/ **11,630**（qemu）。
- S4 中所有 Git 调用均经 `clean_git` 清除 `GIT_DIR`、`GIT_WORK_TREE`、`GIT_OBJECT_DIRECTORY`、`GIT_ALTERNATE_OBJECT_DIRECTORIES`，防止调用环境注入外部对象库。
- “非 treeless、对象可完全离线使用”须由四项共同证明：无非空 alternates；本地配置中无 partial-clone/promisor/filter；锁定 commit 的可达对象无 `?OID`；`git fsck` 成功。

### S5 — 直接验证 `sync_mirror` 本地短路且不创建源码树（**关键**）

```bash
set -euo pipefail

mapfile -t pycache_before < <(
  find tools/infra \
    \( -type d -name '__pycache__' -o -type f -name '*.pyc' \) \
    -print |
    sort
)

env \
  -u GIT_DIR \
  -u GIT_WORK_TREE \
  -u GIT_OBJECT_DIRECTORY \
  -u GIT_ALTERNATE_OBJECT_DIRECTORIES \
  python3.12 -B tools/infra/manifest_check.py

# 必须在 S4 全部通过后执行。S4 已排除 promisor、partial clone
# 和外部 alternates，避免 has_commit/cat-file 发生 lazy fetch。
test ! -e .work/source

env \
  -u GIT_DIR \
  -u GIT_WORK_TREE \
  -u GIT_OBJECT_DIRECTORY \
  -u GIT_ALTERNATE_OBJECT_DIRECTORIES \
  python3.12 -B - <<'PY'
import contextlib
import importlib.util
import io
import tomllib
from pathlib import Path

root = Path.cwd()
fetch_path = root / "tools/infra/fetch.py"
source_root = root / ".work/source"

assert not source_root.exists(), (
    "INFRA-103t precondition violated: .work/source already exists"
)

spec = importlib.util.spec_from_file_location(
    "dadao_infra_fetch_for_infra_103t",
    fetch_path,
)
assert spec is not None and spec.loader is not None
fetch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch)

with (root / "manifests/components.lock.toml").open("rb") as stream:
    manifest = tomllib.load(stream)

components = {
    component["name"]: component
    for component in manifest.get("component", [])
    if component.get("enabled")
}
assert set(components) == {"llvm-project", "qemu"}, set(components)

def forbid_clone_or_fetch(*args, **kwargs):
    raise AssertionError(
        f"sync_mirror attempted clone/fetch command: {args!r}"
    )

fetch.run = forbid_clone_or_fetch

expected_lines = [
    "fetch: mirror llvm-project.git already has 6dfe1677ab8d; skipping fetch",
    "fetch: mirror qemu.git already has c3d48b7d1e89; skipping fetch",
]

actual_lines = []
for name in ("llvm-project", "qemu"):
    component = components[name]
    mirror = root / ".cache" / f"{name}.git"
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        fetch.sync_mirror(
            mirror,
            "https://127.0.0.1:9/MUST-NOT-CONNECT",
            component["commit"],
        )
    actual_lines.extend(captured.getvalue().splitlines())

assert actual_lines == expected_lines, (actual_lines, expected_lines)
assert not source_root.exists(), (
    "INFRA-103t crossed into INFRA-104t by creating .work/source"
)

print("\n".join(actual_lines))
PY

test ! -e .work/source

mapfile -t pycache_after < <(
  find tools/infra \
    \( -type d -name '__pycache__' -o -type f -name '*.pyc' \) \
    -print |
    sort
)

test "$(printf '%s\n' "${pycache_after[@]}")" = \
     "$(printf '%s\n' "${pycache_before[@]}")"
```

期望标准输出精确为：

```text
fetch: mirror llvm-project.git already has 6dfe1677ab8d; skipping fetch
fetch: mirror qemu.git already has c3d48b7d1e89; skipping fetch
```

S5 不调用 `fetch.py` 的 `main()`，因为 `main()` 会创建 `.work/source/` 并提前进入 `INFRA-104t` 范围。测试先把 `fetch.run` 替换为“一旦尝试 clone/fetch 就失败”，再直接调用 `sync_mirror()`；前后均要求 `.work/source` 不存在。`python3.12 -B` 禁止本轮产生字节码，且执行后相对启动 baseline 不得新增 `__pycache__` 或 `.pyc`。

## 验收

| # | 项 | 判据 | 状态 |
| --- | --- | --- | --- |
| 1 | 两镜像存在 | `ls -d .cache/llvm-project.git .cache/qemu.git` | 现在可跑 |
| 2 | 锁定 commit 命中 | 两条 `cat-file -e <commit>^{commit}` 均 exit **0** | 现在可跑 |
| 3 | HEAD 等于锁定 commit | 两条 `rev-parse HEAD` 与 `manifests/components.lock.toml` 的 `commit` **逐字符相同** | 现在可跑 |
| 4 | bare + shallow | 两仓库的 `--is-bare-repository` 与 `--is-shallow-repository` 均为 `true` | 现在可跑 |
| 5 | object 总数符合 ADR 记录 | `count + in-pack`：llvm **189,410** / qemu **11,630** | 现在可跑 |
| 6 | 对象库自包含 | 无非空 alternates；本地配置无 partial-clone/promisor/filter | 现在可跑 |
| 7 | 锁定 commit 无缺失对象 | `rev-list --missing=print` 无 `?OID`，且 `fsck` exit 0 | 现在可跑 |
| 8 | `sync_mirror` 不联网 | S5 精确输出两条 `skipping fetch`，禁止的 `run()` 未触发 | 现在可跑（S4 后） |
| 9 | 未越界进入源码拉取 | S5 前后 `.work/source` 均不存在，且相对 baseline 无新增 pycache/pyc | 现在可跑 |
| 10 | 磁盘占用 | `.cache/` 合计 < 1 GiB | 现在可跑 |
| 11 | 仓库工作区零改动 | `git status --porcelain` 与执行前逐字节相同 | 现在可跑 |
| 12 | 完整历史可用性 | —— | **不适用**（本就是浅镜像；ADR 已声明该边界） |

## 风险与预案

| 风险 | 预案 |
| --- | --- |
| TUNA 临时不可达 | 已测备用：BFSU（`mirrors.bfsu.edu.cn/git/`）、NJU（`mirror.nju.edu.cn/git/`）均可达且 tag SHA **完全相同**（实测三站 `llvmorg-23.1.1^{}` 与 `v11.1.1^{}` 逐字符一致）。换源须先经用户确认（`mirrors.md`） |
| 浅镜像上 `git fetch origin <commit>` 被拒 | 属 `INFRA-104t` 风险，不在本任务；预案见该任务书 S3 |
| 磁盘不足 | `.cache/` 落 `/mnt`（剩余 186 GB），充裕 |

## 完成区

执行时间：2026-09-26 03:01:55Z – 03:07:01Z。engineer 自执行，**未 commit、未 push、未 unshallow、未改远端配置**。

### 1. 两条 clone（真实数据）

| 步骤 | 命令 | exit | 耗时 | 体积（`du -sb`） | 体积 | 实际吞吐 |
| --- | --- | --- | --- | --- | --- | --- |
| S1 | `git clone --bare --depth 1 --branch llvmorg-23.1.1 https://mirrors.tuna.tsinghua.edu.cn/git/llvm-project.git .cache/llvm-project.git` | **0** | **119.53 s** | **303,806,865 B** | 289.73 MiB | ≈2.42 MiB/s |
| S2 | `git clone --bare --depth 1 --branch v11.1.1 https://mirrors.tuna.tsinghua.edu.cn/git/qemu.git .cache/qemu.git` | **0** | **17.77 s** | **45,211,531 B** | 43.12 MiB | ≈2.42 MiB/s |

源 = TUNA 裸连，**一次成功，未重试、未换源**（BFSU/NJU/GitHub 均未使用）。日志：`.work/log/infra/INFRA-103t-s1-clone-llvm.log`、`.work/log/infra/INFRA-103t-s2-clone-qemu.log`。

> 体积与 ADR-1001 D2 预跑基线（284.61 MiB / 51.78 MiB）略有差异，**object 总数逐位相同**（见下）；`du` 报的是块占用，随文件系统而变。耗时亦不同（119.53 s / 17.77 s vs `<100 s` / `4.1 s`），属当次网络实况。

> 日志勘误（已在 `INFRA-103t-s2-clone-qemu.log` 内标注）：S2 日志中 `cache_total_bytes=20` / `du -sh .cache = 0` 是**错误读数**——`.cache` 是指向 `/mnt/dadao-v5/.cache` 的符号链接，普通 `du` 不跟随符号链接。正确读数见该日志末尾的 `du -sbL` 段与下表。

### 2. S3 锁定 commit

命令见 S3；日志 `.work/log/infra/INFRA-103t-s3-verify-commits.log`。commit 取自 `manifests/components.lock.toml`（未从 ADR 抄）。

| 项 | 结果 |
| --- | --- |
| `cat-file -e 6dfe1677ab8dffbc6ec13d53a1e0215d75147689^{commit}` | exit **0** |
| `cat-file -e c3d48b7d1e89604920e5b81b91140c2ad39a1943^{commit}` | exit **0** |
| `rev-parse HEAD`（llvm / qemu） | `6dfe1677ab8dffbc6ec13d53a1e0215d75147689` / `c3d48b7d1e89604920e5b81b91140c2ad39a1943` |
| 与清单 `commit` 字段逐字符比较 | `llvm_HEAD_eq_manifest=PASS`、`qemu_HEAD_eq_manifest=PASS` |
| tag 解析 | `llvmorg-23.1.1^{commit}` / `v11.1.1^{commit}` 与上述逐字符相同 |
| shallow 边界（深度 1 的直接证据） | 两仓库 `shallow` 文件内容分别就是该 pinned commit |

### 3. S4 bare/shallow、对象总数与对象库自包含

**任务书缺陷及当场修正（如实记录）**：engineer 执行时，S4 代码块中的 awk 程序在 `if (` 后换行，**gawk 5.1.0 与 mawk 1.3.4 均报语法错误**；`set -e` 因而在该步中止，其后的 missing-objects 与 `fsck` 未执行。

- 失败现场与最小复现：`.work/log/infra/INFRA-103t-s4a-verbatim-awk-fail.log`、`.work/log/infra/INFRA-103t-s4a-awk-diagnosis.log`（`gawk_exit=1`、`mawk_exit=2`）。
- engineer 先在临时副本做**逐字节等价的排版修正**：把 `if (...)` 的三段条件合并到同一行，三个模式本身一字未改。`diff -u` 见 `.work/log/infra/INFRA-103t-s4b-corrected.log`；修正后运行 exit 0。
- 主会话在 dispatch 收尾时已把同一排版修正写回上方 S4 正文，并从任务书重新提取、在真实镜像上完整复跑；`clean_git`、四个完整性判据和两个 expected_total 均未弱化。复跑日志：`.work/log/infra/INFRA-103t-s4-after-taskbook-fix.log`。
- **object 总数与 fsck 判据未弱化**（未放宽 `count+in-pack`、未跳过 `fsck`）。

显式逐项证据 + 反例门控（日志 `.work/log/infra/INFRA-103t-s4c-explicit-evidence.log`，`S4C_SCRIPT_EXIT=0`）：

| 仓库 | `count`(loose) | `in-pack` | `count+in-pack` | expected | alternates | partial-clone/promisor/filter | `?OID` 缺失行 | `fsck` exit | bare | shallow |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `.cache/llvm-project.git` | 0 | 189,410 | **189,410** | 189,410 | ABSENT | 0（awk 与独立 `grep -Ei` 双向一致） | **0**（`rev-list --objects` 189,409 行） | **0** | true | true |
| `.cache/qemu.git` | 0 | 11,630 | **11,630** | 11,630 | ABSENT | 0（两法一致） | **0**（11,629 行） | **0** | true | true |

- 两仓库本地 config 全量仅 4 项（`core.repositoryformatversion/filemode/bare` + `remote.origin.url`），无 promisor 类键；`objects/info/alternates` 不存在。
- `total` 比 `rev-list --objects` 行数多 1 的原因已核实：多出的正是 annotated **tag object**（llvm `e7ce3600b55034ddf819638f395e3c475fad5be2`、qemu `5e35f26695645b20931e10d8567c7e0169e62c07`，`cat-file -t` 均为 `tag`），tag object 在 pack 内但不被 `rev-list --objects <commit>` 列出。**与 ADR 记录的数字逐位一致，非缺对象。**
- **判据非恒真的反例门控**：在 `/tmp` 合成 bare 仓写入 `extensions.partialclone` / `remote.origin.promisor` / `remote.origin.partialCloneFilter` 三键后，同一检测器输出 3 行（`positive_control_detected_count=3`），即 `test -z "$partial_keys"` 在该情形下**会失败**；另用错误期望值 189,411 与全零 HEAD 验证 `-eq` / `=` 比较确有鉴别力。

### 4. S5 `sync_mirror` 本地短路且不建源码树

按任务书 S5 块**逐字提取**执行（`/tmp/opencode/INFRA-103t/s5-sync-mirror.sh`，取自任务书 149–250 行），**未调用 `fetch.py main()`**。日志 `.work/log/infra/INFRA-103t-s5-sync-mirror.log`，`S5_SCRIPT_EXIT=0`。标准输出：

```text
enabled components: llvm-project, qemu
references: 2
manifest validation: PASS
fetch: mirror llvm-project.git already has 6dfe1677ab8d; skipping fetch
fetch: mirror qemu.git already has c3d48b7d1e89; skipping fetch
```

前 3 行来自块内的 `manifest_check.py`；**harness 自身 stdout 经隔离复跑，精确等于期望的两行**（136 B，sha256 `96bca6d0b9c9fc0d272c09b973cb01f49b602b68ab95c23558ae0f64751d55b7`，`repr` 见日志）。日志 `.work/log/infra/INFRA-103t-s5b-harness-isolated.log`，`S5B_SCRIPT_EXIT=0`。

- 传入 URL 为 `https://127.0.0.1:9/MUST-NOT-CONNECT` 且 `fetch.run` 被替换为一调用即 `AssertionError` 的桩；`sync_mirror()` 两次都走 `has_commit()` 命中分支 ⇒ **未联网、未 clone、未 fetch**。
- **桩非恒真的反例门控**：同一 harness 内两个对照（只用 `/tmp` 路径，绝不碰真实镜像）——① 镜像不存在 ⇒ 桩被触发并打印 `('git','clone','--mirror',...)`；② 镜像存在但无该 commit ⇒ 桩被触发并打印 `('git','-C',...,'fetch','--prune')`。两例均 `guard_fired=YES`。
- `.work/source`：S5 前不存在、S5 后不存在、隔离复跑后仍不存在（`POST: .work/source absent`）。
- `tools/infra` 下 `__pycache__`/`.pyc` 清单前后 `diff` 为空（原有 12 个 `cpython-310.pyc` 为本任务之前既存，本轮 `python3.12 -B` **未新增**）。
- 端到端「离线重建 `.work/source/`」**本任务未验证且不在范围**——S5 按设计不进入 `INFRA-104t`；该能力由 S4 的对象库自包含四项 + 本节短路共同支撑，最终由 `INFRA-104t` 端到端承担。

### 5. 验收逐条结论

| # | 项 | 结论 | 真实证据 |
| --- | --- | --- | --- |
| 1 | 两镜像存在 | **PASS** | `ls -d .cache/llvm-project.git .cache/qemu.git` exit 0；解析为 `/mnt/dadao-v5/.cache/{llvm-project,qemu}.git` |
| 2 | 锁定 commit 命中 | **PASS** | 两条 `cat-file -e <commit>^{commit}` 均 exit **0** |
| 3 | HEAD 等于锁定 commit | **PASS** | 两条 `rev-parse HEAD` 与清单 `commit` 字段**逐字符相同** |
| 4 | bare + shallow | **PASS** | 两仓库 `--is-bare-repository`/`--is-shallow-repository` 均 `true`；`shallow` 文件内容 = pinned commit |
| 5 | object 总数 | **PASS** | `count+in-pack`：llvm **189,410**、qemu **11,630**（`count` 均为 0） |
| 6 | 对象库自包含 | **PASS** | alternates ABSENT；无 partial-clone/promisor/filter（awk + 独立 grep 双法一致）；反例门控已证非恒真 |
| 7 | 无缺失对象 | **PASS** | `--missing=print` 的 `?OID` 行数 **0 / 0**；`fsck --full --no-dangling` exit **0 / 0** |
| 8 | `sync_mirror` 不联网 | **PASS** | 精确两条 `skipping fetch`（136 B，sha256 见上）；`run()` 桩两对照均被触发 |
| 9 | 未越界进入源码拉取 | **PASS** | `.work/source` 三次检查均 absent；`tools/infra` pycache/pyc 前后 `diff` 为空 |
| 10 | 磁盘占用 | **PASS** | `.cache` 合计 **349,022,492 B = 332.85 MiB = 0.3251 GiB < 1 GiB**（`/mnt` 余 186 G） |
| 11 | 仓库工作区零改动 | **PASS** | `git status --porcelain=v1 --untracked-files=all` sha256 `2436ad65bae0b497e059771046a8e782369362378a2479a039d31e9eed0b6e3b`，与开工 baseline **逐字节相同**（`cmp` 通过）；18 个 baseline dirty 文件内容 sha256 全部 `OK` |
| 12 | 完整历史可用性 | **N/A** | 本就是浅镜像，ADR-1001 D2 已声明该边界 |

**保护路径零新增 diff**（`.work/log/infra/INFRA-103t-accept-all.log`）：`git diff --stat -- .tao manifests tools components tests contracts spec Makefile` 输出为空；`git status` 在上述 8 个路径下的条目数均为 **0**。`find . -newermt "2026-09-26 02:58"`（排除 `.git/`、`.cache/`、`.work/`）输出为空 ⇒ 本任务未触碰任何仓库文件。

日志清单：`INFRA-103t-s1-clone-llvm.log`、`-s2-clone-qemu.log`、`-s3-verify-commits.log`、`-s4a-verbatim-awk-fail.log`、`-s4a-awk-diagnosis.log`、`-s4b-corrected.log`、`-s4c-explicit-evidence.log`、`-s5-sync-mirror.log`、`-s5b-harness-isolated.log`、`-accept-all.log`、`-accept-extras.log`（均在 `.work/log/infra/`）。

### 6. 风险与遗留

1. **任务书 S4 awk 排版缺陷已当场修正**：三个匹配条件未变；修正后的任务书代码块已从正文重新提取并在真实镜像上复跑通过，不再作为 deferred。
2. **`.cache/` 依赖 `/mnt` 挂载**（`.cache`、`.work` 均为指向 `/mnt/dadao-v5/` 的符号链接）。挂载缺失或被清理时，`make fetch` 会退回 `git clone --mirror` 全量克隆并打到失效的 `sjtu` 源——该问题归属 `INFRA-107t`（ADR-1001 D3 遗留），本任务未触及。
3. **未做端到端离线重建**：`make fetch` 全流程（创建 `.work/source/`、checkout、patch）由 `INFRA-104t` 验证；若那里出现「浅镜像上 `git fetch origin <commit>` 被拒」，属该任务风险，不回溯本任务。
4. **磁盘**：`.cache` 0.3251 GiB 远低于 1 GiB 判据；`/mnt` 尚余 186 G，`INFRA-105t`/`106t` 的构建产物（约 20 GB）不受影响。

### 7. 独立验收（2026-09-26）

- **reviewer：Accepted**。独立重跑 S3/S4/S5 均 exit 0；对错误锁值、HEAD 不等、非 bare、非 shallow、对象总数错误、alternates、partial clone、缺失/损坏对象、错误清单、错误 stdout、clone/fetch 路径、source/pycache 越界、缺镜像、磁盘超限和 dirty status 共 18 类反例逐项注入，均证明 `git diff --name-only` 非空并得到真实非零退出。
- **还原证据**：每轮反例后 `restored_clean=PASS`；合成树最终 clean、派生产物已清理；真实 S3/S4/S5 复绿，`.work/source` 仍不存在，真实 status 与 18 个 dirty 文件内容均保持审查 baseline。证据见 `.work/log/infra/INFRA-103t-review-*.log`。
- **architect：Accepted**。交叉复核确认反例失败来自目标判据、还原证据充分、完成区与独立输出一致；`INFRA-104t` 的源码树重建和 `INFRA-107t` 的源治理边界清晰，无新增 BLOCKED、跨模块阻断或 ADR decision。
