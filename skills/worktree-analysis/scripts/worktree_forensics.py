#!/usr/bin/env python3
"""Dirty worktree forensics: WHO wrote WHAT, and WHEN.

`git status` tells you what changed. It does not tell you whose work it is, or
whether it belongs to the same task. This script groups dirty files into
temporal CLUSTERS by mtime and cross-references each cluster against the agent
sessions that touched the repo, so you can separate "the agent's work from
yesterday" from "my own work from three months ago" before committing anything.

    python worktree_forensics.py <repo> [--gap-min 90] [--json]

Output: clusters ordered oldest to newest, each with its files, its time
window, and the agent sessions that fall inside that window.
"""
import argparse, glob, json, os, re, subprocess, sys
from datetime import datetime, timedelta

AGENT_HOME = os.path.join(os.path.expanduser("~"), ".claude")
GENERATED = re.compile(
    r"(^|/)(dist|build|out|coverage|node_modules|\.venv|venv|__pycache__"
    r"|graphify-out|\.next|target)(/|$)"
    r"|\.(tsbuildinfo|lock|log|pyc|map)$"
    r"|(^|/)(package-lock\.json|poetry\.lock|uv\.lock|yarn\.lock|pnpm-lock\.yaml)$")
SECRETISH = re.compile(r"(^|/)\.env|secret|credential|\.pem$|\.key$|token", re.I)


def sh(cmd, cwd):
    """git without a shell. On Windows shell=True goes through cmd.exe, where
    SINGLE quotes delimit nothing and --format='%h %s' comes back empty or
    literal."""
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                           timeout=60)
        return p.stdout
    except Exception:
        return ""


def status(repo):
    """[(xy, path)] from porcelain v1, handling renames and spaces in names."""
    out, rows = sh(["git", "status", "--porcelain=v1"], repo), []
    for line in out.splitlines():
        if len(line) < 4:
            continue
        xy, rest = line[:2], line[3:]
        if " -> " in rest:
            rest = rest.split(" -> ", 1)[1]
        rows.append((xy, rest.strip().strip('"')))
    return rows


def slug(p):
    return re.sub(r"[^A-Za-z0-9]", "-", os.path.abspath(p))


def agent_sessions(repo):
    """Agent sessions that touched this repo: (start, end, id, turns)."""
    d = os.path.join(AGENT_HOME, "projects", slug(repo))
    files = glob.glob(os.path.join(d, "*.jsonl"))
    if not files:
        key = os.path.basename(os.path.abspath(repo))
        files = glob.glob(os.path.join(AGENT_HOME, "projects", "*" + key + "*", "*.jsonl"))
    out = []
    for f in files:
        ts, n = [], 0
        for line in open(f, encoding="utf-8", errors="replace"):
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except Exception:
                continue
            if e.get("type") == "assistant":
                n += 1
            t = e.get("timestamp")
            if t:
                try:
                    ts.append(datetime.fromisoformat(t.replace("Z", "+00:00")).astimezone())
                except Exception:
                    pass
        if ts:
            out.append({"id": os.path.basename(f)[:8], "start": min(ts),
                        "end": max(ts), "turns": n})
    return sorted(out, key=lambda s: s["start"])


def cluster(rows, repo, gap_min):
    """Group files by mtime proximity. A gap > gap_min starts a new cluster."""
    items = []
    for xy, path in rows:
        full = os.path.join(repo, path)
        if os.path.isdir(full):                      # `?? dir/` is one line, many files
            for r, _, fs in os.walk(full):
                for fn in fs:
                    fp = os.path.join(r, fn)
                    try:
                        items.append((datetime.fromtimestamp(os.path.getmtime(fp)),
                                      xy, os.path.relpath(fp, repo).replace("\\", "/")))
                    except OSError:
                        pass
            continue
        try:
            items.append((datetime.fromtimestamp(os.path.getmtime(full)), xy, path))
        except OSError:
            items.append((None, xy, path))
    dated = sorted([i for i in items if i[0]], key=lambda i: i[0])
    undated = [i for i in items if not i[0]]

    out, cur = [], []
    for it in dated:
        if cur and (it[0] - cur[-1][0]) > timedelta(minutes=gap_min):
            out.append(cur); cur = []
        cur.append(it)
    if cur:
        out.append(cur)
    return out, undated


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--gap-min", type=int, default=90,
                    help="minutes of silence that separate two clusters")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    repo = os.path.abspath(a.repo)

    if "true" not in sh(["git", "rev-parse", "--is-inside-work-tree"], repo):
        sys.exit(f"not a git repo: {repo}")

    rows = status(repo)
    if not rows:
        print("clean tree - nothing to analyse.")
        return
    clusters, undated = cluster(rows, repo, a.gap_min)
    sess = agent_sessions(repo)
    head = sh(["git", "log", "--format=%h %ad %s", "--date=short", "-1"],
              repo).strip()
    branch = sh(["git", "branch", "--show-current"], repo).strip()

    if a.json:
        print(json.dumps({
            "repo": repo, "branch": branch, "head": head,
            "clusters": [{"start": c[0][0].isoformat(), "end": c[-1][0].isoformat(),
                          "files": [{"xy": x, "path": p} for _, x, p in c]}
                         for c in clusters],
            "sessions": [{**s, "start": s["start"].isoformat(),
                          "end": s["end"].isoformat()} for s in sess],
        }, indent=1, ensure_ascii=False))
        return

    print(f"REPO   {repo}")
    print(f"BRANCH {branch}")
    print(f"HEAD   {head}")
    print(f"DIRTY  {len(rows)} entries -> {len(clusters)} temporal cluster(s) "
          f"(gap {a.gap_min}min)\n")

    for i, c in enumerate(clusters, 1):
        t0, t1 = c[0][0], c[-1][0]
        span = t1 - t0
        age = datetime.now() - t1
        print(f"-- CLUSTER {i} --  {t0:%Y-%m-%d %H:%M} -> {t1:%H:%M}"
              f"  (window {span}, age {age.days}d)")
        hit = [s for s in sess
               if s["end"].replace(tzinfo=None) >= t0 - timedelta(minutes=30)
               and s["start"].replace(tzinfo=None) <= t1 + timedelta(minutes=30)]
        if hit:
            for s in hit:
                print(f"   AGENT: session {s['id']} "
                      f"({s['start']:%m-%d %H:%M}-{s['end']:%H:%M}, {s['turns']} turns)")
        else:
            print("   AGENT: no session in this window -> probably MANUAL")
        for _, xy, p in c:
            flags = []
            if GENERATED.search(p):
                flags.append("GENERATED")
            if SECRETISH.search(p):
                flags.append("!!SECRET?")
            print(f"     {xy} {p}" + ("   [" + ",".join(flags) + "]" if flags else ""))
        print()

    if undated:
        print("-- NO MTIME (deleted?) --")
        for _, xy, p in undated:
            print(f"     {xy} {p}")
        print()

    gen = [p for c in clusters for _, _, p in c if GENERATED.search(p)]
    sec = [p for c in clusters for _, _, p in c if SECRETISH.search(p)]
    print("SUMMARY")
    print(f"  clusters ................. {len(clusters)}")
    print(f"  generated artifacts ...... {len(gen)}"
          + ("  -> .gitignore candidates" if gen else ""))
    if sec:
        print(f"  POSSIBLE SECRET .......... {len(sec)}: {', '.join(sec[:5])}")
    print(f"  agent sessions in repo ... {len(sess)}")


if __name__ == "__main__":
    main()
