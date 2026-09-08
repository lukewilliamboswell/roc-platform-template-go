# Contributing

## Toolchains

Use the Go version in `.go-version`, the Roc version in the `platform/main.roc`
header, and Zig 0.16.0. CI verifies that all headers selected in
`.github/roc-nightly.json` agree. Do not update a pin incidentally.

All repository automation lives in `scripts/` and is Python. Keep commands
cross-platform unless a script is explicitly a maintainer-only tool for a
target-specific artifact, such as Linux runtime vendoring.

## Before opening a change

```console
python scripts/fetch_runtime.py
python scripts/build.py --all
go -C host test ./...
python scripts/check_roc_format.py
python scripts/test.py --operation all --verbose
roc docs platform/main.roc --output=generated-docs --no-cache
```

By default the test runner creates and serves a fresh `roc bundle`. Release
candidate checks use `--bundle` to serve an existing archive; `--published`
checks committed release URLs. Keep these validation inputs distinct.

## Examples and test specifications

Every application root (`examples/*/main.roc`) must have exactly one entry in
`scripts/test_spec.json`. Companion modules and input files stay in that folder. All four stages—`check`, `test`, `build`, and
`run`—are enabled by default. Add multiple cases when arguments, stdin, exit
codes, streams, or boundary-sized values change behavior.

If an upstream bug makes a skip unavoidable, disable the smallest possible
scope and include machine-readable metadata beside it:

```json
{
  "stages": { "build": false },
  "skip_reasons": {
    "build": {
      "reason": "Concise description of the observed compiler failure",
      "issue": "https://github.com/roc-lang/roc/issues/NNNN"
    }
  }
}
```

The runner rejects unexplained skips and non-GitHub issue links.

## Roc ABI changes

`host/roc/roc_platform_abi.h` is the generated C boundary shared by Go and
Roc. When hosted functions or platform types change, regenerate it with:

```console
python scripts/generate_c_glue.py
```

The generator reads the `roc` header in `platform/main.roc`, verifies that the active `roc` executable
comes from that nightly, and downloads `CGlue.roc` from the same immutable Roc
revision. CI runs `python scripts/generate_c_glue.py --check` to reject stale
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

## Vendored runtimes

Runtime dependencies are released separately from Go hosts and platform packages.
Follow [RUNTIME_PROVENANCE.md](RUNTIME_PROVENANCE.md) to review trusted source
changes, publish a new runtime version, and update the consumer lock. Routine CI
consumes the selected release; nightly pin updates do not regenerate runtimes.
Use `python scripts/fetch_runtime.py` before building platform bundles.
Keep license notices and source/SBOM inventory accurate. Never commit generated
runtime or host binaries or overwrite an existing release.

## Windows

Go cgo archives use the MinGW ABI and must remain under Roc's `x64mingw`,
`x64v1mingw`, `arm64mingw`, and `arm64v1mingw` target names. Do not relabel
them as `x64win` or `arm64win`; those are MSVC targets with different startup,
runtime, and linker requirements.

The MinGW targets require a Roc nightly containing
[roc-lang/roc#10637](https://github.com/roc-lang/roc/pull/10637). Keep Windows
producer and consumer lanes enabled when updating the `roc` header in `platform/main.roc`, and validate
both Windows architectures even when only x86-64 can be run natively in CI.

## Review checklist

- Every example passes every stage through a served fresh bundle.
- Roc source is formatted by the pinned compiler.
- Go tests pass and cover any ABI/memory-layout change.
- All supported hosts and all example/target combinations cross-compile.
- Native consumers execute artifacts from every producer OS.
- `roc docs` succeeds and public docs match behavior.
- README commands work from a clean checkout.
- Runtime provenance and third-party notices remain accurate.

## Release checklist

`main` is the development branch. No release or stable compiler support line has
been published. Package versions are independent of compiler versions. Start with
an explicitly documented exact-nightly bootstrap release; create a compiler
compatibility branch only when a second support line is needed. Release preparation,
publication, backports, and URL follow-ups remain manual.

1. Select a reviewed commit and record its SHA and header compiler pin. Build all
   hosts and run the full cross-builder CI on that commit. Generate the bundle
   with `python scripts/bundle.py --output-dir dist`.
2. Test that exact archive with `python scripts/test.py --bundle dist/HASH.tar.zst
   --operation all --verbose` on supported native systems. Keep its SHA-256 and
   the CI evidence. Do not rebuild from a moving branch after validation.
3. Prepare a starter with a complete example folder, the intended immutable
   platform URL, compiler pin, setup instructions, and relevant license notices.
   Validate a temporary copy against the candidate archive before publication.
4. Tag the tested SHA with a new package version and publish those same artifacts.
   Include compiler requirements and archive digests in release notes. If a
   partial publication fails, inspect existing tags/assets and resume using the
   preserved artifacts; never overwrite a published release.
5. Update public example URLs and README release links in a reviewed follow-up,
   preserving development compiler pins. Test the downloads from a fresh compiler
   cache using `python scripts/test.py --published --operation all --verbose`.
   This mode refuses local platform paths and never rewrites committed headers.
6. At that first URL update, add a separately named published-examples CI job on
   supported native runners. Use a fresh cache, install the declared compiler, and
   run the published command above. Keep it in `ci.yml`, which the nightly
   controller dispatches alongside the current-source jobs. Both lanes must pass
   compiler-only and combined compiler/source changes. Do not substitute a local
   archive to make published validation pass.
7. Generate versioned documentation from the release and retain earlier version
   URLs. Keep rendered docs in release/deployment artifacts. Validate the exact
   follow-up PR SHA and required checks before merging; sign its commit if branch
   policy requires it. This repository has no automated release follow-up.

The published lane cannot provide evidence until the first release exists; the
current CI validates source bundles only. Keep this limitation visible during
bootstrap instead of treating source tests as proof of download compatibility.
