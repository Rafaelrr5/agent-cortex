---
name: delegated-agent-supervision
description: "Dispatching a coding agent? Fence scope, verify claims."
version: 1.0.0
author: Rafael Rocha Ribeiro (github.com/Rafaelrr5)
license: MIT
platforms: [linux, macos, windows]
metadata:
  agent:
    tags: [delegation, autonomous-agents, supervision, verification, scope-control, git]
    related_skills: [parallel-agent-fanout, measurement-validity]
---

# Supervising Delegated Coding Agents

## When to Use

Use whenever you hand a coding task to an autonomous agent process you cannot
supervise turn-by-turn — `claude -p`, `codex exec`, `opencode run`, or any
one-shot CLI agent launched in the background.

This skill covers the two failure modes that survive a *correct* fix:
**the agent does more than you asked**, and **the agent's summary is not what
actually happened**. It is about the envelope around the delegation, not how to
drive any particular CLI — see the per-tool skills for that.

## The Two Laws

```
1. Capability flags fence what an agent CAN touch. Only the prompt fences
   what it DECIDES to touch. State the file list explicitly.
2. The agent's final summary is a self-report. Git and re-measurement are
   the evidence. Verify before you relay.
```

## Law 1 — Fence the Scope

`--dangerously-skip-permissions` (and equivalents) removes the *approval*
brake, not the *judgment* brake. A capable agent that finishes early looks
around and finds adjacent work worth doing. That instinct is good in a human
colleague and dangerous in an unattended run you cannot steer.

**Observed:** an agent asked to fix one function in one file also rewrote
`pyproject.toml`'s build backend, edited `README.md` and `requirements.txt`,
**deleted `pytest.ini`**, created an unrequested `training/dataset/`
subproject, and committed an unrelated 365-file cleanup. The requested fix was
correct — it just arrived welded to a pile of unrequested change that then had
to be untangled with the user's involvement.

The run that went rogue was the one told *"no other agent is running — the
whole tree is yours."* Phrases meant as reassurance read as licence.

### The fence block

```
## SCOPE
Your scope is ONLY:
  - path/to/file_a.py
  - tests/unit/test_file_a.py
Do NOT modify any other file. Commit only those paths with explicit
`git add <path>` — never `git add -A` or `git commit -a`. Do NOT push.
If the task appears to require touching anything outside that list, STOP and
report what you would need and why. Do not do it.
```

Name the files **even when the agent is working alone**. Never write "the whole
tree is yours."

### Concurrent agents

Disjoint file lists, and name the other agent's files as off-limits:

```
ANOTHER AGENT IS WORKING CONCURRENTLY on <their files>. Do not touch those.
If you hit a conflict, stop and report rather than resolving across scopes.
```

This works — fenced concurrent agents stayed in their lanes and reported the
boundary rather than crossing it. But concurrency **destroys clean
attribution**: two agents landing commits minutes apart each partly credited
the other's improvement to itself. When you need to know which change caused an
effect, either serialize the runs or demand a controlled measurement that
isolates the one variable.

## Law 2 — Verify Before You Relay

Run these before believing any summary:

```bash
git log --oneline -10          # commits you did not ask for?
git status --porcelain         # files touched outside the fence?
git show --stat <new-sha>      # what is actually in that commit?
git diff <in-scope-file>       # is the requested fix actually there?
```

Then independently re-measure the one or two numbers the conclusion rests on.

For timeline-driven or media outputs, compile/typecheck is necessary but not
sufficient: independently recompute coverage and duration (including overlaps),
render boundary/key frames from the current source, and probe the final artifact.
See `references/timeline-media-verification.md` for the failure pattern and a
compact verification recipe.

### Self-reports observed to be wrong

| Claim | Reality |
|---|---|
| "before/after: A 50, B 75" | Measured against a **zero-byte** output file the harness had silently failed to write |
| "my change produced the improvement" | A **concurrent** agent's commit, landed minutes earlier, had caused it |
| "fundamental is 0.00 cents off target" | True — but only on the sustain portion; the whole-file average said −282 cents |
| "this test failure is pre-existing" | True here — but only confirmed by checking out the prior commit and re-running |

A claimed pre-existing failure costs one command to verify. Do it.

### Session-limit exit ≠ failed task: check the diff first

A long `claude -p` run can exit **code 1** with `You've hit your session limit ·
resets 5am` (or an equivalent quota message) *after it has already written most
or all of the work to disk*. The exit code and the empty-looking output
(`bash: no job control in this shell`) read like total failure — but `git status
--porcelain` / `git diff --stat` often shows the change is already there.

