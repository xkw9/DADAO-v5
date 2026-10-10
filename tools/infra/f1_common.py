#!/usr/bin/env python3
"""Shared layout, manifest and series helpers for the F1 phase (INFRA-108t).

F1 is an *append-only* second phase on top of the M1 reproducible baseline
(ADR-1004 D6/D9).  The invariants this module encodes, and that every other
``f1_*``/``check_f1_*`` tool relies on, are:

* M1 stays exactly where it is: ``<work>/source/<component>`` and
  ``<work>/build/<build-dir>``, produced by ``make prepare`` / ``make build-*``.
  F1 never writes there.
* F1 lives under ``<work>/f1/source/<component>`` and ``<work>/f1/build/<dir>``
  and is created *from* the recorded M1 8-patch head, never from the base lock
  and never from ``.cache`` (``.cache`` only holds the upstream base commit).
* The M1 boundary is frozen in ``components/<component>/patches/f1.json``: base
  lock, patch count, M1 head commit **and M1 head tree**, plus the frozen M1
  series entry names.  ``f1_prepare.py``/``f1_apply.py``/``f1_make_patch.py``/
  ``check_f1_isolation.py``/``check_f1_baseline.py`` all read it, so there is a
  single source of truth instead of each tool re-deriving the boundary.
* F1 patches are ``0009+`` only, appended to the *same* ``series`` file.  The
  M1 prefix of that file is frozen: appending is allowed, rewriting or
  reordering ``0001``-``0008`` is not.
* The F1 layout is checked *canonically* (``f1_layout_failures``): the F1 root
  and every component's source tree / build root must land exactly on
  ``<work>/f1``, ``<work>/f1/source/<component>`` and
  ``<work>/f1/build/<build-dir>`` after symlink resolution.  A path that only
  looks inside because a symlink points elsewhere is an escape and is refused
  before any tool touches the tree.

Every helper here is fail-closed: a missing or inconsistent input raises
``SystemExit`` with an explicit message instead of guessing.
"""
from __future__ import annotations

import email.policy
import hashlib
import json
import os
import re
import subprocess
import tomllib
from email.parser import BytesParser
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[2]

# Directory name of the F1 phase inside the disposable work root.  Everything
# F1 owns lives under ``<work>/<F1_DIRNAME>/``; nothing else may create that
# subtree, and F1 code must never write outside it (plus its own log dir).
F1_DIRNAME = "f1"

# Per-component machine-readable F1 boundary, committed next to the series.
F1_META_NAME = "f1.json"
F1_META_FORMAT = 1

# State records written by f1_prepare.py under the F1 tree.
F1_STATE_DIRNAME = "state"

# Build-tree directory names per component (shared with the M1 Makefile).
BUILD_DIR = {"llvm-project": "llvm", "qemu": "qemu", "gem5": "gem5"}

# The two components this phase isolates.  gem5 stays M1/unused.
F1_COMPONENTS = ("llvm-project", "qemu")

SHA1 = re.compile(r"^[0-9a-f]{40}$")
PATCH_NAME = re.compile(r"^(\d{4})-(?P<slug>.+)\.patch$")
PATCH_PREFIX = re.compile(r"^\[PATCH[^\]]*\]\s*")


def patch_subject(path: Path) -> str:
    """``Subject`` header of a ``format-patch`` mail, without ``[PATCH n/m]``.

    Used to prove that an exported patch file and the F1 commit it came from
    are the same change, so a series can never silently drift from its tree.
    """
    with path.open("rb") as stream:
        message = BytesParser(policy=email.policy.default).parse(stream)
    header = message["Subject"]
    if header is None:
        raise F1Error(f"patch {path} has no Subject header")
    return PATCH_PREFIX.sub("", str(header), count=1)


class F1Error(SystemExit):
    """Fail-closed F1 error: message on stderr, non-zero exit."""

    def __init__(self, message: str) -> None:
        super().__init__(f"f1: {message}")


# --------------------------------------------------------------------------- #
# git helpers
# --------------------------------------------------------------------------- #
def git(repo: Path, *args: str, check: bool = True) -> str:
    """Run ``git -C <repo> <args>`` and return stripped stdout."""
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        raise F1Error(
            f"git {' '.join(args)} failed in {repo} (rc={result.returncode}): "
            f"{result.stderr.strip()}"
        )
    return result.stdout.strip()


def git_ok(repo: Path, *args: str) -> bool:
    """True when ``git -C <repo> <args>`` exits 0 (no output kept)."""
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode == 0


def is_git_worktree(path: Path) -> bool:
    return (path / ".git").exists()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- #
# manifest / layout
# --------------------------------------------------------------------------- #
def load_manifest(root: Path) -> dict:
    with (root / "manifests/components.lock.toml").open("rb") as stream:
        return tomllib.load(stream)


