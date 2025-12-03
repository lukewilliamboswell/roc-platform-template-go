# Roc Platform Template for Go

A template for building [Roc platforms](https://www.roc-lang.org/platforms) with a C/Go host.

## Quick Start

Build the platform:
```sh
make build
```

Run an example:
```sh
roc examples/hello-world.roc
```

## Examples

| Example | Description |
|---------|-------------|
| `hello-world.roc` | Print greeting and command-line args |
| `fizzbuzz.roc` | Classic FizzBuzz 1-15 |
| `exit.roc` | Exit with non-zero code |
| `stderr.roc` | Write to stdout and stderr |
| `match.roc` | Pattern matching demo |
| `sum_fold.roc` | List operations |
| `echo.roc` | Read from stdin and echo back |
| `tests.roc` | Run with `roc test` |

## Building

```sh
make build    # Build for current platform
make clean    # Remove build artifacts
make info     # Show build configuration
```

The build produces `platform/libhost.a` (or `host.lib` on Windows).

## Project Structure

```
platform/
  main.roc          # Platform definition
  Stdout.roc        # Stdout.line! effect
  Stderr.roc        # Stderr.line! effect
  Stdin.roc         # Stdin.line! effect
  targets/          # Prebuilt host libraries per target
host/
  roc_host.c        # C host implementation
  roc_abi.h         # RocCall ABI definitions
  host.go           # Go host (for future Go integration)
examples/
  *.roc             # Example applications
```

## Packaging

Bundle the platform for distribution:
```sh
roc build --bundle .tar.br platform/main.roc
```

## Documentation

Generate platform docs:
```sh
roc docs platform/main.roc
```

Then serve the files in `generated-docs/`.
