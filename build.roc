app [main] {
    cli: platform "https://github.com/roc-lang/basic-cli/releases/download/0.10.0/vNe6s9hWzoTZtFmNkvEICPErI9ptji_ySjicO6CkucY.tar.br",
}

import cli.Cmd
import cli.Task exposing [Task]

main =

    # generate glue for builtins and platform
    Cmd.exec "roc" ["glue", "glue.roc", "host/", "platform/main.roc"]
        |> Task.mapErr! ErrGeneratingGlue

    # get the native target
    native = getNativeTarget!

    # build the target
    buildGoTarget! { target: native, hostDir: "host", platformDir: "platform" }

buildGoTarget : { target : RocTarget, hostDir : Str, platformDir : Str } -> Task {} _
buildGoTarget = \{ target, hostDir, platformDir } ->

    (goos, goarch, prebuiltBinary) =
        when target is
            MacosArm64 -> ("darwin", "arm64", "macos-arm64.a")
            MacosX64 -> ("darwin", "amd64", "macos-x64")
            LinuxArm64 -> ("linux", "arm64", "linux-arm64.a")
            LinuxX64 -> ("linux", "amd64", "linux-x64.a")
            WindowsArm64 -> ("windows", "arm64", "windows-arm64.a")
            WindowsX64 -> ("windows", "amd64", "windows-x64")

    Cmd.new "go"
        |> Cmd.envs [("GOOS", goos), ("GOARCH", goarch), ("CC", "zig cc")]
        |> Cmd.args ["build", "-C", hostDir, "-buildmode=c-archive", "-o", "libhost.a"]
        |> Cmd.status
        |> Task.mapErr! \err -> BuildErr goos goarch (Inspect.toStr err)

    Cmd.exec "cp" ["$(hostDir)/libhost.a", "$(platformDir)/$(prebuiltBinary)"]
        |> Task.mapErr! \err -> CpErr (Inspect.toStr err)

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