def component_entry(root: Path, name: str) -> dict:
    manifest = load_manifest(root)
    for component in manifest.get("component", []):
        if component.get("name") == name:
            if not component.get("enabled"):
                raise F1Error(
                    f"component {name!r} is not enabled in "
                    f"manifests/components.lock.toml; refusing to fake success"
                )
            return component
    known = sorted(
        c.get("name", "") for c in manifest.get("component", []) if c.get("name")
    )
    raise F1Error(f"unknown component {name!r} (known: {', '.join(known)})")


def work_root(root: Path, manifest: dict | None = None) -> Path:
    if manifest is None:
        manifest = load_manifest(root)
    return root / manifest.get("work_root", ".work")


def f1_root(work: Path) -> Path:
    return work / F1_DIRNAME


def m1_source(work: Path, component: str) -> Path:
    return work / "source" / component


def m1_build(work: Path, component: str) -> Path:
    return work / "build" / BUILD_DIR[component]


def f1_source(work: Path, component: str) -> Path:
    return f1_root(work) / "source" / component


def f1_build(work: Path, component: str) -> Path:
    return f1_root(work) / "build" / BUILD_DIR[component]


def f1_state(work: Path, component: str) -> Path:
    return f1_root(work) / F1_STATE_DIRNAME / f"{component}.json"


# --------------------------------------------------------------------------- #
# canonical F1 layout containment
# --------------------------------------------------------------------------- #
def canonical(path: Path) -> str:
    """Absolute, fully symlink-resolved form of ``path``.

    Every F1 layout gate compares *canonical* paths, so a symlink that leaves
    the F1 root is rejected even though its textual path is inside it.  This is
    the only form used for the comparisons below, never a string/``startswith``
    test on the un-resolved path.
    """
    return os.path.realpath(path)


def _link_note(path: Path) -> str:
    return " [symlink]" if path.is_symlink() else ""


def _containment_gate(
    name: str, path: Path, want: str
) -> tuple[str, str, bool]:
    got = canonical(path)
    ok = got == want
    return (
        name,
        f"canonical={got}" if ok
        else f"{path} resolves to {got}, expected {want}{_link_note(path)}",
        ok,
    )


def f1_root_gate(work: Path) -> tuple[str, str, bool]:
    """The F1 root itself must be exactly ``<work>/f1``, not a link elsewhere."""
    base = f1_root(work)
    return _containment_gate(
        "f1_root is canonically <work>/f1", base, os.path.join(canonical(work), F1_DIRNAME)
    )


def f1_component_gates(work: Path, component: str) -> list[tuple[str, str, bool]]:
    """``(name, detail, ok)`` for one component's F1 source tree and build root.

    F1 owns exactly two paths per component -- the source tree at
    ``<f1>/source/<component>`` and the build root at
    ``<f1>/build/<build-dir>`` -- and they are legitimate only when they land on
    those canonical locations.  Because both sides of every comparison are
    resolved through the same anchor, a layout that merely reaches the work root
    through the pre-existing ``.work -> /mnt/dadao-v5/.work`` symlink is *not*
    flagged, while a symlink (or a plain out-of-root path) that escapes the F1
    root is.
    """
    anchor = os.path.join(canonical(work), F1_DIRNAME)
    return [
        _containment_gate(
            f"{component}: F1 source tree is canonically <f1>/source/{component}",
            f1_source(work, component),
            os.path.join(anchor, "source", component),
        ),
        _containment_gate(
            f"{component}: F1 build root is canonically "
            f"<f1>/build/{BUILD_DIR[component]}",
            f1_build(work, component),
            os.path.join(anchor, "build", BUILD_DIR[component]),
        ),
    ]


def f1_layout_failures(work: Path, component: str) -> list[str]:
    """``"<gate>: <detail>"`` for every canonical-containment gate that failed.

    An empty list means the whole F1 layout of ``component`` sits where the ADR
    requires it to sit.  Callers must run this *before* creating, cloning,
    checking out or recording anything: an escaped layout is refused, never
    repaired in place.
    """
    gates = [f1_root_gate(work), *f1_component_gates(work, component)]
    return [f"{name}: {detail}" for name, detail, ok in gates if not ok]


# --------------------------------------------------------------------------- #
# series / f1.json
# --------------------------------------------------------------------------- #
def series_path(root: Path, component: str) -> Path:
    return root / component_entry(root, component)["patch_series"]


def patches_dir(root: Path, component: str) -> Path:
    return series_path(root, component).parent


