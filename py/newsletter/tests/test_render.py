"""render:契约组装、新闻分类映射、复盘、briefs.json upsert(刊号重算)。"""

import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from newsletter import render
from newsletter.config import Paths
from newsletter.models import Brief, Dir, LLMBrief, NewsCat, ReviewStatus, Tone


class TestBuildMetrics(unittest.TestCase):
    def test_metrics_from_actual_obs(self):
        long = pd.DataFrame({
            "date": ["2026-06-12", "2026-06-15"],
            "series_id": ["DGS10", "DGS10"],
            "value": [4.40, 4.47],
            "source": ["fred", "fred"],
        })
        metrics = render.build_metrics(long, "2026-06-18")
        m = next(x for x in metrics if x.key == "dgs10")
        self.assertAlmostEqual(m.value, 4.47)
        self.assertAlmostEqual(m.change, 0.07)
        self.assertEqual(m.kind.value, "yield")
        # spark = 带日期的真实观测尾部序列(因果),供前端 sparkline + hover
        self.assertEqual([(p.date, p.value) for p in m.spark], [("2026-06-12", 4.40), ("2026-06-15", 4.47)])


class TestBuildNews(unittest.TestCase):
    def test_cat_mapping_filter_noise_and_nolink(self):
        merged = [
            {"source": "Fed", "title": "T1", "category": "事实", "affected_assets": ["美债"], "direction": "up", "link": "u1"},
            {"source": "CNBC", "title": "T2", "direction": "bad", "link": "u2"},  # 未分类 + 非法 dir → watch
            {"source": "MW", "title": "T3", "category": "噪音", "direction": "down", "link": "u3"},  # 噪音 → 丢弃
            {"source": "X", "title": "T4", "category": "事实", "link": ""},  # 无链接 → 丢弃
        ]
        news = render.build_news(merged)
        self.assertEqual([n.title for n in news], ["T1", "T2"])  # 噪音/无链接被过滤掉
        self.assertEqual(news[0].cat, NewsCat.FACT)
        self.assertEqual(news[0].dir, Dir.UP)
        self.assertIsNone(news[1].cat)  # 未分类
        self.assertEqual(news[1].dir, Dir.WATCH)  # 非法 dir → watch


class TestBuildReviews(unittest.TestCase):
    def test_resolved_today_first_then_open(self):
        rows = [
            {"if_then": "A", "status": "open"},
            {"if_then": "B", "status": "held", "resolved_date": "2026-06-18", "note": "n"},
            {"if_then": "C", "status": "invalidated", "resolved_date": "2026-06-01"},  # 往日定结,不计
        ]
        reviews = render.build_reviews(rows, "2026-06-18")
        self.assertEqual(reviews[0].status, ReviewStatus.HELD)  # 今日定结在前
        self.assertEqual(reviews[1].status, ReviewStatus.OPEN)
        self.assertEqual(len(reviews), 2)


