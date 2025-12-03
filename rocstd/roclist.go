package rocstd

import (
	"unsafe"
)

// RocList represents a Roc list with reference counting.
//
// Memory layout for non-refcounted elements:
//   - [refcount (8 bytes)][elements...]
//   - bytes points to elements
//
// Memory layout for refcounted elements (e.g., List Str):
//   - [element_count (8 bytes)][refcount (8 bytes)][elements...]
//   - bytes points to elements
//
// Seamless slices have high bit set in capacityOrAllocPtr.
//
// This struct must match the C layout exactly (24 bytes on 64-bit systems).
type RocList[T any] struct {
	bytes              *byte
	length             uintptr
	capacityOrAllocPtr uintptr
}

// NewRocList creates a new RocList from a Go slice.
// The elementsRefcounted parameter indicates whether the elements themselves
// contain refcounted data (e.g., RocStr).
func NewRocList[T any](slice []T, elementsRefcounted bool, ops *RocOps) RocList[T] {
	length := len(slice)

	if length == 0 {
		return RocList[T]{
			bytes:              nil,
			length:             0,
			capacityOrAllocPtr: 0,
		}
	}

	var elemSize uintptr
	if length > 0 {
		elemSize = unsafe.Sizeof(slice[0])
	}

	// Calculate header size
	var headerSize uintptr
	if elementsRefcounted {
		headerSize = ElementCountSize + RefcountSize // 16 bytes
	} else {
		headerSize = RefcountSize // 8 bytes
	}

	dataSize := uintptr(length) * elemSize
	totalSize := headerSize + dataSize

	// Allocate with proper alignment
	alignment := unsafe.Alignof(slice[0])
	if alignment < 8 {
		alignment = 8
	}
	allocPtr := ops.Alloc(alignment, totalSize)

	if elementsRefcounted {
		// Set element count at offset 0
		*(*uintptr)(allocPtr) = uintptr(length)
		// Set refcount at offset 8
		*(*int64)(unsafe.Pointer(uintptr(allocPtr) + ElementCountSize)) = RefcountOne
	} else {
		// Set refcount at offset 0
		*(*int64)(allocPtr) = RefcountOne
	}

	// Copy elements after header
	dataPtr := unsafe.Pointer(uintptr(allocPtr) + headerSize)
	srcPtr := unsafe.Pointer(&slice[0])
	cMemcpy(dataPtr, srcPtr, dataSize)

	return RocList[T]{
		bytes:              (*byte)(dataPtr),
		length:             uintptr(length),
		capacityOrAllocPtr: uintptr(allocPtr),
	}
}

// EmptyList returns an empty RocList.
func EmptyList[T any]() RocList[T] {
	return RocList[T]{
		bytes:              nil,
		length:             0,
		capacityOrAllocPtr: 0,
	}
}

// Len returns the number of elements in the list.
func (l *RocList[T]) Len() int {
	// Clear seamless slice bit if set
	return int(l.length & ^SeamlessSliceBit)
}

// IsEmpty returns true if the list is empty.
func (l *RocList[T]) IsEmpty() bool {
	return l.Len() == 0
}

// IsSeamlessSlice returns true if this is a seamless slice.
func (l *RocList[T]) IsSeamlessSlice() bool {
	return int64(l.capacityOrAllocPtr) < 0
}

// Get returns the element at the given index.
// Panics if index is out of bounds.
func (l *RocList[T]) Get(index int) T {
	if index < 0 || index >= l.Len() {
		panic("rocstd: index out of bounds")
	}

	var zero T
	elemSize := unsafe.Sizeof(zero)
	elemPtr := unsafe.Pointer(uintptr(unsafe.Pointer(l.bytes)) + uintptr(index)*elemSize)
	return *(*T)(elemPtr)
}

// Set sets the element at the given index.
// Panics if index is out of bounds.
// Warning: This modifies the underlying data. Ensure the list is unique first.
func (l *RocList[T]) Set(index int, value T) {
	if index < 0 || index >= l.Len() {
		panic("rocstd: index out of bounds")
	}

	var zero T
	elemSize := unsafe.Sizeof(zero)
	elemPtr := unsafe.Pointer(uintptr(unsafe.Pointer(l.bytes)) + uintptr(index)*elemSize)
	*(*T)(elemPtr) = value
}

