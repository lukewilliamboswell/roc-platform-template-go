#ifndef ROC_STD
#define ROC_STD

#include "roc_platform_abi.h"

#include <stdlib.h>

void *roc_alloc(size_t length, size_t alignment);
void roc_dealloc(void *ptr, size_t alignment);
void *roc_realloc(void *ptr, size_t new_length, size_t alignment);
void roc_dbg(const uint8_t *bytes, size_t len);
void roc_expect_failed(const uint8_t *bytes, size_t len);
void roc_crashed(const uint8_t *bytes, size_t len);

#endif
