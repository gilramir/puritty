#!/usr/bin/env python3
"""The X server across a network, as ETX's is (docs/rhel8-etx.md RE12).

Listens for X clients on a TCP port and passes each connection on to the
real X server (Xvfb), with three changes:

- the connection setup reply says the vendor is `--vendor` (ETX's says
  `Rocket Software`), the string puritty reads to know it is under ETX;
- each direction is held back `--delay` milliseconds, as a hop to another
  host would be;
- a QueryExtension of an extension in `--hide` is answered "not
  present" (Xvfb cannot turn Present off, and ETX's server has none);
- the bytes each way are counted, all connections together, and written
  every second to `--counts` as `to_server from_server connections`, which
  is what the hop from the VM to ETX's server carries;
- with `--trace FILE`, a line for every request, reply, event and error:
  the time, the connection, the sequence number, and the request's opcode
  (with the name a QueryExtension or InternAtom asks for), or the reply's,
  event's or error's code.

Python 3.6 (AlmaLinux 8's), standard library only.

    xproxy.py --listen 6032 --server 127.0.0.1:6005 --vendor "Rocket Software" \
        --delay 1 --counts /tmp/xproxy.counts
"""

import argparse
import asyncio
import os
import struct
import time

totals = {"to_server": 0, "from_server": 0, "connections": 0}
tracing = {"file": None, "start": time.monotonic()}


def note(conn, text):
    f = tracing["file"]
    if f is not None:
        f.write("%10.4f c%d %s\n" % (time.monotonic() - tracing["start"], conn, text))
        f.flush()


