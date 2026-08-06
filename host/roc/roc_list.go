package roc

import (
	"sync/atomic"
	"unsafe"
)

// RocList is the natural C ABI representation of Roc's List type.
type RocList[T any] struct {
	Elements           unsafe.Pointer
	Length             uintptr
	CapacityOrAllocPtr uintptr
}

func NewRocList[T any](items []T) RocList[T] {
	if len(items) == 0 {
		return RocList[T]{}
	}

	var zero T
	elementSize := unsafe.Sizeof(zero)
	elementAlignment := unsafe.Alignof(zero)
	allocationAlignment := max(elementAlignment, uintptr(intBytes))
	headerBytes := uintptr(intBytes)
	if elementsAreRefcounted[T]() {
		headerBytes = 2 * uintptr(intBytes)
	}
	headerBytes = max(headerBytes, elementAlignment)

	dataBytes := uintptr(len(items)) * elementSize
	base := allocRaw(headerBytes+dataBytes, allocationAlignment)
	elements := unsafe.Add(base, int(headerBytes))
	*(*uintptr)(unsafe.Add(elements, -intBytes)) = 1
	if elementsAreRefcounted[T]() {
		*(*uintptr)(unsafe.Add(elements, -2*intBytes)) = uintptr(len(items))
	}
	copy(unsafe.Slice((*T)(elements), len(items)), items)

	return RocList[T]{
		Elements:           elements,
		Length:             uintptr(len(items)),
		CapacityOrAllocPtr: uintptr(len(items)) << 1,
	}
}

func (r RocList[T]) List() []T {
	if r.Elements == nil {
		return nil
	}
	return unsafe.Slice((*T)(r.Elements), int(r.Length))
}

func (r RocList[T]) IsSeamlessSlice() bool {
	return r.CapacityOrAllocPtr&seamlessSliceTag != 0
}

func (r RocList[T]) allocationPtr() unsafe.Pointer {
	if r.IsSeamlessSlice() {
		return pointerFromUintptr(r.CapacityOrAllocPtr &^ seamlessSliceTag)
	}
	return r.Elements
}

func (r RocList[T]) DecRef() {
	allocationPtr := r.allocationPtr()
	if allocationPtr == nil {
		return
	}

	refcountPtr := (*uintptr)(unsafe.Add(allocationPtr, -intBytes))
	if atomic.LoadUintptr(refcountPtr) == 0 {
		return
	}
	if atomic.AddUintptr(refcountPtr, ^uintptr(0)) != 0 {
		return
	}

	var zero T
	elementAlignment := unsafe.Alignof(zero)
	allocationAlignment := max(elementAlignment, uintptr(intBytes))
	headerBytes := uintptr(intBytes)
	count := r.Length
	if elementsAreRefcounted[T]() {
		headerBytes = 2 * uintptr(intBytes)
		count = *(*uintptr)(unsafe.Add(allocationPtr, -2*intBytes))
		for _, element := range unsafe.Slice((*T)(allocationPtr), int(count)) {
			any(element).(decRefer).DecRef()
		}
	}
	headerBytes = max(headerBytes, elementAlignment)
	freeRaw(unsafe.Add(allocationPtr, -int(headerBytes)), allocationAlignment)
}

func elementsAreRefcounted[T any]() bool {
	var zero T
	_, ok := any(zero).(decRefer)
	return ok
}

type decRefer interface {
	DecRef()
}
