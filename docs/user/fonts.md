# Installing a font for yourself

puritty draws with the fonts installed on **the machine it runs on**. To use
one that isn't there (Fira Code, say), you can install it for yourself alone,
with no administrator rights, and choose it in the settings (Ctrl+Comma,
**Font**) or in `config.toml`:

```toml
[font]
family = "Fira Code"
```

puritty lists **monospace fonts** only, since a terminal's cells all have one
width. Most programming fonts are; a proportional font such as Arial is not
offered.

---

## On Linux

Fonts on Linux are found by **fontconfig**, which looks in a folder of your
own as well as the system's.

1. Get the font's files: `.ttf` or `.otf`. A download is usually a `.zip`;
   for Fira Code, the `ttf` folder inside the release's zip.
2. Copy them into your own font folder, making it if it isn't there:

   ```sh
   mkdir -p ~/.local/share/fonts
   cp FiraCode-*.ttf ~/.local/share/fonts/
   ```

3. Tell fontconfig (it would find them by itself, but other programs may not
   until this is run):

   ```sh
   fc-cache -f ~/.local/share/fonts
   ```

4. Check that it is there, and its name, which is what you put in the
   settings:

   ```sh
   fc-list : family | grep -i fira
   ```

puritty sees the new font without restarting: open the settings and it is in
the list.

**Older systems** also read `~/.fonts`, which works the same way.
`~/.local/share/fonts` is the place on anything from the last ten years
(RHEL8 included).

**What doesn't apply.** Instructions that mention `xset fp`, `mkfontdir` or
the X server's font path are for old programs that ask the X server for
fonts. puritty, like every current program, reads font files itself through
fontconfig, so those steps do nothing for it.

### When puritty runs on another machine

With `ssh -X`, ETX, VNC or any remote X desktop, puritty runs on the remote
Linux machine and only its picture reaches you. **Install the font there**,
in your home directory on that machine, not on the computer in front of you.
If your home directory is shared between machines (NFS), installing it once
covers them all.

---

## On Windows

1. Get the font's `.ttf` or `.otf` files.
2. Right-click them and choose **Install** (for yourself), not "Install for
   all users", which needs an administrator.

puritty sees the new font the next time the settings window opens.

---

## If the font doesn't appear

- **It isn't monospace.** puritty doesn't list it. `fc-list :spacing=mono
  family` on Linux shows the monospace ones fontconfig knows.
- **The name differs.** Use the family as `fc-list` prints it: "Fira Code",
  not "FiraCode-Regular".
- **Only bold or italic was copied.** Copy the regular file too.