class TestBuildBrief(unittest.TestCase):
    def test_degraded_when_llm_none(self):
        br = render.build_brief("2026-06-18", {}, [], [], [])
        self.assertEqual(br.models, ["offline"])  # 无 provider:单个离线空视图
        v = br.views[br.models[0]]
        self.assertEqual(v.tone, Tone.NEUTRAL)
        self.assertEqual(v.facts, [])
        self.assertEqual(br.consensus, [])
        self.assertEqual(br.weekday, "周四")

    def test_normalizes_text_and_keeps_figures(self):
        llm = LLMBrief(facts=[{"tag": "黄金", "text": "黄金-7.8%", "figures": [{"t": "-7.8%", "dir": "down"}]}])
        v = render.build_brief("2026-06-18", {"deepseek": llm}, [], [], []).views["deepseek"]
        self.assertEqual(v.facts[0].text, "黄金 -7.8%")  # normalize 加空格
        self.assertEqual(v.facts[0].figures[0].t, "-7.8%")  # figure.t 仍是 text 的子串
        self.assertEqual(v.facts[0].figures[0].dir.value, "down")

    def test_figure_token_absorbs_unit(self):
        # LLM 常把 token 写成纯数字('7.8')而漏掉百分号 → 落库时确定性并入单位,使整段一起上色
        llm = LLMBrief(facts=[{"tag": "黄金", "text": "黄金20日累计下跌7.8%", "figures": [{"t": "7.8", "dir": "down"}]}])
        v = render.build_brief("2026-06-18", {"deepseek": llm}, [], [], []).views["deepseek"]
        self.assertEqual(v.facts[0].figures[0].t, "7.8%")  # '7.8' → '7.8%'

    def test_figure_signed_token_resolves_to_unsigned(self):
        # LLM 常把 token 写成带符号('+15bp'/'-7.8%'),正文却用'升/跌'表方向不带符号 → 去符号后落实成正文子串(不可误杀)
        llm = LLMBrief(facts=[{"tag": "利率", "text": "US2Y升15bp,黄金跌7.8%",
                               "figures": [{"t": "+15bp", "dir": "up"}, {"t": "-7.8%", "dir": "down"}]}])
        v = render.build_brief("2026-06-18", {"deepseek": llm}, [], [], []).views["deepseek"]
        self.assertEqual([(f.t, f.dir.value) for f in v.facts[0].figures], [("15bp", "up"), ("7.8%", "down")])

    def test_figure_not_in_text_dropped(self):
        # 死 figure(连去符号也不在正文)应被丢弃,避免前端静默匹配不到
        llm = LLMBrief(facts=[{"tag": "黄金", "text": "黄金20日跌幅显著", "figures": [{"t": "7.8", "dir": "down"}]}])
        v = render.build_brief("2026-06-18", {"deepseek": llm}, [], [], []).views["deepseek"]
        self.assertEqual(v.facts[0].figures, [])

    def test_full_from_llm(self):
        llm = LLMBrief(headline="H", tone="risk_on", facts=["f1"], interpretation=["i1"],
                       hypotheses=[{"if_then": "x", "invalidation": "z"}],
                       impact=[{"asset": "金", "watch": "w", "direction": "down"}])
        v = render.build_brief("2026-06-18", {"deepseek": llm}, [], [], []).views["deepseek"]
        self.assertEqual(v.tone, Tone.RISK_ON)
        self.assertEqual(v.hypotheses[0].if_then, "x")
        self.assertEqual(v.impacts[0].dir, Dir.DOWN)


class TestBriefsJson(unittest.TestCase):
    def test_upsert_and_issue_recompute(self):
        with tempfile.TemporaryDirectory() as d:
            paths = Paths(Path(d))
            render.upsert_briefs_json(paths, Brief(date="2026-06-17", weekday="周三"), "DeepSeek")
            n = render.upsert_briefs_json(paths, Brief(date="2026-06-18", weekday="周四"), "DeepSeek")
            self.assertEqual(n, 2)
            data = json.loads(paths.briefs_json.read_text(encoding="utf-8"))
            self.assertEqual([b["date"] for b in data["briefs"]], ["2026-06-18", "2026-06-17"])  # 倒序
            issues = {b["date"]: b["issue"] for b in data["briefs"]}
            self.assertEqual(issues["2026-06-17"], 1)  # 最早 = 第 1 刊
            self.assertEqual(issues["2026-06-18"], 2)
            self.assertTrue((paths.briefs / "2026-06-18.json").exists())

    def test_upsert_tolerates_legacy_str_facts(self):
        # 回归红线:升级前的 briefs.json facts/reads 为 str[];upsert 会 model_validate 历史日报,
        # Brief 须能向后兼容旧格式(否则下次 pipeline 崩、无法落盘)。
        with tempfile.TemporaryDirectory() as d:
            paths = Paths(Path(d))
            paths.briefs.mkdir(parents=True, exist_ok=True)
            legacy = {
                "model": "M", "generatedAt": "2026-06-17",
                "briefs": [{"date": "2026-06-17", "weekday": "周三", "facts": ["旧事实1", "旧事实2"], "reads": ["旧解读"]}],
            }
            paths.briefs_json.write_text(json.dumps(legacy, ensure_ascii=False), encoding="utf-8")
            render.upsert_briefs_json(paths, Brief(date="2026-06-18", weekday="周四"), "M")  # 不应抛
            data = json.loads(paths.briefs_json.read_text(encoding="utf-8"))
            old = next(b for b in data["briefs"] if b["date"] == "2026-06-17")
            arch = old["views"]["archive"]  # 旧扁平 brief 迁移进 views.archive 单视图
            self.assertEqual([f["text"] for f in arch["facts"]], ["旧事实1", "旧事实2"])  # 迁移为 {tag,text}
            self.assertTrue(all(isinstance(f, dict) and "tag" in f for f in arch["facts"]))

    def test_upsert_same_date_overwrites(self):
        with tempfile.TemporaryDirectory() as d:
            paths = Paths(Path(d))
            render.upsert_briefs_json(paths, Brief(date="2026-06-18", weekday="周四", headline="old"), "M")
            render.upsert_briefs_json(paths, Brief(date="2026-06-18", weekday="周四", headline="new"), "M")
            data = json.loads(paths.briefs_json.read_text(encoding="utf-8"))
            self.assertEqual(len(data["briefs"]), 1)
            self.assertEqual(data["briefs"][0]["views"]["archive"]["headline"], "new")  # headline 在主视图内


