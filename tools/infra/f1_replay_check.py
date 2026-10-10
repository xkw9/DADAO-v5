#!/usr/bin/env python3
"""Offline replay check for the M1 + F1 patch series (INFRA-108t).

Proves acceptance criterion 3 -- "an empty F1 (or a minimal ``0009+``) series
replays offline and the series is continuous" -- without touching the M1 or F1
worktrees at all.  For every component it builds a throw-away git tree in a
caller-supplied directory from the **local bare mirror only** and replays the
series with ``git am``:

1. clone ``.cache/<component>.git`` (a local path: no network), checkout the base
   lock, ``git am`` patches ``1..m1_patch_count``;
2. require the replayed HEAD tree to equal ``f1.json:m1_head_tree`` -- this is
   the M1 boundary proof that needs no ``.work/source`` tree, and it is what
   makes a stale or altered ``0008`` detectable;
3. require each replayed commit subject to match the corresponding patch's
   ``Subject`` header, index by index;
4. ``git am`` the ``0009+`` entries and require the final commit count to equal
   the number of F1 series entries and the tree to stay clean.

The replayed trees are created by this tool and deleted by the caller; nothing
under ``.work/source``, ``.work/build`` or ``.work/f1`` is read or written.

Usage::

    f1_replay_check.py --work-dir DIR [--root ROOT] [--component NAME]...
                       [--keep]
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from f1_common import (  # noqa: E402
    DEFAULT_ROOT,
    F1_COMPONENTS,
    F1Error,
    f1_entry_names,
    git,
    load_f1_meta,
    load_manifest,
    patch_number,
    patch_subject,
    patches_dir,
    read_series,
    series_path,
    series_problems,
    work_root,
)


def _run(args: list[str], what: str) -> None:
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        raise F1Error(
            f"{what} failed (rc={result.returncode}): {result.stderr.strip()}"
        )


def replay(root: Path, mirror: Path, component: str, dest: Path) -> dict:
    meta = load_f1_meta(root, component)
    problems = series_problems(root, component, meta)
    if problems:
        raise F1Error(f"{component}: invalid series: " + "; ".join(problems))
    directory = patches_dir(root, component)
    names = read_series(series_path(root, component))
    f1_names = f1_entry_names(root, component, meta)
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    _run(["git", "clone", "--no-checkout", str(mirror), str(dest)], "git clone")
    _run(
        ["git", "-C", str(dest), "checkout", "--detach", meta["base_lock"]],
        "git checkout base lock",
    )
    m1_names = names[: meta["m1_patch_count"]]
    for name in m1_names:
        _run(["git", "-C", str(dest), "am", "--quiet", str(directory / name)],
             f"git am {name}")
    m1_head = git(dest, "rev-parse", "HEAD")
    m1_tree = git(dest, "rev-parse", "HEAD^{tree}")
    if m1_tree != meta["m1_head_tree"]:
        raise F1Error(
            f"{component}: replaying {len(m1_names)} patch(es) from the mirror "
            f"produced tree {m1_tree}, but f1.json records m1_head_tree "
            f"{meta['m1_head_tree']}; the M1 boundary does not replay offline"
        )
    log = git(dest, "log", "--reverse", "--format=%s",
              f"{meta['base_lock']}..HEAD").splitlines()
    if len(log) != len(m1_names):
        raise F1Error(
            f"{component}: replay produced {len(log)} commits for "
            f"{len(m1_names)} patches"
        )
    for index, (name, subject) in enumerate(zip(m1_names, log), 1):
        want = patch_subject(directory / name)
        if want != subject:
            raise F1Error(
                f"{component}[{index}]: replayed subject {subject!r} != patch "
                f"{name} subject {want!r}"
            )
    for name in f1_names:
        _run(["git", "-C", str(dest), "am", "--quiet", str(directory / name)],
             f"git am {name}")
    final = git(dest, "rev-parse", "HEAD")
    final_tree = git(dest, "rev-parse", "HEAD^{tree}")
    # Count only the commits the series added on top of the base lock: the base
    # lock itself is an upstream commit and is already reachable from HEAD.
    total = int(git(dest, "rev-list", "--count", f"{meta['base_lock']}..HEAD"))
    status = git(dest, "status", "--porcelain=v1", "--untracked-files=all")
    if status:
        raise F1Error(f"{component}: replayed tree {dest} is dirty: {status[:200]}")
    expected_total = meta["m1_patch_count"] + len(f1_names)
    if total != expected_total:
        raise F1Error(
            f"{component}: replayed history has {total} commits, expected "
            f"{expected_total} ({meta['m1_patch_count']} M1 + {len(f1_names)} F1)"
        )
    # `git am` mints fresh commit ids (new committer timestamp), so the recorded
    # m1_head_commit is deliberately *not* expected to be reachable here.  The
    # F1 boundary is identified by position: the first f1_patch_count commits on
    # top of the base lock are the M1 series, everything after them is F1.
    revs = git(dest, "rev-list", "--reverse", f"{meta['base_lock']}..HEAD").split()
    f1_revs = revs[meta["m1_patch_count"]:]
    f1_log = git(dest, "log", "--reverse", "--format=%s",
                 f"{meta['base_lock']}..HEAD").splitlines()[meta["m1_patch_count"]:]
    for index, (name, subject) in enumerate(zip(f1_names, f1_log), 1):
        want = patch_subject(directory / name)
        if want != subject:
            raise F1Error(
                f"{component}[f1{index}]: replayed subject {subject!r} != patch "
                f"{name} subject {want!r}"
            )
    return {
        "component": component,
        "mirror": str(mirror),
        "m1_commits": len(m1_names),
        "f1_commits": len(f1_revs),
        "replayed_m1_head": m1_head,
        "replayed_m1_tree": m1_tree,
        "m1_boundary_tree_ok": True,
        "replayed_head": final,
        "replayed_head_tree": final_tree,
        "f1_revs": f1_revs,
        "total_commits": total,
        "f1_first_number": (
            patch_number(f1_names[0]) if f1_names else meta["f1_first_patch_number"]
        ),
        "clean": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=str(DEFAULT_ROOT))
    parser.add_argument("--work")
    parser.add_argument("--work-dir", required=True,
                        help="throw-away directory for the replayed trees")
    parser.add_argument("--component", action="append", choices=list(F1_COMPONENTS))
    parser.add_argument("--keep", action="store_true",
                        help="keep the replayed trees instead of deleting them")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    base = Path(args.work_dir).resolve()
    mirror_root = root / ".cache"
    base.mkdir(parents=True, exist_ok=True)

    created: list[Path] = []
    try:
        for component in args.component or F1_COMPONENTS:
            mirror = mirror_root / f"{component}.git"
            if not mirror.is_dir():
                raise F1Error(f"missing local bare mirror {mirror}")
            dest = base / component
            created.append(dest)
            facts = replay(root, mirror, component, dest)
            print(
                f"f1-replay: {component} OK mirror={mirror.name} "
                f"m1={facts['m1_commits']} f1={facts['f1_commits']} "
                f"first_f1={facts['f1_first_number']:04d} "
                f"replayed_tree={facts['replayed_m1_tree'][:12]} "
                f"total={facts['total_commits']} clean=True "
                f"m1_boundary_tree_ok=True"
            )
        print(f"f1-replay: PASS components={len(created)} work_dir={base}")
        return 0
    finally:
        if not args.keep:
            for dest in created:
                shutil.rmtree(dest, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
