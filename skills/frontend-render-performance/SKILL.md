---
name: frontend-render-performance
description: "UI slower the longer it runs? Find O(n) per-event work."
version: 1.0.0
author: Rafael Rocha Ribeiro (github.com/Rafaelrr5)
license: MIT
platforms: [linux, macos, windows]
metadata:
  agent:
    tags: [performance, react, frontend, profiling, memoization, regression-testing]
    related_skills: [measurement-validity]
---

# Frontend Render Performance

## When to Use

Use when a UI is reported as slow in a way that involves **time or accumulation**
rather than a single slow action:

- "gets slow after a while of using it"
- "laggy while it's streaming / typing / loading"
- "fine when I reload, then degrades again"
- "slow on long conversations / big lists / after many items"
- a page that profiles fine on an empty state and badly on a real one

Do **not** use for a single slow operation with a fixed cost (one heavy query,
one huge bundle, one blocking import). That is a different problem: profile the
operation directly.

## The Signature

```
Degrades with use + reload fixes it = per-event work that scales with
accumulated client state.
```

A reload resets in-memory state, so the symptom resets too. That single fact
rules out most server-side and network explanations and points at a handler,
effect, or render path whose cost is a function of how much has piled up.

The usual shape: something fires at high frequency (a stream token, a keystroke,
a scroll, a websocket message, a timer) and does O(n) work over everything
received so far. At n=5 nobody notices. At n=200 the app is unusable, and the
user describes it as "slow after a while".

## Phase 1 — Measure the Curve, Not the Clock

**Do not start by reading code looking for something that looks expensive.** The
expensive thing is usually cheap per unit and merely repeated n times.

Build a harness that drives the high-frequency event over a **synthetic history
of several sizes** and records a *count*, not a duration.

```
history size:   1     5    10    25    50
renders/event:  4    12    22    52   102     <- linear in n. This is the bug.
```

Read the **shape**:

| Shape across sizes | Meaning |
|---|---|
| Flat | Correct. Not your problem. |
| Grows with n | O(n) per event — the target. |
| Grows faster than n | Nested repetition; often a memo miss inside a loop. |

### Why counting, not timing

Wall-clock in a test environment is close to useless for this. In one
investigation the **same unchanged code** timed 387.7 ms/frame, then
6.3 ms/frame, then 260.6 ms/frame on consecutive runs — swings far larger than
the effect being measured, from JIT warm-up, GC, and other load on the machine.
The render *count* in those same runs was stable and exactly linear.

So count the invariant:

- renders (React), patches (DOM), queries, allocations, requests, iterations
- a count is deterministic, survives a noisy machine, and reads as a complexity
  claim rather than a vibe
- it also becomes a permanent gate; a millisecond threshold in CI is a future
  flake, `expect(renders).toBe(0)` is not

### Counting renders in React

Replace the children under test with `memo()` spies. A `memo()` component
re-renders **if and only if one of its props changed identity** — which is
exactly the property being investigated, so the spy is the measurement.

```tsx
const counts = { item: 0 };
vi.mock('@/components/chat', async () => {
  const R = await import('react');
  const MessageItem = R.memo(function Spy(): React.ReactElement {
    counts.item += 1;
    return R.createElement('div');
  });
  return { MessageItem, /* ...other exports stubbed */ };
});
```

Then render, reset the counters (so mount cost is excluded), drive N events, and
read the counters. Vary history size and compare shapes.

Profiler-based alternatives (React DevTools, `<Profiler>`) are fine for
exploration but harder to assert on in CI. Prefer spies for the permanent gate.

## Phase 2 — Find What Defeats the Memo

When `memo()` is already present and still re-rendering, the fault is almost
never in the memoized component. It is upstream, in a prop whose **identity**
is rebuilt every event even though its **value** is unchanged.

Work outward from the child:

1. List every prop the child receives.
2. For each, ask: is this the same object as last event?
3. The offenders are usually functions, arrays, and objects created inline or
   recreated by a hook whose dependency array contains a per-event value.

See `references/react-memo-defeaters.md` for the full catalog with the two
real-world cases that motivated this skill, plus the defenses that were already
in place and still were not enough.

The headline traps:

- **A `useCallback` that lists a per-event array in its deps.** The array is new
  on every state dispatch, so the callback is new, so every child holding it
  re-renders. Read the array from a ref instead and drop the dep.
- **A container rebuilt around stable contents.** `memo` compares the prop, not
  the prop's elements. Stabilizing every item in an array does nothing if the
  array itself is reconstructed.

## Phase 3 — Fix at the Source, Re-measure

