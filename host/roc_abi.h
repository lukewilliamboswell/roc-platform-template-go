#ifndef ROC_ABI_H
#define ROC_ABI_H

#include <stddef.h>
#include <stdint.h>

// Forward declarations
struct RocOps;
struct RocAlloc;
struct RocDealloc;
struct RocRealloc;
struct RocDbg;
struct RocCrashed;
struct RocExpectFailed;

// ============================================================================
// Memory Allocation Callback Structs
// ============================================================================

// RocAlloc - passed to allocation callback
// Host MUST write allocated pointer to 'answer' field
typedef struct RocAlloc {
    size_t alignment;   // Required alignment
    size_t length;      // Number of bytes to allocate
    void* answer;       // OUTPUT: host writes allocated pointer here
} RocAlloc;

// RocDealloc - passed to deallocation callback
typedef struct RocDealloc {
    size_t alignment;   // Original alignment
    void* ptr;          // Pointer to deallocate
} RocDealloc;

// RocRealloc - passed to reallocation callback
// Host reads old pointer from 'answer', writes new pointer back
typedef struct RocRealloc {
    size_t alignment;   // Required alignment
    size_t new_length;  // New size in bytes
    void* answer;       // INPUT/OUTPUT: old ptr in, new ptr out
} RocRealloc;

// ============================================================================
// Debug and Error Callback Structs
// ============================================================================

// RocDbg - debug message (NOT null-terminated)
typedef struct RocDbg {
    char* utf8_bytes;   // Pointer to UTF-8 bytes
    size_t len;         // Length in bytes
} RocDbg;

// RocCrashed - crash message (NOT null-terminated)
typedef struct RocCrashed {
    char* utf8_bytes;   // Pointer to UTF-8 bytes
    size_t len;         // Length in bytes
} RocCrashed;

// RocExpectFailed - expect failure message (NOT null-terminated)
typedef struct RocExpectFailed {
    char* utf8_bytes;   // Pointer to UTF-8 bytes
    size_t len;         // Length in bytes
} RocExpectFailed;

// ============================================================================
// Hosted Functions
// ============================================================================

// HostedFn - function pointer type for hosted functions
// All hosted functions follow RocCall ABI: (ops, ret_ptr, args_ptr) -> void
typedef void (*HostedFn)(struct RocOps*, void*, void*);

// HostedFunctions - array of hosted function pointers
typedef struct HostedFunctions {
    uint32_t count;     // Number of functions
    // Padding for alignment on 64-bit
    uint32_t _padding;
    HostedFn* fns;      // Array of function pointers
} HostedFunctions;

// ============================================================================
// RocOps - Operations struct passed to all Roc functions
// ============================================================================

typedef struct RocOps {
    void* env;                                                              // Host environment pointer
    void (*roc_alloc)(struct RocAlloc*, void*);                            // Allocation callback
    void (*roc_dealloc)(struct RocDealloc*, void*);                        // Deallocation callback
    void (*roc_realloc)(struct RocRealloc*, void*);                        // Reallocation callback
    void (*roc_dbg)(const struct RocDbg*, void*);                          // Debug output callback
    void (*roc_expect_failed)(const struct RocExpectFailed*, void*);       // Expect failure callback
    void (*roc_crashed)(const struct RocCrashed*, void*);                  // Crash handler (must not return)
    HostedFunctions hosted_fns;                                             // Hosted function pointers
} RocOps;

// ============================================================================
// Roc Data Types
// ============================================================================

// RocStr - 24 bytes
// Small strings (< 24 bytes) stored inline with bytes=NULL
// Big strings heap-allocated with refcount at bytes[-8]
typedef struct RocStr {
    char* bytes;                    // Pointer to string data (NULL for small strings)
    size_t length;                  // String length in bytes
    size_t capacity_or_alloc_ptr;   // Capacity (big str) or shifted alloc ptr (slice)
} RocStr;

// RocList - 24 bytes
// Empty list has bytes=NULL, length=0, capacity=0
// Normal lists heap-allocated with refcount at bytes[-8]
typedef struct RocList {
    char* bytes;                    // Pointer to element data
    size_t length;                  // Number of elements
    size_t capacity_or_alloc_ptr;   // Capacity or shifted alloc ptr (seamless slice)
} RocList;

// ============================================================================
// Constants
// ============================================================================

// Small string size threshold (strings smaller than this are stored inline)
#define ROC_SMALL_STRING_SIZE 24

// Mask for detecting small strings (high bit set in capacity)
#define ROC_SMALL_STRING_MASK ((size_t)1 << (sizeof(size_t) * 8 - 1))

// Mask for detecting seamless slices (high bit set in capacity)
#define ROC_SEAMLESS_SLICE_MASK ((size_t)1 << (sizeof(size_t) * 8 - 1))

// ============================================================================
// External Roc Function (provided by compiled Roc code)
// ============================================================================

// The main entry point that Roc provides after compilation
// Follows RocCall ABI: (ops, ret_ptr, args_ptr) -> void
extern void roc__main_for_host(RocOps* ops, void* ret_ptr, void* arg_ptr);

#endif // ROC_ABI_H
