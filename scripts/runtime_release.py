#!/usr/bin/env python3
"""Compare independently built linker-input candidates byte for byte."""
import argparse
import json
import os
from pathlib import Path

from runtime_assets import archive_name, read_archive, sha256


def compare(left, right):
    names = {path.name for path in left.iterdir()}
    if names != {path.name for path in right.iterdir()}:
        raise ValueError("Independent build inventories differ")
    for name in names:
        if (left / name).read_bytes() != (right / name).read_bytes():
            raise ValueError(f"Independent builds differ: {name}")
    dependency = json.loads((left / "dependency.json").read_text())
    version = dependency["release_tag"].removeprefix("linker-inputs-v")
    archive = left / archive_name(version)
    manifest, _ = read_archive(archive)
    if manifest["version"] != version:
        raise ValueError("Release and archive versions differ")
    with open(os.environ.get("GITHUB_OUTPUT", os.devnull), "a") as output:
        output.write(f"sha256={sha256(archive)}\n")
    print("Independent linker-input archives and metadata are byte-identical")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("compare")
    p.add_argument("--left", required=True, type=Path)
    p.add_argument("--right", required=True, type=Path)
    args = parser.parse_args()
    compare(args.left, args.right)
