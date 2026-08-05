app [main!] { pf: platform "../platform/main.roc" }

import pf.Stdout

# Demonstrates focused tests for both successful and rejected input.

main! : List(Str) => Try({}, [Exit(I32), StdoutErr(Str), ..])
main! = |_args| {
	Stdout.line!("Run 'roc test --verbose examples/tests.roc' to execute the tests")?
	Ok({})
}

parse_percentage : Str -> Try(U64, [InvalidPercentage(Str), PercentageOutOfRange(U64)])
parse_percentage = |raw| {
	percentage = U64.from_str(raw) ? |_| InvalidPercentage(raw)

	if percentage <= 100 {
		Ok(percentage)
	} else {
		Err(PercentageOutOfRange(percentage))
	}
}

## A percentage within the inclusive range is decoded.
expect {
	percentage = parse_percentage("85")?
	percentage == 85
}

## The lower boundary is accepted.
expect parse_percentage("0") == Ok(0)

## The upper boundary is accepted.
expect parse_percentage("100") == Ok(100)

## A value above the upper boundary is rejected with its decoded value.
expect parse_percentage("101") == Err(PercentageOutOfRange(101))

## Non-numeric input is mapped to a domain-specific error.
expect parse_percentage("eighty") == Err(InvalidPercentage("eighty"))

## Empty input is not silently treated as zero.
expect parse_percentage("") == Err(InvalidPercentage(""))
