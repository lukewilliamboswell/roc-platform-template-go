#include "roc_std.h"

#include <stdio.h>
#include <string.h>

extern void go_roc_stderr_line(HostStderrLineResult *result, RocStr message);
extern void go_roc_stdout_line(HostStdoutLineResult *result, RocStr message);

/* Called by startup.c so archive linkers must extract this translation unit. */
void roc_link_hosted_effects(void) {}

static RocStr roc_str_from_bytes(const uint8_t *bytes, size_t length) {
    RocStr result = {0};
    if (length < sizeof(RocStr)) {
        memcpy(&result, bytes, length);
        ((uint8_t *)&result)[sizeof(RocStr) - 1] = (uint8_t)length | 0x80;
        return result;
    }

    uint8_t *allocation = roc_alloc(length + sizeof(size_t), sizeof(size_t));
    *((size_t *)allocation) = 1;
    result.bytes = allocation + sizeof(size_t);
    memcpy(result.bytes, bytes, length);
    result.capacity_or_alloc_ptr = length << 1;
    result.length = length;
    return result;
}

HostStderrLineResult roc_stderr_line(RocStr message) {
    HostStderrLineResult result;
    go_roc_stderr_line(&result, message);
    return result;
}

HostStdinLineResult roc_stdin_line(void) {
    uint8_t stack_buffer[256];
    uint8_t *line = stack_buffer;
    size_t capacity = sizeof(stack_buffer);
    size_t length = 0;

    for (;;) {
        int next = fgetc(stdin);
        if (next == EOF || next == '\n') {
            break;
        }
        if (length == capacity) {
            size_t new_capacity = capacity * 2;
            uint8_t *grown = malloc(new_capacity);
            if (grown == NULL) {
                static const uint8_t message[] = "failed to allocate stdin buffer";
                return HostStdinLineResult_make_err(
                    roc_str_from_bytes(message, sizeof(message) - 1));
            }
            memcpy(grown, line, length);
            if (line != stack_buffer) {
                free(line);
            }
            line = grown;
            capacity = new_capacity;
        }
        line[length++] = (uint8_t)next;
    }

    if (ferror(stdin)) {
        static const uint8_t message[] = "failed to read stdin";
        if (line != stack_buffer) {
            free(line);
        }
        return HostStdinLineResult_make_err(
            roc_str_from_bytes(message, sizeof(message) - 1));
    }
    if (length > 0 && line[length - 1] == '\r') {
        length--;
    }

    RocStr value = roc_str_from_bytes(line, length);
    if (line != stack_buffer) {
        free(line);
    }
    return HostStdinLineResult_make_ok(value);
}

HostStdoutLineResult roc_stdout_line(RocStr message) {
    HostStdoutLineResult result;
    go_roc_stdout_line(&result, message);
    return result;
}
