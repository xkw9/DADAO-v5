#!/usr/bin/env python3
"""为宿主 default python3（3.10）补上 stdlib 缺失的 `tomllib`。

## 为什么需要这个脚本（根因，不是 workaround 的借口）

`Makefile:8` 用**单一** `PYTHON ?= python3` 同时服务两类互斥需求：

| 消费方 | 位置 | 需要 |
| --- | --- | --- |
| 仓库工具链 | `Makefile:30` `component-enabled`、`Makefile:55` `manifest_check.py`（`tools/infra/*.py` 另有 6 处 `import tomllib`） | `tomllib` ⇒ **Python ≥ 3.11** |
| QEMU 构建 | `configure` → `mkvenv.py` → `pip install -e python/`（PEP 517） | `setuptools.build_meta` ⇒ 本宿主只有 **3.10** 的 59.6.0 可用 |

`python3.12` 有 `tomllib`，但宿主 jammy 的 `python3-setuptools 59.6.0` 是**为 3.10 构建**的，
其 `__init__.py:10` 依赖 `distutils`，而 `distutils` 在 3.12 已被移除 ⇒ 在 3.12 上不可导入
⇒ `BackendUnavailable` ⇒ `build-qemu_rc=2`。

两侧在宿主上互斥。本脚本选择**给 3.10 补 `tomllib`**（而非换 Python），因为：

1. 3.10 侧的 `setuptools` 已被实测可用，无需任何 pip 动作；
2. 补完 3.10 后，`Makefile:8` 的默认值**无需修改** ⇒ 裸 `make build-qemu` 即可用；
3. 零仓库改动、零 root 权限。

## 为什么 shim 放在 user site-packages 而不是 PYTHONPATH

`sys.path` 顺序为 `stdlib` → `lib-dynload` → **`~/.local/.../site-packages`** → 全局 site-packages。
user site-packages 排在 **stdlib 之后**，所以：

- 3.10 的 stdlib 没有 `tomllib` ⇒ shim 生效；
- 3.11/3.12 的 stdlib 有 `tomllib` ⇒ **真 stdlib 优先，shim 不会遮蔽**（本脚本会实测验证）。

反之若把 shim 放 `PYTHONPATH`（排在 stdlib **之前**），会**遮蔽 3.12 的真 tomllib**。已实测确认，故不用该变体。

## 用法

```bash
python3 tools/infra/install_tomllib_shim.py          # 安装 + 自验证
python3 tools/infra/install_tomllib_shim.py --check  # 只自验证，不改动
```

幂等：已安装则不重复动作。任一验证项失败即以非 0 退出。

> 局限：这是**绕过**，`Makefile` 的设计缺陷未消除（见
> `.xkw/knowledge/deferred.md` 的「Makefile 单一 $(PYTHON) 两侧互斥」条目）。
> 正解是让 `Makefile` 为工具链与 QEMU 构建分别选择解释器。
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SHIM_NAME = "tomllib.py"
SHIM_SOURCE = '''\
"""shim: Python 3.10 的 stdlib 没有 tomllib，转发到 API 等价的 tomli。

