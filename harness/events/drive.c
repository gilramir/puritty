/* drive.exe: the events gate's hands on Windows (docs/windows.md WS19).
 * Finds core-events' window (its title, "puritty-events"), makes it the
 * foreground, and does a case's actions with SendInput, as a person's keys
 * and mouse would reach it; then asks the window to close.
 *
 *     drive.exe CASE
 *
 * Before the case, the pointer is put off the window and F24 is typed,
 * which marks where the case begins in the window's log.
 *
 * Every input is sent only while that window has the foreground, and a
 * button only while the pointer is over it: anything else, and the driver
 * stops without sending, so that nothing reaches another program. Exits 0
 * when every action was done, 2 when it stopped, 3 when there was no
 * window.
 *
 * The actions, one a line (# begins a comment):
 *
 *   key K[+K...]   the keys pressed in order and released in reverse
 *                  (xdotool's names: a, A is not one, shift+a; Return,
 *                  KP_Enter, Left, F5, KP_1, grave, ...)
 *   down K, up K   one key pressed or released
 *   text S         S typed as characters (KEYEVENTF_UNICODE)
 *   move X Y       the pointer to the window's pixel (X, Y)
 *   press B, release B, click B   a button: left, middle, right, x1, x2
 *   wheel D, hwheel D             the wheel turned by D (120 a notch)
 *   layout L       the window's keyboard layout: us (each case begins
 *                  there), usintl (US-International), korean
 *   sleep MS
 *   cursor S       fails unless the pointer shown is S: ibeam, arrow
 *   shot FILE      the screen around the window, as a BMP (a look for a
 *                  person; the gate does not hold it)
 *   mode ...       the probe's (harness/events.py), passed over here */
#define WIN32_LEAN_AND_MEAN
#define UNICODE
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static HWND target;

static int foreground(void) {
    if (GetForegroundWindow() == target) return 1;
    fprintf(stderr, "drive: the foreground is another window; stopped\n");
    return 0;
}

static void settle(void) { Sleep(60); }

typedef struct {
    const char *name;
    WORD vk;
    int ext;
} Key;

static const Key keys[] = {
    {"Return", VK_RETURN, 0}, {"KP_Enter", VK_RETURN, 1}, {"Escape", VK_ESCAPE, 0}, {"Tab", VK_TAB, 0},
    {"BackSpace", VK_BACK, 0}, {"space", VK_SPACE, 0}, {"Left", VK_LEFT, 1}, {"Right", VK_RIGHT, 1},
    {"Up", VK_UP, 1}, {"Down", VK_DOWN, 1}, {"Home", VK_HOME, 1}, {"End", VK_END, 1}, {"Prior", VK_PRIOR, 1},
    {"Next", VK_NEXT, 1}, {"Insert", VK_INSERT, 1}, {"Delete", VK_DELETE, 1}, {"KP_Insert", VK_INSERT, 0},
    {"KP_End", VK_END, 0}, {"KP_Add", VK_ADD, 0}, {"KP_Subtract", VK_SUBTRACT, 0}, {"KP_Multiply", VK_MULTIPLY, 0},
    {"KP_Divide", VK_DIVIDE, 1}, {"KP_Decimal", VK_DECIMAL, 0}, {"shift", VK_LSHIFT, 0}, {"rshift", VK_RSHIFT, 0},
    {"ctrl", VK_LCONTROL, 0}, {"rctrl", VK_RCONTROL, 1}, {"alt", VK_LMENU, 0}, {"ralt", VK_RMENU, 1},
    {"Caps_Lock", VK_CAPITAL, 0}, {"Num_Lock", VK_NUMLOCK, 1}, {"Hangul", VK_HANGUL, 0}, {"Hangul_Hanja", VK_HANJA, 0},
    {"grave", VK_OEM_3, 0}, {"minus", VK_OEM_MINUS, 0}, {"equal", VK_OEM_PLUS, 0}, {"bracketleft", VK_OEM_4, 0},
    {"bracketright", VK_OEM_6, 0}, {"backslash", VK_OEM_5, 0}, {"semicolon", VK_OEM_1, 0},
    {"apostrophe", VK_OEM_7, 0}, {"comma", VK_OEM_COMMA, 0}, {"period", VK_OEM_PERIOD, 0}, {"slash", VK_OEM_2, 0},
};

