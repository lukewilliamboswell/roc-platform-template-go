#!/usr/bin/env python3
"""Release-controller checks; never run a build with publication credentials."""
import argparse
import json
import os
from pathlib import Path
import subprocess

from runtime_assets import REPO, ROOT, archive_name, read_archive, sha256


def must_be_new(tag):
    for endpoint in (f"releases/tags/{tag}", f"git/ref/tags/{tag}"):
        result = subprocess.run(["gh", "api", f"repos/{REPO}/{endpoint}"], capture_output=True, text=True)
        if result.returncode == 0:
            raise ValueError(f"Release/tag already exists: {tag}; use the documented recovery procedure")
        if "(HTTP 404)" not in result.stderr:
            raise ValueError(f"Could not check release identity: {result.stderr}")


def prepare(version):
    name = archive_name(version)
    if os.environ.get("GITHUB_REF") != "refs/heads/main" or os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch":
        raise ValueError("Linker-input publication requires a manual dispatch from main")
    must_be_new(f"linker-inputs-v{version}")
    with open(os.environ["GITHUB_OUTPUT"], "a") as output:
        output.write(f"version={version}\narchive={name}\n")


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
    p = commands.add_parser("prepare")
    p.add_argument("--version", required=True)
    p = commands.add_parser("compare")
    p.add_argument("--left", required=True, type=Path)
    p.add_argument("--right", required=True, type=Path)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.version)
    elif args.command == "compare":
        compare(args.left, args.right)
