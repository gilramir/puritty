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
puritty's own with a master password. PW6's first, second and fourth
questions are still open.
