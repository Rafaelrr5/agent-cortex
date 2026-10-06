# Approval-aware bounded retry simulation

Standalone Python 3.12+ standard-library example. No agent framework, credentials, service integration, daemon, or real scheduler is required.

## Contract

Input is a local JSON array, for example `[{"id":"task-1","revision":"v1","kind":"operational","result":"error"}]`. Allowed kinds are `operational` and `needs_input`; allowed simulated outcomes are `success` and `error`. This script performs no external work: the fixture outcome simulates a local processing result.

An operational attempt is allowed after the explicit cooldown, up to the per-ID lifetime limit. Only success acknowledges that exact revision. Errors update attempt/cooldown bookkeeping but never consume the revision. New revisions do not reset the retry budget. A previously successful revision is skipped. `needs_input` is always reported and never attempted or acknowledged, even when its fixture says success, and even after unlimited elapsed time. Changing classification must be an explicit trusted caller decision; the script does not infer approval. Unknown kinds fail closed. A duplicate ID or invalid item fails the entire tick before persistence. Errors/exhaustion exit 1; cooldown/human-wait exit 0 does NOT mean processing succeeded.

State is not automatically pruned: it retains retry budgets and acknowledgments. IDs are immutable and must not be reused. To retire entries, review them manually and ensure the feed cannot replay them. This demo has no receipt authentication and is unsuitable for untrusted feed producers.

## Run and verify

From this directory, with Python 3.12+ available as `python`:

```sh
python -B job.py --help
python -B test_job.py -v
```

The tests are the runnable, self-contained fixture recipe: each creates an isolated temporary directory, invokes the real CLI with explicit paths/arguments over multiple ticks, asserts state and stdout, and removes its fixtures afterward. Git tests create throwaway local bare remotes and clones; their commits and pushes are confined to those fixtures, never this source repository. `TMPDIR`, when set, selects the parent for temporary fixtures. Nothing is installed.

For an explicitly prepared local fixture or repository, replace every `/ABSOLUTE/...` below with your own native absolute path (on Windows use `C:/...`, not an MSYS `/c/...` path):

```sh
python -B job.py --feed /ABSOLUTE/fixture/feed.json --state /ABSOLUTE/runtime/state.json --now 100 --cooldown 10 --max-attempts 3
```

Feed files use UTF-8 JSON arrays; state is created on the first successful tick. The job fails visibly on corrupt state rather than resetting it. Keep fixture data and state outside this source repository. There are no hidden home-directory defaults. Numeric time arguments are caller-supplied Unix-style seconds, allowing deterministic tests; a scheduler wrapper must supply the current time explicitly.

## Scheduling is disabled

`scheduler.example.json` is inert documentation, not an executable scheduler definition. `enabled` is false and command/destination values are empty. These scripts never read it and never create or run a scheduled task. Do not register any task until you have reviewed fixture results and deliberately opted in.

To configure your own scheduler later, explicitly select an absolute Python executable and script path, copy the complete CLI argument list, select a cadence/cooldown, supply time where required, and disable overlapping runs. Capture stdout, stderr, and exit status. No transport destination is provided: notification channels and credentials are exclusively caller-supplied. An exit status only reports local execution, never delivered notifications or completed downstream work. Use an acknowledgment-capable delivery adapter if actual delivery matters.

## Limitations

Single-writer state only: atomic replacement prevents partial JSON, but does not provide locking, multi-process consistency, or exactly-once delivery. A fixed `.tmp` sibling is used; do not run overlapping ticks against the same state. Do not trust externally editable state or feeds as authorization. No power-loss fsync guarantee, network recovery adapter, destination configuration, or secret storage is implemented. Keep runtime files private and back them up. A scheduler must visibly surface stderr/nonzero status rather than silently swallowing errors.
