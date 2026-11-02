# Verify linker-input provenance

GitHub build-provenance attestations bind the candidate archives and aggregate
manifest to their producer workflow and source commit. The trusted publisher
checks those identities and the tested artifact inventory before admitting an
immutable release and its signed content lock. Follow [the admission
procedure](LINKER_INPUTS.md) when changing that dependency.

Routine builds verify the reviewed archive size, SHA-256 and member inventory,
including cache hits. They do not repeat online attestation admission or accept
a differently signed artifact as a substitute for the locked bytes.

Provenance identifies the recorded producer and artifact; the source inventory
and license notices describe the packaged components. Neither proves that the
software is free of defects, establishes complete dependency coverage, or
constitutes a claimed SLSA level or OpenSSF certification. Native execution
coverage remains separate from archive integrity.