class TestMultiModel(unittest.TestCase):
    @staticmethod
    def _llm(asset, direction, conf):
        return LLMBrief(hypotheses=[{"asset": asset, "direction": direction, "horizon": "h_5d",
                                     "confidence": conf, "if_then": "x", "invalidation": "z"}])

    def test_views_keyed_by_model_order_preserved(self):
        a = LLMBrief(headline="A", facts=["甲"])
        b = LLMBrief(headline="B", facts=["乙"])
        br = render.build_brief("2026-06-18", {"deepseek": a, "anthropic": b}, [], [], [])
        self.assertEqual(br.models, ["deepseek", "anthropic"])  # 顺序保留,[0]=主
        self.assertEqual(br.views["deepseek"].headline, "A")
        self.assertEqual(br.views["anthropic"].headline, "B")

    def test_consensus_majority_and_confidence(self):
        # 3 模型对 NASDAQCOM:down/down/up → 多数 down(2/3),均值信心取 down 那批 (0.6+0.4)/2
        views = {"m1": self._llm("NASDAQCOM", "down", 0.6), "m2": self._llm("NASDAQCOM", "down", 0.4),
                 "m3": self._llm("NASDAQCOM", "up", 0.9)}
        c = next(x for x in render.build_brief("2026-06-18", views, [], [], []).consensus if x.asset == "NASDAQCOM")
        self.assertEqual(c.direction.value, "down")
        self.assertEqual((c.n, c.agree), (3, 2))
        self.assertEqual(c.votes, {"up": 1, "down": 2, "flat": 0})
        self.assertAlmostEqual(c.mean_confidence, 0.5)

    def test_consensus_tie_is_flat(self):
        views = {"m1": self._llm("NASDAQCOM", "up", 0.7), "m2": self._llm("NASDAQCOM", "down", 0.7)}
        c = next(x for x in render.build_brief("2026-06-18", views, [], [], []).consensus if x.asset == "NASDAQCOM")
        self.assertEqual(c.direction.value, "flat")  # 平票 = 分歧
        self.assertEqual(c.agree, 0)

    def test_single_model_has_no_consensus(self):
        br = render.build_brief("2026-06-18", {"deepseek": self._llm("NASDAQCOM", "down", 0.6)}, [], [], [])
        self.assertEqual(br.consensus, [])


class TestMarkdown(unittest.TestCase):
    def test_markdown_smoke(self):
        llm = LLMBrief(headline="H", facts=["事实1"], interpretation=["判断1"])
        br = render.build_brief("2026-06-18", {"deepseek": llm}, [], [], [])
        md = render.render_markdown(br, macro=[{"label": "失业率", "value": 4.3, "obs_date": "2026-05-01"}])
        self.assertIn("每日宏观简报 · 2026-06-18", md)
        self.assertIn("事实 1", md)  # normalize_text 在中文与数字间加空格
        self.assertIn("失业率", md)
        self.assertIn("不构成投资建议", md)


if __name__ == "__main__":
    unittest.main()
