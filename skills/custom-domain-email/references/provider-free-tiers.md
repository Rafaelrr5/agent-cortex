# Free / near-free mail provider tiers

Verified Aug 2026. Providers move goalposts — re-verify limits before committing,
and above all verify **availability for this user** (see Gating).

## Gating — check this FIRST

A tier existing is not a tier the user can get.

| Axis | Example |
|---|---|
| **Data center** | Zoho Forever Free exists only in **US, IN, EU** DCs. DC is fixed at signup and **cannot be migrated**. A signup landing elsewhere sees only paid plans. |
| **Country** | Zoho free discontinued in Canada, Saudi Arabia. |
| **Org type** | Google for Nonprofits **excludes** government entities, hospitals, and "a school, academic institution or university". Philanthropic arms qualify; the institution does not. |

Failure mode this causes: recommend a free tier from generic sources, user reaches
a wall of paid plans, credibility spent. Ask/verify gating up front.

### Zoho free when the plan card is hidden

Symptom: `mailadmin.zoho.com/hosting` shows only Mail Lite / Premium / Workplace
with "Comprar agora" + 15-day trial, no Forever Free card.

Cause: signup landed in a non-free DC.

Workarounds, in order (all returned HTTP 200 with no redirect, Aug 2026):

1. Direct free signup URL, bypasses the plan chooser:
   `https://workplace.zoho.com/signup?type=org&plan=free`
2. Force an eligible DC via the signup domain — `zoho.eu` (EU) or `zoho.in` (IN)
   instead of `zoho.com`:
   `https://workplace.zoho.eu/signup?type=org&plan=free`
3. Sign up for any free Zoho product (e.g. CRM), then **Apps → Zoho Mail → sign up**.

Confirmation that it worked: the form submits straight to SMS verification and the
admin console, with **no plan-selection screen at any point**.

Notes:
- Use a **fresh email address** — reusing the one tied to the wrong-DC account
  returns you to that DC.
- Keep the signup type on **business/organization**, not personal, or you get a
  plain `@zoho.com` mailbox with no custom domain.
- Prefer **EU** from Brazil: lower latency than IN, and GDPR-governed storage is a
  usable answer for LGPD questions about student/minor data.
- A domain can exist in only **one** Zoho organization. If already added to another
  org, remove it there before a new signup.

## Comparison

| Provider | Receive | Send | Access | Addresses | Notes |
|---|---|---|---|---|---|
| **ImprovMX Free** | Forward, 500/day | **0 — none** | lands in your Gmail | 25, 1 domain | Receive-only by design. SMTP starts at Premium (~US$9/mo). 7-day logs. |
| **Cloudflare Email Routing** | Forward | No | your Gmail | ~unlimited aliases | Free, no send. Sending exists separately via Workers/API. |
| **Zoho Mail Free** | **Real mailbox** | **Yes, own DKIM** | webmail + Zoho app only | 5 users, 1 domain, 5 GB ea. | **No IMAP/POP/ActiveSync.** No forwarding, no catch-all (third-party claim, not Zoho docs). DC-gated. |
| **Zoho Mail Lite** | Real mailbox | Yes | **+ IMAP/POP** | per-seat | ~US$1/user/mo; in BRL seen at **R$ 6,25/user/mo annual (≈R$ 75/yr)**, 5 or 10 GB. IMAP is the unlock for Gmail centralization. |
| **Google Workspace Nonprofits** | Real mailbox | Yes | full | up to 2000 | $0 but org-type gated — see above. Validation via Goodstack/Percent. |

## The IMAP consequence

Gmail can only pull an external mailbox over **POP3**. No POP3 → no way to
centralize in Gmail. So:

- **Free + real mailbox** ⇒ you read in the provider's webmail/app. Full stop.
- **Gmail-centralized + real mailbox** ⇒ costs money (Zoho Lite tier or similar).
- **Free + Gmail-centralized** ⇒ only via forwarding, which reintroduces the
  DMARC fragility (see `deliverability-diagnosis.md`).

Present this as a genuine trilemma; do not imply a free option satisfies all three.

## Gmail "Send mail as" is not a real send path

Often suggested for sending from a forwarded domain. ImprovMX's own docs warn it
"lacks proper email authentication (SPF, DKIM, and DMARC)", some providers reject
it outright, it relies on legacy Google functionality, and it stamps "via gmail.com".
Do not present it as equivalent to authenticated sending.
