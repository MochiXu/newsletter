"""A/B 消融(v1.6 S5d):arm 幂等 / evaluate 按 lane(model·arm)拆分 + source / apply_actuals 取 B 臂。"""

import unittest

from newsletter import evaluate, predictions as pred, render
from newsletter.models import Brief, Hypothesis, ModelView


def _llm(asset, direction, horizon="h_5d", conf=0.6):
    from newsletter.models import LLMBrief
    return LLMBrief(hypotheses=[{"asset": asset, "direction": direction, "horizon": horizon,
                                 "confidence": conf, "if_then": "x", "invalidation": "z"}])


def _settled(model, arm, direction, realized, conf, source="forward", date="2026-06-01"):
    return {"created_date": date, "model": model, "asset": "NASDAQCOM", "direction": direction,
            "horizon": "h_5d", "confidence": f"{conf:.4f}", "status": "settled", "resolved_date": date,
            "realized_dir": realized, "realized_text": "+1.0%", "hit": "", "note": "",
            "base_dir": "up", "base_conf": "0.6000", "arm": arm, "source": source}


class TestArmIdempotency(unittest.TestCase):
    def test_arms_are_distinct_rows(self):
        views = {"deepseek": _llm("NASDAQCOM", "up")}
        rows: list[dict] = []
        pred.record(rows, "2026-06-01", views, arm="A", source="forward")
        pred.record(rows, "2026-06-01", views, arm="B", source="backfill")
        self.assertEqual(len(rows), 2)  # A、B 是不同行
        pred.record(rows, "2026-06-01", views, arm="A")  # 同臂重跑幂等
        self.assertEqual(len(rows), 2)
        self.assertEqual({r["arm"] for r in rows}, {"A", "B"})
        self.assertEqual({r["source"] for r in rows}, {"forward", "backfill"})


class TestEvaluateLanes(unittest.TestCase):
    def test_lane_split_and_source(self):
        rows = [
            _settled("m1", "A", "up", "up", 0.6, source="forward"),    # A 命中
            _settled("m1", "B", "down", "up", 0.6, source="backfill"),  # B 未中
        ]
        sc = evaluate.score(rows, long_df=None)
        self.assertIn("m1·A", sc["models"])
        self.assertIn("m1·B", sc["models"])
        self.assertEqual(sc["models"]["m1·A"]["overall"]["hit"], 1.0)
        self.assertEqual(sc["models"]["m1·B"]["overall"]["hit"], 0.0)
        self.assertEqual(sc["source"], "mixed")  # forward + backfill

    def test_no_arm_lane_is_model(self):
        rows = [_settled("m1", "", "up", "up", 0.6)]
        sc = evaluate.score(rows, long_df=None)
        self.assertIn("m1", sc["models"])  # 无臂 → lane=model
        self.assertEqual(sc["source"], "forward")


class TestApplyActualsPrefersB(unittest.TestCase):
    def test_b_arm_actual_used(self):
        brief = Brief(
            date="2026-06-01", weekday="周一", models=["m1"],
            views={"m1": ModelView(hypotheses=[
                Hypothesis(if_then="x", invalidation="z", asset="NASDAQCOM", direction="up", horizon="h_5d")
            ])},
        )
        ledger = [
            _settled("m1", "A", "up", "down", 0.6),  # A 臂:实际 down
            _settled("m1", "B", "up", "up", 0.6),    # B 臂:实际 up
        ]
        render.apply_actuals(brief, ledger)
        actual = brief.views["m1"].hypotheses[0].actual
        self.assertEqual(actual.status, "settled")
        self.assertEqual(actual.realized_dir.value, "up")  # 取了 B 臂(up),非 A(down)
        self.assertTrue(actual.hit)  # 预测 up vs B 实际 up → 命中


if __name__ == "__main__":
    unittest.main()
