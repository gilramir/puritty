/* A stand-in for libpulse-simple.so.0 (harness/soundloss.py): each call
 * is written to $FAKE_PULSE_LOG, a line each. While the file
 * $FAKE_PULSE_DOWN exists the server is gone: pa_simple_new answers NULL,
 * and a write on a stream fails, and that stream stays dead, as a stream
 * whose server went away does. */
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

typedef struct {
    int dead;
} Stream;

static void say(const char *what) {
    const char *path = getenv("FAKE_PULSE_LOG");
    FILE *f = path ? fopen(path, "a") : NULL;
    if (!f) return;
    fprintf(f, "%s\n", what);
    fclose(f);
}

static int down(void) {
    const char *path = getenv("FAKE_PULSE_DOWN");
    return path && access(path, F_OK) == 0;
}

void *pa_simple_new(const char *server, const char *name, int dir, const char *dev, const char *stream_name,
                    const void *spec, const void *map, const void *attr, int *error) {
    (void) server, (void) name, (void) dir, (void) dev, (void) stream_name, (void) spec, (void) map, (void) attr;
    if (down()) {
        say("new refused");
        if (error) *error = 1;
        return NULL;
    }
    say("new");
    return calloc(1, sizeof(Stream));
}

int pa_simple_write(void *s, const void *data, size_t n, int *error) {
    (void) data, (void) n;
    Stream *st = s;
    if (down()) st->dead = 1;
    if (st->dead) {
        say("write failed");
        if (error) *error = 1;
        return -1;
    }
    say("write");
    return 0;
}

int pa_simple_flush(void *s, int *error) {
    (void) s, (void) error;
    return 0;
}

void pa_simple_free(void *s) {
    say("free");
    free(s);
}
