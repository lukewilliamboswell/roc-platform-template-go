# Roc platform template for Go

A small Roc platform whose host is implemented in Go. It targets Roc's new
compiler ABI and provides command-line arguments, stdin, stdout, stderr,
process exit codes, and Roc runtime allocation/diagnostic hooks.

## Status

Linux musl and macOS are supported on x86-64 and ARM64. The repository includes
12 example applications, 27 behavioral cases, Go ABI/unit tests, fresh-package
integration tests, and cross-builder CI.

## ⚠️ TODO: Windows requires upstream Roc MinGW targets

**Windows applications built with this Go host are not currently supported.**

Go's cgo toolchain uses the MinGW ABI on Windows. Roc's current `x64win` and
`arm64win` targets use the MSVC ABI, discover the MSVC/Windows SDK libraries,
and link against the MSVC runtime. Although both toolchains emit COFF objects,
their startup code, runtime libraries, imports, and linker defaults are not
interchangeable.

This is tracked upstream in
[roc-lang/roc#8779](https://github.com/roc-lang/roc/issues/8779). The Go host
has been successfully cross-compiled to both `windows/amd64` and
`windows/arm64` with Zig's GNU Windows targets, but those archives cannot be
published under Roc's MSVC target names. This template will add Windows
consumer lanes only after Roc exposes explicit MinGW-compatible targets.

The exact Roc nightly used by CI is pinned in [`.roc-version`](.roc-version).
Every workflow reads that file, so adopting MinGW support later is an explicit
Roc-version update followed by a small target-table and CI-matrix change.
Windows GitHub runners already participate as producers: they cross-compile
and upload all currently supported macOS and Linux application artifacts.

## Requirements

- The Go version in [`.go-version`](.go-version)
- Zig 0.16.0
- The Roc nightly in [`.roc-version`](.roc-version)
- Python 3.11 or newer

Published platform bundles contain the prebuilt host and Linux runtime inputs;
applications consuming a release bundle only need Roc.

## Build and test

Build every supported Go host:

```console
python scripts/build.py --all
```

Build only the native host, or selected cross targets:

```console
python scripts/build.py
python scripts/build.py x64mac arm64musl
```

Run the complete native suite:

```console
go -C host test ./...
python scripts/test.py --operation all --verbose
```

The C ABI header consumed by the Go host is generated from `platform/main.roc`
with Roc's `CGlue.roc`. Regenerate it after changing the platform boundary:

```console
python scripts/generate_c_glue.py
```

This command uses `.roc-version` for both the compiler revision and the glue
spec revision; CI checks that the committed header is current.

The test command does not point examples at `../platform/main.roc`. It invokes
`roc bundle` to create a fresh platform package, serves that `.tar.zst` over
localhost HTTP, rewrites temporary example copies to the bundle URL, and then
runs `check`, `test`, `build`, and every behavioral case. This exercises the
same package boundary users receive.

Every stage is enabled for every example by default. A disabled app, stage,
platform override, or case is rejected unless its spec entry includes both a
reason and a GitHub issue URL. The source of truth is
[`scripts/test_spec.json`](scripts/test_spec.json).

## Package the platform

After building all hosts:

```console
python scripts/bundle.py --output-dir dist
```

[`scripts/bundle.py`](scripts/bundle.py) calls `roc bundle` directly with the
platform modules and every declared target input. It does not implement a
separate archive format.

## Supported Roc targets

| Roc target | Host archive | Runtime |
| --- | --- | --- |
| `x64mac` | `libhost.a` | vendored link interface; macOS system runtime |
| `arm64mac` | `libhost.a` | vendored link interface; macOS system runtime |
| `x64musl` | `libhost.a` | vendored Zig/musl inputs |
| `x64v1musl` | `libhost.a` | vendored Zig/musl inputs |
| `arm64musl` | `libhost.a` | vendored Zig/musl inputs |
| `arm64v1musl` | `libhost.a` | vendored Zig/musl inputs |

The `v1` targets use Roc's baseline CPU feature sets. Their C runtime inputs
are byte-identical to the corresponding architecture's base musl target.

## CI model

CI has separate producer and consumer jobs:

1. Every macOS, Linux, and Windows producer builds every supported Go host,
   creates and serves a fresh Roc bundle, validates all examples, then
   cross-compiles all 12 applications for all six Roc targets.
2. Each native macOS/Linux consumer downloads artifacts from every producer,
   verifies their manifests and SHA-256 checksums, and runs all 27 cases for
   its target. Linux also executes both default and `v1` binaries.

Each artifact manifest records the exact Roc version, target, application
hashes, and fresh platform-bundle hash. This catches both target portability
problems and builder-host-dependent output failures.

## Runtime provenance and licensing

Linux C runtime inputs are explicit checked-in artifacts generated with the
pinned Zig toolchain. Normal CI consumes them; it does not regenerate them.
Maintainers can reproduce or update them using the Python process documented
in [RUNTIME_PROVENANCE.md](RUNTIME_PROVENANCE.md). Checksums are pinned in
[`scripts/zig_runtime.sha256`](scripts/zig_runtime.sha256).

The same process vendors Zig's text-only Darwin `libSystem.tbd` interface so
non-macOS producers can cross-link macOS artifacts. The runtime itself is
provided by macOS and is not redistributed.

See [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md) and the exact notices in
[`licenses/`](licenses/) before redistributing statically linked applications.

## Platform documentation

Generate the public Roc API documentation with:

```console
roc docs platform/main.roc --output=generated-docs --no-cache
```

CI runs this command on every producer OS. The public API is intentionally
small: `Stdin.line!`, `Stdout.line!`, and `Stderr.line!`.

Development conventions, ABI update guidance, and the release checklist are
in [CONTRIBUTING.md](CONTRIBUTING.md).
