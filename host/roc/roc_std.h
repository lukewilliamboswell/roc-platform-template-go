#ifndef ROC_STD
#define ROC_STD

#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>

typedef struct RocStr {
    uint8_t *bytes;
    size_t capacity_or_alloc_ptr;
    size_t length;
} RocStr;

typedef struct RocList {
    void *elements;
    size_t length;
    size_t capacity_or_alloc_ptr;
} RocList;

typedef struct HostStderrLineResult {
    union {
        RocStr err;
        uint8_t ok;
    } payload;
    uint8_t tag;
} HostStderrLineResult;

typedef struct HostStdinLineResult {
    union {
        RocStr err;
        RocStr ok;
    } payload;
    uint8_t tag;
} HostStdinLineResult;

typedef struct HostStdoutLineResult {
    union {
        RocStr err;
        uint8_t ok;
    } payload;
    uint8_t tag;
} HostStdoutLineResult;

_Static_assert(sizeof(RocStr) == 3 * sizeof(size_t), "RocStr ABI mismatch");
_Static_assert(sizeof(RocList) == 3 * sizeof(size_t), "RocList ABI mismatch");
_Static_assert(sizeof(HostStderrLineResult) == 4 * sizeof(size_t), "stderr result size mismatch");
_Static_assert(sizeof(HostStdinLineResult) == 4 * sizeof(size_t), "stdin result size mismatch");
_Static_assert(sizeof(HostStdoutLineResult) == 4 * sizeof(size_t), "stdout result size mismatch");
_Static_assert(offsetof(HostStderrLineResult, tag) == 3 * sizeof(size_t), "stderr result ABI mismatch");
_Static_assert(offsetof(HostStdinLineResult, tag) == 3 * sizeof(size_t), "stdin result ABI mismatch");
_Static_assert(offsetof(HostStdoutLineResult, tag) == 3 * sizeof(size_t), "stdout result ABI mismatch");

enum {
    ROC_RESULT_ERR = 0,
    ROC_RESULT_OK = 1,
};

HostStderrLineResult roc_host_stderr_line_ok(void);
HostStderrLineResult roc_host_stderr_line_err(RocStr err);
HostStdinLineResult roc_host_stdin_line_ok(RocStr line);
HostStdinLineResult roc_host_stdin_line_err(RocStr err);
HostStdoutLineResult roc_host_stdout_line_ok(void);
HostStdoutLineResult roc_host_stdout_line_err(RocStr err);

HostStderrLineResult roc_stderr_line(RocStr message);
HostStdinLineResult roc_stdin_line(void);
HostStdoutLineResult roc_stdout_line(RocStr message);

void *roc_alloc(size_t length, size_t alignment);
void roc_dealloc(void *ptr, size_t alignment);
void *roc_realloc(void *ptr, size_t new_length, size_t alignment);
void roc_dbg(const uint8_t *bytes, size_t len);
void roc_expect_failed(const uint8_t *bytes, size_t len);
void roc_crashed(const uint8_t *bytes, size_t len);

int32_t roc_main(RocList args);

#endif
