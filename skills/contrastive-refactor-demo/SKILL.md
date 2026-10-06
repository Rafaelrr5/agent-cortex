---
name: contrastive-refactor-demo
description: "Proving a refactor? Build a measured before/after demo."
version: 1.0.0
author: Rafael with AI assistance
license: MIT
platforms: [linux, macos, windows]
---

# Contrastive refactor demo

Two implementations of one feature — one carrying deliberate debt, one
refactored — built so the difference between them can be **measured**, not
asserted. The audience may be a class, a reviewer, a team you are convincing to
fund a refactor, or a portfolio reader.

## When to Use

Use when the deliverable's purpose is to *show* that a technique works:
coursework on software quality or maintenance, a teaching repo, a talk demo, an
internal case for paying down debt.

Not for: shipping a feature, a real refactor of production code (that is
a production refactoring or debugging workflow), or a throwaway experiment answering a
question for yourself (a throwaway experiment).

## Core principle

```
The flawed version must look finished. A demo whose "before" is visibly
broken proves nothing — everyone already agrees broken is bad. The whole
point is that it passes the functional test and still fails the audit.
```

So: the flawed version **works** for the mainstream user — mouse works, happy
path completes, nothing crashes. Every defect is one that survives a casual
look.

## Step 0 — scope the ceremony to who will run it

Match the build-out to the audience, not to what a production system carries.
A CI pipeline, an extra config layer, a second package, a typed build: dead
weight when the audience is one live demo or one reviewer. Nobody watches the
pipeline, and a green badge proves nothing in the room. **A single script that
exits non-zero is the same quality gate and can be run in front of people.**

Propose the minimal shape first and name explicitly what you cut plus the
condition that would justify adding it. A question like "is this really the
smartest way?" is a signal the proposal is heavier than the problem — answer by
cutting, not by defending.

Typical cuts that lose nothing: hosted CI (→ exit code from a local script),
a score-tool config wrapper (→ call the tool directly), two apps (→ two routes
in one app, one server to start at demo time), a type layer, a test level that
structurally cannot see the defect you planted.

**Coordination structure is ceremony too.** A division of labour, a contract
between workers, a responsibilities document — none of it pays for itself
until there is confirmed to be more than one executor. Ask who is actually
building before designing around a split; when the answer turns out to be one
person, the split documents become stale artifacts that read as the current
plan to whoever arrives later.

## Step 1 — freeze a contract before writing either version

Both versions must consume the same data and expose the same hooks, or the
comparison measures two different things and attributes the difference to the
code. Freeze and commit first:

- the input data (fixtures, seed records) in one shared module;
- the test markers/selectors the audit script drives, **identical in both
  versions**;
- the routes.

Commit this as its own change before either implementation exists. If the work
is split across people, this is also the boundary that lets them work without
touching the same files.

## Step 2 — write the flawed version, defects catalogued in advance

Write down each planted defect, which instrument is expected to catch it, and
which technique will remove it. Committing that catalogue *before* measuring
keeps you honest when an instrument surprises you.

Pick defects spanning different detection classes — the payload of the demo is
that they are not all found the same way:

| Defect class | Found by |
|---|---|
| Business rule duplicated, one copy divergent | a test that knows the rule (only after extraction) |
| Non-semantic control standing in for a real one | **nothing automated** — manual check only |
| Missing programmatic labels/names | rule-based scanner |
| Insufficient contrast, layout-dependent defects | scanner in a real browser only |
| Structure/ordering violations | the scoring wrapper, often not the raw engine |
| Monolithic file | review and argument only — no number |

**The duplicated-rule defect is the strongest one; plant it deliberately.**
Copy a business rule into three call sites and make exactly one diverge by a
single operator (`<=` where the others use `<`). The screen then answers the
same question two ways, which is demonstrable live and fixable by a test. It
also makes the maintenance argument literal rather than theoretical.

Before committing it, prove the divergence is real and reachable with a
throwaway script that runs both copies over the same inputs and prints the
input where they disagree. A planted defect you cannot trigger on stage is a
liability.

## Step 3 — refactor, and let testability be the argument

The refactored version imports one implementation of the rule instead of
reproducing it. State the maintenance case in the order that actually holds:

1. Fixing the divergent operator corrects the symptom and leaves the cause —
   three sites still drift on the next change.
2. The rule inside a UI component is unreachable by unit test; testing it means
   rendering, filling, and reading the screen.
3. Extracted, it is a pure function with edge cases covered in milliseconds.

The extraction was not done to enable the test — the test became possible
because the structure improved. That ordering is the point: **code hard to test
is code hard to change safely.**

## Step 4 — measure, never estimate

Run the real tools against the **built and served** artifact, and put the
actual output in the documents. Never write a number you did not observe.

Verify the tests can fail: mutate the logic they guard (flip an operator,
delete a clause), confirm red, restore. A suite that stays green under mutation
is measuring nothing, and one edit plus one run settles it.

Gate on more than one instrument, since either can move for reasons the other
would catch:

```js
if (!(after.score > before.score) || !(after.violations < before.violations)) {
  process.exit(1);
}
```

