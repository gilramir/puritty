/* puritty's sounds on Linux (docs/sounds.md SN6): the key sounds and the
 * bells, played through PulseAudio's simple API, which PipeWire's Pulse
 * layer and ETX's audio forwarding also take.
 *
 * libpulse-simple is loaded with dlopen when the first sound is played, so
 * that puritty needs no audio library to start and a machine without one
 * plays nothing. A build with nix's C library (the devbox's, app/build.sh)
 * cannot load the system's, whose folder nix's loader does not search and
 * whose libraries it would not find: that build names nix's own
 * (PURITTY_PULSE_SIMPLE), which talks to the system's sound server over
 * its socket all the same. Sounds are played on a thread of their own, the loop only
 * leaving a request: a key sound replaces whatever plays, and a bell asked
 * for while a bell plays is dropped, since bells come in floods (`cat` of
 * a binary file). The stream is opened once and kept, with a small buffer
 * (20 ms) so that a key's sound is not late. The structures and constants
 * are PulseAudio's, written here so that no header is needed. */

#define _GNU_SOURCE
#include <dlfcn.h>
#include <pthread.h>
#include <stdint.h>
#include <string.h>

#include "geng.h"
#include "../../../../assets/sounds/puritty_sounds.h"

typedef struct {
    int format;
    uint32_t rate;
    uint8_t channels;
} pa_sample_spec;

typedef struct {
    uint32_t maxlength, tlength, prebuf, minreq, fragsize;
} pa_buffer_attr;

enum { PA_STREAM_PLAYBACK = 1, PA_SAMPLE_S16LE = 3 };

static void *(*pa_new)(const char *, const char *, int, const char *, const char *, const pa_sample_spec *,
                       const void *, const pa_buffer_attr *, int *);
static int (*pa_write)(void *, const void *, size_t, int *);
static int (*pa_flush)(void *, int *);

static pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t asked = PTHREAD_COND_INITIALIZER;
static int wanted = -1;  /* the sound asked for and not yet begun */
static int playing = -1; /* the sound being played */
static int started, broken;

/* A WAV file's samples: its data chunk. */
static const unsigned char *samples(int id, size_t *length) {
    const unsigned char *w = puritty_sounds[id].wav;
    size_t size = puritty_sounds[id].size, at = 12;
    while (at + 8 <= size) {
        size_t chunk = (size_t) w[at + 4] | (size_t) w[at + 5] << 8 | (size_t) w[at + 6] << 16 | (size_t) w[at + 7] << 24;
        if (memcmp(w + at, "data", 4) == 0) {
            *length = chunk <= size - at - 8 ? chunk : size - at - 8;
            return w + at + 8;
        }
        at += 8 + chunk + (chunk & 1);
    }
    *length = 0;
    return w;
}

static void *player(void *arg) {
    (void) arg;
    void *lib = dlopen("libpulse-simple.so.0", RTLD_NOW | RTLD_LOCAL);
#ifdef PURITTY_PULSE_SIMPLE
    if (lib == NULL) lib = dlopen(PURITTY_PULSE_SIMPLE, RTLD_NOW | RTLD_LOCAL);
#endif
    if (lib != NULL) {
        pa_new = (void *(*)(const char *, const char *, int, const char *, const char *, const pa_sample_spec *,
                            const void *, const pa_buffer_attr *, int *)) dlsym(lib, "pa_simple_new");
        pa_write = (int (*)(void *, const void *, size_t, int *)) dlsym(lib, "pa_simple_write");
        pa_flush = (int (*)(void *, int *)) dlsym(lib, "pa_simple_flush");
    }
    void *stream = NULL;
    if (pa_new != NULL && pa_write != NULL && pa_flush != NULL) {
        pa_sample_spec spec = {PA_SAMPLE_S16LE, 44100, 1};
        pa_buffer_attr attr = {(uint32_t) -1, 44100 * 2 / 50, (uint32_t) -1, (uint32_t) -1, (uint32_t) -1};
        int error = 0;
        stream = pa_new(NULL, "puritty", PA_STREAM_PLAYBACK, NULL, "bell", &spec, NULL, &attr, &error);
    }
    pthread_mutex_lock(&lock);
    if (stream == NULL) {
        broken = 1;
        wanted = -1;
        pthread_mutex_unlock(&lock);
        return NULL;
    }
    for (;;) {
        while (wanted < 0) pthread_cond_wait(&asked, &lock);
        int id = wanted;
        wanted = -1;
        playing = id;
        pthread_mutex_unlock(&lock);
        size_t length;
        const unsigned char *at = samples(id, &length);
        /* 10 ms at a time, so that a new key's sound cuts in */
        const size_t piece = 44100 * 2 / 100;
        int error = 0;
        while (length > 0) {
            size_t n = length < piece ? length : piece;
            if (pa_write(stream, at, n, &error) < 0) break;
            at += n;
            length -= n;
            pthread_mutex_lock(&lock);
            int cut = wanted >= 0;
            pthread_mutex_unlock(&lock);
            if (cut) {
                pa_flush(stream, &error);
                break;
            }
        }
        pthread_mutex_lock(&lock);
        playing = -1;
    }
}

/* Plays a sound (`puritty_sounds`' index), or drops it: a bell while a bell
 * plays or waits, or anything when there is no audio. */
void puritty_sound_play(int id) {
    if (id < 0 || id >= PURITTY_SOUND_COUNT) return;
    pthread_mutex_lock(&lock);
    int bell = id >= PURITTY_SOUND_FIRST_BELL;
    int busy_with_bell = playing >= PURITTY_SOUND_FIRST_BELL || wanted >= PURITTY_SOUND_FIRST_BELL;
    if (!broken && !(bell && busy_with_bell)) {
        wanted = id;
        if (!started) {
            started = 1;
            if (geng_thread_start(player, NULL) != 0) {
                broken = 1;
                wanted = -1;
            }
        }
        pthread_cond_signal(&asked);
    }
    pthread_mutex_unlock(&lock);
}
