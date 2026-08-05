app [main!] { pf: platform "../platform/main.roc" }

import pf.Stdout

main! : List(Str) => Try({}, [Exit(I32), StdoutErr(Str), ..])
main! = |args| {
	names = args.drop_first(1)
	Stdout.line!(greeting_for(names))?
	Ok({})
}

greeting_for : List(Str) -> Str
greeting_for = |names| {
	addressee = if names.is_empty() "Roc developer" else Str.join_with(names, ", ")
	"Hello, ${addressee}!"
}

## A useful default keeps the command friendly when no names are supplied.
expect greeting_for([]) == "Hello, Roc developer!"

## Every command-line name is included in the greeting.
expect greeting_for(["Ana", "Bo"]) == "Hello, Ana, Bo!"
