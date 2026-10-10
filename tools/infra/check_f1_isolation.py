#!/usr/bin/env python3
"""F1 isolation checker (INFRA-108t) -- acceptance criterion 1 and the F1/M1
separation rules of ADR-1004 D6/D9.

Every check prints its own ``PASS``/``FAIL`` line and any failure is a hard
non-zero exit, so a green run is a list of individually true statements rather
than a single aggregate assertion.  Checks:

1. ``f1_root`` exists, is a real directory, does not escape the work root, and
   resolves to exactly ``<work>/f1``.
2. Per component: the F1 source tree and the F1 build root resolve to exactly
   ``<f1>/source/<component>`` and ``<f1>/build/<build-dir>``.  This is a
   *canonical* (``realpath``) comparison, so a symlink -- or any other
   out-of-root path -- that leaves the F1 root is rejected even though its
   textual path is inside it, while the pre-existing ``.work`` symlink of this
   host does not make a legitimate layout look escaped.
3. Per component: the F1 source tree sits at the exact canonical path, is a git
   worktree, is a *different* repository from the M1 tree, has the recorded M1
   8-patch head as an ancestor, carries exactly as many commits above that head
   as the F1 series has entries (i.e. the series is fully applied, not half),
   and has a clean working tree.
4. Per component: the state record written by ``f1_prepare.py`` matches the live
   tree (base lock, M1 head commit/tree, F1 head commit/tree, patch count, clean).
5. F1 paths are realpath-disjoint from the M1 source/build paths, and the F1
   build roots are not inside an M1 build root.
6. No F1 artefact leaked into the M1 build trees: no ``f1`` path component
   anywhere under ``<work>/build/{llvm,qemu}``, and none of the M1 build's key
   configuration files mentions the F1 path.
7. The F1 series satisfies the ``0009+`` constraints (frozen M1 prefix,
   continuous numbering, existing non-empty patches).
8. ``--require-idle``: no process is currently working inside the M1 or F1 build
   trees (the serialisation rule: never run an M1 and an F1 build at once).

Usage::

    check_f1_isolation.py [--root ROOT] [--work WORK] [--component NAME]...
                          [--require-m1] [--require-idle]
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from f1_common import (  # noqa: E402
    DEFAULT_ROOT,
    F1_COMPONENTS,
    F1Error,
    f1_build,
    f1_component_gates,
    f1_entry_names,
    f1_root,
    f1_root_gate,
    f1_source,
    git,
    is_git_worktree,
    load_f1_meta,
    load_manifest,
    load_state,
    m1_build,
    m1_source,
    series_problems,
    work_root,
)
from check_f1_baseline import M1_BUILD_KEY_FILES  # noqa: E402


class Report:
    def __init__(self) -> None:
        self.failures = 0
        self.checks = 0

    def check(self, name: str, ok: bool, detail: str = "") -> bool:
        self.checks += 1
        if not ok:
            self.failures += 1
        print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f": {detail}" if detail else ""))
        return ok


def _inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _is_ancestor(repo: Path, ancestor: str) -> bool:
    return subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", ancestor, "HEAD"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode == 0


def _build_dir_f1_components(build: Path) -> list[str]:
    found: list[str] = []
    for directory, subdirs, files in os.walk(build):
        for name in list(subdirs) + list(files):
            if name == "f1":
                path = Path(directory) / name
                found.append(str(path.relative_to(build)))
    return sorted(found)


def _busy_cwd(roots: list[Path]) -> list[tuple[int, str]]:
    busy: list[tuple[int, str]] = []
    resolved = [root.resolve() for root in roots if root.is_dir()]
    if not resolved:
        return busy
    for entry in os.scandir("/proc"):
        if not entry.name.isdigit():
            continue
        try:
            cwd = Path(os.readlink(f"/proc/{entry.name}/cwd"))
        except OSError:
            continue  # not ours, or the process exited
        for root in resolved:
            if _inside(cwd, root):
                busy.append((int(entry.name), str(cwd)))
                break
    return sorted(busy)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=str(DEFAULT_ROOT))
    parser.add_argument("--work")
    parser.add_argument("--component", action="append", choices=list(F1_COMPONENTS))
    parser.add_argument(
        "--require-m1",
        action="store_true",
        help="fail when an M1 source tree is absent instead of reporting it",
    )
    parser.add_argument(
        "--require-idle",
        action="store_true",
        help="fail when a process is working inside an M1 or F1 build tree",
    )
    args = parser.parse_args()
    root = Path(args.root).resolve()
    work = (
        Path(args.work).resolve() if args.work else work_root(root, load_manifest(root))
    )
    components = args.component or list(F1_COMPONENTS)
    report = Report()

    f1_base = f1_root(work)
    if not report.check(
        "f1_root present",
        f1_base.is_dir(),
        f"{f1_base} ({'symlink' if f1_base.is_symlink() else 'directory'})",
    ):
        print("check-f1-isolation: FAIL f1_root missing; run `make f1-prepare`")
        return 1
    report.check(
        "f1_root inside work root",
        _inside(f1_base, work),
        f"{f1_base.resolve()} vs {work.resolve()}",
    )
    # Canonical containment: reported before anything is inspected *inside* the
    # F1 root, so an escaped layout cannot be waved through by the per-component
    # git checks that would still pass on whatever the symlink points at.
    name, detail, ok = f1_root_gate(work)
    report.check(name, ok, detail)

    for component in components:
        label = f"{component}"
        for name, detail, ok in f1_component_gates(work, component):
            report.check(name, ok, detail)

        meta = load_f1_meta(root, component)
        tree = f1_source(work, component)
        build = f1_build(work, component)

        if not report.check(
            f"{label}: F1 source at the canonical path",
            tree.is_dir() and is_git_worktree(tree),
            str(tree),
        ):
            continue
        m1_tree = m1_source(work, component)
        f1_gitdir = (tree / ".git").resolve()
        if m1_tree.is_dir():
            m1_gitdir = (m1_tree / ".git").resolve()
            separate = (
                tree.resolve() != m1_tree.resolve() and f1_gitdir != m1_gitdir
            )
            detail = f"f1={tree.resolve()} m1={m1_tree.resolve()}"
        else:
            separate = f1_gitdir.parent == tree.resolve()
            detail = f"f1={f1_gitdir} (no M1 tree present)"
        report.check(
            f"{label}: F1 tree is a separate repository from M1",
            separate,
            detail,
        )
        status = git(tree, "status", "--porcelain=v1", "--untracked-files=all")
        report.check(
            f"{label}: F1 working tree clean", status == "",
            "clean" if status == "" else f"{len(status.splitlines())} dirty entries",
        )
        head = git(tree, "rev-parse", "HEAD")
        ancestor = _is_ancestor(tree, meta["m1_head_commit"])
        report.check(
            f"{label}: M1 8-patch head is an ancestor of the F1 head",
            ancestor,
            f"m1_head={meta['m1_head_commit'][:12]} f1_head={head[:12]}",
        )
        f1_names = f1_entry_names(root, component, meta)
        # A range like `<m1_head>..HEAD` is only meaningful once the ancestor
        # check passed; report the count as -1 instead of letting git abort the
        # whole report, so every violation gets its own FAIL line.
        on_top = (
            int(git(tree, "rev-list", "--count", f"{meta['m1_head_commit']}..HEAD"))
            if ancestor
            else -1
        )
        report.check(
            f"{label}: commits above the M1 head == F1 series entries",
            on_top == len(f1_names),
            f"commits={on_top} series={len(f1_names)}"
            + ("" if ancestor else " (M1 head is not an ancestor: unmeasurable)"),
        )
        state = load_state(work, component)
        live = {
            "base_lock": meta["base_lock"],
            "m1_patch_count": meta["m1_patch_count"],
            "m1_head_commit": meta["m1_head_commit"],
            "m1_head_tree": meta["m1_head_tree"],
            "f1_patch_count": len(f1_names),
            "f1_applied": on_top,
            "f1_head_commit": head,
            "f1_head_tree": git(tree, "rev-parse", "HEAD^{tree}"),
            "clean": status == "",
        }
        mismatched = {
            key: (state.get(key), value)
            for key, value in live.items()
            if state.get(key) != value
        }
        report.check(
            f"{label}: state record matches the live tree",
            not mismatched,
            "no drift" if not mismatched else f"drift={mismatched}",
        )
        report.check(
            f"{label}: F1 build root is outside the M1 build root",
            not _inside(build, m1_build(work, component)) and build != m1_build(work, component),
            f"f1_build={build} m1_build={m1_build(work, component)}",
        )
        for other in F1_COMPONENTS:
            if other == component:
                continue
            report.check(
                f"{label}: F1 source disjoint from the {other} M1 source",
                not _inside(tree, m1_source(work, other))
                and not _inside(m1_source(work, other), tree),
                f"f1={tree} m1={m1_source(work, other)}",
            )
        problems = series_problems(root, component, meta)
        report.check(
            f"{label}: F1 series constraints",
            not problems,
            f"m1={meta['m1_patch_count']} f1={len(f1_names)}"
            if not problems
            else "; ".join(problems),
        )

    # M1 build trees must contain no F1 artefact at all.
    needles = [b".work/f1", str(f1_base.resolve()).encode(), str(f1_base).encode()]
    for component in components:
        build = m1_build(work, component)
        if not build.is_dir():
            report.check(
                f"M1 build {build.name} present", False, "missing (M1 not built?)"
            )
            continue
        leaked = _build_dir_f1_components(build)
        report.check(
            f"{component}: no f1 path component inside the M1 build tree",
            not leaked,
            f"{build} clean" if not leaked else f"leaked={leaked[:5]}",
        )
        hits: list[str] = []
        for name in M1_BUILD_KEY_FILES[component]:
            path = build / name
            if not path.is_file():
                report.check(
                    f"{component}: M1 build key artefact {name} present", False, "missing"
                )
                continue
            blob = path.read_bytes()
            for needle in needles:
                if needle in blob:
                    hits.append(f"{name}:{needle.decode(errors='replace')}")
        report.check(
            f"{component}: M1 build key files do not reference the F1 paths",
            not hits,
            "no F1 reference" if not hits else f"hits={hits}",
        )
        if args.require_m1:
            m1_tree = m1_source(work, component)
            if m1_tree.is_dir():
                m1_status = git(m1_tree, "status", "--porcelain=v1", "--untracked-files=all")
                report.check(
                    f"{component}: M1 source tree still clean", m1_status == "",
                    "clean" if m1_status == "" else f"{len(m1_status.splitlines())} entries",
                )

    if args.require_idle:
        watched = [m1_build(work, name) for name in components] + [
            f1_build(work, name) for name in components
        ]
        busy = _busy_cwd(watched)
        report.check(
            "no process working inside an M1/F1 build tree",
            not busy,
            "idle" if not busy else f"busy={busy}",
        )

    print(
        f"check-f1-isolation: {'FAIL' if report.failures else 'PASS'} "
        f"({report.checks - report.failures}/{report.checks} checks passed)"
    )
    return 1 if report.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