static int key_of(const char *name, WORD *vk, int *ext) {
    *ext = 0;
    if (strlen(name) == 1 && name[0] >= 'a' && name[0] <= 'z') {
        *vk = (WORD) (name[0] - 'a' + 'A');
        return 1;
    }
    if (strlen(name) == 1 && name[0] >= '0' && name[0] <= '9') {
        *vk = (WORD) name[0];
        return 1;
    }
    if (name[0] == 'F' && atoi(name + 1) >= 1 && atoi(name + 1) <= 24) {
        *vk = (WORD) (VK_F1 + atoi(name + 1) - 1);
        return 1;
    }
    if (strncmp(name, "KP_", 3) == 0 && name[3] >= '0' && name[3] <= '9' && !name[4]) {
        *vk = (WORD) (VK_NUMPAD0 + name[3] - '0');
        return 1;
    }
    for (size_t i = 0; i < sizeof keys / sizeof *keys; i++)
        if (strcmp(keys[i].name, name) == 0) {
            *vk = keys[i].vk;
            *ext = keys[i].ext;
            return 1;
        }
    fprintf(stderr, "drive: no key %s\n", name);
    return 0;
}

/* The keys pressed and not yet released, which the driver releases
 * whatever happens, so that no key is left held. */
static Key held[16];
static int nheld;

static void raw_key(WORD vk, int ext, int up) {
    INPUT in;
    memset(&in, 0, sizeof in);
    in.type = INPUT_KEYBOARD;
    in.ki.wVk = vk;
    in.ki.wScan = (WORD) MapVirtualKeyW(vk, MAPVK_VK_TO_VSC);
    in.ki.dwFlags = (ext ? KEYEVENTF_EXTENDEDKEY : 0) | (up ? KEYEVENTF_KEYUP : 0);
    SendInput(1, &in, sizeof in);
}

/* A key down or up, with its scan code, as a keyboard sends it. */
static int send_key(const char *name, int up) {
    WORD vk;
    int ext;
    if (!key_of(name, &vk, &ext) || !foreground()) return 0;
    raw_key(vk, ext, up);
    if (!up && nheld < 16) held[nheld++] = (Key) {name, vk, ext};
    for (int i = 0; up && i < nheld; i++)
        if (held[i].vk == vk && held[i].ext == ext) held[i--] = held[--nheld];
    settle();
    return 1;
}

static int combo(char *spec) {
    char *names[8];
    int n = 0;
    for (char *k = strtok(spec, "+"); k && n < 8; k = strtok(NULL, "+")) names[n++] = k;
    for (int i = 0; i < n; i++)
        if (!send_key(names[i], 0)) return 0;
    for (int i = n - 1; i >= 0; i--)
        if (!send_key(names[i], 1)) return 0;
    return 1;
}

static int text(const char *s) {
    int n = MultiByteToWideChar(CP_UTF8, 0, s, -1, NULL, 0);
    WCHAR *w = malloc((size_t) n * sizeof *w);
    MultiByteToWideChar(CP_UTF8, 0, s, -1, w, n);
    for (int i = 0; w[i]; i++) {
        if (!foreground()) return 0;
        INPUT in[2];
        memset(in, 0, sizeof in);
        in[0].type = INPUT_KEYBOARD;
        in[0].ki.wScan = w[i];
        in[0].ki.dwFlags = KEYEVENTF_UNICODE;
        in[1] = in[0];
        in[1].ki.dwFlags |= KEYEVENTF_KEYUP;
        SendInput(2, in, sizeof *in);
        settle();
    }
    free(w);
    return 1;
}

static int move(int x, int y) {
    if (!foreground()) return 0;
    POINT p = {x, y};
    ClientToScreen(target, &p);
    SetCursorPos(p.x, p.y);
    settle();
    return 1;
}

/* A button's release goes wherever the pointer is: a drag may end past the
 * window's edge, and the window has the pointer captured. */
