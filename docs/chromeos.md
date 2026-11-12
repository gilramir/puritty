# puritty on a Chromebook: discussion points

Gilbert, 2026-11-12: "I want to run puritty on my chrome book. Is it
better to do a javascript version, or should we wait for the wasm backend
in Geng and do a wasm version". His Chromebook is Intel, with ChromeOS's
Linux environment already on. He asked that these be recorded as
discussion points; **nothing is decided and nothing is built.**

## CB1 · The Linux build, in ChromeOS's Linux environment

ChromeOS's Linux environment is a Debian container whose X11 and Wayland
programs open as ChromeOS windows. puritty's Linux build is an X11
program, so on an Intel or AMD Chromebook it should run as it is: local
shells, the built-in ssh client, tmux -CC and settings would all be the
Linux behavior. **Not yet tried.** What would want checking:

- **Fonts.** The container has few; the default font may be missing
  (`apt install fonts-firacode` and the like).
- **Scale.** ChromeOS scales Linux windows; puritty may come out blurry
  or the wrong size until it reads the scale the container reports.
- **Clipboard.** Copy and paste between ChromeOS and the container go
  through ChromeOS's bridge, which may not behave like an X11 desktop's
  selections (PRIMARY in particular).

An ARM Chromebook would need an arm64 build. `ssh-crypto` already gives
way to PuTTY's portable code off x86-64 (`ssh_crypto_config.h`), but
neither the Geng runtime nor puritty has been built for ARM.

## CB2 · A browser version: what blocks it, JS or WASM alike

- **No TCP from a web page.** ssh needs a relay server in between, or
  Chrome's Direct Sockets API, which is only for Isolated Web Apps; IWAs
  are on ChromeOS only, and enterprise-only per a Chromium thread
  ([Direct Sockets](https://developer.chrome.com/docs/iwa/direct-sockets),
  [blink-dev](https://groups.google.com/a/chromium.org/g/blink-dev/c/5cSZjgnJelk/m/K56ic8m_AgAJ)).
- **No local shell.** A page has nothing to run one in: ssh only.
- **The ssh crypto is PuTTY's C.** The JS backend cannot use it; it
  would be rewritten in Geng or replaced with WebCrypto, which has no
  chacha20-poly1305. A WasmGC backend cannot compile C either, so it
  would be a separate linear-memory WASM module beside the program.
- **Drawing and input are C** against X11 and Win32 (`packages/x11`,
  `packages/win32`); a browser needs a canvas layer in their place
  either way.
- **The WASM backend is not begun.** geng-lang `docs/wasm.md`: WasmGC
  only, a fourth backend off Core, deferred to M5.

Between the two, WASM would be the better final target for speed: the
Vt parser and the renderer are the hot code, and on the JS backend they
run at node's speed (geng-lang's bar is native faster than node). But
the blockers above are the same for both, so the backend is not what
decides.

## CB3 · ChromeOS's own Terminal, as a comparison

Gilbert asked whether ChromeOS's Terminal is a WASM program. It is in
part ([libapps](https://chromium.googlesource.com/apps/libapps/)):

- **The terminal is JavaScript**: hterm, Google's JS terminal emulator.
- **Its ssh is OpenSSH compiled from C to WASM** (`ssh_client/`, with
  `wassh/` and `wasi-js-bindings/` on the JS side), linear-memory WASM
  under WASI, earlier Native Client. That is the route PuTTY's crypto
  would take (CB2), not a garbage-collected language backend.
- **It is a system app with access ordinary pages lack**: it opens TCP
  connections and reaches the Linux container. How it reaches the
  container is not checked here.

## CB4 · Where it stands

- A browser version makes sense only where the Linux environment is off,
  as on a Chromebook whose administrator disables it.
- Offered, not done: a Linux x86-64 build as a GitHub draft prerelease
  (with SC26, TM37, TM38), to try in the container.
- Gilbert has made no decision.
