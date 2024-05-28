app [main] {
    cli: platform "https://github.com/roc-lang/basic-cli/releases/download/0.10.0/vNe6s9hWzoTZtFmNkvEICPErI9ptji_ySjicO6CkucY.tar.br",
}

import cli.Cmd
import cli.Task exposing [Task]
import cli.File
import cli.Path

main : Task {} _
main =
    Cmd.exec "roc" ["glue", "glue.roc", "host/", "platform/main.roc"]
        |> Task.mapErr! \_ -> ErrGlue

    target = getNativeTarget
        |> Task.mapErr! \_ -> BuildForLegacyLinker
    if target == LinuxX64 then
        buildForSurgicalLinker
            |> Task.mapErr! \_ -> ErrBuildForLegacyLinker
    else
        buildForLegacyLinker target
            |> Task.mapErr! \_ -> BuildForLegacyLinker

buildForSurgicalLinker : Task {} _
buildForSurgicalLinker =
    buildLibappSo!
    buildDynhost!
    preprocess!

buildLibappSo =
    Cmd.exec "roc" ("build --lib app.roc --output host/libapp.so" |> Str.split " ") 
        |> Task.mapErr!  \_ -> BuildLibApp

buildDynhost =
    Cmd.new "go"
        |> Cmd.args ("build -C host -buildmode pie -o ../platform/dynhost" |> Str.split " ")
        |> Cmd.envs [("GOOS", "linux"), ("GOARCH", "amd64"), ("CC", "zig cc")]
        |> Cmd.status
        |> Task.mapErr! \_ -> BuildDynhost

preprocess =
    Cmd.exec "roc" ("preprocess-host app.roc" |> Str.split " ")
        |> Task.mapErr!  \_ -> BuildPreprocess
    # roc preprocess creates libapp.so, that is not needed.
    File.delete! ("platform/libapp.so" |> Path.fromStr)


buildForLegacyLinker = \target ->
    (goos, goarch, zigTarget, prebuiltBinary) =
        when target is
            MacosArm64 -> ("darwin", "arm64", "aarch64-macos", "macos-arm64.a")
            MacosX64 -> ("darwin", "amd64", "x86_64-macos", "macos-x64.a")
            LinuxArm64 -> ("linux", "arm64", "aarch64-linux", "linux-arm64.a")
            LinuxX64 -> ("linux", "amd64", " x86_64-linux", "linux-x64.a")
            WindowsArm64 -> ("windows", "arm64", "aarch64-windows", "windows-arm64.obj")
            WindowsX64 -> ("windows", "amd64", "x86_64-windows", "windows-x64.obj")
            
    Cmd.new "go"
        |> Cmd.envs [("GOOS", goos), ("GOARCH", goarch), ("CC", "zig cc -target $(zigTarget)"), ("CGO_ENABLED", "1")]
        |> Cmd.args ("build -C host -buildmode c-archive -o ../platform/$(prebuiltBinary) -tags legacy,netgo" |> Str.split " ")
        |> Cmd.status
        |> Task.mapErr! \err -> BuildErr target (Inspect.toStr err)

RocTarget : [
    MacosArm64,
    MacosX64,
    LinuxArm64,
    LinuxX64,
    WindowsArm64,
    WindowsX64,
]

getNativeTarget : Task RocTarget _
getNativeTarget =

    archFromStr = \bytes ->
        when Str.fromUtf8 bytes is
            Ok str if str == "arm64\n" -> Arm64
            Ok str if str == "x86_64\n" -> X64
            Ok str -> UnsupportedArch str
            _ -> crash "invalid utf8 from uname -m"

    arch =
        Cmd.new "uname"
            |> Cmd.arg "-m"
            |> Cmd.output
            |> Task.map .stdout
            |> Task.map archFromStr
            |> Task.mapErr! \err -> ErrGettingNativeArch (Inspect.toStr err)

    osFromStr = \bytes ->
        when Str.fromUtf8 bytes is
            Ok str if str == "Darwin\n" -> Macos
            Ok str if str == "Linux\n" -> Linux
            Ok str -> UnsupportedOS str
            _ -> crash "invalid utf8 from uname -s"

    os =
        Cmd.new "uname"
            |> Cmd.arg "-s"
            |> Cmd.output
            |> Task.map .stdout
            |> Task.map osFromStr
            |> Task.mapErr! \err -> ErrGettingNativeOS (Inspect.toStr err)

    when (os, arch) is
        (Macos, Arm64) -> Task.ok MacosArm64
        (Macos, X64) -> Task.ok MacosX64
        (Linux, Arm64) -> Task.ok LinuxArm64
        (Linux, X64) -> Task.ok LinuxX64
        _ -> Task.err (UnsupportedNative os arch)
