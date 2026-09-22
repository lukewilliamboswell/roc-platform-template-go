#!/usr/bin/env python3
"""Package the tested runtime archive for content-addressed PR publication."""
import argparse, hashlib, json, os, shutil, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUTS = ("licenses", "scripts/runtime_sources.json", "scripts/runtime_bootstrap.sha256",
          "scripts/install_runtime_zig.py", "scripts/vendor_zig_runtime.py",
          "scripts/package_runtime.py", "scripts/runtime_assets.py", "scripts/build_input_release.py",
          ".github/workflows/release-runtime.yml")

def fingerprint():
    tree = subprocess.check_output(["git", "ls-tree", "-r", "-z", "--full-tree", "HEAD", "--", *INPUTS], cwd=ROOT)
    if not tree:
        raise ValueError("runtime input inventory is empty")
    return hashlib.sha256(tree).hexdigest()

def prepare(source: Path, output: Path):
    output.mkdir(parents=True, exist_ok=False)
    archives = list(source.glob("roc-go-runtimes-*.tar.gz"))
    if len(archives) != 1:
        raise ValueError("expected exactly one tested runtime archive")
    asset = output / "link-inputs-all.tar"
    shutil.copyfile(archives[0], asset)
    identity = {"repository": os.environ["GITHUB_REPOSITORY"], "sha": os.environ["GITHUB_SHA"],
                "ref": os.environ["GITHUB_REF"],
                "workflow": os.environ["GITHUB_REPOSITORY"] + "/.github/workflows/release-runtime.yml",
                "input_fingerprint": fingerprint()}
    manifest = {"schema_version": 1, "kind": "roc-go-link-inputs", "source": identity,
                "assets": {"all": {"asset": asset.name,
                "sha256": hashlib.sha256(asset.read_bytes()).hexdigest(), "size": asset.stat().st_size}}}
    (output / "build-input-release.json").write_text(json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    prepare(args.source, args.output)
