import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest

SCRIPT = Path(__file__).with_name("oauth_keepalive.py")

# Pool falso no lugar de agent.credential_pool do Hermes: le as contas de pool.json
# e grava em calls.json cada refresh pedido. Nenhuma rede, nenhuma conta real.
FAKE_POOL = textwrap.dedent('''
    import json, os
    from types import SimpleNamespace
    STATUS_DEAD, STATUS_EXHAUSTED = "dead", "exhausted"
    ROOT = os.path.dirname(os.path.dirname(__file__))
    def _calls(add=None):
        p = os.path.join(ROOT, "calls.json")
        c = json.load(open(p)) if os.path.exists(p) else []
        if add: c.append(add); json.dump(c, open(p, "w"))
        return c
    class Pool:
        def __init__(self, provider, rows):
            self.provider = provider
            self.rows = [SimpleNamespace(**r) for r in rows]
        def entries(self):
            return self.rows
        def try_refresh_matching(self, credential_id):
            _calls(credential_id)
            row = next(r for r in self.rows if r.id == credential_id)
            if row.refresh_result == "raise":
                raise RuntimeError("boom")
            row.last_status = row.refresh_result
            row.last_error_reason = "invalid_grant" if row.refresh_result == "dead" else None
            return row
    def load_pool(provider):
        data = json.load(open(os.path.join(ROOT, "pool.json")))
        if provider not in data:
            raise KeyError(provider)
        return Pool(provider, data[provider])
''')


def row(id, label, **kw):
    base = dict(id=id, label=label, source="manual:hermes_pkce", auth_type="oauth", refresh_token="rt",
                last_status="ok", last_error_reason=None, extra={}, refresh_result="ok")
    base.update(kw)
    return base


class Keepalive(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR"))
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "agent").mkdir()
        (self.root / "agent" / "__init__.py").write_text("")
        (self.root / "agent" / "credential_pool.py").write_text(FAKE_POOL)
        self.home = self.root / "home"
        self.home.mkdir()

    def run_cli(self, pool, *args, path=None):
        (self.root / "pool.json").write_text(json.dumps(pool))
        env = dict(os.environ, HERMES_AGENT_DIR=str(self.root), HERMES_HOME=str(self.home))
        if path is not None:
            env["PATH"] = path
        r = subprocess.run([sys.executable, "-B", str(SCRIPT), *args], capture_output=True, text=True,
                           env=env, timeout=30, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.assertEqual(r.returncode if not args else 0, 0, r.stderr)
        return r

    def calls(self):
        p = self.root / "calls.json"
        return json.loads(p.read_text()) if p.exists() else []

    def test_healthy_accounts_are_refreshed_silently(self):
        r = self.run_cli({"anthropic": [row("a1", "work"), row("a2", "backup")],
                          "openai-codex": [row("c1", "gpt")]})
        self.assertEqual(r.stdout, "")
        self.assertEqual(self.calls(), ["a1", "a2", "c1"])

    def test_dead_and_failed_refresh_alert(self):
        r = self.run_cli({"anthropic": [row("a1", "old", last_status="dead", last_error_reason="invalid_grant"),
                                        row("a2", "dies", refresh_result="dead"),
                                        row("a3", "crash", refresh_result="raise")],
                          "openai-codex": []})
        self.assertIn("anthropic 'old' esta morta (invalid_grant)", r.stdout)
        self.assertIn("anthropic 'dies' nao renovou (invalid_grant)", r.stdout)
        self.assertIn("anthropic 'crash' nao renovou (RuntimeError)", r.stdout)
        self.assertEqual(self.calls(), ["a2", "a3"])  # a conta ja morta nao gasta refresh

    def test_skips_exhausted_borrowed_apikey_and_disabled(self):
        r = self.run_cli({"anthropic": [row("a1", "cooldown", last_status="exhausted"),
                                        row("a2", "claude_code", source="claude_code"),
                                        row("a3", "key", auth_type="api_key"),
                                        row("a4", "off", extra={"disabled": True})],
                          "openai-codex": [row("c1", "gpt")]})
        self.assertEqual(r.stdout, "")
        self.assertEqual(self.calls(), ["c1"])

    def test_unreadable_provider_is_reported_not_fatal(self):
        r = self.run_cli({"anthropic": [row("a1", "work")]})
        self.assertIn("openai-codex: nao consegui ler as contas (KeyError)", r.stdout)
        self.assertEqual(self.calls(), ["a1"])

    def test_install_copies_script_without_hermes_on_path(self):
        r = self.run_cli({}, "--install", path=str(self.root / "empty-bin"))
        dest = self.home / "scripts" / "oauth_keepalive.py"
        self.assertTrue(dest.is_file())
        self.assertEqual(dest.read_bytes(), SCRIPT.read_bytes())
        self.assertEqual(r.returncode, 1)
        self.assertIn("crie o cron manualmente", r.stdout)


if __name__ == "__main__":
    unittest.main()
