package roc

/*
#include "./roc_std.h"
*/
import "C"

import (
	"fmt"
	"os"
	"unsafe"
)

func fromCRocStr(value C.RocStr) RocStr {
	return *(*RocStr)(unsafe.Pointer(&value))
}

func toCRocStr(value RocStr) C.RocStr {
	return *(*C.RocStr)(unsafe.Pointer(&value))
}

//export go_roc_stderr_line
func go_roc_stderr_line(result *C.HostStderrLineResult, message C.RocStr) {
	owned := fromCRocStr(message)
	defer owned.DecRef()

	if _, err := fmt.Fprintln(os.Stderr, owned.String()); err != nil {
		*result = C.HostStderrLineResult_make_err(toCRocStr(NewRocStr(err.Error())))
		return
	}
	*result = C.HostStderrLineResult_make_ok()
}

//export go_roc_stdout_line
func go_roc_stdout_line(result *C.HostStdoutLineResult, message C.RocStr) {
	owned := fromCRocStr(message)
	defer owned.DecRef()

	if _, err := fmt.Fprintln(os.Stdout, owned.String()); err != nil {
		*result = C.HostStdoutLineResult_make_err(toCRocStr(NewRocStr(err.Error())))
		return
	}
	*result = C.HostStdoutLineResult_make_ok()
}
