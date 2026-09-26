# INFRA-104t: 源码拉取与补丁系列应用

**模块**：infra
**项目里程碑**：M1 复现
**状态**：已验证
**日期**：2026-09-25
**依赖**：`INFRA-103t`（已验证；仍须实查能力）
**解决阻塞**：B1（`.work/source/` 不存在）
**决策依据**：`.xkw/knowledge/adr-1001-m1-reproduction-infra.md` D3（Accepted）

## 目标与成功定义

从仓库本地 `.cache/{llvm-project,qemu}.git` 浅 bare 镜像重建 `.work/source/{llvm-project,qemu}`，并把两个 `components/*/patches/series` 各 8 个补丁用 `git am` 忠实重放到 manifest 锁定基线之上。

成功必须同时满足：确定环境中的串行 `make prepare` 真实退出 0；fetch 精确走两个本地镜像；`.cache/**` 完整内容前后逐字节快照一致；每个 base 都是 HEAD 祖先，`base..HEAD=8` 且浅历史总数 9；邮件 Subject 与 commit Subject 逐条一致；LLVM/QEMU 结构门禁与 decodetree 合约门禁通过；两个 base-to-HEAD 文件差异均非空；仓库 dirty baseline 受保护。

本任务不验证可编译性，不新增 ISA 语义。

## 权威来源、依赖与边界

- `manifests/components.lock.toml`：组件名、锁定 commit、patch series。
  - LLVM base：`6dfe1677ab8dffbc6ec13d53a1e0215d75147689`
  - QEMU base：`c3d48b7d1e89604920e5b81b91140c2ad39a1943`
- `Makefile`、`tools/infra/fetch.py`、`tools/infra/apply_series.py`：`manifest-check → fetch → apply-series`。
- `contracts/opcodes.yaml` 与 `tools/qemu/validate_decodetree.py`：256 条 decodetree 结构契约（178 active + 78 `excluded_m1`）。
- `.xkw/knowledge/adr-1001-m1-reproduction-infra.md` D3 已 Accepted；本任务不改变 decision。

`INFRA-103t` 的状态标签不是充分前置。S0 必须重验镜像 bare/shallow、HEAD、advertised HEAD、锁定对象以及宿主工具。当前锁值就是镜像 advertised HEAD，因此浅本地 clone/fetch 的能力前置已具备；实际仍失败则停止，不绕过。

### 允许产生/修改

- `.work/source/{llvm-project,qemu}`
- `.work/log/infra/INFRA-104t-*.log`
- `/tmp/opencode/INFRA-104t/`
- 本任务书 `## 完成区`（执行结束后的唯一仓库内记录变更；状态转换由主会话负责）

### 禁止触碰

- `.cache/**` 的任何内容、配置或链接；不得 unshallow
- `tools/`、`components/*/patches/`、`manifests/`、`contracts/`、`tests/`、`spec/`、`.tao/`、其它 `.xkw/` 文件和实现文件
- 不下载、不手工联网 fetch、不改脚本、不手工修 patch、不提交

本任务独占 `.work/source` 和 `.cache` 读取窗口，不得与 fetch/apply/clean/build 并行。关键路径为 `INFRA-103t → INFRA-104t → {INFRA-105t,INFRA-106t}`。

## 全局执行与失败规则

1. 每个多判据阶段都必须由下文完整 Bash verifier 执行；统一 `set -euo pipefail`。禁止复制散装命令后让最后一条偶然决定退出码。
2. 经 `tee` 的 verifier 均按模板捕获并检查 `${PIPESTATUS[0]}`；任何非零立即停止。
3. 任何 `.work/source` 创建或 prepare 前，它必须既不是现存路径也不是悬空符号链接：`test ! -e .work/source && test ! -L .work/source`。该门禁必须在 `set -euo pipefail` 中执行；允许先创建 `/tmp/opencode/INFRA-104t/` 检查脚本与 `.work/log/infra/` 日志目录，但 S0 自身仍在任何 `mkdir` 前执行双门禁。
4. `make prepare` 只允许运行一次。任何失败保留现场并停止；不得 `make clean-work`、reset、abort 后继续、手工 checkout、跳过 fetch 或自动重试。新的尝试必须走新的 `/dispatch`。
5. `git fetch origin <commit>` 被拒或 `git am` 冲突时立即停止并报告；不得改脚本或手工绕过。
6. 完成区数字只能来自真实日志。结构/重放证据不得称为“可编译”。

## Dispatch 清洁 Git 环境与 baseline（主会话前置）

所有阶段只允许使用唯一 Git wrapper `/tmp/opencode/INFRA-104t/git-clean`。主会话在采集本轮 baseline 前先创建以下两个 wrapper；二者的 allowlist 必须逐字相同：

```bash
mkdir -p /tmp/opencode/INFRA-104t
cat > /tmp/opencode/INFRA-104t/git-clean <<'SH'
#!/usr/bin/env bash
set -euo pipefail
base=/tmp/opencode/INFRA-104t
exec env -i \
  PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
  LC_ALL=C HOME="$base/home" XDG_CONFIG_HOME="$base/xdg" \
  GIT_CONFIG_NOSYSTEM=1 GIT_TEMPLATE_DIR="$base/template" \
  git "$@"
SH
cat > /tmp/opencode/INFRA-104t/run-isolated <<'SH'
#!/usr/bin/env bash
set -euo pipefail
base=/tmp/opencode/INFRA-104t
exec env -i \
  PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
  LC_ALL=C HOME="$base/home" XDG_CONFIG_HOME="$base/xdg" \
  GIT_CONFIG_NOSYSTEM=1 GIT_TEMPLATE_DIR="$base/template" \
  "$@"
SH
chmod 0755 /tmp/opencode/INFRA-104t/git-clean /tmp/opencode/INFRA-104t/run-isolated
```

identity 不得从 ambient Git 读取。主会话须把 `IDENTITY_CONFIG` 设置为明确、可信且只读的现有 global config 路径，并用清洁环境生成 JSON 文件；不硬编码 name/email：

```bash
IDENTITY_CONFIG=/home/ubuntu/.gitconfig  # 若可信配置不在此处，主会话显式替换并记录路径
test -r "$IDENTITY_CONFIG"
rm -rf /tmp/opencode/INFRA-104t/home /tmp/opencode/INFRA-104t/xdg \
       /tmp/opencode/INFRA-104t/template /tmp/opencode/INFRA-104t/hooks
mkdir -p /tmp/opencode/INFRA-104t/dispatch /tmp/opencode/INFRA-104t/home \
         /tmp/opencode/INFRA-104t/xdg /tmp/opencode/INFRA-104t/template \
         /tmp/opencode/INFRA-104t/hooks
env -i PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
  LC_ALL=C GIT_CONFIG_NOSYSTEM=1 IDENTITY_CONFIG="$IDENTITY_CONFIG" \
  OUT=/tmp/opencode/INFRA-104t/dispatch/git-identity \
  python3.12 -B - <<'PY'
import json, os, subprocess
cfg = os.environ["IDENTITY_CONFIG"]
def get(key):
    value = subprocess.run(
        ["git", "config", "--file", cfg, "--get", key], check=True,
        text=True, stdout=subprocess.PIPE,
    ).stdout.rstrip("\n")
    if not value or "\n" in value or "\0" in value:
        raise SystemExit(f"invalid {key}")
    return value
with open(os.environ["OUT"], "w", encoding="utf-8") as stream:
    json.dump({"format": 1, "name": get("user.name"), "email": get("user.email")}, stream)
    stream.write("\n")
PY
```

`git-identity` 格式固定为单个 JSON object：`format=1`，`name`/`email` 为非空无换行字符串。随后在 clean `env -i` 下按该文件写 isolated config：

```bash
/tmp/opencode/INFRA-104t/run-isolated python3.12 -B - <<'PY'
import json, subprocess
from pathlib import Path
base = Path("/tmp/opencode/INFRA-104t")
identity = json.loads((base / "dispatch/git-identity").read_text(encoding="utf-8"))
if identity.get("format") != 1 or not identity.get("name") or not identity.get("email"):
    raise SystemExit("invalid git-identity")
cfg = base / "home/.gitconfig"
cfg.unlink(missing_ok=True)
for key, value in (
    ("user.name", identity["name"]), ("user.email", identity["email"]),
    ("commit.gpgSign", "false"), ("core.hooksPath", str(base / "hooks")),
):
    subprocess.run(["git", "config", "--file", str(cfg), key, value], check=True)
PY
/tmp/opencode/INFRA-104t/git-clean var GIT_COMMITTER_IDENT >/dev/null
```

主会话使用 wrapper 执行 workflow 的精确 status 命令并采集 baseline；S0/S6 必须复用同一 wrapper：

```bash
cd /home/ubuntu/DADAO-v5
/tmp/opencode/INFRA-104t/git-clean status --porcelain=v1 --untracked-files=all \
  > /tmp/opencode/INFRA-104t/dispatch/git-status.before
sha256sum /tmp/opencode/INFRA-104t/dispatch/git-status.before \
  > /tmp/opencode/INFRA-104t/dispatch/git-status.before.sha256
cp .xkw/tasks/infra/INFRA-104t-源码拉取与补丁系列应用.md \
  /tmp/opencode/INFRA-104t/dispatch/task.before
```

dirty 内容哈希清单仍由主会话按 baseline 中路径逐项生成到 `dispatch/dirty-content-sha256.before`。这是 workflow 指定 status 命令在 clean Git environment 下的执行，不改变命令参数。

## S0 — 启动保护、宿主门禁与 cache before

主会话须提供上述新 baseline status、status SHA256、dirty 内容 SHA256、`task.before` 与 `git-identity`。

先建立 `/tmp/opencode/INFRA-104t/s0.sh`，内容如下：

```bash
#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/DADAO-v5
: "${BASELINE_STATUS:?set BASELINE_STATUS to the dispatch status file}"
: "${BASELINE_STATUS_SHA256:?set BASELINE_STATUS_SHA256 to the expected digest}"
: "${BASELINE_HASHES:?set BASELINE_HASHES to the dispatch dirty hash file}"
: "${TASK_BEFORE:?set TASK_BEFORE to the dispatch copy of this task file}"
tmp=/tmp/opencode/INFRA-104t
gitc="$tmp/git-clean"
isolated="$tmp/run-isolated"

# command、test、printf、case、for 等为 Bash builtin；先检查 S1–S7
# 用到的全部外部命令，再做任何 mkdir。
for tool in bash env git make python3.12 sha256sum cmp grep awk tee df cat wc rm mkdir cp sed chmod; do
  command -v "$tool" >/dev/null
done
test ! -e .work/source
test ! -L .work/source
test -x "$gitc"
test -x "$isolated"
test -f "$tmp/dispatch/git-identity"
mkdir -p .work/log/infra

test "$(sha256sum "$BASELINE_STATUS" | awk '{print $1}')" = "$BASELINE_STATUS_SHA256"
sha256sum -c -- "$BASELINE_HASHES"
cmp -- "$TASK_BEFORE" .xkw/tasks/infra/INFRA-104t-源码拉取与补丁系列应用.md

bash_major=${BASH_VERSINFO[0]}
test "$bash_major" -ge 4
python3.12 -B - <<'PY'
import sys, tomllib, yaml
assert sys.version_info >= (3, 12), sys.version
print(f"python={sys.version.split()[0]} yaml={yaml.__version__}")
PY
make --version
"$isolated" python3.12 -B - <<'PY'
import json, subprocess
from pathlib import Path
base = Path("/tmp/opencode/INFRA-104t")
identity = json.loads((base / "dispatch/git-identity").read_text(encoding="utf-8"))
if identity.get("format") != 1:
    raise SystemExit("invalid identity format")
for key in ("name", "email"):
    value = identity.get(key)
    if not isinstance(value, str) or not value or "\n" in value or "\0" in value:
        raise SystemExit(f"invalid identity {key}")
for name in ("xdg", "template", "hooks"):
    directory = base / name
    if not directory.is_dir() or any(directory.iterdir()):
        raise SystemExit(f"isolated directory is absent or non-empty: {name}")
cfg = base / "home/.gitconfig"
cfg.unlink(missing_ok=True)
for key, value in (
    ("user.name", identity["name"]), ("user.email", identity["email"]),
    ("commit.gpgSign", "false"), ("core.hooksPath", str(base / "hooks")),
):
    subprocess.run(["git", "config", "--file", str(cfg), key, value], check=True)
PY
"$gitc" --version
"$gitc" var GIT_COMMITTER_IDENT >/dev/null
"$gitc" status --porcelain=v1 --untracked-files=all > "$tmp/status.s0"
cmp -- "$BASELINE_STATUS" "$tmp/status.s0"
avail_kib=$(df -Pk /mnt | awk 'NR==2 {print $4}')
case "$avail_kib" in (''|*[!0-9]*) exit 1;; esac
test "$avail_kib" -ge 5242880
printf 'mnt_available_kib=%s\n' "$avail_kib"

for pair in \
  'llvm-project 6dfe1677ab8dffbc6ec13d53a1e0215d75147689' \
  'qemu c3d48b7d1e89604920e5b81b91140c2ad39a1943'; do
  set -- $pair
  name=$1; base=$2; mirror=.cache/$name.git
  test "$("$gitc" -C "$mirror" rev-parse --is-bare-repository)" = true
  test "$("$gitc" -C "$mirror" rev-parse --is-shallow-repository)" = true
  test "$("$gitc" -C "$mirror" rev-parse HEAD)" = "$base"
  test "$("$gitc" ls-remote "$mirror" HEAD | awk '{print $1}')" = "$base"
  "$gitc" -C "$mirror" cat-file -e "$base^{commit}"
done
```

