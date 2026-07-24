from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from amazon_market_spy.sources import read_sources


class SourceTests(unittest.TestCase):
    def test_read_sources_filters_inactive_and_sorts_by_priority(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sources.csv"
            path.write_text(
                "\n".join(
                    [
                        "source_name,source_type,category,url,priority,active",
                        "B,seller,Mugs,https://example.com/b,2,yes",
                        "A,seller,Mugs,https://example.com/a,1,true",
                        "C,seller,Mugs,https://example.com/c,3,no",
                    ]
                ),
                encoding="utf-8",
            )

            sources = read_sources(path)

        self.assertEqual([source.source_name for source in sources], ["A", "B"])
        self.assertTrue(all(source.active for source in sources))

    def test_read_sources_normalizes_rank_page_types(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sources.csv"
            path.write_text(
                "\n".join(
                    [
                        "source_name,source_type,category,url,priority,active",
                        "Best,best-seller,Mugs,https://example.com/best,1,yes",
                        "New,new releases,Mugs,https://example.com/new,2,yes",
                        "Movers,movers_shakers,Mugs,https://example.com/movers,3,yes",
                    ]
                ),
                encoding="utf-8",
            )

            sources = read_sources(path)

        self.assertEqual([source.source_type for source in sources], ["best_seller", "new_release", "movers_and_shakers"])

    def test_read_sources_repairs_rank_rows_with_missing_category(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sources.csv"
            path.write_text(
                "\n".join(
                    [
                        "source_name,source_type,category,url,priority,active",
                        "Caps New Releases,new_release,https://www.amazon.com/gp/new-releases/fashion/2474996011,1,yes",
                    ]
                ),
                encoding="utf-8",
            )

            sources = read_sources(path)

        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0].source_type, "new_release")
        self.assertEqual(sources[0].category, "")
        self.assertEqual(sources[0].url, "https://www.amazon.com/gp/new-releases/fashion/2474996011")
        self.assertEqual(sources[0].priority, 1)
        self.assertTrue(sources[0].active)

    def test_read_sources_derives_seller_display_name_for_generic_labels(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sources.csv"
            path.write_text(
                "\n".join(
                    [
                        "source_name,source_type,category,url,priority,active",
                        "Competitor Store 6,seller,LASFOUR (Warrior),https://www.amazon.com/s?me=A1HHNBJES4IIQK,1,yes",
                    ]
                ),
                encoding="utf-8",
            )

            sources = read_sources(path)

        self.assertEqual(sources[0].source_name, "Competitor Store 6")
        self.assertEqual(sources[0].display_name, "LASFOUR (Warrior)")
        self.assertEqual(sources[0].seller_name, "LASFOUR (Warrior)")
        self.assertEqual(sources[0].seller_id, "A1HHNBJES4IIQK")
        self.assertEqual(sources[0].seller_url, "https://www.amazon.com/s?me=A1HHNBJES4IIQK")


if __name__ == "__main__":
    unittest.main()
