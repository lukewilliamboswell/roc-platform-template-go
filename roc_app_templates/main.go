package roc_app

/*
#cgo LDFLAGS: -L.. -lapp
#include "./main.h"
*/
import "C"

import (
	"fmt"
	"host/roc_std"
	"os"
	"unsafe"
)

func Main() roc_std.RocStr {
	var str C.struct_RocStr
	C.roc__mainForHost_1_exposed_generic(&str)
	return *(*roc_std.RocStr)(unsafe.Pointer(&str))
}

//export roc_alloc
func roc_alloc(size C.ulong, alignment int) unsafe.Pointer {
	return C.malloc(size)
}

//export roc_realloc
func roc_realloc(ptr unsafe.Pointer, newSize, _ C.ulong, alignment int) unsafe.Pointer {
	return C.realloc(ptr, newSize)
}

//export roc_dealloc
func roc_dealloc(ptr unsafe.Pointer, alignment int) {
	C.free(ptr)
}

//export roc_dbg
func roc_dbg(loc *C.struct_RocStr, msg *C.struct_RocStr, src *C.struct_RocStr) {
	locStr := *(*roc_std.RocStr)(unsafe.Pointer(loc))
	msgStr := *(*roc_std.RocStr)(unsafe.Pointer(msg))
	srcStr := *(*roc_std.RocStr)(unsafe.Pointer(src))

	if srcStr == msgStr {
		fmt.Fprintf(os.Stderr, "[%s] {%s}\n", locStr, msgStr)
	} else {
		fmt.Fprintf(os.Stderr, "[%s] {%s} = {%s}\n", locStr, srcStr, msgStr)
	}
}
