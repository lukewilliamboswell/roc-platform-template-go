app [main!] { pf: platform "../platform/main.roc" }

import pf.Stdout

# Demonstrates a CLI default with `??`, domain error mapping with infix `?`,
# effect propagation with postfix `?`, and a bounded loop.

main! : List(Str) => Try({}, [Exit(I32), InvalidLimit(Str), LimitTooLarge(I64), LimitTooSmall(I64), StdoutErr(Str), ..])
main! = |args| {
	limit = limit_from_args(args)?
	print_fizzbuzz!(limit)?
	Ok({})
}

limit_from_args : List(Str) -> Try(I64, [InvalidLimit(Str), LimitTooLarge(I64), LimitTooSmall(I64), ..])
limit_from_args = |args| {
	# Missing input has a sensible boundary default; malformed input does not.
	raw_limit = args.get(1) ?? "15"
	limit = I64.from_str(raw_limit) ? |_| InvalidLimit(raw_limit)

	if limit < 1 {
		Err(LimitTooSmall(limit))
	} else if limit > 100 {
		Err(LimitTooLarge(limit))
	} else {
		Ok(limit)
	}
}

print_fizzbuzz! : I64 => Try({}, [StdoutErr(Str), ..])
print_fizzbuzz! = |limit| {
	var $n = 1

	while $n <= limit {
		Stdout.line!(fizzbuzz($n))?
		$n = $n + 1
	}

	Ok({})
}

fizzbuzz : I64 -> Str
fizzbuzz = |n| match (n % 3 == 0, n % 5 == 0) {
	(True, True) => "FizzBuzz"
	(True, False) => "Fizz"
	(False, True) => "Buzz"
	(False, False) => n.to_str()
}

## FizzBuzz uses the conventional output for each divisibility combination.
expect {
	actual = [fizzbuzz(1), fizzbuzz(3), fizzbuzz(5), fizzbuzz(15)]
	actual == ["1", "Fizz", "Buzz", "FizzBuzz"]
}

## Omitting the limit selects the documented default.
expect {
	limit = limit_from_args(["fizzbuzz"])?
	limit == 15
}

## An explicit valid limit is decoded directly.
expect {
	limit = limit_from_args(["fizzbuzz", "20"])?
	limit == 20
}

## A non-numeric limit is preserved in a domain-specific error.
expect limit_from_args(["fizzbuzz", "many"]) == Err(InvalidLimit("many"))

## Limits below the useful range are rejected.
expect limit_from_args(["fizzbuzz", "0"]) == Err(LimitTooSmall(0))

## Limits are capped so accidental input cannot flood the terminal.
expect limit_from_args(["fizzbuzz", "101"]) == Err(LimitTooLarge(101))
