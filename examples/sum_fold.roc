app [main!] { pf: platform "../platform/main.roc" }

import pf.Stdout

# Demonstrates parsing CLI values, mapping errors, and folding decoded numbers.

main! : List(Str) => Try({}, [Exit(I32), InvalidNumber(Str), StdoutErr(Str), ..])
main! = |args| {
	provided_numbers = args.drop_first(1)
	raw_numbers = if provided_numbers.is_empty() ["1", "2", "3"] else provided_numbers
	numbers = parse_numbers(raw_numbers)?
	labels = numbers.map(|number| number.to_str())

	Stdout.line!("Numbers: ${Str.join_with(labels, ", ")}")?
	Stdout.line!("Total: ${sum(numbers).to_str()}")?
	Ok({})
}

parse_numbers : List(Str) -> Try(List(I64), [InvalidNumber(Str), ..])
parse_numbers = |raw_numbers| {
	var $numbers = []

	for raw in raw_numbers {
		number = I64.from_str(raw) ? |_| InvalidNumber(raw)
		$numbers = $numbers.append(number)
	}

	Ok($numbers)
}

sum : List(I64) -> I64
sum = |numbers| numbers.fold(0, |total, number| total + number)

## Parsing exposes all decoded values to the test.
expect {
	numbers = parse_numbers(["10", "-3", "5"])?
	numbers == [10, -3, 5]
}

## The rejected CLI value is retained in a domain-specific error.
expect parse_numbers(["10", "many", "5"]) == Err(InvalidNumber("many"))

## Folding an empty list has the additive identity as its total.
expect sum([]) == 0

## Folding supports both positive and negative numbers.
expect sum([10, -3, 5]) == 12
