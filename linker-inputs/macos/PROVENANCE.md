# macOS linker-interface provenance

`interfaces.json` is a project-authored list of symbol names needed to link the
current Go host. It is not copied from an Apple SDK, framework, binary, or TBD.
The names were audited from unresolved symbols in the repository's own x86_64
host archive and checked against public Go runtime source and Apple open-source
Libc material. The Go runtime/cgo dependencies are architecture-neutral; native
arm64 CI is required before release. The generated file contains linkage metadata only; macOS provides
the implementation at execution time.

The catalog intentionally covers only `libSystem`. Review and regenerate it
when the Go pin, host sources, compiler flags, or target list changes. Native
macOS CI is the final compatibility check. This provenance file, catalog, and
their hashes are included in every linker-input archive and SBOM.
