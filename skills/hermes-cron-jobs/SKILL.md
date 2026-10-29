---
name: hermes-cron-jobs
description: "Schedule Hermes cron jobs and prove they actually run."
version: 1.0.0
author: Rafael Rocha Ribeiro (github.com/Rafaelrr5)
license: MIT
platforms: [linux, macos, windows]
metadata:
  agent:
    tags: [hermes, cron, scheduling, gateway, automation, verification]
    related_skills: [hermes-messaging-channels, delivery-verification]
---

# Hermes cron jobs: schedule it, then prove it runs

## When to Use

- creating, editing or debugging a Hermes cron job (the `cronjob` tool or `hermes cron`)
- any recurring automation that must run unattended: sync, watchdog, digest, alert
- "the job exists but nothing happens"
- writing the script a script-mode (`no_agent`) job will execute

## The rule

**"Job created" is not evidence that the job works.**

Creating a job succeeds even when it will never fire (no gateway running) and even
when its script fails on the first tick. Both failures are silent. Never tell
anyone an automation is live until you have seen a real run produce the intended
effect.

## Sequence

### 1. Create the job

A script-mode job (`no_agent`) costs zero tokens: the script is the job, and its
stdout is delivered verbatim. Empty stdout means nothing is delivered. So make the
script **silent on the happy path** and loud only on a real problem. Printing
`{"wakeAgent": false}` is also treated as a silent run.

Scripts must live in `HERMES_HOME/scripts/`. The scheduler rejects paths that
resolve outside it, including symlinks.

### 2. Check the gateway before celebrating

The cron ticker is a thread **inside the gateway**. Without a gateway the job is
saved and inert.

```bash
hermes gateway status
```

If it is not running, install it as a service (`hermes gateway install`; on a
Linux server also `sudo loginctl enable-linger $USER`, or install the system
service). On Windows without admin rights the installer may fall back to a
Startup-folder login item, which only starts **after an interactive login**, not
at boot with the session locked. Tell the user: that is a real behavioural
difference. See `hermes-messaging-channels` for proving whether a login item
actually fired.

### 3. Trigger it, and read the result in the right place

```
cronjob(action='run', job_id='<id>')
```

The `last_status` returned by a manual `run` belongs to the **previous** run; the
new one executes asynchronously. Before triggering, check the job's state: resuming
a paused recurring job whose `next_run_at` is in the past can fire a catch-up on
the next tick. If a run is already in flight, use that run as the evidence rather
than starting a second one.

The real result is written to:

```
HERMES_HOME/cron/output/<job_id>/<timestamp>.md
```

Sort by time and read the **newest** file; older runs mislead. Typical statuses:
`silent (empty output)` (the happy path in script mode), `script failed` (with the
error), `ok` (ran and produced output).

### 4. Prove the effect, not the status

A run that did real work and a run that did nothing can both report
`silent (empty output)`, because the script only speaks on error. Check the
external artifact: the file written, the commit on the remote, the row in the
table. Status is a symptom; the artifact is the proof.

For delivery, read the exact run in `HERMES_HOME/cron/executions.db` read-only and
check its delivery outcome. `completed` alone does not prove delivery: `queued` is
still pending, `failed` failed, `not_configured` had no destination. Never write to
that ledger or to `jobs.json` to work around the CLI.

Look for unprocessed format literals in the output (`%s`, `{name}`, `%%`). They
are the signature of a string that silently failed to interpolate.

### 5. Confirm it fires on its own

A manual trigger only proves that the script runs. Wait for (or come back to) a
run whose timestamp matches none of your triggers. That is what proves the ticker
is alive.

### 6. Make sure something watches it

Ask: "if this job fails at 3 a.m., what will notice?" If the answer is nothing,
add it to a watchdog in the same piece of work. A runnable one is in
[`crons/cron-health-watchdog`](../../crons/cron-health-watchdog). It reports
errored jobs, overdue jobs, a dead ticker, and pg_cron/pg_net failures, and it
alerts once per change.

- A service that answers `202` and works in the background never fails for its
  caller. Check the artifact it should produce, not the HTTP status.
- A new artifact check needs a start date, or it raises false alarms for the time
  before the automation existed.
- An overdue one-shot job that never ran shows up as "late". Ask before deleting it.

## "Alert only on what's new"

Keep the set of already-seen keys in a durable working directory, never in a
scratch or temp folder that gets pruned (pruning makes the alert resend everything).
Prove three paths before scheduling:

1. First run prints the baseline. Show it to the user, so the first scheduled tick
   is legitimately silent.
2. An immediate second run prints nothing.
3. Remove a few keys from the state by hand and run again: exactly those come back.

Without the third test, "silent" cannot tell working dedup from broken detection.

## Script language: prefer Python, especially on Windows

