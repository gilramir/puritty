/* Phase 2's survey probe (visiterm docs/phase2-window.md §4): a program on a
 * pty. The child starts with posix_spawn in a new session (POSIX_SPAWN_SETSID)
 * and opens the slave as its descriptor 0 without O_NOCTTY, which makes the
 * slave its controlling terminal, so nothing runs between fork and exec that
 * the probe wrote. */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <signal.h>
#include <spawn.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <termios.h>
#include <unistd.h>

#include "geng.h"

extern char **environ;

static geng_bytes *bytes_of(const void *s, size_t n) {
    geng_bytes *b = geng_alloc_atomic(sizeof *b + n, GENG_HEADER_BYTES(sizeof *b + n));
    b->length = (int32_t) n;
    b->pad = 0;
    b->data = (uint8_t *) (b + 1);
    b->buffer = NULL;
    b->block = NULL;
    if (n > 0) memcpy(b->data, s, n);
    return b;
}

static char *cstring(geng_bytes *s) {
    char *c = geng_alloc_atomic((size_t) s->length + 1, GENG_HEADER_RAW((size_t) s->length + 1));
    memcpy(c, s->data, (size_t) s->length);
    c[s->length] = 0;
    return c;
}

geng_cancel probe_pty_spawn(int32_t cols, int32_t rows, void *argv_array, geng_wait *wait) {
    int32_t argc = geng_array_length(argv_array);
    geng_bytes **items = geng_array_items(argv_array);
    char **argv = geng_array_items(geng_array_alloc(argc + 1, sizeof(char *), 0));
    for (int32_t i = 0; i < argc; i++) argv[i] = cstring(items[i]);
    argv[argc] = NULL;

    int master = posix_openpt(O_RDWR | O_NOCTTY | O_CLOEXEC);
    char slave[64];
    if (master < 0 || grantpt(master) < 0 || unlockpt(master) < 0 || ptsname_r(master, slave, sizeof slave) != 0) {
        geng_succeed(wait, geng_slot_I4(-errno));
        return (geng_cancel) {0};
    }
    struct winsize size = {.ws_row = (unsigned short) rows, .ws_col = (unsigned short) cols};
    ioctl(master, TIOCSWINSZ, &size);

    posix_spawn_file_actions_t actions;
    posix_spawn_file_actions_init(&actions);
    posix_spawn_file_actions_addopen(&actions, 0, slave, O_RDWR, 0);
    posix_spawn_file_actions_adddup2(&actions, 0, 1);
    posix_spawn_file_actions_adddup2(&actions, 0, 2);
    posix_spawnattr_t attributes;
    posix_spawnattr_init(&attributes);
    sigset_t none, all;
    sigemptyset(&none);
    sigfillset(&all);
    posix_spawnattr_setsigmask(&attributes, &none);
    posix_spawnattr_setsigdefault(&attributes, &all);
    posix_spawnattr_setflags(&attributes, POSIX_SPAWN_SETSID | POSIX_SPAWN_SETSIGMASK | POSIX_SPAWN_SETSIGDEF);
    pid_t pid;
    int code = posix_spawnp(&pid, argv[0], &actions, &attributes, argv, environ);
    posix_spawn_file_actions_destroy(&actions);
    posix_spawnattr_destroy(&attributes);
    if (code != 0) {
        close(master);
        geng_succeed(wait, geng_slot_I4(-code));
        return (geng_cancel) {0};
    }
    fcntl(master, F_SETFL, fcntl(master, F_GETFL) | O_NONBLOCK);
    geng_succeed(wait, geng_slot_I4(master));
    return (geng_cancel) {0};
}

/* One read at a time, held in static storage, which Boehm scans. */
static struct {
    int fd;
    geng_wait *wait;
} pending;

static uint8_t chunk[65536];

/* Answers and returns 1, or returns 0 when there is nothing yet. A pty's
 * master reads EIO once every slave descriptor is closed: the end. */
static int try_read(int fd, geng_wait *wait) {
    ssize_t n;
    do n = read(fd, chunk, sizeof chunk);
    while (n < 0 && errno == EINTR);
    if (n < 0 && errno == EAGAIN) return 0;
    geng_succeed(wait, geng_slot_P(bytes_of(chunk, n > 0 ? (size_t) n : 0)));
    return 1;
}

static void readable(void *env, short revents) {
    (void) env;
    (void) revents;
    if (!try_read(pending.fd, pending.wait)) geng_io_wait(pending.fd, POLLIN, readable, NULL);
}

geng_cancel probe_pty_read(int32_t fd, geng_wait *wait) {
    if (try_read(fd, wait)) return (geng_cancel) {0};
    pending.fd = fd;
    pending.wait = wait;
    geng_io_wait(fd, POLLIN, readable, NULL);
    return (geng_cancel) {0};
}

geng_cancel probe_pty_write(int32_t fd, void *bytes, geng_wait *wait) {
    geng_bytes *b = bytes;
    size_t done = 0;
    while (done < (size_t) b->length) {
        ssize_t n = write(fd, b->data + done, (size_t) b->length - done);
        if (n > 0) done += (size_t) n;
        else if (n < 0 && errno != EINTR && errno != EAGAIN) break;
    }
    geng_succeed(wait, geng_slot_U(0));
    return (geng_cancel) {0};
}
