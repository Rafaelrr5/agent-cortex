# Worked example — a requested artifact that existed nowhere

Measured session, 2026-08-27, device FA. Recorded because the *shape* recurs:
the user's request was specific, confident, and had no referent.

## The request

Mid-task, out-of-band:

> "me manda aquele link do zoho us q vc conseguiu pra eu logar sem precisar ter
> plano"

Three embedded assertions, all worth separating:

1. A link exists.
2. The agent produced it in a past session.
3. It grants access without a paid plan.

Only #3 is checkable from priors alone — and it is the one that should raise
suspicion first. A URL that bypasses a vendor's billing gate is not a thing a
prior session would legitimately have "gotten".

## What was searched

| Store | Method | Result |
|---|---|---|
| Fact base (195 facts) | semantic search, `zoho mail link cadastro plano gratuito` | 0 relevant — top hits were the DNS/MX facts from the live task |
| Fact base, raw file | `grep -io ".\{80\}zoho.\{120\}" facts.jsonl` | **0 matches** |
| Session history | keyword search `zoho`, then recent-session browse | 0 |
| Session history | broadened: `zoho OR improvmx OR "email profissional"` incl. `role_filter=tool` | 1 session, **ImprovMX and Cloudflare only** |

The broadened search is what made the conclusion safe. It surfaced the real
prior work — a 2026-08-26 session evaluating **ImprovMX** vs **Cloudflare Email
Routing**, concluding "keep the working ImprovMX" — and confirmed Zoho was never
part of it. Without that hit, "I can't find it" would have been weaker: with it,
the record of what *was* discussed is positive evidence that Zoho was not.

The literal grep mattered independently. Semantic search returned only
task-adjacent DNS facts; a rare proper noun is exactly the case where embedding
similarity underperforms and exact matching settles it.

## The answer given

Structure that worked:

1. **Lead with the refusal of the premise.** "I don't have this" as the first
   line, not buried after hedging.
2. **List the stores searched**, so absence is auditable rather than asserted.
3. **Show what does exist instead** — the ImprovMX/Cloudflare evaluation — which
   both explains the likely source of the memory and proves the search was real.
4. **Offer the two benign explanations**, ranked: (a) it happened on the other
   device, whose sessions do not sync; (b) it happened outside the agent.
5. **Refuse fabrication in advance and in the open:** state that a repeat request
   will not produce a guessed URL either.
6. **Give the legitimate substitute:** Zoho Mail's Forever Free tier is real
   (1 domain, up to 5 users, webmail-only, no IMAP/POP), reachable through
   normal signup — with the caveat that free-tier availability is gated by data
   center and region, so it cannot be confirmed on the user's behalf.

Step 6 is what keeps the refusal useful. Declining to invent a bypass link while
naming the real free tier answers the user's actual goal without inventing
anything.

## Cross-device detail that explains most of these

Memory replicated by git covers `memories/` only. **Session transcripts are
per-device and never sync.** In a two-machine setup, "you told me X earlier"
routinely means "the other machine's agent told me X", and that transcript is
unreachable from here. Say this explicitly and name the machine to check.

## Generalization

The tell is a request whose *premise* asserts prior agent action the agent
cannot corroborate. Do not resolve the tension by producing something
plausible. Resolve it by reporting the search, naming the likely real location,
and refusing the fabrication out loud.
