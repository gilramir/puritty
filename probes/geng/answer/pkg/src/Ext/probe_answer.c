/* A C thread answering a row's Task.
 *
 * Built as is, the thread, started by geng_thread_start, answers through a post
 * (geng-lang D897): the row
 * opens one with the wait as its environment, the thread sends its answer to
 * it, and the post's ready, on the program's thread, answers the wait. A race
 * that cancels the row closes the post, and the thread's late send is
 * refused.
 *
 * The two builds below are by hand. With -DPROBE_NAIVE, the row keeps the wait it was handed in malloc'd memory, which
 * is what a package writing "a thread, an eventfd and a queue" of its own
 * would do: neither the nursery nor Boehm scans it. Built with
 * -DPROBE_ROOTED, the wait is also held from a static array, which the
 * nursery's step 1 scans, so the object it points at is pinned. */

#define _GNU_SOURCE
#include <errno.h>
#include <poll.h>
#include <pthread.h>
#include <stdint.h>
#include <stdlib.h>
#include <sys/eventfd.h>
#include <time.h>
#include <unistd.h>

#include "geng.h"

static int32_t refused;

#if defined PROBE_NAIVE || defined PROBE_ROOTED
typedef struct job {
    geng_wait *wait;
    int fd;
    int32_t ms;
    int32_t value;
    int slot;
} job;

#ifdef PROBE_ROOTED
#define SLOTS 4096
static geng_wait *rooted[SLOTS];
static int next_slot;
#endif

static void *work(void *arg) {
    job *j = arg;
    struct timespec t = {j->ms / 1000, (long) (j->ms % 1000) * 1000000L};
    while (nanosleep(&t, &t) != 0 && errno == EINTR) {
    }
    uint64_t one = 1;
    (void) write(j->fd, &one, sizeof one);
    return NULL;
}

static void ready(void *env, short revents) {
    (void) revents;
    job *j = env;
    uint64_t n;
    (void) read(j->fd, &n, sizeof n);
    close(j->fd);
#ifdef PROBE_ROOTED
    rooted[j->slot] = NULL;
#endif
    geng_succeed(j->wait, geng_slot_I4(j->value));
    free(j);
}

geng_cancel probe_later(int32_t ms, int32_t value, geng_wait *wait) {
    job *j = malloc(sizeof *j);
    j->wait = wait;
    j->fd = eventfd(0, EFD_CLOEXEC | EFD_NONBLOCK);
    j->ms = ms;
    j->value = value;
#ifdef PROBE_ROOTED
    j->slot = next_slot++ % SLOTS;
    rooted[j->slot] = wait;
#endif
    pthread_t thread;
    pthread_attr_t attr;
    pthread_attr_init(&attr);
    pthread_attr_setdetachstate(&attr, PTHREAD_CREATE_DETACHED);
    pthread_create(&thread, &attr, work, j);
    pthread_attr_destroy(&attr);
    geng_io_wait(j->fd, POLLIN, ready, j);
    return (geng_cancel) {0};
}
#else

typedef struct job {
    geng_post *post;
    int32_t ms;
    int32_t value;
} job;

static void *work(void *arg) {
    job *j = arg;
    struct timespec t = {j->ms / 1000, (long) (j->ms % 1000) * 1000000L};
    while (nanosleep(&t, &t) != 0 && errno == EINTR) {
    }
    int32_t *answer = malloc(sizeof *answer);
    *answer = j->value;
    if (!geng_post_send(j->post, answer)) {
        free(answer);
        __atomic_add_fetch(&refused, 1, __ATOMIC_SEQ_CST);
    }
    geng_post_done(j->post);
    free(j);
    return NULL;
}

static void answered(void *env, void *message) {
    int32_t value = *(int32_t *) message;
    free(message);
    geng_succeed(env, geng_slot_I4(value));
}

static geng_task *cancel(void *env) {
    geng_post_close(env);
    return NULL;
}

geng_cancel probe_later(int32_t ms, int32_t value, geng_wait *wait) {
    geng_post *post = geng_post_open(answered, free, wait);
    job *j = malloc(sizeof *j);
    j->post = post;
    j->ms = ms;
    j->value = value;
    geng_thread_start(work, j);
    return (geng_cancel) {cancel, post};
}
#endif

#ifndef PROBE_NAIVE
#ifndef PROBE_ROOTED
/* One thread sends 1 to n, each emitted into a source. */
typedef struct count_job {
    geng_post *post;
    int32_t n;
} count_job;

static void *count_work(void *arg) {
    count_job *j = arg;
    for (int32_t k = 1; k <= j->n; k++) {
        int32_t *m = malloc(sizeof *m);
        *m = k;
        if (!geng_post_send(j->post, m)) {
            free(m);
            break;
        }
    }
    geng_post_done(j->post);
    free(j);
    return NULL;
}

static void count_emit(void *source, void *message) {
    int32_t k = *(int32_t *) message;
    free(message);
    geng_source_emit(source, geng_slot_I4(k));
}

geng_cancel probe_count(void *source, int32_t n, geng_wait *wait) {
    count_job *j = malloc(sizeof *j);
    j->post = geng_post_open(count_emit, free, source);
    j->n = n;
    geng_thread_start(count_work, j);
    geng_succeed(wait, geng_slot_U(0));
    return (geng_cancel) {0};
}
#endif
#endif

/* How many sends a closed post refused. */
geng_cancel probe_refused(int32_t unused, geng_wait *wait) {
    (void) unused;
    geng_succeed(wait, geng_slot_I4(__atomic_load_n(&refused, __ATOMIC_SEQ_CST)));
    return (geng_cancel) {0};
}
