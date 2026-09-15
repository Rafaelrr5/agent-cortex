---
name: static-site-vps-deploy
description: "Use when deploying a static site to a VPS nginx."
version: 1.0.0
author: Rafael Rocha Ribeiro (github.com/Rafaelrr5)
license: MIT
platforms: [windows, linux, macos]
metadata:
  agent:
    tags: [Deployment, VPS, Nginx, SSH, StaticSite, rsync]
    related_skills: [domain-dns-cutover, custom-domain-email]
---

# Deploy / mirror a static site to a VPS behind nginx

For sites that are plain files (HTML/CSS/JS, bundled SPAs) served by nginx
from a directory on a VPS you reach over SSH by key. Covers the deploy
script, the nginx path traps, verifying the result live, and injecting
cross-framework UI like a back button.

## When to Use

- publishing or updating a static site/hub of pages on a VPS (`ssh root@<ip>`
  enters by key, nginx serves a docroot)
- a page's URL has a duplicated/awkward path segment and you need to fix the
  route
- you removed a page and it must actually stop being reachable
- you need a "back to index" control that works across different games/apps
  built with different frameworks

## Mirror, don't append (the #1 trap)

`tar -xzf -` over ssh only ADDS/overwrites files. It never deletes. So a
deploy that untars into the docroot leaves every renamed/removed file behind
as live, reachable cruft (old duplicated route, a page you "took down").

**Deploy must MIRROR:** what you deleted locally must disappear from the
server. Use `rsync -a --delete SRC/ DEST/`. Then deleting a folder in the
repo and re-running the deploy is all it takes to pull a page from the air.

### When the local machine has no rsync (e.g. Windows Git Bash)

Common on Windows devices: local Git Bash has NO `rsync`, but the
Ubuntu VPS has `/usr/bin/rsync`. Do the mirror on the SERVER side:

```bash
tar -czf - --exclude=node_modules --exclude=.git --exclude=<src/offline> . \
  | ssh "$SERVIDOR" "
      set -e
      rm -rf /tmp/site-stage && mkdir -p /tmp/site-stage
      tar -xzf - -C /tmp/site-stage
      rsync -a --delete /tmp/site-stage/ $DESTINO/
      chown -R www-data:www-data $DESTINO
      rm -rf /tmp/site-stage
    "
```

tar runs on the client (always available); rsync runs on the server (where
it exists). Check both ends first: `which rsync` locally and
`ssh $SERVIDOR 'which rsync'`.

A ready-to-copy script is in `templates/deploy-mirror.sh`.

## Verify LIVE, including negative routes

A green deploy is not "200 on the pages I kept." It is ALSO "404 on the
routes I killed." Always curl both:

```bash
codigo() { curl -s -o /dev/null -w "%{http_code}" --max-time 25 "$1" || true; }
# kept pages -> expect 200
# removed page + old duplicated route -> expect 404
```

The `|| true` matters on Windows Git Bash: curl prints the right code but
exits 23 writing to /dev/null, and `set -e` would kill the check exactly
when it passed.

### Status codes are NOT behavior verification

200/404 only proves a file is reachable. It says nothing about whether your
CHANGE is live. A deploy can be fully green while the bug you fixed is still
in the air. After any behavior/content change, assert the changed value in
the served bytes:

```bash
curl -s "$SITE/<path>/<asset>" -o srv.tmp -D hdr.tmp
grep -iE 'last-modified|etag|content-length' hdr.tmp   # did it even change?
grep -c '<the new value>' srv.tmp                       # is the fix in there?
```

Then exercise the actual behavior in a browser and read the number/text off
the screen. "Deploy said OK" is a claim about transport, not about the fix.

## The published file may not be the file you edited

Before editing, establish WHICH file the browser actually executes. A repo
often keeps a tidy modular tree (`components/`, `data/`, `src/`) next to a
single-file bundle that is what actually ships. Editing the modular source,
deploying green, and seeing zero change is the classic symptom.

Cheap checks, in order:

```bash
# 1. Is the entry page suspiciously huge? (300KB of "HTML" = inlined bundle)
wc -c <page>/index.html <page>/main.js <page>/data/*.js

# 2. Does it import anything, or is everything inline?
grep -nE '<script|import ' <page>/index.html

# 3. Does the value you're changing appear INSIDE the entry page?
grep -c '<the value>' <page>/index.html
```

If the value lives in the entry page, that copy is authoritative and MUST be
patched too. In the browser, `document.querySelectorAll('script')` returning
a single entry with `src:""` and a six-figure `textContent.length` is the
tell: everything is inlined, nothing is fetched.

Apply the fix to BOTH the bundle and the modular source, so the readable
source does not silently drift from what ships. Note in the commit message
which one actually executes.

### Stale cache masks a correct fix

A re-test right after deploy can serve the pre-fix asset from cache and make
a good fix look broken. Before concluding failure, force a clean load — and
clear any client-side state the app persists:

```python
cdp("Network.enable"); cdp("Network.setCacheDisabled", cacheDisabled=True)
js("(() => { localStorage.clear(); return 1; })()")   # apps that save progress
cdp("Page.reload", ignoreCache=True)
```

If the server's bytes are already correct (curl+grep above) but the browser
disagrees, it is cache — not the deploy.

## nginx path traps

- **Duplicated path segment** (`/jogos/jogos/<x>`): caused by a docroot that
  itself contains a subfolder with the same name as the location. Fix by
  FLATTENING at the docroot (move contents up one level) — do NOT touch the
  nginx config. `location /jogos/ { alias /var/www/jogos/; }` means the URL
  `/jogos/<x>/` maps to `/var/www/jogos/<x>/`, so the games belong directly
  in the docroot, not in a nested `jogos/`.
- Flattening changes relative depth: fix in-page relative refs
  (`../../brand/...` -> `../brand/...`) after moving a page up a level.
- **Never leave a backup config in `sites-enabled/`** — nginx loads EVERY
  file in the dir, so a `site.bak-<ts>` beside the original breaks reload
  with `duplicate listen options for [::]:443` and downs the site. Backups
  go outside the dir (e.g. `/root/nginx-backups/`).

## Framework-agnostic UI injection (e.g. a back button)

To add one control to several pages built differently (one vanilla HTML, one
Vite single-file bundle), inject a self-contained `<a>` with INLINE styles —
no dependency on the page's CSS or framework. Anchor it `position:fixed` with
a high `z-index`. Place it BOTTOM-left, not top-left, when the app has its
own top-left nav during use (it would collide). One block works everywhere:

```html
<a href="../" style="position:fixed;bottom:16px;left:16px;z-index:9999;...">← Todos os jogos</a>
```

Inject after the mount node (`<div id="root">` / `<div id="app">`) so it
survives the framework rendering into that node.

## Workflow

1. Find the SOURCE repo (sites are edited in the repo, not on the server).
   In a typical checkout, code lives under `projects/<project>` with a
   `deploy.sh` at the root.
2. **Identify the artifact the browser executes** before editing anything —
   bundle vs. modular source (see section above). Grep for the value you are
   about to change and confirm every copy of it.
3. Make edits locally; fix relative refs if you moved files.
4. Verify locally (open in preview) before deploy.
5. Run the mirror deploy; read its live 200/404 checks.
6. **Verify the BEHAVIOR live**, not just the status codes: curl the served
   asset and grep for the new value, then exercise the change in a browser
   with cache disabled.
7. Optionally `ssh` in to confirm the docroot and that stale dirs are gone.
8. Commit.

## Pitfalls

- Listing a `node_modules`-heavy tree with `find` floods output (700k+
  chars). Scope with `-maxdepth` and `--exclude`, or list only the dirs.
- Don't confuse the site source with a third-party clone vendored inside it.
- Preserve, don't delete, a page pulled from the air: move it to an
  `_offline/` dir excluded from deploy, so it can be republished later.
