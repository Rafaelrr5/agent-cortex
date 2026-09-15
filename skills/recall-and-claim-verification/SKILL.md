---
name: recall-and-claim-verification
description: "Asked for a past artifact? Verify it before resupplying."
version: 1.1.0
author: Rafael Rocha Ribeiro (github.com/Rafaelrr5)
license: MIT
platforms: [linux, macos, windows]
metadata:
  agent:
    tags: [verification, recall, memory, cross-device, honesty, fabrication, tool-output, provenance]
    related_skills: []
---

# Recall and Claim Verification

Three failure modes share one root: **treating an unverified claim as an
established fact.** The claim can come from the user as recall ("send me that
link you found"), from the user as a premise ("the free plan is only in the EU"),
or from a tool ("HTTP 200, success"). All three feel like solid ground and none
of them is.

The output of this skill is either evidence or an explicit "I don't have it" —
never a plausible reconstruction.

## When to Use

- The user asks you to **re-send, re-share, or continue** something from a past
  session: a link, a credential, a file, a number, a decision
- The user says "you found / you got / you sent me X" and you have no memory of X
- The user references work done "earlier today", "on the other machine", "in the
  other chat"
- A tool or API returns a success status for a side effect you have not observed
- Before reporting any external side effect (upload, attach, publish, write) as
  done
- The user asks for something based on a **stated premise about a product,
  vendor, or plan** ("I need the EU region because the free tier isn't on .com")

Supporting files:
- `references/false-recall-worked-example.md` — a measured session where a
  requested artifact did not exist in any store, and how it was resolved

- `references/live-state-probes.md` — probing live infrastructure (TCP
  open/refused/filtered, DNS, SMTP) and reading the output without over-reading it

## Part 1 — The user recalls something you cannot find

### Step 1: Search every store before answering

A single miss is not evidence of absence. Search **all** of them, because they
fail independently:

| Store | Covers | Misses |
|---|---|---|
| Long-term memory / fact base | curated durable facts | anything never promoted to a fact |
| Semantic search | paraphrases, concepts | exact strings, rare proper nouns |
| **Literal grep of the raw store** | exact tokens, URLs, product names | nothing — this is the backstop |
| Session history | this device's transcripts | **other devices entirely** |

Semantic search and literal grep are not redundant. A brand name like `zoho`
may score below threshold semantically while a `grep -i` over the raw
`facts.jsonl` settles it in one shot. **Run both before concluding.**

### Step 2: Distinguish "not here" from "never existed"

These demand different responses and conflating them is the actual error:

- **Not here** — plausibly exists, on another device or another tool. Say where
  to look.
- **Never existed** — the premise itself is wrong. Say that, plainly.

Report which one you concluded and what you searched to get there. "I looked in
A, B, and C; zero hits" is a verifiable statement. "I don't have that" alone is
not, and invites the user to just ask again.

### Step 3: Name the likeliest benign explanation

Users are not misremembering at random. Usually the artifact is real and the
*location* is wrong. The dominant cause in a multi-device setup:

> **Sessions do not sync across devices, even when memory does.** A fact base
> replicated by git covers `memories/` only. A conversation held on device A is
> invisible to device B forever.

Point at the specific place to look, and how. That converts a dead end into a
next step.

### Step 4: Refuse to fabricate — explicitly, and in advance

When the requested artifact is a URL, a token, a command, or a citation, a
**plausible guess is worse than nothing**: it is indistinguishable from a real
answer and the user will act on it.

State the refusal as a standing rule, not a one-off apology, so the user does not
simply rephrase and get a fabrication on the second ask:

> "Even if you ask again, I won't invent a URL for this."

Then give the honest substitute — the legitimate path to the same goal:

- Name the real product/tier that exists, and its actual limits
- Point to the normal signup/docs entry point
- Say what you *cannot* confirm

**Never invent** a paywall-bypass link, an undocumented endpoint, an internal
URL, a version number, or a citation. If the user's framing implies one existed
("the link that lets me skip the plan"), address the framing rather than
producing something that matches it.

## Part 2 — A tool claims success you have not observed

A `200 OK` proves the request was accepted. It does not prove the effect
happened. Several APIs return a **hollow success body** — all fields empty or
zeroed — identically whether or not the operation took effect.

The rule:

> **Only an end-to-end observation of the effect counts as proof.**
> The status code is a claim; the working system is evidence.

| Reported | Actually proves | Real proof |
|---|---|---|
| `200` + empty/zeroed body | the request parsed | the effect, observed directly |
| "uploaded successfully" | a code path ran | fetch it back |
| "file written" | no exception raised | read it back |
| key/credential attached | the API accepted the call | authenticate with it |

When the proof fails, **say the operation failed** — do not soften it into
"should be working now" or "may take a moment to propagate". Retry with a
bounded, stated number of attempts and intervals; if it still fails, report the
blocker and stop. An unverified success handed to the user is a defect you
introduced.

### Do not promote an unverified path to "the way to do it"

If the sequence never actually worked, it is not a procedure — it is a set of
attempts. Recording it as guidance means a future session repeats a known
failure while believing it is following best practice. Report the dead end as a
dead end and preserve only what was independently confirmed.

## Part 3 — The user's premise is wrong

The user arrives with a conclusion already formed ("I need the EU region because
the free plan isn't on .com") and asks you to act on it. If the premise is false,
**answering the question as posed is the failure** — and a well-cited answer to
the wrong question is worse than none, because the citations make it persuasive.

> **Verify the premise before you serve it.** The user's framing is a claim, with
> the same standing as a tool's `200 OK`.

### Check the premise, not just the request

Restate it as something falsifiable before researching. "The free plan is only in
the EU region" is checkable; "the .com doesn't work" is not. Then go to the
**canonical vendor URL directly** — `/pricing`, `/plans`, the docs page. Don't
search for a page whose address you already know; search adds an indirection that
can only degrade the source, and vendor pricing pages are exactly what SEO spam
imitates.

Two habits do most of the work:

- **Diff the regional twins.** Vendor sites are cloned per region (`.com`,
  `.eu`, `.in`) and the clones **disagree** about availability. Extract both and
  compare tier lists, CTA hrefs, and footnotes. A regional page whose CTA points
  at *another* region's host is strong evidence that tier isn't served there.
- **Read the asterisk, not the headline.** The disclaimer carries the
  eligibility logic ("Available only in select data centers") and renders as
  footnote text that summaries and forum answers routinely drop.

### Distinguish the funnel surface from the account surface

"The UI doesn't offer it" is not "my account can't have it." Onboarding wizards
and upgrade funnels commonly enumerate **paid tiers only**. Before reading an
omission as an entitlement fact, establish which surface you are on:

| Tell | Reads as |
|---|---|
| URL contains `/hosting`, `/signup`, `?plan=`, `mode=insideHosting`, `redirectToPricing` | funnel / marketing surface |
| Numbered breadcrumb or step trail ending in "you're all set" | onboarding wizard |
| Billing / Subscription / Plan under the account console | **entitlement authority** |

Route the user to the settings surface and re-check there before accepting the
funnel's implied limit.

### Don't conclude absence from a truncated extract

Pricing pages exceed the extract budget and get head+tail truncated, so the
comparison table lands in the omitted middle. Raise your extraction tool's character
budget to 30000, or retrieve its saved full-text output if it is still truncated.
Save the extracted text from `https://vendor.example/pricing.html` as `pricing.txt`
using whatever HTTP fetch or browser extraction tool your agent exposes, then mine
the full text with keyword windows rather than re-reading:

```python
from pathlib import Path
import re

# pricing.txt is the full text saved by your extraction tool, not a summary.
c = Path("pricing.txt").read_text(encoding="utf-8")
for m in re.finditer(r"[Ff]orever [Ff]ree|Free Plan|plan=free|select data center", c):
    s, e = max(0, m.start() - 400), min(len(c), m.end() + 400)
    print("===", c[s:e].replace("\n", " "), "\n")
```

"I didn't see it" in a truncated extract is not evidence it isn't there.

### Then correct the premise explicitly, and flag the trap

Lead with the inversion in the first line ("this is the opposite of what you
expected — here's the evidence"), quote the vendor's own wording, and only then
give steps.

**Name the irreversible step before the user takes it.** Vendor platforms enforce
uniqueness constraints that silently block a redo — a domain can be claimed by
only one organization, so creating a fresh free org for a domain the existing org
already holds fails until the domain is released. Say that *before* the clicking
starts, not after the wall.

Worked-example lesson: a user's regional-plan premise was inverted by the vendor's
own pricing pages. That specific Zoho finding later expired; reciting it without
a fresh check caused a repeat failure. Mark expired findings **SUPERSEDED** and
read that warning before reusing any recorded evidence chain.

## Part 4 — Your own stored claim has expired

The three failure modes above take a claim from the user or a tool. The fourth
takes it from **yourself**: a memory entry, a brain fact, or a skill reference
you wrote in an earlier session.

> **Availability facts decay. Freshness is part of the claim.**

Highest-decay categories, all of which change without anyone telling you:

| Claim type | Decays because |
|---|---|
| "Vendor X offers free tier Y" | tiers are withdrawn, regionally gated, renamed |
| DNS records, open ports, deployed services | the user edits infra between sessions |
| Prices, quotas, limits | revised continuously |
| "URL Z works" | SPAs return 200 long after the product dies |

Before repeating any stored claim in these categories, **re-probe it**. A stored
fact is a lead, not evidence. This is not hypothetical: a stored vendor-plan
worked example was recited without re-checking, and produced a
confidently wrong recommendation the user had to correct.

For product/tier existence, census the vendor's rendered text; for
infrastructure, see `references/live-state-probes.md`.

### When the user corrects you with a primary source

They have the account and are looking at the vendor's site. Treat their
contradiction as high-quality evidence:

1. **Re-measure at once** — do not defend the prior answer or hedge with "it may
   still work".
2. **Concede in the first line and name the reasoning error**, not just the
   wrong conclusion. "I read a 200 on a JS shell as proof" is the durable part;
   "I was wrong about Zoho" is not.
3. **Correct the stale artifacts in the same session** — memory entry, brain
   fact, and the reference file. Skipping this guarantees the repeat.
4. **Re-derive everything downstream.** When a tier dies, every recommendation
   resting on it dies too.

## Pitfalls

- **Answering from one store.** Semantic search alone misses exact tokens;
  memory alone misses transcripts. Search several, then say which.
- **Silently accepting the premise.** If the user says "the link you sent", and
  you sent nothing, correcting that is the answer. Playing along produces
  fabrication.
- **Treating "I couldn't find it" as the whole reply.** Without the search list
  and the likely location, it reads as a shrug.
- **Assuming another device's history is reachable.** It is not. Say so instead
  of promising to look.
- **Reporting a side effect from the status code.** Verify the effect.
- **Retrying an unverified operation indefinitely.** Bound the attempts, state
  them, then escalate to the user with options.
- **Offering only blocked options.** When every path you control is blocked,
  include at least one path the *user* controls (run it on the machine that
  already has access), with the risk of each stated.
- **Acting on the user's premise without checking it.** "Take me to the EU
  console" presumes the free tier is there. Falsify the presumption first, or
  you will efficiently deliver the wrong outcome.
- **Trusting one regional twin.** Availability, price, and tier names differ per
  region — never generalize `.com` pricing to `.eu` or back.
- **Reading a UI's omissions as entitlement facts.** A screen that doesn't offer
  something may be a funnel, a role-restricted view, or a feature-flagged
  surface. Check the URL and breadcrumb before concluding.
- **Carrying region-specific config across regions.** Region determines the
  values configured downstream (for Zoho Mail: `mx.zoho.com` +
  `include:spf` on `zoho.com` versus the `zoho.eu` equivalents). Mixing them
  silently breaks delivery. Re-derive from the region actually landed in and
  state which one you used.
- **Reciting a stored availability fact without re-probing.** Your own note from
  last week is a lead, not evidence — see Part 4.
- **Reading HTTP 200 as proof a product exists.** SPA shells answer 200 for
  retired tiers. Census the rendered text instead.
- **Reporting a probe's policy rejection as a fact about the target.** An SMTP
  `550 dynamic IP` is a verdict on your source address, not on the mailbox.
- **Defending a position after the user brings a primary source.** Re-measure,
  concede, name the mechanism, fix the stale note.

## Reporting shape

Use the user's language; be direct, with no preamble. Lead with the conclusion —
including "I don't have this" — before the reasoning. When correcting a false
premise, do it in the first line and name what you searched; a well-evidenced
correction demonstrates competence rather than adding friction. Offer options as
a table with the risk of each made explicit, and let the user choose rather than
deciding on their behalf.
