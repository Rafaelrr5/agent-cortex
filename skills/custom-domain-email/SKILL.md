---
name: custom-domain-email
description: Use when own-domain email breaks or needs setup.
version: 1.0.0
author: Rafael Rocha Ribeiro (github.com/Rafaelrr5)
license: MIT
metadata:
  agent:
    tags: [email, dns, dmarc, spf, dkim, deliverability, mx, zoho, improvmx, cloudflare, forwarding]
    related_skills: []
---

# Custom Domain Email

## When to Use

- "I want to send/receive email with my domain"
- "Emails from <sender> never arrive at my domain"
- Choosing a mail provider under a cost constraint (free / near-free tiers)
- Migrating MX between providers without dropping mail
- Any MX / SPF / DKIM / DMARC record work

Supporting files:
- `references/provider-free-tiers.md` — hard limits and gating of free/cheap tiers (ImprovMX, Zoho, Cloudflare, Google nonprofits)
- `references/deliverability-diagnosis.md` — decision tree for "mail not arriving", suppression lists, worked case
- `scripts/mail-dns-audit.sh` — re-runnable probe: NS/MX/SPF/DMARC/DKIM for a domain + a sender's policy

## Step 0 — Find where DNS ACTUALLY lives (never skip)

The registrar and the DNS host are frequently different. Users say "my domain is at
<registrar>" and mean registration only.

```bash
bash scripts/mail-dns-audit.sh example.com
```

Read the `NS` block first. Records must be edited **at the nameserver host**
(Vercel / Cloudflare / Netlify / etc.), not the registrar. Changing NS at the
registrar to "get access" will take the website down with it.

Real example: a `.com.br` registered at registro.br with NS delegated to
`ns1.vercel-dns.com` — all MX/TXT work happens in the Vercel dashboard, and
registro.br is irrelevant to email.

## Step 1 — Establish the requirement before proposing anything

Ask (one `clarify` call, all questions together):

1. **Send, receive, or both?** Many free tiers are receive-only. This alone
   eliminates most options.
2. **Must it land in an existing inbox (Gmail) or is a separate mailbox OK?**
   This is the decisive tradeoff — see Step 2.
3. **How many addresses?** Free tiers cap at 2–5.
4. **Hard budget, or is a few R$/month acceptable?** Ask explicitly. Do not
   assume "free" forever; state the paid number once, with the exact figure, then
   respect the answer. (~US$1/user/month buys IMAP, which is often the whole ask.)

## Step 2 — Forwarding vs real mailbox (the load-bearing decision)

| | Forwarding (ImprovMX, Cloudflare Email Routing) | Real mailbox (Zoho, Migadu, Purelymail) |
|---|---|---|
| Mechanism | MX → relay → your Gmail | MX → your actual mailbox |
| Free tier sends? | Usually **no** | Yes, DKIM-signed |
| Unified in Gmail | Yes | Only with IMAP/POP (usually paid) |
| Survives strict senders | **Structurally fragile** | Yes |

