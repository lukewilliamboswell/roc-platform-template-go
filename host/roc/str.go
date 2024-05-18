package roc

//#include "roc.h"
import "C"

import (
	"unsafe"
)

const is64Bit = uint64(^uintptr(0)) == ^uint64(0)

type RocStr C.struct_RocStr

func (rocStr RocStr) String() string {
	if int(rocStr.capacity) < 0 {
		// Small string
		ptr := (*byte)(unsafe.Pointer(&rocStr))

		byteLen := 12
		if is64Bit {
			byteLen = 24
		}

		shortStr := unsafe.String(ptr, byteLen)
		len := shortStr[byteLen-1] ^ 128
		return shortStr[:len]
	}

	// Remove the bit for seamless string
	len := (uint(rocStr.len) << 1) >> 1
	ptr := (*byte)(unsafe.Pointer(rocStr.bytes))

	return unsafe.String(ptr, len)
}
