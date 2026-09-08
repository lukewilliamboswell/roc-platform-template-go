#!/usr/bin/env python3
"""Export the repository-pinned Roc nightly tag for GitHub Actions."""

from __future__ import annotations

import json
import os
from pathlib import Path

from compiler_pins import discover, local_sources


ROOT = Path(__file__).resolve().parents[1]


def pinned_tag(root: Path = ROOT) -> str:
    if (root / ".roc-version").exists():
        raise ValueError("Remove .roc-version; compiler headers are authoritative")
    config = json.loads((root / ".github/roc-nightly.json").read_text(encoding="utf-8"))
    roots = config["compiler_roots"]
    pins = discover(local_sources(root, roots))
    tag = next(iter(pins.values()))[1][2]
    if not tag.startswith("nightly-"):
        raise ValueError("This platform currently requires an exact Roc nightly")
    return tag


def main() -> None:
    tag = pinned_tag()
    github_env = os.environ.get("GITHUB_ENV")
    if not github_env:
        raise SystemExit("GITHUB_ENV is not set")
    with Path(github_env).open("a", encoding="utf-8") as stream:
        stream.write(f"ROC_NIGHTLY_TAG={tag}\n")
    print(f"Pinned Roc nightly: {tag}")


if __name__ == "__main__":
    main()
