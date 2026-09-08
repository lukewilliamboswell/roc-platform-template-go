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

## Publish an independent runtime version

Merge reviewed recipe changes to `main`, then dispatch **Release runtime
dependencies** with a new numeric version, for example `0.1.0`. The workflow
captures the dispatch commit and accepts no alternative source ref. It:

1. Checks that neither the runtime tag nor release already exists.
2. Builds twice using isolated caches and the checksum-pinned Zig distribution.
3. Compares archives and metadata byte-for-byte. The first `0.1.0` release must
   match the original `scripts/runtime_bootstrap.sha256` binary baseline.
4. Runs the full existing cross-builder and native application validation matrix
   with the candidate archive. These jobs have read-only permissions.
5. In a separate job that executes no build scripts, creates SLSA provenance for
   the archive and SBOM and an SBOM attestation bound to the archive digest.
6. Verifies the signed assets, creates a draft `runtime-vX.Y.Z` release targeting
   the tested commit, uploads and reads back all assets, then publishes it. Runtime
   releases are never designated the latest platform release.

The release contains the tarball, `runtime.spdx.json`, `SHA256SUMS`,
`provenance.sigstore.json`, `sbom.sigstore.json`, and a proposed consumer lock
named `runtime-release.json`. Published releases must be immutable.

Routine nightly and pull-request CI cannot publish or attest runtime releases.

## Consume and verify

`scripts/runtime_release.json` is the reviewed dependency lock. Routine CI fetches
that exact release; generated runtime files are ignored rather than tracked.
Git history is preserved. The normal contributor sequence is:

```console
python scripts/fetch_runtime.py
python scripts/build.py --all
python scripts/test.py --operation all
python scripts/bundle.py --output-dir dist
```

The fetcher needs Python 3.11+ and a GitHub CLI supporting `gh attestation verify`
with signer/source digest constraints. CI uses its read-only GitHub token.
It downloads immutable versioned assets and checks the locked archive digest,
provenance, SBOM, repository, workflow, source commit, signer commit, main ref,
and GitHub-hosted runner identity before extraction. The published SBOM must
match its signed predicate and every archive file checksum.

Only the declared regular-file inventory may be installed. Traversal, links,
duplicate entries, missing files, and unexpected paths fail validation. The
installation preserves separately generated host archives. Cached assets live
under `.runtime-cache/<sha256>`; every fetch reauthenticates them, and bundle
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

Publication rejects reused versions rather than replacing assets or tags. If a
run stops after creating a draft, retain the run's `runtime-signed` artifact and
inspect the draft, tag commit, signatures, and uploaded hashes. Recovery is manual:
only upload missing assets from that original signed artifact, require existing
assets to match byte-for-byte, verify all downloads, then publish the draft. Never
rebuild against a newer main commit, overwrite assets, move a tag, or delete a
published release. If the exact signed artifact cannot be recovered, leave the
partial version unused and select a new version.

A runtime upgrade is a reviewed lock change independent of nightly pins. Include
source/license and SBOM differences, exact release digest, and cross-platform CI
evidence. Publication alone does not promote the dependency into platform builds.
