---
name: windows-background-process-hygiene
description: "Console flashing on Windows? Spawn/diagnose hidden procs."
version: 1.0.0
author: Rafael Rocha Ribeiro (github.com/Rafaelrr5)
license: MIT
platforms: [windows]
metadata:
  agent:
    tags: [windows, subprocess, console-window, pythonw, uv, venv, cron, hooks, daemons]
    related_skills: [windows-performance-tuning]
---

# Windows background process hygiene

Spawning helpers, watchers, hooks and daemons on Windows so they **never show a window**, and
finding the culprit when something already does.

## When to Use

- A console / `python.exe` window **flashes or pops up repeatedly** on the user's screen and
  nobody knows who opens it. (Frustration form: *"ta abrindo toda hora terminal com python.exe,
  para pelo amor de deus"* — treat this as a bug to root-cause, not a cosmetic annoyance.)
- You are about to write anything that spawns a background child on Windows: a cron script, an
  agent watcher, a notifier, a file-watcher, a wrapper.
- A window that should be hidden appeared anyway even though `CREATE_NO_WINDOW` was passed.
- A previously silent background job started showing itself after an interpreter/venv change.

## The one principle

**`CREATE_NO_WINDOW` is not inherited across a re-exec, and the process you can see is rarely
the process that opened the window.**

Everything below follows from those two facts. Do not tune flags blindly — first prove *which
PID owns a visible window*, then fix the spawn chain end to end.

## Root cause: the uv-venv trampoline

A `venv/Scripts/python.exe` created by **uv** is a launcher stub that **re-executes the base
interpreter** (`~/AppData/Roaming/uv/python/cpython-*/python.exe`). That second process is a
fresh `CreateProcess` that does **not** carry your `CREATE_NO_WINDOW`.

On its own that is invisible, because the child inherits the parent's console. It becomes a
**visible window** when combined with `DETACHED_PROCESS` (0x00000008): a detached child has no
console to inherit, so the console-mode re-exec **allocates a brand-new, visible one**. Every
spawn = one window on screen.

For scheduled Python jobs on Windows, spawn the base `pythonw.exe` resolved from
`pyvenv.cfg` and pass `creationflags=CREATE_NO_WINDOW` on every child spawn. If using the
base `python.exe` instead, keep `CREATE_NO_WINDOW` and avoid `DETACHED_PROCESS`; bypass
the venv trampoline so a re-exec cannot lose the flag. The same trap applies to any
hand-written script.

## Fix recipe

### 1. Resolve a windowless interpreter instead of `sys.executable`

`pythonw.exe` never allocates a console. Read the base interpreter from the venv's
`pyvenv.cfg` (`home = ...`) so you bypass the trampoline as well:

```python
NO_WINDOW = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW

def _windowless_python():
    if os.name != "nt":
        return sys.executable
    exe = os.path.abspath(sys.executable)
    cands = []
    try:
        cfg = os.path.join(os.path.dirname(os.path.dirname(exe)), "pyvenv.cfg")
        with open(cfg, encoding="utf-8") as f:
            for line in f:
                if line.split("=")[0].strip().lower() == "home":
                    home = line.split("=", 1)[1].strip()
                    cands += [os.path.join(home, "pythonw.exe"),
                              os.path.join(home, "python.exe")]
    except OSError:
        pass
    cands.append(os.path.join(os.path.dirname(exe), "pythonw.exe"))
    return next((c for c in cands if os.path.exists(c)), exe)
```

Only safe when the child is **stdlib-only** or the venv's `site-packages` is put back on the
path (`PYTHONPATH` / `site.addsitedir`) — the base interpreter does not see venv packages.

### 2. Flag *every* `subprocess` call, including the ones inside the child

One un-flagged `subprocess.run` deep in the watcher (a `git status`, a CLI notifier, a
`taskkill`) is one window. Pass `creationflags=NO_WINDOW` on all of them, and keep
`shell=True` calls in scope too.

### 3. Fix only the layer that actually flashes

A script invoked **by another tool that already owns a console** (a hook fired by a CLI, a
build step) does not flash — the *detached child it spawns* does. Minimal correct fix =
change the child spawn, leave the entrypoint alone. See the stdin pitfall for why forcing
`pythonw` on the entrypoint can be actively harmful.

## Diagnose: who actually owns the window

**Counting processes proves nothing** — most console-mode Python processes have no window at
all. Enumerate window ownership per PID instead:

```powershell
Get-Process | Where-Object { $_.MainWindowHandle -ne 0 -and $_.MainWindowTitle } |
  ForEach-Object { "$($_.Id) $($_.ProcessName) '$($_.MainWindowTitle)' " +
    (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)").CommandLine }
```

Run `scripts/window_owners.ps1` for that plus a **watch mode** that logs newly-born
processes with parent PID and full command line — the spawn chain (`<agent-host>.exe` → `python` →
`uv python` → `conhost`) is what identifies the culprit.

**Match cadence to trigger before reading any code.** A flash every ~2 min points at a cron
tick; a flash on every agent reply points at a per-response hook; a flash per file save points
at a watcher. Guessing the wrong source burns the whole session (this skill's origin session
started on the cron scheduler and the answer was a Claude Code `Stop` hook).

## Hide an already-running offender without killing it

Patching the script does **not** retro-fix watchers already sleeping in memory. They keep
their window until they exit. Hide the window and let the process finish its job:

```powershell
Add-Type -Namespace W -Name N -MemberDefinition '[DllImport("user32.dll")] public static extern bool ShowWindow(System.IntPtr h, int c);'
Get-Process python,pythonw -EA SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 } |
  Where-Object { (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)").CommandLine -like '*<your-script>*' } |
  ForEach-Object { [W.N]::ShowWindow($_.MainWindowHandle, 0) }
```

Prefer this to `taskkill` when the process still owes the user a delivery (a review, a
notification, an upload).

## Pitfalls

1. **`pythonw.exe` has no stdin/stdout/stderr.** `sys.stdin` is `None` (guard before
   `.read()`), and prints go nowhere — log to a file. **A piped payload can arrive empty**: a
   hook entrypoint switched to `pythonw` ran fine (rc=0) but received an *empty* event JSON.
   Keep the console interpreter for anything that **reads stdin**; make only the detached
   child windowless.
2. **`CREATE_NO_WINDOW` alone is not enough** whenever a launcher/trampoline re-execs, and
   `DETACHED_PROCESS` is what turns that into a visible window. Fix the interpreter, not just
   the flag.
3. **Fixing the source does not fix running instances.** Verify with a *fresh* trigger, and
   hide the leftovers.
4. **Verify by triggering, not by reading the diff.** Fire the real entrypoint the way the real
   caller does (pipe the same payload), then re-check window ownership and
   `conhost.exe`-with-that-parent count (expect 0).
5. **`wmic` is gone on recent Windows 11** — use `Get-CimInstance`.
6. **Don't blame the scheduler by default.** Cron/gateway spawns in an agent runtime may
   already be windowless; verify the spawn chain before blaming the scheduler. Hand-written
   hooks and helper scripts are the usual offenders.

## Support files

- `references/console-window-flash.md` — the full worked case (Claude Code `Stop` hook watcher
  flashing on every reply): symptom→culprit path, the exact two-layer fix, spawn-source
  inventory for an agent-runtime + Claude Code box, and how to search a huge tree without timing out.
- `scripts/window_owners.ps1` — read-only. Lists PIDs owning visible windows with command
  lines; `-Watch <seconds>` logs newly-spawned processes with parent and command line.
