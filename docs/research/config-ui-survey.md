# Config UI Survey

Which apps have the best settings screens, what they do well, and what to copy for ours. Our config will live in a TOML file that people can edit by hand, though they shouldn't need to. Compiled November 2026 from vendor docs, design specs, GitHub issues and review sites.

> Few sources study settings UIs directly. Most of this comes from design specs, docs and user reviews, plus how each app is known to behave. Treat it as signal, not data.

## Short answer: who's best

| Rank | App | Why it's the model |
|------|-----|--------------------|
| 1 | **VS Code settings editor** | The best file-backed settings UI overall. Search across everything, a "modified" marker on each setting, reset per setting, "Edit in settings.json" one click away, and the same schema drives both the UI and the file. |
| 2 | **Windows Terminal** | The best among terminals, and the closest to what we're building: a UI for a hand-editable file, profiles that inherit from a Defaults page, a reset button per field, Save/Discard, an "Open JSON file" link. |
| 3 | **Termius** | The best for SSH hosts. A simple form per host, with groups whose settings (jump host, user, key) pass down to every host in the group. Reviewers consistently praise how easy it is. |
| Notable | **Zed** (Dec 2025) | A new settings editor for a file-based app. Its own window, categories on the left, full keyboard navigation, the file stays the source of truth. |
| Notable | **iTerm2** | Very deep and capable. Its search highlights the matching control on the page, but it's dense and a little overwhelming. |
| Avoid | **PuTTY, SecureCRT, MobaXterm** | A deep category tree, many small tabs, no search, and no sign of which values you've changed. SecureCRT is described as "complex due to extensive options." |
| Avoid | **Ghostty, Kitty, Alacritty, WezTerm** | File only, with no UI. Ghostty users have built at least four third-party editors (ghostty-designer, madeye/ghostty-config, zerebos/ghostty-config, a TUI), which shows people want one. |

## What the good ones do

### 1. Search over everything (VS Code, JetBrains, iTerm2, Zed)
- Typing filters the whole settings list, and the category list on the left narrows to categories that have matches (VS Code).
- iTerm2 and macOS System Settings also highlight the matching control on its page. That matters for dense pages.
- Match on synonyms and on the TOML key name, not just the label. JetBrains users complain that search fails when their wording differs from the app's.

### 2. Show what you've changed (VS Code, Windows Terminal)
- Each changed setting gets a marker (VS Code uses a colored bar in the margin).
- A "Modified" filter lists only the settings that differ from the defaults. This is the fastest way to answer "what did I change?"
- A reset button on each setting puts back the default or the inherited value.

### 3. Inheritance you can see (Windows Terminal, Termius, Royal TS, Tabby)
- Windows Terminal: every profile inherits from a **Profiles → Defaults** page. A field you haven't overridden shows the inherited value, and once you change it, a reset button appears.
- Termius / Tabby / Royal TS: folders or groups of SSH hosts carry shared settings (jump host, credentials, user). Termius reviewers call this a standout for managing many servers.
- What to avoid: Royal TS hides inheritance behind "use from parent folder" checkboxes and an "Apply Inheritance" bulk action, and users keep asking for more of it. Make inheritance the default, shown inline, with no extra step.

### 4. Live preview (Windows Terminal, ghostty-designer)
- Windows Terminal shows a preview terminal while you edit and writes changes only when you click Save.
- ghostty-designer previews changes in your running terminals and lets you review a diff before it saves.
- For colors, fonts, cursor and padding, live preview matters more than anything else.

