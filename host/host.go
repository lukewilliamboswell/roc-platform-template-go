package main

/*
#include "roc_abi.h"
#include <stdlib.h>
#include <string.h>
*/
import "C"

import (
	"bufio"
	"fmt"
	"os"
	"strings"
	"unsafe"
)

// ============================================================================
// Memory Allocation Callbacks (called from C)
// ============================================================================

const sizeHeaderBytes = 8

//export goRocAlloc
func goRocAlloc(alignment, length C.size_t, answer *unsafe.Pointer) {
	align := uintptr(alignment)
	len := uintptr(length)

	// Calculate size including metadata
	sizeStorage := max(align, sizeHeaderBytes)
	totalSize := sizeStorage + len

	// Allocate
	ptr := C.malloc(C.size_t(totalSize))
	if ptr == nil {
		fmt.Fprintln(os.Stderr, "\x1b[31mHost error:\x1b[0m allocation failed")
		os.Exit(1)
	}

	// Store total size in metadata
	sizePtr := (*uintptr)(unsafe.Pointer(uintptr(ptr) + sizeStorage - sizeHeaderBytes))
	*sizePtr = totalSize

	// Return user pointer
	*answer = unsafe.Pointer(uintptr(ptr) + sizeStorage)
}

//export goRocDealloc
func goRocDealloc(alignment C.size_t, ptr unsafe.Pointer) {
	align := uintptr(alignment)
	userPtr := uintptr(ptr)

	sizeStorage := max(align, sizeHeaderBytes)
	basePtr := unsafe.Pointer(userPtr - sizeStorage)

	C.free(basePtr)
}

//export goRocRealloc
func goRocRealloc(alignment, newLength C.size_t, answer *unsafe.Pointer) {
	align := uintptr(alignment)
	newLen := uintptr(newLength)
	oldUserPtr := uintptr(*answer)

	sizeStorage := max(align, sizeHeaderBytes)
	oldBasePtr := unsafe.Pointer(oldUserPtr - sizeStorage)

	// Calculate new size
	newTotalSize := sizeStorage + newLen

	// Reallocate
	newBasePtr := C.realloc(oldBasePtr, C.size_t(newTotalSize))
	if newBasePtr == nil {
		fmt.Fprintln(os.Stderr, "\x1b[31mHost error:\x1b[0m reallocation failed")
		os.Exit(1)
	}

	// Store new size
	newSizePtr := (*uintptr)(unsafe.Pointer(uintptr(newBasePtr) + sizeStorage - sizeHeaderBytes))
	*newSizePtr = newTotalSize

	// Return new user pointer
	*answer = unsafe.Pointer(uintptr(newBasePtr) + sizeStorage)
}

// ============================================================================
// Debug and Error Callbacks (called from C)
// ============================================================================

//export goRocDbg
func goRocDbg(utf8Bytes *C.char, length C.size_t) {
	message := C.GoStringN(utf8Bytes, C.int(length))
	fmt.Fprintf(os.Stderr, "\x1b[33mRoc dbg:\x1b[0m %s\n", message)
}

//export goRocExpectFailed
func goRocExpectFailed(utf8Bytes *C.char, length C.size_t) {
	message := C.GoStringN(utf8Bytes, C.int(length))
	trimmed := strings.TrimSpace(message)
	fmt.Fprintf(os.Stderr, "\x1b[33mExpect failed:\x1b[0m %s\n", trimmed)
}

//export goRocCrashed
func goRocCrashed(utf8Bytes *C.char, length C.size_t) {
	message := C.GoStringN(utf8Bytes, C.int(length))
	fmt.Fprintf(os.Stderr, "\n\x1b[31mRoc crashed:\x1b[0m %s\n", message)
	os.Exit(1)
}

// ============================================================================
// Hosted Functions (called from C)
// ============================================================================

//export goHostedStderrLine
func goHostedStderrLine(strBytes *C.char, strLen C.size_t, isSmall C.int) {
	message := C.GoStringN(strBytes, C.int(strLen))
	fmt.Fprintln(os.Stderr, message)
}

