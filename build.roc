app [main] {
    cli: platform "https://github.com/roc-lang/basic-cli/releases/download/0.17.0/lZFLstMUCUvd5bjnnpYromZJXkQUrdhbva4xdBInicE.tar.br",
}

import cli.Cmd
import cli.Stdout
import cli.Env

main =
    {os, arch} = Env.platform!

    buildForSurgicalLinker! os arch
    buildForLegacyLinker!

exampleFile = "examples/hello-world.roc"

buildForSurgicalLinker : _, _ -> Task {} _
buildForSurgicalLinker = \os, arch ->
    buildLibappDylib! os
    buildDynhost! os arch
    preprocess! os

buildLibappDylib = \os ->
    when os is
        LINUX -> Cmd.exec! "roc" ("build --lib $(exampleFile) --output host/libapp.so" |> Str.splitOn " ")
        MACOS -> Cmd.exec! "roc" ("build --lib $(exampleFile) --output host/libapp.dylib" |> Str.splitOn " ")
        WINDOWS -> Cmd.exec! "roc" ("build --lib $(exampleFile) --output host/app.lib" |> Str.splitOn " ")
        OTHER str -> crash "unreachable - unkown os $(str)"

buildDynhost = \os, arch ->

    goos =
        when os is
            LINUX -> "linux"
            MACOS -> "darwin"
            WINDOWS -> "windows"
            OTHER str -> crash "unreachable - unkown os $(str)"

    goarch =
        when arch is
            X86 -> "386"
            X64 -> "amd64"
            ARM -> "arm"
            AARCH64 -> "arm64"
            OTHER str -> crash "unreachable - unkown arch $(str)"

    Cmd.new "go"
        |> Cmd.args ("build -C host -buildmode pie -o ../platform/dynhost" |> Str.splitOn " ")
        |> Cmd.envs [("GOOS", goos), ("GOARCH", goarch), ("CC", "zig cc"), ("CGO_ENABLED", "1")]
        |> Cmd.status
        |> Task.mapErr BuildDynhost

preprocess = \os ->
    when os is
        LINUX -> Cmd.exec! "roc" ["preprocess-host", "platform/dynhost", "platform/main.roc", "host/libapp.so"]
        MACOS -> Cmd.exec! "roc" ["preprocess-host", "platform/dynhost", "platform/main.roc", "host/libapp.dylib"]
        WINDOWS -> Cmd.exec! "roc" ["preprocess-host", "platform/dynhost", "platform/main.roc", "host/app.lib"]
        OTHER str -> crash "unreachable - unkown os $(str)"

buildForLegacyLinker : Task {} _
buildForLegacyLinker =
    [MacosArm64, MacosX64, LinuxArm64, LinuxX64, WindowsArm64, WindowsX64]
        |> List.map \target -> buildDotA target
        |> Task.sequence
        |> Task.map \_ -> {}
        |> Task.mapErr! \_ -> BuildForLegacyLinker

buildDotA = \target ->
    (goos, goarch, zigTarget, prebuiltBinary) =
        when target is
            MacosArm64 -> ("darwin", "arm64", "aarch64-macos", "macos-arm64.a")
            MacosX64 -> ("darwin", "amd64", "x86_64-macos", "macos-x64.a")
            LinuxArm64 -> ("linux", "arm64", "aarch64-linux", "linux-arm64.a")
            LinuxX64 -> ("linux", "amd64", " x86_64-linux", "linux-x64.a")
            WindowsArm64 -> ("windows", "arm64", "aarch64-windows", "windows-arm64.obj")
            WindowsX64 -> ("windows", "amd64", "x86_64-windows", "windows-x64.obj")
    Stdout.line! "build host for $(Inspect.toStr target)"

    Cmd.new "go"
        |> Cmd.envs [("GOOS", goos), ("GOARCH", goarch), ("CC", "zig cc -target $(zigTarget)"), ("CGO_ENABLED", "1")]
        |> Cmd.args ("build -C host -buildmode c-archive -o ../platform/$(prebuiltBinary) -tags legacy,netgo" |> Str.splitOn " ")
        |> Cmd.status
        |> Task.mapErr! \err -> BuildErr target (Inspect.toStr err)
