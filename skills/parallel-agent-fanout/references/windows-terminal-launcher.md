# Launching agent windows on Windows

Device-neutral notes for opening N interactive Claude Code windows. **Check which
terminal actually exists before reusing any recipe** — it varies per machine.

```bash
which wt                                    # Windows Terminal
ls "C:/Program Files/Git/usr/bin/mintty.exe"  # Git for Windows fallback
which claude && claude --version
```

## Prefer `wt` when it exists

Prefer a native terminal tool over a helper script when available. Where Windows
Terminal is installed, `wt -w new-window` is the native channel and no wrapper is
needed for the window itself.

## The `cmd /k` trap — cost a wasted window in a real session

This looks reasonable and is broken:

```bash
wt -w new-window --title "A" -d "$REPO" cmd /k "echo ... && pause && claude \"$(cat)\""
```

`cmd.exe` does not expand `$(cat)`. The subshell runs in the *calling* bash against
empty stdin, so `claude` receives an empty prompt. The window opens, prints, and hangs
at `pause` — and the launching call still returns **exit 0**.

Two lessons: don't mix bash substitution into a `cmd` string, and don't trust the exit
code (see the skill body).

## Working invocation — bash inside the window

Put the body in a script on disk and have `wt` run **bash**, not `cmd`:

```bash
BASH="C:/Program Files/Git/bin/bash.exe"
T="C:/Users/<user>/agent-tasks"
R="C:/Users/<user>/Downloads/reps/<repo>"

wt -w new-window --title "TASK A - ..." "$BASH" -lc \
  "'$T/open-task.sh' '$T/<prompt>.md' '$R' 'TASK A - ...'"
```

Three at once, with a small stagger so `wt` doesn't race itself:

```bash
for j in "A-persistence|TASK A - ..." "B-i18n|TASK B - ..." "C-presentation|TASK C - ..."; do
  f="${j%%|*}"; t="${j##*|}"
  wt -w new-window --title "$t" "$BASH" -lc "'$T/open-task.sh' '$T/autosend-$f.md' '$R' '$t'"
  sleep 2
done
```

Use forward-slash native paths (`C:/...`). MSYS path translation is disabled for native
programs, so `/c/Users/...` fails when passed to `wt`, `node`, or `git`.

### The `-lc` + relative-path trap — cost two dead windows in one session

`bash -l` is a **login shell**: it sources the profile chain, and a machine-specific
`.bashrc` can leave the shell in `$HOME`. Then any relative path in the `-lc` string
is resolved against `$HOME`, not against the directory you were in when you
built the command. This opens and instantly closes the window:

```bash
# BROKEN — cd happens in the CALLING shell; -l resets cwd to $HOME inside the window
cd "$T" && wt.exe --title "X" bash -lc "./open-task.sh prompt.md '$R' 'X'"
```

The script "is not found", the launcher exits, `wt` tears the window down — and
the launching call still returns **exit 0**. Symptom the user reports: *"the
window didn't open"* / *"there's no cmd open"*.

Fixes, apply all three:

1. **Absolute path to the script**, never `./`.
2. **Absolute paths for every argument** too (prompt file, repo dir).
3. **Absolute path to bash itself** — `"C:/Program Files/Git/bin/bash.exe"`
   rather than bare `bash`, so you are not depending on the launching PATH.

```bash
# WORKS — everything absolute; -l is then harmless
wt.exe --title "VPS Setup" "C:/Program Files/Git/bin/bash.exe" -lc \
  "/c/Users/<user>/agent-tasks/open-task.sh \
   /c/Users/<user>/agent-tasks/<prompt>.md \
   /c/Users/<user>/Downloads/reps/<repo> 'VPS Setup'"
```

Note the asymmetry that makes this confusing: `wt.exe` needs the **native**
`C:/...` form for the bash executable, while the arguments handed *to bash* work
in MSYS `/c/...` form because bash itself resolves them. Both styles appear in
one working command line; that is correct, not a mistake.

Confirm in a **separate** call — absence of the process is the only real evidence
the window died:

```bash
tasklist | grep -i WindowsTerminal   # a PID here means it is alive and waiting
```


## The launcher script

Human-in-the-loop by design: it prints the task and **stops at a `read`** so the user
reviews before the agent starts.

```bash
#!/usr/bin/env bash
# open-task.sh <prompt.md> <repo-dir> [titulo]
set -u
PROMPT_FILE="${1:?uso: open-task.sh <prompt.md> <repo-dir> [titulo]}"
REPO_DIR="${2:?}"; TITLE="${3:-Claude Code}"

[ -f "$PROMPT_FILE" ] || { echo "ERRO: prompt nao encontrado"; read -r; exit 1; }
cd "$REPO_DIR" || { echo "ERRO: repo nao encontrado"; read -r; exit 1; }

CYAN=$'\033[36m'; DIM=$'\033[2m'; RST=$'\033[0m'
echo "${CYAN}=== ${TITLE} ===${RST}"
echo "${DIM}repo   :${RST} $(pwd)"
echo "${DIM}branch :${RST} $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '(sem git)')"
echo
sed 's/^/  /' "$PROMPT_FILE"
echo
read -r -p "Enter para iniciar o Claude Code (Ctrl+C aborta)... "

PROMPT="$(cat "$PROMPT_FILE")"
exec claude --dangerously-skip-permissions "$PROMPT"
```

Validate before launching — a syntax error only shows up as a window that vanishes:

```bash
chmod +x open-task.sh && bash -n open-task.sh && echo OK
```

## Counting what actually opened

`MainWindowTitle` is unreliable: Windows Terminal hosts every tab in one process, so
three tasks can surface as one titled window. Count launcher processes and read the
prompt filename out of the command line:

```bash
powershell.exe -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='bash.exe'\" | Where-Object { \$_.CommandLine -match 'open-task' } | ForEach-Object { if (\$_.CommandLine -match '<prefix>-([ABC])-') { 'TASK ' + \$Matches[1] + '  pid=' + \$_.ProcessId } }"
```

Expect **2 processes per task** (the `wt`-spawned shell plus the launcher's bash). Six
lines for three tasks is correct, not a duplicate launch.

## Killing a stray window

`taskkill //PID N //F` fails in git-bash — MSYS mangles the `//`. Use PowerShell:

```bash
powershell.exe -NoProfile -Command "Stop-Process -Id <pid> -Force"
```

Identify the owner first so you don't kill an unrelated process:

```bash
powershell.exe -NoProfile -Command "Get-CimInstance Win32_Process -Filter 'ProcessId=<pid>' | Select-Object ProcessId,ParentProcessId,CommandLine | Format-List"
```

## Related: killing a background server

Using your runtime's process-stop tool on an `npm start` can kill the npm wrapper but leave the `node`
child holding the port. Verify with the port, not the kill status:

```bash
netstat -ano | grep -E ":<port>\s+.*LISTENING"
```