def read_series(path: Path) -> list[str]:
    """Ordered series entries, blanks and ``#`` comments removed."""
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def series_prefix_text(path: Path, count: int) -> str:
    """The first *count* series lines joined with ``\\n`` plus a trailing one.

    Byte-comparing this against a stored value proves the M1 prefix of the
    series was not rewritten, reordered or renamed, while still allowing
    ``0009+`` lines to be appended after it.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) < count:
        raise F1Error(
            f"{path} has {len(lines)} lines, cannot freeze the first {count}"
        )
    return "\n".join(lines[:count]) + "\n"


def patch_number(name: str) -> int | None:
    match = PATCH_NAME.match(name)
    return int(match.group(1)) if match else None


def load_f1_meta(root: Path, component: str) -> dict:
    """Load and fully validate ``components/<component>/patches/f1.json``."""
    path = patches_dir(root, component) / F1_META_NAME
    if not path.is_file():
        raise F1Error(f"missing F1 boundary metadata {path}")
    try:
        meta = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise F1Error(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(meta, dict):
        raise F1Error(f"{path} must contain a JSON object")
    if meta.get("format") != F1_META_FORMAT:
        raise F1Error(f"{path}: format {meta.get('format')!r} != {F1_META_FORMAT}")
    if meta.get("component") != component:
        raise F1Error(
            f"{path}: component {meta.get('component')!r} != {component!r}"
        )
    entry = component_entry(root, component)
    for key in ("base_lock", "m1_head_commit", "m1_head_tree"):
        value = meta.get(key)
        if not isinstance(value, str) or not SHA1.fullmatch(value):
            raise F1Error(f"{path}: {key} must be a full 40-hex sha1, got {value!r}")
    if meta["base_lock"] != entry["commit"]:
        raise F1Error(
            f"{path}: base_lock {meta['base_lock']} != manifest commit "
            f"{entry['commit']} for {component}"
        )
    count = meta.get("m1_patch_count")
    if not isinstance(count, int) or count < 1:
        raise F1Error(f"{path}: m1_patch_count must be a positive int, got {count!r}")
    first = meta.get("f1_first_patch_number")
    if first != count + 1:
        raise F1Error(
            f"{path}: f1_first_patch_number {first!r} != m1_patch_count + 1 "
            f"({count + 1})"
        )
    entries = meta.get("m1_series_entries")
    if not isinstance(entries, list) or len(entries) != count:
        raise F1Error(
            f"{path}: m1_series_entries must be a list of {count} names, got "
            f"{entries!r}"
        )
    for index, name in enumerate(entries, 1):
        if patch_number(name) != index:
            raise F1Error(
                f"{path}: m1_series_entries[{index - 1}] = {name!r} is not "
                f"numbered {index:04d}"
            )
    return meta


def f1_entry_names(root: Path, component: str, meta: dict) -> list[str]:
    """The ``0009+`` part of the series, in order."""
    names = read_series(series_path(root, component))
    first = meta["f1_first_patch_number"]
    return [name for name in names if (patch_number(name) or 0) >= first]


def series_problems(
    root: Path, component: str, meta: dict, *, require_patches: bool = True
) -> list[str]:
    """Every F1 series violation found, as human-readable strings.

    An empty list means the series satisfies: frozen M1 prefix, continuous
    numbering from ``0001``, and (optionally) existing non-empty patch files.
    """
    problems: list[str] = []
    path = series_path(root, component)
    count = meta["m1_patch_count"]
    first = meta["f1_first_patch_number"]
    names = read_series(path)

    if not names:
        problems.append(f"{path}: series is empty (expected at least {count} entries)")
        return problems

    for index, name in enumerate(names, 1):
        number = patch_number(name)
        if number is None:
            problems.append(
                f"{path}[{index}]: {name!r} is not a NNNN-slug.patch file name"
            )
        elif number != index:
            problems.append(
                f"{path}[{index}]: {name!r} is numbered {number:04d}; series "
                f"numbering must be continuous (expected {index:04d})"
            )

    if names[:count] != list(meta["m1_series_entries"]):
        problems.append(
            f"{path}: the frozen M1 prefix was modified: expected "
            f"{list(meta['m1_series_entries'])}, found {names[:count]}"
        )

    f1_names = [name for name in names if (patch_number(name) or 0) >= first]
    for offset, name in enumerate(f1_names):
        number = patch_number(name)
        if number != first + offset:
            problems.append(
                f"{path}: F1 entry {name!r} is numbered {number}, expected "
                f"{first + offset} (F1 appends must be continuous from {first:04d})"
            )

    duplicates = sorted({n for n in names if names.count(n) > 1})
    if duplicates:
        problems.append(f"{path}: duplicate series entries {duplicates}")

    if require_patches:
        for name in names:
            patch = path.parent / name
            if not patch.is_file():
                problems.append(f"{path}: referenced patch {name!r} does not exist")
            elif patch.stat().st_size == 0:
                problems.append(f"{path}: referenced patch {name!r} is empty")
    return problems


def load_state(work: Path, component: str) -> dict:
    path = f1_state(work, component)
    if not path.is_file():
        raise F1Error(
            f"missing F1 state record {path}; run `make f1-prepare` first"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def write_state(work: Path, component: str, record: dict) -> Path:
    path = f1_state(work, component)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(record, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path
