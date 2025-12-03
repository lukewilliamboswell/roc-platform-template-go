package rocstd

import (
	"testing"
)

func TestEmptyList(t *testing.T) {
	list := EmptyList[int]()

	if !list.IsEmpty() {
		t.Error("Empty list should be empty")
	}
	if list.Len() != 0 {
		t.Errorf("Expected length 0, got %d", list.Len())
	}
}

func TestIntList(t *testing.T) {
	ops := DefaultOps()

	ints := []int{1, 2, 3, 4, 5}
	list := NewRocList(ints, false, ops)

	if list.IsEmpty() {
		t.Error("List should not be empty")
	}
	if list.Len() != 5 {
		t.Errorf("Expected length 5, got %d", list.Len())
	}

	// Test Get
	for i, expected := range ints {
		if got := list.Get(i); got != expected {
			t.Errorf("Get(%d): expected %d, got %d", i, expected, got)
		}
	}

	// Test ToSlice
	slice := list.ToSlice()
	for i, expected := range ints {
		if slice[i] != expected {
			t.Errorf("ToSlice()[%d]: expected %d, got %d", i, expected, slice[i])
		}
	}

	list.Free(false, ops)
}

func TestFloat64List(t *testing.T) {
	ops := DefaultOps()

	floats := []float64{1.1, 2.2, 3.3}
	list := NewRocList(floats, false, ops)

	if list.Len() != 3 {
		t.Errorf("Expected length 3, got %d", list.Len())
	}

	for i, expected := range floats {
		if got := list.Get(i); got != expected {
			t.Errorf("Get(%d): expected %f, got %f", i, expected, got)
		}
	}

	list.Free(false, ops)
}

func TestByteList(t *testing.T) {
	ops := DefaultOps()

	bytes := []byte{0x01, 0x02, 0x03, 0xff}
	list := NewRocList(bytes, false, ops)

	if list.Len() != 4 {
		t.Errorf("Expected length 4, got %d", list.Len())
	}

	for i, expected := range bytes {
		if got := list.Get(i); got != expected {
			t.Errorf("Get(%d): expected %x, got %x", i, expected, got)
		}
	}

	list.Free(false, ops)
}

func TestListSet(t *testing.T) {
	ops := DefaultOps()

	ints := []int{1, 2, 3}
	list := NewRocList(ints, false, ops)

	list.Set(1, 42)
	if got := list.Get(1); got != 42 {
		t.Errorf("After Set(1, 42), Get(1) = %d, expected 42", got)
	}

	list.Free(false, ops)
}

func TestListAsSlice(t *testing.T) {
	ops := DefaultOps()

	ints := []int{10, 20, 30}
	list := NewRocList(ints, false, ops)

	slice := list.AsSlice()
	if len(slice) != 3 {
		t.Errorf("AsSlice length: expected 3, got %d", len(slice))
	}

	for i, expected := range ints {
		if slice[i] != expected {
			t.Errorf("AsSlice[%d]: expected %d, got %d", i, expected, slice[i])
		}
	}

	list.Free(false, ops)
}

func TestListIsUnique(t *testing.T) {
	ops := DefaultOps()

	list := NewRocList([]int{1, 2, 3}, false, ops)

	if !list.IsUnique(false) {
		t.Error("New list should be unique")
	}

	list.Free(false, ops)
}

func TestListClone(t *testing.T) {
	ops := DefaultOps()

	original := NewRocList([]int{1, 2, 3}, false, ops)
	clone := original.Clone(false)

	if original.Len() != clone.Len() {
		t.Error("Clone should have same length")
	}

	for i := 0; i < original.Len(); i++ {
		if original.Get(i) != clone.Get(i) {
			t.Errorf("Clone[%d] differs", i)
		}
	}

	original.Free(false, ops)
	clone.Free(false, ops)
}

func TestListOfStrings(t *testing.T) {
	ops := DefaultOps()

	strings := []string{"hello", "world", "foo", "bar"}
	list := NewRocListOfStr(strings, ops)

	if list.Len() != 4 {
		t.Errorf("Expected length 4, got %d", list.Len())
	}

	// Test RocListToGoStrings
	result := RocListToGoStrings(&list)
	for i, expected := range strings {
		if result[i] != expected {
			t.Errorf("ToGoStrings[%d]: expected %q, got %q", i, expected, result[i])
		}
	}

	// Test individual Get
	for i, expected := range strings {
		rocStr := list.Get(i)
		if rocStr.String() != expected {
			t.Errorf("Get(%d).String(): expected %q, got %q", i, expected, rocStr.String())
		}
	}

	list.Free(true, ops)
}

func TestEmptyListOfStrings(t *testing.T) {
	ops := DefaultOps()

	list := NewRocListOfStr([]string{}, ops)

	if !list.IsEmpty() {
		t.Error("Empty list of strings should be empty")
	}
	if list.Len() != 0 {
		t.Errorf("Expected length 0, got %d", list.Len())
	}
}

func TestListPanicsOnOutOfBounds(t *testing.T) {
	ops := DefaultOps()
	list := NewRocList([]int{1, 2, 3}, false, ops)

	defer func() {
		if r := recover(); r == nil {
			t.Error("Expected panic on out of bounds access")
		}
		list.Free(false, ops)
	}()

	_ = list.Get(10) // Should panic
}

func TestListSetPanicsOnOutOfBounds(t *testing.T) {
	ops := DefaultOps()
	list := NewRocList([]int{1, 2, 3}, false, ops)

	defer func() {
		if r := recover(); r == nil {
			t.Error("Expected panic on out of bounds Set")
		}
		list.Free(false, ops)
	}()

	list.Set(10, 42) // Should panic
}
