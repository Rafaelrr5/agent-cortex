import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("checker", Path(__file__).parents[1] / "scripts/check_delivery.py")
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)

class DeliveryTests(unittest.TestCase):
    def test_success(self):
        self.assertEqual(checker.validate({"criteria": [{"id": "smoke", "status": "verified", "evidence": "assertion passed"}], "pending": []}), 1)

    def test_refusals(self):
        for report in [None, {}, {"criteria": [], "pending": []},
                       {"criteria": [{"id": "x", "status": "failed", "evidence": "exit 1"}], "pending": []},
                       {"criteria": [{"id": "x", "status": "verified", "evidence": ""}], "pending": []},
                       {"criteria": [{"id": "x", "status": "verified", "evidence": "ok"}]},
                       {"criteria": [{"id": "x", "status": "verified", "evidence": "ok"}] * 2, "pending": []}]:
            with self.subTest(report=report), self.assertRaises(ValueError):
                checker.validate(report)
