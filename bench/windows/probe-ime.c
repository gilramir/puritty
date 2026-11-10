/* puritty's Windows survey (docs/windows.md WS11): whether keys sent with
 * SendInput reach the Korean IME and compose, so that IME input can be
 * tested without a person typing. Opens a window, makes it the foreground,
 * switches it to the Korean layout and to Hangul mode, and sends g k s
 * (which compose 한 on the 2-set keyboard), then Space; it logs every
 * WM_IME_* message's composition and result strings to probe-ime.log.
 *
 * Every key is sent only while this window is the foreground window: if
 * anything else has the focus, the probe stops without sending, so that no
 * key reaches another program. Hangul mode is switched back off, and the
 * window closes itself. */

#define WIN32_LEAN_AND_MEAN
#define UNICODE
#include <windows.h>
#include <imm.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static FILE *out;
static HWND win;
static int stopped;

static void log_comp(HWND h, LPARAM lp) {
    HIMC c = ImmGetContext(h);
    if (!c) return;
    wchar_t s[64];
    if (lp & GCS_COMPSTR) {
        LONG n = ImmGetCompositionStringW(c, GCS_COMPSTR, s, sizeof s - 2);
        s[n > 0 ? n / 2 : 0] = 0;
        fprintf(out, "  preedit \"%ls\" (", s);
        for (LONG i = 0; i < n / 2; i++) fprintf(out, "%sU+%04X", i ? " " : "", s[i]);
        fprintf(out, ")\n");
    }
    if (lp & GCS_RESULTSTR) {
        LONG n = ImmGetCompositionStringW(c, GCS_RESULTSTR, s, sizeof s - 2);
        s[n > 0 ? n / 2 : 0] = 0;
        fprintf(out, "  commit \"%ls\" (", s);
        for (LONG i = 0; i < n / 2; i++) fprintf(out, "%sU+%04X", i ? " " : "", s[i]);
        fprintf(out, ")\n");
    }
    ImmReleaseContext(h, c);
}

static LRESULT CALLBACK proc(HWND h, UINT m, WPARAM wp, LPARAM lp) {
    switch (m) {
    case WM_IME_STARTCOMPOSITION:
        fprintf(out, "WM_IME_STARTCOMPOSITION\n");
        break;
    case WM_IME_COMPOSITION:
        fprintf(out, "WM_IME_COMPOSITION %#llx\n", (unsigned long long) lp);
        log_comp(h, lp);
        break;
    case WM_IME_ENDCOMPOSITION:
        fprintf(out, "WM_IME_ENDCOMPOSITION\n");
        break;
    case WM_CHAR:
        fprintf(out, "WM_CHAR U+%04X\n", (unsigned) wp);
        return 0;
    case WM_KEYDOWN:
        fprintf(out, "WM_KEYDOWN vk %#x\n", (unsigned) wp);
        break;
    case WM_DESTROY:
        PostQuitMessage(0);
        return 0;
    }
    return DefWindowProcW(h, m, wp, lp);
}

static void pump(int ms) {
    DWORD end = GetTickCount() + (DWORD) ms;
    MSG msg;
    while ((int) (end - GetTickCount()) > 0) {
        while (PeekMessageW(&msg, NULL, 0, 0, PM_REMOVE)) {
            TranslateMessage(&msg);
            DispatchMessageW(&msg);
        }
        Sleep(5);
    }
}

/* A key down and up, only while this window has the foreground. */
static void key(WORD vk) {
    if (stopped) return;
    if (GetForegroundWindow() != win) {
        fprintf(out, "STOPPED: the foreground is another window (%p), no key sent\n", (void *) GetForegroundWindow());
        stopped = 1;
        return;
    }
    INPUT in[2];
    memset(in, 0, sizeof in);
    in[0].type = INPUT_KEYBOARD;
    in[0].ki.wVk = vk;
    in[1] = in[0];
    in[1].ki.dwFlags = KEYEVENTF_KEYUP;
    UINT sent = SendInput(2, in, sizeof(INPUT));
    fprintf(out, "sent vk %#x (%u)\n", vk, sent);
    pump(150);
}

int main(int argc, char **argv) {
    (void) argc;
    char path[MAX_PATH];
    snprintf(path, sizeof path, "%s", argv[0]);
    char *dot = strrchr(path, '.');
    if (dot) strcpy(dot, ".log");
    out = fopen(path, "w");
    if (!out) return 1;
    WNDCLASSW wc;
    memset(&wc, 0, sizeof wc);
    wc.lpfnWndProc = proc;
    wc.hInstance = GetModuleHandleW(NULL);
    wc.lpszClassName = L"puritty-probe-ime";
    RegisterClassW(&wc);
    win = CreateWindowExW(0, L"puritty-probe-ime", L"puritty probe-ime", WS_OVERLAPPEDWINDOW, 300, 300, 600, 200, NULL,
                          NULL, wc.hInstance, NULL);
    ShowWindow(win, SW_SHOWNORMAL);
    /* Windows keeps a program that was not started by input from taking
     * the foreground; joining the foreground thread's input for a moment
     * lets it, and sends nothing to that thread's windows. */
    HWND fg = GetForegroundWindow();
    DWORD fgThread = GetWindowThreadProcessId(fg, NULL), me = GetCurrentThreadId();
    BOOL joined = fgThread != me && AttachThreadInput(me, fgThread, TRUE);
    BringWindowToTop(win);
    SetForegroundWindow(win);
    SetFocus(win);
    if (joined) AttachThreadInput(me, fgThread, FALSE);
    fprintf(out, "foreground was %p, joined its input %d\n", (void *) fg, joined);
    pump(800);
    fprintf(out, "foreground is this window: %d\n", GetForegroundWindow() == win);
    HKL korean = LoadKeyboardLayoutW(L"00000412", KLF_ACTIVATE);
    fprintf(out, "Korean layout %p, active %p, IME %d\n", (void *) korean, (void *) GetKeyboardLayout(0),
            ImmIsIME(GetKeyboardLayout(0)));
    HIMC c = ImmGetContext(win);
    DWORD conv = 0, sent = 0;
    ImmGetConversionStatus(c, &conv, &sent);
    fprintf(out, "conversion before %#lx (native %d)\n", conv, (conv & IME_CMODE_NATIVE) != 0);
    ImmSetConversionStatus(c, conv | IME_CMODE_NATIVE, sent);
    ImmGetConversionStatus(c, &conv, &sent);
    fprintf(out, "conversion now %#lx (native %d)\n", conv, (conv & IME_CMODE_NATIVE) != 0);
    pump(200);
    /* the 한/영 key, as a person switches to Hangul */
    key(VK_HANGUL);
    ImmGetConversionStatus(c, &conv, &sent);
    fprintf(out, "after VK_HANGUL: conversion %#lx (native %d)\n", conv, (conv & IME_CMODE_NATIVE) != 0);
    key('G');
    key('K');
    key('S');
    key(VK_SPACE);
    key(VK_HANGUL);
    ImmGetConversionStatus(c, &conv, &sent);
    ImmSetConversionStatus(c, conv & ~(DWORD) IME_CMODE_NATIVE, sent);
    ImmReleaseContext(win, c);
    pump(300);
    fprintf(out, "done%s\n", stopped ? " (stopped)" : "");
    fclose(out);
    DestroyWindow(win);
    return 0;
}
