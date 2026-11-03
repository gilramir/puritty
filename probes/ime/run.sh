#!/bin/sh
# Runs the XIM probe against one IME and engine on its own Xvfb, and types
# a script into it with xdotool (docs/phase3-input.md).
#
#   run.sh IME ENGINE SCRIPT
#     IME     fcitx5 | ibus
#     ENGINE  hangul | mozc | pinyin
#   REMOTE=HOST in the environment runs the probe on HOST over ssh -X.
#   TRACE=1 records the probe's X traffic with xtrace in trace.log.
#     SCRIPT  words for xdotool, run in order: "type:gks" types the letters
#             100 ms apart, "key:Return" presses and releases keys,
#             "sleep:0.5" waits.
#
# Run from visiterm's devbox (Xvfb); the IMEs and xdotool are built from the
# nixpkgs commit the devbox pins, by harness/ime/imes.nix. Everything an IME writes goes
# to a fresh home under .harness-work/ime.
set -e
cd "$(dirname "$0")"
IME=$1 ENGINE=$2 SCRIPT=$3
B=$(nix build --impure --no-link --print-out-paths -f ../../harness/ime/imes.nix fcitx5 ibus xdotool dbus | grep -v -- -man)
FCITX=$(echo "$B" | grep fcitx5) IBUS=$(echo "$B" | grep ibus-with) XDO=$(echo "$B" | grep xdotool)/bin/xdotool
DBUS=$(echo "$B" | grep 'dbus-[0-9.]*$')
W=$(realpath ../..)/.harness-work/ime/$IME-$ENGINE
rm -rf "$W"; mkdir -p "$W/config" "$W/data" "$W/cache" "$W/runtime"; chmod 700 "$W/runtime"
export HOME=$W XDG_CONFIG_HOME=$W/config XDG_DATA_HOME=$W/data XDG_CACHE_HOME=$W/cache XDG_RUNTIME_DIR=$W/runtime
export DISPLAY=:79 LANG=C.UTF-8

Xvfb :79 -screen 0 800x600x24 -nolisten tcp >"$W/xvfb.log" 2>&1 &
XVFB=$!
trap 'kill $IMEPID $XVFB $BUSPID $XTRACE 2>/dev/null; true' EXIT
sleep 0.5

eval "$("$DBUS"/bin/dbus-launch --sh-syntax)"
BUSPID=$DBUS_SESSION_BUS_PID

case $IME in
fcitx5)
  mkdir -p "$XDG_CONFIG_HOME/fcitx5"
  printf '[Groups/0]\nName=Default\nDefault Layout=us\nDefaultIM=%s\n\n[Groups/0/Items/0]\nName=keyboard-us\nLayout=\n\n[Groups/0/Items/1]\nName=%s\nLayout=\n\n[GroupOrder]\n0=Default\n' \
    "$ENGINE" "$ENGINE" >"$XDG_CONFIG_HOME/fcitx5/profile"
  printf '[Behavior]\nActiveByDefault=True\nShareInputState=No\n' >"$XDG_CONFIG_HOME/fcitx5/config"
  # the preedit is the client's to draw (on-the-spot), as visiterm's is
  mkdir -p "$XDG_CONFIG_HOME/fcitx5/conf"
  printf 'UseOnTheSpot=True\n' >"$XDG_CONFIG_HOME/fcitx5/conf/xim.conf"
  export XMODIFIERS=@im=fcitx
  "$FCITX"/bin/fcitx5 --disable=wayland,waylandim,notificationitem,kimpanel,clipboard >"$W/ime.log" 2>&1 &
  IMEPID=$!
  ;;
ibus)
  export XMODIFIERS=@im=ibus GSETTINGS_BACKEND=memory
  "$IBUS"/bin/ibus-daemon --xim --panel=disable --replace >"$W/ime.log" 2>&1 &
  IMEPID=$!
  sleep 1.5
  "$IBUS"/bin/ibus engine "$ENGINE" >>"$W/ime.log" 2>&1 || true
  ;;
esac
sleep 1.5

# REMOTE=HOST runs the probe there over ssh -X, its display this Xvfb
if [ -n "$REMOTE" ]; then
  scp -q ${XIM:-xim} "$REMOTE":/tmp/xim-probe
  ssh -X "$REMOTE" /tmp/xim-probe 3 >"$W/xim.log" 2>&1 &
  sleep 2
elif [ -n "$TRACE" ]; then
  # TRACE=1 puts xtrace between the probe and the server
  xtrace -n -D :80 -d :79 -o "$W/trace.log" -k >/dev/null 2>&1 &
  XTRACE=$!
  sleep 0.5
  DISPLAY=:80 ./${XIM:-xim} 2 >"$W/xim.log" 2>&1 &
else
  ./${XIM:-xim} 2 >"$W/xim.log" 2>&1 &
fi
XIM=$!
sleep 1
for w in $SCRIPT; do
  case $w in
  type:*) "$XDO" type --delay 100 "${w#type:}" ;;
  key:*) "$XDO" key --delay 100 $(echo "${w#key:}" | tr , ' ') ;;
  sleep:*) sleep "${w#sleep:}" ;;
  esac
done
wait $XIM || true
cat "$W/xim.log"
