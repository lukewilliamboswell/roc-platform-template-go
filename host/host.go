package main

/*
#include <stdlib.h>
*/
import "C"

import (
	"bufio"
	"fmt"
	"os"
	"strings"
	"unsafe"

	"github.com/lukewilliamboswell/roc-platform-template-go/rocstd"
)

// ============================================================================
// Hosted Functions (called from C via function pointers)
// ============================================================================

// goOps returns a RocOps for use in Go hosted functions
func goOps() *rocstd.RocOps {
	return rocstd.DefaultOps()
}

//export goHostedStderrLine
func goHostedStderrLine(strPtr unsafe.Pointer) {
	rocStr := (*rocstd.RocStr)(strPtr)
	fmt.Fprintln(os.Stderr, rocStr.String())
}

//export goHostedStdinLine
func goHostedStdinLine(retPtr unsafe.Pointer) {
	reader := bufio.NewReader(os.Stdin)
	line, err := reader.ReadString('\n')

	result := (*rocstd.RocStr)(retPtr)

	if err != nil {
		*result = rocstd.Empty()
		return
	}

	// Trim newline
	line = strings.TrimSuffix(line, "\n")
	line = strings.TrimSuffix(line, "\r")

	*result = rocstd.NewRocStr(line, goOps())
}

//export goHostedStdoutLine
func goHostedStdoutLine(strPtr unsafe.Pointer) {
	rocStr := (*rocstd.RocStr)(strPtr)
	fmt.Println(rocStr.String())
}

// ============================================================================
// Args List Builder
// ============================================================================

//export goBuildArgsList
func goBuildArgsList(argc C.int, argv **C.char) unsafe.Pointer {
	count := int(argc)
	ops := goOps()

	if count == 0 {
		empty := rocstd.EmptyList[rocstd.RocStr]()
		return unsafe.Pointer(&empty)
	}

	// Convert argv to Go strings
	argvSlice := unsafe.Slice(argv, count)
	goStrings := make([]string, count)
	for i := 0; i < count; i++ {
		goStrings[i] = C.GoString(argvSlice[i])
	}

	// Create RocList of RocStr
	list := rocstd.NewRocListOfStr(goStrings, ops)

	// We need to return by value, so copy to C-allocated memory
	listPtr := C.malloc(C.size_t(unsafe.Sizeof(list)))
	*(*rocstd.RocList[rocstd.RocStr])(listPtr) = list

	return listPtr
}

// Required for c-archive mode
func main() {}
