from __future__ import annotations

import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from amazon_market_spy.models import Source
from amazon_market_spy.reporting import (
    LARK_TREND_ALERT_FIELDS,
    PRODUCT_FIELDS,
    build_historical_comparison,
    build_lark_trend_alerts,
    build_niche_intelligence,
    build_rank_trends,
    build_seller_intelligence,
    build_source_trends,
    build_trend_alerts,
    compare_snapshots,
    read_csv,
    write_csv,
)


class ReportingTests(unittest.TestCase):
    def test_write_csv_preserves_existing_category_ranks_when_new_values_are_blank(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "latest_products.csv"
            first_row = {
                "date": "2026-06-16",
                "fetched_at": "2026-06-16T00:00:00+00:00",
                "source_name": "Best Sellers",
                "source_type": "best_seller",
                "page_type": "best_seller",
                "category": "Signs",
                "asin": "B0KEEP1111",
                "rank": "1",
                "title": "Ranked Sign",
                "bsr_rank": "65003",
                "bsr_category": "Home & Kitchen",
                "category_ranks_raw": "#65,003 in Home & Kitchen; #149 in Decorative Signs & Plaques",
                "primary_bsr_rank": "65003",
                "primary_bsr_category": "Home & Kitchen",
                "sub_bsr_rank": "149",
                "sub_bsr_category": "Decorative Signs & Plaques",
                "all_bsr_ranks": "#65,003 in Home & Kitchen; #149 in Decorative Signs & Plaques",
                "subcategory_rank_score": "90",
                "rank_parse_method": "detail_bullets",
                "rank_parse_confidence": "high",
            }
            blank_row = dict(first_row)
            for field in (
                "bsr_rank",
                "bsr_category",
                "category_ranks_raw",
                "primary_bsr_rank",
                "primary_bsr_category",
                "sub_bsr_rank",
                "sub_bsr_category",
                "all_bsr_ranks",
                "subcategory_rank_score",
            ):
                blank_row[field] = ""

            write_csv(path, [first_row], PRODUCT_FIELDS)
            write_csv(path, [blank_row], PRODUCT_FIELDS)
            rows = read_csv(path)

        self.assertEqual(rows[0]["bsr_rank"], "65003")
        self.assertEqual(rows[0]["primary_bsr_category"], "Home & Kitchen")
        self.assertEqual(rows[0]["sub_bsr_rank"], "149")
        self.assertEqual(rows[0]["sub_bsr_category"], "Decorative Signs & Plaques")

    def test_write_csv_does_not_preserve_legacy_category_ranks_without_parse_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "latest_products.csv"
            legacy_row = {
                "date": "2026-06-16",
                "fetched_at": "2026-06-16T00:00:00+00:00",
                "source_name": "Best Sellers",
                "source_type": "best_seller",
                "page_type": "best_seller",
                "category": "Signs",
                "asin": "B0KEEP1111",
                "rank": "1",
                "title": "Ranked Sign",
                "primary_bsr_rank": "1321",
                "primary_bsr_category": "Home & Kitchen",
                "sub_bsr_rank": "3",
                "sub_bsr_category": "Decorative Signs & Plaques",
                "category_ranks_raw": "#1,321 in Home & Kitchen; #3 in Decorative Signs & Plaques",
            }
            blank_row = dict(legacy_row)
            for field in (
                "category_ranks_raw",
                "primary_bsr_rank",
                "primary_bsr_category",
                "sub_bsr_rank",
                "sub_bsr_category",
            ):
                blank_row[field] = ""

            write_csv(path, [legacy_row], PRODUCT_FIELDS)
            write_csv(path, [blank_row], PRODUCT_FIELDS)
            rows = read_csv(path)

        self.assertEqual(rows[0]["primary_bsr_rank"], "")
        self.assertEqual(rows[0]["sub_bsr_rank"], "")
        self.assertEqual(rows[0]["category_ranks_raw"], "")

    def test_compare_snapshots_reports_rank_movement(self) -> None:
        previous = [
            {
                "fetched_at": "2026-06-10T00:00:00+00:00",
                "source_name": "Best Sellers",
                "source_type": "best_seller",
                "page_type": "best_seller",
                "category": "Mugs",
                "asin": "B0RANK1111",
                "rank": "5",
                "title": "Moving Mug",
                "price": "20.00",
            }
        ]
        current = [
            {
                "fetched_at": "2026-06-11T00:00:00+00:00",
                "source_name": "Best Sellers",
                "source_type": "best_seller",
                "page_type": "best_seller",
                "category": "Mugs",
                "asin": "B0RANK1111",
                "rank": "2",
                "title": "Moving Mug",
                "price": "20.00",
            }
        ]

        changes = compare_snapshots(previous, current, "2026-06-11T00:00:00+00:00")

        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["change_type"], "rank_changed")
        self.assertEqual(changes[0]["old_rank"], "5")
        self.assertEqual(changes[0]["new_rank"], "2")
        self.assertEqual(changes[0]["previous_rank"], "5")
        self.assertEqual(changes[0]["rank_delta"], "3")
        self.assertEqual(changes[0]["rank_direction"], "up")

    def test_build_historical_comparison_includes_display_rank_movement(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot_dir = Path(temp_dir) / "snapshots"
            previous_rows = [
                {
                    "date": "2026-06-10",
                    "fetched_at": "2026-06-10T00:00:00+00:00",
                    "source_name": "Best Sellers",
                    "source_type": "best_seller",
                    "page_type": "best_seller",
                    "category": "Mugs",
                    "asin": f"B0MOVE{index:04d}",
                    "rank": str(index),
                    "display_rank": str(index),
                    "title": f"Product {index}",
                    "product_url": f"https://www.amazon.com/dp/B0MOVE{index:04d}",
                }
                for index in range(1, 82)
            ]
            current_rows = [
                {
                    "date": "2026-06-11",
                    "fetched_at": "2026-06-11T00:00:00+00:00",
                    "source_name": "Best Sellers",
                    "source_type": "best_seller",
                    "page_type": "best_seller",
                    "category": "Mugs",
                    "asin": f"B0MOVE{index:04d}",
                    "rank": str(index),
                    "display_rank": str(index),
                    "title": f"Product {index}",
                    "product_url": f"https://www.amazon.com/dp/B0MOVE{index:04d}",
                }
                for index in range(1, 82)
            ]
            previous_rows[2]["display_rank"] = "31"
            current_rows[2]["display_rank"] = "3"
            write_csv(snapshot_dir / "2026-06-10_snapshot.csv", previous_rows, PRODUCT_FIELDS)
            write_csv(snapshot_dir / "2026-06-11_snapshot.csv", current_rows, PRODUCT_FIELDS)

            comparisons = build_historical_comparison(snapshot_dir, snapshot_dir / "2026-06-11_snapshot.csv")

        target = next(row for row in comparisons if row["asin"] == "B0MOVE0003")
        self.assertEqual(target["previous_display_rank"], "31")
        self.assertEqual(target["display_rank_change"], "28")
        self.assertEqual(target["display_rank_pct_change"], "90.32")
        self.assertEqual(target["display_rank_velocity"], "28.00")
        self.assertEqual(target["products_in_source"], "81")
        self.assertEqual(target["display_percentile"], "3.70")

    def test_build_rank_trends_across_snapshots(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot_dir = Path(temp_dir) / "snapshots"
            write_csv(
                snapshot_dir / "2026-06-01_snapshot.csv",
                [
                    {
                        "fetched_at": "2026-06-01T00:00:00+00:00",
                        "date": "2026-06-01",
                        "source_name": "Best Sellers",
                        "source_type": "best_seller",
                        "page_type": "best_seller",
                        "category": "Mugs",
                        "asin": "B0RANK1111",
                        "rank": "9",
                        "title": "Moving Mug",
                        "image_url": "https://example.com/old-mug.jpg",
                        "price": "21.00",
                        "review_count": "90",
                        "review_rating": "4.5",
                        "product_url": "https://www.amazon.com/dp/B0RANK1111",
                    }
                ],
                PRODUCT_FIELDS,
            )
            write_csv(
                snapshot_dir / "2026-06-10_snapshot.csv",
                [
                    {
                        "fetched_at": "2026-06-10T00:00:00+00:00",
                        "date": "2026-06-10",
                        "source_name": "Best Sellers",
                        "source_type": "best_seller",
                        "page_type": "best_seller",
                        "category": "Mugs",
                        "asin": "B0RANK1111",
                        "rank": "5",
                        "title": "Moving Mug",
                        "image_url": "https://example.com/mid-mug.jpg",
                        "price": "20.00",
                        "review_count": "100",
                        "review_rating": "4.6",
                        "product_url": "https://www.amazon.com/dp/B0RANK1111",
                    }
                ],
                PRODUCT_FIELDS,
            )
            write_csv(
                snapshot_dir / "2026-06-11_snapshot.csv",
                [
                    {
                        "fetched_at": "2026-06-11T00:00:00+00:00",
                        "date": "2026-06-11",
                        "source_name": "Best Sellers",
                        "source_type": "best_seller",
                        "page_type": "best_seller",
                        "category": "Mugs",
                        "asin": "B0RANK1111",
                        "rank": "2",
                        "title": "Moving Mug",
                        "image_url": "https://example.com/latest-mug.jpg",
                        "price": "19.00",
                        "review_count": "115",
                        "review_rating": "4.7",
                        "bsr_rank": "12",
                        "bsr_category": "Coffee Mugs",
                        "category_ranks_raw": "#12 in Coffee Mugs",
                        "product_url": "https://www.amazon.com/dp/B0RANK1111",
                    }
                ],
                PRODUCT_FIELDS,
            )

            trends = build_rank_trends(snapshot_dir)

        self.assertEqual(len(trends), 1)
        self.assertEqual(trends[0]["first_rank"], "9")
        self.assertEqual(trends[0]["latest_rank"], "2")
        self.assertEqual(trends[0]["image_url"], "https://example.com/latest-mug.jpg")
        self.assertEqual(trends[0]["review_count"], "115")
        self.assertEqual(trends[0]["review_rating"], "4.7")
        self.assertEqual(trends[0]["bsr_rank"], "12")
        self.assertEqual(trends[0]["bsr_category"], "Coffee Mugs")
        self.assertEqual(trends[0]["category_ranks_raw"], "#12 in Coffee Mugs")
        self.assertEqual(trends[0]["primary_bsr_rank"], "12")
        self.assertEqual(trends[0]["primary_bsr_category"], "Coffee Mugs")
        self.assertEqual(trends[0]["sub_bsr_rank"], "")
        self.assertEqual(trends[0]["subcategory_rank_score"], "")
        self.assertEqual(trends[0]["review_growth_7d"], "15")
        self.assertEqual(trends[0]["review_growth_30d"], "25")
        self.assertEqual(trends[0]["review_velocity_score"], "15")
        self.assertEqual(trends[0]["rank_change"], "7")
        self.assertEqual(trends[0]["rank_direction"], "up")
        self.assertEqual(trends[0]["days_seen"], "3")
        self.assertEqual(trends[0]["best_rank_7d"], "2")
        self.assertEqual(trends[0]["avg_rank_7d"], "3.50")
        self.assertEqual(trends[0]["appearances_7d"], "2")
        self.assertEqual(trends[0]["price_change"], "-2.00")

    def test_trends_use_source_aware_snapshot_key(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot_dir = Path(temp_dir) / "snapshots"
            write_csv(
                snapshot_dir / "2026-06-10_snapshot.csv",
                [
                    {
                        "date": "2026-06-10",
                        "fetched_at": "2026-06-10T00:00:00+00:00",
                        "source_name": "Store A",
                        "source_type": "seller",
                        "page_type": "seller",
                        "category": "Mugs",
                        "asin": "b0rank1111",
                        "rank": "20",
                        "title": "Moving Mug",
                        "product_url": "https://www.amazon.com/dp/B0RANK1111",
                    },
                    {
                        "date": "2026-06-10",
                        "fetched_at": "2026-06-10T00:00:00+00:00",
                        "source_name": "Store A",
                        "source_type": "seller",
                        "page_type": "seller",
                        "category": "Mugs",
                        "asin": "1234567890",
                        "rank": "1",
                        "title": "Bad Numeric ID",
                    },
                ],
                PRODUCT_FIELDS,
            )
            today_path = snapshot_dir / "2026-06-11_snapshot.csv"
            write_csv(
                today_path,
                [
                    {
                        "date": "2026-06-11",
                        "fetched_at": "2026-06-11T00:00:00+00:00",
                        "source_name": "Store B",
                        "source_type": "seller",
                        "page_type": "seller",
                        "category": "Signs",
                        "asin": "B0RANK1111",
                        "rank": "5",
                        "title": "Moving Mug",
                        "product_url": "https://www.amazon.com/dp/B0RANK1111",
                    },
                    {
                        "date": "2026-06-11",
                        "fetched_at": "2026-06-11T00:00:00+00:00",
                        "source_name": "Store C",
                        "source_type": "seller",
                        "page_type": "seller",
                        "category": "Duplicate",
                        "asin": "B0RANK1111",
                        "rank": "2",
                        "title": "Duplicate Product",
                        "product_url": "https://www.amazon.com/dp/B0RANK1111",
                    },
                ],
                PRODUCT_FIELDS,
            )

            trends = build_rank_trends(snapshot_dir)
            comparisons = build_historical_comparison(snapshot_dir, today_path)

        self.assertEqual(len(trends), 3)
        self.assertEqual(
            sorted(row["source_id"] for row in trends),
            [
                "seller:amazon.com:store-a",
                "seller:amazon.com:store-b",
                "seller:amazon.com:store-c",
            ],
        )
        self.assertTrue(all(row["rank_change"] == "" for row in trends))
        self.assertEqual(len(comparisons), 2)
        self.assertEqual(sorted(row["source_id"] for row in comparisons), ["seller:amazon.com:store-b", "seller:amazon.com:store-c"])
        self.assertTrue(all(row["previous_rank"] == "" for row in comparisons))
        self.assertTrue(all(row["rank_change_vs_previous_seen"] == "" for row in comparisons))

    def test_historical_comparison_only_compares_matching_source_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot_dir = Path(temp_dir) / "snapshots"
            previous_rows = [
                _source_row("B0SELLERC1", "Seller A", "seller", "Mugs", "50"),
                _source_row("B0BESTNEW1", "Mugs Best Sellers", "best_seller", "Mugs", "60"),
                _source_row("B0CATDIFF1", "Mugs Best Sellers", "best_seller", "Mugs", "70"),
                _source_row("B0SAME0001", "Seller A", "seller", "Mugs", "50"),
                _source_row("B0UNKNOWN1", "Moving Products", "movers_and_shakers", "Mugs", "90"),
            ]
            current_rows = [
                _source_row("B0SELLERC1", "Seller B", "seller", "Mugs", "5"),
                _source_row("B0BESTNEW1", "Mugs New Releases", "new_release", "Mugs", "5"),
                _source_row("B0CATDIFF1", "Signs Best Sellers", "best_seller", "Signs", "5"),
                _source_row("B0SAME0001", "Seller A", "seller", "Mugs", "20"),
                _source_row("B0UNKNOWN1", "Seller A", "seller", "Mugs", "5"),
            ]
            write_csv(snapshot_dir / "2026-06-10_snapshot.csv", previous_rows, PRODUCT_FIELDS)
            today_path = snapshot_dir / "2026-06-11_snapshot.csv"
            write_csv(today_path, current_rows, PRODUCT_FIELDS)

            comparisons = build_historical_comparison(snapshot_dir, today_path)

        by_asin = {row["asin"]: row for row in comparisons}
        self.assertEqual(by_asin["B0SELLERC1"]["previous_rank"], "")
        self.assertEqual(by_asin["B0BESTNEW1"]["previous_rank"], "")
        self.assertEqual(by_asin["B0CATDIFF1"]["previous_rank"], "")
        self.assertEqual(by_asin["B0UNKNOWN1"]["previous_rank"], "")
        self.assertEqual(by_asin["B0SAME0001"]["previous_rank"], "50")
        self.assertEqual(by_asin["B0SAME0001"]["rank_change_vs_previous_seen"], "30")
        self.assertEqual(by_asin["B0SAME0001"]["previous_source_rank"], "50")
        self.assertEqual(by_asin["B0SAME0001"]["source_rank_change"], "30")
        self.assertEqual(by_asin["B0BESTNEW1"]["source_type"], "category_new_release")
        self.assertEqual(by_asin["B0CATDIFF1"]["source_id"], "category_best_seller:amazon.com:signs")

    def test_duplicate_same_source_rows_consolidate_to_best_valid_rank(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot_dir = Path(temp_dir) / "snapshots"
            write_csv(
                snapshot_dir / "2026-06-10_snapshot.csv",
                [_source_row("B0DUPERANK", "Seller A", "seller", "Mugs", "20")],
                PRODUCT_FIELDS,
            )
            today_path = snapshot_dir / "2026-06-11_snapshot.csv"
            write_csv(
                today_path,
                [
                    _source_row("B0DUPERANK", "Seller A", "seller", "Mugs", "9", title="Duplicate Worse Rank"),
                    _source_row("B0DUPERANK", "Seller A", "seller", "Mugs", "4", title="Duplicate Better Rank"),
                ],
                PRODUCT_FIELDS,
            )

            comparisons = build_historical_comparison(snapshot_dir, today_path)

        self.assertEqual(len(comparisons), 1)
        self.assertEqual(comparisons[0]["today_rank"], "4")
        self.assertEqual(comparisons[0]["source_rank"], "4")
        self.assertEqual(comparisons[0]["source_duplicate_count"], "2")
        self.assertEqual(comparisons[0]["rank_change_vs_previous_seen"], "16")
        self.assertEqual(comparisons[0]["title"], "Duplicate Better Rank")

    def test_invalid_rank_does_not_enter_history_movement(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot_dir = Path(temp_dir) / "snapshots"
            write_csv(
                snapshot_dir / "2026-06-10_snapshot.csv",
                [_source_row("B0ZEROCOMP", "Seller A", "seller", "Mugs", "0")],
                PRODUCT_FIELDS,
            )
            today_path = snapshot_dir / "2026-06-11_snapshot.csv"
            write_csv(
                today_path,
                [_source_row("B0ZEROCOMP", "Seller A", "seller", "Mugs", "5")],
                PRODUCT_FIELDS,
            )

            comparisons = build_historical_comparison(snapshot_dir, today_path)

        self.assertEqual(comparisons[0]["previous_rank"], "")
        self.assertEqual(comparisons[0]["rank_change_vs_previous_seen"], "")
        self.assertEqual(comparisons[0]["previous_source_rank"], "")

    def test_source_trends_include_seller_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot_dir = Path(temp_dir) / "snapshots"
            write_csv(
                snapshot_dir / "2026-06-11_snapshot.csv",
                [
                    {
                        "date": "2026-06-11",
                        "fetched_at": "2026-06-11T00:00:00+00:00",
                        "source_name": "Seller A",
                        "source_type": "seller",
                        "page_type": "seller",
                        "category": "Mugs",
                        "asin": "B0RANK1111",
                        "rank": "5",
                        "title": "Moving Mug",
                    }
                ],
                PRODUCT_FIELDS,
            )
            sources = [
                Source(
                    source_name="Seller A",
                    source_type="seller",
                    category="Mugs",
                    url="https://www.amazon.com/sp?seller=A1SELLERA",
                    priority=1,
                    active=True,
                    row_number=1,
                )
            ]

            trends = build_source_trends(snapshot_dir, sources)

        self.assertEqual(len(trends), 1)
        self.assertEqual(trends[0]["source_name"], "Seller A")
        self.assertEqual(trends[0]["seller_name"], "Seller A")
        self.assertEqual(trends[0]["seller_id"], "A1SELLERA")
        self.assertEqual(trends[0]["seller_url"], "https://www.amazon.com/sp?seller=A1SELLERA")

    def test_source_trends_coalesce_generic_and_display_seller_names(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot_dir = Path(temp_dir) / "snapshots"
            write_csv(
                snapshot_dir / "2026-06-10_snapshot.csv",
                [
                    {
                        "date": "2026-06-10",
                        "fetched_at": "2026-06-10T00:00:00+00:00",
                        "source_name": "Competitor Store 6",
                        "source_type": "seller",
                        "page_type": "seller",
                        "category": "LASFOUR (Warrior)",
                        "asin": "B0SELLA001",
                        "rank": "5",
                        "title": "Old Seller Product",
                    }
                ],
                PRODUCT_FIELDS,
            )
            write_csv(
                snapshot_dir / "2026-06-11_snapshot.csv",
                [
                    {
                        "date": "2026-06-11",
                        "fetched_at": "2026-06-11T00:00:00+00:00",
                        "source_name": "LASFOUR (Warrior)",
                        "source_type": "seller",
                        "seller_name": "LASFOUR (Warrior)",
                        "seller_id": "A1HHNBJES4IIQK",
                        "seller_url": "https://www.amazon.com/s?me=A1HHNBJES4IIQK",
                        "page_type": "seller",
                        "category": "LASFOUR (Warrior)",
                        "asin": "B0SELLA001",
                        "rank": "3",
                        "title": "Current Seller Product",
                    }
                ],
                PRODUCT_FIELDS,
            )
            sources = [
                Source(
                    source_name="Competitor Store 6",
                    source_type="seller",
                    category="LASFOUR (Warrior)",
                    url="https://www.amazon.com/s?me=A1HHNBJES4IIQK",
                    priority=1,
                    active=True,
                    row_number=1,
                    seller_name="LASFOUR (Warrior)",
                    seller_url="https://www.amazon.com/s?me=A1HHNBJES4IIQK",
                    seller_id="A1HHNBJES4IIQK",
                )
            ]

            trends = build_source_trends(snapshot_dir, sources)

        self.assertEqual(len(trends), 1)
        self.assertEqual(trends[0]["source_name"], "LASFOUR (Warrior)")
        self.assertEqual(trends[0]["seller_name"], "LASFOUR (Warrior)")
        self.assertEqual(trends[0]["seller_id"], "A1HHNBJES4IIQK")
        self.assertEqual(trends[0]["snapshots_seen"], "2")

    def test_build_historical_comparison_compares_today_to_prior_snapshots(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot_dir = Path(temp_dir) / "snapshots"
            write_csv(
                snapshot_dir / "2026-06-10_snapshot.csv",
                [
                    {
                        "date": "2026-06-10",
                        "fetched_at": "2026-06-10T00:00:00+00:00",
                        "source_name": "Best Sellers",
                        "source_type": "best_seller",
                        "page_type": "best_seller",
                        "category": "Mugs",
                        "asin": "B0RANK1111",
                        "rank": "15",
                        "title": "Moving Mug",
                        "image_url": "https://example.com/rank-old.jpg",
                        "price": "20.00",
                        "review_count": "100",
                        "review_rating": "4.6",
                        "product_url": "https://www.amazon.com/dp/B0RANK1111",
                    }
                ],
                PRODUCT_FIELDS,
            )
            for snapshot_date in ["2026-06-05", "2026-06-06", "2026-06-07", "2026-06-08"]:
                write_csv(
                    snapshot_dir / f"{snapshot_date}_snapshot.csv",
                    [
                        {
                            "date": snapshot_date,
                            "fetched_at": f"{snapshot_date}T00:00:00+00:00",
                            "source_name": "Best Sellers",
                            "source_type": "best_seller",
                            "page_type": "best_seller",
                            "category": "Mugs",
                            "asin": "B0WIN11111",
                            "rank": "25",
                            "title": "Winner Mug",
                            "image_url": "https://example.com/winner-old.jpg",
                            "price": "18.00",
                            "product_url": "https://www.amazon.com/dp/B0WIN11111",
                        }
                    ],
                    PRODUCT_FIELDS,
                )
            write_csv(
                snapshot_dir / "2026-06-09_snapshot.csv",
                [
                    {
                        "date": "2026-06-09",
                        "fetched_at": "2026-06-09T00:00:00+00:00",
                        "source_name": "Best Sellers",
                        "source_type": "best_seller",
                        "page_type": "best_seller",
                        "category": "Mugs",
                        "asin": "B0WIN11111",
                        "rank": "25",
                        "title": "Winner Mug",
                        "image_url": "https://example.com/winner-old.jpg",
                        "price": "18.00",
                        "product_url": "https://www.amazon.com/dp/B0WIN11111",
                    }
                ],
                PRODUCT_FIELDS,
            )
            write_csv(
                snapshot_dir / "2026-06-10_snapshot.csv",
                [
                    {
                        "date": "2026-06-10",
                        "fetched_at": "2026-06-10T00:00:00+00:00",
                        "source_name": "Best Sellers",
                        "source_type": "best_seller",
                        "page_type": "best_seller",
                        "category": "Mugs",
                        "asin": "B0RANK1111",
                        "rank": "15",
                        "title": "Moving Mug",
                        "image_url": "https://example.com/rank-old.jpg",
                        "price": "20.00",
                        "review_count": "100",
                        "review_rating": "4.6",
                        "product_url": "https://www.amazon.com/dp/B0RANK1111",
                    },
                    {
                        "date": "2026-06-10",
                        "fetched_at": "2026-06-10T00:00:00+00:00",
                        "source_name": "Best Sellers",
                        "source_type": "best_seller",
                        "page_type": "best_seller",
                        "category": "Mugs",
                        "asin": "B0WIN11111",
                        "rank": "22",
                        "title": "Winner Mug",
                        "image_url": "https://example.com/winner-mid.jpg",
                        "price": "18.00",
                        "product_url": "https://www.amazon.com/dp/B0WIN11111",
                    },
                    {
                        "date": "2026-06-10",
                        "fetched_at": "2026-06-10T00:00:00+00:00",
                        "source_name": "Best Sellers",
                        "source_type": "best_seller",
                        "page_type": "best_seller",
                        "category": "Mugs",
                        "asin": "B0TREND111",
                        "rank": "60",
                        "title": "Trending Mug",
                        "image_url": "https://example.com/trending-old.jpg",
                        "price": "18.00",
                        "product_url": "https://www.amazon.com/dp/B0TREND111",
                    },
                    {
                        "date": "2026-06-10",
                        "fetched_at": "2026-06-10T00:00:00+00:00",
                        "source_name": "Best Sellers",
                        "source_type": "best_seller",
                        "page_type": "best_seller",
                        "category": "Mugs",
                        "asin": "B0LOSE1111",
                        "rank": "10",
                        "title": "Losing Mug",
                        "image_url": "https://example.com/losing-old.jpg",
                        "price": "18.00",
                        "product_url": "https://www.amazon.com/dp/B0LOSE1111",
                    },
                ],
                PRODUCT_FIELDS,
            )
            today_path = snapshot_dir / "2026-06-11_snapshot.csv"
            write_csv(
                today_path,
                [
                    {
                        "date": "2026-06-11",
                        "fetched_at": "2026-06-11T00:00:00+00:00",
                        "source_name": "Best Sellers",
                        "source_type": "best_seller",
                        "page_type": "best_seller",
                        "category": "Mugs",
                        "asin": "B0RANK1111",
                        "rank": "2",
                        "title": "Moving Mug",
                        "image_url": "https://example.com/rank-new.jpg",
                        "price": "19.00",
                        "review_count": "112",
                        "review_rating": "4.7",
                        "bsr_rank": "12",
                        "bsr_category": "Handmade Products",
                        "category_ranks_raw": "#12 in Handmade Products; #4 in Coffee Mugs",
                        "product_url": "https://www.amazon.com/dp/B0RANK1111",
                    },
                    {
                        "date": "2026-06-11",
                        "fetched_at": "2026-06-11T00:00:00+00:00",
                        "source_name": "Best Sellers",
                        "source_type": "best_seller",
                        "page_type": "best_seller",
                        "category": "Mugs",
                        "asin": "B0NEW11111",
                        "rank": "10",
                        "title": "New Mug",
                        "image_url": "https://example.com/new.jpg",
                        "price": "15.00",
                        "product_url": "https://www.amazon.com/dp/B0NEW11111",
                    },
                    {
                        "date": "2026-06-11",
                        "fetched_at": "2026-06-11T00:00:00+00:00",
                        "source_name": "Best Sellers",
                        "source_type": "best_seller",
                        "page_type": "best_seller",
                        "category": "Mugs",
                        "asin": "B0WIN11111",
                        "rank": "8",
                        "title": "Winner Mug",
                        "image_url": "https://example.com/winner-new.jpg",
                        "price": "18.00",
                        "product_url": "https://www.amazon.com/dp/B0WIN11111",
                    },
                    {
                        "date": "2026-06-11",
                        "fetched_at": "2026-06-11T00:00:00+00:00",
                        "source_name": "Best Sellers",
                        "source_type": "best_seller",
                        "page_type": "best_seller",
                        "category": "Mugs",
                        "asin": "B0TREND111",
                        "rank": "30",
                        "title": "Trending Mug",
                        "image_url": "https://example.com/trending-new.jpg",
                        "price": "18.00",
                        "product_url": "https://www.amazon.com/dp/B0TREND111",
                    },
                    {
                        "date": "2026-06-11",
                        "fetched_at": "2026-06-11T00:00:00+00:00",
                        "source_name": "Best Sellers",
                        "source_type": "best_seller",
                        "page_type": "best_seller",
                        "category": "Mugs",
                        "asin": "B0LOSE1111",
                        "rank": "50",
                        "title": "Losing Mug",
                        "image_url": "https://example.com/losing-new.jpg",
                        "price": "18.00",
                        "product_url": "https://www.amazon.com/dp/B0LOSE1111",
                    },
                ],
                PRODUCT_FIELDS,
            )

            comparisons = build_historical_comparison(snapshot_dir, today_path)

        by_asin = {row["asin"]: row for row in comparisons}
        self.assertEqual(by_asin["B0RANK1111"]["previous_latest_rank"], "15")
        self.assertEqual(by_asin["B0RANK1111"]["previous_rank"], "15")
        self.assertEqual(by_asin["B0RANK1111"]["rank_change_vs_previous_seen"], "13")
        self.assertEqual(by_asin["B0RANK1111"]["historical_status"], "improved_vs_previous_seen")
        self.assertEqual(by_asin["B0RANK1111"]["classification"], "new_win;rising")
        self.assertEqual(by_asin["B0RANK1111"]["opportunity_score"], "56")
        self.assertEqual(by_asin["B0RANK1111"]["pod_component"], "0")
        self.assertEqual(by_asin["B0RANK1111"]["momentum_component"], "19")
        self.assertEqual(by_asin["B0RANK1111"]["market_component"], "19")
        self.assertEqual(by_asin["B0RANK1111"]["competition_component"], "8")
        self.assertEqual(by_asin["B0RANK1111"]["niche_component"], "15")
        self.assertEqual(by_asin["B0RANK1111"]["image_url"], "https://example.com/rank-new.jpg")
        self.assertEqual(by_asin["B0RANK1111"]["review_count"], "112")
        self.assertEqual(by_asin["B0RANK1111"]["review_rating"], "4.7")
        self.assertEqual(by_asin["B0RANK1111"]["bsr_rank"], "12")
        self.assertEqual(by_asin["B0RANK1111"]["bsr_category"], "Handmade Products")
        self.assertEqual(by_asin["B0RANK1111"]["category_ranks_raw"], "#12 in Handmade Products; #4 in Coffee Mugs")
        self.assertEqual(by_asin["B0RANK1111"]["primary_bsr_rank"], "12")
        self.assertEqual(by_asin["B0RANK1111"]["primary_bsr_category"], "Handmade Products")
        self.assertEqual(by_asin["B0RANK1111"]["sub_bsr_rank"], "4")
        self.assertEqual(by_asin["B0RANK1111"]["sub_bsr_category"], "Coffee Mugs")
        self.assertEqual(by_asin["B0RANK1111"]["subcategory_rank_score"], "100")
        self.assertEqual(by_asin["B0RANK1111"]["review_growth_7d"], "12")
        self.assertEqual(by_asin["B0RANK1111"]["review_growth_30d"], "12")
        self.assertEqual(by_asin["B0RANK1111"]["review_velocity_score"], "15")
        self.assertEqual(by_asin["B0RANK1111"]["days_seen"], "2")
        self.assertEqual(by_asin["B0RANK1111"]["best_rank_7d"], "2")
        self.assertEqual(by_asin["B0RANK1111"]["avg_rank_7d"], "8.50")
        self.assertEqual(by_asin["B0RANK1111"]["appearances_7d"], "2")
        self.assertEqual(by_asin["B0RANK1111"]["price_change_vs_previous_seen"], "-1.00")
        self.assertEqual(by_asin["B0NEW11111"]["historical_status"], "new_vs_history")
        self.assertEqual(by_asin["B0NEW11111"]["classification"], "")
        self.assertEqual(by_asin["B0NEW11111"]["opportunity_score"], "40")
        self.assertEqual(by_asin["B0NEW11111"]["days_seen"], "1")
        self.assertEqual(by_asin["B0NEW11111"]["best_rank_7d"], "10")
        self.assertEqual(by_asin["B0NEW11111"]["avg_rank_7d"], "10.00")
        self.assertEqual(by_asin["B0NEW11111"]["appearances_7d"], "1")
        self.assertEqual(by_asin["B0WIN11111"]["classification"], "new_win;rising;winner")
        self.assertEqual(by_asin["B0WIN11111"]["opportunity_score"], "61")
        self.assertEqual(by_asin["B0TREND111"]["classification"], "rising")
        self.assertEqual(by_asin["B0TREND111"]["opportunity_score"], "44")
        self.assertEqual(by_asin["B0LOSE1111"]["classification"], "declining")
        self.assertEqual(by_asin["B0LOSE1111"]["opportunity_score"], "0")

        alerts = build_trend_alerts(comparisons)
        self.assertEqual(
            [row["asin"] for row in alerts],
            ["B0WIN11111", "B0RANK1111", "B0TREND111", "B0LOSE1111"],
        )

        lark_alerts = build_lark_trend_alerts(comparisons, include_non_pod=True)
        self.assertEqual(
            [row["asin"] for row in lark_alerts],
            ["B0WIN11111", "B0RANK1111", "B0TREND111"],
        )
        self.assertEqual(list(lark_alerts[0].keys()), LARK_TREND_ALERT_FIELDS)
        rank_alert = lark_alerts[1]
        self.assertEqual(rank_alert["image_url"], "https://example.com/rank-new.jpg")
        self.assertEqual(rank_alert["local_image_path"], "")
        self.assertEqual(rank_alert["bsr_rank"], "12")
        self.assertEqual(rank_alert["bsr_category"], "Handmade Products")
        self.assertEqual(rank_alert["category_ranks_raw"], "#12 in Handmade Products; #4 in Coffee Mugs")
        self.assertEqual(rank_alert["primary_bsr_rank"], "12")
        self.assertEqual(rank_alert["sub_bsr_rank"], "4")
        self.assertEqual(rank_alert["subcategory_rank_score"], "100")
        self.assertEqual(rank_alert["review_count"], "112")
        self.assertEqual(rank_alert["review_rating"], "4.7")
        self.assertEqual(rank_alert["review_growth_7d"], "12")
        self.assertEqual(rank_alert["review_growth_30d"], "12")
        self.assertEqual(rank_alert["review_velocity_score"], "15")
        self.assertEqual(rank_alert["pod_component"], "0")
        self.assertEqual(rank_alert["momentum_component"], "19")
        self.assertEqual(rank_alert["market_component"], "19")
        self.assertEqual(rank_alert["competition_component"], "8")
        self.assertEqual(rank_alert["niche_component"], "15")
        self.assertEqual(rank_alert["alert_type"], "new_win")
        self.assertEqual(rank_alert["priority"], "Low")
        self.assertEqual(rank_alert["rank_change"], "13")
        self.assertEqual(rank_alert["rank_direction"], "up")
        self.assertEqual(rank_alert["first_seen"], "2026-06-10")
        self.assertEqual(rank_alert["suggested_action"], "Research immediately")
        self.assertEqual(rank_alert["status"], "New")
        self.assertEqual(rank_alert["owner"], "")
        self.assertEqual(rank_alert["note"], "")
        self.assertEqual(lark_alerts[2]["alert_type"], "rising")
        self.assertEqual(lark_alerts[2]["suggested_action"], "Watch 2-3 days")

    def test_build_lark_trend_alerts_limits_to_top_100(self) -> None:
        rows = [
            {
                "date": "2026-06-11",
                "classification": "",
                "opportunity_score": "60",
                "image_url": f"https://example.com/limited-{i}.jpg",
                "asin": f"B0LIM{i:05d}",
                "title": f"Limited Product {i}",
                "source_name": "Best Sellers",
                "source_type": "best_seller",
                "category": "Mugs",
                "today_rank": str(i),
                "previous_rank": str(i + 10),
                "rank_change_vs_previous_seen": "10",
                "rank_direction_vs_previous_seen": "up",
                "first_seen_date": "2026-06-11",
                "days_seen": "1",
                "product_url": f"https://www.amazon.com/dp/B0LIM{i:05d}" if i != 1 else "",
            }
            for i in range(1, 103)
        ]

        lark_alerts = build_lark_trend_alerts(rows, include_non_pod=True)

        self.assertEqual(len(lark_alerts), 100)
        self.assertEqual(lark_alerts[0]["asin"], "B0LIM00001")
        self.assertEqual(lark_alerts[0]["product_url"], "https://www.amazon.com/dp/B0LIM00001")
        self.assertEqual(lark_alerts[-1]["asin"], "B0LIM00100")

    def test_historical_comparison_uses_subcategory_rank_score_in_opportunity_score(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot_dir = Path(temp_dir) / "snapshots"
            today_path = snapshot_dir / "2026-06-16_snapshot.csv"
            write_csv(
                today_path,
                [
                    {
                        "date": "2026-06-16",
                        "fetched_at": "2026-06-16T00:00:00+00:00",
                        "source_name": "Best Sellers",
                        "source_type": "best_seller",
                        "page_type": "best_seller",
                        "category": "Signs",
                        "asin": "B0SUBCAT01",
                        "rank": "45",
                        "title": "Custom Decorative Sign",
                        "category_ranks_raw": "#65,003 in Home & Kitchen; #149 in Decorative Signs & Plaques",
                        "product_url": "https://www.amazon.com/dp/B0SUBCAT01",
                    }
                ],
                PRODUCT_FIELDS,
            )

            comparisons = build_historical_comparison(snapshot_dir, today_path)

        self.assertEqual(comparisons[0]["sub_bsr_rank"], "149")
        self.assertEqual(comparisons[0]["subcategory_rank_score"], "90")
        self.assertEqual(comparisons[0]["opportunity_score"], "60")
        self.assertEqual(comparisons[0]["pod_component"], "16")
        self.assertEqual(comparisons[0]["momentum_component"], "12")
        self.assertEqual(comparisons[0]["market_component"], "11")
        self.assertEqual(comparisons[0]["competition_component"], "0")
        self.assertEqual(comparisons[0]["niche_component"], "15")

    def test_research_scores_follow_display_order_and_subcategory_rank_patterns(self) -> None:
        cases = [
            {
                "name": "proven winner",
                "asin": "B0PROVEN01",
                "title": "Printed Quote Mug",
                "display": [3, 2, 2, 3],
                "rank": [25, 20, 18, 19],
                "production_model": "pod",
            },
            {
                "name": "fast mover",
                "asin": "B0FASTMV01",
                "title": "Graphic Tee Printed Shirt",
                "display": [40, 20, 9, 4],
                "rank": [500, 300, 140, 60],
                "production_model": "pod",
            },
            {
                "name": "early opportunity",
                "asin": "B0EARLYO01",
                "title": "UV Printed Metal Sign",
                "display": [70, 30, 12],
                "rank": [900, 400, 180],
                "production_model": "pod",
            },
            {
                "name": "declining product",
                "asin": "B0DECLIN01",
                "title": "Printed Pillow Cover",
                "display": [3, 6, 15, 28],
                "rank": [20, 40, 95, 180],
                "production_model": "pod",
            },
            {
                "name": "stable but weak",
                "asin": "B0WEAK0001",
                "title": "Printed Garden Flag",
                "display": [70, 72, 71, 69],
                "rank": [800, 820, 810, 790],
                "production_model": "pod",
            },
            {
                "name": "one-day spike",
                "asin": "B0SPIKE001",
                "title": "Personalized Coffee Mug",
                "display": [80, 4],
                "rank": [900, 90],
                "production_model": "pod",
            },
            {
                "name": "retail winner",
                "asin": "B0RETAIL01",
                "title": "Hallmark Keepsake Ornament",
                "display": [2, 2, 1],
                "rank": [15, 12, 10],
                "production_model": "non_pod",
            },
        ]

        rows = {case["name"]: _build_scored_history_case(**case) for case in cases}

        proven = rows["proven winner"]
        self.assertGreaterEqual(_score_int(proven, "validation_score"), 80)
        self.assertGreaterEqual(_score_int(proven, "stability_score"), 80)
        self.assertGreaterEqual(_score_int(proven, "momentum_score"), 45)
        self.assertLess(_score_int(proven, "momentum_score"), 75)
        self.assertEqual(proven["research_segment"], "Proven Winner")

        fast = rows["fast mover"]
        self.assertGreaterEqual(_score_int(fast, "momentum_score"), 85)
        self.assertGreaterEqual(_score_int(fast, "validation_score"), 65)
        self.assertLess(_score_int(fast, "stability_score"), 80)
        self.assertEqual(fast["research_segment"], "Fast Mover")

        early = rows["early opportunity"]
        self.assertGreaterEqual(_score_int(early, "momentum_score"), 85)
        self.assertGreaterEqual(_score_int(early, "validation_score"), 55)
        self.assertGreaterEqual(_score_int(early, "freshness_score"), 80)
        self.assertGreaterEqual(_score_int(early, "opportunity_score"), 80)
        self.assertEqual(early["research_segment"], "Early Opportunity")

        declining = rows["declining product"]
        self.assertLessEqual(_score_int(declining, "momentum_score"), 35)
        self.assertEqual(declining["research_segment"], "Declining")

        weak = rows["stable but weak"]
        self.assertLess(_score_int(weak, "validation_score"), 55)
        self.assertGreaterEqual(_score_int(weak, "stability_score"), 80)
        self.assertNotEqual(weak["research_segment"], "Proven Winner")

        spike = rows["one-day spike"]
        self.assertGreaterEqual(_score_int(spike, "momentum_score"), 80)
        self.assertLess(_score_int(spike, "momentum_confidence"), 50)
        self.assertEqual(spike["research_segment"], "Watchlist")

        retail = rows["retail winner"]
        self.assertGreaterEqual(_score_int(retail, "validation_score"), 80)
        self.assertGreaterEqual(_score_int(retail, "stability_score"), 80)
        self.assertLess(_score_int(retail, "opportunity_score"), 40)
        self.assertNotEqual(retail["research_segment"], "Early Opportunity")

    def test_build_lark_trend_alerts_filters_non_pod_by_default(self) -> None:
        rows = [
            {
                "date": "2026-06-11",
                "classification": "",
                "opportunity_score": "90",
                "asin": "B0PHYS1111",
                "title": "Stanley Stainless Steel Vacuum Insulated Tumbler with Lid and Straw",
                "source_name": "Best Sellers",
                "source_type": "best_seller",
                "category": "Tumblers",
                "today_rank": "1",
                "days_seen": "1",
            },
            {
                "date": "2026-06-11",
                "classification": "",
                "opportunity_score": "60",
                "asin": "B0CUST1111",
                "title": "Personalized Dog Mom Coffee Mug Custom Name",
                "source_name": "Best Sellers",
                "source_type": "best_seller",
                "category": "Mugs",
                "today_rank": "2",
                "days_seen": "1",
            },
        ]

        lark_alerts = build_lark_trend_alerts(rows)

        self.assertEqual([row["asin"] for row in lark_alerts], ["B0CUST1111"])
        self.assertEqual(lark_alerts[0]["is_pod"], "yes")

    def test_build_lark_trend_alerts_adds_seller_metadata_for_seller_sources(self) -> None:
        rows = [
            {
                "date": "2026-06-11",
                "classification": "",
                "opportunity_score": "60",
                "asin": "B0SELLA001",
                "title": "Seller Product",
                "source_name": "Seller A",
                "source_type": "seller",
                "category": "Mugs",
                "today_rank": "1",
                "first_seen_date": "2026-06-11",
                "days_seen": "1",
            },
            {
                "date": "2026-06-11",
                "classification": "",
                "opportunity_score": "60",
                "asin": "B0BESTA001",
                "title": "Best Seller Product",
                "source_name": "Best Sellers",
                "source_type": "best_seller",
                "category": "Mugs",
                "today_rank": "2",
                "first_seen_date": "2026-06-11",
                "days_seen": "1",
            },
        ]
        sources = [
            Source(
                source_name="Seller A",
                source_type="seller",
                category="Mugs",
                url="https://www.amazon.com/s?me=A1SELLERA",
                priority=1,
                active=True,
                row_number=1,
            ),
            Source(
                source_name="Best Sellers",
                source_type="best_seller",
                category="Mugs",
                url="https://www.amazon.com/Best-Sellers-Kitchen/zgbs/kitchen",
                priority=1,
                active=True,
                row_number=2,
            ),
        ]

        lark_alerts = build_lark_trend_alerts(rows, source_metadata=sources, include_non_pod=True)

        self.assertEqual(lark_alerts[0]["seller_name"], "Seller A")
        self.assertEqual(lark_alerts[0]["seller_id"], "A1SELLERA")
        self.assertEqual(lark_alerts[0]["seller_url"], "https://www.amazon.com/s?me=A1SELLERA")
        self.assertEqual(lark_alerts[1]["seller_name"], "")
        self.assertEqual(lark_alerts[1]["seller_id"], "")
        self.assertEqual(lark_alerts[1]["seller_url"], "")

    def test_build_niche_intelligence_summarizes_pod_niches(self) -> None:
        rows = [
            {
                "date": "2026-06-16",
                "source_name": "Best Sellers",
                "source_type": "best_seller",
                "seller_name": "Seller A",
                "asin": "B0NICHE001",
                "title": "Dog Mom Custom Shirt",
                "classification": "new_win;rising",
                "opportunity_score": "90",
                "today_rank": "2",
                "rank_change_vs_previous_seen": "20",
                "display_rank": "3",
                "previous_display_rank": "31",
                "display_rank_change": "28",
                "display_rank_velocity": "28.00",
                "display_percentile": "3.70",
                "bsr_rank": "65003",
                "primary_bsr_rank": "65003",
                "primary_bsr_category": "Home & Kitchen",
                "sub_bsr_rank": "149",
                "sub_bsr_category": "Decorative Signs & Plaques",
                "all_bsr_ranks": "#65,003 in Home & Kitchen; #149 in Decorative Signs & Plaques",
                "subcategory_rank_score": "90",
                "review_count": "120",
                "review_rating": "4.8",
                "review_growth_7d": "8",
                "product_url": "https://www.amazon.com/dp/B0NICHE001",
                "image_url": "https://example.com/dog-mom.jpg",
            },
            {
                "date": "2026-06-16",
                "source_name": "Best Sellers",
                "source_type": "best_seller",
                "seller_name": "Seller B",
                "asin": "B0NICHE002",
                "title": "Stanley Stainless Steel Mug",
                "classification": "new_win",
                "opportunity_score": "100",
                "today_rank": "1",
                "is_pod": "no",
                "pod_type": "physical_brand_product",
                "pod_score": "-50",
                "pod_reason": "physical brand",
            },
        ]

        niches = build_niche_intelligence(rows)
        by_niche = {row["niche"]: row for row in niches}

        self.assertIn("Dog Mom", by_niche)
        self.assertNotIn("Personalized Mug", by_niche)
        self.assertEqual(by_niche["Dog Mom"]["niche_group"], "pet")
        self.assertEqual(by_niche["Dog Mom"]["products_tracked"], "1")
        self.assertEqual(by_niche["Dog Mom"]["pod_products"], "1")
        self.assertEqual(by_niche["Dog Mom"]["opportunities"], "1")
        self.assertEqual(by_niche["Dog Mom"]["new_wins"], "1")
        self.assertEqual(by_niche["Dog Mom"]["rising_products"], "1")
        self.assertEqual(by_niche["Dog Mom"]["best_rank"], "2")
        self.assertEqual(by_niche["Dog Mom"]["best_bsr_rank"], "65003")
        self.assertEqual(by_niche["Dog Mom"]["best_subcategory_rank"], "149")
        self.assertEqual(by_niche["Dog Mom"]["best_subcategory_product"], "Dog Mom Custom Shirt")
        self.assertEqual(by_niche["Dog Mom"]["total_review_growth"], "8")
        self.assertEqual(by_niche["Dog Mom"]["avg_review_rating"], "4.8")
        self.assertEqual(by_niche["Dog Mom"]["top_seller"], "Seller A")
        self.assertEqual(by_niche["Dog Mom"]["top_product_asin"], "B0NICHE001")
        self.assertEqual(by_niche["Dog Mom"]["top_product_title"], "Dog Mom Custom Shirt")
        self.assertEqual(by_niche["Dog Mom"]["best_mover"], "Dog Mom Custom Shirt")
        self.assertEqual(by_niche["Dog Mom"]["best_rank_change"], "28")
        self.assertEqual(by_niche["Dog Mom"]["niche_momentum_score"], "74")

    def test_build_seller_intelligence_sorts_by_momentum_score(self) -> None:
        rows = [
            {
                "source_name": "Seller A",
                "source_type": "seller",
                "asin": "B0SELLA001",
                "title": "Seller A Decorative Sign",
                "today_rank": "10",
                "rank_change_vs_previous_seen": "15",
                "classification": "new_win;rising",
                "opportunity_score": "80",
                "display_rank": "3",
                "previous_display_rank": "31",
                "display_rank_change": "28",
                "sub_bsr_rank": "149",
                "sub_bsr_category": "Decorative Signs & Plaques",
                "review_growth_7d": "12",
                "review_growth_30d": "12",
                "review_velocity_score": "15",
            },
            {
                "source_name": "Seller A",
                "source_type": "seller",
                "asin": "B0SELLA002",
                "title": "Seller A Lower Sign",
                "today_rank": "30",
                "rank_change_vs_previous_seen": "5",
                "classification": "",
                "opportunity_score": "20",
                "display_rank": "25",
                "previous_display_rank": "30",
                "display_rank_change": "5",
                "sub_bsr_rank": "400",
                "sub_bsr_category": "Decorative Signs & Plaques",
                "review_growth_7d": "0",
                "review_growth_30d": "2",
                "review_velocity_score": "5",
            },
            {
                "source_name": "Seller B",
                "source_type": "seller",
                "asin": "B0SELLB001",
                "title": "Seller B Mug",
                "today_rank": "20",
                "rank_change_vs_previous_seen": "10",
                "classification": "rising",
                "opportunity_score": "60",
                "display_rank": "2",
                "previous_display_rank": "12",
                "display_rank_change": "10",
                "sub_bsr_rank": "300",
                "sub_bsr_category": "Coffee Mugs",
                "review_growth_7d": "1",
                "review_growth_30d": "1",
                "review_velocity_score": "5",
            },
            {
                "source_name": "Seller B",
                "source_type": "seller",
                "asin": "1234567890",
                "today_rank": "1",
                "classification": "new_win",
                "opportunity_score": "100",
            },
        ]
        sources = [
            Source(
                source_name="Seller A",
                source_type="seller",
                category="Mugs",
                url="https://www.amazon.com/s?m=A1SELLERA",
                priority=1,
                active=True,
                row_number=1,
            ),
            Source(
                source_name="Seller B",
                source_type="seller",
                category="Mugs",
                url="https://www.amazon.com/s?seller=A1SELLERB",
                priority=1,
                active=True,
                row_number=2,
            ),
        ]

        sellers = build_seller_intelligence(rows, sources)

        self.assertEqual([row["seller"] for row in sellers], ["Seller A", "Seller B"])
        self.assertEqual(sellers[0]["seller_name"], "Seller A")
        self.assertEqual(sellers[0]["seller_id"], "A1SELLERA")
        self.assertEqual(sellers[0]["seller_url"], "https://www.amazon.com/s?m=A1SELLERA")
        self.assertEqual(sellers[0]["source_name"], "Seller A")
        self.assertEqual(sellers[0]["source_type"], "seller")
        self.assertEqual(sellers[0]["products_tracked"], "2")
        self.assertEqual(sellers[0]["new_wins"], "1")
        self.assertEqual(sellers[0]["rising_products"], "1")
        self.assertEqual(sellers[0]["average_rank"], "20.00")
        self.assertEqual(sellers[0]["review_growth_7d"], "12")
        self.assertEqual(sellers[0]["review_growth_30d"], "14")
        self.assertEqual(sellers[0]["review_velocity_score"], "20")
        self.assertEqual(sellers[0]["momentum_score"], "170")
        self.assertEqual(sellers[0]["best_mover"], "Seller A Decorative Sign")
        self.assertEqual(sellers[0]["best_mover_rank_change"], "28")
        self.assertEqual(sellers[0]["average_rank_improvement"], "16.50")
        self.assertEqual(sellers[0]["seller_momentum_score"], "180")
        self.assertEqual(sellers[0]["best_subcategory_rank"], "149")
        self.assertEqual(sellers[0]["best_subcategory_product"], "Seller A Decorative Sign")
        self.assertEqual(sellers[1]["products_tracked"], "1")
        self.assertEqual(sellers[1]["seller_id"], "A1SELLERB")
        self.assertEqual(sellers[1]["review_velocity_score"], "5")
        self.assertEqual(sellers[1]["best_mover"], "Seller B Mug")
        self.assertEqual(sellers[1]["best_mover_rank_change"], "10")
        self.assertEqual(sellers[1]["average_rank_improvement"], "10.00")
        self.assertEqual(sellers[1]["seller_momentum_score"], "85")
        self.assertEqual(sellers[1]["best_subcategory_rank"], "300")
        self.assertEqual(sellers[1]["best_subcategory_product"], "Seller B Mug")


def _build_scored_history_case(
    name: str,
    asin: str,
    title: str,
    display: list[int],
    rank: list[int],
    production_model: str,
) -> dict[str, str]:
    with tempfile.TemporaryDirectory() as temp_dir:
        snapshot_dir = Path(temp_dir) / "snapshots"
        start_date = date(2026, 6, 10)
        is_pod = "yes" if production_model == "pod" else "no" if production_model == "non_pod" else "maybe"
        pod_score = "88" if production_model == "pod" else "-88" if production_model == "non_pod" else "0"
        pod_confidence = "high" if production_model in {"pod", "non_pod"} else "low"
        pod_reason = "Fixture production model evidence."
        today_path = snapshot_dir / f"{start_date + timedelta(days=len(display) - 1)}_snapshot.csv"

        for index, (display_order, subcategory_rank) in enumerate(zip(display, rank, strict=True)):
            snapshot_date = start_date + timedelta(days=index)
            write_csv(
                snapshot_dir / f"{snapshot_date}_snapshot.csv",
                [
                    {
                        "date": snapshot_date.isoformat(),
                        "fetched_at": f"{snapshot_date.isoformat()}T00:00:00+00:00",
                        "source_name": "Best Sellers",
                        "source_type": "best_seller",
                        "page_type": "best_seller",
                        "category": "Mugs",
                        "asin": asin,
                        "rank": str(display_order),
                        "display_rank": str(display_order),
                        "title": title,
                        "image_url": f"https://example.com/{asin.lower()}-{index}.jpg",
                        "price": "19.99",
                        "review_count": str(60 + index),
                        "review_rating": "4.6",
                        "sub_bsr_rank": str(subcategory_rank),
                        "sub_bsr_category": "Coffee Mugs",
                        "product_url": f"https://www.amazon.com/dp/{asin}",
                        "is_pod": is_pod,
                        "production_model": production_model,
                        "production_confidence": "95",
                        "production_reason": pod_reason,
                        "pod_type": production_model,
                        "pod_score": pod_score,
                        "pod_confidence": pod_confidence,
                        "pod_reason": pod_reason,
                    }
                ],
                PRODUCT_FIELDS,
            )

        comparisons = build_historical_comparison(snapshot_dir, today_path)

    assert comparisons, f"Expected a scored comparison row for {name}"
    return comparisons[0]


def _score_int(row: dict[str, str], field: str) -> int:
    return int(float(row.get(field, "") or 0))


def _source_row(
    asin: str,
    source_name: str,
    source_type: str,
    category: str,
    rank: str,
    *,
    title: str | None = None,
) -> dict[str, str]:
    return {
        "date": "2026-06-11",
        "fetched_at": "2026-06-11T00:00:00+00:00",
        "source_name": source_name,
        "source_type": source_type,
        "page_type": source_type,
        "category": category,
        "asin": asin,
        "rank": rank,
        "display_rank": rank,
        "title": title or f"{asin} Product",
        "product_url": f"https://www.amazon.com/dp/{asin}",
    }


if __name__ == "__main__":
    unittest.main()
