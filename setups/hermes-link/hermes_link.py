#!/usr/bin/env python3
"""hermes-link: duas maquinas Hermes (ex.: seu PC e um servidor) com as mesmas
contas de modelo, uma pasta compartilhada e as conversas uma da outra.

O que cada rodada faz (o PC roda a cada 10 min pelo cron do Hermes; o servidor
so responde pelo ssh, nao precisa enxergar o PC):

1. Contas: compara o pool de contas OAuth (anthropic, openai-codex) dos dois
   lados e copia a versao mais nova de cada conta para o outro lado. Conta que
   so existe de um lado e copiada para o outro. Assim voce faz login uma vez so.
   Por que "a mais nova": o refresh token dessas contas e de uso unico. Quando
   um lado renova, o token antigo do outro lado morre; a rodada leva o par novo
   para la antes que ele faca falta. Por isso a renovacao fica centralizada
   aqui: cada rodada renova neste lado as contas que vencem em ate 150 min e
   empurra o par novo para o servidor na hora. No servidor, deixe o
   oauth_keepalive.py com "within": 30 (de hora em hora): ele so renova se este
   lado ficou desligado e as contas estao para vencer.
2. Conversas: exporta em markdown (segredos mascarados) as conversas recentes
   de cada lado para shared/sessions/<nome-da-maquina>/.
3. Pasta compartilhada: HERMES_HOME/shared fica igual nos dois lados; vence o
   arquivo modificado por ultimo. Apagar nao se propaga: apague nos dois lados.

Instalar (no PC, com acesso ssh ao servidor):
    python hermes_link.py --install --remote usuario@host --ssh-key ~/.ssh/chave \\
        --name pc --remote-name vm
Rodar na mao:   python hermes_link.py
Saida vazia = nada mudou. Problemas que precisam de voce (conta morta nos dois
lados) viram aviso no Telegram pelo servidor, no maximo um por dia.
"""
from __future__ import annotations

import argparse
import base64
import glob
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

PROVIDERS = ("anthropic", "openai-codex")
NO_WINDOW = 0x08000000 if os.name == "nt" else 0
MAX_FILE = 25 * 1024 * 1024
FIRST_EXPORT = "14d"


def hermes_home() -> Path:
    env = os.environ.get("HERMES_HOME", "").strip()
    if env:
        return Path(env)
    local = os.environ.get("LOCALAPPDATA", "").strip()
    if os.name == "nt" and local:
        return Path(local) / "hermes"
    return Path.home() / ".hermes"


HOME = hermes_home()
SHARED = HOME / "shared"
STATE = HOME / "state" / "hermes-link.json"
CFG = HOME / "scripts" / "hermes_link.json"


def hermes_python() -> str:
    """Python do proprio Hermes (tem os modulos de credencial)."""
    pat = "Scripts/python.exe" if os.name == "nt" else "bin/python"
    found = glob.glob(str(HOME / "installs" / "*" / "environments" / "*" / "venv" / pat))
    return max(found, key=os.path.getmtime) if found else sys.executable


def auth_api():
    agent_dir = os.environ.get("HERMES_AGENT_DIR", "").strip() or str(HOME / "hermes-agent")
    sys.path.insert(0, agent_dir)
    from hermes_cli import auth
    return auth


def load_state() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=1), encoding="utf-8")


# ---------- contas ----------

def own_row(e: dict) -> bool:
    """So contas que o Hermes logou; emprestadas (claude_code) e chaves de API ficam de fora."""
    return (isinstance(e, dict) and str(e.get("source") or "").startswith("manual")
            and e.get("auth_type") == "oauth" and bool(e.get("refresh_token")))


def expiry_ms(e: dict) -> int:
    ms = int(e.get("expires_at_ms") or 0)
    tok = e.get("access_token") or ""
    if tok.count(".") == 2:  # JWT (openai-codex): o exp esta no payload
        try:
            body = tok.split(".")[1]
            exp = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4))).get("exp")
            ms = max(ms, int(exp or 0) * 1000)
        except (ValueError, TypeError):
            pass
    return ms


def rank(e: dict) -> tuple:
    return (e.get("last_status") != "dead", expiry_ms(e))


def pair(e: dict | None) -> tuple:
    return ((e or {}).get("access_token"), (e or {}).get("refresh_token"))


def dump_creds() -> dict:
    auth = auth_api()
    return {p: [e for e in auth.read_credential_pool(p) if own_row(e)] for p in PROVIDERS}


