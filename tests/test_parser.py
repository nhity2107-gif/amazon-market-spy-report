from __future__ import annotations

import unittest

from amazon_market_spy.models import Source
from amazon_market_spy.parser import parse_amazon_search_results


class ParserTests(unittest.TestCase):
    def test_parse_search_tiles(self) -> None:
        source = Source(
            source_name="Competitor Store 1",
            source_type="seller",
            category="Mugs",
            url="https://www.amazon.com/s?me=A123",
            priority=1,
            active=True,
            row_number=1,
        )
        html = """
        <div data-component-type="s-search-result" data-asin="B0TEST1111">
          <a href="/Personalized-Mug/dp/B0TEST1111/ref=sr_1_1">
            <h2><span>Personalized Dog Mom Mug</span></h2>
          </a>
          <img src="https://example.com/tracker.gif" />
          <img class="s-image" data-image-latency="s-product-image" src="https://example.com/high-quality-mug.jpg" />
          <span class="a-offscreen">$18.99</span>
          <span aria-label="4.7 out of 5 stars">4.7 out of 5 stars</span>
          <span>1,234 ratings</span>
          <span>500+ bought in past month</span>
        </div>
        <div data-component-type="s-search-result" data-asin="B0TEST2222">
          <h2 aria-label="Custom Cat Dad Coffee Cup"></h2>
          <a href="/dp/B0TEST2222"></a>
          <span class="a-offscreen">$21.50</span>
          <span>Sponsored</span>
        </div>
        """

        rows = parse_amazon_search_results(html, source, "2026-06-11T00:00:00+00:00")

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["date"], "2026-06-11")
        self.assertEqual(rows[0]["asin"], "B0TEST1111")
        self.assertEqual([row["asin"] for row in rows], ["B0TEST1111", "B0TEST2222"])
        self.assertEqual([row["display_rank"] for row in rows], ["1", "2"])
        self.assertEqual([row["display_order"] for row in rows], ["1", "2"])
        self.assertEqual(rows[0]["title"], "Personalized Dog Mom Mug")
        self.assertEqual(rows[0]["price"], "18.99")
        self.assertEqual(rows[0]["rating"], "4.7")
        self.assertEqual(rows[0]["review_count"], "1234")
        self.assertEqual(rows[0]["review_rating"], "4.7")
        self.assertEqual(rows[0]["bought_past_month"], "500")
        self.assertEqual(rows[0]["image_url"], "https://example.com/high-quality-mug.jpg")
        self.assertEqual(rows[0]["bsr_rank"], "")
        self.assertEqual(rows[0]["bsr_category"], "")
        self.assertEqual(rows[0]["category_ranks_raw"], "")
        self.assertEqual(rows[0]["primary_bsr_rank"], "")
        self.assertEqual(rows[0]["sub_bsr_rank"], "")
        self.assertEqual(rows[0]["all_bsr_ranks"], "")
        self.assertEqual(rows[0]["subcategory_rank_score"], "")
        self.assertEqual(rows[0]["is_pod"], "yes")
        self.assertEqual(rows[0]["pod_type"], "personalized_mug")
        self.assertGreaterEqual(int(rows[0]["pod_score"]), 40)
        self.assertEqual(rows[0]["niche_primary"], "Dog Mom")
        self.assertIn("Personalized Mug", rows[0]["niche_tags"])
        self.assertEqual(rows[1]["sponsored"], "yes")

    def test_parse_rank_page_links_without_data_asin(self) -> None:
        source = Source(
            source_name="Amazon Best Sellers",
            source_type="best_seller",
            category="Mugs",
            url="https://www.amazon.com/Best-Sellers-Kitchen/zgbs/kitchen",
            priority=1,
            active=True,
            row_number=1,
        )
        html = """
        <ol>
          <li>
            <span>#1</span>
            <a href="/Best-Seller-Mug/dp/B0BEST1111/ref=zg_bs_1">
              <img alt="Best Seller Coffee Mug" data-image-latency="s-product-image" src="one.jpg" />
            </a>
            <span class="a-offscreen">$19.99</span>
            <span aria-label="4.8 out of 5 stars"></span>
            <span>321 ratings</span>
          </li>
          <li>
            <span>#2</span>
            <a href="/New-Release-Cup/dp/B0BEST2222/ref=zg_bs_2">New Release Cup</a>
            <span class="a-offscreen">$22.00</span>
          </li>
        </ol>
        """

        rows = parse_amazon_search_results(html, source, "2026-06-11T00:00:00+00:00")

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["asin"], "B0BEST1111")
        self.assertEqual([row["asin"] for row in rows], ["B0BEST1111", "B0BEST2222"])
        self.assertEqual([row["display_rank"] for row in rows], ["1", "2"])
        self.assertEqual([row["display_order"] for row in rows], ["1", "2"])
        self.assertEqual(rows[0]["rank"], "1")
        self.assertEqual(rows[0]["page_type"], "best_seller")
        self.assertEqual(rows[0]["title"], "Best Seller Coffee Mug")
        self.assertEqual(rows[0]["image_url"], "one.jpg")
        self.assertEqual(rows[0]["price"], "19.99")
        self.assertEqual(rows[0]["review_count"], "321")
        self.assertEqual(rows[0]["review_rating"], "4.8")
        self.assertEqual(rows[1]["rank"], "2")

    def test_listing_title_extraction_ignores_variation_swatches(self) -> None:
        source = Source(
            source_name="Competitor Store 1",
            source_type="seller",
            category="Mugs",
            url="https://www.amazon.com/s?me=A123",
            priority=1,
            active=True,
            row_number=1,
        )
        html = """
        <div data-component-type="s-search-result" data-asin="B0SWATCH11">
          <a href="/dp/B0SWATCH11">
            <h2>
              <span>Personalized Dad Coffee Mug Custom Father's Day Gift</span>
            </h2>
          </a>
          <div class="a-section">
            <span>Gift Idea 1</span>
            <span>A1</span>
            <span>Blue</span>
          </div>
          <img class="s-image" src="https://example.com/mug.jpg" alt="A1">
        </div>
        """

        rows = parse_amazon_search_results(html, source, "2026-06-11T00:00:00+00:00")

        self.assertEqual(rows[0]["title"], "Personalized Dad Coffee Mug Custom Father's Day Gift")
        self.assertEqual(rows[0]["raw_title"], "Personalized Dad Coffee Mug Custom Father's Day Gift")
        self.assertEqual(rows[0]["title_source"], "listing_card")
        self.assertEqual(rows[0]["title_fixed"], "false")
        self.assertEqual(rows[0]["image_source"], "listing_card")
        self.assertEqual(rows[0]["image_fixed"], "false")

    def test_listing_title_uses_line_clamp_selector_before_image_alt(self) -> None:
        source = Source(
            source_name="Competitor Store 1",
            source_type="seller",
            category="Mugs",
            url="https://www.amazon.com/s?me=A123",
            priority=1,
            active=True,
            row_number=1,
        )
        html = """
        <div data-component-type="s-search-result" data-asin="B0CLAMP111">
          <a class="a-link-normal s-line-clamp-2" href="/dp/B0CLAMP111">
            <span>Custom Teacher Appreciation Coffee Mug Personalized Name Gift</span>
          </a>
          <img class="s-image" src="https://example.com/teacher.jpg" alt="Gift Idea 1">
        </div>
        """

        rows = parse_amazon_search_results(html, source, "2026-06-11T00:00:00+00:00")

        self.assertEqual(rows[0]["title"], "Custom Teacher Appreciation Coffee Mug Personalized Name Gift")

    def test_rejects_numeric_data_asin_and_preserves_real_product_asin(self) -> None:
        source = Source(
            source_name="Competitor Store 1",
            source_type="seller",
            category="Mugs",
            url="https://www.amazon.com/s?me=A123",
            priority=1,
            active=True,
            row_number=1,
        )
        html = """
        <div data-component-type="s-search-result" data-asin="1234567890">
          <a href="/Bad-Widget/dp/1234567890/ref=sr_1_1">
            <h2><span>Numeric Widget</span></h2>
          </a>
        </div>
        <div data-component-type="s-search-result" data-asin="9876543210">
          <a href="/Real-Product/dp/B0REAL1111/ref=sr_1_2">
            <h2><span>Real Product</span></h2>
          </a>
        </div>
        """

        rows = parse_amazon_search_results(html, source, "2026-06-11T00:00:00+00:00")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["asin"], "B0REAL1111")
        self.assertEqual(rows[0]["product_url"], "https://www.amazon.com/Real-Product/dp/B0REAL1111/ref=sr_1_2")


if __name__ == "__main__":
    unittest.main()
