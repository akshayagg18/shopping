import sys
from pathlib import Path
import unittest

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import pipeline  # noqa: E402


class CoreSemanticsTests(unittest.TestCase):
    def test_narrow_csv_dialect(self):
        self.assertEqual(pipeline.parse_fields(b'"u1",,x', 3), ("u1", "", "x"))
        self.assertIsNone(pipeline.parse_fields(b'u1,"bad,x', 3))
        self.assertIsNone(pipeline.parse_fields(b'u1,x,"partial', 3))

    def test_timestamp_rejects_leap_second_and_unicode_digits(self):
        frame = pl.DataFrame(
            {
                "ts": [
                    "2026-10-03T10:00:60Z",
                    "2026-10-03T10:00:00Z",
                    "2026-10-03T09:00:00-01:00",
                    "١٧٩١٠٢١٦٠٠٠٠٠",
                ]
            }
        ).with_columns(pipeline.timestamp_ms("ts").alias("parsed"))
        self.assertIsNone(frame[0, "parsed"])
        self.assertEqual(frame[1, "parsed"], frame[2, "parsed"])
        self.assertIsNone(frame[3, "parsed"])

    def test_union_find_uses_smallest_component_name(self):
        uf = pipeline.UnionFind()
        uf.union("u9", "u3")
        uf.union("u2", "u9")
        mapping = dict(uf.mapping().iter_rows())
        self.assertEqual(mapping, {"u9": "u2", "u3": "u2", "u2": "u2"})


if __name__ == "__main__":
    unittest.main()
