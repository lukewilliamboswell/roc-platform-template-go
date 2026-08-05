package roc

import (
	"strings"
	"testing"
	"unsafe"
)

func TestRocStrRoundTripAndRepresentation(t *testing.T) {
	inlineLimit := int(unsafe.Sizeof(RocStr{}))
	tests := []struct {
		name  string
		value string
		small bool
	}{
		{name: "empty", value: "", small: true},
		{name: "unicode", value: "Hello, 世界", small: true},
		{name: "largest inline", value: strings.Repeat("a", inlineLimit-1), small: true},
		{name: "first allocated", value: strings.Repeat("b", inlineLimit), small: false},
		{name: "long", value: strings.Repeat("Roc and Go ", 20), small: false},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			value := NewRocStr(test.value)
			if value.Small() != test.small {
				t.Fatalf("Small() = %v, want %v", value.Small(), test.small)
			}
			if value.Len() != len(test.value) {
				t.Fatalf("Len() = %d, want %d", value.Len(), len(test.value))
			}
			if got := value.String(); got != test.value {
				t.Fatalf("String() = %q, want %q", got, test.value)
			}
			if !test.small {
				if value.CapacityOrAllocPtr != uintptr(len(test.value))<<1 {
					t.Fatalf("capacity word = %#x", value.CapacityOrAllocPtr)
				}
				refcount := *(*uintptr)(unsafe.Add(value.Bytes, -intBytes))
				if refcount != 1 {
					t.Fatalf("refcount = %d, want 1", refcount)
				}
			}
			value.DecRef()
		})
	}
}

func TestRocListLayoutAndElements(t *testing.T) {
	values := []RocStr{
		NewRocStr("small"),
		NewRocStr(strings.Repeat("allocated", 8)),
	}
	list := NewRocList(values)

	if list.Length != uintptr(len(values)) {
		t.Fatalf("length = %d, want %d", list.Length, len(values))
	}
	if list.CapacityOrAllocPtr != uintptr(len(values))<<1 {
		t.Fatalf("capacity word = %#x", list.CapacityOrAllocPtr)
	}
	if got := *(*uintptr)(unsafe.Add(list.Elements, -intBytes)); got != 1 {
		t.Fatalf("refcount = %d, want 1", got)
	}
	if got := *(*uintptr)(unsafe.Add(list.Elements, -2*intBytes)); got != uintptr(len(values)) {
		t.Fatalf("element count = %d, want %d", got, len(values))
	}

	items := list.List()
	for index, expected := range values {
		if got := items[index].String(); got != expected.String() {
			t.Fatalf("item %d = %q, want %q", index, got, expected.String())
		}
	}
	list.DecRef()
}

func TestRocListEmpty(t *testing.T) {
	list := NewRocList([]uint64{})
	if list.Elements != nil || list.Length != 0 || list.CapacityOrAllocPtr != 0 {
		t.Fatalf("empty list has non-zero representation: %#v", list)
	}
	if list.List() != nil {
		t.Fatal("empty list view must be nil")
	}
	list.DecRef()
}

func TestRuntimeAllocatorAlignment(t *testing.T) {
	for _, alignment := range []uintptr{1, 8, 16, 64, 256} {
		ptr := allocRaw(37, alignment)
		effective := max(alignment, uintptr(intBytes))
		if uintptr(ptr)%effective != 0 {
			t.Fatalf("pointer %#x is not aligned to %d", uintptr(ptr), effective)
		}
		bytes := unsafe.Slice((*byte)(ptr), 37)
		for index := range bytes {
			bytes[index] = byte(index)
		}
		freeRaw(ptr, alignment)
	}
}
