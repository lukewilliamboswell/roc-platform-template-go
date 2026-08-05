package roc

/*
#include "./roc_std.h"

static inline void *roc_pointer_from_uintptr(uintptr_t value) {
	return (void *)value;
}
*/
import "C"

import (
	"sync/atomic"
	"unsafe"
)

const intSize = 32 << (^uint(0) >> 63)
const intBytes = intSize / 8

func allocRaw(size, alignment uintptr) unsafe.Pointer {
	return C.roc_alloc(C.size_t(size), C.size_t(alignment))
}

func freeRaw(ptr unsafe.Pointer, alignment uintptr) {
	C.roc_dealloc(ptr, C.size_t(alignment))
}

// pointerFromUintptr decodes a pointer stored in a Roc ABI word. The memory is
// allocated by the C runtime, never by Go, so it is safe to recover in C.
func pointerFromUintptr(value uintptr) unsafe.Pointer {
	return C.roc_pointer_from_uintptr(C.uintptr_t(value))
}

// allocForRoc allocates a Roc value with one pointer-sized refcount word.
func allocForRoc(size uintptr) unsafe.Pointer {
	base := allocRaw(size+uintptr(intBytes), uintptr(intBytes))
	ptr := unsafe.Add(base, intBytes)
	*(*uintptr)(unsafe.Add(ptr, -intBytes)) = 1
	return ptr
}

// decRefCount releases an allocation whose visible data starts at ptr.
func decRefCount(ptr unsafe.Pointer, headerBytes, alignment uintptr) bool {
	refcountPtr := (*uintptr)(unsafe.Add(ptr, -intBytes))
	if atomic.LoadUintptr(refcountPtr) == 0 {
		return false
	}
	if atomic.AddUintptr(refcountPtr, ^uintptr(0)) != 0 {
		return false
	}

	freeRaw(unsafe.Add(ptr, -int(headerBytes)), alignment)
	return true
}
