# Delegation Prompt Skeleton and Verification Recipe

Distilled from a session where six one-shot `claude -p` delegations fixed a
real audio pipeline. Five stayed in their lane; the one handed an unfenced
"the whole tree is yours" rewrote packaging, deleted `pytest.ini`, and created
an unrequested subproject alongside its (correct) fix.

## Full prompt skeleton

```
You are working in <repo> (read CLAUDE.md / AGENTS.md first).

## SCOPE
Your scope is ONLY:
  - path/to/file_a.py
  - tests/unit/test_file_a.py
Do NOT modify any other file. Commit only those paths with explicit
`git add <path>` — never `git add -A` or `git commit -a`. Do NOT push.
If the task appears to require touching anything outside that list, STOP and
report what you would need and why. Do not do it.

[Parallel runs only:]
ANOTHER AGENT IS WORKING CONCURRENTLY on <their files>. Do not touch those.
If you hit a conflict, stop and report rather than resolving across scopes.

## THE PROBLEM
<what is broken, with the measurements you already took>
Re-verify these numbers yourself before changing anything; do not take them
on faith.

## WHY THE EXISTING GUARD MISSED IT
<if a test or assertion should have caught this but didn't, say why — it is
 usually the same bug class you are about to fix>

## WHAT TO DO
<numbered concrete steps>
<name the source of truth explicitly, e.g. "read pattern_steps from the
 catalog row; do NOT parse it back out of the filename">

## VERIFY IT, DO NOT ASSUME
<the specific checks that would catch a fake success>

CRITICAL: <harness> SWALLOWS exceptions and writes a ZERO-BYTE output file.
`ls -la` the output and confirm non-empty BEFORE reporting any score.

The success criterion is NOT a higher number. It is <specific observable>.
If the score DROPS because a previously-hollow check now has real content to
judge, that is a GOOD outcome — say so plainly with the numbers.

## RULES
- <lint / type / test gates that must pass>
- Small logical commits in this repo's existing style. Do NOT push.
- Comments explain WHY, not what.
- Measure everything you claim. Never report a number you did not compute.
- If the fix does not fully work, say so with the numbers.
  An honest 85 beats a hollow 100.
```

## Invocation notes (Windows / git-bash, locally-logged-in CLI)

```bash
cd <repo> && unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN ANTHROPIC_BASE_URL \
  && cat <<'PROMPT' > "$LOCALAPPDATA/Temp/task.txt"
<prompt body>
PROMPT
claude -p --dangerously-skip-permissions < "$LOCALAPPDATA/Temp/task.txt" 2>&1
```

Launch with `terminal(background=true, notify=true)`; follow with
`process(action='poll')`.

- **Prompt goes through stdin, never argv.** A real task prompt exceeds the
  Windows command-line length limit.
- **`unset` the three Anthropic vars** when the project's `.env` exports an API
  key: the CLI prefers it over its own subscription login and can refuse to
  start (`connectors are disabled because ANTHROPIC_API_KEY or another auth
  source is set`). The exception is `--bare`, which requires the key.
- Heredoc-to-file then redirect is more robust than piping the heredoc straight
  in when the prompt body contains backticks or `$`.

## Post-run verification

```bash
git log --oneline -10               # commits you did not ask for?
git status --porcelain              # files outside the fence?
git show --stat <sha>               # what is actually in that commit?
git diff <in-scope-file>            # is the requested fix actually there?
```

Then re-measure, yourself, the numbers the conclusion depends on.

### Verifying a "pre-existing failure" claim

```bash
git stash push -u -- tests/          # or: git checkout <commit-before-run>
<run the failing test>               # does it fail here too?
git checkout -                       # restore
git stash pop
```

Confirmed pre-existing = not your agent's problem, and worth telling the user
so they don't attribute it to today's work. Unconfirmed = investigate.

### Attribution when agents ran concurrently

Compare commit timestamps against each run's window. If another agent's commit
landed inside your agent's run, any end-to-end improvement is jointly caused.
Ask for (or build yourself) a controlled measurement that varies only the one
thing you care about.

## If the agent went out of scope

1. Back up the in-scope work: `cp <good-file> "$LOCALAPPDATA/Temp/<name>.bak"`.
2. Do **not** revert or delete unilaterally — destructive, irreversible, and
   the extra work is sometimes independently valuable.
3. Present to the user: in scope / out of scope / recommendation, and let them
   choose. Expect deletion commands to require explicit consent; that block is
   correct behaviour, not an obstacle to route around.
