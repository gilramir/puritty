#!/usr/bin/env python3
"""An XDND drop target that logs everything (puritty docs/sftp.md FT21):
the types a source offers, each position it reports, and on the drop the
data in every type it offered, as bytes. One JSON object a line on stdout.

    target.py [--x X --y Y --w W --h H] [--name NAME]

XDND version 5 (https://www.freedesktop.org/wiki/Specifications/XDND/):
XdndAware on the window; XdndEnter, Position, Leave, Drop from the
source; XdndStatus and Finished back; the data read with ConvertSelection
of XdndSelection, INCR included.
"""
import argparse, json, sys, time
from Xlib import X, display, Xatom
from Xlib.protocol import event

ap = argparse.ArgumentParser()
ap.add_argument("--x", type=int, default=700)
ap.add_argument("--y", type=int, default=100)
ap.add_argument("--w", type=int, default=500)
ap.add_argument("--h", type=int, default=500)
ap.add_argument("--name", default="xdnd-probe")
a = ap.parse_args()

d = display.Display()
s = d.screen()
A = lambda n: d.intern_atom(n)
name = lambda at: d.get_atom_name(at) if at else None
w = s.root.create_window(a.x, a.y, a.w, a.h, 0, s.root_depth, X.InputOutput, X.CopyFromParent,
                         background_pixel=s.white_pixel, event_mask=X.PropertyChangeMask | X.StructureNotifyMask)
w.set_wm_name(a.name)
w.change_property(A("XdndAware"), Xatom.ATOM, 32, [5])
w.map()
d.flush()


def say(**k):
    k["t"] = round(time.time(), 3)
    print(json.dumps(k, ensure_ascii=False), flush=True)


def send(to, kind, data):
    ev = event.ClientMessage(window=to, client_type=A(kind), data=(32, data))
    d.create_resource_object("window", to).send_event(ev, event_mask=0)
    d.flush()


def read_property(prop):
    """The property's bytes, following INCR."""
    got = w.get_full_property(prop, X.AnyPropertyType, sizehint=1 << 24)
    if got is None:
        return None, None
    if got.property_type == A("INCR"):
        w.delete_property(prop)
        d.flush()
        parts = []
        while True:
            e = d.next_event()
            if e.type == X.PropertyNotify and e.atom == prop and e.state == X.PropertyNewValue:
                piece = w.get_full_property(prop, X.AnyPropertyType, sizehint=1 << 24)
                w.delete_property(prop)
                d.flush()
                if piece is None or len(piece.value) == 0:
                    break
                parts.append(bytes(piece.value))
        return b"".join(parts), "INCR"
    v = got.value
    if isinstance(v, str):
        v = v.encode("latin-1")
    elif not isinstance(v, (bytes, bytearray)):
        v = b"".join(int(x).to_bytes(4, "little") for x in v) if got.format == 32 else bytes(v)
    return bytes(v), name(got.property_type)


def convert(target, when):
    prop = A("PROBE_DATA")
    w.convert_selection(A("XdndSelection"), target, prop, when)
    d.flush()
    deadline = time.time() + 5
    while time.time() < deadline:
        while d.pending_events():
            e = d.next_event()
            if e.type == X.SelectionNotify:
                if e.property == X.NONE:
                    return None, "refused"
                return read_property(prop)
        time.sleep(0.01)
    return None, "no answer in 5 s"


source = None
types = []
positions = 0
end = time.time() + 120
while time.time() < end:
    if not d.pending_events():
        time.sleep(0.005)
        continue
    e = d.next_event()
    if e.type != X.ClientMessage:
        continue
    kind = name(e.client_type)
    l = e.data[1]
    if kind == "XdndEnter":
        source = l[0]
        version = l[1] >> 24
        more = l[1] & 1
        types = [name(t) for t in l[2:5] if t]
        if more:
            tl = d.create_resource_object("window", source).get_full_property(A("XdndTypeList"), Xatom.ATOM)
            types = [name(t) for t in tl.value] if tl else types
        say(event="enter", version=version, more_than_three=bool(more), types=types)
        positions = 0
    elif kind == "XdndPosition":
        positions += 1
        x, y = l[2] >> 16, l[2] & 0xFFFF
        if positions <= 3 or positions % 20 == 0:
            say(event="position", n=positions, root=[x, y], action=name(l[4]), time=l[3])
        # accept, a copy, and ask for every position (bit 1), no rectangle
        send(l[0], "XdndStatus", [w.id, 3, 0, 0, A("XdndActionCopy")])
    elif kind == "XdndLeave":
        say(event="leave", positions=positions)
    elif kind == "XdndDrop":
        when = l[2]
        say(event="drop", positions=positions, time=when)
        for t in types:
            data, how = convert(A(t), when)
            say(event="data", type=t, how=how, length=None if data is None else len(data),
                bytes=None if data is None else data[:600].hex(), text=None if data is None else data[:600].decode("utf-8", "backslashreplace"))
        send(l[0], "XdndFinished", [w.id, 1, A("XdndActionCopy"), 0, 0])
        say(event="finished")
        break
