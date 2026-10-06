---
name: single-source-training-materials
description: "Use when a recurring training series needs one source for all materials."
version: 1.0.0
author: Rafael with AI assistance
---

# Single-source training materials

Use for a recurring class, workshop or webinar whose editions need the same slides,
summary, quiz, references and review page. Do not add this pipeline to a one-off deck.

## Diagnose before automating

Inspect the edition tracker, the operational checklist and host script, artifacts from
several editions, and the actual portal structure. Count editions, repeated blocks and
repeated authoring from those documents, not estimates. Different presenters' visual
drift may mean the problem is consistency rather than speed.

Write the fixed contract as a table: summary, recording, slides, quiz, references,
questions, survey, conclusion. Separate changing text from invariant order and styling.

## One source, independent destinations

Keep one data file per edition. Shared builders and theme serve every edition.
Do not parse slides to generate the summary: both consume the data. Derive summary
from agenda plus learning points, and conclusion from learning points. Use stable
content identifiers for quiz answers rather than duplicating an explanation.

Run `python scripts/generate.py` from this directory. The authored generic fixture is
[edition-example.json](fixtures/edition-example.json). Outputs are HTML slides, summary,
quiz JSON and a review page with the answer key. No portal is modified. Run
`python scripts/generate.py --self-test` for missing fields, escaping, shared-source
consistency and invalid answer-index tests. See [verification](VERIFICATION.md).

## HTML deck and print contract

Use a renderer per slide kind, dispatched by a dictionary; adding a kind should not
change old content. Anchor fixed blocks from the top rather than the bottom when
variable-length leading text would move them. Use a 1280 × 720 CSS-pixel section and
`@page { size: 13.333333in 7.5in; margin: 0; }` for a 16:9 print target. At standard
96 CSS pixels per inch and 72 PDF points per inch, the target is 960 × 540 points.
This is a sizing contract, not a claim that this anchor generated or inspected a PDF.

Count rendered sections against source entries. For a branded PDF, inspect embedded
font metadata and render every page type: cover, dense cards, table and dark slide.
Open the actual screenshots, not just the markup. No screenshots or font embedding
are claimed by the dependency-free anchor, which uses system fonts.

If the approved template exists only as a deck/PDF, follow
[visual-template-extraction](references/visual-template-extraction.md) before styling.

## Delivery and pitfalls

- Generate per-edition local files and review page; published courses remain untouched.
- Probe documented write routes before promising portal upload. A 404 may reflect a
  plan restriction rather than a nonexistent route. Never invent endpoints.
- Match editions by verified title and publication state, not numbers embedded in slugs.
- Prefer ready-to-paste blocks when no API exists. Production click automation introduces
  silent failures and access to real learner data.
- A file per block does not replace the combined review page and answer key.
- Normalize titles before generating filenames, and prevent path traversal or collisions.
- Obtain colors, fonts and logos from approved brand assets; sampled colors are estimates.
- Decide who authors the source, whether quizzes need an import package and whether an
  editable format is needed. Do not assume SCORM or a platform-specific package.

## Attribution

Prepared by Rafael with AI assistance, adapted from private recurring-session procedural
notes. The source did not record an author; attribution to Rafael is preparation credit,
not a claim of sole authorship of every imported technique. Example content is authored
for this public fixture, not extracted from a private training edition.
