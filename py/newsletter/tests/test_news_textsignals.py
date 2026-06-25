"""新闻文本信号(v1.8 P3):EPU / GPR / 鹰鸽 / 事件分类(纯代码,离线)。"""

import unittest

from newsletter.news import textsignals as txt


class TestTextSignals(unittest.TestCase):
    def test_epu(self):
        self.assertEqual(txt.epu_score("economic growth faces policy uncertainty from the Fed"), 1.0)
        self.assertEqual(txt.epu_score("the cat sat on the mat"), 0.0)  # 无三类词
        self.assertEqual(txt.epu_score("inflation rose"), 0.0)  # 缺政策 + 不确定

    def test_uncertainty_density(self):
        self.assertGreater(txt.uncertainty_density("uncertainty risk volatility doubt"), 0)
        self.assertEqual(txt.uncertainty_density("calm steady clear"), 0.0)

    def test_gpr(self):
        self.assertGreater(txt.gpr_density("war and sanctions raise geopolitical tension"), 0)
        self.assertEqual(txt.gpr_density("stocks rose on earnings"), 0.0)

    def test_hawkish_dovish(self):
        self.assertGreater(txt.hawkish_dovish("the Fed will hike and tighten, restrictive policy"), 0)  # 偏鹰
        self.assertLess(txt.hawkish_dovish("a rate cut and easing, dovish stimulus"), 0)  # 偏鸽
        self.assertIsNone(txt.hawkish_dovish("gold prices climbed"))  # 无信号

    def test_event_types(self):
        ev = txt.event_types("The FOMC raised rates amid CPI inflation data and oil prices")
        self.assertIn("monetary", ev)
        self.assertIn("inflation", ev)
        self.assertIn("energy", ev)
        self.assertEqual(txt.event_types("a quiet day"), [])

    def test_word_count(self):
        self.assertEqual(txt.word_count("one two three"), 3)
        self.assertEqual(txt.word_count(""), 0)


if __name__ == "__main__":
    unittest.main()
