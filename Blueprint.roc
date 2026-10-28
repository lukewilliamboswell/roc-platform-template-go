# Product code uses the latest nightly supplied as bare `roc`.
# Blueprint locks native toolchain downloads separately from that compiler.
app [config] { pf: platform "https://github.com/lukewilliamboswell/roc-blueprint/releases/download/0.8.0/FbJymjYdCxx9vqMcau7r4tQfeAbnVGqqJoYrLGqPCqKu.tar.zst" }

import pf.Config
import pf.System

go_tool : System -> Config.Download
go_tool = |system|
	match system {
		"x86_64-linux" => Archive("https://go.dev/dl/go1.27.0.linux-amd64.tar.gz", TarGz, "go/bin/go")
		"aarch64-linux" => Archive("https://go.dev/dl/go1.27.0.linux-arm64.tar.gz", TarGz, "go/bin/go")
		"aarch64-darwin" => Archive("https://go.dev/dl/go1.27.0.darwin-arm64.tar.gz", TarGz, "go/bin/go")
		_ => Unavailable
	}

zig_tool : System -> Config.Download
zig_tool = |system|
	match system {
		"x86_64-linux" => Archive("https://ziglang.org/download/0.16.0/zig-x86_64-linux-0.16.0.tar.xz", TarXz, "zig-x86_64-linux-0.16.0/zig")
		"aarch64-linux" => Archive("https://ziglang.org/download/0.16.0/zig-aarch64-linux-0.16.0.tar.xz", TarXz, "zig-aarch64-linux-0.16.0/zig")
		"aarch64-darwin" => Archive("https://ziglang.org/download/0.16.0/zig-aarch64-macos-0.16.0.tar.xz", TarXz, "zig-aarch64-macos-0.16.0/zig")
		_ => Unavailable
	}

config = [
	Name("roc-platform-template-go"),
	Systems(["x86_64-linux", "aarch64-linux", "aarch64-darwin"]),
	Environment("source", [Expect(["python", "roc", "git", "gh"])]),
	Environment("host", [Programs([Fetch("go", go_tool), Fetch("zig", zig_tool)]), Expect(["python", "roc", "git", "gh", "sh"])]),
	Task("check", [Use("source"), Run(["python", "scripts/check.py"])]),
	Task("fetch-runtime", [Use("source"), Run(["python", "scripts/fetch_runtime.py"])]),
	Task("build-host", [Use("host"), Run(["python", "scripts/build.py", "--all"])]),
	Task("test-host", [Use("host"), Run(["python", "scripts/test_host.py"])]),
	Task("check-glue", [Use("source"), Run(["python", "scripts/generate_c_glue.py", "--check"])]),
	Task("update-glue", [Use("source"), Run(["python", "scripts/generate_c_glue.py"])]),
	Task("bundle", [Use("source"), Run(["python", "scripts/bundle.py"])]),
	Task("test-examples", [Use("source"), Run(["python", "scripts/test.py", "--operation", "all", "--verbose"])]),
	Task("produce", [Use("source"), Run(["python", "scripts/test.py", "--operation", "produce"])]),
	Task("package-release", [Use("source"), Run(["python", "scripts/package_release.py"])]),
	Task("test-release", [Use("source"), Run(["python", "scripts/test_release.py"])]),
]
