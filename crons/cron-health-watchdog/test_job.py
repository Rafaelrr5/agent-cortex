import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("job", Path(__file__).with_name("job.py"))
job = importlib.util.module_from_spec(spec)
spec.loader.exec_module(job)

NOW = 1_800_000_000.0  # fixed clock, 2027-01-15 08:00 UTC


def iso(offset_seconds):
    import datetime as dt
    return dt.datetime.fromtimestamp(NOW + offset_seconds, dt.timezone.utc).isoformat()


class Checks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR"))
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.jobs = self.root / "jobs.json"
        self.state = self.root / "state.json"
        self.heartbeat = self.root / "ticker_heartbeat"
        self.runs = self.root / "pg_runs.json"
        self.http = self.root / "http_failures.json"

    def write_jobs(self, *jobs):
        self.jobs.write_text(json.dumps({"jobs": list(jobs)}), encoding="utf-8")

    def healthy(self, name="backup"):
        return {"name": name, "enabled": True, "state": "scheduled", "last_status": "ok", "next_run_at": iso(600)}

    def cli(self, *extra, expected=0, now=NOW):
        result = subprocess.run([sys.executable, "-B", str(Path(__file__).with_name("job.py")),
                                 "--jobs", str(self.jobs), "--state", str(self.state), "--now", str(now), *extra],
                                capture_output=True, text=True, timeout=30,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.assertEqual(result.returncode, expected, result.stderr)
        return result

    def test_healthy_is_silent(self):
        self.write_jobs(self.healthy())
        self.heartbeat.write_text(f"{NOW - 60} 1234", encoding="utf-8")
        self.assertEqual(self.cli("--heartbeat", str(self.heartbeat)).stdout, "")

    def test_alerts_once_then_silent_then_again_on_change(self):
        failed = dict(self.healthy("sync"), last_status="error", last_error="Traceback\nRuntimeError: remote rejected")
        self.write_jobs(self.healthy(), failed)
        first = self.cli().stdout
        self.assertIn("hermes sync: last run failed (RuntimeError: remote rejected)", first)
        self.assertEqual(self.cli().stdout, "", "unchanged problem set must not repeat")
        late = dict(self.healthy("digest"), next_run_at=iso(-3600))
        self.write_jobs(self.healthy(), failed, late)
        second = self.cli().stdout
        self.assertIn("hermes digest: overdue", second)
        self.assertIn("2 scheduled-job problem(s)", second)

    def test_recovery_rearms_the_alert(self):
        failed = dict(self.healthy("sync"), last_status="error", last_error="boom")
        self.write_jobs(failed)
        self.assertNotEqual(self.cli().stdout, "")
        self.write_jobs(self.healthy("sync"))
        self.assertEqual(self.cli().stdout, "")
        self.write_jobs(failed)
        self.assertNotEqual(self.cli().stdout, "", "same failure after a recovery is news again")

    def test_paused_disabled_and_ignored_jobs_are_skipped(self):
        broken = {"last_status": "error", "next_run_at": iso(-99999)}
        self.write_jobs(dict(self.healthy("a"), **broken, state="paused"),
                        dict(self.healthy("b"), **broken, enabled=False),
                        dict(self.healthy("watchdog"), **broken))
        self.assertEqual(self.cli("--ignore", "watchdog").stdout, "")

    def test_late_threshold_is_respected(self):
        self.write_jobs(dict(self.healthy(), next_run_at=iso(-29 * 60)))
        self.assertEqual(self.cli().stdout, "")
        self.write_jobs(dict(self.healthy(), next_run_at=iso(-31 * 60)))
        self.assertIn("overdue", self.cli().stdout)

    def test_stale_heartbeat(self):
        self.write_jobs(self.healthy())
        self.heartbeat.write_text(f"{NOW - 40 * 60} 1234", encoding="utf-8")
        self.assertIn("no heartbeat for 40 min", self.cli("--heartbeat", str(self.heartbeat)).stdout)

    def test_pg_cron_and_pg_net_failures(self):
        self.write_jobs(self.healthy())
        self.runs.write_text(json.dumps([
            {"jobname": "nightly", "active": True, "last_status": "failed", "last_message": "ERROR: relation missing"},
            {"jobname": "hourly", "active": True, "last_status": "succeeded", "failed_runs": 2},
            {"jobname": "retired", "active": False, "last_status": "failed"},
        ]), encoding="utf-8")
        self.http.write_text(json.dumps([
            {"created": "2027-01-15T07:00:00Z", "status_code": 500, "content": "internal error", "timed_out": False},
            {"created": "2027-01-15T07:30:00Z", "status_code": None, "timed_out": True},
        ]), encoding="utf-8")
        out = self.cli("--pg-runs", str(self.runs), "--http-failures", str(self.http)).stdout
        self.assertIn("pg_cron nightly: last run failed (ERROR: relation missing)", out)
        self.assertIn("pg_cron hourly: 2 failed run(s)", out)
        self.assertNotIn("retired", out)
        self.assertIn("pg_net 2027-01-15 07:00: 500 internal error", out)
        self.assertIn("pg_net 2027-01-15 07:30: timeout", out)

    def test_unreadable_source_is_a_problem_not_silence(self):
        out = self.cli("--heartbeat", str(self.heartbeat)).stdout  # neither jobs nor heartbeat exist
        self.assertIn("hermes jobs: check could not read its source", out)
        self.assertIn("hermes scheduler: check could not read its source", out)
        self.jobs.write_text("{not json", encoding="utf-8")
        self.assertIn("JSONDecodeError", self.cli().stdout)

    def test_corrupt_state_fails_visibly_and_is_kept(self):
        self.write_jobs(self.healthy())
        self.state.write_text("[]", encoding="utf-8")
        result = self.cli(expected=1)
        self.assertIn("unexpected JSON root type", result.stderr)
        self.assertEqual(self.state.read_text(encoding="utf-8"), "[]")

    def test_naive_timestamp_is_reported(self):
        self.write_jobs(dict(self.healthy(), next_run_at="2027-01-15T08:00:00"))
        self.assertIn("no timezone", self.cli().stdout)


if __name__ == "__main__":
    unittest.main()
