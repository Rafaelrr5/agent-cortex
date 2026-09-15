#!/usr/bin/env bash
# mail-dns-audit.sh — probe mail DNS for a domain, and optionally a sender's policy.
#
#   bash mail-dns-audit.sh example.com                  # audit your domain
#   bash mail-dns-audit.sh example.com anthropic.com    # + sender's DMARC/SPF posture
#
# Read the NS block FIRST: records must be edited at the nameserver host,
# which is often NOT the registrar.
#
# Portable across git-bash/MSYS (uses nslookup, present on Windows) with dig
# preferred when available.

set -uo pipefail

DOMAIN="${1:-}"
SENDER="${2:-}"
RESOLVER="${RESOLVER:-8.8.8.8}"

if [ -z "$DOMAIN" ]; then
  echo "usage: bash mail-dns-audit.sh <your-domain> [sender-domain]" >&2
  exit 2
fi

if command -v dig >/dev/null 2>&1; then
  q() { dig +short "@$RESOLVER" "$2" "$1" 2>/dev/null | sed 's/^/    /'; }
else
  q() {
    nslookup -type="$2" "$1" "$RESOLVER" 2>/dev/null \
      | grep -Ei "nameserver|mail exchanger|text =|Address:|canonical" \
      | grep -v "^Server" | sed 's/^/    /'
  }
fi

section() { printf '\n=== %s ===\n' "$1"; }

printf '### Mail DNS audit: %s   (resolver %s)\n' "$DOMAIN" "$RESOLVER"

section "NS — WHERE YOU MUST EDIT RECORDS (not necessarily the registrar)"
q "$DOMAIN" NS

section "MX — who accepts mail"
q "$DOMAIN" MX

section "SPF / root TXT — must be EXACTLY ONE v=spf1 record"
q "$DOMAIN" TXT

section "DMARC — policy + where reports go"
q "_dmarc.$DOMAIN" TXT
echo "    (rua must point at a WORKING domain, never an alias of this one)"

section "DKIM — common selectors"
for sel in zoho google default dkim mail selector1 selector2 s1 k1 hs1; do
  out="$(q "${sel}._domainkey.$DOMAIN" TXT)"
  [ -n "$(printf '%s' "$out" | tr -d '[:space:]')" ] && printf '  [%s]\n%s\n' "$sel" "$out"
done
echo "    (absent output = no DKIM found for these selectors; yours may differ)"

if [ -n "$SENDER" ]; then
  printf '\n\n### Sender posture: %s\n' "$SENDER"
  echo "p=reject  => forwarding this sender WILL break; you need a real mailbox."

  section "$SENDER DMARC"
  q "_dmarc.$SENDER" TXT

  section "mail.$SENDER DMARC (subdomain often used for transactional)"
  q "_dmarc.mail.$SENDER" TXT

  section "$SENDER SPF — the includes name the ESP (ses/hubspot/sendgrid/google...)"
  q "$SENDER" TXT

  section "mail.$SENDER SPF"
  q "mail.$SENDER" TXT
fi

cat <<'EOF'


### Checklist
  [ ] NS identified — editing at the right dashboard
  [ ] exactly one v=spf1 TXT at the root
  [ ] MX hostnames copied from THIS account's console (they are per-data-center)
  [ ] DKIM selector verified AND enabled in the provider console
  [ ] DMARC rua points at a different, working domain
  [ ] real inbound test received
  [ ] real outbound test sent, passing SPF+DKIM at the recipient
EOF