Fix one leak, re-run the harness, confirm the curve flattened, then look for the
next. Fixing several at once means you cannot attribute the improvement, and
some "fixes" do nothing.

Re-measure with the *same* harness and report before/after side by side:

```
50 turns of history, per streaming token:
  before: 102 MessageItem renders, 50 ThinkingBlock renders
  after:    2 MessageItem renders,  0 ThinkingBlock renders
```

### Guard against over-caching

Every fix here is a caching or identity-freezing change, so each one can
introduce the opposite bug: content that stops updating when it genuinely
should. **Write that test too.** A cached group whose own data is still arriving
must still re-render:

```ts
// live block changed -> renders; the 10 settled ones -> do not
expect(counts.thinking).toBe(1);
```

A frozen UI is a worse bug than a slow one. Do not ship the speedup without this
test.

## Phase 4 — Make It a Gate, and Prove It Can Go Red

A performance test that has never failed is decoration. Before believing it:

1. Remove the fix (see the dirty-repo recipe below).
2. Run the gate. It **must** fail, with numbers matching the original symptom.
3. Restore the fix. It must pass.

Without step 2 you have no evidence the test observes the thing you fixed.

### Safely A/B a fix in a repo you do not own

`git stash` is the obvious tool and it is a trap in a shared repo. In one
session `git stash push -- <path>` followed by `git stash pop` **partially
applied an unrelated pre-existing stash**, leaving conflict markers (`UU`)
across eight untouched files. The repo had eight stashes from other branches;
popping is not scoped the way you expect.

Use plain file copies instead — no stash, no index, nothing to reconcile:

```bash
T="$TMPDIR"                       # or $LOCALAPPDATA/Temp on Windows
cp path/to/File.tsx "$T/File.mine.tsx"
git checkout HEAD -- path/to/File.tsx     # baseline
<run the gate: expect RED>
cp "$T/File.mine.tsx" path/to/File.tsx    # restore
<run the gate: expect GREEN>
```

If a stash operation does go wrong, do not improvise: `git status` immediately,
`git restore --source=HEAD --staged --worktree -- <the files you did not touch>`,
then confirm the stash list is still the length it was. Say so in your report.

### Baseline the other gates before attributing them

A repo-wide `lint` / `typecheck` / spec-check that returns hundreds of problems
after your edit says nothing until you know the count *before* it. Measure both:

```bash
# with your change
pnpm run lint 2>&1 | grep -E '^✖' > /tmp/mine.txt
# baseline
cp <changed files> /tmp/ && git checkout HEAD -- <changed files>
pnpm run lint 2>&1 | grep -E '^✖' > /tmp/base.txt
# restore, then diff the two
```

"215 problems, byte-identical to baseline, none in the files I touched" is a
verified claim. "Those look pre-existing" is a guess. This protects you in both
directions: you neither inherit someone else's red build nor claim a clean run
you never had.

And do run the type checker on your own new test file. In this session it caught
a reference to a `messagesRef` that did not exist yet — a real bug in the fix
that would have crashed the feature the moment a user clicked the button.

## Working Rules For This User

- **Confirm the target branch before editing.** He may name one explicitly
  ("faça na main") while the working copy sits on another. Check
  `git branch --show-current` first and switch; do not edit wherever you landed.
- **Exhaust the investigation, then report short.** Chase every open thread
  before coming back, but lead the reply with the before/after table and the
  root cause. Do not narrate the steps he already watched scroll past.
- **Do not commit or push** unless asked. Leave the tree dirty and say so.
- If the repo carries a spec/requirement-ID convention (an `AGENTS.md` mapping
  directories to owner docs), a performance fix is a behavioral change: it needs
  a **new** ID and a filled coverage column citing the gate you just wrote.

## Pitfalls

| Pitfall | Do this instead |
|---|---|
| Reading code hunting for something "expensive" | Measure the curve first; the culprit is cheap × n |
| Timing in a test environment | Count operations; read the shape across sizes |
| One input size | Three or more, or you cannot see O(n) vs O(1) |
| Trusting `memo()` because it is present | It compares prop identity; verify with a spy |
| Stabilizing array contents but not the array | `memo` compares the container |
| Fixing several leaks at once | One at a time, re-measure between |
| Shipping a cache without a staleness test | Frozen UI is worse than slow UI |
| A perf test never seen failing | Revert the fix and watch it go red |
| `git stash` to A/B in a shared repo | Copy to temp + `git checkout HEAD --` |
| "Those lint errors were already there" | Diff against the same gate run at `HEAD` |

## Files

- `references/react-memo-defeaters.md` — catalog of what breaks `React.memo`,
  with real cases, the defenses that were already present and insufficient, and
  the harness pattern for counting renders.
