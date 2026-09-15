---
name: commit-work
description: Split a dirty tree into clean commits in this repo's voice.
version: 1.0.0
author: Rafael Rocha Ribeiro (github.com/Rafaelrr5)
license: MIT
platforms: [linux, macos, windows]
---

# Commit Work

Turn a dirty working tree — usually a worktree holding several unrelated pieces of
work at once — into a sequence of clean, reviewable commits written in the voice the
target repo already speaks. The skill learns that voice from the repo's own log every
run, so it works in any project; it never pushes, never rewrites pushed history, and
never invents a rationale for a file it cannot explain.

## When to Use

- The user mentions this skill, says "commit", "commita isso", "sobe esse trabalho",
  or finishes a task with `git status` not clean.
- A worktree accumulated changes from more than one task and needs splitting.
- Don't use for: pushing, opening PRs, releases (`github-pr-workflow`), resolving a
  merge between two agents' branches (`merge-reconciler`), or rewriting a commit that
  is already on a remote.

## Prerequisites

- `git` on PATH and a repo path. Nothing else is required.
- Optional, for intent recovery: agent transcripts at `~/.claude/history.jsonl` and
  `~/.claude/projects/<slug>/*.jsonl`.

## How to Run

Load the skill and execute Step 0 through Step 8 in order, in the same turn, without
checking back in. The only input needed is which project, and only when the current
directory does not already answer it.

```bash
git -C <repo> status --porcelain=v1
```

### Autonomy contract

Proceed without asking. Stop and ask only when one of these is true:

- a changed file has no explanation in the diff or the transcripts;
- a staged or changed file looks like a secret (`.env*`, key, token, credential dump);
- HEAD is detached (a commit there is dangling — see Worktrees);
- the requested project resolves to more than one dirty checkout;
- the path is not a git repo at all.

## Step 0 — Locate the repo and the worktree

```bash
git rev-parse --is-inside-work-tree
git rev-parse --show-toplevel
git rev-parse --git-dir --git-common-dir
git worktree list
git branch --show-current
```

- `--git-dir` different from `--git-common-dir` means **this is a linked worktree**:
  its own HEAD, index and stash; hooks, config, refs and objects shared with the main
  checkout.
- No repo in the current directory and the user named a project: resolve the name
  against the sibling repo roots (`~/repos`, `~/projects`, ...). If
  several candidates match, pick the **only dirty one**; if more than one is dirty,
  ask which.
- Commit only paths inside `--show-toplevel` of THIS worktree. Never stage a file
  living in a sibling worktree, even when it is the same repo.

## Step 1 — Orient

```bash
git status --porcelain=v1
git diff --stat
git diff --cached --stat
```

Something already staged: decide whether it belongs to commit 1, or `git reset` it
(index only — never `--hard`).

## Step 2 — Learn this repo's voice before writing anything

Do not assume the convention. Read it:

```bash
git log --format='%h|%an|%ad|%s' --date=short -40
git log --format='===%h===%n%B' -8 --grep='Co-Authored-By'
git log --format='%s' -200 | grep -oE '^[a-z]+\([^)]+\)' | sort | uniq -c | sort -rn
git log --format='%B' -400 | grep -oE 'Co-Authored-By: .*' | sort | uniq -c | sort -rn
```

That last one decides the trailer: its exact spelling varies per repo and per era.
Also read `AGENTS.md`, `CLAUDE.md` and `CONTRIBUTING.md` at the root when present —
they usually carry the commit rules and the requirement-ID scheme.

A repo with no agent-authored history has no established voice: apply this skill's
format, but never overwrite a deliberate human style visible in the log.

## Step 3 — Recover intent from the agent transcripts

A dirty tree rarely explains itself; the prompt log does.

```bash
python scripts/recover_intent.py <repo-path> --limit 50
```

The script prints the recent prompts for that project from `~/.claude/history.jsonl`
plus the user turns of the three most recently modified session files. Bind transcript
to diff: for every changed file, look for its path in that output. A file nobody
discussed is a leftover — surface it, do not narrate a purpose for it.

