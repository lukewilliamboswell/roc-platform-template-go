# Roc platform template for Go

This is a template for getting started with a [roc
platform](https://www.roc-lang.org/platforms) using [Go](https://golang.org).

If you have any ideas to improve this template, please let me know. 😀


## Developing locally

Build the platform with `roc build.roc` to produce the prebuilt-binaries in
`platform/`.

Then you will be able to run `roc example/hello-world.roc`.

This requires zig 0.11.0. Newer version of zig have an
[issue](https://github.com/ziglang/zig/issues/20689).


## Packaging the platform

Bundle the platform source and prebuilt-binaries with `roc build --bundle
.tar.br platform/main.roc`, and then upload to a URL.


## Platform documentation

Generate the documentation with `roc docs platform/main.roc` and then serve the
files in `generated-docs/` using a webserver.


## Advaced - LLVM IR

You can generate the LLVM IR for the app with `roc build --emit-llvm-ir app.roc`
which is an authoritative reference for what roc will generate in the
application object.
