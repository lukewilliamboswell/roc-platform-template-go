package main

import (
	"host/roc"
	"os"
)

func entry() {
	var exitCode = roc.Main()
	os.Exit(exitCode)
}
