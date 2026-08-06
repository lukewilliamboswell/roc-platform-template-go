package roc

import "unsafe"

const seamlessSliceTag = uintptr(1)

// RocStr is the natural C ABI representation of Roc's Str type.
type RocStr struct {
	Bytes              unsafe.Pointer
	CapacityOrAllocPtr uintptr
	Length             uintptr
}

func NewRocStr(str string) RocStr {
	var result RocStr
	structBytes := int(unsafe.Sizeof(result))

	if len(str) < structBytes {
		bytes := unsafe.Slice((*byte)(unsafe.Pointer(&result)), structBytes)
		copy(bytes, str)
		bytes[structBytes-1] = byte(len(str)) | 0x80
		return result
	}

	ptr := allocForRoc(uintptr(len(str)))
	copy(unsafe.Slice((*byte)(ptr), len(str)), str)
	return RocStr{
		Bytes:              ptr,
		CapacityOrAllocPtr: uintptr(len(str)) << 1,
		Length:             uintptr(len(str)),
	}
}

func (r RocStr) Small() bool {
	return int(r.Length) < 0
}

func (r RocStr) IsSeamlessSlice() bool {
	return !r.Small() && r.CapacityOrAllocPtr&seamlessSliceTag != 0
}

func (r RocStr) Len() int {
	if r.Small() {
		bytes := unsafe.Slice((*byte)(unsafe.Pointer(&r)), int(unsafe.Sizeof(r)))
		return int(bytes[len(bytes)-1] ^ 0x80)
	}
	return int(r.Length)
}

func (r RocStr) String() string {
	length := r.Len()
	if r.Small() {
		return string(unsafe.Slice((*byte)(unsafe.Pointer(&r)), length))
	}
	if r.Bytes == nil {
		return ""
	}
	return string(unsafe.Slice((*byte)(r.Bytes), length))
}

func (r RocStr) allocationPtr() unsafe.Pointer {
	if r.IsSeamlessSlice() {
		return pointerFromUintptr(r.CapacityOrAllocPtr &^ seamlessSliceTag)
	}
	return r.Bytes
}

func (r RocStr) DecRef() {
	if r.Small() {
		return
	}
	if ptr := r.allocationPtr(); ptr != nil {
		decRefCount(ptr, uintptr(intBytes), uintptr(intBytes))
	}
}