宿主门禁以至少 5 GiB `/mnt` 可用空间为保守下限；打印版本或空间不是 PASS，所有 `test`/assert 必须返回 0。

### 完整 `.cache/**` 快照器

写入 `/tmp/opencode/INFRA-104t/snapshot_cache.py`：

```python
#!/usr/bin/env python3
import argparse
import hashlib
import os
import stat
import subprocess
from pathlib import Path, PurePosixPath

COMPONENTS = ("llvm-project.git", "qemu.git")

def digest_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def emit_tree(label: str, root: Path, out: list[str]) -> None:
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise SystemExit(f"not a directory: {label}")
    out.append(f"{label}\t.\tD")
    def walk(directory: Path, rel: PurePosixPath) -> None:
        entries = sorted(os.scandir(directory), key=lambda e: os.fsencode(e.name))
        for ent in entries:
            child_rel = rel / ent.name
            shown = child_rel.as_posix()
            mode = ent.stat(follow_symlinks=False).st_mode
            path = Path(ent.path)
            if stat.S_ISDIR(mode):
                out.append(f"{label}\t{shown}\tD")
                walk(path, child_rel)
            elif stat.S_ISREG(mode):
                out.append(f"{label}\t{shown}\tF\t{digest_file(path)}")
            elif stat.S_ISLNK(mode):
                out.append(f"{label}\t{shown}\tL\t{os.readlink(path)}")
            else:
                raise SystemExit(f"unsupported entry type: {label}/{shown}")
    walk(root, PurePosixPath("."))

def git(git_cmd: str, repo: Path, *args: str) -> str:
    return subprocess.run(
        [git_cmd, "-C", str(repo), *args], check=True,
        text=True, stdout=subprocess.PIPE,
    ).stdout.rstrip("\n")

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--summary", required=True)
    ap.add_argument("--git", required=True)
    ns = ap.parse_args()
    os.environ["LC_ALL"] = "C"
    lexical = Path(ns.cache)
    lexical_mode = os.lstat(lexical).st_mode
    lines: list[str] = []
    if stat.S_ISLNK(lexical_mode):
        lines.append(f"CACHE_ROOT\t.\tL\t{os.readlink(lexical)}")
    elif stat.S_ISDIR(lexical_mode):
        lines.append("CACHE_ROOT\t.\tD")
    else:
        raise SystemExit("cache lexical root is neither directory nor symlink")
    cache = lexical.resolve(strict=True)
    # CACHE captures every entry under resolved .cache, including unrelated entries.
    emit_tree("CACHE", cache, lines)
    # Fixed component order also snapshots resolved mirror roots if a top-level
    # component entry is itself a symlink.
    mirrors: list[tuple[str, Path]] = []
    for name in COMPONENTS:
        repo = (cache / name).resolve(strict=True)
        emit_tree(f"MIRROR:{name}", repo, lines)
        mirrors.append((name, repo))
    Path(ns.snapshot).write_text("\n".join(lines) + "\n", encoding="utf-8")
    summary: list[str] = []
    for name, repo in mirrors:
        summary.append(f"[{name}]")
        summary.append(f"HEAD={git(ns.git, repo, 'rev-parse', 'HEAD')}")
        summary.append(f"shallow={git(ns.git, repo, 'rev-parse', '--is-shallow-repository')}")
        summary.append("count-objects:")
        summary.extend(git(ns.git, repo, "count-objects", "-v").splitlines())
        summary.append("config:")
        raw = subprocess.run(
            [ns.git, "-C", str(repo), "config", "--local", "--null", "--list"],
            check=True, stdout=subprocess.PIPE,
        ).stdout
        for item in sorted(x for x in raw.split(b"\0") if x):
            summary.append(item.decode("utf-8", "surrogateescape"))
    Path(ns.summary).write_text("\n".join(summary) + "\n", encoding="utf-8")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```

该脚本先对 CLI 传入的 lexical `.cache` 执行 `os.lstat`：snapshot 首行记录 `CACHE_ROOT` 类型；根为 symlink 时记录 `os.readlink` 原始 target，根为目录时记录 `D`，其它类型 fail，然后才 `resolve(strict=True)`。因此根链接从 `a` 改指向内容相同的 `b` 也会使 before/after `cmp` 失败。解析后完整树按名字字节序遍历；输出只含逻辑 label/相对路径，不含解析后的绝对根路径。目录记录 `D`，常规文件记录内容 SHA256，内部符号链接记录 target，异常类型 fail。`CACHE` 覆盖 `.cache/**` 所有条目；固定顺序的两个 `MIRROR:*` 段额外保证顶层镜像若为链接，其解析目标也被完整记录。可读 summary 不能代替完整 snapshot。

把以下内容追加到 `s0.sh` 后执行：

```bash
LC_ALL=C python3.12 -B "$tmp/snapshot_cache.py" \
  --cache .cache \
  --snapshot "$tmp/cache.before" \
  --summary "$tmp/cache-summary.before" \
  --git "$tmp/git-clean"
cat "$tmp/cache-summary.before"
```

运行 S0 verifier：

```bash
bash -o pipefail -c '
  bash /tmp/opencode/INFRA-104t/s0.sh 2>&1 | tee .work/log/infra/INFRA-104t-s0.log
  rc=${PIPESTATUS[0]}; printf "s0_exit=%s\n" "$rc"; exit "$rc"
'
```

## S1 — 确定环境中串行执行一次 prepare

完整 verifier `/tmp/opencode/INFRA-104t/s1-prepare.sh`：

```bash
#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/DADAO-v5
test ! -e .work/source
test ! -L .work/source
tmp=/tmp/opencode/INFRA-104t
test -f "$tmp/home/.gitconfig"
test -d "$tmp/xdg"
test -d "$tmp/template"
test -d "$tmp/hooks"
test -x "$tmp/git-clean"
test -x "$tmp/run-isolated"
"$tmp/git-clean" var GIT_COMMITTER_IDENT >/dev/null

set +e
"$tmp/run-isolated" make -j1 PYTHON=python3.12 prepare 2>&1 \
  | tee .work/log/infra/INFRA-104t-prepare.log
prepare_rc=${PIPESTATUS[0]}
set -e
test "$prepare_rc" -eq 0

log=.work/log/infra/INFRA-104t-prepare.log
test "$(grep -Fxc 'fetch: mirror llvm-project.git already has 6dfe1677ab8d; skipping fetch' "$log")" -eq 1
test "$(grep -Fxc 'fetch: mirror qemu.git already has c3d48b7d1e89; skipping fetch' "$log")" -eq 1
! grep -Fq 'mirror llvm-project.git cloned' "$log" || exit 1
! grep -Fq 'mirror qemu.git cloned' "$log" || exit 1
! grep -Fq 'updated (incremental)' "$log" || exit 1
```

S0 与 S1 使用完全相同的 `env -i` allowlist。固定 PATH、`LC_ALL=C`、隔离 HOME/XDG、`GIT_CONFIG_NOSYSTEM=1` 与空 `GIT_TEMPLATE_DIR`；隔离 `.gitconfig` 只含已验证的非空 identity、`commit.gpgSign=false` 和指向空目录的 `core.hooksPath`。因此 `MAKEFLAGS`/`MFLAGS`/`GNUMAKEFLAGS`、两个 `COMPONENT_SOURCE_*` 覆盖、`GIT_CONFIG_PARAMETERS`/`GIT_CONFIG_COUNT`/`GIT_CONFIG_KEY_*`/`GIT_CONFIG_VALUE_*`、Git 路径/对象库/worktree/identity/date 等 ambient 注入均不会继承。Git 2.34.1 支持这里使用的 `HOME/.gitconfig`、`GIT_CONFIG_NOSYSTEM`、`GIT_TEMPLATE_DIR` 与 `core.hooksPath`；不依赖较新的 `GIT_CONFIG_GLOBAL`。仓库和 local mirror config 仍由 Git 正常读取，只有 system/global/template/hooks 与 ambient env 被隔离。执行时 prepare 输出先落固定日志，再机械检查同一日志：

```bash
bash -o pipefail -c '
  bash /tmp/opencode/INFRA-104t/s1-prepare.sh 2>&1 \
    | tee .work/log/infra/INFRA-104t-s1.log
  rc=${PIPESTATUS[0]}; printf "prepare_verifier_exit=%s\n" "$rc"; exit "$rc"
'
```

日志证据只证明本流程命中本地短路，不能声称宿主绝无任何网络包。

## S2 — 本地来源、基线与历史 verifier

```bash
cat > /tmp/opencode/INFRA-104t/s2-history.sh <<'SH'
#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/DADAO-v5
gitc=/tmp/opencode/INFRA-104t/git-clean
check() {
  local name=$1 base=$2
  local repo=.work/source/$name
  test -d "$repo/.git"
  test "$("$gitc" -C "$repo" config --get remote.origin.url)" = "/home/ubuntu/DADAO-v5/.cache/$name.git"
  test "$("$gitc" -C "$repo" rev-parse --is-shallow-repository)" = true
  "$gitc" -C "$repo" merge-base --is-ancestor "$base" HEAD
  test "$("$gitc" -C "$repo" rev-list --count "$base..HEAD")" -eq 8
  test "$("$gitc" -C "$repo" rev-list --count HEAD)" -eq 9
  test -z "$("$gitc" -C "$repo" status --porcelain=v1 --untracked-files=all)"
  printf '%s origin=%s base_to_head=%s total=%s shallow=true\n' \
    "$name" "$("$gitc" -C "$repo" config --get remote.origin.url)" \
    "$("$gitc" -C "$repo" rev-list --count "$base..HEAD")" \
    "$("$gitc" -C "$repo" rev-list --count HEAD)"
}
check llvm-project 6dfe1677ab8dffbc6ec13d53a1e0215d75147689
check qemu c3d48b7d1e89604920e5b81b91140c2ad39a1943
SH
bash -o pipefail -c '
  bash /tmp/opencode/INFRA-104t/s2-history.sh 2>&1 | tee .work/log/infra/INFRA-104t-history.log
  rc=${PIPESTATUS[0]}; printf "history_exit=%s\n" "$rc"; exit "$rc"
'
```

“apply-series 未报错”不能替代祖先、8、9、shallow 四个机械判据。

## S3 — 完整 Subject oracle 与真实运行

写入 `/tmp/opencode/INFRA-104t/check_subjects.py`：

```python
#!/usr/bin/env python3
import argparse
import email.policy
import re
import subprocess
from email.parser import BytesParser
from pathlib import Path

PREFIX = re.compile(r"^\[PATCH[^\]]*\]\s*")

def fail(message: str) -> "NoReturn":
    raise SystemExit(f"FAIL: {message}")

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--component", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--series", required=True)
    ap.add_argument("--base", required=True)
    ap.add_argument("--git", required=True)
    ap.add_argument("--expected-count", type=int, default=8)
    ns = ap.parse_args()
    repo = Path(ns.repo)
    series = Path(ns.series)
    names = [
        line.strip() for line in series.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if len(names) != ns.expected_count:
        fail(f"{ns.component}: series count {len(names)} != {ns.expected_count}")
    expected: list[str] = []
    for index, name in enumerate(names, 1):
        patch = series.parent / name
        with patch.open("rb") as stream:
            message = BytesParser(policy=email.policy.default).parse(stream)
        header = message["Subject"]
        if header is None:
            fail(f"{ns.component}[{index}]: missing Subject in {name}")
        decoded = str(header)
        expected.append(PREFIX.sub("", decoded, count=1))
    result = subprocess.run(
        [ns.git, "-C", str(repo), "log", "--reverse", "--format=%s", f"{ns.base}..HEAD"],
        check=True, text=True, stdout=subprocess.PIPE,
    )
    actual = result.stdout.splitlines()
    if len(actual) != ns.expected_count:
        fail(f"{ns.component}: log count {len(actual)} != {ns.expected_count}")
    failed = False
    for index, (want, got) in enumerate(zip(expected, actual), 1):
        mark = "OK" if want == got else "FAIL"
        print(f"{ns.component}[{index}] {mark} expected={want!r} actual={got!r}")
        failed |= want != got
    if failed:
        return 1
    print(f"{ns.component}: PASS series={len(names)} log={len(actual)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```

CLI 同时服务真实树和 S7 合成树。Subject 缺失即 fail；`policy.default` 解码/unfold 后通过 `str(header)` 获取；只删除一次开头 `^\[PATCH[^\]]*\]\s*`；series/log 均严格为 8。

