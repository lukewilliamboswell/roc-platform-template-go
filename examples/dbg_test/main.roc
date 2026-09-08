app [main!] { pf: platform "../../platform/main.roc", roc: "nightly-2026-09-07-14d9829" }

import pf.Stdout

main! : List(Str) => Try({}, [Exit(I32), StdoutErr(Str), ..])
main! = |_args| {
	dbg "test message"
	Stdout.line!("stdout works")?
	Ok({})
}
