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
roc fmt --check platform
roc fmt --check examples
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

`host/roc/roc_std.h` is the C boundary shared by Go and Roc. When hosted
functions or platform types change, generate C glue from the same pinned Roc
source and compare layouts, result tags, ownership, and exported signatures:

```console
roc glue path/to/roc/src/glue/src/CGlue.roc /tmp/roc-go-glue platform/main.roc
```

Update the C static assertions, Go representations, ownership tests, and
integration cases together. Hosted refcounted arguments are owned by the host
and must be decremented. Values returned to Roc transfer ownership to Roc.

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

Do not label MinGW Go archives as Roc `x64win` or `arm64win` inputs. Those Roc
targets are MSVC today. Windows application support remains blocked on
[roc-lang/roc#8779](https://github.com/roc-lang/roc/issues/8779). When new
MinGW targets land, update `.roc-version`, the target tables in
`platform/main.roc`, `scripts/build.py`, `scripts/bundle.py`, and
`scripts/test.py`, then enable Windows consumer jobs in CI.

## Review checklist

- Every example passes every stage through a served fresh bundle.
- Roc source is formatted by the pinned compiler.
- Go tests pass and cover any ABI/memory-layout change.
- All supported hosts and all example/target combinations cross-compile.
- Native consumers execute artifacts from every producer OS.
- `roc docs` succeeds and public docs match behavior.
- README commands work from a clean checkout.
- Runtime provenance and third-party notices remain accurate.
