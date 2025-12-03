// Package rocstd provides Go bindings for Roc standard library types.
//
// This package provides type-safe wrappers for Roc's core types like RocStr
// and RocList, abstracting away the low-level memory layout details and
// providing an idiomatic Go API.
//
// # Thread Safety
//
// This package is NOT thread-safe. The following limitations apply:
//   - RocStr and RocList types use non-atomic reference counting
//   - Concurrent access to the same RocStr or RocList is unsafe
//   - DefaultOps() returns a shared instance - do not use from multiple goroutines
//   - All operations should be performed from a single goroutine
//
// If you need concurrent access, use external synchronization (mutex) or
// create separate copies for each goroutine.
package rocstd

/*
#include <stdlib.h>
#include <string.h>
*/
import "C"

import "unsafe"

// Memory layout constants for Roc types.
const (
	// Size of RocStr and RocList structs (3 usizes = 24 bytes on 64-bit)
	RocStructSize = 24

	// Maximum length for small strings (stored inline in the struct)
	SmallStrMaxLen = RocStructSize - 1 // 23 bytes

	// SeamlessSliceBit is set in length to indicate a seamless slice
	SeamlessSliceBit = uintptr(1) << 63

	// SmallStrMarker is set in the last byte to mark a small string
	SmallStrMarker = byte(0x80)

	// RefcountOne is the value representing a refcount of 1
	RefcountOne = int64(1)

	// RefcountSize is the size of the refcount header
	RefcountSize = 8

	// ElementCountSize is the size of the element count header (for lists with refcounted elements)
	ElementCountSize = 8
)

// cMalloc allocates memory using C malloc.
func cMalloc(size uintptr) unsafe.Pointer {
	return C.malloc(C.size_t(size))
}

// cFree frees memory allocated by C malloc.
func cFree(ptr unsafe.Pointer) {
	C.free(ptr)
}

// cRealloc reallocates memory using C realloc.
func cRealloc(ptr unsafe.Pointer, size uintptr) unsafe.Pointer {
	return C.realloc(ptr, C.size_t(size))
}

// cMemcpy copies n bytes from src to dst.
func cMemcpy(dst, src unsafe.Pointer, n uintptr) {
	C.memcpy(dst, src, C.size_t(n))
}
