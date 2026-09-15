---
name: github-pages-deploy
description: "Publish a static site or client-side game to GitHub Pages."
version: 1.0.0
author: Rafael Rocha Ribeiro (github.com/Rafaelrr5)
license: MIT
platforms: [windows, linux, macos]
metadata:
  agent:
    tags: [Deployment, GitHubPages, StaticSite, GitHub, Hosting]
    related_skills: [static-site-vps-deploy]
---

# Publish a static site / client-side app via GitHub Pages

For putting a static artifact (plain HTML/CSS/JS, a bundled SPA, a
client-side game) on a real public URL with ZERO infrastructure: no VPS, no
nginx, no SSH. GitHub Pages serves the repo. Use this when the user wants to
"see it without being on the local network" and the app has no server side.

Complements `static-site-vps-deploy` (VPS/nginx path) and
`nextjs-selfhost-deploy` (SSR path) — both assume a VPS; this skill covers
the no-infra GitHub path only.

## When to Use

- "publique o jogo de um jeito que eu consiga ver sem estar na rede local"
- putting a static demo/prototype/game on a URL without provisioning a server
- a client-side-only app (no backend, no SSR, no secrets needed at runtime)

If the app needs a backend or SSR, stop — this is the wrong tool. Use a VPS
deploy skill instead.

## Prerequisites

- Repo pushed to GitHub (any visibility; Pages is PUBLIC once enabled,
  regardless of repo `private`).
- Git credential helper working (`git push` succeeds without a prompt).
- The entry point must be `index.html` at the repo root (or `docs/`); for
  JS-framework builds, commit the built `dist/`/`out/` output.

## Getting a token

Two paths; pick whichever is already true on the machine:

```bash
# A) env var already exported
[ -n "$GITHUB_TOKEN" ] && TOKEN=$GITHUB_TOKEN

# B) harvest from git credential helper (matches what `git push` uses —
#    works when no env var is set, via git-credential-manager / OS keychain)
TOKEN=$(printf "protocol=https\nhost=github.com\n" | git credential fill \
        | grep -oP '^password=\K.*')
```

## Enable Pages via API

```bash
# Enable Pages serving repo root of `main` — a legacy build. HTTP 201 = on.
curl -s -X POST \
  -H "Authorization: token $TOKEN" \
  -H "Accept: application/vnd.github+json" \
  https://api.github.com/repos/$OWNER/$REPO/pages \
  -d '{"source":{"branch":"main","path":"/"}}'

# Poll until status flips "building" -> "built" and grab the public URL
curl -s -H "Authorization: token $TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/pages
#   -> "html_url": "https://<user>.github.io/<repo>/"
```

Final URL: `https://<user>.github.io/<repo>/` (repo name lowercased). First
build takes ~30-60s. Do NOT report "live" on a bare HTTP 200 of the URL —
that only proves GitHub answered, not that YOUR content built and served.

## Verify the deploy served YOUR content (not just 200)

1. **Byte-compare served vs committed HTML** — catches stale build, wrong
   branch, or an empty build:
   ```bash
   curl -s "https://$USER.github.io/$REPO/index.html" -o "$LOCALAPPDATA/Temp/served.html"
   diff index.html "$LOCALAPPDATA/Temp/served.html"   # exit 0 = identical
   ```
2. **Resolve every asset ref to 200** — the #1 Windows→Pages trap:
   NTFS is case-insensitive, Pages serves from case-sensitive Linux, so a
   file `Hero.PNG` referenced as `hero.png` works locally but 404s live:
   ```bash
   grep -oE '(assets/[A-Za-z0-9_./-]+\.(png|jpg|jpeg|svg|mp3|wav))' index.html \
     | sort -u | while read -r a; do
         code=$(curl -s -o /dev/null -w "%{http_code}" "https://$USER.github.io/$REPO/$a")
         [ "$code" != "200" ] && echo "MISSING($code): $a"
       done
   ```
   All 200 and diff clean = the static artifact is fully served.

## Workflow

1. Ensure `index.html` + assets are committed and pushed (`git status` clean,
   `main` == `origin/main` after `git fetch`).
2. Harvest token and enable Pages via API; note the `html_url`.
3. Poll Pages status until "built".
4. Byte-compare the served `index.html` against the committed one.
5. Resolve every asset ref against the live URL; assert all 200.
6. Report the URL with the verification summary (what matched, any gaps).

## Pitfalls

- **Native tools get no MSYS path translation on Windows**: `/tmp/...` fails
  silently for `curl`/`git`/`diff`. Use `$LOCALAPPDATA/Temp/...` for scratch
  files a native tool must read or write.
- **GitHub Pages does not host private content privately** — enabling Pages
  makes the site world-readable even if the repo is private.
- **Repository name in the URL is lowercased** by GitHub; a mixed-case repo
  name still resolves at the lowercase path.
- **Live in-browser render/console check may be unavailable** if the browser
  tool's Chrome daemon is down on the machine; in that case do the static
  byte-compare + asset-resolution checks and say explicitly which check you
  could NOT run, rather than claiming a full verification.