The scheduler runs `.sh`/`.bash` through **bash** and every other extension through
**Python** (a `.cmd` would be handed to Python and break). On Windows the gateway
can be spawned with a narrower PATH than the user's shell, and a `.sh` script that
works in the terminal fails in cron with:

```
Cannot run .sh/.bash script: bash not found on PATH.
```

Writing the script in Python removes the dependency. Inside it, resolve external
binaries by absolute path; `shutil.which("git")` can fail for the same reason.

The script runs on the Python that Hermes uses, which may lack third-party
packages and should not have them installed into it. A script that needs one can
test the `import` and re-execute itself under a system interpreter that has it,
guarding against a re-exec loop with an environment variable.

### Minimal shape

```python
import subprocess, sys
from pathlib import Path

GIT = r"C:\Program Files\Git\cmd\git.exe" if sys.platform == "win32" else "/usr/bin/git"
REPO = Path(__file__).resolve().parent / "repo"   # or an absolute path; never rely on cwd

def main():
    r = subprocess.run([GIT, "-C", str(REPO), "status", "--porcelain"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(f"git status failed: {r.stderr.strip()[:300]}")   # loud: delivered
        return 1
    return 0                                                     # silent: nothing delivered

if __name__ == "__main__":
    sys.exit(main())
```

## The same job on a PC and on a server

Keep **one** script that runs on both. Branch on `os.name == "nt"` only for paths,
and pass Windows-only `creationflags` only on Windows. Job ids differ per machine,
so look jobs up by name. When a job moves to the server, **pause the copy on the
PC**: two machines running the same job duplicate every delivery and commit. For a
repo the job writes to, set `git config core.autocrlf input` on Linux, or one
CRLF/LF mismatch shows the whole file as modified.

## Completion notices arrive late and out of order

Runs started with `action='run'` report back asynchronously. The notices can arrive
**minutes later** and **out of chronological order**, so a failure you already fixed
can show up after a later success. Compare the run's timestamp with the time of
your fix before reacting. A run older than the fix is history, not a regression.

## Alert → act: a script gate in front of an agent

When an alert should trigger an investigation, not just a notification, put a
cheap script in front of an agent job:

1. **The script is the gate and the queue.** It runs the detector and keeps
   incidents in a durable file. Empty queue: print `{"wakeAgent": false}` (zero
   tokens). Otherwise print the incidents with ids.
2. **Acknowledge only after handling.** The agent runs `<script> --ack <id>` after
   fixing and verifying, judging it non-actionable, or handing it to a human. An
   unacknowledged incident wakes the agent again next tick, because an agent run
   can die.
3. **Cap the retries.** After N wake-ups, mark it given up and report it as
   unresolved, so a broken agent cannot loop forever.
4. **Prove every path before calling it done:** empty → no wake; seeded incident →
   printed; ack → gone; retry cap → given up and gone.

## Monitor mode: a failed agent run consumes the change

In monitor mode (`monitor_script` / `monitor_url`) Hermes hashes the source output
and persists the new hash **before** the agent runs. If that agent run dies
(provider overloaded, timeout), the run is recorded as failed once. After that,
every tick reads `no_change (agent run suppressed)` until the observed output
changes by itself. A supervisor can sit blind for hours this way.

Mitigations:

- For operational, recoverable work, include something in the monitor output that
  changes until the work is acknowledged (an ack-gated queue as above). A time
  bucket (`int(time.time() // 1800)`) can serve as a stopgap, with a retry cap.
- **Never** use a time bucket for items waiting on a human. An unchanged approval
  request would wake a model every 30 minutes with nothing it can do. Send the
  decision once and re-evaluate only on a human reply or a material change. A
  timer tick is never authorization.
- Do not pin a decision-making monitor to a single provider with no fallback.

To diagnose "the cron didn't act": the `executions` table in `cron/executions.db`
shows the failed run among the completed ones. The output folder shows only
`no_change`, which hides it.

## Pitfalls

- Long chained one-liners in the verification step can trip the terminal tool's
  payload guard (`command parser limit or malformed executable payload`). Run
  checks as short separate commands.
- `memory_char_limit` and similar settings are read at session start; a change via
  `hermes config set` does not apply to the session already running.
- A one-word reply in a new chat ("b", "yes") is often an answer to a question a
  cron alert asked, and cron deliveries may not show up in session search. Read
  the newest files in `cron/output/*/` first. When an alert asks a question, label
  the options with letters and restate each action, so a one-letter reply is
  executable on its own.

## Verification

Done means all of these, observed rather than assumed:

1. `hermes gateway status` shows a running gateway.
2. The newest `cron/output/<job_id>/*.md` shows the expected status.
3. The external artifact exists and is newer than your change.
4. One run fired by the schedule, not by you.
5. A watchdog would report this job if it started failing.
