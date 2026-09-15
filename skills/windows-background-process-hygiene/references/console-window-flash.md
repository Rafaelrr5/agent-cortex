# Worked case: a console window flashing on every agent reply

Origin session (Windows 11, an agent runtime plus the Claude Code CLI). Verbatim report:
*"ta abrindo toda hora terminal com python.exe para pelo amor de deus"*.

## 1. Symptom → culprit, in the order that worked

| Step | What it showed |
|---|---|
| List your scheduler's jobs + list `<agent-home>/scripts` | 3 jobs, one every 2 min. Plausible, **wrong**. |
| PowerShell birth-watcher, 150 s (`scripts/window_owners.ps1 -Watch`) | Full spawn tree. Cron children appeared as `uv python … -c "site.addsitedir…" sync-brain.py` → already handled by core. |
| Same capture, filtered for oddities | `cc_stop_hook.py --watch <sid> <token>`, spawned **per Claude Code reply**, plus its own `conhost.exe`. Cadence matched the complaint; the 2-min cron did not. |
| `~/.claude/settings.json` | `hooks.Stop` → `venv/Scripts/python.exe cc_stop_hook.py`. |
| Window-ownership enumeration (100 s) | Exactly one visible `python.exe` window, title = the venv interpreter path, cmdline = `cc_stop_hook.py --watch` → **proof**, not inference. |

The lesson worth keeping: **cadence identifies the trigger**. A long-running Claude Code task
emitting many `Stop` events produced "toda hora", which *looked* like a 2-minute cron.

## 2. Why it was visible (the mechanism)

`cc_stop_hook.py` is a Claude Code `Stop` hook: it must return in milliseconds (the hook blocks
the CLI), so it writes a marker and spawns a **detached** watcher of itself that sleeps 90 s
(debounce), then audits the transcript and delivers a verdict.

```python
flags = 0x00000008 | 0x08000000   # DETACHED_PROCESS | CREATE_NO_WINDOW
subprocess.Popen([sys.executable, SELF, "--watch", sid, token], ..., creationflags=flags)
```

Looks correct. It is not, because `sys.executable` was
`…/<agent-runtime>/venv/Scripts/python.exe`, a **uv trampoline** (`pyvenv.cfg` contains
`uv = 0.11.19`, `home = …/AppData/Roaming/uv/python/cpython-3.11-…`). The stub re-execs the
base `python.exe`; the re-exec does not inherit `CREATE_NO_WINDOW`; being `DETACHED_PROCESS`
there is no console to inherit, so a **new visible console** is allocated. One per reply.

Confirmation in the process capture — the same PID chain appears twice, second hop unflagged:

```
PID=2184  parent=bash    …/venv/Scripts/python.exe  cc_stop_hook.py --watch <sid> <token>
PID=16284 parent=2184    …/uv/python/cpython-3.11/python.exe  cc_stop_hook.py --watch …   <- visible
PID=29772 parent=16284   conhost.exe 0x4                                                   <- the window
```

## 3. The fix, both layers

**Layer A — the spawned child (this is the one that flashes).** Resolve the base `pythonw.exe`
from `pyvenv.cfg` instead of `sys.executable` (helper in the SKILL.md), and add
`creationflags=NO_WINDOW` to every `subprocess.run` inside the watcher: the `git status` /
`git log` probes (`shell=True`), the review invocation, and the notifier `send`. Guard
`sys.stdin is not None` before reading, since the script may now run under `pythonw`.

Verification (fresh trigger, real payload piped in):

```bash
echo '{"session_id":"TESTE","transcript_path":"","cwd":"C:\\Users\\me"}' | \
  "…/venv/Scripts/python.exe" cc_stop_hook.py
# watcher now runs as  …/uv/python/cpython-3.11/pythonw.exe cc_stop_hook.py --watch …
# conhost children of that PID: 0
# 100 s of window-ownership polling: no new visible window
```

**Layer B — the entrypoint: leave it alone.** Pointing `settings.json` at `pythonw.exe` was
tried and **reverted**: the hook ran (rc=0) but the piped event JSON arrived **empty**
(`keys=[]` in the hook log, i.e. `session_id`/`transcript_path` lost). The entrypoint is
launched by Claude Code inside its own console, so it never flashed anyway. Console
interpreter for stdin-reading entrypoints; windowless interpreter for detached children.

**Leftovers.** The watcher spawned *before* the patch keeps its window for its whole 90 s +
review lifetime. `ShowWindow(h, 0)` (snippet in SKILL.md) hides it while still letting it
deliver its Telegram verdict — better than `taskkill`.

No restart needed: Claude Code reads the hook script from disk on every `Stop`.

## 4. Spawn-source inventory for an agent runtime + Claude Code box

Check in this order, matching cadence to symptom:

1. **Claude Code hooks** — `~/.claude/settings.json` → `hooks.{Stop,PostToolUse,…}`. Fires per
   reply / per tool call. Most likely offender because it is hand-written.
2. **Agent-runtime scheduler** — list your scheduler's jobs + inspect `<agent-home>/scripts/*.py`.
   In this session the runtime already spawned these windowless by resolving the base
   `pythonw.exe` and applying `CREATE_NO_WINDOW`; verify those choices in your own runtime.
   A **hand-rolled** `Popen` inside one of those scripts is still yours to fix.
3. **Gateway / desktop serve / kernel runners** — long-lived, spawned once; they are not the
   source of a *repeating* flash.
4. **Startup-folder login items** — once per boot only.
5. **Windows Task Scheduler** — check `Get-ScheduledTask` if nothing above matches the cadence.

## 5. Searching a huge tree for the spawn site

While hunting the `Popen`, `grep -rn --include=*.py` across the whole agent-runtime source tree
**timed out at 180 s**. Two habits that worked instead:

- Scope `search_files` to a **subdirectory** (`.../cron`, `.../claude-watch`) rather than the
  repo root; it returns in seconds.
- Keep `search_files` patterns to plain word alternation — `CREATE_NO_WINDOW|creationflags|Popen`.
  Regex escapes get mangled on the way to ripgrep (`subprocess\.` arrived as `subprocess/.`,
  `run\(` as `run/(`) and the call fails with *"regex parse error: unclosed group"*. Drop the
  escapes and the parens.
