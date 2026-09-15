---
name: brand-retrofit
description: "Use when applying a brand to code that already exists."
version: 1.0.0
author: Rafael Rocha Ribeiro (github.com/Rafaelrr5)
license: MIT
platforms: [linux, macos, windows]
metadata:
  agent:
    tags: [brand, css, retrofit, design-tokens, legacy-code, visual-identity]
    related_skills: []
---

# Brand Retrofit

Apply an existing, already-measured brand to a **codebase that already runs**. Not designing a
new piece — correcting one someone else wrote: an inherited landing page, a Lovable/v0/bolt
prototype, a classroom game, a scaffold that shipped with whatever palette the generator felt
like.

Distinct from its two neighbours:

| Task | Skill |
|---|---|
| Derive a brand's real values from its assets | `brand-identity-extraction` |
| Design a new artifact in a known brand | the brand's own skill (for example, a client brand guide) + a design workflow |
| **Make existing code obey a known brand** | **this skill** |

## When to Use

- "apply brand X to this repo", "match the project identity", "/<brand> and show me the preview".
- You are about to hand a branded deliverable to a user and the source is code you didn't write.
- An AI-generated scaffold needs to stop looking like every other AI-generated scaffold.
- **Precondition:** the brand's exact values already exist in a skill. If they don't, run
  `brand-identity-extraction` first — retrofitting guessed hexes multiplies the error across
  every file you touch.

## 1. Audit before touching anything

Thirty seconds of inventory decides the size of the job and stops you from "fixing" what was
already right.

```python
import re
from collections import Counter
t = open(path, encoding='utf-8', errors='replace').read()
print(Counter(x.upper() for x in re.findall(r'#[0-9a-fA-F]{6}\b', t)).most_common(15))
print(set(re.findall(r'font-family\s*:\s*([^;\n"\']+)', t, re.I)))
print(re.findall(r'fonts\.googleapis[^"\']+', t))
```

Report the diagnosis as a table of **violations**, not as a wall of prose. Code often already
has the right hexes and the wrong everything-else — say that plainly instead of implying a
rewrite was needed.

Recurring offenders in generated code:

| Found | Why it violates | Fix |
|---|---|---|
| `Inter` / `Outfit` / `Poppins` / `Roboto` | Generator defaults; often a *sibling brand's* face | The brand's own font |
| `<link>` to `fonts.googleapis.com` | Breaks offline; classroom/kiosk pieces run with no wifi | `@font-face` with base64 TTF |
| `#0d0a14`, `#0a0712`, `#0f172a` | Near-black that exists in no brand palette | Derive from the primary (§3) |
| `#22c55e` / `#ef4444` | Tailwind semantics, not brand | Map onto the palette (§4) |
| `background-clip: text` gradient headings | Most brands use flat colour type | Flat brand colour |
| `font-weight: 800/900` | Real brand fonts rarely ship Black; browser fake-bolds and it looks wrong | Cap at the weight the TTF actually has |
| No logo, no institutional footer | Public-facing pieces usually require it | Signature component |

## 2. Additive layer, never a rewrite

Do not rewrite the existing CSS rule by rule. Expensive, unreadable diff, irreversible.
Overlay instead:

```
<repo>/brand/
  <brand>.css        # @font-face (base64 TTF) + :root tokens + shared signature component
  <piece>.css        # per-piece override: redefines the tokens THAT PIECE already uses
  logos/…            # the variants this repo needs, copied from the brand skill's assets/
```

Load order in `<head>` — both positions matter:

```html
<link rel="stylesheet" href="../brand/<brand>.css">   <!-- BEFORE: exposes the tokens -->
<style> …original CSS untouched… </style>
<link rel="stylesheet" href="../brand/<piece>.css">   <!-- AFTER: wins without !important -->
```

The override is mostly just **redefining the variables the piece already declares**:

```css
:root {
  --primary:   var(--brand-primary);
  --bg-dark:   #4C3370;        /* was #0a0712 */
  --font-body: var(--brand-font);
}
```

A well-written piece flips entirely in ~15 lines. Only descend to specific selectors where a
light/dark inversion breaks contrast. Reserve `!important` for `font-family`, because original
CSS tends to repeat the face across dozens of selectors.

Free benefit worth stating to the user: deleting the two `<link>`s undoes the whole retrofit.
That is the argument that gets a retrofit accepted by whoever wrote the original.

## 3. Depth without leaving the palette

Brands rarely ship a dark neutral, but apps need elevation. Derive it from the primary instead
of inventing a near-black:

```css
--bg-deep:       /* primary darkened ~35% */
--bg-primary:    /* ~28% */
--bg-card:       /* ~15% — elevated surface */
--bg-card-hover: /* ~8%  */
--primary-deep:  /* shadow tone: button "step", pressed state */
```

