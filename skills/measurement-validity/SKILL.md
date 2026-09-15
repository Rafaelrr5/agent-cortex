---
name: measurement-validity
description: "Numbers driving a decision? Check the instrument first."
version: 1.0.0
author: Rafael Rocha Ribeiro (github.com/Rafaelrr5)
license: MIT
platforms: [linux, macos, windows]
metadata:
  agent:
    tags: [measurement, benchmarking, evaluation, metrics, statistics, verification]
    related_skills: [delegated-agent-supervision]
---

# Measurement Validity

## When to Use

Use before acting on — or reporting — any number that drives a decision:
benchmark scores, eval harness output, A/B comparisons, quality metrics,
regression checks, "is this change an improvement" questions.

Especially when the pipeline contains a **non-deterministic** component (an
LLM, a sampler, a scheduler, a network race), or when the metric was written by
someone chasing the very bug it now reports.

## Core Principle

```
A measurement has two possible failure locations: the system, or the
instrument pointed at it. Check the instrument first — it costs minutes;
debugging the wrong subsystem costs hours.
```

## Part 1 — Is the Instrument Honest?

Two long-standing "the model won't follow instructions" failures both turned
out to be instrument bugs:

- A metric counted `"cell_" in track["name"]`, but `name` was a human-written
  label (`"intro hat cell"`) while the underscore only ever existed in the
  *filename*. Real usage was 10–12 per run and had always been reported as
  **0**. Weeks of prompt engineering chased a counting bug.
- A check failed because the required asset **did not exist in the data store**
  at all. The failure was honest; the diagnosis ("the model ignores the
  prompt") was not. No amount of instruction could conjure the missing input.

### Checks before accepting a metric

| Check | How |
|---|---|
| **Join on the right key** | Does the metric resolve the identifier the *system* uses (index/ID) rather than a display string? |
| **Hand-compute one case** | Take one input where you know the answer; confirm the metric reproduces it |
| **Error channel exists** | A count that reports 0 for "none" *and* 0 for "lookup failed" hides the second. Add an explicit unresolved/out-of-range counter |
| **Input data actually contains it** | Inspect the store directly, not the code that reads it |
| **Method valid for the signal** | A fundamental-frequency reading averaged across a pitch glide said −282 cents; measured on the sustain it was +2 cents. The number was real; the method made it meaningless |
| **Artifact actually exists** | Harnesses that catch exceptions to "keep going" will score a **zero-byte** file and report a number from stale data |

### Provider migrations and stale fixtures

Before comparing model quality, validate every expected identifier against the exact fixture/store consumed by the runner. A renamed canonical category can make all correct outputs score as failures; add an offline integrity test, correct the stale reference, and rerun the comparison. Keep the original failure distinguishable from the corrected instrument.

Price hosted deployments using that host's published meters, not the model vendor's direct API rates. Include reasoning output, cache writes/reads, retries and separately billed search calls. Label SKU/account discounts and long-context tiers unknown until verified; a token-only estimate never proves a no-higher-invoice promise.

### The hollow pass

A check that passes **for the wrong reason** is more dangerous than one that
fails. A rule of "no kick on every beat" passed cleanly — because the render
contained *almost no kick at all*. The score read 100/100 while an entire
instrument was inaudible.

After any check flips green, ask: **could this pass by absence?** Verify the
green came from correct content, not missing content. Prefer metrics that
assert presence and shape over metrics that only assert the absence of a
violation.

Corollary: when you fix the underlying gap, a hollow 100 may legitimately drop
to an honest 85. That is progress. Report it as progress.

## Part 2 — Is N Big Enough?

**A single before/after comparison in a stochastic pipeline is not evidence.**

Measured once: **100 vs 85** — a decisive-looking win.
Repeated six times: means of **91.7 vs 90.0**, with the arms swapping places on
2 of 6 runs. The real effect was roughly *one tenth* of what the single run
advertised. The N=1 number had already been reported to the user and had to be
publicly retracted.

### Protocol

1. **Establish the noise floor first.** Run the *unchanged* system 5+ times and
   record the spread. If your change's effect is smaller than that spread, one
   run cannot detect it.
2. **N ≥ 5 per arm**, more when the spread is wide.
3. **Report mean, median, min–max, and win rate.** Never a single figure.
   "B beat A in 3 of 6, mean +1.7" is honest; "B scored 100, A scored 85" is
   not.
4. **Isolate what you can.** A controlled comparison on a *fixed* input (a
   hand-written plan, pinned seed, recorded fixture) that exercises the changed
   code without the stochastic component is worth more than ten noisy
   end-to-end runs.
5. **Find the determinism boundary.** Running one stage 3× and getting
   byte-identical output proved the variance lived entirely downstream — which
   redirected the whole investigation away from a wrong hypothesis.
6. **Never cherry-pick the best run as "the result."** Best-of-N reported as
   typical is the N=1 error with extra steps. Keeping a best-of-N artifact for
   demonstration is fine — label it as such.

### Aggregate in code, not in your head

Append each run's numbers to a file, then reduce with a script. Eyeballing six
runs invites the same selection bias the protocol exists to prevent. Filter
obvious artifacts explicitly — e.g. a "hit" count so high it indicates smear
rather than signal.

## Part 3 — Reporting

- State the spread, not just the centre.
- Say plainly when the effect is smaller than you previously claimed. Retract
  your own earlier number explicitly rather than quietly replacing it.
- Separate "the machinery is fixed and verified" from "the intervention has a
  large measurable effect." Both can be true independently; conflating them
  oversells the work.
- When a metric improved for a reason you did not cause (a concurrent change,
  a different fix landing first), say so.

## Red Flags

- "The model/LLM just isn't following instructions" — before checking the
  metric and the input data
- "The number went up, it works" — from one run of a stochastic pipeline
- "All checks are green" — without asking whether any pass by absence
- "The metric is simple, it must be right" — the metric is code; it has bugs
- Reporting a score without first confirming the measured artifact is non-empty
