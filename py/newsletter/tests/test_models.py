"""models:LLM 输出归一化 + 前端契约序列化(别名/枚举)。"""

import unittest

from newsletter.models import Brief, BriefsPayload, Dir, LLMBrief, Tone


class TestLLMNormalization(unittest.TestCase):
    def test_facts_dict_leak_normalized(self):
        # 根治旧 bug:模型把 ["x"] 返成 [{"fact":"x"}]
        b = LLMBrief(facts=[{"fact": "10Y 4.48%"}, "VIX 16", {"x": "金价高位"}, {"text": "t"}])
        self.assertEqual(b.facts, ["10Y 4.48%", "VIX 16", "金价高位", "t"])
        self.assertTrue(all(isinstance(x, str) for x in b.facts))

    def test_interpretation_blank_dropped(self):
        b = LLMBrief(interpretation=["有内容", "", "  "])
        self.assertEqual(b.interpretation, ["有内容"])

    def test_tone_coercion(self):
        self.assertEqual(LLMBrief(tone="risk_on").tone, Tone.RISK_ON)
        self.assertEqual(LLMBrief(tone="RISK-OFF").tone, Tone.RISK_OFF)
        self.assertEqual(LLMBrief().tone, Tone.NEUTRAL)

    def test_impact_direction_coercion(self):
        b = LLMBrief(impact=[{"asset": "金", "watch": "w", "direction": "UP"},
                             {"asset": "债", "watch": "w", "direction": "甚么"}])
        self.assertEqual(b.impact[0].direction, Dir.UP)
        self.assertEqual(b.impact[1].direction, Dir.WATCH)  # 未知 → watch

    def test_empty_llm_brief(self):
        b = LLMBrief()
        self.assertEqual(b.facts, [])
        self.assertEqual(b.headline, "")


class TestContractSerialization(unittest.TestCase):
    def test_brief_camelcase_aliases(self):
        br = Brief(date="2026-06-18", weekday="周四",
                  hypotheses=[{"ifThen": "若A则B", "invalidation": "Z"}])
        obj = br.to_json_obj()
        self.assertEqual(set(obj), {"date", "weekday", "issue", "time", "tone", "headline",
                                    "metrics", "signals", "regime", "facts", "reads",
                                    "hypotheses", "impacts", "reviews", "news"})
        self.assertEqual(obj["hypotheses"][0], {
            "ifThen": "若A则B", "invalidation": "Z",
            "asset": "", "direction": "flat", "horizon": "h_20d",
            "confidence": 0.0, "keyFactors": [],
        })
        self.assertEqual(obj["tone"], "neutral")

    def test_payload_generated_at_alias(self):
        p = BriefsPayload(model="DeepSeek", generated_at="2026-06-18",
                          briefs=[Brief(date="2026-06-18", weekday="周四")])
        obj = p.to_json_obj()
        self.assertEqual(obj["generatedAt"], "2026-06-18")
        self.assertEqual(obj["model"], "DeepSeek")

    def test_news_cat_null(self):
        from newsletter.models import News
        n = News(title="t", source="s")
        self.assertIsNone(n.model_dump(by_alias=True)["cat"])


if __name__ == "__main__":
    unittest.main()
