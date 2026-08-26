#include "roc_std.h"

extern void go_roc_stderr_line(HostStderrLineResult *result, RocStr message);
extern void go_roc_stdin_line(HostStdinLineResult *result);
extern void go_roc_stdout_line(HostStdoutLineResult *result, RocStr message);

HostStderrLineResult roc_stderr_line(RocStr message) {
    HostStderrLineResult result;
    go_roc_stderr_line(&result, message);
    return result;
}

HostStdinLineResult roc_stdin_line(void) {
    HostStdinLineResult result;
    go_roc_stdin_line(&result);
    return result;
}

HostStdoutLineResult roc_stdout_line(RocStr message) {
    HostStdoutLineResult result;
    go_roc_stdout_line(&result, message);
    return result;
}
