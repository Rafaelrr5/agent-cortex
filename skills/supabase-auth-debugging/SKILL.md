---
name: supabase-auth-debugging
description: "Supabase login/OAuth/email-link failures: diagnose fast."
version: 1.0.0
author: Rafael Rocha Ribeiro (github.com/Rafaelrr5)
license: MIT
platforms: [linux, macos, windows]
metadata:
  agent:
    tags: [Supabase, Auth, OAuth, Next.js, Debugging, Production]
    related_skills: []
---

# Supabase Auth Debugging

## When to Use

A Supabase-backed app (Next.js/SSR or SPA) has a broken **login, signup, OAuth
(Google etc.), email confirmation, magic link or password reset**. Symptoms like
"login com Google não funciona", user lands on the home page logged out,
`?code=` appears on the wrong URL, "PKCE code verifier not found", "Email link is
invalid or has expired", 401 right after a supposedly successful sign-in,
**HTTP 502 exactly on `/auth/callback`** after the provider round-trip.

Also when asked to "check the login and signup routes for problems" — this skill
is the checklist that separates **config faults** (Supabase dashboard / Google
Cloud) from **code faults** (callback route, middleware, cookies).

## Core principle

**Most Supabase auth breakage in production is configuration, not code.** Read
the code once to learn the intended flow, then prove where the flow *actually*
leaves the rails using the live services. Do not start patching route handlers
before step 3 below points at the code.

## Procedure (one pass, ~10 min)

### 0. A 502 on the callback is the reverse proxy, not auth
If the user reports **502** (not "logged out"), skip to the proxy before
touching Supabase: `grep 502 /var/log/nginx/access.log` + the matching line in
`error.log`. `upstream sent too big header while reading response header from
upstream` = the `Set-Cookie` from `exchangeCodeForSession` exceeded nginx's
default 4k `proxy_buffer_size`. The Supabase session cookie carries the
provider tokens when the client asks for `access_type=offline` /
`prompt=consent`, which is what pushes it over. Fix both ends (nginx buffers,
and drop those `queryParams` if the app never reads `provider_token`) — recipe
Supabase auth logs will look *healthy* in this case (Google succeeded); the
failure is entirely between node and nginx.

### 1. Locate the pieces (code side, read-only)
- Client initiator: grep `signInWithOAuth`, `signUp`, `signInWithPassword`,
  `resetPasswordForEmail`. Note every `redirectTo` / `emailRedirectTo` value
  **including query strings** (`/auth/callback?next=/protected`).
- Server side: `/auth/callback` (exchangeCodeForSession), `/auth/confirm`
  (verifyOtp), the middleware public-path allowlist, and the redirect helper.
- Which Supabase client factory each path uses (browser vs SSR cookie client vs
  service-role). Wrong factory = session never persisted.

### 2. Get the live project identity without local secrets
No `.env` in the checkout? Pull URL + anon key from the deployed bundle:
```bash
curl -s https://SITE/auth | grep -o 'https://[a-z0-9]*\.supabase\.co' | sort -u
# anon key: grep the /_next/static/chunks/*.js for eyJ...  or sb_publishable_...
```
`GET $URL/auth/v1/settings` (with `apikey:` header) shows which providers are
enabled, `disable_signup`, `mailer_autoconfirm`.

### 3. Black-box the redirect allowlist (the #1 culprit)
Supabase only honours `redirect_to` values that match **Authentication → URL
Configuration → Redirect URLs**; otherwise it silently falls back to **Site URL**.
An entry `https://site/auth/callback` does **not** match
`https://site/auth/callback?next=/x` — query strings need a `**` glob. Probe it
two-curl recipe. Test every `redirectTo` you collected in step 1 (with query),
plus `/protected`, `/auth/reset-password`, both apex and `www`, and
`http://localhost:3000` for dev.

Tell-tale in nginx/app access logs: a request like `GET /?code=<uuid>` with
referer `accounts.google.com` = provider succeeded, Supabase bounced the user to
Site URL because `redirect_to` was rejected. Callback route never ran.

### 4. Read the auth logs, not just the app logs
Supabase MCP `query_logs` with `source = 'auth_logs'`: look for
`"Redirecting to external provider"` (authorize), `/callback` with an
`auth_event.action=login` (provider round-trip OK), `/token` with
`invalid_credentials`, `/verify` with `otp_expired`. A successful `/callback`
log followed by a logged-out user = redirect/cookie problem, not Google.

On the VPS: `journalctl -u <app>` for `[oauth/callback]` errors. Ignore
`AuthPKCECodeVerifierMissingError` produced by curl / smoke tests hitting
`/auth/callback?code=bogus` — that is expected noise, not the user's bug.

### 5. Confirm the code paths are honest (only now)
- Callback: `exchangeCodeForSession` → `getUser` → profile check → internal
  redirect via a helper that never trusts `Host` blindly.
- `next` param goes through a `normalizeNextPath`-style guard (no `//`, no
  external origin, decode loop).
- Middleware: new public routes are in the allowlist; nothing runs between
  `createServerClient` and `auth.getUser()`.
- Google Cloud client: `redirect_uri` is `https://<ref>.supabase.co/auth/v1/callback`;
  follow the authorize `Location` with a browser UA — a 200 sign-in page means
  the client is valid (`redirect_uri_mismatch`/`deleted_client` would show).

### 6. Report
State clearly **config vs code**, list every redirect value that fails the
probe, and give the exact dashboard entries to add (`https://site/**`,
`https://www.site/**`, `http://localhost:3000/**`). Offer to apply via the
Management API only if the user hands over a PAT — the dashboard click is
faster. Verify prod release commit (e.g. `RELEASE_COMMIT` on the VPS) matches
the branch you read so you are not reviewing code that is not deployed.

## Pitfalls

- Redirect allowlist rejection is **silent**: no error param, HTTP 302 to Site
  URL. The user just "comes back logged out".
- The same rejected list breaks **three flows at once**: OAuth (`?next=`),
  signup confirmation (`emailRedirectTo: /protected`), password reset
  (`/auth/reset-password`). Check all three, report all three.
- `redirect_to` to a foreign origin is also rejected → falls back to Site URL,
  so lack of open-redirect in Supabase is *not* evidence the app helper is safe;
  still read `normalizeNextPath`.
- Don't conclude "Google client broken" from curl alone: Google returns 302 →
  200 sign-in for a valid client; only an error page proves misconfiguration.
- Site URL with `www` + app served on apex: cookies set on one host are not
  seen on the other. Check `Set-Cookie` domain when apex/www both serve the app.
- "I have a password account with the same e-mail, is that why Google fails?"
  — no. Supabase links Google to an existing email/password user automatically
  when the provider reports the e-mail verified (Google does). Prove it with
  SQL instead of asserting: `select u.email, array_agg(i.provider) from
  auth.users u join auth.identities i on i.user_id=u.id group by u.id` — users
  showing `{email,google}` are the evidence. Manual linking (`linkIdentity`) is
  only needed for providers with unverified e-mails.
- `AuthApiError: invalid flow state` right after a burst of 502s is the user
  retrying with a code Supabase already consumed — a consequence, not a cause.

## Support files
  2026-09-03 production case (exact outputs, what matched / what fell back).
  502 on `/auth/callback` (same day, hours later): diagnosis, nginx + Node
  header limits, the `queryParams` diet, and the identity-linking SQL.
