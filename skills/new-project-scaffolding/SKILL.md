---
name: new-project-scaffolding
description: "New code project? Inherit the portfolio's conventions."
version: 1.0.0
author: Rafael Rocha Ribeiro (github.com/Rafaelrr5)
license: MIT
platforms: [linux, macos, windows]
metadata:
  agent:
    tags: [Project, Scaffolding, Conventions, Git, Onboarding, Contract]
    related_skills: [commit-work]
---

# Starting a new project — born in the right place, not moved there later

## When to Use

Load this the moment you are about to create the **first file** of something new
for the user: a tool, a bridge, a script that will grow, a prototype they will
come back to. Also load it when a project you created is being relocated, because
the same checks apply on the way out.

Not for: a one-off scratch file, an edit inside an existing repo, or a throwaway
you will delete in the same turn.

## The rule: read the convention off the neighbours, don't invent one

Users accumulate a place where code lives and a shape that code takes. Creating
outside that place is a real error, not a stylistic slip — it strands the work
where their tooling, backups, and habits do not look.

A user corrected this directly after a project was created loose in their home
directory:

> "Code projects like this should be in the dedicated projects folder."

They also keep contexts strictly compartmentalized — employer, clients, other
projects, personal — and does not reuse infrastructure or credentials between
them. So "which portfolio does this belong to?" is a real question with a wrong
answer, and it is decided **before** the first `mkdir`.

## Step 1 — one command tells you the convention

Do not ask the user where things go. Look:

```bash
cd <portfolio-parent> && for d in */; do n="${d%/}"
  printf "%-30s CLAUDE.md:%s git:%s\n" "$n" \
    "$([ -f "$n/CLAUDE.md" ] && echo yes || echo NO)" \
    "$([ -d "$n/.git" ] && echo yes || echo NO)"; done
```

Read the majority answer as the standard. In one portfolio audit,
7 of 8 siblings were git repos and 5 carried a root `CLAUDE.md` — which made a
project with neither an obvious outlier.

If the parent directory itself is unknown, survey the local project portfolio
to find its roots and conventions before choosing a location.

## Step 2 — a new project is born complete

Match the neighbours in the same pass that creates the project:

1. **Right parent directory**, chosen by context.
2. **`git init` + a real first commit.** Not "later, once it works" — the first
   commit is what makes every subsequent change reviewable.
3. **The root contract file** the siblings carry (`CLAUDE.md` / `AGENTS.md`).
4. **A `.gitignore` written before the first commit**, not after. Anything
   secret-shaped (`*.env`, generated build output with values baked in) belongs
   in it from commit zero — see the secrets section below.

Landing it correctly costs one command. Moving it later costs a correction, plus
stale paths in every document you already wrote.

## Step 3 — if you DO have to move it, two things go stale silently

Both were missed once and caught only by re-checking:

- **Paths inside the project's own docs.** A README that says
  `cd ~/thing && python test.py` is wrong the instant `thing` moves. Grep the
  project for its own old path.
- **The test suite, re-run from the new location.** A suite that passed before
  the move proves nothing about after it — relative paths, sibling imports, and
  gitignore anchors are all position-dependent.

## The root contract file is input for the next agent, not decoration

When you author `CLAUDE.md` / `AGENTS.md`, write what **breaks the project if
violated**, not a description of what the code does. The useful shape:

- **How to verify** — the exact command, and what a pass looks like.
- **Invariants**, each with its consequence: *"the endpoint must answer in under
  8 s — it is a hard platform limit; do not put real work inside it."*
- **Traps already paid for** — the bug that cost an hour last time.
- **Pieces that live outside this repo** (a cron job id, a scheduled task, a
  monitor script in another tree) — otherwise the next agent edits half a system
  and reports success.

A contract file restating the obvious is noise the next session will skim past.

## Secrets: assume the repo will be shared, from the first commit

Decide the secret path **before** writing code that needs one, because the
retrofit is worse than the design.

The pattern that survives both "the code is versioned" and "the deploy target has
no secret store":

```
src/thing.py          versioned; os.environ.get("KEY", "")   <- empty default
prepare_deploy.py     reads the gitignored env file, rewrites the default
build/thing.py        real values baked in; build/ is gitignored  <- ship THIS
```

Keep `os.environ.get(NAME, "<value>")` rather than a bare literal, so the same
file still works on a host where env vars *do* exist. Ship a committed
`config.env.example` next to the gitignored real one.

Then **prove** the secret stayed out, rather than assuming the `.gitignore`
worked:

```bash
git ls-files                                   # eyeball what is tracked
git check-ignore -v <secret-file> || echo "DANGER: not ignored"
git grep -lE '<secret-pattern>' HEAD || echo "clean"
```

`git check-ignore` is the one that catches a `.gitignore` rule that does not
actually match the path you thought it did.

## Verification before you call it done

```bash
cd <new-project>
git log --oneline           # a real first commit exists
git status --short          # empty = nothing untracked was forgotten
<the project's own test command>   # run it HERE, in its final location
```

Report the location, the commit, and the passing suite. "I created the project"
without those three is a claim, not a result.