For accessibility/quality scanners specifically — why two tools that share an
engine still disagree, how to run them against one browser session, and the two
API shapes that break it — see
`references/accessibility-audit-reconciliation.md`.

## Step 5 — name what the instruments cannot see

This is the most valuable slide, and it only exists if you look for it.

A rule-based scanner cannot fire on an element type that is absent: a rule
requiring accessible names on buttons says nothing about a `<div onclick>` that
should have been a button. Zero violations means "no rule matched", never "the
behaviour is correct". **Whenever a scanner returns clean, name one defect class
it structurally cannot see and verify that class by hand** — such a check is
usually ~20-50 lines and catches what mature engines are built not to look for.

### Write the hand check as an outcome check, not a property check

Scanners ask *conformance* questions: which rule was violated. A hand check
that asks "is this element focusable?" is still conformance-shaped — it
interrogates an element. Ask the *efficacy* question instead: drive the real
task end to end through the constrained channel and assert the **goal state
changed** (a record appeared, a total moved), not that the activation landed.
Asserting on the activation passes when the handler silently no-ops.

Only the outcome check returns the unambiguous result — *the task cannot be
completed* — and that binary outranks any score in a write-up or a room.

The same walk yields a cost proxy for free: count the stops the constrained
channel makes before reaching the goal. A run that never arrives reports both
that the path is missing and how much effort was spent discovering that, which
a pass/fail alone does not convey.

**Adding an instrument means extending the gate.** A gate left on the original
conditions keeps certifying the old, weaker definition of "better" while the
new measurement sits in the report as decoration.

When the hand-written check finds something the tools missed, promote it: it
outranks whatever limitation you *planned* to discuss. Replace the predicted
lesson with the observed one and say in the write-up that you did.

## Step 6 — write it up without overselling

Non-negotiable, in the README and in the first minute of any presentation:
**the defects are planted on purpose.** Stated up front it reads as method;
discovered at the end it reads as manipulation.

Also state plainly:

- The numbers describe these two implementations and do not generalise. The
  **method** generalises.
- Automated coverage has a ceiling; cite it rather than implying a clean scan
  means conformance.
- Which claims have a measurement behind them and which are argument only. Mark
  the weakest item as weak — a monolith-versus-modules claim usually has no
  number, and saying so buys credibility for the items that do.
- What the artifact does *not* demonstrate (no peer review, no branching model,
  two cases only).

A rehearsal script should carry the exact commands, timings, and a fallback:
save the audit output to a file so a network or browser failure on the day
downgrades the demo instead of cancelling it.

Prose in every artifact — slides, README, chapters — gets an anti-AI-slop pass
before it ships (a plain-language editorial pass). Cut rule-of-three padding, "not just X but Y",
significance inflation and motivational closers; what survives is a definition
followed by the concrete case. One line may keep rhetorical weight — the
thesis, because it is the finding rather than decoration.

### An introductory deck sets up the demo, it does not spoil it

Concepts belong on slides; results belong in the live run. Define the idea and
stop — the matching defect lands later, on screen. A slide that states the
finding spends the payoff before the room can be surprised by it, and the demo
is reduced to confirming what was already read out.

Keep the deck one dependency-free HTML file: it opens on a machine you did not
prepare, navigates by keyboard, and prints to PDF through a per-slide page
break. **Screenshot every slide and look at the images before committing** —
text wrapping is invisible in the markup. Recipe, the two wrapping faults that
only appear rendered, and the capture script:
`references/presentation-deck.md`.

**Recompute the timing total in code whenever a block is added or retimed.**
Section timings drift past the allowed window silently; parse the per-block
minutes out of the script and sum them rather than re-adding by hand.

## Commit and reporting shape

One commit per stage — contract, domain, flawed version, refactor, audit,
documents — each with the reasoning in the body. The history is itself part of
the deliverable when the topic is maintenance.

Delete planning documents the moment they stop describing reality, in the same
commit that changes the plan. A stale division-of-work file reads as the
current plan to whoever arrives later.

When a framing question goes unanswered, record the assumption once where the
deliverable carries it (README, roadmap) and keep building. Do not close every
report by re-asking it: repeating the question does not produce an answer and
displaces the status the reader opened the message for.

Build so a late answer costs documents, never code. Fixtures, planted defects,
the refactor and the audit are framing-independent; only the write-up argues a
particular theme. Keep one chapter per theme axis plus a shared measurement
section, and a reframe becomes editing prose around numbers that still hold.

Treat the arriving frame as a question generator, not just a relabelling: ask
what the new frame wants to know that nothing currently measures, and add that
instrument. A frame concerned with the user's experience rather than the
code's conformance is what motivates the outcome check in Step 5 — the
strongest result can be the one the final framing asked for.

## Runnable public anchor

Reference snippets illustrate integration recipes, not standalone tested programs.
Only the following anchor has the verification scope recorded below.

Run `python scripts/audit.py` from this directory. See [verification](VERIFICATION.md) for scope and negative tests.

## Attribution

Prepared by Rafael with AI assistance. Adapted from private procedural notes whose recorded author was Hermes Agent. This is not a claim of sole authorship of those notes. Third-party tools retain their own licenses.
