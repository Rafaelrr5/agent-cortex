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

    def test_full_cli_lifecycle_and_outage(self):
        self.fixture([])
        self.assertEqual(json.loads(self.cli().stdout), {"id": "", "sequence": -1})
        request = {"id": "r1", "sequence": 1, "kind": "request"}
        self.fixture([request])
        baseline = self.cli().stdout
        self.fixture([request, {"id": "reply1", "sequence": 2, "kind": "reply"}])
        self.assertEqual(self.cli().stdout, baseline)
        self.assertEqual(self.cli().stdout, baseline)
        self.fixture([])
        self.assertEqual(self.cli().stdout, baseline)
        self.feed.unlink()
        self.assertEqual(self.cli(expected=1).stdout, baseline)
        self.feed.write_text("broken", encoding="utf-8")
        self.assertEqual(self.cli(expected=1).stdout, baseline)
        self.fixture([{"id": "r2", "sequence": 3, "kind": "request"}])
        self.assertNotEqual(self.cli().stdout, baseline)

    def test_invalid_record_preserves_state(self):
        self.fixture([{"id": "r1", "sequence": 1, "kind": "request"}])
        self.cli()
        previous = self.state.read_bytes()
        self.fixture([{"id": "oops"}])
        self.cli(expected=1)
        self.assertEqual(previous, self.state.read_bytes())

    def test_no_dependency_fresh_outage(self):
        self.assertEqual(json.loads(self.cli(expected=1).stdout)["id"], "")
        self.assertFalse(self.state.exists())

    def test_order_and_reply_do_not_change_identity(self):
        base = {"id": "b", "sequence": 2}
        self.assertEqual(job.tick([{"id": "a", "sequence": 1, "kind": "request"}], base), base)


if __name__ == "__main__":
    unittest.main()
