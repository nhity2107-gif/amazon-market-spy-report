from __future__ import annotations

import unittest

from amazon_market_spy.category_rank import (
    ensure_category_rank_fields,
    extract_bsr_from_product_page,
    subcategory_rank_score,
)


class CategoryRankTests(unittest.TestCase):
    def test_extracts_multiple_best_sellers_ranks(self) -> None:
        html = """
        <div id="detailBullets_feature_div">
          <span>Best Sellers Rank</span>
          <span>#12 in Handmade Products (See Top 100 in Handmade Products)</span>
          <span>#4 in Coffee Mugs</span>
          <span>#89 in Home & Kitchen</span>
        </div>
        """

        ranks = extract_bsr_from_product_page(html)

        self.assertEqual(ranks["bsr_rank"], "12")
        self.assertEqual(ranks["bsr_category"], "Handmade Products")
        self.assertEqual(ranks["primary_bsr_rank"], "12")
        self.assertEqual(ranks["primary_bsr_category"], "Handmade Products")
        self.assertEqual(ranks["sub_bsr_rank"], "4")
        self.assertEqual(ranks["sub_bsr_category"], "Coffee Mugs")
        self.assertEqual(ranks["subcategory_rank_score"], "100")
        self.assertEqual(
            ranks["category_ranks_raw"],
            "Best Sellers Rank #12 in Handmade Products (See Top 100 in Handmade Products) #4 in Coffee Mugs #89 in Home & Kitchen",
        )
        self.assertEqual(ranks["all_bsr_ranks"], "#12 in Handmade Products; #4 in Coffee Mugs; #89 in Home & Kitchen")
        self.assertEqual(ranks["rank_parse_method"], "detail_bullets")
        self.assertEqual(ranks["rank_parse_confidence"], "high")
        self.assertEqual(ranks["raw_bsr_block"], ranks["category_ranks_raw"])
        self.assertEqual(ranks["rank_parse_warning"], "")
        self.assertTrue(ranks["rank_extracted_at"])

    def test_extracts_primary_and_subcategory_rank(self) -> None:
        html = """
        <div>
          Best Sellers Rank
          #65,003 in Home & Kitchen
          #149 in Decorative Signs & Plaques
        </div>
        """

        ranks = extract_bsr_from_product_page(html)

        self.assertEqual(ranks["primary_bsr_rank"], "65003")
        self.assertEqual(ranks["primary_bsr_category"], "Home & Kitchen")
        self.assertEqual(ranks["sub_bsr_rank"], "149")
        self.assertEqual(ranks["sub_bsr_category"], "Decorative Signs & Plaques")
        self.assertEqual(ranks["all_bsr_ranks"], "#65,003 in Home & Kitchen; #149 in Decorative Signs & Plaques")
        self.assertEqual(ranks["subcategory_rank_score"], "90")
        self.assertEqual(ranks["rank_parse_method"], "text_scan")
        self.assertEqual(ranks["rank_parse_confidence"], "medium")
        self.assertIn("text_scan fallback", ranks["rank_parse_warning"])

    def test_selects_lowest_non_primary_subcategory_rank(self) -> None:
        html = """
        <div id="productDetails_db_sections">
          Best Sellers Rank
          #49,600 in Clothing, Shoes & Jewelry
          #2,873 in Women's Novelty Hoodies
          #91 in Men's Novelty Hoodies
        </div>
        """

        ranks = extract_bsr_from_product_page(html)

        self.assertEqual(ranks["primary_bsr_rank"], "49600")
        self.assertEqual(ranks["primary_bsr_category"], "Clothing, Shoes & Jewelry")
        self.assertEqual(ranks["sub_bsr_rank"], "91")
        self.assertEqual(ranks["sub_bsr_category"], "Men's Novelty Hoodies")
        self.assertEqual(
            ranks["all_bsr_ranks"],
            "#49,600 in Clothing, Shoes & Jewelry; #2,873 in Women's Novelty Hoodies; #91 in Men's Novelty Hoodies",
        )

    def test_returns_blank_fields_when_rank_is_unavailable(self) -> None:
        ranks = extract_bsr_from_product_page("<html><body>No product details here</body></html>")

        self.assertEqual(ranks["bsr_rank"], "")
        self.assertEqual(ranks["bsr_category"], "")
        self.assertEqual(ranks["category_ranks_raw"], "")
        self.assertEqual(ranks["primary_bsr_rank"], "")
        self.assertEqual(ranks["sub_bsr_rank"], "")
        self.assertEqual(ranks["all_bsr_ranks"], "")
        self.assertEqual(ranks["subcategory_rank_score"], "")
        self.assertEqual(ranks["rank_parse_method"], "text_scan")
        self.assertEqual(ranks["rank_parse_confidence"], "low")
        self.assertIn("no BSR block", ranks["rank_parse_warning"])
        self.assertTrue(ranks["rank_extracted_at"])

    def test_strips_commas_from_primary_rank_value(self) -> None:
        html = """
        <table>
          <tr>
            <th>Best Sellers Rank</th>
            <td>#1,234 in Clothing, Shoes & Jewelry (See Top 100 in Clothing, Shoes & Jewelry)</td>
          </tr>
        </table>
        """

        ranks = extract_bsr_from_product_page(html)

        self.assertEqual(ranks["bsr_rank"], "1234")
        self.assertEqual(ranks["bsr_category"], "Clothing, Shoes & Jewelry")
        self.assertEqual(ranks["primary_bsr_rank"], "1234")
        self.assertEqual(ranks["sub_bsr_rank"], "")
        self.assertEqual(
            ranks["category_ranks_raw"],
            "Best Sellers Rank #1,234 in Clothing, Shoes & Jewelry (See Top 100 in Clothing, Shoes & Jewelry)",
        )
        self.assertEqual(ranks["rank_parse_method"], "text_scan")
        self.assertEqual(ranks["rank_parse_confidence"], "medium")

    def test_extracts_rank_from_product_details_section(self) -> None:
        html = """
        <table id="productDetails_detailBullets_sections1">
          <tr>
            <th>Best Sellers Rank</th>
            <td>
              #65,003 in Home & Kitchen
              #149 in Decorative Signs & Plaques
            </td>
          </tr>
        </table>
        """

        ranks = extract_bsr_from_product_page(html)

        self.assertEqual(ranks["primary_bsr_rank"], "65003")
        self.assertEqual(ranks["primary_bsr_category"], "Home & Kitchen")
        self.assertEqual(ranks["sub_bsr_rank"], "149")
        self.assertEqual(ranks["sub_bsr_category"], "Decorative Signs & Plaques")
        self.assertEqual(ranks["rank_parse_method"], "product_details")
        self.assertEqual(ranks["rank_parse_confidence"], "high")

    def test_extracts_rank_from_nested_product_details_section_before_text_scan(self) -> None:
        html = """
        <html>
          <body>
            <div>Sponsored #1 in Unrelated Page Text</div>
            <div id="productDetails_detailBullets_sections1">
              <div>
                <table>
                  <tr>
                    <th>Best Sellers Rank</th>
                    <td>
                      <span>#49,600 in Clothing, Shoes & Jewelry</span>
                      <span>#2,873 in Women's Novelty Hoodies</span>
                    </td>
                  </tr>
                </table>
              </div>
            </div>
          </body>
        </html>
        """

        ranks = extract_bsr_from_product_page(html)

        self.assertEqual(ranks["primary_bsr_rank"], "49600")
        self.assertEqual(ranks["primary_bsr_category"], "Clothing, Shoes & Jewelry")
        self.assertEqual(ranks["sub_bsr_rank"], "2873")
        self.assertEqual(ranks["sub_bsr_category"], "Women's Novelty Hoodies")
        self.assertEqual(ranks["rank_parse_method"], "product_details")
        self.assertEqual(ranks["rank_parse_confidence"], "high")
        self.assertEqual(
            ranks["raw_bsr_block"],
            "Best Sellers Rank #49,600 in Clothing, Shoes & Jewelry #2,873 in Women's Novelty Hoodies",
        )

    def test_extracts_rank_from_product_information_item_details(self) -> None:
        html = """
        <section id="product-information-accordion">
          <h2>Product information</h2>
          <div class="accordion-panel">
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

        ranks = extract_bsr_from_product_page(html)

        self.assertEqual(ranks["primary_bsr_rank"], "24164")
        self.assertEqual(ranks["primary_bsr_category"], "Kitchen & Dining")
        self.assertEqual(ranks["sub_bsr_rank"], "169")
        self.assertEqual(ranks["sub_bsr_category"], "Mugs")
        self.assertEqual(ranks["rank_parse_method"], "product_information_item_details")
        self.assertEqual(ranks["rank_parse_confidence"], "high")
        self.assertEqual(
            ranks["raw_bsr_block"],
            "Best Sellers Rank\n#24,164 in Kitchen & Dining\n#169 in Mugs",
        )

    def test_extracts_sales_rank_text(self) -> None:
        html = """
        <div id="detailBullets_feature_div">
          <span>Sales Rank</span>
          <span>#2,345 in Handmade Products</span>
          <span>#88 in Coffee Mugs</span>
        </div>
        """

        ranks = extract_bsr_from_product_page(html)

        self.assertEqual(ranks["primary_bsr_rank"], "2345")
        self.assertEqual(ranks["primary_bsr_category"], "Handmade Products")
        self.assertEqual(ranks["sub_bsr_rank"], "88")
        self.assertEqual(ranks["sub_bsr_category"], "Coffee Mugs")
        self.assertEqual(ranks["rank_parse_method"], "detail_bullets")

    def test_ensure_category_rank_fields_backfills_old_raw_values(self) -> None:
        row = {
            "bsr_rank": "65003",
            "bsr_category": "Home & Kitchen",
            "category_ranks_raw": "#65,003 in Home & Kitchen; #149 in Decorative Signs & Plaques",
        }

        ensure_category_rank_fields(row)

        self.assertEqual(row["primary_bsr_rank"], "65003")
        self.assertEqual(row["primary_bsr_category"], "Home & Kitchen")
        self.assertEqual(row["sub_bsr_rank"], "149")
        self.assertEqual(row["sub_bsr_category"], "Decorative Signs & Plaques")
        self.assertEqual(row["all_bsr_ranks"], "#65,003 in Home & Kitchen; #149 in Decorative Signs & Plaques")
        self.assertEqual(row["subcategory_rank_score"], "90")

    def test_subcategory_rank_score_bands(self) -> None:
        self.assertEqual(subcategory_rank_score("100"), "100")
        self.assertEqual(subcategory_rank_score("500"), "90")
        self.assertEqual(subcategory_rank_score("1000"), "80")
        self.assertEqual(subcategory_rank_score("5000"), "70")
        self.assertEqual(subcategory_rank_score("10000"), "60")
        self.assertEqual(subcategory_rank_score("10001"), "40")


if __name__ == "__main__":
    unittest.main()
