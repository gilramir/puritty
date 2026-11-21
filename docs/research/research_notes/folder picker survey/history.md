# File managers and pickers through history

Survey notes, 2026-11-20, for the remote folder picker (`../../../sftp.md`
FT32). Hacker News quotes were taken word for word through the HN Algolia
API; primary documents (Inside Macintosh, the NeXTSTEP UI Guidelines, the
ReqTools readme, the Amiga RKM, the `mc` manual, the CHI '96 paper, the
Microsoft KB, COMPUTE!, xtreefanpage, the GNOME lists, OSNews) were fetched
and searched. "(paraphrase)" and "(unverified)" mark what isn't verbatim or
couldn't be confirmed.

## 1. Norton Commander (DOS, 1986, John Socha) and the "orthodox" family

**How it works.** Two full-height panels side by side, a live DOS command
line under them, and a bar labeling F1–F10 that changes with Ctrl and Alt
("a list of commands that are extended on demand by the CTRL and ALT
keys", Wikipedia). Tab switches panels. Tag files, F5 (copy) or F6 (move),
and a dialog opens with **the other panel's folder filled in as the
destination**; Enter confirms. `mc`'s manual says the same of its clone:
"The destination defaults to the directory in the non-selected panel" and
"they always ask you for confirmation first"
(<https://source.midnight-commander.org/man/mc.html>). Ctrl+O hides the
panels, Alt+F1/F2 picks a drive, Alt+letters searches (unverified, from
memory).

**Strengths.**
- "Like most dual-pane file managers, it gets the shortcuts from Norton
  Commander: F5 for copying files, etc."
  (<https://fman.io/blog/dual-pane-file-manager-history/>)
- InfoWorld (1988): "way ahead of the pack"; BYTE (1989): "navigating
  through a crowded hard disk is a breeze" (via Wikipedia, through a
  summarizer).
- "Once you get used to two panes, it's hard to go back."
  (<https://news.ycombinator.com/item?id=22000435>)
- "the two-pane file browser … was a compromise solution that has worked
  for decades." (<https://news.ycombinator.com/item?id=22000628>)
- Muscle memory lasts decades
  (<https://news.ycombinator.com/item?id=7856661>).

**Weaknesses.**
- Two panels on the same folder: the late-80s joke of the programmer who
  erased drive C because both panels showed it
  (<https://tech-in-japan.github.io/articles/466839/index.html>).
- "In a restricted environment like a console only system these two pane
  file managers are very useful … However I rarely use them on a graphical
  environment" (<https://news.ycombinator.com/item?id=45272572>).

### FAR Manager (Eugene Roshal, 1996–)

A faithful NC clone on Windows; far2l runs over SSH.
- "completely keyboard-based … my file operations are 2-3 times more
  effective then of my peers using system file managers with mouse"
  (<https://news.ycombinator.com/item?id=32347830>)
- "Very keyboard-oriented, extremely capable, super fast"
  (<https://news.ycombinator.com/item?id=43101190>)
- "Same key bindings, look and feel as Norton Commander, with lots more
  functionality, but added with considerable thought and restraint."
  (<https://news.ycombinator.com/item?id=37105120>)
- A skill you must already have: "my Linux friend, who insists that
  everything I can do in Far, he can do in Bash quicker … he doesn't know
  Far keyboard shortcuts." (<https://news.ycombinator.com/item?id=37105971>)

### Total Commander (Christian Ghisler, 1993–)

NC in a GUI: two mouse-able panels, a drive bar each, tabs, an F-key row.
Quick search typed into a panel can also **filter** the list
(<https://www.ghisler.com/screenshots_new/en/10.html>). FTP and plugin file
systems.
- "you always move from A to B if organizing/copying/moving. When I see
  people trying to achieve something in explorer, its literally 10x
  slower." (<https://news.ycombinator.com/item?id=32340442>)
- "Once you get used to 2-pane logic, the efficiency boost with anything
  file-related is really huge." (<https://news.ycombinator.com/item?id=21711077>)
- Alt+letter quick search collides with Alt opening menus (ghisler.ch
  forum, search summary): in a terminal, Alt and F-keys may already belong
  to the remote program.

### Midnight Commander (Miguel de Icaza, 1994–)

NC in a Unix terminal; its virtual file systems include sftp:// and sh://,
so a panel can be a remote host. Quick search: "Press C-s or Alt-s … the
selection bar will move to the next file starting with the typed letters";
Alt-o loads the folder in the other panel; C-\ is a directory hotlist
(<https://source.midnight-commander.org/man/mc.html>).
- "I learned to have two parallel windows when moving files … That's why
  Midnight Commander was feeling so great." … "Until the day that I wanted
  to eliminate my usage of function keys."
  (<https://news.ycombinator.com/item?id=47742454>)
- "It is nowhere near as good [as NC]" (<https://news.ycombinator.com/item?id=7856661>)
- "it did not work with Midnight Commander over SSH" (said of a terminal,
  <https://news.ycombinator.com/item?id=19999396>): F-keys and Alt through
  terminals are fragile.

## 2. XTree and XTreeGold (1985–; clone ZTreeWin)

**How it works.** A whole-disk folder tree on top, the highlighted folder's
files in a strip under it, disk statistics at the right, a two-line menu of
single-letter commands at the bottom. Tag files and act on the set;
"Showall" and "Global" flatten every file into one list. A destination is
typed at "to:" or pointed at in the tree with F2 ("nor to point to it with
F2", <https://www.xtreefanpage.org/x40tips.htm>). XTreeGold added a split
(F8).

**Strengths.**
- "I've always liked XTree's tree-structured display … With the keyboard
  always active, you can type a command, use a multitude of hot keys, or
  simply highlight a command with the arrow keys and hit Return." (COMPUTE!,
  May 1992, <https://atarimagazines.com/compute/issue140/110_XTree_Gold_25.php>)
- On the split: "almost a necessity if you want to move files from one
  subdirectory to the other." (same review)
- "had the best user interface of any file manager that I have ever used
  … It already had separate histories for each text field of the user
  interface, in which items could be made persistent."
  (<https://news.ycombinator.com/item?id=33779135>)
- "No file manager has ever approached the productivity I had when using
  XTree Gold for DOS." (<https://news.ycombinator.com/item?id=39077683>)

**Weakness: the whole-disk scan.** "slow; to reenter Xtree2 after you
conclude an application Xtree2 must first reread the disk … I avoid Xtree2
like the plague." (1988, <https://www.xtreefanpage.org/x52revs.htm>).
XTreeGold added "root only" logging to cope.

## 3. Windows 3.x File Manager (WINFILE)

MDI: each window has drive buttons, a tree and files. "Files can be dragged
to any visible folder or to a drive icon … there is NO right-clicking
anywhere in Windows 3.1." (<http://toastytech.com/guis/win31.html>). Copy
or move is decided by which drive you drop on: within a drive it asks "Are
you sure you want to move the selected files…" and "does not give the
option to copy … press and hold down the CTRL key"
(<https://jeffpar.github.io/kbarchive/kb/072/Q72402>).
- "Perhaps File Manager's best new feature is its speed." (COMPUTE!, Oct
  1992, <https://atarimagazines.com/compute/issue145/68_Windows_31.php>)
- "One of Windows' sore spots is file management." (COMPUTE!, Feb 1993,
  <https://www.atarimagazines.com/compute/issue149/S8_How_to_manage_your_f.php>)
- Microsoft's Windows 95 usability work: "Beginning users were bewildered
  by the hierarchical file system. Intermediate users could get around in
  the hierarchy, but often just barely, and usually saved all of their
  documents in the default directory for the program they were using."
  (Kent Sullivan, CHI '96,
  <https://chi1996.acm.org/proceedings/desbrief/Sullivan/kds_txt.html>)

## 4. The Windows 3.x Open/Save dialog and its Windows 95 replacement

3.x: a File Name box with files under it, a Directories list showing the
current folder's ancestors indented above its children, Type and Drives
dropdowns. Windows 95: one list, a "Look in" dropdown for the path, Up and
New Folder.

Sullivan, CHI '96: "beginners and intermediates had a lot of trouble using
the system-provided dialogs for opening and saving files … The problems
stemmed from the fields in the dialog not being in a logical order and
having a complex selection methodology … We tested many variations until we
arrived at the final design." Of an early tree: users were "confused by the
Parent Folder icon. It appeared in every folder and looked like a file, yet
was really a navigation control."

Standardization was the strength: "Windows has two killer features … the
standard print dialog … and the standard file dialog (at least until
Windows 8)." (<https://news.ycombinator.com/item?id=46583806>)

## 5. Classic Mac OS Standard File (System 7; Navigation Services from 8.5)

All from Inside Macintosh: Files
(<https://developer.apple.com/library/archive/documentation/mac/Files/Files-304.html>):
- One list of the current folder, with a popup above it naming the folder:
  "To ascend the directory hierarchy … click the directory pop-up menu …
  To ascend immediately to the top … click the Desktop button."
- Type-to-select: "If the user presses A … selects the first item in the
  list that starts with the letter a … keystrokes in rapid succession form
  a string; keystrokes spaced in time are processed separately."
- Save: "keystrokes are directed to the filename field. If the user presses
  the Tab key … subsequent keystrokes are interpreted as selectors in the
  displayed list."
- Cmd-↑ parent, Cmd-↓ open, Cmd-D Desktop, Cmd-N new folder, Return
  confirms; "When the user uses a keyboard equivalent to select a button in
  the dialog box, the button blinks."

Strengths: the popup is a compact breadcrumb; one click to the top; every
action has a key. "There is 69 pages of documentation of just how to select
a file!" (<https://news.ycombinator.com/item?id=38905700>)

Weaknesses: one folder at a time, click by click down; no recent or
favorite folders, so a utility, Default Folder, sold "Switch quickly among
recently used folders. Easily navigate to your favorite folders … Click on a
Finder window to display its contents"
(<https://stclairsoft.com/DefaultFolderClassic/index.html>). Its descendant
hid path typing: "there is no way to discover that it's possible to
paste/type a path into the standard file selection dialog"
(<https://news.ycombinator.com/item?id=31775565>).

## 6. NeXTSTEP File Viewer and browser (1988–)

Three bands: a **shelf** of dragged-in favorites, an **icon path**, and a
**browser** of Miller columns. The Open and Save panels used the same
browser. NeXTSTEP UI Guidelines, Release 3
(<https://www.mirrorservice.org/sites/www.bitsavers.org/pdf/next/Release_3_Nov93/NeXTSTEP_User_Interface_Guidelines_Release_3_Nov93.pdf>):
"Command-space should be used for file name completion … (In many
applications, the Esc key also performs file name completion.)"; "The Open
panel should come up showing the folder of the most recent main window."

- Apple's HIG: columns suit "a deep data hierarchy in which people tend to
  navigate back and forth frequently between levels"; "Let people resize
  columns." (<https://developer.apple.com/design/human-interface-guidelines/column-views>)
- "NeXTSTEP's File Viewer and Shelf (better than Finder)."
  (<https://news.ycombinator.com/item?id=8746559>)
- "I never got along with the Miller columns in FileViewer / OSX Finder."
  (<https://news.ycombinator.com/item?id=45265334>)
- "I love the Miller columns … I hate the lack of an address bar."
  (<https://news.ycombinator.com/item?id=8741619>)
- Dolphin dropped column view in 2012 as "not used enough."
  (<https://news.ycombinator.com/item?id=48942520>)

## 7. Amiga ASL and ReqTools requesters (AmigaOS 2.0+, 1990–)

ASL: a list, a Drawer (path) field, a File field, an optional Pattern; Open
or Save, Disks, Parent, Cancel. "The contents of an ASL requester data
structure are preserved across calls … allows the requester to remember and
redisplay the user's previous selections." (RKM Libraries ch. 16)

ReqTools (Nico François), from its readme
(<https://discmaster.textfiles.com/view/6410/FreshFishVol9-CD1.bin/useful/util/libs/reqtools/readme>):
"buffers directories in memory"; "can be used as a directory requester
(showing no files)"; "shows all devices (with volume names) and all
assigns"; paths typed in the field: "enter 'Devs:mountlist' … Enter '/'
to go to the parent directory"; "Completely keyboard controlable"; a save
mode that offers to create folders typed that aren't there. Its reason:
"While asl.library was great in look-and-feel I felt it lacked quite a bit
in the power department."

- Replaceable system-wide: "it took very little time before more advanced
  replacements for the standard file requester appeared."
  (<https://news.ycombinator.com/item?id=25727971>)
- Before add-ons the keyboard was weak: "Later there were add-ons like
  Reqtools and MCP which let you use keys more, e.g. Escape to close a
  window, or Return (Enter) to hit OK." (<https://news.ycombinator.com/item?id=48412831>)

## 8. RISC OS drag-to-save (Acorn, 1987–)

The Save box is a name field, OK and a **file icon** you drag into any open
folder window. ROOL's guide: "You won't find any 'Browse for a folder to
save into' windows in RISC OS – you may as well use the Filer to browse to
the folder and then you can just drag and drop into it … If you don't
happen to have a folder window open … you can type the name into the save
window"
(<https://www.riscosopen.org/wiki/documentation/show/Quick%20Guide:%2011.%20Drag%20to%20Save>).

- "drag and drop saving is such a logical, consistent and elegant idea …
  file dialogs for saving are a throw back to the days of single tasking
  GUIs" (<https://www.osnews.com/story/15403/why-we-love-drag-and-drop-on-risc-os/>)
- The window manager "did not pop application windows to the top on first
  click, so you could conveniently do your drag and drop without having the
  target vanishing." (GNOME usability list, 2004,
  <https://lists.gnome.org/archives/usability/2004-September/msg00255.html>)
- "a save dialog is just an icon in a box … I so wish other OSes would copy
  that model." (<https://news.ycombinator.com/item?id=14207692>)
- Against: "Drag and drop is typically an alternative method … not the sole
  method, because it can't be performed by keyboard-bound users." (Matthew
  Thomas, <https://lists.gnome.org/archives/hig/2001-December/msg00034.html>);
  with no folder window open it "takes quite a while … is not accessible
  via keyboard" (the 2004 thread).

## Lessons drawn

1. Default the destination to something useful, show it plainly, and let
   one action accept it (NC's F5 "to:", NeXT's panel at the last window's
   folder, ASL's memory). The NC joke: when source and destination look
   alike, make the destination unmistakable.
2. Typing always works in two forms: jump or filter in the list, and a path
   field with completion (Standard File, mc, TC, NeXT, ReqTools).
3. Drag and keyboard pointing are two ways to one choice, never the only
   one (RISC OS against the GNOME critics). Nothing should move under the
   pointer during a drag.
4. Orientation without a whole-tree scan: a breadcrumb to the root, lazy
   listings one level at a time, cached (XTree's rescan; ReqTools'
   buffers).
5. Shortcuts from a small set that survives a terminal (Enter, Esc, Tab,
   arrows, Backspace, typing); F-keys and Alt+letters only as extras.
   Remembered places beat navigation (Default Folder, NeXT's shelf, mc's
   hotlist, XTree's histories), and the default is what most people take
   (Sullivan).
