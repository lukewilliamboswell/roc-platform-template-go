#!/usr/bin/env python3
"""Fetch, check, or stage authenticated external linker inputs."""
from __future__ import annotations

import argparse
from pathlib import Path

import fetch_runtime as implementation


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("fetch", help="fetch and authenticate the reviewed lock")
    commands.add_parser("check", help="check installed files against the lock and cache")
    stage = commands.add_parser("stage", help="stage an unsigned same-run CI candidate")
    stage.add_argument("archive", type=Path)
    stage.add_argument("--sha256", required=True)
    args = parser.parse_args()
    if args.command == "fetch":
        implementation.fetch()
    elif args.command == "check":
        print(f"Verified linker inputs: {implementation.verify_installed()}")
    else:
        manifest, _ = implementation.read_archive(args.archive)
        if implementation.sha256(args.archive) != args.sha256:
            raise ValueError("Linker-input candidate checksum mismatch")
        cache = implementation.ROOT / ".linker-inputs-cache" / args.sha256
        cache.mkdir(parents=True, exist_ok=True)
        archive = cache / implementation.archive_name(manifest["version"])
        implementation.shutil.copyfile(args.archive, archive)
        implementation.install(archive, args.sha256)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError) as error:
        raise SystemExit(f"Linker-input verification failed: {error}") from None
