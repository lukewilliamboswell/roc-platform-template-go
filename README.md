# Roc platform template for Go

A small Roc platform whose host is implemented in Go. It targets Roc's new
compiler ABI and provides command-line arguments, stdin, stdout, stderr,
process exit codes, and Roc runtime allocation/diagnostic hooks.

## Status

Linux musl, macOS, and Windows MinGW are supported on x86-64 and ARM64. The
repository includes 12 example applications, 27 behavioral cases, Go ABI/unit
tests, fresh-package integration tests, and cross-builder CI.

## Upstream dependency

The exact development compiler is declared in the `roc` field of
[`platform/main.roc`](platform/main.roc) and each example header. CI and the
nightly updater read these headers; there is no separate version file.

Go's cgo toolchain uses the MinGW ABI on Windows, so this platform deliberately
targets `x64mingw` and `arm64mingw`, including their baseline `v1` variants.
Roc's `x64win` and `arm64win` names remain MSVC targets and are not compatible
with these host archives.

## Requirements

- The Go version in [`.go-version`](.go-version)
- Zig 0.16.0
- The Roc nightly in the `roc` header in [`platform/main.roc`](platform/main.roc)
- Python 3.11 or newer
- GitHub CLI with artifact-attestation verification for contributor builds

Published platform bundles contain the prebuilt host and Linux runtime inputs;
applications consuming a release bundle only need Roc.

## Run an example

This template has **no published platform release yet**. The examples currently
use local platform source and require a contributor build:

```console
python scripts/fetch_runtime.py
python scripts/build.py --all
roc version
roc examples/hello_world/main.roc
```

Expected output: `Hello, World!`
Use the compiler named in the example's `roc` header. Each application has its
own folder so companion modules and input files can travel with it.

The first platform release must provide a prebuilt platform archive, a starter containing
complete application files, and its exact compiler requirement. A reviewed
follow-up will replace the local example dependencies with immutable release
URLs and link the suitable release here. Thereafter users will only need Roc.
See [the release checklist](CONTRIBUTING.md#release-checklist).

## Build and test

Fetch the authenticated runtime dependency and build every supported Go host:

```console
python scripts/fetch_runtime.py
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

This command reads the compiler pin from `platform/main.roc` and uses the same
revision for the glue specification. CI checks that the committed header is current.

The development test command invokes `roc bundle` to create a fresh platform package, serves that `.tar.zst` over
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
| `x64mingw` | `libhost.a` | vendored Zig/mingw-w64 and Windows import inputs |
| `x64v1mingw` | `libhost.a` | vendored Zig/mingw-w64 and Windows import inputs |
| `arm64mingw` | `libhost.a` | vendored Zig/mingw-w64 and Windows import inputs |
| `arm64v1mingw` | `libhost.a` | vendored Zig/mingw-w64 and Windows import inputs |

The `v1` targets use Roc's baseline CPU feature sets. Their C runtime inputs
are byte-identical to the corresponding architecture's base musl or MinGW
target.

## CI model

CI has separate producer and consumer jobs:

1. Every macOS, Linux, and Windows producer builds every supported Go host,
   creates and serves a fresh Roc bundle, validates all examples, then
   cross-compiles all 12 applications for all ten Roc targets.
2. Each native macOS/Linux/Windows consumer downloads artifacts from every
   producer, verifies their manifests and SHA-256 checksums, and runs all 27
   cases for its target. Linux and x86-64 Windows execute both default and `v1`
   binaries; ARM64 Windows artifacts are cross-linked and format-checked until
   GitHub provides a native ARM64 Windows runner.

Each artifact manifest records the exact Roc version, target, application
hashes, and fresh platform-bundle hash. This catches both target portability
problems and builder-host-dependent output failures.

## Runtime provenance and licensing

Third-party runtime/link inputs have an independent, reproducible CI release
process. Each release supplies an archive, SPDX SBOM, and downloadable signed
provenance/SBOM attestations. Routine platform builds consume a digest-pinned,
verified runtime release and rebuild the Go host from current source.
See [RUNTIME_PROVENANCE.md](RUNTIME_PROVENANCE.md) for source identity,
verification and recovery instructions, and
[SLSA_PROVENANCE.md](SLSA_PROVENANCE.md) for the attestation trust model.

The same process packages Zig's text-only Darwin `libSystem.tbd` interface so
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
