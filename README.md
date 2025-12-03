# Roc Platform Template for Go

A template for building [Roc platforms](https://www.roc-lang.org/platforms) with a Go/C host.

## Quick Start

Build the platform:
```sh
make build
```

Run an example:
```sh
roc examples/hello-world.roc
```

Run all tests:
```sh
make test
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
make build       # Build for current platform
make test        # Run Go tests and all examples
make bundle      # Bundle platform for distribution
make clean       # Remove build artifacts
make info        # Show build configuration
```

### Cross-Compilation

Build for all supported platforms (requires [zig](https://ziglang.org/)):

```sh
make all-targets    # Build all 8 targets
make x64glibc       # Build for specific target
```

Supported targets:
- `arm64mac` - macOS ARM64
- `x64mac` - macOS x86_64
- `arm64glibc` - Linux ARM64 (glibc)
- `x64glibc` - Linux x86_64 (glibc)
- `arm64musl` - Linux ARM64 (musl)
- `x64musl` - Linux x86_64 (musl)
- `arm64win` - Windows ARM64
- `x64win` - Windows x86_64

## Project Structure

```
platform/
  main.roc          # Platform definition
  Stdout.roc        # Stdout.line! effect
  Stderr.roc        # Stderr.line! effect
  Stdin.roc         # Stdin.line! effect
  targets/          # Prebuilt host libraries per target
host/
  host.go           # Go hosted functions
  go.mod            # Go module (uses rocstd)
chost/
  roc_host.c        # C host (main, RocOps callbacks)
  roc_abi.h         # RocCall ABI definitions
rocstd/
  rocstr.go         # RocStr type
  roclist.go        # RocList[T] generic type
  rocops.go         # Memory allocation interface
  memory.go         # Memory layout constants
examples/
  *.roc             # Example applications
```

## rocstd Package

The `rocstd/` directory contains a Go package providing type-safe wrappers for Roc types:

```go
import "github.com/lukewilliamboswell/roc-platform-template-go/rocstd"

// Create a RocStr from Go string
str := rocstd.NewRocStr("hello", rocstd.DefaultOps())

// Create a RocList from Go slice
list := rocstd.NewRocList([]int{1, 2, 3}, false, rocstd.DefaultOps())

// Create a list of strings
strList := rocstd.NewRocListOfStr([]string{"a", "b", "c"}, rocstd.DefaultOps())
```

Run the Go tests:
```sh
cd rocstd && go test ./...
```

**Note:** The rocstd package is not thread-safe. See the package documentation for details.

## Packaging

Bundle the platform for distribution:
```sh
make all-targets  # Build all 8 targets first
make bundle       # Create distributable .tar.zst
```

## Documentation

Generate platform docs:
```sh
roc docs platform/main.roc
```

Then serve the files in `generated-docs/`.
