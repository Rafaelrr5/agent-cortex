# Reconstruct an approved visual template

Identify fonts → extract assets → sample colors → rebuild → compare side by side.
A template is a specification, not permission to redesign.

## Fonts

With optional PyMuPDF, inspect `page.get_fonts(full=True)`; entry index 3 gives the
font name. A six-letter prefix plus `+` denotes a subset. Fonts present on only a
few pages may be pasted-text residue; check their actual usage.
Do not embed `document.extract_font(xref)` as a complete font: extracted subsets
lack new glyphs. Obtain the complete licensed font from its official source and
embed it. Reinspect generated PDF fonts to detect unintended fallback.

## Assets and transparency

Use `page.get_images(full=True)` and `document.extract_image(xref)`, deduplicating
by xref. Inspect every exported asset: numeric names do not identify its purpose.
Prefer original SVG or approved vector artwork to raster extraction.
A black rectangle behind a logo may require correct PDF soft-mask composition,
not just changing the PNG mode. As a last resort render a crop with
`page.get_pixmap(clip=rectangle, dpi=300)`, then key out a known white background.
A threshold such as all RGB channels above 240 is only a starting heuristic:
it destroys legitimate white artwork and can leave halos. Inspect the result.
Intersect the crop with `page.rect` and reject an empty rectangle before rendering;
an out-of-bounds clip can produce an opaque bandwriter-dimensions error.
For monochrome art only, CSS `filter: brightness(0) invert(1)` can create a light variant.

## Palette and comparison

Count sampled RGB values to identify dominant roles and approximate area ratios.
Antialiasing/compression produce near-matches: approved brand values, not sampled
hex codes, are canonical. Do not claim a percentage limit was verified without a
valid area measurement. Compare original and new cover, cards, table and dark slide
images for margins, font weight and background. Report extraction as a substitute
when original vector assets are unavailable.

Optional PDF/image dependencies belong in a dedicated project environment, never
an agent's environment. This reference is a procedure, not a claim that a public
source PDF or measured reproduction is included.
