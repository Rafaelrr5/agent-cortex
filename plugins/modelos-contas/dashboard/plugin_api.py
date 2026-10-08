"""Modelos e Contas — visao unificada de modelo padrao, cadeia de reserva, prioridade
das contas e limites reais de uso. Montado em /api/plugins/modelos-contas/.

Escritas passam pelas mesmas funcoes do core que `hermes auth priority` e
`hermes fallback` usam; o modelo padrao e gravado pela rota nativa
POST /api/model/set (chamada direto pelo frontend). Tokens so sao renovados em
memoria para consultar cota: auth.json nunca e reescrito por esta leitura.
"""
import json
import os
import sqlite3
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

router = APIRouter()

_SECRET_KEYS = {"access_token", "refresh_token", "api_key", "id_token", "agent_key"}


# --------------------------------------------------------------------------- state
def _status(e: Dict[str, Any], now: float) -> Dict[str, Any]:
    if e.get("disabled"):
        return {"kind": "reserva", "text": "bloqueada por voce", "until": None}
    reset = e.get("last_error_reset_at")
    if e.get("last_status") == "exhausted" and reset and float(reset) > now:
        if e.get("last_error_reason") == "reserva_urgencia_manual":
            return {"kind": "reserva", "text": "reserva de urgencia", "until": None}
        return {"kind": "bad", "text": "bloqueada", "until": float(reset)}
    cds = {m: float(t) for m, t in (e.get("model_cooldowns") or {}).items() if t and float(t) > now}
    if cds:
        m, t = min(cds.items(), key=lambda kv: kv[1])
        return {"kind": "warn", "text": f"pausa em {m}", "until": t}
    return {"kind": "ok", "text": "disponivel", "until": None}


def _raw_pool() -> Dict[str, List[Dict[str, Any]]]:
    from hermes_cli.auth import read_credential_pool
    return read_credential_pool() or {}


def _env(name: str) -> str:
    """Valor do .env do perfil ativo (o dashboard pode servir varios perfis)."""
    try:
        from agent.secret_scope import get_secret_str
        value = get_secret_str(name, "")
    except Exception:
        value = os.getenv(name, "")
    if not value:
        try:
            from hermes_cli.config import load_env
            value = (load_env() or {}).get(name, "")
        except Exception:
            value = ""
    return (value or "").strip()


def _acp_command() -> str:
    """Executavel por tras do provedor copilot-acp (o usuario pode apontar para o Kiro)."""
    return _env("HERMES_COPILOT_ACP_COMMAND") or _env("COPILOT_CLI_PATH") or "copilot"


def _is_kiro(command: str) -> bool:
    return Path(command).name.lower().startswith("kiro")


def _external_label(provider: str) -> str:
    if provider == "copilot-acp":
        return "Kiro (via ACP)" if _is_kiro(_acp_command()) else "GitHub Copilot CLI (via ACP)"
    return "login fora do pool"


def _can_disable() -> bool:
    """`hermes auth disable` ainda nao existe em todo Hermes: sem ele o botao some."""
    try:
        from agent.credential_pool import CredentialPool
        return hasattr(CredentialPool, "set_user_disabled")
    except Exception:
        return False