Transcripts silent? Read the diff and claim only what the diff proves. Never fabricate
a measurement.

## Step 4 — Group the diff into commits

One commit = **one reviewable claim**. Heuristics, in priority order:

1. **By owner doc / requirement prefix**, when the repo defines one (the doc map in
   `AGENTS.md`). A commit spanning two prefixes is fine when they are two halves of
   one failure — cite both.
2. **Spec edits ride with their code.** The requirement row and the code satisfying it
   go in the SAME commit. Never a trailing "docs: update specs".
3. **Generated artifacts ride with their source** (bundles, lockfiles, generated
   clients, `*.generated.*`). Regenerate before staging; a stale artifact is a silent
   bug.
4. **Migrations ride with the code that reads them.**
5. **Locale files split by key** — `git add -p` when one file serves two features.
6. **Tests ride with the behavior they cover.**

When a file legitimately spans two commits, use `git add -p`. Never reorder work into
a fictional sequence: each commit describes a tree that is true and should build.

Print the plan before executing — per commit, the subject and the exact paths.

## Step 5 — Write the message

**Subject:** `type(scope): lowercase summary, no trailing period`. Use only the types
and scopes Step 2 found in the log. Scope is an area, not a path. State the outcome,
not the mechanism ("a connector is an instance, not a missing connection" beats
"change connector lookup"). Match the corpus length (commonly 60-90 chars); never
truncate to 72 at the cost of saying nothing.

**Body, wrapped at 80 columns.** The order that reads well and matches most agent
corpora:

1. **The failure, with a measured number and why it was invisible.** Only a number you
   actually measured this session; otherwise describe the mechanism precisely.
2. **What changed and why *there*** — justify the location, cite requirement IDs
   inline when the repo has them.
3. **The rejected alternative and the cost that killed it**, plus what was
   deliberately NOT done.
4. `Two things worth flagging for review:` — optional, for surprises a reviewer would
   otherwise have to find.
5. `Not covered:` — optional, known gaps and where they are recorded.
6. The requirement-ID line alone, when the commit closes IDs.

Full sentences, em dashes, backticks around symbols. Facts, not effort. No
bullets-only body for a substantive change. No behavioral effect: say
`no behavioral change`.

**Trailer** — exactly one line, last, only when an agent did the work:

```
Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
```

The name must be the model that actually did the work, spelled the way Step 2 found it
in this repo. Add a variant suffix (`(1M context)`) only when running that variant. A
non-Claude model uses its own name. The user did the work and you only committed it:
omit the trailer. Never add "Generated with", emoji, or a second attribution line.

## Step 6 — Verify before each commit

Read `package.json`, `pyproject.toml` or `Makefile` first; never guess a script name.
Run what the diff touches, not the whole matrix. Never pipe a check through
`tail`/`head`/`|| echo` — that masks the exit code. A check fails: fix it inside the
same commit; do not commit red and do not weaken the test.

### Dirty-tree test isolation

When tests discover untracked files outside the commit scope, also run the focused
suite from a scratch snapshot populated from the staged Git tree and its tracked
runtime dependencies. Do not copy the dirty worktree wholesale: excluded fixtures
can pass falsely or conceal missing committed dependencies. Record working-tree and
snapshot test counts separately, then verify `HEAD^{tree}` equals the tested staged
tree after committing. Hash excluded dirty files before and after to prove that
hooks and test execution left other owners' work unchanged.

## Step 7 — Stage and commit

```bash
git add path/one path/two
git status --porcelain
git commit -F <scratch>/msg1.txt
```

Write the message file with `write_file` — a multi-paragraph body does not survive
`-m`. Use the OS scratch dir (`$LOCALAPPDATA/Temp` on Windows, `$TMPDIR` elsewhere),
pass forward-slash paths to git, and repeat per commit.

## Step 8 — Close out

