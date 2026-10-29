---
name: hermes-provider-credentials
description: "Multiple accounts per provider in Hermes: pools, fallbacks, failure diagnosis."
version: 1.0.0
author: Rafael Rocha Ribeiro (github.com/Rafaelrr5)
license: MIT
platforms: [linux, macos, windows]
metadata:
  agent:
    tags: [hermes, auth, credentials, providers, oauth, rate-limits, fallback]
    related_skills: [hermes-cron-jobs, measurement-validity]
---

# Hermes inference credentials: pools, fallbacks, failures

Behaviour described here was read from the Hermes Agent v0.21 source. This
subsystem changes between releases, so confirm against your installed version
before promising an outcome (see *Read the source* below).

## When to Use

- "add a second Claude/ChatGPT account for when this one runs out"
- "set up a fallback provider" / "why did it switch models?" / "why is it using X?"
- adding an OpenAI-compatible endpoint
- rate-limit exhaustion, `hermes auth` behaviour, a backup account that is dead
  when it is needed
- a provider behaving badly: replies cut off mid-sentence, a model missing from
  the picker

This is about Hermes's **own** inference auth (`auth.json`, the credential pool,
`fallback_providers`). Giving the agent access to a third-party SaaS account is a
different layer.

## First move: check the default

Hermes already ships multi-account support. Before designing anything:

```bash
hermes auth list              # every provider, every pooled credential, active one marked
hermes auth status <provider>
```

Often the feature being asked for already exists and is already the default. The
pool's default strategy, `fill_first`, uses credential #1 until it is exhausted,
then moves to #2: same provider, same model. That **is** "use my other account
when this one runs out".

```bash
hermes auth add anthropic --type oauth --label second
hermes auth add <provider> --type api-key --label work
```

| Command | Purpose |
|---|---|
| `hermes auth list` | pool, labels, active credential |
| `hermes auth add <p> --type oauth --label X` | add an account |
| `hermes auth priority <p> <target> <n>` | reorder (`0` is tried first under `fill_first`) |
| `hermes auth reset <p> [target]` | clear exhaustion flags so a credential is retried |
| `hermes auth refresh <p> <target>` | refresh one OAuth credential's tokens |
| `hermes auth remove <p> <index\|id\|label>` | drop a credential |

`hermes auth add` and `hermes fallback add` need an interactive terminal. An agent
cannot run them from a tool call. Hand the user the whole command sequence in one
message instead of failing on the TTY check and coming back for another round.

## Pick the right layer

| Goal | Mechanism | Same model quality? |
|---|---|---|
| second account, same model | credential pool (`hermes auth add`) | yes |
| survive a provider outage | fallback chain (`hermes fallback add`) | no, a different model |
| new OpenAI-compatible endpoint | `providers:` / `custom_providers:` entry | API key only |

A second provider entry is the wrong shape for a second subscription account. It
cannot carry an OAuth login, and a fallback entry degrades to another model.

### Strategy: prompt cache decides

```yaml
credential_pool_strategies:
  anthropic: fill_first     # fill_first | round_robin | random | least_used
```

| Strategy | Switches when | Prompt cache |
|---|---|---|
| `fill_first` (default) | the credential is exhausted | preserved |
| `round_robin`, `least_used`, `random` | every request | lost |

Do not recommend per-request rotation for a conversational agent. Each account has
its own cache prefix: alternating means neither builds one, so a long conversation
re-pays the whole prefix every turn. Rotation also rewrites `auth.json`, which
holds live tokens for every provider, on every call. "Spreading load across
accounts is more efficient" is the intuition to resist. The cache loss costs more
than smoother quota gains.

### The fallback chain: use the CLI

The chain lives in `fallback_providers:` in `config.yaml`; edit it with
`hermes fallback list | add | remove | clear`, not by hand. `add` refuses an entry
identical to the primary or to one already in the chain.

A chain built up from setup defaults tends to hold cheap or free models nobody
chose. When the user states the chain they want, `clear` and rebuild it, then read
the final order back to them.

### Failover order: pool first, chain second

On a rate-limit, billing or auth failure, Hermes recovers inside the primary's
credential pool **before** it activates the fallback chain. Every non-exhausted
credential of the primary provider is tried first.

So "Claude account 1, then Codex, then Claude account 2" cannot be expressed:

| Wanted | What happens |
|---|---|
| claude1 → codex → claude2 | claude1 → claude2 → codex |

A fallback entry resolves its credential from an inline `api_key` or a `key_env`
only, so a chain entry cannot hold a subscription OAuth login either. When the
order asked for is not representable, say so, give the order the engine will
produce, and name the only alternative: keep the second account out of the pool
and switch by hand, which gives up automatic failover. Do not build something
adjacent and present it as what was asked.

### "Why is it using X?" / "Make X emergency-only"

1. `hermes fallback list`. If X is already last, the config already does what was
   asked. Change nothing and say so.
2. Find why the earlier tiers were skipped:
   `grep -nE "Fallback to|exhausted|no available entries" "$HERMES_HOME/logs/agent.log" | tail`.
   The usual cause is a fully exhausted or dead primary pool, plus a middle tier
   failing at that moment.
