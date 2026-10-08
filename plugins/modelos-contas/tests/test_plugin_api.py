"""Testes do backend do painel, contra um HERMES_HOME temporario com credenciais falsas.

Rodar com o Python do Hermes, apontando para o checkout:
    PYTHONPATH=<hermes-agent> <hermes-venv>/python -m pytest plugins/modelos-contas/tests
"""
import hashlib
import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

import pytest

API = Path(__file__).resolve().parents[1] / "dashboard" / "plugin_api.py"


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    for name in ("HERMES_COPILOT_ACP_COMMAND", "COPILOT_CLI_PATH", "ANTHROPIC_API_KEY", "ANTHROPIC_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    (tmp_path / "config.yaml").write_text(
        "model:\n  provider: anthropic\n  default: claude-opus-4-1\n"
        "fallback_providers:\n  - provider: copilot-acp\n    model: claude-sonnet-4\n", encoding="utf-8")
    from agent.credential_pool import PooledCredential
    from hermes_cli.auth import write_credential_pool
    rows = [PooledCredential(provider="anthropic", id=f"row{i}", label=f"conta{i + 1}", source="manual:hermes_pkce",
                             auth_type="oauth", access_token=f"fixture-{i}", priority=i) for i in range(2)]
    write_credential_pool("anthropic", [r.to_dict() for r in rows])
    return tmp_path


@pytest.fixture()
def api(home):
    spec = importlib.util.spec_from_file_location("modelos_contas_api", API)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def client(api):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    app = FastAPI()
    app.include_router(api.router)
    return TestClient(app)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_state_lists_providers_outside_the_pool(client):
    s = client.get("/state").json()
    assert [o["provider"] for o in [s["primary"], *s["fallback"]]] == ["anthropic", "copilot-acp"]
    external = [p for p in s["pools"] if p.get("external")]
    assert [p["provider"] for p in external] == ["copilot-acp"]
    assert external[0]["entries"][0]["label"] == "GitHub Copilot CLI (via ACP)"


def test_kiro_takes_over_the_copilot_acp_label(client, monkeypatch, api):
    monkeypatch.setattr(api, "_acp_command", lambda: "/opt/kiro-cli/kiro-cli")
    ext = next(p for p in client.get("/state").json()["pools"] if p.get("external"))
    assert ext["entries"][0]["label"] == "Kiro (via ACP)"


def test_kiro_quota_is_read_from_its_own_store(tmp_path, monkeypatch, api):
    db = tmp_path / "kiro.sqlite3"
    with sqlite3.connect(db) as c:
        c.execute("create table auth_kv (key text, value text)")
        c.execute("create table state (key text, value text)")
        c.execute("insert into auth_kv values ('kirocli:odic:token', ?)",
                  (json.dumps({"access_token": "fixture-kiro", "expires_at": "2999-01-01T00:00:00.1234567Z"}),))
        c.execute("insert into state values ('api.codewhisperer.profile', ?)",
                  (json.dumps({"arn": "arn:aws:codewhisperer:us-east-1:000000000000:profile/FAKE"}),))
    calls = []

    def fake_http(url, headers, data=None):
        calls.append((url, headers))
        return 200, {"nextDateReset": 1.7e9, "subscriptionInfo": {"subscriptionTitle": "KIRO PRO"},
                     "usageBreakdownList": [{"displayNamePlural": "Credits", "currentUsageWithPrecision": 250.0,
                                             "usageLimitWithPrecision": 1000.0, "nextDateReset": 1.7e9}]}

    monkeypatch.setattr(api, "_kiro_db", lambda: db)
    monkeypatch.setattr(api, "_http", fake_http)
    monkeypatch.setattr(api, "_kiro_renew", lambda cmd: pytest.fail("valid token must not trigger a renew"))
    q = api._quota_kiro("kiro-cli")
    assert q["plan"] == "KIRO PRO"
    assert q["windows"] == [{"label": "Credits 250/1000", "pct": 25.0, "reset": 1.7e9}]
    assert calls[0][0].startswith("https://q.us-east-1.amazonaws.com/getUsageLimits?")
    assert calls[0][1]["Authorization"] == "Bearer fixture-kiro"
    assert "fixture-kiro" not in json.dumps(q)


def test_expired_kiro_login_asks_kiro_to_renew_then_reports(tmp_path, monkeypatch, api):
    db = tmp_path / "kiro.sqlite3"
    with sqlite3.connect(db) as c:
        c.execute("create table auth_kv (key text, value text)")
        c.execute("create table state (key text, value text)")
        c.execute("insert into auth_kv values ('kirocli:odic:token', ?)",
                  (json.dumps({"access_token": "old", "expires_at": "2000-01-01T00:00:00Z"}),))
    renewed = []
    monkeypatch.setattr(api, "_kiro_db", lambda: db)
    monkeypatch.setattr(api, "_kiro_renew", renewed.append)
    assert "expirado" in api._quota_kiro("kiro-cli")["error"]
    assert renewed == ["kiro-cli"]


def test_order_save_rewrites_the_chain(client, home):
    r = client.post("/fallback", json={"chain": [{"provider": "anthropic", "model": "claude-opus-4-1"},
                                                  {"provider": "copilot-acp", "model": "claude-sonnet-4"}]})
    assert r.json() == {"ok": True, "count": 2}
    s = client.get("/state").json()
    assert [f["provider"] for f in s["fallback"]] == ["anthropic", "copilot-acp"]


def test_block_and_release_keep_the_login(client, home, api):
    if not client.get("/state").json()["capabilities"]["disable"]:
        pytest.skip("this Hermes has no `hermes auth disable`")
    client.post("/enabled", json={"provider": "anthropic", "id": "row0", "enabled": False})
    rows = {e["id"]: e for e in next(p for p in client.get("/state").json()["pools"] if p["provider"] == "anthropic")["entries"]}
    assert rows["row0"]["disabled"] and rows["row0"]["status"]["text"] == "bloqueada por voce"
    stored = json.loads((home / "auth.json").read_text(encoding="utf-8"))
    assert "fixture-0" in json.dumps(stored)  # continua logada
    client.post("/enabled", json={"provider": "anthropic", "id": "row0", "enabled": True})
    rows = {e["id"]: e for e in next(p for p in client.get("/state").json()["pools"] if p["provider"] == "anthropic")["entries"]}
    assert not rows["row0"]["disabled"]


def test_block_is_refused_cleanly_on_a_hermes_without_it(client, monkeypatch, api):
    monkeypatch.setattr(api, "_can_disable", lambda: False)
    assert client.get("/state").json()["capabilities"]["disable"] is False
    assert client.post("/enabled", json={"provider": "anthropic", "id": "row0", "enabled": False}).status_code == 501


def test_reading_never_rewrites_auth_json(client, home, monkeypatch, api):
    monkeypatch.setattr(api, "_http", lambda *a, **k: (0, None))  # sem rede
    before = _digest(home / "auth.json")
    client.get("/state")
    client.get("/limits?refresh=true")
    assert _digest(home / "auth.json") == before
