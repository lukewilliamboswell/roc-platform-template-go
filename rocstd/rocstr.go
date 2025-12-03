package rocstd

import (
	"unsafe"
)

// RocStr represents a Roc string with small string optimization.
//
// Memory layout:
//   - Small string (len < 24): data stored inline, last byte = len | 0x80
//   - Big string: [refcount (8 bytes)][string data], bytes points to data
//   - Seamless slice: length has high bit set, capacityOrAllocPtr stores shifted pointer
//
// This struct must match the C layout exactly (24 bytes on 64-bit systems).
type RocStr struct {
	bytes              *byte
	length             uintptr
	capacityOrAllocPtr uintptr
}

// NewRocStr creates a new RocStr from a Go string.
// For strings < 24 bytes, uses small string optimization (no allocation).
// For larger strings, allocates memory using the provided RocOps.
func NewRocStr(s string, ops *RocOps) RocStr {
	length := len(s)

	if length == 0 {
		return RocStr{
			bytes:              nil,
			length:             0,
			capacityOrAllocPtr: SeamlessSliceBit, // Empty string marker
		}
	}

	if length < RocStructSize {
		// Small string: store inline
		var result RocStr
		ptr := unsafe.Pointer(&result)

		// Copy string data
		for i := 0; i < length; i++ {
			*(*byte)(unsafe.Pointer(uintptr(ptr) + uintptr(i))) = s[i]
		}

		// Set last byte to length | 0x80
		*(*byte)(unsafe.Pointer(uintptr(ptr) + SmallStrMaxLen)) = byte(length) | SmallStrMarker

		return result
	}

	// Big string: allocate with refcount header
	headerSize := uintptr(RefcountSize)
	totalSize := headerSize + uintptr(length)
	allocPtr := ops.Alloc(8, totalSize)

	// Set refcount to 1
	*(*int64)(allocPtr) = RefcountOne

	// Copy string data after refcount
	dataPtr := unsafe.Pointer(uintptr(allocPtr) + headerSize)
	for i := 0; i < length; i++ {
		*(*byte)(unsafe.Pointer(uintptr(dataPtr) + uintptr(i))) = s[i]
	}

	return RocStr{
		bytes:              (*byte)(dataPtr),
		length:             uintptr(length),
		capacityOrAllocPtr: uintptr(allocPtr),
	}
}

// NewRocStrFromBytes creates a new RocStr from a byte slice.
func NewRocStrFromBytes(b []byte, ops *RocOps) RocStr {
	return NewRocStr(string(b), ops)
}

// Empty returns an empty RocStr.
func Empty() RocStr {
	return RocStr{
		bytes:              nil,
		length:             0,
		capacityOrAllocPtr: SeamlessSliceBit,
	}
}

// IsSmall returns true if this is a small string (stored inline).
func (s *RocStr) IsSmall() bool {
	// Small strings have the high bit set in capacityOrAllocPtr
	return int64(s.capacityOrAllocPtr) < 0
}

// IsSeamlessSlice returns true if this is a seamless slice.
func (s *RocStr) IsSeamlessSlice() bool {
	return !s.IsSmall() && int64(s.length) < 0
}

// IsEmpty returns true if the string is empty.
func (s *RocStr) IsEmpty() bool {
	return s.Len() == 0
}

// Len returns the length of the string in bytes.
func (s *RocStr) Len() int {
	if s.IsSmall() {
		// Small string: length is in last byte with high bit masked off
		ptr := unsafe.Pointer(s)
		lastByte := *(*byte)(unsafe.Pointer(uintptr(ptr) + SmallStrMaxLen))
		return int(lastByte & ^SmallStrMarker)
	}

	// Big string or seamless slice: clear the seamless slice bit if set
	length := s.length & ^SeamlessSliceBit
	return int(length)
}

// String returns the RocStr as a Go string.
// This creates a copy of the string data.
func (s *RocStr) String() string {
	return string(s.AsSlice())
}

// AsSlice returns the string data as a byte slice.
// The slice points to the underlying data (no copy).
// Warning: The slice is only valid while the RocStr is alive.
func (s *RocStr) AsSlice() []byte {
	length := s.Len()
	if length == 0 {
		return nil
	}

	var dataPtr unsafe.Pointer
	if s.IsSmall() {
		dataPtr = unsafe.Pointer(s)
	} else {
		dataPtr = unsafe.Pointer(s.bytes)
	}

	return unsafe.Slice((*byte)(dataPtr), length)
}

// getRefcountPtr returns a pointer to the refcount for big strings.
// Returns nil for small strings or seamless slices.
func (s *RocStr) getRefcountPtr() *int64 {
	if s.IsSmall() || s.IsSeamlessSlice() {
		return nil
	}

	// Refcount is at the allocation pointer
	return (*int64)(unsafe.Pointer(s.capacityOrAllocPtr))
}

// getAllocPtr returns the allocation pointer for the string.
// For seamless slices, returns the stored allocation pointer.
// For big strings, returns capacityOrAllocPtr.
// Returns nil for small strings.
func (s *RocStr) getAllocPtr() unsafe.Pointer {
	if s.IsSmall() {
		return nil
	}

	if s.IsSeamlessSlice() {
		// Seamless slice: pointer is stored shifted by 1
		return unsafe.Pointer((s.capacityOrAllocPtr & ^SeamlessSliceBit) << 1)
	}

	return unsafe.Pointer(s.capacityOrAllocPtr)
}

// Incref increments the reference count by n.
// Has no effect on small strings.
func (s *RocStr) Incref(n int) {
	if s.IsSmall() {
		return
	}

	// For seamless slices, get the original allocation's refcount
	var refPtr *int64
	if s.IsSeamlessSlice() {
		allocPtr := s.getAllocPtr()
		if allocPtr == nil {
			return
		}
		refPtr = (*int64)(allocPtr)
	} else {
		refPtr = (*int64)(unsafe.Pointer(s.capacityOrAllocPtr))
	}

	if refPtr != nil {
		*refPtr += int64(n)
	}
}

// Decref decrements the reference count and frees memory if count reaches 0.
// Has no effect on small strings.
func (s *RocStr) Decref(ops *RocOps) {
	if s.IsSmall() {
		return
	}

	allocPtr := s.getAllocPtr()
	if allocPtr == nil {
		return
	}

	refPtr := (*int64)(allocPtr)
	*refPtr--

	if *refPtr == 0 {
		ops.Dealloc(8, allocPtr)
	}
}

// Free releases the memory for a big string.
// Equivalent to Decref, but more explicit about intent.
func (s *RocStr) Free(ops *RocOps) {
	s.Decref(ops)
}

// IsUnique returns true if this is the only reference to the string.
// Small strings always return true.
func (s *RocStr) IsUnique() bool {
	if s.IsSmall() {
		return true
	}

	refPtr := s.getRefcountPtr()
	if refPtr == nil {
		return false // Seamless slices are never unique
	}

	return *refPtr == RefcountOne
}

// Clone creates a copy of the string.
// For small strings, this is just a struct copy.
// For big strings, this increments the refcount.
func (s *RocStr) Clone() RocStr {
	if !s.IsSmall() {
		s.Incref(1)
	}
	return *s
}
