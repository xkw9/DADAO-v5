#!/usr/bin/env python3
"""Serialised, resource-sampled wrapper for the F1 build entrypoints.

ADR-1004 requires that LLVM and QEMU ``configure``/``build``/``link`` never run
concurrently with each other or with an M1 build: this host has 3906 MiB RAM and
during ``INFRA-105t`` the lowest observed ``MemAvailable`` was 45 MiB, so a second
parallel build/link is a real OOM risk, not a theoretical one.

This wrapper is what makes that rule mechanical instead of procedural:

* it refuses to start while any process is working inside an M1 or F1 build tree
  (detected via ``/proc/<pid>/cwd``), so an F1 build cannot overlap an M1 one;
* it takes an exclusive ``flock`` on ``<work>/f1/.build.lock`` for the whole run,
  so two F1 builds cannot overlap either -- the second one exits non-zero with a
  clear message instead of thrashing;
* it samples ``/proc/meminfo`` and swap usage while the command runs and reports
  the minimum ``MemAvailable`` observed, giving the resource evidence the task
  book asks for;
* it records start/end timestamps and the real child exit code in a log.

Usage::

    f1_build_lock.py [--root ROOT] [--label NAME] [--log FILE]
                     [--work-dir DIR]... -- CMD [ARG...] [-- CMD [ARG...]...]
"""
from __future__ import annotations

import argparse
import fcntl
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from f1_common import (  # noqa: E402
    DEFAULT_ROOT,
    F1_COMPONENTS,
    BUILD_DIR,
    f1_root,
    load_manifest,
    m1_build,
    work_root,
)


def _inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def busy_processes(roots: list[Path]) -> list[tuple[int, str]]:
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
            continue
        for root in resolved:
            if _inside(cwd, root):
                busy.append((int(entry.name), str(cwd)))
                break
    return sorted(busy)


def meminfo_kib(field: str) -> int:
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if line.startswith(field):
                return int(line.split()[1])
    except OSError:
        pass
    return -1


def sample_resources() -> tuple[int, int]:
    return meminfo_kib("MemAvailable:"), meminfo_kib("SwapFree:")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=str(DEFAULT_ROOT))
    parser.add_argument("--work")
    parser.add_argument("--label", default="f1-build")
    parser.add_argument("--log", help="append the serialisation record here")
    parser.add_argument(
        "--interval",
        type=float,
        default=2.0,
        help="resource sampling interval in seconds (default: 2)",
    )
    parser.add_argument(
        "--ignore-busy",
        action="store_true",
        help="skip the concurrent-build probe (lock is still taken)",
    )
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    argv = list(args.command)
    if argv and argv[0] == "--":
        argv = argv[1:]
    commands: list[list[str]] = []
    for token in argv:
        if token == "--":
            commands.append([])
        elif commands:
            commands[-1].append(token)
        else:
            commands.append([token])
    commands = [command for command in commands if command]
    if not commands:
        print(
            "f1-build-lock: no command given; usage: f1_build_lock.py ... -- CMD",
            file=sys.stderr,
        )
        return 2

    root = Path(args.root).resolve()
    work = (
        Path(args.work).resolve() if args.work else work_root(root, load_manifest(root))
    )
    watched = [m1_build(work, name) for name in F1_COMPONENTS] + [
        work / "f1" / "build" / BUILD_DIR[name] for name in F1_COMPONENTS
    ]
    lines: list[str] = []

    def emit(text: str) -> None:
        print(text)
        lines.append(text)

    if not args.ignore_busy:
        busy = busy_processes(watched)
        if busy:
            emit(
                f"f1-build-lock: REFUSING {args.label}: {len(busy)} process(es) "
                f"already working inside a build tree: {busy}"
            )
            _flush(args.log, lines)
            return 1

    f1_root(work).mkdir(parents=True, exist_ok=True)
    lock_path = f1_root(work) / ".build.lock"
    handle = lock_path.open("a+")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        emit(
            f"f1-build-lock: REFUSING {args.label}: another F1 build holds "
            f"{lock_path}; builds must be serialised"
        )
        _flush(args.log, lines)
        handle.close()
        return 1

    available, swap_free = sample_resources()
    emit(
        f"f1-build-lock: {args.label} acquired {lock_path} at "
        f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} "
        f"MemAvailable={available} KiB SwapFree={swap_free} KiB"
    )
    low = available
    start = time.time()
    rc = 0
    try:
        for command in commands:
            emit(f"f1-build-lock: run {' '.join(command)}")
            process = subprocess.Popen(command)
            while process.poll() is None:
                available, swap_free = sample_resources()
                low = min(low, available)
                time.sleep(args.interval)
            rc = process.returncode
            emit(f"f1-build-lock: exit {rc} for {' '.join(command)}")
            if rc != 0:
                break
    finally:
        elapsed = time.time() - start
        fcntl.flock(handle, fcntl.LOCK_UN)
        handle.close()
    emit(
        f"f1-build-lock: {args.label} finished rc={rc} in {elapsed:.1f}s "
        f"min_MemAvailable={low} KiB"
    )
    _flush(args.log, lines)
    return rc


def _flush(log: str | None, lines: list[str]) -> None:
    if not log:
        return
    path = Path(log)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        for line in lines:
            stream.write(line + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
