package main

//#cgo CFLAGS: -Wno-main-return-type
import "C"
import (
	"fmt"
	_ "host/roc"
)

//export roc_stderr_line
func roc_stderr_line() {
	fmt.Println("roc_stderr_line called")
}

//export roc_stdin_line
func roc_stdin_line() {
	fmt.Println("roc_stdin_line called")
}

//export roc_stdout_line
func roc_stdout_line() {
	fmt.Println("roc_stdout_line called")
}

//export main
func main() {
	fmt.Println("in go main")
}
