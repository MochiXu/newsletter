"""store:parquet latest 往返 + history 归档。"""

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from newsletter.config import Paths
from newsletter.store import RawStore


def _df(val):
    return pd.DataFrame({
        "date": ["2026-06-12", "2026-06-13"],
        "series_id": ["DGS10", "DGS10"],
        "value": [4.40, val],
        "source": ["fred", "fred"],
    })


class TestRawStore(unittest.TestCase):
    def test_roundtrip_and_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            store = RawStore(Paths(Path(d)))
            self.assertTrue(store.read_latest().empty)  # 初始为空
            store.write_snapshot(_df(4.48), pull_date="2026-06-18")
            back = store.read_latest()
            self.assertEqual(len(back), 2)
            self.assertEqual(store.latest_pull_date(), "2026-06-18")

    def test_history_archive_on_second_write(self):
        with tempfile.TemporaryDirectory() as d:
            paths = Paths(Path(d))
            store = RawStore(paths)
            store.write_snapshot(_df(4.48), pull_date="2026-06-18")  # 首次:无归档
            self.assertEqual(list(paths.raw_history.glob("*.parquet")), [])
            store.write_snapshot(_df(4.50), pull_date="2026-06-19")  # 次日:归档前一份
            archived = [p.name for p in paths.raw_history.glob("*.parquet")]
            self.assertEqual(archived, ["series-2026-06-18.parquet"])
            # 归档内容是旧值,latest 是新值
            self.assertEqual(pd.read_parquet(paths.raw_history / "series-2026-06-18.parquet")["value"].iloc[-1], 4.48)
            self.assertEqual(store.read_latest()["value"].iloc[-1], 4.50)

    def test_missing_columns_raises(self):
        with tempfile.TemporaryDirectory() as d:
            store = RawStore(Paths(Path(d)))
            with self.assertRaises(ValueError):
                store.write_snapshot(pd.DataFrame({"date": ["x"], "value": [1.0]}), "2026-06-18")

    def test_features_snapshot(self):
        with tempfile.TemporaryDirectory() as d:
            store = RawStore(Paths(Path(d)))
            store.write_features("2026-06-18", pd.DataFrame([{"date": "2026-06-18", "SP500_ret_20": 0.01}]))
            got = store.read_features("2026-06-18")
            self.assertIsNotNone(got)
            self.assertAlmostEqual(got["SP500_ret_20"].iloc[0], 0.01)


if __name__ == "__main__":
    unittest.main()