static int mouse(DWORD flags, DWORD data) {
    POINT p;
    GetCursorPos(&p);
    int release = (flags & (MOUSEEVENTF_LEFTUP | MOUSEEVENTF_MIDDLEUP | MOUSEEVENTF_RIGHTUP | MOUSEEVENTF_XUP)) != 0;
    if (!foreground()) return 0;
    if (!release && WindowFromPoint(p) != target) {
        fprintf(stderr, "drive: the pointer is not over the window; stopped\n");
        return 0;
    }
    INPUT in;
    memset(&in, 0, sizeof in);
    in.type = INPUT_MOUSE;
    in.mi.dwFlags = flags;
    in.mi.mouseData = data;
    SendInput(1, &in, sizeof in);
    settle();
    return 1;
}

static int buttons(const char *b, int press, int release) {
    DWORD down, up, data = 0;
    if (strcmp(b, "left") == 0) down = MOUSEEVENTF_LEFTDOWN, up = MOUSEEVENTF_LEFTUP;
    else if (strcmp(b, "middle") == 0) down = MOUSEEVENTF_MIDDLEDOWN, up = MOUSEEVENTF_MIDDLEUP;
    else if (strcmp(b, "right") == 0) down = MOUSEEVENTF_RIGHTDOWN, up = MOUSEEVENTF_RIGHTUP;
    else if (strcmp(b, "x1") == 0) down = MOUSEEVENTF_XDOWN, up = MOUSEEVENTF_XUP, data = XBUTTON1;
    else if (strcmp(b, "x2") == 0) down = MOUSEEVENTF_XDOWN, up = MOUSEEVENTF_XUP, data = XBUTTON2;
    else {
        fprintf(stderr, "drive: no button %s\n", b);
        return 0;
    }
    if (press && !mouse(down, data)) return 0;
    if (release && !mouse(up, data)) return 0;
    return 1;
}

static int layout(const char *name) {
    const WCHAR *id = strcmp(name, "korean") == 0 ? L"00000412" : strcmp(name, "usintl") == 0 ? L"00020409" : L"00000409";
    HKL k = LoadKeyboardLayoutW(id, 0);
    PostMessageW(target, WM_INPUTLANGCHANGEREQUEST, 0, (LPARAM) k);
    Sleep(200);
    return 1;
}

/* The screen around the window, 400 pixels past each edge, as a BMP: a
 * copy of what is shown, which takes no focus. */
static int shot(const char *path) {
    RECT r;
    GetWindowRect(target, &r);
    int x = r.left - 400, y = r.top - 400, w = r.right - r.left + 800, h = r.bottom - r.top + 800;
    HDC screen = GetDC(NULL), mem = CreateCompatibleDC(screen);
    BITMAPINFO bi;
    memset(&bi, 0, sizeof bi);
    bi.bmiHeader.biSize = sizeof bi.bmiHeader;
    bi.bmiHeader.biWidth = w;
    bi.bmiHeader.biHeight = h;
    bi.bmiHeader.biPlanes = 1;
    bi.bmiHeader.biBitCount = 24;
    void *bits;
    HBITMAP bmp = CreateDIBSection(screen, &bi, DIB_RGB_COLORS, &bits, NULL, 0);
    HGDIOBJ was = SelectObject(mem, bmp);
    BitBlt(mem, 0, 0, w, h, screen, x, y, SRCCOPY | CAPTUREBLT);
    GdiFlush();
    int stride = (w * 3 + 3) & ~3;
    BITMAPFILEHEADER fh = {0x4D42, (DWORD) (sizeof fh + sizeof bi.bmiHeader + (size_t) stride * h), 0, 0,
                           (DWORD) (sizeof fh + sizeof bi.bmiHeader)};
    FILE *f = fopen(path, "wb");
    if (f) {
        fwrite(&fh, sizeof fh, 1, f);
        fwrite(&bi.bmiHeader, sizeof bi.bmiHeader, 1, f);
        fwrite(bits, (size_t) stride * h, 1, f);
        fclose(f);
    }
    SelectObject(mem, was);
    DeleteObject(bmp);
    DeleteDC(mem);
    ReleaseDC(NULL, screen);
    return f != NULL;
}

/* Whether the pointer shown is the I-beam or the arrow, as `want` says. */
static int cursor_is(const char *want) {
    CURSORINFO ci = {sizeof ci, 0, NULL, {0, 0}};
    GetCursorInfo(&ci);
    HCURSOR c = LoadCursorW(NULL, (LPCWSTR) (strcmp(want, "arrow") == 0 ? IDC_ARROW : IDC_IBEAM));
    if (ci.hCursor == c) return 1;
    fprintf(stderr, "drive: the pointer is not the %s\n", want);
    return 0;
}

