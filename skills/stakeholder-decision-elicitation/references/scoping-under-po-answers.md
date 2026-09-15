# Scoping under a PO's answers

Patterns for the moment a non-technical owner's decisions land and you have to
absorb them without the design fragmenting. Extracted from the Jogo Empresarial
re-scope (31/08/2026), but none of it is specific to that project.

---

## 1. The staging boundary — "phase one is character creation"

**Problem.** The owner asks for heterogeneous stages: early rounds about
discovery and validation, later rounds about operating. Each stage looks like it
needs its own simulation. N stages become N engines, nothing is shared, and the
planned second module has nothing to inherit.

**Pattern.** Split the timeline into a **producing** phase and a **consuming**
phase, with a named artifact between them.

```
rounds 1..8   choices        ->  Dossier (~10 parameters)
rounds 9..12  Dossier + ops  ->  ONE engine  ->  results
```

The early rounds **simulate nothing**. They are a form: choices map to parameters
through a lookup table. The single engine lives downstream and is the only piece
that computes.

**Why it pays three times.**

1. One engine survives, so a later module is the same engine with a pre-filled
   artifact instead of a cohort-built one.
2. The mapping table is data, so the owner can retune it with no deploy — which
   is exactly the layer where their expertise belongs and yours does not.
3. It produces **delayed consequence**, which is usually the pedagogical or
   product point: the team that skipped validation in round 3 pays in round 9,
   and the result screen can show them precisely why.

**Generalizes to:** onboarding that configures later behaviour, assessment with
heterogeneous item types, character creation, any "setup then play" product.

---

## 2. Reward variance reduction, not the mean

**Problem.** In any scored or gamified flow, if a virtuous choice maps to "more
points", participants stop reasoning and optimize for the known-correct answer.
The experience degrades into a quiz with steps.

**Pattern.** Draw a hidden ground truth at start. Let effort buy **precision
about it**, never a better value.

```
hidden_truth ~ Uniform(lo, hi)          # never displayed
noise        = k * (1 - effort)
shown        = hidden_truth * (1 +/- noise)
```

| Effort | What the participant sees |
|---|---|
| none | "between 90 and 700" — useless |
| high | "between 290 and 350" — actionable |

**Consequences you get for free.**

- Nothing can be memorized as "the right choice"; you buy **information**, paying
  in time, money, and scope.
- Thorough investigation of a bad idea reveals precisely that it is bad — so
  *abandoning or pivoting becomes the rational move*, which is often the lesson
  the owner actually wants taught.
- Two participants with identical downstream decisions and different outcomes
  have a **legible** explanation rather than a coin flip.

**Mandatory check before shipping:** simulate many runs and confirm the diligent
strategy beats the careless one *on average*. If it does not, the mechanic is
decorative and the model is wrong.

**Generalizes to:** research and discovery phases, due-diligence mechanics, any
system where you want to teach the value of information.

---

## 3. Re-derive the consequences the owner did not state

Owners answer in their own frame. Second-order effects land in yours. Walk the
answers looking specifically for changes to **arity, simultaneity, and
ownership**:

| Their answer | Derived consequence they did not mention |
|---|---|
| "teams instead of individuals" | submission authorship, per-member assessment, one absentee blocks a team |
| "some competition between them" | closing becomes a **cohort-wide simultaneous** calculation; needs atomic close, rollback, and an explicit absence policy |
| "panel of dimensions, not one score" | some dimensions are computable, others are human judgement — draw that line explicitly |
| "real-world data drives it" | a graded 12-round game cannot have its balance hostage to last week's exchange rate |

That last one deserves its own rule: when real external data feeds a balanced,
graded experience, **demote the data from engine to layer**. Calibrate on
reference values, let live indicators enter as bounded deviation, clamp the
total, and fall back to reference with a visible notice when a source is down.

---

## 4. Text is never scored automatically

Owners ask for "quality of reasoning" as an evaluated dimension. Keep it, and
keep it human.

Automatic scoring of free text produces a wrong grade wearing the costume of an
objective one — and the owner loses the argument the moment a participant
contests it. The system **stores, organizes, presents side by side, and
exports**; a person grades.

**The hybrid case** is where this gets decided: a field that is written *and*
must drive the engine (a value proposition, a strategy statement). Resolve it by
splitting the input — free text for human reading, plus a **closed-list choice**
of axes for the machine. Never parse the prose.

---

## 5. Calibrate in parallel, not in series

A spec-first process is right and worth agreeing with. Its blind spot is narrow
and specific: **balance is an emergent property and cannot be validated in a
document.** You can write a hundred pages, approve them, build them, and learn in
round 8 of the pilot that one strategy dominates.

So propose a cheap simulation — spreadsheet or script, explicitly **not the
system** — running alongside the early documentation stages. It costs days,
produces no throwaway code, and answers before any screen exists:

- does any strategy win too often?
- does the diligent strategy beat the careless one?
- is a late-stage crisis recoverable, or a death sentence?
- is the spread between best and worst discussable, or humiliating?
- is the outcome decided too early to stay interesting?
- does randomness dominate repeated runs of the same strategy?

Set a pass/fail threshold per question **before** running, and treat a failure as
"change the model now", not "tune it during the pilot".

Ordering rule that follows: build the **engine before any screen**, and make the
first playable deliberately ugly. A polished clickable prototype validates screen
flow; what needs early validation is whether the thing works at all. Cut from the
polish end, never from calibration.

---

## 6. Invariants worth fixing on day one

Cheap now, structurally expensive later, and all three came from owner answers
rather than technical taste:

1. **A closed round is immutable.** Never recompute a published result, not even
   to fix a rule — corrections create a new round. Otherwise a grade changes
   after it was already discussed in public.
2. **Freeze external indicators into the round** with value and provenance, so
   the run is reconstructible years later with every upstream source offline.
3. **Record who submitted and when.** In group work it is the only objective
   trace of individual participation, and it cannot be reconstructed later.