**Practice:** on any non-zero exit from a one-shot coding run, do NOT report
"the agent failed" until you have looked at the working tree. Sequence:

```bash
git status --porcelain          # was anything actually touched?
git diff --stat                 # how much landed?
<extract/typecheck the result>  # does it compile? (e.g. node --check for a <script>)
```

Only then decide whether to re-run, hand-finish the remainder, or report done.
In one session the run died on the limit but had completed all four requested
fronts (controls, a pre-game screen, fullscreen HUD, and a visual rebuild);
`node --check` + an ID/class cross-check + a headless-Chrome screenshot confirmed
the whole thing was functional. Treating the exit code alone as failure would
have thrown away finished, correct work.

### Recuperacao depois de timeout de delegacao

Uma nova tarefa delegada isolada NAO herda o contexto do worker expirado. Nunca peça 'use o que você já coletou' sem fornecer a coleta: passe o caminho do transcript e autorize sua leitura, ou inclua as evidências concretas no contexto. Exija checkpoint de achados em arquivo antes da exploração longa; um JSON vazio criado por um worker sem contexto não recupera a revisão e não conta como cobertura. Em fan-out grande, valide uma execução pelo mesmo launcher real antes do lote e interrompa novos dispatches ao identificar quota/429, em vez de repetir a falha por todo o inventário. Não substitua o executor expressamente escolhido pelo usuário.


Leia o diff e execute os testes ja gravados antes de repetir a implementacao. Confira tambem o script de testes do projeto: arquivos novos deixados pelo worker podem existir sem entrar no comando canonico, produzindo GREEN apenas da suite antiga. Redistribua somente o restante em escopos menores: o limite pode interromper depois de GREEN, ou entre RED e GREEN. Preserve o cron de publicacao pausado enquanto fontes parcialmente escritas nao passaram pela revisao; registre explicitamente essa pausa no handoff. Saida sem resumo nao prova ausencia de artefatos. Execute cada suite com exit code proprio ou agregue os codigos: comandos separados por ponto-e-virgula podem terminar com exit 0 do ultimo comando apesar de suites anteriores falharem. Em adapters subprocess, propague o home resolvido pelo contexto ao ambiente filho; herdar apenas os.environ pode acessar o perfil errado mesmo com argv correto.

### Preflight de fan-out e cobertura real

Antes de multiplicar workers na mesma rota, valide um canario representativo com leitura inocua por ferramenta e retorno final. Inferencia de texto sozinha nao prova suporte a tool calling; catalogo/config nao prova compatibilidade com a conta, endpoint e payload. Isto e teste funcional necessario, nao polling de cota. Reutilize evidencia recente apenas se a rota efetiva e o caminho de ferramentas forem os mesmos. Se o canario falhar por erro comum de provider, pause o lote; nao reproduza o erro em todas as unidades. Corrija apenas dentro da autorizacao existente ou use alternativa ja autorizada.

Em auditoria "cada unidade", persista inventario com identificador, arquivo/simbolo, executor e evidencia por unidade. Agregue contagens por codigo. Worker sem relatorio/teste e inconclusivo; nao o conte como auditado nem preencha achados plausiveis. Rodar menos workers simultaneos e permitido por capacidade real, mas nao reduzir silenciosamente a cobertura pedida.

### Servidor de teste precisa de identidade

Antes de testar, confira o dono da porta, comando, PID e horario de criacao. Nunca mate todo processo da porta ou limpe estado por conveniencia: encerre somente recursos comprovadamente seus e autorizados; caso contrario escolha porta/diretorio isolados. Confirme readiness e identidade da instancia, nao apenas HTTP 200. EADDRINUSE pode deixar os testes atingindo servidor antigo. Ao encerrar, confira filhos e listener; matar wrapper npm nao garante que node terminou.

### Model swaps require tracing every request boundary

Before migrating an agent's model, inspect all direct SDK calls as well as shared adapters. A small calendar/classifier pre-pass can bypass the normalizer used by the main streaming loop; a new model's default thinking can then consume its tiny output budget and silently trigger a fallback. Test outgoing parameters for each real path, including thinking-off and streaming fallback, and preserve summary-role exceptions and unrelated provider pins. Mock shims must expose the same pure normalizer as the generated bundle or integration tests cannot exercise the contract.

### Ask for measurements, not adjectives

```
Measure everything you claim. Never report a number you did not compute.
If the fix does not fully work, say so with the numbers.
An honest 85 beats a hollow 100.
```

