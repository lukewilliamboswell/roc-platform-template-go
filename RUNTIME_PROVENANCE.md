# Vendored runtime provenance

The Linux and Windows platform targets intentionally check in their C startup,
runtime, and system-import archives. This lets Roc link standalone executables
without requiring the application user to install a C toolchain or SDK.

## Source

- Toolchain: Zig 0.16.0
- Upstream release: <https://ziglang.org/download/0.16.0/>
- libc: musl 1.2.5 plus the security fixes shipped by Zig 0.16.0
- Windows runtime: mingw-w64 and Universal CRT import libraries shipped by Zig
- Source targets: `x86_64-linux-musl`, `aarch64-linux-musl`,
  `x86_64-windows-gnu`, and `aarch64-windows-gnu`
- Roc targets: `x64musl`, `x64v1musl`, `arm64musl`, `arm64v1musl`,
  `x64mingw`, `x64v1mingw`, `arm64mingw`, and `arm64v1mingw`
- macOS interface stub: Zig's `lib/libc/darwin/libSystem.tbd`

Zig 0.16.0 builds its static musl environment from both musl source and Zig
libc source, so all four emitted inputs are kept explicit rather than merging
them into an opaque archive:

- `crt1.o`
- `libc.a`
- `libzigc.a`
- `libcompiler_rt.a`

The Go-specific musl constructor adapter is not patched into these artifacts.
It is the reviewed source in `host/startup.c` and is built into `libhost.a`.

The MinGW targets carry Zig's `crt2.obj`, `libmingw32.lib`, `zigc.lib`,
`compiler_rt.lib`, and the exact UCRT/Windows import libraries from Zig's
link recipe. Import libraries contain symbol metadata for Windows system DLLs;
the DLL implementations remain part of Windows and are not redistributed.

The Darwin text-based interface stub is checked in at
`platform/targets/macos-sysroot/usr/lib/libSystem.tbd`. Roc automatically uses
that platform-provided sysroot when cross-linking macOS applications. It
contains symbol/interface metadata only; the actual libSystem runtime remains
part of macOS. Including the stub is what lets Linux and Windows CI producers
link the macOS targets without an Apple SDK installation.

## Reproduce and verify

With exactly Zig 0.16.0 on `PATH`:

```console
# Rebuild in isolated Zig caches, verify pinned hashes, and replace artifacts
python scripts/vendor_zig_runtime.py

# Rebuild in isolated caches and byte-compare with the checked-in artifacts
python scripts/vendor_zig_runtime.py --check
```

`scripts/zig_runtime.sha256` pins every emitted file, including the Darwin
interface stub. A Zig upgrade is an explicit review: update the version in the
script, inspect upstream runtime and license changes, regenerate the files,
then update the manifest.

This maintainer-only reproduction is intentionally not part of normal CI.
CI links and executes the checked-in artifacts through freshly built platform
bundles; it does not regenerate toolchain runtime libraries.

Zig's archive members contain randomized cache paths. The vendoring script
uses a fixed-length temporary path, extracts members in their original order,
gives them stable indexed names, and replaces only that equal-length cache-root
string with a canonical spelling. MinGW objects are built with stripped output;
their residual CodeView payloads are cleared and marked for linker removal
without changing section layout, code, symbols, or relocations. Go host archives
are built with symbol and DWARF stripping enabled, and Windows archives are
re-indexed with Zig for consistent COFF linker lookup. Independent clean builds
are therefore byte-identical without embedding a maintainer or checkout path.

The `v1` target copies are byte-identical to their architecture's base musl or
MinGW target. Roc's `v1` distinction applies to application CPU features,
while these C ABI/runtime inputs are already built for the architecture
baseline.
