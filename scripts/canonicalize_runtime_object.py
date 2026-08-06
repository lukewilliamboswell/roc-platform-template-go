#!/usr/bin/env python3
"""Remove Zig's random cache-root spelling from a generated object file."""

from pathlib import Path
import sys


CANONICAL_ROOT = b"/tmp/roc-go-zig-runtime.CANON0"


def canonicalize(object_path: Path, random_work_root: Path) -> None:
    random_root = str(random_work_root).encode()
    if len(random_root) != len(CANONICAL_ROOT):
        raise ValueError("random and canonical cache roots must have equal lengths")
    contents = object_path.read_bytes()
    object_path.write_bytes(contents.replace(random_root, CANONICAL_ROOT))


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(f"usage: {sys.argv[0]} OBJECT RANDOM_WORK_ROOT")

    try:
        canonicalize(Path(sys.argv[1]), Path(sys.argv[2]))
    except ValueError as error:
        raise SystemExit(str(error)) from None


if __name__ == "__main__":
    main()