def setup_reply(data, little, vendor):
    """The server's setup reply with its vendor string replaced; a refusal
    (first byte not 1) unchanged."""
    if data[0] != 1:
        return data
    order = "<" if little else ">"
    (vlen,) = struct.unpack(order + "H", data[24:26])
    padded = (vlen + 3) & ~3
    new = vendor.encode("latin-1")
    newpadded = (len(new) + 3) & ~3
    body = (
        data[8:24]
        + struct.pack(order + "H", len(new))
        + data[26:40]
        + new
        + b"\0" * (newpadded - len(new))
        + data[40 + padded :]
    )
    return data[0:6] + struct.pack(order + "H", len(body) // 4) + body


class Delayed:
    """Writes what it is given to `writer` `delay` seconds later, in order."""

    def __init__(self, writer, delay, key):
        self.writer = writer
        self.delay = delay
        self.key = key
        self.queue = asyncio.Queue()
        self.task = asyncio.ensure_future(self.run())

    def put(self, data):
        self.queue.put_nowait((time.monotonic() + self.delay, data))

    async def run(self):
        while True:
            due, data = await self.queue.get()
            if data is None:
                break
            wait = due - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            self.writer.write(data)
            totals[self.key] += len(data)
            await self.writer.drain()
        try:
            self.writer.close()
        except Exception:
            pass


async def replies(reader, out, order, conn):
    """The server's messages passed on whole, each noted when tracing."""
    buf = b""
    try:
        while True:
            data = await reader.read(65536)
            if not data:
                break
            buf += data
            sent = 0
            while len(buf) - sent >= 32:
                kind = buf[sent] & 0x7F
                size = 32
                if kind == 1 or kind == 35:
                    (more,) = struct.unpack(order + "I", buf[sent + 4 : sent + 8])
                    size += more * 4
                if len(buf) - sent < size:
                    break
                (seq,) = struct.unpack(order + "H", buf[sent + 2 : sent + 4])
                if kind == 0:
                    note(conn, "<- error %d seq %d" % (buf[sent + 1], seq))
                elif kind == 1:
                    note(conn, "<- reply seq %d" % seq)
                elif kind == 35:
                    note(conn, "<- generic event ext %d type %d seq %d" % (buf[sent + 1], struct.unpack(order + "H", buf[sent + 8 : sent + 10])[0], seq))
                else:
                    note(conn, "<- event %d seq %d" % (kind, seq))
                sent += size
            if sent:
                out.put(buf[:sent])
                buf = buf[sent:]
    except (ConnectionError, OSError):
        pass
    out.put(None)


async def requests(reader, out, order, hidden, conn):
    """The client's requests passed on whole, with a QueryExtension of a
    hidden extension asking for a name no server has, so the answer is
    "not present" and the sequence numbers stay as they were."""
    buf = b""
    seq = 0
    try:
        while True:
            data = await reader.read(65536)
            if not data:
                break
            buf += data
            sent = 0
            while len(buf) - sent >= 4:
                (n,) = struct.unpack(order + "H", buf[sent + 2 : sent + 4])
                if n == 0:
                    # BIG-REQUESTS: the length in the next four bytes
                    if len(buf) - sent < 8:
                        break
                    (n,) = struct.unpack(order + "I", buf[sent + 4 : sent + 8])
                size = n * 4
                if size < 4 or len(buf) - sent < size:
                    break
                req = buf[sent : sent + size]
                seq = (seq + 1) & 0xFFFF
                said = ""
                if req[0] in (16, 98) and size >= 8:
                    # InternAtom, QueryExtension: the name asked for
                    (nlen,) = struct.unpack(order + "H", req[4:6])
                    said = " " + req[8 : 8 + nlen].decode("latin-1")
                if req[0] == 98 and said[1:] in hidden:
                    req = req[:8] + b"\x7f" * nlen + req[8 + nlen :]
                    said += " (hidden)"
                note(conn, "-> request %d seq %d%s" % (req[0], seq, said))
                out.put(req)
                sent += size
            buf = buf[sent:]
    except (ConnectionError, OSError):
        pass
    out.put(None)


async def client(creader, cwriter, args):
    host, port = args.server.rsplit(":", 1)
    try:
        sreader, swriter = await asyncio.open_connection(host, int(port))
    except OSError:
        cwriter.close()
        return
    totals["connections"] += 1
    conn = totals["connections"]
    delay = args.delay / 1000.0
    to_server = Delayed(swriter, delay, "to_server")
    from_server = Delayed(cwriter, delay, "from_server")
    try:
        # the client's setup: its byte order, then the lengths of its
        # authorization, all passed on as they are
        head = await creader.readexactly(12)
        little = head[0:1] == b"l"
        order = "<" if little else ">"
        nlen, dlen = struct.unpack(order + "HH", head[6:10])
        rest = await creader.readexactly(((nlen + 3) & ~3) + ((dlen + 3) & ~3))
        to_server.put(head + rest)
        # the server's reply: eight bytes, then its length in fours
        rhead = await sreader.readexactly(8)
        (more,) = struct.unpack(order + "H", rhead[6:8])
        rbody = await sreader.readexactly(more * 4)
        from_server.put(setup_reply(rhead + rbody, little, args.vendor))
    except (asyncio.IncompleteReadError, ConnectionError, OSError):
        to_server.put(None)
        from_server.put(None)
        return
    hidden = set(h for h in args.hide.split(",") if h)
    note(conn, "connected")
    await asyncio.gather(requests(creader, to_server, order, hidden, conn), replies(sreader, from_server, order, conn))
    note(conn, "closed")


async def report(path):
    while True:
        with open(path + ".new", "w") as f:
            f.write("%d %d %d\n" % (totals["to_server"], totals["from_server"], totals["connections"]))
        os.replace(path + ".new", path)
        await asyncio.sleep(1)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--listen", type=int, required=True)
    p.add_argument("--server", required=True)
    p.add_argument("--vendor", default="Rocket Software")
    p.add_argument("--delay", type=float, default=0.0, help="milliseconds each way")
    p.add_argument("--hide", default="", help="extensions to answer not present, by commas")
    p.add_argument("--counts", default="/tmp/xproxy.counts")
    p.add_argument("--trace", default="", help="a file to note every message in")
    args = p.parse_args()
    if args.trace:
        tracing["file"] = open(args.trace, "w")
    loop = asyncio.get_event_loop()
    server = loop.run_until_complete(
        asyncio.start_server(lambda r, w: client(r, w, args), "0.0.0.0", args.listen)
    )
    asyncio.ensure_future(report(args.counts))
    try:
        loop.run_forever()
    finally:
        server.close()


if __name__ == "__main__":
    main()
