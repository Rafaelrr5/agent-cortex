Layout Convention:
  - Each layout is a directory containing an index.html file.
  - The layout directory name should be descriptive (e.g., a-index, b-console, c-track).
  - The index.html must be self-contained or load shared resources from a known location (e.g., a shared.js in the parent directory).

Palette Convention:
  - Each palette is represented by a preview image named P-<palette>.png (e.g., P-cobalt.png).
  - The preview image should show the palette colors in use (e.g., as swatches or in a small UI element).
  - Store all palette preview images in a palettes/ directory (or alongside the layouts if preferred).

Output Convention:
  - Screenshots: saved in a shots/ directory, named with a layout code and scene (e.g., A1-hero.png for layout A, hero section).
  - Palette sheet: a single image combining all palette previews, named PALETTES.png.