//export goHostedStdinLine
func goHostedStdinLine(retPtr unsafe.Pointer) {
	reader := bufio.NewReader(os.Stdin)
	line, err := reader.ReadString('\n')

	result := (*C.RocStr)(retPtr)

	if err != nil {
		// Return empty string
		result.bytes = nil
		result.length = 0
		result.capacity_or_alloc_ptr = C.size_t(1 << 63)
		return
	}

	// Trim newline
	line = strings.TrimSuffix(line, "\n")
	line = strings.TrimSuffix(line, "\r")

	// Create RocStr
	length := len(line)
	if length == 0 {
		result.bytes = nil
		result.length = 0
		result.capacity_or_alloc_ptr = C.size_t(1 << 63)
		return
	}

	if length < 24 {
		// Small string
		ptr := unsafe.Pointer(result)
		for i := 0; i < length; i++ {
			*(*byte)(unsafe.Pointer(uintptr(ptr) + uintptr(i))) = line[i]
		}
		*(*byte)(unsafe.Pointer(uintptr(ptr) + 23)) = byte(length) | 0x80
	} else {
		// Big string - allocate directly with malloc (simple for now)
		strPtr := C.malloc(C.size_t(length))
		if strPtr == nil {
			fmt.Fprintln(os.Stderr, "\x1b[31mHost error:\x1b[0m allocation failed")
			os.Exit(1)
		}
		C.memcpy(strPtr, unsafe.Pointer(unsafe.StringData(line)), C.size_t(length))
		result.bytes = (*C.char)(strPtr)
		result.length = C.size_t(length)
		result.capacity_or_alloc_ptr = C.size_t(length)
	}
}

//export goHostedStdoutLine
func goHostedStdoutLine(strBytes *C.char, strLen C.size_t, isSmall C.int) {
	message := C.GoStringN(strBytes, C.int(strLen))
	fmt.Println(message)
}

// ============================================================================
// Args List Builder (called from C)
// ============================================================================

//export goBuildArgsList
func goBuildArgsList(argc C.int, argv **C.char) C.RocList {
	count := int(argc)

	if count == 0 {
		var list C.RocList
		list.bytes = nil
		list.length = 0
		list.capacity_or_alloc_ptr = 0
		return list
	}

	// Allocate list storage
	// Extra bytes for refcount: 16 bytes (8 for refcount, 8 for elem count since elems are refcounted)
	elemSize := uintptr(24) // sizeof(RocStr)
	extraBytes := uintptr(16)
	totalSize := extraBytes + (uintptr(count) * elemSize)

	rawPtr := C.malloc(C.size_t(totalSize))
	if rawPtr == nil {
		fmt.Fprintln(os.Stderr, "\x1b[31mHost error:\x1b[0m allocation failed")
		os.Exit(1)
	}

	// Data starts after extra bytes
	dataPtr := unsafe.Pointer(uintptr(rawPtr) + extraBytes)

	// Set refcount = 1 at (data - 8)
	refcountPtr := (*int64)(unsafe.Pointer(uintptr(dataPtr) - 8))
	*refcountPtr = 1

	// Set element count at (data - 16)
	elemCountPtr := (*uintptr)(unsafe.Pointer(uintptr(dataPtr) - 16))
	*elemCountPtr = uintptr(count)

	// Fill in the strings
	elements := (*[1 << 20]C.RocStr)(dataPtr)[:count:count]
	argvSlice := (*[1 << 20]*C.char)(unsafe.Pointer(argv))[:count:count]

	for i := 0; i < count; i++ {
		goStr := C.GoString(argvSlice[i])
		length := len(goStr)

		if length == 0 {
			elements[i].bytes = nil
			elements[i].length = 0
			elements[i].capacity_or_alloc_ptr = C.size_t(1 << 63)
		} else if length < 24 {
			// Small string
			ptr := unsafe.Pointer(&elements[i])
			for j := 0; j < length; j++ {
				*(*byte)(unsafe.Pointer(uintptr(ptr) + uintptr(j))) = goStr[j]
			}
			*(*byte)(unsafe.Pointer(uintptr(ptr) + 23)) = byte(length) | 0x80
		} else {
			// Big string
			strPtr := C.malloc(C.size_t(length))
			if strPtr == nil {
				fmt.Fprintln(os.Stderr, "\x1b[31mHost error:\x1b[0m allocation failed")
				os.Exit(1)
			}
			C.memcpy(strPtr, unsafe.Pointer(unsafe.StringData(goStr)), C.size_t(length))
			elements[i].bytes = (*C.char)(strPtr)
			elements[i].length = C.size_t(length)
			elements[i].capacity_or_alloc_ptr = C.size_t(length)
		}
	}

	var list C.RocList
	list.bytes = (*C.char)(dataPtr)
	list.length = C.size_t(count)
	list.capacity_or_alloc_ptr = C.size_t(count)

	return list
}

// max returns the larger of two uintptr values
func max(a, b uintptr) uintptr {
	if a > b {
		return a
	}
	return b
}

// Required for c-archive mode
func main() {}
