# Roc platform template for Go

A command-line Roc platform with a Go host for arguments, UTF-8 stdin/stdout/stderr
and process exit codes. It supports Linux musl and macOS on x86-64 and ARM64,
and Windows MinGW on x86-64. Windows ARM64 is not supported.

## Run an example

Install the [latest Roc nightly](https://github.com/roc-lang/nightlies/releases/latest),
then download and extract the examples ZIP from the
[latest platform release](https://github.com/lukewilliamboswell/roc-platform-template-go/releases/latest):

```sh
roc examples/hello_world/main.roc
```

The example prints `Hello, World!`. Released examples use their immutable
platform bundle and need no Go host build.

To work on this checkout, install the tools in [Contributing](CONTRIBUTING.md),
then run from the repository root:

```sh
blueprint run fetch-runtime
blueprint run build-host
roc examples/hello_world/main.roc
```

Checkout examples use the local platform and the current Roc nightly.
[Contributing](CONTRIBUTING.md) covers testing, generated ABI bindings and releases.
[Linker inputs](LINKER_INPUTS.md) explains reviewed dependency adoption and routine
hash verification; [runtime sources](RUNTIME_PROVENANCE.md) describes their
contents and reproduction. See [provenance](SLSA_PROVENANCE.md) for the trust
boundary and [third-party notices](THIRD_PARTY_LICENSES.md) for redistribution.
