#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import functools
import hashlib
import http.server
import json
import os
import platform
import re
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import threading
import urllib.parse
from pathlib import Path, PurePosixPath

from bundle import bundle_platform


ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "scripts" / "test_spec.json"
STAGES = ("check", "test", "build", "run")
SUPPORTED_TARGETS = (
    "x64mac",
    "arm64mac",
    "x64musl",
    "x64v1musl",
    "arm64musl",
    "arm64v1musl",
    "x64mingw",
    "x64v1mingw",
    "arm64mingw",
    "arm64v1mingw",
)
TARGET_PLATFORMS = {
    "x64mac": "macos",
    "arm64mac": "macos",
    "x64musl": "linux",
    "x64v1musl": "linux",
    "arm64musl": "linux",
    "arm64v1musl": "linux",
    "x64mingw": "windows",
    "x64v1mingw": "windows",
    "arm64mingw": "windows",
    "arm64v1mingw": "windows",
}
KNOWN_PLATFORMS = frozenset({"linux", "macos", "windows"})
WINDOWS_MACHINE_TYPES = {
    "x64mingw": 0x8664,
    "x64v1mingw": 0x8664,
    "arm64mingw": 0xAA64,
    "arm64v1mingw": 0xAA64,
}
APP_KEYS = frozenset(
    {"path", "enabled", "stages", "skip_reasons", "platforms", "cases", "build_args"}
)
CASE_KEYS = frozenset(
    {
        "name",
        "enabled",
        "skip_reasons",
        "platforms",
        "args",
        "stdin",
        "stdin_hex",
        "temp_cwd",
        "cwd",
        "timeout",
        "exit_code",
        "env",
        "unset_env",
        "equals",
        "contains",
        "regex",
        "stdout_equals",
        "stdout_contains",
        "stdout_regex",
        "stderr_equals",
        "stderr_contains",
        "stderr_regex",
    }
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")


class TestFailure(Exception):
    pass


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


@contextlib.contextmanager
def serve_bundle(bundle: Path):
    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

    handler = functools.partial(QuietHandler, directory=str(bundle.parent))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    url = f"http://{host}:{port}/{urllib.parse.quote(bundle.name)}"
    print(f"Serving fresh platform bundle: {url}")
    try:
        yield url
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@contextlib.contextmanager
def rewrite_examples_for_bundle(examples_dir: Path, bundle_url: str):
    pattern = re.compile(r'\bplatform\s+"[^"]+"')
    with tempfile.TemporaryDirectory(prefix="platform-go-bundled-examples-") as temporary:
        output_dir = Path(temporary) / "examples"
        for source in sorted(examples_dir.rglob("*.roc")):
            relative = source.relative_to(examples_dir)
            destination = output_dir / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            contents = source.read_text(encoding="utf-8")
            rewritten, count = pattern.subn(
                f'platform "{bundle_url}"', contents, count=1
            )
            if count != 1:
                raise TestFailure(f"Expected one platform dependency in {source}")
            destination.write_text(rewritten, encoding="utf-8")
        yield output_dir


def current_platform() -> str:
    return {
        "Darwin": "macos",
        "Linux": "linux",
        "Windows": "windows",
    }.get(platform.system(), platform.system().lower())


def command_text(args: list[str]) -> str:
    return subprocess.list2cmdline(args) if os.name == "nt" else " ".join(args)


def expand(value: str, source: Path) -> str:
    return value.format(root=ROOT, source=source, source_dir=source.parent)


def require_string_list(owner: str, value: object) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise TestFailure(f"{owner} must be an array of strings")
    return value


def require_skip_reason(owner: str, item: dict[str, object], key: str) -> None:
    reasons = item.get("skip_reasons", {})
    if not isinstance(reasons, dict):
        raise TestFailure(f"{owner}: skip_reasons must be an object")
    entry = reasons.get(key)
    if not isinstance(entry, dict):
        raise TestFailure(
            f"{owner}: disabling {key} requires skip_reasons.{key}"
        )
    reason = entry.get("reason")
    issue = entry.get("issue")
    if not isinstance(reason, str) or not reason.strip():
        raise TestFailure(f"{owner}: skip_reasons.{key}.reason must be non-empty")
    if not isinstance(issue, str) or re.fullmatch(
        r"https://github\.com/[^/]+/[^/]+/issues/[0-9]+(?:#[^\s]+)?", issue
    ) is None:
        raise TestFailure(
            f"{owner}: skip_reasons.{key}.issue must be a GitHub issue URL"
        )


def validate_skip_reasons(owner: str, item: dict[str, object]) -> None:
    if item.get("enabled", True) is False:
        require_skip_reason(owner, item, "enabled")
    stages = item.get("stages", {})
    if isinstance(stages, dict):
        for stage, enabled in stages.items():
            if enabled is False:
                require_skip_reason(owner, item, str(stage))
    for stage in STAGES:
        if item.get(stage) is False:
            require_skip_reason(owner, item, stage)
    platforms = item.get("platforms", {})
    if isinstance(platforms, dict):
        for platform_name, override in platforms.items():
            if isinstance(override, dict):
                validate_skip_reasons(f"{owner}.platforms.{platform_name}", override)


def reject_unknown_keys(
    owner: str, item: dict[str, object], allowed: frozenset[str]
) -> None:
    unknown = set(item) - allowed
    if unknown:
        raise TestFailure(f"{owner}: unknown fields: {', '.join(sorted(unknown))}")


def validate_platforms(
    owner: str, item: dict[str, object], *, allowed_controls: frozenset[str]
) -> None:
    platforms = item.get("platforms", {})
    if not isinstance(platforms, dict):
        raise TestFailure(f"{owner}: platforms must be an object")
    unknown_platforms = set(platforms) - KNOWN_PLATFORMS
    if unknown_platforms:
        raise TestFailure(
            f"{owner}: unknown platforms: {', '.join(sorted(unknown_platforms))}"
        )
    for platform_name, override in platforms.items():
        if not isinstance(override, dict):
            raise TestFailure(f"{owner}.platforms.{platform_name} must be an object")
        reject_unknown_keys(
            f"{owner}.platforms.{platform_name}",
            override,
            allowed_controls | frozenset({"skip_reasons"}),
        )


def run_cases(app: dict[str, object]) -> list[dict[str, object]]:
    cases = app.get("cases", [])
    if not isinstance(cases, list) or not all(isinstance(case, dict) for case in cases):
        raise TestFailure(f"{app['path']}: cases must be an array of objects")
    names = [case.get("name") for case in cases]
    if not all(isinstance(name, str) and name for name in names):
        raise TestFailure(f"{app['path']}: every case needs a non-empty string name")
    if len(names) != len(set(names)):
        raise TestFailure(f"{app['path']}: case names must be unique")
    return cases


def platform_override(
    item: dict[str, object], platform_name: str | None = None
) -> dict[str, object]:
    platforms = item.get("platforms", {})
    if not isinstance(platforms, dict):
        raise TestFailure("platforms must be an object")
    selected_platform = platform_name or current_platform()
    override = platforms.get(selected_platform, {})
    if not isinstance(override, dict):
        raise TestFailure(f"platforms.{selected_platform} must be an object")
    return override


def stage_enabled(
    defaults: dict[str, bool],
    app: dict[str, object],
    stage: str,
    platform_name: str | None = None,
) -> bool:
    enabled = app.get("enabled", True)
    if not isinstance(enabled, bool):
        raise TestFailure(f"{app['path']}: enabled must be a boolean")

    stage_value: object = defaults[stage]
    overrides = app.get("stages", {})
    if not isinstance(overrides, dict):
        raise TestFailure(f"{app['path']}: stages must be an object")
    if stage in overrides:
        stage_value = overrides[stage]

    selected_platform = platform_name or current_platform()
    platform_values = platform_override(app, selected_platform)
    platform_enabled = platform_values.get("enabled", True)
    if not isinstance(platform_enabled, bool):
        raise TestFailure(
            f"{app['path']}: platforms.{selected_platform}.enabled must be a boolean"
        )
    if stage in platform_values:
        stage_value = platform_values[stage]
    if not isinstance(stage_value, bool):
        raise TestFailure(f"{app['path']}: {stage} must be a boolean")
    return enabled and platform_enabled and stage_value


def case_enabled(source: Path, case: dict[str, object]) -> bool:
    enabled = case.get("enabled", True)
    if not isinstance(enabled, bool):
        raise TestFailure(f"{source} [{case.get('name')}]: enabled must be a boolean")
    override = platform_override(case)
    platform_enabled = override.get("enabled", True)
    if not isinstance(platform_enabled, bool):
        raise TestFailure(
            f"{source} [{case.get('name')}]: "
            f"platforms.{current_platform()}.enabled must be a boolean"
        )
    return enabled and platform_enabled


def load_spec(examples_dir: Path) -> tuple[dict[str, bool], list[dict[str, object]]]:
    data = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    defaults = data.get("stages")
    apps = data.get("apps")
    if not isinstance(defaults, dict) or set(defaults) != set(STAGES):
        raise TestFailure(f"{SPEC_PATH}: stages must define {', '.join(STAGES)}")
    if not all(isinstance(defaults[name], bool) for name in STAGES):
        raise TestFailure(f"{SPEC_PATH}: all stage defaults must be booleans")
    if not all(defaults[name] for name in STAGES):
        raise TestFailure(f"{SPEC_PATH}: every stage must be enabled by default")
    if not isinstance(apps, list) or not all(isinstance(app, dict) for app in apps):
        raise TestFailure(f"{SPEC_PATH}: apps must be an array of objects")

    paths = [app.get("path") for app in apps]
    if not all(isinstance(path, str) for path in paths) or len(paths) != len(set(paths)):
        raise TestFailure(f"{SPEC_PATH}: every app needs a unique string path")

    discovered = {
        (Path("examples") / path.relative_to(examples_dir)).as_posix()
        for path in examples_dir.rglob("*.roc")
    }
    specified = set(paths)
    if discovered != specified:
        missing = sorted(discovered - specified)
        extra = sorted(specified - discovered)
        raise TestFailure(f"Test spec mismatch; missing={missing}, extra={extra}")

    for app in apps:
        reject_unknown_keys(str(app.get("path", "<missing path>")), app, APP_KEYS)
        stages = app.get("stages", {})
        if not isinstance(stages, dict):
            raise TestFailure(f"{app['path']}: stages must be an object")
        unknown_stages = set(stages) - set(STAGES)
        if unknown_stages:
            raise TestFailure(
                f"{app['path']}: unknown stages: {', '.join(sorted(unknown_stages))}"
            )
        if not all(isinstance(value, bool) for value in stages.values()):
            raise TestFailure(f"{app['path']}: stage overrides must be booleans")
        validate_platforms(
            str(app["path"]),
            app,
            allowed_controls=frozenset({"enabled", *STAGES}),
        )
        validate_skip_reasons(str(app["path"]), app)
        if "run" in app:
            raise TestFailure(f"{app['path']}: use cases; singular run is not supported")
        cases = run_cases(app)
        for case in cases:
            owner = f"{app['path']} [{case.get('name')}]"
            reject_unknown_keys(owner, case, CASE_KEYS)
            validate_platforms(
                owner, case, allowed_controls=frozenset({"enabled"})
            )
            validate_skip_reasons(owner, case)
        if defaults["run"] and app.get("enabled", True) and not cases:
            raise TestFailure(f"{app['path']}: run is enabled but cases is empty")
    return defaults, apps


def source_path(app: dict[str, object], examples_dir: Path) -> Path:
    relative = Path(str(app["path"]))
    if not relative.parts or relative.parts[0] != "examples":
        raise TestFailure(f"{app['path']}: paths must be relative to examples/")
    return examples_dir.joinpath(*relative.parts[1:])


def print_output(stdout: str, stderr: str) -> None:
    if stdout:
        print(stdout, end="" if stdout.endswith("\n") else "\n")
    if stderr:
        print(stderr, end="" if stderr.endswith("\n") else "\n", file=sys.stderr)


def run_process(
    args: list[str],
    *,
    cwd: Path = ROOT,
    env: dict[str, str] | None = None,
    stdin: bytes | None = None,
    timeout: float = 30,
) -> subprocess.CompletedProcess[bytes]:
    print(f"+ {command_text(args)}", flush=True)
    try:
        return subprocess.run(
            args,
            cwd=cwd,
            env=env,
            input=stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise TestFailure(f"Timed out after {timeout:g}s: {command_text(args)}") from error


def decode(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


def require_success(
    result: subprocess.CompletedProcess[bytes], description: str, *, verbose: bool
) -> None:
    stdout = decode(result.stdout)
    stderr = decode(result.stderr)
    if result.returncode != 0:
        print_output(stdout, stderr)
        raise TestFailure(f"{description}: exited with {result.returncode}")
    if verbose:
        print_output(stdout, stderr)


def verify_text(
    source: Path,
    case_name: str,
    stream: str,
    output: str,
    equals: object,
    contains: object,
    regexes: object,
) -> None:
    normalized = output.replace("\r\n", "\n").replace("\r", "\n")
    if "[ROC CRASHED]" in normalized:
        raise TestFailure(f"{source} [{case_name}]: runtime crash\n{normalized}")
    if equals is not None:
        if not isinstance(equals, str):
            raise TestFailure(f"{source} [{case_name}] {stream}_equals must be a string")
        expected = equals.replace("\r\n", "\n").replace("\r", "\n")
        if normalized != expected:
            raise TestFailure(
                f"{source} [{case_name}]: {stream} output differs"
                f"\n--- expected ---\n{expected}"
                f"\n--- actual ---\n{normalized}"
            )
    expected_values = require_string_list(f"{source} [{case_name}] {stream}_contains", contains)
    patterns = require_string_list(f"{source} [{case_name}] {stream}_regex", regexes)
    for expected in expected_values:
        if expected not in normalized:
            raise TestFailure(
                f"{source} [{case_name}]: missing {stream} output {expected!r}"
                f"\n--- {stream} ---\n{normalized}"
            )
    for pattern_value in patterns:
        if re.search(pattern_value, normalized, re.MULTILINE) is None:
            raise TestFailure(
                f"{source} [{case_name}]: {stream} did not match {pattern_value!r}"
                f"\n--- {stream} ---\n{normalized}"
            )


def verify_exact_text(
    source: Path,
    case_name: str,
    stream: str,
    output: str,
    expected: object,
) -> None:
    if expected is None:
        return
    if not isinstance(expected, str):
        raise TestFailure(
            f"{source} [{case_name}] {stream}_equals must be a string"
        )
    normalized = output.replace("\r\n", "\n").replace("\r", "\n")
    if normalized != expected:
        raise TestFailure(
            f"{source} [{case_name}]: unexpected {stream} output"
            f"\n--- expected {stream} ---\n{expected}"
            f"\n--- actual {stream} ---\n{normalized}"
        )


def verify_output(
    source: Path, case_name: str, stdout: str, stderr: str, case: dict[str, object]
) -> None:
    verify_text(
        source,
        case_name,
        "combined",
        stdout + stderr,
        case.get("equals"),
        case.get("contains", []),
        case.get("regex", []),
    )
    verify_text(
        source,
        case_name,
        "stdout",
        stdout,
        case.get("stdout_equals"),
        case.get("stdout_contains", []),
        case.get("stdout_regex", []),
    )
    verify_text(
        source,
        case_name,
        "stderr",
        stderr,
        case.get("stderr_equals"),
        case.get("stderr_contains", []),
        case.get("stderr_regex", []),
    )
    verify_exact_text(
        source,
        case_name,
        "stdout",
        stdout,
        case.get("stdout_equals"),
    )
    verify_exact_text(
        source,
        case_name,
        "stderr",
        stderr,
        case.get("stderr_equals"),
    )


def make_environment(source: Path, case: dict[str, object]) -> dict[str, str]:
    env = os.environ.copy()
    unset_env = require_string_list(
        f"{source} [{case['name']}] unset_env", case.get("unset_env", [])
    )
    for name in unset_env:
        env.pop(name, None)
    values = case.get("env", {})
    if not isinstance(values, dict):
        raise TestFailure(f"{source} [{case['name']}]: env must be an object")
    for name, value in values.items():
        if not isinstance(name, str) or not isinstance(value, str):
            raise TestFailure(f"{source} [{case['name']}]: env values must be strings")
        env[name] = expand(value, source)
    return env


def run_case(
    source: Path, binary: Path, case: dict[str, object], *, verbose: bool
) -> None:
    case_name = str(case["name"])
    print(f"\n--- {display_path(source)} [{case_name}] ---")
    case_args = require_string_list(
        f"{source} [{case_name}] args", case.get("args", [])
    )
    args = [str(binary.resolve()), *(expand(value, source) for value in case_args)]
    if "stdin_hex" in case:
        try:
            stdin = bytes.fromhex(str(case["stdin_hex"]))
        except ValueError as error:
            raise TestFailure(f"{source} [{case_name}]: invalid stdin_hex") from error
    else:
        stdin_value = case.get("stdin", "")
        if not isinstance(stdin_value, str):
            raise TestFailure(f"{source} [{case_name}]: stdin must be a string")
        stdin = stdin_value.encode()

    temporary_cwd = (
        tempfile.TemporaryDirectory(prefix="platform-go-case-")
        if case.get("temp_cwd")
        else None
    )
    cwd = (
        Path(temporary_cwd.name)
        if temporary_cwd
        else Path(expand(str(case.get("cwd", "{root}")), source))
    )
    try:
        result = run_process(
            args,
            cwd=cwd,
            env=make_environment(source, case),
            stdin=stdin,
            timeout=float(case.get("timeout", 10)),
        )
    finally:
        if temporary_cwd:
            temporary_cwd.cleanup()

    stdout = decode(result.stdout)
    stderr = decode(result.stderr)
    expected_exit = case.get("exit_code", 0)
    if not isinstance(expected_exit, int):
        raise TestFailure(f"{source} [{case_name}]: exit_code must be an integer")
    if verbose or result.returncode != expected_exit:
        print_output(stdout, stderr)
    if result.returncode != expected_exit:
        raise TestFailure(
            f"{source} [{case_name}]: exited with {result.returncode}, expected {expected_exit}"
        )
    verify_output(source, case_name, stdout, stderr, case)
    print(f"PASS run: {source.name} [{case_name}]")


def binary_relative(app: dict[str, object], *, windows: bool) -> Path:
    relative = Path(str(app["path"])).relative_to("examples")
    return relative.with_suffix(".exe" if windows else "")


def build_app(
    source: Path,
    app: dict[str, object],
    binary: Path,
    *,
    target: str | None,
    verbose: bool,
) -> None:
    binary.parent.mkdir(parents=True, exist_ok=True)
    build_args = require_string_list(
        f"{source} build_args", app.get("build_args", [])
    )
    args = ["roc", "build", str(source), f"--output={binary}"]
    if target is not None:
        args.append(f"--target={target}")
    args.extend(build_args)
    result = run_process(args, timeout=120)
    require_success(result, f"build {source} for {target or 'native'}", verbose=verbose)
    print(f"PASS build: {source.name} [{target or 'native'}]")


def verify_windows_binary(binary: Path, target: str) -> None:
    contents = binary.read_bytes()
    if len(contents) < 0x40 or contents[:2] != b"MZ":
        raise TestFailure(f"{binary}: missing DOS/PE header")
    pe_offset = struct.unpack_from("<I", contents, 0x3C)[0]
    if (
        pe_offset + 6 > len(contents)
        or contents[pe_offset : pe_offset + 4] != b"PE\0\0"
    ):
        raise TestFailure(f"{binary}: missing PE signature")
    machine = struct.unpack_from("<H", contents, pe_offset + 4)[0]
    expected = WINDOWS_MACHINE_TYPES[target]
    if machine != expected:
        raise TestFailure(
            f"{binary}: PE machine 0x{machine:04x}, expected 0x{expected:04x}"
        )
    print(f"PASS format: {binary.name} [{target} PE 0x{machine:04x}]")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_artifact_manifest(
    target_dir: Path,
    target: str,
    binaries: list[Path],
    platform_bundle_sha256: str,
) -> None:
    entries = [
        {
            "path": binary.relative_to(target_dir).as_posix(),
            "sha256": sha256(binary),
        }
        for binary in sorted(binaries)
    ]
    manifest = {
        "format": 1,
        "target": target,
        "platform_bundle_sha256": platform_bundle_sha256,
        "roc_version": subprocess.check_output(
            ["roc", "version"], text=True
        ).strip(),
        "binaries": entries,
    }
    (target_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def verify_artifact_manifest(target_dir: Path) -> tuple[str, set[str]]:
    manifest_path = target_dir / "manifest.json"
    if not manifest_path.is_file():
        raise TestFailure(f"Missing artifact manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("format") != 1:
        raise TestFailure(f"Unsupported artifact manifest: {manifest_path}")
    target = manifest.get("target")
    bundle_hash = manifest.get("platform_bundle_sha256")
    roc_version = manifest.get("roc_version")
    entries = manifest.get("binaries")
    if (
        target not in SUPPORTED_TARGETS
        or not isinstance(bundle_hash, str)
        or re.fullmatch(r"[0-9a-f]{64}", bundle_hash) is None
        or not isinstance(roc_version, str)
        or not roc_version.strip()
        or not isinstance(entries, list)
    ):
        raise TestFailure(f"Invalid artifact manifest: {manifest_path}")

    declared: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise TestFailure(f"Invalid binary entry in {manifest_path}")
        relative = entry.get("path")
        expected_hash = entry.get("sha256")
        if (
            not isinstance(relative, str)
            or not isinstance(expected_hash, str)
            or re.fullmatch(r"[0-9a-f]{64}", expected_hash) is None
        ):
            raise TestFailure(f"Invalid binary entry in {manifest_path}")
        posix_path = PurePosixPath(relative)
        if (
            posix_path.is_absolute()
            or relative != posix_path.as_posix()
            or not posix_path.parts
            or any(part in {"", ".", ".."} or ":" in part for part in posix_path.parts)
        ):
            raise TestFailure(f"Unsafe binary path in {manifest_path}: {relative!r}")
        binary = target_dir / relative
        if not binary.is_file():
            raise TestFailure(f"Missing prebuilt binary: {binary}")
        actual_hash = sha256(binary)
        if actual_hash != expected_hash:
            raise TestFailure(
                f"Checksum mismatch for {binary}: {actual_hash} != {expected_hash}"
            )
        if relative in declared:
            raise TestFailure(f"Duplicate binary in {manifest_path}: {relative}")
        declared.add(relative)
    actual_files = {
        path.relative_to(target_dir).as_posix()
        for path in target_dir.rglob("*")
        if path.is_file() and path != manifest_path
    }
    if actual_files != declared:
        raise TestFailure(
            f"Artifact files differ from {manifest_path}; "
            f"missing={sorted(declared - actual_files)}, "
            f"undeclared={sorted(actual_files - declared)}"
        )
    return str(target), declared


def cross_build_suite(
    examples_dir: Path,
    output_dir: Path,
    targets: list[str],
    platform_bundle_sha256: str,
    *,
    verbose: bool,
) -> dict[str, int]:
    defaults, apps = load_spec(examples_dir)
    counts = {stage: 0 for stage in STAGES}
    for target in targets:
        print(f"\n=== CROSS BUILD {target} ===")
        target_dir = output_dir / target
        target_dir.mkdir(parents=True, exist_ok=True)
        binaries: list[Path] = []
        for app in apps:
            if not stage_enabled(
                defaults, app, "build", TARGET_PLATFORMS[target]
            ):
                print(f"SKIP build: {app['path']} [{target}]")
                continue
            source = source_path(app, examples_dir)
            binary = target_dir / binary_relative(
                app, windows=TARGET_PLATFORMS[target] == "windows"
            )
            build_app(source, app, binary, target=target, verbose=verbose)
            if target in WINDOWS_MACHINE_TYPES:
                verify_windows_binary(binary, target)
            binaries.append(binary)
            counts["build"] += 1
        write_artifact_manifest(
            target_dir, target, binaries, platform_bundle_sha256
        )
    return counts


def run_prebuilt_suite(
    examples_dir: Path,
    binaries_dir: Path,
    *,
    label: str,
    verbose: bool,
) -> dict[str, int]:
    defaults, apps = load_spec(examples_dir)
    target, declared = verify_artifact_manifest(binaries_dir)
    expected_platform = TARGET_PLATFORMS[target]
    if current_platform() != expected_platform:
        raise TestFailure(
            f"Cannot run {target} artifacts on {current_platform()} (need {expected_platform})"
        )

    print(f"\n=== RUN PREBUILT {target} FROM {label} ===")
    counts = {stage: 0 for stage in STAGES}
    expected: set[str] = set()
    for app in apps:
        if not stage_enabled(defaults, app, "run", expected_platform):
            print(f"SKIP run: {app['path']}")
            continue
        source = source_path(app, examples_dir)
        relative = binary_relative(app, windows=expected_platform == "windows")
        relative_text = relative.as_posix()
        expected.add(relative_text)
        if relative_text not in declared:
            raise TestFailure(f"Manifest does not contain required binary: {relative_text}")
        binary = binaries_dir / relative
        if os.name != "nt":
            binary.chmod(binary.stat().st_mode | stat.S_IXUSR)
        for case in run_cases(app):
            if case_enabled(source, case):
                run_case(source, binary, case, verbose=verbose)
                counts["run"] += 1
            else:
                print(f"SKIP run: {source.name} [{case['name']}]")

    if declared != expected:
        raise TestFailure(
            f"Prebuilt artifact contents differ from runnable spec; "
            f"missing={sorted(expected - declared)}, extra={sorted(declared - expected)}"
        )
    return counts


def run_local_suite(
    examples_dir: Path, operation: str, *, verbose: bool
) -> dict[str, int]:
    defaults, apps = load_spec(examples_dir)
    selected = {
        "all": set(STAGES),
        "validate": {"check", "test"},
        "build": {"build"},
        "run": {"build", "run"},
    }[operation]
    counts = {stage: 0 for stage in STAGES}

    cache_dir = ROOT / ".test-cache"
    cache_dir.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="roc-platform-template-tests-", dir=cache_dir
    ) as build_root:
        build_dir = Path(build_root)
        binaries: dict[str, Path] = {}

        for stage in STAGES:
            if stage not in selected:
                continue
            print(f"\n=== {stage.upper()} ===")
            for app in apps:
                if not stage_enabled(defaults, app, stage):
                    print(f"SKIP {stage}: {app['path']}")
                    continue
                source = source_path(app, examples_dir)
                if stage == "check":
                    result = run_process(["roc", "check", str(source), "--no-cache"])
                    require_success(result, f"check {source}", verbose=verbose)
                    print(f"PASS check: {source.name}")
                elif stage == "test":
                    result = run_process(["roc", "test", str(source), "--no-cache"])
                    require_success(result, f"test {source}", verbose=verbose)
                    print(f"PASS test: {source.name}")
                elif stage == "build":
                    binary = build_dir / binary_relative(app, windows=os.name == "nt")
                    build_app(source, app, binary, target=None, verbose=verbose)
                    binaries[str(app["path"])] = binary
                else:
                    binary = binaries.get(str(app["path"]))
                    if binary is None:
                        raise TestFailure(f"{app['path']}: run is enabled but build is disabled")
                    for case in run_cases(app):
                        if case_enabled(source, case):
                            run_case(source, binary, case, verbose=verbose)
                            counts[stage] += 1
                        else:
                            print(f"SKIP run: {source.name} [{case['name']}]")
                    continue
                counts[stage] += 1
    return counts


def merge_counts(*results: dict[str, int]) -> dict[str, int]:
    return {stage: sum(result[stage] for result in results) for stage in STAGES}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate, build, and run the platform examples from a shared test spec"
    )
    parser.add_argument("--examples-dir", type=Path, default=ROOT / "examples")
    parser.add_argument(
        "--operation",
        choices=(
            "all",
            "validate",
            "build",
            "run",
            "cross-build",
            "produce",
            "run-prebuilt",
        ),
        default="all",
    )
    parser.add_argument(
        "--target",
        action="append",
        choices=SUPPORTED_TARGETS,
        dest="targets",
        help="Roc target to cross-build; repeat for more than one target",
    )
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument(
        "--bundle-output-dir",
        type=Path,
        help="retain the fresh bundle here instead of a temporary directory",
    )
    parser.add_argument("--binaries-dir", type=Path)
    parser.add_argument("--label", default="local artifact")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    if args.operation != "run-prebuilt" and shutil.which("roc") is None:
        raise TestFailure("'roc' was not found on PATH")
    examples_dir = args.examples_dir
    if not examples_dir.is_absolute():
        examples_dir = ROOT / examples_dir
    examples_dir = examples_dir.resolve()
    if not examples_dir.is_dir():
        raise TestFailure(f"Examples directory does not exist: {examples_dir}")

    if args.operation != "run-prebuilt":
        version = subprocess.check_output(["roc", "version"], text=True).strip()
        print(f"Using {version}")

    if args.operation == "run-prebuilt":
        if args.binaries_dir is None:
            raise TestFailure("run-prebuilt requires --binaries-dir")
        binaries_dir = args.binaries_dir
        if not binaries_dir.is_absolute():
            binaries_dir = ROOT / binaries_dir
        counts = run_prebuilt_suite(
            examples_dir,
            binaries_dir.resolve(),
            label=args.label,
            verbose=args.verbose,
        )
    else:
        if args.operation in {"cross-build", "produce"}:
            if not args.targets or args.output_dir is None:
                raise TestFailure(
                    f"{args.operation} requires --target and --output-dir"
                )
            output_dir = args.output_dir
            if not output_dir.is_absolute():
                output_dir = ROOT / output_dir
            output_dir = output_dir.resolve()

        if args.bundle_output_dir is None:
            bundle_context = tempfile.TemporaryDirectory(
                prefix="platform-go-bundle-"
            )
        else:
            bundle_output_dir = args.bundle_output_dir
            if not bundle_output_dir.is_absolute():
                bundle_output_dir = ROOT / bundle_output_dir
            bundle_context = contextlib.nullcontext(str(bundle_output_dir.resolve()))

        with bundle_context as bundle_directory:
            bundle = bundle_platform(Path(bundle_directory))
            bundle_hash = sha256(bundle)
            print(f"Fresh platform bundle SHA-256: {bundle_hash}")
            with serve_bundle(bundle) as bundle_url:
                with rewrite_examples_for_bundle(
                    examples_dir, bundle_url
                ) as packaged_examples:
                    if args.operation == "cross-build":
                        counts = cross_build_suite(
                            packaged_examples,
                            output_dir,
                            args.targets,
                            bundle_hash,
                            verbose=args.verbose,
                        )
                    elif args.operation == "produce":
                        validation = run_local_suite(
                            packaged_examples, "validate", verbose=args.verbose
                        )
                        builds = cross_build_suite(
                            packaged_examples,
                            output_dir,
                            args.targets,
                            bundle_hash,
                            verbose=args.verbose,
                        )
                        counts = merge_counts(validation, builds)
                    else:
                        counts = run_local_suite(
                            packaged_examples, args.operation, verbose=args.verbose
                        )
    completed = ", ".join(
        f"{stage}: {count}" for stage, count in counts.items() if count > 0
    )
    print(f"\nAll test stages passed ({completed})")


if __name__ == "__main__":
    try:
        main()
    except (
        json.JSONDecodeError,
        OSError,
        RuntimeError,
        subprocess.CalledProcessError,
        TestFailure,
    ) as error:
        raise SystemExit(str(error)) from None