```bash
cat > /tmp/opencode/INFRA-104t/s3-subjects.sh <<'SH'
#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/DADAO-v5
python3.12 -B /tmp/opencode/INFRA-104t/check_subjects.py \
  --component llvm-project --repo .work/source/llvm-project \
  --series components/llvm-project/patches/series \
  --base 6dfe1677ab8dffbc6ec13d53a1e0215d75147689 --expected-count 8 \
  --git /tmp/opencode/INFRA-104t/git-clean
python3.12 -B /tmp/opencode/INFRA-104t/check_subjects.py \
  --component qemu --repo .work/source/qemu \
  --series components/qemu/patches/series \
  --base c3d48b7d1e89604920e5b81b91140c2ad39a1943 --expected-count 8 \
  --git /tmp/opencode/INFRA-104t/git-clean
SH
bash -o pipefail -c '
  bash /tmp/opencode/INFRA-104t/s3-subjects.sh 2>&1 | tee .work/log/infra/INFRA-104t-subjects.log
  rc=${PIPESTATUS[0]}; printf "subjects_exit=%s\n" "$rc"; exit "$rc"
'
```

## S4 — LLVM/QEMU 产物与 contracts verifier

写入可单独调用的 `/tmp/opencode/INFRA-104t/check_llvm_all_targets.py`：

```python
#!/usr/bin/env python3
import argparse
from pathlib import Path

def skip_bracket(text: str, start: int) -> int | None:
    """Return index after a CMake [=[...]=] argument/comment, or None."""
    if start >= len(text) or text[start] != "[":
        return None
    pos = start + 1
    while pos < len(text) and text[pos] == "=":
        pos += 1
    if pos >= len(text) or text[pos] != "[":
        return None
    equals = text[start + 1:pos]
    close = "]" + equals + "]"
    end = text.find(close, pos + 1)
    if end < 0:
        raise SystemExit("unterminated CMake bracket argument/comment")
    return end + len(close)

def active_tokens(text: str) -> list[tuple[str, str]]:
    """Tokenize active CMake code, excluding comments and string arguments."""
    tokens: list[tuple[str, str]] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch.isspace() or ch == ";":
            i += 1
            continue
        if ch == "#":
            bracket_end = skip_bracket(text, i + 1)
            if bracket_end is not None:          # #[[...]] / #[=[...]=] / any = depth
                i = bracket_end
            else:                                # ordinary #... line comment
                newline = text.find("\n", i + 1)
                i = len(text) if newline < 0 else newline + 1
            continue
        if ch == '"':                            # quoted argument; honor backslash escapes
            i += 1
            while i < len(text):
                if text[i] == "\\":
                    i += 2
                elif i < len(text) and text[i] == '"':
                    i += 1
                    break
                else:
                    i += 1
            else:
                raise SystemExit("unterminated CMake quoted argument")
            continue
        bracket_end = skip_bracket(text, i)
        if bracket_end is not None:               # bracket argument; ignore its contents
            i = bracket_end
            continue
        if ch == "(":
            tokens.append(("LPAREN", ch)); i += 1; continue
        if ch == ")":
            tokens.append(("RPAREN", ch)); i += 1; continue
        start = i
        while i < len(text):
            if text[i].isspace() or text[i] in "();#\"":
                break
            if text[i] == "[" and skip_bracket(text, i) is not None:
                break
            i += 1
        if i == start:
            # A lone '[' that is not a bracket opener is part of a bare token.
            i += 1
            while i < len(text) and not text[i].isspace() and text[i] not in "();#\"":
                i += 1
        tokens.append(("WORD", text[start:i]))
    return tokens

def check(path: Path) -> None:
    tokens = active_tokens(path.read_text(encoding="utf-8"))
    blocks: list[list[str]] = []
    i = 0
    while i < len(tokens):
        # Every top-level WORD '(' starts one complete command. Parse to its
        # matching ')' and always jump past it, so message(set(...)) cannot be
        # reconsidered as a top-level set command.
        if i + 1 < len(tokens) and tokens[i][0] == "WORD" and tokens[i + 1][0] == "LPAREN":
            command = tokens[i][1].lower()
            depth = 1
            body: list[str] = []
            j = i + 2
            while j < len(tokens) and depth:
                kind, value = tokens[j]
                if kind == "LPAREN":
                    depth += 1
                elif kind == "RPAREN":
                    depth -= 1
                elif kind == "WORD" and depth == 1:
                    body.append(value)
                j += 1
            if depth:
                raise SystemExit(f"unterminated active top-level command: {command}")
            if command == "set" and body and body[0] == "LLVM_ALL_TARGETS":
                blocks.append(body[1:])
            i = j
            continue
        if tokens[i][0] in ("LPAREN", "RPAREN"):
            raise SystemExit("unmatched top-level parenthesis")
        i += 1
    if len(blocks) != 1:
        raise SystemExit(f"active set(LLVM_ALL_TARGETS ...) count {len(blocks)} != 1")
    count = blocks[0].count("DADAO")
    if count != 1:
        raise SystemExit(f"bare DADAO token count in active LLVM_ALL_TARGETS is {count} != 1")
    print("LLVM_ALL_TARGETS: PASS active_blocks=1 bare_DADAO=1")

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cmake", required=True)
    ns = ap.parse_args()
    check(Path(ns.cmake))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```

该最小 lexer 忽略普通 `#...` 行注释、任意等号层级 bracket comment、带反斜杠转义的 quoted argument，以及任意等号层级 bracket argument。parser 把每个顶层 `WORD LPAREN ... matching RPAREN` 作为完整 command 并整体跳过，只分析顶层 command 名为 `set` 的 body；未终止 command 和顶层孤立括号 fail-closed。因此 `message(set(...))` 内层 token 不会被二次扫描。只有 active code 中的 bare tokens 可形成 `set(LLVM_ALL_TARGETS ...)` 和 `DADAO`；checker 有独立 CLI，S7 可在不依赖其它 LLVM/QEMU 产物时单独证伪。

完整结构检查器 `/tmp/opencode/INFRA-104t/verify_outputs.py`：

```python
#!/usr/bin/env python3
from pathlib import Path

llvm = Path(".work/source/llvm-project/llvm")
root = llvm / "lib/Target/DADAO"
for name in ("DADAO.td", "DADAOInstrFormats.td", "DADAOInstrInfo.td", "DADAORegisterInfo.td"):
    if not (root / name).is_file():
        raise SystemExit(f"missing file: {root / name}")
for name in ("AsmParser", "Disassembler", "MCTargetDesc", "TargetInfo"):
    if not (root / name).is_dir():
        raise SystemExit(f"missing directory: {root / name}")

decode = Path(".work/source/qemu/target/dadao/insn.decode")
machine = Path(".work/source/qemu/hw/dadao/dadao-machine.c")
if not decode.is_file() or not machine.is_file():
    raise SystemExit("missing QEMU decode or machine source")
with decode.open("rb") as stream:
    lines = sum(1 for _ in stream)
if lines != 274:
    raise SystemExit(f"insn.decode line count {lines} != 274")
print("outputs: PASS; LLVM files/dirs; QEMU lines=274")
```

完整 Bash verifier：

```bash
cat > /tmp/opencode/INFRA-104t/s4-outputs.sh <<'SH'
#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/DADAO-v5
python3.12 -B /tmp/opencode/INFRA-104t/check_llvm_all_targets.py \
  --cmake .work/source/llvm-project/llvm/CMakeLists.txt
python3.12 -B /tmp/opencode/INFRA-104t/verify_outputs.py
validator_log=.work/log/infra/INFRA-104t-decodetree.log
set +e
python3.12 -B tools/qemu/validate_decodetree.py \
  .work/source/qemu/target/dadao/insn.decode contracts/opcodes.yaml 2>&1 | tee "$validator_log"
rc=${PIPESTATUS[0]}
set -e
test "$rc" -eq 0
test "$(grep -Fxc '  YAML 记录数: 256' "$validator_log")" -eq 1
test "$(grep -Fxc '  decode pattern 数: 256' "$validator_log")" -eq 1
test "$(grep -Fxc '  错误数: 0' "$validator_log")" -eq 1
test "$(grep -Fxc 'validate_decodetree: PASS' "$validator_log")" -eq 1
SH
bash -o pipefail -c '
  bash /tmp/opencode/INFRA-104t/s4-outputs.sh 2>&1 | tee .work/log/infra/INFRA-104t-outputs.log
  rc=${PIPESTATUS[0]}; printf "outputs_exit=%s\n" "$rc"; exit "$rc"
'
```

不存在 `MCTableGen/` 预期，第四个目录是 `TargetInfo/`。LLVM 注册门禁由独立 lexer checker 解析 active code 中唯一 `set(LLVM_ALL_TARGETS ...)` 块并要求 bare token `DADAO` 精确一次，禁止任意文本 grep。`274` 是文件行数，`256` 是 validator pattern 数；`wc` 不能代替 contracts 检查。

## S5 — base-to-HEAD 差异 verifier

```bash
cat > /tmp/opencode/INFRA-104t/s5-diff.sh <<'SH'
#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/DADAO-v5
gitc=/tmp/opencode/INFRA-104t/git-clean
check() {
  local name=$1 base=$2 out=/tmp/opencode/INFRA-104t/$1.diff-names
  "$gitc" -C ".work/source/$name" diff --stat "$base" HEAD
  "$gitc" -C ".work/source/$name" diff --name-only "$base" HEAD > "$out"
  test -s "$out"
  printf '%s changed_files=%s\n' "$name" "$(wc -l < "$out")"
  cat "$out"
}
check llvm-project 6dfe1677ab8dffbc6ec13d53a1e0215d75147689
check qemu c3d48b7d1e89604920e5b81b91140c2ad39a1943
SH
bash -o pipefail -c '
  bash /tmp/opencode/INFRA-104t/s5-diff.sh 2>&1 | tee .work/log/infra/INFRA-104t-diff.log
  rc=${PIPESTATUS[0]}; printf "diff_exit=%s\n" "$rc"; exit "$rc"
'
```

## S6 — cache after 与仓库 baseline verifier

先执行完整 cache after 门禁：

```bash
cat > /tmp/opencode/INFRA-104t/s6-cache.sh <<'SH'
#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/DADAO-v5
tmp=/tmp/opencode/INFRA-104t
LC_ALL=C python3.12 -B "$tmp/snapshot_cache.py" \
  --cache .cache --snapshot "$tmp/cache.after" --summary "$tmp/cache-summary.after" \
  --git "$tmp/git-clean"
cmp -- "$tmp/cache.before" "$tmp/cache.after"
cmp -- "$tmp/cache-summary.before" "$tmp/cache-summary.after"
cat "$tmp/cache-summary.after"
echo 'cache full-tree snapshot: IDENTICAL'
SH
bash -o pipefail -c '
  bash /tmp/opencode/INFRA-104t/s6-cache.sh 2>&1 | tee .work/log/infra/INFRA-104t-cache-after.log
  rc=${PIPESTATUS[0]}; printf "cache_after_exit=%s\n" "$rc"; exit "$rc"
'
```

写入 `/tmp/opencode/INFRA-104t/verify_repo_baseline.py`：

```python
#!/usr/bin/env python3
import argparse
import hashlib
import subprocess
from pathlib import Path

TASK = Path(".xkw/tasks/infra/INFRA-104t-源码拉取与补丁系列应用.md")
MARK = b"## \xe5\xae\x8c\xe6\x88\x90\xe5\x8c\xba\n"

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def load_hashes(path: Path):
    for raw in path.read_text(encoding="utf-8").splitlines():
        digest, name = raw.split(maxsplit=1)
        yield digest, Path(name.lstrip(" *"))

def status(git_cmd: str) -> bytes:
    return subprocess.run(
        [git_cmd, "status", "--porcelain=v1", "--untracked-files=all"],
        check=True, stdout=subprocess.PIPE,
    ).stdout

def prefix(data: bytes) -> bytes:
    if data.count(MARK) != 1:
        raise SystemExit("completion marker count != 1")
    return data.split(MARK, 1)[0] + MARK

ap = argparse.ArgumentParser()
ap.add_argument("--mode", choices=("pre", "post"), required=True)
ap.add_argument("--baseline-status", required=True)
ap.add_argument("--baseline-hashes", required=True)
ap.add_argument("--task-before", required=True)
ap.add_argument("--git", required=True)
ns = ap.parse_args()
baseline = Path(ns.baseline_status).read_bytes()
current = status(ns.git)
before = Path(ns.task_before).read_bytes()

if ns.mode == "pre":
    if current != baseline:
        raise SystemExit("repository status differs before completion edit")
    for want, path in load_hashes(Path(ns.baseline_hashes)):
        if sha(path) != want:
            raise SystemExit(f"baseline dirty hash changed: {path}")
    if TASK.read_bytes() != before:
        raise SystemExit("task changed before completion edit")
else:
    if prefix(TASK.read_bytes()) != prefix(before):
        raise SystemExit("task changed outside completion section")
    for want, path in load_hashes(Path(ns.baseline_hashes)):
        if path != TASK and sha(path) != want:
            raise SystemExit(f"baseline dirty hash changed: {path}")
    task_status = subprocess.run(
        [ns.git, "status", "--porcelain=v1", "--untracked-files=all", "--", str(TASK)],
        check=True, stdout=subprocess.PIPE,
    ).stdout
    if current != baseline:
        if not task_status or current.count(task_status) != 1:
            raise SystemExit("cannot isolate task status line")
        if current.replace(task_status, b"", 1) != baseline:
            raise SystemExit("status changed outside task completion edit")
print(f"repo-baseline-{ns.mode}: PASS")
```

