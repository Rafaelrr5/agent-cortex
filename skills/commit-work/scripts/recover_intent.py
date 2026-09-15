#!/usr/bin/env python3
"""Print the agent prompts that explain a dirty tree.

Two sources, both written by Claude Code:
  ~/.claude/history.jsonl            — prompt index, one JSON object per line
  ~/.claude/projects/<slug>/*.jsonl  — full sessions, newest 3 files

<slug> is the repo's absolute path with every non-alphanumeric char flattened to '-'.

Usage: python recover_intent.py <repo-path> [--limit 50] [--sessions 3]
       python recover_intent.py --selftest
"""
import argparse
import glob
import json
import os
import pathlib
import re
import sys


def slug(repo_path: str) -> str:
    """Absolute path -> the ~/.claude/projects directory name."""
    return re.sub(r'[^A-Za-z0-9]', '-', os.path.abspath(repo_path))


def _rows(path: pathlib.Path):
    if not path.exists():
        return
    with path.open(encoding='utf-8', errors='replace') as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except ValueError:
                continue


def _texts(content):
    """User-message content -> list of strings (str or list-of-blocks form)."""
    if isinstance(content, str):
        return [content] if content.strip() else []
    if isinstance(content, list):
        return [b.get('text', '') for b in content
                if isinstance(b, dict) and b.get('type') == 'text' and b.get('text')]
    return []


def history(repo_path: str, limit: int):
    key = os.path.basename(os.path.abspath(repo_path))
    rows = [r for r in _rows(pathlib.Path.home() / '.claude' / 'history.jsonl')
            if key in str(r.get('project', ''))]
    rows.sort(key=lambda r: int(r.get('timestamp', 0) or 0))
    for r in rows[-limit:]:
        print(r.get('timestamp'), ' '.join(str(r.get('display', '')).split())[:240])


def sessions(repo_path: str, count: int, limit: int):
    d = os.path.join(os.path.expanduser('~/.claude/projects'), slug(repo_path))
    files = sorted(glob.glob(os.path.join(d, '*.jsonl')), key=os.path.getmtime)[-count:]
    if not files:
        # Exact slug only. The flattening rule has changed between versions;
        # when it misses, fall back to a glob on the repo basename.
        key = os.path.basename(os.path.abspath(repo_path))
        files = sorted(glob.glob(os.path.join(os.path.dirname(d), '*' + key + '*', '*.jsonl')),
                       key=os.path.getmtime)[-count:]
    for f in files:
        print('###', os.path.basename(f))
        shown = 0
        for r in _rows(pathlib.Path(f)):
            if r.get('type') != 'user':
                continue
            for t in _texts((r.get('message') or {}).get('content')):
                print('USER:', ' '.join(t.split())[:300])
                shown += 1
                if shown >= limit:
                    break
            if shown >= limit:
                break


def selftest():
    assert slug(r'C:\x\ai_agent') .endswith('-x-ai-agent'), slug(r'C:\x\ai_agent')
    assert _texts('hi') == ['hi']
    assert _texts('  ') == []
    assert _texts([{'type': 'text', 'text': 'a'}, {'type': 'tool_use'}]) == ['a']
    assert _texts(None) == []
    print('selftest ok')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('repo', nargs='?')
    ap.add_argument('--limit', type=int, default=50)
    ap.add_argument('--sessions', type=int, default=3)
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args()
    if a.selftest:
        selftest()
        sys.exit(0)
    if not a.repo:
        ap.error('repo path required')
    print('=== history.jsonl ===')
    history(a.repo, a.limit)
    print('=== sessions ===')
    sessions(a.repo, a.sessions, a.limit)
