---
name: multi-layout-preview
description: Use when creating multi-layout website previews.
version: 1.0.0
author: Rafael with AI assistance
license: MIT
category: creative
---
## When to Use
Create functional prototypes of multiple website layouts to compare designs visually and interactively, ensuring they work in a real browser without console errors or layout overflow.

Procedure:
  1. Prepare layout directories: each layout in its own folder with an index.html.
  2. Prepare palette preview images: each as P-<palette>.png in a palettes/ directory.
  3. Write a rendering script (e.g., shoot.py) that:
        - Uses Playwright to load each layout in a browser.
        - Waits for layout to stabilize (e.g., 1800ms).
        - Checks for console errors and fails if any.
        - Checks the wordmark (or a specific element) for overflow (scrollWidth > clientWidth) and fails if clipped.
        - Takes a screenshot of the layout (and optionally scrolls to other sections).
        - Saves screenshots to a shots/ directory with a naming convention (e.g., A1-hero.png).
  4. After generating layout screenshots, generate a palette sheet:
        - Create a blank canvas.
        - For each layout and palette, place the palette preview image and label.
        - Save the combined image (e.g., PALETTES.png).
  5. Verify the output by checking the screenshots and palette sheet for correctness.
Preferences:
  - Functional prototypes: the layouts must be actual HTML/CSS/JS that run in a browser.
  - No static mockups: avoid using image editors to create the previews; use the actual browser.
  - Error checking: treat any console error as a failure.
  - Clipping check: treat any overflow of the wordmark (or designated element) as a failure.
  - Palette sheet: must show all palette previews with labels for easy comparison.
Pitfalls:
  - Do not skip the console error check; JavaScript errors can break the layout unpredictably.
  - Do not skip the clipping check; overflow may not be visible in the screenshot but breaks the design.
  - Do not reuse screenshots from previous runs without verifying the layout and palette are up-to-date.
  - Do not forget to update the palette sheet when changing palettes; it should reflect the current set.
## Runnable public anchor

Run `python scripts/preview.py` from this directory. See [verification](VERIFICATION.md) for scope and negative tests.

## Attribution

Prepared by Rafael with AI assistance. Adapted from private procedural notes whose recorded author was Hermes Agent. This is not a claim of sole authorship of those notes. Third-party tools retain their own licenses.