仓库 pre/post 是整个任务的最终门禁：须先完成 S7，再回来运行以下 pre、填写完成区并运行 post。填写完成区前运行 pre verifier并留日志：

```bash
cat > /tmp/opencode/INFRA-104t/s6-repo-pre.sh <<'SH'
#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/DADAO-v5
: "${BASELINE_STATUS:?}" "${BASELINE_HASHES:?}" "${TASK_BEFORE:?}"
python3.12 -B /tmp/opencode/INFRA-104t/verify_repo_baseline.py --mode pre \
  --baseline-status "$BASELINE_STATUS" --baseline-hashes "$BASELINE_HASHES" \
  --task-before "$TASK_BEFORE" --git /tmp/opencode/INFRA-104t/git-clean
SH
bash -o pipefail -c '
  bash /tmp/opencode/INFRA-104t/s6-repo-pre.sh 2>&1 | tee .work/log/infra/INFRA-104t-repo-pre.log
  rc=${PIPESTATUS[0]}; printf "repo_pre_exit=%s\n" "$rc"; exit "$rc"
'
```

仅在 pre PASS 后填写完成区；不得改状态。随后执行明确的 post verifier：

```bash
cat > /tmp/opencode/INFRA-104t/s6-repo-post.sh <<'SH'
#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/DADAO-v5
: "${BASELINE_STATUS:?}" "${BASELINE_HASHES:?}" "${TASK_BEFORE:?}"
python3.12 -B /tmp/opencode/INFRA-104t/verify_repo_baseline.py --mode post \
  --baseline-status "$BASELINE_STATUS" --baseline-hashes "$BASELINE_HASHES" \
  --task-before "$TASK_BEFORE" --git /tmp/opencode/INFRA-104t/git-clean
SH
bash -o pipefail -c '
  bash /tmp/opencode/INFRA-104t/s6-repo-post.sh 2>&1 | tee .work/log/infra/INFRA-104t-repo-post.log
  rc=${PIPESTATUS[0]}; printf "repo_post_exit=%s\n" "$rc"; exit "$rc"
'
```

post 允许的唯一变化是本任务书完成区：若任务书在 baseline 已 dirty，完整 status 仍须逐字节相同；若当时 clean，则机械删除唯一 task status 行后必须与 baseline 逐字节相同。其它 baseline dirty 文件逐项内容哈希不变，任务书完成区之前逐字节不变。

## S7 — 同一 checker 的合成树反例与复绿

完整 verifier `/tmp/opencode/INFRA-104t/s7-negative.sh`：

```bash
#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/DADAO-v5
tmp=/tmp/opencode/INFRA-104t/engineer
gitc=/tmp/opencode/INFRA-104t/git-clean
rm -rf -- "$tmp"
mkdir -p "$tmp/subjects/patches" "$tmp/decode" "$tmp/cmake" \
  "$tmp/isolation-expected" "$tmp/isolation-wrong"

# Subject fixture: patch 邮件属于 base，随后正好 8 个被比较 commits。
"$gitc" -C "$tmp/subjects" init -q
"$gitc" -C "$tmp/subjects" config user.name Fixture
"$gitc" -C "$tmp/subjects" config user.email fixture@example.invalid
"$gitc" -C "$tmp/subjects" config commit.gpgSign false
"$gitc" -C "$tmp/subjects" config core.hooksPath /tmp/opencode/INFRA-104t/hooks
: > "$tmp/subjects/patches/series"
for ((i=1; i<=8; i++)); do
  name=$(printf '%04d-fixture.patch' "$i")
  printf '%s\n' "$name" >> "$tmp/subjects/patches/series"
  cat > "$tmp/subjects/patches/$name" <<EOF
From 0000000000000000000000000000000000000000 Mon Sep 17 00:00:00 2001
From: Fixture <fixture@example.invalid>
Subject: [PATCH $i/8] synthetic $i

fixture
EOF
done
"$gitc" -C "$tmp/subjects" add patches
"$gitc" -C "$tmp/subjects" commit -q -m fixture-base
base=$("$gitc" -C "$tmp/subjects" rev-parse HEAD)
for ((i=1; i<=8; i++)); do
  printf '%s\n' "$i" >> "$tmp/subjects/data"
  "$gitc" -C "$tmp/subjects" add data
  "$gitc" -C "$tmp/subjects" commit -q -m "synthetic $i"
done
test -z "$("$gitc" -C "$tmp/subjects" status --porcelain=v1 --untracked-files=all)"
python3.12 -B /tmp/opencode/INFRA-104t/check_subjects.py \
  --component synthetic --repo "$tmp/subjects" --series "$tmp/subjects/patches/series" \
  --base "$base" --expected-count 8 --git "$gitc"
sed -i 's/Subject: \[PATCH 1\/8\] synthetic 1/Subject: [PATCH 1\/8] WRONG/' \
  "$tmp/subjects/patches/0001-fixture.patch"
"$gitc" -C "$tmp/subjects" diff --name-only > "$tmp/subject-injection.diff-names"
test -s "$tmp/subject-injection.diff-names"
cat "$tmp/subject-injection.diff-names"
set +e
python3.12 -B /tmp/opencode/INFRA-104t/check_subjects.py \
  --component synthetic --repo "$tmp/subjects" --series "$tmp/subjects/patches/series" \
  --base "$base" --expected-count 8 --git "$gitc" > "$tmp/subject-negative.out" 2>&1
subject_rc=$?
set -e
cat "$tmp/subject-negative.out"
test "$subject_rc" -ne 0
"$gitc" -C "$tmp/subjects" restore patches/0001-fixture.patch
test -z "$("$gitc" -C "$tmp/subjects" status --porcelain=v1 --untracked-files=all)"
python3.12 -B /tmp/opencode/INFRA-104t/check_subjects.py \
  --component synthetic --repo "$tmp/subjects" --series "$tmp/subjects/patches/series" \
  --base "$base" --expected-count 8 --git "$gitc"

# Validator fixture：真实输入副本进入独立 clean git tree，注入只改副本。
"$gitc" -C "$tmp/decode" init -q
"$gitc" -C "$tmp/decode" config user.name Fixture
"$gitc" -C "$tmp/decode" config user.email fixture@example.invalid
"$gitc" -C "$tmp/decode" config commit.gpgSign false
"$gitc" -C "$tmp/decode" config core.hooksPath /tmp/opencode/INFRA-104t/hooks
cp .work/source/qemu/target/dadao/insn.decode "$tmp/decode/insn.decode"
cp contracts/opcodes.yaml "$tmp/decode/opcodes.yaml"
"$gitc" -C "$tmp/decode" add insn.decode opcodes.yaml
"$gitc" -C "$tmp/decode" commit -q -m fixture-base
test -z "$("$gitc" -C "$tmp/decode" status --porcelain=v1 --untracked-files=all)"
python3.12 -B tools/qemu/validate_decodetree.py "$tmp/decode/insn.decode" "$tmp/decode/opcodes.yaml"
python3.12 -B - "$tmp/decode/insn.decode" <<'PY'
import sys
from pathlib import Path
p = Path(sys.argv[1])
lines = p.read_text().splitlines()
for i, line in enumerate(lines):
    fields = line.split()
    if len(fields) >= 3 and set(fields[1]) <= set("01.") and "0" in fields[1]:
        fields[1] = fields[1].replace("0", "1", 1)
        lines[i] = "  ".join(fields)
        break
else:
    raise SystemExit("no injectable pattern")
p.write_text("\n".join(lines) + "\n")
PY
"$gitc" -C "$tmp/decode" diff --name-only > "$tmp/decode-injection.diff-names"
test -s "$tmp/decode-injection.diff-names"
cat "$tmp/decode-injection.diff-names"
set +e
python3.12 -B tools/qemu/validate_decodetree.py "$tmp/decode/insn.decode" "$tmp/decode/opcodes.yaml" \
  > "$tmp/decode-negative.out" 2>&1
decode_rc=$?
set -e
cat "$tmp/decode-negative.out"
test "$decode_rc" -ne 0
"$gitc" -C "$tmp/decode" restore insn.decode
test -z "$("$gitc" -C "$tmp/decode" status --porcelain=v1 --untracked-files=all)"
python3.12 -B tools/qemu/validate_decodetree.py "$tmp/decode/insn.decode" "$tmp/decode/opcodes.yaml"

# CMake fixture：checker 独立运行，不让其它产物缺失掩盖其结论。
"$gitc" -C "$tmp/cmake" init -q
"$gitc" -C "$tmp/cmake" config user.name Fixture
"$gitc" -C "$tmp/cmake" config user.email fixture@example.invalid
"$gitc" -C "$tmp/cmake" config commit.gpgSign false
"$gitc" -C "$tmp/cmake" config core.hooksPath /tmp/opencode/INFRA-104t/hooks
cat > "$tmp/cmake/CMakeLists.txt" <<'EOF'
set(LLVM_ALL_TARGETS
  X86
  DADAO
)
EOF
"$gitc" -C "$tmp/cmake" add CMakeLists.txt
"$gitc" -C "$tmp/cmake" commit -q -m fixture-base
test -z "$("$gitc" -C "$tmp/cmake" status --porcelain=v1 --untracked-files=all)"
python3.12 -B /tmp/opencode/INFRA-104t/check_llvm_all_targets.py \
  --cmake "$tmp/cmake/CMakeLists.txt"
cmake_negative() {
  local label=$1 rc
  cat > "$tmp/cmake/CMakeLists.txt"
  "$gitc" -C "$tmp/cmake" diff --name-only > "$tmp/cmake-$label.diff-names"
  test -s "$tmp/cmake-$label.diff-names"
  cat "$tmp/cmake-$label.diff-names"
  set +e
  python3.12 -B /tmp/opencode/INFRA-104t/check_llvm_all_targets.py \
    --cmake "$tmp/cmake/CMakeLists.txt" > "$tmp/cmake-$label.out" 2>&1
  rc=$?
  set -e
  cat "$tmp/cmake-$label.out"
  test "$rc" -ne 0
  "$gitc" -C "$tmp/cmake" restore CMakeLists.txt
  test -z "$("$gitc" -C "$tmp/cmake" status --porcelain=v1 --untracked-files=all)"
  python3.12 -B /tmp/opencode/INFRA-104t/check_llvm_all_targets.py \
    --cmake "$tmp/cmake/CMakeLists.txt"
  printf 'cmake_negative[%s]=%s; restored clean and green\n' "$label" "$rc"
}
cmake_negative line-comment <<'EOF'
# set(LLVM_ALL_TARGETS DADAO)
EOF
cmake_negative bracket-comment-0 <<'EOF'
#[[
set(LLVM_ALL_TARGETS DADAO)
]]
EOF
cmake_negative bracket-comment-2 <<'EOF'
#[==[
set(LLVM_ALL_TARGETS DADAO)
]==]
EOF
cmake_negative quoted-argument <<'EOF'
set(OTHER "escaped quote: \" set(LLVM_ALL_TARGETS DADAO)")
EOF
cmake_negative bracket-argument <<'EOF'
set(OTHER [=[set(LLVM_ALL_TARGETS DADAO)]=])
EOF
cmake_negative nested-command-text <<'EOF'
message(set(LLVM_ALL_TARGETS DADAO))
EOF

# Ambient Git pollution resilience：这是隔离韧性 PASS，不是“checker 应非零”。
for repo in isolation-expected isolation-wrong; do
  "$gitc" -C "$tmp/$repo" init -q
  "$gitc" -C "$tmp/$repo" config user.name Fixture
  "$gitc" -C "$tmp/$repo" config user.email fixture@example.invalid
  "$gitc" -C "$tmp/$repo" config commit.gpgSign false
done
printf 'EXPECTED\n' > "$tmp/isolation-expected/value"
printf 'baseline\n' > "$tmp/isolation-expected/scenario.env"
"$gitc" -C "$tmp/isolation-expected" add value scenario.env
"$gitc" -C "$tmp/isolation-expected" commit -q -m expected
printf 'WRONG\n' > "$tmp/isolation-wrong/value"
"$gitc" -C "$tmp/isolation-wrong" add value
"$gitc" -C "$tmp/isolation-wrong" commit -q -m wrong
cat > "$tmp/isolation-expected/scenario.env" <<EOF
GIT_DIR=$tmp/isolation-wrong/.git
GIT_CONFIG_COUNT=1
GIT_CONFIG_KEY_0=test.ambient
GIT_CONFIG_VALUE_0=WRONG
EOF
"$gitc" -C "$tmp/isolation-expected" diff --name-only > "$tmp/isolation-injection.diff-names"
test -s "$tmp/isolation-injection.diff-names"
cat "$tmp/isolation-injection.diff-names"
test "$(GIT_DIR="$tmp/isolation-wrong/.git" GIT_CONFIG_COUNT=1 \
  GIT_CONFIG_KEY_0=test.ambient GIT_CONFIG_VALUE_0=WRONG \
  "$gitc" -C "$tmp/isolation-expected" show HEAD:value)" = EXPECTED
set +e
GIT_DIR="$tmp/isolation-wrong/.git" GIT_CONFIG_COUNT=1 \
  GIT_CONFIG_KEY_0=test.ambient GIT_CONFIG_VALUE_0=WRONG \
  "$gitc" -C "$tmp/isolation-expected" config --get test.ambient \
  > "$tmp/isolation-config.out" 2>&1
isolation_config_rc=$?
set -e
test "$isolation_config_rc" -ne 0
test ! -s "$tmp/isolation-config.out"
"$gitc" -C "$tmp/isolation-expected" restore scenario.env
test -z "$("$gitc" -C "$tmp/isolation-expected" status --porcelain=v1 --untracked-files=all)"
test -z "$("$gitc" -C "$tmp/isolation-wrong" status --porcelain=v1 --untracked-files=all)"
echo 'git-clean ambient pollution resilience: PASS'

printf 'negative gates: subject_rc=%s decode_rc=%s; six CMake classes failed independently and restored\n' \
  "$subject_rc" "$decode_rc"
```