def _state() -> Dict[str, Any]:
    from hermes_cli.config import load_config
    from hermes_cli.fallback_config import get_fallback_chain

    cfg = load_config()
    m = cfg.get("model") or {}
    if isinstance(m, str):
        m = {"default": m}
    strategies = cfg.get("credential_pool_strategies") or {}
    now = time.time()
    pools = []
    for provider, entries in sorted(_raw_pool().items()):
        rows = []
        ordered = sorted(entries, key=lambda x: x.get("priority", 99))
        for i, e in enumerate(ordered):
            rows.append({
                "id": e.get("id"), "label": e.get("label"), "priority": e.get("priority"),
                "auth_type": e.get("auth_type"), "source": e.get("source"),
                "requests": e.get("request_count", 0), "status": _status(e, now),
                "error": e.get("last_error_message"), "disabled": bool(e.get("disabled")),
                "can_up": i > 0, "can_down": i < len(ordered) - 1, "locked_reason": None,
            })
        if rows:
            pools.append({"provider": provider, "strategy": strategies.get(provider, "fill_first"), "entries": rows})
    primary = {"provider": m.get("provider"), "model": m.get("default") or m.get("model"),
               "base_url": m.get("base_url") or None}
    fallback = [{"provider": f.get("provider"), "model": f.get("model"), "base_url": f.get("base_url")}
                for f in get_fallback_chain(cfg)]
    # Provedores da ordem sem conta no pool (ex.: copilot-acp/Kiro, que se autentica sozinho)
    # tambem aparecem, para mostrar a cota quando o provedor informa. Com o copilot-acp apontado
    # para o Kiro, o token do GitHub no pool `copilot` so libera o provedor: o bloco vira o do Kiro.
    if _is_kiro(_acp_command()):
        for pool in pools:
            if pool["provider"] == "copilot":
                pool["serves"], pool["title"] = "copilot-acp", "copilot · " + _external_label("copilot-acp")
    pooled = {p["provider"] for p in pools} | {p["serves"] for p in pools if p.get("serves")}
    for prov in dict.fromkeys(o["provider"] for o in [primary, *fallback] if o.get("provider")):
        if prov in pooled:
            continue
        pools.append({"provider": prov, "strategy": None, "external": True, "entries": [{
            "id": _EXTERNAL_PREFIX + prov, "label": _external_label(prov), "priority": 0,
            "auth_type": "externo", "source": None, "requests": None, "disabled": False,
            "status": {"kind": "ok", "text": "login externo", "until": None}, "error": None,
            "can_up": False, "can_down": False, "locked_reason": None,
        }]})
    return {
        "primary": primary,
        "fallback": fallback,
        "pools": pools,
        "capabilities": {"disable": _can_disable()},
        "now": now,
    }


@router.get("/state")
async def state():
    try:
        return await run_in_threadpool(_state)
    except Exception as exc:  # contrato de plugin: nunca estourar para o cliente
        return {"error": f"nao foi possivel ler a configuracao: {exc}"}


# --------------------------------------------------------------------------- priority
class PriorityBody(BaseModel):
    provider: str
    id: str
    priority: int


@router.post("/priority")
async def set_priority(body: PriorityBody):
    from agent.credential_pool import load_pool

    def _run():
        pool = load_pool(body.provider.strip().lower())
        moved = pool.move_entry(body.id, int(body.priority))
        if moved is None:
            raise HTTPException(status_code=404, detail="conta nao encontrada neste provedor")
        note = "Posicao ajustada ao tamanho da lista." if moved.priority != body.priority else None
        return {"ok": True, "effective": moved.priority, "note": note}

    return await run_in_threadpool(_run)


# --------------------------------------------------------------------------- block / release
class EnabledBody(BaseModel):
    provider: str
    id: str
    enabled: bool


@router.post("/enabled")
async def set_enabled(body: EnabledBody):
    """Mesma funcao do core que `hermes auth disable|enable`: a conta continua logada."""
    from agent.credential_pool import load_pool

    if not _can_disable():
        raise HTTPException(status_code=501, detail="este Hermes ainda nao tem `hermes auth disable`")

    def _run():
        pool = load_pool(body.provider.strip().lower())
        if pool.set_user_disabled(body.id, not body.enabled) is None:
            raise HTTPException(status_code=404, detail="conta nao encontrada neste provedor")
        return {"ok": True}

    return await run_in_threadpool(_run)


# --------------------------------------------------------------------------- fallback chain
class ChainEntry(BaseModel):
    provider: str
    model: str
    base_url: Optional[str] = None


class ChainBody(BaseModel):
    chain: List[ChainEntry]


