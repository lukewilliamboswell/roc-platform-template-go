// roc_host.c - C wrapper for Go host functions
// Handles function pointer setup and callbacks that CGO can't handle directly

#include "roc_abi.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <unistd.h>

// ============================================================================
// Go function declarations (implemented in Go, exported via CGO)
// ============================================================================

extern void goRocAlloc(size_t alignment, size_t length, void** answer);
extern void goRocDealloc(size_t alignment, void* ptr);
extern void goRocRealloc(size_t alignment, size_t new_length, void** answer);
extern void goRocDbg(char* utf8_bytes, size_t len);
extern void goRocExpectFailed(char* utf8_bytes, size_t len);
extern void goRocCrashed(char* utf8_bytes, size_t len);
extern void goHostedStderrLine(char* str_bytes, size_t str_len, int is_small);
extern void goHostedStdinLine(void* ret_ptr);
extern void goHostedStdoutLine(char* str_bytes, size_t str_len, int is_small);

// ============================================================================
// Helper functions
// ============================================================================

// Helper to allocate with same layout as c_roc_alloc
static void* host_alloc(size_t alignment, size_t length) {
    size_t size_storage = alignment > 8 ? alignment : 8;
    size_t total_size = size_storage + length;
    void* ptr = malloc(total_size);
    if (!ptr) {
        fprintf(stderr, "Host error: allocation failed\n");
        exit(1);
    }
    // Store size in header
    *((size_t*)((char*)ptr + size_storage - 8)) = total_size;
    return (char*)ptr + size_storage;
}

// ============================================================================
// C callback wrappers (called by Roc via RocOps)
// ============================================================================

// Pure C memory allocation
static void c_roc_alloc(RocAlloc* alloc, void* env) {
    size_t size_storage = alloc->alignment > 8 ? alloc->alignment : 8;
    size_t total_size = size_storage + alloc->length;
    void* ptr = malloc(total_size);
    if (!ptr) {
        fprintf(stderr, "Host error: allocation failed\n");
        exit(1);
    }
    // Store size in header
    *((size_t*)((char*)ptr + size_storage - 8)) = total_size;
    alloc->answer = (char*)ptr + size_storage;
}

static void c_roc_dealloc(RocDealloc* dealloc, void* env) {
    size_t size_storage = dealloc->alignment > 8 ? dealloc->alignment : 8;
    void* base = (char*)dealloc->ptr - size_storage;
    free(base);
}

static void c_roc_realloc(RocRealloc* roc_realloc, void* env) {
    size_t size_storage = roc_realloc->alignment > 8 ? roc_realloc->alignment : 8;
    void* old_base = (char*)roc_realloc->answer - size_storage;
    size_t new_total = size_storage + roc_realloc->new_length;
    void* new_ptr = realloc(old_base, new_total);
    if (!new_ptr) {
        fprintf(stderr, "Host error: reallocation failed\n");
        exit(1);
    }
    *((size_t*)((char*)new_ptr + size_storage - 8)) = new_total;
    roc_realloc->answer = (char*)new_ptr + size_storage;
}

// Pure C debug/error handlers
static void c_roc_dbg(const RocDbg* dbg, void* env) {
    fprintf(stderr, "\033[33mRoc dbg:\033[0m %.*s\n", (int)dbg->len, dbg->utf8_bytes);
}

static void c_roc_expect_failed(const RocExpectFailed* expect, void* env) {
    fprintf(stderr, "\033[33mExpect failed:\033[0m %.*s\n", (int)expect->len, expect->utf8_bytes);
}

static void c_roc_crashed(const RocCrashed* crash, void* env) {
    fprintf(stderr, "\n\033[31mRoc crashed:\033[0m %.*s\n", (int)crash->len, crash->utf8_bytes);
    exit(1);
}

// ============================================================================
// Hosted function wrappers
// ============================================================================

// Check if a RocStr is a small string
static int roc_str_is_small(const RocStr* str) {
    return ((int64_t)str->capacity_or_alloc_ptr) < 0;
}

// Helper to get string bytes and length from RocStr
static void roc_str_get_bytes(const RocStr* str, const char** out_bytes, size_t* out_len) {
    if (roc_str_is_small(str)) {
        // Small string: data in struct itself
        unsigned char* ptr = (unsigned char*)str;
        unsigned char last_byte = ptr[23];
        *out_len = last_byte ^ 0x80;
        *out_bytes = (const char*)str;
    } else {
        *out_len = str->length;
        // Clear seamless slice bit if set
        if ((int64_t)*out_len < 0) {
            *out_len = *out_len & ~((size_t)1 << 63);
        }
        *out_bytes = str->bytes;
    }
}

// Stderr.line! (index 0) - Pure C implementation
static void c_hosted_stderr_line(RocOps* ops, void* ret_ptr, void* args_ptr) {
    RocStr* str = (RocStr*)args_ptr;
    const char* bytes;
    size_t len;
    roc_str_get_bytes(str, &bytes, &len);
    fwrite(bytes, 1, len, stderr);
    fputc('\n', stderr);
}