执行并保存聚合退出码：

```bash
bash -o pipefail -c '
  bash /tmp/opencode/INFRA-104t/s7-negative.sh 2>&1 | tee .work/log/infra/INFRA-104t-negative.log
  rc=${PIPESTATUS[0]}; printf "negative_exit=%s\n" "$rc"; exit "$rc"
'
```

Subject、decode、CMake 三类 checker 均由对应 clean Git fixture 直接证伪；每类注入后的 `diff --name-only` 文件必须非空、checker 必须真实非零、restore 后 status 必须 clean 且同一 checker 复绿。CMake 的 6 类反例必须逐类独立运行，禁止合并后让多个泄漏互相掩盖：普通行注释、`#[[...]]`、多等号 bracket comment、带转义 quoted argument、bracket argument、`message(set(...))` 嵌套无关文本。ambient 污染场景是 wrapper 隔离韧性 PASS，不得误写成 checker 应非零。真实反例由 `/complete` reviewer 在自己的 `/tmp/opencode/INFRA-104t/reviewer/` 独立重做；cache 根链接替换反例主要由 reviewer 执行，engineer 至少必须完成真实 cache before/after 全树比较。不得污染真实 `.work/source`、contracts 或 patch 树。

## 验收

| # | 项 | 直接机械门禁 | 可执行性 |
| --- | --- | --- | --- |
| 1 | prepare | S1 聚合 exit 0；`env -i` allowlist 中 `make -j1` 成功，无拒绝/冲突 | 现在可跑 |
| 2 | 本地 fetch/cache | 两条精确 skip 各 1；否定 cloned/updated；origin 绝对本地路径；完整 cache snapshot+summary `cmp` | 现在可跑 |
| 3 | 锁定基线 | S2 两个 `merge-base --is-ancestor`、`base..HEAD=8` | 现在可跑 |
| 4 | 浅历史数 | S2 两树 shallow=true 且 `rev-list --count HEAD=9` | 现在可跑 |
| 5 | series 忠实性 | S3 同一 checker：两组件 series=8、log=8、逐索引 Subject 精确一致 | 现在可跑 |
| 6 | LLVM 产物 | S4 四文件、四目录；唯一 `LLVM_ALL_TARGETS` 块中 DADAO token 精确一次 | 现在可跑 |
| 7 | QEMU/contracts | S4 两文件、274 行；validator exit 0 且机械匹配 256/256/0/PASS | 现在可跑 |
| 8 | 差异非空 | S5 两个 name-only 文件均 `test -s` | 现在可跑 |
| 9 | 保护边界 | S6 cache 完整树一致；repo pre/post verifier 限定仅完成区变化，其他 dirty 哈希不变 | 现在可跑 |
| 10 | 源码可编译 | 本任务不构建；结构/重放证据不等于可编译性 | **BLOCKED**（LLVM 由 `INFRA-105t`、QEMU 由 `INFRA-106t`；验收 3–8 仅作替代证据，不得报 PASS） |
| 11 | checker FAIL 路径 | S7 Subject/decode 及 CMake 六类逐项非空注入、真实非零、restore clean、同 checker 复绿；另有 ambient Git 污染隔离 PASS；聚合 exit 0 | 现在可跑 |

## 四项预检与 ADR

1. **内部一致性**：任何 source 创建/prepare 前双重排除现存路径与悬空链接；单次串行 prepare、失败即停、禁止 clean/retry/绕过；所有多判据块均为 `set -euo pipefail` verifier。
2. **依赖实际可用性**：S0 实查宿主命令、Python 模块、identity、空间和镜像 bare/shallow/HEAD/advertised HEAD/object。
3. **验收可执行性**：#1–#9/#11 各有直接脚本与日志；#10 明确 BLOCKED。
4. **spec/vectors 一致性**：不新增或判断 ISA 语义，vectors、size/sign 全量重算和 ISA 探针 N/A；仅 decodetree 结构由独立 validator 对齐 contracts 的 mask/value/name/format。

不新增或修改 ADR。`adr-1001` D3 已 Accepted；本修订只收紧确定环境、本地短路、cache 完整性和失败边界。未来若改 source、允许联网回退或改变恢复策略，必须另行 `/plan` 并重新判断 ADR。

## 完成区

（engineer 于 2026-09-26 执行完毕；**状态字段未改动**。以下全部数字均取自本节所列日志的真实输出。）

### 1. dispatch baseline 与清洁 Git 环境

| 项 | 值 |
| --- | --- |
| baseline 状态快照 `dispatch/git-status.before` | 19 条路径，SHA256 `4c4530525e91bab55bcabda9bf06150644b22906b5668d61e149c38073322081` |
| dirty 内容哈希 `dispatch/dirty-content-sha256.before` | 19 条（含本任务书自身） |
| 任务书 dispatch 副本 `dispatch/task.before` | 与执行前一致 |
| 隔离身份 | `xkw <xkwlyxp@stu.pku.edu.cn>`，`commit.gpgSign=false`，`core.hooksPath` → 空目录 |
| 宿主 | git 2.34.1、Python 3.12.14、PyYAML 6.0.3、GNU Make 4.3 |

所有 Git 判定一律经 `…/git-clean`（`env -i` allowlist：固定 PATH、`LC_ALL=C`、隔离 `HOME`/`XDG_CONFIG_HOME`、`GIT_CONFIG_NOSYSTEM=1`、空 `GIT_TEMPLATE_DIR`）。ambient `GIT_ASKPASS` 存在但被 `env -i` 剥离。**未使用任何明文 `git`**（唯一例外是 §6.2 描述的反例组 J 故意使用的对照）。

### 2. S0–S7 聚合 exit 与日志

| 步骤 | 日志 | 聚合 exit | 关键输出 |
| --- | --- | --- | --- |
| S0 | `INFRA-104t-s0.log` | 0 | 19/19 baseline 哈希 `OK`；`mnt_available_kib=194469672`；两镜像 `bare=true`/`shallow=true`/HEAD 与 advertised HEAD 均等于锁定 base |
| S1 | `INFRA-104t-s1.log` = `INFRA-104t-prepare.log` | 0 | 两条精确 skip 各 ×1；`cloned` ×0；`updated (incremental)` ×0；`Applying:` ×16；`apply-series: llvm-project applied 8 patches` / `qemu applied 8 patches` |
| S2 | `INFRA-104t-history.log` | 0 | `base_to_head=8 total=9 shallow=true`（两组件）；origin 均为 `/home/ubuntu/DADAO-v5/.cache/<name>.git` |
| S3 | `INFRA-104t-subjects.log` | 0 | 两组件各 `PASS series=8 log=8`，逐索引 16/16 Subject 精确一致 |
| S4 | `INFRA-104t-outputs.log` + `INFRA-104t-decodetree.log` | 0 | `LLVM_ALL_TARGETS: PASS active_blocks=1 bare_DADAO=1`；`outputs: PASS; LLVM files/dirs; QEMU lines=274`；validator `YAML 记录数: 256` / `decode pattern 数: 256` / `错误数: 0` / `validate_decodetree: PASS`（各恰好一次） |
| S5 | `INFRA-104t-diff.log` | 0 | `llvm-project changed_files=36`、`qemu changed_files=31`，两个 name-only 文件均 `test -s` |
| S6 cache | `INFRA-104t-cache-after.log` | 0 | `cache full-tree snapshot: IDENTICAL` |
| S6 repo-pre | `INFRA-104t-repo-pre.log` | 0 | `repo-baseline-pre: PASS` |
| S7 | `INFRA-104t-negative.log` | 0 | `subject_rc=1 decode_rc=1`；六类 CMake 逐项 `=1; restored clean and green`；`git-clean ambient pollution resilience: PASS` |
| S6 repo-post | `INFRA-104t-repo-post.log` | 0 | `repo-baseline-post: PASS`（在本节写入之后执行） |

**`make prepare` 只运行过一次**（S1，`make -j1 PYTHON=python3.12 prepare`）；`.work/source` 由该次运行创建，S0 的 `test ! -e / ! -L` 双门禁因此**不可重跑**，S1 本身亦不可重跑。

为使 exit 码有盘上证据，新增 `INFRA-104t-aggregate-rc.log`：把**可安全重跑**的 verifier 各重跑一次并记录真实 `$?`（S2/S3/S4/S5/S6-cache/S6-repo-pre/S7 全部 `rc=0`），并把 S0、S1 的**每一条内容判据**做只读复核（S0.1–S0.10、S1.1–S1.7、S6.1–S6.2 全部 `rc=0`，含两镜像 bare/shallow/HEAD/advertised HEAD/object、两条 skip 恰好一次、`cloned` 与 `updated (incremental)` 计数为 0、16 条 `Applying:`、apply-series 8+8）。该复核的 0 失败写在日志末行 `aggregate re-verification failures: 0`。

### 3. `.cache` before/after

- `cache.before`：126 行，SHA256 `c0601aef1b5ac84c84dce07840fd3ff0099ca3377a5541b21a20d49bdc59732a`；首行 `CACHE_ROOT	.	L	/mnt/dadao-v5/.cache`（`.cache` 是指向 `/mnt/dadao-v5/.cache` 的符号链接）。
- S6：`cmp cache.before cache.after` 与 summary `cmp` 均通过，after 同为 126 行、同一 SHA256，日志末行 `cache full-tree snapshot: IDENTICAL`。
- `.cache` 全程只读：无 `unshallow`、无 `gc`、无 config 改写（§5.1 的 SHA256/条目/链接/根链接四类反例证明快照器对其敏感）。

### 4. 两组件结果数字

| 项 | llvm-project | qemu |
| --- | --- | --- |
| 锁定 base | `6dfe1677ab8dffbc6ec13d53a1e0215d75147689` | `c3d48b7d1e89604920e5b81b91140c2ad39a1943` |
| 补丁后 HEAD | `a5c3a44403fd8efd5ea4e0b0f9fc2961ed9ca784` | `5c3535f66892868a5829a1b0a242866da6d98e08` |
| `base..HEAD` / `rev-list --count HEAD` | 8 / 9，shallow=true | 8 / 9，shallow=true |
| Subject oracle | series=8 log=8，8/8 逐索引一致 | series=8 log=8，8/8 逐索引一致 |
| 产物 | 4 个 `.td` + 4 个目录；`LLVM_ALL_TARGETS` 唯一活动块内裸 `DADAO` 恰好 1 次 | `insn.decode` 274 行 + `hw/dadao/dadao-machine.c`；validator 256/256/0 |
| base..HEAD 改动文件 | 36 | 31 |
| 工作树 | clean | clean |

两仓库 `status --porcelain=v1 --untracked-files=all` 均为空；`origin` 为本地绝对路径（未联网）。

### 5. 反例注入：真实非零 + 还原 + 同 checker 复绿

S7 日志给出三类反例的真实退出码；每个注入都留下**非空** `diff --name-only` 证据（`…/engineer/*.diff-names`）：

- **Subject**：注入 `WRONG` 后 `subject_rc=1`，`subject-injection.diff-names` = `patches/0001-fixture.patch`（非空）。
- **decode**：注入后 `decode_rc=1`，`decode-injection.diff-names` = `insn.decode`（非空）。
- **CMake 六类**：`line-comment`、`bracket-comment-0`、`bracket-comment-2`、`quoted-argument`、`bracket-argument`、`nested-command-text`，逐项 `=1` 且 `restored clean and green`，六个 `*.diff-names` 各 1 行 `CMakeLists.txt`。
- **ambient 污染**：`isolation-injection.diff-names` = `scenario.env`（非空）；同一被污染环境下 `git-clean` 仍读到 `EXPECTED`，普通 `git` 读到 `WRONG`（见 §6.2）。

### 6. 自审：每个 checker 都有可达 FAIL 路径

自审 harness 全部只放 `/tmp/opencode/INFRA-104t/selfaudit/`，只读真实 `.work/source`、`components/*/patches` 与 `contracts/`，从不写入真实仓库或 `.cache`。六份日志（`INFRA-104t-selfaudit-{s0,s1s2,s1neg,checkers,baseline,transcription}.log`）末行分别为 `failures: 0`，全文 `SELF-AUDIT FAIL` 计数为 0。

