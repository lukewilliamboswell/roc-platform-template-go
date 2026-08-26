//go:build !windows

package main

/*
#include <stdlib.h>
*/
import "C"

import "unsafe"

// processArgs returns the process arguments as UTF-8 strings.
//
// POSIX argv is already a byte string, so it is used as-is.
func processArgs(argc int, argv unsafeArgv) []string {
	if argc <= 0 {
		return nil
	}
	cArgs := unsafe.Slice((**C.char)(argv), argc)
	args := make([]string, argc)
	for i, arg := range cArgs {
		args[i] = C.GoString(arg)
	}
	return args
}
