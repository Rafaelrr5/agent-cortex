---
name: isolated-worktree-testing
description: "Use when testing tracked local changes away from the source checkout. Capture before switching."
---

# Isolated worktree testing

Use a detached worktree to test a captured revision without switching the source
branch. Git worktrees share repository metadata: this is checkout isolation, not a
security sandbox. Untrusted commands need a separate security boundary.

## Supported snapshot

`python scripts/capture_worktree.py SOURCE TARGET` resolves source HEAD and captures
`git diff --binary HEAD` **in the source checkout before creating the worktree**.
This combines staged and unstaged tracked content relative to HEAD; it does not preserve
index staging distinctions. TARGET must not exist. No fetch, checkout, merge or push occurs.

The helper refuses untracked nonignored files and submodules before creating anything.
It does not silently omit new source files. If new files are required, stop and choose an
explicit reviewed snapshot method; do not stage files merely to evade this restriction.
Ignored files (including ignored new source files), local secrets and dependency installs
are not copied. Review ignore rules and expected file coverage first. Do not edit the
source concurrently: capture is not transactional. Compare source status before/after
and repeat if another writer changed the intended snapshot.

## Procedure

1. Review source status including ignored/untracked files, intended base and acceptance.
2. Capture using the helper. Record the printed base SHA and patch SHA-256.
3. Run project-specific tests in TARGET, with independent dependencies and disposable
   data. Disable implicit package publishing. A smoke check is not full-suite coverage.
4. Record commands, real exit codes, tested revision and failures. Apply/build failures
   leave the worktree available for inspection; a failed capture never means verified.
5. Inspect TARGET status. Remove only the exact disposable worktree, via
   `git -C SOURCE worktree remove TARGET`. Dirty trees require review and explicit
   cleanup authorization; never use blanket recursive deletion or automatic `--force`.

Never share `node_modules` by symlink or junction, and never delete dependencies in
an inherited linked directory. If a tool creates links/reparse points, stop and inspect
ownership and targets before cleanup. The helper performs no recursive cleanup.

Run tests: `python -B -m unittest discover -s tests -v`.
Tests create disposable local repositories under TMPDIR, with no remote or credentials.

## Provenance

Rewritten from the supplied `verification-workflow` source, whose metadata declares
MIT licensing and machine-generated authorship (no named human author). Source notices
must be retained by the distributor where required; this summary does not replace a
license grant. This version removes the stale post-switch diff and shared-dependency advice.
