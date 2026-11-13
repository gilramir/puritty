# The home page's picture, `tmux-on-windows.png`

puritty on Windows 11 (beelink1, in its user's desktop session), with three
restored ssh tabs to nene in their own colors; the first runs `tmux -CC
attach` on a tmux 3.8 session made for it: `git log` on the left, two Tang
poems and a table in Chinese on the right, Thai in a floating pane.

1. On nene, write the panes' text and make the session (its own socket):

   ```sh
   D=<a scratch directory>; python3 text.py $D      # zh.ans, th.ans
   T=(/nix/store/k111lnbq1vw0k4v4cjhi1iwp5lky3ryn-tmux-3.8/bin/tmux -L puritty-shot -f /dev/null)
   env -u TMUX $T new-session -d -s shot -n work -x 124 -y 39 -c ~/prj/puritty
   $T split-window -h -t shot:work -c ~/prj/puritty "sh -c 'cat $D/zh.ans; exec zsh'"
   $T new-window -d -t shot -n editor; $T new-window -d -t shot -n logs
   $T send-keys -t shot:work.0 "git log --oneline --graph -14" Enter
   $T new-pane -t shot:work -x 56 -y 12 -X 3 -Y 2 -c ~/prj/puritty "sh -c 'cat $D/th.ans; exec zsh'"
   ```

2. Copy `app/puritty.exe` (`app/build-windows.sh`), `hero.toml`,
   `saved.toml`, `hero.ps1` and `stop.ps1` to `C:\Users\yosup\geng-probe\hero`
   and run `hero.ps1` in the desktop session with
   `harness/windows/inSession.ps1 -Script`. It restores the three tabs
   from `saved.toml` (its own `LOCALAPPDATA`, so the user's puritty is not
   touched), centers the window on the desktop at 1640x1139 as before,
   shows each tab once (so none is marked for printing while away), types
   the attach into the first, and saves the window with a 60-pixel margin
   (`hero.png`) and the whole desktop (`desktop.png`, to see that no
   desktop icon is in the margin).

3. `stop.ps1` ends that puritty, by its id; `$T kill-server` ends the
   session.
