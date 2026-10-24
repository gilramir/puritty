#define _GNU_SOURCE
#include <errno.h>
#include <poll.h>
#include <signal.h>
#include <sys/signalfd.h>
#include <unistd.h>

#include "geng.h"

geng_cancel probe_pid(int32_t unused, geng_wait *wait) {
    (void) unused;
    geng_succeed(wait, geng_slot_I4((int32_t) getpid()));
    return (geng_cancel) {0};
}

geng_cancel probe_block_here(int32_t signo, geng_wait *wait) {
    sigset_t set;
    sigemptyset(&set);
    sigaddset(&set, signo);
    pthread_sigmask(SIG_BLOCK, &set, NULL);
    geng_succeed(wait, geng_slot_U(0));
    return (geng_cancel) {0};
}

/* One wait at a time, held in static storage, which Boehm scans. */
static struct {
    int fd;
    geng_wait *wait;
} pending;

static void readable(void *env, short revents) {
    (void) env;
    (void) revents;
    struct signalfd_siginfo info;
    ssize_t n = read(pending.fd, &info, sizeof info);
    close(pending.fd);
    geng_succeed(pending.wait, geng_slot_I4(n == (ssize_t) sizeof info ? (int32_t) info.ssi_signo : -errno));
}

geng_cancel probe_wait_for(int32_t signo, geng_wait *wait) {
    sigset_t set;
    sigemptyset(&set);
    sigaddset(&set, signo);
    pending.fd = signalfd(-1, &set, SFD_NONBLOCK | SFD_CLOEXEC);
    pending.wait = wait;
    geng_io_wait(pending.fd, POLLIN, readable, NULL);
    return (geng_cancel) {0};
}

/* PROBE_MAIN_BLOCKS: block SIGTERM on the process's first thread before
 * geng_main starts, as the runtime would if geng_main's thread blocked the
 * asynchronous signals; the program's thread inherits the mask. */
#ifdef PROBE_MAIN_BLOCKS
__attribute__((constructor)) static void block_on_first_thread(void) {
    sigset_t set;
    sigemptyset(&set);
    sigaddset(&set, SIGTERM);
    pthread_sigmask(SIG_BLOCK, &set, NULL);
}
#endif
