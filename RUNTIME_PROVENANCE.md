# Runtime dependency releases

Third-party runtime and linker inputs have an independent release lifecycle in
this repository. They are distinct from the Go host (`libhost.a`), which is built
from current platform source for every platform update.

## Trusted sources and archive contents

`scripts/runtime_sources.json` records the official Zig distribution URL and
SHA-256, bundled component versions and source paths, patch context, and notices.
The producer downloads and verifies that distribution before compiling. Source
and license declarations are checked against its contents. The distribution
includes patched musl, mingw-w64, Zig libc/compiler runtime, and Darwin interface
metadata; it is the source authority rather than pristine upstream components.

The archive preserves `targets/` paths for Linux musl and Windows MinGW, including
baseline variants, and the Darwin `libSystem.tbd` text stub. It contains no Go
host or Windows/Apple runtime DLL implementation. `runtime/` contains the source
inventory, license notices, and an exhaustive per-file SHA-256 manifest.

Tar members are sorted regular files with fixed ownership, modes, and timestamps;
gzip has a fixed timestamp and no embedded filename. The existing object/archive
normalization makes independent builds byte-identical. The archive and generated
SPDX 2.3 SBOM must match across two clean GitHub-hosted builders.

## Publish and adopt inputs

Follow [the linker-input procedure](LINKER_INPUTS.md) to review producer changes,
validate the exact candidate, publish it through the trusted controller and
adopt its signed content lock. Build and test jobs cannot publish. The
publisher verifies inert candidate bytes and never executes candidate code.

## Consume and verify

`link-inputs.lock.json` is the reviewed dependency lock after adoption. Routine
CI fetches that exact release; generated runtime files are ignored rather than tracked.
Git history is preserved. The normal contributor sequence is:

```console
python scripts/fetch_runtime.py
python scripts/build.py --all
python scripts/test.py --operation all
python scripts/bundle.py --output-dir dist
```

The trusted publisher checks provenance, workflow identity, source commit and
attestations when a lock changes. Routine consumers deliberately use only the
committed size and SHA-256: cache hits need no network request, cache misses
download only the exact locked archive, and every use rehashes it before safe
extraction. Repeating online attestation checks would add traffic without
changing the reviewed dependency selection.

`link-inputs.lock.json` is created only by the trusted publisher. Its absence is
an error: routine consumers never select an older versioned release or rebuild
external inputs as a fallback.

Only the declared regular-file inventory may be installed. Traversal, links,
duplicate entries, missing files, and unexpected paths fail validation. The
installation preserves separately generated host archives. Cached assets live
under `.linker-inputs-cache/<sha256>`; every fetch rehashes them, and bundle
assembly compares installed files and metadata with the digest-pinned archive.
A verification failure never falls back to unverified bytes.

`--candidate ARCHIVE --sha256 DIGEST` is an explicit unsigned installation path
for read-only producer validation. Those jobs supply `RUNTIME_CANDIDATE_SHA256`.
It is not an input exposed by nightly dispatch and is never a publication path.

## Local reproduction

With the source manifest's exact Zig version on PATH:

```console
python scripts/vendor_zig_runtime.py --output-dir ci-output/runtime-targets
python scripts/package_runtime.py --targets-dir ci-output/runtime-targets --output-dir ci-output/runtime-dist --version 0.1.0
```

These commands write build artifacts, not tracked source. Local archives have no
CI attestation and must not be substituted for a published dependency.

## Recovery and upgrades

The release tag is derived from the aggregate manifest hash. The trusted
publisher may resume only an identical draft, verifies every downloaded asset,
and refuses a differing existing tag or release. Never rebuild against a newer
PR commit, overwrite assets, move a tag, or delete an immutable release.

A runtime upgrade is a reviewed lock change independent of nightly pins. Include
source/license and SBOM differences, exact release digest, and cross-platform CI
evidence. Publication alone does not promote the dependency into platform builds.
