import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).parents[1] / "scripts/check_candidate.py"
spec = importlib.util.spec_from_file_location("subject", SCRIPT)
subject = importlib.util.module_from_spec(spec)
spec.loader.exec_module(subject)

class RepoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"])
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.git("init", "-q")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "core.autocrlf", "false")
        (self.repo / "data.txt").write_text("base\n", encoding="utf-8")
        self.git("add", "data.txt")
        self.git("commit", "-qm", "fixture base")
        self.base = self.git("rev-parse", "HEAD").strip()

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.repo), *args], stderr=subprocess.PIPE).decode()

    def test_candidate_success_is_read_only(self):
        (self.repo / "data.txt").write_text("candidate\n", encoding="utf-8")
        self.git("add", "data.txt")
        self.git("commit", "-qm", "fixture candidate")
        candidate = self.git("rev-parse", "HEAD").strip()
        before = self.git("status", "--porcelain")
        report = subject.inspect(self.repo, self.base, candidate)
        self.assertEqual(report["changed_paths"], ["data.txt"])
        self.assertEqual(report["candidate"], candidate)
        self.assertEqual(self.git("status", "--porcelain"), before)
        self.assertEqual(self.git("rev-parse", "HEAD").strip(), candidate)

    def test_divergent_candidate_refused(self):
        (self.repo / "data.txt").write_text("branch one\n", encoding="utf-8")
        self.git("add", "data.txt")
        self.git("commit", "-qm", "fixture first")
        first = self.git("rev-parse", "HEAD").strip()
        self.git("checkout", "--detach", self.base)
        (self.repo / "data.txt").write_text("branch two\n", encoding="utf-8")
        self.git("add", "data.txt")
        self.git("commit", "-qm", "fixture second")
        with self.assertRaisesRegex(ValueError, "not descended"):
            subject.inspect(self.repo, first, "HEAD")

    def test_unknown_revision_refused(self):
        with self.assertRaises(subprocess.CalledProcessError):
            subject.inspect(self.repo, self.base, "missing-revision")
