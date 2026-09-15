#!/usr/bin/env python3
"""
cortex.py - long-term memory for coding agents, in one file.

WHY THIS EXISTS
  An agent's context window is short-term memory. Everything it learned about
  your stack dies at the end of the session, so you re-explain the same
  procedure every week. This is the layer that survives.

ARCHITECTURE (4 tiers, only tier 1 lives here)
  L0  a small always-in-prompt file        identity + hot index (~4 KB)
  L1  THIS FILE                            on demand, unbounded: patterns,
                                           decisions, gotchas
  L2  local embeddings                     closes the semantic search
  L3  raw session transcripts              last resort

CORE PRINCIPLE - memory travels as TEXT, never as a binary.
  facts.jsonl   = source of truth, versioned in git (`merge=union`)
  cortex.db     = DERIVED, rebuildable, gitignored
Measured, not assumed: a jsonl -> db -> search roundtrip returns bit-identical
scores, and UNIQUE(content) absorbs merge duplicates on its own. That is what
makes it safe to sync across machines through git, which you must never do with
a SQLite file directly (the WAL sidecars corrupt).

RANKING - decided by measurement, not intuition (recall@5 on a 40-query set):
  lexical only (FTS5 bm25)   exact-token 100%   paraphrase   0%   recall  57%
  embeddings only            exact-token 100%   paraphrase  43%   recall 100%
  naive RRF fusion           exact-token 100%   paraphrase  14%   WORSE
Embeddings lead. Lexical enters only as a tiebreak for exact identifiers
(`createServiceRoleClient`), at low weight, because FTS5 is wrong with
confidence and drags a naive fusion below either input alone.

USAGE
  python cortex.py add "fact" --category pattern --project api --tags a,b
  python cortex.py search "how did we do X" -n 5
  python cortex.py supersede <hash> "the corrected fact"
  python cortex.py stats | export | rebuild

Embeddings are optional: `pip install fastembed numpy` upgrades search from
lexical to semantic. Without them the CLI still works, and says so.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows
    fcntl = None
try:
    import msvcrt
except ImportError:  # pragma: no cover - POSIX
    msvcrt = None

# ------------------------------------------------------------------- paths --
CORTEX_HOME = Path(os.environ.get("CORTEX_HOME") or (Path.home() / ".cortex"))
FACTS_JSONL = CORTEX_HOME / "facts.jsonl"        # <- SOURCE OF TRUTH (git)
FACTS_LOCK = CORTEX_HOME / "facts.jsonl.lock"    # transient, not versioned
DB_PATH = CORTEX_HOME / "cortex.db"              # <- derived, gitignored

MODEL_NAME = os.environ.get(
    "CORTEX_MODEL", "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
)
EMB_DIM = 768

# Weights from the measurement in the docstring. Semantic carries the answer;
# the other two only break ties.
W_LEXICAL = 0.15      # applied only above LEX_FLOOR, i.e. near-exact token hit
W_TRUST = 0.10
LEX_FLOOR = 0.85
DEVICE_PENALTY = 0.02  # a weak signal. See _rank() for why it is not a filter.


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _device() -> str:
    """Short identity of this machine, for provenance - never for filtering."""
    explicit = os.environ.get("CORTEX_DEVICE")
    if explicit:
        return explicit.strip()
    import socket

    return (socket.gethostname() or "unknown").split(".")[0].lower()


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _short(h: str) -> str:
    return h[:16]


# ------------------------------------------------------------------- store --
SCHEMA = """
CREATE TABLE IF NOT EXISTS facts (
    content_hash   TEXT PRIMARY KEY,
    content        TEXT NOT NULL UNIQUE,
    category       TEXT DEFAULT 'general',
    project        TEXT DEFAULT '',
    tags           TEXT DEFAULT '',
    device         TEXT DEFAULT 'both',
    trust_score    REAL DEFAULT 0.5,
    status         TEXT DEFAULT 'current',
    superseded_by  TEXT DEFAULT '',
    used_count     INTEGER DEFAULT 0,
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_status ON facts(status);
CREATE TABLE IF NOT EXISTS embeddings (
    content_hash TEXT PRIMARY KEY,
    model        TEXT NOT NULL,
    vec          BLOB NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS facts_fts USING fts5(
    content, content='facts', content_rowid='rowid'
);
"""


@contextmanager
def _db():
    CORTEX_HOME.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


@contextmanager
def _facts_lock(timeout: float = 30.0):
    """Cross-process lock around facts.jsonl.

    Two agents writing at once is the normal case, not the edge case: a cron
    job and an interactive session share this file.
    """
    CORTEX_HOME.mkdir(parents=True, exist_ok=True)
    fh = open(FACTS_LOCK, "a+b")
    deadline = time.time() + timeout
    try:
        while True:
            try:
                if fcntl is not None:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                elif msvcrt is not None:
                    fh.seek(0)
                    msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except OSError:
                if time.time() > deadline:
                    raise TimeoutError(f"facts.jsonl locked for >{timeout}s")
                time.sleep(0.1)
        yield
    finally:
        try:
            if fcntl is not None:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            elif msvcrt is not None:
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
        fh.close()


# -------------------------------------------------------------- embeddings --
_MODEL = None


def _model():
    """Load the embedding model once, or return None if unavailable.

    Never raise: a machine without the optional deps must still be able to
    read and write memory, only with lexical search.
    """
    global _MODEL
    if _MODEL is not None:
        return _MODEL or None
    try:
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from fastembed import TextEmbedding

            _MODEL = TextEmbedding(model_name=MODEL_NAME)
    except Exception:
        _MODEL = False
        return None
    return _MODEL


def _embed(texts: list[str]):
    model = _model()
    if model is None:
        return None
    import numpy as np

    vecs = np.array(list(model.embed(texts)), dtype=np.float32)
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vecs / norms


def _sync_embeddings(conn: sqlite3.Connection, verbose: bool = False) -> int:
    rows = conn.execute(
        "SELECT f.content_hash, f.content FROM facts f "
        "LEFT JOIN embeddings e ON e.content_hash = f.content_hash AND e.model = ? "
        "WHERE e.content_hash IS NULL",
        (MODEL_NAME,),
    ).fetchall()
    if not rows:
        return 0
    vecs = _embed([r["content"] for r in rows])
    if vecs is None:
        if verbose:
            print("  (no embedding backend; lexical search only)", file=sys.stderr)
        return 0
    conn.executemany(
        "INSERT OR REPLACE INTO embeddings(content_hash, model, vec) VALUES (?,?,?)",
        [(r["content_hash"], MODEL_NAME, v.tobytes()) for r, v in zip(rows, vecs)],
    )
    return len(rows)


# ------------------------------------------------------------------ jsonl ---
def _read_jsonl() -> list[dict]:
    if not FACTS_JSONL.exists():
        return []
    out, seen = [], set()
    for line in FACTS_JSONL.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue  # a half-written line from a crashed writer: skip, keep the rest
        content = (rec.get("content") or "").strip()
        if not content:
            continue
        # Dedup by CONTENT, not by line: `merge=union` on a git merge legitimately
        # produces the same fact twice, once per branch.
        h = _hash(content)
        if h in seen:
            continue
        seen.add(h)
        rec["content"] = content
        rec["content_hash"] = h
        out.append(rec)
    return out


def _write_jsonl(records: list[dict]) -> None:
    tmp = FACTS_JSONL.with_suffix(".jsonl.tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
    tmp.replace(FACTS_JSONL)


def _rec_from_row(row: sqlite3.Row) -> dict:
    return {
        "content": row["content"],
        "category": row["category"],
        "project": row["project"],
        "tags": row["tags"],
        "device": row["device"],
        "trust_score": row["trust_score"],
        "status": row["status"],
        "superseded_by": row["superseded_by"],
        "used_count": row["used_count"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _upsert(conn: sqlite3.Connection, rec: dict) -> None:
    content = rec["content"].strip()
    h = _hash(content)
    now = _now()
    conn.execute(
        """INSERT INTO facts (content_hash, content, category, project, tags, device,
                              trust_score, status, superseded_by, used_count,
                              created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(content_hash) DO UPDATE SET
               category=excluded.category, project=excluded.project,
               tags=excluded.tags, device=excluded.device,
               trust_score=excluded.trust_score, status=excluded.status,
               superseded_by=excluded.superseded_by,
               used_count=MAX(facts.used_count, excluded.used_count),
               updated_at=excluded.updated_at""",
        (
            h,
            content,
            rec.get("category", "general"),
            rec.get("project", ""),
            rec.get("tags", ""),
            rec.get("device", "both"),
            float(rec.get("trust_score", 0.5)),
            rec.get("status", "current"),
            rec.get("superseded_by", ""),
            int(rec.get("used_count", 0)),
            rec.get("created_at", now),
            now,
        ),
    )
    rowid = conn.execute(
        "SELECT rowid FROM facts WHERE content_hash = ?", (h,)
    ).fetchone()["rowid"]
    conn.execute("INSERT OR REPLACE INTO facts_fts(rowid, content) VALUES (?,?)",
                 (rowid, content))


# ---------------------------------------------------------------- ranking ---
def _lexical_scores(conn: sqlite3.Connection, query: str, hashes: list[str]) -> dict:
    """FTS5 bm25, normalised to 0..1. Only used above LEX_FLOOR."""
    terms = [t for t in re.findall(r"[\w.]{3,}", query) if t]
    if not terms:
        return {}
    match = " OR ".join(f'"{t}"' for t in terms)
    try:
        rows = conn.execute(
            "SELECT f.content_hash AS h, bm25(facts_fts) AS s "
            "FROM facts_fts JOIN facts f ON f.rowid = facts_fts.rowid "
            "WHERE facts_fts MATCH ? ORDER BY s LIMIT 200",
            (match,),
        ).fetchall()
    except sqlite3.OperationalError:
        return {}
    if not rows:
        return {}
    scores = {r["h"]: -float(r["s"]) for r in rows}  # bm25: lower is better
    lo, hi = min(scores.values()), max(scores.values())
    span = (hi - lo) or 1.0
    return {h: (s - lo) / span for h, s in scores.items()}


def _rank(conn, query: str, limit: int, project: str | None, category: str | None):
    rows = conn.execute("SELECT * FROM facts WHERE status = 'current'").fetchall()
    if not rows:
        return [], "none"

    hashes = [r["content_hash"] for r in rows]
    lex = _lexical_scores(conn, query, hashes)

    mode = "lexical"
    sem = {}
    qv = _embed([query])
    if qv is not None:
        import numpy as np

        stored = {
            r["content_hash"]: np.frombuffer(r["vec"], dtype=np.float32)
            for r in conn.execute(
                "SELECT content_hash, vec FROM embeddings WHERE model = ?", (MODEL_NAME,)
            )
        }
        if stored:
            mode = "semantic"
            q = qv[0]
            for h in hashes:
                v = stored.get(h)
                if v is not None and v.shape[0] == q.shape[0]:
                    sem[h] = float(q @ v)

    dev = _device()
    scored = []
    for r in rows:
        h = r["content_hash"]
        lx = lex.get(h, 0.0)
        s = sem.get(h, lx if mode == "lexical" else 0.0)
        s += W_LEXICAL * lx * (lx > LEX_FLOOR)
        s += W_TRUST * float(r["trust_score"])
        # Device is a WEAK tiebreak and never a filter. Measured: at a 0.55
        # multiplier the right fact fell 54 positions. The cause is conceptual -
        # `device` records WHERE A PATH EXISTS, not where the knowledge matters.
        # Only absolute paths are genuinely machine-specific.
        if r["device"] not in ("both", "", dev):
            s -= DEVICE_PENALTY
        if project and project.lower() not in (r["project"] or "").lower():
            s *= 0.5
        if category and r["category"] != category:
            s *= 0.4
        scored.append((s, r))
    scored.sort(key=lambda t: t[0], reverse=True)
    return scored[:limit], mode


# --------------------------------------------------------------- commands ---
def cmd_add(args) -> int:
    content = args.content.strip()
    if not content:
        print("empty fact", file=sys.stderr)
        return 2
    rec = {
        "content": content,
        "category": args.category,
        "project": args.project or "",
        "tags": args.tags or "",
        "device": args.device or _device(),
        "trust_score": args.trust,
        "status": "current",
        "superseded_by": "",
        "used_count": 0,
        "created_at": _now(),
        "updated_at": _now(),
    }
    with _facts_lock():
        records = _read_jsonl()
        if any(r["content_hash"] == _hash(content) for r in records):
            print(f"already known: {_short(_hash(content))}")
            return 0
        records.append(rec)
        _write_jsonl([{k: v for k, v in r.items() if k != "content_hash"} for r in records])
    with _db() as conn:
        _upsert(conn, rec)
        _sync_embeddings(conn)
    print(f"added {_short(_hash(content))}  [{rec['category']}]")
    return 0


def cmd_supersede(args) -> int:
    """Replace a fact instead of editing it. History is the point.

    An agent that silently rewrites what it believed cannot be audited, and a
    wrong fact that was never marked wrong comes back through any sync.
    """
    with _facts_lock():
        records = _read_jsonl()
        target = next(
            (r for r in records if r["content_hash"].startswith(args.hash)), None
        )
        if target is None:
            print(f"no fact starting with {args.hash}", file=sys.stderr)
            return 1
        new_content = args.content.strip()
        new_hash = _hash(new_content)
        target["status"] = "superseded"
        target["superseded_by"] = new_hash
        target["updated_at"] = _now()
        new_rec = {
            "content": new_content,
            "category": target.get("category", "general"),
            "project": target.get("project", ""),
            "tags": target.get("tags", ""),
            "device": target.get("device", "both"),
            "trust_score": float(target.get("trust_score", 0.5)),
            "status": "current",
            "superseded_by": "",
            "used_count": 0,
            "created_at": _now(),
            "updated_at": _now(),
        }
        records.append(dict(new_rec, content_hash=new_hash))
        _write_jsonl([{k: v for k, v in r.items() if k != "content_hash"} for r in records])
    with _db() as conn:
        _upsert(conn, target)
        _upsert(conn, new_rec)
        _sync_embeddings(conn)
    print(f"{_short(target['content_hash'])} superseded by {_short(new_hash)}")
    return 0


def cmd_search(args) -> int:
    with _db() as conn:
        _sync_embeddings(conn)
        hits, mode = _rank(conn, args.query, args.n, args.project, args.category)
        if not hits:
            print("no facts stored yet" if not _read_jsonl() else "no match")
            return 0
        print(f"search: {args.query!r}   ({mode}, device {_device()})")
        print("-" * 72)
        for i, (score, r) in enumerate(hits, 1):
            print(f"  {i}. [{score:.3f}] {r['content']}")
            meta = f"{r['category']} · trust {r['trust_score']:.2f} · used {r['used_count']}x"
            if r["project"]:
                meta += f" · {r['project']}"
            print(f"     {_short(r['content_hash'])} · {meta}")
        conn.executemany(
            "UPDATE facts SET used_count = used_count + 1 WHERE content_hash = ?",
            [(r["content_hash"],) for _, r in hits],
        )
    return 0


def cmd_feedback(args) -> int:
    delta = 0.1 if args.good else -0.1
    with _db() as conn:
        row = conn.execute(
            "SELECT * FROM facts WHERE content_hash LIKE ?", (args.hash + "%",)
        ).fetchone()
        if row is None:
            print(f"no fact starting with {args.hash}", file=sys.stderr)
            return 1
        new_trust = max(0.0, min(1.0, float(row["trust_score"]) + delta))
        conn.execute(
            "UPDATE facts SET trust_score = ?, updated_at = ? WHERE content_hash = ?",
            (new_trust, _now(), row["content_hash"]),
        )
        rec = dict(_rec_from_row(row), trust_score=new_trust)
    with _facts_lock():
        records = _read_jsonl()
        for r in records:
            if r["content_hash"] == row["content_hash"]:
                r["trust_score"] = new_trust
                r["updated_at"] = _now()
        _write_jsonl([{k: v for k, v in r.items() if k != "content_hash"} for r in records])
    print(f"{_short(row['content_hash'])} trust -> {new_trust:.2f}")
    return 0


def cmd_rebuild(args) -> int:
    """Drop the derived DB and rebuild it from the text. The safety net.

    After any git merge, this is the only recovery step needed - which is the
    whole reason the truth lives in jsonl.
    """
    if DB_PATH.exists():
        DB_PATH.unlink()
    records = _read_jsonl()
    with _db() as conn:
        for rec in records:
            _upsert(conn, rec)
        n = _sync_embeddings(conn, verbose=True)
    print(f"rebuilt {len(records)} facts from {FACTS_JSONL} ({n} embedded)")
    return 0


def cmd_export(args) -> int:
    with _db() as conn:
        rows = conn.execute("SELECT * FROM facts ORDER BY created_at").fetchall()
    with _facts_lock():
        _write_jsonl([_rec_from_row(r) for r in rows])
    print(f"exported {len(rows)} facts to {FACTS_JSONL}")
    return 0


def cmd_stats(args) -> int:
    records = _read_jsonl()
    with _db() as conn:
        db_n = conn.execute("SELECT COUNT(*) c FROM facts").fetchone()["c"]
        cur = conn.execute(
            "SELECT COUNT(*) c FROM facts WHERE status='current'"
        ).fetchone()["c"]
        emb = conn.execute("SELECT COUNT(*) c FROM embeddings").fetchone()["c"]
        cats = conn.execute(
            "SELECT category, COUNT(*) c FROM facts WHERE status='current' "
            "GROUP BY category ORDER BY c DESC"
        ).fetchall()
    print(f"jsonl {len(records)} · db {db_n} · current {cur} · embedded {emb}")
    print(f"backend: {'semantic' if _model() else 'lexical only (pip install fastembed numpy)'}")
    for c in cats:
        print(f"  {c['category']:<16} {c['c']}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="cortex", description=__doc__.split("\n")[1])
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add", help="store one atomic fact")
    a.add_argument("content")
    a.add_argument("--category", default="general")
    a.add_argument("--project", default="")
    a.add_argument("--tags", default="")
    a.add_argument("--device", default="")
    a.add_argument("--trust", type=float, default=0.5)
    a.set_defaults(func=cmd_add)

    s = sub.add_parser("search", help="semantic search over current facts")
    s.add_argument("query")
    s.add_argument("-n", type=int, default=5)
    s.add_argument("--project", default=None)
    s.add_argument("--category", default=None)
    s.set_defaults(func=cmd_search)

    sp = sub.add_parser("supersede", help="replace a fact, keeping the old one")
    sp.add_argument("hash")
    sp.add_argument("content")
    sp.set_defaults(func=cmd_supersede)

    f = sub.add_parser("feedback", help="nudge a fact's trust score")
    f.add_argument("hash")
    g = f.add_mutually_exclusive_group(required=True)
    g.add_argument("--good", action="store_true")
    g.add_argument("--bad", action="store_true")
    f.set_defaults(func=cmd_feedback)

    for name, fn, helptext in (
        ("rebuild", cmd_rebuild, "rebuild the DB from facts.jsonl"),
        ("export", cmd_export, "write the DB back out to facts.jsonl"),
        ("stats", cmd_stats, "counts and backend in use"),
    ):
        sp2 = sub.add_parser(name, help=helptext)
        sp2.set_defaults(func=fn)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
