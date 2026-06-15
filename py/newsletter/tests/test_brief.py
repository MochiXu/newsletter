"""M1 智能平面的离线单测(纯标准库 unittest,无网络)。

运行(仓库根目录):
    PYTHONPATH=py python3 -m unittest newsletter.tests.test_brief -v
"""

import tempfile
import unittest
from pathlib import Path

from newsletter.data import Observation, load_latest
from newsletter.deliver.feishu import _sign
from newsletter.render import fmt, render_markdown, render_text


def _obs():
    return [Observation("2026-06-16", "DGS10", "10Y", "2026-06-12", 4.48, "%", "FRED", "")]


class TestRender(unittest.TestCase):
    def test_fmt(self):
        self.assertEqual(fmt(4.48), "4.48")
        self.assertEqual(fmt(119.5073), "119.5073")
        self.assertEqual(fmt(0.4), "0.4")
        self.assertEqual(fmt(4335.0), "4335")

    def test_fallback_brief(self):
        md = render_markdown("2026-06-16", _obs(), None)
        self.assertIn("数据快照", md)
        self.assertIn("4.48", md)
        self.assertIn("ANTHROPIC_API_KEY", md)
        self.assertIn("不构成投资建议", md)

    def test_full_brief(self):
        brief = {
            "headline": "测试总览",
            "facts": ["10Y 4.48%"],
            "interpretation": ["利率偏高,压制长久期"],
            "hypotheses": [{"if_then": "若降息预期升温则金价走强", "invalidation": "实际利率反弹"}],
            "impact": [{"asset": "黄金", "watch": "盯实际利率"}],
        }
        md = render_markdown("2026-06-16", _obs(), brief)
        self.assertIn("测试总览", md)
        self.assertIn("解读层", md)
        self.assertIn("失效条件", md)
        self.assertIn("观察点", md)
        txt = render_text("2026-06-16", _obs(), brief)
        self.assertIn("可证伪假设", txt)
        self.assertIn("不构成投资建议", txt)


class TestData(unittest.TestCase):
    def test_load_latest_picks_newest_run_date(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "obs.csv"
            p.write_text(
                "run_date,series_id,label,obs_date,value,unit,source,note\n"
                "2026-06-15,DGS10,10Y,2026-06-12,4.40,%,FRED,\n"
                "2026-06-16,DGS10,10Y,2026-06-13,4.48,%,FRED,\n"
                '2026-06-16,DX-Y.NYB,"USD Index (DXY, ICE)",2026-06-15,99.66,index,Yahoo,"窄口径"\n',
                encoding="utf-8",
            )
            obs = load_latest(p)
            self.assertEqual(len(obs), 2)  # 只取最新 run_date(2026-06-16)
            self.assertEqual(obs[0].run_date, "2026-06-16")
            self.assertEqual(obs[0].value, 4.48)
            self.assertEqual(obs[1].label, "USD Index (DXY, ICE)")  # 引号字段正确解析

    def test_load_missing_file(self):
        self.assertEqual(load_latest(Path("/no/such/file.csv")), [])


class TestFeishuSign(unittest.TestCase):
    def test_sign_deterministic(self):
        a = _sign(1700000000, "secret")
        self.assertEqual(a, _sign(1700000000, "secret"))
        self.assertNotEqual(a, _sign(1700000001, "secret"))
        self.assertTrue(len(a) > 0)


if __name__ == "__main__":
    unittest.main()
