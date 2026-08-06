#include <pthread.h>

static void *thread_main(void *unused) {
    return unused;
}

int main(void) {
    pthread_t thread;
    if (pthread_create(&thread, 0, thread_main, 0) != 0) {
        return 1;
    }
    return pthread_join(thread, 0);
}
