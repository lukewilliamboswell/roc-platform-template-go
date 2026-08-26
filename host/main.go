package main

/*
#include "roc/roc_std.h"
*/
import "C"

import (
	"host/roc"
	"unsafe"
)

// unsafeArgv is the C runtime's argv, passed untyped so the per-OS
// processArgs implementations can decide whether to read it at all.
type unsafeArgv = unsafe.Pointer

//export go_platform_main
func go_platform_main(argc C.int, argv **C.char) C.int {
	strArgs := processArgs(int(argc), unsafeArgv(argv))
	args := make([]roc.RocStr, len(strArgs))
	for i, arg := range strArgs {
		args[i] = roc.NewRocStr(arg)
	}

	rocArgs := roc.NewRocList(args)
	cRocArgs := *(*C.RocList)(unsafe.Pointer(&rocArgs))
	return C.int(C.roc_main(cRocArgs))
}

// A main function is required when building a Go c-archive. The actual C entry
// point lives in startup.c so it can receive argc and argv from the C runtime.
func main() {}