def merge_creds(local: dict, remote: dict) -> tuple[dict, dict, list[str]]:
    """Devolve (para_local, para_remoto, problemas). Cada lado recebe so o que mudou."""
    to_local: dict = {}
    to_remote: dict = {}
    problems: list[str] = []
    for p in PROVIDERS:
        lrows = {e["id"]: e for e in local.get(p, [])}
        rrows = {e["id"]: e for e in remote.get(p, [])}
        for cid in sorted(set(lrows) | set(rrows)):
            le, re_ = lrows.get(cid), rrows.get(cid)
            if le and re_ and pair(le) == pair(re_):
                winner = le
            elif le and re_:
                winner = le if rank(le) >= rank(re_) else re_
                loser = re_ if winner is le else le
                # _base = par que o lado de destino tinha quando lemos; se ele renovou depois, o disco vence.
                (to_remote if winner is le else to_local).setdefault(p, []).append({**winner, "_base": pair(loser)})
            else:
                winner = le or re_
                (to_remote if le else to_local).setdefault(p, []).append(winner)
            if winner.get("last_status") == "dead":
                problems.append(f"{p} '{winner.get('label')}' esta morta nos dois lados "
                                f"({winner.get('last_error_reason') or 'dead'})")
    return to_local, to_remote, problems


def write_creds(changes: dict) -> list[str]:
    auth = auth_api()
    done = []
    for p, rows in changes.items():
        current = [e for e in auth.read_credential_pool(p) if isinstance(e, dict)]
        by_id = {e.get("id"): e for e in current}
        bases, cleared, incoming = {}, [], {}
        for row in rows:
            row = dict(row)
            base = row.pop("_base", None)
            old = by_id.get(row["id"])
            if old is not None and base is not None:
                bases[row["id"]] = tuple(base)
                if old.get("last_status") == "dead" and row.get("last_status") != "dead":
                    cleared.append(row["id"])  # morta por token gasto; o par novo a revive
            incoming[row["id"]] = row
            done.append(f"{p}:{row.get('label')}")
        ordered = [incoming.pop(e.get("id"), e) for e in current] + list(incoming.values())
        # Cooldowns de cota ja gravados neste lado sao preservados pelo proprio Hermes no merge.
        auth.write_credential_pool(p, ordered, token_bases=bases, status_cleared_ids=cleared)
    return done


def refresh_due(within: float) -> tuple[list[str], list[str]]:
    """Renova AQUI as contas que vencem em ate `within` minutos. Quem chama empurra o par novo
    para o outro lado na mesma rodada: o refresh token e de uso unico, entao a renovacao tem
    que acontecer de um lado so e chegar ao outro em segundos."""
    auth_api()
    from agent.credential_pool import STATUS_DEAD, STATUS_EXHAUSTED, load_pool
    done, problems = [], []
    for p in PROVIDERS:
        pool = load_pool(p)
        for e in pool.entries():
            row = {"source": e.source, "auth_type": e.auth_type, "refresh_token": e.refresh_token,
                   "access_token": e.access_token, "expires_at_ms": getattr(e, "expires_at_ms", 0)}
            if not own_row(row) or e.last_status in (STATUS_DEAD, STATUS_EXHAUSTED):
                continue
            if (expiry_ms(row) / 1000 - time.time()) / 60 > within:
                continue
            try:
                r = pool.try_refresh_matching(credential_id=e.id)
            except Exception as exc:
                r, err = None, type(exc).__name__
            else:
                err = None
            if r is None or r.last_status == STATUS_DEAD:
                problems.append(f"{p} '{e.label}' nao renovou ({err or (r.last_error_reason if r else 'refresh falhou')})")
            else:
                done.append(f"{p}:{e.label}")
    return done, problems


# ---------- conversas ----------

def hermes_bin() -> str:
    return shutil.which("hermes") or str(Path.home() / ".local" / "bin" / "hermes")


def export_sessions(name: str, sources: list[str]) -> int:
    state = load_state()
    since = state.get("exported_until") or FIRST_EXPORT
    started = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() - 60))
    out = SHARED / "sessions" / name
    out.mkdir(parents=True, exist_ok=True)
    n = 0
    for src in sources:
        r = subprocess.run([hermes_bin(), "sessions", "export", "--format", "md", "--redact",
                            "--source", src, "--newer-than", since, "--min-messages", "2",
                            "--yes", str(out) + os.sep],
                           capture_output=True, timeout=600, creationflags=NO_WINDOW)
        text = (r.stdout + r.stderr).decode("utf-8", "replace")
        if r.returncode:
            raise RuntimeError(f"export {src}: {text.strip()[-300:]}")
        for word in text.split():
            if word.isdigit():
                n += int(word)
                break
    (out / "manifest.jsonl").unlink(missing_ok=True)
    state["exported_until"] = started
    save_state(state)
    return n


