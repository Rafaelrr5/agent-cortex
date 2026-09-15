---
name: clickable-concept-prototype
description: "Clickable phone-frame HTML mockup to sell an app idea."
version: 1.2.0
author: Rafael Rocha Ribeiro (github.com/Rafaelrr5)
license: MIT
platforms: [linux, macos, windows]
metadata:
  agent:
    tags: [prototype, mvp, mockup, stakeholder, non-technical, html, validation, app-concept]
    related_skills: [stakeholder-decision-elicitation]
---

# Clickable Concept Prototype

## When to Use

A non-technical stakeholder (a PO, a professor, a client, a teacher) has an app idea and you
need them to **see and click it** before anyone commits to building the real thing. The right
deliverable is a navigable visual prototype — not a spec document, not production code, not a
static image. The prototype exists to make the idea concrete enough to critique and to anchor
the next conversation.

Distinct from siblings: `sketch` produces 2–3 static design variants to compare; `claude-design`
carries general design taste/process. This skill is specifically about a **single, honest,
clickable multi-screen prototype whose job is stakeholder validation**, plus the content-safety
pattern that advice/triage apps require.

Validated building a small-business app concept for a non-technical stakeholder —
an app to help people start a small business.

## Form rules that make it land with non-technical people

- **Draw a phone frame on the big screen.** A `<div>` that mimics a smartphone (rounded ~44px,
  notch, home bar) with the app inside instantly communicates “this is a mobile app.” On a
  real phone (`@media max-width:820px`) drop the frame and go full-screen.
- **Fixed “Prototype / demo” banner at the top** so nobody mistakes it for a finished product.
  A side legend (hidden on mobile) says what is already clickable.
- **Three taps max to the “aha.”** Cover → big button → list/journey → one live item.
- **Full interaction depth, mock content.** Build EVERY step of the flow so it actually clicks
  through. Placeholder “in construction” screens read as an unfinished sketch and get rejected.
  Honesty lives in the **banner + README** (“all content is illustrative”), NOT in leaving
  screens unbuilt. Separate the two axes: *interaction* = complete, *content* = openly fake.
  ⚠️ This rule was learned the hard way — the previous version of this skill advised the
  opposite (2–3 screens + placeholders) and the stakeholder-facing result was sent back twice
  with “it needed to become something better, like an actual MVP… interactive and enjoyable to use.”
- **Zero jargon in any visible text.** Human labels (“Your idea and you”), never
  “module/endpoint/JSON/API.”
- Match the stakeholder's brand if one exists (e.g. load the client's documented brand guide).

## Make it feel like an MVP, not a mockup

A prototype earns the word “MVP” when it is **pleasant to use**, not when it has more screens.
These five mechanics are what flip the perception, and they cost little in a static file:

1. **Progress that persists.** `localStorage` under one versioned key (`app-name-v1`). Close it,
   reopen it, land where you left off. Offer an explicit “Start over” that clears the key.
2. **Visible advancement.** A progress bar in the header + `n of N completed` + a ✓ state on
   finished items in the list. Cheap, and it makes the thing feel alive.
3. **A “continue where you left off” CTA** at the top of the index/journey screen, styled larger
   than the list rows, naming the next step.
4. **Varied input types** so it isn't ten identical screens: single choice, multi-select,
   1–5 dot scale, free text, number. One `campo(q, dados)` factory switching on `q.tipo` keeps
   this to ~40 lines.
