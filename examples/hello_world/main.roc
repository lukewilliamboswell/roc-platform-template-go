app [main!] { pf: platform "../../platform/main.roc", roc: "nightly-2026-09-08-39a3f89" }

import pf.Stdout

main! : List(Str) => Try({}, [Exit(I32), StdoutErr(Str), ..])
main! = |_args| {
	Stdout.line!("Hello, World!")?
	Ok({})
}