| 组 | 覆盖对象 | 结论 |
| --- | --- | --- |
| A | S0 全部判据（工具门禁、`.work/source` 双门禁、baseline 摘要、dirty 哈希、cmp、空间数值边界、镜像五判据、快照器四类敏感度、根符号链接改指、summary cmp） | 0 失败；根链接改指被精确定位为**仅 1 行**变化（`CACHE_ROOT`），两侧各 76 行；FIFO fail-closed；同名同尺寸改内容被 SHA256 抓到 |
| B/C | S1 日志判据与 S2 历史判据（逐条 + 按真实顶层 `check()` 顺序） | 0 失败；并证明多 `test` 函数体在首个失败处即中止，而非「最后一条命令说了算」 |
| D | `check_subjects.py` 每个分支（series 条数、缺 Subject、log 条数、Subject 不一致） | 0 失败；注入 `diff --name-only` = `patches/0004-p.patch`（非空），`git restore` 后同一 checker 复绿 |
| D2 | `[PATCH …]` 前缀处理的真实 `git am` 行为 | 见 §6.1 |
| E | `check_llvm_all_targets.py` 每个分支（双裸 DADAO、无 DADAO、两个活动块、未闭合命令、未配对括号、未闭合 bracket、未闭合 引号） | 0 失败；真实 `llvm/CMakeLists.txt` 亦通过 |
| F | `verify_outputs.py` 每个分支（4 个 `.td`、4 个目录、`dadao-machine.c`、`insn.decode`、274/275/273 行） | 0 失败；真实已打补丁树亦通过 |
| G | validator 四条计数判据（256/256/0/PASS，含重复行 → 计数 2） | 0 失败 |
| H | S5 `test -s` 非空判据 | 0 失败；并记录其**已知边界**：非空但错误的文件仍会通过，语义由 §4 的具体数字承担 |
| I | `verify_repo_baseline.py` 全部 8 个分支（pre：状态漂移 / dirty 哈希 / 任务自身哈希 / 任务字节；post：完成区外改动 / marker 计数≠1 / 他文件哈希 / 新增未跟踪路径 / 任务行不可隔离） | 0 失败；全部在 `/tmp` 合成仓库上跑，真实仓库只作为对照只读 |
| J | ambient 污染判据的非空性 | 见 §6.2 |
| K | 「所发脚本与任务书代码块逐字节一致」检查器自身的 FAIL 路径 | 0 失败；追加 1 行、删除 1 行、改动任务书块，三种注入均被检出并用同一检查器复绿 |

**15/15 逐字节一致（执行当时）**：S0–S7 的全部所发脚本（`s0.sh`、`snapshot_cache.py`、`s1-prepare.sh`、`s2-history.sh`、`check_subjects.py`、`s3-subjects.sh`、`check_llvm_all_targets.py`、`verify_outputs.py`、`s4-outputs.sh`、`s5-diff.sh`、`s6-cache.sh`、`verify_repo_baseline.py`、`s6-repo-pre.sh`、`s6-repo-post.sh`、`s7-negative.sh`）与任务书对应围栏代码块**逐字节相同**（`s0.sh` = block05 + block07，中间一个空行）。检查器 `…/verify_transcription.py`，当时结论 `verbatim check: 15/15 byte-identical, 0 differing`。

> **已更新（主会话代行验收，2026-09-26）**：§6.5 把 block09 的三行改为 `|| exit 1` 之后，本项**现状为 14/15**：唯一不一致是 `s1-prepare.sh`，差异恰为那三行（任务书侧有 `|| exit 1`，engineer 执行时落盘的 `/tmp/opencode/INFRA-104t/s1-prepare.sh` 无）。这是**已声明**的差异，不是新缺陷；除该三行外 14 个脚本仍逐字节一致。复现命令与逐行 diff 见 §9.3。

#### 6.1 上报发现 1：`check_subjects.py` 的前缀语义与 `git am` 不完全一致（不影响本任务数据）

实测 git 2.34.1 的 `git am` 对 Subject 前缀是**连续剥离**：`[PATCH 1/1] X` → `X`；`[PATCH] [PATCH 1/1] X` → `X`（两个都吃掉）；`[RFC] [PATCH 1/1] X` → `X`（`[RFC]` 也吃）；无前缀则原样保留。任务书 `check_subjects.py` 用 `PREFIX.sub(..., count=1)`（只剥一次），因此在**双前缀**或**前导 `[RFC]`** 输入上会与 `git am` 不一致 —— 已在合成 fixture 上端到端复现该 checker 报 FAIL。

对本任务**不可达**：`components/{llvm-project,qemu}/patches` 的 **16/16** 个 Subject 都恰好含**一个** `[PATCH …]` 前缀（`VERDICT OK 16/16`）。且 16 条真实期望值比对的是 `git am` 自己产出的 commit subject（S2/S3 从真实仓库读出），不依赖该正则。**engineer 未擅自改动任务书**，仅上报，是否把 `count=1` 改为与 git 一致的语义请主会话决定。

#### 6.2 上报发现 2：S1 末尾三条 `! grep -Fq` 门禁可假通过

任务书 S1 脚本最后三行为裸 `! grep -Fq '…' "$log"`。bash 在 `set -e` 下对「状态被 `!` 取反」的命令**抑制 errexit**，故这三行检出违禁字符串时返回 1 却**不中止**；又因其为最后三行，脚本退出码等于第三行结果 —— 只要 `'updated (incremental)'` 不在日志中，即便检出 `cloned` 也**退出 0**。最小复现实测：原形对含 `llvm cloned` / `qemu cloned` 的日志均 `rc=0`（假通过），仅对 `updated (incremental)` `rc=1`；加 `|| exit 1` 后三种注入均 `rc=1`，对真实日志仍 `rc=0`。见 `INFRA-104t-selfaudit-s1neg.log`。

**本次未受该缺陷影响**：S1 的实质结论由两条 `grep -Fxc … -eq 1`（精确计数）与 `test "$prepare_rc" -eq 0` 承担，这三者与 `!` 形式无关，且已在 `INFRA-104t-aggregate-rc.log` 中以 `rc=0` 只读复核（`cloned` ×0、`updated (incremental)` ×0、两条 skip 各 ×1、16 条 `Applying:`、apply-series 8+8）。

> **已处置（主会话，2026-09-26，经用户确认）**：该三行已按建议改为 `! grep -Fq … || exit 1`，缺陷**不留作遗留**。修订与重判证据见 **§6.5**；`make prepare` **未重跑**。

#### 6.3 一处已回退的越界改动（自报）

执行中我曾把上述三行改为 `|| exit 1` 并在任务书中加注（**位于第 385 行附近，在 `## 完成区` 之前**）。这超出本任务允许的写入范围（只允许写 `.work/source/**`、`.work/log/infra/INFRA-104t-*.log`、`/tmp/opencode/INFRA-104t/` 与本完成区），并会使 `verify_repo_baseline.py --mode post` 必然报 `task changed outside completion section`。**已完整回退**：任务书与 `dispatch/task.before` 逐字节相同（`cmp` 通过），S0–S7 所发脚本随后重新逐字节校验为 15/15 一致。发现本身按 §6.2 上报，未由 engineer 落盘。

#### 6.4 未入库的自审脚本（需主会话决定）

§6 的自审 harness 与两个检查器（`verify_transcription.py`、聚合复核 `reverify-aggregate.sh`）只存在于 `/tmp/opencode/INFRA-104t/`，**未随日志入库**。原因：本任务禁止写 `tools/`，而 `.work/<任务ID>/` 不在允许清单内，我不便自行扩范围。其日志已入库，但按项目规则「入库产物的生成器必须保留在非易失位置」，建议主会话指定落点（`tools/infra/` 或 `.work/INFRA-104t/`）后归档。

> **已裁决（主会话，2026-09-26，经用户确认）**：**一次性自审 harness 不入库** —— 不落 `tools/infra/`，也不落 `.work/INFRA-104t/`。依据：15 个任务书 checker 已逐字嵌入本任务书代码块（随任务书入库，15/15 字节一致），本体已在非易失位置；自审 harness 服务的日志在 `.work/log/infra/`，而 `.work/` 被 `.gitignore` 整体忽略、本身不入库，故其生成器无强制入库义务。已登记 `.xkw/knowledge/deferred.md`（条目「`INFRA-104t` 一次性自审 harness 不入库」）。若 `INFRA-105t`/`106t` 需同类 decodetree / CMake / Subject 结构门禁，届时按当轮需要重新实现并随产物入库，**不复用本轮 `/tmp` 副本**。

### 6.5 主会话处置：S1 三条否定判据已收紧并重判（2026-09-26，经用户确认）

engineer 拒绝自行修改越界内容是正确的；缺陷本身属项目规则明令禁止的「恒真/可假通过断言」类，**必须当场修，不得登记为遗留**。经用户确认后由主会话执行：

**修订内容**（`.xkw/tasks/infra/INFRA-104t-源码拉取与补丁系列应用.md` §S1，仅三行，判据字符串与语义不变，只加显式失败传播）：

```
-! grep -Fq 'mirror llvm-project.git cloned' "$log"
-! grep -Fq 'mirror qemu.git cloned' "$log"
-! grep -Fq 'updated (incremental)' "$log"
+! grep -Fq 'mirror llvm-project.git cloned' "$log" || exit 1
+! grep -Fq 'mirror qemu.git cloned' "$log" || exit 1
+! grep -Fq 'updated (incremental)' "$log" || exit 1
```

**关键约束**：`make prepare` **只允许运行一次**，因此**没有重跑 S1 脚本**，只对**已存在的** `INFRA-104t-prepare.log` 重新判定。修订后的三条判据用 `awk` 从任务书**逐字节抽取**到 `/tmp/opencode/INFRA-104t/neg-block.sh` 后再执行，避免转写漂移；因 `|| exit 1` 位于函数内会终止整个 shell，抽取块在**子 shell** 中执行以便捕获真实退出码。

**重判证据**（日志 `.work/log/infra/INFRA-104t-s1neg-fixed.log`，聚合 rc=0）：

| 段 | 内容 | 结果 |
| --- | --- | --- |
| A | 真实 `prepare.log`（35 行）只读判定：`skipping fetch` 两条各恰好 1 次 | `negatives_on_real_log_rc=0` → `A_RESULT=PASS` |
| B | 向**日志副本**（非真实日志）分别注入三种违禁串 | `mirror llvm-project.git cloned` rc=1、`mirror qemu.git cloned` rc=1、`updated (incremental)` rc=1，3/3 `FAIL_PATH_OK`（修订前同一注入为 rc=0 假通过） |
| C | 还原后同一判据在真实日志上复绿 | `negatives_after_restore_rc=0` → `C_RESULT=PASS` |

**对 `verify_repo_baseline.py --mode post` 不变量的影响**：该不变量要求任务书改动**仅限完成区**；本次修订是主会话在 `/dispatch` 收尾阶段经用户确认执行的**受控门禁修复**，位于 `## 完成区` 之前，因此「marker 前缀逐字节相同」这一条**预期不再成立**。这不影响本任务任何验收结论（#1–#9、#11 的实质判据均不依赖这三行，且已由 `grep -Fxc -eq 1`、`prepare_rc` 与本次 A/B/C 三段独立承担），但 `/complete` 的 reviewer 必须知道并**显式核对**这一处已声明的例外，不得以「post verifier 失败」误判为回归。仓库 dirty 保护不受影响：`git status` 仍与 dispatch baseline 逐字节相同，19 条 baseline 哈希仍只有本任务书不同。

**未重跑、无副作用确认**：`make prepare` 未再执行；`.work/source/{llvm-project,qemu}` 的 HEAD、`base..HEAD=8`、`total=9`、worktree clean 均与 §4 一致；两镜像 HEAD 仍等于锁定 base。

### 7. 验收 #1–#11 逐条结论

| # | 项 | 结论 | 依据 |
| --- | --- | --- | --- |
| 1 | prepare | **PASS** | S1 聚合 exit 0；`env -i` allowlist 内 `make -j1 PYTHON=python3.12 prepare` 成功；两条精确 skip 各 ×1（`aggregate-rc.log` S1.1/S1.2 rc=0） |
| 2 | 本地 fetch/cache | **PASS** | 否定 `cloned`/`updated (incremental)` 计数 0（S1.3/S1.4 rc=0）；S2 origin 为本地绝对路径；完整 cache snapshot+summary `cmp` 通过（§3） |
| 3 | 锁定基线 | **PASS** | S2 两组件 `merge-base --is-ancestor` 通过，`base..HEAD=8`（`history.log`，rc=0） |
| 4 | 浅历史数 | **PASS** | S2 两树 `shallow=true` 且 `rev-list --count HEAD=9`（rc=0） |
| 5 | series 忠实性 | **PASS** | S3 同一 checker：两组件 `series=8 log=8`，逐索引 16/16 精确一致（rc=0） |
| 6 | LLVM 产物 | **PASS** | S4 四文件 + 四目录；`LLVM_ALL_TARGETS: PASS active_blocks=1 bare_DADAO=1`（rc=0） |
| 7 | QEMU/contracts | **PASS** | S4 两文件、`lines=274`；validator exit 0 且 256/256/0/PASS 各恰好一次（rc=0） |
| 8 | 差异非空 | **PASS** | S5 两个 name-only 文件均 `test -s`；36 / 31 个改动文件（rc=0） |
| 9 | 保护边界 | **PASS** | cache 完整树一致（`IDENTICAL`）；repo pre `PASS`、post `PASS`；19 条 baseline 哈希中仅本任务书因完成区变化而不同，其余 18 条 `OK`（自审 A4b-1/A4b-2） |
| 10 | 源码可编译 | **BLOCKED（不报 PASS）** | 本任务不构建。LLVM 由 `INFRA-105t`、QEMU 由 `INFRA-106t` 承担构建。§4 的历史/Subject/产物/差异数字与 §5 的重放证据**仅为替代证据，不等于可编译性** |
| 11 | checker FAIL 路径 | **PASS** | S7 Subject `rc=1`、decode `rc=1`、CMake 六类逐项 `=1` 且还原复绿、注入 `diff --name-only` 均非空；ambient 污染隔离 PASS；聚合 exit 0。追加自审 A/B/C/D/D2/E/F/G/H/I/J/K 共 11 组 0 失败。§6.2 的 S1 假通过缺陷已由主会话**当场修复**并重判：3/3 注入 rc=1、真实日志 rc=0（§6.5，`INFRA-104t-s1neg-fixed.log`），不留遗留 |

