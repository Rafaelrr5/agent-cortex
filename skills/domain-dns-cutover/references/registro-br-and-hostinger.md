# registro.br and Hostinger — verified specifics

Provider-specific detail behind the generic procedure in SKILL.md. Everything
here was observed against live systems, not read off a docs page.

## registro.br (`.com.br` and other `.br`)

### The name never leaves

`.br` is a single registry. There is **no registrar-to-registrar transfer** like
`.com`. What providers market as "transfer your .br domain to us" is a change of
the **provider/vendor code** inside registro.br:

- Hostinger's code is **`HSTDOMAINS (127)`** (set under provider/ownership).
- This governs administration and renewal billing only.
- It is **independent of DNS** and independent of hosting.
- It is almost never required to put a site online. Do not bundle it into a
  go-live plan unless the user asked to consolidate billing.

Related gotcha: registering a *new* `.br` at a reseller with the same CPF/CNPJ
can fail with "you already have a domain registration on another provider" until
existing `.br` domains are pointed at that provider's code.

### Zone editor quirks

| Constraint | Detail |
|---|---|
| Root record name | leave the **Name field empty** — `@` is rejected |
| Rejected characters | `@` and `*` are not accepted anywhere |
| Unsupported type | no `SRV` records |
| Two-stage save | **ADICIONAR** only adds the row to the on-screen list; **SALVAR ALTERAÇÕES** commits the zone |

"Basic mode" vs "advanced mode" both mean *the zone is hosted at registro.br*.
Neither is relevant when delegating NS elsewhere — delegation bypasses the zone
entirely, and so does the "Modo básico só poderá ser selecionado em Nh" lock.

### The two banners are different

Seen together on one page, easy to conflate:

| Banner | Blocks |
|---|---|
| "os servidores DNS do domínio se encontram em transição … em aproximadamente Nh" | **publication of the whole zone** |
| "Devido à recente seleção do Modo avançado, o Modo básico só poderá ser selecionado em aproximadamente Nh" | only switching editing modes |

Observed: ~2 h transition after moving NS off an external provider. During it,
records are saved and visible in the panel while `a.auto.dns.br` and
`b.auto.dns.br` answer `NODATA`. Nothing is wrong; nothing should be re-saved.

Authoritative servers for registro.br-hosted zones: `a.auto.dns.br`
(200.160.2.88), `b.auto.dns.br` (200.160.2.89).

### Delegation is validated

Changing NS to an external provider triggers a lookup against that provider. If
it is not authoritative for the domain yet, registro.br refuses with a
"Pesquisa recusada" / query-refused error. Hence: create the zone at the
destination **first**.

The delegation action is **"Alterar servidores DNS"** in the DNS section of the
domain page — not the "Configurar Zona DNS" editor.

## Hostinger API

Base: `https://developers.hostinger.com/api/<group>/v1/...`
Auth: `Authorization: Bearer <token>`; token from hPanel → Account → API.

### Endpoints that earned their notes

| Call | Behaviour worth knowing |
|---|---|
| `GET /vps/v1/virtual-machines` | full inventory: id, plan, state, ipv4/ipv6, template, hostname |
| `GET /domains/v1/portfolio` | a not-yet-configured free domain shows as `{"domain": null, "status": "pending_setup"}` |
| `GET /dns/v1/zones/{domain}` | returns `[]` for a domain the account does not manage — indistinguishable from an empty zone |
| `PUT /dns/v1/zones/{domain}` | **`[DNS:4009] Domain not found`** until the domain is added to the account in hPanel. This is why zone creation cannot be automated as an onboarding step. |
| `POST /vps/v1/public-keys` | `{name, key}` → returns a real `{"id": N}` |
| `POST /vps/v1/public-keys/attach/{vmId}` | `{"ids":[N]}` → returns a **hollow body** `{"id":0,"name":"","state":""}` on HTTP 200 whether or not it did anything. **On an already-provisioned VM it frequently does nothing at all** — see "Key attach silently no-ops" below. Verify by SSH, never by response. |
| `GET /vps/v1/virtual-machines/{id}/public-keys` | **`[VPS:2002] Route is not found`** — the route does not exist. A routing error, not an auth failure; do not debug the token over it. |
| `PUT /vps/v1/virtual-machines/{id}/root-password` | **the reliable way into a running VM.** Generates a real queued action (`ct_set_rootpasswd`); password is live in ~30 s. Body must satisfy the symbol rule below. |
| `POST /vps/v1/virtual-machines/{id}/restart` | real action `ct_restart`; box is back in ~60 s |
| `POST /vps/v1/virtual-machines/{id}/recovery` | recovery mode, if locked out |

### Two API traps that cost real time

