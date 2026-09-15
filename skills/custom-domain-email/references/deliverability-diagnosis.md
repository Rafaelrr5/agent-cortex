# Diagnosing "mail from X never arrives"

## Rule 0 — Locate where the message stopped BEFORE theorizing

Every plausible cause predicts a different observable. Establish the observable
first; otherwise you build an elaborate theory the user's next sentence destroys.

Ask, immediately: **"does it show up in the relay/mailbox provider's log at all?"**

| Observation | Message reached | Live causes |
|---|---|---|
| In relay log, delivered, absent from final inbox | relay ✅, final hop ❌ | DMARC broken on forward; recipient spam filter |
| In relay log, refused/bounced | relay ✅ | relay spam filter; blocklist; recipient rejected |
| **Not in log at all** | never reached relay ❌ | **sender never sent it (suppression)**; refused at connection; log-privacy hiding it |

A broken-forward DMARC theory only fits row 1. If the user says "it's not even in
the log", that theory is **dead** — do not keep defending it.

## Trap: an empty log can be a lie

ImprovMX log privacy levels:

- **Minimum** — "we scramble the subject and sender, so nobody can read them, us
  included". Searching by sender name returns **nothing even for mail that arrived**.
- **Standard** — adds subject, sender, recipient, forwarded-to.
- **Full** — also **stores undelivered messages** (so you can recover the mail).

Free retention is 7 days. Before concluding "never arrived": set logging to **Full**
and search by **timestamp**, not by sender.

## Suppression lists — the cause people miss

Signature: **"it worked once, then never again."** Also: no bounce, no spam, no
trace anywhere, and other senders deliver fine.

Mechanism: one hard bounce (very often caused by a broken forward) → sender's ESP
marks the address permanently undeliverable → **nothing is sent thereafter**. The
receiving side has nothing to log because nothing is transmitted.

### Identify the sender's ESP from DNS — it dictates the escape path

```bash
nslookup -type=txt mail.sender.com 8.8.8.8   # SPF includes name the ESP
nslookup -type=txt _dmarc.sender.com 8.8.8.8 # p=reject ⇒ forwarding is hostile
```

Anthropic, Aug 2026:
```
_dmarc.anthropic.com       v=DMARC1; p=reject; sp=reject; fo=1
_dmarc.mail.anthropic.com  v=DMARC1; p=reject; sp=reject; fo=1
mail.anthropic.com SPF     include:_spf.google.com
                           include:23987127.spf02.hubspotemail.net
```
So: HubSpot + Google Workspace, with the strictest DMARC posture. `p=reject` means
a broken forward is dropped or hard-bounced, never quarantined.

### HubSpot suppression has two levels

- **Account-level hard bounce** — only the sending company can clear it, via the
  *Unbounce* button on the contact.
- **Global bounce** — after hard-bouncing in **3+ HubSpot accounts**, HubSpot
  suppresses the address across **all** accounts automatically. Globally bounced
  contacts **do not appear in the sender's own lists/segments**, so even a
  cooperative sender cannot find or clear it; only HubSpot support can.

Implication: a globally bounced address is unusable for **every** company sending
via HubSpot. Treat it as a total loss, not a fixable state.

### AWS SES

Account-level suppression list, cleared only by the sending account. Same
user-visible symptom.

## Proving it is address-level (cheap, do before any migration)

1. Create a **brand-new alias** on the same domain; request the mail there.
2. Send an ordinary message from another account to the **old** address.

| New alias | Old address (ordinary mail) | Conclusion |
|---|---|---|
| arrives | arrives | **Address-level suppression** — old address is burnt |
| fails | arrives | Domain/IP level — blocklist, relay spam filter |
| arrives | fails | The address itself is broken (alias/routing) |

This yields evidence citable in a support ticket, and it decides whether migration
alone is sufficient (it is not, if suppressed).

## Escalation reality

For Anthropic specifically (Aug 2026), and a useful template elsewhere:

- **The account email cannot be changed.** Help article 8452276: "It's not possible
  to change the email address associated with your Claude account at this time."
- The Fin support bot has reported being unable to inspect or modify suppression
  lists, open tickets, or escalate — see claude-code issue #79808, a paying Max
  subscriber with this exact problem, still open.
- The only route with human handling on lower tiers is the **"I can't login"** flow
  in the Help Center messenger.
- Open the ticket **from an address you control** (not the broken one) and name the
  broken address in the body.
- Include the two-test evidence above; a vague request gets a canned reply.

Also warn the user, before they commit an address anywhere: providers that forbid
changing the account email make address choice irreversible.

## OAuth is not a workaround if account matching is by literal email

"Sign in with Google" bypasses email entirely — but only helps if the account is
already on a Google-accessible address. Claude matches accounts by the **literal
email string**, so OAuth with a different address silently creates a **new empty
account** rather than logging into the existing one.

## Worked case (Aug 2026)

Domain: `.com.br`, registered registro.br, **NS delegated to Vercel**. MX =
ImprovMX free. SPF `include:spf.improvmx.com ~all`. DMARC `p=quarantine` with
`rua=admin@<same broken domain>`. No DKIM.

Reported: everything arrives except Anthropic; **nothing in the ImprovMX log**;
one Anthropic mail did arrive once, long ago.

Findings:
1. DNS edits belong in **Vercel**, not registro.br.
2. ImprovMX free is **Sending: 0** — half the user's stated requirement
   (send *and* receive) was impossible on the current stack, independent of the bug.
3. Anthropic publishes `p=reject` ⇒ forwarding is structurally unsafe for them.
4. "Once, then never" + empty log ⇒ **suppression**, not a broken forward. First
   theory (DKIM broken on relay) was wrong and had to be retracted — it predicts
   delivered-then-vanished.
5. Zoho free unavailable to this user — signup DC gated. Resolved via
   `workplace.zoho.eu/signup?type=org&plan=free`.
6. Google Workspace for Nonprofits ineligible: the organization is registered as a municipal
   government entity, and the university route is excluded too.

Ordering that matters: **migrate to a real mailbox BEFORE creating the replacement
address.** Creating the new address while still behind the fragile forward risks
burning the new address too, leaving no plan C.