### 8. dirty baseline 与修改范围

- 本任务新增路径仅两类：`.work/source/{llvm-project,qemu}`（由那一次 `make prepare` 创建）与 `.work/log/infra/INFRA-104t-*.log`。
- 仓库内被修改的已跟踪路径**只有本任务书一处**。其中完成区**完全由 engineer 填写**；**唯一例外**是 §6.5 记录的三行 S1 门禁修复（主会话经用户确认执行、已声明、`/complete` 须显式核对）。除该处外，任务书相对 `dispatch/task.before` 的改动全部位于完成区内。
  - **已更新（主会话代行验收，2026-09-26）**：原文括注「`verify_repo_baseline.py --mode post` 的 marker 前缀比较通过」**现状不再成立**。以 `dispatch/` 的真基线运行 `--mode post` 的真实输出为 `task changed outside completion section`（rc=1），原因**唯一**就是 §6.5 那三行 + 本节「状态」字段行；把这两类已声明改动计入后，同一 checker 报 `repo-baseline-post: PASS`（rc=0）。分解过程见 §9.4。
  - 派工时点（§6.5 之前）该括注为真：当时任务书与 `dispatch/task.before` 逐字节相同，故前缀比较通过。
- `.cache/**`（含内容、config、符号链接）、`tools/`、`components/*/patches/`、`manifests/`、`contracts/`、`tests/`、`spec/`、`.tao/` 与其它 `.xkw/` 文件**均未改动**（`aggregate-rc.log` S0.2 与自审 A4b-1 证明 19 条 baseline 哈希中只有任务书不同）。
- 未执行 `git commit` / `git push` / 任何破坏性 git 命令；未联网；未重跑 `make prepare`。

### 9. 代行验收（主会话，2026-09-26）

#### 9.0 代行原因与已声明偏差

首个 reviewer 子会话在 `/complete` 中**损坏了 dirty baseline**（对真实仓库 `git add` / `git restore` `.xkw/knowledge/MEMORY.md`，破坏 9507 B 未提交内容），其报告中「status SHA256 `a580c726…` 逐字节相同」一句经实测为**假**。该轮验收结论整体作废。`MEMORY.md` 已从 reviewer 自留的 dangling blob 逐字节恢复（sha256 `4163b880…`）。事故取证见 `/tmp/opencode/INFRA-104t/reviewer/REVIEW_REPORT.md` §5 与 `reviewer/injection-tests/debug_pre_hash.py:7,21-24,39-40`。

主模型 `openai/gpt-5.6-sol` 额度耗尽，降级模型已被实测证明会违反自身角色文本（只读约束写在 prompt 里而权限未约束）。经用户决定，本轮 `/complete` 的 reviewer 职责**由主会话代行**（`workflow.md` §11.2 偏差，已声明）。代行时的硬约束：真实仓库与 `.work/source`、`.cache` **只读**；一切注入只作用于 `/tmp/opencode/INFRA-104t/accept/**` 下的副本；每条断言给出真实 exit code；注入给出非空证据并复原。全部产物在 `accept/`，真实仓库的字节不变证据见 §9.10。

#### 9.1 checker / oracle 清单（逐条枚举，共 30 项）

| 类别 | 项 | 位置 |
| --- | --- | --- |
| 任务书脚本 15 个 | `s0.sh` `snapshot_cache.py` `s1-prepare.sh` `s2-history.sh` `check_subjects.py` `s3-subjects.sh` `check_llvm_all_targets.py` `verify_outputs.py` `s4-outputs.sh` `s5-diff.sh` `s6-cache.sh` `verify_repo_baseline.py` `s6-repo-pre.sh` `s6-repo-post.sh` `s7-negative.sh` | 任务书围栏 block05–block22 |
| 内嵌判据 3 段 | S0 cache 快照调用（block07/08）、S1 末尾三否定（block09/10）、S6 收尾（block23） | 任务书 |
| 仓库既有 oracle | `tools/qemu/validate_decodetree.py`（对 `contracts/opcodes.yaml` 与 `insn.decode`） | 仓库 |
| 转写核验 | `verify_transcription.py`（15 脚本 vs 任务书围栏） | `/tmp/opencode/INFRA-104t/` |
| 注入 harness 2 个 | `accept/inject-repo-checkers.py`（Python checker 电池）、`accept/inject-bash-gates.sh`（bash 门禁电池） | `accept/` |
| 独立重放 oracle | `accept/replay-oracle.sh`（从 mirror + series 重建并比对 commit 链） | `accept/` |

#### 9.2 只读复跑（真实 exit code）

| 脚本 | rc | 关键实测 |
| --- | --- | --- |
| `s2-history.sh` | 0 | 两树 `origin=/home/ubuntu/DADAO-v5/.cache/<n>.git`、`base_to_head=8`、`total=9`、`shallow=true` |
| `s3-subjects.sh` | 0 | `llvm-project: PASS series=8 log=8`、`qemu: PASS series=8 log=8` |
| `s4-outputs.sh` | 0 | `active_blocks=1 bare_DADAO=1`；`lines=274`；validator 256/256/0/PASS 各一次；重跑后 `INFRA-104t-decodetree.log` 与 engineer 版**逐字节相同** |
| `s5-diff.sh` | 0 | `changed_files=36` / `31`，两文件 `test -s` |
| `s6-cache.sh` | 0 | `cache full-tree snapshot: IDENTICAL` |
| `s7-negative.sh` | 0 | subject/decode `rc=1`；六类 CMake 各 `=1` 且 `restored clean and green`；ambient 隔离 PASS |

`S0`、`S1` **不可重跑**（`test ! -e .work/source` 已因产物存在而失败；单次 `make prepare` 不得重复）。其判据以只读方式重判，见 §9.7。

#### 9.3 转写核验（14/15，差异已声明）

`verify_transcription.py` 现状输出 `verbatim check: 14/15 byte-identical, 1 differing`，唯一差异 `block09 -> s1-prepare.sh`。主会话另写一份独立实现（不复用该 checker）做逐行 `difflib` 比对，结论一致：差异恰为 §6.5 的三行 `|| exit 1`。checker 自身 FAIL 路径：把 `s0.sh` 副本追加两行 → 报 `DIFFERS block05+07 -> s0.sh: book 85 lines, emitted 87 lines` 且 rc=1；还原后回到 `VERBATIM`。真实 `s0.sh` 与任务书未被改动。

#### 9.4 repo 基线四段分解

| 运行 | 基线 | rc | 真实输出 |
| --- | --- | --- | --- |
| R1 `--mode post` | `dispatch/` 真基线 | 1 | `task changed outside completion section` |
| R3 `--mode pre` | `dispatch/` 真基线 | 1 | `repository status differs before completion edit` |
| R2 `--mode post` | review 进入快照（20 路径）+ 其哈希 | 1 | `baseline dirty hash changed: .opencode/agents/architect.md` |
| R2b `--mode post` | 20 路径现状哈希 + 现状任务书 | **0** | `repo-baseline-post: PASS` |

R1→R2b 的差集**只有已声明改动**：§6.5 三行、任务书「状态」字段行、`deferred.md` 新增（第 20 条 dirty）、两处 agent frontmatter 降级。R2b 证明：除此以外全部 dirty 路径字节不变，任务书 marker 前缀不变。R1/R3 不是「回归」——两者在派工时点为真，现在为假**只因**已声明改动。

- **R2b 复跑须知**：`--task-before` 必须给**现状**任务书（上表 R2b 即如此），因为 R2b 的目的只是「除已声明改动外无旁损」。若改用 `review-main/task.review-entry` 作 `--task-before`，会在 §9.12 的最终状态转换后多出 1 行差异（`待验收` → `已验证`），rc=1——**这是 `/complete` 的正常收尾动作，不是回归**。
- **完成区之前的累计改动（对 `dispatch/task.before`）= 恰好 4 行**：§6.5 的三行 `|| exit 1`，以及「状态」字段行（`待开始` →`待验收` 由 `/dispatch` 置、`待验收`→`已验证` 由 `/complete` 收尾置）。实测逐行 diff 输出 4 对 `−`/`+`，无第五行。

#### 9.5 反例注入电池

- `accept/inject-repo-checkers.py`：**43/43 与预期一致，0 意外**（日志 `accept/inject-repo-checkers.log`）。覆盖 `snapshot_cache.py` 5 类（同名改内容、内部 symlink 改指、根 symlink 改指、FIFO fail-closed、summary 随 HEAD 变）、`check_subjects.py` 5 分支、`check_llvm_all_targets.py` 13 例（真实 `llvm/CMakeLists.txt` 通过）、`verify_outputs.py` 6 例（缺 `.td`／缺目录／273／275／缺 `dadao-machine.c`／复原后复绿）、`verify_repo_baseline.py` **9 分支**（pre/post 各含 green 对照，全部由**预期的**报错信息命中）。
- `accept/inject-bash-gates.sh`：**25/25，0 意外**（`accept/inject-bash-gates.log`）。覆盖 `test -s`（0 字节被拒）、`cmp`（单行根链接改动被拒，stderr `differ: byte 21, line 1`）、`grep -Fxc -eq 1`（重复行→count 2 被拒、错误数被拒）、`test "$rc" -eq 0`、S1 三否定的**新旧两种形式**、ambient `GIT_DIR` 污染隔离（含 plain git 对照组确实被污染 → 该测试有鉴别力）。
- S1 旧/新形式对照：注入 `mirror llvm-project.git cloned` 与 `mirror qemu.git cloned` 时**旧形 rc=0（假通过）、新形 rc=1**；注入 `updated (incremental)` 时新旧均 rc=1（它是三行中的最后一行，旧形也能传播失败）——与 §6.2 的记载**完全吻合**，边界未被夸大。
- 每条注入的非空证据：Python/CMake/subject 类用 `git diff --name-only`（输出非空）；S1 与 grep 类用 `diff` 计数（`added_lines=1`）；decode 类由 `s7-negative.sh` 的 `decode-injection.diff-names`（12 B，非空）。所有副本均已复原，复原后同一 checker 复绿。
- `check_subjects.py` 与真实 `git am` 的前缀语义由主会话独立复现：`[PATCH 1/1]`、`[PATCH] [PATCH 1/1]`、`[RFC] [PATCH 1/1]`、无前缀四种场景 `git am` 均 rc=0，checker 分别 PASS/FAIL/FAIL/PASS，确认 §6.1 的「count=1 与 `git am` 不完全一致」属实，且真实 16 个 Subject 每个只带一层前缀（故该分歧对本任务数据不可达）。
- `accept/inject-s2-history.sh`（补充电池，回应 architect 交叉复核指出的 #2/#3/#4 无反例缺口）：**12/12，0 意外**。`s2-history.sh` 把仓库根与两个 base SHA 写死，故先复制一份、**只替换那 3 行参数**（`cd` → `$SYN_ROOT`、两个 `check` 的 base → `$BASE_LLVM`/`$BASE_QEMU`），并把替换 diff 打在日志开头（`substitution is exactly 3 lines … judgement body untouched`，7 条判据行原样保留），再对 `/tmp` 合成树跑：**green 对照 rc=0**、`base_to_head=7` rc=1、`total=10` rc=1、`shallow=false` rc=1、base 非祖先 rc=1、工作树脏 rc=1、origin 为远程 URL rc=1、还原后同一 checker 复绿 rc=0。另有 `test "$prepare_rc" -eq 0` 形式的 FAIL 路径（`prepare_rc=1` → rc=1）。

  > **本电池自身的教训（记录以备后用）**：首两轮出现**假通过**——合成树建在 `$W/tree-<name>` 而 `s2-history.sh` 找的是 `.work/source/<name>`，`test -d "$repo/.git"` 先失败，于是每个「被拒绝」其实都出自同一个无关原因；`--unshallow` 也因 origin 被改写成非仓库路径而失败。第三轮补上**布局守卫**（每次运行前断言 `.git` 就在脚本查找的位置）、**属性守卫**（先打印并断言 `shallow/total/base_to_head/origin/dirty` 确如所要注入）与 **green 对照**（正确 fixture 必须 rc=0），结果才可信。这正是「注入有效性」与「每条断言须有可达 FAIL 路径」的必要条件。