@router.post("/fallback")
async def set_fallback(body: ChainBody):
    from hermes_cli.config import load_config, save_config

    chain, seen = [], set()
    for c in body.chain:
        p, mdl = c.provider.strip(), c.model.strip()
        if not p or not mdl:
            raise HTTPException(status_code=400, detail="toda reserva precisa de provedor e modelo")
        key = (p, mdl, (c.base_url or "").strip())
        if key in seen:
            continue
        seen.add(key)
        entry = {"provider": p, "model": mdl}
        if c.base_url:
            entry["base_url"] = c.base_url.strip()
        chain.append(entry)

    def _run():
        try:
            from hermes_cli.web_server import _CONFIG_MUTATION_LOCK as lock
        except Exception:
            import threading
            lock = threading.RLock()
        with lock:
            cfg = load_config()
            cfg["fallback_providers"] = chain
            cfg.pop("fallback_model", None)
            save_config(cfg)
        return {"ok": True, "count": len(chain)}

    return await run_in_threadpool(_run)


# --------------------------------------------------------------------------- limits
def _http(url: str, headers: Dict[str, str], data: Optional[bytes] = None):
    req = urllib.request.Request(url, headers=headers, data=data)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as ex:
        body = ex.read().decode("utf-8", "replace")
        try:
            return ex.code, json.loads(body)
        except Exception:
            return ex.code, body
    except Exception as ex:
        return 0, str(ex)


def _friendly(code: int, body: Any) -> str:
    msg = ""
    if isinstance(body, dict):
        err = body.get("error")
        msg = (err.get("message") if isinstance(err, dict) else err) or body.get("detail") or ""
    msg = str(msg or body)[:160]
    if code == 401 or "revoked" in msg or "expired" in msg:
        return "acesso expirado ou revogado: refaca o login desta conta"
    if code == 429:
        return "o provedor recusou a consulta por excesso de chamadas; tente de novo em instantes"
    if code == 0:
        return "sem conexao com o provedor"
    return f"o provedor respondeu {code}: {msg}"


def _anthropic_token(e: Dict[str, Any]) -> Optional[str]:
    tok, refresh, exp = e.get("access_token"), e.get("refresh_token"), e.get("expires_at_ms") or 0
    if e.get("source") == "claude_code" or not tok:
        try:
            c = json.loads((Path.home() / ".claude" / ".credentials.json").read_text(encoding="utf-8"))["claudeAiOauth"]
            tok, refresh, exp = c["accessToken"], c.get("refreshToken"), c.get("expiresAt") or 0
        except Exception:
            return None
    if exp and exp / 1000 < time.time() + 60 and refresh:
        code, j = _http("https://console.anthropic.com/v1/oauth/token", {"Content-Type": "application/json"},
                        json.dumps({"grant_type": "refresh_token", "refresh_token": refresh,
                                    "client_id": "9d1c250a-e61b-44d9-88ed-5944d1962f5e"}).encode())
        if code == 200 and isinstance(j, dict):
            tok = j.get("access_token", tok)
    return tok


def _quota_anthropic(e: Dict[str, Any]) -> Dict[str, Any]:
    tok = _anthropic_token(e)
    if not tok:
        return {"error": "token desta conta nao encontrado"}
    h = {"Authorization": f"Bearer {tok}", "anthropic-beta": "oauth-2025-04-20", "User-Agent": "claude-cli/2.0.0"}
    out: Dict[str, Any] = {"windows": []}
    c, p = _http("https://api.anthropic.com/api/oauth/profile", h)
    if c == 200 and isinstance(p, dict):
        acc, org = p.get("account") or {}, p.get("organization") or {}
        out["email"] = acc.get("email") or acc.get("email_address")
        out["plan"] = org.get("organization_type") or ""
    c, u = _http("https://api.anthropic.com/api/oauth/usage", h)
    if c != 200 or not isinstance(u, dict):
        out["error"] = _friendly(c, u)
        return out
    names = {"five_hour": "Sessao 5h", "seven_day": "Semana", "seven_day_opus": "Semana Opus",
             "seven_day_sonnet": "Semana Sonnet"}
    for k, label in names.items():
        w = u.get(k)
        if isinstance(w, dict) and w.get("utilization") is not None:
            out["windows"].append({"label": label, "pct": w.get("utilization"), "reset": w.get("resets_at")})
    x = u.get("extra_usage")
    if isinstance(x, dict) and x.get("is_enabled"):
        used, lim = x.get("used_credits"), x.get("monthly_limit")
        pct = (used / lim * 100) if used is not None and lim else x.get("utilization")
        out["windows"].append({"label": "Creditos extras (mes)", "pct": pct, "reset": None})
    return out