由 tools/infra/install_tomllib_shim.py 生成，请勿手工编辑。
放在 user site-packages（而非 PYTHONPATH）是因为它排在 stdlib 之后：
3.10 无 tomllib 故本 shim 生效；3.11+ 的 stdlib tomllib 优先，不会被遮蔽。
"""

from tomli import TOMLDecodeError, load, loads  # noqa: F401

__all__ = ["load", "loads", "TOMLDecodeError"]
'''


def _run(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def _user_site() -> Path:
    # 不用 site.getusersitepackages()：它不保证父目录已建，且跨版本路径需实测。
    out = subprocess.run(
        [sys.executable, "-c", "import site; print(site.getusersitepackages())"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    return Path(out)


def _check_python_version() -> tuple[int, str]:
    rc, out = _run([sys.executable, "-c", "import sys; print('%d.%d.%d' % sys.version_info[:3])"])
    return rc, out


def install() -> list[str]:
    """执行安装，返回动作说明列表。幂等。"""
    actions: list[str] = []

    user_site = _user_site()
    user_site.mkdir(parents=True, exist_ok=True)
    actions.append(f"user site-packages = {user_site}")

    # 1) tomli —— 3.10 侧 tomllib 的后端
    rc, out = _run([sys.executable, "-c", "import tomli"])
    if rc == 0:
        actions.append("tomli 已安装，跳过")
    else:
        rc, out = _run(
            [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "-q",
             "--user", "tomli"]
        )
        if rc != 0:
            raise RuntimeError(f"pip install --user tomli 失败：\n{out}")
        actions.append("已 pip install --user tomli")

    # 2) shim
    shim = user_site / SHIM_NAME
    if shim.exists() and shim.read_text() == SHIM_SOURCE:
        actions.append(f"{shim} 已是目标内容，跳过")
    else:
        shim.write_text(SHIM_SOURCE)
        actions.append(f"已写入 {shim}")
    return actions


def verify() -> list[tuple[str, bool, str]]:
    """返回 [(检查名, 是否通过, 实测输出)]。任一失败则整体失败。"""
    results: list[tuple[str, bool, str]] = []

    rc, out = _check_python_version()
    results.append(("本解释器版本", rc == 0, out))

    # 本解释器（3.10）应能 import tomllib，且解析出 components.lock.toml
    rc, out = _run([
        sys.executable, "-c",
        "import tomllib;"
        "m=tomllib.load(open('manifests/components.lock.toml','rb'));"
        "print('components=%d' % len(m.get('component',[])))",
    ])
    results.append((f"{sys.executable} 可 import tomllib 并解析 components.lock.toml", rc == 0, out))

    # shim 只为「stdlib 没有 tomllib 的解释器」而存在，故判据必须按被测解释器
    # **有无 stdlib tomllib** 分支：
    #   <  3.11 —— stdlib 无 tomllib ⇒ shim 必须生效（shim 存在的全部意义）
    #   >= 3.11 —— stdlib 有 tomllib ⇒ shim 正确地**不**生效（它排在 stdlib 之后，见文件头）
    # 否则用 3.12 跑 --check 会「明明安装完好却误报 RESULT: FAILED」。
    # （2026-09-26 复现时实测到该误报并修正；修的是判据，不是安装。）
    rc_v, out_v = _run([
        sys.executable, "-c",
        "import sys; print(1 if sys.version_info >= (3, 11) else 0)",
    ])
    has_stdlib_tomllib = out_v.strip() == "1"
    rc, out = _run([sys.executable, "-c", "import tomllib; print(tomllib.__file__)"])
    tomllib_path = out.strip()
    if has_stdlib_tomllib:
        results.append((
            f"{sys.executable} 自带 stdlib tomllib（本就不需要 shim）",
            rc == 0,
            tomllib_path,
        ))
    else:
        results.append((
            f"{sys.executable} 的 tomllib 来自 user site-packages 的 shim",
            rc == 0 and "site-packages" in tomllib_path,
            tomllib_path,
        ))

    # 3.11+ 若存在，其 stdlib tomllib 必须未被遮蔽
    other = None
    for cand in ("python3.11", "python3.12", "python3.13"):
        if shutil.which(cand) or Path(f"/usr/bin/{cand}").exists():
            other = cand
            break
    if other is None:
        results.append(("无 3.11+ 解释器可比对，跳过遮蔽检查", True, "n/a"))
    else:
        rc, out = _run([other, "-c", "import tomllib; print(tomllib.__file__)"])
        not_shadowed = rc == 0 and "site-packages" not in out
        results.append((f"{other} 的 stdlib tomllib 未被 shim 遮蔽", not_shadowed, out))

    # Makefile 的两条守卫都必须放行
    rc, out = _run(["make", "manifest-check"])
    results.append((f"make manifest-check（$(PYTHON)=python3）rc={rc}", rc == 0, out.splitlines()[-1] if out else ""))

    rc, out = _run([
        sys.executable, "-c",
        "import tomllib,sys;"
        "m=tomllib.load(open('manifests/components.lock.toml','rb'));"
        "sys.exit(0 if any(c['name']=='qemu' and c.get('enabled') for c in m.get('component',[])) else 1)",
    ])
    results.append((f"component-enabled(qemu) rc={rc}（守卫须放行）", rc == 0, out or "(no output)"))

    # QEMU 侧不能被破坏：非隔离 venv 里 setuptools.build_meta 仍须可导入。
    # 探针解释器固定取 **/usr/bin/python3**（QEMU 的 mkvenv.py 用的就是它），
    # 不跟随 sys.executable —— 否则用 3.12 自检时会在 3.12 上查 setuptools，
    # 而 3.12 的 setuptools 依赖已移除的 distutils，必然 FAIL，那是宿主事实、
    # 不是本 shim 造成的。临时目录用 mkdtemp，不绑定任何任务号。
    probe = Path("/usr/bin/python3")
    if not probe.exists():
        probe = Path(sys.executable)
    rc_v, out_v = _run([str(probe), "-c", "import sys; print('%d.%d.%d' % sys.version_info[:3])"])
    venv_dir = Path(tempfile.mkdtemp(prefix="tomllib-shim-verify-"))
    try:
        rc, out = _run([
            str(probe), "-m", "venv", "--without-pip", "--system-site-packages", "--clear", str(venv_dir),
        ])
        if rc == 0:
            rc2, out2 = _run([
                str(venv_dir / "bin" / "python"), "-c",
                "import setuptools.build_meta as b; print('setuptools', __import__('setuptools').__version__)",
            ])
            results.append((
                f"{out_v} 非隔离 venv 内 setuptools.build_meta 可导入（QEMU 侧未受损）",
                rc2 == 0,
                out2,
            ))
        else:
            results.append((f"创建 {out_v} 探针 venv", False, out))
    finally:
        shutil.rmtree(venv_dir, ignore_errors=True)
    return results


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="只自验证，不改动任何文件")
    args = ap.parse_args()

    print("=== install_tomllib_shim ===")
    if args.check:
        print("mode = --check（不改动文件）")
    else:
        for act in install():
            print(f"  [install] {act}")

    print("\n=== verify ===")
    results = verify()
    failed = 0
    for name, ok, out in results:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
        if out:
            for line in out.splitlines():
                print(f"         {line}")
        if not ok:
            failed += 1

    print(f"\nRESULT: {'OK' if failed == 0 else 'FAILED'}  ({len(results) - failed}/{len(results)} passed)")
    if failed:
        print("说明：shim 只解决 tomllib 侧。若 QEMU 侧报 setuptools 不可导入，"
              "那是另一个问题（宿主 3.12 的 setuptools 依赖已移除的 distutils）。")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
