# Roc platform template for Go

A command-line Roc platform with a Go host. It provides command-line arguments,
stdin, stdout, stderr, process exit codes, and Roc runtime allocation and
diagnostic hooks.

The platform builds for Linux musl, macOS, and Windows MinGW on x86-64 and ARM64.
CI executes applications natively on Linux and macOS for both architectures and
on x86-64 Windows. ARM64 Windows builds are cross-linked and format-checked.

## Run an example

Install these contributor toolchains:

- The Go version in [`.go-version`](.go-version)
- Zig 0.16.0
- The exact Roc nightly in the `roc` header of [`platform/main.roc`](platform/main.roc)
- Python 3.11 or newer
- GitHub CLI with `gh attestation verify` and source/signer digest verification

From the repository root, fetch the authenticated runtime dependency and build
the native Go host:

```console
python scripts/fetch_runtime.py
python scripts/build.py
roc examples/hello_world/main.roc
```

Expected output: `Hello, World!`

Examples currently use the local platform. The published
[runtime 0.1.0 release](https://github.com/lukewilliamboswell/roc-platform-template-go/releases/tag/runtime-v0.1.0)
contains third-party runtime and linker inputs; a complete platform release
containing the Go hosts has not been published yet. See the
[platform release checklist](CONTRIBUTING.md#release-checklist).

## Build, test, and package

Build all supported hosts before running the suite or producing a platform bundle:

```console
python scripts/fetch_runtime.py
python scripts/build.py --all
go -C host test ./...
python scripts/test.py --operation all --verbose
python scripts/bundle.py --output-dir dist
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

## Runtime dependencies

Runtime binaries are release assets and are not tracked in the source tree.
[`scripts/runtime_release.json`](scripts/runtime_release.json) pins the runtime
version, archive digest, and signing/source identities. The fetcher verifies
provenance and SBOM attestations, the archive checksum, and the complete file
inventory before installing inputs under `platform/targets/`.

Runtime releases are built independently from the checksum-pinned sources in
[`scripts/runtime_sources.json`](scripts/runtime_sources.json). Two clean CI
builds must produce identical archives and SBOMs, and the full platform test
matrix must pass before signing and immutable publication. Routine platform
updates reuse the locked release and rebuild the Go hosts from current source.

See [RUNTIME_PROVENANCE.md](RUNTIME_PROVENANCE.md) for source, verification, and
release details, [SLSA_PROVENANCE.md](SLSA_PROVENANCE.md) for the attestation trust
model, and [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md) for redistribution
notices.

## Supported Roc targets

Every target uses a Go `libhost.a` built from this repository.

| Roc targets | Runtime and linker inputs |
| --- | --- |
| `x64mac`, `arm64mac` | Darwin text link interface from the runtime release; macOS supplies the runtime |
| `x64musl`, `x64v1musl` | Zig/musl inputs from the runtime release |
| `arm64musl`, `arm64v1musl` | Zig/musl inputs from the runtime release |
| `x64mingw`, `x64v1mingw` | Zig/mingw-w64 and Windows import inputs from the runtime release |
| `arm64mingw`, `arm64v1mingw` | Zig/mingw-w64 and Windows import inputs from the runtime release |

The `v1` variants use Roc's baseline CPU feature sets. Go's cgo toolchain uses
the MinGW ABI on Windows; Roc's `x64win` and `arm64win` MSVC targets are
incompatible with these hosts. The Darwin `libSystem.tbd` file enables
cross-linking; the macOS runtime itself is not redistributed.

## CI and nightly updates

Six producer environments across macOS, Linux, and Windows authenticate the
locked runtime release, build every Go host, and cross-compile all 12 example
applications for all ten targets. Eight native consumer targets run all 27
behavioral cases against every producer's output.

Artifact manifests record the compiler version, target, application checksums,
platform bundle digest, and runtime archive digest. CI also checks Go units,
generated C bindings, Roc formatting, documentation, and the tracked-binary policy.

Compiler pins live in the `roc` headers selected by
[`.github/roc-nightly.json`](.github/roc-nightly.json). The daily updater changes
only those pins and automatically merges verified bot updates after CI passes
on the current main base. Runtime dependency and source changes have separate
PRs. See [nightly update instructions](CONTRIBUTING.md#nightly-compiler-updates)
for manual dispatch and retry behavior.
