# agent-cortex

Long-term memory and working discipline for coding agents.

An agent's context window is short-term memory. Everything it learned about your
stack dies when the session ends, so you explain the same procedure again next
week. This repo is the part that survives: a single-file memory store, plus the
skills that keep delegated work honest.

Nothing here is a framework. It is five files you can read in an afternoon, each
carrying a lesson that was paid for by a bug.

## `cortex.py` — memory that outlives the session

One file, Python standard library, SQLite. Embeddings optional.

```bash
python cortex.py add "Scheduled jobs written as .sh fail silently on Windows: \
the scheduler spawns with a narrow PATH and cannot find bash" --category gotcha

python cortex.py search "my cron job does nothing and reports no error" -n 5
python cortex.py supersede <hash> "the corrected version of that fact"
python cortex.py stats
```

Three decisions make it work, and all three were measured rather than assumed.

**Memory travels as text, never as a binary.** `facts.jsonl` is the source of
truth and goes in git with `merge=union`. The SQLite database and the vectors
are derived and gitignored. A jsonl → db → search roundtrip returns bit-identical
scores, and `UNIQUE(content)` absorbs merge duplicates on its own. This is what
makes syncing across machines safe: you must never put a live SQLite file in git,
because its WAL sidecars corrupt, but you can always rebuild it from the text.

**Embeddings lead the ranking; lexical search is only a tiebreak.** Measured
recall@5 over a 40-query set:

| Ranking | Exact token | Paraphrase | recall@5 |
|---|---|---|---|
| Lexical only (FTS5 bm25) | 100% | 0% | 57% |
| Embeddings only | 100% | 43% | **100%** |
| Naive RRF fusion | 100% | 14% | worse than either |

The fusion result is the interesting one. FTS5 is confidently wrong on
paraphrase, and a rank-based fusion has no way to discount that confidence, so
adding a second signal made the system worse. Lexical now enters only above a
0.85 floor, as a tiebreak for exact identifiers like
`createServiceRoleClient`, at weight 0.15.

**Facts are superseded, never edited.** A wrong fact that was silently rewritten
cannot be audited, and it comes back through the next sync. `supersede` keeps the
old row, marks it, and points it at the replacement.

There is also a lesson encoded in what the ranking *does not* do: the machine a
fact came from is a weak tiebreak, worth −0.02, and never a filter. When it was a
0.55 multiplier, the correct fact for a query fell 54 positions. The cause is
conceptual, not numerical: the device field records *where a path exists*, not
where the knowledge matters. Only absolute paths are genuinely machine-specific.

Without `fastembed` and `numpy` installed, search degrades to lexical and says
so. It never crashes for a missing optional dependency.

## `skills/` — the working discipline

Markdown procedures, readable by a human and loadable by any agent that supports
skill files. They encode the checks, not the happy path.

| Skill | What it is for |
|---|---|
| [`commit-work`](skills/commit-work) | Turn a dirty tree into clean commits written in the voice that repo's log already speaks. Learns the convention from the log every run instead of assuming one. |
| [`worktree-analysis`](skills/worktree-analysis) | Read a long-dirty tree, cluster it by time and authorship, and decide *whether* each cluster deserves a commit at all. Ships a forensics script. |
| [`delegate-coding-task`](skills/delegate-coding-task) | Fence a coding task before handing it to another agent, then verify the result against the tree rather than against the agent's own report. |
| [`agent-config-sync`](skills/agent-config-sync) | Share hooks and scheduled jobs between machines without a pull on one machine silently breaking the other. |

The thread running through all four: **an agent's closing message is a
self-report, not evidence.** "Implemented and tested" routinely means one file
written and nothing run. Every skill here ends with a verification section
naming the command whose real output would prove the claim.

## Install

```bash
git clone https://github.com/Rafaelrr5/agent-cortex
cd agent-cortex
python cortex.py stats                 # works immediately, lexical search
pip install fastembed numpy            # optional: upgrades search to semantic
python cortex.py rebuild               # embeds what is already stored
```

`CORTEX_HOME` (default `~/.cortex`) decides where `facts.jsonl` and the database
live. Point it at a git repo if you want memory to sync between machines, and
set `merge=union` on `facts.jsonl` in `.gitattributes`.

Skills: copy the folders you want into wherever your agent loads skills from.
They are plain markdown with YAML frontmatter and no runtime dependency on this
repo, apart from the two Python scripts they call by path.

## Scope

This is extracted from a setup I actually run daily, with everything specific to
an employer, a client or a private project removed. What is left is the part that
generalises. Issues and PRs welcome, particularly measurements that contradict
the table above — the ranking decisions here were made by running the queries,
and should be revised the same way.

MIT.
