"""M1 智能平面的离线单测(纯标准库 unittest,无网络)。

运行(仓库根目录):
    PYTHONPATH=py python3 -m unittest newsletter.tests.test_brief -v
"""

import os
import tempfile
import unittest
from pathlib import Path

from newsletter import export_json
from newsletter import hypotheses as hyp
from newsletter import news as news_mod
from newsletter.brief import _merge_news
from newsletter.config import load_dotenv
from newsletter.data import Observation, load_all, load_latest
from newsletter.deliver.feishu import _sign
from newsletter.news import NewsItem
from newsletter.providers import _extract_json, select_provider
from newsletter.render import data_table, fmt, render_json, render_markdown, render_text

_PROVIDER_ENV = [
    "LLM_PROVIDER", "LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL",
    "ANTHROPIC_API_KEY", "ANTHROPIC_MODEL",
    "OPENAI_API_KEY", "OPENAI_MODEL",
    "MINIMAX_API_KEY", "DEEPSEEK_API_KEY", "MOONSHOT_API_KEY", "ZHIPU_API_KEY",
]


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
        self.assertIn("仅产出事实层", md)
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


class TestProviders(unittest.TestCase):
    def setUp(self):
        # 保存并清空所有 provider 相关 env,保证测试与宿主环境无关、彼此隔离。
        self._saved = {k: os.environ.pop(k, None) for k in _PROVIDER_ENV}

    def tearDown(self):
        for k in _PROVIDER_ENV:
            os.environ.pop(k, None)
        for k, v in self._saved.items():
            if v is not None:
                os.environ[k] = v

    def test_extract_json_plain(self):
        self.assertEqual(_extract_json('{"a": 1}'), {"a": 1})

    def test_extract_json_fenced(self):
        self.assertEqual(_extract_json('```json\n{"a": 1}\n```'), {"a": 1})

    def test_extract_json_embedded(self):
        self.assertEqual(_extract_json('好的:{"a": 1} 以上'), {"a": 1})

    def test_select_none_without_keys(self):
        self.assertIsNone(select_provider())

    def test_select_openai_preset(self):
        os.environ["LLM_PROVIDER"] = "openai"
        os.environ["OPENAI_API_KEY"] = "sk-test"
        p = select_provider()
        self.assertIsNotNone(p)
        self.assertEqual(p.name, "openai")
        self.assertEqual(p.model, "gpt-4o-mini")
        self.assertIn("openai.com", p.url)

    def test_select_generic_openai_compat(self):
        os.environ["LLM_PROVIDER"] = "openai-compat"
        os.environ["LLM_BASE_URL"] = "https://example.com/v1/chat/completions"
        os.environ["LLM_API_KEY"] = "k"
        os.environ["LLM_MODEL"] = "my-model"
        p = select_provider()
        self.assertIsNotNone(p)
        self.assertEqual(p.model, "my-model")
        self.assertEqual(p.url, "https://example.com/v1/chat/completions")

    def test_auto_detect_prefers_anthropic(self):
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant"
        os.environ["OPENAI_API_KEY"] = "sk-oai"
        p = select_provider()
        self.assertEqual(p.name, "anthropic")


class TestNews(unittest.TestCase):
    RSS = (
        b'<rss><channel>'
        b'<item><title>T1</title><link>http://a/1</link>'
        b'<description>&lt;p&gt;hello&lt;/p&gt;</description><pubDate>Mon</pubDate></item>'
        b'<item><title>T2</title><link>http://a/2</link></item>'
        b'</channel></rss>'
    )
    ATOM = (
        b'<feed xmlns="http://www.w3.org/2005/Atom">'
        b'<entry><title>AT</title><link href="http://b/1"/><summary>S</summary></entry>'
        b'</feed>'
    )

    def test_parse_rss(self):
        items = news_mod.parse_feed("Src", self.RSS)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].title, "T1")
        self.assertEqual(items[0].link, "http://a/1")
        self.assertEqual(items[0].summary, "hello")  # html 已剥离
        self.assertEqual(items[0].source, "Src")

    def test_parse_atom(self):
        items = news_mod.parse_feed("Src", self.ATOM)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "AT")
        self.assertEqual(items[0].link, "http://b/1")  # 取 href

    def test_parse_garbage(self):
        self.assertEqual(news_mod.parse_feed("Src", b"not xml"), [])

    def test_atom_link_prefers_alternate(self):
        atom = (
            b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>T</title>'
            b'<link rel="edit" href="http://api/edit/1"/>'
            b'<link rel="alternate" href="http://site/article/1"/>'
            b"<summary>s</summary></entry></feed>"
        )
        items = news_mod.parse_feed("S", atom)
        self.assertEqual(items[0].link, "http://site/article/1")  # 取文章页而非编辑端点


