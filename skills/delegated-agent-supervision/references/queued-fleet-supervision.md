# Supervising a queued agent fleet

Companion to Law 2. Where the main skill covers verifying a *single* delegated
agent's summary against git, this covers verifying a *board or queue* of
dispatched workers against their own logs.

Evidence recorded 2026-09-04, device FA, ~12 concurrent tasks on one board.

## The task record attributed the wrong cause

Two tasks pinned to the top model tier were parked as blocked with the
diagnostic:

```
!! [error] Agent crash x2: pid 19492 not alive
   consecutive_failures=2 | most_recent_outcome=crashed
   failure_threshold=2 | failure_limit=2
```

Nothing there says quota. The worker log did:

```
rate_limit_error
  error_code: credits_required
  disabled_reason: org_level_disabled
  can_user_purchase_credits: false

-> failover to secondary account

HTTP 429  usage_limit_reached
  plan_type: prolite
  resets_in_seconds: 395948        # ~4.5 days

-> 3 retries with backoff -> process exit -> "crashed"
```

The supervisor observed a dead process and recorded a crash. That is a correct
observation and a wrong diagnosis. **The log is the evidence; the status is a
self-report.**

Why the fallback chain did not save it: each tier's fallback pointed at another
subscription account. When both paid windows exhausted together, there was no
floor. The fix was pinning the affected work to a per-token API-key provider,
which has no shared window to exhaust. Worth keeping at least one such provider
reachable precisely so there is somewhere to land.

## Reading the reset horizon

The 429 payload carries `resets_at` / `resets_in_seconds`. Use it:

- resets in **hours** — waiting is reasonable
- resets in **days** — waiting is not a plan; re-route

## Recovery sequence

An override alone changes nothing — it is read at the *next* dispatch, so a
blocked task sits there with a shiny new setting and no progress. All three
steps are required, in order:

1. Apply the provider/model override to each affected task.
2. Release the block, recording *why* the route changed in the reason.
3. Trigger a dispatch pass and read how many workers were actually spawned.

Then **wait 1–2 minutes** and re-read. Three fields, together:

- current status
- last failure error — populated while *running* means it already died once
- block kind — separates "needs a human decision" from "technical failure"

## What the second read changed

First read, taken immediately after dispatch: 10 running, 2 waiting.
Reported to the user as ten tasks executing in parallel.

Second read, minutes later: 4 genuinely running, 4 finished, 3 blocked awaiting
human decisions, 2 dead from the quota cascade.

The first report was wrong in every column that mattered. The only cost of
getting it right was waiting two minutes.

## Lead the report with the human decisions

When the fleet drained, the genuinely valuable output was three questions that
no model could answer:

- a security remediation needing explicit authorization before touching live
  access control
- a scope question (does a requirement still apply, given the world changed?)
- a missing integration credential blocking write-back to an external tracker

Each came with the evidence the worker had already gathered. Those belong at
the top of the report, stated plainly enough to answer in one message — not
buried under a list of what completed.
