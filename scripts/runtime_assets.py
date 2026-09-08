"""Shared deterministic archive format and strict runtime inventory validation."""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import re
import tarfile
from pathlib import Path, PurePosixPath

from vendor_zig_runtime import TARGET_ARTIFACTS, DARWIN_SYSROOT

ROOT = Path(__file__).resolve().parents[1]
REPO = "lukewilliamboswell/roc-platform-template-go"
WORKFLOW = f"{REPO}/.github/workflows/release-runtime.yml"
MANIFEST = "runtime/manifest.json"
SOURCES = "runtime/sources.json"
NOTICES = ("musl-COPYRIGHT", "zig-LICENSE", "mingw-w64-COPYING")
RUNTIME_PATHS = frozenset(
    f"targets/{target}/{name}"
    for target, names in TARGET_ARTIFACTS.items() for name in names
) | {f"targets/{DARWIN_SYSROOT.as_posix()}"}
PAYLOAD_PATHS = RUNTIME_PATHS | {SOURCES} | {f"runtime/licenses/{n}" for n in NOTICES}
MAX_ARCHIVE_BYTES = 128 * 1024 * 1024
MAX_UNPACKED_BYTES = 256 * 1024 * 1024
VERSION = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)")
SHA = re.compile(r"[0-9a-f]{64}")
COMMIT = re.compile(r"[0-9a-f]{40}")


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def archive_name(version: str) -> str:
    if VERSION.fullmatch(version) is None:
        raise ValueError("Runtime version must be an exact numeric X.Y.Z")
    return f"roc-go-runtimes-{version}.tar.gz"


def safe_path(name: str) -> bool:
    path = PurePosixPath(name)
    return (bool(name) and not path.is_absolute() and name == path.as_posix()
            and all(re.fullmatch(r"[A-Za-z0-9_.-]+", p) and p not in {".", ".."}
                    for p in path.parts))


def write_archive(destination: Path, files: dict[str, bytes]) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as output:
        with gzip.GzipFile(filename="", fileobj=output, mode="wb", mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w", format=tarfile.USTAR_FORMAT) as tar:
                for name, data in sorted(files.items()):
                    info = tarfile.TarInfo(name)
                    info.size = len(data)
                    info.mode = 0o644
                    info.mtime = 0
                    tar.addfile(info, io.BytesIO(data))


def read_archive(archive: Path) -> tuple[dict, dict[str, bytes]]:
    if archive.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError("Runtime archive exceeds size limit")
    files = {}
    total = 0
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar:
            if (not member.isfile() or not safe_path(member.name)
                    or member.name in files or member.name not in PAYLOAD_PATHS | {MANIFEST}):
                raise ValueError(f"Unexpected or unsafe archive entry: {member.name}")
            total += member.size
            if total > MAX_UNPACKED_BYTES:
                raise ValueError("Runtime archive exceeds unpacked size limit")
            stream = tar.extractfile(member)
            if stream is None:
                raise ValueError("Missing archive entry data")
            files[member.name] = stream.read()
    if set(files) != PAYLOAD_PATHS | {MANIFEST}:
        raise ValueError("Runtime archive inventory is incomplete")
    manifest = json.loads(files[MANIFEST])
    if (manifest.get("format") != 1 or not VERSION.fullmatch(manifest.get("version", ""))
            or not COMMIT.fullmatch(manifest.get("source_commit", ""))
            or set(manifest.get("files", {})) != PAYLOAD_PATHS):
        raise ValueError("Invalid runtime manifest")
    for name in PAYLOAD_PATHS:
        if hashlib.sha256(files[name]).hexdigest() != manifest["files"][name]:
            raise ValueError(f"Runtime checksum mismatch: {name}")
    return manifest, files


def component_for(path: str) -> str:
    if path.endswith("libSystem.tbd"):
        return "darwin"
    name = PurePosixPath(path).name
    if name in {"libzigc.a", "libcompiler_rt.a", "zigc.lib", "compiler_rt.lib"}:
        return "zig"
    return "mingw" if "mingw/" in path else "musl"
