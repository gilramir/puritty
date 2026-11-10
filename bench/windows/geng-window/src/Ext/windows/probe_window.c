/* The window thread of puritty's Windows survey (docs/windows.md WS4). The
 * program's thread opens a post (geng_post, D897) and starts this thread,
 * which makes a window, runs its message loop, and turns messages into
 * lines queued under a lock; each time it queues, it sends the post a
 * message, which wakes Geng's loop. `events` answers at once when the queue
 * holds something, and otherwise keeps its wait in the post's environment
 * for the post's `ready` to answer. The thread holds no Geng value: only
 * the post, which neither moves nor dies while it is held. */

#define WIN32_LEAN_AND_MEAN
#define UNICODE
#include <windows.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "geng.h"

typedef struct holder {
    geng_wait *pending;
} holder;

#define HOLDER_HEADER (GENG_HEADER_WORDS(holder) | GENG_HEADER_POINTER(holder, pending))

static CRITICAL_SECTION lock;
static char queue[65536];
static size_t queued;
static geng_post *post;
static holder *held;

static void enqueue(const char *line) {
    EnterCriticalSection(&lock);
    size_t n = strlen(line);
    if (queued + n + 1 < sizeof queue) {
        memcpy(queue + queued, line, n);
        queued += n;
        queue[queued++] = '\n';
    }
    LeaveCriticalSection(&lock);
    geng_post_send(post, malloc(1));
}

static LRESULT CALLBACK proc(HWND h, UINT m, WPARAM wp, LPARAM lp) {
    char line[128];
    switch (m) {
    case WM_SIZE:
        snprintf(line, sizeof line, "size %ux%u", LOWORD(lp), HIWORD(lp));
        enqueue(line);
        return 0;
    case WM_SETFOCUS:
        enqueue("focus in");
        return 0;
    case WM_KILLFOCUS:
        enqueue("focus out");
        return 0;
    case WM_TIMER:
        PostMessageW(h, WM_CLOSE, 0, 0);
        return 0;
    case WM_CLOSE:
        enqueue("close");
        DestroyWindow(h);
        return 0;
    case WM_DESTROY:
        PostQuitMessage(0);
        return 0;
    }
    return DefWindowProcW(h, m, wp, lp);
}

static void *window_thread(void *arg) {
    (void) arg;
    WNDCLASSW wc;
    memset(&wc, 0, sizeof wc);
    wc.lpfnWndProc = proc;
    wc.hInstance = GetModuleHandleW(NULL);
    wc.lpszClassName = L"geng-window-probe";
    wc.hbrBackground = (HBRUSH) GetStockObject(BLACK_BRUSH);
    RegisterClassW(&wc);
    HWND w = CreateWindowExW(0, L"geng-window-probe", L"Geng window probe", WS_OVERLAPPEDWINDOW, 400, 400, 640, 360, NULL,
                             NULL, wc.hInstance, NULL);
    char line[64];
    snprintf(line, sizeof line, "made on thread %lu", GetCurrentThreadId());
    enqueue(line);
    ShowWindow(w, SW_SHOWNORMAL);
    SetTimer(w, 1, 3000, NULL);
    MSG msg;
    while (GetMessageW(&msg, NULL, 0, 0) > 0) {
        TranslateMessage(&msg);
        DispatchMessageW(&msg);
    }
    geng_post_done(post);
    return NULL;
}

/* On the program's thread, for each message the window thread sent. */
static void ready(void *env, void *message) {
    free(message);
    holder *h = env;
    geng_wait *w = h->pending;
    if (w == NULL) return;
    EnterCriticalSection(&lock);
    size_t n = queued;
    LeaveCriticalSection(&lock);
    if (n == 0) return;
    h->pending = NULL;
    geng_succeed(w, geng_slot_I4(1));
}

geng_cancel probe_window_open(geng_wait *wait) {
    InitializeCriticalSection(&lock);
    /* old, so that the static and the window thread's queue never see it move;
     * the post keeps it alive, and the image's statics are roots */
    held = geng_alloc_old(sizeof *held, HOLDER_HEADER);
    held->pending = NULL;
    post = geng_post_open(ready, free, held);
    if (post == NULL || geng_thread_start(window_thread, NULL) != 0) {
        geng_succeed(wait, geng_slot_I4(-1));
        return (geng_cancel) {0};
    }
    geng_succeed(wait, geng_slot_I4(0));
    return (geng_cancel) {0};
}

static geng_task *stop(void *env) {
    holder *h = env;
    h->pending = NULL;
    return NULL;
}

geng_cancel probe_window_events(geng_wait *wait) {
    EnterCriticalSection(&lock);
    size_t n = queued;
    LeaveCriticalSection(&lock);
    if (n > 0) {
        geng_succeed(wait, geng_slot_I4(1));
        return (geng_cancel) {0};
    }
    held->pending = wait;
    geng_write_barrier(held, &held->pending, wait);
    return (geng_cancel) {stop, held};
}

geng_cancel probe_window_take(geng_wait *wait) {
    EnterCriticalSection(&lock);
    size_t n = queued;
    geng_bytes *b = geng_alloc_atomic(sizeof *b + n, GENG_HEADER_BYTES(sizeof *b + n));
    b->length = (int32_t) n;
    b->pad = 0;
    b->data = (uint8_t *) (b + 1);
    b->buffer = NULL;
    b->block = NULL;
    memcpy(b->data, queue, n);
    queued = 0;
    LeaveCriticalSection(&lock);
    geng_succeed(wait, geng_slot_P(b));
    return (geng_cancel) {0};
}
