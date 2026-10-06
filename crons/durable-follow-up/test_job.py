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


class Checks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR"))
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.feed = self.root / "feed.json"
        self.state = self.root / "state.json"

    def fixture(self, records):
        self.feed.write_text(json.dumps(records), encoding="utf-8")

    def cli(self, *extra, expected=0):
        result = subprocess.run([sys.executable, "-B", str(Path(__file__).with_name("job.py")), 
                                 "--feed", str(self.feed), "--state", str(self.state), *extra],
                                capture_output=True, text=True, timeout=30,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.assertEqual(result.returncode, expected, result.stderr)
        return result

    def opened(self, identity="o1", at=0):
        return {"id": identity, "at": at, "kind": "open"}

    def test_full_cli_lifecycle_beyond_window_and_duplicate(self):
        args = ["--window", "10", "--capacity", "4"]
        self.fixture([self.opened(), self.opened()])
        first = self.cli(*args, "--now", "0").stdout
        self.assertEqual(len(json.loads(first)), 1)
        self.fixture([])
        self.assertEqual(self.cli(*args, "--now", "100").stdout, first)
        self.fixture([{"id": "o1", "at": 101, "kind": "resolved", "evidence": "checked artifact"}])
        self.assertEqual(json.loads(self.cli(*args, "--now", "101").stdout), [])
        self.fixture([self.opened(at=102)])
        self.assertEqual(json.loads(self.cli(*args, "--now", "102").stdout), [])

    def test_explicit_ack_and_empty_evidence(self):
        state, _ = job.tick([self.opened()], {}, 0, 10, 3)
        state, output = job.tick([{"id": "o1", "at": 10, "kind": "ack"}], state, 10, 10, 3)
        self.assertEqual(len(output), 1)
        state, output = job.tick([{"id": "o1", "at": 11, "kind": "ack", "evidence": "operator reviewed"}], state, 11, 10, 3)
        self.assertEqual(output, [])

    def test_capacity_fails_without_dropping_existing_state(self):
        self.fixture([self.opened()])
        self.cli("--now", "0", "--window", "10", "--capacity", "1")
        baseline = self.state.read_bytes()
        self.fixture([self.opened("o2", at=1)])
        self.cli("--now", "1", "--window", "10", "--capacity", "1", expected=1)
        self.assertEqual(baseline, self.state.read_bytes())

    def test_corrupt_state_fails_closed(self):
        with self.assertRaises(ValueError):
            job.tick([], {"o1": {"opened": 0, "resolved": "false"}}, 0, 10, 4)

    def test_missing_input_does_not_clear_state(self):
        self.fixture([self.opened()])
        self.cli("--now", "0", "--window", "10", "--capacity", "4")
        baseline = self.state.read_bytes()
        self.feed.unlink()
        self.cli("--now", "100", "--window", "10", "--capacity", "4", expected=1)
        self.assertEqual(self.state.read_bytes(), baseline)


if __name__ == "__main__":
    unittest.main()
