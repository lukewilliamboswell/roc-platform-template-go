#include "roc/roc_std.h"

extern int go_platform_main(int argc, char **argv);

/*
 * Hosted symbols are weak references in the Roc app object. Taking their
 * addresses here creates strong references from an archive member that is
 * always selected for main, ensuring the cgo export wrappers are extracted.
 */
__attribute__((used)) static void *const roc_host_symbols[] = {
    (void *)&roc_stderr_line,
    (void *)&roc_stdin_line,
    (void *)&roc_stdout_line,
};

#if defined(__linux__)
/*
 * Go's c-archive constructor expects argc and argv, like a glibc constructor.
 * musl calls init-array entries with no arguments, but its startup stage still
 * has main, argc, and argv in the first three C ABI argument registers when it
 * calls __libc_start_init. Override musl's weak implementation and forward the
 * process arguments to every constructor.
 */
typedef void (*init_fn)(int, char **, char **);

extern void _init(void) __attribute__((weak));
extern init_fn __init_array_start[] __attribute__((weak));
extern init_fn __init_array_end[] __attribute__((weak));

void __libc_start_init(void *main_fn, int argc, char **argv) {
    (void)main_fn;
    if (_init != NULL) {
        _init();
    }

    char **envp = argv + argc + 1;
    for (init_fn *constructor = __init_array_start;
         constructor < __init_array_end;
         constructor++) {
        (*constructor)(argc, argv, envp);
    }
}
#endif

int main(int argc, char **argv) {
    return go_platform_main(argc, argv);
}
