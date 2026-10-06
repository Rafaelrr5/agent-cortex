import argparse
import copy
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


def emit(value):
    print(json.dumps(value, sort_keys=True, separators=(",", ":")), flush=True)

import subprocess


def git(repo, *args, check=True):
    result = subprocess.run(["git", "--literal-pathspecs", "-C", str(repo), *args],
                            capture_output=True, text=True, timeout=30,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if check and result.returncode:
        raise ValueError("git failed: " + result.stderr.strip())
    return result


def tick(repo, state, now, cooldown, paths=(), commit=False, remote=None):
    if state.get("last_alert") is not None and (type(state["last_alert"]) is not int or state["last_alert"] < 0):
        raise ValueError("invalid alert state")
    repo = Path(repo).resolve()
    top = Path(git(repo, "rev-parse", "--show-toplevel").stdout.strip()).resolve()
    if top != repo:
        raise ValueError("--repo must be the repository root")
    if git(repo, "ls-files", "-u").stdout:
        message = "unresolved conflict; no changes made"
    else:
        message = ""
        if remote is not None:
            # Only caller-supplied filesystem bare remotes, never a configured URL.
            remote = Path(remote).resolve()
            if not remote.is_dir() or git(remote, "rev-parse", "--is-bare-repository").stdout.strip() != "true":
                raise ValueError("remote must be a local bare repository")
            git(repo, "fetch", "--no-tags", "--no-recurse-submodules", str(remote), "HEAD")
            merge = git(repo, "merge", "--no-edit", "--no-commit", "FETCH_HEAD", check=False)
            if merge.returncode:
                if git(repo, "ls-files", "-u").stdout:
                    git(repo, "merge", "--abort")
                    message = "incoming conflict; merge aborted; manual resolution required"
                else:
                    raise ValueError("merge failed: " + merge.stderr.strip())
            elif git(repo, "rev-parse", "-q", "--verify", "MERGE_HEAD", check=False).returncode == 0:
                git(repo, "merge", "--abort")
                message = "divergent histories; clean merge requires manual review"
    if message:
        allowed = state.get("last_alert") is None or now - state["last_alert"] >= cooldown
        if allowed:
            state = {"last_alert": now}
        return state, {"status": "blocked", "alert": message if allowed else "rate-limited; conflict remains"}, 1
    if commit:
        if not paths:
            raise ValueError("commit requires explicit owned file paths")
        owned = []
        for raw in paths:
            relative = Path(raw)
            if relative.is_absolute() or ".." in relative.parts or not relative.parts or relative.parts[0] == ".git":
                raise ValueError("owned path must be a relative file within the repository")
            target = (repo / relative).resolve()
            if (not target.is_relative_to(repo) or target.is_dir()
                    or target.relative_to(repo).parts[0] == ".git"):
                raise ValueError("owned path escapes repository or names a directory")
            if not git(repo, "ls-files", "--", relative.as_posix()).stdout.strip():
                raise ValueError("only previously tracked owned files may be committed")
            owned.append(relative.as_posix())
        if git(repo, "status", "--porcelain", "--", *owned).stdout:
            git(repo, "commit", "--only", "-m", "Update explicitly owned files", "--", *owned)
    return state, {"status": "ok", "published": False}, 0


def main():
    parser = argparse.ArgumentParser(description="Local-only Git reconciliation; never pushes")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--state", required=True)
    parser.add_argument("--now", type=int, required=True)
    parser.add_argument("--cooldown", type=int, required=True)
    parser.add_argument("--local-remote")
    parser.add_argument("--owned-path", action="append", default=[])
    parser.add_argument("--commit-owned", action="store_true")
    args = parser.parse_args()
    if args.cooldown < 1 or args.now < 0:
        raise ValueError("positive cooldown required")
    # Runtime state must never become content eligible for a later commit.
    state_path = Path(args.state).resolve()
    if state_path.is_relative_to(Path(args.repo).resolve()):
        raise ValueError("state must be outside the repository")
    state, output, code = tick(args.repo, load(args.state, {}), args.now, args.cooldown,
                               args.owned_path, args.commit_owned, args.local_remote)
    emit(output)
    save(args.state, state)
    return code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
