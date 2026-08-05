#!/usr/bin/env python3
"""Check every repository Roc source file with portable individual paths."""

from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRS = (ROOT / "platform", ROOT / "examples")


def main() -> None:
    sources = sorted(
        source
        for directory in SOURCE_DIRS
        for source in directory.rglob("*.roc")
    )
    if not sources:
        raise SystemExit("No Roc source files found")

    for source in sources:
        relative = source.relative_to(ROOT).as_posix()
        subprocess.run(["roc", "fmt", "--check", relative], cwd=ROOT, check=True)
    print(f"Roc formatting valid for {len(sources)} files.")


if __name__ == "__main__":
    main()
