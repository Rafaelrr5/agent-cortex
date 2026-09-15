---
name: domain-dns-cutover
description: "Move a domain to new hosting; verify at authoritative NS."
version: 1.0.0
author: Rafael Rocha Ribeiro (github.com/Rafaelrr5)
license: MIT
platforms: [linux, macos, windows]
metadata:
  agent:
    tags: [dns, domains, registrar, vps, nameservers, tls, certbot, hostinger, registro-br]
    related_skills: [custom-domain-email]
---

# Domain DNS Cutover

Pointing a domain the user owns at new infrastructure — a VPS, a new host, a new
DNS provider — and proving it actually resolves before calling it done.

## When to Use

- "I want to put my domain on <provider>"
- "Move the domain to the VPS / to Hostinger / off Vercel"
- Choosing between an A record and delegating nameservers
- A domain that stopped resolving after a provider change
- Any registrar-panel work: NS delegation, zone records, provider transfer
- Before running certbot / issuing TLS for a domain

Not this skill: MX/SPF/DKIM/DMARC and mail deliverability — that is
`custom-domain-email`, which owns the email half of DNS.

Supporting files:
- `references/registro-br-and-hostinger.md` — `.br` registrar rules, transition
  windows, Hostinger API endpoints and their misleading error codes
- `scripts/dns-authoritative-check.py` — re-runnable check of A records against
  the authoritative nameservers (handles the Windows `nslookup` encoding trap)

## Step 0 — Separate the three layers before answering anything

Users compress three independent things into "put the domain on X". Untangling
them is most of the value you add, and getting it wrong sends them to the wrong
panel.

| Layer | What it is | Where it changes | Moves to the new provider? |
|---|---|---|---|
| **Registration / provider** | who administers and renews the name | the registrar | often **not required** |
| **DNS (NS)** | who answers queries for the zone | registrar → "change nameservers" | optional |
| **Hosting** | where the site actually runs | the host / VPS | this is the real goal |

State which layers the task actually needs. Very often only *hosting* has to
move, and the domain can stay exactly where it is.

**ccTLD trap:** some ccTLDs cannot be transferred between registrars at all.
A `.com.br` never leaves registro.br — the registry is single. What exists is
changing the *provider* to the new host's code (Hostinger = `HSTDOMAINS (127)`),
which is independent of DNS and usually unnecessary. Never promise a "transfer"
before checking the TLD's rules.

## Step 1 — Read the current state from DNS, not from the user

Memory and panels go stale; the resolver does not. Check before proposing.

```bash
python scripts/dns-authoritative-check.py example.com
```

Look for the shape of the answer, because each one means something different:

| Result | Means |
|---|---|
| NS at the old provider | nothing has moved yet |
| NS at the registrar's own DNS + empty zone | domain is **inert** — resolves to nothing |
| `NODATA` (name exists, no A) | zone is live but the record is missing or unpublished |
| `NXDOMAIN` | the name itself does not exist at that server |
| Leftover `v=spf1 -all` | residual record that blocks all mail — flag it |

A domain whose NS moved to the registrar with an empty zone is **already down**.
Say so plainly rather than describing it as "in progress".

## Step 2 — Pick the route: A record, or NS delegation

Both are legitimate. The choice is about *where the user wants to manage the
zone*, and it has a hard ordering consequence.

| | **Route A — A record** | **Route B — delegate NS** |
|---|---|---|
| Zone lives at | the registrar | the new provider |
| Works when the target is a VPS with a fixed IP | **yes, immediately** | yes |
| Prerequisite | none | the destination must already host a zone for this domain |
| Time to live | minutes | propagation, plus any registrar lock |
| Good for | shipping today; a single VPS | unifying DNS + mail + hosting in one panel |

### The ordering rule that breaks Route B

**Registrars validate the nameserver before accepting the delegation.** They
query the target and refuse if it is not authoritative for the domain, typically
with a "query refused" / "Pesquisa recusada" error. So Route B requires, in this
order:

1. Add the domain in the destination's panel — this is what creates the zone.
2. Read the destination's nameservers **from that account** (defaults published
   in docs are frequently not what your account is assigned).
3. Only then change NS at the registrar.

You usually **cannot do step 1 through the provider's API**: a zone-write call
against a domain the account does not yet own returns "domain not found" (see the
reference). Treat step 1 as a manual step for the user and say so instead of
burning calls on it.

**Consequence for planning:** when the user wants Route B but the destination has
no zone yet, Route A gets them live today and Route B becomes a later
improvement. Offer that inversion — do not let a management preference block
shipping.

## Step 3 — Respect registrar transition windows

After nameservers change, registrars commonly **freeze** the zone for a period
(registro.br: ~2 h) before publishing anything. During the freeze, records saved
in the panel are visible in the panel and **absent from the authoritative
servers**. This is not propagation and not an error.

> **Read the panel's own banner before diagnosing.** A screenshot that says
> "os servidores DNS do domínio se encontram em transição … em aproximadamente
> 1h11m" has already answered the question. Two separate notices often sit on the
> same page and mean different things:
>
> | Banner | What it blocks |
> |---|---|
> | "servidores DNS em transição … Nh" | **publication of the zone** — this is the one that matters |
> | "Modo básico só poderá ser selecionado em Nh" | only switching zone-editing modes — usually irrelevant |
>
> Dismissing both as irrelevant because one of them is, is a real failure mode.

Tell the user to **stop touching the panel** during the window — each save can
restart the clock. "No action required" is the correct instruction, and it is
worth saying explicitly, because a stalled user will otherwise keep editing.

## Step 4 — Verify at the authority, never at the cache or the panel

Three sources disagree, and only one is evidence:

