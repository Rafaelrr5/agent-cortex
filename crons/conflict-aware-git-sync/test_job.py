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
                                 "--state", str(self.state), *extra],
                                capture_output=True, text=True, timeout=30,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.assertEqual(result.returncode, expected, result.stderr)
        return result

    def setup_repo(self):
        self.repo = self.root / "repo"
        self.repo.mkdir()
        job.git(self.repo, "init", "-b", "main")
        job.git(self.repo, "config", "user.name", "Example Tester")
        job.git(self.repo, "config", "user.email", "tester@example.invalid")
        for name in ("owned.txt", "other.txt"):
            (self.repo / name).write_text("base\n", encoding="utf-8")
        job.git(self.repo, "add", "--", "owned.txt", "other.txt")
        job.git(self.repo, "commit", "-m", "fixture")
        self.remote = self.root / "remote.git"
        self.remote.mkdir()
        job.git(self.remote, "init", "--bare", "--initial-branch=main")
        job.git(self.repo, "push", str(self.remote), "main")

    def test_full_cli_owned_commit_preserves_other_staging_no_push(self):
        self.setup_repo()
        remote_before = job.git(self.remote, "rev-parse", "HEAD").stdout
        (self.repo / "owned.txt").write_text("owned change\n", encoding="utf-8")
        (self.repo / "other.txt").write_text("other change\n", encoding="utf-8")
        job.git(self.repo, "add", "--", "other.txt")
        args = ["--repo", str(self.repo), "--now", "0", "--cooldown", "10"]
        self.cli(*args)
        self.cli(*args, "--commit-owned", "--owned-path", "owned.txt")
        self.assertEqual(job.git(self.repo, "show", "--pretty=", "--name-only", "HEAD").stdout.strip(), "owned.txt")
        self.assertEqual(job.git(self.repo, "diff", "--cached", "--name-only").stdout.strip(), "other.txt")
        self.assertEqual(job.git(self.remote, "rev-parse", "HEAD").stdout, remote_before)
        self.cli(*args, "--commit-owned", "--owned-path", "owned.txt")

    def test_conflict_abort_and_rate_limit_with_bare_remote(self):
        self.setup_repo()
        peer = self.root / "peer"
        job.git(self.root, "clone", str(self.remote), str(peer))
        job.git(peer, "config", "user.name", "Example Tester")
        job.git(peer, "config", "user.email", "tester@example.invalid")
        (peer / "owned.txt").write_text("remote\n", encoding="utf-8")
        job.git(peer, "commit", "-am", "remote")
        job.git(peer, "push", str(self.remote), "main")
        (self.repo / "owned.txt").write_text("local\n", encoding="utf-8")
        job.git(self.repo, "commit", "-am", "local")
        head = job.git(self.repo, "rev-parse", "HEAD").stdout
        args = ["--repo", str(self.repo), "--cooldown", "10", "--local-remote", str(self.remote)]
        first = self.cli(*args, "--now", "0", expected=1)
        self.assertIn("merge aborted", first.stdout)
        self.assertIn("rate-limited", self.cli(*args, "--now", "1", expected=1).stdout)
        self.assertIn("merge aborted", self.cli(*args, "--now", "10", expected=1).stdout)
        self.assertEqual(job.git(self.repo, "rev-parse", "HEAD").stdout, head)
        self.assertEqual(job.git(self.repo, "ls-files", "-u").stdout, "")

    def test_path_ownership_fail_closed(self):
        self.setup_repo()
        for path in (".", "..", "../outside", ".git/config", str(self.root / "outside"), "new.txt"):
            with self.assertRaises(ValueError):
                job.tick(self.repo, {}, 0, 10, [path], True)

    def test_fast_forward_local_only(self):
        self.setup_repo()
        peer = self.root / "peer"
        job.git(self.root, "clone", str(self.remote), str(peer))
        job.git(peer, "config", "user.name", "Example Tester")
        job.git(peer, "config", "user.email", "tester@example.invalid")
        (peer / "owned.txt").write_text("incoming\n", encoding="utf-8")
        job.git(peer, "commit", "-am", "incoming")
        job.git(peer, "push", str(self.remote), "main")
        self.cli("--repo", str(self.repo), "--now", "0", "--cooldown", "10", "--local-remote", str(self.remote))
        self.assertEqual((self.repo / "owned.txt").read_text(), "incoming\n")


if __name__ == "__main__":
    unittest.main()
