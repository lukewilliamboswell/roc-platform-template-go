#include "roc_std.h"

struct ResultVoidI32 {
    union {long int exit_code;} payload;
    unsigned char disciminant;
};

struct ResultVoidStr {
    union {struct RocStr str;} payload;
    unsigned char disciminant;
};

struct ResultVoidI32 roc__mainForHost_1_exposed(size_t captures);
size_t roc__mainForHost_1_exposed_size();