// Stdin.line! (index 1) - Pure C implementation
static void c_hosted_stdin_line(RocOps* ops, void* ret_ptr, void* args_ptr) {
    RocStr* result = (RocStr*)ret_ptr;
    char buffer[4096];

    if (fgets(buffer, sizeof(buffer), stdin) == NULL) {
        // Return empty string
        result->bytes = NULL;
        result->length = 0;
        result->capacity_or_alloc_ptr = (size_t)1 << 63;  // Small string marker
        return;
    }

    // Trim newline
    size_t len = strlen(buffer);
    if (len > 0 && buffer[len-1] == '\n') {
        buffer[--len] = '\0';
    }
    if (len > 0 && buffer[len-1] == '\r') {
        buffer[--len] = '\0';
    }

    if (len == 0) {
        result->bytes = NULL;
        result->length = 0;
        result->capacity_or_alloc_ptr = (size_t)1 << 63;
        return;
    }

    if (len < 24) {
        // Small string
        memset(result, 0, 24);
        memcpy(result, buffer, len);
        ((unsigned char*)result)[23] = (unsigned char)(len | 0x80);
    } else {
        // Big string - allocate with refcount header using host_alloc
        size_t str_header = 8;  // just refcount for strings
        char* str_alloc = (char*)host_alloc(8, str_header + len);

        // Set string refcount to 1
        *((int64_t*)str_alloc) = 1;

        // String data after header
        char* str_data = str_alloc + str_header;
        memcpy(str_data, buffer, len);

        result->bytes = str_data;
        result->length = len;
        result->capacity_or_alloc_ptr = (size_t)str_alloc;
    }
}

// Stdout.line! (index 2) - Pure C implementation
static void c_hosted_stdout_line(RocOps* ops, void* ret_ptr, void* args_ptr) {
    RocStr* str = (RocStr*)args_ptr;
    const char* bytes;
    size_t len;
    roc_str_get_bytes(str, &bytes, &len);
    fwrite(bytes, 1, len, stdout);
    fputc('\n', stdout);
}

// Array of hosted function pointers (sorted alphabetically by name)
static HostedFn hosted_fns_array[3] = {
    (HostedFn)c_hosted_stderr_line,  // Stderr.line! (index 0)
    (HostedFn)c_hosted_stdin_line,   // Stdin.line! (index 1)
    (HostedFn)c_hosted_stdout_line,  // Stdout.line! (index 2)
};

// ============================================================================
// Platform main entry point
// ============================================================================

// Create initialized RocOps struct
static RocOps create_roc_ops(void) {
    RocOps ops;
    ops.env = NULL;
    ops.roc_alloc = c_roc_alloc;
    ops.roc_dealloc = c_roc_dealloc;
    ops.roc_realloc = c_roc_realloc;
    ops.roc_dbg = c_roc_dbg;
    ops.roc_expect_failed = c_roc_expect_failed;
    ops.roc_crashed = c_roc_crashed;
    ops.hosted_fns.count = 3;
    ops.hosted_fns._padding = 0;
    ops.hosted_fns.fns = hosted_fns_array;
    return ops;
}

// Build a RocList of RocStr from argc/argv
extern RocList goBuildArgsList(int argc, char** argv);

// Build args list in pure C - using same allocation layout as c_roc_alloc
static RocList build_args_list_c(int argc, char** argv) {
    if (argc == 0) {
        RocList list;
        list.bytes = NULL;
        list.length = 0;
        list.capacity_or_alloc_ptr = 0;
        return list;
    }

    // Allocate list: extra_bytes (16 for refcount header) + element data
    size_t elem_size = 24;  // sizeof(RocStr)
    size_t alignment = 8;   // alignment of RocStr
    size_t extra_bytes = 16;  // 8 for refcount + 8 for elem count
    size_t data_size = extra_bytes + (argc * elem_size);

    // Allocate through host_alloc (same layout as c_roc_alloc)
    char* alloc_ptr = (char*)host_alloc(alignment, data_size);

    // Data starts after extra_bytes
    RocStr* data = (RocStr*)(alloc_ptr + extra_bytes);

    // Set refcount = 1 at (alloc_ptr + 0)
    *((int64_t*)alloc_ptr) = 1;

    // Set element count at (alloc_ptr + 8)
    *((size_t*)(alloc_ptr + 8)) = argc;

    // Fill in strings
    for (int i = 0; i < argc; i++) {
        size_t len = strlen(argv[i]);

        if (len == 0) {
            data[i].bytes = NULL;
            data[i].length = 0;
            data[i].capacity_or_alloc_ptr = (size_t)1 << 63;
        } else if (len < 24) {
            // Small string
            memset(&data[i], 0, 24);
            memcpy(&data[i], argv[i], len);
            ((unsigned char*)&data[i])[23] = (unsigned char)(len | 0x80);
        } else {
            // Big string - allocate with refcount header
            size_t str_header = 8;  // just refcount for strings
            char* str_alloc = (char*)host_alloc(8, str_header + len);

            // Set string refcount to 1
            *((int64_t*)str_alloc) = 1;

            // String data after header
            char* str_data = str_alloc + str_header;
            memcpy(str_data, argv[i], len);

            data[i].bytes = str_data;
            data[i].length = len;
            // capacity_or_alloc_ptr stores the alloc pointer for freeing
            data[i].capacity_or_alloc_ptr = (size_t)str_alloc;
        }
    }

    RocList list;
    list.bytes = (char*)data;
    list.length = argc;
    list.capacity_or_alloc_ptr = (size_t)alloc_ptr;  // store alloc ptr for freeing
    return list;
}

// Platform main - called from main()
int platform_main(int argc, char** argv) {
    RocOps ops = create_roc_ops();

    // Build args list in C
    RocList args_list = build_args_list_c(argc, argv);

    // Call Roc main
    int32_t exit_code = -99;
    roc__main_for_host(&ops, &exit_code, &args_list);

    return exit_code;
}

// Main entry point
int main(int argc, char** argv) {
    int exit_code = platform_main(argc, argv);
    // Flush output streams
    fflush(stdout);
    fflush(stderr);
    return exit_code;
}
