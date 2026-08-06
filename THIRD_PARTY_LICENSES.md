# Third-party licenses

The files below are vendored as static-link inputs under
`platform/targets/{x64musl,x64v1musl,arm64musl,arm64v1musl}/`:

- `crt1.o` and `libc.a`: musl libc 1.2.5 with Zig's security backports
- `libzigc.a`: Zig libc 0.16.0
- `libcompiler_rt.a`: compiler runtime emitted by Zig 0.16.0

The MinGW targets under
`platform/targets/{x64mingw,x64v1mingw,arm64mingw,arm64v1mingw}/` vendor:

- `crt2.obj` and `libmingw32.lib`: mingw-w64 startup and C runtime support
- `zigc.lib` and `compiler_rt.lib`: Zig libc and compiler runtime support
- `api-ms-win-crt-*.lib` and the named Windows `.lib` files: import metadata
  for Windows system libraries; these archives contain no Microsoft runtime
  implementation

The platform also vendors Zig's Darwin text-based interface stub at
`platform/targets/macos-sysroot/usr/lib/libSystem.tbd`. It supplies symbol
metadata for cross-linking; it does not contain Apple's libSystem runtime.

These files are generated or copied by `scripts/vendor_zig_runtime.py` from
the libc sources and interface metadata in the pinned Zig 0.16.0 distribution.
See `RUNTIME_PROVENANCE.md` for the exact process and checksums.

## musl libc

musl as a whole is licensed under the following standard MIT license:

Copyright © 2005-2020 Rich Felker, et al.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

The exact upstream notice shipped by Zig is checked in at
[`licenses/musl-COPYRIGHT`](licenses/musl-COPYRIGHT). It includes the complete
author list, third-party derivation notices, and attribution exceptions.

## Zig and Zig libc

The MIT License (Expat)

Copyright (c) Zig contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

The exact Zig distribution notice is checked in at
[`licenses/zig-LICENSE`](licenses/zig-LICENSE). Zig's compiler runtime is Zig
source distributed under this project license.

## mingw-w64

The mingw-w64 runtime and startup sources are distributed under the Zope
Public License 2.1, except for files marked with their own public-domain, BSD,
or LGPL terms. The exact notice shipped in Zig 0.16.0 is checked in at
[`licenses/mingw-w64-COPYING`](licenses/mingw-w64-COPYING).
