#!/usr/bin/env python3
"""Reject generated binary artifacts in the Git index."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    paths = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    forbidden = []
    for name in filter(None, paths):
        path = ROOT / name
        if not path.is_file():
            continue
        with path.open("rb") as stream:
            magic = stream.read(8)
        if (name.startswith("platform/targets/") or path.suffix.lower() in {".a", ".o", ".obj", ".lib", ".exe", ".dll", ".so", ".dylib", ".wasm"}
                or name.endswith((".tar.gz", ".tar.xz", ".tar.zst", ".zip"))
                or magic.startswith((b"\x7fELF", b"MZ", b"!<arch>\n", b"\x00asm", b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf"))):
            forbidden.append(name)
    if forbidden:
        raise SystemExit(f"Generated binaries must be release assets, not tracked source: {forbidden}")
    print("Tracked binary policy passed")


if __name__ == "__main__":
    main()