# ---------- pasta compartilhada ----------

def manifest() -> dict:
    SHARED.mkdir(parents=True, exist_ok=True)
    m = {}
    for path in SHARED.rglob("*"):
        if path.is_file() and not path.name.endswith(".hermes-link.tmp"):
            st = path.stat()
            m[path.relative_to(SHARED).as_posix()] = [st.st_mtime, st.st_size]
    return m


def read_files(rels: list[str]) -> dict:
    return {rel: [(SHARED / rel).stat().st_mtime, base64.b64encode((SHARED / rel).read_bytes()).decode()]
            for rel in rels if (SHARED / rel).is_file()}


def write_files(files: dict) -> int:
    root = SHARED.resolve()
    for rel, (mtime, data) in files.items():
        dest = (SHARED / rel).resolve()
        if root not in dest.parents:
            continue  # nunca escreve fora da pasta compartilhada
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(dest.name + ".hermes-link.tmp")
        tmp.write_bytes(base64.b64decode(data))
        os.replace(tmp, dest)
        os.utime(dest, (mtime, mtime))
    return len(files)


def plan_files(local: dict, remote: dict) -> tuple[list[str], list[str], list[str]]:
    push, pull, skipped = [], [], []
    for rel in sorted(set(local) | set(remote)):
        lm, rm = local.get(rel), remote.get(rel)
        if lm and rm and lm[1] == rm[1] and abs(lm[0] - rm[0]) <= 2:
            continue
        newer_local = rm is None or (lm is not None and lm[0] > rm[0])
        size = (lm if newer_local else rm)[1]
        if size > MAX_FILE:
            skipped.append(rel)
        else:
            (push if newer_local else pull).append(rel)
    return push, pull, skipped


# ---------- ponte ssh ----------

SERVE = {
    "dump_creds": lambda _: dump_creds(),
    "write_creds": write_creds,
    "export_sessions": lambda a: export_sessions(a["name"], a["sources"]),
    "manifest": lambda _: manifest(),
    "read_files": read_files,
    "write_files": write_files,
    "alert": lambda msg: subprocess.run([hermes_bin(), "send", "-q", "-t", "telegram", "-f", "-"],
                                        input=msg.encode(), timeout=90).returncode,
}


def serve(op: str) -> int:
    arg = json.loads(sys.stdin.read() or "null")
    sys.stdout.write(json.dumps({"ok": SERVE[op](arg)}))
    return 0


class Remote:
    def __init__(self, cfg: dict):
        self.cfg = cfg

    def __call__(self, op: str, arg=None):
        c = self.cfg
        cmd = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=20"]
        if c.get("ssh_key"):
            cmd += ["-i", os.path.expanduser(c["ssh_key"])]
        remote_cmd = (f"P=$(ls -t ~/.hermes/installs/*/environments/*/venv/bin/python 2>/dev/null | head -1); "
                      f"exec ${{P:-python3}} ~/.hermes/scripts/hermes_link.py --serve {op}")
        r = subprocess.run(cmd + [c["remote"], remote_cmd], input=json.dumps(arg).encode(),
                           capture_output=True, timeout=900, creationflags=NO_WINDOW)
        if r.returncode:
            raise RuntimeError(f"servidor ({op}): {r.stderr.decode('utf-8', 'replace').strip()[-300:]}")
        return json.loads(r.stdout.decode("utf-8"))["ok"]


def alert_once(remote: Remote, problems: list[str]) -> None:
    state = load_state()
    key = "|".join(sorted(problems))
    if state.get("alerted") == key and time.time() - state.get("alerted_at", 0) < 86400:
        return
    remote("alert", "Hermes: conta(s) de modelo precisam de login de novo\n- " + "\n- ".join(problems)
           + "\nComo resolver: hermes auth remove PROVEDOR NOME e depois "
             "hermes auth add PROVEDOR --type oauth --label NOME (em qualquer um dos dois lados)")
    state.update(alerted=key, alerted_at=time.time())
    save_state(state)


