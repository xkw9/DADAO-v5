#!/usr/bin/env python3
"""Prove the default M1 entrypoints are semantically unchanged (INFRA-108t).

Acceptance criterion 4 says the F1 work must not change what the M1
``make build-*``/``make check``/``make prepare`` entrypoints *mean*.  The check
is differential and mechanical -- no frozen copy of the recipes, no prose:

1. **Structural superset** -- every line of ``git show HEAD:Makefile`` still
   occurs in the working ``Makefile`` with at least the same multiplicity, so no
   M1 definition, variable, recipe or target line was removed or rewritten.
   (Adding to the existing ``.PHONY`` line would break this, which is why the F1
   targets live on their own ``.PHONY`` line.)
2. **Identical recipe expansion** -- ``make -n`` is run for every M1 target in two
   throw-away trees, one holding the HEAD ``Makefile`` and one holding the
   working ``Makefile``, and the two outputs (plus exit codes) must be
   byte-identical after masking the two temporary ``$(CURDIR)`` values.  A
   changed flag, a dropped ``-j``, a reworded echo or a new prerequisite in any
   M1 target changes this output and fails the check.
3. **No F1 leakage** -- the working tree's ``make -n`` expansion of the M1
   targets must not mention any F1 script, target or variable, so F1 can never
   change (or be dragged into) an M1 entrypoint.

Usage::

    check_m1_entrypoints.py [--root ROOT] [--keep]
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from f1_common import DEFAULT_ROOT  # noqa: E402

M1_TARGETS = (
    "help",
    "manifest-check",
    "doctor",
    "status",
    "fetch",
    "fetch-refs",
    "apply-series",
    "prepare",
    "build-mc",
    "build-qemu",
    "build-gem5",
    "docker-image",
    "docker-shell",
    "clean-work",
    "validate-vectors",
    "check",
    "check-spec-drift",
    "check-spec-refs",
)

# Directories `make -n` needs to expand the M1 recipes (component-enabled reads
# the lock file, validate-vectors has `contracts/opcodes.yaml` as a prerequisite).
NEEDED_DIRS = ("manifests", "contracts")

F1_MARKERS = ("f1_", "f1-", "$(F1_", "F1_WORK", "F1_SRC_RAW", "F1_BUILD_RAW")


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


def head_makefile(root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), "show", "HEAD:Makefile"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise SystemExit(
            f"check-m1-entrypoints: cannot read HEAD:Makefile: {result.stderr.strip()}"
        )
    return result.stdout


def expand(tree: Path, target: str) -> tuple[int, str]:
    env = dict(os.environ)
    # `docker-shell`'s recipe uses $(PWD), which make takes from the environment;
    # pin it to the tree so both sides expand to a maskable absolute path.
    env["PWD"] = str(tree.resolve())
    result = subprocess.run(
        ["make", "-n", "--no-print-directory", "-f", "Makefile", target],
        cwd=tree,
        capture_output=True,
        text=True,
        env=env,
    )
    output = result.stdout + result.stderr
    return result.returncode, output.replace(str(tree.resolve()), "<CURDIR>")


def prepare_tree(source: Path, makefile_text: str, dest: Path) -> Path:
    dest.mkdir(parents=True)
    (dest / "Makefile").write_text(makefile_text, encoding="utf-8")
    for name in NEEDED_DIRS:
        origin = source / name
        if origin.is_dir():
            shutil.copytree(origin, dest / name)
    # `build-qemu`'s recipe recurses into `make -C .work/build/qemu`.  A line
    # containing $(MAKE) is executed even under -n, so give the sub-make a real
    # (empty) tree to look at; otherwise both sides would stop at the same
    # unrelated "No such file or directory" and the later targets would never be
    # expanded at all.
    sub = dest / ".work/build/qemu"
    sub.mkdir(parents=True, exist_ok=True)
    (sub / "Makefile").write_text("all:\n\t@:\n", encoding="utf-8")
    return dest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=str(DEFAULT_ROOT))
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    report = Report()

    head_text = head_makefile(root)
    work_text = (root / "Makefile").read_text(encoding="utf-8")

    head_lines = Counter(head_text.splitlines())
    work_lines = Counter(work_text.splitlines())
    missing = {
        line: count - work_lines.get(line, 0)
        for line, count in head_lines.items()
        if work_lines.get(line, 0) < count
    }
    report.check(
        "every HEAD Makefile line is still present in the working Makefile",
        not missing,
        "pure addition"
        if not missing
        else f"{len(missing)} line(s) removed/rewritten: "
        + repr(sorted(missing)[:3]),
    )
    added = sum(work_lines.values()) - sum(head_lines.values())
    print(f"  Makefile: HEAD {len(head_text.splitlines())} lines, "
          f"working {len(work_text.splitlines())} lines (+{added})")

    holder = Path(tempfile.mkdtemp(prefix="check-m1-entrypoints-"))
    try:
        head_tree = prepare_tree(root, head_text, holder / "head")
        work_tree = prepare_tree(root, work_text, holder / "work")
        per_target: dict[str, str] = {}
        for target in M1_TARGETS:
            head_rc, head_out = expand(head_tree, target)
            work_rc, work_out = expand(work_tree, target)
            if head_rc != work_rc:
                per_target[target] = f"exit code HEAD={head_rc} working={work_rc}"
            elif head_out != work_out:
                per_target[target] = _first_difference(head_out, work_out)
        report.check(
            f"`make -n` expansion + exit code identical for all {len(M1_TARGETS)} "
            f"M1 targets",
            not per_target,
            "identical" if not per_target
            else "; ".join(f"{k}: {v}" for k, v in sorted(per_target.items())),
        )
        work_out = "".join(expand(work_tree, target)[1] for target in M1_TARGETS)
        leaked = sorted(
            {
                line.strip()
                for line in work_out.splitlines()
                if any(marker in line for marker in F1_MARKERS)
            }
        )
        report.check(
            "no F1 target/script/variable appears in any M1 entrypoint",
            not leaked,
            "clean" if not leaked else f"leaked={leaked[:3]}",
        )
        # Prove the comparison is not vacuous: the M1 recipes really did expand.
        head_total = sum(
            len(expand(head_tree, target)[1].splitlines()) for target in M1_TARGETS
        )
        report.check(
            "M1 recipes really expanded (non-empty reference expansion)",
            head_total > 0,
            f"{head_total} expansion lines across {len(M1_TARGETS)} targets",
        )
    finally:
        if not args.keep:
            shutil.rmtree(holder, ignore_errors=True)
        else:
            print(f"  kept temporary trees in {holder}")

    print(
        f"check-m1-entrypoints: {'FAIL' if report.failures else 'PASS'} "
        f"({report.checks - report.failures}/{report.checks} checks passed)"
    )
    return 1 if report.failures else 0


def _first_difference(left: str, right: str) -> str:
    for index, (a, b) in enumerate(zip(left.splitlines(), right.splitlines()), 1):
        if a != b:
            return f"first difference at line {index}: HEAD={a!r} working={b!r}"
    return (
        f"line count differs: HEAD={len(left.splitlines())} "
        f"working={len(right.splitlines())}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