**The structural problem with forwarding:** on relay, SPF breaks (the relay IP is
not in the original sender's SPF). Only the surviving original DKIM signature can
satisfy DMARC. Any header/encoding change in transit invalidates it. Against a
sender publishing `p=reject`, the result is a **silent drop or hard bounce** — no
spam folder, no NDR.

Consequence to state plainly to the user: forwarding is not "slightly riskier"
for strict senders — a real mailbox makes that failure mode *structurally
impossible*, which is different from *less likely*. Senders on `p=none` pass
through broken forwarding unnoticed, which is why "everything arrives except
<one sender>" is the classic signature.

Second-order damage: each such bounce can put the address on the sender's
**suppression list**. Then nothing is sent at all, forever. See
`references/deliverability-diagnosis.md`.

## Step 3 — Verify availability BEFORE recommending a tier

Free tiers are gated in ways the marketing page hides. **Check gating before
recommending, not after the user hits a paywall.** Known axes:

- **Data center / region** (Zoho free = US, IN, EU only; permanent at signup)
- **Country** (Zoho free discontinued in Canada, Saudi Arabia)
- **Org type** (Google for Nonprofits excludes government entities, schools,
  universities, hospitals — kills most public-university project use)

Pitfall from a real session: recommended "Zoho free, confirmed active" from
generic 2026 sources, then the user's own screenshot showed only paid plans
because their signup landed in a non-free DC. Stating a free tier exists is not
the same as confirming *this user* can get it.

## Step 4 — DNS records

Get the exact values from the provider's console — **they are per-account and
per-data-center.** Never copy from a tutorial.

Shape (Zoho, EU DC — substitute your own):

| Type | Name | Value | Priority |
|---|---|---|---|
| MX | `@` | `mx.zoho.eu` | 10 |
| MX | `@` | `mx2.zoho.eu` | 20 |
| MX | `@` | `mx3.zoho.eu` | 50 |
| TXT | `@` | `v=spf1 include:zoho.eu ~all` | — |
| TXT | `zoho._domainkey` | `v=DKIM1; k=rsa; p=…` (console generates) | — |

Zoho MX hostnames differ per DC and resolve to different IPs:
`mx.zoho.com` / `mx.zoho.eu` / `mx.zoho.in`. Using `.com` values on an EU
account breaks receiving entirely.

Rules:
- **Exactly one SPF record.** Replacing providers means editing the existing TXT,
  not adding a second. Two SPF records = validation failure.
- **MX is domain-wide.** There is no clean per-address split; cutover is atomic.
- **DNS last.** Create and verify the mailbox first, then move MX. The old
  provider keeps working until then; moving MX early creates a dead window.
- Propagation: MX 1–2 h, TXT up to 48 h.

### DMARC

Start `p=none` while validating, then tighten. Anti-pattern seen in the wild:

```
rua=mailto:admin@thedomain-with-the-delivery-problem.com
```

Reports are mailed *into the broken system*. Point `rua` at an address on a
different, known-working domain.

## Step 5 — Verify

```bash
bash scripts/mail-dns-audit.sh example.com
```

Then send a real message in **and** out. "Records verified in the console" is not
delivery confirmation.

## Pitfalls

- **Editing DNS at the registrar when NS points elsewhere.** Step 0 exists for this.
- **Assuming a free tier is universally available.** Region/DC/org-type gating is common.
- **Copying MX values from a tutorial.** They are account- and DC-specific.
- **Building a DMARC theory before establishing where the message stopped.** A
  broken-forward theory predicts *delivered-then-vanished*. If the message never
  reached the relay at all, that theory is dead — the cause is upstream (sender
  never sent, or refused at connection). Ask "does it appear in the relay's log?"
  *before* theorizing. Getting this backwards wastes a whole diagnostic round.
- **Trusting an empty relay log.** ImprovMX's `Minimum` privacy level scrambles
  sender and subject, so searching by sender name returns nothing even for mail
  that did arrive. Raise logging to Full and search by **timestamp**, not sender.
- **Treating a suppressed address as recoverable.** If a sender suppressed the
  address, changing mail providers does not help. The address must be replaced.
- **Reusing the account/email that landed on the wrong tier or DC.** Signup-time
  choices (Zoho DC) are permanent; a fresh signup needs a fresh address.
- **Assuming the account email can be changed later.** Several providers
  (Anthropic among them) do not allow it at all. Warn the user *before* they
  commit an address to a service.

## Verification checklist

- [ ] `NS` identified; edits going to the right dashboard
- [ ] Exactly one SPF TXT at the root
- [ ] MX hostnames copied from *this account's* console
- [ ] DKIM selector verified and enabled in the console
- [ ] DMARC `rua` on a different, working domain
- [ ] Real inbound test received
- [ ] Real outbound test sent and passing SPF+DKIM at the recipient
