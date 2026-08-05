package roc

/*
#include "./roc_std.h"
*/
import "C"

import (
	"bufio"
	"errors"
	"fmt"
	"io"
	"os"
	"strings"
	"unsafe"
)

var stdin = bufio.NewReader(os.Stdin)

func fromCRocStr(value C.RocStr) RocStr {
	return *(*RocStr)(unsafe.Pointer(&value))
}

func toCRocStr(value RocStr) C.RocStr {
	return *(*C.RocStr)(unsafe.Pointer(&value))
}

//export roc_stderr_line
func roc_stderr_line(message C.RocStr) C.HostStderrLineResult {
	owned := fromCRocStr(message)
	defer owned.DecRef()

	if _, err := fmt.Fprintln(os.Stderr, owned.String()); err != nil {
		return C.roc_host_stderr_line_err(toCRocStr(NewRocStr(err.Error())))
	}
	return C.roc_host_stderr_line_ok()
}

//export roc_stdin_line
func roc_stdin_line() C.HostStdinLineResult {
	line, err := stdin.ReadString('\n')
	if err != nil && !errors.Is(err, io.EOF) {
		return C.roc_host_stdin_line_err(toCRocStr(NewRocStr(err.Error())))
	}

	line = strings.TrimSuffix(line, "\n")
	line = strings.TrimSuffix(line, "\r")
	return C.roc_host_stdin_line_ok(toCRocStr(NewRocStr(line)))
}

//export roc_stdout_line
func roc_stdout_line(message C.RocStr) C.HostStdoutLineResult {
	owned := fromCRocStr(message)
	defer owned.DecRef()

	if _, err := fmt.Fprintln(os.Stdout, owned.String()); err != nil {
		return C.roc_host_stdout_line_err(toCRocStr(NewRocStr(err.Error())))
	}
	return C.roc_host_stdout_line_ok()
}
