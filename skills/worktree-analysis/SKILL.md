---
name: worktree-analysis
description: "Read a dirty tree, decide if commits are warranted, commit."
version: 1.0.0
author: Rafael Rocha Ribeiro (github.com/Rafaelrr5)
license: MIT
platforms: [linux, macos, windows]
---

# Worktree Analysis

Read a dirty working tree, work out **who did what and when**, judge whether the
work is worth committing at all, and commit only the parts that pass that judgement
— each with a message that says what actually changed and why.

The judgement is the point. `commit-work` already knows how to split a tree into
clean commits; this skill decides **whether it should**, and hands the survivors to
that skill's message discipline. A tree can be dirty for reasons that must NOT
become commits: build artifacts, someone else's abandoned experiment, a half-migration
that doesn't build, a vendored upstream clone.

## When to Use

- The user asks what a dirty repo contains, or says "commit it if it makes sense".
- An agent session finished and you need to know what survived, and whether it
  belongs in history.
- A tree has been dirty long enough that nobody remembers what is in it.
- Don't use for: a tree you already understand and just want split (`commit-work`
  alone), pushing or opening PRs, or reconciling two agents' branches.

## Prerequisites

- `git` on PATH.
- Optional but valuable: Claude Code transcripts in `~/.claude/projects/<slug>/*.jsonl`.
  Without them, clustering still works from mtime alone; authorship gets less certain.

## Autonomy contract

Run Steps 1-4 (analysis) without asking — reading is free.

**Committing is a separate decision.** Commit without asking only when ALL hold:
the cluster is one coherent piece of work; it builds/tests green; nothing in it is
generated, secret, or vendored; and its intent is recoverable from transcript or diff.

Stop and ask when any of these is true:

- more than one cluster qualifies and they are **not** the same task (the user may
  want them ordered, or only one of them);
- the work does not build, or a test fails and the failure is inside the cluster;
- a file has no explanation in transcript or diff;
- the cluster mixes the user's own work with an agent's (see Step 3 — this is common
  and the user usually wants a say);
- HEAD is detached, or the repo has no commits at all;
- anything matches a secret pattern.

Never commit a cluster you would have to describe as "assorted changes". That is the
signal that the analysis is not finished, not that the message needs to be vaguer.

## Step 1 — Forensics: cluster the tree by time and authorship

```bash
python <skill_dir>/scripts/worktree_forensics.py <repo>
```

The script groups every dirty path into **temporal clusters** (default: a gap over
90 min starts a new cluster), then cross-references each cluster's window against
Claude Code sessions that touched the repo, and flags generated artifacts and
possible secrets. `--json` for machine-readable output; `--gap-min N` to retune.

Read the output before running any git command of your own. It answers the question
`git status` cannot: *is this one piece of work, or five unrelated ones?*

A cluster the script marks as having no session in its window is the
user's own hand-written work. A cluster with a session is agent work, and the session
id lets you recover the exact prompt in Step 3.

**Trap:** mtime is not authorship. A file the user edited and an agent later
reformatted carries only the LAST touch. Treat clustering as a strong hypothesis to
confirm against the diff, never as proof.

## Step 2 — Read the actual diff, per cluster

```bash
git -C <repo> diff --stat -- <paths of one cluster>
git -C <repo> diff -- <one file>
git -C <repo> log --oneline -5
```

For untracked files, read the file. Per cluster, answer in one sentence: **what
claim does this work make?** If you cannot, the cluster is not committable yet —
say so instead of writing a vague message.

Check whether the cluster is self-contained: does it reference symbols, files, or
migrations that live in ANOTHER cluster? If yes, the two are one commit, or neither
is ready.

**Static reading is a hypothesis, not proof.** A cluster can look self-contained —
every import resolving to a file that is already committed — and still fail to build
alone, because a *test* in it references a field that another cluster added to a
shared type. Prove isolation empirically before promising it (Step 4a).

## Step 3 — Recover intent

```
python <commit-work>/scripts/recover_intent.py <repo> --limit 50
```

That prints the user's prompts. For agent clusters, also read the session transcript
itself (`~/.claude/projects/<slug>/<session-id>.jsonl`) to see what the agent *did*
versus what it *claimed*.

The agent's closing message is a self-report — useful for intent, worthless as
evidence. Verify its claims against the tree (Step 4). Where they diverge, the tree
wins and the divergence goes in the report.

## Step 4 — Decide, per cluster: commit / leave / flag

Read the repo's own contract first (`CLAUDE.md`, `AGENTS.md`, `CONTRIBUTING.md`),
then the build/test commands it declares. Run only what the cluster touches:

```bash
npm run build && npm test -- --run     # or pytest, make, cargo — read, never guess
```

