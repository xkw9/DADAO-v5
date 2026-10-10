#!/usr/bin/env python3
"""M1 baseline protection checker for the F1 phase (INFRA-108t).

Records and compares the *frozen M1 baseline* so an F1 action can be proven
byte-identical before/after:

* M1 source trees ``.work/source/{llvm-project,qemu}``: HEAD commit, HEAD tree,
  commit count, shallow flag, origin URL, full ``git ls-files -s`` digest (every
  tracked path+mode+blob id) and the porcelain status (must stay empty).
* M1 build trees ``.work/build/{llvm,qemu}``: a full ``(type, path, size)``
  listing digest for *every* entry -- catches added/removed/resized artefacts --
  plus sha256 of a declared set of key artefacts.
* ``components/*/patches/0001``-``0008``: sha256 of each patch file, the sha256
  of the whole ``series`` file **and** of its frozen M1 prefix (so appending
  ``0009+`` later is allowed while rewriting ``0001``-``0008`` is not).
* The M1 747-case test baseline inputs (``tests/vectors``, ``contracts``,
  ``tools/testcases``): per-file sha256.

Usage::

    check_f1_baseline.py snapshot --out FILE
    check_f1_baseline.py compare --before FILE [--after FILE]

``compare`` recomputes from the live tree unless ``--after`` is given.  Any
difference in any recorded field is a hard failure (exit 1) with the offending
field printed, so an altered ``0008``, a rebuilt M1 tree or an edited vector
file cannot pass silently.  ``__pycache__`` and ``*.pyc`` are excluded from the
input inventory on purpose: they are interpreter caches, not baseline inputs.
"""
from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parent))

from f1_common import (  # noqa: E402
    DEFAULT_ROOT,
    F1_COMPONENTS,
    F1_META_NAME,
    BUILD_DIR,
    F1Error,
    git,
    is_git_worktree,
    load_manifest,
    load_f1_meta,
    m1_build,
    m1_source,
    patches_dir,
    series_prefix_text,
    sha256_file,
    sha256_text,
    work_root,
)

BASELINE_FORMAT = 1

# Key M1 build artefacts.  Hashing every byte of a 10 GiB build tree is neither
# cheap nor needed: the full (type, path, size) listing digest already detects
# additions/removals/resizes, and these files are the ones whose *content* the
# M1 baseline actually pins (tools, key DADAO library, configuration).
M1_BUILD_KEY_FILES = {
    "llvm-project": (
        "CMakeCache.txt",
        "build.ninja",
        "bin/llvm-mc",
        "bin/llvm-lit",
        "bin/FileCheck",
        "lib/libLLVMDADAOCodeGen.a",
    ),
    "qemu": (
        "Makefile",
        "Makefile.mtest",
        "Makefile.prereqs",
        "config.status",
        "config-host.mak",
        "qemu-version.h",
        "qemu-system-dadao",
    ),
}

# M1 747-case baseline inputs.
INPUT_DIRS = ("tests/vectors", "contracts", "tools/testcases")
INPUT_SKIP_DIRS = {"__pycache__"}
INPUT_SKIP_SUFFIX = (".pyc", ".pyo")


def _listing_digest(root: Path) -> tuple[str, int]:
    """sha256 over every entry's (type, relative path, size or link target)."""
    rows: list[str] = []
    stack: list[tuple[Path, PurePosixPath]] = [(root, PurePosixPath("."))]
    while stack:
        directory, rel = stack.pop()
        for entry in sorted(os.scandir(directory), key=lambda e: os.fsencode(e.name)):
            child_rel = rel / entry.name
            mode = entry.stat(follow_symlinks=False).st_mode
            if stat.S_ISDIR(mode):
                rows.append(f"D\t{child_rel.as_posix()}")
                stack.append((Path(entry.path), child_rel))
            elif stat.S_ISREG(mode):
                rows.append(
                    f"F\t{child_rel.as_posix()}\t{entry.stat(follow_symlinks=False).st_size}"
                )
            elif stat.S_ISLNK(mode):
                rows.append(f"L\t{child_rel.as_posix()}\t{os.readlink(entry.path)}")
            else:
                raise F1Error(f"unsupported entry type under {root}: {child_rel}")
    files = sum(1 for row in rows if row.startswith("F\t"))
    return sha256_text("\n".join(sorted(rows)) + "\n"), files


def _source_record(repo: Path) -> dict:
    if not repo.is_dir() or not is_git_worktree(repo):
        raise F1Error(
            f"M1 source {repo} is missing or not a git worktree; the baseline "
            f"cannot be recorded or compared"
        )
    status = git(repo, "status", "--porcelain=v1", "--untracked-files=all")
    return {
        "path": str(repo),
        "head": git(repo, "rev-parse", "HEAD"),
        "head_tree": git(repo, "rev-parse", "HEAD^{tree}"),
        "commit_count": int(git(repo, "rev-list", "--count", "HEAD")),
        "shallow": git(repo, "rev-parse", "--is-shallow-repository"),
        "origin_url": git(repo, "config", "--get", "remote.origin.url"),
        "index_sha256": sha256_text(git(repo, "ls-files", "-s")),
        "status": status,
    }


