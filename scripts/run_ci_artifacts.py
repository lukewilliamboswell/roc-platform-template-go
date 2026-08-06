#!/usr/bin/env python3
"""Run a native target suite against artifacts from every CI builder."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGETS = (
    "x64mac",
    "arm64mac",
    "x64musl",
    "x64v1musl",
    "arm64musl",
    "arm64v1musl",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_bundle(artifact: Path, target: str) -> None:
    bundles = sorted((artifact / "bundle").glob("*.tar.zst"))
    if len(bundles) != 1:
        raise SystemExit(
            f"{artifact.name}: expected exactly one platform bundle, found {len(bundles)}"
        )
    manifest_path = artifact / "binaries" / target / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        expected = manifest["platform_bundle_sha256"]
    except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError) as error:
        raise SystemExit(f"{artifact.name}: cannot read {manifest_path}: {error}") from None
    actual = sha256(bundles[0])
    if actual != expected:
        raise SystemExit(
            f"{artifact.name}: platform bundle checksum mismatch: {actual} != {expected}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts-root", type=Path, required=True)
    parser.add_argument("--target", choices=TARGETS, required=True)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    root = args.artifacts_root.resolve()
    artifacts = sorted(path for path in root.glob("apps-*") if path.is_dir())
    if not artifacts:
        raise SystemExit(f"No producer artifacts found under {root}")

    for artifact in artifacts:
        verify_bundle(artifact, args.target)
        command = [
            sys.executable,
            str(ROOT / "scripts" / "test.py"),
            "--operation",
            "run-prebuilt",
            "--binaries-dir",
            str(artifact / "binaries" / args.target),
            "--label",
            artifact.name,
        ]
        if args.verbose:
            command.append("--verbose")
        subprocess.run(command, cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
