# Two-stage delegation: read-only reviewer, then a ranked implementation session

Validated 2026-09-04 on a real audio pipeline (music_assistant): 1 review
subagent (~10 min, 31 calls) + 1 unattended `claude -p` run that landed 10/10
ranked fixes as 10 separate commits, 159 new tests, 1554 passed, mypy strict
clean, zero out-of-scope files, zero binary artifacts committed. The user asked
for exactly this shape ("prossiga ate finalizar a sessao, seguindo o rank").

## Why two stages

A single "fix this project" prompt gives the agent both the diagnosis and the
licence to act on it, and its report mixes the two. Splitting them:

- The **reviewer** runs read-only, in an isolated context (`delegate_task`),
  with the FULL problem history you hold (brain/L1 facts, past measurements,
  what was already tried). It must cite `file:line`, prove claims by running
  code, and rank improvements by impact on the *actual result*, each with a
  `how_to_verify`. Its output is a spec, not a change.
- The **implementer** runs unattended (`claude -p ... < prompt.md`,
  `terminal(background=true, notify=true)`, timeout 18000) with the review
  file as its only spec and a strict per-rank loop. It is told to keep going
  through the ranks until the session runs out.

The review becomes a durable artifact (drop it in Downloads with a dated name),
the implementer's log becomes the audit trail, and both are checkable.

## Reviewer prompt — the parts that mattered

- Paste the *measured* problem statement, not the symptom ("sounds bad").
  The reviewer then verifies each measured claim instead of re-deriving it.
- List what was already delivered and ask "is it wired into the product path
  or only in scripts/training?" — that question alone surfaced the main bug
  (a script-only env override hiding a renderer defect).
- Demand: status table per known problem (solved / partial / open with
  evidence), max 10 ranked improvements with where/why/how_to_verify/effort,
  a "proven by running code" list with actual output, and a "could not verify"
  list. Use `output_schema` so the result is machine-splittable.
- Read-only, no network, no LLM generations (deterministic and cheap).

## Implementer prompt — the per-rank loop (copy this)

```
Implement the ranked improvements IN ORDER (1 -> N) for as long as you can in
this session, one at a time, each as a separately verified and committed unit.
Do not skip ahead; do not batch several ranks into one commit. If a rank is
infeasible or contradicted by the code, write why in <LOG> and move on.

PER RANK:
1. Read the cited code paths (file:line). Confirm the claim against the
   current code BEFORE changing anything.
2. Smallest change that fully solves it, in the repo's conventions.
3. Unit test that fails before and passes after (RED -> GREEN). Run the
   targeted file, then the whole suite.
4. Verify OBJECTIVELY with the method the review gives for that rank. <Name
   the objective instrument and its known blind spot here — see below.>
5. Append to <LOG>: rank, files, test added, ACTUAL measured before/after
   numbers from commands you ran (never estimated), caveats.
6. Commit in the repo's voice; stage only that rank's files; never .env /
   .db / media / venv. Never push, never rewrite history, never delete tests.

When the session is running out or all ranks are done: tree clean or stashed
with a clear message; finish <LOG> with a FINAL STATUS table
(DONE sha / SKIPPED why / IN PROGRESS what remains); stop.
Final stdout: only the FINAL STATUS table and the log path.
```

Per-rank overrides worth writing when they apply (each one prevented a
plausible shortcut this session):

- Backward compatibility as a **byte-identity** test ("plans without the new
  field must render byte-identically; add a regression test proving it").
- Local artifacts (SQLite catalog, generated media): implement the change as
  an idempotent script + stop the source of duplication, run it, do NOT
  commit the artifact.
- Thresholds configurable but default ON.
- No LLM in the loop: replace "A/B over generations" with "assert the injected
  text appears in the built prompt + a hand-written plan passes the checker".

## Name the instrument's blind spot explicitly

The review found that the project's objective scorer anchored on drums and
literally could not see the bass desync it was being asked to prove fixed. The
implementer prompt said so in one line:

```
Do NOT trust "score unchanged" as proof for rank 1 — the scorer anchors on
drums and cannot see the sub desync. Measure <the direct observable> instead.
```

The agent then built a direct probe, reported the score flat at 85 *and* the
real metric moving, and found a stronger proof (product render byte-identical
to the known-good workaround render). Without the line, "score unchanged"
would have been reported as success. This is the same law as `measurement-
validity`: check the instrument before trusting the number.

## Expect the implementer to contradict the reviewer

A reviewer that could not run everything will get some open items wrong. In
this session 3 of 10 ranks flipped on measurement (a "lying metric" was real
clutter; a key the reviewer leaned toward was refuted 2:1 by a pitch histogram;
only 11 of 86 "duplicate" rows were actual duplicates). Because the loop said
"confirm the claim before changing anything" and "write why if contradicted",
the agent answered the question instead of forcing the reviewer's fix. When
relaying, surface those contradictions first — they are the most valuable part
of the run and the part the user would otherwise trust wrongly.

## Post-run verification actually performed

```bash
git log --oneline <start-sha>..HEAD            # one commit per rank, in order
git status --short                             # only pre-existing dirt
git diff --name-only <start-sha>..HEAD | grep -Ei '\.(db|mp3|wav|env)$|^uploads/|^venv/'
<venv>/python -m pytest tests -q               # re-run the totals yourself
<venv>/python -m mypy src --strict
cat one rank's report JSON                     # the numbers exist and match the log
```

Then write the outcome (commits range, headline numbers, the contradictions,
the open follow-ups the log itself lists) to the project's L1 facts.
