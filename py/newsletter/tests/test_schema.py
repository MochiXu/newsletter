"""schema:confidence 语义钉死(校准前提)+ roster「不超不漏」约束。"""

import unittest

from newsletter.llm import schema


class TestConfidenceSemantics(unittest.TestCase):
    """v1.6 S2:confidence 必须明确为'方向成立的主观概率',否则校准无意义。"""

    def _conf_prop(self) -> dict:
        return schema.BRIEF_SCHEMA["properties"]["hypotheses"]["items"]["properties"]["confidence"]

    def test_confidence_pinned_as_probability(self):
        conf = self._conf_prop()
        self.assertEqual(conf["type"], "number")
        self.assertIn("主观概率", conf["description"])
        self.assertIn("校准", conf["description"])

    def test_system_states_confidence_semantic(self):
        self.assertIn("主观概率", schema.SYSTEM)


class TestRosterConstraint(unittest.TestCase):
    """假设层锁死成固定 roster:每方向各给且只给一条(minItems==maxItems==资产数)。"""

    def test_hypotheses_min_max_locked(self):
        h = schema.BRIEF_SCHEMA["properties"]["hypotheses"]
        self.assertEqual(h["minItems"], h["maxItems"])
        # v1.7 多 horizon:网格 = 资产数 × 期限数(4 × 3 = 12)
        self.assertEqual(h["minItems"], schema._GRID_N)
        self.assertEqual(h["minItems"], len(schema._PRED_IDS) * len(schema._HORIZONS))
        self.assertEqual(h["items"]["properties"]["horizon"]["enum"], ["h_5d", "h_20d", "h_60d"])  # 砍 next_1d


if __name__ == "__main__":
    unittest.main()
