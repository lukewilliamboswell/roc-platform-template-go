#include "roc_std.h"

union ResultVoidI32Union {
    long int exit_code;
};

struct ResultVoidI32 {
    union ResultVoidI32Union payload;
    unsigned char disciminant;
};


union ResultVoidStrUnion {
    struct RocStr str;
};

struct ResultVoidStr {
    union ResultVoidStrUnion payload;
    unsigned char disciminant;
};

void roc__mainForHost_1_exposed_generic(void* captures);
size_t roc__mainForHost_1_exposed_size();
void roc__mainForHost_0_caller(char* flags, void* closure_data, struct ResultVoidI32 *result);