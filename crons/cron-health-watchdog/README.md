# Cron health watchdog

Standalone Python 3.12+ standard-library example. No agent framework, credentials,
database driver, daemon, or real scheduler is required.

## The failure it prevents

Scheduled jobs fail quietly. Three cases this example was built from:

- A Hermes job keeps its last run as `error` for days, and nobody reads the output
  folder.
- The scheduler itself stops (on Hermes the cron ticker is a thread inside the
  gateway): jobs stay "scheduled", their next run slides into the past, and no
  run means no error to report.
- A Postgres `pg_cron` job that calls an HTTP endpoint through `pg_net` reports
  `succeeded`. That only proves the request was queued. The 500 from the called
  service lives in `net._http_response`, which pg_net deletes after its TTL
  (default 6 hours). A watchdog that only reads `cron.job_run_details` never
  sees it.

## Contract

Inputs are local snapshots, never live connections:

| Flag | Source | Problem reported |
|---|---|---|
| `--jobs` (required) | Hermes `HERMES_HOME/cron/jobs.json` | enabled, unpaused job whose `last_status` is `error`; or whose `next_run_at` is more than `--late-minutes` (default 30) in the past |
| `--heartbeat` | Hermes `HERMES_HOME/cron/ticker_heartbeat` | first field (epoch seconds) older than `--ticker-max-minutes` (default 15) |
| `--pg-runs` | JSON array from the first query below | active job whose last run failed, or with failed runs in the window |
| `--http-failures` | JSON array from the second query below | every row: a non-2xx, error or timed-out response |

`--ignore <job name>` skips a job (repeatable); use it for the watchdog's own job.

A source that is missing, unreadable or malformed is itself reported as a problem.
A broken check must never look like a healthy system.

Output is silent when everything is healthy, and silent when the problem set is
identical to the last alert. When the set changes (a new failure, one fewer, a
different message), it prints the whole current list once. When everything
recovers, the stored fingerprint is cleared, so the same failure returning later
alerts again. Corrupt state fails with exit 1 and is left untouched for
inspection.

This shape fits Hermes script-mode cron (`no_agent`): empty stdout is a silent
success, and anything printed is delivered verbatim.

### Exporting the Postgres side

These queries match the column names in the pg_cron and pg_net sources. Check
them against the versions you have installed, and run them under a role that can
read the `cron` and `net` schemas.

```sql
-- pg_runs.json: last run and failures in the last 26 hours, per job
select j.jobname, j.active,
       last.status          as last_status,
       last.return_message  as last_message,
       (select count(*) from cron.job_run_details f
         where f.jobid = j.jobid and f.status = 'failed'
           and f.start_time > now() - interval '26 hours') as failed_runs
from cron.job j
left join lateral (
  select r.status, r.return_message from cron.job_run_details r
  where r.jobid = j.jobid order by r.start_time desc limit 1
) last on true;

-- http_failures.json: responses that were not 2xx, inside pg_net's retention
select created, status_code, timed_out, error_msg, left(content, 200) as content
from net._http_response
where created > now() - interval '6 hours'
  and (timed_out or error_msg is not null or status_code not between 200 and 299);
```

`net._http_response` is pg_net's internal table, and rows disappear after
`pg_net.ttl`. Run the export more often than the TTL during the hours your jobs
fire, or failures will expire before the watchdog sees them. Response `content`
can contain whatever the called service returned. Keep the export private, and
trim it further if your endpoints echo request data.

## Run and verify

From this directory, with Python 3.12+ available as `python`:

```sh
python -B job.py --help
python -B test_job.py -v
```

Ten tests cover: a healthy system is silent; one alert per change, then silence;
recovery re-arms the alert; paused, disabled and ignored jobs are skipped; the
lateness threshold on both sides; a stale heartbeat; pg_cron and pg_net failures;
an unreadable source reported as a problem; corrupt state failing visibly; and a
timestamp without a timezone. Every test runs the real CLI against a fixed clock
in a temporary directory.

The two SQL queries were run in PGlite against tables with the pg_cron and pg_net
column layout (one failed last run, one older failure, one never-run job, a 500,
a timeout, a 200 and an expired row). Their output, fed to `job.py`, produced
exactly the three expected problems.

It was also run read-only against a live Hermes `jobs.json` and
`ticker_heartbeat` on Windows. That machine was healthy, and the output was empty
on both runs.

For your own files, replace every `/ABSOLUTE/...` with a native absolute path (on
Windows use `C:/...`):

```sh
python -B job.py --jobs /ABSOLUTE/hermes/cron/jobs.json \
  --heartbeat /ABSOLUTE/hermes/cron/ticker_heartbeat \
  --state /ABSOLUTE/runtime/watchdog-state.json \
  --now "$(python -c 'import time; print(time.time())')" --ignore cron-health-watchdog
```

Keep `--state` out of short-lived scratch directories. If the fingerprint is
pruned, the next tick repeats an alert that was already delivered.

## Scheduling is disabled

`scheduler.example.json` is inert documentation. `enabled` is false and the
command and destination values are empty. Nothing here registers a job.

To schedule it with Hermes, Hermes script-mode jobs must live in
`HERMES_HOME/scripts/`. Copy `job.py` there, wrap it in a script that passes the
current time and your paths, and create the job with `no_agent` so no model call
is made. The wrapper must be Python, not `.sh`: on Windows the gateway can start
with a narrower PATH than your shell and fail with `bash not found on PATH`. Then
prove it: trigger one run, read the newest file in
`HERMES_HOME/cron/output/<job_id>/`, and wait for one natural tick you did not
trigger.

## Limitations

Single-writer state; do not run overlapping ticks against the same state file.
The Hermes `jobs.json` fields read here (`enabled`, `state`, `last_status`,
`last_error`, `next_run_at`) and the heartbeat format were read from Hermes Agent
v0.21. A Hermes upgrade can change them, and the watchdog then reports a read
failure instead of guessing. It detects failures that leave a trace. A job that
"succeeds" while producing nothing (an HTTP 202 whose background work dies)
needs a check on the artifact it should have produced. That check belongs next
to the job, not in this script.