### 5. The file stays the source of truth (all of them)
- Every good app keeps an "Open settings file" link. Windows Terminal puts it at the bottom of the navigation, and VS Code has it on every page.
- The UI and the file describe the same settings, so a change in one shows up in the other. Zed says so explicitly.
- No UI covers every setting at first. Zed and early Windows Terminal both left some settings file-only, and Windows Terminal users complained loudly (issue #9539) when basic defaults couldn't be edited in the UI. Cover the common 90% before launch.

### 6. Keyboard and accessibility
- Zed built tab groups and focus handling so the whole editor works from the keyboard.
- The Windows Terminal spec requires every control to work with a keyboard and a screen reader, and to be localized.

## Saving to TOML without wrecking hand edits

This part is easy to get wrong, and hand-editing users will notice.

- **Edit the document, don't regenerate it.** Load the file into a format-preserving model (`toml_edit` in Rust, `tomlkit`/`tomlrt` in Python, `go-toml-edit` in Go) and change only the keys the user touched. Comments, ordering and blank lines stay as they were.
- **Known issue:** a March 2026 `toml_edit` report says a parse-and-write round trip can drop blank lines and duplicate comments when dotted keys are involved. Add a test that loads and saves an unedited sample config and checks the bytes are identical.
- **Write only what differs from the default.** Setting something back to its default should remove the key, which keeps the file short and readable. VS Code and Windows Terminal both work this way.
- **Keep unknown keys.** Values the UI doesn't recognize (typos, settings from newer versions) should survive a save. Show them in an "Other settings in your file" section instead of dropping them.
- **Pick up outside edits.** Watch the file. If someone edits it by hand while the UI is open, reload, or warn if the UI also has unsaved changes.
- **Back up before writing.** Windows Terminal saves a backup each time it writes. A third-party Windows Terminal tool had a bug where resetting settings also deleted the comments and overwrote the backup.
- **Show errors clearly.** If the hand-edited file doesn't parse, show the line and the error, and open the UI read-only. Don't silently reset to defaults.

## Recommended design for our app

1. **Its own window**, as in Zed and the Windows Terminal spec: a search box at the top and categories on the left (General, Appearance, Profiles, SSH Hosts, Keyboard, Advanced). On the right, one scrolling page per category with clear section headings, not dozens of small tabs as in PuTTY.
2. **One schema drives everything.** Each setting has a key, type, default, label, description, keywords for search, and whether it applies per profile or per host. The UI, TOML validation, docs and search all come from that schema.
3. **Every row looks the same:** label, short description, control, a "modified" marker, and a reset button. Hovering shows the TOML key (e.g. `font.size`) so people can find it in the file.
4. **Inheritance in three layers:** Defaults → Group → Host/Profile. A field you haven't overridden shows the inherited value in gray with "from Defaults" or "from group *prod*". Typing in it creates an override.
5. **Live preview** of a sample terminal while you change appearance settings.
6. **Changes apply as you make them**, with an Undo bar. Windows Terminal uses Save/Discard instead. Pick one model and use it everywhere. My suggestion is to apply at once: it fits live preview and avoids "did I save?" doubts.
7. **"Open config.toml"** is always visible, and saves preserve the file as described above.
8. **A "Modified" filter**, plus an import screen for PuTTY, MobaXterm and `~/.ssh/config` (already on the roadmap in `terminal-survey.md`).

## Sources
- [Zed: How we rebuilt settings](https://zed.dev/blog/settings-ui)
- [Zed configuration docs](https://www.mintlify.com/zed-industries/zed/configuration/settings)
- [Windows Terminal Settings UI spec (#1564)](https://raw.githubusercontent.com/microsoft/terminal/main/doc/specs/%231564%20-%20Settings%20UI/spec.md)
- [Windows Terminal cascading settings spec](https://cdn05042023.gitlink.org.cn/folkslinux/windows-terminal/src/branch/main/doc/specs/%231564%20-%20Settings%20UI/cascading-settings.md)
- [Windows Terminal #9539: base layer in UI](https://github.com/microsoft/terminal/issues/9539)
- [Windows Terminal #1423](https://github.com/microsoft/terminal/issues/1423)
- [Windows Terminal new settings UI (Pureinfotech)](https://pureinfotech.com/windows-terminal-new-settings-ui/)
- [Windows Terminal Preview gets settings UI (Windows Central)](https://windowscentral.com/windows-terminal-preview-gets-settings-ui-first-time)
- [Reset Windows Terminal settings (Pureinfotech)](https://pureinfotech.com/reset-settings-windows-terminal/)
- [TerminalStyles PR #15: reset dropped comments](https://github.com/fcreme/TerminalStyles/pull/15)
- [VS Code 1.27 release notes (settings editor)](https://code.visualstudio.com/updates/v1_27)
- [All-new VS Code settings editor UI (dev.to)](https://dev.to/vscode/all-new-vscode-settings-editor-ui-----3j48)
- [VS Code #167088 modified-elsewhere indicator](https://github.com/microsoft/vscode/issues/167088)
- [VS Code #57370 modified-in-folder](https://github.com/microsoft/vscode/issues/57370)
- [iTerm2 preferences docs](https://iterm2.com/documentation-preferences.html)
- [JetBrains settings dialog](https://jetbrains.com/help/rider/2021.3/Settings_Preferences_Dialog.html)
- [JetBrains settings search request (ReSharper forum)](https://resharper-support.jetbrains.com/hc/en-us/community/posts/206649785/comments/205815955)
- [Termius reviews (G2)](https://www.g2.com/products/termius/reviews)
- [Tabby](https://github.com/Eugeny/tabby)
- [Royal TS folder inheritance](https://docs.royalapps.com/r2021/royalts/reference/organization/folder.html)
- [Royal TS proxy inheritance request](https://community.royalapps.com/t/proxy-inheritance/789)
- [Remote Desktop Manager inheritance](https://docs.devolutions.net/rdm/knowledge-base/knowledge-base-articles/inheritance-in-remote-desktop-manager)
- [MobaXterm vs SecureCRT (appmus)](https://appmus.com/vs/mobaxterm-vs-securecrt)
- [MobaXterm vs SecureCRT (G2)](https://www.g2.com/compare/mobaxterm-vs-securecrt)
- [ghostty-designer](https://github.com/reemus-dev/ghostty-designer/wiki)
- [madeye/ghostty-config](https://github.com/madeye/ghostty-config)
- [zerebos/ghostty-config](https://github.com/zerebos/ghostty-config)
- [Vitruves/ghostty-config (TUI)](https://github.com/Vitruves/ghostty-config/wiki)
- [toml_edit round-trip issue](https://hub.harborframework.com/tasks/abundant/toml-rs__toml-675)
- [tomlrt (Python)](https://pypi.org/project/tomlrt/)
- [go-toml-edit](https://pkg.go.dev/github.com/stricttools/go-toml-edit@v0.5.1)
