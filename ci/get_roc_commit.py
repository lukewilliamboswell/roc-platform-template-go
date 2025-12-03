#!/usr/bin/env python3
"""
Get the pinned Roc commit from roc_commit.txt.
"""
from pathlib import Path


def main() -> None:
    commit_file = Path(__file__).resolve().parent / "roc_commit.txt"
    try:
        commit = commit_file.read_text().strip()
    except FileNotFoundError:
        raise SystemExit(f"Missing roc_commit.txt at {commit_file}")

    if len(commit) != 40:
        raise SystemExit(f"Invalid commit hash: {commit}")

    print(commit)


if __name__ == "__main__":
    main()
