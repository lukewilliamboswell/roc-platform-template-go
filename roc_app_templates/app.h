#include "roc_std.h"

struct ResultVoidI32 {
    union {long int exit_code;} payload;
    unsigned char disciminant;
};

struct ResultVoidStr {
    union {struct RocStr str;} payload;
    unsigned char disciminant;
};

void roc__mainForHost_1_exposed_generic(void* captures);
size_t roc__mainForHost_1_exposed_size();
void roc__mainForHost_0_caller(char* flags, void* closure_data, struct ResultVoidI32 *result);