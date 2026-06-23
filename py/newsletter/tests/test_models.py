"""models:LLM 输出归一化 + 前端契约序列化(别名/枚举)。"""

import unittest

from newsletter.models import Brief, BriefsPayload, Dir, LLMBrief, TaggedItem, Tone


class TestLLMNormalization(unittest.TestCase):
    def test_facts_tagged_normalized(self):
        # facts 升级为 [{tag,text}];容忍带标签 dict / 纯字符串 / 旧式 {fact} / 单值 dict(tag 置空);
        # 越界 tag(不在 FACT_TAGS)归空,与 schema 枚举对齐
        b = LLMBrief(facts=[{"tag": "利率", "text": "10Y 4.48%"}, "VIX 16", {"fact": "金价高位"},
                            {"x": "t"}, {"tag": "实际利率", "text": "越界标签"}])
        self.assertEqual(
            [(x.tag, x.text) for x in b.facts],
            [("利率", "10Y 4.48%"), ("", "VIX 16"), ("", "金价高位"), ("", "t"), ("", "越界标签")],
        )
        self.assertTrue(all(isinstance(x, TaggedItem) for x in b.facts))

    def test_figures_carried_and_dir_coerced(self):
        b = LLMBrief(facts=[{"tag": "利率", "text": "升 +9bp 至 2.23%",
                             "figures": [{"t": "+9bp", "dir": "UP"}, {"t": "2.23%", "dir": "flat"}]}])
        figs = b.facts[0].figures
        self.assertEqual([(x.t, x.dir.value) for x in figs], [("+9bp", "up"), ("2.23%", "flat")])

    def test_interpretation_blank_dropped(self):
        b = LLMBrief(interpretation=["有内容", "", "  ", {"tag": "黄金", "text": ""}])
        self.assertEqual([(x.tag, x.text) for x in b.interpretation], [("", "有内容")])

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
        # 旧扁平 brief(顶层 hypotheses)→ 迁移进 views.archive 单视图;脊柱 + views/models/consensus 为新契约
        br = Brief(date="2026-06-18", weekday="周四",
                  hypotheses=[{"ifThen": "若A则B", "invalidation": "Z"}])
        obj = br.to_json_obj()
        self.assertEqual(set(obj), {"date", "weekday", "issue", "time", "tz", "metrics", "signals",
                                    "regime", "priceSeries", "factors", "reviews", "news",
                                    "models", "views", "consensus"})
        self.assertEqual(obj["models"], ["archive"])
        view = obj["views"]["archive"]
        self.assertEqual(set(view), {"tone", "headline", "facts", "reads", "hypotheses", "impacts"})
        self.assertEqual(view["hypotheses"][0], {
            "ifThen": "若A则B", "invalidation": "Z",
            "asset": "", "direction": "flat", "horizon": "h_20d",
            "confidence": 0.0, "keyFactors": [], "actual": None,
        })
        self.assertEqual(view["tone"], "neutral")

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
