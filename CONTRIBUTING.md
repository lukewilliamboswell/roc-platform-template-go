# Contributing

## Toolchains

Use the exact Go and Roc versions in `.go-version` and `.roc-version`, plus Zig
0.16.0. CI reads the same files. Do not update a pin as an incidental part of
another change.

All repository automation lives in `scripts/` and is Python. Keep commands
cross-platform unless a script is explicitly a maintainer-only tool for a
target-specific artifact, such as Linux runtime vendoring.

## Before opening a change

```console
python scripts/build.py --all
go -C host test ./...
python scripts/check_roc_format.py
python scripts/test.py --operation all --verbose
roc docs platform/main.roc --output=generated-docs --no-cache
```

The test runner always creates and serves a fresh `roc bundle`; do not add a
relative-platform shortcut to the integration path.

## Examples and test specifications

Every `.roc` file under `examples/` must have exactly one entry in
`scripts/test_spec.json`. All four stages—`check`, `test`, `build`, and
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

The generator reads `.roc-version`, verifies that the active `roc` executable
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

Routine changes must not regenerate runtime archives. For a deliberate Zig or
musl update, follow `RUNTIME_PROVENANCE.md`, review upstream license changes,
run `python scripts/vendor_zig_runtime.py`, inspect symbol/archive differences,
then run `python scripts/vendor_zig_runtime.py --check` from a clean build.

Keep `THIRD_PARTY_LICENSES.md`, `licenses/`, provenance, and checksums in sync.

## Windows

Go cgo archives use the MinGW ABI and must remain under Roc's `x64mingw`,
`x64v1mingw`, `arm64mingw`, and `arm64v1mingw` target names. Do not relabel
them as `x64win` or `arm64win`; those are MSVC targets with different startup,
runtime, and linker requirements.

The MinGW targets require a Roc nightly containing
[roc-lang/roc#10637](https://github.com/roc-lang/roc/pull/10637). Keep Windows
producer and consumer lanes enabled when updating `.roc-version`, and validate
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