Naming the specific trap you fear reliably gets it checked:

```
CRITICAL: <harness> SWALLOWS exceptions and writes a ZERO-BYTE output file.
`ls -la` the output and confirm it is non-empty BEFORE reporting any score.
```

Agents given that warning caught the trap. The one not given it reported a
stale number.

### Define success as the observation, not the score

When the metric can be gamed by absence, say so explicitly:

```
The success criterion is NOT a higher number. It is <specific observable>.
If the total score DROPS because a previously-hollow check now has real
content to judge, that is a GOOD outcome — say so plainly with the numbers.
```

This produced genuinely useful honesty: one agent reported "the sidechain order
ships but is net-negative today" rather than burying a regression under a
green number.

## Two-Stage: Reviewer Then Ranked Implementer

For "review X and improve it" asks, do not hand one agent both jobs. Run a
read-only reviewer (an isolated delegated task, full problem history, file:line
evidence, ranked list with `how_to_verify` per item, an explicit output schema), save its
report as a dated artifact, then launch one unattended `claude -p` session with
that report as its only spec and a strict per-rank loop: confirm claim → smallest
fix → RED/GREEN test → objective verification → log real numbers → one commit
per rank → FINAL STATUS table. Name the objective instrument's blind spot in the
prompt ("do NOT trust 'score unchanged' as proof for rank N — the scorer cannot
see Y"), and tell it to write *why* when a rank is contradicted by the code
rather than force the reviewer's fix. Expect ~1 in 3 open items to flip on
measurement; relay those contradictions first. Full prompt loop, overrides and
verification: `references/review-then-rank-session.md`.

## Queued Fleets: the Status Field Is Also a Self-Report

When agents are dispatched by a queue or board rather than launched by hand,
Law 2 still applies — but the self-report you must distrust is no longer just
the final summary. It is **the recorded status of each task**. A supervisor
process writes those statuses by observing worker processes, and it can
attribute a cause wrongly.

### A stalled worker has three different causes that look identical

| Recorded state | What actually happened | Correct action |
|---|---|---|
| Blocked, with a finished report or artifact already attached | The work is **done**. A human owes a decision | Do not retry or re-route. Extract the question and put it to the user |
| Blocked after repeated worker deaths ("crash x2", "pid N not alive") | Usually **quota**, not a bug — see below | Re-route to an available provider, release, re-dispatch |
| Waiting, predecessors unfinished | A real dependency | Leave it. It releases itself |

Only the middle row is a problem you can fix by changing models. Re-routing a
task that is waiting on a human is pure waste, and it buries the question the
user actually needs to answer.

### Quota exhaustion is recorded as a crash

Observed: a worker died twice; the task record said only
`Agent crash x2 — pid not alive`, with no mention of quota anywhere. The
worker log showed the real story — the primary model returned
`rate_limit_error` with `credits_required` / `org_level_disabled`, failover
moved to the secondary account, which returned HTTP 429 `usage_limit_reached`
with a reset horizon of ~4.5 days, and three retries later the process exited.

**Always read the worker's own log before diagnosing a repeated death.** The
task record carries the symptom; only the log carries the cause. A `429` with
`credits_required` or `usage_limit_reached` is a routing decision, not a defect
— no amount of retrying at the same tier clears it, and the reset horizon in
the payload tells you whether waiting is even viable (hours: wait; days: move).

This is the queue-level twin of the "pre-existing failure" trap: one command
separates a real bug from an environmental stall. Run it.

### Verify a re-dispatch after a delay, never at the instant of dispatch

A status read taken immediately after re-dispatching is **not evidence**.
Newly-spawned workers report as running and can die seconds later on the exact
error you were routing around. Wait a minute or two, then re-read, and check
more than the status field — a record showing *running* while also carrying a
stale failure error has already crashed at least once.

Only report "N tasks running in parallel" after that second read. In this
session the first report was drawn from the instant snapshot and claimed ten
running; minutes later several had finished, several were blocked awaiting
human decisions, and two were dead from quota. The instant snapshot produced a
materially wrong status report to the user.

### Approval holds need a verified dispatch barrier

For a portfolio-wide agent-runtime/repository workflow review, also read
`references/process-audit.md` for measurement, scope and cost discipline.

When provisioning audit cards without execution authorization, inspect the live
CLI and use `--initial-status blocked`, but **do not trust that field alone**.
A live run was promoted and spawned despite being created blocked; the worker
then refused the unapproved scope and reblocked with `needs_input`. A later
blocked snapshot hides this unauthorized attempt. Read `task_events` and
`task_runs` after a dispatcher tick, not just the task status.

Preserve an explicit authorization hold and use real dependency gates for its
unapproved descendants. Do not unblock/reblock to retrofit a block kind: that
opens a dispatch race. On builds where `block` refuses an already-blocked card,
report the limitation and fix through a supported atomic path, never raw SQLite
writes. Record any unintended worker launch honestly, even if it self-stops.

### Surface the human decisions first

When a fleet drains, the valuable output is usually not "what finished" but
**the questions that are now blocking**. Collect every task blocked on human
input, state each decision plainly with the evidence the worker gathered, and
lead the report with them. Those are the only items that cannot progress
without the user.

See `references/queued-fleet-supervision.md` for the recorded evidence and the
recovery sequence.

### Provisioning audit cards without a dispatch race

Do not provision an unapproved parentless root in a live-dispatch board unless
the current build offers a verified atomic human-hold creation path. Creating
with `--initial-status blocked` and immediately calling `block` is **not a safe
substitute**: the latter can refuse an already-blocked card without setting its
kind, leaving it eligible for promotion. A shorter timing window does not fix
the race. Use an existing verified approval dependency or keep the proposed
backlog outside the executable queue until an atomic hold is available.

Inspect `create --help`, `block --help` and `reclaim --help` on the live build.
CLI syntax changes: this build accepts a positional reason and `--kind`; do not
invent `--reason` or assume all commands accept `--json`. If an unauthorized
worker is active, use supported claim recovery, verify the actual process
stopped, and inspect its log and file changes before reporting containment.
Never release a hold just to make the CLI accept a second block.

Use `--idempotency-key` to make provisioning repeatable. Set the executor ceiling
explicitly; then verify both task status and attempt history after a dispatcher
tick. The root needs a real authorization barrier, not just a blocked label.

## Steering and Stopping

One-shot `-p` / `exec` runs are **not steerable mid-flight**. The only levers
are the prompt you started with and killing the process. Everything you care
about must be in the prompt before launch.

If a run starts producing out-of-scope commits, kill it rather than letting it
accumulate more:

```
Use your runtime's process-stop tool with the specific session identifier,
or terminate the verified worker PID with your operating system's process manager.
```

Spot-check `git status --porcelain` during long runs to catch drift early.

## Cleaning Up After a Scope Violation

1. **Back up the in-scope work first** — copy the good files to a temp path
   before touching anything.
2. **Do NOT revert or delete unilaterally.** Reverting another agent's work is
   destructive and irreversible, and the out-of-scope change is sometimes
   independently valuable (an unrequested `.gitignore` cleanup was legitimate,
   just unasked-for). Deletion commands may be blocked pending user consent —
   correctly so; do not rephrase around the block.
3. **Present the choice to the user:** what was in scope, what was not, what
   you would keep, and why. Let them decide.

## Prompt Skeleton

See `references/delegation-prompt-skeleton.md` for the full copy-paste
structure, invocation notes, and the post-run verification recipe.

For a large or multi-part prompt, do NOT inline it as the CLI argv string —
write it to a Markdown brief and pass it through stdin with `< prompt.md` in
one background call. `$(cat ...)` expands into argv and does NOT evade Windows
length limits. See `references/long-prompt-via-file.md` for the pattern and
startup/completion verification.

## Checklist

Before launch:
- [ ] Multi-item "review and fix" ask? Split into reviewer → ranked implementer (see above)
- [ ] Objective instrument's blind spot named, with the direct observable to measure instead
- [ ] Explicit file list in the prompt; `git add <path>` mandated (or, for a rank session: per-rank commits, never .db/media/.env)
- [ ] "STOP and report" instruction for out-of-scope needs
- [ ] Concurrent agents' files named as off-limits (if applicable)
- [ ] Known traps named specifically (swallowed errors, stale artifacts)
- [ ] Success defined as an observation, not a score
- [ ] "Never report a number you did not compute"

After completion:
- [ ] `git log` / `git status --porcelain` reviewed for scope violations
- [ ] The requested fix confirmed present in the diff
- [ ] Key numbers independently re-measured
- [ ] Timeline/batch coverage independently recomputed when the artifact spans segments
- [ ] Boundary/key frames rendered and final container probed for media outputs
- [ ] "Pre-existing failure" claims verified against the prior commit
- [ ] Attribution checked if agents ran concurrently
