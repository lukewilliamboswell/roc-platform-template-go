#!/usr/bin/env python3
"""Cross-compile the Go platform host for Roc's supported targets."""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_ZIG_VERSION = "0.16.0"
REQUIRED_GO_MINOR = "go1.26"


@dataclass(frozen=True)
class Target:
    goos: str
    goarch: str
    zig_target: str
    filename: str = "libhost.a"


TARGETS = {
    "x64mac": Target("darwin", "amd64", "x86_64-macos"),
    "arm64mac": Target("darwin", "arm64", "aarch64-macos"),
    "x64musl": Target("linux", "amd64", "x86_64-linux-musl"),
    "x64v1musl": Target("linux", "amd64", "x86_64-linux-musl"),
    "arm64musl": Target("linux", "arm64", "aarch64-linux-musl"),
    "arm64v1musl": Target("linux", "arm64", "aarch64-linux-musl"),
    "x64mingw": Target("windows", "amd64", "x86_64-windows-gnu"),
    "x64v1mingw": Target("windows", "amd64", "x86_64-windows-gnu"),
    "arm64mingw": Target("windows", "arm64", "aarch64-windows-gnu"),
    "arm64v1mingw": Target("windows", "arm64", "aarch64-windows-gnu"),
}


def output(args: list[str]) -> str:
    return subprocess.check_output(args, text=True).strip()


def require_toolchains() -> None:
    zig_version = output(["zig", "version"])
    go_version = output(["go", "env", "GOVERSION"])
    if zig_version != REQUIRED_ZIG_VERSION:
        raise SystemExit(
            f"Zig {REQUIRED_ZIG_VERSION} is required; found {zig_version}"
        )
    if not go_version.startswith(f"{REQUIRED_GO_MINOR}."):
        raise SystemExit(
            f"Go {REQUIRED_GO_MINOR}.x is required; found {go_version}"
        )


def native_target() -> str:
    machine = platform.machine().lower()
    system = platform.system()
    if system == "Darwin":
        return "arm64mac" if machine in {"arm64", "aarch64"} else "x64mac"
    if system == "Linux":
        return "arm64musl" if machine in {"arm64", "aarch64"} else "x64musl"
    if system == "Windows":
        return "arm64mingw" if machine in {"arm64", "aarch64"} else "x64mingw"
    raise SystemExit(f"Unsupported host platform: {system} {machine}")


def build_target(name: str) -> None:
    target = TARGETS[name]
    cflags = "-O2 -g0"
    if target.goos == "windows":
        cflags += " -fno-sanitize=all"
    print(
        f"Building Go host for {name} "
        f"({target.goos}/{target.goarch} via {target.zig_target})...",
        flush=True,
    )
    env = os.environ.copy()
    env.update(
        {
            "GOOS": target.goos,
            "GOARCH": target.goarch,
            "GOAMD64": "v1",
            "GOARM64": "v8.0",
            "CGO_ENABLED": "1",
            "CC": f"zig cc -target {target.zig_target}",
            "CGO_CFLAGS": cflags,
        }
    )
    with tempfile.TemporaryDirectory(prefix=f"roc-go-host-{name}-") as temporary:
        temporary_output = Path(temporary) / target.filename
        subprocess.run(
            [
                "go",
                "build",
                "-C",
                str(ROOT / "host"),
                "-buildmode=c-archive",
                "-buildvcs=false",
                "-trimpath",
                "-ldflags=-s -w",
                "-tags",
                "netgo,osusergo",
                "-o",
                str(temporary_output),
            ],
            env=env,
            check=True,
        )
        if target.goos == "windows":
            # Go's ARM64 c-archive omits the COFF archive symbol index that
            # lld-link needs in order to pull the exported host callbacks.
            subprocess.run(["zig", "ar", "s", str(temporary_output)], check=True)
        destination = ROOT / "platform" / "targets" / name / target.filename
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(temporary_output, destination)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("targets", nargs="*", choices=TARGETS)
    parser.add_argument(
        "--all", action="store_true", help="build every supported Roc target"
    )
    args = parser.parse_args()
    if args.all and args.targets:
        parser.error("--all cannot be combined with explicit targets")

    require_toolchains()
    selected = list(TARGETS) if args.all else args.targets or [native_target()]
    for name in selected:
        build_target(name)
    print(f"Built Go host libraries for: {' '.join(selected)}")


if __name__ == "__main__":
    main()
