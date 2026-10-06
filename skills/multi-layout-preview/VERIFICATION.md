# Local verification

Run from this skill directory with Python 3.

```text
python scripts/preview.py
python scripts/preview.py --negative console
python scripts/preview.py --negative clipping
```

The initial no-dependency run exited 2 with actionable isolated-environment installation instructions. The parent then installed Playwright 1.63.0 in a separate verification environment, leaving the agent environment unchanged, and supplied an installed Chromium executable with `--browser`.

Observed real browser results on Windows with Python 3.12.10:

- Normal run: exit 0. Both `a-cards` and `b-columns` reported `console_errors=0, clipped=False`; real screenshots were saved in `outputs/`.
- `--negative console`: exit 1, `FAIL a-cards: console_errors=1, clipped=False`.
- `--negative clipping`: exit 1, `FAIL a-cards: console_errors=0, clipped=True`.

The rendering gate and both injected failure paths are verified. The script checks only marked text containers and console errors in these fixtures; it is not a comprehensive accessibility audit or a palette-sheet compositor. For an existing Chromium installation, add `--browser <executable>` to each command above.

These are fixture-specific results, not general benchmark measurements.