class TestHypotheses(unittest.TestCase):
    def test_record_new_and_dedupe(self):
        rows = []
        hyps = [{"if_then": "若 X 则 Y", "invalidation": "Z"}]
        hyp.record_new(rows, "2026-06-16", hyps)
        hyp.record_new(rows, "2026-06-16", hyps)  # 同日同假设不重复
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "open")
        self.assertEqual(rows[0]["created_date"], "2026-06-16")

    def test_record_new_idempotent_per_day(self):
        # 同日重跑:即便 LLM 措辞不同(文本去重挡不住),整天也只记一次,不累积
        rows = []
        hyp.record_new(rows, "2026-06-16", [{"if_then": "措辞 A1"}, {"if_then": "措辞 A2"}])
        self.assertEqual(len(rows), 2)
        hyp.record_new(rows, "2026-06-16", [{"if_then": "改写后的 B1"}, {"if_then": "改写后的 B2"}])
        self.assertEqual(len(rows), 2)  # 当天已记录 → 整体跳过
        # 换一天则正常追加
        hyp.record_new(rows, "2026-06-17", [{"if_then": "次日假设"}])
        self.assertEqual(len(rows), 3)

    def test_record_new_skips_non_dict(self):
        rows = []
        hyp.record_new(rows, "2026-06-16", ["oops 字符串", {"if_then": "若 X 则 Y"}, 42])
        self.assertEqual(len(rows), 1)  # 非 dict 元素被跳过,不崩溃
        self.assertEqual(rows[0]["if_then"], "若 X 则 Y")

    def test_open_items_and_apply_reviews(self):
        rows = [
            {"created_date": "2026-06-15", "if_then": "若 A 则 B", "invalidation": "C",
             "status": "open", "resolved_date": "", "verdict": "", "note": ""},
        ]
        open_hyps = hyp.open_items(rows)
        self.assertEqual(len(open_hyps), 1)
        reviews = [{"index": 1, "status": "held", "note": "数据兑现"}]
        hyp.apply_reviews(open_hyps, reviews, "2026-06-16")  # open_hyps 是 rows 的引用
        self.assertEqual(rows[0]["status"], "held")
        self.assertEqual(rows[0]["resolved_date"], "2026-06-16")
        self.assertEqual(rows[0]["note"], "数据兑现")
        self.assertEqual(hyp.open_items(rows), [])  # 已不再 open

    def test_save_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "hypotheses.csv"
            rows = []
            hyp.record_new(rows, "2026-06-16", [{"if_then": "若 X,则 Y", "invalidation": "Z"}])
            hyp.save(p, rows)
            loaded = hyp.load(p)
            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0]["if_then"], "若 X,则 Y")  # 含逗号字段正确

    def test_load_missing(self):
        self.assertEqual(hyp.load(Path("/no/such/hyp.csv")), [])


