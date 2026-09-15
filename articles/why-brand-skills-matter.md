# Why brand skills matter more than brand guidelines

Every organisation with a brand has a PDF. Forty pages, logo clear-space
diagrams, a palette with hex values, two typefaces and a paragraph about tone of
voice. It was expensive. It is thorough. It is also, in practice, consulted
roughly twice: once when it is delivered, and once when someone is already in
trouble.

Meanwhile every deck, landing page, report and internal tool drifts. Not because
anyone disagrees with the PDF, but because opening it, finding the right hex
value and applying it correctly costs more than approximating from memory. The
approximation is close enough to feel fine and wrong enough to need fixing in
review.

## The cost is the review loop, not the pixels

This is the part that gets mis-sold to non-technical stakeholders, so it is
worth being precise.

The argument for brand consistency is usually aesthetic: assets should look like
they come from the same company. True, and not very persuasive to someone
deciding where to spend a budget.

The argument that actually lands is the review loop. When an asset arrives
off-brand, it enters a cycle: someone notices, writes feedback, the producer
revises, it comes back, someone checks again. Each pass is a day or two of
calendar time, mostly spent waiting rather than working. Two or three passes per
asset, across every asset a team produces, is a substantial fraction of the
team's actual throughput, spent entirely on a problem that is fully specified in
advance.

The asset was always going to end up on-brand. The only question is how many
round trips it took to get there.

## Why the guidelines document does not close the loop

A guidelines PDF is a *reference*: it answers a question you already knew to
ask. The failures it needs to prevent are failures of not knowing there was a
question.

Nobody looks up the disabled-state colour, because nobody thinks of a disabled
state as a branded decision. Nobody checks whether the brand purple passes
contrast on white at body-text size, because the PDF says it is the brand purple
and that seems sufficient. Nobody notices a Google-Fonts fallback quietly
replacing the licensed typeface, because the page still renders and still looks
professional.

These are not lapses of diligence. They are the normal result of storing the
rules somewhere that must be actively consulted, for decisions nobody recognises
as decisions.

## The mechanism: the brand as an executable procedure

A brand skill is the same information, written so that whoever produces the
asset, a person or an agent, has it in hand at production time instead of having
to fetch it.

What makes it different from the PDF:

**Tokens, not swatches.** Not "the primary is a deep purple", but the value, its
derived hover and active and disabled variants, and the specific surfaces each
one is allowed on. A producer copies values instead of interpolating them.

**The failure cases, named.** "This primary fails contrast on white below 18px,
so body text uses the near-black and the primary is reserved for headings and
fills." That sentence prevents a specific recurring mistake that no palette
listing can prevent.

**Verification built in.** How to check the output actually applied the brand,
not just that it looks plausible. This matters more than it sounds: a screenshot
of the landing screen proves the landing screen. In one retrofit I did, the
landing screen was perfect and the menu, two clicks in, was still entirely the
old palette. The screenshot was true and the conclusion drawn from it was false.

**The exceptions.** Where the brand deliberately does not apply, so a producer
does not spend an afternoon forcing it somewhere it was never meant to go.

Written that way, the brand stops being a document you comply with and becomes a
procedure you execute. The asset arrives on-brand on the first pass. The review
loop does not get faster: it stops existing for that class of problem.

## The honest measurement

I have not run this as a controlled experiment, and I am not going to quote a
percentage I did not measure.

What I can say precisely is what I observed retrofitting a brand onto an
existing set of pages. The violations that a guidelines document had failed to
prevent, in order of frequency:

1. Typefaces loaded from a public font CDN rather than the licensed files, so
   the rendered result was a lookalike, not the brand.
2. Hover and active states invented on the spot, because the palette listed the
   base colour only.
3. One accent colour used correctly, one partially, one simply wrong, all from
   the same nominally documented palette.
4. Institutional header and footer elements missing entirely, because they were
   described in prose rather than provided as markup.

Every one of these is the same failure: the information existed, and reaching
for it at the moment of the decision cost more than guessing.

## What this does not solve

**It does not design the brand.** Extracting a skill from real assets requires
those assets to exist and to be right. A skill built from an inconsistent set of
sources encodes the inconsistency and then enforces it, which is worse than
nothing.

**It does not replace judgement on new surfaces.** The first time the brand
meets a format it was never designed for, someone has to decide. The skill
records that decision afterwards so it is only made once.

**It does not survive being written once and abandoned.** When the brand changes
and the skill does not, producers now follow a confidently wrong procedure, and
confidently wrong is harder to catch than obviously missing.

---

The anchor in this repo is
[`brand-retrofit`](../skills/brand-retrofit): applying a brand to code that
already exists, without a rewrite, including how to verify the result on
surfaces a screenshot of the landing page will not reach.