def _quota_codex(e: Dict[str, Any]) -> Dict[str, Any]:
    tok, refresh = e.get("access_token"), e.get("refresh_token")
    if not tok:
        return {"error": "token desta conta nao encontrado"}
    hdr = lambda t: {"Authorization": f"Bearer {t}", "User-Agent": "codex_cli_rs/0.40.0"}
    c, u = _http("https://chatgpt.com/backend-api/wham/usage", hdr(tok))
    if c == 401 and refresh:  # renova so em memoria
        rc, j = _http("https://auth.openai.com/oauth/token", {"Content-Type": "application/json"},
                      json.dumps({"grant_type": "refresh_token", "refresh_token": refresh,
                                  "client_id": "app_EMoamEEZ73f0CkXaXp7hrann"}).encode())
        if rc == 200 and isinstance(j, dict) and j.get("access_token"):
            c, u = _http("https://chatgpt.com/backend-api/wham/usage", hdr(j["access_token"]))
    if c != 200 or not isinstance(u, dict):
        return {"error": _friendly(c, u)}
    out: Dict[str, Any] = {"windows": [], "email": u.get("email"), "plan": u.get("plan_type")}
    rl = u.get("rate_limit") or {}
    for k in ("primary_window", "secondary_window"):
        w = rl.get(k)
        if not isinstance(w, dict):
            continue
        secs = w.get("limit_window_seconds") or 0  # janela nao vem rotulada: identificar pela duracao
        label = "Sessao 5h" if secs and secs <= 6 * 3600 else "Semana" if secs >= 6 * 86400 else f"Janela {secs // 3600}h"
        reset = w.get("reset_at") or (time.time() + w["reset_after_seconds"] if w.get("reset_after_seconds") else None)
        out["windows"].append({"label": label, "pct": w.get("used_percent"), "reset": reset})
    return out


def _kiro_db() -> Optional[Path]:
    home = Path.home()
    candidates = [Path(os.environ.get("LOCALAPPDATA", str(home))) / "kiro-cli" / "data.sqlite3",
                  home / ".local" / "share" / "kiro-cli" / "data.sqlite3",
                  home / "Library" / "Application Support" / "kiro-cli" / "data.sqlite3"]
    return next((p for p in candidates if p.is_file()), None)


def _kiro_session(db: Path):
    """(access_token, expira_em_epoch, profile_arn) do banco do kiro-cli, so leitura."""
    with closing(sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True, timeout=5)) as c:
        row = c.execute("select value from auth_kv where key = 'kirocli:odic:token'").fetchone()
        prof = c.execute("select value from state where key = 'api.codewhisperer.profile'").fetchone()
    if not row:
        return None, 0.0, None
    tok = json.loads(row[0])
    try:
        exp = datetime.strptime(str(tok.get("expires_at"))[:19], "%Y-%m-%dT%H:%M:%S").replace(
            tzinfo=timezone.utc).timestamp()
    except ValueError:
        exp = 0.0
    return tok.get("access_token"), exp, (json.loads(prof[0]).get("arn") if prof else None)


def _kiro_renew(command: str) -> None:
    """O proprio kiro-cli renova e grava o login dele; `/usage` nao gasta credito."""
    flags = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW
    try:
        subprocess.run([command, "chat", "--no-interactive", "/usage"], capture_output=True,
                       stdin=subprocess.DEVNULL, timeout=60, creationflags=flags)
    except (OSError, subprocess.SubprocessError):
        pass


