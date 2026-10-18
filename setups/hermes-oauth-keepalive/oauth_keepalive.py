"""Mantem vivas as contas OAuth do Hermes (Claude, ChatGPT/Codex) e avisa quando uma morre.

Por que existe: o refresh token de uma conta que fica dias sem uso expira
(HTTP 400 invalid_grant, "Refresh token expired"). Com a estrategia fill_first
as contas reserva ficam paradas e morrem em silencio; quando o failover precisa
delas, nao ha nada. Um refresh diario renova o par de tokens de cada conta.

Uso:
  python oauth_keepalive.py                       verifica e renova (modo cron)
  python oauth_keepalive.py --install [--deliver telegram] [--at "10 4 * * *"]
                                                  copia para HERMES_HOME/scripts e cria o cron

Saida do modo cron: stdout vazio = tudo ok (o cron fica em silencio);
stdout com texto = aviso de conta morta para o dono.

Opcional: HERMES_HOME/scripts/oauth_keepalive.json com
  {"forward_ssh": "usuario@host", "ssh_key": "/caminho/da/chave"}
repassa o aviso por ssh para outra maquina rodar `hermes send` (util quando
esta maquina nao tem gateway de mensagens).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PROVIDERS = ("anthropic", "openai-codex")
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def hermes_home() -> Path:
    env = os.environ.get("HERMES_HOME", "").strip()
    if env:
        return Path(env)
    local = os.environ.get("LOCALAPPDATA", "").strip()
    if os.name == "nt" and local:
        return Path(local) / "hermes"
    return Path.home() / ".hermes"


def load_pool_api():
    agent_dir = os.environ.get("HERMES_AGENT_DIR", "").strip() or str(hermes_home() / "hermes-agent")
    sys.path.insert(0, agent_dir)
    from agent.credential_pool import STATUS_DEAD, STATUS_EXHAUSTED, load_pool
    return load_pool, STATUS_DEAD, STATUS_EXHAUSTED


def check(providers=PROVIDERS) -> list[str]:
    load_pool, dead, exhausted = load_pool_api()
    problems: list[str] = []
    for provider in providers:
        try:
            pool = load_pool(provider)
        except Exception as exc:  # pool ilegivel: avisa e segue para o proximo
            problems.append(f"{provider}: nao consegui ler as contas ({type(exc).__name__})")
            continue
        for e in pool.entries():
            # So contas que o proprio Hermes logou; emprestadas (claude_code, gh_cli) e chaves de API ficam de fora.
            if not str(e.source or "").startswith("manual") or e.auth_type != "oauth" or not e.refresh_token:
                continue
            if (getattr(e, "extra", None) or {}).get("disabled"):
                continue
            if e.last_status == dead:
                problems.append(f"{provider} '{e.label}' esta morta ({e.last_error_reason or 'dead'})")
                continue
            if e.last_status == exhausted:
                continue  # em cooldown de cota: o refresh apagaria o cooldown. Renova amanha.
            err = None
            try:
                r = pool.try_refresh_matching(credential_id=e.id)
            except Exception as exc:
                r, err = None, type(exc).__name__
            if r is None or r.last_status == dead:
                why = err or (r.last_error_reason if r else None) or "refresh falhou"
                problems.append(f"{provider} '{e.label}' nao renovou ({why})")
    return problems


def message(problems: list[str]) -> str:
    where = "Windows" if os.name == "nt" else os.uname().nodename
    return (f"Hermes ({where}): conta(s) de modelo precisam de login de novo\n- "
            + "\n- ".join(problems)
            + "\nComo resolver: saia da conta no navegador e rode, no terminal, "
              "hermes auth remove PROVEDOR NOME e depois hermes auth add PROVEDOR --type oauth --label NOME")


def forward(msg: str, cfg_path: Path) -> None:
    if not cfg_path.is_file():
        return
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    host = cfg.get("forward_ssh")
    if not host:
        return
    cmd = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=20"]
    if cfg.get("ssh_key"):
        cmd += ["-i", os.path.expanduser(cfg["ssh_key"])]
    cmd += [host, "bash -lc 'hermes send -q -t telegram -f -'"]
    r = subprocess.run(cmd, input=msg, text=True, capture_output=True, timeout=90, creationflags=NO_WINDOW)
    if r.returncode:
        print(f"(repasse por ssh falhou: {r.stderr.strip()[-200:]})")


def install(deliver: str, schedule: str) -> int:
    dest = hermes_home() / "scripts" / "oauth_keepalive.py"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if Path(__file__).resolve() != dest.resolve():
        shutil.copyfile(__file__, dest)
    hermes = shutil.which("hermes")
    if not hermes:
        print(f"copiado para {dest}; comando hermes nao encontrado, crie o cron manualmente")
        return 1
    listing = subprocess.run([hermes, "cron", "list"], capture_output=True, text=True, creationflags=NO_WINDOW).stdout
    if "oauth-keepalive" in listing:
        print(f"script atualizado em {dest}; o cron oauth-keepalive ja existe")
        return 0
    r = subprocess.run([hermes, "cron", "create", schedule, "--name", "oauth-keepalive", "--no-agent",
                        "--script", "oauth_keepalive.py", "--deliver", deliver],
                       capture_output=True, text=True, creationflags=NO_WINDOW)
    print(r.stdout.strip() or r.stderr.strip())
    return r.returncode


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Renova as contas OAuth do Hermes e avisa quando uma morre.")
    ap.add_argument("--install", action="store_true", help="copia para HERMES_HOME/scripts e cria o cron diario")
    ap.add_argument("--deliver", default="local", help="destino do aviso no cron (ex.: telegram, all). Padrao: local")
    ap.add_argument("--at", default="10 4 * * *", help="horario cron. Padrao: 04:10 todo dia")
    args = ap.parse_args(argv)
    if args.install:
        return install(args.deliver, args.at)
    problems = check()
    if problems:
        msg = message(problems)
        print(msg)
        forward(msg, Path(__file__).with_suffix(".json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
