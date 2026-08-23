//go:build windows

package main

import "os"

// processArgs returns the process arguments as UTF-8 strings.
//
// The C runtime hands main an ANSI argv converted through the console code
// page, so any character outside that code page is already lost by the time
// it reaches Go. Go's os.Args is built from GetCommandLineW instead, so it
// preserves the full Unicode command line.
func processArgs(argc int, argv unsafeArgv) []string {
	_, _ = argc, argv
	return os.Args
}
