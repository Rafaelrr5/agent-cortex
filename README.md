# agent-cortex

Long-term memory and working discipline for coding agents.

An agent's context window is short-term memory. Everything it learned about your
stack dies when the session ends, so you explain the same procedure again next
week. This repo is the part that survives: a single-file memory store, plus 22
procedures that encode how the work is actually checked.

Nothing here is a framework. Every file is something I run, extracted from a
daily setup with everything client-specific removed, and each one exists because
a particular failure cost me an afternoon.

---

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
truth and goes in git with `merge=union`. The SQLite database and the vectors are
derived and gitignored. A jsonl → db → search roundtrip returns bit-identical
scores, and `UNIQUE(content)` absorbs merge duplicates on its own. This is what
makes syncing across machines safe: a live SQLite file in git corrupts through
its WAL sidecars, but text always rebuilds.

**Embeddings lead the ranking; lexical search is only a tiebreak.** Measured
recall@5 over a 40-query set:

| Ranking | Exact token | Paraphrase | recall@5 |
|---|---|---|---|
| Lexical only (FTS5 bm25) | 100% | 0% | 57% |
| Embeddings only | 100% | 43% | **100%** |
| Naive RRF fusion | 100% | 14% | worse than either |

The fusion row is the interesting one. FTS5 is confidently wrong on paraphrase,
and a rank-based fusion has no way to discount that confidence, so adding a
second signal made the system worse. Lexical now enters only above a 0.85 floor,
as a tiebreak for exact identifiers like `createServiceRoleClient`, at weight
0.15.

**Facts are superseded, never edited.** A wrong fact that was silently rewritten
cannot be audited, and it returns through the next sync. `supersede` keeps the
old row, marks it, and points it at the replacement.

There is also a lesson in what the ranking *does not* do: the machine a fact came
from is a weak tiebreak, worth −0.02, and never a filter. At a 0.55 multiplier,
the correct fact for a query fell 54 positions. The cause is conceptual: the
device field records *where a path exists*, not where the knowledge matters. Only
absolute paths are genuinely machine-specific.

Without `fastembed` and `numpy` installed, search degrades to lexical and says
so. It never crashes for a missing optional dependency.

---

## `skills/` — 22 procedures

Markdown documents, readable by a human and loadable by any agent that supports
skill files. They encode the checks, not the happy path.

### Verification and judgement

| Skill | What it is for |
|---|---|
| [`measurement-validity`](skills/measurement-validity) | Before trusting a number that will drive a decision, check the instrument that produced it. |
| [`recall-and-claim-verification`](skills/recall-and-claim-verification) | Asked to resupply something you produced before? Verify it still exists and still says that, rather than recalling it. |
| [`delegated-agent-supervision`](skills/delegated-agent-supervision) | Supervising a dispatched agent: fence the scope, then verify against the tree instead of the agent's report. |
| [`worktree-analysis`](skills/worktree-analysis) | Read a long-dirty tree, cluster it by time and authorship, and decide *whether* each cluster deserves a commit at all. Ships a forensics script. |
| [`commit-work`](skills/commit-work) | Turn a dirty tree into clean commits written in the voice that repo's log already speaks, learned from the log each run. |

### Delegation and parallel work

| Skill | What it is for |
|---|---|
| [`delegate-coding-task`](skills/delegate-coding-task) | Fence a coding task before handing it over: allowed files, forbidden files, and an explicit order to stop outside the fence. |
| [`parallel-agent-fanout`](skills/parallel-agent-fanout) | Fan one job out to several concurrent agents on a single repo without them overwriting each other. |
| [`agent-config-sync`](skills/agent-config-sync) | Share hooks and scheduled jobs between machines without a pull on one silently breaking the other. |

### Deployment and infrastructure