**1. `urllib` is blocked; `curl` is not.** A Python `urllib.request` call to this
API returns `403` with body `error code: 1010` — a Cloudflare User-Agent block,
**not** an auth or scope problem. The identical request via `curl` returns 200.
Do not go hunting for a token permission that is not missing. Shell out to curl:

```python
def api(method, path, payload=None):
    cmd = ["curl", "-s", "-w", "\n%{http_code}", "-X", method, API + path,
           "-H", "Authorization: Bearer " + TOKEN,
           "-H", "Content-Type: application/json"]
    if payload is not None:
        cmd += ["-d", json.dumps(payload)]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=90).stdout
    body, _, code = out.rpartition("\n")
    return int(code.strip() or 0), body
```

**2. Root password must contain one of `-().&@?'#;/,+`.** Otherwise `422`
`[VPS:2004]`. A generic random generator over `!@#%^*-_=+` fails this often
enough to look like an API bug — force at least one required symbol.

Distinguishing signal between the two failures: a Cloudflare block is a bare
`403 error code: 1010`; a validation failure is a `422` with a JSON `message`
and a `correlation_id`.

### Key attach silently no-ops on a running VM

Observed on one VM from two different machines, days apart:

- From machine A the attach worked and `ssh` succeeded ~20 s later.
- From machine B, `POST /public-keys` created key id fine, `attach` returned
  HTTP 200 twice, and `ssh -i` still gave `Permission denied (publickey,password)`
  at 25 s, 45 s, 4 min and 7 min. `ssh -v` confirmed the right key was offered
  and the server refused it.
- A **reboot did not help** — so the injection is not a boot-time step.
- **The diagnostic:** `GET /virtual-machines/{id}/actions` listed only the
  original `ct_create`. The attaches queued **no action at all**, while
  `restart` and `root-password` each produced a real action id. Hollow body +
  no action in the queue = nothing happened.

Read attach as reliable only at provisioning/rebuild time. On a live box, go
straight to the root-password route and install the key yourself on first login:

```python
cli.connect(IP, username="root", password=pw, timeout=25,
            allow_agent=False, look_for_keys=False)   # both flags required
cli.exec_command('install -d -m 700 /root/.ssh && '
                 'grep -qxF "$PUB" /root/.ssh/authorized_keys || '
                 'echo "$PUB" >> /root/.ssh/authorized_keys')
```

Write the generated password to a `chmod 600` file **before** applying it (never
into chat or logs), so a password can never be live and unknown. Once the key is
in `authorized_keys`, the password stops being the access path.


### MCP server

Official package `hostinger-api-mcp` on npm (publisher `devs_hostinger`), **not**
in the agent runtime’s MCP connector catalog when verified. Requires Node >= 24.

It ships **segmented binaries** rather than one monolith — register only what the
task needs:

| Binary | Tools |
|---|---|
| `hostinger-dns-mcp` | 8 |
| `hostinger-domains-mcp` | 40 |
| `hostinger-vps-mcp` | 63 |
| `hostinger-hosting-mcp` | 58 |
| `hostinger-mail-mcp` | 38 |
| `hostinger-reach-mcp` | 49 |
| `hostinger-ecommerce-mcp` | 29 |
| `hostinger-billing-mcp` | 9 |
| `hostinger-api-mcp` (all) | 371 |

Auth env var: `HOSTINGER_API_TOKEN` (`API_TOKEN` is a deprecated alias). OAuth
with PKCE is supported when no token is set, but only over stdio.

Tool names are `GROUP_actionV1` (e.g. `DNS_updateDNSRecordsV1`,
`VPS_attachPublicKeyV1`). To read the tool contract out of an installed copy:

```bash
node -e "
const t=require('fs').readFileSync('src/core/tools/dns.js','utf8')
  .replace(/\/\/ Auto-generated.*/,'').replace('export default','');
JSON.parse(t.trim().replace(/;\s*$/,''))
  .forEach(x=>console.log(x.name, x.method, x.path));
"
```

These tool lists are plain JSON (not minified), so they parse directly — unlike
the community packages covered in the mcp-connector-onboarding vetting notes.

## Web console

Hostinger's browser terminal did not accept pasted input in a real session — the
command simply never ran, with no error. Do not troubleshoot it and do not
escalate to guessing root passwords; attach an SSH key by API (SKILL.md Step 5)
and use a real `ssh` client.

## Fresh-VPS baseline

A newly provisioned Hostinger KVM box (Ubuntu 24.04) presents:

- port **22 open**, **80 and 443 closed**
- **no** firewall group configured on the provider side
- `GET /hosting/v1/websites` → `total: 0`

That is a bare server awaiting a webserver, not a misconfiguration.
