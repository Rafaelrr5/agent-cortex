"""Read-only ancestry and changed-path report; never merges or pushes."""
import json
import subprocess
import sys


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], stderr=subprocess.PIPE)


def inspect(repo, base, candidate):
    base_sha = git(repo, "rev-parse", "--verify", base + "^{commit}").decode().strip()
    candidate_sha = git(repo, "rev-parse", "--verify", candidate + "^{commit}").decode().strip()
    result = subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", base_sha, candidate_sha], capture_output=True)
    if result.returncode:
        raise ValueError("candidate is not descended from base or ancestry check failed")
    paths = git(repo, "diff", "--name-only", "-z", base_sha, candidate_sha).decode("utf-8", "surrogateescape").split("\0")
    return {"base": base_sha, "candidate": candidate_sha, "changed_paths": [p for p in paths if p], "verdict": "ancestry only; tests and approval required"}


if __name__ == "__main__":
    try:
        print(json.dumps(inspect(*sys.argv[1:4]), ensure_ascii=True))
    except (ValueError, TypeError, OSError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
