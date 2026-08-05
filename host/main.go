package main

/*
#include "roc/roc_std.h"
*/
import "C"

import (
	"host/roc"
	"unsafe"
)

//export go_platform_main
func go_platform_main(argc C.int, argv **C.char) C.int {
	count := int(argc)
	args := make([]roc.RocStr, count)
	if count > 0 {
		cArgs := unsafe.Slice(argv, count)
		for i, arg := range cArgs {
			args[i] = roc.NewRocStr(C.GoString(arg))
		}
	}

	rocArgs := roc.NewRocList(args)
	cRocArgs := *(*C.RocList)(unsafe.Pointer(&rocArgs))
	return C.int(C.roc_main(cRocArgs))
}

// A main function is required when building a Go c-archive. The actual C entry
// point lives in startup.c so it can receive argc and argv from the C runtime.
func main() {}
