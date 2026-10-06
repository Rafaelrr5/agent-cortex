"""Capture tracked changes before creating a detached worktree. No cleanup or network."""
import hashlib
from pathlib import Path
import subprocess
import sys


def git(repo, *args, data=None):
    return subprocess.run(["git", "-C", str(repo), *args], input=data,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True).stdout


def capture(source, target):
    source = Path(source).resolve()
    target = Path(target).resolve()
    if target.exists():
        raise ValueError("target already exists")
    if git(source, "ls-files", "--others", "--exclude-standard", "-z"):
        raise ValueError("untracked files unsupported; choose an explicit snapshot method")
    if any(entry.startswith(b"160000 ") for entry in git(source, "ls-files", "--stage", "-z").split(b"\0")):
        raise ValueError("submodule snapshots unsupported")
    base = git(source, "rev-parse", "HEAD").decode().strip()
    patch = git(source, "diff", "--binary", "HEAD", "--")
    git(source, "worktree", "add", "--detach", str(target), base)
    if patch:
        git(target, "apply", "--binary", "-", data=patch)
    return base, hashlib.sha256(patch).hexdigest()


if __name__ == "__main__":
    try:
        base, digest = capture(sys.argv[1], sys.argv[2])
        print("base=" + base + " patch_sha256=" + digest)
    except (ValueError, OSError, IndexError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