class TestRenderM2Sections(unittest.TestCase):
    def test_news_and_hyp_in_markdown(self):
        obs = [Observation("2026-06-16", "DGS10", "10Y", "2026-06-12", 4.48, "%", "FRED", "")]
        news = [{"source": "CNBC", "title": "T", "link": "L", "category": "事实",
                 "summary": "某事发生", "affected_assets": ["美债", "黄金"], "note": "利率↑"}]
        hyp_rows = [
            {"created_date": "2026-06-15", "if_then": "若 A 则 B", "status": "held",
             "resolved_date": "2026-06-16", "verdict": "held", "note": "兑现"},
            {"created_date": "2026-06-15", "if_then": "若 C 则 D", "status": "open",
             "resolved_date": "", "verdict": "", "note": ""},
        ]
        md = render_markdown("2026-06-16", obs, None, news=news, hyp_rows=hyp_rows)
        self.assertIn("今日新闻", md)
        self.assertIn("[事实]", md)
        self.assertIn("美债、黄金", md)
        self.assertIn("假设复盘", md)
        self.assertIn("已兑现", md)
        self.assertIn("待观察", md)


class TestMergeNews(unittest.TestCase):
    def _items(self):
        return [
            NewsItem("S", "Alpha", "l1", "", ""),
            NewsItem("S", "Beta", "l2", "", ""),
            NewsItem("S", "Gamma", "l3", "", ""),
        ]

    def test_merge_by_title_handles_missing_and_reorder(self):
        # LLM 漏掉 Beta,且顺序打乱(Gamma 在前)——按标题对齐不应错位
        classified = [
            {"title": "Gamma", "category": "事实", "summary": "g", "affected_assets": ["x"]},
            {"title": "Alpha", "category": "解读", "summary": "a", "affected_assets": ["y"]},
        ]
        merged = _merge_news(self._items(), classified)
        self.assertEqual(merged[0]["title"], "Alpha")
        self.assertEqual(merged[0]["category"], "解读")
        self.assertNotIn("category", merged[1])  # Beta 未匹配,保持未分类
        self.assertEqual(merged[2]["title"], "Gamma")
        self.assertEqual(merged[2]["category"], "事实")

    def test_merge_by_index_when_title_translated(self):
        # 真实 bug:LLM 把英文标题翻译成中文,标题对齐零匹配;index 对齐仍命中
        classified = [
            {"index": 1, "title": "阿尔法", "category": "事实", "summary": "a", "affected_assets": ["x"]},
            {"index": 2, "title": "贝塔", "category": "解读", "summary": "b", "affected_assets": ["y"]},
            {"index": 3, "title": "伽马", "category": "噪音", "summary": "g", "affected_assets": []},
        ]
        merged = _merge_news(self._items(), classified)
        self.assertEqual([m.get("category") for m in merged], ["事实", "解读", "噪音"])
        # 原标题保留(用 NewsItem 的,不被模型翻译值污染)
        self.assertEqual([m["title"] for m in merged], ["Alpha", "Beta", "Gamma"])

    def test_merge_index_out_of_range_ignored(self):
        # 越界 / 非法 index 不应错位或抛错,退回标题兜底
        classified = [
            {"index": 99, "title": "Beta", "category": "事实", "summary": "b", "affected_assets": []},
            {"index": "x", "title": "Alpha", "category": "解读", "summary": "a", "affected_assets": []},
        ]
        merged = _merge_news(self._items(), classified)
        self.assertEqual(merged[0]["category"], "解读")  # Alpha 经标题兜底
        self.assertEqual(merged[1]["category"], "事实")  # Beta 经标题兜底
        self.assertNotIn("category", merged[2])  # Gamma 无匹配

    def test_merge_no_classification(self):
        merged = _merge_news(self._items(), None)
        self.assertEqual(len(merged), 3)
        self.assertTrue(all("category" not in m for m in merged))


