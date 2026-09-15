# Probing live state — when a citation cannot settle the question

Most verification in this skill grounds claims in documents. A different class of
claim is about the **current state of a running system**:

- "this port is reachable"
- "the domain's MX is unset"
- "that mail server accepts this address"

No page can establish these. They need a **probe**, and the probe's output must
be read for what it actually proves — the common failure is over-reading it.

## TCP reachability — three outcomes, three different meanings

Conflating "filtered" with "closed" produces wrong conclusions and wrong advice.

```python
import socket

def probe(ip, port, t=6):
    s = socket.socket(); s.settimeout(t)
    try:
        s.connect((ip, port)); return "OPEN"
    except socket.timeout:
        return "FILTERED"
    except ConnectionRefusedError:
        return "REFUSED"
    finally:
        s.close()
```

| Outcome | Means | Implication |
|---|---|---|
| **OPEN** | something is listening | usable |
| **REFUSED** | packet reached the host, nothing bound | **not** blocked — just start the service |
| **FILTERED** (timeout) | dropped upstream | provider/firewall policy — needs a support ticket, not a config change |

Worked use (Aug 2026, Hostinger KVM): `80/443/22` OPEN but
`25/587/465/143/993` all FILTERED. That is provider-level mail-port blocking,
so self-hosting mail on that box was ruled out **without touching the box**. A
reverse lookup returning a generic provider hostname
(`srvNNNNNN.<provider>.cloud`) independently kills outbound sending reputation —
check `socket.gethostbyaddr(ip)` before proposing any self-hosted mail plan.

## DNS — always against a public resolver

Query what the world sees, not what a local resolver cached:

```bash
nslookup -type=mx   example.com 8.8.8.8
nslookup -type=txt  example.com 8.8.8.8   # SPF lives at the root
nslookup -type=txt _dmarc.example.com 8.8.8.8
nslookup -type=ns   example.com 8.8.8.8   # where records must actually be edited
```

A live MX check overrode a stale memory entry this session: the note said the
domain had no MX; the probe showed three Zoho MX records already published. **DNS
state is exactly the kind of fact that changes between sessions** — the user
edits it without telling you. Probe before repeating any stored DNS claim.

## Pitfalls reading probe output

- **A policy rejection is not an answer about the target.** An SMTP `RCPT TO`
  probe from a residential IP returns
  `550 ... we generally do not accept email from dynamic IP's`. That is a verdict
  on **your** source IP, not on whether the mailbox exists. Reporting it as "the
  address does not exist" is a fabricated conclusion from real output.
- **An empty log is not proof of non-delivery.** Privacy modes scramble or omit
  entries; search by timestamp before concluding nothing arrived.
- **Absence of a record vs failure to query.** Confirm the query itself succeeded
  before reporting "no SPF" — a blank section can mean either.
- **HTTP 200 on an SPA proves only that a server answered.** For product or tier
  existence, census the rendered text; see `wrong-premise-vendor-plan.md`.
- **Probing from one vantage point and generalizing.** Availability, DNS, and
  blocking all vary by network location. State which one you used.

## Reporting shape

Show the measurement, then the conclusion, so the user can audit the step rather
than trust it:

> `203.0.113.10`: 80/443/22 OPEN, 25/587/465/143/993 FILTERED → provider blocks
> mail ports; self-hosting there is out.

When a probe contradicts a stored fact, say so explicitly and correct the store
in the same session.
