from __future__ import annotations

import contextlib
import csv
import io
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from amazon_market_spy.category_rank import CATEGORY_RANK_FIELDS, extract_bsr_from_product_page
from amazon_market_spy.cli import (
    DETAIL_CACHE_FIELDS,
    apply_category_ranks,
    apply_detail_fixes,
    build_source_scan_report_row,
    build_parser,
    build_rank_audit_rows,
    fetch_category_ranks_for_opportunities,
    fetch_detail_fixes_for_products,
    fetch_pages_with_retries,
    fetch_with_retries,
    main,
    parse_source_pages,
    repair_bsr_outputs,
    select_bsr_repair_candidates,
    source_page_limit,
    source_scroll_enabled,
    write_outputs,
)
from amazon_market_spy.fetch import FetchedPage
from amazon_market_spy.models import Source


class CliTests(unittest.TestCase):
    def write_detail_cache(self, path: Path, rows: list[dict[str, str]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=DETAIL_CACHE_FIELDS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)

    def read_detail_cache(self, path: Path) -> list[dict[str, str]]:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))

    def write_rows(self, path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)

    def complete_detail_cache_row(self, asin: str, *, primary_rank: str = "12345", sub_rank: str = "77") -> dict[str, str]:
        raw_bsr = f"Best Sellers Rank #{primary_rank} in Home & Kitchen #{sub_rank} in Mugs"
        return {
            "asin": asin,
            "title": "Personalized Family Coffee Mug Gift for Dad",
            "image_url": "https://example.com/cached.jpg",
            "primary_bsr_rank": primary_rank,
            "primary_bsr_category": "Home & Kitchen",
            "sub_bsr_rank": sub_rank,
            "sub_bsr_category": "Mugs",
            "category_ranks_raw": raw_bsr,
            "raw_bsr_block": raw_bsr,
            "review_count": "42",
            "review_rating": "4.7",
            "title_fixed": "true",
            "image_fixed": "true",
            "rank_parse_method": "product_information_item_details",
            "rank_parse_confidence": "high",
            "detail_fixed_at": "2026-06-22T00:00:00+00:00",
        }

    def test_refresh_bsr_option_parses_for_scan_and_trend(self) -> None:
        parser = build_parser()

        default_scan_args = parser.parse_args(["scan"])
        scan_args = parser.parse_args(["scan", "--refresh-bsr"])
        trend_args = parser.parse_args(["trend", "--refresh-bsr"])
        no_skip_args = parser.parse_args(["scan", "--no-skip-fixed-details"])
        refresh_all_args = parser.parse_args(["trend", "--refresh-all-details"])
        repair_args = parser.parse_args(
            [
                "repair-asin",
                "--asin",
                "B0GVJX7MWC",
                "--url",
                "https://www.amazon.com/dp/B0GVJX7MWC",
            ]
        )
        repair_bsr_args = parser.parse_args(
            [
                "repair-bsr",
                "--output",
                "output",
                "--headful",
                "--limit",
                "300",
                "--detail-timeout",
                "60",
                "--only-missing",
                "--force",
                "--min-score",
                "70",
            ]
        )

        self.assertTrue(default_scan_args.skip_fixed_details)
        self.assertFalse(default_scan_args.refresh_all_details)
        self.assertTrue(scan_args.refresh_bsr)
        self.assertTrue(trend_args.refresh_bsr)
        self.assertFalse(no_skip_args.skip_fixed_details)
        self.assertTrue(refresh_all_args.refresh_all_details)
        self.assertEqual(repair_args.asin, "B0GVJX7MWC")
        self.assertEqual(repair_bsr_args.limit, 300)
        self.assertEqual(repair_bsr_args.detail_timeout, 60)
        self.assertTrue(repair_bsr_args.headful)
        self.assertTrue(repair_bsr_args.only_missing)
        self.assertTrue(repair_bsr_args.force)
        self.assertEqual(repair_bsr_args.min_score, 70)

    def test_seller_default_scans_three_pages(self) -> None:
        args = build_parser().parse_args(["scan"])
        source = Source(
            source_name="Store",
            source_type="seller",
            category="Mugs",
            url="https://www.amazon.com/s?me=A123",
            priority=1,
            active=True,
            row_number=1,
        )

        self.assertEqual(source_page_limit(source, args), 3)

    def test_best_seller_default_scans_two_pages(self) -> None:
        args = build_parser().parse_args(["scan"])
        source = Source(
            source_name="Best Sellers",
            source_type="best_seller",
            category="Mugs",
            url="https://www.amazon.com/Best-Sellers/zgbs",
            priority=1,
            active=True,
            row_number=1,
        )

        self.assertEqual(source_page_limit(source, args), 2)

    def test_new_release_default_scans_two_pages(self) -> None:
        args = build_parser().parse_args(["scan"])
        source = Source(
            source_name="New Releases",
            source_type="new_release",
            category="Mugs",
            url="https://www.amazon.com/gp/new-releases",
            priority=1,
            active=True,
            row_number=1,
        )

        self.assertEqual(source_page_limit(source, args), 2)

    def test_scroll_is_disabled_for_ranking_paginated_sources(self) -> None:
        args = build_parser().parse_args(["scan", "--scroll"])
        seller = Source(
            source_name="Store",
            source_type="seller",
            category="Mugs",
            url="https://www.amazon.com/s?me=A123",
            priority=1,
            active=True,
            row_number=1,
        )
        best_seller = Source(
            source_name="Best Sellers",
            source_type="best_seller",
            category="Mugs",
            url="https://www.amazon.com/Best-Sellers/zgbs",
            priority=1,
            active=True,
            row_number=2,
        )
        new_release = Source(
            source_name="New Releases",
            source_type="new_release",
            category="Mugs",
            url="https://www.amazon.com/gp/new-releases",
            priority=1,
            active=True,
            row_number=3,
        )

        self.assertTrue(source_scroll_enabled(seller, args))
        self.assertFalse(source_scroll_enabled(best_seller, args))
        self.assertFalse(source_scroll_enabled(new_release, args))

    def test_fetch_with_retries_passes_scroll_options(self) -> None:
        class FakeFetcher:
            def __init__(self) -> None:
                self.kwargs: dict[str, object] = {}

            def fetch(self, url: str, **kwargs: object) -> str:
                self.kwargs = {"url": url, **kwargs}
                return "<html></html>"

        fetcher = FakeFetcher()
        source = Source(
            source_name="Store",
            source_type="seller",
            category="Mugs",
            url="https://www.amazon.com/s?me=A123",
            priority=1,
            active=True,
            row_number=1,
        )

        html = fetch_with_retries(
            fetcher=fetcher,  # type: ignore[arg-type]
            source=source,
            screenshot_path=None,
            error_screenshot_path=None,
            retries=0,
            delay=0,
            scroll=True,
            max_scrolls=4,
            scroll_wait_ms=250,
        )

        self.assertEqual(html, "<html></html>")
        self.assertEqual(fetcher.kwargs["url"], source.url)
        self.assertIs(fetcher.kwargs["scroll"], True)
        self.assertEqual(fetcher.kwargs["max_scrolls"], 4)
        self.assertEqual(fetcher.kwargs["scroll_wait_ms"], 250)

    def test_fetch_pages_with_retries_passes_pagination_options(self) -> None:
        class FakeFetcher:
            def __init__(self) -> None:
                self.kwargs: dict[str, object] = {}

            def fetch_pages(self, url: str, **kwargs: object) -> list[FetchedPage]:
                self.kwargs = {"url": url, **kwargs}
                return [FetchedPage(html="<html></html>", url=url, page_number=1)]

        fetcher = FakeFetcher()
        source = Source(
            source_name="Store",
            source_type="seller",
            category="Mugs",
            url="https://www.amazon.com/s?me=A123",
            priority=1,
            active=True,
            row_number=1,
        )

        pages = fetch_pages_with_retries(
            fetcher=fetcher,  # type: ignore[arg-type]
            source=source,
            screenshot_path=None,
            error_screenshot_path=None,
            retries=0,
            delay=0,
            scroll=True,
            max_scrolls=4,
            scroll_wait_ms=250,
            max_pages=3,
        )

        self.assertEqual(len(pages), 1)
        self.assertEqual(fetcher.kwargs["url"], source.url)
        self.assertIs(fetcher.kwargs["scroll"], True)
        self.assertEqual(fetcher.kwargs["max_scrolls"], 4)
        self.assertEqual(fetcher.kwargs["scroll_wait_ms"], 250)
        self.assertEqual(fetcher.kwargs["max_pages"], 3)

    def test_fetch_category_ranks_limits_detail_pages_and_applies_by_asin(self) -> None:
        class FakeFetcher:
            def __init__(self) -> None:
                self.urls: list[str] = []

            def fetch(self, url: str) -> str:
                self.urls.append(url)
                return """
                <div id="detailBullets_feature_div">
                  Best Sellers Rank
                  #12 in Handmade Products (See Top 100 in Handmade Products)
                  #4 in Coffee Mugs
                </div>
                """

        fetcher = FakeFetcher()
        opportunities = [
            {"asin": "B0FETCH111", "product_url": "https://www.amazon.com/dp/B0FETCH111"},
            {"asin": "B0FETCH222", "product_url": "https://www.amazon.com/dp/B0FETCH222"},
        ]

        ranks_by_asin = fetch_category_ranks_for_opportunities(
            fetcher,  # type: ignore[arg-type]
            opportunities,
            max_detail_pages=1,
            detail_delay=0,
        )
        products = [{"asin": "B0FETCH111"}, {"asin": "B0FETCH222"}]
        updated = apply_category_ranks(products, ranks_by_asin)

        self.assertEqual(fetcher.urls, ["https://www.amazon.com/dp/B0FETCH111"])
        self.assertEqual(ranks_by_asin["B0FETCH111"]["bsr_rank"], "12")
        self.assertEqual(ranks_by_asin["B0FETCH111"]["bsr_category"], "Handmade Products")
        self.assertEqual(ranks_by_asin["B0FETCH111"]["primary_bsr_rank"], "12")
        self.assertEqual(ranks_by_asin["B0FETCH111"]["sub_bsr_rank"], "4")
        self.assertEqual(ranks_by_asin["B0FETCH111"]["sub_bsr_category"], "Coffee Mugs")
        self.assertEqual(ranks_by_asin["B0FETCH111"]["subcategory_rank_score"], "100")
        self.assertEqual(updated, 1)
        self.assertEqual(
            products[0]["category_ranks_raw"],
            "Best Sellers Rank #12 in Handmade Products (See Top 100 in Handmade Products) #4 in Coffee Mugs",
        )
        self.assertEqual(products[0]["all_bsr_ranks"], "#12 in Handmade Products; #4 in Coffee Mugs")
        self.assertEqual(products[0]["rank_source_url"], "https://www.amazon.com/dp/B0FETCH111")
        self.assertEqual(products[0]["rank_page_status"], "ok")
        self.assertEqual(products[0]["rank_parse_method"], "detail_bullets")
        self.assertEqual(products[0]["rank_parse_confidence"], "high")
        self.assertEqual(products[0]["rank_parse_warning"], "")
        self.assertEqual(products[1]["bsr_rank"], "")
        self.assertEqual(products[1]["primary_bsr_rank"], "")
        self.assertEqual(products[1]["sub_bsr_rank"], "")

    def test_fetch_category_ranks_prioritizes_missing_seller_preview_products_round_robin(self) -> None:
        class FakeFetcher:
            def __init__(self) -> None:
                self.urls: list[str] = []

            def fetch(self, url: str) -> str:
                self.urls.append(url)
                return "<html></html>"

        product_rows = [
            {
                "asin": "B0SELLA002",
                "source_type": "seller",
                "seller_name": "Seller A",
                "display_order": "2",
                "product_url": "https://www.amazon.com/dp/B0SELLA002",
            },
            {
                "asin": "B0SELLB001",
                "source_type": "seller",
                "seller_name": "Seller B",
                "display_order": "1",
                "product_url": "https://www.amazon.com/dp/B0SELLB001",
            },
            {
                "asin": "B0SELLA001",
                "source_type": "seller",
                "seller_name": "Seller A",
                "display_order": "1",
                "product_url": "https://www.amazon.com/dp/B0SELLA001",
            },
        ]
        opportunities = [
            {"asin": "B0OPPORT01", "product_url": "https://www.amazon.com/dp/B0OPPORT01"},
        ]
        fetcher = FakeFetcher()

        fetch_category_ranks_for_opportunities(
            fetcher,  # type: ignore[arg-type]
            opportunities,
            max_detail_pages=2,
            detail_delay=0,
            product_rows=product_rows,
        )

        self.assertEqual(
            fetcher.urls,
            [
                "https://www.amazon.com/dp/B0SELLA001",
                "https://www.amazon.com/dp/B0SELLB001",
            ],
        )

    def test_bsr_repair_prioritizes_missing_seller_preview_before_opportunities(self) -> None:
        products = [
            {
                "asin": "B0OPPORT01",
                "source_type": "search_result",
                "display_order": "1",
            },
            {
                "asin": "B0SELLA002",
                "source_type": "seller",
                "seller_name": "Seller A",
                "display_order": "2",
            },
            {
                "asin": "B0SELLA001",
                "source_type": "seller",
                "seller_name": "Seller A",
                "display_order": "1",
            },
        ]

        selected, skipped_fresh = select_bsr_repair_candidates(
            products,
            priority_asins={"B0OPPORT01"},
            opportunity_scores={"B0OPPORT01": 99},
            limit=2,
            only_missing=True,
            today="2026-08-18",
        )

        self.assertEqual([row["asin"] for row in selected], ["B0SELLA001", "B0SELLA002"])
        self.assertEqual(skipped_fresh, 0)

    def test_rank_audit_rows_warn_for_text_scan(self) -> None:
        rows = [
            {
                "asin": "B0WARN1111",
                "title": "Warn Product",
                "product_url": "https://www.amazon.com/dp/B0WARN1111",
                "display_rank": "3",
                "source_name": "Mugs Best Sellers",
                "primary_bsr_rank": "1200",
                "primary_bsr_category": "Kitchen & Dining",
                "sub_bsr_rank": "",
                "sub_bsr_category": "",
                "category_ranks_raw": "Best Sellers Rank #1,200 in Kitchen & Dining",
                "raw_bsr_block": "Best Sellers Rank #1,200 in Kitchen & Dining",
                "rank_extracted_at": "2026-06-18T00:00:00Z",
                "rank_parse_method": "text_scan",
                "rank_parse_confidence": "medium",
            }
        ]

        audit_rows = build_rank_audit_rows(rows)

        self.assertEqual(audit_rows[0]["raw_bsr_block"], "Best Sellers Rank #1,200 in Kitchen & Dining")
        self.assertIn("text_scan fallback", audit_rows[0]["rank_parse_warning"])

    def test_fetch_category_ranks_uses_expanded_product_information_details(self) -> None:
        class FakeDetailResult:
            html = """
            <section id="product-information-accordion">
              <h2>Product information</h2>
              <div>
                <h3>Item details</h3>
                <table>
                  <tr>
                    <th>Best Sellers Rank</th>
                    <td>
                      <span>#24,164 in Kitchen & Dining</span>
                      <span>#169 in Mugs</span>
                    </td>
                  </tr>
                </table>
              </div>
            </section>
            """
            url = "https://www.amazon.com/dp/B0ACCORD11"
            status = "ok"
            error = ""
            accordion_found = True
            accordion_expanded = True
            bsr_visible_after_expand = True

        class FakeFetcher:
            def fetch_detail_page(self, url: str, timeout: int, capture_screenshot: bool) -> FakeDetailResult:
                return FakeDetailResult()

        ranks_by_asin = fetch_category_ranks_for_opportunities(
            FakeFetcher(),  # type: ignore[arg-type]
            [{"asin": "B0ACCORD11", "product_url": "https://www.amazon.com/dp/B0ACCORD11"}],
            max_detail_pages=1,
            detail_delay=0,
        )

        fields = ranks_by_asin["B0ACCORD11"]
        self.assertEqual(fields["primary_bsr_rank"], "24164")
        self.assertEqual(fields["primary_bsr_category"], "Kitchen & Dining")
        self.assertEqual(fields["sub_bsr_rank"], "169")
        self.assertEqual(fields["sub_bsr_category"], "Mugs")
        self.assertEqual(fields["rank_parse_method"], "product_information_item_details")
        self.assertEqual(fields["rank_parse_confidence"], "high")
        self.assertEqual(fields["accordion_found"], "true")
        self.assertEqual(fields["accordion_expanded"], "true")
        self.assertEqual(fields["bsr_visible_after_expand"], "true")
        self.assertEqual(fields["raw_bsr_block"], "Best Sellers Rank\n#24,164 in Kitchen & Dining\n#169 in Mugs")

    def test_scan_detail_bsr_matches_audit_for_b0gzpx6l94_product_page(self) -> None:
        product_url = "https://www.amazon.com/dp/B0GZPX6L94"
        html = """
        <html>
          <body>
            <span id="productTitle">Personalized Fist Bump Dad and Kids Name Wooden Plaque Custom Father's Day Gift</span>
            <section id="product-information-accordion">
              <h2>Product information</h2>
              <div class="accordion-panel">
                <h3>Item details</h3>
                <table>
                  <tr>
                    <th>Best Sellers Rank</th>
                    <td>
                      <span>#14,631 in Home & Kitchen</span>
                      <span>#55 in Decorative Signs & Plaques</span>
                    </td>
                  </tr>
                </table>
              </div>
            </section>
          </body>
        </html>
        """
        diagnostics = {
            "accordion_found": "true",
            "accordion_expanded": "true",
            "bsr_visible_after_expand": "true",
        }
        audit_fields = extract_bsr_from_product_page(
            html,
            source_url=product_url,
            page_status="ok",
            diagnostics=diagnostics,
        )

        class FakeDetailResult:
            status = "ok"
            error = ""
            screenshot = None
            accordion_found = True
            accordion_expanded = True
            bsr_visible_after_expand = True

            def __init__(self, page_html: str) -> None:
                self.html = page_html
                self.url = product_url

        class FakeFetcher:
            def fetch_detail_page(self, url: str, timeout: int, capture_screenshot: bool) -> FakeDetailResult:
                self.url = url
                self.timeout = timeout
                self.capture_screenshot = capture_screenshot
                return FakeDetailResult(html)

        row = {
            "asin": "B0GZPX6L94",
            "title": "Gift Idea 1",
            "image_url": "",
            "product_url": product_url,
            "primary_bsr_rank": "1321",
            "primary_bsr_category": "Home & Kitchen",
            "sub_bsr_rank": "3",
            "sub_bsr_category": "Decorative Signs & Plaques",
            "category_ranks_raw": "#1,321 in Home & Kitchen; #3 in Decorative Signs & Plaques",
            "raw_bsr_block": "#1,321 in Home & Kitchen; #3 in Decorative Signs & Plaques",
            "all_bsr_ranks": "#1,321 in Home & Kitchen; #3 in Decorative Signs & Plaques",
        }

        fixes = fetch_detail_fixes_for_products(
            FakeFetcher(),  # type: ignore[arg-type]
            [row],
            max_detail_fixes=1,
            detail_delay=0,
        )
        updated = apply_detail_fixes([row], fixes)

        self.assertEqual(updated, 1)
        for field in (
            "primary_bsr_rank",
            "primary_bsr_category",
            "sub_bsr_rank",
            "sub_bsr_category",
            "category_ranks_raw",
            "raw_bsr_block",
            "all_bsr_ranks",
            "rank_parse_method",
            "rank_parse_confidence",
            "accordion_found",
            "accordion_expanded",
            "bsr_visible_after_expand",
        ):
            self.assertEqual(row[field], audit_fields[field])
        self.assertEqual(row["primary_bsr_rank"], "14631")
        self.assertEqual(row["primary_bsr_category"], "Home & Kitchen")
        self.assertEqual(row["sub_bsr_rank"], "55")
        self.assertEqual(row["sub_bsr_category"], "Decorative Signs & Plaques")
        self.assertEqual(row["rank_parse_method"], "product_information_item_details")

    def test_refresh_bsr_overwrites_stale_values_from_product_information_details(self) -> None:
        product_url = "https://www.amazon.com/dp/B0H1BZGTBZ"
        html = """
        <html>
          <body>
            <section id="product-information-accordion">
              <h2>Product information</h2>
              <div>
                <h3>Item details</h3>
                <table>
                  <tr>
                    <th>Best Sellers Rank</th>
                    <td>
                      <span>#34,934 in Kitchen & Dining</span>
                      <span>#259 in Mugs</span>
                    </td>
                  </tr>
                </table>
              </div>
            </section>
          </body>
        </html>
        """

        class FakeDetailResult:
            status = "ok"
            error = ""
            screenshot = None
            accordion_found = True
            accordion_expanded = True
            bsr_visible_after_expand = True

            def __init__(self) -> None:
                self.html = html
                self.url = product_url

        class FakeFetcher:
            def __init__(self) -> None:
                self.urls: list[str] = []

            def fetch_detail_page(self, url: str, timeout: int, capture_screenshot: bool) -> FakeDetailResult:
                self.urls.append(url)
                return FakeDetailResult()

        row = {
            "asin": "B0H1BZGTBZ",
            "title": "Personalized Dad Sign for Home Decor",
            "image_url": "https://example.com/listing.jpg",
            "product_url": product_url,
            "primary_bsr_rank": "16114",
            "primary_bsr_category": "Kitchen & Dining",
            "sub_bsr_rank": "80",
            "sub_bsr_category": "Mugs",
            "category_ranks_raw": "#16,114 in Kitchen & Dining; #80 in Mugs",
            "raw_bsr_block": "#16,114 in Kitchen & Dining; #80 in Mugs",
            "all_bsr_ranks": "#16,114 in Kitchen & Dining; #80 in Mugs",
            "rank_extracted_at": "2026-06-18T00:00:00Z",
            "rank_parse_method": "text_scan",
            "rank_parse_confidence": "medium",
            "rank_parse_warning": "old warning",
        }

        fetcher = FakeFetcher()
        fixes = fetch_detail_fixes_for_products(
            fetcher,  # type: ignore[arg-type]
            [row],
            max_detail_fixes=1,
            detail_delay=0,
            refresh_bsr=True,
        )
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            updated = apply_detail_fixes([row], fixes)

        self.assertEqual(fetcher.urls, [product_url])
        self.assertEqual(updated, 1)
        self.assertEqual(row["primary_bsr_rank"], "34934")
        self.assertEqual(row["primary_bsr_category"], "Kitchen & Dining")
        self.assertEqual(row["sub_bsr_rank"], "259")
        self.assertEqual(row["sub_bsr_category"], "Mugs")
        self.assertEqual(row["category_ranks_raw"], "Best Sellers Rank\n#34,934 in Kitchen & Dining\n#259 in Mugs")
        self.assertEqual(row["raw_bsr_block"], "Best Sellers Rank\n#34,934 in Kitchen & Dining\n#259 in Mugs")
        self.assertEqual(row["all_bsr_ranks"], "#34,934 in Kitchen & Dining; #259 in Mugs")
        self.assertEqual(row["rank_parse_method"], "product_information_item_details")
        self.assertEqual(row["rank_parse_confidence"], "high")
        self.assertEqual(row["rank_parse_warning"], "")
        self.assertIn("ASIN=B0H1BZGTBZ", output.getvalue())
        self.assertIn("primary_bsr_rank=16114 -> 34934", output.getvalue())
        self.assertIn("sub_bsr_rank=80 -> 259", output.getvalue())
        self.assertIn("rank_parse_confidence=high", output.getvalue())

    def test_failed_refresh_bsr_preserves_existing_bsr_values(self) -> None:
        product_url = "https://www.amazon.com/dp/B0H1BZGTBZ"

        class FakeDetailResult:
            html = "<html><body><span id=\"productTitle\">Personalized Dad Sign for Home Decor</span></body></html>"
            status = "ok"
            error = ""
            screenshot = None

            def __init__(self) -> None:
                self.url = product_url

        class FakeFetcher:
            def fetch_detail_page(self, url: str, timeout: int, capture_screenshot: bool) -> FakeDetailResult:
                return FakeDetailResult()

        row = {
            "asin": "B0H1BZGTBZ",
            "title": "Personalized Dad Sign for Home Decor",
            "image_url": "https://example.com/listing.jpg",
            "product_url": product_url,
            "primary_bsr_rank": "16114",
            "primary_bsr_category": "Home & Kitchen",
            "sub_bsr_rank": "80",
            "sub_bsr_category": "Decorative Signs & Plaques",
            "category_ranks_raw": "#16,114 in Home & Kitchen; #80 in Decorative Signs & Plaques",
            "raw_bsr_block": "#16,114 in Home & Kitchen; #80 in Decorative Signs & Plaques",
            "all_bsr_ranks": "#16,114 in Home & Kitchen; #80 in Decorative Signs & Plaques",
            "rank_extracted_at": "2026-06-18T00:00:00Z",
            "rank_parse_method": "product_information_item_details",
            "rank_parse_confidence": "high",
        }

        fixes = fetch_detail_fixes_for_products(
            FakeFetcher(),  # type: ignore[arg-type]
            [row],
            max_detail_fixes=1,
            detail_delay=0,
            refresh_bsr=True,
        )
        updated = apply_detail_fixes([row], fixes)

        self.assertEqual(updated, 1)
        self.assertEqual(row["detail_bsr_found"], "false")
        self.assertEqual(row["detail_bsr_error"], "BSR unavailable on detail page")
        self.assertEqual(row["primary_bsr_rank"], "16114")
        self.assertEqual(row["sub_bsr_rank"], "80")
        self.assertEqual(row["category_ranks_raw"], "#16,114 in Home & Kitchen; #80 in Decorative Signs & Plaques")
        self.assertEqual(row["raw_bsr_block"], "#16,114 in Home & Kitchen; #80 in Decorative Signs & Plaques")
        self.assertEqual(row["rank_extracted_at"], "2026-06-18T00:00:00Z")
        self.assertEqual(row["rank_parse_method"], "product_information_item_details")
        self.assertEqual(row["rank_parse_confidence"], "high")

    def test_write_outputs_persists_refreshed_bsr_to_latest_products_csv(self) -> None:
        product_url = "https://www.amazon.com/dp/B0H1BZGTBZ"
        html = """
        <html>
          <body>
            <span id="productTitle">Wrappiness Personalized To My Son Mug from Dad Mom</span>
            <section id="product-information-accordion">
              <h2>Product information</h2>
              <div>
                <h3>Item details</h3>
                <table>
                  <tr>
                    <th>Best Sellers Rank</th>
                    <td>
                      <span>#34,934 in Kitchen & Dining</span>
                      <span>#259 in Mugs</span>
                    </td>
                  </tr>
                </table>
              </div>
            </section>
          </body>
        </html>
        """

        class FakeDetailResult:
            status = "ok"
            error = ""
            screenshot = None
            accordion_found = True
            accordion_expanded = True
            bsr_visible_after_expand = True

            def __init__(self) -> None:
                self.html = html
                self.url = product_url

        class FakeFetcher:
            def fetch_detail_page(self, url: str, timeout: int, capture_screenshot: bool) -> FakeDetailResult:
                return FakeDetailResult()

        product = {
            "date": "2026-06-22",
            "fetched_at": "2026-06-22T00:00:00+00:00",
            "source_name": "Wrappiness",
            "source_type": "seller",
            "seller_name": "Wrappiness",
            "seller_id": "A1PCU8P64JFCQ2",
            "category": "Mugs",
            "asin": "B0H1BZGTBZ",
            "title": "Wrappiness Personalized To My Son Mug from Dad Mom",
            "image_url": "https://example.com/listing.jpg",
            "product_url": product_url,
            "display_rank": "5",
            "display_order": "5",
            "rank": "5",
            "position": "5",
            "opportunity_score": "95",
            "is_pod": "yes",
            "pod_score": "130",
            "pod_type": "quote_mug",
            "niche_primary": "Dad",
            "niche_tags": "Dad;Father's Day;Mugs",
            "primary_bsr_rank": "",
            "primary_bsr_category": "",
            "sub_bsr_rank": "",
            "sub_bsr_category": "",
            "category_ranks_raw": "",
            "raw_bsr_block": "",
            "rank_parse_method": "",
            "rank_parse_confidence": "",
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "output"
            snapshot_dir = root / "snapshots"
            write_outputs(
                output_dir,
                snapshot_dir,
                root / "master_snapshot.csv",
                "2026-06-22T00:00:00+00:00",
                [product],
                [],
                sources=[],
                detail_fix_fetcher=FakeFetcher(),  # type: ignore[arg-type]
                refresh_bsr=True,
                max_detail_fixes=1,
                detail_delay=0,
            )
            with (output_dir / "latest_products.csv").open("r", encoding="utf-8-sig", newline="") as handle:
                latest_rows = list(csv.DictReader(handle))

        self.assertEqual(len(latest_rows), 1)
        latest = latest_rows[0]
        self.assertEqual(latest["asin"], "B0H1BZGTBZ")
        self.assertEqual(latest["bsr_rank"], "34934")
        self.assertEqual(latest["bsr_category"], "Kitchen & Dining")
        self.assertEqual(latest["primary_bsr_rank"], "34934")
        self.assertEqual(latest["primary_bsr_category"], "Kitchen & Dining")
        self.assertEqual(latest["sub_bsr_rank"], "259")
        self.assertEqual(latest["sub_bsr_category"], "Mugs")
        self.assertEqual(latest["rank_parse_method"], "product_information_item_details")
        self.assertEqual(latest["rank_parse_confidence"], "high")

    def test_refresh_bsr_ignores_stale_detail_cache_and_latest_matches_audit_parser(self) -> None:
        product_url = "https://www.amazon.com/dp/B0GVJX7MWC"
        html = """
        <html>
          <body>
            <span id="productTitle">Noni Personalized Family Portrait Wall Art Custom Watercolor Portrait From Photo</span>
            <section id="product-information-accordion">
              <h2>Product information</h2>
              <div>
                <h3>Item details</h3>
                <table>
                  <tr>
                    <th>Best Sellers Rank</th>
                    <td>
                      <span>#24,321 in Home & Kitchen</span>
                      <span>#17 in Posters & Prints</span>
                    </td>
                  </tr>
                </table>
              </div>
            </section>
          </body>
        </html>
        """
        audit_fields = extract_bsr_from_product_page(
            html,
            source_url=product_url,
            page_status="ok",
            diagnostics={
                "accordion_found": "true",
                "accordion_expanded": "true",
                "bsr_visible_after_expand": "true",
            },
        )

        class FakeDetailResult:
            status = "ok"
            error = ""
            screenshot = None
            accordion_found = True
            accordion_expanded = True
            bsr_visible_after_expand = True

            def __init__(self) -> None:
                self.html = html
                self.url = product_url

        class FakeFetcher:
            def __init__(self) -> None:
                self.urls: list[str] = []

            def fetch_detail_page(self, url: str, timeout: int, capture_screenshot: bool) -> FakeDetailResult:
                self.urls.append(url)
                return FakeDetailResult()

        product = {
            "date": "2026-06-23",
            "fetched_at": "2026-06-23T00:00:00+00:00",
            "source_name": "LBB Trading",
            "source_type": "seller",
            "seller_name": "LBB Trading",
            "seller_id": "A3D2FVIUCX0QRY",
            "category": "Posters",
            "asin": "B0GVJX7MWC",
            "title": "Noni Personalized Family Portrait Wall Art Custom Watercolor Portrait From Photo",
            "image_url": "https://example.com/listing.jpg",
            "product_url": product_url,
            "display_rank": "2",
            "display_order": "2",
            "rank": "2",
            "position": "2",
            "opportunity_score": "91",
            "is_pod": "yes",
            "pod_score": "120",
            "pod_type": "unknown",
            "niche_primary": "Dad",
            "niche_tags": "Dad;Family",
            "bsr_rank": "18644",
            "bsr_category": "Home & Kitchen",
            "primary_bsr_rank": "18644",
            "primary_bsr_category": "Home & Kitchen",
            "sub_bsr_rank": "12",
            "sub_bsr_category": "Posters & Prints",
            "category_ranks_raw": "#18,644 in Home & Kitchen; #12 in Posters & Prints",
            "raw_bsr_block": "#18,644 in Home & Kitchen; #12 in Posters & Prints",
            "all_bsr_ranks": "#18,644 in Home & Kitchen; #12 in Posters & Prints",
            "rank_parse_method": "product_information_item_details",
            "rank_parse_confidence": "high",
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "output"
            snapshot_dir = root / "snapshots"
            stale_cache_row = self.complete_detail_cache_row("B0GVJX7MWC", primary_rank="18644", sub_rank="12")
            stale_cache_row["sub_bsr_category"] = "Posters & Prints"
            self.write_detail_cache(output_dir / "detail_cache.csv", [stale_cache_row])
            fetcher = FakeFetcher()

            write_outputs(
                output_dir,
                snapshot_dir,
                root / "master_snapshot.csv",
                "2026-06-23T00:00:00+00:00",
                [product],
                [],
                sources=[],
                detail_fix_fetcher=fetcher,  # type: ignore[arg-type]
                refresh_bsr=True,
                max_detail_fixes=1,
                detail_delay=0,
            )
            with (output_dir / "latest_products.csv").open("r", encoding="utf-8-sig", newline="") as handle:
                latest_rows = list(csv.DictReader(handle))
            cache_rows = self.read_detail_cache(output_dir / "detail_cache.csv")

        latest = latest_rows[0]
        self.assertEqual(fetcher.urls, [product_url])
        for field in (
            "primary_bsr_rank",
            "primary_bsr_category",
            "sub_bsr_rank",
            "sub_bsr_category",
            "category_ranks_raw",
            "raw_bsr_block",
            "all_bsr_ranks",
            "rank_parse_method",
            "rank_parse_confidence",
        ):
            self.assertEqual(latest[field], audit_fields[field])
        self.assertNotEqual(latest["rank_extracted_at"], "")
        self.assertEqual(latest["bsr_rank"], audit_fields["primary_bsr_rank"])
        self.assertEqual(latest["bsr_category"], audit_fields["primary_bsr_category"])
        self.assertEqual(cache_rows[0]["primary_bsr_rank"], audit_fields["primary_bsr_rank"])
        self.assertEqual(cache_rows[0]["sub_bsr_rank"], audit_fields["sub_bsr_rank"])

    def test_repair_bsr_updates_multiple_asins_across_outputs(self) -> None:
        fields = ["asin", "title", "image_url", "product_url", "display_rank", "display_order", "opportunity_score", *CATEGORY_RANK_FIELDS]

        def product_row(asin: str, rank: str, sub_rank: str, url: str, display_rank: str) -> dict[str, str]:
            raw = f"# {rank} in Home & Kitchen; # {sub_rank} in Mugs" if rank else ""
            return {
                "asin": asin,
                "title": "Personalized Family Coffee Mug Gift for Dad",
                "image_url": "https://example.com/listing.jpg",
                "product_url": url,
                "display_rank": display_rank,
                "display_order": display_rank,
                "opportunity_score": "95",
                "bsr_rank": rank,
                "bsr_category": "Home & Kitchen" if rank else "",
                "primary_bsr_rank": rank,
                "primary_bsr_category": "Home & Kitchen" if rank else "",
                "sub_bsr_rank": sub_rank,
                "sub_bsr_category": "Mugs" if sub_rank else "",
                "category_ranks_raw": raw,
                "raw_bsr_block": raw,
                "all_bsr_ranks": raw,
                "rank_extracted_at": "2026-06-22T00:00:00+00:00" if rank else "",
                "rank_parse_confidence": "high" if rank else "",
            }

        class FakeDetailResult:
            status = "ok"
            error = ""
            screenshot = None
            accordion_found = True
            accordion_expanded = True
            bsr_visible_after_expand = True

            def __init__(self, html: str, url: str) -> None:
                self.html = html
                self.url = url

        class FakeFetcher:
            def __init__(self, pages: dict[str, str]) -> None:
                self.pages = pages

            def fetch_detail_page(self, url: str, timeout: int, capture_screenshot: bool) -> FakeDetailResult:
                return FakeDetailResult(self.pages[url], url)

        url1 = "https://www.amazon.com/dp/B0BATCH001"
        url2 = "https://www.amazon.com/dp/B0BATCH002"
        rows = [
            product_row("B0BATCH001", "10000", "50", url1, "1"),
            product_row("B0BATCH002", "", "", url2, "2"),
        ]
        pages = {
            url1: "<section id='product-information-accordion'><h3>Item details</h3><table><tr><th>Best Sellers Rank</th><td><span>#11,111 in Home & Kitchen</span><span>#11 in Mugs</span></td></tr></table></section>",
            url2: "<section id='product-information-accordion'><h3>Item details</h3><table><tr><th>Best Sellers Rank</th><td><span>#22,222 in Home & Kitchen</span><span>#22 in Mugs</span></td></tr></table></section>",
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "output"
            snapshot_dir = Path(temp_dir) / "snapshots"
            for filename in ("latest_products.csv", "product_trends.csv", "trend_alerts.csv", "lark_trend_alerts.csv"):
                self.write_rows(output_dir / filename, fields, rows)

            result = repair_bsr_outputs(
                output_dir=output_dir,
                snapshot_dir=snapshot_dir,
                fetcher=FakeFetcher(pages),  # type: ignore[arg-type]
                limit=10,
                detail_timeout=60,
                today="2026-06-23",
            )
            with (output_dir / "latest_products.csv").open("r", encoding="utf-8-sig", newline="") as handle:
                latest_rows = {row["asin"]: row for row in csv.DictReader(handle)}
            with (output_dir / "product_trends.csv").open("r", encoding="utf-8-sig", newline="") as handle:
                trend_rows = {row["asin"]: row for row in csv.DictReader(handle)}

        self.assertEqual(result.selected_count, 2)
        self.assertEqual(result.refreshed_count, 2)
        self.assertEqual(latest_rows["B0BATCH001"]["primary_bsr_rank"], "11111")
        self.assertEqual(latest_rows["B0BATCH002"]["primary_bsr_rank"], "22222")
        self.assertEqual(trend_rows["B0BATCH001"]["sub_bsr_rank"], "11")
        self.assertEqual(trend_rows["B0BATCH002"]["sub_bsr_rank"], "22")

    def test_repair_bsr_high_confidence_overwrites_old_bsr(self) -> None:
        fields = ["asin", "title", "image_url", "product_url", "display_rank", "opportunity_score", *CATEGORY_RANK_FIELDS]
        url = "https://www.amazon.com/dp/B0OVERWRT1"
        row = {
            "asin": "B0OVERWRT1",
            "title": "Personalized Family Coffee Mug Gift for Dad",
            "image_url": "https://example.com/listing.jpg",
            "product_url": url,
            "display_rank": "4",
            "opportunity_score": "90",
            "bsr_rank": "12345",
            "bsr_category": "Home & Kitchen",
            "primary_bsr_rank": "12345",
            "primary_bsr_category": "Home & Kitchen",
            "sub_bsr_rank": "77",
            "sub_bsr_category": "Mugs",
            "category_ranks_raw": "#12,345 in Home & Kitchen; #77 in Mugs",
            "raw_bsr_block": "#12,345 in Home & Kitchen; #77 in Mugs",
            "all_bsr_ranks": "#12,345 in Home & Kitchen; #77 in Mugs",
            "rank_extracted_at": "2026-06-22T00:00:00+00:00",
            "rank_parse_confidence": "high",
        }

        class FakeResult:
            html = "<section id='product-information-accordion'><h3>Item details</h3><table><tr><th>Best Sellers Rank</th><td><span>#33,333 in Kitchen & Dining</span><span>#99 in Mugs</span></td></tr></table></section>"
            status = "ok"
            error = ""
            screenshot = None
            accordion_found = True
            accordion_expanded = True
            bsr_visible_after_expand = True

            def __init__(self) -> None:
                self.url = url

        class FakeFetcher:
            def fetch_detail_page(self, url: str, timeout: int, capture_screenshot: bool) -> FakeResult:
                return FakeResult()

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "output"
            self.write_rows(output_dir / "latest_products.csv", fields, [row])
            result = repair_bsr_outputs(
                output_dir=output_dir,
                snapshot_dir=Path(temp_dir) / "snapshots",
                fetcher=FakeFetcher(),  # type: ignore[arg-type]
                limit=1,
                detail_timeout=60,
                today="2026-06-23",
            )
            with (output_dir / "latest_products.csv").open("r", encoding="utf-8-sig", newline="") as handle:
                latest = list(csv.DictReader(handle))[0]

        self.assertEqual(result.refreshed_count, 1)
        self.assertEqual(latest["bsr_rank"], "33333")
        self.assertEqual(latest["bsr_category"], "Kitchen & Dining")
        self.assertEqual(latest["primary_bsr_rank"], "33333")
        self.assertEqual(latest["sub_bsr_rank"], "99")
        self.assertEqual(latest["rank_parse_confidence"], "high")

    def test_repair_bsr_failed_extraction_preserves_old_bsr(self) -> None:
        fields = ["asin", "title", "image_url", "product_url", "display_rank", "opportunity_score", *CATEGORY_RANK_FIELDS]
        row = {
            "asin": "B0FAIL0001",
            "title": "Personalized Family Coffee Mug Gift for Dad",
            "image_url": "https://example.com/listing.jpg",
            "product_url": "https://www.amazon.com/dp/B0FAIL0001",
            "display_rank": "3",
            "opportunity_score": "88",
            "bsr_rank": "12345",
            "bsr_category": "Home & Kitchen",
            "primary_bsr_rank": "12345",
            "primary_bsr_category": "Home & Kitchen",
            "sub_bsr_rank": "77",
            "sub_bsr_category": "Mugs",
            "category_ranks_raw": "#12,345 in Home & Kitchen; #77 in Mugs",
            "raw_bsr_block": "#12,345 in Home & Kitchen; #77 in Mugs",
            "all_bsr_ranks": "#12,345 in Home & Kitchen; #77 in Mugs",
            "rank_extracted_at": "2026-06-22T00:00:00+00:00",
            "rank_parse_confidence": "high",
        }

        class FakeResult:
            html = "<html><body>No BSR here</body></html>"
            status = "ok"
            error = ""
            screenshot = None
            url = "https://www.amazon.com/dp/B0FAIL0001"
            accordion_found = False
            accordion_expanded = False
            bsr_visible_after_expand = False

        class FakeFetcher:
            def fetch_detail_page(self, url: str, timeout: int, capture_screenshot: bool) -> FakeResult:
                return FakeResult()

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "output"
            self.write_rows(output_dir / "latest_products.csv", fields, [row])
            result = repair_bsr_outputs(
                output_dir=output_dir,
                snapshot_dir=Path(temp_dir) / "snapshots",
                fetcher=FakeFetcher(),  # type: ignore[arg-type]
                limit=1,
                detail_timeout=60,
                force=True,
                today="2026-06-23",
            )
            with (output_dir / "latest_products.csv").open("r", encoding="utf-8-sig", newline="") as handle:
                latest = list(csv.DictReader(handle))[0]

        self.assertEqual(result.refreshed_count, 0)
        self.assertEqual(result.failed_count, 1)
        self.assertEqual(latest["primary_bsr_rank"], "12345")
        self.assertEqual(latest["sub_bsr_rank"], "77")
        self.assertEqual(latest["rank_parse_confidence"], "high")

    def test_repair_bsr_updates_detail_cache(self) -> None:
        fields = ["asin", "title", "image_url", "product_url", "display_rank", "opportunity_score", *CATEGORY_RANK_FIELDS]
        url = "https://www.amazon.com/dp/B0CACHE333"
        row = {
            "asin": "B0CACHE333",
            "title": "Personalized Family Coffee Mug Gift for Dad",
            "image_url": "https://example.com/listing.jpg",
            "product_url": url,
            "display_rank": "7",
            "opportunity_score": "86",
            "rank_extracted_at": "2026-06-22T00:00:00+00:00",
            "rank_parse_confidence": "medium",
        }

        class FakeResult:
            html = "<section id='product-information-accordion'><h3>Item details</h3><table><tr><th>Best Sellers Rank</th><td><span>#44,444 in Home & Kitchen</span><span>#144 in Mugs</span></td></tr></table></section>"
            status = "ok"
            error = ""
            screenshot = None
            accordion_found = True
            accordion_expanded = True
            bsr_visible_after_expand = True

            def __init__(self) -> None:
                self.url = url

        class FakeFetcher:
            def fetch_detail_page(self, url: str, timeout: int, capture_screenshot: bool) -> FakeResult:
                return FakeResult()

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "output"
            self.write_rows(output_dir / "latest_products.csv", fields, [row])
            result = repair_bsr_outputs(
                output_dir=output_dir,
                snapshot_dir=Path(temp_dir) / "snapshots",
                fetcher=FakeFetcher(),  # type: ignore[arg-type]
                limit=1,
                detail_timeout=60,
                today="2026-06-23",
            )
            cache_rows = self.read_detail_cache(output_dir / "detail_cache.csv")

        self.assertEqual(result.refreshed_count, 1)
        self.assertEqual(cache_rows[0]["asin"], "B0CACHE333")
        self.assertEqual(cache_rows[0]["primary_bsr_rank"], "44444")
        self.assertEqual(cache_rows[0]["sub_bsr_rank"], "144")
        self.assertEqual(cache_rows[0]["rank_parse_confidence"], "high")
        self.assertEqual(cache_rows[0]["rank_source_url"], url)

    def test_fetch_detail_fixes_repairs_invalid_title_and_missing_image(self) -> None:
        class FakeFetcher:
            def __init__(self) -> None:
                self.urls: list[str] = []

            def fetch(self, url: str) -> str:
                self.urls.append(url)
                return """
                <html>
                  <head><meta property="og:image" content="https://example.com/og.jpg"></head>
                  <body>
                    <span id="productTitle">Personalized Dad Coffee Mug Custom Father's Day Gift</span>
                    <img id="landingImage" src="https://example.com/landing.jpg">
                    <div id="detailBullets_feature_div">
                      <span>Best Sellers Rank</span>
                      <span>#65,003 in Home & Kitchen</span>
                      <span>#149 in Decorative Signs & Plaques</span>
                    </div>
                  </body>
                </html>
                """

        row = {
            "asin": "B0DETAIL11",
            "title": "Gift Idea 1",
            "raw_title": "Gift Idea 1",
            "title_source": "listing_card",
            "title_fixed": "false",
            "image_url": "",
            "image_source": "",
            "image_fixed": "false",
            "product_url": "https://www.amazon.com/dp/B0DETAIL11",
        }

        fixes = fetch_detail_fixes_for_products(
            FakeFetcher(),  # type: ignore[arg-type]
            [row],
            max_detail_fixes=1,
            detail_delay=0,
        )
        updated = apply_detail_fixes([row], fixes)

        self.assertEqual(updated, 1)
        self.assertEqual(row["title"], "Personalized Dad Coffee Mug Custom Father's Day Gift")
        self.assertEqual(row["raw_title"], "Gift Idea 1")
        self.assertEqual(row["title_source"], "detail_page")
        self.assertEqual(row["title_fixed"], "true")
        self.assertEqual(row["image_url"], "https://example.com/landing.jpg")
        self.assertEqual(row["image_source"], "detail_page")
        self.assertEqual(row["image_fixed"], "true")
        self.assertEqual(row["detail_page_status"], "ok")
        self.assertEqual(row["detail_title_found"], "true")
        self.assertEqual(row["detail_image_found"], "true")
        self.assertEqual(row["detail_error"], "")
        self.assertEqual(row["detail_bsr_found"], "true")
        self.assertEqual(row["detail_bsr_error"], "")
        self.assertEqual(row["primary_bsr_rank"], "65003")
        self.assertEqual(row["primary_bsr_category"], "Home & Kitchen")
        self.assertEqual(row["sub_bsr_rank"], "149")
        self.assertEqual(row["sub_bsr_category"], "Decorative Signs & Plaques")
        self.assertEqual(
            row["category_ranks_raw"],
            "Best Sellers Rank #65,003 in Home & Kitchen #149 in Decorative Signs & Plaques",
        )
        self.assertEqual(row["rank_source_url"], "https://www.amazon.com/dp/B0DETAIL11")
        self.assertEqual(row["rank_page_status"], "ok")

    def test_cached_asin_is_skipped_and_merged_from_detail_cache(self) -> None:
        class FakeFetcher:
            def __init__(self) -> None:
                self.urls: list[str] = []

            def fetch(self, url: str) -> str:
                self.urls.append(url)
                return "<html></html>"

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "output" / "detail_cache.csv"
            self.write_detail_cache(cache_path, [self.complete_detail_cache_row("B0CACHE111")])
            row = {
                "asin": "B0CACHE111",
                "title": "Gift Idea 1",
                "image_url": "",
                "product_url": "https://www.amazon.com/dp/B0CACHE111",
            }
            fetcher = FakeFetcher()
            output = io.StringIO()

            with contextlib.redirect_stdout(output):
                fixes = fetch_detail_fixes_for_products(
                    fetcher,  # type: ignore[arg-type]
                    [row],
                    max_detail_fixes=1,
                    detail_delay=0,
                    detail_cache_path=cache_path,
                )

        self.assertEqual(fixes, {})
        self.assertEqual(fetcher.urls, [])
        self.assertEqual(row["title"], "Personalized Family Coffee Mug Gift for Dad")
        self.assertEqual(row["image_url"], "https://example.com/cached.jpg")
        self.assertEqual(row["primary_bsr_rank"], "12345")
        self.assertEqual(row["sub_bsr_rank"], "77")
        self.assertIn("Detail skipped from cache: B0CACHE111", output.getvalue())
        self.assertIn("Detail pages skipped from cache: 1", output.getvalue())

    def test_new_asin_missing_title_gets_detail_fetched(self) -> None:
        class FakeFetcher:
            def __init__(self) -> None:
                self.urls: list[str] = []

            def fetch(self, url: str) -> str:
                self.urls.append(url)
                return """
                <html>
                  <head><meta property="og:title" content="Personalized Family Coffee Mug Gift for Dad"></head>
                  <body>
                    <img id="landingImage" src="https://example.com/new-title.jpg">
                    <section id="product-information-accordion">
                      <h3>Item details</h3>
                      <table><tr><th>Best Sellers Rank</th><td><span>#12,345 in Home & Kitchen</span><span>#77 in Mugs</span></td></tr></table>
                    </section>
                  </body>
                </html>
                """

        row = {
            "asin": "B0NEWTITLE",
            "title": "Gift Idea 1",
            "image_url": "https://example.com/listing.jpg",
            "product_url": "https://www.amazon.com/dp/B0NEWTITLE",
            "_new_asin_today": "true",
        }
        fetcher = FakeFetcher()
        fixes = fetch_detail_fixes_for_products(
            fetcher,  # type: ignore[arg-type]
            [row],
            max_detail_fixes=1,
            detail_delay=0,
        )
        apply_detail_fixes([row], fixes)

        self.assertEqual(fetcher.urls, ["https://www.amazon.com/dp/B0NEWTITLE"])
        self.assertEqual(row["title"], "Personalized Family Coffee Mug Gift for Dad")
        self.assertEqual(row["title_source"], "detail_page")
        self.assertEqual(row["title_fixed"], "true")
        self.assertEqual(row["detail_fetched_reason"], "new_asin")

    def test_new_asin_missing_image_gets_detail_fetched(self) -> None:
        class FakeFetcher:
            def __init__(self) -> None:
                self.urls: list[str] = []

            def fetch(self, url: str) -> str:
                self.urls.append(url)
                return """
                <html>
                  <body>
                    <span id="productTitle">Personalized Family Coffee Mug Gift for Dad</span>
                    <div id="imgTagWrapperId"><img src="https://example.com/wrapper.jpg"></div>
                    <section id="product-information-accordion">
                      <h3>Item details</h3>
                      <table><tr><th>Best Sellers Rank</th><td><span>#12,345 in Home & Kitchen</span><span>#77 in Mugs</span></td></tr></table>
                    </section>
                  </body>
                </html>
                """

        row = {
            "asin": "B0NEWIMAGE",
            "title": "Personalized Family Coffee Mug Gift for Dad",
            "image_url": "",
            "product_url": "https://www.amazon.com/dp/B0NEWIMAGE",
            "_new_asin_today": "true",
        }
        fetcher = FakeFetcher()
        fixes = fetch_detail_fixes_for_products(
            fetcher,  # type: ignore[arg-type]
            [row],
            max_detail_fixes=1,
            detail_delay=0,
        )
        apply_detail_fixes([row], fixes)

        self.assertEqual(fetcher.urls, ["https://www.amazon.com/dp/B0NEWIMAGE"])
        self.assertEqual(row["image_url"], "https://example.com/wrapper.jpg")
        self.assertEqual(row["image_source"], "detail_page")
        self.assertEqual(row["image_fixed"], "true")
        self.assertEqual(row["detail_fetched_reason"], "new_asin")

    def test_cached_new_asin_with_valid_title_image_is_skipped(self) -> None:
        class FakeFetcher:
            def __init__(self) -> None:
                self.called = False

            def fetch(self, url: str) -> str:
                self.called = True
                return "<html></html>"

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "output" / "detail_cache.csv"
            self.write_detail_cache(cache_path, [self.complete_detail_cache_row("B0NEWSKIP1")])
            row = {
                "asin": "B0NEWSKIP1",
                "title": "Personalized Family Coffee Mug Gift for Dad",
                "image_url": "https://example.com/listing.jpg",
                "product_url": "https://www.amazon.com/dp/B0NEWSKIP1",
                "primary_bsr_rank": "12345",
                "primary_bsr_category": "Home & Kitchen",
                "sub_bsr_rank": "77",
                "sub_bsr_category": "Mugs",
                "category_ranks_raw": "Best Sellers Rank #12345 in Home & Kitchen #77 in Mugs",
                "raw_bsr_block": "Best Sellers Rank #12345 in Home & Kitchen #77 in Mugs",
                "all_bsr_ranks": "#12345 in Home & Kitchen; #77 in Mugs",
                "rank_parse_confidence": "high",
                "_new_asin_today": "true",
            }
            fetcher = FakeFetcher()
            fixes = fetch_detail_fixes_for_products(
                fetcher,  # type: ignore[arg-type]
                [row],
                max_detail_fixes=1,
                detail_delay=0,
                detail_cache_path=cache_path,
            )

        self.assertEqual(fixes, {})
        self.assertFalse(fetcher.called)

    def test_new_asin_is_fetched_and_written_to_detail_cache(self) -> None:
        class FakeFetcher:
            def __init__(self) -> None:
                self.urls: list[str] = []

            def fetch(self, url: str) -> str:
                self.urls.append(url)
                return """
                <html>
                  <body>
                    <span id="productTitle">Personalized Family Coffee Mug Gift for Dad</span>
                    <img id="landingImage" src="https://example.com/new.jpg">
                    <section id="product-information-accordion">
                      <h3>Item details</h3>
                      <table>
                        <tr><th>Best Sellers Rank</th><td><span>#22,222 in Home & Kitchen</span><span>#88 in Mugs</span></td></tr>
                      </table>
                    </section>
                  </body>
                </html>
                """

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "output" / "detail_cache.csv"
            row = {
                "asin": "B0NEWASIN1",
                "title": "Personalized Family Coffee Mug Gift for Dad",
                "image_url": "https://example.com/listing.jpg",
                "product_url": "https://www.amazon.com/dp/B0NEWASIN1",
            }
            fetcher = FakeFetcher()
            output = io.StringIO()

            with contextlib.redirect_stdout(output):
                fixes = fetch_detail_fixes_for_products(
                    fetcher,  # type: ignore[arg-type]
                    [row],
                    max_detail_fixes=1,
                    detail_delay=0,
                    detail_cache_path=cache_path,
                )

            cache_rows = self.read_detail_cache(cache_path)

        self.assertEqual(fetcher.urls, ["https://www.amazon.com/dp/B0NEWASIN1"])
        self.assertIn("B0NEWASIN1", fixes)
        self.assertIn("Detail fetched: B0NEWASIN1 reason=new_asin", output.getvalue())
        self.assertIn("New ASINs: 1", output.getvalue())
        self.assertEqual(cache_rows[0]["asin"], "B0NEWASIN1")
        self.assertEqual(cache_rows[0]["primary_bsr_rank"], "22222")
        self.assertEqual(cache_rows[0]["rank_parse_confidence"], "high")

    def test_missing_image_asin_is_fetched(self) -> None:
        class FakeFetcher:
            def __init__(self) -> None:
                self.urls: list[str] = []

            def fetch(self, url: str) -> str:
                self.urls.append(url)
                return """
                <html>
                  <body>
                    <span id="productTitle">Personalized Family Coffee Mug Gift for Dad</span>
                    <img id="landingImage" src="https://example.com/fixed.jpg">
                    <section id="product-information-accordion">
                      <h3>Item details</h3>
                      <table>
                        <tr><th>Best Sellers Rank</th><td><span>#12,345 in Home & Kitchen</span><span>#77 in Mugs</span></td></tr>
                      </table>
                    </section>
                  </body>
                </html>
                """

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "output" / "detail_cache.csv"
            incomplete_cache_row = self.complete_detail_cache_row("B0MISSIMG1")
            incomplete_cache_row["image_url"] = ""
            self.write_detail_cache(cache_path, [incomplete_cache_row])
            row = {
                "asin": "B0MISSIMG1",
                "title": "Personalized Family Coffee Mug Gift for Dad",
                "image_url": "",
                "product_url": "https://www.amazon.com/dp/B0MISSIMG1",
            }
            fetcher = FakeFetcher()
            output = io.StringIO()

            with contextlib.redirect_stdout(output):
                fixes = fetch_detail_fixes_for_products(
                    fetcher,  # type: ignore[arg-type]
                    [row],
                    max_detail_fixes=1,
                    detail_delay=0,
                    detail_cache_path=cache_path,
                )

        self.assertEqual(fetcher.urls, ["https://www.amazon.com/dp/B0MISSIMG1"])
        self.assertIn("B0MISSIMG1", fixes)
        self.assertIn("missing_image", output.getvalue())

    def test_high_confidence_bsr_asin_is_skipped(self) -> None:
        class FakeFetcher:
            def __init__(self) -> None:
                self.called = False

            def fetch(self, url: str) -> str:
                self.called = True
                return "<html></html>"

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "output" / "detail_cache.csv"
            self.write_detail_cache(cache_path, [self.complete_detail_cache_row("B0HIGHBSR1")])
            row = {
                "asin": "B0HIGHBSR1",
                "title": "Personalized Family Coffee Mug Gift for Dad",
                "image_url": "https://example.com/listing.jpg",
                "product_url": "https://www.amazon.com/dp/B0HIGHBSR1",
            }
            fetcher = FakeFetcher()

            fixes = fetch_detail_fixes_for_products(
                fetcher,  # type: ignore[arg-type]
                [row],
                max_detail_fixes=1,
                detail_delay=0,
                detail_cache_path=cache_path,
            )

        self.assertEqual(fixes, {})
        self.assertFalse(fetcher.called)
        self.assertEqual(row["primary_bsr_rank"], "12345")
        self.assertEqual(row["rank_parse_confidence"], "high")

    def test_refresh_bsr_forces_rank_refresh_despite_complete_cache(self) -> None:
        class FakeFetcher:
            def __init__(self) -> None:
                self.urls: list[str] = []

            def fetch(self, url: str) -> str:
                self.urls.append(url)
                return """
                <html>
                  <body>
                    <span id="productTitle">Personalized Family Coffee Mug Gift for Dad</span>
                    <img id="landingImage" src="https://example.com/refreshed.jpg">
                    <section id="product-information-accordion">
                      <h3>Item details</h3>
                      <table>
                        <tr><th>Best Sellers Rank</th><td><span>#33,333 in Kitchen & Dining</span><span>#99 in Mugs</span></td></tr>
                      </table>
                    </section>
                  </body>
                </html>
                """

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "output" / "detail_cache.csv"
            self.write_detail_cache(cache_path, [self.complete_detail_cache_row("B0REFRESH1")])
            row = {
                "asin": "B0REFRESH1",
                "title": "",
                "image_url": "",
                "product_url": "https://www.amazon.com/dp/B0REFRESH1",
            }
            fetcher = FakeFetcher()
            output = io.StringIO()

            with contextlib.redirect_stdout(output):
                fixes = fetch_detail_fixes_for_products(
                    fetcher,  # type: ignore[arg-type]
                    [row],
                    max_detail_fixes=1,
                    detail_delay=0,
                    refresh_bsr=True,
                    detail_cache_path=cache_path,
                )
            updated = apply_detail_fixes([row], fixes)

        self.assertEqual(fetcher.urls, ["https://www.amazon.com/dp/B0REFRESH1"])
        self.assertEqual(updated, 1)
        self.assertEqual(row["primary_bsr_rank"], "33333")
        self.assertEqual(row["sub_bsr_rank"], "99")
        self.assertIn("Detail fetched: B0REFRESH1 reason=refresh_bsr", output.getvalue())
        self.assertIn("Detail refreshed BSR: B0REFRESH1", output.getvalue())

    def test_refresh_bsr_prioritizes_display_rank_before_missing_bsr(self) -> None:
        class FakeFetcher:
            def __init__(self) -> None:
                self.urls: list[str] = []

            def fetch(self, url: str) -> str:
                self.urls.append(url)
                return """
                <html>
                  <body>
                    <section id="product-information-accordion">
                      <h3>Item details</h3>
                      <table>
                        <tr><th>Best Sellers Rank</th><td><span>#33,333 in Home & Kitchen</span><span>#99 in Mugs</span></td></tr>
                      </table>
                    </section>
                  </body>
                </html>
                """

        rows = [
            {
                "asin": "B0MISSLOW1",
                "title": "Personalized Family Coffee Mug Gift for Dad",
                "image_url": "https://example.com/low.jpg",
                "product_url": "https://www.amazon.com/dp/B0MISSLOW1",
                "display_rank": "10",
            },
            {
                "asin": "B0TOPRANK1",
                "title": "Personalized Family Coffee Mug Gift for Dad",
                "image_url": "https://example.com/top.jpg",
                "product_url": "https://www.amazon.com/dp/B0TOPRANK1",
                "display_rank": "2",
                "primary_bsr_rank": "12345",
                "primary_bsr_category": "Home & Kitchen",
                "sub_bsr_rank": "77",
                "sub_bsr_category": "Mugs",
                "category_ranks_raw": "#12,345 in Home & Kitchen; #77 in Mugs",
                "raw_bsr_block": "#12,345 in Home & Kitchen; #77 in Mugs",
                "rank_parse_confidence": "high",
            },
        ]
        fetcher = FakeFetcher()

        fetch_detail_fixes_for_products(
            fetcher,  # type: ignore[arg-type]
            rows,
            max_detail_fixes=1,
            detail_delay=0,
            refresh_bsr=True,
        )

        self.assertEqual(fetcher.urls, ["https://www.amazon.com/dp/B0TOPRANK1"])

    def test_detail_fallback_overwrites_legacy_bsr_fields(self) -> None:
        class FakeFetcher:
            def fetch(self, url: str) -> str:
                return """
                <html>
                  <body>
                    <span id="productTitle">Personalized Dad Coffee Mug Custom Father's Day Gift</span>
                    <div id="productDetails_detailBullets_sections1">
                      <span>Best Sellers Rank</span>
                      <span>#65,003 in Home & Kitchen</span>
                      <span>#149 in Decorative Signs & Plaques</span>
                    </div>
                  </body>
                </html>
                """

        row = {
            "asin": "B0DETAIL33",
            "title": "Gift Idea 1",
            "image_url": "https://example.com/listing.jpg",
            "product_url": "https://www.amazon.com/dp/B0DETAIL33",
            "bsr_rank": "12",
            "bsr_category": "Handmade Products",
            "category_ranks_raw": "#12 in Handmade Products",
        }

        fixes = fetch_detail_fixes_for_products(
            FakeFetcher(),  # type: ignore[arg-type]
            [row],
            max_detail_fixes=1,
            detail_delay=0,
        )
        updated = apply_detail_fixes([row], fixes)

        self.assertEqual(updated, 1)
        self.assertEqual(row["bsr_rank"], "65003")
        self.assertEqual(row["bsr_category"], "Home & Kitchen")
        self.assertEqual(row["primary_bsr_rank"], "65003")
        self.assertEqual(row["primary_bsr_category"], "Home & Kitchen")
        self.assertEqual(
            row["category_ranks_raw"],
            "Best Sellers Rank #65,003 in Home & Kitchen #149 in Decorative Signs & Plaques",
        )
        self.assertEqual(row["sub_bsr_rank"], "149")
        self.assertEqual(row["sub_bsr_category"], "Decorative Signs & Plaques")
        self.assertEqual(row["detail_bsr_found"], "true")

    def test_failed_detail_fallback_writes_debug_artifacts_and_preserves_variation_url(self) -> None:
        class FakeDetailResult:
            html = "<html><head><title>Amazon.com: Gift Idea 1</title></head><body>No product data</body></html>"
            status = "ok"
            error = ""
            screenshot = b"fake-png"

        class FakeFetcher:
            def __init__(self) -> None:
                self.url = ""
                self.timeout = 0
                self.capture_screenshot = False

            def fetch_detail_page(self, url: str, timeout: int, capture_screenshot: bool) -> FakeDetailResult:
                self.url = url
                self.timeout = timeout
                self.capture_screenshot = capture_screenshot
                return FakeDetailResult()

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fetcher = FakeFetcher()
            row = {
                "asin": "B0DETAIL22",
                "title": "A1",
                "image_url": "",
                "product_url": "https://www.amazon.com/dp/B0DETAIL22?th=1&merchant-items=1",
            }

            fixes = fetch_detail_fixes_for_products(
                fetcher,  # type: ignore[arg-type]
                [row],
                max_detail_fixes=1,
                detail_delay=0,
                detail_timeout=30,
                debug_html_dir=root / "debug_html",
                screenshot_dir=root / "screenshots",
            )
            updated = apply_detail_fixes([row], fixes)

            self.assertEqual(fetcher.url, "https://www.amazon.com/dp/B0DETAIL22?th=1&merchant-items=1")
            self.assertEqual(fetcher.timeout, 30)
            self.assertTrue(fetcher.capture_screenshot)
            self.assertEqual(updated, 1)
            self.assertEqual(row["title"], "A1")
            self.assertEqual(row["image_url"], "")
            self.assertEqual(row["detail_page_status"], "ok")
            self.assertEqual(row["detail_title_found"], "true")
            self.assertEqual(row["detail_image_found"], "false")
            self.assertEqual(row["detail_bsr_found"], "false")
            self.assertEqual(row["detail_bsr_error"], "BSR unavailable on detail page")
            self.assertIn("invalid detail title", row["detail_error"])
            self.assertIn("image unavailable", row["detail_error"])
            self.assertTrue((root / "debug_html" / "detail_failed_B0DETAIL22.html").exists())
            self.assertEqual((root / "screenshots" / "detail_failed_B0DETAIL22.png").read_bytes(), b"fake-png")

    def test_parse_source_pages_keeps_display_rank_continuous(self) -> None:
        source = Source(
            source_name="Store",
            source_type="seller",
            category="Mugs",
            url="https://www.amazon.com/s?me=A123",
            priority=1,
            active=True,
            row_number=1,
        )
        pages = [
            FetchedPage(
                html="""
                <div data-component-type="s-search-result" data-asin="B0PAGE1111">
                  <a href="/dp/B0PAGE1111"><h2><span>First Personalized Mug</span></h2></a>
                </div>
                <div data-component-type="s-search-result" data-asin="B0PAGE2222">
                  <a href="/dp/B0PAGE2222"><h2><span>Second Personalized Mug</span></h2></a>
                </div>
                """,
                url="https://www.amazon.com/s?me=A123&page=1",
                page_number=1,
            ),
            FetchedPage(
                html="""
                <div data-component-type="s-search-result" data-asin="B0PAGE3333">
                  <a href="/dp/B0PAGE3333"><h2><span>Third Personalized Mug</span></h2></a>
                </div>
                """,
                url="https://www.amazon.com/s?me=A123&page=2",
                page_number=2,
            ),
        ]

        rows = parse_source_pages(pages, source, "2026-06-11T00:00:00+00:00")

        self.assertEqual([row["asin"] for row in rows], ["B0PAGE1111", "B0PAGE2222", "B0PAGE3333"])
        self.assertEqual([row["display_rank"] for row in rows], ["1", "2", "3"])
        self.assertEqual([row["rank"] for row in rows], ["1", "2", "3"])
        self.assertEqual(rows[2]["page_url"], "https://www.amazon.com/s?me=A123&page=2")

    def test_source_scan_report_counts_duplicates_and_highlights_low_coverage(self) -> None:
        source = Source(
            source_name="Store",
            source_type="seller",
            category="Mugs",
            url="https://www.amazon.com/s?me=A123",
            priority=1,
            active=True,
            row_number=1,
        )
        pages = [
            FetchedPage(
                html="<html></html>",
                url="https://www.amazon.com/s?me=A123&page=1",
                page_number=1,
                product_asins=("B0DUP11111", "B0DUP11111", "B0MISS1111"),
                raw_total_text="1-3 of 10 results",
                scrolls=4,
                scroll_stop_reason="no_new_asin_after_3_scrolls",
                stop_reason="no_next_page",
            )
        ]

        row = build_source_scan_report_row(
            source,
            pages,
            [{"asin": "B0DUP11111"}],
            max_pages=3,
            elapsed_seconds=1.234,
        )

        self.assertEqual(row["source_name"], "Store")
        self.assertEqual(row["source_type"], "seller")
        self.assertEqual(row["raw_total_text"], "1-3 of 10 results")
        self.assertEqual(row["max_pages"], "3")
        self.assertEqual(row["expected_products"], "10")
        self.assertEqual(row["expected_top_products"], "10")
        self.assertEqual(row["collected_products"], "2")
        self.assertEqual(row["top_page_coverage"], "20.00%")
        self.assertEqual(row["full_coverage"], "20.00%")
        self.assertEqual(row["status"], "LOW_TOP_PAGE_COVERAGE")
        self.assertEqual(row["pages_scanned"], "1")
        self.assertEqual(row["next_clicks"], "0")
        self.assertEqual(row["duplicates"], "1")
        self.assertEqual(row["filtered"], "1")
        self.assertEqual(row["elapsed_seconds"], "1.23")
        self.assertEqual(row["final_url"], "https://www.amazon.com/s?me=A123&page=1")
        self.assertEqual(row["stop_reason"], "no_next_page")

    def test_source_scan_report_marks_large_seller_partial_by_design(self) -> None:
        source = Source(
            source_name="Large Store",
            source_type="seller",
            category="Mugs",
            url="https://www.amazon.com/s?me=A123",
            priority=1,
            active=True,
            row_number=1,
        )
        asins = tuple(f"B0TOP{i:05d}" for i in range(48))
        pages = [
            FetchedPage(
                html="<html></html>",
                url="https://www.amazon.com/s?me=A123&page=3",
                page_number=3,
                product_asins=asins,
                raw_total_text="1-16 of 600 results",
                stop_reason="max_pages_reached",
            )
        ]

        row = build_source_scan_report_row(
            source,
            pages,
            [{"asin": asin} for asin in asins],
            max_pages=3,
            elapsed_seconds=2.0,
        )

        self.assertEqual(row["expected_products"], "600")
        self.assertEqual(row["expected_top_products"], "48")
        self.assertEqual(row["collected_products"], "48")
        self.assertEqual(row["top_page_coverage"], "100.00%")
        self.assertEqual(row["full_coverage"], "8.00%")
        self.assertEqual(row["status"], "PARTIAL_BY_DESIGN")

    def test_source_scan_report_computes_ranking_top_coverage_without_total(self) -> None:
        source = Source(
            source_name="Mugs Best Sellers",
            source_type="best_seller",
            category="Mugs",
            url="https://www.amazon.com/Best-Sellers-Mugs/zgbs/kitchen/367142011",
            priority=1,
            active=True,
            row_number=1,
        )
        page_one_asins = tuple(f"B0BS1{i:05d}" for i in range(50))
        page_two_asins = tuple(f"B0BS2{i:05d}" for i in range(45))
        pages = [
            FetchedPage(
                html="<html></html>",
                url="https://www.amazon.com/Best-Sellers-Mugs/zgbs/kitchen/367142011",
                page_number=1,
                product_asins=page_one_asins,
            ),
            FetchedPage(
                html="<html></html>",
                url="https://www.amazon.com/Best-Sellers-Mugs/zgbs/kitchen/367142011?pg=2",
                page_number=2,
                product_asins=page_two_asins,
                stop_reason="max_pages_reached",
            ),
        ]
        asins = page_one_asins + page_two_asins

        row = build_source_scan_report_row(
            source,
            pages,
            [{"asin": asin} for asin in asins],
            max_pages=2,
            elapsed_seconds=2.0,
        )

        self.assertEqual(row["expected_products"], "")
        self.assertEqual(row["expected_top_products"], "100")
        self.assertEqual(row["collected_products"], "95")
        self.assertEqual(row["top_page_coverage"], "95.00%")
        self.assertEqual(row["full_coverage"], "")
        self.assertEqual(row["status"], "OK")
        self.assertEqual(row["pages_scanned"], "2")
        self.assertEqual(row["next_clicks"], "1")

    def test_source_scan_report_marks_unknown_without_amazon_total(self) -> None:
        source = Source(
            source_name="Store",
            source_type="seller",
            category="Mugs",
            url="https://www.amazon.com/s?me=A123",
            priority=1,
            active=True,
            row_number=1,
        )

        row = build_source_scan_report_row(
            source,
            [
                FetchedPage(
                    html="<html><body>No result total</body></html>",
                    url="https://www.amazon.com/s?me=A123",
                    page_number=1,
                    product_asins=("B0ONLY1111",),
                )
            ],
            [{"asin": "B0ONLY1111"}],
            max_pages=3,
            elapsed_seconds=0.25,
        )

        self.assertEqual(row["raw_total_text"], "")
        self.assertEqual(row["expected_products"], "")
        self.assertEqual(row["expected_top_products"], "48")
        self.assertEqual(row["top_page_coverage"], "")
        self.assertEqual(row["full_coverage"], "")
        self.assertEqual(row["status"], "UNKNOWN")

    def test_scan_offline_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_csv = root / "sources.csv"
            html_dir = root / "html"
            output_dir = root / "output"
            snapshot_dir = root / "data" / "snapshots"
            master_snapshot_path = root / "data" / "master_snapshot.csv"
            html_dir.mkdir()
            image_source = root / "source-image.jpg"
            image_source.write_bytes(b"fake-jpeg")
            image_uri = image_source.as_uri()

            source_csv.write_text(
                "\n".join(
                    [
                        "source_name,source_type,category,url,priority,active",
                        "Competitor Store 1,seller,LASFOUR (Warrior),https://www.amazon.com/s?me=A123,1,yes",
                    ]
                ),
                encoding="utf-8",
            )
            (html_dir / "competitor-store-1.html").write_text(
                f"""
                <span>1-1 of 1 results</span>
                <div data-component-type="s-search-result" data-asin="B0TEST1111">
                  <a href="/dp/B0TEST1111"><h2><span>Personalized Mug</span></h2></a>
                  <img class="s-image" data-image-latency="s-product-image" src="{image_uri}" />
                  <span class="a-offscreen">$18.99</span>
                  <span aria-label="4.6 out of 5 stars">4.6 out of 5 stars</span>
                  <span>47 ratings</span>
                </div>
                """,
                encoding="utf-8",
            )

            exit_code = main(
                [
                    "scan",
                    "--sources",
                    str(source_csv),
                    "--html-dir",
                    str(html_dir),
                    "--offline",
                    "--output",
                    str(output_dir),
                    "--snapshot-dir",
                    str(snapshot_dir),
                    "--master-snapshot",
                    str(master_snapshot_path),
                ]
            )

            with (output_dir / "latest_products.csv").open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                latest_fields = reader.fieldnames or []
                rows = list(reader)
            with (output_dir / "today_snapshot.csv").open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                today_fields = reader.fieldnames or []
                today_rows = list(reader)
            with (output_dir / "rank_trends.csv").open("r", encoding="utf-8-sig", newline="") as handle:
                trend_rows = list(csv.DictReader(handle))
            with (output_dir / "product_trends.csv").open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                product_trend_fields = reader.fieldnames or []
                product_trend_rows = list(reader)
            with (output_dir / "historical_comparison.csv").open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                comparison_fields = reader.fieldnames or []
                comparison_rows = list(reader)
            with (output_dir / "rank_audit.csv").open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                rank_audit_fields = reader.fieldnames or []
                rank_audit_rows = list(reader)
            with (output_dir / "trend_alerts.csv").open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                alert_fields = reader.fieldnames or []
                alert_rows = list(reader)
            with (output_dir / "lark_trend_alerts.csv").open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                lark_alert_fields = reader.fieldnames or []
                lark_alert_rows = list(reader)
            with (output_dir / "source_trends.csv").open("r", encoding="utf-8-sig", newline="") as handle:
                source_trend_rows = list(csv.DictReader(handle))
            with (output_dir / "source_scan_report.csv").open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                source_scan_report_fields = reader.fieldnames or []
                source_scan_report_rows = list(reader)
            with (output_dir / "seller_intelligence.csv").open("r", encoding="utf-8-sig", newline="") as handle:
                seller_rows = list(csv.DictReader(handle))
            with (output_dir / "niche_intelligence.csv").open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                niche_fields = reader.fieldnames or []
                niche_rows = list(reader)
            image_gallery_path = output_dir / "image_gallery.html"
            index_path = output_dir / "index.html"
            priority_board_path = output_dir / "priority_board.html"
            priority_board_csv_path = output_dir / "priority_board.csv"
            products_page_path = output_dir / "products.html"
            top_winners_path = output_dir / "top_winners.html"
            new_breakouts_path = output_dir / "new_breakouts.html"
            fast_movers_path = output_dir / "fast_movers.html"
            new_releases_path = output_dir / "new_releases.html"
            trends_page_path = output_dir / "trends.html"
            database_page_path = output_dir / "database.html"
            top_opportunities_path = output_dir / "top_opportunities.html"
            all_opportunities_path = output_dir / "all_opportunities.html"
            new_products_path = output_dir / "new_products.html"
            rising_products_path = output_dir / "rising_products.html"
            seller_intelligence_page_path = output_dir / "seller_intelligence.html"
            niche_intelligence_page_path = output_dir / "niche_intelligence.html"
            source_explorer_path = output_dir / "source_explorer.html"
            non_pod_excluded_path = output_dir / "non_pod_excluded.html"
            local_image_exists = (output_dir / "images" / "B0TEST1111.jpg").exists()
            index_exists = index_path.exists()
            priority_board_exists = priority_board_path.exists()
            priority_board_csv_exists = priority_board_csv_path.exists()
            products_page_exists = products_page_path.exists()
            top_winners_exists = top_winners_path.exists()
            new_breakouts_exists = new_breakouts_path.exists()
            fast_movers_exists = fast_movers_path.exists()
            new_releases_exists = new_releases_path.exists()
            trends_page_exists = trends_page_path.exists()
            database_page_exists = database_page_path.exists()
            image_gallery_exists = image_gallery_path.exists()
            top_opportunities_exists = top_opportunities_path.exists()
            all_opportunities_exists = all_opportunities_path.exists()
            new_products_exists = new_products_path.exists()
            rising_products_exists = rising_products_path.exists()
            seller_intelligence_page_exists = seller_intelligence_page_path.exists()
            niche_intelligence_page_exists = niche_intelligence_page_path.exists()
            source_explorer_exists = source_explorer_path.exists()
            non_pod_excluded_exists = non_pod_excluded_path.exists()
            index_html = index_path.read_text(encoding="utf-8")
            priority_board_html = priority_board_path.read_text(encoding="utf-8")
            image_gallery_html = image_gallery_path.read_text(encoding="utf-8")
            top_opportunities_html = top_opportunities_path.read_text(encoding="utf-8")
            seller_intelligence_page_html = seller_intelligence_page_path.read_text(encoding="utf-8")
            niche_intelligence_page_html = niche_intelligence_page_path.read_text(encoding="utf-8")
            source_explorer_html = source_explorer_path.read_text(encoding="utf-8")
            with master_snapshot_path.open("r", encoding="utf-8-sig", newline="") as handle:
                master_rows = list(csv.DictReader(handle))
            snapshot_paths = list(snapshot_dir.glob("*_snapshot.csv"))
            workbook_path = output_dir / "daily_market_spy_report.xlsx"
            workbook_exists = workbook_path.exists()
            with ZipFile(workbook_path) as workbook:
                workbook_xml = workbook.read("xl/workbook.xml").decode("utf-8")
                seller_sheet_xml = workbook.read("xl/worksheets/sheet6.xml").decode("utf-8")
                niche_sheet_xml = workbook.read("xl/worksheets/sheet7.xml").decode("utf-8")
                raw_sheet_xml = workbook.read("xl/worksheets/sheet8.xml").decode("utf-8")

        self.assertEqual(exit_code, 0)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(today_rows), 1)
        self.assertEqual(
            source_scan_report_fields,
            [
                "source_name",
                "source_type",
                "raw_total_text",
                "max_pages",
                "expected_products",
                "expected_top_products",
                "collected_products",
                "top_page_coverage",
                "full_coverage",
                "status",
                "pages_scanned",
                "next_clicks",
                "duplicates",
                "filtered",
                "elapsed_seconds",
                "final_url",
                "stop_reason",
            ],
        )
        self.assertEqual(len(source_scan_report_rows), 1)
        self.assertEqual(source_scan_report_rows[0]["source_name"], "LASFOUR (Warrior)")
        self.assertEqual(source_scan_report_rows[0]["source_type"], "seller")
        self.assertEqual(source_scan_report_rows[0]["raw_total_text"], "1-1 of 1 results")
        self.assertEqual(source_scan_report_rows[0]["max_pages"], "3")
        self.assertEqual(source_scan_report_rows[0]["expected_products"], "1")
        self.assertEqual(source_scan_report_rows[0]["expected_top_products"], "1")
        self.assertEqual(source_scan_report_rows[0]["collected_products"], "1")
        self.assertEqual(source_scan_report_rows[0]["top_page_coverage"], "100.00%")
        self.assertEqual(source_scan_report_rows[0]["full_coverage"], "100.00%")
        self.assertEqual(source_scan_report_rows[0]["status"], "OK")
        self.assertEqual(source_scan_report_rows[0]["pages_scanned"], "1")
        self.assertEqual(source_scan_report_rows[0]["next_clicks"], "0")
        self.assertEqual(source_scan_report_rows[0]["final_url"], "https://www.amazon.com/s?me=A123")
        self.assertEqual(latest_fields[latest_fields.index("asin") + 1], "is_pod")
        self.assertIn("niche_primary", latest_fields)
        self.assertEqual(
            rank_audit_fields,
            [
                "asin",
                "title",
                "product_url",
                "display_rank",
                "source_name",
                "primary_bsr_rank",
                "primary_bsr_category",
                "sub_bsr_rank",
                "sub_bsr_category",
                "category_ranks_raw",
                "raw_bsr_block",
                "rank_extracted_at",
                "rank_parse_method",
                "rank_parse_confidence",
                "rank_parse_warning",
                "accordion_found",
                "accordion_expanded",
                "bsr_visible_after_expand",
            ],
        )
        self.assertEqual(len(rank_audit_rows), 1)
        self.assertIn("niche_tags", latest_fields)
        self.assertIn("raw_title", latest_fields)
        self.assertIn("title_source", latest_fields)
        self.assertIn("title_fixed", latest_fields)
        self.assertIn("image_source", latest_fields)
        self.assertIn("image_fixed", latest_fields)
        self.assertIn("bsr_rank", latest_fields)
        self.assertIn("bsr_category", latest_fields)
        self.assertIn("category_ranks_raw", latest_fields)
        self.assertIn("primary_bsr_rank", latest_fields)
        self.assertIn("sub_bsr_rank", latest_fields)
        self.assertIn("all_bsr_ranks", latest_fields)
        self.assertIn("subcategory_rank_score", latest_fields)
        self.assertIn("products_in_source", latest_fields)
        self.assertIn("previous_display_rank", latest_fields)
        self.assertIn("display_rank_change", latest_fields)
        self.assertIn("display_rank_velocity", latest_fields)
        self.assertIn("display_percentile", latest_fields)
        self.assertEqual(today_fields[today_fields.index("asin") + 1], "is_pod")
        self.assertIn("niche_primary", today_fields)
        self.assertIn("bsr_rank", today_fields)
        self.assertIn("sub_bsr_rank", today_fields)
        self.assertEqual(rows[0]["asin"], "B0TEST1111")
        self.assertEqual(rows[0]["raw_title"], "Personalized Mug")
        self.assertEqual(rows[0]["title_source"], "listing_card")
        self.assertEqual(rows[0]["title_fixed"], "false")
        self.assertEqual(rows[0]["image_source"], "listing_card")
        self.assertEqual(rows[0]["image_fixed"], "false")
        self.assertEqual(rows[0]["is_pod"], "yes")
        self.assertEqual(rows[0]["pod_type"], "personalized_mug")
        self.assertEqual(rows[0]["niche_primary"], "Personalized Mug")
        self.assertEqual(rows[0]["niche_tags"], "Personalized Mug")
        self.assertEqual(rows[0]["bsr_rank"], "")
        self.assertEqual(rows[0]["bsr_category"], "")
        self.assertEqual(rows[0]["category_ranks_raw"], "")
        self.assertEqual(rows[0]["primary_bsr_rank"], "")
        self.assertEqual(rows[0]["primary_bsr_category"], "")
        self.assertEqual(rows[0]["sub_bsr_rank"], "")
        self.assertEqual(rows[0]["sub_bsr_category"], "")
        self.assertEqual(rows[0]["all_bsr_ranks"], "")
        self.assertEqual(rows[0]["subcategory_rank_score"], "")
        self.assertEqual(rows[0]["source_name"], "LASFOUR (Warrior)")
        self.assertEqual(rows[0]["seller_name"], "LASFOUR (Warrior)")
        self.assertEqual(rows[0]["seller_id"], "A123")
        self.assertEqual(rows[0]["seller_url"], "https://www.amazon.com/s?me=A123")
        self.assertEqual(rows[0]["display_rank"], "1")
        self.assertEqual(rows[0]["display_order"], "1")
        self.assertEqual(rows[0]["products_in_source"], "1")
        self.assertEqual(rows[0]["previous_display_rank"], "")
        self.assertEqual(rows[0]["display_rank_change"], "")
        self.assertEqual(rows[0]["display_percentile"], "100.00")
        self.assertEqual(rows[0]["rank"], "1")
        self.assertEqual(rows[0]["price"], "18.99")
        self.assertEqual(rows[0]["review_count"], "47")
        self.assertEqual(rows[0]["review_rating"], "4.6")
        self.assertEqual(today_rows[0]["image_url"], image_uri)
        self.assertEqual(today_rows[0]["review_count"], "47")
        self.assertEqual(today_rows[0]["review_rating"], "4.6")
        self.assertEqual(len(trend_rows), 1)
        self.assertEqual(trend_rows[0]["asin"], "B0TEST1111")
        self.assertEqual(trend_rows[0]["source_name"], "LASFOUR (Warrior)")
        self.assertEqual(trend_rows[0]["seller_name"], "LASFOUR (Warrior)")
        self.assertEqual(trend_rows[0]["image_url"], image_uri)
        self.assertEqual(len(product_trend_rows), 1)
        self.assertEqual(product_trend_fields[product_trend_fields.index("asin") + 1], "image_url")
        self.assertIn("niche_primary", product_trend_fields)
        self.assertIn("raw_title", product_trend_fields)
        self.assertIn("image_source", product_trend_fields)
        self.assertIn("bsr_rank", product_trend_fields)
        self.assertIn("sub_bsr_rank", product_trend_fields)
        self.assertEqual(product_trend_rows[0]["image_url"], image_uri)
        self.assertEqual(product_trend_rows[0]["raw_title"], "Personalized Mug")
        self.assertEqual(product_trend_rows[0]["title_source"], "listing_card")
        self.assertEqual(product_trend_rows[0]["image_source"], "listing_card")
        self.assertEqual(product_trend_rows[0]["source_name"], "LASFOUR (Warrior)")
        self.assertEqual(product_trend_rows[0]["seller_name"], "LASFOUR (Warrior)")
        self.assertEqual(product_trend_rows[0]["review_count"], "47")
        self.assertEqual(product_trend_rows[0]["review_rating"], "4.6")
        self.assertEqual(product_trend_rows[0]["review_growth_7d"], "0")
        self.assertEqual(product_trend_rows[0]["review_growth_30d"], "0")
        self.assertEqual(product_trend_rows[0]["review_velocity_score"], "0")
        self.assertEqual(len(comparison_rows), 1)
        self.assertEqual(comparison_fields[comparison_fields.index("asin") + 1], "is_pod")
        self.assertIn("niche_primary", comparison_fields)
        self.assertIn("raw_title", comparison_fields)
        self.assertIn("image_source", comparison_fields)
        self.assertIn("bsr_rank", comparison_fields)
        self.assertIn("sub_bsr_rank", comparison_fields)
        self.assertIn("products_in_source", comparison_fields)
        self.assertIn("display_rank_change", comparison_fields)
        self.assertEqual(alert_fields[alert_fields.index("asin") + 1], "is_pod")
        self.assertIn("niche_primary", alert_fields)
        self.assertIn("raw_title", alert_fields)
        self.assertIn("image_source", alert_fields)
        self.assertIn("bsr_rank", alert_fields)
        self.assertIn("sub_bsr_rank", alert_fields)
        self.assertEqual(comparison_rows[0]["image_url"], image_uri)
        self.assertEqual(comparison_rows[0]["raw_title"], "Personalized Mug")
        self.assertEqual(comparison_rows[0]["title_source"], "listing_card")
        self.assertEqual(comparison_rows[0]["image_source"], "listing_card")
        self.assertEqual(comparison_rows[0]["is_pod"], "yes")
        self.assertEqual(comparison_rows[0]["niche_primary"], "Personalized Mug")
        self.assertEqual(comparison_rows[0]["niche_tags"], "Personalized Mug")
        self.assertEqual(comparison_rows[0]["source_name"], "LASFOUR (Warrior)")
        self.assertEqual(comparison_rows[0]["seller_name"], "LASFOUR (Warrior)")
        self.assertEqual(comparison_rows[0]["review_count"], "47")
        self.assertEqual(comparison_rows[0]["review_rating"], "4.6")
        self.assertEqual(comparison_rows[0]["review_growth_7d"], "0")
        self.assertEqual(comparison_rows[0]["review_growth_30d"], "0")
        self.assertEqual(comparison_rows[0]["review_velocity_score"], "0")
        self.assertEqual(comparison_rows[0]["historical_status"], "new_vs_history")
        self.assertEqual(comparison_rows[0]["opportunity_score"], "60")
        self.assertEqual(comparison_rows[0]["pod_component"], "16")
        self.assertEqual(comparison_rows[0]["momentum_component"], "12")
        self.assertEqual(comparison_rows[0]["market_component"], "17")
        self.assertEqual(comparison_rows[0]["competition_component"], "6")
        self.assertEqual(comparison_rows[0]["niche_component"], "15")
        self.assertEqual(comparison_rows[0]["display_strength"], "85")
        self.assertEqual(comparison_rows[0]["rank_strength"], "")
        self.assertEqual(comparison_rows[0]["display_momentum"], "50")
        self.assertEqual(comparison_rows[0]["rank_momentum"], "")
        self.assertEqual(comparison_rows[0]["validation_score"], "84")
        self.assertEqual(comparison_rows[0]["momentum_score"], "50")
        self.assertEqual(comparison_rows[0]["stability_score"], "45")
        self.assertEqual(comparison_rows[0]["freshness_score"], "100")
        self.assertEqual(comparison_rows[0]["research_segment"], "Watchlist")
        self.assertEqual(len(alert_rows), 0)
        self.assertEqual(len(lark_alert_rows), 0)
        self.assertEqual(
            lark_alert_fields,
            [
                "date",
                "alert_type",
                "priority",
                "opportunity_score",
                "pod_component",
                "momentum_component",
                "market_component",
                "competition_component",
                "niche_component",
                "display_strength",
                "rank_strength",
                "display_momentum",
                "rank_momentum",
                "validation_score",
                "momentum_score",
                "stability_score",
                "freshness_score",
                "validation_confidence",
                "momentum_confidence",
                "stability_confidence",
                "research_segment",
                "score_reason",
                "products_in_source",
                "previous_display_rank",
                "display_rank_change",
                "display_rank_pct_change",
                "display_rank_velocity",
                "display_percentile",
                "asin",
                "is_pod",
                "production_model",
                "production_confidence",
                "production_reason",
                "pod_type",
                "pod_score",
                "pod_confidence",
                "pod_reason",
                "pod_relevance",
                "pod_relevance_reasons",
                "seller_leader",
                "seller_mover",
                "seller_new_push",
                "category_winner",
                "category_breakout",
                "category_stable",
                "new_release_rising",
                "new_release_breakout",
                "new_release_watch",
                "bsr_available",
                "strong_sub_bsr",
                "very_strong_sub_bsr",
                "evidence_labels",
                "evidence_count",
                "evidence_reasons",
                "seller_evidence_leader",
                "seller_evidence_mover",
                "seller_evidence_new_push",
                "seller_evidence_best_rank",
                "seller_evidence_source_count",
                "best_seller_evidence_winner",
                "best_seller_evidence_breakout",
                "best_seller_evidence_stable",
                "best_seller_evidence_best_rank",
                "best_seller_evidence_source_count",
                "new_release_evidence_rising",
                "new_release_evidence_breakout",
                "new_release_evidence_watch",
                "new_release_evidence_best_rank",
                "new_release_evidence_source_count",
                "bsr_evidence_available",
                "bsr_evidence_strong",
                "bsr_evidence_very_strong",
                "bsr_evidence_best_sub_bsr",
                "bsr_evidence_best_sub_bsr_category",
                "evidence_source_family_count",
                "evidence_source_families",
                "niche_primary",
                "niche_secondary",
                "niche_tags",
                "niche_score",
                "niche_reason",
                "bsr_rank",
                "bsr_category",
                "category_ranks_raw",
                "raw_bsr_block",
                "primary_bsr_rank",
                "primary_bsr_category",
                "sub_bsr_rank",
                "sub_bsr_category",
                "all_bsr_ranks",
                "subcategory_rank_score",
                "rank_extracted_at",
                "rank_source_url",
                "rank_page_status",
                "rank_parse_method",
                "rank_parse_confidence",
                "rank_parse_warning",
                "accordion_found",
                "accordion_expanded",
                "bsr_visible_after_expand",
                "image_url",
                "image_source",
                "image_fixed",
                "local_image_path",
                "review_count",
                "review_rating",
                "review_growth_7d",
                "review_growth_30d",
                "review_velocity_score",
                "title",
                "raw_title",
                "title_source",
                "title_fixed",
                "detail_fetched_reason",
                "detail_page_status",
                "detail_title_found",
                "detail_image_found",
                "detail_error",
                "detail_bsr_found",
                "detail_bsr_error",
                "source_name",
                "source_type",
                "source_id",
                "source_rank",
                "marketplace",
                "category_id",
                "category_name",
                "source_identity_method",
                "source_identity_evidence",
                "legacy_source_type",
                "rank_rejected_reason",
                "source_duplicate_count",
                "previous_source_rank",
                "source_rank_change",
                "source_observation_count",
                "source_days_seen",
                "seller_name",
                "seller_id",
                "seller_url",
                "category",
                "today_rank",
                "previous_rank",
                "rank_change",
                "rank_direction",
                "first_seen",
                "days_seen",
                "product_url",
                "suggested_action",
                "status",
                "owner",
                "note",
            ],
        )
        self.assertEqual(lark_alert_fields[lark_alert_fields.index("asin") + 1], "is_pod")
        self.assertIn("niche_primary", lark_alert_fields)
        self.assertIn("raw_title", lark_alert_fields)
        self.assertIn("image_source", lark_alert_fields)
        self.assertIn("bsr_rank", lark_alert_fields)
        self.assertIn("sub_bsr_rank", lark_alert_fields)
        self.assertIn("pod_component", lark_alert_fields)
        self.assertIn("momentum_component", lark_alert_fields)
        self.assertIn("market_component", lark_alert_fields)
        self.assertIn("competition_component", lark_alert_fields)
        self.assertIn("niche_component", lark_alert_fields)
        self.assertFalse(local_image_exists)
        self.assertTrue(index_exists)
        self.assertTrue(priority_board_exists)
        self.assertTrue(priority_board_csv_exists)
        self.assertTrue(products_page_exists)
        self.assertTrue(top_winners_exists)
        self.assertTrue(new_breakouts_exists)
        self.assertTrue(fast_movers_exists)
        self.assertTrue(new_releases_exists)
        self.assertTrue(trends_page_exists)
        self.assertTrue(database_page_exists)
        self.assertTrue(image_gallery_exists)
        self.assertTrue(top_opportunities_exists)
        self.assertTrue(all_opportunities_exists)
        self.assertTrue(new_products_exists)
        self.assertTrue(rising_products_exists)
        self.assertTrue(seller_intelligence_page_exists)
        self.assertTrue(niche_intelligence_page_exists)
        self.assertTrue(source_explorer_exists)
        self.assertTrue(non_pod_excluded_exists)
        self.assertEqual(index_html, priority_board_html)
        self.assertIn("Today", priority_board_html)
        self.assertIn("New Winners", priority_board_html)
        self.assertIn("Fast Rising", priority_board_html)
        self.assertIn("Competitor Launches", priority_board_html)
        self.assertIn("Emerging Trends", priority_board_html)
        self.assertIn("product_discovery.html", image_gallery_html)
        self.assertIn("product_discovery.html", top_opportunities_html)
        self.assertNotIn("<span>Category Rank:</span>", top_opportunities_html)
        self.assertNotIn("<span>Subcategory Rank:</span>", top_opportunities_html)
        self.assertIn("New Launches", seller_intelligence_page_html)
        self.assertIn("Current Top10", seller_intelligence_page_html)
        self.assertIn("trend_explorer.html", niche_intelligence_page_html)
        self.assertIn("competitor.html", source_explorer_html)
        self.assertEqual(len(source_trend_rows), 1)
        self.assertEqual(source_trend_rows[0]["source_name"], "LASFOUR (Warrior)")
        self.assertEqual(source_trend_rows[0]["seller_name"], "LASFOUR (Warrior)")
        self.assertEqual(source_trend_rows[0]["seller_id"], "A123")
        self.assertEqual(source_trend_rows[0]["seller_url"], "https://www.amazon.com/s?me=A123")
        self.assertEqual(len(seller_rows), 1)
        self.assertEqual(seller_rows[0]["seller_name"], "LASFOUR (Warrior)")
        self.assertEqual(seller_rows[0]["seller_id"], "A123")
        self.assertEqual(seller_rows[0]["seller_url"], "https://www.amazon.com/s?me=A123")
        self.assertEqual(seller_rows[0]["source_name"], "LASFOUR (Warrior)")
        self.assertEqual(seller_rows[0]["source_type"], "seller")
        self.assertEqual(seller_rows[0]["seller"], "LASFOUR (Warrior)")
        self.assertEqual(seller_rows[0]["products_tracked"], "1")
        self.assertEqual(seller_rows[0]["average_rank"], "1.00")
        self.assertEqual(seller_rows[0]["review_growth_7d"], "0")
        self.assertEqual(seller_rows[0]["review_growth_30d"], "0")
        self.assertEqual(seller_rows[0]["review_velocity_score"], "0")
        self.assertEqual(seller_rows[0]["momentum_score"], "60")
        self.assertEqual(seller_rows[0]["pod_products"], "1")
        self.assertEqual(seller_rows[0]["pod_opportunities"], "0")
        self.assertEqual(seller_rows[0]["pod_momentum_score"], "60")
        self.assertEqual(seller_rows[0]["top_niche"], "Personalized Mug")
        self.assertEqual(seller_rows[0]["niche_count"], "1")
        self.assertEqual(seller_rows[0]["best_subcategory_rank"], "")
        self.assertEqual(seller_rows[0]["best_subcategory_product"], "")
        self.assertIn("niche", niche_fields)
        self.assertIn("niche_momentum_score", niche_fields)
        self.assertIn("best_subcategory_rank", niche_fields)
        self.assertEqual(len(niche_rows), 1)
        self.assertEqual(niche_rows[0]["niche"], "Personalized Mug")
        self.assertEqual(niche_rows[0]["niche_group"], "product")
        self.assertEqual(niche_rows[0]["products_tracked"], "1")
        self.assertEqual(niche_rows[0]["pod_products"], "1")
        self.assertEqual(niche_rows[0]["opportunities"], "0")
        self.assertEqual(niche_rows[0]["top_seller"], "LASFOUR (Warrior)")
        self.assertEqual(niche_rows[0]["top_product_asin"], "B0TEST1111")
        self.assertEqual(niche_rows[0]["top_product_title"], "Personalized Mug")
        self.assertEqual(niche_rows[0]["best_subcategory_rank"], "")
        self.assertEqual(niche_rows[0]["best_subcategory_product"], "")
        self.assertEqual(len(master_rows), 1)
        self.assertEqual(master_rows[0]["asin"], "B0TEST1111")
        self.assertEqual(master_rows[0]["seller_name"], "LASFOUR (Warrior)")
        self.assertEqual(len(snapshot_paths), 1)
        self.assertRegex(snapshot_paths[0].name, r"^\d{4}-\d{2}-\d{2}_snapshot\.csv$")
        self.assertTrue(workbook_exists)
        self.assertIn("Executive Summary", workbook_xml)
        self.assertIn("New Wins", workbook_xml)
        self.assertIn("Winners", workbook_xml)
        self.assertIn("Rising", workbook_xml)
        self.assertIn("Declining", workbook_xml)
        self.assertIn("Seller Intelligence", workbook_xml)
        self.assertIn("Niche Intelligence", workbook_xml)
        self.assertIn("Raw Snapshot", workbook_xml)
        self.assertIn("LASFOUR (Warrior)", seller_sheet_xml)
        self.assertIn("Personalized Mug", niche_sheet_xml)
        self.assertIn("LASFOUR (Warrior)", raw_sheet_xml)

    def test_scan_offline_respects_max_products(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_csv = root / "sources.csv"
            html_dir = root / "html"
            output_dir = root / "output"
            snapshot_dir = root / "data" / "snapshots"
            master_snapshot_path = root / "data" / "master_snapshot.csv"
            html_dir.mkdir()

            source_csv.write_text(
                "\n".join(
                    [
                        "source_name,source_type,category,url,priority,active",
                        "Competitor Store 1,seller,LASFOUR (Warrior),https://www.amazon.com/s?me=A123,1,yes",
                    ]
                ),
                encoding="utf-8",
            )
            (html_dir / "competitor-store-1.html").write_text(
                """
                <div data-component-type="s-search-result" data-asin="B0FIRST111">
                  <a href="/dp/B0FIRST111"><h2><span>First Personalized Mug</span></h2></a>
                </div>
                <div data-component-type="s-search-result" data-asin="B0SECOND22">
                  <a href="/dp/B0SECOND22"><h2><span>Second Personalized Mug</span></h2></a>
                </div>
                """,
                encoding="utf-8",
            )

            exit_code = main(
                [
                    "scan",
                    "--sources",
                    str(source_csv),
                    "--html-dir",
                    str(html_dir),
                    "--offline",
                    "--output",
                    str(output_dir),
                    "--snapshot-dir",
                    str(snapshot_dir),
                    "--master-snapshot",
                    str(master_snapshot_path),
                    "--max-products",
                    "1",
                ]
            )

            with (output_dir / "latest_products.csv").open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))

        self.assertEqual(exit_code, 0)
        self.assertEqual([row["asin"] for row in rows], ["B0FIRST111"])


if __name__ == "__main__":
    unittest.main()
