#!/usr/bin/env python3
"""Compare independently built linker-input candidates."""
import argparse
import os
from pathlib import Path

from fetch_runtime import load_lock
from runtime_assets import ROOT, archive_name, read_archive, sha256


def compare(left, right):
    names = {path.name for path in left.iterdir()}
    if names != {path.name for path in right.iterdir()}:
        raise ValueError("Independent build inventories differ")
    for name in names:
        if (left / name).read_bytes() != (right / name).read_bytes():
            raise ValueError(f"Independent builds differ: {name}")
    lock = load_lock(left / "runtime-release.json")
    archive = left / archive_name(lock["version"])
    manifest, _ = read_archive(archive)
    if lock["version"] == "0.1.0":
        for line in (ROOT / "scripts/runtime_bootstrap.sha256").read_text().splitlines():
            digest, path = line.split("  ", 1)
            if manifest["files"][f"targets/{path}"] != digest:
                raise ValueError(f"Bootstrap runtime differs from original baseline: {path}")
    with open(os.environ.get("GITHUB_OUTPUT", os.devnull), "a") as output:
        output.write(f"sha256={sha256(archive)}\n")
    print("Independent runtime archives and metadata are byte-identical")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--left", required=True, type=Path)
    parser.add_argument("--right", required=True, type=Path)
    args = parser.parse_args()
    compare(args.left, args.right)
