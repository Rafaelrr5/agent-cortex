"""Watchdog for scheduled jobs: speaks only when the set of problems changes.

Reads local snapshots only. It never queries a database or calls a service itself.

Sources, each optional except --jobs:
  --jobs           Hermes cron/jobs.json: enabled job whose last run errored, or
                   whose next run is overdue.
  --heartbeat      Hermes cron/ticker_heartbeat: the scheduler thread stopped ticking.
  --pg-runs        JSON array exported from pg_cron: last run failed, or failures in window.
  --http-failures  JSON array exported from pg_net: non-2xx or timed-out responses.
                   pg_cron reports "succeeded" once the HTTP request is queued; the
                   500 from the called service is only visible here.

A source that cannot be read becomes a problem, never silence.
"""
import argparse
import copy
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import sys


def load(path, default):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return copy.deepcopy(default)
    if not isinstance(value, type(default)):
        raise ValueError("unexpected JSON root type")
    return value


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    os.replace(temporary, path)


def short(text, limit=160):
    lines = (text or "").strip().splitlines()
    return (lines[-1] if lines else "no detail")[:limit]


def hermes_jobs(document, now, late_seconds, ignore):
    if not isinstance(document, dict) or not isinstance(document.get("jobs"), list):
        raise ValueError("jobs file has no 'jobs' list")
    problems = []
    for job in document["jobs"]:
        if not isinstance(job, dict):
            raise ValueError("job entry is not an object")
        name = job.get("name") or job.get("id") or "unnamed"
        if not job.get("enabled") or job.get("state") == "paused" or name in ignore:
            continue
        if job.get("last_status") == "error":
            problems.append(f"hermes {name}: last run failed ({short(job.get('last_error'))})")
        due = job.get("next_run_at")
        if due:
            due_at = dt.datetime.fromisoformat(due)
            if due_at.tzinfo is None:
                raise ValueError(f"job {name}: next_run_at has no timezone")
            if due_at.timestamp() < now - late_seconds:
                problems.append(f"hermes {name}: overdue, was due {due[:16].replace('T', ' ')}")
    return problems


def ticker(path, now, max_age):
    text = Path(path).read_text(encoding="utf-8").split()
    if not text:
        raise ValueError("heartbeat file is empty")
    age = now - float(text[0])
    if age > max_age:
        return [f"hermes scheduler: no heartbeat for {int(age // 60)} min (gateway down?)"]
    return []


def pg_runs(rows):
    problems = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("jobname"), str):
            raise ValueError("pg run row needs a 'jobname'")
        if row.get("active") is False:
            continue
        if row.get("last_status") == "failed":
            problems.append(f"pg_cron {row['jobname']}: last run failed ({short(row.get('last_message'), 120)})")
        elif row.get("failed_runs"):
            problems.append(f"pg_cron {row['jobname']}: {int(row['failed_runs'])} failed run(s) in window")
    return problems


def http_failures(rows):
    problems = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("http failure row is not an object")
        reason = "timeout" if row.get("timed_out") else (row.get("status_code") or row.get("error_msg") or "no response")
        when = str(row.get("created") or "unknown time")[:16].replace("T", " ")
        problems.append(f"pg_net {when}: {reason} {short(row.get('content') or row.get('error_msg') or '', 120)}".rstrip())
    return problems


def tick(sources, state):
    """sources: list of (label, callable). Returns (new_state, lines_to_print)."""
    if not isinstance(state, dict) or not isinstance(state.get("fingerprint", ""), str):
        raise ValueError("invalid watchdog state")
    problems = []
    for label, check in sources:
        try:
            problems += check()
        except (OSError, ValueError, KeyError, TypeError) as exc:
            problems.append(f"{label}: check could not read its source ({type(exc).__name__}: {str(exc)[:160]})")
    if not problems:
        return {"fingerprint": ""}, []
    fingerprint = hashlib.sha256("\n".join(sorted(problems)).encode("utf-8")).hexdigest()
    if fingerprint == state.get("fingerprint"):
        return state, []
    return {"fingerprint": fingerprint}, [f"{len(problems)} scheduled-job problem(s):"] + [f"- {p}" for p in problems]


def main():
    parser = argparse.ArgumentParser(description="Alert once per change in the set of failing scheduled jobs")
    parser.add_argument("--jobs", required=True)
    parser.add_argument("--state", required=True)
    parser.add_argument("--now", type=float, required=True)
    parser.add_argument("--heartbeat")
    parser.add_argument("--pg-runs")
    parser.add_argument("--http-failures")
    parser.add_argument("--late-minutes", type=int, default=30)
    parser.add_argument("--ticker-max-minutes", type=int, default=15)
    parser.add_argument("--ignore", action="append", default=[], help="job name to skip, e.g. this watchdog itself")
    args = parser.parse_args()
    if args.now < 0 or args.late_minutes < 1 or args.ticker_max_minutes < 1:
        raise ValueError("positive time arguments required")

    def need(path):
        if not Path(path).is_file():
            raise FileNotFoundError(f"{Path(path).name} unavailable")
        return path

    sources = [("hermes jobs", lambda: hermes_jobs(load(need(args.jobs), {}), args.now, args.late_minutes * 60, set(args.ignore)))]
    if args.heartbeat:
        sources.append(("hermes scheduler", lambda: ticker(need(args.heartbeat), args.now, args.ticker_max_minutes * 60)))
    if args.pg_runs:
        sources.append(("pg_cron", lambda: pg_runs(load(need(args.pg_runs), []))))
    if args.http_failures:
        sources.append(("pg_net", lambda: http_failures(load(need(args.http_failures), []))))
    state, lines = tick(sources, load(args.state, {}))
    save(args.state, state)
    if lines:
        print("\n".join(lines), flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
