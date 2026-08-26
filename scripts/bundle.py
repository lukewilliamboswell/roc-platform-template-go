#!/usr/bin/env python3
"""Build a complete Roc platform bundle from the current checkout."""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLATFORM = ROOT / "platform"
MINGW_INPUTS = (
    "crt2.obj",
    "libhost.a",
    "libmingw32.lib",
    "zigc.lib",
    "compiler_rt.lib",
    "api-ms-win-crt-conio-l1-1-0.lib",
    "api-ms-win-crt-convert-l1-1-0.lib",
    "api-ms-win-crt-environment-l1-1-0.lib",
    "api-ms-win-crt-filesystem-l1-1-0.lib",
    "api-ms-win-crt-heap-l1-1-0.lib",
    "api-ms-win-crt-locale-l1-1-0.lib",
    "api-ms-win-crt-math-l1-1-0.lib",
    "api-ms-win-crt-multibyte-l1-1-0.lib",
    "api-ms-win-crt-private-l1-1-0.lib",
    "api-ms-win-crt-process-l1-1-0.lib",
    "api-ms-win-crt-runtime-l1-1-0.lib",
    "api-ms-win-crt-stdio-l1-1-0.lib",
    "api-ms-win-crt-string-l1-1-0.lib",
    "api-ms-win-crt-time-l1-1-0.lib",
    "api-ms-win-crt-utility-l1-1-0.lib",
    "advapi32.lib",
    "kernel32.lib",
    "ntdll.lib",
    "shell32.lib",
    "user32.lib",
)
TARGET_INPUTS = {
    "x64mac": ("libhost.a",),
    "arm64mac": ("libhost.a",),
    "x64musl": ("crt1.o", "libhost.a", "libc.a", "libzigc.a", "libcompiler_rt.a"),
    "x64v1musl": ("crt1.o", "libhost.a", "libc.a", "libzigc.a", "libcompiler_rt.a"),
    "arm64musl": ("crt1.o", "libhost.a", "libc.a", "libzigc.a", "libcompiler_rt.a"),
    "arm64v1musl": ("crt1.o", "libhost.a", "libc.a", "libzigc.a", "libcompiler_rt.a"),
    "x64mingw": MINGW_INPUTS,
    "x64v1mingw": MINGW_INPUTS,
    "arm64mingw": MINGW_INPUTS,
    "arm64v1mingw": MINGW_INPUTS,
}
PLATFORM_SUPPORT_INPUTS = ("targets/macos-sysroot/usr/lib/libSystem.tbd",)


def bundle_inputs() -> list[Path]:
    inputs = sorted(PLATFORM.glob("*.roc"))
    missing: list[Path] = []
    for target, filenames in TARGET_INPUTS.items():
        for filename in filenames:
            path = PLATFORM / "targets" / target / filename
            if not path.is_file():
                missing.append(path)
            inputs.append(path)
    for relative in PLATFORM_SUPPORT_INPUTS:
        path = PLATFORM / relative
        if not path.is_file():
            missing.append(path)
        inputs.append(path)
    if missing:
        formatted = "\n".join(f"  - {path.relative_to(ROOT)}" for path in missing)
        raise RuntimeError(
            "Platform bundle inputs are missing. Run scripts/build.py --all first:\n"
            f"{formatted}"
        )
    return inputs


def bundle_platform(output_dir: Path) -> Path:
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    relative_inputs = [str(path.relative_to(PLATFORM)) for path in bundle_inputs()]
    result = subprocess.run(
        [
            "roc",
            "bundle",
            *relative_inputs,
            "--output-dir",
            str(output_dir),
        ],
        cwd=PLATFORM,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    print(result.stdout, end="")
    if result.returncode != 0:
        raise RuntimeError(f"roc bundle exited with {result.returncode}")

    matches = re.findall(r"^Created:\s+(.+)$", result.stdout, re.MULTILINE)
    if len(matches) != 1:
        raise RuntimeError("Could not identify the bundle path in roc bundle output")
    bundle = Path(matches[0])
    if not bundle.is_absolute():
        bundle = (PLATFORM / bundle).resolve()
    if not bundle.is_file():
        raise RuntimeError(f"roc bundle reported a missing output: {bundle}")
    return bundle


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    try:
        bundle = bundle_platform(args.output_dir)
    except (OSError, RuntimeError) as error:
        raise SystemExit(str(error)) from None
    print(f"Bundle ready: {bundle}")


if __name__ == "__main__":
    main()
