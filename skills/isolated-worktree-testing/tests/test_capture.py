import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).parents[1] / "scripts/capture_worktree.py"
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

    def test_staged_and_unstaged_capture_preserves_source(self):
        (self.repo / "data.txt").write_text("staged\n", encoding="utf-8")
        self.git("add", "data.txt")
        (self.repo / "data.txt").write_text("unstaged\n", encoding="utf-8")
        before = self.git("status", "--porcelain")
        target = self.root / "verify"
        base, digest = subject.capture(self.repo, target)
        self.assertEqual(base, self.base)
        self.assertEqual(len(digest), 64)
        self.assertEqual((target / "data.txt").read_text(), "unstaged\n")
        self.assertEqual(self.git("status", "--porcelain"), before)
        self.assertEqual(self.git("rev-parse", "HEAD").strip(), self.base)
        # Only disposable fixture files are reset; no links or dependencies exist.
        subprocess.check_call(["git", "-C", str(target), "restore", "data.txt"])
        self.git("worktree", "remove", str(target))
        self.assertFalse(target.exists())

    def test_untracked_refused_before_worktree(self):
        (self.repo / "new.txt").write_text("new")
        target = self.root / "verify"
        with self.assertRaisesRegex(ValueError, "untracked"):
            subject.capture(self.repo, target)
        self.assertFalse(target.exists())

    def test_existing_target_refused(self):
        target = self.root / "verify"
        target.mkdir()
        with self.assertRaisesRegex(ValueError, "exists"):
            subject.capture(self.repo, target)

    def test_submodule_refused(self):
        # Index-only gitlink; no second repository or network required.
        self.git("update-index", "--add", "--cacheinfo", "160000," + self.base + ",component")
        with self.assertRaisesRegex(ValueError, "submodule"):
            subject.capture(self.repo, self.root / "verify")
