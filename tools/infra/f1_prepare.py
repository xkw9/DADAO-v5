#!/usr/bin/env python3
"""Create the F1 isolated source trees at the M1 8-patch head (INFRA-108t).

F1 never re-fetches and never re-applies M1: it clones the *M1 worktree* (a
local path, so no network) and detaches at the recorded M1 head commit, so the
F1 tree's history contains the M1 base lock plus the M1 patches and any future
``0009+`` F1 patches.

Fail-closed rules (all of them leave the tree untouched):

* the M1 source tree must exist, be clean, sit exactly on
  ``f1.json:m1_head_commit`` and carry exactly ``m1_patch_count`` commits above
  the base lock;
* the F1 layout must be *canonical*: ``<work>/f1``, the component source tree
  and the component build root must resolve to exactly ``<work>/f1``,
  ``<work>/f1/source/<component>`` and ``<work>/f1/build/<build-dir>``.  This is
  checked before anything is created, cloned, checked out or recorded, so a
  symlinked (or otherwise out-of-root) F1 source/build path is refused instead
  of being cloned into, verified or state-recorded in place;
* an F1 source path that already exists but is not a git worktree is refused;
* an F1 source tree that already exists is only *verified* (head, ancestry,
  clean, origin, and: the commits above the M1 head must not outnumber the F1
  series entries and must match those entries' ``Subject`` headers one by one) and
  is then left alone -- never reset, re-checked-out or deleted;
* a tree *created* by this tool is required to sit exactly on the M1 head (zero
  F1 commits); the already-exported ``0009+`` entries are applied afterwards by
  ``f1_apply.py``, not by this tool;
* the recorded ``f1.json:m1_head_tree`` must equal the M1 HEAD tree, so stale
  boundary metadata is caught instead of silently producing a wrong F1 tree.

After a successful creation (or verification) a state record is written to
``.work/f1/state/<component>.json`` holding the base lock, the 8-patch head
commit/tree, the F1 head commit/tree, the F1 patch count (series side) and the
number of F1 commits actually applied, plus the clean status -- the data
``check_f1_isolation.py`` re-verifies later.

Usage::

    f1_prepare.py [--root ROOT] [--work WORK] [--component NAME]...
    f1_prepare.py ... --dry-run
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
    f1_layout_failures,
    f1_root,
    f1_source,
    git,
    is_git_worktree,
    load_f1_meta,
    load_manifest,
    m1_source,
    patch_subject,
    patches_dir,
    read_series,
    series_path,
    work_root,
    write_state,
)


def _is_ancestor(repo: Path, ancestor: str) -> bool:
    return subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", ancestor, "HEAD"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode == 0


def _require_m1_source(root: Path, work: Path, component: str, meta: dict) -> Path:
    """Validate the M1 tree and return its absolute path."""
    source = m1_source(work, component)
    if not source.is_dir() or not is_git_worktree(source):
        raise F1Error(
            f"M1 source {source} is missing or not a git worktree; F1 must be "
            f"created from the M1 8-patch head, so there is nothing to branch from"
        )
    status = git(source, "status", "--porcelain=v1", "--untracked-files=all")
    if status:
        raise F1Error(
            f"M1 source {source} is dirty ({len(status.splitlines())} entries); "
            f"refusing to derive an F1 tree from a modified M1 baseline"
        )
    head = git(source, "rev-parse", "HEAD")
    if head != meta["m1_head_commit"]:
        raise F1Error(
            f"M1 source {source} HEAD is {head}, but f1.json records "
            f"m1_head_commit={meta['m1_head_commit']}; refusing to create an F1 "
            f"tree from an unexpected baseline"
        )
    tree = git(source, "rev-parse", "HEAD^{tree}")
    if tree != meta["m1_head_tree"]:
        raise F1Error(
            f"M1 source {source} HEAD tree is {tree}, but f1.json records "
            f"m1_head_tree={meta['m1_head_tree']}"
        )
    if not _is_ancestor(source, meta["base_lock"]):
        raise F1Error(
            f"M1 source {source}: base lock {meta['base_lock']} is not an "
            f"ancestor of HEAD"
        )
    count = int(git(source, "rev-list", "--count", f"{meta['base_lock']}..HEAD"))
    if count != meta["m1_patch_count"]:
        raise F1Error(
            f"M1 source {source}: {count} commits above the base lock, but "
            f"f1.json records m1_patch_count={meta['m1_patch_count']}"
        )
    return source.resolve()


def _create(source: Path, target: Path, head: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["git", "clone", "--no-checkout", str(source), str(target)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise F1Error(
            f"git clone --no-checkout {source} -> {target} failed "
            f"(rc={result.returncode}): {result.stderr.strip()}"
        )
    note = (result.stderr.strip().splitlines() or [""])[-1]
    if note:
        print(f"  git clone: {note}")
    checkout = subprocess.run(
        ["git", "-C", str(target), "checkout", "--detach", head],
        capture_output=True,
        text=True,
    )
    if checkout.returncode != 0:
        raise F1Error(
            f"git checkout --detach {head} in {target} failed "
            f"(rc={checkout.returncode}): {checkout.stderr.strip()}"
        )


def _verify(
    target: Path,
    meta: dict,
    origin: Path,
    *,
    created: bool,
    f1_names: list[str],
    directory: Path,
) -> dict:
    if not target.is_dir() or not is_git_worktree(target):
        raise F1Error(f"F1 source {target} is not a git worktree")
    if target.resolve() == origin:
        raise F1Error(
            f"F1 source {target} resolves to the M1 tree {origin}; the F1 tree "
            f"must be a separate worktree"
        )
    status = git(target, "status", "--porcelain=v1", "--untracked-files=all")
    if status:
        raise F1Error(
            f"F1 source {target} is dirty ({len(status.splitlines())} entries): "
            f"{status.splitlines()[:5]}"
        )
    head = git(target, "rev-parse", "HEAD")
    url = git(target, "config", "--get", "remote.origin.url")
    if Path(url).resolve() != origin:
        raise F1Error(
            f"F1 source {target} origin is {url}, expected the M1 tree {origin}"
        )
    ancestor = _is_ancestor(target, meta["m1_head_commit"])
    if not ancestor:
        raise F1Error(
            f"F1 source {target}: M1 head {meta['m1_head_commit']} is not an "
            f"ancestor of HEAD {head}"
        )
    on_top = int(git(target, "rev-list", "--count", f"{meta['m1_head_commit']}..HEAD"))
    if created:
        # A tree created now sits exactly on the M1 head, so it has no F1 commit
        # yet -- `make f1-apply-series` is what applies the already-exported 0009+.
        if on_top != 0:
            raise F1Error(
                f"F1 source {target} was created with {on_top} commit(s) above "
                f"{meta['m1_head_commit'][:12]}; expected 0"
            )
    else:
        if on_top > len(f1_names):
            raise F1Error(
                f"F1 source {target}: {on_top} commit(s) above the M1 head, but "
                f"the F1 series has only {len(f1_names)} entr(ies)"
            )
        subjects = git(
            target, "log", "--reverse", "--format=%s",
            f"{meta['m1_head_commit']}..HEAD",
        ).splitlines()
        for index, name in enumerate(f1_names[:on_top]):
            want = patch_subject(directory / name)
            if subjects[index] != want:
                raise F1Error(
                    f"F1 source {target}: commit {index + 1} above the M1 head has "
                    f"subject {subjects[index]!r}, but the series entry {name!r} "
                    f"has subject {want!r}; the exported series has drifted from "
                    f"the tree"
                )
    return {
        "head": head,
        "head_tree": git(target, "rev-parse", "HEAD^{tree}"),
        "origin_url": url,
        "shallow": git(target, "rev-parse", "--is-shallow-repository"),
        "commit_count": int(git(target, "rev-list", "--count", "HEAD")),
        "f1_applied": on_top,
    }


def prepare(root: Path, work: Path, component: str, dry_run: bool) -> int:
    # Canonical containment first, before *any* mutation (no mkdir, no clone, no
    # checkout, no state record): an F1 source/build path that is not exactly
    # <work>/f1/{source/<component>,build/<build-dir>} after symlink resolution
    # is an escaped layout, and an escaped layout is refused, never repaired.
    escaped = f1_layout_failures(work, component)
    if escaped:
        raise F1Error(
            f"refusing to touch the F1 layout of {component}: it is not at its "
            f"canonical F1 location, so F1 would be operating outside "
            f"{f1_root(work)} -- " + "; ".join(escaped)
        )

    meta = load_f1_meta(root, component)
    origin = _require_m1_source(root, work, component, meta)
    target = f1_source(work, component)

    f1_root_path = f1_root(work)
    f1_root_path.mkdir(parents=True, exist_ok=True)

    f1_names = [
        name
        for name in _series_names(root, component)
        if int(name[:4]) >= meta["f1_first_patch_number"]
    ]
    print(
        f"f1-prepare: {component} base_lock={meta['base_lock'][:12]} "
        f"m1_head={meta['m1_head_commit'][:12]} "
        f"m1_tree={meta['m1_head_tree'][:12]} f1_series={len(f1_names)}"
    )
    if target.exists() and not is_git_worktree(target):
        raise F1Error(
            f"{target} exists but is not a git worktree; refusing to touch it"
        )
    if target.exists():
        action = "verify existing"
    else:
        action = "create"
        if dry_run:
            print(f"  would {action} {target} from {origin}")
            return 0
        _create(origin, target, meta["m1_head_commit"])

    facts = _verify(
        target,
        meta,
        origin,
        created=(action == "create"),
        f1_names=f1_names,
        directory=patches_dir(root, component),
    )
    record = {
        "format": 1,
        "component": component,
        "created_from": str(origin),
        "base_lock": meta["base_lock"],
        "m1_patch_count": meta["m1_patch_count"],
        "m1_head_commit": meta["m1_head_commit"],
        "m1_head_tree": meta["m1_head_tree"],
        "f1_patch_count": len(f1_names),
        "f1_applied": facts["f1_applied"],
        "f1_pending": len(f1_names) - facts["f1_applied"],
        "f1_head_commit": facts["head"],
        "f1_head_tree": facts["head_tree"],
        "f1_source": str(target),
        "f1_build": str(work / "f1" / "build"),
        "commit_count": facts["commit_count"],
        "shallow": facts["shallow"],
        "clean": True,
    }
    path = write_state(work, component, record)
    print(
        f"  {action}: {target} head={facts['head'][:12]} "
        f"tree={facts['head_tree'][:12]} shallow={facts['shallow']} "
        f"commits={facts['commit_count']} "
        f"f1_applied={facts['f1_applied']}/{len(f1_names)} clean=True"
    )
    if len(f1_names) - facts["f1_applied"] > 0:
        print(
            f"  pending: {len(f1_names) - facts['f1_applied']} exported F1 "
            f"patch(es) are not applied yet -- run `make f1-apply-series`"
        )
    print(f"  state: {path}")
    return 0


def _series_names(root: Path, component: str) -> list[str]:
    return read_series(series_path(root, component))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=str(DEFAULT_ROOT))
    parser.add_argument("--work", help="override the disposable work root")
    parser.add_argument(
        "--component",
        action="append",
        choices=list(F1_COMPONENTS),
        help="restrict to one component (default: all F1 components)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report what would be created without creating anything",
    )
    args = parser.parse_args()
    root = Path(args.root).resolve()
    work = Path(args.work).resolve() if args.work else work_root(root, load_manifest(root))
    for component in args.component or F1_COMPONENTS:
        prepare(root, work, component, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