```bash
git log --format='%h %s' -<N>
git status --porcelain
```

Report the commit list. The tree must be clean, or the remainder must be exactly the
files you said you were leaving behind, with the reason. Do not push.

## Hard rules

- Commit on the **current branch**. Never create, switch, rebase, or amend a pushed
  commit. Never `git push` unless asked.
- Never `git add -A` or `git add .`. Stage explicit paths, one commit at a time.
- Never `--no-verify`; let the repo's hooks run.
- Never commit gitignored generated state, `.env*`, or anything holding a secret —
  flag it instead.

## Worktrees

- **Detached HEAD** (common in agent and IDE worktrees): a commit there is reachable
  only by hash. Ask before committing; do not create a branch to "fix" it on your own.
- **The branch you want is checked out in another worktree.** `git checkout` refuses,
  by design. Never resolve that by switching worktrees or by detaching — commit on the
  branch this worktree already has.
- **Index, HEAD and stash are per-worktree; hooks, config and objects are shared.** A
  hook that rewrites generated files runs against THIS worktree's tree.
- **Ignored per-worktree output** (`graphify-out/`, `dist/`, `.venv/`) reappears dirty
  after any local tooling run. It stays out of every commit.
- **Sibling worktrees hold other agents' work in progress.** Their paths never enter
  your `git add`, and their conflicts are `merge-reconciler`'s job.

## Pitfalls

- **Folder name is not the remote name**, and not every remote is GitHub — `gh` is
  useless against Google Cloud Source Repositories or a self-hosted remote. Check
  `git remote -v` before reaching for it.
- **A stale generated artifact is a silent bug.** Regenerate and stage it with its
  source, in the same commit.
- **A behavioral change with no requirement ID** violates the repo rules in projects
  that use them: add the row to the owner doc in the same commit, or state
  `no behavioral change`.
- **Merge commits are pull artifacts.** Do not create one; if a pull is needed, ask.
- **A directory with no `.git`** has nothing to commit — ask before `git init`.
- **Upstream clones vendored into the tree** are not yours to commit into.

## Verification

The run succeeded when every path from Step 1 is either committed or explicitly
reported as left behind; `git log -<N>` shows one subject per reviewable claim;
`git show --stat HEAD` contains no unrelated file; and the trailer matches what Step 2
found in the corpus.

## Recovery and dependency verification

- After worker timeout, inspect HEAD, index and completed test logs before retrying. A post-commit hook can outlive the caller even after the commit exists; verify its exact tree and do not duplicate it.
- For missing npm peer modules after `npm ci`, inspect effective `legacy-peer-deps` and the existing lockfile before adding dependencies. Reproduce with explicit peer resolution in an isolated copy; a global npm setting can omit locked peers and masquerade as a missing manifest dependency.
- Do not fan out multiple heavy test/build processes per repository during portfolio commits. Prefer one bounded verification process per repo and checkpoint candidate trees/logs before committing; resource contention causes false timeout blockers.

## Windows partial-staging verification

- Write generated unified patches as UTF-8 bytes with LF newlines, not Python's
  default Windows text translation: CRLF patch context can fail against LF blobs.
  Run `git apply --cached --check` before applying; preserve the working files.
- When independent features share a file, test the intermediate staged content,
  not only the combined working tree. For Node TypeScript actions, a temporary
  `registerHooks` loader can substitute a scratch source at the original module
  URL while retaining real relative imports and in-memory SQLite tests. Compare
  that source to `git show :path` before committing; keep helpers outside the repo.
- Hash scoped files and check branch, HEAD, and staged paths before each commit.
  Stop the affected group when external edits invalidate the tested snapshot.

## Project notes

Per-repo notes (owner-doc prefixes, verify scripts, remote, known traps) belong
in `references/<repo>.md`, read **only** when that repo is the target. Notes for
a client or employer repo are local-only: keep them out of version control, and
when they are absent work from what the repo itself declares in `AGENTS.md`.
