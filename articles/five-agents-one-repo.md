# Five agents, one repo: bounded parallel work

The gap between someone who is fast with AI and someone who is not is rarely
prompt quality. It is that one of them runs a single conversation and waits, and
the other runs five bounded jobs at once and spends the time reviewing.

The second is not five times faster. Sometimes it is slower, because parallel
agents on one repository have a failure mode that serial work does not have:
they overwrite each other, and the damage is discovered after all five have
finished.

This is about how to get the speed without the mess.

## Where the naive version breaks

Open five terminals, give each one a task on the same repo, go and get coffee.

What you find on return:

**Two agents edited the same file.** The last writer wins. The other agent's
work is gone, and its closing summary still says it succeeded, because from its
own context it did.

**One agent ran `git add -A` and committed.** It swept up the other four agents'
in-progress work into a commit whose message describes only its own change. This
one is genuinely painful to unpick.

**One agent hit an ambiguity, made a reasonable decision, and rewrote a module
that was not part of its task.** The decision was defensible. It was also not
yours to make, and now it is entangled with four other changes.

Notice that none of these is a model failing at its job. Each agent did
something sensible given what it knew. The problem is that none of them knew
about the other four.

## The mechanism: the fence is the whole technique

Before dispatch, each task gets a written contract with four parts. Not a
suggestion in prose. An explicit list.

**Allowed files.** The exact paths this agent may modify. Not a directory, not a
glob when you can avoid it: paths.

**Forbidden files.** The paths the other concurrent agents own. Naming them
explicitly is not redundant with the allowed list, because it converts a silent
overlap into an instruction the agent can refuse.

**Stop conditions.** What to do when the work turns out to require touching
something outside the fence. The answer is always: stop, report what it needs,
change nothing. An agent that improvises past its fence is more expensive than
one that halts, every time.

**Forbidden operations.** For concurrent work on one repo this is at minimum:
no `git add -A`, no commit, no push, unless explicitly asked. Staging is a
shared resource. An agent that stages files it did not write is reaching into
another agent's work.

A dispatch then looks like:

```
Task: replace the inline date formatting in the invoice list with the shared
      formatDate helper.

Allowed:   src/components/InvoiceList.tsx
           src/components/InvoiceRow.tsx
Forbidden: src/lib/format.ts  (another job is editing it right now)
           anything under src/api/

If the helper's signature turns out to be wrong for this use, STOP and report.
Do not change the helper.

Do not run `git add -A`. Do not commit. Do not push.
```

Nothing clever. The value is entirely in having written it down before five
things are running at once.

## Splitting tasks so the fences do not touch

The fence only works if the tasks are genuinely separable, and deciding that is
the part that needs a human.

**Split by file ownership, not by feature.** "Add dark mode" and "fix the header
spacing" sound independent and both touch the stylesheet. "Everything under
`src/auth/`" and "everything under `src/billing/`" are independent because the
paths say so.

**A shared file means a serial dependency.** If two tasks need the same file,
they are one task, or they are two tasks that run one after the other. There is
no third option that ends well.

**Give the shared file to exactly one owner.** When several jobs need a new
helper, one job writes the helper and finishes, then the rest start. The wait is
real and it is cheaper than the merge.

## The measurement

Honest answer: I have not benchmarked wall-clock time against serial execution,
and the number would be dominated by task selection anyway.

What I can report is the failure rate. Since writing fences down, the overwrite
class of failure went to zero, because it is structurally prevented rather than
avoided by luck. What still happens, at roughly one in five dispatches, is an
agent stopping at its fence and asking, which is the fence working: that is a
thirty-second answer from me instead of a tangled diff.

The real gain is not that five agents are faster than one. It is that the review
step becomes possible at all. Five bounded diffs, each small and each in a known
set of files, can be read. One unbounded diff spanning the repo cannot, and in
practice does not get read.

## What this does not solve

**It does not fix bad task decomposition.** If the work genuinely does not split,
fencing it produces five agents all stopping at their fences. The fence tells
you the decomposition was wrong. It does not do the decomposition.

**It does not remove the review.** Five fenced diffs still need five reviews.
Parallelism buys you throughput, not trust.

**It does not scale forever.** My own ceiling is around five concurrent jobs, set
by how much diff I can actually read afterwards, not by anything technical. Past
that, verification becomes the bottleneck and the extra agents are producing
work that queues up unreviewed, which is the same as not having done it.

---

The anchors in this repo:
[`delegate-coding-task`](../skills/delegate-coding-task) for writing the fence,
and [`parallel-agent-fanout`](../skills/parallel-agent-fanout) for running
several at once on one repository, including the Windows launcher details that
cost me an evening.
