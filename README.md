# Roc platform template for Go

A command-line Roc platform with a Go host. It provides command-line arguments,
stdin, stdout, stderr, process exit codes, and Roc runtime allocation and
diagnostic hooks.

The platform supports Linux musl and macOS on x86-64 and ARM64, and Windows
MinGW on x86-64. CI executes applications natively on every supported OS and
architecture. Windows ARM64 is not supported.

## Run an example

Install these contributor tools (Blueprint provisions locked Go and Zig):

- The latest [Roc nightly](https://github.com/roc-lang/nightlies/releases/latest)
- [Blueprint 0.8.0](https://github.com/lukewilliamboswell/roc-blueprint/releases/tag/0.8.0)
- Python 3.11 or newer
- GitHub CLI with `gh attestation verify` and source/signer digest verification

From the repository root, fetch the authenticated runtime dependency and build
the Go hosts:

```console
blueprint run fetch-runtime
blueprint run build-host
roc examples/hello_world/main.roc
```

Expected output: `Hello, World!`

Repository examples use the working-tree platform by relative path and have no
compiler pin. For a released starter, download the examples ZIP from the
[latest platform release](https://github.com/lukewilliamboswell/roc-platform-template-go/releases/latest).
Its examples name that release's immutable bundle; the source tree continues to
use relative paths.

## Build, test, and package

Build all supported hosts before running the suite or producing a platform bundle:

```console
blueprint run fetch-runtime
blueprint run build-host
blueprint run test-host
blueprint run check
blueprint run test-examples
blueprint run bundle -- --output-dir dist
```

For selected hosts, use `python scripts/build.py x64mac arm64musl`.

The test runner creates a fresh platform bundle, serves it over localhost, and
checks, tests, builds, and runs temporary copies of every example against it.
The bundle command packages the platform modules, Go hosts, runtime inputs, and
source/license metadata using `roc bundle`.

Generate API documentation with:

```console
roc docs platform/main.roc --output=generated-docs --no-cache
```

The public API is `Stdin.line!`, `Stdout.line!`, and `Stderr.line!`. ABI changes,
C header generation, test conventions, and release instructions are documented
in [CONTRIBUTING.md](CONTRIBUTING.md).

## Linker-input dependencies

Linker inputs are release assets and are not tracked in the source tree.
[`link-inputs.lock.json`](link-inputs.lock.json) pins the content-addressed release,
archive digest, and signing/source identities. The trusted publisher admits
provenance and the exact producer artifacts before writing this lock. Routine fetches verify the locked archive size and SHA-256
and the complete file inventory, including after a cache hit, before installing
inputs under `platform/targets/`. They make no attestation API calls.

Linker-input releases are built independently from the checksum-pinned sources in
[`scripts/runtime_sources.json`](scripts/runtime_sources.json). Two clean CI
builds must produce identical archives and SBOMs, and the full platform test
matrix must pass before signing and immutable publication. Routine platform
updates reuse the locked release and rebuild the Go hosts from current source.

See [LINKER_INPUTS.md](LINKER_INPUTS.md) for the new independent linker-input
release stream and [RUNTIME_PROVENANCE.md](RUNTIME_PROVENANCE.md) for the
historical runtime release's source, verification, and
release details, [SLSA_PROVENANCE.md](SLSA_PROVENANCE.md) for the attestation trust
model, and [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md) for redistribution
notices.

## Supported Roc targets

Every target uses a Go `libhost.a` built from this repository.

| Roc targets | Runtime and linker inputs |
| --- | --- |
| `x64mac`, `arm64mac` | Project-authored Darwin text link interface from the linker-input release; macOS supplies the runtime |
| `x64musl`, `x64v1musl` | Zig/musl inputs from the linker-input release |
| `arm64musl`, `arm64v1musl` | Zig/musl inputs from the linker-input release |
| `x64mingw`, `x64v1mingw` | Zig/mingw-w64 and Windows import inputs from the linker-input release |

The `v1` variants use Roc's baseline CPU feature sets. Go's cgo toolchain uses
the MinGW ABI on Windows; Roc's `x64win` and `arm64win` MSVC targets are
incompatible with these hosts. The Darwin `libSystem.tbd` file enables
cross-linking; the macOS runtime itself is not redistributed.

## CI and nightly updates

One Linux builder uses the Go 1.27.0 and Zig 0.16.0 downloads locked in
[`Blueprint.lock`](Blueprint.lock) to build every Go host and cross-compile all
12 applications for all eight target variants. Eight native consumer lanes run
all 27 recorded cases and separately check, link and run the exact release
examples archive against that same bundle with an empty package cache.

CI resolves the latest nightly once for the whole run, verifies generated C
bindings, runs Roc and Go tests, and checks formatting, documentation and the
tracked-binary policy. Product headers do not select a compiler.

[`nightly.yml`](.github/workflows/nightly.yml) runs roc-automation's shared
compatibility workflow against the latest immutable platform release and latest
nightly, on Linux x64/ARM64, Apple Silicon macOS and Windows x64. Release CI also
covers Intel macOS and baseline CPU variants. Compatibility failure calls for a
source fix and a new platform release; the nightly never edits source or pins.

[`release.yml`](.github/workflows/release.yml) validates a selected `main` commit,
then publishes the same tested platform bundle and examples ZIP, with provenance, checksums, and artifact-bound SPDX 3.0.1 and CycloneDX 1.7
inventories. See [contributing](CONTRIBUTING.md) for the release procedure.
