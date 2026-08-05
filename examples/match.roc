app [main!] { pf: platform "../platform/main.roc" }

import pf.Stdout

# Demonstrates a total match over user input, including an explicit catch-all.

main! : List(Str) => Try({}, [Exit(I32), StdoutErr(Str), ..])
main! = |args| {
	status = args.get(1) ?? "pending"
	Stdout.line!(status_message(status))?
	Ok({})
}

status_message : Str -> Str
status_message = |status| match status {
	"pending" => "Order is waiting to be processed."
	"shipped" => "Order is on its way."
	"delivered" => "Order has arrived."
	_ => "Unknown order status: ${status}"
}

## Known statuses map to a user-facing message.
expect status_message("shipped") == "Order is on its way."

## Unexpected input remains visible instead of being silently reclassified.
expect status_message("delayed") == "Unknown order status: delayed"