def run(cfg: dict, steps=("creds", "sessions", "files")) -> list[str]:
    remote = Remote(cfg)
    report = []
    if "creds" in steps:
        to_local, to_remote, problems = merge_creds(dump_creds(), remote("dump_creds"))
        if to_remote:
            report.append("contas -> " + cfg["remote_name"] + ": " + ", ".join(remote("write_creds", to_remote)))
        if to_local:
            report.append("contas <- " + cfg["remote_name"] + ": " + ", ".join(write_creds(to_local)))
        # Renovacao centralizada aqui (quem roda o cron): renova e ja empurra o par novo.
        renewed, failed = refresh_due(float(cfg.get("refresh_within", 150)))
        if renewed:
            _, push, _ = merge_creds(dump_creds(), remote("dump_creds"))
            if push:
                remote("write_creds", push)
            report.append("renovadas e enviadas: " + ", ".join(renewed))
        problems += failed
        if problems:
            report += problems
            alert_once(remote, problems)
    if "sessions" in steps:
        n = export_sessions(cfg["name"], cfg.get("sources", ["cli", "local"]))
        n += remote("export_sessions", {"name": cfg["remote_name"], "sources": cfg.get("remote_sources", ["cli", "telegram"])})
        if n:
            report.append(f"conversas exportadas: {n}")
    if "files" in steps:
        push, pull, skipped = plan_files(manifest(), remote("manifest"))
        if push:
            remote("write_files", read_files(push))
        if pull:
            write_files(remote("read_files", pull))
        if push or pull:
            report.append(f"pasta shared: {len(push)} enviados, {len(pull)} recebidos")
        if skipped:
            report.append(f"grandes demais (>25 MB), nao copiados: {', '.join(skipped[:5])}")
    return report


def install(args) -> int:
    dest = HOME / "scripts" / "hermes_link.py"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if Path(__file__).resolve() != dest.resolve():
        shutil.copy2(__file__, dest)
    cfg = json.loads(CFG.read_text(encoding="utf-8")) if CFG.is_file() else {}
    for k in ("remote", "ssh_key", "name", "remote_name"):
        if getattr(args, k, None):
            cfg[k] = getattr(args, k)
    if not cfg.get("remote"):
        print("faltou --remote usuario@host")
        return 2
    cfg.setdefault("name", "pc")
    cfg.setdefault("remote_name", "servidor")
    CFG.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    scp = ["scp", "-q", "-o", "BatchMode=yes"] + (["-i", os.path.expanduser(cfg["ssh_key"])] if cfg.get("ssh_key") else [])
    subprocess.run(scp + [str(dest), f"{cfg['remote']}:.hermes/scripts/hermes_link.py"], check=True, creationflags=NO_WINDOW)
    listed = subprocess.run([hermes_bin(), "cron", "list"], capture_output=True, creationflags=NO_WINDOW)
    if b"hermes-link" not in listed.stdout:
        subprocess.run([hermes_bin(), "cron", "create", args.every, "--name", "hermes-link", "--no-agent",
                        "--script", "hermes_link.py", "--deliver", "local"], check=True, creationflags=NO_WINDOW)
    print(f"instalado: {dest}, cron hermes-link ({args.every}); servidor: {cfg['remote']}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--serve", choices=sorted(SERVE), help=argparse.SUPPRESS)
    ap.add_argument("--install", action="store_true", help="instala no PC e no servidor e cria o cron")
    ap.add_argument("--remote", help="usuario@host do servidor")
    ap.add_argument("--ssh-key", dest="ssh_key")
    ap.add_argument("--name", help="nome desta maquina (pasta das conversas)")
    ap.add_argument("--remote-name", dest="remote_name")
    ap.add_argument("--every", default="*/10 * * * *", help="frequencia do cron. Padrao: a cada 10 min")
    ap.add_argument("--only", choices=["creds", "sessions", "files"], action="append")
    ap.add_argument("--refresh-within", dest="refresh_within", type=float,
                    help="renova as contas que vencem em ate N minutos (padrao 150; o .json pode mudar)")
    args = ap.parse_args(argv)
    if args.serve:
        return serve(args.serve)
    if args.install:
        return install(args)
    if not CFG.is_file():
        print(f"sem configuracao em {CFG}; rode com --install primeiro")
        return 2
    cfg = json.loads(CFG.read_text(encoding="utf-8"))
    if args.refresh_within is not None:
        cfg["refresh_within"] = args.refresh_within
    report = run(cfg, tuple(args.only or ("creds", "sessions", "files")))
    if report:
        print("\n".join(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
