# Independently released linker inputs

External linker inputs are built and released independently from the platform
source. `libhost.a` is deliberately excluded and is rebuilt from the current
checkout. One immutable release, named from the SHA-256 of its aggregate
manifest, contains a genuine tar archive with the inputs for every advertised
target. The committed lock pins the manifest and archive bytes.

The dispatch-only producer builds twice from the checksum-pinned Zig
distribution, compares all output bytes, and runs the full cross-build/native
validation matrix against that exact candidate. It attests the exact archive
and aggregate manifest requested for an open PR. The permission-isolated
publisher in `roc-automation` verifies the PR head, producer run, hashes, and
attestations before publishing an immutable release and adding a GitHub-signed,
lock-only commit to that same PR. The caller pins the reviewed controller by its
full 40-character commit.

The macOS `libSystem.tbd` is generated from
`linker-inputs/macos/interfaces.json`. Neither generation nor packaging reads an
Apple SDK, framework, library, or pre-existing TBD. Its catalog and provenance
are packaged and recorded in the SBOM. ARM64 Windows targets are intentionally
suspended until the project has reliable native execution coverage.

Dispatch `Publish PR linker inputs` from the default branch with the open PR
number. The controller creates `linker-inputs.lock.json`; do not construct or
edit it by hand. The strict lock binds the archive and manifest names, sizes,
hashes, source branch and commit, producer workflow, and producer-input
fingerprint. Then use:

```console
python scripts/linker_inputs.py fetch
python scripts/linker_inputs.py check
```

Producer validation uses `stage ARCHIVE --sha256 DIGEST`; this unsigned path is
limited to a same-run CI candidate and cannot publish. Routine PRs never rebuild
these inputs: they restore the archive cache, rehash it, and download only on a
verified cache miss. The old versioned releases remain immutable historical
records and provide the temporary bootstrap fallback until the first lock-only
commit lands.