1. **The panel** — proves the record was accepted, not that it is served.
2. **A public resolver (8.8.8.8)** — may hold a negative cache entry for a name
   that now resolves, or serve a stale positive one.
3. **The domain's own authoritative nameservers** — the only source of truth.

Query the authoritative servers by name (`a.auto.dns.br`, `ns1.<provider>.com`)
and confirm the record **and** its value. Do not conclude "the records were never
saved" from a cache miss; if the panel shows them, the honest reading is
unpublished-yet, not absent.

> **Windows encoding trap:** `nslookup` emits localised output in `cp850`, so
> `subprocess.run(..., text=True)` raises `UnicodeDecodeError`, the stdout is
> lost, and any parse built on it silently reports "no records". Decode
> explicitly with `cp850`. Also never regex the whole output for an IP — the DNS
> server's own address appears first and produces confident false positives.
> `scripts/dns-authoritative-check.py` handles both.

## Step 5 — Getting into the target VPS

The cutover is pointless if nobody can reach the box. A brand-new VPS typically
has **22 open and 80/443 closed** — that is a bare server, not a fault.

When a provider's browser/web console will not take input, do not fight it and
do not start guessing at root passwords. Providers expose SSH key management in
their API; attaching the user's existing public key is additive, reversible, and
needs no secret from them:

```bash
# 1) upload the key -> returns an id
curl -s -X POST "$API/vps/v1/public-keys" -H "Authorization: Bearer $TK" \
  -H 'Content-Type: application/json' \
  -d "{\"name\":\"agent-<device>-<date>\",\"key\":\"$(cat "$HOME/.ssh/<key-name>.pub")\"}"

# 2) attach it to the machine
curl -s -X POST "$API/vps/v1/public-keys/attach/<vmId>" -H "Authorization: Bearer $TK" \
  -H 'Content-Type: application/json' -d '{"ids":[<keyId>]}'

# 3) the ONLY proof that matters
ssh -o BatchMode=yes -o StrictHostKeyChecking=no root@<ip> 'hostname; uname -sr'
```

Attach calls often return a **hollow success body** (`{"id":0,"name":"","state":""}`)
whether or not they worked, and some documented read-back routes do not exist
(`Route is not found` is a routing error, not an auth error). Only a real SSH
login verifies it. Allow ~20 s for the key to land.

### When attach does nothing: give up on it fast

Key attach is reliable at **provisioning** time and unreliable on a **running**
box — the same call that works on a fresh VM can queue nothing at all on a live
one (details and evidence in the reference). Budget **two attempts and about two
minutes**, then switch routes. Signals that attach is a dead end here:

- `GET /vps/v1/virtual-machines/{id}/actions` shows **no new action** for your
  attach, while other calls (restart, root-password) do create one.
- `ssh -v` shows the right key **offered** and refused — the key is fine, it is
  simply not in `authorized_keys`.

**Do not reboot to "make the injection apply".** It is not a boot-time step;
rebooting costs downtime and changes nothing. Escalate instead to setting the
root password by API and installing the key yourself on the first login — that
converts a password into permanent key access in one step, and afterwards the
password is no longer the way in.

Handle the generated password safely: write it to a `chmod 600` file **before**
the API call that applies it (so it can never be live-and-unknown), and never
print it into chat or logs — the transcript persists on disk.


Check whether the local key has a passphrase before promising unattended access:

```bash
ssh-keygen -y -P "" -f "$HOME/.ssh/<key-name>" >/dev/null 2>&1 && echo "no passphrase"
```

## Step 6 — TLS comes last, and only it depends on DNS

Sequence the work so the DNS wait blocks as little as possible:

| Step | Blocked by DNS? |
|---|---|
| Webserver, runtime, process manager, firewall | no |
| Clone, build, start the app | no |
| `curl -I http://localhost:3000` on the box | no |
| `certbot --nginx -d domain -d www.domain` | **yes** |

Everything except certificate issuance can proceed during a transition window.
When a user says "I'll wait for things to unblock", correct the premise: waiting
buys nothing but delay. Only the TLS step needs the name to resolve.

Gate certbot on a real resolution check, and never work around a DNS failure
with `--standalone` (it wants port 80 and will fight the running webserver):

```bash
dig +short example.com @8.8.8.8   # must return the target IP before certbot
```

## Pitfalls

- **Trusting stale knowledge about where DNS lives.** Re-query every time; a
  domain's NS may have moved since the last session. Correct yourself out loud.
- **Reading the zone state and skipping the panel's banner.** The banner explains
  the state you are trying to infer. Read the user's screenshot fully.
- **Concluding "the records were not saved" from a cache miss.** Check the
  authoritative servers, and prefer "saved but not published yet".
- **Editing the zone-config screen when the goal is delegation.** Registrars have
  a separate "change nameservers" action; the zone editor is the wrong screen and
  its basic/advanced modes are irrelevant to delegation.
- **Assuming a zone-write API call can onboard the domain.** It cannot until the
  account owns the domain.
- **Copying a provider's documented default nameservers.** Read them from the
  user's own account.
- **Scheduling a monitor when no delivery channel exists.** A cron job on a host
  with a stopped gateway (or a messaging channel disabled on this device) fires
  nowhere. Verify the channel, or do not create the job — a silent monitor is
  worse than none, because the user waits for an alert that cannot arrive. Remove
  it and say you will check on request.

## Reporting shape (Portuguese-language support)

Portuguese, direct, no preamble. Lead with the decision or the blocker, not a
recap. Markdown tables for the three-layer split and for record values; give
exact field values including the fact that the root record's *name* field is left
**empty** at registro.br (it rejects `@` and `*`). Separate crisply what YOU did
from what only the USER can do, and say why. When an earlier statement of yours
turns out wrong, correct it inline and name the wrong reasoning — users can read
corrections as competence, not noise.
