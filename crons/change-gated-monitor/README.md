# Stable latest-request identity

Standalone Python 3.12+ standard-library example. No agent framework, credentials, service integration, daemon, or real scheduler is required.

## Contract

Input is a JSON array. A request is `{"id":"request-1","sequence":1,"kind":"request"}`; replies use `"kind":"reply"`. Sequence numbers must increase for newly created requests. Identity is `(sequence, id)`; a deterministic lexical ID tie-break handles equal sequences. Content and reply status are deliberately not part of stdout. Empty rolling snapshots retain the last identity. On missing/malformed input, stdout repeats the persisted identity, stderr exposes the outage, and exit status is 1. Fresh successful empty state is `{"id":"","sequence":-1}`. Fresh outage emits that sentinel but does not persist it. Corrupt state fails rather than inventing a baseline.

The caller compares successful stdout with its previous baseline to wake work once. Never advance a scheduler baseline on nonzero exit status. The monitor records an observation, not successful processing or message delivery. It does not execute an agent, fetch a service, or acknowledge a request.

## Run and verify

From this directory, with Python 3.12+ available as `python`:

```sh
python -B job.py --help
python -B test_job.py -v
```

The tests are the runnable, self-contained fixture recipe: each creates an isolated temporary directory, invokes the real CLI with explicit paths/arguments over multiple ticks, asserts state and stdout, and removes its fixtures afterward. Git tests create throwaway local bare remotes and clones; their commits and pushes are confined to those fixtures, never this source repository. `TMPDIR`, when set, selects the parent for temporary fixtures. Nothing is installed.

For an explicitly prepared local fixture or repository, replace every `/ABSOLUTE/...` below with your own native absolute path (on Windows use `C:/...`, not an MSYS `/c/...` path):

```sh
python -B job.py --feed /ABSOLUTE/fixture/feed.json --state /ABSOLUTE/runtime/state.json
```

Feed files use UTF-8 JSON arrays; state is created on the first successful tick. The job fails visibly on corrupt state rather than resetting it. Keep fixture data and state outside this source repository. There are no hidden home-directory defaults. Numeric time arguments are caller-supplied Unix-style seconds, allowing deterministic tests; a scheduler wrapper must supply the current time explicitly.

## Scheduling is disabled

`scheduler.example.json` is inert documentation, not an executable scheduler definition. `enabled` is false and command/destination values are empty. These scripts never read it and never create or run a scheduled task. Do not register any task until you have reviewed fixture results and deliberately opted in.

To configure your own scheduler later, explicitly select an absolute Python executable and script path, copy the complete CLI argument list, select a cadence/cooldown, supply time where required, and disable overlapping runs. Capture stdout, stderr, and exit status. No transport destination is provided: notification channels and credentials are exclusively caller-supplied. An exit status only reports local execution, never delivered notifications or completed downstream work. Use an acknowledgment-capable delivery adapter if actual delivery matters.

## Limitations

Single-writer state only: atomic replacement prevents partial JSON, but does not provide locking, multi-process consistency, or exactly-once delivery. A fixed `.tmp` sibling is used; do not run overlapping ticks against the same state. Do not trust externally editable state or feeds as authorization. No power-loss fsync guarantee, network recovery adapter, destination configuration, or secret storage is implemented. Keep runtime files private and back them up. A scheduler must visibly surface stderr/nonzero status rather than silently swallowing errors.
