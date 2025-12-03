platform ""
    requires {} { main! : List(Str) => Try({}, [Exit(I32)]) }
    exposes [Stdout, Stderr, Stdin]
    packages {}
    provides { main_for_host! : "main_for_host" }
    targets: {
        files: "targets/",
        exe: {
            arm64mac: ["libhost.a", app],
        }
    }

import Stdout
import Stderr
import Stdin

main_for_host! : List(Str) => I32
main_for_host! = |args| {
    result = main!(args)
    match result {
        Ok({}) => 0
        Err(Exit(code)) => code
    }
}
