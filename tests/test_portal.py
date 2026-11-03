"""Synthetic protocol tests; these do not establish live API compatibility."""
import importlib
from pathlib import Path
import sys
import types
import unittest
from datetime import date

package = types.ModuleType("portal_test")
package.__path__ = [str(Path(__file__).resolve().parents[1] / "custom_components/stavy_meridel")]
sys.modules[package.__name__] = package
parser = importlib.import_module("portal_test.parser")
api = importlib.import_module("portal_test.api")


def fixture():
    return {"consumptionUnits": "m³", "measurementsTable": {
        "headers": [{"key": "sn", "label": "Sériové číslo"},
                    {"key": "room", "label": "Místnost"},
                    {"key": "old", "label": "ŘÍJEN 2026"},
                    {"key": "latest", "label": "LISTOPAD 2026"}],
        "rows": [{"sn": {"value": "123456"}, "room": {"value": "Koupelna"},
                  "old": {"value": 12}, "latest": {"value": "12,500"}}]}}


class ParserTests(unittest.TestCase):
    def parse(self, data):
        return parser.parse_dashboard(data, 4, date(2026, 11, 3))

    def test_czech_units_and_month(self):
        item, = self.parse(fixture())
        self.assertEqual((item.value, item.period, item.room), (12.5, "2026-11", "Koupelna"))

    def test_missing_latest_does_not_fall_back_to_old(self):
        data = fixture()
        data["measurementsTable"]["rows"][0]["latest"]["value"] = None
        self.assertIsNone(self.parse(data)[0].value)

    def test_future_column_ignored(self):
        data = fixture()
        data["measurementsTable"]["headers"].append({"key": "future", "label": "Prosinec 2026"})
        data["measurementsTable"]["rows"][0]["future"] = {"value": 999}
        self.assertEqual(self.parse(data)[0].value, 12.5)

    def test_unknown_header_rejected(self):
        data = fixture()
        data["measurementsTable"]["headers"] = [{"key": "sn", "label": "ID"}]
        with self.assertRaises(parser.SchemaError):
            self.parse(data)

    def test_bad_numbers_rejected(self):
        for value in (True, -1, "NaN", "inf", "chyba"):
            with self.subTest(value=value):
                data = fixture()
                data["measurementsTable"]["rows"][0]["latest"]["value"] = value
                with self.assertRaises(parser.SchemaError):
                    self.parse(data)

    def test_wrong_units_rejected(self):
        data = fixture()
        data["consumptionUnits"] = "l"
        with self.assertRaises(parser.SchemaError):
            self.parse(data)

    def test_reset_keeps_raw_state_without_computing_consumption(self):
        data = fixture()
        data["consumptionUnits"] = "dílky"
        data["measurementsTable"]["headers"][-2]["label"] = "Prosinec 2025"
        data["measurementsTable"]["headers"][-1]["label"] = "Leden 2026"
        data["measurementsTable"]["rows"][0]["latest"]["value"] = 2
        self.assertEqual(parser.parse_dashboard(data, 19, date(2026, 1, 3))[0].value, 2)

    def test_duplicate_serial_rejected(self):
        data = fixture()
        data["measurementsTable"]["rows"] *= 2
        with self.assertRaises(parser.SchemaError):
            self.parse(data)

    def test_failed_meter_unavailable(self):
        data = fixture()
        data["measurementsTable"]["rows"][0]["stav"] = {"icon": "error"}
        self.assertIsNone(self.parse(data)[0].value)

    def test_removed_meter_skipped(self):
        data = fixture()
        data["measurementsTable"]["rows"][0]["stav"] = {"icon": "trash"}
        self.assertEqual(self.parse(data), [])


class Response:
    def __init__(self, status, data):
        self.status, self.data = status, data

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def json(self):
        if isinstance(self.data, Exception):
            raise self.data
        return self.data


class Session:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return Response(*next(self.responses))


class ClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_expired_token_reauth_once(self):
        session = Session([(200, {"token": "first"}), (401, {}),
                           (200, {"token": "second"}), (200, {"ok": True})])
        client = api.PortalClient(session, "test", "example", "0000000000")
        self.assertEqual(await client.get("apartments/byCode"), {"ok": True})
        self.assertEqual(len(session.calls), 4)
        self.assertTrue(all(c[0].startswith(api.BASE_URL) for c in session.calls))
        self.assertTrue(all(c[1]["allow_redirects"] is False for c in session.calls))
        self.assertEqual(session.calls[-1][1]["headers"]["Authorization"], "Bearer second")

    async def test_invalid_password_not_retried_forever(self):
        session = Session([(401, {})])
        client = api.PortalClient(session, "test", "bad", "0000000000")
        with self.assertRaises(api.AuthError):
            await client.get("apartments/byCode")
        self.assertEqual(len(session.calls), 1)

    async def test_browser_challenge_is_error(self):
        session = Session([(200, ValueError("HTML"))])
        client = api.PortalClient(session, "test", "example", "0000000000")
        with self.assertRaises(api.ApiError):
            await client.login()

    async def test_redirect_not_followed(self):
        session = Session([(302, {})])
        client = api.PortalClient(session, "test", "example", "0000000000")
        with self.assertRaises(api.ApiError):
            await client.login()


if __name__ == "__main__":
    unittest.main()
