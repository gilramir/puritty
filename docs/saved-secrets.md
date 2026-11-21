# Saved passwords and passphrases: a survey

The Windows product's fourth item (`feature-plan.md`, "The Windows
product"): "Passwords and key passphrases in the Windows credential store,
never in `config.toml`." Gilbert, 2026-11-18: survey it. Sections are PW1,
PW2, and so on; nothing here is built, and the questions in PW6 are
Gilbert's.

## PW1 · What there is today

- **The built-in client asks every time.** `Ssh.Auth` asks its caller for
  a password (`NeedPassword`, the `password` method), for keyboard-
  interactive answers (`NeedResponses`: each prompt's text and whether it
  echoes) and for a key's passphrase, and the window asks in the box over
  the screen (`ssh-client.md` SC20, SC23). Nothing is kept; a reconnect
  (R) asks again.
- **Keys need no password where an agent holds them**: OpenSSH's agent on
  Windows (its keys kept in the registry, protected by DPAPI, across
  reboots) and Pageant (SC19). A user whose key is in an agent is never
  asked for anything.
- **On Linux a host runs OpenSSH by default** (`client` unset), which asks
  in the terminal itself; puritty never sees the password. Only a host
  with `client = "built-in"` asks in puritty's box there.
- **`config.toml` never holds a secret** (ST10), and the diagnostic log
  writes nothing typed (DG6).

## PW2 · What other programs do

General knowledge where not said otherwise:

- **PuTTY** stores no passwords at all, on purpose (its FAQ): keys and
  Pageant are its answer.
- **WinSCP** stores a session's password in its own settings, obfuscated
  rather than encrypted unless a master password is set.
- **Tabby** (an Electron terminal with an ssh client) is the one ssh
  client found that uses Windows' Credential Manager: read in its source
  (`tabby-ssh/src/services/passwordStorage.service.ts`), it keeps an ssh
  password by `ssh@HOST:PORT` and the user, and a key's passphrase,
  through `keytar`, which is Credential Manager on Windows, the Secret
  Service on Linux and the Keychain on macOS; with its own vault turned
  on (a master passphrase) they go there instead. Its issue #9645 reports
  saved passwords gone after a reboot on Windows.
- **MobaXterm 25** keeps them in its registry key, encrypted under a
  master password, now required; before 25.0 each was encrypted with an
  all-zero IV (CVE-2025-0714). Searches found no ssh client but Tabby that
  uses Credential Manager (SecureCRT, Xshell, Bitvise, Royal TS and
  mRemoteNG keep their own encrypted stores).
- **Windows' own Remote Desktop** and **Git Credential Manager** keep
  theirs in Windows' Credential Manager, as `TERMSRV/host` and
  `git:https://host` entries the user can see and remove in Control
  Panel.
- **On Linux**, GNOME's and KDE's programs keep secrets in the Secret
  Service (`org.freedesktop.secrets` on D-Bus: gnome-keyring, KWallet),
  through libsecret; OpenSSH keeps none and leaves passphrases to
  `ssh-agent`.

## PW3 · Windows' Credential Manager, measured (beelink1, 2026-11-18)

`CredWriteW`, `CredReadW` and `CredDeleteW` (`advapi32`, which
`packages/win32` already links), from PowerShell by P/Invoke, a generic
credential (`CRED_TYPE_GENERIC`), its target
`puritty-probe:ssh:gram@example.com:22`, kept on the machine
(`CRED_PERSIST_LOCAL_MACHINE`):

- **In the desktop session**: written, read back with its user name and
  bytes, and listed by `cmdkey /list` as
  `LegacyGeneric:target=puritty-probe:ssh:gram@example.com:22`, which is
  where Control Panel's Credential Manager shows it, under "Generic
  credentials". Deleted; read again, `ERROR_NOT_FOUND` (1168).
- **Its size**: a secret of 2560 bytes was taken, of 2561 refused
  (`RPC_X_BAD_STUB_DATA`, 1783): `CRED_MAX_CREDENTIAL_BLOB_SIZE`. A
  password or passphrase is far below it.
- **Over ssh it does not work**: every call from an ssh logon failed with
  `ERROR_NO_SUCH_LOGON_SESSION` (1312), since a network logon has no
  credential store. puritty runs in the desktop session, so this does not
  touch it; a test of it on beelink1 has to run there (`inSession.ps1`),
  as the probe's second run did. Nothing was left behind.

The secret is protected by DPAPI under the user's logon: another user
cannot read it, but any program running as the same user can, by its
target name, as it can read the browser's saved passwords. Credential
Guard does not cover generic credentials.

## PW4 · Linux's Secret Service, looked at (nene, 2026-11-18)

