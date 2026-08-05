platform ""
    requires {} { main! : List(Str) => Try({}, [Exit(I32), ..]) }
    exposes [Stdout, Stderr, Stdin]
    packages {}
    provides { "roc_main": main_for_host! }
    hosted {
        "roc_stderr_line": Host.stderr_line!,
        "roc_stdin_line": Host.stdin_line!,
        "roc_stdout_line": Host.stdout_line!,
    }
    targets: {
        inputs_dir: "targets/",
        x64musl: { inputs: ["crt1.o", "libhost.a", app, "libc.a"] },
    }

import Stdout
import Stderr
import Stdin
import Host

main_for_host! : List(Str) => I32
main_for_host! = |args| {
    result = main!(args)
    match result {
        Ok({}) => 0
        Err(Exit(code)) => code
        Err(other) => {
            _ = Stderr.line!("ERROR: ${Str.inspect(other)}")
            -1
        }
    }
}
