app [main!] { pf: platform "../../platform/main.roc", roc: "nightly-2026-09-11-793f9d8" }

import pf.Stdout

main! : List(Str) => Try({}, [Exit(I32), StdoutErr(Str), ..])
main! = |_args| {
	Stdout.line!("Hello, World!")?
	Ok({})
}
