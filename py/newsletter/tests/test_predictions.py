"""predictions:账本登记(幂等)、代码裁决(命中/未中/死区/利率 bp)、未到期 pending、actuals join。"""

import unittest

import pandas as pd

from newsletter import predictions as pred, render


def _llm(asset, direction, horizon="h_5d", conf=0.6):
    from newsletter.models import LLMBrief
    return LLMBrief(hypotheses=[{"asset": asset, "direction": direction, "horizon": horizon,
                                 "confidence": conf, "if_then": "x", "invalidation": "z"}])


def _series(sid, dates, vals):
    return pd.DataFrame({"date": dates, "series_id": [sid] * len(dates), "value": vals,
                         "source": ["t"] * len(dates)})


class TestRecord(unittest.TestCase):
    def test_record_all_models_and_idempotent(self):
        views = {"deepseek": _llm("NASDAQCOM", "up"), "anthropic": _llm("NASDAQCOM", "down")}
        rows: list[dict] = []
        pred.record(rows, "2026-06-01", views)
        self.assertEqual(len(rows), 2)  # 各模型一条(不止主模型)
        pred.record(rows, "2026-06-01", views)  # 同日重跑
        self.assertEqual(len(rows), 2)  # 按 (date,model,asset,horizon) 幂等
        self.assertEqual({r["model"] for r in rows}, {"deepseek", "anthropic"})
        self.assertEqual(rows[0]["status"], "pending")


class TestBackfill(unittest.TestCase):
    DATES10 = [f"2026-06-{d:02d}" for d in range(1, 11)]

    def test_settles_and_hit_price(self):
        long = _series("NASDAQCOM", self.DATES10, [100, 101, 102, 103, 104, 105, 106, 107, 108, 109])
        rows: list[dict] = []
        pred.record(rows, "2026-06-01", {"m": _llm("NASDAQCOM", "up", "h_5d")})
        newly = pred.backfill(rows, long, "2026-06-10")
        self.assertEqual(len(newly), 1)
        r = rows[0]
        self.assertEqual((r["status"], r["resolved_date"]), ("settled", "2026-06-06"))  # 06-01 起第5个交易日
        self.assertEqual((r["realized_dir"], r["hit"]), ("up", "1"))  # 涨 → up,预测 up → 命中
        self.assertTrue(r["realized_text"].endswith("%"))

    def test_miss_when_wrong_direction(self):
        long = _series("NASDAQCOM", self.DATES10, [100, 101, 102, 103, 104, 105, 106, 107, 108, 109])
        rows: list[dict] = []
        pred.record(rows, "2026-06-01", {"m": _llm("NASDAQCOM", "down", "h_5d")})  # 预测跌,实际涨
        pred.backfill(rows, long, "2026-06-10")
        self.assertEqual((rows[0]["realized_dir"], rows[0]["hit"]), ("up", "0"))

    def test_flat_deadband(self):
        # 微涨 0.2% < 0.5% 死区 → 判 flat
        long = _series("NASDAQCOM", self.DATES10, [100, 100, 100, 100, 100, 100.2, 100, 100, 100, 100])
        rows: list[dict] = []
        pred.record(rows, "2026-06-01", {"m": _llm("NASDAQCOM", "flat", "h_5d")})
        pred.backfill(rows, long, "2026-06-10")
        self.assertEqual((rows[0]["realized_dir"], rows[0]["hit"]), ("flat", "1"))

    def test_yield_in_bp(self):
        dates = [f"2026-06-{d:02d}" for d in range(1, 8)]
        long = _series("DGS2", dates, [4.00, 4.05, 4.10, 4.15, 4.20, 4.25, 4.30])  # 06-01→06-06 +25bp
        rows: list[dict] = []
        pred.record(rows, "2026-06-01", {"m": _llm("DGS2", "up", "h_5d")})
        pred.backfill(rows, long, "2026-06-07")
        r = rows[0]
        self.assertEqual((r["realized_dir"], r["hit"]), ("up", "1"))
        self.assertTrue(r["realized_text"].endswith("bp"))  # 利率类按 bp 而非 %

    def test_pending_when_not_enough_future(self):
        long = _series("NASDAQCOM", [f"2026-06-{d:02d}" for d in range(1, 5)], [100, 101, 102, 103])
        rows: list[dict] = []
        pred.record(rows, "2026-06-01", {"m": _llm("NASDAQCOM", "up", "h_5d")})  # 需第5个交易日,只有4天
        self.assertEqual(pred.backfill(rows, long, "2026-06-04"), [])
        self.assertEqual(rows[0]["status"], "pending")  # 尚未到期 → 仍 pending(前端沙漏)


class TestApplyActuals(unittest.TestCase):
    def test_join_into_brief_cards_and_consensus(self):
        a, b = _llm("NASDAQCOM", "up", "h_5d"), _llm("NASDAQCOM", "down", "h_5d")
        brief = render.build_brief("2026-06-01", {"deepseek": a, "anthropic": b}, [], [], [])
        rows: list[dict] = []
        pred.record(rows, "2026-06-01", {"deepseek": a, "anthropic": b})
        long = _series("NASDAQCOM", [f"2026-06-{d:02d}" for d in range(1, 11)],
                       [100, 101, 102, 103, 104, 105, 106, 107, 108, 109])
        pred.backfill(rows, long, "2026-06-10")
        render.apply_actuals(brief, rows)

        ds = brief.views["deepseek"].hypotheses[0].actual
        self.assertEqual((ds.status, ds.realized_dir.value, ds.hit), ("settled", "up", True))  # 预测 up,实际 up
        an = brief.views["anthropic"].hypotheses[0].actual
        self.assertFalse(an.hit)  # 预测 down,实际 up → 未中
        c = next(c for c in brief.consensus if c.asset == "NASDAQCOM")
        self.assertEqual(c.actual.status, "settled")
        self.assertEqual(c.actual.realized_dir.value, "up")
        self.assertFalse(c.actual.hit)  # up/down 平票 → 共识 flat,实际 up → 不算命中

    def test_pending_shows_when_unsettled(self):
        a = _llm("NASDAQCOM", "up", "h_20d")
        brief = render.build_brief("2026-06-01", {"deepseek": a}, [], [], [])
        rows: list[dict] = []
        pred.record(rows, "2026-06-01", {"deepseek": a})
        render.apply_actuals(brief, rows)  # 无 long_df 结算 → 仍 pending
        self.assertEqual(brief.views["deepseek"].hypotheses[0].actual.status, "pending")


if __name__ == "__main__":
    unittest.main()
