---
name: premortem
description: "Premortem any plan with consequences, unprompted: causes of death, early signals, a watch."
version: 1.0.0
author: Rafael Rocha Ribeiro (github.com/Rafaelrr5)
license: MIT
platforms: [linux, macos, windows]
metadata:
  agent:
    tags: [premortem, risk, planning, strategy, monitoring]
    related_skills: [hermes-cron-jobs, measurement-validity]
---

# Automatic premortem

Whenever the user brings a plan with consequences, run a premortem **without being
asked**. The goal is a plan that does not die, not a report.

## When to Use

Any plan with consequences: a project, product, launch, purchase, career move,
exam, deployment, partnership, schedule. Naming a project is enough to trigger it.
Skip trivial tasks and anything undone in minutes. Depth follows risk: a small
plan gets two or three lines, a large one the full version.

## Procedure

1. **Ground it first.** Pull the real state before forming an opinion: the
   project's notes, `git log` (pace, date of the last commit, size of the backlog),
   and metrics read-only where a source exists. A premortem without numbers is a
   generic guess. Mark what cannot be measured as unknown.
2. **Project forward:** "Three to six months from now, this plan is dead. Why?"
   Write concrete causes, each with the mechanism that kills the plan.
3. **Rank** by likelihood × impact. Keep at most five.
4. For each cause give an **early signal** that is observable and numeric, a
   **mitigation** cheap enough to do now, and where useful a **cut-off criterion**
   (the number at which you stop or change course).
5. **Check the common causes of death:**
   - a step depends on someone remembering to do it → make it a scheduled check
     that notifies them;
   - scope or feature velocity far ahead of real usage (many specs, almost no
     users) → freeze and measure;
   - monetising before traction (charging to post, ads) kills supply in a cold
     marketplace;
   - re-scoping midway → structure the work so a change costs a document, not code;
   - dependence on a third party: app store, account, credential, free-tier
     quota, external approval;
   - a deadline with no intermediate checkpoint; a hidden recurring cost; "done"
     without evidence.
6. **Ask one short question** about the decisive missing number (real users,
   third-party content, conversion). When answered, **re-rank**: say which cause is
   already happening and show the number that proves it.
7. **Turn the signals into a watch**, not text. When the user gives the starting
   numbers, they are agreeing to be watched: create the job, test it, and record it
   (see below).

## Output (short)

```
Premortem
1. <cause>: signal <observable number>; prevent <cheap action now>
...
Doing now: <watch / checkpoints>
```

Then keep helping with the plan. The premortem travels with the plan; it is not a
sermon or a gate.

## The signal watch

A scheduled script with no model call, silent on a normal day. It prints only in
three cases:

1. a weekly scoreboard (e.g. Mondays): the handful of numbers from the premortem,
   the last commit, the current phase goal;
2. a **new** alert when a signal crosses its threshold, deduplicated per ISO week
   (`%G-W%V`) in a state file kept in a durable directory;
3. a milestone reached, once (the first outside contribution, the first paying
   user).

Real errors print loudly; empty stdout means nothing is sent.

Count thresholds from `max(last event, start date)`, so the watch does not fire on
its first day. Separate the owner's own activity from everyone else's (list the
owner's accounts once the user confirms them) and treat imported or seeded items
separately. A marketplace full of seeded listings with zero takers is empty of
people, not of content, and that changes the recommendation.

**Test before saying it is live.** Put a date override behind an environment
variable instead of calling `date.today()` directly, and run four cases: today
(silence expected), a Monday (scoreboard), a date past a threshold (alert), and a
second day in the same week (dedup, so silence). Reset the state between cases.
Then follow `hermes-cron-jobs`: gateway running, one natural run, and no
celebration just because the job was created.

Report back in one line per item: what it watches, when it speaks, the earliest
date an alert can fire, and what was tested.

## Pitfalls

- A generic risk ("it might go wrong", "lack of time") is useless. Name the
  mechanism and the number that reveals it.
- Do not repeat the premortem of the same plan on every message. Re-evaluate only
  when the plan or the data changes.
- Never invent a traction metric. Server logs mix bots and people; count rows in
  the database, or ask.
- Read production data read-only and as aggregates. Never pull rows with personal
  data into the conversation.
- Compare what the database holds with what the public API returns. Data that is
  loaded can still be invisible in the app.
- Before creating a watch, list the project's existing scheduled jobs. A technical
  error monitor is not a traction monitor. Complement it, do not duplicate it.
