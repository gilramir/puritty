/* puritty's Windows survey (docs/windows.md): the facts a window needs,
 * measured on the machine. Opens one window, per-monitor DPI aware (v2),
 * and writes to probe-window.log beside the program:
 *
 *   - the monitor the window is on: its size in pixels and its DPI;
 *   - the keyboard layouts installed, the one active, and whether the
 *     window has an input context (IMM32), and what IME it names;
 *   - for each layout, what `ToUnicodeEx` gives for a few keys, unshifted
 *     and shifted: what a key encoder needs for its "unshifted code point";
 *   - the clipboard's formats now;
 *   - how long a full-window BitBlt of a 32-bit DIB section takes, the
 *     median of 60, which is the cost of showing a frame drawn by FreeType
 *     into memory;
 *   - the time from CreateWindow to the first WM_PAINT.
 *
 * It draws a test pattern (a gradient, and text through GDI in Fira Code)
 * so a screenshot shows the window, and closes itself after `SECONDS`.
 * Built with x86_64-w64-mingw32-clang, -municode not needed: wWinMain is
 * not used, the console is. */

#define WIN32_LEAN_AND_MEAN
#define UNICODE
#define _UNICODE
#include <windows.h>
#include <imm.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define SECONDS 25

static FILE *out;
static HWND win;
static HBITMAP dib;
static uint32_t *pixels;
static int dw, dh;
static LARGE_INTEGER freq, t_create;
static int painted;

static double now_ms(void) {
    LARGE_INTEGER t;
    QueryPerformanceCounter(&t);
    return (double) t.QuadPart * 1000.0 / (double) freq.QuadPart;
}

static void make_dib(int w, int h) {
    if (dib) DeleteObject(dib);
    BITMAPINFO bi;
    memset(&bi, 0, sizeof bi);
    bi.bmiHeader.biSize = sizeof bi.bmiHeader;
    bi.bmiHeader.biWidth = w;
    bi.bmiHeader.biHeight = -h; /* top-down */
    bi.bmiHeader.biPlanes = 1;
    bi.bmiHeader.biBitCount = 32;
    bi.bmiHeader.biCompression = BI_RGB;
    dib = CreateDIBSection(NULL, &bi, DIB_RGB_COLORS, (void **) &pixels, NULL, 0);
    dw = w;
    dh = h;
    for (int y = 0; y < h; y++)
        for (int x = 0; x < w; x++)
            pixels[y * w + x] = (uint32_t) ((x * 255 / (w ? w : 1)) << 16 | (y * 255 / (h ? h : 1)) << 8 | 0x40);
}

static int cmp(const void *a, const void *b) {
    double x = *(const double *) a, y = *(const double *) b;
    return x < y ? -1 : x > y;
}

static void measure_blit(HDC hdc) {
    HDC mem = CreateCompatibleDC(hdc);
    HGDIOBJ old = SelectObject(mem, dib);
    double t[60];
    for (int i = 0; i < 60; i++) {
        double a = now_ms();
        BitBlt(hdc, 0, 0, dw, dh, mem, 0, 0, SRCCOPY);
        GdiFlush();
        t[i] = now_ms() - a;
    }
    qsort(t, 60, sizeof t[0], cmp);
    fprintf(out, "blit %dx%d: median %.3f ms, least %.3f, most %.3f\n", dw, dh, t[30], t[0], t[59]);
    SelectObject(mem, old);
    DeleteDC(mem);
}

static void draw_text(HDC hdc, UINT dpi) {
    int px = MulDiv(14, (int) dpi, 72);
    HFONT f = CreateFontW(-px, 0, 0, 0, FW_NORMAL, 0, 0, 0, DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
                          CLEARTYPE_QUALITY, FIXED_PITCH, L"Fira Code");
    HGDIOBJ old = SelectObject(hdc, f);
    SetBkMode(hdc, TRANSPARENT);
    SetTextColor(hdc, RGB(255, 255, 255));
    const wchar_t *lines[] = {L"puritty on Windows: probe-window", L"Fira Code -> => != 0x1F 한국어 ภาษาไทย 😀",
                              L"┌──┬──┐ █▓▒░ box drawing"};
    for (int i = 0; i < 3; i++) TextOutW(hdc, px, px + i * px * 2, lines[i], (int) wcslen(lines[i]));
    wchar_t face[64];
    GetTextFaceW(hdc, 64, face);
    TEXTMETRICW tm;
    GetTextMetricsW(hdc, &tm);
    fprintf(out, "GDI font asked Fira Code at %d px: got \"%ls\", height %ld, ave width %ld\n", px, face, tm.tmHeight,
            tm.tmAveCharWidth);
    SelectObject(hdc, old);
    DeleteObject(f);
}

static void report_keys(void) {
    HKL layouts[32];
    int n = GetKeyboardLayoutList(32, layouts);
    fprintf(out, "keyboard layouts: %d; active %p\n", n, (void *) GetKeyboardLayout(0));
    /* a few virtual keys: Q, 1, ;, [, /, and the key left of 1 */
    UINT vks[] = {'Q', '1', VK_OEM_1, VK_OEM_4, VK_OEM_2, VK_OEM_3};
    const char *names[] = {"Q", "1", "OEM_1", "OEM_4", "OEM_2", "OEM_3"};
    for (int i = 0; i < n; i++) {
        wchar_t name[KL_NAMELENGTH];
        fprintf(out, "  layout %p:", (void *) layouts[i]);
        for (int k = 0; k < 6; k++) {
            BYTE state[256];
            memset(state, 0, sizeof state);
            wchar_t plain[8] = {0}, shifted[8] = {0};
            UINT sc = MapVirtualKeyExW(vks[k], MAPVK_VK_TO_VSC, layouts[i]);
            int a = ToUnicodeEx(vks[k], sc, state, plain, 8, 4, layouts[i]);
            state[VK_SHIFT] = 0x80;
            int b = ToUnicodeEx(vks[k], sc, state, shifted, 8, 4, layouts[i]);
            fprintf(out, " %s=[%d:U+%04X|%d:U+%04X]", names[k], a, a > 0 ? plain[0] : 0, b, b > 0 ? shifted[0] : 0);
        }
        (void) name;
        fprintf(out, "\n");
    }
}

