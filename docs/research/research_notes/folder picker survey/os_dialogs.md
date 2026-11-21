# Today's OS file and folder pickers

Survey notes, 2026-11-20, for the remote folder picker (`../../../sftp.md`
FT32). Each claim has its source. "(unverified)" means it comes from memory
or a search summary whose page was not opened. Screenshots were checked
when the survey was made and are not kept here.

## 1. Windows IFileDialog (Vista on; folder mode is FOS_PICKFOLDERS)

**How it works.**
- A breadcrumb address bar on top that turns into a text field when clicked,
  a search box, a navigation pane on the left (Quick access or Home, This PC,
  Network).
- An Explorer list or grid; a "File name:" or "Folder:" box and the
  Open/Save/"Select Folder" buttons at the bottom.
- Folder mode is the same dialog showing only folders. "Select Folder"
  returns the selected subfolder, or the current folder if none is selected
  (unverified).
- It remembers the last folder and size per application, or per dialog with
  `SetClientGuid`: "the dialog will open in the last folder a user opened or
  the last folder they used to save an item". Microsoft tells developers
  not to force a folder with `SetFolder`: "it is not a good or expected user
  experience".
  <https://learn.microsoft.com/en-us/windows/win32/shell/common-file-dialog>

**Strengths.**
- A path pasted into the File name box and Enter goes there (search summary
  of <https://community.graphisoft.com/t5/Archicad-C-API/Browsing-File-Path/m-p/328822>).
- Breadcrumb and editable address bar behave as in Explorer.
- Per-dialog memory exists because before Vista "a video editing
  application would present the same folder in the Render As dialog as it
  would in the Import Media dialog" (the doc above).
- wxWidgets moved to it because it "shows a much more user-friendly dialog
  than the one used by SHBrowseForFolder()" (search summary).

**Weaknesses.**
- No files in folder mode: "Once you opt for FOS_PICKFOLDERS then you can't
  see files in the dialog, only folders"
  (<https://kiwix.lema.org/stackoverflow.com_en_all_2023-11/questions/54694027/c-select-folder-include-files>);
  the folder dialog "doesn't show files on Windows, though it does on Mac"
  (<https://community.adobe.com/t5/photoshop-ecosystem-discussions/windows-file-dialog-show-files/td-p/14391765>).
  Users lose the cue "is this the folder that holds my stuff?"
- Virtual folders that can't be chosen still show, because they
  "potentially lead to pickable items", and the user gets "You can't save
  here" (Raymond Chen,
  <https://devblogs.microsoft.com/oldnewthing/20191021-00/?p=103014>,
  <https://devblogs.microsoft.com/oldnewthing/20231011-00/?p=108884>).
- The wrong starting folder: Windows 11 with OneDrive backup starts in
  OneDrive; "Win11 F12 save-as dialog doesn't default to last accessed
  folder"
  (<https://techcommunity.microsoft.com/t5/windows-11/win11-f12-save-as-dialog-doesn-t-default-to-last-accessed-folder/m-p/4546197>);
  "Windows 11 will not save the open dialog position… really frustrating"
  (<https://techcommunity.microsoft.com/discussions/windowsinsiderprogram/windows-11-will-not-save-the-open-dialog-position-its-really-frustrating/4402867/replies/4402906>).

## 2. SHBrowseForFolder, the "Browse For Folder" tree

**How it works.** A modal box: a caption, one tree from Desktop or Computer,
optionally "Make New Folder", OK and Cancel. Drill down only; an edit box
(BIF_EDITBOX) exists but is rarely turned on.

Microsoft
(<https://learn.microsoft.com/en-us/windows/win32/api/shlobj_core/nf-shlobj_core-shbrowseforfolderw>):
"For Windows Vista or later, it is recommended that you use IFileDialog
with the FOS_PICKFOLDERS option"; "The older style is displayed by default
and is not resizable." .NET's FolderBrowserDialog moved over only in .NET
Core 3.1.

**Weaknesses.**
- No breadcrumb, no favorites, nowhere to paste a path. UiPath forum, "The
  way the File/Folder Path component prompts for folder is terrible": no
  Quick Access and "nowhere to type in even the beginning of the path"
  (<https://forum.uipath.com/t/the-way-the-file-folder-path-component-prompts-for-folder-is-terrible/390938>,
  search summary).
- Too small: XBrowseForFolder sells a tree "70% larger"
  (<https://www.codeproject.com/Articles/5063/XBrowseForFolder>, search
  summary); XnView users asked to "make 'browse for folder' resizeable"
  (<https://newsgroup.xnview.com/viewtopic.php?p=68326>).
- "looks very old and is very difficult to use"
  (<https://www.nuget.org/packages/FolderBrowserEx>).
- Unreachable network drives clutter the tree with red-X entries
  (screenshot at <https://discourse.mcneel.com/t/select-folder-window-style-change-c/67439>).

## 3. macOS NSOpenPanel and NSSavePanel

**How it works.**
- The Finder sidebar (Favorites, iCloud, Locations, Tags); back/forward,
  icon/list/column/gallery views, a path popup, search.
- With `canChooseDirectories`, files that can't be chosen are dimmed
  (Apple confirms dimming for filtered files; for folder mode, unverified).
- Save opens as a compact sheet ("Save As:" and a "Where:" popup of recent
  and favorite folders); a disclosure arrow expands it.

**Fast paths users praise.**
- Cmd+Shift+G, Go to Folder, with completion: matching folders "appear as
  you type" (<https://support.apple.com/en-au/guide/mac-help/mchlp1236>).
- Typing "/" or "~" opens that field
  (<https://www.macworld.com/article/628623/how-to-jump-to-folder-location-mac.html>).
- Dragging a folder from Finder onto the panel goes there (search summary of
  <https://macmost.com/10-ways-to-quickly-get-to-folders-when-saving-files>).
- Cmd+Up/Down, arrows across columns, Space for Quick Look, Cmd+Shift+D/O/L
  for Desktop/Documents/Downloads
  (<https://www.intego.com/mac-security-blog/master-the-macos-open-and-save-dialogs/>).
- Column view for deep trees: "particularly useful because of the large
  preview" (Intego).

**Weaknesses.**
- Recent regressions (<https://mjtsai.com/blog/2022/04/04/searching-in-open-save-panels/>):
  search "sometimes it works, but sometimes it takes a long time to find no
  results"; "The recent list does not include most of the folders that I've
  recently chosen"; "macOS stopped remembering the width of the open/save
  panel sidebar"; "macOS 11 and later keep losing all my favorites"; a
  commenter: "Absolutely maddening."
- Pasting a path doesn't navigate: "no provision for pasting a file or
  folder path from the clipboard and act on that path"
  (<https://discussions.apple.com/thread/254893349>); a pasted path becomes
  the file name (<https://developer.blender.org/T71346>, search summary).
- The collapsed Save sheet hides where the file goes; the setting that kept
  it expanded was removed after Mojave (Mac Format, search summary).

## 4. GTK 3 and 4 (GNOME)

**How it works.** Header bar with Cancel, search, Open/Select; places
sidebar (Recent, Home, XDG folders, bookmarks, mounts); a path bar of
buttons above a list. GTK 4.10 added a grid. The text entry is behind
Ctrl+L ("/" and "~" also open it, unverified for every version).

**Strengths.** Clean, a good sidebar, Ctrl+L completes. The grid shipped
after 18 years: "It only took us 18 years!"
(<https://blog.gtk.org/2022/12/15/a-grid-for-the-file-chooser/>; Bugzilla
141154, April 2004).

**Weaknesses.**
- Typing starts a search, not a name or a path: "when you start typing,
  instead of naming the file it just start searching"
  (<https://gitlab.gnome.org/GNOME/gtk/-/issues/853>; also #139, #1272;
  GTK4 #3371: type-ahead "steals input from location entry").
- The path entry is hidden. GTK #2443 (2020, open): "the only way to show
  the address bar is 'Ctrl+L', after reading many similarly frustrated
  posts… removing/hiding the address bar is very counter intuitive"
  (<https://gitlab.gnome.org/GNOME/gtk/-/issues/2443>). Arch forum: "There
  is no way to type in a path"; "It's the worst designed UX I've seen
  probably ever"; "clicked everything trying to get that to appear"
  (<https://bbs.archlinux.org/viewtopic.php?id=231697>). Asked again on
  GNOME Discourse, January 2025
  (<https://discourse.gnome.org/t/how-to-suggest-an-address-bar-for-file-browsing-dialogues-in-gnome/26296>).
- **Enter in a typed path confirms instead of navigating** (folder mode):
  "Hitting enter after typing the path closes the dialog and selects the
  path you just typed… a disconnect between the path entry and the… list"
  (<https://gitlab.gnome.org/GNOME/gtk/-/issues/268>). The bug most
  relevant to a destination picker.
- "Sometimes you have to single click, sometimes you have to double click"
  (Arch thread).
- Thumbnails missing unless Nautilus made them first
  (<https://gitlab.gnome.org/GNOME/gtk/-/issues/5663>); size fixed (#5590).
- "the file picker is one of the reasons I left GTK behind for KDE/Qt"
  (GamingOnLinux comment, search summary).

## 5. KDE KFileWidget (Dolphin-like)

**How it works** (<https://docs.kde.org/stable_kf6/en/khelpcenter/fundamentals/files.html>):
a Places panel "shared with Dolphin" (F9); a breadcrumb where "each folder
name in the path… is a button" and ">" opens a subfolder menu, turned into
a text path by a click; a Name field that takes a name or a path, with
completion; back/forward/up/reload, zoom, preview; F8 or Alt+. for hidden
files; the last 10 filters remembered.

**Strengths.** Users prefer it to GTK's for the visible path, thumbnails and
settings: "the GTK3 file picker is **** – when compared to the native
Plasma file picker" (Phoronix forum, search summary). People force it into
GTK apps through the portal.

**Weaknesses.**
- Behind Dolphin: no grouping, two panels only, "toolbar is
  uncustomisable"; a KIO developer: "Grouping is very unlikely… we agree
  that we can make them more similar"; Nate Graham: "Re-unifying code is
  always ten times more difficult than forking it"
  (<https://discuss.kde.org/t/why-is-the-kde-file-picker-so-inferior-to-dolphin-and-can-this-be-remediated/13109>).
- Users can't tell which dialog they got (<https://bugs.kde.org/show_bug.cgi?id=504342>).
- "forgets last used directory when it was a kio-fuse mount path"
  (<https://bugs.kde.org/show_bug.cgi?id=452968>).

## 6. Qt's own dialog (QFileDialog, DontUseNativeDialog)

An editable "Look in:" path combo, back/forward/up/new-folder/view
buttons, a small sidebar, list or detail view, "File name:" and "Files of
type:". Typing a path in File name completes it. Used where no platform
plugin is (AppImages, Krita).

- Strengths: the path is always visible and editable; predictable; the same
  everywhere.
- Weaknesses: "looks way out of place (*UGLY* in a hugely distracting way)"
  (<https://riverbankcomputing.com/pipermail/pyqt/2016-August/037912.html>);
  no grid, a tiny sidebar, no breadcrumb; "opens a basic qt file picker"
  filed as a Krita bug (<https://bugs.kde.org/show_bug.cgi?id=506926>).

## 7. xdg-desktop-portal FileChooser

A D-Bus API: the app asks and the desktop's backend draws the dialog (GTK,
KDE, and since GNOME 47 Nautilus itself, "the same clickable address bar as
Nautilus by default"; the reason, "visual and behavioral consistency with a
single codebase",
<https://discourse.gnome.org/t/planning-filechooser-portal-implementation-with-nautilus/20335>).
The app gets a document-portal path (`/run/user/UID/doc/...`).

- Strength: every toolkit gets the desktop's picker.
- Weaknesses: remembers the wrong folder ("keeps using /run/user/<UID>/...
  as the remembered path", Mozilla bug 1785158; "no longer remembers
  last-used directory… since 1.21.0",
  <https://bugzilla.redhat.com/show_bug.cgi?id=2435752>, search summary;
  on the asymmetry: "handing path B back in will not cause the chooser to
  navigate to path A",
  <https://bugs.launchpad.net/ubuntu/+source/xdg-desktop-portal/+bug/2020655/comments/32>);
  drag-and-drop selection gone in GNOME 49's Nautilus chooser
  (<https://discourse.gnome.org/t/select-file-by-drag-and-drop-in-nautilus-file-picker-chooser/33033>,
  search summary); the wrong backend picked.

## Lessons drawn

1. Typing a path must always work, and Enter in it navigates, never
   confirms (GTK #268). Paste works; completion as Cmd+Shift+G and KDE do.
2. Typing in the list never goes somewhere surprising: no search that takes
   focus (GTK #853, #3371).
3. Say which folder "Choose" picks; Windows' "Select Folder" and the Mac
   panel are ambiguous between the highlighted and the current folder.
4. Show files in a folder picker, dimmed; they also warn of name collisions.
5. Places are the fast path: home, the shell's folder, recent destinations,
   bookmarks, the root; kept, never lost (macOS's complaints).
6. Remember the last folder per purpose and host; never store a path the
   user didn't choose (Microsoft's ClientGuid; the portal and KIO bugs).
7. Mouse and keyboard to the same actions, one click rule, a generous,
   resizable size (SHBrowseForFolder's signature complaint); a folder
   dropped on the picker is a choice (macOS).
8. No collapsed mode that hides the destination, no drill-only tree.
