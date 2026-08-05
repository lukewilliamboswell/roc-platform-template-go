package roc

/*
#include "./roc_std.h"
*/
import "C"

import (
	"unsafe"
)

const refcountOne = 1 << 63
const is64Bit = uint64(^uintptr(0)) == ^uint64(0)
const intSize = 32 << (^uint(0) >> 63)
const intBytes = intSize / 8

// allocForRoc allocates memory. Prefixes that memory with a refcounter set to
// one.
func allocForRoc(size int) unsafe.Pointer {
	// TODO: find out alignment
	refCountPtr := roc_alloc(C.size_t(size)+intBytes, intBytes)
	ptr := unsafe.Add(refCountPtr, intBytes)
	setRefCountToOne(ptr)
	return ptr
}

// freeForRoc frees the memory with its refcounter.
func freeForRoc(ptr unsafe.Pointer) {
	refcountPtr := unsafe.Add(ptr, -intBytes)
	roc_dealloc(refcountPtr, 0)
}

// decRefCount reduces the refcounter by one.
//
// If the refcounter gets 0, the memory is freed.
func decRefCount(ptr unsafe.Pointer) {
	refcountPtr := unsafe.Add(ptr, -intBytes)

	switch *(*uint)(refcountPtr) {
	case refcountOne:
		freeForRoc(ptr)
	case 0:
		// Data is static. Nothing to do
	default:
		*(*uint)(refcountPtr) -= 1
	}
}

func setRefCountToInfinity(ptr unsafe.Pointer) {
	// Setting the refcount to 0 tells roc, not to modify it.
	refcountPtr := unsafe.Add(ptr, -intBytes)
	*(*uint)(refcountPtr) = 0
}

func setRefCountToOne(ptr unsafe.Pointer) {
	refcountPtr := unsafe.Add(ptr, -intBytes)
	*(*uint)(refcountPtr) = refcountOne
}

//export roc_alloc
func roc_alloc(size C.size_t, alignment C.size_t) unsafe.Pointer {
	_ = alignment
	return C.malloc(size)
}

//export roc_realloc
func roc_realloc(ptr unsafe.Pointer, newSize C.size_t, alignment C.size_t) unsafe.Pointer {
	_ = alignment
	return C.realloc(ptr, newSize)
}

//export roc_dealloc
func roc_dealloc(ptr unsafe.Pointer, alignment C.size_t) {
	_ = alignment
	C.free(ptr)
}

//export roc_crashed
func roc_crashed(bytes *byte, len C.size_t) {
	panic("roc_crashed called TODO")
}

//export roc_expect_failed
func roc_expect_failed(bytes *byte, len C.size_t) {
	panic("roc_expect_failed called TODO")
}

//export roc_dbg
func roc_dbg(bytes *byte, len C.size_t) {
	panic("roc_expect_failed called TODO")
}
