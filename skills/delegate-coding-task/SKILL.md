---
name: delegate-coding-task
description: "Use when handing a coding task to another agent. Fence the scope, verify the result."
version: 1.0.0
author: Rafael Rocha Ribeiro (github.com/Rafaelrr5)
license: MIT
platforms: [linux, macos, windows]
---

# Delegate a coding task

Hand a bounded coding task to a second agent (Claude Code, Codex, OpenCode, any
CLI that takes a prompt and edits a repo), then verify what came back before
you believe any part of it.

The hard part is not launching the agent. It is that **an agent's closing
message is a self-report, not evidence**. "Implemented and tested" routinely
means one file written and nothing run. This skill is the fence you put around
the work and the checks you run after.

## When to Use

- A task involves writing, editing, refactoring, debugging or testing code in a
  repository, and you are not the one typing.
- You are running several independent workstreams and want them in parallel.
- Don't use for: research, writing, analysis, or config of the orchestrator
  itself. Those have no repo to fence and no diff to verify.

## Step 1 — Decide if the task is delegable at all

A delegable task has all four:

| Property | Test |
|---|---|
| **Bounded** | you can name the files it may touch |
| **Verifiable** | there is a command whose output proves it worked |
| **Reversible** | worst case is a bad diff on a branch, not a deploy |
| **Self-contained** | it does not need a decision only the user can make |

Missing any one of these, do it yourself or go back to the user. A task
delegated without a verification command is not delegated, it is abandoned.

## Step 2 — Write the prompt as a contract

Put it in a file, not on the command line: a multi-paragraph prompt does not
survive shell quoting, and a file is the artifact you cite later. The contract
has six parts, in this order:

1. **Goal** in one sentence, stated as an outcome, not an activity.
2. **Files it MAY touch**, explicit paths.
3. **Files it MUST NOT touch** — name the ones another agent or the user is
   working in right now. Without this line, concurrent work gets clobbered.
4. **Definition of done**, as a command plus the expected output.
5. **Stop condition:** "if the fix requires changing a file outside the allowed
   list, stop and report instead of widening the scope."
6. **Forbidden operations:** no `git add -A`, no commit, no push, no
   dependency install, unless explicitly asked.

Do not restate what the repo's own `AGENTS.md` / `CLAUDE.md` already says. The
agent loads it; repeating it wastes context and creates two sources of truth.

## Step 3 — Launch non-interactively

Prefer print/headless mode with the prompt on stdin. An interactive window is
for when the user actually wants the keyboard.

```bash
# prompt via stdin survives any length and any quoting
cat task.md | claude -p --permission-mode acceptEdits
```

**Strip inherited credentials from the child's environment** when the project
exports them for a different purpose. A subprocess that inherits
`ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN` or `ANTHROPIC_BASE_URL` from a repo
`.env` will silently talk to the wrong endpoint, bill the wrong account, or
fail with an auth error that looks like a bug in your prompt.

```python
env = {k: v for k, v in os.environ.items()
       if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL")}
```

## Step 4 — Verify against the tree, never against the report

Run all of these. Each one catches a different class of lie:

```bash
git -C <repo> status --porcelain      # did it touch what it said, and only that?
git -C <repo> diff --stat             # is the size plausible for the claim?
git -C <repo> log --oneline -5        # did it commit when told not to?
<the repo's own test command>         # does the claimed test actually pass?
```

Then read the diff of at least the file carrying the core claim. A green test
suite that never exercised the new path is the most common false positive:
check that the test names in the output actually mention the behaviour.

Divergence between the report and the tree is a finding, not a formality. The
tree wins, and the divergence goes in what you tell the user.

## Parallelism

Independent tasks run concurrently. The constraints:

- **One repo, two agents: only with disjoint file lists.** Put the other
  agent's paths in each prompt's MUST NOT list.
- **One verification process per repo.** Fanning out several heavy
  test/build runs in the same checkout causes resource contention that reports
  itself as a timeout, and you will debug the wrong thing.
- **Never let two agents share a branch.** One branch each, or one worktree
  each.

## Pitfalls

- **"Tested" without a command is not tested.** Ask for the command and its
  output in the report, then re-run it yourself.
- **A silent success is usually a blocked start.** A launcher that needs an
  approval prompt, a trust dialog, or an executable bit will hang, not fail.
  Confirm from real output that the process actually started before reporting
  that you delegated anything.
- **An agent developing against a dirty tree writes code that compiles only
  there.** Its work depends on someone else's uncommitted changes, which is
  invisible in the diff. Build it from a clean checkout before shipping.
- **Widening scope mid-task is the default failure mode.** Without an explicit
  stop condition, an agent asked to fix one function will refactor the module
  and you will review the wrong diff.
- **The prompt file is the audit trail.** Keep it. When the result is wrong,
  the first question is always whether the contract was wrong.

## Verification

The run succeeded when: the diff touches only allowed paths; the definition-of-
done command was run by you and passed; nothing was committed or pushed that
you did not ask for; and every claim you repeat to the user is one you saw in
real output.
