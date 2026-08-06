#include "roc_std.h"

#include <stdio.h>
#include <string.h>

typedef struct AllocationHeader {
    void *base;
    size_t length;
} AllocationHeader;

static size_t normalized_alignment(size_t alignment) {
    return alignment < sizeof(void *) ? sizeof(void *) : alignment;
}

static void allocation_failed(void) {
    static const char message[] = "roc_alloc: out of memory\n";
    fwrite(message, 1, sizeof(message) - 1, stderr);
    exit(1);
}

void *roc_alloc(size_t length, size_t alignment) {
    alignment = normalized_alignment(alignment);
    if ((alignment & (alignment - 1)) != 0 ||
        length > SIZE_MAX - sizeof(AllocationHeader) - (alignment - 1)) {
        allocation_failed();
    }

    size_t total = sizeof(AllocationHeader) + (alignment - 1) + length;
    void *base = malloc(total);
    if (base == NULL) {
        allocation_failed();
    }

    uintptr_t unaligned = (uintptr_t)base + sizeof(AllocationHeader);
    uint8_t *user = (uint8_t *)((unaligned + alignment - 1) & ~(alignment - 1));
    AllocationHeader *header = (AllocationHeader *)user - 1;
    header->base = base;
    header->length = length;
    return user;
}

void roc_dealloc(void *ptr, size_t alignment) {
    if (ptr == NULL) {
        return;
    }
    (void)alignment;
    AllocationHeader *header = (AllocationHeader *)ptr - 1;
    free(header->base);
}

void *roc_realloc(void *ptr, size_t new_length, size_t alignment) {
    if (ptr == NULL) {
        return roc_alloc(new_length, alignment);
    }

    AllocationHeader *header = (AllocationHeader *)ptr - 1;
    size_t old_length = header->length;
    void *new_ptr = roc_alloc(new_length, alignment);
    memcpy(new_ptr, ptr, old_length < new_length ? old_length : new_length);
    roc_dealloc(ptr, alignment);
    return new_ptr;
}

static void diagnostic(const char *prefix, const uint8_t *bytes, size_t len) {
    fwrite(prefix, 1, strlen(prefix), stderr);
    fwrite(bytes, 1, len, stderr);
    fputc('\n', stderr);
}

void roc_dbg(const uint8_t *bytes, size_t len) {
    diagnostic("[ROC DBG] ", bytes, len);
}

void roc_expect_failed(const uint8_t *bytes, size_t len) {
    diagnostic("[ROC EXPECT] ", bytes, len);
}

void roc_crashed(const uint8_t *bytes, size_t len) {
    diagnostic("[ROC CRASHED] ", bytes, len);
    exit(1);
}
