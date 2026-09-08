# Signed runtime provenance

The dedicated runtime release workflow signs the independently built and tested
runtime archive using GitHub artifact attestations and short-lived Sigstore OIDC
certificates. There are no stored signing keys. See [the release process](RUNTIME_PROVENANCE.md).

The release carries two distinct claims:

- SLSA v1 build provenance covers the exact runtime tarball and SPDX SBOM file.
- An SPDX SBOM attestation binds the source/component/file inventory to that
  tarball's digest.

Both verification bundles are downloadable release assets as well as records in
GitHub's attestations service. The consumer verifies both predicate types, plus
the source and signer commit, expected repository/workflow/main ref, and
GitHub-hosted runner identity. It compares the downloaded SBOM with the verified
predicate. A checksum alone, an attestation from another workflow, or a valid
signature for another commit is insufficient.

Build and test jobs have read-only repository credentials. Attestation permissions
exist only in the signing job; release write permission exists only in the
publisher. The publisher verifies and uploads the same tested artifacts. It does
not execute them. The source manifest in the signed tarball records the upstream
Zig distribution digest and bundled component sources; generic GitHub provenance
itself should not be interpreted as automatically enumerating those dependencies.

This establishes signed build provenance and an authenticated dependency inventory.
It is not a claim of a particular SLSA level or comprehensive OpenSSF compliance.
Report measured checks and remaining limitations, including native ARM64 Windows
execution, rather than inferring guarantees from an attestation badge.
