#!/usr/bin/env python3
"""Asks an X window to close as a window manager does: a WM_PROTOCOLS client
message naming WM_DELETE_WINDOW, sent to the window itself. Xvfb has no
window manager, and xdotool's `windowquit` asks one (`_NET_CLOSE_WINDOW`),
so the scenarios send this instead.

    wmclose.py WINDOW-ID          (DISPLAY from the environment)
"""

import ctypes
import ctypes.util
import sys


class ClientMessage(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("serial", ctypes.c_ulong),
        ("send_event", ctypes.c_int),
        ("display", ctypes.c_void_p),
        ("window", ctypes.c_ulong),
        ("message_type", ctypes.c_ulong),
        ("format", ctypes.c_int),
        ("data", ctypes.c_long * 5),
    ]


class Event(ctypes.Union):
    _fields_ = [("client", ClientMessage), ("pad", ctypes.c_long * 24)]


def main() -> int:
    window = int(sys.argv[1], 0)
    x = ctypes.CDLL(ctypes.util.find_library("X11"))
    x.XOpenDisplay.restype = ctypes.c_void_p
    x.XInternAtom.restype = ctypes.c_ulong
    x.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
    x.XSendEvent.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_long, ctypes.c_void_p]
    x.XFlush.argtypes = [ctypes.c_void_p]
    x.XCloseDisplay.argtypes = [ctypes.c_void_p]
    d = x.XOpenDisplay(None)
    if not d:
        sys.exit("wmclose.py: cannot open the display")
    e = Event()
    e.client.type = 33  # ClientMessage
    e.client.window = window
    e.client.message_type = x.XInternAtom(d, b"WM_PROTOCOLS", 0)
    e.client.format = 32
    e.client.data[0] = x.XInternAtom(d, b"WM_DELETE_WINDOW", 0)
    e.client.data[1] = 0  # CurrentTime
    x.XSendEvent(d, window, 0, 0, ctypes.byref(e))
    x.XFlush(d)
    x.XCloseDisplay(d)
    return 0


if __name__ == "__main__":
    sys.exit(main())