class TestDotenv(unittest.TestCase):
    def _write(self, text):
        d = tempfile.mkdtemp()
        p = Path(d) / ".env"
        p.write_text(text, encoding="utf-8")
        return p

    def test_loads_and_strips_quotes_and_export(self):
        key = "DOTENV_TEST_KEY_A"
        self.addCleanup(lambda: os.environ.pop(key, None), )
        p = self._write(f'# comment\n\n{key}="val-1"\nexport {key}2=val-2\n')
        self.addCleanup(lambda: os.environ.pop(key + "2", None))
        loaded = load_dotenv(p)
        self.assertEqual(loaded, 2)
        self.assertEqual(os.environ[key], "val-1")  # 引号被去掉
        self.assertEqual(os.environ[key + "2"], "val-2")  # export 前缀被去掉

    def test_does_not_override_existing_env(self):
        key = "DOTENV_TEST_KEY_B"
        os.environ[key] = "from-shell"
        self.addCleanup(lambda: os.environ.pop(key, None))
        p = self._write(f"{key}=from-file\n")
        load_dotenv(p)
        self.assertEqual(os.environ[key], "from-shell")  # shell 优先,文件不覆盖

    def test_missing_file_is_noop(self):
        self.assertEqual(load_dotenv(Path(tempfile.mkdtemp()) / "nope.env"), 0)


def _seven_series(run_date, vals):
    """构造某 run_date 的 7 个 series 观测;vals 顺序对应 _METRIC_SPECS。"""
    spec = [
        ("DGS10", "10Y", "%"), ("DGS2", "2Y", "%"), ("T10Y2Y", "2s10s", "%"),
        ("VIXCLS", "VIX", "index"), ("DX-Y.NYB", "DXY", "index"),
        ("DTWEXBGS", "USD Broad", "index"), ("GC=F", "Gold", "USD/oz"),
    ]
    return [
        Observation(run_date, sid, lab, run_date, v, unit, "FRED", "")
        for (sid, lab, unit), v in zip(spec, vals)
    ]


