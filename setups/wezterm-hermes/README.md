# WezTerm + Hermes: reopen each tab's own conversation

Opening WezTerm starts Hermes. Opening a new tab starts a fresh Hermes session.
After closing and reopening WezTerm normally, the saved windows and tabs reopen;
each Hermes tab resumes its own conversation instead of every tab grabbing the
same globally latest session. Git Bash and PowerShell entries remain available
in the launch menu.

This is an edited copy of my daily Windows configuration, not an export of my
sessions. The executable and profile paths are configurable. The repository
contains no live snapshot, conversation IDs, credentials, transcripts or database.
Original configuration and public adaptation: Rafael Rocha Ribeiro + Hermes.
The repository's MIT license covers these files. WezTerm and Hermes Agent are
separate upstream projects and are not bundled.

## Install without replacing your setup blindly

1. Install [WezTerm](https://wezterm.org/installation.html) and
   [Hermes Agent](https://hermes-agent.nousresearch.com/docs/getting-started/installation).
   Complete `hermes setup` and verify `hermes` opens normally first.
2. Back up your existing `~/.wezterm.lua`. Review [wezterm.lua](wezterm.lua), then
   copy its contents into that file, or merge the settings into your own config.
   Multiple handlers for the same startup event can spawn duplicate windows;
   do not layer this over an existing restore handler unchanged.
3. Set `hermes` at the top of the Lua file to your executable if WezTerm cannot
   resolve `hermes` from PATH. For example, use an absolute executable path with
   forward slashes. Keep it as one argv element, even when the path has spaces.
4. Set `hermes_home` to the directory containing your active Hermes `config.yaml`
   and `state.db`. `hermes config path` identifies that config file. The default
   uses inherited `HERMES_HOME`, otherwise `~/.hermes`; a custom Windows install
   or named profile may use a different directory. This directory must exist.
   The same home is explicitly passed to every spawned child.
5. Review the optional Git Bash path. PowerShell uses `powershell.exe` from PATH.
   Restart WezTerm normally to use the startup restore handler.

No installer runs, no credentials are copied, and this configuration does not
register a Windows login/startup task. "Automatic" means that opening WezTerm or
creating a tab launches Hermes directly.

## What is saved

The `update-status` event samples the tabs every 1,000 ms. It saves a private
`wezterm-tabs.json` under the selected Hermes home, grouped by window and tab
order. It records only shell kind and, when available, the Hermes session ID.
An unchanged snapshot is not rewritten; when no windows remain, the last
nonempty snapshot is retained.

Hermes itself supplies `terminal-sessions/wezterm_pane-<id>` breadcrumbs. This Lua
file reads those records; it does not patch Hermes, write its database or invent
session IDs. On reopening, it passes the recorded ID as a separate argument:

```text
hermes --resume <saved-session-id>
```

Pane IDs restart when WezTerm restarts. A breadcrumb more than five seconds older
than the first observation of a pane is rejected, so an old ID cannot silently
replace that pane's saved conversation. The saved ID remains the fallback until
Hermes writes a fresh breadcrumb, including after `/new` or compression changes
the live conversation ID.

Use `session.terminal_continue` enabled in Hermes; otherwise it does not write
breadcrumbs and this config can reopen Hermes tabs but cannot discover new
conversation IDs. `hermes -c` is useful in the same terminal, but restoring a
closed application requires the recorded session ID because pane IDs are reused.
An explicit WezTerm startup command bypasses restoration.

## Verification you can run without opening a terminal window

The config itself has no Python dependency. The optional test harness uses Lupa
to execute the actual Lua file, with real temporary files and a stubbed WezTerm
API. Use a separate virtual environment rather than installing into Hermes:

```bash
uv venv .venv-test
uv pip install --python .venv-test/Scripts/python.exe lupa==2.8
.venv-test/Scripts/python.exe -I -B test_restore.py
```

Run these commands from this directory on Windows. On a POSIX test host, use
`.venv-test/bin/python`; that does not establish POSIX GUI support.

Observed: 13 tests passed on Windows, with Python 3.12.10 and Lupa 2.8. They cover
fresh launch, window/tab order, resume argv boundaries, file save/reload, changed
session IDs, a closed tab, stale breadcrumbs, malformed snapshots, explicit
commands, active-pane selection, shutdown retention, shell detection, both JSON
API variants, separate profile snapshots, and write-error logging/recovery.

[probe_native.py](probe_native.py) also exercises the real Hermes breadcrumb
writer in a temporary `HERMES_HOME`, then feeds its output through the Lua save
and restart path. Run it with the Python from your Hermes installation:

```text
.venv-test/Scripts/python.exe -B probe_native.py --python <Hermes-Python-executable> --source <Hermes-source-checkout>
```

The source argument is optional when that Python can import Hermes without it.
Observed: the native writer produced a breadcrumb that the Lua snapshot read,
and reopening selected `hermes --resume demo-native`. The WezTerm process API
was stubbed in this probe too; no GUI, model request or agent conversation ran.

## Limits and recovery

- Windows is the intended host. POSIX Hermes may identify the terminal by tty
  before `WEZTERM_PANE`; this config does not implement that lookup.
- GUI close/reopen was not exercised for the public copy. Headless tests verify
  Lua and file behavior, not actual window scheduling or process launch.
- This is conversation restoration, not live-process persistence. It does not
  preserve running tools, scrollback, pane splits, working directories, window
  geometry or the selected tab. One active pane per tab is recorded.
- A single WezTerm GUI/mux instance should own a profile's snapshot. Independent
  instances sharing that file can overwrite one another. Changing profiles
  within an existing pane is not tracked; configure separate homes/instances.
- Sampling can miss changes made just before shutdown. A tab closed before the
  next successful sample may return; a session not yet breadcrumbed starts fresh.
- Snapshot writes use a direct file write, not an atomic replacement. A crash
  during writing can lose the snapshot. Malformed input starts one fresh tab.
- Deleted conversations can make Hermes refuse the recorded resume ID. This
  config does not inspect the session database. Remove the stale entry, or move
  aside `wezterm-tabs.json` to start fresh; your Hermes history stays intact.
- Foreground-process detection is intentionally coarse: Python counts as Hermes
  and an unknown process falls back to a fresh Hermes tab. Shells with inherited
  Hermes breadcrumbs can be classified as Hermes. It is not a process supervisor.
- Config hot reload retains the original setup's permissive handling of existing
  panes; the age guard is strongest after normal application startup.

Keep `wezterm-tabs.json` and `terminal-sessions/` private. The IDs are not access
credentials, but they identify your work. This repo publishes only code and tests.

Sources: [Hermes session behavior](https://hermes-agent.nousresearch.com/docs/user-guide/sessions),
[WezTerm gui-startup](https://wezterm.org/config/lua/gui-events/gui-startup.html),
and [WezTerm update-status](https://wezterm.org/config/lua/window-events/update-status.html).
