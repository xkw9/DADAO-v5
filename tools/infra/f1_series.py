#!/usr/bin/env python3
"""F1 series (``0009+``) constraint checker (INFRA-108t).

The single authority for the series rules that ADR-1004 D6 requires:

* numbering is continuous from ``0001`` to the last entry;
* the first ``f1.json:m1_patch_count`` entries are *byte-name* identical to the
  frozen ``f1.json:m1_series_entries`` -- no rename, no reorder, no removal;
* F1 entries start exactly at ``f1_first_patch_number`` and are continuous
  (this is what rejects a skipped number such as jumping 0009 -> 0011);
* no duplicate entries, and every referenced patch file exists and is non-empty.

The empty F1 state (no ``0009`` yet) is a valid state, not a failure: the check
then only proves the frozen M1 prefix is intact.

``--list`` prints the resolved M1/F1 split instead of validating.

Usage::

    f1_series.py [--root ROOT] [--component NAME]... [--list]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from f1_common import (  # noqa: E402
    DEFAULT_ROOT,
    F1_COMPONENTS,
    f1_entry_names,
    load_f1_meta,
    read_series,
    series_path,
    series_problems,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=str(DEFAULT_ROOT))
    parser.add_argument(
        "--component", action="append", choices=list(F1_COMPONENTS)
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="print the M1/F1 split instead of validating",
    )
    args = parser.parse_args()
    root = Path(args.root).resolve()

    failed = False
    for component in args.component or F1_COMPONENTS:
        meta = load_f1_meta(root, component)
        path = series_path(root, component)
        if args.list:
            names = read_series(path)
            f1_names = f1_entry_names(root, component, meta)
            print(
                f"{component}: m1={len(names) - len(f1_names)} "
                f"f1={len(f1_names)} first_f1="
                f"{meta['f1_first_patch_number']:04d} path={path}"
            )
            for name in f1_names:
                print(f"  F1 {name}")
            continue
        problems = series_problems(root, component, meta)
        f1_names = f1_entry_names(root, component, meta)
        if problems:
            failed = True
            print(f"f1-series: FAIL {component} ({len(problems)} problem(s))")
            for problem in problems:
                print(f"  {problem}")
            continue
        print(
            f"f1-series: PASS {component} m1={meta['m1_patch_count']} "
            f"f1={len(f1_names)} first_f1={meta['f1_first_patch_number']:04d} "
            f"series={path.name}"
        )
    if args.list:
        return 0
    if failed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
