#!/usr/bin/env python3
"""Fetch, authenticate, and install the locked linker-input release."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import urllib.request

from runtime_assets import (ROOT, REPO, MANIFEST, RUNTIME_PATHS, PAYLOAD_PATHS,
                            SHA, COMMIT, archive_name, json_bytes, read_archive, sha256)
from build_input_release import fingerprint as input_fingerprint

LOCK = ROOT / "link-inputs.lock.json"
def load_lock(path: Path = LOCK) -> dict:
    value = json.loads(path.read_text())
    record = value.get("targets", {}).get("all", {})
    source = value.get("source", {})
    manifest = value.get("manifest", {})
    if (set(value) != {"schema_version", "kind", "repository", "release", "manifest", "source", "targets"}
            or value.get("schema_version") != 1 or value.get("kind") != "roc-go-link-inputs"
            or value.get("repository") != REPO or set(value.get("targets", {})) != {"all"}
            or not re.fullmatch(r"link-inputs-sha256-[0-9a-f]{64}", value.get("release", ""))
            or set(manifest) != {"asset", "sha256"}
            or manifest.get("asset") != "build-input-release.json"
            or not SHA.fullmatch(manifest.get("sha256", ""))
            or set(source) != {"repository", "sha", "ref", "workflow", "input_fingerprint"}
            or source.get("repository") != REPO or not COMMIT.fullmatch(source.get("sha", ""))
            or not source.get("ref", "").startswith("refs/heads/")
            or source.get("workflow") != f"{REPO}/.github/workflows/release-runtime.yml"
            or source.get("input_fingerprint") != input_fingerprint()
            or set(record) != {"asset", "sha256", "size"}
            or record.get("asset") != "link-inputs-all.tar"
            or not SHA.fullmatch(record.get("sha256", ""))
            or type(record.get("size")) is not int or record["size"] <= 0):
        raise ValueError("Invalid content-addressed linker-input lock")
    return {"repository": REPO, "release": value["release"], "asset": record["asset"],
            "sha256": record["sha256"], "size": record["size"],
            "source_commit": source["sha"], "source_ref": source["ref"]}


def download(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "roc-go-linker-inputs-fetch"})
    temporary = destination.with_suffix(destination.suffix + ".partial")
    try:
        with urllib.request.urlopen(request, timeout=120) as response, temporary.open("wb") as output:
            shutil.copyfileobj(response, output)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def ensure_regular(path: Path, platform: Path) -> None:
    relative = path.relative_to(platform)
    current = platform
    if current.is_symlink():
        raise ValueError("Platform directory must not be a symlink")
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"Runtime path must not be a symlink: {current}")


def install(archive: Path, digest: str, platform: Path = ROOT / "platform") -> None:
    if not SHA.fullmatch(digest) or sha256(archive) != digest:
        raise ValueError("Linker-input candidate/archive checksum mismatch")
    manifest, files = read_archive(archive)
    for name in files:
        ensure_regular(platform / name, platform)
    ensure_regular(platform / "linker-inputs/receipt.json", platform)
    # Stage all bytes before modifying the installation. Write the receipt last;
    # interrupted installs cannot pass verify_installed against mixed contents.
    with tempfile.TemporaryDirectory(prefix="runtime-install-") as temporary:
        staging = Path(temporary)
        for name, data in files.items():
            path = staging / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        for name in files:
            destination = platform / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(staging / name, destination)
    receipt = {"format": 1, "sha256": digest, "source_commit": manifest["source_commit"], "version": manifest["version"]}
    (platform / "linker-inputs/receipt.json").write_bytes(json_bytes(receipt))
    print(f"Installed linker inputs {manifest['version']} ({digest})")


def verify_installed(platform: Path = ROOT / "platform", lock_path: Path = LOCK) -> str:
    # Explicit same-run candidate mode is used only by read-only release tests.
    candidate = os.environ.get("LINKER_INPUTS_CANDIDATE_SHA256")
    lock = None if candidate else load_lock(lock_path)
    expected_digest = candidate or lock["sha256"]
    if not SHA.fullmatch(expected_digest):
        raise ValueError("Invalid expected linker-input digest")
    receipt = json.loads((platform / "linker-inputs/receipt.json").read_text())
    manifest = json.loads((platform / MANIFEST).read_text())
    if receipt.get("sha256") != expected_digest or set(manifest.get("files", {})) != PAYLOAD_PATHS:
        raise ValueError("Installed linker inputs does not match the selected release")
    if lock and manifest["source_commit"] != lock["source_commit"]:
        raise ValueError("Installed linker inputs metadata differs from lock")
    for name, expected in manifest["files"].items():
        path = platform / name
        ensure_regular(path, platform)
        if sha256(path) != expected:
            raise ValueError(f"Installed linker-input checksum mismatch: {name}")
    allowed = RUNTIME_PATHS | {"linker-inputs/receipt.json", MANIFEST} | PAYLOAD_PATHS
    for directory in (platform / "targets", platform / "linker-inputs"):
        for path in directory.rglob("*"):
            ensure_regular(path, platform)
            if path.is_file():
                relative = path.relative_to(platform).as_posix()
                if relative not in allowed and not (directory.name == "targets" and path.name in {"libhost.a", "libhost.h", "host.lib", "host.h"}):
                    raise ValueError(f"Unexpected installed linker inputs file: {relative}")
    # Compare installed metadata and bytes with the original authenticated archive
    # on every bundle, so editing the manifest/receipt cannot bless modified files.
    cache = ROOT / ".linker-inputs-cache" / expected_digest
    archive = cache / (lock["asset"] if lock else archive_name(manifest["version"]))
    if sha256(archive) != expected_digest:
        raise ValueError("Cached linker-input archive checksum mismatch")
    _, original = read_archive(archive)
    for name, data in original.items():
        if (platform / name).read_bytes() != data:
            raise ValueError(f"Installed linker inputs differs from authenticated archive: {name}")
    return expected_digest


def fetch() -> None:
    lock = load_lock()
    cache = ROOT / ".linker-inputs-cache" / lock["sha256"]
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / lock["asset"]
    if (not archive.is_file() or archive.stat().st_size != lock["size"]
            or sha256(archive) != lock["sha256"]):
        archive.unlink(missing_ok=True)
        download(f"https://github.com/{REPO}/releases/download/{lock['release']}/{lock['asset']}", archive)
    if archive.stat().st_size != lock["size"] or sha256(archive) != lock["sha256"]:
        raise ValueError("Cached linker-input archive differs from its reviewed content hash")
    install(archive, lock["sha256"], ROOT / "platform")
    verify_installed(ROOT / "platform", ROOT / "link-inputs.lock.json")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-installed", action="store_true")
    parser.add_argument("--candidate", type=Path, help="install an unsigned same-run CI candidate for validation only")
    parser.add_argument("--sha256", help="required digest for --candidate")
    args = parser.parse_args()
    if args.candidate:
        if args.verify_installed or not args.sha256:
            parser.error("--candidate requires --sha256 and excludes --verify-installed")
        manifest, _ = read_archive(args.candidate)
        cache = ROOT / ".linker-inputs-cache" / args.sha256
        if not SHA.fullmatch(args.sha256) or sha256(args.candidate) != args.sha256:
            raise ValueError("Linker-input candidate checksum mismatch")
        cache.mkdir(parents=True, exist_ok=True)
        cached = cache / archive_name(manifest["version"])
        shutil.copyfile(args.candidate, cached)
        install(cached, args.sha256)
    elif args.verify_installed:
        print(f"Verified linker inputs: {verify_installed()}")
    else:
        fetch()


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError) as error:
        raise SystemExit(f"Linker-input verification failed: {error}") from None
