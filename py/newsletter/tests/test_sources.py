"""sources:各适配器解析 + HTTP key 安全(离线,monkeypatch http)。"""

import unittest
from unittest import mock

from newsletter.sources import fred, tiingo, twelvedata, yahoo
from newsletter.sources.base import FetchError, to_frame


class TestParsing(unittest.TestCase):
    def test_fred_parse_skips_missing(self):
        payload = {"observations": [
            {"date": "2026-06-10", "value": "4.40"},
            {"date": "2026-06-11", "value": "."},  # 缺失
            {"date": "2026-06-12", "value": "4.48"},
        ]}
        with mock.patch.object(fred, "http_get_json", return_value=payload):
            df = fred.FredSource("k").fetch("DGS10")
        self.assertEqual(list(df["date"]), ["2026-06-10", "2026-06-12"])
        self.assertEqual(list(df["value"]), [4.40, 4.48])

    def test_fred_missing_key(self):
        with self.assertRaises(FetchError):
            fred.FredSource(None).fetch("DGS10")

    def test_twelvedata_parse_and_error(self):
        ok = {"status": "ok", "values": [
            {"datetime": "2026-06-12", "close": "4360.0"},
            {"datetime": "2026-06-13", "close": "4365.5"},
        ]}
        with mock.patch.object(twelvedata, "http_get_json", return_value=ok):
            df = twelvedata.TwelveDataSource("k").fetch("XAU/USD")
        self.assertEqual(len(df), 2)
        self.assertEqual(df["value"].iloc[-1], 4365.5)
        with mock.patch.object(twelvedata, "http_get_json", return_value={"status": "error", "message": "bad symbol"}):
            with self.assertRaises(FetchError):
                twelvedata.TwelveDataSource("k").fetch("DXY")

    def test_tiingo_parse_close(self):
        payload = [
            {"date": "2026-06-12T00:00:00.000Z", "close": 27.8, "adjClose": 27.5},
            {"date": "2026-06-13T00:00:00.000Z", "close": 27.9, "adjClose": 27.6},
        ]
        with mock.patch.object(tiingo, "http_get_json", return_value=payload):
            df = tiingo.TiingoSource("tok").fetch("UUP")
        self.assertEqual(list(df["date"]), ["2026-06-12", "2026-06-13"])
        self.assertEqual(df["value"].iloc[-1], 27.9)  # 用 close 而非 adjClose

    def test_tiingo_error_dict(self):
        with mock.patch.object(tiingo, "http_get_json", return_value={"detail": "Not found"}):
            with self.assertRaises(FetchError):
                tiingo.TiingoSource("tok").fetch("NOPE")

    def test_yahoo_parse(self):
        payload = {"chart": {"result": [{
            "timestamp": [1749600000, 1749686400],
            "indicators": {"quote": [{"close": [4360.0, None]}]},  # None 应跳过
        }]}}
        with mock.patch.object(yahoo, "http_get_json", return_value=payload):
            df = yahoo.YahooSource().fetch("GC=F")
        self.assertEqual(len(df), 1)
        self.assertEqual(df["value"].iloc[0], 4360.0)


class TestToFrame(unittest.TestCase):
    def test_dedup_sort_dropna(self):
        df = to_frame([("2026-06-12", "1"), ("2026-06-10", "2"), ("2026-06-12", "3"), ("2026-06-11", "x")])
        # 升序、去重保留最后、非数丢弃
        self.assertEqual(list(df["date"]), ["2026-06-10", "2026-06-12"])
        self.assertEqual(df.loc[df.date == "2026-06-12", "value"].iloc[0], 3.0)


class TestKeySafety(unittest.TestCase):
    def test_http_error_strips_query(self):
        from newsletter.sources import base
        import urllib.error

        def boom(*a, **k):
            raise urllib.error.URLError("down")

        with mock.patch.object(base.urllib.request, "urlopen", side_effect=boom):
            with self.assertRaises(FetchError) as ctx:
                base.http_get_json("https://api.example.com/x?api_key=SECRET123&z=1", retries=1)
        self.assertNotIn("SECRET123", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
