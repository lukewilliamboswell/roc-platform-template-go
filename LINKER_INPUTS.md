# Independently released linker inputs

External linker inputs are built and released independently from the platform
source. `libhost.a` is deliberately excluded and is rebuilt from the current
checkout. One immutable `linker-inputs-vX.Y.Z` release contains the inputs for
every advertised target, an SPDX 2.3 SBOM, checksums, and `dependency.json`.

The producer builds twice from the checksum-pinned Zig distribution, compares
all output bytes, and runs the full cross-build/native validation matrix against
that exact candidate. A permission-isolated reusable workflow in `roc-automation`
checks the declared inventory and source identity, signs it, uploads a draft,
downloads and compares it, then publishes only an immutable release. The caller
pins the reviewed `roc-automation` controller by its full 40-character commit.

The macOS `libSystem.tbd` is generated from
`linker-inputs/macos/interfaces.json`. Neither generation nor packaging reads an
Apple SDK, framework, library, or pre-existing TBD. Its catalog and provenance
are packaged and recorded in the SBOM. ARM64 Windows targets are intentionally
suspended until the project has reliable native execution coverage.

After publishing `linker-inputs-v1.0.0`, construct and review
`linker-inputs.lock.json` from its exact release metadata. The strict lock binds
the archive and SBOM names, sizes, hashes, source commit/ref/repository, and the
shared signer repository/workflow/commit. Then use:

```console
python scripts/linker_inputs.py fetch
python scripts/linker_inputs.py check
```

Producer validation uses `stage ARCHIVE --sha256 DIGEST`; this unsigned path is
limited to a same-run CI candidate and cannot publish. The old `runtime-v*`
releases remain immutable historical records and must not be replaced or moved.
