#!/usr/bin/env python3
"""Release-controller checks; never run a build with publication credentials."""
import argparse
import json
import os
from pathlib import Path
import subprocess

from fetch_runtime import load_lock, verify_release
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
        raise ValueError("Runtime publication requires a manual dispatch from main")
    must_be_new(f"runtime-v{version}")
    with open(os.environ["GITHUB_OUTPUT"], "a") as output:
        output.write(f"version={version}\narchive={name}\n")


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
        for line in (ROOT / "scripts/zig_runtime.sha256").read_text().splitlines():
            digest, path = line.split("  ", 1)
            if manifest["files"][f"targets/{path}"] != digest:
                raise ValueError(f"Bootstrap runtime differs from original baseline: {path}")
    with open(os.environ.get("GITHUB_OUTPUT", os.devnull), "a") as output:
        output.write(f"sha256={sha256(archive)}\n")
    print("Independent runtime archives and metadata are byte-identical")


def publish(directory):
    lock = load_lock(directory / "runtime-release.json")
    if os.environ.get("GITHUB_SHA") != lock["source_commit"] or os.environ.get("GITHUB_REF") != lock["source_ref"]:
        raise ValueError("Candidate source differs from this release workflow")
    verify_release(directory, lock)
    tag = f"runtime-v{lock['version']}"
    must_be_new(tag)
    notes = directory / "RELEASE.md"
    notes.write_text(f"Runtime dependencies {lock['version']}\n\n"
                     f"Built and tested from `{lock['source_commit']}`.\n"
                     f"Archive SHA-256: `{lock['sha256']}`.\n\n"
                     "Third-party runtimes and linker inputs only; Go hosts are built by platform CI.\n"
                     "The SPDX SBOM records bundled sources and file checksums. Both provenance and SBOM attestations are attached.\n"
                     "See RUNTIME_PROVENANCE.md at the source commit for verification and recovery instructions.\n")
    subprocess.run(["gh", "release", "create", tag, "--repo", REPO, "--target", lock["source_commit"],
                    "--draft", "--latest=false", "--title", f"Runtime dependencies {lock['version']}",
                    "--notes-file", str(notes)], check=True)
    assets = [archive_name(lock["version"]), "runtime.spdx.json", "SHA256SUMS", "runtime-release.json",
              "provenance.sigstore.json", "sbom.sigstore.json"]
    subprocess.run(["gh", "release", "upload", tag, "--repo", REPO, *[str(directory / name) for name in assets]], check=True)
    # Download the draft assets and verify bytes before locking the release.
    import tempfile
    with tempfile.TemporaryDirectory() as temporary:
        subprocess.run(["gh", "release", "download", tag, "--repo", REPO, "--dir", temporary], check=True)
        for name in assets:
            if (Path(temporary) / name).read_bytes() != (directory / name).read_bytes():
                raise ValueError(f"Uploaded release asset differs: {name}")
    subprocess.run(["gh", "release", "edit", tag, "--repo", REPO, "--draft=false", "--latest=false"], check=True)
    release = json.loads(subprocess.check_output(["gh", "api", f"repos/{REPO}/releases/tags/{tag}"], text=True))
    if not release.get("immutable"):
        raise ValueError("Published release is not immutable; enable repository release immutability")
    print(release["html_url"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("prepare")
    p.add_argument("--version", required=True)
    p = commands.add_parser("compare")
    p.add_argument("--left", required=True, type=Path)
    p.add_argument("--right", required=True, type=Path)
    p = commands.add_parser("publish")
    p.add_argument("--directory", required=True, type=Path)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.version)
    elif args.command == "compare":
        compare(args.left, args.right)
    else:
        publish(args.directory)
