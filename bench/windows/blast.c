/* blast: output a terminal must take, timed from inside it
 * (docs/windows.md WS26). Run in the terminal being measured:
 *
 *   blast dump FILE RESULT     write FILE to the console as it comes
 *   blast frames N RESULT      N whole screens of coloured text, each from
 *                              the top left, sized to the console
 *
 * It waits START seconds (third argument's fourth, default 4) so that the
 * window can be maximised first, enables VT processing, then writes in
 * 64 KB writes and appends to RESULT a line: the mode, the bytes, the
 * console's columns and rows, and the milliseconds the writes took.
 * Built with the Windows toolchain: x86_64-w64-mingw32-clang -O2. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static HANDLE out;

static void put(const char *p, size_t n) {
    while (n > 0) {
        DWORD k = n > 65536 ? 65536 : (DWORD) n, w = 0;
        if (!WriteFile(out, p, k, &w, NULL) || w == 0) exit(2);
        p += w;
        n -= w;
    }
}

int main(int argc, char **argv) {
    if (argc < 4) {
        fprintf(stderr, "usage: blast dump FILE RESULT [START] | blast frames N RESULT [START]\n");
        return 1;
    }
    int start = argc > 4 ? atoi(argv[4]) : 4;
    Sleep((DWORD) start * 1000);
    out = GetStdHandle(STD_OUTPUT_HANDLE);
    DWORD mode = 0;
    if (GetConsoleMode(out, &mode)) SetConsoleMode(out, mode | ENABLE_VIRTUAL_TERMINAL_PROCESSING);
    CONSOLE_SCREEN_BUFFER_INFO info;
    int cols = 80, rows = 24;
    if (GetConsoleScreenBufferInfo(out, &info)) {
        cols = info.srWindow.Right - info.srWindow.Left + 1;
        rows = info.srWindow.Bottom - info.srWindow.Top + 1;
    }
    char *buf = NULL;
    size_t len = 0;
    if (strcmp(argv[1], "dump") == 0) {
        FILE *f = fopen(argv[2], "rb");
        if (!f) return 1;
        fseek(f, 0, SEEK_END);
        len = (size_t) ftell(f);
        fseek(f, 0, SEEK_SET);
        buf = malloc(len);
        if (fread(buf, 1, len, f) != len) return 1;
        fclose(f);
    } else {
        /* each frame: home, then every row: a colour, then letters that
         * change frame to frame, so that every cell is drawn again */
        int n = atoi(argv[2]);
        size_t cap = (size_t) n * (size_t) rows * ((size_t) cols + 24) + 64;
        buf = malloc(cap);
        for (int fr = 0; fr < n; fr++) {
            len += (size_t) sprintf(buf + len, "\x1b[H");
            for (int r = 0; r < rows; r++) {
                len += (size_t) sprintf(buf + len, "\x1b[38;5;%dm\x1b[48;5;%dm", 16 + (fr + r) % 216, 232 + (fr + r) % 24);
                for (int c = 0; c < cols; c++) buf[len++] = (char) ('!' + (fr + r + c) % 94);
                if (r < rows - 1) len += (size_t) sprintf(buf + len, "\r\n");
            }
        }
        len += (size_t) sprintf(buf + len, "\x1b[0m");
    }
    LARGE_INTEGER f, t0, t1;
    QueryPerformanceFrequency(&f);
    QueryPerformanceCounter(&t0);
    put(buf, len);
    QueryPerformanceCounter(&t1);
    double ms = (double) (t1.QuadPart - t0.QuadPart) * 1000.0 / (double) f.QuadPart;
    FILE *r = fopen(argv[3], "a");
    if (r) {
        fprintf(r, "%s\t%zu\t%dx%d\t%.0f\n", argv[1], len, cols, rows, ms);
        fclose(r);
    }
    return 0;
}
