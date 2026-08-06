app [main!] { pf: platform "../platform/main.roc" }

import pf.Stdin
import pf.Stdout

# Demonstrates interactive I/O while propagating both read and write failures.

main! : List(Str) => Try({}, [Exit(I32), StdinErr(Str), StdoutErr(Str), ..])
main! = |_args| {
	Stdout.line!("Enter something and I'll echo it back:")?
	input = Stdin.line!({})?

	if input == "" {
		Stdout.line!("No input received.")?
	} else {
		Stdout.line!("You entered: ${input}")?
	}

	Ok({})
}
