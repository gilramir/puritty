/* conpty-drain: a program under the system's ConPTY at COLS by ROWS, its
 * output read as fast as it comes and thrown away, with no terminal
 * (docs/windows.md WS26). How long ConPTY alone takes to pass a workload
 * on, and how many bytes it passes for what the program wrote.
 *
 *   conpty-drain COLS ROWS RESULT COMMAND-LINE
 *
 * Appends to RESULT: the size, the bytes read, the milliseconds from the
 * start to the end of the output. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static HANDLE out_read;
static volatile LONGLONG got;
/* CONPTY_CAPTURE=FILE keeps what ConPTY passed on */
static FILE *capture;

static DWORD WINAPI drain(LPVOID arg) {
    (void) arg;
    static char buf[1 << 16];
    DWORD n;
    while (ReadFile(out_read, buf, sizeof buf, &n, NULL) && n > 0) {
        got += n;
        if (capture) fwrite(buf, 1, n, capture);
    }
    return 0;
}

int main(int argc, char **argv) {
    if (argc < 5) {
        fprintf(stderr, "usage: conpty-drain COLS ROWS RESULT COMMAND-LINE\n");
        return 1;
    }
    COORD size = {(SHORT) atoi(argv[1]), (SHORT) atoi(argv[2])};
    if (getenv("CONPTY_CAPTURE")) capture = fopen(getenv("CONPTY_CAPTURE"), "wb");
    HANDLE in_read, in_write, out_write;
    CreatePipe(&in_read, &in_write, NULL, 0);
    CreatePipe(&out_read, &out_write, NULL, 0);
    HPCON pc;
    if (CreatePseudoConsole(size, in_read, out_write, 0, &pc) != S_OK) return 2;
    SIZE_T bytes = 0;
    InitializeProcThreadAttributeList(NULL, 1, 0, &bytes);
    STARTUPINFOEXW si;
    memset(&si, 0, sizeof si);
    si.StartupInfo.cb = sizeof si;
    /* no standard handles of the parent's: under ssh they are pipes, and a
     * child given them writes past the pseudo console */
    si.StartupInfo.dwFlags = STARTF_USESTDHANDLES;
    si.lpAttributeList = (LPPROC_THREAD_ATTRIBUTE_LIST) malloc(bytes);
    InitializeProcThreadAttributeList(si.lpAttributeList, 1, 0, &bytes);
    UpdateProcThreadAttribute(si.lpAttributeList, 0, PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE, pc, sizeof pc, NULL, NULL);
    /* the command line after the third argument, as one string */
    wchar_t line[4096];
    int len = MultiByteToWideChar(CP_UTF8, 0, argv[4], -1, line, 4096);
    for (int i = 5; i < argc && len > 0 && len < 4000; i++) {
        line[len - 1] = L' ';
        len += MultiByteToWideChar(CP_UTF8, 0, argv[i], -1, line + len, 4096 - len);
    }
    PROCESS_INFORMATION pi;
    LARGE_INTEGER f, t0, t1;
    QueryPerformanceFrequency(&f);
    HANDLE th = CreateThread(NULL, 0, drain, NULL, 0, NULL);
    QueryPerformanceCounter(&t0);
    if (!CreateProcessW(NULL, line, NULL, NULL, FALSE, EXTENDED_STARTUPINFO_PRESENT, NULL, NULL, &si.StartupInfo, &pi)) return 3;
    WaitForSingleObject(pi.hProcess, INFINITE);
    /* ConPTY passes on what is left, then its output ends when it closes */
    ClosePseudoConsole(pc);
    CloseHandle(out_write);
    WaitForSingleObject(th, 120000);
    if (capture) fclose(capture);
    QueryPerformanceCounter(&t1);
    double ms = (double) (t1.QuadPart - t0.QuadPart) * 1000.0 / (double) f.QuadPart;
    FILE *r = fopen(argv[3], "a");
    if (r) {
        fprintf(r, "%dx%d\t%lld\t%.0f\n", size.X, size.Y, (long long) got, ms);
        fclose(r);
    }
    return 0;
}
