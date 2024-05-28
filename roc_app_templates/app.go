package roc

//#include "main.h"
import "C"

func Main() string {
	var str RocStr
	C.roc__mainForHost_1_exposed_generic(str.CPtr())
	return str.String()
}
