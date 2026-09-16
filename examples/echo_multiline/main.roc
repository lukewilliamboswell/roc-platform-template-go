app [main!] { pf: platform "../../platform/main.roc", roc: "nightly-2026-09-16-a49a16f" }

import pf.Stdin
import pf.Stdout

# Echoes input as it arrives instead of retaining the entire stream in memory.

main! : List(Str) => Try({}, [Exit(I32), StdinErr(Str), StdoutErr(Str), ..])
main! = |_args| {
	var $reading = True

	while $reading {
		line = Stdin.line!({})?

		if line == "" {
			$reading = False
		} else {
			Stdout.line!(line)?
		}
	}

	Ok({})
}
