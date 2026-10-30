"""Offline contract tests for the existing TWSE stock-detail endpoint.

Run: python -m unittest discover -s tests -v
No network calls, credentials, database or production side effects.
"""
import importlib.util
import json
import pathlib
import unittest
from unittest.mock import patch
from io import BytesIO

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("stock_detail", ROOT / "api" / "stock_detail.py")
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class FakeResponse:
    def raise_for_status(self):
        pass

    def json(self):
        return [{"Code": "2330", "Name": "台積電", "ClosingPrice": "1000"},
                {"Code": "2454", "Name": "聯發科", "ClosingPrice": "1200"}]


def invoke(path):
    instance = object.__new__(module.handler)
    instance.path = path
    instance.wfile = BytesIO()
    instance.send_response = lambda code: setattr(instance, "status", code)
    instance.send_header = lambda *args: None
    instance.end_headers = lambda: None
    instance.do_GET()
    return instance.status, json.loads(instance.wfile.getvalue().decode("utf-8"))


class StockDetailContractTests(unittest.TestCase):
    @patch.object(module.requests, "get", return_value=FakeResponse())
    def test_valid_stock(self, mocked):
        status, payload = invoke("/api/stock_detail?code=2330")
        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["data"]["Code"], "2330")
        self.assertIn("STOCK_DAY_ALL", mocked.call_args.args[0])

    @patch.object(module.requests, "get")
    def test_missing_code_rejected_before_network(self, mocked):
        status, payload = invoke("/api/stock_detail")
        self.assertEqual(status, 400)
        self.assertFalse(payload["ok"])
        mocked.assert_not_called()

    @patch.object(module.requests, "get", return_value=FakeResponse())
    def test_unknown_code(self, mocked):
        status, payload = invoke("/api/stock_detail?code=9999")
        self.assertEqual(status, 404)
        self.assertFalse(payload["ok"])


if __name__ == "__main__":
    unittest.main()
