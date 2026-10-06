---
name: agent-branch-integration
description: "Use when reviewing delegated branches for integration. Gate the exact candidate revision."
---

# Branch integration gate

A completed task or green worker report does not prove compatibility with the current
base. The integrator owns evidence and authorization, not automatic publication.

## Contract

Read the original scope, subsequent decisions, allowed paths, acceptance and pending
approvals. Resolve conflicting instructions by authority and explicit supersession,
not by assuming the newest comment is authorized. Do not commit, amend, rebase, merge,
push or release without the applicable permission. Preparation approval is not merge approval.

## Read-only gate

Run `python scripts/check_candidate.py REPO BASE CANDIDATE`.
It resolves exact commits, refuses a candidate not descended from BASE and reports
changed paths and both SHAs as JSON. It does not run tests or claim integration success.
Do not confuse ancestry with compatibility or changed paths with scope authorization.

1. Review the complete diff, new source files, secrets and allowed scope; do not stage all.
2. Verify the candidate in a detached disposable worktree with independent dependencies.
   Run acceptance tests and, where relevant, check again after the build to catch output
   unexpectedly included in lint/typecheck inputs. Never delete shared linked dependencies.
3. Record local checks and CI results against the **same exact SHA**; distinguish skipped
   tests and platform differences. Local results do not invent unavailable CI evidence.
4. Immediately before an approved integration, re-resolve base and candidate. Any movement
   invalidates the old readiness decision. Stop for conflicts; do not blindly prefer one side.
5. If explicitly authorized, perform the repository's approved integration strategy.
   Never force-push a shared branch. Publication is a separate authorization gate.
6. Read back the resulting branch SHA and relevant remote state before claiming success.
   Release dependent work only when the required integrated revision is actually available.

No daemon, board, credential workaround or automatic cleanup is needed. Permission
blocks remain blocks. Keep a handoff with tested SHAs, commands, verdict, pending owner
and next action; report integration and publication as separate states.

Run tests: `python -B -m unittest discover -s tests -v`.
Tests use only disposable local repositories under TMPDIR, with no remote.

## Provenance

Adapted from the supplied same-named local procedure. Its metadata declares MIT licensing
and machine-generated authorship, with no named human author. Distributors must retain
required source notices; this summary is not a replacement license grant. Private runtime
conventions and product-specific anecdotes were removed, not presented as general evidence.