5. **A payoff screen at the end.** THE most important one. Stitch every answer into a single
   “My plan” view: the user's own sentence quoted back, the computed numbers as cards, and the
   numbered next steps collected from each step's response. Add `window.print()` + a `@media
   print` block so it saves as PDF. Without a payoff the journey feels like a form; with it,
   it feels like a product.

**Let 1–2 steps genuinely compute.** Real arithmetic on the user's own numbers (a price from
cost+margin; “how many units just to cover fixed costs”; cash needed to open + 3 months of
runway) is what convinces a non-technical stakeholder the thing is real. Show a derived,
non-obvious second number — that's the moment they lean in.

**Give each step its own accent colour** (`m.cor`) applied to the header and result card. Ten
steps in one flat purple read as one long screen.

## Architecture rules (keep it trivially hostable and handoff-ready)

- **Plain HTML + CSS + JS, static.** No framework, no build, no database, no login. Opens by
  double-clicking `index.html`, runs offline, drops onto any static host.
- **Separate content from code.** Put all text/questions in a `js/dados.js` (array of objects).
  In the real version that becomes JSON produced by non-coders — changing content must never
  require touching the navigation logic (`js/app.js`).
- **Navigation = swap `innerHTML` of one `.tela` div.** No router.
- **Privacy by default:** answers live only on the user's own device (page memory +
  `localStorage`) — nothing is transmitted anywhere, and a “Start over” button clears them.
  Say this plainly in the README; it is a selling point with cautious stakeholders. Never ask
  for CPF/SSN, passwords, or bank data — not even in a prototype.

## Responsible-response pattern (for advice / triage / “should I” apps)

When the app gives the user guidance, it must never promise an outcome. Build a reusable
response component with these blocks, in order:

1. **Answer/estimate** — conditional, never categorical. “Based on what you told us…”, never
   “your business is viable” / “you will profit R$ X.”
2. **⚠️ Warning** — the limit of that estimate.
3. **👉 Next step** — one concrete action.
4. **🔗 Where to confirm** — hand off to an official source or a professional
   (accountant/lawyer) when relevant.

Always triage, never a verdict. Example: “MEI *might be* a hypothesis to investigate; confirm
the activity with an official source” + a warning that the app doesn't do the enrollment + a
link to the official portal.

## Repo layout (reproduce with modifications)

```
Project/
  index.html        # phone frame + <div class="tela">
  css/estilo.css    # brand tokens
  js/dados.js       # CONTENT (becomes JSON in the real version)
  js/app.js         # screen switching + responsible-response component
  README.md         # what it is, how to open, decisions, next steps
```

Before delivering: `node --check js/*.js`, then run a **headless smoke test of the real flow**
(see below). `git init` + commit. Put the repo where the user keeps projects (for example:
`Projects/`, folder name with no spaces).

## Verify by simulating the clicks, not by screenshotting

A no-framework prototype has no test runner, and driving a browser for this is slow and can
stall on profile permission dialogs. Instead run the app's own `dados.js` + `app.js` inside
node's `vm` against a ~90-line mock DOM, then **simulate the whole journey**: click every step,
answer every question, assert the results screen, the persisted state, the arithmetic, and the
final payoff screen. It runs in milliseconds and catches real regressions.

Starter harness: `templates/smoke-dom-test.js` — copy to `testes/smoke.js` and adapt the walk
section. Two traps it already works around:

If instead the artifact is ONE `index.html` with everything inline in a single
`<script>` (a game/canvas demo, not the split `dados.js`/`app.js` layout),
use `references/verify-single-file-html-game.md`: extract the script →
`node --check`, cross-check `getElementById` IDs against the HTML, and drive a
headless-Chrome `--screenshot` for the visual proof (with its two gotchas —
`--virtual-time-budget` hangs on an rAF loop; skip a blocking intro screen by
forcing its flag in a throwaway copy of the file).

- **`const` at the top level of a vm script is NOT a property of the sandbox object.**
  `sandbox.MODULOS` is `undefined`; read it with `vm.runInContext("MODULOS", sandbox)`.
- **Don't `eval(fs.readFileSync(...))` inside `node -e`** to poke at the data — the same scoping
  bite, plus quoting pain on Windows bash. Write the test to a file and run the file.

Mention the passing test in the handoff: it is the evidence the flow actually works end to end.

## Pitfalls

- **`CLAUDE.md` is a protected agent-instruction file.** Writing it triggers an approval prompt
  that can time out on its own (“silence is not consent”) — this is not a repo failure. Write
  everything else, deliver, and offer to add CLAUDE.md once the user can approve. Do not try to
  route around it via terminal/execute_code.
- **Stop at the prototype; don't slide into production.** “Complete flow” means every screen of
  the *demo* clicks through on mock content — it does NOT mean real content, a backend, auth, or
  the production build. Some users delegate real coding elsewhere (for example, to Claude Code CLI).
  Once the journey is navigable, pause and offer: (a) take it to the meeting as-is, or
  (b) prepare the delegation prompt for the real work (real content, the content→JSON pipeline
  non-coders will fill in, integration). Don't start the production version unasked.
- **Don't reach for an automated browser to check your own prototype.** It can stall on a
  fresh-profile permission dialog and it tells you less than the smoke test. The in-app preview
  pane renders the local file for the user; you verify with `node --check` + `testes/smoke.js`.
- **Ship the whole flow in one pass.** Delivering a thin version “to check the direction” costs
  a full rebuild plus the user's patience. If the ask is a prototype for a stakeholder meeting,
  the first delivery should already be the complete clickable journey with mock content.