def _build_record(build: Path, component: str) -> dict:
    if not build.is_dir():
        raise F1Error(f"M1 build {build} is missing; the baseline cannot be compared")
    digest, files = _listing_digest(build)
    keys: dict[str, str] = {}
    for name in M1_BUILD_KEY_FILES[component]:
        path = build / name
        if not path.is_file():
            raise F1Error(
                f"M1 build key artefact {path} is missing; refusing to record a "
                f"baseline that silently drops coverage"
            )
        keys[name] = sha256_file(path)
    return {
        "path": str(build),
        "file_count": files,
        "listing_sha256": digest,
        "key_files": keys,
    }


def _patch_record(root: Path, component: str) -> dict:
    directory = patches_dir(root, component)
    meta_path = directory / F1_META_NAME
    if not meta_path.is_file():
        raise F1Error(f"missing F1 boundary metadata {meta_path}")
    meta = load_f1_meta(root, component)
    series = directory / "series"
    entries = {
        line.strip()
        for line in series.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    digests: dict[str, str] = {}
    for name in sorted(entries):
        path = directory / name
        if not path.is_file():
            raise F1Error(f"series references missing patch {path}")
        digests[name] = sha256_file(path)
    count = meta["m1_patch_count"]
    return {
        "series_sha256": sha256_file(series),
        "series_m1_prefix_sha256": sha256_text(series_prefix_text(series, count)),
        "series_entry_count": len(entries),
        "patch_sha256": digests,
        "m1_head_commit": meta["m1_head_commit"],
        "m1_head_tree": meta["m1_head_tree"],
        "base_lock": meta["base_lock"],
    }


def _input_record(root: Path) -> dict:
    digests: dict[str, str] = {}
    for relative in INPUT_DIRS:
        base = root / relative
        if not base.is_dir():
            raise F1Error(f"baseline input directory {base} is missing")
        for directory, subdirs, files in os.walk(base):
            subdirs[:] = sorted(d for d in subdirs if d not in INPUT_SKIP_DIRS)
            for name in sorted(files):
                if name.endswith(INPUT_SKIP_SUFFIX):
                    continue
                path = Path(directory) / name
                key = str(path.relative_to(root))
                digests[key] = sha256_file(path)
    if not digests:
        raise F1Error("baseline input inventory is empty")
    return {"file_count": len(digests), "file_sha256": digests}


def snapshot(root: Path) -> dict:
    manifest = load_manifest(root)
    work = work_root(root, manifest)
    return {
        "format": BASELINE_FORMAT,
        "work_root": str(work),
        "m1_source": {
            name: _source_record(m1_source(work, name)) for name in F1_COMPONENTS
        },
        "m1_build": {
            name: _build_record(m1_build(work, name), name) for name in F1_COMPONENTS
        },
        "patches": {
            name: _patch_record(root, name) for name in F1_COMPONENTS
        },
        "baseline_inputs": _input_record(root),
    }


def _walk(prefix: str, before: object, after: object, out: list[str]) -> None:
    if isinstance(before, dict) and isinstance(after, dict):
        for key in sorted(set(before) | set(after)):
            _walk(f"{prefix}.{key}" if prefix else str(key),
                  before.get(key, "<absent>"), after.get(key, "<absent>"), out)
        return
    if before != after:
        out.append(f"{prefix}: before={before!r} after={after!r}")


def compare(before: dict, after: dict) -> list[str]:
    differences: list[str] = []
    if before.get("format") != after.get("format"):
        differences.append(
            f"format: before={before.get('format')!r} after={after.get('format')!r}"
        )
    for section in ("m1_source", "m1_build", "patches", "baseline_inputs"):
        _walk(section, before.get(section, {}), after.get(section, {}), differences)
    return differences


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=str(DEFAULT_ROOT))
    sub = parser.add_subparsers(dest="command", required=True)
    take = sub.add_parser("snapshot", help="record the frozen M1 baseline")
    take.add_argument("--out", required=True)
    diff = sub.add_parser("compare", help="compare against a recorded baseline")
    diff.add_argument("--before", required=True)
    diff.add_argument(
        "--after",
        help="compare two recorded files instead of the live tree (self-test aid)",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if args.command == "snapshot":
        record = snapshot(root)
        Path(args.out).write_text(
            json.dumps(record, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(
            "check-f1-baseline: snapshot {components} components, "
            "{inputs} baseline input files -> {out}".format(
                components=len(F1_COMPONENTS),
                inputs=record["baseline_inputs"]["file_count"],
                out=args.out,
            )
        )
        for name in F1_COMPONENTS:
            print(
                f"  {name}: m1_head={record['m1_source'][name]['head'][:12]} "
                f"tree={record['m1_source'][name]['head_tree'][:12]} "
                f"status_clean={not record['m1_source'][name]['status']} "
                f"build_files={record['m1_build'][name]['file_count']} "
                f"patches={record['patches'][name]['series_entry_count']}"
            )
        return 0

    before = json.loads(Path(args.before).read_text(encoding="utf-8"))
    after = (
        json.loads(Path(args.after).read_text(encoding="utf-8"))
        if args.after
        else snapshot(root)
    )
    differences = compare(before, after)
    if differences:
        print(
            f"check-f1-baseline: FAIL -- {len(differences)} baseline difference(s):",
            file=sys.stderr,
        )
        for line in differences:
            print(f"  {line}", file=sys.stderr)
        return 1
    print(f"check-f1-baseline: PASS ({args.before} identical to current tree)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
