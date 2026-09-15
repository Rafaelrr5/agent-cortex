---
name: agent-config-sync
description: "Use when sharing agent hooks and scheduled jobs between machines."
version: 1.0.0
author: Rafael Rocha Ribeiro (github.com/Rafaelrr5)
license: MIT
platforms: [linux, macos, windows]
---

# Sync agent config between machines

Share an agent's **hooks and scheduled jobs** across the machines you work on,
without a pull on one machine silently breaking the other.

The naive version of this is a git repo with a `hooks/` folder that every
machine pulls. It breaks immediately and quietly, because absolute paths,
available interpreters and credentials differ per machine. What follows is the
shape that survives.

## When to Use

- "the hook/job I made on the other machine didn't show up here"
- installing on machine B something that exists on machine A
- turning on config sync for a new machine
- taking inventory of what each machine has

Not for: memory/knowledge (different repo, different rules) or runtime state
(job queues, sessions, databases — those do not sync, by decision).

## The shape

One repo, one folder per machine:

```
config/
  devices/
    workstation/
      hooks/<name>.py
      manifest.json
    laptop/
      hooks/...
```

Each machine **writes only its own folder** and **reads** the others. That
single rule removes the entire class of merge conflicts: a conflict under
`devices/` means someone edited another machine's folder by hand, which is
always a bug.

Import is a command, never a pull:

```bash
agent-config list                     # every machine
agent-config list laptop              # one machine
agent-config show laptop hook stop.py # read before installing
agent-config import laptop hook stop.py
```

## Rules that must not be reverted

Each of these is a bug that was paid for once.

**Import rewrites paths, and covers all three escapes.** A path appears in
config as `/`, `\`, and `\\`. Rewrite each form separately, most specific
first. Do the `\` pass before the `\\` pass and it eats half of every escaped
backslash, producing a string literal that no longer parses.

**A hook is installed at the rewritten source path, not at a fixed
`hooks/` directory.** File in one place and the registered command pointing at
another gives you a hook that is dead and silent. After importing, verify by
hand that every quoted path in the command actually exists on this machine: a
virtualenv interpreter is not guaranteed anywhere else.

**The import preserves every field of the hook, not just type and command.**
Timeouts, matchers and filters are part of the contract.

**Never write to the scheduler's own job file.** A running scheduler owns that
file and rewrites it wholesale on every tick; an external write is either
overwritten or corrupts the schedule. Import should *prepare* the job and print
a spec for the scheduler's own API to consume.

**Shell scripts as scheduled jobs fail silently on Windows.** The scheduler
spawns with a narrow PATH and cannot find bash: the job reports an error status
and delivers nothing. Write jobs in Python. Warn at import time when the
imported job is a `.sh`.

**The export skips binaries** (`.exe`, `.dll`, `.cmd`, `.bat`) referenced in a
command. A hook command is `<interpreter> <script>`; only the script is config.
Without the filter, a virtualenv's `python.exe` goes into the repo as text.

**Credentials are redacted on export and the import aborts on the marker.** A
private repo still leaks through zips, backups and forks. Move the value by
another channel and edit the installed file by hand.

**Export requires an explicit local policy file.** No policy, no export.
Opt-in per hook (by event, command and files) and per job (by exact id). An
implicit "export everything in this folder" eventually exports something that
should never have left the machine.

**Import is always explicit, never automatic.** A pull that overwrote `hooks/`
would break the receiving machine in silence. This is the same failure class as
a union merge strategy on a file where deletions are meaningful: the deleted
entry comes back from the other side and nobody notices.

## Idempotence, and how you know it broke

Running the sync twice in a row must produce **no new commit**. Achieve it by
ignoring volatile fields in the comparison: export timestamps, and the
scheduler's runtime fields (`next_run_at`, `last_status`, `failure_streak`,
`repeat.completed`).

A commit every tick means a new volatile field appeared in the scheduler's
output. Add it to the ignore list rather than accepting the noise — otherwise
the history becomes unreadable exactly when you need to read it.

## Debug

The happy path is silent, which is the problem. To see anything:

```bash
python sync.py            # run the whole sync by hand
git -C config log --oneline -5
```

A rejected push (`fetch first`) when two machines export at nearly the same
time is **expected and not an error**: the next tick pulls, merges and pushes
on its own. Do not fix it by hand.

A real conflict should abort the merge, leave the repo clean, and alert at most
once an hour. An alert per tick trains you to ignore alerts.