gnome-keyring is running and owns `org.freedesktop.secrets`; libsecret
(`libsecret-1.so.0`) is installed. The service has two collections,
`login` and `session`; the default (`login`) is **locked** in this
desktop's session, so the first write would make gnome-keyring ask for
its password in a dialog of its own. Not written, so as not to put that
dialog on Gilbert's desktop. A desktop that starts no keyring daemon at
all, as a bare X session or one reached by `ssh -X` may, has no Secret
Service, and a program has to say so and go on asking.

puritty links no D-Bus library today. Speaking the Secret Service means
either libsecret (and its GLib) in the Linux builds, a dependency the
release tarballs would carry, or D-Bus spoken directly over its socket,
as a small client of its own.

## PW5 · How it could work

- **Opt-in, a secret at a time.** The box that asks for a password or a
  passphrase (SC23) gains "Remember" (off by default). With it, the
  secret is written to the store after the server has taken it, never
  before.
- **Used before asking.** When `Ssh.Auth` would ask, a saved secret for
  that key is tried first, once. If the server refuses it, the box asks,
  saying the saved one was refused, with "Remember" on so a new one
  replaces it.
- **What is kept, by what name:**
  - a password for the `password` method, and for keyboard-interactive
    when it asks one prompt that does not echo:
    `puritty:ssh:USER@HOST:PORT`;
  - a key's passphrase: `puritty:key:FINGERPRINT`, so that moving the
    file keeps it;
  - a jump host's are its own, by its own address.
  - Never kept: several prompts at once, or a prompt that echoes, which
    is a one-time code or a question, not a password.
- **Seen and removed**: a host's form says "Password saved" with Forget,
  and the entries stay visible in Credential Manager. Removing a host
  does not remove a secret another host with the same address uses.
- **For a passphrase, the agent instead.** "Add to the agent" can put the
  key in OpenSSH's agent (or Pageant) rather than saving the passphrase.
  That is how OpenSSH means keys to be kept, and the agent's copy is used
  by every program, not only puritty.
- **Cost, roughly**: about 100 lines of C in `packages/win32`
  (read, write, delete) and a `Credentials` module; the store asked
  before the box, and written after the server's answer; the box's
  checkbox and the form's row; the words in English and Korean; app tests
  through a fake store; a beelink1 check run in the session. Linux by the
  Secret Service is as much again, plus the dependency choice of PW4.

## PW6 · For Gilbert

1. **Which secrets**: passwords only, or key passphrases too? *Leaning:*
   both, the passphrase also offered to the agent.
2. **Default**: "Remember" off until checked, or a setting
   (`[ssh] remember_secrets = "ask" | "never"`) that hides the box's
   checkbox where an organization does not want secrets kept? *Leaning:*
   the checkbox, off by default, and the setting with `ask` the default.
3. **Linux**: not at all (OpenSSH asks there by default, and puritty never
   sees it), the Secret Service through libsecret, or D-Bus spoken
   directly? *Leaning:* Windows first; Linux later, D-Bus directly, if a
   built-in-client host on Linux is common enough to want it.
4. **Machine or roaming**: `CRED_PERSIST_LOCAL_MACHINE`, kept on this
   machine, or `CRED_PERSIST_ENTERPRISE`, which follows a domain user's
   roaming profile to other machines? *Leaning:* this machine only.

## PW7 · Decided: Windows' Credential Manager, nothing on Linux (2026-11-18, Dnene63)

*Gilbert, 2026-11-18*, after PW2's answer that Tabby is the one ssh
client found that uses it: "we will use windows credential manager.
Nothing on Linux right now." So PW6's third question is answered (no
Linux store for now; a built-in-client host on Linux goes on asking each
time), and the store on Windows is Credential Manager, not a vault of
puritty's own with a master password. The rest, the same day, as PW6
leaned: **passwords and key passphrases both**, a key's also offered to
the agent; **a "Remember" checkbox, off by default**, with
`remember_secrets = "ask" | "never"` (`ask` the default) to turn saving
off; **this machine only** (`CRED_PERSIST_LOCAL_MACHINE`). And build it.

## PW8 · Built: remembered in Credential Manager (2026-11-18)

- **What is asked carries whom it is for.** `Ssh.Session`'s `Password`
  and `Responses` questions gain `account`, `user@host:port` of the
  connection that asks, so a jump host's question names its own.
- **`Remembered`** (pure, in the app) says which questions may be kept
  and by what name: a password as `puritty:ssh:USER@HOST:PORT`, the user
  beside it; a keyboard-interactive question only when it asks one thing
  that does not echo and says "password", "passwd", "암호" or "비밀번호"
  (a "Verification code:" is never kept); a key's passphrase as
  `puritty:key:PATH`, the file as the client was given it. PW5 named it
  by the key's fingerprint, but the window is told the path, not the
  key; a moved key is asked for again. It also says what the store gets
  at the login (`changesAt`).
