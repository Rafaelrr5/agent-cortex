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

    def item(self, kind="operational", result="error", revision="v1"):
        return {"id": "task1", "revision": revision, "kind": kind, "result": result}

    def test_full_cli_lifecycle(self):
        args = ["--cooldown", "10", "--max-attempts", "3"]
        self.fixture([self.item()])
        self.assertEqual(json.loads(self.cli(*args, "--now", "0", expected=1).stdout)[0]["attempt"], 1)
        self.assertEqual(json.loads(self.cli(*args, "--now", "5").stdout)[0]["status"], "cooldown")
        self.fixture([self.item(result="success")])
        self.cli(*args, "--now", "10")
        self.assertEqual(json.loads(self.cli(*args, "--now", "20").stdout), [])
        self.assertEqual(job.load(self.state, {})["task1"]["ack"], "v1")

    def test_human_gate_never_retries_or_acknowledges(self):
        state = {}
        for now in (0, 100, 100000):
            state, output = job.tick([self.item("needs_input", "success")], state, now, 10, 3)
            self.assertEqual(state, {})
            self.assertEqual(output[0]["status"], "needs_input")

    def test_bounded_attempts_and_failed_ack(self):
        state = {}
        for now in (0, 10, 20, 30, 40):
            state, output = job.tick([self.item()], state, now, 10, 3)
        self.assertEqual(state["task1"]["attempts"], 3)
        self.assertIsNone(state["task1"]["ack"])
        self.assertEqual(output[0]["status"], "exhausted")
        state, output = job.tick([self.item(revision="v2")], state, 1000, 10, 3)
        self.assertEqual(output[0]["status"], "exhausted")

    def test_malformed_unknown_and_missing_feed(self):
        self.fixture([self.item("unknown")])
        self.cli("--now", "0", "--cooldown", "10", "--max-attempts", "3", expected=1)
        self.assertFalse(self.state.exists())
        self.feed.unlink()
        self.cli("--now", "0", "--cooldown", "10", "--max-attempts", "3", expected=1)

    def test_corrupt_state_and_human_override(self):
        with self.assertRaises(ValueError):
            job.tick([self.item()], {"task1": {"attempts": -1}}, 0, 10, 3)
        state, _ = job.tick([self.item()], {}, 0, 10, 3)
        baseline = json.dumps(state, sort_keys=True)
        state, output = job.tick([self.item("needs_input", "success")], state, 10000, 10, 3)
        self.assertEqual(json.dumps(state, sort_keys=True), baseline)
        self.assertEqual(output[0]["status"], "needs_input")

    def test_new_revision_not_blindly_consumed(self):
        state, _ = job.tick([self.item(result="success")], {}, 0, 10, 4)
        state, _ = job.tick([self.item(revision="v2")], state, 10, 10, 4)
        self.assertEqual(state["task1"]["ack"], "v1")


if __name__ == "__main__":
    unittest.main()