A pre-existing failure is not this cluster's fault. Prove it before excusing it:
`git stash` the cluster, re-run, restore. If it fails clean too, it is pre-existing —
say so with that evidence, do not merely assert it.

## Step 4a — Prove isolation in a scratch worktree (do this before promising a commit)

Never test "cluster N alone" by mutating the user's tree — no `stash`, no `checkout`
of their files. Build the isolated candidate in a throwaway worktree at HEAD:

```bash
git -C <repo> worktree add --detach "$SCRATCH/verify" HEAD
# link deps instead of reinstalling (Windows junction needs no admin):
python -c "import subprocess;subprocess.run(['cmd','/c','mklink','/J',r'<scratch>\\frontend\\node_modules',r'<repo>\\frontend\\node_modules'])"
git -C <repo> diff -- <cluster paths> > "$SCRATCH/verify/c.patch"
cd "$SCRATCH/verify" && git apply c.patch     # plus: copy the cluster's untracked files
npm run build && npm test -- --run            # whatever the repo declares
git -C <repo> worktree remove --force "$SCRATCH/verify"
```

A green run proves the cluster stands alone. A red run is the *finding*: report the
exact missing symbol and which other cluster introduces it, then treat the two as one
commit or leave both. Confirm afterwards that the user's tree still shows the same
dirty count it started with.

Windows notes: `mklink` output is OEM-encoded and can raise `UnicodeDecodeError` in
Python — check `os.path.isdir(link)` for success rather than trusting the return
text, and never chain the check with `&&` after a failed `cmd //c`, which reports a
false positive.

Verdict per cluster:

| Verdict | When | Action |
|---|---|---|
| **COMMIT** | coherent, builds, intent known, nothing generated/secret | hand to `commit-work` Step 5 for the message |
| **LEAVE** | generated artifact, vendored clone, ignored output | report as deliberately left, propose `.gitignore` if it recurs |
| **FLAG** | doesn't build, unexplained file, mixes owners, possible secret | report with the specific question that would unblock it |

Print the verdict table before touching the index. That table IS the deliverable
when nothing qualifies — a run that commits nothing and explains why is a success.

## Step 5 — Commit the survivors

Load `commit-work` and follow its Steps 2, 5, 6, 7 (repo voice, message body,
verification, staging). Do not reimplement them here. Key inherited rules: explicit
paths only, never `git add -A`, message via `git commit -F <file>`, and the
`Co-Authored-By` trailer only when an agent did the work, spelled the way that repo's
log already spells it.

One addition specific to this skill: when a cluster came from a Claude Code session,
the body should state what was **verified** versus what the agent merely claimed.
A reviewer reading history later needs to know which lines were actually exercised.

## Step 6 — Report

Give the user, in this order:

1. The cluster table: window, age, owner (agent id or MANUAL), verdict.
2. What was committed — hashes and subjects.
3. What was left behind and why, with the `.gitignore` suggestion when it applies.
4. Anything the analysis found that the user did not know: work older than they
   thought, a divergence between an agent's report and the tree, a secret at risk.

Then stop. Never push.

## Pitfalls

- **A long-dirty tree is usually several tasks, not one.** Committing it as one
  change destroys the only chance to describe any of them. Cluster first.
- **`mtime` lies after a checkout, a stash pop, or a formatter run.** Cross-check
  against the diff and the transcript window.
- **An untracked directory is one line in `git status`** (`?? dir/`) but many files.
  The forensics script expands it; `git status` alone will undercount.
- **Generated files reappear dirty forever.** `graphify-out/`, `*.tsbuildinfo`,
  `dist/`, lockfiles under tooling churn. They are never a commit; they are a
  `.gitignore` gap.
- **On Windows, do not pass `--format='%h %s'` through `shell=True`.** cmd.exe does
  not honour single quotes and the format comes back empty or literal. Pass argv
  lists (the forensics script does).
- **A test that fails before your change is not yours to fix silently.** Prove it
  pre-existing with a stash, or fix it in its own commit.
- **The user's abandoned experiment is not yours to commit.** A MANUAL cluster months
  old, with no matching prompt, is a question — not a commit.
- **An agent's cluster often depends on the user's uncommitted work.** The agent
  developed against the dirty tree, so its code compiles *there* and nowhere else.
  This is invisible in the diff and in the import graph; only a scratch-worktree build
  (Step 4a) exposes it. When it happens, the agent's work cannot ship first: either
  both clusters go together, or the user decides.

## Verification

The run succeeded when: every dirty path from Step 1 appears in the Step 6 report as
committed, left, or flagged; no commit contains a file from two clusters; each commit
subject states one claim; the working tree afterwards holds exactly the paths you said
you were leaving; and nothing was pushed.
