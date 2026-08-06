app [main!] { pf: platform "../platform/main.roc" }

import pf.Stdout

# A nominal error can provide the human-facing representation used by the
# platform's final `Str.inspect` error boundary.
CommandError := [OperationFailed, UnknownCommand(Str)].{
	to_inspect : CommandError -> Str
	to_inspect = |error| match error {
		OperationFailed => "the operation failed"
		UnknownCommand(command) => "unknown command ${Str.inspect(command)}; expected \"success\" or \"failure\""
	}
}

main! : List(Str) => Try({}, [ApplicationError(CommandError), Exit(I32), StdoutErr(Str), ..])
main! = |args| {
	command = args.get(1) ?? "failure"

	match command {
		"success" => {
			Stdout.line!("The operation completed successfully.")?
			Ok({})
		}
		"failure" => application_error(OperationFailed)
		_ => application_error(UnknownCommand(command))
	}
}

application_error : CommandError -> Try({}, [ApplicationError(CommandError), ..])
application_error = |error| Err(ApplicationError(error))

## A nominal error controls how it appears inside the platform error tag.
expect {
	error : CommandError
	error = OperationFailed
	Str.inspect(error) == "the operation failed"
}

## Custom inspection can retain useful context while presenting clear guidance.
expect {
	error : CommandError
	error = UnknownCommand("maybe")
	Str.inspect(error) == "unknown command \"maybe\"; expected \"success\" or \"failure\""
}