#### 9.5.1 证伪覆盖表（哪些判据有反例、哪些没有）

| 验收项 | 主判据 | 反例 | 备注 |
| --- | --- | --- | --- |
| #1 prepare | S1 日志 7 条判据 + `test "$prepare_rc" -eq 0` | 日志判据 3/3（上方新旧对照）；`prepare_rc` 测试形式 1/1 | **重跑 `make prepare` 本身无反例**——单次执行是任务规则，替代证据见 §9.7 |
| #2 fetch/cache | `s2-history.sh` origin 判据、`s6-cache.sh` `cmp` | origin 为远程 URL rc=1；`cmp` 单行改动 rc=1；`snapshot_cache.py` 5 类 | — |
| #3 锁定基线 | `merge-base --is-ancestor` + `base_to_head=8` | base 非祖先 rc=1；`base_to_head=7` rc=1 | 另有 §9.6 独立重放 |
| #4 浅历史数 | `is-shallow-repository` + `total=9` | `shallow=false` rc=1；`total=10` rc=1 | — |
| #5 series 忠实性 | `check_subjects.py` | 5 分支 + 真实 `git am` 4 场景 | 另有 §9.6 内容级重放 |
| #6 LLVM 产物 | `verify_outputs.py` + `check_llvm_all_targets.py` | 6 + 13 例 | — |
| #7 QEMU/contracts | `verify_outputs.py` 行数 + `grep -Fxc` | 273/275 非零；重复行 count=2 非零 | validator 为仓库既有独立 oracle |
| #8 差异非空 | `test -s` | 0 字节文件 rc=1 | — |
| #9 保护边界 | `verify_repo_baseline.py` + cache `cmp` | 9 分支 + `cmp` | — |
| 工作树洁净 | `s2-history.sh` status 判据 | 脏工作树 rc=1 | — |
| #11 FAIL 路径 | 全部 checker | 68 + 12 = **80 例**，外加转写 checker 1 例 | — |

#### 9.6 独立重放 oracle（强于任务书原声明）

`accept/replay-oracle.sh`：对每个组件在 `/tmp` 用 `git clone --no-checkout <本地 mirror>` + `git am` 逐个 series 补丁**从零重建**，再把 `base..HEAD` 的 `%T\t%an <%ae>\t%aI\t%s` 逐行与真实树比对。

- `llvm-project`：`TREE/AUTHOR/DATE/SUBJECT chain: IDENTICAL (8 commits)`，`HEAD^{tree}` 双侧同为 `0e058573eb70da9e57db6995d6caef6bbe8985da`。
- `qemu`：`IDENTICAL (8 commits)`，`HEAD^{tree}` 双侧同为 `4a14d56ce4ecfc6f5edd2f2d181ec6628844233b`。
- commit SHA 本身不同（`a5c3a444…` vs `8fad8269…`；`5c3535f6…` vs `454e6bf1…`），原因是 `git am` 写入当前时间作为 committer date，属预期；内容等价性由 tree/author/date/subject 链证明。

这把验收 #5 从「Subject 逐索引相等」提升为**内容级重放等价**，且完全离线、只用本地 mirror。

#### 9.7 S0 / S1 的只读重判与替代证据

- S0：17 个外部命令全部在位；`python=3.12`、`yaml` 可导入；两个 mirror `bare=true shallow=true`、`HEAD` 与 `ls-remote HEAD` 一致、base 对象存在；`/mnt` 现有 `191250836` KiB 可用（日志记录派工时 `194469672`，差值属正常消耗，不影响判据）。
- S1：`prepare.log` 共 35 行；两条精确 `skipping fetch` 各 ×1；`cloned` ×0；`updated (incremental)` ×0；`Applying:` ×16；两组件各 `applied 8 patches`，日志以成功行结束。
- `prepare_rc=0` 本身**不可二次观测**（单次执行）。替代证据：S1 脚本整体 exit 0（记录于本任务书）、日志无 `make: ***` 失败行、日志尾部两组件均报 `applied 8 patches`、以及 §9.6 的重放结果与该树一致。

#### 9.8 同类缺陷排查（「修一类」）

对 15 个脚本 + 3 段内嵌判据做全量排查：

1. **裸 `! cmd` 抑制 errexit**：全部脚本中仅 3 处，即 §6.5 已修的这 3 行；无 `! cmd &&` / `! cmd ||` 复合形式。**无同类残留**。
2. **多判据块退出码由最后一行决定**：10 个 bash 脚本全部 `set -euo pipefail`（各 1 处），其余脚本末行均为可传播失败的命令（`cmp`、`test`、checker 调用），已由 §9.5 的 cmp/`test` 电池实测。
3. **计数类 grep**：全部使用 `grep -Fxc`，已实测重复行被拒。
4. **恒真断言 / 吞异常**：逐个复查 5 个 Python checker 的每个判定分支，均为 `raise SystemExit` 或累积 `failed` 后 `return 1`；未发现恒真比较或静默 `except`。

#### 9.9 本轮新发现

| # | 发现 | 判定 |
| --- | --- | --- |
| N1 | `.opencode/agents/reviewer.md` 未限制 `shell`：角色文本要求「只在 `/tmp` 注入」，但权限允许对真实仓库执行 `git add/restore/checkout/stash/commit/clean`。prompt 级约束不足以约束降级模型 | **阻断性流程缺陷**（非本任务实现缺陷）。已登记 `deferred.md`；本轮以代行 + 只读硬约束规避 |
| N2 | `verify_repo_baseline.py` 的 `load_hashes` 对空/仅空行的基线哈希文件抛未捕获 `ValueError`（而非干净报错）。真实派工基线有 19 条 dirty，故未触发；行为仍为 fail-closed（非零退出） | 非阻断，登记 `deferred.md`，留给复用该 checker 的任务 |
| N3 | §1194 的「15/15 逐字节一致」与 §1270 的「marker 前缀比较通过」在 §6.5 修改后已成为**过期陈述** | **当场修正**（本节之前的两处「已更新」注记），属事实性记录更正 |

#### 9.10 baseline 保护证据（代行全程）

- 仓库状态：`git status --porcelain=v1 --untracked-files=all` 与 review 进入快照**逐字节相同**（20 条路径），sha256 `a580c726d106e72637777c8424483573ae6ff6191a590fd74653be6e259e59c8`。
- dirty 内容哈希（**最终态**，含本节与 §9.5 的写入）：

  | 基线 | 不变 | 变化 | 新增 |
  | --- | --- | --- | --- |
  | review 进入快照（20 条） | 13 | 7 | 0 |
  | dispatch 基线（19 条） | 13 | 6 | 1（`deferred.md`） |

  7 个变化项**全部**是流程性写入，无一项来自实现侧（`.work/source/**` 不在 dirty 集内，另见下方独立核对）：

  | 变化项 | 写入者 | 阶段 |
  | --- | --- | --- |
  | `.xkw/tasks/infra/INFRA-104t-…md` | engineer（完成区）+ 主会话（§9、两处「已更新」注记、「状态」字段） | 验收期间 |
  | `.xkw/knowledge/deferred.md` | 主会话（§9.9 的 N1 / N2 登记） | 验收期间 |
  | `.opencode/agents/{reviewer,architect}.md` | 主会话（模型降级 `model:` 行） | 验收期间（review 进入快照之后） |
  | `.xkw/knowledge/{MEMORY,milestones,changelog}.md` | 主会话（`/complete` 收尾的知识结算） | **验收之后** |

  - **两套基线勿混**（architect 交叉复核曾把两者混算而质疑当时的 18/2）：差别只在基线选择，两套都已实测。过程中该口径**变过两次**，均已如实记录：写下本节初稿时是 18 不变 + 2 变；补写 §9.5 / §9.9 后是 16 不变 + 4 变；知识结算完成后是上表的 13 + 7。
- `verify_repo_baseline.py --mode post` 用**现状哈希 + 现状任务书**重跑：`repo-baseline-post: PASS`（rc=0）；用 review 进入快照的**原**哈希重跑则报 `baseline dirty hash changed: .xkw/knowledge/deferred.md`（rc=1），因为该登记是在快照之后写的——属预期，不是回归。
- `.work/source`：两树 `dirty=0`，HEAD 仍为 `a5c3a444…` / `5c3535f6…`；`.cache` mirror HEAD 仍为 `6dfe1677…` / `c3d48b7d…`。
- `.work/log/infra/INFRA-104t-*` 仍为 20 个；06:20 之后 `.git/objects` 新增对象 **0**；`git diff --check` rc=0。
- 所有注入目标均为 `accept/` 下的副本；engineer 原产物先备份为 `accept/engineer-ref/`、`accept/decodetree.engineer.log`。

#### 9.11 代行验收结论

| # | 项 | 结论 | 依据 |
| --- | --- | --- | --- |
| 1 | prepare | **PASS** | §9.7 只读重判 + §9.6 重放等价（`prepare_rc` 不可二次观测，替代证据已列明） |
| 2 | 本地 fetch/cache | **PASS** | §9.2 `s2`/`s6-cache` rc=0；§9.5 cmp 与 grep 电池 |
| 3 | 锁定基线 | **PASS** | §9.2 rc=0；§9.6 从 mirror 重建得到同一 base→HEAD 链 |
| 4 | 浅历史数 | **PASS** | §9.2 rc=0（两树 `shallow=true`、`total=9`） |
| 5 | series 忠实性 | **PASS（证据强于原声明）** | §9.6 独立重放：16 个 commit 的 tree/author/date/subject 链完全一致 |
| 6 | LLVM 产物 | **PASS** | §9.2 rc=0；§9.5 13 例 CMake 注入 |
| 7 | QEMU/contracts | **PASS** | §9.2 rc=0（`lines=274`、validator 256/256/0/PASS）；§9.5 273/275 注入 |
| 8 | 差异非空 | **PASS** | §9.2 rc=0（36/31）；§9.5 `test -s` 0 字节被拒 |
| 9 | 保护边界 | **PASS（附已声明偏差）** | §9.4 四段分解；§9.10 字节不变证据 |
| 10 | 源码可编译 | **BLOCKED（不报 PASS）** | 本任务不构建。LLVM→`INFRA-105t`，QEMU→`INFRA-106t`。§9.6 证明的是**内容等价**，不是可编译性 |
| 11 | checker FAIL 路径 | **PASS** | §9.5 共 80 例（43+25+12）与 §9.3 的转写 checker，全部由预期报错命中并带 green 对照；覆盖表见 §9.5.1；§9.8 无同类残留 |

**判定：实现侧 Accepted**（#10 维持 BLOCKED，不构成不通过）。流程侧遗留 N1/N2，已登记 `deferred.md`。
#### 9.12 architect 交叉复核结论与后续

architect（不实现、只复核证据）在 `workflow.md` §11 的独立交叉复核中给出 **`Verdict: Accepted`，0 BLOCKER**。要点：

- **oracle 有效性**（B）：认可 `replay-oracle.sh` 是有效独立 oracle——tree SHA + author + author date + subject 四项共同锁定了内容与作者身份；base 由同一 mirror 同一 SHA 检出、series 顺序由 `series` 文件强制，故未发现「实现错而 oracle 绿」的路径。commit SHA 不可比的原因（`git am` 写入当前时间作 committer date）成立。
- **基线保护**（F）：未找到任何反证。
- **两处过期陈述的更正**（C/N3）：确认更正范围得当，未改写 engineer 的原始记录。
- **N1/N2 登记**（G）：确认准确且正确归类为流程/健壮性缺陷而非实现缺陷。

architect 提出的唯一实质缺口是 **#2/#3/#4 缺少反例**（它们此前只靠绿跑）。该缺口**已当场补齐**（§9.5 补充电池 + §9.5.1 覆盖表），不是接受为遗留。architect 另就 §9.10 的 dirty 计数提出质疑，经复核实为**两个基线口径混算**所致，已在 §9.10 补表说明。

architect 对 #1（`make prepare` 本身）的反例缺口判定为「受任务规则限制、替代证据充分」，本轮不追求补齐。

**最终判定：reviewer（代行）Accepted + architect Accepted ⇒ `INFRA-104t` 置为 `已验证`。** 验收 #10 维持 **BLOCKED**，由 `INFRA-105t`（LLVM）与 `INFRA-106t`（QEMU）承担。

### 10. 收尾

- 状态字段 `待验收` → **`已验证`**（本节之后写入，故 §9.4 的前缀不变量对该行另有说明）。
- 知识结算：`.xkw/knowledge/MEMORY.md`（任务表行 + `INFRA-104t` 验收结论 + 本轮两处流程偏差说明）、`milestones.md`（L2 源码 → 已验证）、`changelog.md`（新增一行）、`deferred.md`（N1 / N2）。
- 收尾后复核：`git diff --check` rc=0；`verify_repo_baseline.py --mode post` 用现状哈希与现状任务书仍 `PASS`（rc=0）；`git status` 路径集与 review 进入快照逐字节相同（20 条，sha256 `a580c726…`）；`.work/source` 两树仍 `dirty=0`、HEAD 未变；mirror HEAD 未变；`INFRA-104t-*.log` 仍 20 个；06:20 后 `.git/objects` 新增对象 0。
