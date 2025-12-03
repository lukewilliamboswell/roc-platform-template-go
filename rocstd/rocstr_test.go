package rocstd

import (
	"testing"
)

func TestEmptyString(t *testing.T) {
	ops := DefaultOps()
	s := NewRocStr("", ops)

	if !s.IsEmpty() {
		t.Error("Empty string should be empty")
	}
	if s.Len() != 0 {
		t.Errorf("Expected length 0, got %d", s.Len())
	}
	if s.String() != "" {
		t.Errorf("Expected empty string, got %q", s.String())
	}
}

func TestSmallString(t *testing.T) {
	ops := DefaultOps()

	testCases := []string{
		"a",
		"hi",
		"hello",
		"hello, world!",
		"12345678901234567890123", // 23 chars - max small string
	}

	for _, tc := range testCases {
		t.Run(tc, func(t *testing.T) {
			s := NewRocStr(tc, ops)

			if !s.IsSmall() {
				t.Error("Expected small string")
			}
			if s.IsSeamlessSlice() {
				t.Error("Should not be seamless slice")
			}
			if s.Len() != len(tc) {
				t.Errorf("Expected length %d, got %d", len(tc), s.Len())
			}
			if s.String() != tc {
				t.Errorf("Expected %q, got %q", tc, s.String())
			}
		})
	}
}

func TestBigString(t *testing.T) {
	ops := DefaultOps()

	testCases := []string{
		"123456789012345678901234", // 24 chars - first big string
		"this is a longer string that definitely won't fit in a small string",
		"a" + string(make([]byte, 100)) + "b", // 102 chars
	}

	for _, tc := range testCases {
		t.Run("len"+string(rune(len(tc))), func(t *testing.T) {
			s := NewRocStr(tc, ops)

			if s.IsSmall() {
				t.Error("Expected big string")
			}
			if s.IsSeamlessSlice() {
				t.Error("Should not be seamless slice")
			}
			if s.Len() != len(tc) {
				t.Errorf("Expected length %d, got %d", len(tc), s.Len())
			}
			if s.String() != tc {
				t.Errorf("Expected %q, got %q", tc, s.String())
			}

			// Clean up
			s.Free(ops)
		})
	}
}

func TestAsSlice(t *testing.T) {
	ops := DefaultOps()

	// Test small string
	small := NewRocStr("hello", ops)
	slice := small.AsSlice()
	if string(slice) != "hello" {
		t.Errorf("Expected 'hello', got %q", string(slice))
	}

	// Test big string
	bigStr := "this is a very long string that won't fit"
	big := NewRocStr(bigStr, ops)
	slice = big.AsSlice()
	if string(slice) != bigStr {
		t.Errorf("Expected %q, got %q", bigStr, string(slice))
	}
	big.Free(ops)
}

func TestIsUnique(t *testing.T) {
	ops := DefaultOps()

	// Small strings are always unique
	small := NewRocStr("hi", ops)
	if !small.IsUnique() {
		t.Error("Small strings should be unique")
	}

	// Big strings start unique
	big := NewRocStr("this is a big string for testing", ops)
	if !big.IsUnique() {
		t.Error("New big string should be unique")
	}

	// After clone, still "unique" in terms of refcount (both point to same data)
	clone := big.Clone()
	_ = clone // Use clone

	// Clean up
	big.Free(ops)
	clone.Free(ops)
}

func TestClone(t *testing.T) {
	ops := DefaultOps()

	// Clone small string
	small := NewRocStr("hi", ops)
	smallClone := small.Clone()
	if small.String() != smallClone.String() {
		t.Error("Clone should have same content")
	}

	// Clone big string
	big := NewRocStr("this is a big string for testing", ops)
	bigClone := big.Clone()
	if big.String() != bigClone.String() {
		t.Error("Clone should have same content")
	}

	big.Free(ops)
	bigClone.Free(ops)
}

func TestNewRocStrFromBytes(t *testing.T) {
	ops := DefaultOps()

	bytes := []byte("hello from bytes")
	s := NewRocStrFromBytes(bytes, ops)

	if s.String() != "hello from bytes" {
		t.Errorf("Expected 'hello from bytes', got %q", s.String())
	}

	s.Free(ops)
}

func TestEmptyFunc(t *testing.T) {
	s := Empty()

	if !s.IsEmpty() {
		t.Error("Empty() should return empty string")
	}
	if s.Len() != 0 {
		t.Errorf("Expected length 0, got %d", s.Len())
	}
}