static int act(char *line) {
    char *nl = strpbrk(line, "\r\n");
    if (nl) *nl = 0;
    while (*line == ' ') line++;
    if (!*line || *line == '#') return 1;
    char *arg = strchr(line, ' ');
    if (arg) *arg++ = 0;
    else arg = "";
    int x = 0, y = 0;
    if (strcmp(line, "key") == 0) return combo(arg);
    if (strcmp(line, "down") == 0) return send_key(arg, 0);
    if (strcmp(line, "up") == 0) return send_key(arg, 1);
    if (strcmp(line, "text") == 0) return text(arg);
    if (strcmp(line, "move") == 0 && sscanf(arg, "%d %d", &x, &y) == 2) return move(x, y);
    if (strcmp(line, "press") == 0) return buttons(arg, 1, 0);
    if (strcmp(line, "release") == 0) return buttons(arg, 0, 1);
    if (strcmp(line, "click") == 0) return buttons(arg, 1, 1);
    if (strcmp(line, "wheel") == 0) return mouse(MOUSEEVENTF_WHEEL, (DWORD) atoi(arg));
    if (strcmp(line, "hwheel") == 0) return mouse(MOUSEEVENTF_HWHEEL, (DWORD) atoi(arg));
    if (strcmp(line, "layout") == 0) return layout(arg);
    if (strcmp(line, "sleep") == 0) return Sleep((DWORD) atoi(arg)), 1;
    if (strcmp(line, "shot") == 0) return shot(arg);
    if (strcmp(line, "cursor") == 0) return cursor_is(arg);
    if (strcmp(line, "mode") == 0) return 1;
    fprintf(stderr, "drive: no action %s\n", line);
    return 0;
}

int main(int argc, char **argv) {
    if (argc < 2) return 1;
    SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2);
    for (int i = 0; i < 100 && !target; i++) {
        target = FindWindowW(L"puritty", L"puritty-events");
        if (!target) Sleep(100);
    }
    if (!target) {
        fprintf(stderr, "drive: no window\n");
        return 3;
    }
    /* Windows keeps a program not started by input from taking the
     * foreground; joining the foreground thread's input for a moment lets
     * it, and sends that thread nothing (WS11). Tried a few times, as a
     * window that has just closed may still hold it. */
    for (int tries = 0; tries < 10 && GetForegroundWindow() != target; tries++) {
        HWND fg = GetForegroundWindow();
        DWORD fgThread = GetWindowThreadProcessId(fg, NULL), me = GetCurrentThreadId();
        BOOL joined = fg && fgThread != me && AttachThreadInput(me, fgThread, TRUE);
        BringWindowToTop(target);
        SetForegroundWindow(target);
        if (joined) AttachThreadInput(me, fgThread, FALSE);
        Sleep(200);
    }
    Sleep(400);
    layout("us");
    /* the pointer off the window, and F24, which says the case begins:
     * what the window said before it, as it opened, is not the case's */
    RECT r;
    GetWindowRect(target, &r);
    SetCursorPos(r.right + 8, r.top + 8);
    Sleep(100);
    /* the pins are taken with both locks off (docs/windows.md WS19) */
    int ok = 1;
    if (GetKeyState(VK_CAPITAL) & 1) fprintf(stderr, "drive: Caps Lock is on; the pins are taken with it off\n"), ok = 0;
    if (GetKeyState(VK_NUMLOCK) & 1) fprintf(stderr, "drive: Num Lock is on; the pins are taken with it off\n"), ok = 0;
    char begin[] = "F24";
    if (ok) ok = combo(begin);
    FILE *f = fopen(argv[1], "r");
    char line[1024];
    while (ok && f && fgets(line, sizeof line, f)) ok = act(line);
    if (f) fclose(f);
    while (nheld > 0) {
        nheld--;
        raw_key(held[nheld].vk, held[nheld].ext, 1);
    }
    Sleep(300);
    PostMessageW(target, WM_CLOSE, 0, 0);
    return ok ? 0 : 2;
}
