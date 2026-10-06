# Reconciling two accessibility instruments

The worked case is axe-core run directly versus Lighthouse's accessibility
category, but the shape generalises to any scoring wrapper around a borrowed
engine: **the wrapper's number is not the engine's result**.

## Why the numbers differ even though one embeds the other

Lighthouse has no accessibility engine of its own — it bundles a pinned
axe-core build. Four transformations sit between raw engine output and score.
Name the one responsible before calling any difference a bug.

| Transformation | Effect |
|---|---|
| **Rule selection** | The wrapper curates which rules become audits. Rules the engine has but the wrapper never wrapped cannot affect the score at any severity. |
| **Your own tag filter** | Filtering a direct run to `wcag2a/wcag2aa/wcag21a/wcag21aa` drops rules tagged `best-practice` — `heading-order` is one. The wrapper scores it anyway, so it reproves a rule your direct run never ran. Check `axe.getRules().find(r => r.ruleId === id).tags` before calling it a discrepancy. |
| **Aggregation** | The engine reports violations with a node array; the wrapper reports one pass/fail per audit. Three broken nodes and thirty cost the same points. Weights differ per rule, so one single-node failure can cost more than a twelve-node one. |
| **Denominator** | Applicable weight is computed **per page** — inapplicable audits are excluded. A more semantic page exposes more checkable elements and therefore has a *larger* denominator. Two scores can be fractions of different bases; print the applicable weight beside every score. |

Render context is a fifth source when it applies: the wrapper may audit under an
emulated mobile viewport while a direct run uses desktop, so viewport-dependent
rules fire in only one.

Print both engine versions — the bundled build drifts from the standalone one —
before debugging a one-rule difference.

## Reporting

Use the engine's rule IDs and node counts to say what to fix. Use the score
only as a trend, labelled as a weighted subset at one viewport. A score
presented as a conformance percentage does not survive scrutiny.

Automated rules do not verify complete keyboard operation, focus order or screen-reader meaning. Coverage varies by rule set and page; do not infer conformance from a score.

## The defect neither instrument reports

A `<div onclick>` acting as a button produces **zero violations**. The
accessible-name rule needs a button to exist; the nested-interactive rule needs
nested controls. To the engine it is ordinary static content — a false negative
by absence, and typically the most severe defect present.

Verify it directly instead. The focus probe is the cheap version:

```js
const target = page.locator('[data-testid="action-button"]');
await target.focus().catch(() => {});
const receivesFocus = await target.evaluate((el) => el === document.activeElement);

await page.evaluate(() => document.body.focus());
let reachableByTab = false;
for (let i = 0; i < 40 && !reachableByTab; i++) {
  await page.keyboard.press('Tab');
  reachableByTab = await target.evaluate((el) => el === document.activeElement);
}
```

Bound the Tab loop; an unreachable target otherwise spins forever.

## Walking the whole task, not just the control

The probe above proves the control is unreachable. The stronger result is that
the **task cannot be completed** — drive the real workflow through the keyboard
and assert the goal state changed. Count focus stops along the way for a cost
proxy:

```js
const rows = () => page.locator('[data-testid="list"] tbody tr').count();
const before = await rows();

const marker = () =>
  page.evaluate(() => document.activeElement?.getAttribute('data-testid') ?? null);

await page.evaluate(() => document.body.focus());
let stops = 0;
let activated = false;

for (let i = 0; i < 40 && !activated; i++) {
  await page.keyboard.press('Tab');
  const current = await marker();
  if (current) stops++;

  if (current === 'selection-field') {
    await page.keyboard.press('ArrowDown');   // choose a non-conflicting value
  }
  if (current === 'text-field') {
    await page.keyboard.type('Keyboard test');
  }
  if (current === 'action-button') {
    await page.keyboard.press('Enter');
    activated = true;
  }
}

await page.waitForTimeout(300);
const recorded = (await rows()) > before;   // the assertion that matters
```

Four things make this work:

- **Assert the outcome, not the keypress.** `recorded` compares row counts.
  Asserting that Enter was pressed passes even when the handler never runs.
- **Read `data-testid` off `document.activeElement`** to know where focus
  landed, so one loop both walks and fills the form.
- **Pick values that avoid a validation error**, or the run fails for a reason
  unrelated to the barrier being measured.
- **Wait briefly before re-counting**; the state update is asynchronous.

The flawed version reports the task impossible with a high stop count (focus
cycling without ever arriving); the fixed one completes with roughly one stop
per field. That contrast survives in a room better than any score.

## Running both against one browser session

Launch Chromium once with a debugging port, drive the engine through the
browser automation library, and point the wrapper at the same port. Two API
shapes must be right or it fails immediately:

```js
import { chromium } from 'playwright';
import { AxeBuilder } from '@axe-core/playwright';
import lighthouse from 'lighthouse';

const PORT = 9222;
const browser = await chromium.launch({ args: [`--remote-debugging-port=${PORT}`] });

// PITFALL: AxeBuilder rejects a page from browser.newPage() with
// "Please use browser.newContext()" — the implicit context is not accepted.
const context = await browser.newContext();
const page = await context.newPage();
const result = await new AxeBuilder({ page: page })
  .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
  .analyze();

// PITFALL: the port belongs in the flags object (2nd arg). Passing a config as
// 2nd arg and connection info as 4th makes Lighthouse treat a Playwright page
// as a Puppeteer one: "this._page.target is not a function".
const { lhr } = await lighthouse(url, {
  port: PORT,
  output: 'json',
  onlyCategories: ['accessibility'],
});
```

Recover per-audit weights and the page-specific denominator from the report
rather than hardcoding them, since both shift per page and per release:

```js
const applicable = lhr.categories.accessibility.auditRefs
  .filter((ref) => ref.weight > 0 && lhr.audits[ref.id].score !== null);
const applicableWeight = applicable.reduce((s, a) => s + a.weight, 0);
```

Audit the **built and served** page, not the dev server, and wait for hydration
before measuring — a pre-hydration DOM scores a document the user never sees.

## Turning the comparison into a gate

A script that prints the table and exits non-zero on regression is the same
quality gate as a hosted pipeline, minus the hosting — and it can be run live
in front of people. Gate on every instrument you run, including the hand check:

```js
if (
  !(after.score > before.score) ||
  !(after.violatingNodes < before.violatingNodes) ||
  !after.task.recorded
) {
  process.exit(1);
}
```

Extend the condition in the same change that adds a measurement. A gate frozen
on the original instruments keeps certifying the older, weaker definition of
"better" while the new number sits in the report doing nothing.

A gate comparing two versions you already know proves little; its value starts
when it runs against the previous state of the code on every change.
