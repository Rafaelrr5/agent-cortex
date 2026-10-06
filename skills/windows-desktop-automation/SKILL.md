---
name: windows-desktop-automation
description: "Code spawning CLIs/SendKeys on Windows? Exact argv, focus."
version: 1.0.0
author: Rafael with AI assistance
license: MIT
platforms: [windows]
---

# Windows desktop automation from code

For code (Node, Python, etc.) that opens a CLI in a new PowerShell window, passes it
arbitrary text (prompts, paths), or types into an existing window with clipboard +
`WScript.Shell.SendKeys`. Typical bugs: prompts that arrive split or empty, flags that eat
the positional argument, and keystrokes that land in the wrong window when several jobs
run together.

Hidden-window and console-flash problems belong to a separate hidden-process diagnostic workflow.

## When to Use

- Prompts or paths reach a spawned CLI split, missing quotes, or reported as "no prompt
  provided", especially when the text contains `"` or when an attachment/extra-dir flag
  is present.
- A scheduler or bot types into existing windows, and text lands in the wrong window when
  several targets, or several jobs at the same minute, are handled.
- You're writing a new tool that generates .ps1 launchers or uses clipboard + SendKeys.

## Procedure

1. **Reproduce at the argv boundary before reading more code.** Swap the target exe for a
   stand-in that dumps argv (`node -e "console.log(JSON.stringify(process.argv.slice(2)))"`)
   and feed it the exact generated script and text. For the real CLI, run once in its
   non-interactive mode (`-p`, `--print`) with `--help` open. A "missing argument" error
   means a flag took the positional as a value.
2. **Check which PowerShell and which binary actually run.** Look at `$PSVersionTable`
   (5.1 is the default) and at `Get-Command tool` / `where tool`. It may be a `.ps1`/`.cmd`
   npm shim rather than the `.exe`.
3. **Fix argument passing** with the recipe below. Verify with the argv dump against a
   hostile corpus.
4. **Fix window typing**: add a focus guard, deliver to existing windows before spawning new
   ones, and serialize delivery globally.
5. **Lock it in with offline tests** that run the real generated PowerShell with the desktop
   calls stubbed (see reference). Then do one smoke run against the real exe.
6. Report what was verified against the real binary versus the stubs, and say plainly what
   stayed unverified (real SendKeys into a live window takes over the user's desktop, so
   don't do it unasked).

## Rules

- **Windows PowerShell 5.1 does not escape embedded `"` in native-command arguments.**
  `& exe $text` splits any text containing quotes, so any prompt with JSON-quoted paths
  breaks. Build the command line in the host language with MSVC/`CommandLineToArgvW`
  quoting. Pass it through the stop-parsing token from an env var:
  `& 'C:\full\tool.exe' --% %TOOL_ARGS%`.
- **Invoke the real `.exe` by full path, never the npm `.ps1`/`.cmd` shim.** Shims re-splat
  `$args` / `%*` and re-break the quoting. Resolve from PATH (including
  `<prefix>\node_modules\@scope\pkg\bin\tool.exe`) and offer an override env var.
- **Put `--` before a positional argument that follows a variadic option** (e.g.
  `--add-dir <dirs...>`). The parser otherwise takes the positional as one more value.
- **Check the 32767-char command-line cap** before launching. Fail with a clear error and
  point to a file or attachment for long content.
- **Generated .ps1 files: UTF-8 with BOM** (PS 5.1 reads BOM-less files as ANSI). Quote every
  interpolated value as a single-quoted literal (`'` → `''`). Use `-LiteralPath` for paths.
  Delete temp files at the top of the script, because code after an interactive TUI only
  runs on exit.
- **SendKeys types into whatever window is in front.** `AppActivate` returning true isn't
  enough. Compare `GetForegroundWindow()` with the target `MainWindowHandle` immediately
  before the paste and before Enter, and abort with a one-line error if they differ.
- **Within one batch, type into existing windows before opening new ones.** New consoles take
  focus asynchronously. Keep reported results in input order.
- **Clipboard and focus are global:** jobs that fire in the same tick must run through one
  serial promise chain/queue. Chain with `.catch` so one failure doesn't stall the rest.
- **Show users the first line of PowerShell errors and log the full record.** ErrorRecord
  dumps are unreadable in a UI.

## Support files

- `references/argv-quoting-and-test-harness.md`: the quoting function, the `--%` script
  template, the tested hostile-input corpus, the focus-guard snippet, and how to run the real
  generated PowerShell offline (stubbed cmdlets, node as fake exe, 8.3 path pitfall).

## Runnable public anchor

Reference snippets illustrate integration recipes, not standalone tested programs.
Only the following anchor has the verification scope recorded below.

Run `python scripts/test_boundary.py` from this directory. See [verification](VERIFICATION.md) for scope and negative tests.

## Attribution

Prepared by Rafael with AI assistance. Adapted from private procedural notes whose recorded author was hermes-curator. This is not a claim of sole authorship of those notes. Third-party tools retain their own licenses.
