# Long task prompts via stdin

## When to use

Use for multi-part background coding tasks, especially on Windows. Save a Markdown brief, then redirect it to the CLI's stdin in a single background terminal call. No Python/shell launcher, visible terminal window, or PTY is needed.

```
write_file(path="C:/Users/<user>/Downloads/task_brief.md", content="...")
terminal(
  command="claude -p --dangerously-skip-permissions --max-turns 200 < C:/Users/<user>/Downloads/task_brief.md",
  workdir="C:/path/to/repo", background=true, notify=true, timeout=18000
)
```

## Rules

- Use `< prompt.md` (stdin), NOT `"$(cat prompt.md)"`. Shell substitution expands the entire file back into argv and DOES NOT avoid the Windows command-line length limit. File indirection is useful only if the CLI reads the file or stdin itself.
- Keep a human-readable Markdown brief as the scope/acceptance artifact; it is not a launcher script. Do not add it accidentally to the repo's commit.
- Specify exact allowed files, protected pre-existing changes, verification commands and boundaries for network, credentials, deployment and git operations. Long print-mode tasks cannot be steered mid-flight.
- Inspect the project's real CLAUDE.md/spec first. Do not contradict product decisions or repo gates with generic instructions.
- Use `background=true, notify=true`. Read process output once after startup to confirm active work rather than an immediate auth/flag failure; completion notification handles the rest. Repeated long `wait` calls time out and add no value.
- A live process is not completed work. On notification, verify diff/status and rerun the checks relevant to the final code before claiming success.
- When project environment keys override the CLI's existing authenticated account, remove those variables from this subprocess only. Never rewrite credentials or switch organizational context to make a task run.