def _quota_kiro(command: str) -> Dict[str, Any]:
    db = _kiro_db()
    if db is None:
        return {"error": "login do Kiro nao encontrado neste computador (rode `kiro-cli login`)"}
    tok, exp, arn = _kiro_session(db)
    if not tok or exp < time.time() + 60:
        _kiro_renew(command)
        tok, exp, arn = _kiro_session(db)
    if not tok or exp < time.time():
        return {"error": "login do Kiro expirado: rode `kiro-cli login`"}
    if not arn:
        return {"error": "perfil do Kiro nao encontrado (rode `kiro-cli profile`)"}
    query = urllib.parse.urlencode({"origin": "AI_EDITOR", "profileArn": arn, "resourceType": "AGENTIC_REQUEST"})
    region = arn.split(":")[3] if arn.count(":") >= 4 else "us-east-1"
    c, u = _http(f"https://q.{region}.amazonaws.com/getUsageLimits?{query}",
                 {"Authorization": f"Bearer {tok}", "Accept": "application/json"})
    if c != 200 or not isinstance(u, dict):
        return {"error": _friendly(c, u)}
    sub = u.get("subscriptionInfo") or {}
    out: Dict[str, Any] = {"windows": [], "plan": sub.get("subscriptionTitle"),
                           "email": (u.get("userInfo") or {}).get("email")}
    for b in u.get("usageBreakdownList") or []:
        for item, prefix in ((b, ""), (b.get("freeTrialInfo") or {}, "Teste gratis: ")):
            used = item.get("currentUsageWithPrecision", item.get("currentUsage"))
            limit = item.get("usageLimitWithPrecision", item.get("usageLimit"))
            if used is None or not limit:
                continue
            name = b.get("displayNamePlural") or b.get("displayName") or "Uso"
            out["windows"].append({"label": f"{prefix}{name} {used:g}/{limit:g}", "pct": used / limit * 100,
                                   "reset": item.get("nextDateReset") or b.get("nextDateReset") or u.get("nextDateReset")})
    if not out["windows"]:
        out["error"] = "o Kiro nao informou limite para esta conta"
    return out


def _external_fetcher(provider: str):
    """Cota de provedor que se autentica fora do pool, quando existe uma API para isso."""
    if provider == "copilot-acp":
        command = _acp_command()
        if _is_kiro(command):
            return lambda: _quota_kiro(command)
    return None


_EXTERNAL_PREFIX = "externo:"
_FETCHERS = {"anthropic": _quota_anthropic, "openai-codex": _quota_codex}
_cache: Dict[str, Any] = {"at": 0.0, "data": None}


def _limits() -> Dict[str, Any]:
    jobs = [(p, e.get("id"), (lambda f=_FETCHERS[p], e=e: f(e)))
            for p, es in _raw_pool().items() if p in _FETCHERS for e in es]
    for pool in _state()["pools"]:
        fetch = _external_fetcher(pool.get("serves") or pool["provider"]) if pool.get("external") or pool.get("serves") else None
        if fetch:
            jobs.append((pool["provider"], pool["entries"][0]["id"], fetch))
    with ThreadPoolExecutor(max_workers=6) as ex:
        results = list(ex.map(lambda job: job[2](), jobs))
    accounts = {}
    for (p, entry_id, _), q in zip(jobs, results):
        accounts[entry_id] = {"provider": p, **{k: v for k, v in q.items() if k not in _SECRET_KEYS}}
    return {"accounts": accounts, "checked_at": datetime.now().strftime("%d/%m %H:%M")}


@router.get("/limits")
async def limits(refresh: bool = False):
    if refresh or not _cache["data"] or time.time() - _cache["at"] > 120:
        try:
            _cache["data"] = await run_in_threadpool(_limits)
            _cache["at"] = time.time()
        except Exception as exc:
            return {"accounts": {}, "error": f"nao foi possivel consultar os limites: {exc}"}
    return _cache["data"]