// ToSlice converts the RocList to a Go slice.
// This creates a copy of the data.
func (l *RocList[T]) ToSlice() []T {
	length := l.Len()
	if length == 0 {
		return nil
	}

	result := make([]T, length)
	var zero T
	elemSize := unsafe.Sizeof(zero)

	for i := 0; i < length; i++ {
		elemPtr := unsafe.Pointer(uintptr(unsafe.Pointer(l.bytes)) + uintptr(i)*elemSize)
		result[i] = *(*T)(elemPtr)
	}

	return result
}

// AsSlice returns a slice pointing to the underlying data.
// Warning: The slice is only valid while the RocList is alive.
func (l *RocList[T]) AsSlice() []T {
	length := l.Len()
	if length == 0 {
		return nil
	}
	return unsafe.Slice((*T)(unsafe.Pointer(l.bytes)), length)
}

// getAllocPtr returns the allocation pointer for the list.
func (l *RocList[T]) getAllocPtr() unsafe.Pointer {
	if l.IsEmpty() {
		return nil
	}

	if l.IsSeamlessSlice() {
		// Seamless slice: pointer is stored shifted by 1
		return unsafe.Pointer((l.capacityOrAllocPtr & ^SeamlessSliceBit) << 1)
	}

	return unsafe.Pointer(l.capacityOrAllocPtr)
}

// getRefcountPtr returns a pointer to the refcount.
func (l *RocList[T]) getRefcountPtr(elementsRefcounted bool) *int64 {
	allocPtr := l.getAllocPtr()
	if allocPtr == nil {
		return nil
	}

	if elementsRefcounted {
		// Refcount is after element count
		return (*int64)(unsafe.Pointer(uintptr(allocPtr) + ElementCountSize))
	}
	return (*int64)(allocPtr)
}

// Incref increments the reference count.
func (l *RocList[T]) Incref(elementsRefcounted bool) {
	refPtr := l.getRefcountPtr(elementsRefcounted)
	if refPtr != nil {
		*refPtr++
	}
}

// Decref decrements the reference count and frees memory if count reaches 0.
// The elementsRefcounted parameter should be true for lists containing
// refcounted elements (like RocStr).
func (l *RocList[T]) Decref(elementsRefcounted bool, ops *RocOps) {
	allocPtr := l.getAllocPtr()
	if allocPtr == nil {
		return
	}

	refPtr := l.getRefcountPtr(elementsRefcounted)
	if refPtr == nil {
		return
	}

	*refPtr--
	if *refPtr == 0 {
		// Determine alignment
		var zero T
		alignment := unsafe.Alignof(zero)
		if alignment < 8 {
			alignment = 8
		}
		ops.Dealloc(alignment, allocPtr)
	}
}

// Free releases the memory for the list.
func (l *RocList[T]) Free(elementsRefcounted bool, ops *RocOps) {
	l.Decref(elementsRefcounted, ops)
}

// IsUnique returns true if this is the only reference to the list.
func (l *RocList[T]) IsUnique(elementsRefcounted bool) bool {
	if l.IsEmpty() {
		return true
	}

	if l.IsSeamlessSlice() {
		return false
	}

	refPtr := l.getRefcountPtr(elementsRefcounted)
	if refPtr == nil {
		return true
	}

	return *refPtr == RefcountOne
}

// Clone creates a copy of the list reference (increments refcount).
func (l *RocList[T]) Clone(elementsRefcounted bool) RocList[T] {
	if !l.IsEmpty() {
		l.Incref(elementsRefcounted)
	}
	return *l
}

// NewRocListOfStr creates a new RocList[RocStr] from Go strings.
// Each string is converted to a RocStr.
func NewRocListOfStr(strings []string, ops *RocOps) RocList[RocStr] {
	if len(strings) == 0 {
		return EmptyList[RocStr]()
	}

	rocStrs := make([]RocStr, len(strings))
	for i, s := range strings {
		rocStrs[i] = NewRocStr(s, ops)
	}

	return NewRocList(rocStrs, true, ops)
}

// RocListToGoStrings converts a RocList of RocStr to a slice of Go strings.
func RocListToGoStrings(l *RocList[RocStr]) []string {
	length := l.Len()
	if length == 0 {
		return nil
	}

	result := make([]string, length)
	for i := 0; i < length; i++ {
		rocStr := l.Get(i)
		result[i] = rocStr.String()
	}

	return result
}
