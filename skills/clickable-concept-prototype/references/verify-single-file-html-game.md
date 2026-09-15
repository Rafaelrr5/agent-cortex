# Verifying a single-file HTML/JS game (inline `<script>`, no build)

Complements the vm smoke-test in SKILL.md, which assumes the split
`js/dados.js` + `js/app.js` layout. When the artifact is ONE `index.html` with
all JS inline in a single `<script>` block (a game, a canvas demo, a cozy
sim), there is no separate file to smoke-test. Use this instead.

Validated on `Arrumadinho` (vanilla HTML/CSS/JS cozy game, `index.html` ~1190
lines, zero build per its own ADR).

## 1. Syntax: extract the `<script>` and `node --check` it

```python
# execute_code
import re
html = open(r"C:/path/to/index.html", encoding="utf-8").read()
m = re.search(r"<script>(.*?)</script>", html, re.S)
open(r".tmpcheck.js", "w", encoding="utf-8").write(m.group(1))
```

```bash
node --check .tmpcheck.js   # prints SINTAXE-OK / error
```

This catches a broken refactor (a half-finished edit that left the file
uncompilable) without needing any browser.

## 2. Cross-check DOM references after a refactor

The classic failure after renaming IDs/classes/functions is dangling
references. With the same `html` + extracted JS in memory:

```python
ids_in_js  = set(re.findall(r'getElementById\(["\']([^"\']+)["\']\)', js))
ids_in_html = set(re.findall(r'id="([^"]+)"', html))
print("IDs no JS ausentes no HTML:", ids_in_js - ids_in_html)  # must be empty
```

Also grep for removed symbols to confirm no stale caller survives:
`sorte_a_olhar(kind of: movePlayerTo, askPlayerName, old-class-name)` should
return 0 after a clean refactor. Heuristics that regex *called-but-undefined
functions* or *dynamic className without CSS* produce false positives on
`${...}` template strings and Portuguese comment words — don't trust them;
the ID cross-check and `node --check` are the reliable ones.

## 3. Visual proof: headless Chrome `--screenshot`

```bash
chrome --headless=new --disable-gpu --no-sandbox \
  --user-data-dir="$LOCALAPPDATA/Temp/chrome-arr" \
  --virtual-time-budget=3000 --run-all-compositor-stages-before-draw \
  --screenshot=out.png --window-size=1280,720 "file:///.../index.html"
```

Then `vision_analyze(out.png)` (or the model's own built-in vision) to confirm
the scene renders, nothing floats/overlaps, the HUD sits where it should.

### Gotcha A — `--virtual-time-budget` hangs forever on an rAF loop

A game with `requestAnimationFrame(gameLoop)` **never signals idle**, so
`--virtual-time-budget` waits indefinitely and the command times out (exit 124)
after the screenshot *has actually been written*. Wrap the call in `timeout 25`
so the screenshot file lands and the shell returns. Check `ls -la out.png` —
if bytes > 0, you got your shot even though the process was killed.

### Gotcha B — how to skip a pre-game screen to screenshot the scene

If the game boots into a fullscreen creation/intro screen that blocks the
scene, `?skip=1` and `location.replace` do NOT work (nothing reads the query
string; and a fresh `--user-data-dir` has an empty localStorage). Instead
**generate a throwaway copy of the file** with the blocking flag forced on:

```python
html2 = html.replace(
  "movedOut: new Set() };",   # a unique anchor right after `state` is built
  "movedOut: new Set() };\nstate.criado = true;",   # force "already created"
  1)
open(".test-jardim.html", "w", encoding="utf-8").write(html2)
```

Screenshot that copy. Delete it after (deletion may be blocked pending user
consent — leave it and tell the user rather than rephrasing around the block).

## Order of trust

`node --check` (compiles) → ID cross-check (no dangling refs) → screenshot
(renders correctly). All three green means the delegation/refactor landed
correctly even when the coding agent died mid-run.
