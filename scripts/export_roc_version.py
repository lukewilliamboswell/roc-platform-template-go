#!/usr/bin/env python3
"""Export the repository-pinned Roc nightly tag for GitHub Actions."""

from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    values = (ROOT / ".roc-version").read_text(encoding="utf-8").splitlines()
    if len(values) != 1 or not values[0].startswith("nightly-"):
        raise SystemExit(".roc-version must contain exactly one Roc nightly tag")
    github_env = os.environ.get("GITHUB_ENV")
    if not github_env:
        raise SystemExit("GITHUB_ENV is not set")
    with Path(github_env).open("a", encoding="utf-8") as stream:
        stream.write(f"ROC_NIGHTLY_TAG={values[0]}\n")
    print(f"Pinned Roc nightly: {values[0]}")


if __name__ == "__main__":
    main()
