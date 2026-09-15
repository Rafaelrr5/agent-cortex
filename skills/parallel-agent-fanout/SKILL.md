---
name: parallel-agent-fanout
description: "Fan out one job to concurrent agents on one repo."
version: 1.0.0
author: Rafael Rocha Ribeiro (github.com/Rafaelrr5)
license: MIT
platforms: [linux, macos, windows]
metadata:
  agent:
    tags: [Delegation, Parallel, Claude-Code, Git, Orchestration, Ponytail]
    related_skills: []
---

# Parallel agent fan-out

Splitting ONE body of work across SEVERAL coding agents running at the same time
against the SAME repository and the SAME branch.

## When to Use

- The user asks for "some improvements" / "make it better" and the work decomposes
  into independent tracks (engineering, docs, presentation).
- Two or more agents will touch one repo concurrently.
- You are writing the prompt files that other agents will execute.

Not this skill: one agent, one task (use `delegate-coding-task` for opening a
single window; Claude Code documentation for the CLI surface itself). Not this skill:
resolving a collision that already happened (use a separate merge-reconciliation workflow).

## The three rules that make it safe

Concurrent agents on one branch collide in exactly two ways — same file, or stale
index. Both are prevented by contract, not by luck.

### 1. Disjoint file ownership, stated in every prompt

Give each agent an explicit list of files it owns, AND tell it who owns the rest.
Naming the other agents' territory is what stops the helpful drive-by edit.

```
Seus arquivos: `server.js`, `test/`, `.github/`, `package.json`
Agente B tem `public/`. Agente C tem `README.md`, `docs/`.
Fora da sua lista: não edita, anota no resumo final.
```

The escape hatch matters: **"anota no resumo final"** gives the agent somewhere to put
a legitimate cross-boundary need instead of silently taking it.

### 2. Rebase before every commit, push immediately

```
Antes de CADA commit: `git pull --rebase origin master` → commit → push na hora.
Commits pequenos, push imediato. Nunca acumule.
```

An agent that batches five commits then pushes will lose the race and hit a conflict it
was not briefed to resolve. Small + immediate keeps every agent's index fresh.

### 3. Name the dependency order, then hand over the keyboard

Agents that consume another agent's output must be told to wait and how to check:

> "Espere a tradução do agente B antes de capturar (`git pull`, veja se o português saiu
> do `public/`). Se depois de uma espera razoável não chegou, capture assim mesmo e diga
> no resumo que precisa refazer."

Always pair the wait with a **timeout escape**, or the agent blocks forever on a peer
that failed.

When you report to the user, give them the Enter order (dependency-last), not just the
list of windows.

## Prompt authoring — apply ponytail ultra to EVERY prompt

**First: confirm the skill EXISTS in the CLI on this device.** Claude Code
slash-command skills are installed per machine in `~/.claude/skills/<name>/SKILL.md`;
`~/.claude/CLAUDE.md` can document how to use them. **These are a DIFFERENT mechanism
from the skill files in this repository.** If `/ponytail` is not installed there,
the observed failure is `Unknown command: /ponytail`: the CLI treats the remaining
text as arguments to an unknown skill and **discards the entire prompt** — the window
opens, the agent sits idle, and nothing signals failure until the user checks it.

Install your own `/ponytail` command from your skills directory and verify it before
opening N windows; this repository does not supply that command:

```bash
mkdir -p ~/.claude/skills/ponytail
cp "<your-agent-skills-dir>/ponytail/SKILL.md" \
   ~/.claude/skills/ponytail/SKILL.md
# Verify the installed CLI's skill frontmatter; document usage in ~/.claude/CLAUDE.md
claude -p "/ponytail ultra
what is step 1 of the ladder and what are its 3 levels?"
```

The test must return the skill's **content** (YAGNI / lite-full-ultra), not merely
recognize the command. A 20s `claude -p` check here saves reopening every window.

**Prompt convention, refined in a session on 27/08/2026:** when writing delegation
prompts, put `/ponytail ultra` on the first line of **each** prompt file — and apply the
ladder to your own scope specification before you write it.

The failure mode this fixes: the orchestrator is lazy about the code it writes itself but
generous in what it *asks other agents to build*, so over-engineering gets laundered
through the delegation. Cut the scope first, then delegate the cut version.

Worked example from a real session — what got cut before the prompts went out:

| Drafted | Shipped | Why |
|---|---|---|
| `i18n.js` + toggle + localStorage + `navigator.language` | Translate and delete the other language | i18n infra for a requirement nobody has |
| CI matrix Node 18/20/22 | Node 20 only | 3x CI time for versions nobody reported |
| Refactor into a testable module + exports | `module.exports` at the bottom of the existing file | new architecture to make 6 functions reachable |
| CHANGELOG, CODE_OF_CONDUCT, issue/PR templates | none | ceremony for a community that does not exist yet |

Also write the *prohibitions* into the prompt. "Não construa i18n" and "Sem CHANGELOG,
sem CODE_OF_CONDUCT — se achar que falta, anote no resumo" are load-bearing; an unbriefed
agent defaults to maximalism.

## Anti-fabrication clauses (put these in the prompt)

Agents under-report failure unless told not to. Two clauses that earn their space:

```
Verifique rodando, não raciocinando. Falhou, reporte — não descreva o que deveria
ter acontecido.
```

```
Se você não conseguir capturar screenshot nesse ambiente: NÃO invente, NÃO commite
placeholder. Diga no resumo e deixe o README intocado nesse ponto.
```

And for any agent whose job depends on a peer's claimed success:

```
LEIA O CÓDIGO pra confirmar o que realmente entrou. Não assuma que o outro agente
teve sucesso.
```

## Verify the launch — an exit code is not a window

`wt`, `start`, and most launchers return 0 for "I handed off successfully", which is
true even when the child died immediately. **Never report "N windows opened" from exit
codes.** Confirm the processes exist, and confirm the *count*.

Windows: `MainWindowTitle` under-counts badly, because Windows Terminal hosts many tabs
in ONE process — three launched tasks show as one titled window. Count the launcher
processes instead, matching on the prompt filename in the command line.

Platform launcher details, including the `cmd /k` trap and a working `wt` invocation:
`references/windows-terminal-launcher.md`.

## Pitfalls

- **Exit 0 is not a launched window.** See above. Verify processes, then report.
- **`bash -lc` + a relative script path silently kills the window.** A login
  shell resets cwd to `$HOME`, so `./open-task.sh` is not found, the launcher
  exits, and `wt` closes the window — while the launching call still returns 0.
  Pass absolute paths for bash, the script, AND every argument. Details in
  `references/windows-terminal-launcher.md`.
- **A launcher that stops at a review gate will "time out."** If the design is
  human-in-the-loop (a `read` before `exec`), the terminal call hitting its timeout is
  *expected success*, not failure. Do not re-run — that opens a duplicate window.
  Confirm with a separate process check.
- **Don't poll the agents' windows.** Once handed over they belong to the user. Report
  what was opened and stop.
- **Device-specific launcher paths do not transfer.** A delegation recipe pinned to one
  machine's username, terminal emulator, or wrapper script will be wrong on the user's
  other machine. Re-check which terminal exists (`wt`? mintty?) before reusing a recipe.
- **Same-name skills across categories can break a runtime's skill loader.** Loading
  by bare name may be refused as ambiguous; use the full categorized path
  (`software-development/ponytail`) supported by your loader, or open the file directly.