static void report_ime(HWND h) {
    HIMC c = ImmGetContext(h);
    HKL kl = GetKeyboardLayout(0);
    wchar_t desc[128] = {0};
    UINT len = ImmGetDescriptionW(kl, desc, 128);
    fprintf(out, "IMM32: context %s; active layout is an IME (ImmIsIME) %d; description \"%ls\" (%u)\n",
            c ? "yes" : "no", ImmIsIME(kl), desc, len);
    if (c) ImmReleaseContext(h, c);
}

static void report_clipboard(HWND h) {
    if (!OpenClipboard(h)) {
        fprintf(out, "clipboard: could not open\n");
        return;
    }
    fprintf(out, "clipboard formats:");
    UINT f = 0;
    while ((f = EnumClipboardFormats(f)) != 0) fprintf(out, " %u", f);
    fprintf(out, "; CF_UNICODETEXT available %d\n", IsClipboardFormatAvailable(CF_UNICODETEXT));
    CloseClipboard();
}

static void report_monitor(HWND h) {
    HMONITOR m = MonitorFromWindow(h, MONITOR_DEFAULTTONEAREST);
    MONITORINFOEXW mi;
    mi.cbSize = sizeof mi;
    GetMonitorInfoW(m, (MONITORINFO *) &mi);
    UINT dpi = GetDpiForWindow(h);
    fprintf(out, "monitor %ls: %ldx%ld pixels, work area %ldx%ld; window DPI %u (%u%%); monitors %d\n", mi.szDevice,
            mi.rcMonitor.right - mi.rcMonitor.left, mi.rcMonitor.bottom - mi.rcMonitor.top,
            mi.rcWork.right - mi.rcWork.left, mi.rcWork.bottom - mi.rcWork.top, dpi, dpi * 100 / 96,
            GetSystemMetrics(SM_CMONITORS));
}

static LRESULT CALLBACK proc(HWND h, UINT msg, WPARAM wp, LPARAM lp) {
    switch (msg) {
    case WM_PAINT: {
        PAINTSTRUCT ps;
        HDC hdc = BeginPaint(h, &ps);
        if (!painted) {
            painted = 1;
            fprintf(out, "first WM_PAINT %.1f ms after CreateWindow\n", now_ms() - (double) t_create.QuadPart * 1000.0 / (double) freq.QuadPart);
            measure_blit(hdc);
        }
        HDC mem = CreateCompatibleDC(hdc);
        HGDIOBJ old = SelectObject(mem, dib);
        BitBlt(hdc, 0, 0, dw, dh, mem, 0, 0, SRCCOPY);
        SelectObject(mem, old);
        DeleteDC(mem);
        draw_text(hdc, GetDpiForWindow(h));
        EndPaint(h, &ps);
        return 0;
    }
    case WM_SIZE:
        make_dib(LOWORD(lp), HIWORD(lp));
        return 0;
    case WM_TIMER:
        DestroyWindow(h);
        return 0;
    case WM_DESTROY:
        PostQuitMessage(0);
        return 0;
    }
    return DefWindowProcW(h, msg, wp, lp);
}

int main(int argc, char **argv) {
    (void) argc;
    char path[MAX_PATH];
    snprintf(path, sizeof path, "%s", argv[0]);
    char *dot = strrchr(path, '.');
    if (dot) strcpy(dot, ".log");
    out = fopen(path, "w");
    if (!out) return 1;
    QueryPerformanceFrequency(&freq);
    BOOL aware = SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2);
    fprintf(out, "per-monitor-v2 DPI awareness set: %d\n", aware);
    WNDCLASSW wc;
    memset(&wc, 0, sizeof wc);
    wc.lpfnWndProc = proc;
    wc.hInstance = GetModuleHandleW(NULL);
    wc.lpszClassName = L"puritty-probe";
    wc.hCursor = LoadCursorW(NULL, (LPCWSTR) IDC_IBEAM);
    RegisterClassW(&wc);
    QueryPerformanceCounter(&t_create);
    win = CreateWindowExW(0, L"puritty-probe", L"puritty probe-window", WS_OVERLAPPEDWINDOW, 200, 200, 1200, 600, NULL,
                          NULL, wc.hInstance, NULL);
    if (!win) {
        fprintf(out, "CreateWindow failed: %lu\n", GetLastError());
        return 1;
    }
    ShowWindow(win, SW_SHOWNORMAL);
    SetForegroundWindow(win);
    report_monitor(win);
    report_ime(win);
    report_keys();
    report_clipboard(win);
    fflush(out);
    SetTimer(win, 1, SECONDS * 1000, NULL);
    MSG m;
    while (GetMessageW(&m, NULL, 0, 0) > 0) {
        TranslateMessage(&m);
        DispatchMessageW(&m);
    }
    fprintf(out, "closed\n");
    fclose(out);
    return 0;
}
