#!/usr/bin/env python3
"""Reproduce and vendor the pinned Zig runtime and linker inputs."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import os
import re
import secrets
import shlex
import shutil
import string
import subprocess
from pathlib import Path

from canonicalize_runtime_object import canonicalize


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
PROBE = SCRIPT_DIR / "runtime_probe.c"
MANIFEST = SCRIPT_DIR / "zig_runtime.sha256"
REQUIRED_ZIG_VERSION = "0.16.0"
ARTIFACTS = ("crt1.o", "libc.a", "libzigc.a", "libcompiler_rt.a")
TARGETS = ("x64musl", "x64v1musl", "arm64musl", "arm64v1musl")
DARWIN_SYSROOT = Path("macos-sysroot/usr/lib/libSystem.tbd")


def make_work_dir() -> Path:
    # canonicalize_runtime_object uses an equal-length replacement so cache
    # paths do not perturb object hashes.
    parent = Path("/tmp")
    if os.name != "posix" or not parent.is_dir():
        raise RuntimeError("Runtime vendoring currently requires a POSIX /tmp directory")
    alphabet = string.ascii_letters + string.digits
    for _ in range(100):
        suffix = "".join(secrets.choice(alphabet) for _ in range(6))
        candidate = parent / f"roc-go-zig-runtime.{suffix}"
        try:
            candidate.mkdir()
            return candidate
        except FileExistsError:
            continue
    raise RuntimeError("Could not allocate an isolated runtime work directory")


def run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(args, check=True, **kwargs)


def locate_artifacts(trace: str) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for line in trace.splitlines():
        if not line.startswith("ld.lld "):
            continue
        for token in shlex.split(line):
            normalized = token.replace("\\", "/")
            for artifact in ARTIFACTS:
                if normalized.endswith(f"/{artifact}"):
                    result[artifact] = Path(token)
    return result


def normalize_archive(
    input_archive: Path, output_archive: Path, work_dir: Path
) -> None:
    key = f"{output_archive.parent.name}-{output_archive.name}"
    members_dir = work_dir / "archive-members" / key
    members_dir.mkdir(parents=True)
    listing = subprocess.check_output(
        ["zig", "ar", "t", str(input_archive)], text=True
    ).splitlines()
    stable_members: list[str] = []
    for index, member in enumerate(listing):
        stable_name = f"{index:04d}-{Path(member).name}"
        stable_path = members_dir / stable_name
        # Full-path matching is essential: musl includes generic and
        # architecture-specific members with identical basenames.
        with stable_path.open("wb") as stream:
            run(
                ["zig", "ar", "pP", str(input_archive), member],
                stdout=stream,
            )
        canonicalize(stable_path, work_dir)
        stable_members.append(stable_name)
    run(
        ["zig", "ar", "rcsD", str(output_archive), *stable_members],
        cwd=members_dir,
    )


def build_runtime(
    roc_target: str, zig_target: str, work_dir: Path, generated_dir: Path
) -> None:
    target_work = work_dir / roc_target
    output_dir = generated_dir / roc_target
    target_work.mkdir()
    output_dir.mkdir(parents=True)
    global_cache = target_work / "global-cache"
    local_cache = target_work / "local-cache"
    global_cache.mkdir()
    local_cache.mkdir()
    env = os.environ.copy()
    env.update(
        {
            "ZIG_GLOBAL_CACHE_DIR": str(global_cache),
            "ZIG_LOCAL_CACHE_DIR": str(local_cache),
        }
    )
    result = subprocess.run(
        [
            "zig",
            "cc",
            "-target",
            zig_target,
            "-static",
            "-O2",
            "-g0",
            "-fno-sanitize=all",
            "-v",
            str(PROBE),
            "-o",
            str(target_work / "probe"),
        ],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    trace_path = target_work / "zig-cc.trace"
    trace_path.write_text(result.stderr, encoding="utf-8")
    if result.returncode != 0:
        raise RuntimeError(f"zig cc failed for {roc_target}; trace: {trace_path}")

    discovered = locate_artifacts(result.stderr)
    missing = [name for name in ARTIFACTS if not discovered.get(name, Path()).is_file()]
    if missing:
        raise RuntimeError(
            f"Could not locate {', '.join(missing)} for {roc_target}; trace: {trace_path}"
        )

    snapshots: dict[str, Path] = {}
    for name, source in discovered.items():
        snapshot = target_work / f"raw-{name}"
        shutil.copy2(source, snapshot)
        snapshots[name] = snapshot
    shutil.copy2(snapshots["crt1.o"], output_dir / "crt1.o")
    for name in ARTIFACTS[1:]:
        normalize_archive(snapshots[name], output_dir / name, work_dir)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def generated_manifest(generated_dir: Path) -> str:
    lines = []
    for target in TARGETS:
        for artifact in ARTIFACTS:
            relative = Path(target) / artifact
            lines.append(f"{digest(generated_dir / relative)}  {relative.as_posix()}")
    lines.append(
        f"{digest(generated_dir / DARWIN_SYSROOT)}  {DARWIN_SYSROOT.as_posix()}"
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="rebuild and byte-compare instead of replacing checked-in files",
    )
    parser.add_argument("--keep-work", action="store_true")
    args = parser.parse_args()

    version = subprocess.check_output(["zig", "version"], text=True).strip()
    if version != REQUIRED_ZIG_VERSION:
        raise SystemExit(
            f"Zig {REQUIRED_ZIG_VERSION} is required; found {version}"
        )

    work_dir = make_work_dir()
    keep_work = args.keep_work or os.environ.get("KEEP_RUNTIME_WORK") == "1"
    try:
        generated_dir = work_dir / "generated"
        generated_dir.mkdir()
        build_runtime("x64musl", "x86_64-linux-musl", work_dir, generated_dir)
        build_runtime("arm64musl", "aarch64-linux-musl", work_dir, generated_dir)

        for source, destination in (
            ("x64musl", "x64v1musl"),
            ("arm64musl", "arm64v1musl"),
        ):
            shutil.copytree(generated_dir / source, generated_dir / destination)

        zig_environment = subprocess.check_output(["zig", "env"], text=True)
        lib_dir_match = re.search(
            r'^\s*\.lib_dir = "([^"]+)",$', zig_environment, re.MULTILINE
        )
        if lib_dir_match is None:
            raise RuntimeError("zig env did not report lib_dir")
        darwin_source = (
            Path(lib_dir_match.group(1)) / "libc" / "darwin" / "libSystem.tbd"
        )
        if not darwin_source.is_file():
            raise RuntimeError(
                f"Zig Darwin interface stub is missing: {darwin_source}"
            )
        darwin_generated = generated_dir / DARWIN_SYSROOT
        darwin_generated.parent.mkdir(parents=True)
        shutil.copy2(darwin_source, darwin_generated)

        actual_manifest = generated_manifest(generated_dir)
        expected_manifest = MANIFEST.read_text(encoding="utf-8")
        if actual_manifest != expected_manifest:
            difference = "".join(
                difflib.unified_diff(
                    expected_manifest.splitlines(keepends=True),
                    actual_manifest.splitlines(keepends=True),
                    fromfile=str(MANIFEST),
                    tofile="generated.sha256",
                )
            )
            raise RuntimeError(f"Generated runtime checksums changed:\n{difference}")

        for target in TARGETS:
            destination_dir = ROOT / "platform" / "targets" / target
            destination_dir.mkdir(parents=True, exist_ok=True)
            for artifact in ARTIFACTS:
                source = generated_dir / target / artifact
                destination = destination_dir / artifact
                if args.check:
                    if source.read_bytes() != destination.read_bytes():
                        raise RuntimeError(f"Checked-in artifact differs: {destination}")
                else:
                    shutil.copy2(source, destination)
        darwin_destination = ROOT / "platform" / "targets" / DARWIN_SYSROOT
        if args.check:
            if darwin_generated.read_bytes() != darwin_destination.read_bytes():
                raise RuntimeError(
                    f"Checked-in artifact differs: {darwin_destination}"
                )
        else:
            darwin_destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(darwin_generated, darwin_destination)
        if args.check:
            print("Zig runtime artifacts are reproducible and match checked-in copies.")
        else:
            print(f"Vendored Zig {REQUIRED_ZIG_VERSION} runtime artifacts.")
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error)) from None
    finally:
        if keep_work:
            print(f"Kept runtime work directory: {work_dir}")
        else:
            shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
