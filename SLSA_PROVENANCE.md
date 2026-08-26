# SLSA provenance

The checked-in Zig runtime and system-link artifacts use two complementary
controls:

1. [`scripts/zig_runtime.sha256`](scripts/zig_runtime.sha256) is the central
   integrity manifest. Normal CI fails if any managed artifact does not match.
2. [`.github/workflows/runtime-provenance.yml`](.github/workflows/runtime-provenance.yml)
   independently rebuilds every artifact with the pinned Zig toolchain,
   byte-compares the results, and asks GitHub's attestation service to create
   signed SLSA build provenance for every subject in the manifest.

The provenance is an in-toto attestation with a SLSA build-provenance predicate.
GitHub signs it with a short-lived Sigstore certificate bound to the workflow's
OIDC identity and stores it in the repository's attestations API. The signing
key is therefore not stored in this repository or exposed to maintainers.

The provenance workflow runs after relevant changes land on `main`; it can also
be started manually. Pull requests only perform the checksum check because
untrusted pull-request code must not receive attestation-writing permissions.

## Verify an artifact

After the provenance workflow has completed for the artifact's revision, use a
recent GitHub CLI:

```console
gh attestation verify platform/targets/x64musl/libc.a \
  --repo lukewilliamboswell/roc-platform-template-go
```

Verification checks the artifact digest, Sigstore signature, certificate
identity, transparency information, and repository identity. A checksum match
alone proves only integrity against this checkout; successful attestation
verification additionally establishes which GitHub workflow and source revision
produced the artifact.

## Scope and SLSA claim

This establishes signed SLSA build provenance for the vendored runtime subjects.
It does not claim that the entire repository or arbitrary developer builds meet
a particular SLSA level. Level claims must be assessed against the build
platform and workflow controls in the applicable version of the SLSA
specification.

The older `slsa-framework/slsa-github-generator` generic generator is not used
because its maintainers now mark it as unmaintained and recommend GitHub artifact
attestations for new integrations.
