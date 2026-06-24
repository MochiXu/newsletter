"""非交易日 / 无数据日的空 brief 契约(v1.7):session + closed_reason、空脊柱、md、序列化。"""

import unittest

import pandas as pd

from newsletter import features, render
from newsletter.models import Brief


class TestHasObservation(unittest.TestCase):
    def _df(self):
        return pd.DataFrame({
            "series_id": ["NASDAQCOM", "NASDAQCOM", "XAUUSD"],
            "date": ["2026-06-17", "2026-06-18", "2026-06-18"],
            "value": [1.0, 2.0, 3.0],
        })

    def test_has_observation(self):
        df = self._df()
        self.assertTrue(features.has_observation(df, "NASDAQCOM", "2026-06-18"))
        self.assertFalse(features.has_observation(df, "NASDAQCOM", "2026-06-19"))  # 无该日

    def test_last_observation_date(self):
        self.assertEqual(features.last_observation_date(self._df(), "NASDAQCOM"), "2026-06-18")
        self.assertIsNone(features.last_observation_date(self._df(), "NOPE"))


class TestClosedBrief(unittest.TestCase):
    def test_closed_weekend(self):
        b = render.build_closed_brief("2026-06-20", "closed", "weekend")
        self.assertEqual(b.session, "closed")
        self.assertEqual(b.closed_reason, "weekend")
        self.assertEqual(b.metrics, [])
        self.assertEqual(b.views, {})  # 脊柱与 views 全空

    def test_no_data(self):
        b = render.build_closed_brief("2026-06-18", "no_data", "")
        self.assertEqual(b.session, "no_data")
        self.assertEqual(b.closed_reason, "")

    def test_default_session_trading(self):
        b = Brief(date="2026-06-18", weekday="周四")
        self.assertEqual(b.session, "trading")  # 默认交易日(向后兼容)

    def test_serializes_camel(self):
        obj = render.build_closed_brief("2026-06-20", "closed", "weekend").to_json_obj()
        self.assertEqual(obj["session"], "closed")
        self.assertEqual(obj["closedReason"], "weekend")  # 驼峰别名

    def test_markdown_closed(self):
        md = render.render_markdown(render.build_closed_brief("2026-06-20", "closed", "weekend"))
        self.assertIn("休市", md)
        self.assertIn("周末", md)

    def test_markdown_no_data(self):
        md = render.render_markdown(render.build_closed_brief("2026-06-18", "no_data", ""))
        self.assertIn("数据", md)


if __name__ == "__main__":
    unittest.main()
