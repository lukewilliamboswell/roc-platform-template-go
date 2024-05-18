package main

//#cgo CFLAGS: -Wno-main-return-type
import "C"

import (
	"fmt"
	"host/roc"
)

//export main
func main() {
	var foo = roc.Main()

	fmt.Print(foo)
}

