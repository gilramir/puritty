/* How many bytes a pty's master takes before a write would block, with
 * PROGRAM on the slave and nobody reading the master (docs/phase3-input.md):
 * the paste that can be written before puritty must read again. It stops
 * at 1 MB, which a program that keeps reading takes.
 *   fill raw|cooked PROGRAM...   (cooked: the tty's default modes, echo on) */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <pty.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <termios.h>
#include <unistd.h>
#include <sys/wait.h>
int main(int argc, char **argv) {
    int m, s;
    struct termios t;
    openpty(&m, &s, NULL, NULL, NULL);
    tcgetattr(s, &t);
    if (!strcmp(argv[1], "raw")) cfmakeraw(&t);
    tcsetattr(s, TCSANOW, &t);
    pid_t p = fork();
    if (!p) { setsid(); ioctl(s, TIOCSCTTY, 0); dup2(s, 0); dup2(s, 1); dup2(s, 2); close(m); execvp(argv[2], argv + 2); _exit(127); }
    close(s);
    fcntl(m, F_SETFL, O_NONBLOCK);
    usleep(200000);
    char buf[4096];
    memset(buf, 'x', sizeof buf);
    for (int i = 63; i < 4096; i += 64) buf[i] = '\n';
    long total = 0;
    for (int tries = 0; tries < 50; tries++) {
        ssize_t n = write(m, buf, sizeof buf);
        if (n > 0) { total += n; tries = 0; if (total >= 1 << 20) break; continue; }
        if (n < 0 && errno != EAGAIN) { perror("write"); break; }
        usleep(20000);
    }
    printf("%s %s: %ld bytes written before the master stopped taking them\n", argv[1], argv[2], total);
    kill(p, 9);
    return 0;
}
