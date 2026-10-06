---
name: delivery-verification
description: "Use when closing or resuming multi-step work. Verify acceptance before declaring delivery."
---

# Delivery verification

Extract a contract before executing: objective, allowed and forbidden scope, owner,
source of authority, observable acceptance criteria, evidence, pending decisions,
and next step. Keep one canonical editable handoff, not two competing queues.

## Decision rules

- Local reversible changes require scope authorization; publication, spending,
  destructive actions and external sends require specific approval.
- A worker report, completed status or successful process exit is a claim, not proof.
  Read the artifact and run nonempty checks against the actual acceptance criteria.
- If a baseline, source or criterion is missing, mark that criterion inconclusive.
  Do not turn absent telemetry into zero failures.
- After an external write, read back the exact target. Local tests do not prove deployment.
- Resume from the handoff and validate local reality; stale notes are not installed state.
- Permission failures are blockers, not invitations to bypass controls. Retry operational
  failures only with a reason and a bounded budget.

## Evidence contract

Each criterion needs an ID, an observed result, evidence and a verdict: `verified`,
`failed`, or `inconclusive`. Completion requires every criterion verified and no pending
items. Evidence should identify command, exit code, artifact and revision where relevant.
Never include secrets in evidence. Report unknowns explicitly.

Run `python scripts/check_delivery.py report.json` from this skill directory.
The checker validates structure and recorded verdicts only: it cannot establish that
someone ran the command or that evidence is truthful. Independently inspect evidence.

Minimal report:

```json
{"criteria":[{"id":"smoke","status":"verified","evidence":"python -m unittest: exit 0; smoke assertion passed"}],"pending":[]}
```

Run tests: `python -B -m unittest discover -s tests -v`.

## Closure

Return the artifact or usable link, verified results, remaining limitations and the
next owner/action. Do not say an attachment was sent unless the outgoing message
actually contains it. Save procedure separately from project-specific decisions.

## Provenance

Adapted from the supplied local `workflow-delivery` procedure. No named human author
or license was declared in that source; no third-party authorship or license is inferred.
This rewrite removes private orchestration and storage conventions.