3. Prove each tier now with a one-shot:
   `hermes -z "Reply only: ok" --provider <p> --model <m>`.
4. The real fix is usually re-logging the dead pool row, so the emergency tier is
   no longer reached.

## Accounts that die while you are not looking

- **Idle OAuth accounts expire.** Refresh tokens die after some days without use.
  Under `fill_first` the backup rows sit idle, so they are dead exactly when
  failover needs them. Refresh every pooled OAuth row on a schedule; a ready
  no-agent cron for it is in
  [`setups/hermes-oauth-keepalive`](../../setups/hermes-oauth-keepalive).
- **One account on two machines: only one side may refresh.** Several providers'
  refresh tokens are single-use. When machine A refreshes, machine B's copy of the
  old pair dies. Either keep each login on one machine, or sync the newest pair
  between them ([`setups/hermes-link`](../../setups/hermes-link)). Never run two
  independent refreshers.
- **Re-authorising in the same browser re-adds the same account.** The provider
  reuses the live web session. Log out of the provider's website first. Two pool
  rows can be the same account under different labels. Compare the account
  identifier each credential's profile endpoint returns before claiming "two
  accounts in the pool", or failover lands on the same quota.
- **Named profiles have their own pool.** They do not inherit the default
  profile's logins. A second OAuth login per profile is interactive. Say so
  instead of reporting full failover on that profile.

## "How much quota is left?"

The `rate-limited`/`exhausted` mark in `hermes auth list` is a **local** flag set
by the last failure. It can sit on a credential with most of its quota free. To
answer "how much is left", ask the provider's usage endpoint per credential. If a
rotation is followed by the backup being marked exhausted within a second, check
the backup directly before blaming the account: that pattern can be a client-side
rotation bug rather than a real limit.

## A model missing from the picker is usually a hidden provider

The desktop picker requests models with `explicit_only=true`, which drops every
provider row without **explicit** configuration, and all of that provider's models
with it. Credentials borrowed from the environment (an ambient CLI login such as a
`gh` token) are deliberately not counted as configuration. The user is
authenticated, everything works from the CLI, and the picker still hides the row.
Compare the strict and permissive model lists. A row present only in the
permissive one is the gate. The fix is an explicit credential (`hermes auth add`,
or the provider's key in `.env`), not a catalog change.

The picker also never lists credentials, only providers and models. No setting
makes "account 1 / account 2" selectable there. Promise it and you will have to
walk it back.

## External-process (ACP) providers

Providers that drive a CLI over stdio (`copilot-acp` and friends) can be repointed
at any ACP-speaking CLI through environment variables, so read `.env` before
assuming which binary is in play. Two things to know:

- **Replies that stop mid-sentence with no error** are usually a tool collision,
  not the transport. The external CLI has its own tools; Hermes denies its
  permission requests, and the CLI turns the denial into a refusal that returns
  only the text so far. The fix is configuring the CLI with a no-tool agent
  profile, so Hermes is the only executor.
- These providers get **no prompt caching**: the whole transcript is re-sent each
  turn. Fine as a fallback, poor as the primary for long conversations.

## Calling models from your own scripts

`call_llm`-style helpers walk the fallback chain silently when the requested model
is unavailable for that account. A request for model A can come back answered by
your most expensive default model, under the wrong label. Pass a `route_info` dict,
check the provider and model that actually answered, and reject mismatches.

## Read the source, not your memory

| Question | Where (in the hermes-agent tree) |
|---|---|
| how a credential is picked and rotated | `agent/credential_pool.py` |
| which providers accept OAuth | `hermes_cli/auth_commands.py` |
| fallback entry schema and key resolution | `hermes_cli/fallback_config.py`, `hermes_cli/fallback_cmd.py` |
| what the picker lists | `hermes_cli/inventory.py` (`explicit_only`) |

Scope searches to those directories; an unscoped recursive grep over the whole tree
is slow. A bare `python -c` probe does not load `HERMES_HOME/.env`, so load it
first, or a working fix keeps reporting as broken.

## Pitfalls

- **Prefer no change.** If the default already does what was asked, say so and
  write nothing. A helper script, a duplicate provider entry and a non-default
  strategy all add maintenance to something that works.
- **`auth.json` holds live tokens for every provider.** Back it up before any
  programmatic write. Test credential logic on a copy in a temp directory. Print
  labels, ids and statuses, never token values.
- **Restart every long-lived process after a code or credential change.** The
  gateway, the desktop app's embedded backend and the dashboard each keep their
  own copy. A fresh `hermes -z` one-shot is the clean proof, not a turn in a chat
  that was already open.
- **Do not pin cron jobs to a single free endpoint model.** Free models get retired
  and the job fails every tick. Pin to a pooled provider so the pool and chain
  apply.
- **Whether a provider's terms allow several subscriptions driven from one
  machine** cannot be answered from the code. Say so explicitly rather than
  implying it is fine.

## Verification

- `hermes auth list` shows the rows you expect, in the order you expect.
- `hermes fallback list` matches the chain you described back to the user.
- A one-shot per tier answers: `hermes -z "Reply only: ok" --provider <p> --model <m>`.
- For a failover claim: `agent.log` shows the exhaustion mark and the rotation for
  the main turn, not only for an auxiliary call.