- **`SecretStore`**, a module per platform as `SshAgents` is: Windows'
  is `packages/win32`'s new `Credentials` (`CredReadW`, `CredWriteW`,
  `CredDeleteW` on generic credentials, `CRED_PERSIST_LOCAL_MACHINE`,
  in `puritty_win32.c`); Linux's keeps nothing, so nothing is offered.
- **In `Main`**: a question that may be kept is first answered from the
  store (a line says so) when the store holds it and it has not been given
  on this connection. Asked again for it, the answer was refused: the box
  says "The remembered one was refused.", with Remember checked. Else the
  box asks, with "[ ] Remember it in Windows' Credential Manager" and
  Tab to check it (a checkbox since PW10). What the box was told to remember is written when the
  session has logged in (`Started`), never before. A remembered one that
  was refused, and not to be remembered again, is taken away then. A
  question asked again drops what was waiting for its name. R starts
  over.
- **`[connections] remember_secrets`**: `ask` (the default) or `never`,
  on the settings window's Program page, English and Korean.

**Measured**: five tests in the app suite (425): the names; which
keyboard-interactive prompts are kept; never offered on Linux, with
`never`, or for a host key; a checked answer replacing one waiting for
the same name; a refused one forgotten, an unchecked one left alone.
On beelink1 (`harness/windows/secrets/remember.py`, in the desktop
session; nene's test sshd on the LAN, the test key encrypted with
"hunter2"), four runs of `puritty.exe --host test`, each `exit 0`:
the passphrase typed, Tab, Enter, and Credential Manager then held
`puritty:key:…\id_test`; nothing typed, logged in from it; a wrong one
put in its place by `cmdkey`, asked again, the right one typed and
Enter (Remember already checked); nothing typed, logged in from it. The
credential, the files and the scheduled task were removed after.
Passwords use the same path but no test sshd here takes a password (it
would be the machine's own account's), so that path is held by the
tests alone.

**Secrets in Geng's heap** (SC12 question 7, SC16): a remembered
secret is a Geng string only from the read to the answer, as a typed one
already is (SC20), and one to be remembered only until the login; what
lives long is in Credential Manager, not in puritty.

**Not built: "Add to the agent"** for a passphrase (PW7's "plus agent").
OpenSSH's `SSH2_AGENTC_ADD_IDENTITY` carries the key's private numbers,
and SC16 keeps a private key in C, never as Geng bytes, while the agent's
pipe is written from Geng (`Ssh.Agent`, `Os`). So either the message
passes through Geng once, as the session keys do (accepted by SC12
question 7), or C writes it to the pipe itself, a bigger change. Gilbert, 2026-11-18: skipped for now, to
revisit later (`review.md` RV4).

## PW10 · The checkbox as a checkbox (2026-11-19)

Gilbert, 2026-11-19, on beelink1: the box's "[ ] Remember it in
Windows' Credential Manager" was text, and Tab ticked it, which is not
how a checkbox works anywhere else. People click it, or Tab to it and
press Space.

**Now:** the box (`Dialog`) has a real checkbox under the field, drawn as
the settings window draws its controls: a rounded square, filled in the
accent color with a check mark when ticked, and a ring in the accent
color when it has the keys. Its label is beside it.

- **The mouse**: a click on the square or on its label ticks or unticks
  it and gives it the keys (`Dialog.checkAt`). A click anywhere else in
  the window gives the keys back to the field.
- **The keys**: Tab moves the focus from the field to the checkbox and
  back. Space ticks it while it has the focus. Enter answers from
  either, as before, and Esc declines. While the checkbox has the keys,
  the field shows no caret and its border is no longer the accent's, and
  what is typed goes nowhere, as in any dialog.
- The hint loses "Tab: remember".

**Checked:** on beelink1, the box drawn by `remember.py`'s new picture
run: the checkbox and its label under the field, unticked, the field
focused. The keys themselves (Tab, Space, Enter) could not be checked by
the harness this time. Its keys went to Windows Search, whose panel kept
the keyboard although Windows reported puritty's window in front, so the
key runs were stopped, to be tried by hand.

**A correction to PW8's measurement.** `cmdkey` run over ssh works on the
ssh logon's credentials, not the desktop session's that puritty uses
(PW3). So PW8's run 3 ("a wrong one put in its place by `cmdkey`") put
nothing in the desktop's store, and its cleanup removed nothing there:
the test's credential, with "hunter2", stayed in beelink1's Credential
Manager. On 2026-11-19 it made the runs log in unasked. `remember.py` now
runs each `cmdkey` in the desktop session (`on_desktop`) and checks the
store is empty at the start and the end; the credential is gone. It also
sends keys only while puritty is running and reported in front.

