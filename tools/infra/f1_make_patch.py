#!/usr/bin/env python3
"""Append-only export of the F1 (``0009+``) patches (INFRA-108t).

``make_patch.py`` (M1) rewrites the whole series from the base lock, which is
exactly what F1 must never do to ``0001``-``0008``.  This tool is the
append-only counterpart:

* the range exported is ``f1.json:m1_head_commit..HEAD`` of the **F1** tree, so
  nothing below the M1 head can ever be re-emitted;
* the numbering continues the series (``--start-number``), so continuity is true
  by construction and ``[PATCH n/m]`` indices keep counting from 0009;
* the frozen M1 prefix of ``series`` is preserved byte-for-byte -- only new
  lines are appended;
* if any target patch file already exists (an M1 patch, or an F1 patch exported
  by an earlier run) the tool refuses **before writing anything**;
* consistency between the already-exported entries and the tree is proven by
  comparing each commit subject with the corresponding patch's ``Subject``
  header, so an exported series can never silently drift from the F1 tree.

Usage::

    f1_make_patch.py [--root ROOT] [--work WORK] [--component NAME]... [--dry-run]
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
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
    patch_number,
    patch_subject,
    patches_dir,
    series_path,
    series_problems,
    work_root,
)


def commit_subjects(repo: Path, since: str) -> list[str]:
    text = git(repo, "log", "--reverse", "--format=%s", f"{since}..HEAD")
    return text.splitlines() if text else []


def export(root: Path, work: Path, component: str, dry_run: bool) -> int:
    meta = load_f1_meta(root, component)
    problems = series_problems(root, component, meta)
    if problems:
        raise F1Error(
            f"{component}: refusing to export onto an invalid series: "
            + "; ".join(problems)
        )
    target = f1_source(work, component)
    if not target.is_dir() or not is_git_worktree(target):
        raise F1Error(
            f"missing F1 source {target}; run `make f1-prepare` first"
        )
    status = git(target, "status", "--porcelain=v1", "--untracked-files=all")
    if status:
        raise F1Error(
            f"F1 source {target} is dirty ({len(status.splitlines())} entries); "
            f"refusing to export patches from a modified tree"
        )
    m1_head = meta["m1_head_commit"]
    if subprocess.run(
        ["git", "-C", str(target), "merge-base", "--is-ancestor", m1_head, "HEAD"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode != 0:
        raise F1Error(
            f"F1 source {target}: M1 head {m1_head} is not an ancestor of HEAD "
            f"{git(target, 'rev-parse', 'HEAD')}"
        )
    revs = git(target, "rev-list", "--reverse", f"{m1_head}..HEAD")
    revs = revs.splitlines() if revs else []
    subjects = commit_subjects(target, m1_head)
    if len(revs) != len(subjects):
        raise F1Error("internal: rev-list/log disagree on the F1 commit count")
    series_file = series_path(root, component)
    directory = patches_dir(root, component)
    existing = f1_entry_names(root, component, meta)
    if len(existing) > len(revs):
        raise F1Error(
            f"series lists {len(existing)} F1 patch(es) but the F1 tree has only "
            f"{len(revs)} commit(s) above {m1_head[:12]}; refusing to export"
        )
    for index, name in enumerate(existing):
        want = subjects[index]
        got = patch_subject(directory / name)
        if want != got:
            raise F1Error(
                f"series entry {name!r} subject {got!r} does not match F1 commit "
                f"{revs[index][:12]} subject {want!r}"
            )
    if len(existing) == len(revs):
        print(
            f"f1-make-patch: {component} nothing to export "
            f"({len(revs)} F1 commit(s) already in the series)"
        )
        return 0
    start = (
        meta["f1_first_patch_number"]
        if not existing
        else patch_number(existing[-1]) + 1
    )
    if start <= meta["m1_patch_count"]:
        raise F1Error(
            f"computed start number {start} would overwrite the frozen M1 range "
            f"1..{meta['m1_patch_count']}"
        )
    since = m1_head if not existing else revs[len(existing) - 1]
    print(
        f"f1-make-patch: {component} exporting {len(revs) - len(existing)} patch(es) "
        f"as {start:04d}+ from {target} (since {since[:12]})"
    )
    with tempfile.TemporaryDirectory(prefix="f1-make-patch-") as scratch:
        result = subprocess.run(
            [
                "git", "-C", str(target), "format-patch", "--no-signature",
                "--start-number", str(start), "-o", scratch, f"{since}..HEAD",
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise F1Error(
                f"git format-patch failed (rc={result.returncode}): "
                f"{result.stderr.strip()}"
            )
        generated = sorted(
            Path(scratch).iterdir(), key=lambda p: patch_number(p.name) or 0
        )
        expected = list(range(start, start + len(generated)))
        actual = [patch_number(path.name) for path in generated]
        if actual != expected:
            raise F1Error(
                f"git format-patch produced numbers {actual}, expected {expected}"
            )
        for offset, path in enumerate(generated):
            destination = directory / path.name
            if destination.exists():
                raise F1Error(
                    f"refusing to overwrite existing patch {destination} "
                    f"(M1 0001-0008 and already-exported F1 patches are frozen)"
                )
            if dry_run:
                print(f"  would write {destination} (#{expected[offset]})")
                continue
            shutil.copyfile(path, destination)
            print(f"  wrote {destination.relative_to(root)} (#{expected[offset]})")
        if dry_run:
            return 0
    if not dry_run:
        with series_file.open("a", encoding="utf-8") as stream:
            for path in generated:
                stream.write(f"{path.name}\n")
    problems = series_problems(root, component, meta)
    if problems:
        raise F1Error(
            "series is invalid after the export (this is a tool bug): "
            + "; ".join(problems)
        )
    print(
        f"f1-make-patch: {component} series now has "
        f"{len(read_all(series_file))} entries ({len(existing)} -> "
        f"{len(existing) + len(generated)} F1)"
    )
    return 0


def read_all(path: Path) -> list[str]:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


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
        export(root, work, component, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