class TestLoadAll(unittest.TestCase):
    def test_load_all_keeps_every_run_date(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "obs.csv"
            p.write_text(
                "run_date,series_id,label,obs_date,value,unit,source,note\n"
                "2026-06-15,DGS10,10Y,2026-06-12,4.40,%,FRED,\n"
                "2026-06-16,DGS10,10Y,2026-06-13,4.48,%,FRED,\n"
                "2026-06-16,DGS2,2Y,2026-06-13,4.09,%,FRED,\n",
                encoding="utf-8",
            )
            self.assertEqual(len(load_all(p)), 3)  # 跨 run_date 全保留
            self.assertEqual(len(load_latest(p)), 2)  # 仍只取最新一日


class TestRenderJson(unittest.TestCase):
    def _history(self):
        day1 = _seven_series("2026-06-16", [4.40, 4.00, 0.40, 17.68, 99.66, 119.50, 4335.2])
        day2 = _seven_series("2026-06-17", [4.48, 4.09, 0.40, 16.20, 99.48, 119.51, 4364.9])
        return day1 + day2, day2

    def _brief(self):
        return {
            "headline": "鹰派暂停",
            "tone": "risk-off",
            "facts": ["10Y 4.48%"],
            "interpretation": ["重新计入更高更久"],
            "hypotheses": [{"if_then": "若 X 则 Y", "invalidation": "Z"}],
            "impact": [
                {"asset": "美元 DXY", "watch": "105 前高", "direction": "up"},
                {"asset": "黄金", "watch": "实际利率", "direction": "down"},
            ],
        }

    def test_full_contract(self):
        history, obs = self._history()
        news = [{"source": "Fed", "title": "Fed holds", "link": "L", "category": "事实",
                 "summary": "维持利率", "affected_assets": ["UST"], "direction": "down"}]
        hyp_rows = [
            {"created_date": "2026-06-16", "if_then": "若 A 则 B", "status": "held",
             "resolved_date": "2026-06-17", "verdict": "held", "note": "兑现"},
            {"created_date": "2026-06-16", "if_then": "若 C 则 D", "status": "open",
             "resolved_date": "", "verdict": "", "note": ""},
        ]
        b = render_json("2026-06-17", obs, history, self._brief(), news=news, hyp_rows=hyp_rows)

        self.assertEqual(b["date"], "2026-06-17")
        self.assertEqual(b["weekday"], "周三")
        self.assertEqual(b["time"], "07:00 CST")
        self.assertEqual(b["tone"], "risk-off")

        # 7 行指标,含广义美元一行,顺序固定
        self.assertEqual(len(b["metrics"]), 7)
        self.assertEqual(b["metrics"][0], {"key": "us10y", "label": "US10Y", "value": 4.48, "change": 0.08, "kind": "yield"})
        self.assertEqual(b["metrics"][5]["key"], "usdbroad")
        self.assertEqual(b["metrics"][5]["label"], "广义美元")
        self.assertEqual(b["metrics"][6]["key"], "gold")
        self.assertAlmostEqual(b["metrics"][3]["change"], -1.48)  # VIX 变化

        # 四层 + 方向 + 复盘 + 新闻枚举映射
        self.assertEqual(b["reads"], ["重新计入更高更久"])
        self.assertEqual(b["hypotheses"][0], {"ifThen": "若 X 则 Y", "invalidation": "Z"})
        self.assertEqual([i["dir"] for i in b["impacts"]], ["up", "down"])
        self.assertEqual(b["news"][0]["cat"], "fact")  # 事实 -> fact
        self.assertEqual(b["news"][0]["dir"], "down")
        statuses = {r["status"] for r in b["reviews"]}
        self.assertEqual(statuses, {"held", "open"})

    def test_degraded_brief_none(self):
        history, obs = self._history()
        b = render_json("2026-06-17", obs, history, None, news=None, hyp_rows=[])
        self.assertEqual(b["tone"], "neutral")  # 无 LLM 退中性
        self.assertEqual(b["headline"], "")
        self.assertEqual(b["facts"], [])
        self.assertEqual(b["hypotheses"], [])
        self.assertEqual(len(b["metrics"]), 7)  # 指标仍在(来自数据平面)
        self.assertEqual(b["news"], [])

    def test_news_unclassified_cat_none(self):
        history, obs = self._history()
        news = [{"source": "X", "title": "T", "link": ""}]  # 无 category
        b = render_json("2026-06-17", obs, history, None, news=news)
        self.assertIsNone(b["news"][0]["cat"])
        self.assertEqual(b["news"][0]["dir"], "watch")  # 缺省方向

    def test_change_zero_when_single_run_date(self):
        obs = _seven_series("2026-06-17", [4.48, 4.09, 0.40, 16.20, 99.48, 119.51, 4364.9])
        b = render_json("2026-06-17", obs, obs, self._brief())  # history == obs:无前值
        self.assertTrue(all(m["change"] == 0.0 for m in b["metrics"]))


class TestExportRebuild(unittest.TestCase):
    def test_rebuild_sorts_desc_and_renumbers_issue(self):
        import json as _json
        with tempfile.TemporaryDirectory() as d:
            bd = Path(d)
            for date in ("2026-06-17", "2026-06-04", "2026-06-16"):  # 乱序写入
                (bd / f"{date}.json").write_text(
                    _json.dumps({"date": date, "issue": 999}), encoding="utf-8"
                )
            out = export_json.rebuild(bd, model="DeepSeek")
            self.assertEqual(out["model"], "DeepSeek")
            self.assertEqual(out["generatedAt"], "2026-06-17")
            dates = [b["date"] for b in out["briefs"]]
            self.assertEqual(dates, ["2026-06-17", "2026-06-16", "2026-06-04"])  # 倒序
            issues = {b["date"]: b["issue"] for b in out["briefs"]}
            self.assertEqual(issues, {"2026-06-04": 1, "2026-06-16": 2, "2026-06-17": 3})  # 年代序


class TestDataTableEscape(unittest.TestCase):
    def test_escapes_pipe_and_newline(self):
        obs = [Observation("d", "id", "lab", "od", 1.0, "u", "FRED", "含 | 竖线\n和换行")]
        rows = [ln for ln in data_table(obs, with_note=True).splitlines() if ln.startswith("|")]
        self.assertEqual(len(rows), 3)  # 表头 + 分隔 + 1 数据行(没被换行截断)
        self.assertNotIn("\n", rows[2])
        self.assertIn("\\|", rows[2])  # 竖线已转义


if __name__ == "__main__":
    unittest.main()
