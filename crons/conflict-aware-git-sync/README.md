# Conflict-aware local Git reconciliation

Standalone Python 3.12+ standard-library example. No agent framework, credentials, service integration, daemon, or real scheduler is required.

## Contract

Requires Git on PATH and a trusted throwaway or explicitly selected repository. Existing unmerged entries block all changes. An optional caller-supplied `--local-remote /ABSOLUTE/remote.git` must be a filesystem bare repository; no configured remote URLs are used. Fetch disables submodule recursion. Fast-forward updates are allowed. A conflicted incoming merge is aborted, preserving local HEAD; a clean but divergent merge is also aborted for manual review. No force reset, automatic conflict resolution, union merge, or push occurs.

Without `--commit-owned`, the job never creates commits. To opt in, add `--commit-owned --owned-path owned.txt` (repeat for more files). Paths must be individual previously tracked files within the root, not directories, traversal, untracked files, or Git metadata. Literal pathspecs prevent wildcard staging. `git commit --only` excludes unrelated staged content and preserves it in the index. It commits current working-file contents for the explicitly owned files, not just previously staged hunks. Tracked deletions are supported. Repository state/alert JSON must be outside the repository.

A blocked tick exits 1. The substantive stdout alert is emitted at most once per cooldown; intervening ticks still print a visible blocked/rate-limited status and exit 1. This is stdout rate limiting, not notification delivery. State is saved after emitting stdout; a crash can repeat an alert. Git errors are stderr/nonzero, never disguised as success. Existing dirty changes can prevent merging; the job leaves resolution to the caller. Git configuration and hooks are trusted and may run local commands: do not use an untrusted repository/configuration. No publication path exists in this example.

## Run and verify

From this directory, with Python 3.12+ available as `python`:

```sh
python -B job.py --help
python -B test_job.py -v
```

The tests are the runnable, self-contained fixture recipe: each creates an isolated temporary directory, invokes the real CLI with explicit paths/arguments over multiple ticks, asserts state and stdout, and removes its fixtures afterward. Git tests create throwaway local bare remotes and clones; their commits and pushes are confined to those fixtures, never this source repository. `TMPDIR`, when set, selects the parent for temporary fixtures. Nothing is installed.

For an explicitly prepared local fixture or repository, replace every `/ABSOLUTE/...` below with your own native absolute path (on Windows use `C:/...`, not an MSYS `/c/...` path):

```sh
python -B job.py --repo /ABSOLUTE/throwaway/repo --state /ABSOLUTE/runtime/git-state.json --now 100 --cooldown 60
```

Feed files use UTF-8 JSON arrays; state is created on the first successful tick. The job fails visibly on corrupt state rather than resetting it. Keep fixture data and state outside this source repository. There are no hidden home-directory defaults. Numeric time arguments are caller-supplied Unix-style seconds, allowing deterministic tests; a scheduler wrapper must supply the current time explicitly.

## Scheduling is disabled

`scheduler.example.json` is inert documentation, not an executable scheduler definition. `enabled` is false and command/destination values are empty. These scripts never read it and never create or run a scheduled task. Do not register any task until you have reviewed fixture results and deliberately opted in.

To configure your own scheduler later, explicitly select an absolute Python executable and script path, copy the complete CLI argument list, select a cadence/cooldown, supply time where required, and disable overlapping runs. Capture stdout, stderr, and exit status. No transport destination is provided: notification channels and credentials are exclusively caller-supplied. An exit status only reports local execution, never delivered notifications or completed downstream work. Use an acknowledgment-capable delivery adapter if actual delivery matters.

## Limitations

Single-writer state only: atomic replacement prevents partial JSON, but does not provide locking, multi-process consistency, or exactly-once delivery. A fixed `.tmp` sibling is used; do not run overlapping ticks against the same state. Do not trust externally editable state or feeds as authorization. No power-loss fsync guarantee, network recovery adapter, destination configuration, or secret storage is implemented. Keep runtime files private and back them up. A scheduler must visibly surface stderr/nonzero status rather than silently swallowing errors.
