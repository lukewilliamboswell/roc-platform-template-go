# Contributing

## Toolchains

Install Blueprint 0.8.0, Python 3.11 or newer, GitHub CLI and the latest Roc
nightly. `Blueprint.roc` declares Go 1.27.0 and Zig 0.16.0; `Blueprint.lock`
records the exact downloads. The supported Blueprint development environments
are Linux x64/ARM64 and Apple Silicon macOS. Native Windows and Intel macOS
consumers need only Roc and Python to test a release archive.

The bare `roc` is the product compiler. Do not add a `roc` field to the platform,
examples or `Blueprint.roc`, or add `.roc-version` or `.github/roc-nightly.json`.
CI resolves the latest nightly once and passes that exact version to every job.
Go and Zig toolchain changes require review of `Blueprint.roc`, `.go-version`,
`host/go.mod`, the build script's requirements and the generated lock together.

## Nightly compatibility

The scheduled shared nightly checks the latest immutable platform release on
the latest nightly. It does not rebuild a host, edit headers, open updater PRs,
or merge. Diagnose failures using its per-target artifacts, fix the working
tree in a PR, and publish a new release after validation. Manual selector inputs
reproduce historical pairs; leave both empty to refresh current compatibility.

See the [upstream platform guide](https://lukewilliamboswell.github.io/roc-automation/platforms.html)
and [shared nightly contract](https://lukewilliamboswell.github.io/roc-automation/nightly-compatibility.html).

## Before opening a change

```console
blueprint run fetch-runtime
blueprint run build-host
blueprint run test-host
blueprint run check
blueprint run check-glue
blueprint run test-examples
roc docs platform/main.roc --output=generated-docs --no-cache
```

By default the test runner creates and serves a fresh `roc bundle`. Release
candidate checks use `--bundle` to serve an existing archive; `--published`
checks committed release URLs. Keep these validation inputs distinct.

## Examples and test specifications

Every application root (`examples/*/main.roc`) must have exactly one entry in
`tests/spec.json`. Companion modules and input files stay in that folder. All four stages—`check`, `test`, `build`, and
`run`—are enabled by default. Add multiple cases when arguments, stdin, exit
codes, streams, or boundary-sized values change behavior.

Use the shared schema version 1 with `release: "working-tree"`, no release
dependencies, and explicit case names, arguments, stdin, stdout, stderr and exit
codes. Keep all cases runnable. The same cases travel in the immutable examples
archive with its release version and bundle URL; release testing compares exact
streams and exits. A skipped case cannot establish compatibility.

## Roc ABI changes

`host/roc/roc_platform_abi.h` is the generated C boundary shared by Go and
Roc. When hosted functions or platform types change, regenerate it with:

```console
blueprint run update-glue
```

The generator reads the active compiler revision from `roc version` and downloads
`CGlue.roc` from that exact revision. CI runs `blueprint run check-glue` to reject stale
bindings. For offline compiler development, pass `--glue-spec` with
`CGlue.roc` from an exact matching Roc source checkout.

Do not edit the generated header by hand. Update the Go representations,
ownership tests, and integration cases with any ABI change. Hosted refcounted
arguments are owned by the host and must be decremented. Values returned to
Roc transfer ownership to Roc.

The Linux startup adapter in `host/startup.c` is intentional: Go c-archives
expect process arguments in their runtime constructor, while musl normally
invokes init-array entries without forwarding them. Changes here require a
native executable test, not only an archive build.

## Runtime dependencies

Linker inputs are released separately from Go hosts and platform packages.
Follow [LINKER_INPUTS.md](LINKER_INPUTS.md) to review trusted source changes and
publish a content-addressed PR build. The trusted publisher adds the reviewed
lock; routine CI consumes that release and never regenerates these inputs.
Compiler compatibility checks do not rebuild linker inputs.
Use `python scripts/fetch_runtime.py` before building platform bundles.
Keep license notices and source/SBOM inventory accurate. Never commit generated
runtime or host binaries or overwrite an existing release.

## Windows

Go cgo archives use the MinGW ABI and must remain under Roc's `x64mingw`,
`x64v1mingw` target name. Windows ARM64 support is suspended until native
execution is reliable. Do not relabel
them as `x64win` or `arm64win`; those are MSVC targets with different startup,
runtime, and linker requirements.

The MinGW targets require a Roc nightly containing
[roc-lang/roc#10637](https://github.com/roc-lang/roc/pull/10637). Keep Windows consumer lanes enabled when changing the compiler or host. Windows
ARM64 remains unsupported.

## Review checklist

- Every example passes every stage through a served fresh bundle.
- Roc source is formatted by the resolved latest nightly.
- Go tests pass and cover any ABI/memory-layout change.
- All supported hosts and all example/target combinations cross-compile.
- Native consumers execute artifacts from every producer OS.
- `roc docs` succeeds and public docs match behavior.
- README commands work from a clean checkout.
- Runtime provenance and third-party notices remain accurate.

## Release procedure

Product versions are independent of compiler versions. A release is an immutable
platform bundle and a complete examples ZIP. Never rewrite committed example
URLs after publication: only the archived copies name the release.

1. Review `docs/releases/0.1.0.md` (use version-specific notes for subsequent
   releases), the source, bindings and linker-input lock. Merge only after the
   PR's required `CI result` passes on the current main base.
2. Dispatch `Release platform` from `main` with the final version. It resolves
   one nightly, builds the host once, bundles once, packages the examples, and
   validates the same bundle/ZIP on all eight native target lanes. No rebuild
   occurs between validation and publication.
3. The publish job attests the exact bundle and examples, stages a draft through
   the shared publisher, verifies the uploaded bytes, then publishes. Keep tags
   and assets immutable. A partial publication must be recovered using the
   preserved candidate; never rebuild or overwrite a final release.
4. Dispatch `Nightly compatibility` on `main` with both selectors empty. Require
   every shared native runner and the aggregate verdict to pass. Intel macOS
   and baseline CPU variants have additional release CI coverage beyond that
   shared runner matrix.
5. Verify the release download from a fresh cache and retain the workflow run
   links and compiler identity from the authored release notes. The dashboard
   refreshes in roc-automation's Documentation deployment; development CI alone
   is not published compatibility evidence.

For a local dry run after building hosts:

```console
blueprint run bundle -- --output-dir dist
blueprint run package-release -- --bundle dist/HASH.tar.zst --version 0.1.0-dev
blueprint run test-release -- --bundle dist/HASH.tar.zst --archive dist/roc-platform-template-go-examples-0.1.0-dev.zip
```
