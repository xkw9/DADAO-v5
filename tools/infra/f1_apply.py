#!/usr/bin/env python3
"""Apply the F1 (``0009+``) patch series to an F1 source tree (INFRA-108t).

F1 patches are ordinary ``git am`` mails appended to the same series as M1, so
author/message fidelity is preserved exactly like ``apply_series.py`` does for
M1.  What differs is *where* they land and *what may not be touched*:

* the target is ``.work/f1/source/<component>``; the M1 tree is never a target;
* the tree must be clean, must contain ``f1.json:m1_head_commit`` as an
  ancestor, and the number of commits already above that head must match the
  number of F1 series entries already applied -- otherwise the tool refuses
  instead of guessing where to continue;
* ``0001``-``0008`` are never applied here (they are already in the F1 tree's
  history by construction), and a series violation is refused up front.

A failed ``git am`` is left in place on purpose: the operator decides whether to
run ``git am --abort``; this tool never resets anything.

Usage::

    f1_apply.py [--root ROOT] [--work WORK] [--component NAME]... [--dry-run]
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from f1_common import (  # noqa: E402
    DEFAULT_ROOT,
    F1_COMPONENTS,
    F1Error,
    f1_entry_names,
    f1_source,
    git,
    is_git_worktree,
    load_f1_meta,
    load_manifest,
    series_path,
    series_problems,
    work_root,
)


def apply(root: Path, work: Path, component: str, dry_run: bool) -> int:
    meta = load_f1_meta(root, component)
    problems = series_problems(root, component, meta)
    if problems:
        raise F1Error(
            f"{component}: refusing to apply an invalid F1 series: "
            + "; ".join(problems)
        )
    target = f1_source(work, component)
    if not target.is_dir() or not is_git_worktree(target):
        raise F1Error(
            f"missing F1 source {target}; run `make f1-prepare` before "
            f"`make f1-apply-series`"
        )
    status = git(target, "status", "--porcelain=v1", "--untracked-files=all")
    if status:
        raise F1Error(
            f"F1 source {target} is dirty ({len(status.splitlines())} entries); "
            f"refusing to apply patches onto a modified tree"
        )
    ancestor = subprocess.run(
        ["git", "-C", str(target), "merge-base", "--is-ancestor",
         meta["m1_head_commit"], "HEAD"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode == 0
    if not ancestor:
        raise F1Error(
            f"F1 source {target}: M1 head {meta['m1_head_commit']} is not an "
            f"ancestor of HEAD {git(target, 'rev-parse', 'HEAD')}"
        )
    applied = int(git(target, "rev-list", "--count", f"{meta['m1_head_commit']}..HEAD"))
    names = f1_entry_names(root, component, meta)
    if applied > len(names):
        raise F1Error(
            f"F1 source {target} already has {applied} commit(s) above the M1 "
            f"head but the series only lists {len(names)} F1 patch(es); the "
            f"series must be exported with f1_make_patch.py first"
        )
    if applied == len(names):
        print(
            f"f1-apply: {component} nothing to do (all {len(names)} F1 patch(es) "
            f"already applied)"
        )
        return 0
    pending = names[applied:]
    print(
        f"f1-apply: {component} applying {len(pending)} patch(es) "
        f"{pending[0]}..{pending[-1]} -> {target}"
    )
    if dry_run:
        for name in pending:
            print(f"  would git am {series_path(root, component).parent / name}")
        return 0
    ident = git(target, "var", "GIT_COMMITTER_IDENT")
    if not ident:
        raise F1Error(
            f"no committer identity available for `git am` in {target}; refusing "
            f"to fabricate patch authorship"
        )
    for name in pending:
        patch = series_path(root, component).parent / name
        result = subprocess.run(
            ["git", "-C", str(target), "am", str(patch)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(result.stdout, end="")
            print(result.stderr, end="", file=sys.stderr)
            raise F1Error(
                f"git am {patch} failed (rc={result.returncode}); the tree is left "
                f"in its am state on purpose -- inspect it and run "
                f"`git -C {target} am --abort` deliberately if you want to retry"
            )
        print(f"  applied {name}")
    final = int(git(target, "rev-list", "--count", f"{meta['m1_head_commit']}..HEAD"))
    if final != len(names):
        raise F1Error(
            f"after applying, {target} has {final} commit(s) above the M1 head "
            f"but the series lists {len(names)}"
        )
    print(f"f1-apply: {component} head={git(target, 'rev-parse', 'HEAD')[:12]} PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=str(DEFAULT_ROOT))
    parser.add_argument("--work")
    parser.add_argument("--component", action="append", choices=list(F1_COMPONENTS))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    work = (
        Path(args.work).resolve() if args.work else work_root(root, load_manifest(root))
    )
    for component in args.component or F1_COMPONENTS:
        apply(root, work, component, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
