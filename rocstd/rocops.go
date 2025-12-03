package rocstd

import "unsafe"

// RocOps provides memory allocation callbacks for Roc types.
// When creating RocStr or RocList values that need heap allocation,
// a RocOps must be provided to handle the allocation.
//
// For hosted functions, the RocOps pointer is passed by Roc.
// For testing or standalone use, use DefaultOps() which uses C malloc/free.
type RocOps struct {
	// Alloc allocates memory with the given alignment and length.
	// Returns a pointer to the allocated memory.
	Alloc func(alignment, length uintptr) unsafe.Pointer

	// Dealloc frees memory previously allocated by Alloc.
	Dealloc func(alignment uintptr, ptr unsafe.Pointer)

	// Realloc reallocates memory to a new size.
	// The ptr parameter contains both input (old pointer) and output (new pointer).
	Realloc func(alignment, newLength uintptr, ptr unsafe.Pointer) unsafe.Pointer
}

// DefaultOps returns a RocOps that uses C malloc/free for memory allocation.
// This is useful for testing or when creating Roc types outside of a hosted function.
//
// Note: The allocation layout matches Roc's expectations:
// - size_storage = max(alignment, 8) bytes for storing the total size
// - The returned pointer is offset by size_storage from the actual allocation
func DefaultOps() *RocOps {
	return &defaultOps
}

var defaultOps = RocOps{
	Alloc:   defaultAlloc,
	Dealloc: defaultDealloc,
	Realloc: defaultRealloc,
}

// defaultAlloc allocates memory using C malloc with the Roc allocation layout.
// Layout: [size_storage bytes for total size][user data]
// Returns pointer to user data (after the size header).
func defaultAlloc(alignment, length uintptr) unsafe.Pointer {
	sizeStorage := alignment
	if sizeStorage < 8 {
		sizeStorage = 8
	}
	totalSize := sizeStorage + length

	ptr := cMalloc(totalSize)
	if ptr == nil {
		panic("rocstd: allocation failed")
	}

	// Store total size in the header (at offset sizeStorage - 8)
	sizePtr := unsafe.Pointer(uintptr(ptr) + sizeStorage - 8)
	*(*uintptr)(sizePtr) = totalSize

	// Return pointer to user data
	return unsafe.Pointer(uintptr(ptr) + sizeStorage)
}

// defaultDealloc frees memory allocated by defaultAlloc.
func defaultDealloc(alignment uintptr, ptr unsafe.Pointer) {
	sizeStorage := alignment
	if sizeStorage < 8 {
		sizeStorage = 8
	}
	base := unsafe.Pointer(uintptr(ptr) - sizeStorage)
	cFree(base)
}

// defaultRealloc reallocates memory using C realloc.
func defaultRealloc(alignment, newLength uintptr, ptr unsafe.Pointer) unsafe.Pointer {
	sizeStorage := alignment
	if sizeStorage < 8 {
		sizeStorage = 8
	}
	oldBase := unsafe.Pointer(uintptr(ptr) - sizeStorage)
	newTotal := sizeStorage + newLength

	newPtr := cRealloc(oldBase, newTotal)
	if newPtr == nil {
		panic("rocstd: reallocation failed")
	}

	// Store new total size
	sizePtr := unsafe.Pointer(uintptr(newPtr) + sizeStorage - 8)
	*(*uintptr)(sizePtr) = newTotal

	return unsafe.Pointer(uintptr(newPtr) + sizeStorage)
}
