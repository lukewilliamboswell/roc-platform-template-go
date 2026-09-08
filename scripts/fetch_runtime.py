#!/usr/bin/env python3
"""Fetch, authenticate, and install the locked runtime release."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import urllib.request

from runtime_assets import (ROOT, REPO, WORKFLOW, MANIFEST, RUNTIME_PATHS, PAYLOAD_PATHS,
                            SHA, COMMIT, archive_name, json_bytes, read_archive, sha256)

LOCK = ROOT / "scripts/runtime_release.json"
PROVENANCE = "https://slsa.dev/provenance/v1"
SBOM_TYPE = "https://spdx.dev/Document/v2.3"


def load_lock(path: Path = LOCK) -> dict:
    lock = json.loads(path.read_text())
    expected = {"format", "version", "sha256", "source_commit", "signer_digest", "repository", "signer_workflow", "source_ref"}
    if (set(lock) != expected or lock["format"] != 1 or lock["repository"] != REPO
            or lock["signer_workflow"] != WORKFLOW or lock["source_ref"] != "refs/heads/main"
            or not SHA.fullmatch(lock["sha256"]) or not COMMIT.fullmatch(lock["source_commit"])
            or not COMMIT.fullmatch(lock["signer_digest"])):
        raise ValueError("Invalid runtime release lock")
    archive_name(lock["version"])
    return lock


def download(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "roc-go-runtime-fetch"})
    temporary = destination.with_suffix(destination.suffix + ".partial")
    try:
        with urllib.request.urlopen(request, timeout=120) as response, temporary.open("wb") as output:
            shutil.copyfileobj(response, output)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def verify_attestation(artifact: Path, bundle: Path, lock: dict, predicate: str) -> list:
    command = ["gh", "attestation", "verify", str(artifact), "--bundle", str(bundle),
               "--repo", lock["repository"], "--signer-workflow", lock["signer_workflow"],
               "--source-ref", lock["source_ref"], "--source-digest", lock["source_commit"],
               "--signer-digest", lock["signer_digest"], "--deny-self-hosted-runners",
               "--predicate-type", predicate, "--format", "json"]
    result = subprocess.run(command, check=True, stdout=subprocess.PIPE, text=True)
    verified = json.loads(result.stdout)
    if not isinstance(verified, list) or not verified:
        raise ValueError("No verified runtime attestation")
    return verified


def verify_release(directory: Path, lock: dict) -> Path:
    archive = directory / archive_name(lock["version"])
    if sha256(archive) != lock["sha256"]:
        raise ValueError("Runtime release archive checksum mismatch")
    provenance = directory / "provenance.sigstore.json"
    sbom = directory / "runtime.spdx.json"
    verify_attestation(archive, provenance, lock, PROVENANCE)
    verify_attestation(sbom, provenance, lock, PROVENANCE)
    verified = verify_attestation(archive, directory / "sbom.sigstore.json", lock, SBOM_TYPE)
    document = json.loads(sbom.read_text())
    if not any(item["verificationResult"]["statement"]["predicate"] == document for item in verified):
        raise ValueError("Published SBOM differs from the signed predicate")
    manifest, files = read_archive(archive)
    if manifest["source_commit"] != lock["source_commit"] or manifest["version"] != lock["version"]:
        raise ValueError("Archive metadata differs from the runtime release lock")
    expected = {f"./{path}": hashlib.sha256(data).hexdigest() for path, data in files.items()}
    actual = {file["fileName"]: next(c["checksumValue"] for c in file["checksums"] if c["algorithm"] == "SHA256") for file in document["files"]}
    if actual != expected or len(document["files"]) != len(expected):
        raise ValueError("SBOM file inventory differs from archive")
    return archive


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
        raise ValueError("Runtime candidate/archive checksum mismatch")
    manifest, files = read_archive(archive)
    for name in files:
        ensure_regular(platform / name, platform)
    ensure_regular(platform / "runtime/receipt.json", platform)
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
    (platform / "runtime/receipt.json").write_bytes(json_bytes(receipt))
    print(f"Installed runtime {manifest['version']} ({digest})")


def verify_installed(platform: Path = ROOT / "platform", lock_path: Path = LOCK) -> str:
    # Explicit same-run candidate mode is used only by read-only release tests.
    candidate = os.environ.get("RUNTIME_CANDIDATE_SHA256")
    lock = None if candidate else load_lock(lock_path)
    expected_digest = candidate or lock["sha256"]
    if not SHA.fullmatch(expected_digest):
        raise ValueError("Invalid expected runtime digest")
    receipt = json.loads((platform / "runtime/receipt.json").read_text())
    manifest = json.loads((platform / MANIFEST).read_text())
    if receipt.get("sha256") != expected_digest or set(manifest.get("files", {})) != PAYLOAD_PATHS:
        raise ValueError("Installed runtime does not match the selected release")
    if lock and (manifest["source_commit"] != lock["source_commit"] or manifest["version"] != lock["version"]):
        raise ValueError("Installed runtime metadata differs from lock")
    for name, expected in manifest["files"].items():
        path = platform / name
        ensure_regular(path, platform)
        if sha256(path) != expected:
            raise ValueError(f"Installed runtime checksum mismatch: {name}")
    allowed = RUNTIME_PATHS | {"runtime/receipt.json", MANIFEST} | PAYLOAD_PATHS
    for directory in (platform / "targets", platform / "runtime"):
        for path in directory.rglob("*"):
            ensure_regular(path, platform)
            if path.is_file():
                relative = path.relative_to(platform).as_posix()
                if relative not in allowed and not (directory.name == "targets" and path.name in {"libhost.a", "libhost.h", "host.lib", "host.h"}):
                    raise ValueError(f"Unexpected installed runtime file: {relative}")
    # Compare installed metadata and bytes with the original authenticated archive
    # on every bundle, so editing the manifest/receipt cannot bless modified files.
    cache = ROOT / ".runtime-cache" / expected_digest
    archive = cache / archive_name(manifest["version"])
    if sha256(archive) != expected_digest:
        raise ValueError("Cached runtime archive checksum mismatch")
    _, original = read_archive(archive)
    for name, data in original.items():
        if (platform / name).read_bytes() != data:
            raise ValueError(f"Installed runtime differs from authenticated archive: {name}")
    return expected_digest


def fetch() -> None:
    lock = load_lock()
    cache = ROOT / ".runtime-cache" / lock["sha256"]
    cache.mkdir(parents=True, exist_ok=True)
    base = f"https://github.com/{REPO}/releases/download/runtime-v{lock['version']}"
    for name in [archive_name(lock["version"]), "runtime.spdx.json", "provenance.sigstore.json", "sbom.sigstore.json"]:
        destination = cache / name
        if not destination.exists():
            download(f"{base}/{name}", destination)
    archive = verify_release(cache, lock)
    install(archive, lock["sha256"])
    verify_installed()


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
        cache = ROOT / ".runtime-cache" / args.sha256
        if not SHA.fullmatch(args.sha256) or sha256(args.candidate) != args.sha256:
            raise ValueError("Runtime candidate checksum mismatch")
        cache.mkdir(parents=True, exist_ok=True)
        cached = cache / archive_name(manifest["version"])
        shutil.copyfile(args.candidate, cached)
        install(cached, args.sha256)
    elif args.verify_installed:
        print(f"Verified runtime: {verify_installed()}")
    else:
        fetch()


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        raise SystemExit(f"Runtime verification failed: {error}") from None