| Skill | What it is for |
|---|---|
| [`static-site-vps-deploy`](skills/static-site-vps-deploy) | Ship a static site to nginx on a VPS, with a backup and a smoke test that actually loads the page. |
| [`github-pages-deploy`](skills/github-pages-deploy) | Publish a static site or client-side game to GitHub Pages, including the path traps. |
| [`domain-dns-cutover`](skills/domain-dns-cutover) | Move a domain to new hosting and verify at the authoritative nameserver, not at your resolver's cache. |
| [`custom-domain-email`](skills/custom-domain-email) | Own-domain email: SPF, DKIM, DMARC, and diagnosing why mail lands in spam. |
| [`supabase-auth-debugging`](skills/supabase-auth-debugging) | Login, OAuth and email-link failures, diagnosed by symptom rather than by guesswork. |

### Windows

| Skill | What it is for |
|---|---|
| [`windows-background-process-hygiene`](skills/windows-background-process-hygiene) | Console windows flashing on your desktop: find the real spawn chain and make it windowless. Includes the debugging narrative, wrong first hypothesis included. |
| [`windows-performance-tuning`](skills/windows-performance-tuning) | A slow Windows box, tuned along the whole latency chain instead of one setting. |

### Frontend, design and stakeholders

| Skill | What it is for |
|---|---|
| [`frontend-render-performance`](skills/frontend-render-performance) | A UI that gets slower the longer it runs: find the O(n) work hiding in an event handler. |
| [`brand-retrofit`](skills/brand-retrofit) | Apply a brand to code that already exists, without a rewrite and without a screenshot lying to you. |
| [`clickable-concept-prototype`](skills/clickable-concept-prototype) | A clickable phone-frame HTML mockup, built to get a decision out of a non-technical stakeholder. |
| [`stakeholder-decision-elicitation`](skills/stakeholder-decision-elicitation) | Get an actual decision from a non-technical owner over chat, instead of another "looks good". |

### Getting started and reading code

| Skill | What it is for |
|---|---|
| [`new-project-scaffolding`](skills/new-project-scaffolding) | Start a new project inheriting the conventions the rest of your work already uses. |
| [`codebase-inspection`](skills/codebase-inspection) | Size up an unfamiliar codebase: lines, languages, test-to-source ratio. |
| [`blocked-page-recovery`](skills/blocked-page-recovery) | A fetch that returns 403, 429, a paywall or a bot wall, and what to try in what order. |

The thread running through all of them: **an agent's closing message is a
self-report, not evidence.** "Implemented and tested" routinely means one file
written and nothing run. Every skill ends with a verification section naming the
command whose real output would prove the claim.

---

## Install

```bash
git clone https://github.com/Rafaelrr5/agent-cortex
cd agent-cortex
python cortex.py stats                 # works immediately, lexical search
pip install fastembed numpy            # optional: upgrades search to semantic
python cortex.py rebuild               # embeds what is already stored
```

`CORTEX_HOME` (default `~/.cortex`) decides where `facts.jsonl` and the database
live. Point it at a git repo if you want memory to sync between machines, and set
`merge=union` on `facts.jsonl` in `.gitattributes`.

Skills: copy the folders you want into wherever your agent loads skills from.
They are plain markdown with YAML frontmatter and no runtime dependency on this
repo, apart from the two Python scripts they call by path.

---

## Articles

Short pieces on working with agents, each anchored to something in this repo you
can read and run. Full index in [`articles/`](articles).

| Article | The question it answers |
|---|---|
| [Implemented and tested is not evidence](articles/implemented-and-tested-is-not-evidence.md) | Why an agent's closing summary cannot be trusted, and what to read instead |
| [Why your agent forgets everything](articles/why-your-agent-forgets-everything.md) | Why every session starts from zero, and what a memory store has to get right |
| [Five agents, one repo](articles/five-agents-one-repo.md) | Running concurrent agents on one codebase without them overwriting each other |
| [Why brand skills matter more than brand guidelines](articles/why-brand-skills-matter.md) | The business argument for executable brand rules: review cost, not aesthetics |

## Scope

Extracted from a setup I run daily, with everything tied to an employer, a client
or a private project removed. What is left is the part that generalises.

Issues and PRs welcome, particularly measurements that contradict the table
above. The ranking decisions here were made by running the queries, and should be
revised the same way.

MIT.
