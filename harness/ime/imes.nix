# The IMEs of the phase 3 matrix (docs/phase3-input.md), from the nixpkgs
# commit puritty's devbox pins: fcitx5 and ibus, each with its Korean,
# Japanese and pinyin engines.
let
  pkgs = import (builtins.fetchTarball
    "https://github.com/NixOS/nixpkgs/archive/c80073788adf88abfdc443465311f00e7a231600.tar.gz") { };
in {
  fcitx5 = pkgs.qt6Packages.fcitx5-with-addons.override {
    addons = [ pkgs.fcitx5-hangul pkgs.fcitx5-mozc pkgs.qt6Packages.fcitx5-chinese-addons ];
  };
  ibus = pkgs.ibus-with-plugins.override {
    plugins = [ pkgs.ibus-engines.hangul pkgs.ibus-engines.mozc pkgs.ibus-engines.libpinyin ];
  };
  xdotool = pkgs.xdotool;
  dbus = pkgs.dbus;
}
