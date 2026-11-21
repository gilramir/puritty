#!/bin/sh
# The desktop inside the puritty-etx container (docs/rhel8-etx.md RE12):
# Xvfb at ETX's measured size, reached only through xproxy.py as
# etx-server:32 (another host, display 32, vendor "Rocket Software"), and
# xfwm4 on it. Runs until the container is stopped.
#
# ETX_DELAY_MS (default 1) holds each direction of the X connection back;
# ETX_TRACE set notes every X message in share/xtrace.txt.
set -e
Xvfb :5 -screen 0 1902x879x24 -dpi 100 -listen tcp -nolisten unix -ac \
    -extension MIT-SHM >/tmp/xvfb.log 2>&1 &
for i in $(seq 1 50); do [ -e /tmp/.X5-lock ] && break; sleep 0.1; done
python3 /etx/xproxy.py --listen 6032 --server 127.0.0.1:6005 \
    --vendor "Rocket Software" --hide Present,MIT-SHM,DRI3 --delay "${ETX_DELAY_MS:-1}" \
    --counts /tmp/xproxy.counts ${ETX_TRACE:+--trace /share/xtrace.txt} >/tmp/xproxy.log 2>&1 &
for i in $(seq 1 50); do [ -e /tmp/xproxy.counts ] && break; sleep 0.1; done
export DISPLAY=etx-server:32
# a session bus, which xfwm4's settings (xfconf) need, as an Xfce session
# has; its address kept for the commands etx.sh runs
eval "$(dbus-launch --sh-syntax)"
echo "$DBUS_SESSION_BUS_ADDRESS" >/tmp/dbus.address
# ETX_COMPOSITING=true or false, written before xfwm4 starts
[ -z "$ETX_COMPOSITING" ] || xfconf-query -c xfwm4 -p /general/use_compositing -n -t bool -s "$ETX_COMPOSITING"
xfwm4 >/tmp/xfwm4.log 2>&1 &
echo ready >/tmp/etx.ready
wait
