# "Implemented and tested" is not evidence

You asked an agent to fix a bug. Ten minutes later it reports: *"Fixed the token
expiry check in the auth middleware. Implemented and tested."*

You merge it. Two days later the same bug is back, because it was never fixed,
or because it was fixed in a file that is not the one running in production, or
because "tested" meant the agent wrote a test file and never executed it.

This is not a model quality problem. It happens with the best models available,
and it will happen with the next ones, because of what the closing message
actually is.

## The closing message is a self-report

An agent writes its final summary from the same context that produced the work.
If it believed it edited the right file, the summary says it edited the right
file. If it wrote a test and the runner was never invoked, nothing in the
context contradicts "tested". The summary is a sincere account of an intention,
not an observation of the result.

That distinction matters because the two are indistinguishable from the outside.
A run that genuinely fixed the bug and a run that hallucinated fixing it produce
the same shape of message, with the same confident tone and the same level of
technical detail. You cannot grade the report by reading it more carefully.

## The naive fix, and why it fails

The obvious response is to ask for proof in the prompt: *"and show me the test
output."*

This fails in a specific way. The agent, still writing from the same context,
produces output that looks like test output. Not always fabricated wholesale:
more often it is real output from a previous run, or from a different test, or
the output of a command that succeeded for a reason unrelated to your fix. The
text passes a glance. It is still a self-report, just formatted as a terminal.

Asking the report to validate itself cannot work. The check has to come from
outside the run.

## The mechanism: name the command before the work starts

The fix is not a better prompt for the agent. It is deciding, before dispatch,
what observation would prove the claim, and then making that observation
yourself.

Concretely, for the auth bug above:

```bash
# not "did you fix it" but: what changed, and does the change run?
git -C <repo> diff --stat
git -C <repo> diff -- src/middleware/auth.ts
npm test -- auth.spec.ts 2>&1 | tail -20
```

Three properties make this work:

**It reads the tree, not the conversation.** `git diff` cannot be influenced by
what the agent believed it did.

**It is decided in advance.** If you invent the check after reading the report,
you will unconsciously pick a check the report already satisfies.

**It can fail.** A verification step that cannot return a negative is
decoration. If you cannot describe the output that would mean "the agent was
wrong", you do not have a check yet.

This generalises past coding. For a deploy, the check is an HTTP request against
the live URL and the expected status code, not the deploy log. For a data
migration, a `SELECT COUNT(*)` on the target, not the migration summary. The
pattern is always the same: identify the artifact the work was supposed to
change, then read that artifact.

## The measurement

I have not run a controlled study, and I will not pretend otherwise. What I can
report honestly is the shape of what the checks catch.

Over roughly three months of delegating bounded coding tasks, the failures the
post-run `git diff` caught, in descending frequency:

1. Work done in the right file but on the wrong branch or worktree.
2. A test written and never executed, reported as passing.
3. Scope creep: the requested change made, plus four unrequested edits to files
   that were not in the fence.
4. The change made only in a comment or a docstring.

None of these were caught by reading the agent's summary, because in all four
cases the summary was a reasonable description of what the agent thought it had
done. All four were obvious in under thirty seconds of looking at the tree.

The cost of the check is those thirty seconds. The cost of skipping it is the
debugging session two days later, when the bug is back and the commit message
says it was fixed.

## What this does not solve

**It does not tell you the change is correct.** `git diff` proves something
happened in the right place. Whether that something is the right something is
still a review problem, and review is still your job.

**It does not scale to unbounded work.** If the task was "improve the codebase",
there is no single artifact to read, and no check to name in advance. That is an
argument for fencing the task, not for skipping the check.

**It adds friction, deliberately.** If you are dispatching thirty tiny tasks an
hour, thirty verification steps will feel like overhead. It is overhead. It is
cheaper than the alternative, but it is not free, and anyone selling you an
agent workflow with no verification step is selling you the two-days-later
debugging session without mentioning it.

---

The anchors for this in the repo:
[`delegated-agent-supervision`](../skills/delegated-agent-supervision) for
fencing and checking a dispatched agent, and
[`worktree-analysis`](../skills/worktree-analysis) for reading a tree that has
been dirty long enough that you no longer remember what is in it. The forensics
script there clusters uncommitted changes by time and tells you which clusters
came from an agent session and which came from you.
