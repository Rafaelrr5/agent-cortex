"""Testes da logica de merge (sem rede, sem ssh): python test_hermes_link.py"""
import base64
import json
import unittest

import hermes_link as hl


def row(cid, at, rt, exp=0, status=None, source="manual:hermes_pkce"):
    return {"id": cid, "label": cid, "auth_type": "oauth", "source": source,
            "access_token": at, "refresh_token": rt, "expires_at_ms": exp, "last_status": status}


def jwt(exp):
    body = base64.urlsafe_b64encode(json.dumps({"exp": exp}).encode()).decode().rstrip("=")
    return f"h.{body}.s"


class Merge(unittest.TestCase):
    def test_conta_so_de_um_lado_vai_para_o_outro(self):
        to_l, to_r, probs = hl.merge_creds({"anthropic": [row("a", "x", "y")]}, {})
        self.assertEqual([r["id"] for r in to_r["anthropic"]], ["a"])
        self.assertEqual(to_l, {})
        self.assertEqual(probs, [])

    def test_par_igual_nao_mexe(self):
        self.assertEqual(hl.merge_creds({"anthropic": [row("a", "x", "y", 5)]},
                                        {"anthropic": [row("a", "x", "y", 5)]})[:2], ({}, {}))

    def test_mais_novo_vence(self):
        to_l, to_r, _ = hl.merge_creds({"anthropic": [row("a", "x1", "y1", 100)]},
                                       {"anthropic": [row("a", "x2", "y2", 200)]})
        self.assertEqual(to_l["anthropic"][0]["access_token"], "x2")
        self.assertEqual(to_l["anthropic"][0]["_base"], ("x1", "y1"))
        self.assertEqual(to_r, {})

    def test_viva_vence_morta_mesmo_mais_nova(self):
        to_l, to_r, probs = hl.merge_creds({"anthropic": [row("a", "x1", "y1", 900, "dead")]},
                                           {"anthropic": [row("a", "x2", "y2", 200)]})
        self.assertEqual(to_l["anthropic"][0]["access_token"], "x2")
        self.assertEqual(probs, [])

    def test_morta_dos_dois_lados_vira_aviso(self):
        _, _, probs = hl.merge_creds({"anthropic": [row("a", "x1", "y1", 1, "dead")]},
                                     {"anthropic": [row("a", "x2", "y2", 2, "dead")]})
        self.assertEqual(len(probs), 1)

    def test_expiracao_do_jwt_codex(self):
        to_l, _, _ = hl.merge_creds({"openai-codex": [row("c", jwt(100), "r1")]},
                                    {"openai-codex": [row("c", jwt(200), "r2")]})
        self.assertEqual(to_l["openai-codex"][0]["refresh_token"], "r2")

    def test_contas_emprestadas_ficam_de_fora(self):
        self.assertFalse(hl.own_row(row("cc", "x", "y", source="claude_code")))


class Files(unittest.TestCase):
    def test_plano(self):
        push, pull, skipped = hl.plan_files(
            {"a": [10, 1], "b": [10, 1], "c": [50, 1], "big": [99, hl.MAX_FILE + 1]},
            {"a": [11, 1], "c": [10, 1], "d": [5, 1], "big": [1, 1]})
        self.assertEqual((push, pull, skipped), (["b", "c"], ["d"], ["big"]))


if __name__ == "__main__":
    unittest.main()
