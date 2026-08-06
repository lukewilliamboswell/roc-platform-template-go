#!/usr/bin/env python3
"""Generate or verify the C host ABI with the repository-pinned Roc nightly."""

from __future__ import annotations

import argparse
import difflib
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROC_VERSION_FILE = ROOT / ".roc-version"
PLATFORM_FILE = ROOT / "platform" / "main.roc"
OUTPUT_FILE = ROOT / "host" / "roc" / "roc_platform_abi.h"
PIN_PATTERN = re.compile(
    r"nightly-\d{4}-[A-Za-z]+-\d{1,2}-(?P<revision>[0-9a-f]{7,40})"
)
ROC_REVISION_PATTERN = re.compile(r"\b[0-9a-f]{7,40}\b")


def pinned_revision() -> tuple[str, str]:
    values = ROC_VERSION_FILE.read_text(encoding="utf-8").splitlines()
    if len(values) != 1:
        raise SystemExit(".roc-version must contain exactly one Roc nightly tag")

    tag = values[0]
    match = PIN_PATTERN.fullmatch(tag)
    if match is None:
        raise SystemExit(f"invalid Roc nightly tag in .roc-version: {tag!r}")
    return tag, match.group("revision")


def require_pinned_roc(expected_revision: str) -> str:
    try:
        version = subprocess.check_output(["roc", "version"], text=True).strip()
    except FileNotFoundError as error:
        raise SystemExit("roc is not installed or is not on PATH") from error
    except subprocess.CalledProcessError as error:
        raise SystemExit("failed to read the active Roc compiler version") from error

    revisions = ROC_REVISION_PATTERN.findall(version.lower())
    if not any(revision.startswith(expected_revision) for revision in revisions):
        raise SystemExit(
            f"Roc nightly {expected_revision} is required; found {version!r}"
        )
    return version


def download_glue_spec(revision: str, destination: Path) -> str:
    url = (
        "https://raw.githubusercontent.com/roc-lang/roc/"
        f"{revision}/src/glue/src/CGlue.roc"
    )
    request = urllib.request.Request(url, headers={"User-Agent": "roc-go-glue"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            destination.write_bytes(response.read())
    except (OSError, urllib.error.URLError) as error:
        raise SystemExit(f"failed to download pinned CGlue.roc from {url}: {error}")
    return url


def generate(glue_spec: Path, output_dir: Path) -> Path:
    subprocess.run(
        ["roc", "glue", str(glue_spec), str(output_dir), str(PLATFORM_FILE)],
        cwd=ROOT,
        check=True,
    )
    generated = output_dir / OUTPUT_FILE.name
    if not generated.is_file():
        raise SystemExit(f"roc glue did not generate {generated}")
    return generated


def check_generated(generated: Path) -> None:
    if not OUTPUT_FILE.is_file():
        raise SystemExit(f"missing generated C glue: {OUTPUT_FILE.relative_to(ROOT)}")

    expected = OUTPUT_FILE.read_text(encoding="utf-8").splitlines(keepends=True)
    actual = generated.read_text(encoding="utf-8").splitlines(keepends=True)
    if expected == actual:
        print(f"C glue is up to date: {OUTPUT_FILE.relative_to(ROOT)}")
        return

    diff = difflib.unified_diff(
        expected,
        actual,
        fromfile=str(OUTPUT_FILE.relative_to(ROOT)),
        tofile="generated/roc_platform_abi.h",
    )
    print("".join(diff), end="")
    raise SystemExit(
        "generated C glue is stale; run python scripts/generate_c_glue.py"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="compare generated glue with the committed header",
    )
    parser.add_argument(
        "--glue-spec",
        type=Path,
        help="use CGlue.roc from an exact matching Roc source checkout",
    )
    args = parser.parse_args()

    tag, revision = pinned_revision()
    version = require_pinned_roc(revision)

    # Roc cleans stale `roc-*` directories in the system temp directory, so
    # keep this workspace outside that namespace while the compiler runs.
    with tempfile.TemporaryDirectory(prefix="go-host-c-glue-") as temporary:
        temporary_dir = Path(temporary)
        if args.glue_spec is None:
            glue_spec = temporary_dir / "CGlue.roc"
            glue_source = download_glue_spec(revision, glue_spec)
        else:
            glue_spec = args.glue_spec.resolve()
            if not glue_spec.is_file():
                raise SystemExit(f"C glue spec does not exist: {glue_spec}")
            glue_source = str(glue_spec)

        generated = generate(glue_spec, temporary_dir / "generated")
        print(f"Using pinned Roc nightly: {tag} ({version})")
        print(f"Using C glue spec: {glue_source}")

        if args.check:
            check_generated(generated)
        else:
            shutil.copyfile(generated, OUTPUT_FILE)
            print(f"Generated: {OUTPUT_FILE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
