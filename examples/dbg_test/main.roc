app [main!] { pf: platform "../../platform/main.roc", roc: "nightly-2026-10-24-f6c6cfb" }

import pf.Stdout

main! : List(Str) => Try({}, [Exit(I32), StdoutErr(Str)])
main! = |_args| {
	dbg "test message"
	Stdout.line!("stdout works")?
	Ok({})
}
