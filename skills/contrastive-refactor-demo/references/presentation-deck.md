# The introductory deck for a contrastive demo

The demo itself carries the evidence. The deck exists only to give the audience
vocabulary before the live run, so a term the demo relies on (affordance,
conformance versus efficacy, false negative by absence) is not being heard for
the first time while something is happening on screen.

Budget it small — a few minutes of naming things. Every concept reappears in
the demo, and that is where it fixes.

## Concepts only; the result stays in the live run

Define the idea and stop at the definition. "A signifier that promises an
action the implementation does not deliver" belongs on a slide; "our button is
a `<div>` the keyboard cannot reach" does not. A slide that states the finding
spends the payoff before the room can be surprised by it, and the demo then
only confirms what was already read out.

The one slide that may carry the conclusion is the thesis slide near the end,
because that sentence *is* the finding rather than a preview of it.

## Shape: one self-contained HTML file

No build step, no framework, no network. It opens on whatever machine is in the
room, including one you did not prepare.

- Sections toggled by an `active` class; arrow keys, space, PageUp/PageDown,
  Home/End. Click the left third to go back, anywhere else to advance.
- `@media print { .slide { display: flex !important; page-break-after: always; } }`
  gives PDF export through the browser's own print dialog — no exporter
  dependency.
- Type scale in `clamp()` so the same file is readable on a laptop and on a
  projector.

A keyboard-navigable deck is also the consistent choice when the demo's
argument is about keyboard operation.

## Screenshot every slide before committing

Reading the markup does not reveal how text breaks. Two failures that only
appear rendered:

- **A `max-width` in `ch` tuned for body prose (~46ch) orphans words** at
  heading and subtitle sizes. Presentation text needs a wider measure than an
  article; verify at the real viewport instead of trusting the number.
- **A manual `<br>` inside a width-constrained paragraph breaks twice** — once
  where you asked and again where the width runs out. Use separate `<p>`
  elements for separate lines.

Capture with the browser automation the project **already** depends on for the
audit. No new dependency, and the PNGs double as the fallback when the room's
machine will not open the file:

```js
import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import { resolve } from 'node:path';

mkdirSync('reports/slides', { recursive: true });
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
await page.goto(pathToFileURL(resolve('presentation/concepts.html')).href);

const total = await page.locator('.slide').count();
for (let i = 0; i < total; i++) {
  await page.screenshot({ path: `reports/slides/slide-${String(i + 1).padStart(2, '0')}.png` });
  await page.keyboard.press('ArrowRight');
  await page.waitForTimeout(120);
}
await browser.close();
```

Then actually look at the images — at least the title slide, one dense slide
(table or list) and one with a styled block. Those three expose most layout
faults.

## Recompute the timing total in code

Adding a block to a timed presentation pushes the total past the allowed window
silently, because nobody re-adds eight numbers by hand. Parse the per-block
minutes out of the rehearsal script and sum them:

```python
timings = [float(x.replace(',', '.')) for x in re.findall(r'— ([\d,]+) min', s)]
print(timings, sum(timings))
```

When the total overshoots, trim the blocks that only narrate and protect the
ones where something runs on screen. Re-run the sum after editing; a
redistribution done by eye usually lands a minute off.

## Cross-reference the deck from the rehearsal script

Each block of the spoken rehearsal script names the slides that back it ("slides 4 to
11"). Without that mapping the presenter is holding two documents that do not
admit each other exists, and loses time hunting for the right screen mid-talk.
