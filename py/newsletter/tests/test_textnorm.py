"""textnorm:确定性中英文排版规范化(标点 ASCII 化 / 盘古空格 / 句读补空格,数字内分隔符不动)。"""

import unittest

from newsletter.textnorm import normalize_text


class TestNormalizeText(unittest.TestCase):
    def test_pangu_spacing_cjk_alnum(self):
        self.assertEqual(normalize_text("较MA200偏弱"), "较 MA200 偏弱")
        self.assertEqual(normalize_text("升9bp至2.23%"), "升 9bp 至 2.23%")
        self.assertEqual(normalize_text("VIX跳上18.44"), "VIX 跳上 18.44")

    def test_no_split_alnum_tokens(self):
        # 词内字母数字不拆:9bp / 0.27% / 2s10s / MA200 保持完整
        for tok in ("9bp", "0.27%", "2s10s", "MA200", "risk-off"):
            self.assertIn(tok, normalize_text(f"前 {tok} 后"))

    def test_sign_attaches_to_number(self):
        self.assertEqual(normalize_text("收窄-2bp"), "收窄 -2bp")
        self.assertEqual(normalize_text("日涨+15bp"), "日涨 +15bp")

    def test_fullwidth_punct_to_ascii(self):
        self.assertEqual(normalize_text("利率上行,黄金承压。"), "利率上行, 黄金承压.")
        self.assertEqual(normalize_text("如『higher』所示"), "如'higher'所示")  # 引号转换;不在引号侧补空格
        self.assertEqual(normalize_text('用"双引号"'), "用'双引号'")  # 双引号→单引号(JSON 安全)

    def test_numeric_separators_kept(self):
        # 小数点 / 千分位不被当句读、不加空格
        self.assertEqual(normalize_text("收于7,500.58"), "收于 7,500.58")
        self.assertEqual(normalize_text("z=-0.29"), "z=-0.29")

    def test_sentence_period_between_numbers(self):
        # 句号在数字之间(全角→.)要补空格,避免 16.4%.60 粘连
        self.assertEqual(normalize_text("波动16.4%。60日回看"), "波动 16.4%. 60 日回看")

    def test_idempotent(self):
        once = normalize_text("升9bp至2.23%,黄金-7.8%。")
        self.assertEqual(normalize_text(once), once)

    def test_empty_safe(self):
        self.assertEqual(normalize_text(""), "")
        self.assertEqual(normalize_text(None), "")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