A deep-purple brand primary (invented example: `#6A4A98`): `#3B2858` → `#462F67` → `#573F81` → `#644A91`, ambient
`linear-gradient(160deg,#4D3471,#3B2858 45%,#302048)`. White stays AAA on all of them.

## 4. Semantics when the palette has no green

Right/wrong/partial is the one thing a canonical palette usually can't cover — most brands have
no green. **Do not import one.** Reach for a support colour already documented in the brand
(print/folder extensions often carry a blue or cyan), then fall back to warm = caution, the
brand's own red/coral = error.

Example brand: correct `#32C1DA` (support cyan) · partial `#FCD400` · wrong `#E6493C`.

Colour emoji (🟢🔴✅❌) is the same violation in another form — the colour comes from the system
font, not the brand. Swap for neutral glyphs (`✓` `✕` `⚠`) and keep colour in CSS.

## 5. The CSS layer does not reach everything — sweep the JS

Colour in a `style=""` attribute built by a template literal beats any stylesheet. Grep the
script side; typical hiding places:

- data catalogues: `{ "name": "…", "color": "#22c55e" }`
- threshold helpers: `const c = v => v >= 70 ? '#22c55e' : v >= 45 ? '#ffd300' : '#ef4444'`
- result/rank objects: `rank = { title: …, color: '#22c55e' }`
- confetti / particle / chart colour arrays

Then prove only palette survives:

```python
print(set(x.lower() for x in re.findall(r'#[0-9a-fA-F]{6}\b', js_section)))
```

## 6. Verify by rendering every state, not the first screen

A screenshot of the landing screen proves nothing. In a client's games retrofit the menu looked
correct while the in-game screen kept the old near-black, because `.menu-screen` carried its
own hardcoded gradient that no token reached.

Drive a headless browser through the states with `scripts/shot_states.py`:

```bash
python scripts/shot_states.py steps.json
```

```json
[
  {"url": "file:///…/index.html", "wait": 4, "shot": "menu.png"},
  {"js": "document.querySelector('[data-block-id=\"1\"]').click()", "shot": "scenario.png"},
  {"js": "document.querySelectorAll('.option-btn')[0].click()", "shot": "feedback.png"}
]
```

Then read each PNG with `vision_analyze`. Reading CSS is not looking at pixels.

## 7. Report honestly

Close with: what changed (violation → fix table), what was verified and how, and **what is
still wrong**. A retrofit that silently leaves a known violation in place is worse than one
that names it. In practice the leftovers are contrast pairs the brand explicitly forbids and
sub-projects on a different stack — say so and offer to finish, rather than implying done.

Do not commit. Retrofits touch files someone else owns; show the preview and let the user
decide. Keep verification debris (`_shots/`, `steps.json`, drivers) out of the tree or
gitignored.

## Pitfalls

- **CRLF silently breaks `str.replace` on Windows.** Reading a `\r\n` file without
  `newline=''` normalizes to `\n`, so `t.count(my_snippet)` returns **0** with no error and
  your patch no-ops. Use `open(p, encoding='utf-8', newline='')` for both read and write when
  substituting strings in repo files. Assert the count before replacing.
- **Private repo, no `gh` installed.** The token is already in Git Credential Manager:
  `printf 'protocol=https\nhost=github.com\n\n' | git credential fill` returns
  `password=<token>`, usable as `Authorization: Bearer` against the GitHub API. Plain
  `git clone` over HTTPS just works via the same helper — try that before extracting anything.
  Never print the value into the chat; redact it before echoing.
- **Base64 `@font-face` inflates CSS** (~50 KB per TTF). Worth it for offline pieces, but keep
  it in the single shared brand file, never repeated per piece.
- **A `404` from the GitHub API on a URL the user says they own means private, not missing.**
  Authenticate before concluding the repo doesn't exist.
- **Vite/React/Tailwind sub-apps are a separate job.** A design system in `oklch` inside
  `src/styles.css` with `@theme inline` ignores the overlay — it needs its own token patch.
  Scope it out loud instead of half-doing it.
- **Don't recolour a logo to fit the piece.** Pick the brand's existing variant for that
  background (negative/white over dark). Recolouring is a brand violation in every brand skill.

## Where to go deeper

- `scripts/shot_states.py` — headless multi-state screenshot driver used in §6.
- For a worked audit, combine the violation inventory in §1 with the derived tokens in §3
  and the game-state failure in §6; record any open items using the reporting pattern in §7.

## Verification

- [ ] Audit table produced before any edit; existing-correct values acknowledged
- [ ] Brand values sourced from the brand's skill, not from memory or a screenshot
- [ ] Overlay architecture used; original CSS unmodified and the retrofit reversible
- [ ] Fonts self-hosted; no remote font request left
- [ ] JS/inline-style colours swept and re-grepped
- [ ] Every distinct screen state rendered and inspected visually
- [ ] Leftover violations named explicitly in the final report
- [ ] Nothing committed; verification artifacts kept out of the tree
