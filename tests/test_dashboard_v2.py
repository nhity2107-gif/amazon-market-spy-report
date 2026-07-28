from __future__ import annotations

import csv
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from amazon_market_spy.artifacts import write_lark_opportunity_artifacts
from amazon_market_spy.cli import main
from amazon_market_spy.dashboard_v2 import (
    MOCK_PRESENTATION_DATA,
    V2_PAGE_ROUTES,
    generate_dashboard_v2,
    validate_mock_data_contract,
)
from amazon_market_spy.dashboard_v2 import pages as v2_pages
from amazon_market_spy.dashboard_v2.services import (
    DashboardDataMissing,
    DashboardDataValidationError,
    DashboardService,
)


class DashboardV2Tests(unittest.TestCase):
    def test_mock_data_contract_has_required_top_level_keys(self) -> None:
        validate_mock_data_contract(MOCK_PRESENTATION_DATA)

        with self.assertRaises(ValueError):
            validate_mock_data_contract({"morning_brief": {}, "ideas": []})

    def test_v2_generation_succeeds_and_writes_primary_pages(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "v2"
            result = generate_dashboard_v2(output_dir)

            expected_files = {filename for _, filename, _ in V2_PAGE_ROUTES}
            generated_files = {Path(page["path"]).name for page in result["pages"]}

            self.assertEqual(generated_files, expected_files)
            self.assertEqual(Path(result["main_page"]), output_dir / "index.html")
            for filename in expected_files:
                self.assertTrue((output_dir / filename).exists(), filename)

    def test_v2_navigation_contains_expected_pages_and_active_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "v2"
            generate_dashboard_v2(output_dir, data=MOCK_PRESENTATION_DATA)
            html = (output_dir / "product_explorer.html").read_text(encoding="utf-8")

        for label in ["Home", "Product Explorer", "Competitor Explorer", "Market Explorer"]:
            self.assertIn(label, html)
        for filename in ["index.html", "product_explorer.html", "competitor.html", "market_explorer.html"]:
            self.assertIn(filename, html)
        self.assertIn('href="product_explorer.html" aria-current="page"', html)
        self.assertNotIn("Product Detail", html)
        self.assertNotIn("Idea Detail", html)

    def test_shared_shell_home_widgets_and_active_navigation_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_service_fixture(root)
            output_dir = root / "v2"
            generate_dashboard_v2(output_dir)

            active_links = {
                "index.html": 'href="index.html" aria-current="page"',
                "product_explorer.html": 'href="product_explorer.html" aria-current="page"',
                "competitor.html": 'href="competitor.html" aria-current="page"',
                "market_explorer.html": 'href="market_explorer.html" aria-current="page"',
            }
            for filename, active_link in active_links.items():
                html = (output_dir / filename).read_text(encoding="utf-8")
                self.assertIn('class="top-shell"', html)
                self.assertIn('class="primary-nav"', html)
                self.assertIn("Dataset Information", html)
                self.assertIn(active_link, html)

            home_html = (output_dir / "index.html").read_text(encoding="utf-8")

        for section in [
            "Research Today",
            "Market Pulse",
            "Data Status",
            "Data Details",
            "Dataset Overview",
            "Evidence Overview",
            "Coverage Overview",
            "Data Quality",
            "Dataset Information",
            "Dashboard evidence reflects the current production evidence rules. Decision scoring and threshold recommendations are not active.",
        ]:
            self.assertIn(section, home_html)
        self.assertIn("data-home-data-details", home_html)
        self.assertNotIn("data-home-data-details open", home_html)
        self.assertLess(home_html.index("Research Today"), home_html.index("Market Pulse"))
        self.assertLess(home_html.index("Market Pulse"), home_html.index("Data Status"))
        self.assertLess(home_html.index("Data Status"), home_html.index("Data Details"))
        self.assertIn("Source-aware Observations", home_html)
        self.assertIn("product_explorer.html?seller_evidence=seller_leader", home_html)
        self.assertIn("product_explorer.html?best_seller_evidence=category_breakout", home_html)
        self.assertIn("product_explorer.html?supporting_evidence=very_strong_sub_bsr", home_html)

    def test_product_explorer_contains_three_column_shell(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "v2"
            generate_dashboard_v2(output_dir, data=MOCK_PRESENTATION_DATA)
            html = (output_dir / "product_explorer.html").read_text(encoding="utf-8")

        self.assertIn('class="product-workspace"', html)
        self.assertIn("data-filter-panel", html)
        self.assertIn('class="product-table"', html)
        self.assertIn("data-quick-preview", html)
        self.assertIn("Evidence Inspector", html)
        self.assertIn("saved-view-list", html)
        self.assertIn("filter-row-list", html)
        self.assertIn("toolbar-actions", html)
        self.assertIn("preview-meta-row", html)
        self.assertIn("Saved Views", html)
        self.assertIn("Advanced Filters", html)
        self.assertIn("grid-template-columns: minmax(210px, 19%) minmax(0, 1fr) minmax(280px, 24%)", html)

    def test_product_explorer_contains_serialized_normalized_product_data(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_service_fixture(root)
            output_dir = root / "v2"
            generate_dashboard_v2(output_dir)
            html = (output_dir / "product_explorer.html").read_text(encoding="utf-8")

        self.assertIn('id="product-explorer-data"', html)
        self.assertIn("Real Personalized Mug", html)
        self.assertIn("B0REAL0001", html)
        self.assertIn('"winner_score":87', html)
        self.assertIn('"product_type":"Personalized Mug"', html)
        self.assertIn('"recipient":"Unknown"', html)

    def test_product_explorer_search_and_filter_controls_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "v2"
            generate_dashboard_v2(output_dir, data=MOCK_PRESENTATION_DATA)
            html = (output_dir / "product_explorer.html").read_text(encoding="utf-8")

        self.assertIn('id="product-search"', html)
        self.assertIn('data-result-count aria-live="polite"', html)
        for field in ["product_type", "recipient", "theme", "occasion", "seller"]:
            self.assertIn(f'data-filter-select="{field}"', html)
        for field in ["score", "growth", "reviews", "price"]:
            self.assertIn(f'data-range-min="{field}"', html)
            self.assertIn(f'data-range-max="{field}"', html)
        for key in ["winner", "rising", "low_reviews", "new_launch"]:
            self.assertIn(f'data-quick-filter="{key}"', html)
        for key in ["all", "new_winners", "fast_rising", "christmas", "grandpa", "mug", "metal_sign"]:
            self.assertIn(f'data-saved-view="{key}"', html)

    def test_product_explorer_filter_summary_clear_all_and_empty_result_state_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "v2"
            generate_dashboard_v2(output_dir, data=MOCK_PRESENTATION_DATA)
            html = (output_dir / "product_explorer.html").read_text(encoding="utf-8")

        self.assertIn("data-active-filter-summary", html)
        self.assertIn("data-active-filter-chips", html)
        self.assertIn("data-clear-filters", html)
        self.assertIn("No products match the current search and filters.", html)
        self.assertIn("Clear All Filters", html)

    def test_product_explorer_url_state_javascript_is_present(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "v2"
            generate_dashboard_v2(output_dir, data=MOCK_PRESENTATION_DATA)
            html = (output_dir / "product_explorer.html").read_text(encoding="utf-8")

        self.assertIn("URLSearchParams", html)
        self.assertIn("window.history", html)
        self.assertIn("popstate", html)
        for parameter in ["q", "view", "score_min", "score_max", "growth_min", "reviews_max", "price_min"]:
            self.assertIn(parameter, html)
        for parameter in ['params.set("sort"', 'params.set("direction"', 'params.set("page"', 'params.set("page_size"', 'params.set("focus"']:
            self.assertIn(parameter, html)

    def test_product_explorer_core_workspace_controls_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "v2"
            generate_dashboard_v2(output_dir, data=MOCK_PRESENTATION_DATA)
            html = (output_dir / "product_explorer.html").read_text(encoding="utf-8")

        for key in ["title", "seller", "idea", "winner_score", "growth", "reviews", "price"]:
            self.assertIn(f'data-sort-key="{key}"', html)
        self.assertIn('aria-sort="none"', html)
        self.assertIn("data-sort-indicator", html)
        self.assertIn("data-select-page", html)
        self.assertIn("data-row-checkbox", html)
        self.assertIn("data-selection-toolbar", html)
        self.assertIn("data-selection-count", html)
        self.assertIn("data-hidden-selection-count", html)
        self.assertIn("data-clear-selection", html)
        self.assertIn('rowActionButton("amazon", "Open"', html)
        for action in ["seller", "source", "copy-asin", "copy-url"]:
            self.assertIn(f'data-preview-action="{action}"', html)
        self.assertNotIn("Available in Task 2.3B", html)
        self.assertNotIn(">Compare<", html)
        self.assertNotIn(">Export<", html)
        self.assertNotIn("Watchlist", html)

    def test_product_explorer_default_columns_are_minimal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "v2"
            generate_dashboard_v2(output_dir, data=MOCK_PRESENTATION_DATA)
            html = (output_dir / "product_explorer.html").read_text(encoding="utf-8")

        for label in ["Product", "Why It Matters", "Momentum", "Proof", "Open"]:
            self.assertIn(label, html)
        for key in ["select", "image", "seller", "product_type", "primary_evidence", "legacy_score", "growth", "reviews", "price", "source"]:
            self.assertIn(f'data-column-toggle="{key}"', html)
        for key in ["select", "image", "seller", "product_type", "legacy_score", "price", "source"]:
            self.assertIn(f'data-column-header="{key}" data-optional-column hidden', html)
        self.assertIn('data-column="seller" data-optional-column', html)
        self.assertIn('data-column="product_type" data-optional-column', html)
        self.assertIn('seller: "Seller"', html)
        self.assertIn('product_type: "Product Type"', html)
        self.assertIn('data-column-header="legacy_score" data-optional-column hidden', html)
        self.assertIn('const subtitle = [product.seller, product.product_type]', html)
        self.assertIn("whyItMatters(product)", html)
        self.assertIn("marketProof(product)", html)

    def test_product_explorer_more_filters_keep_advanced_data_accessible(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "v2"
            generate_dashboard_v2(output_dir, data=MOCK_PRESENTATION_DATA)
            html = (output_dir / "product_explorer.html").read_text(encoding="utf-8")

        self.assertIn("data-more-filters", html)
        self.assertIn("<summary>More Filters</summary>", html)
        self.assertIn('data-filter-select="product_type"', html)
        self.assertIn('data-filter-select="seller"', html)
        self.assertIn('data-filter-select="recipient"', html)
        self.assertIn('data-filter-select="theme"', html)
        self.assertIn('data-filter-select="occasion"', html)
        self.assertIn('data-evidence-filters', html)
        self.assertIn('data-range-min="reviews"', html)
        self.assertIn('data-range-min="price"', html)
        self.assertIn('data-quick-filter="winner"', html)
        self.assertLess(html.index("Product Type</h2>"), html.index("More Filters"))
        self.assertLess(html.index("Seller</h2>"), html.index("More Filters"))
        self.assertGreater(html.index('data-evidence-filters'), html.index("More Filters"))

    def test_product_explorer_pagination_defaults_and_options_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "v2"
            generate_dashboard_v2(output_dir, data=MOCK_PRESENTATION_DATA)
            html = (output_dir / "product_explorer.html").read_text(encoding="utf-8")

        self.assertIn("const DEFAULT_PAGE_SIZE = 100", html)
        self.assertIn("const PAGE_SIZES = [50, 100, 200]", html)
        self.assertIn("data-page-size", html)
        for value in ["50", "100", "200"]:
            self.assertIn(f'<option value="{value}"', html)
        for action in ["first", "previous", "next", "last"]:
            self.assertIn(f'data-page-action="{action}"', html)
        self.assertIn("data-page-range", html)
        self.assertIn("data-page-status", html)

    def test_home_queue_diversity_deduplicates_asins_and_caps_groups(self) -> None:
        products = []
        for index in range(8):
            products.append(
                {
                    "asin": f"B0CAP{index}",
                    "title": f"Product {index}",
                    "seller": "Seller A" if index < 4 else f"Seller {index}",
                    "product_type": "Mug" if index < 5 else f"Type {index}",
                    "category_breakout": True,
                    "best_seller_movement": 20 - index,
                    "review_count": index + 1,
                }
            )
        products.append({**products[0], "title": "Duplicate Product"})

        selected = v2_pages._diverse_products(v2_pages._sort_products_for_preset(products, "research_today"), limit=8)

        keys = {(product.get("marketplace", "amazon.com"), product["asin"]) for product in selected}
        self.assertEqual(len(keys), len(selected))
        self.assertLessEqual(sum(1 for product in selected if product["seller"] == "Seller A"), 2)
        self.assertLessEqual(sum(1 for product in selected if product["product_type"] == "Mug"), 3)

    def test_product_explorer_keyboard_navigation_and_stats_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "v2"
            generate_dashboard_v2(output_dir, data=MOCK_PRESENTATION_DATA)
            html = (output_dir / "product_explorer.html").read_text(encoding="utf-8")

        for key in ["ArrowDown", "ArrowUp", "Home", "End", "Escape", "scrollIntoView"]:
            self.assertIn(key, html)
        self.assertIn("aria-selected", html)
        self.assertIn("data-result-stats", html)
        for stat in ["total", "matching", "sellers", "ideas", "types"]:
            self.assertIn(f"data-stat-{stat}", html)
        self.assertIn("uniqueMeaningfulCount", html)

    def test_product_explorer_quick_preview_receives_real_product_data(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_service_fixture(root)
            output_dir = root / "v2"
            generate_dashboard_v2(output_dir)
            html = (output_dir / "product_explorer.html").read_text(encoding="utf-8")

        self.assertIn("Real Personalized Mug", html)
        self.assertIn("Real Seller", html)
        self.assertIn("Dad Gift", html)
        self.assertIn("Personalized Mug", html)
        self.assertIn("data-preview-asin", html)
        self.assertIn("B0REAL0001", html)
        for action in ["amazon", "seller", "source", "copy-asin", "copy-url"]:
            self.assertIn(f'data-preview-action="{action}"', html)

    def test_visual_product_previews_exist_without_replacing_v2_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "v2"
            generate_dashboard_v2(output_dir, data=MOCK_PRESENTATION_DATA)
            home_html = (output_dir / "index.html").read_text(encoding="utf-8")
            product_html = (output_dir / "product_explorer.html").read_text(encoding="utf-8")
            competitor_html = (output_dir / "competitor.html").read_text(encoding="utf-8")

        self.assertIn("data-home-preview-panel", home_html)
        self.assertIn("data-home-preview-item", home_html)
        self.assertIn("activity-thumbnail", home_html)
        self.assertIn("setPinnedItem", home_html)
        self.assertIn("product-title-thumbnail", product_html)
        self.assertIn('image.matches?.(".thumbnail, .product-title-thumbnail")', product_html)
        self.assertIn("data-filter-panel", product_html)
        self.assertIn("Evidence Inspector", product_html)
        self.assertIn("seller-thumbnail-strip", competitor_html)
        self.assertIn("representative_products", competitor_html)
        self.assertIn("seller_focus", competitor_html)
        self.assertIn("seller_focus_tags", competitor_html)
        self.assertIn("seller-focus-tags", competitor_html)
        self.assertIn("Open in Product Explorer &rarr;", competitor_html)
        self.assertIn("View Amazon Store &#8599;", competitor_html)
        self.assertIn("Store unavailable", competitor_html)
        self.assertIn('target="_blank" rel="noopener"', competitor_html)
        self.assertIn("seller-preview-stat", competitor_html)
        self.assertIn("seller-open-link", competitor_html)
        self.assertIn('title="Open in Product Explorer">&rarr;</a>', competitor_html)
        self.assertIn("<strong>${escapeHtml(value)}</strong><span>${escapeHtml(label)}</span>", competitor_html)
        self.assertIn("Fast Movers", competitor_html)
        self.assertIn("slice(0, 3)", competitor_html)
        self.assertIn("Display Order Preview", competitor_html)
        self.assertIn("slice(0, 10)", competitor_html)
        self.assertNotIn("View Seller Products", competitor_html)
        self.assertIn('addEventListener("pointerover"', competitor_html)
        self.assertIn("pinnedKey", competitor_html)
        self.assertIn("data-seller-table", competitor_html)
        for removed_panel_detail in [
            "Median Price",
            "Median Reviews",
            "Median Rank",
            "Top Categories",
            "Top Product Types",
            "Strong Sub-BSR Products",
        ]:
            self.assertNotIn(removed_panel_detail, competitor_html)

    def test_seller_focus_filters_generic_terms_for_compact_preview(self) -> None:
        products = [
            {
                "theme": "seller",
                "idea": "Patriotic Gift",
                "category_name": "Amazon Product",
                "product_type": "Metal Sign",
                "style": "Outdoor Decor",
            },
            {
                "theme": "Custom",
                "idea": "Lake House Gift",
                "category_name": "Products",
                "product_type": "Personalized Gifts",
                "style": "Camping",
            },
            {
                "theme": "Patriotic",
                "idea": "Custom Gift",
                "category_name": "Amazon",
                "product_type": "Personalized Mug",
                "style": "Fishing",
            },
        ]

        self.assertEqual(v2_pages._seller_focus_tags(products), ["Patriotic", "Lake House", "Metal Sign"])
        self.assertEqual(v2_pages._clean_focus_value("Custom Shirt"), "Custom Shirt")
        self.assertEqual(v2_pages._clean_focus_value("Personalized Gifts"), "")

    def test_seller_preview_sorts_by_display_order_rank_ascending(self) -> None:
        products = [
            _seller_preview_product(1, source_rank=3),
            _seller_preview_product(2, source_rank=1),
            _seller_preview_product(3, source_rank=2),
        ]

        cards = v2_pages._seller_product_cards(products, "title", reverse=False, limit=10)

        self.assertEqual([card["asin"] for card in cards], ["B0SELL0002", "B0SELL0003", "B0SELL0001"])

    def test_seller_preview_numeric_string_ranks_sort_correctly(self) -> None:
        products = [
            _seller_preview_product(1, source_rank="10"),
            _seller_preview_product(2, source_rank="2"),
            _seller_preview_product(3, source_rank="1"),
        ]

        cards = v2_pages._seller_product_cards(products, "title", reverse=False, limit=10)

        self.assertEqual([card["asin"] for card in cards], ["B0SELL0003", "B0SELL0002", "B0SELL0001"])

    def test_seller_preview_missing_ranks_appear_after_ranked_products(self) -> None:
        products = [
            _seller_preview_product(1, source_rank=""),
            _seller_preview_product(2, source_rank=2),
            _seller_preview_product(3, source_rank="invalid"),
            _seller_preview_product(4, source_rank=1),
        ]

        cards = v2_pages._seller_product_cards(products, "title", reverse=False, limit=10)

        self.assertEqual([card["asin"] for card in cards], ["B0SELL0004", "B0SELL0002", "B0SELL0001", "B0SELL0003"])

    def test_seller_preview_rank_ties_use_stable_product_identity(self) -> None:
        products = [
            _seller_preview_product(3, asin="B0TIE0003", source_rank=1),
            _seller_preview_product(1, asin="B0TIE0001", source_rank=1),
            _seller_preview_product(2, asin="B0TIE0002", source_rank=1),
        ]

        cards = v2_pages._seller_product_cards(products, "title", reverse=False, limit=10)

        self.assertEqual([card["asin"] for card in cards], ["B0TIE0001", "B0TIE0002", "B0TIE0003"])

    def test_seller_preview_selects_ten_same_type_products_from_full_catalog(self) -> None:
        products = [
            _seller_preview_product(index, product_type="Metal Sign", source_rank=index)
            for index in range(1, 11)
        ]

        cards = v2_pages._seller_product_cards(products, "title", reverse=False, limit=10)

        self.assertEqual(len(cards), 10)
        self.assertEqual(len({card["asin"] for card in cards}), 10)
        self.assertEqual([card["asin"] for card in cards], [f"B0SELL{index:04d}" for index in range(1, 11)])
        self.assertTrue(all(card["meta"].startswith("Metal Sign") for card in cards))

    def test_seller_preview_limits_to_ten_after_rank_sorting(self) -> None:
        products = [_seller_preview_product(index, source_rank=index) for index in range(1, 13)]

        cards = v2_pages._seller_product_cards(products, "title", reverse=False, limit=10)

        self.assertEqual(len(cards), 10)
        self.assertEqual([card["asin"] for card in cards], [f"B0SELL{index:04d}" for index in range(1, 11)])

    def test_seller_preview_uses_thumbnail_fallback_fields(self) -> None:
        products = [
            _seller_preview_product(1, image_url="", thumbnail_url="https://example.com/thumb.jpg"),
            _seller_preview_product(2, image_url="", main_image="https://example.com/main.jpg"),
            _seller_preview_product(3, image_url="", image="https://example.com/image.jpg"),
            _seller_preview_product(4, image_url="", images=[{"src": "https://example.com/nested.jpg"}]),
        ]

        cards = v2_pages._seller_product_cards(products, "title", reverse=False, limit=10)
        by_asin = {card["asin"]: card for card in cards}

        self.assertEqual(by_asin["B0SELL0001"]["image"], "https://example.com/thumb.jpg")
        self.assertEqual(by_asin["B0SELL0001"]["image_field"], "thumbnail_url")
        self.assertEqual(by_asin["B0SELL0002"]["image"], "https://example.com/main.jpg")
        self.assertEqual(by_asin["B0SELL0002"]["image_field"], "main_image")
        self.assertEqual(by_asin["B0SELL0003"]["image"], "https://example.com/image.jpg")
        self.assertEqual(by_asin["B0SELL0003"]["image_field"], "image")
        self.assertEqual(by_asin["B0SELL0004"]["image"], "https://example.com/nested.jpg")
        self.assertEqual(by_asin["B0SELL0004"]["image_field"], "images.src")

    def test_seller_preview_deduplicates_exact_products_not_product_type(self) -> None:
        products = [
            _seller_preview_product(1, asin="B0DUP0001", product_type="Custom Shirt", image_url="https://example.com/a.jpg", source_rank=1),
            _seller_preview_product(2, asin="B0DUP0001", product_type="Custom Shirt", image_url="https://example.com/b.jpg", source_rank=2),
            _seller_preview_product(3, asin="", product_type="Custom Shirt", product_url="https://www.amazon.com/example/dp/B0URL0001?ref=one", source_rank=3),
            _seller_preview_product(4, asin="", product_type="Custom Shirt", product_url="https://www.amazon.com/example/dp/B0URL0001?ref=two", source_rank=4),
            _seller_preview_product(5, asin="B0UNIQUE5", product_type="Custom Shirt", source_rank=5),
        ]

        cards = v2_pages._seller_product_cards(products, "title", reverse=False, limit=10)

        self.assertEqual(len(cards), 3)
        self.assertEqual(sum(1 for card in cards if card["asin"] == "B0DUP0001"), 1)
        self.assertGreaterEqual(sum(1 for card in cards if card["meta"].startswith("Custom Shirt")), 3)

    def test_seller_preview_takes_first_ten_valid_products_after_image_filter_and_dedupe(self) -> None:
        products = [
            _seller_preview_product(index, source_rank=index, image_url="")
            for index in range(1, 4)
        ]
        products.extend(
            _seller_preview_product(10 + index, asin="B0DUPLATE", source_rank=10 + index, image_url=f"https://example.com/dup-{index}.jpg")
            for index in range(4)
        )
        products.extend(_seller_preview_product(20 + index, source_rank=20 + index) for index in range(10))

        cards = v2_pages._seller_product_cards(products, "title", reverse=False, limit=10)
        asins = {card["asin"] for card in cards}

        self.assertEqual(len(cards), 10)
        self.assertIn("B0DUPLATE", asins)
        self.assertIn("B0SELL0028", asins)
        self.assertNotIn("B0SELL0029", asins)
        self.assertTrue(all(card["image"] for card in cards))

    def test_seller_preview_fewer_than_ten_valid_products_renders_all_available(self) -> None:
        products = [
            _seller_preview_product(1, seller="Small Seller", source_rank=2),
            _seller_preview_product(2, seller="Small Seller", source_rank=1),
        ]
        data = {**MOCK_PRESENTATION_DATA, "products": products}

        html = v2_pages.render_competitor(data)
        payload = _seller_payload(html)
        seller = next(row for row in payload if row["seller"] == "Small Seller")

        self.assertEqual(len(seller["representative_products"]), 2)
        self.assertEqual([card["asin"] for card in seller["representative_products"]], ["B0SELL0002", "B0SELL0001"])
        self.assertNotIn("placeholderCount", html)

    def test_seller_preview_store_cta_uses_existing_seller_url(self) -> None:
        products = [
            _seller_preview_product(
                1,
                seller="Storefront Seller",
                seller_url="https://www.amazon.com/s?me=A1STORE",
            ),
            _seller_preview_product(2, seller="No Store Seller", seller_url=""),
        ]
        data = {**MOCK_PRESENTATION_DATA, "products": products}

        html = v2_pages.render_competitor(data)
        payload = _seller_payload(html)
        storefront_seller = next(row for row in payload if row["seller"] == "Storefront Seller")
        no_store_seller = next(row for row in payload if row["seller"] == "No Store Seller")

        self.assertEqual(storefront_seller["seller_url"], "https://www.amazon.com/s?me=A1STORE")
        self.assertEqual(no_store_seller["seller_url"], "")
        self.assertIn("View Amazon Store &#8599;", html)
        self.assertIn('target="_blank" rel="noopener"', html)
        self.assertIn("Store unavailable", html)

    def test_dxl_trading_current_dataset_matches_first_ten_display_order_products(self) -> None:
        if not (Path("output") / "latest_products.csv").exists():
            self.skipTest("Current output/latest_products.csv is not available.")
        data = DashboardService(Path("output")).load()
        products = [product for product in data["products"] if product.get("seller") == "DXL Trading"]
        if not products:
            self.skipTest("DXL Trading is not available in the current output dataset.")

        valid_images = [v2_pages._seller_thumbnail_src(product) for product in products]
        valid_images = [item for item in valid_images if item[0]]
        if len(valid_images) < 10:
            self.skipTest("DXL Trading has fewer than ten products with valid images in the current output dataset.")
        expected_products = v2_pages._seller_representative_products(products, limit=10)
        expected_asins = [str(product.get("asin", "") or "") for product, _, _ in expected_products]
        cards = v2_pages._seller_product_cards(products, "title", reverse=False, limit=10)

        self.assertEqual(len(products), 159)
        self.assertGreaterEqual(len(valid_images), 10)
        self.assertEqual(len(cards), 10)
        self.assertEqual([card["asin"] for card in cards], expected_asins)
        self.assertEqual(
            [v2_pages._seller_display_order_rank(product) for product, _, _ in expected_products],
            sorted(v2_pages._seller_display_order_rank(product) for product, _, _ in expected_products),
        )

    def test_product_explorer_evidence_filters_and_legacy_signals_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_service_fixture(root)
            output_dir = root / "v2"
            generate_dashboard_v2(output_dir)
            html = (output_dir / "product_explorer.html").read_text(encoding="utf-8")

        self.assertIn("Legacy Signals", html)
        self.assertIn("Legacy Winner", html)
        self.assertIn("Legacy Rising", html)
        self.assertIn("Evidence and Source Filters", html)
        for family in ["seller", "best_seller", "new_release", "supporting"]:
            self.assertIn(f'data-evidence-filter-group="{family}"', html)
        for key in [
            "seller_leader",
            "seller_mover",
            "seller_new_push",
            "category_winner",
            "category_breakout",
            "category_stable",
            "new_release_rising",
            "new_release_breakout",
            "new_release_watch",
            "strong_sub_bsr",
            "very_strong_sub_bsr",
        ]:
            self.assertIn(f'data-evidence-filter="{key}"', html)
        for definition in [
            "Top 10 in the same tracked seller source for at least 7 days.",
            "Improved at least 10 positions within the same seller source.",
            "Sub-category BSR is 1,000 or better.",
        ]:
            self.assertIn(definition, html)

    def test_product_explorer_evidence_filter_javascript_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "v2"
            generate_dashboard_v2(output_dir, data=MOCK_PRESENTATION_DATA)
            html = (output_dir / "product_explorer.html").read_text(encoding="utf-8")

        for parameter in ["seller_evidence", "best_seller_evidence", "new_release_evidence", "supporting_evidence"]:
            self.assertIn(parameter, html)
        self.assertIn("function explicitEvidenceValue", html)
        self.assertIn("product[key] === true", html)
        self.assertIn("let familyMatch = false", html)
        self.assertIn("if (!familyMatch) return false", html)
        self.assertIn("params.append(config.param, value)", html)
        self.assertIn('"no_data"', html)
        self.assertIn("Not active", html)
        self.assertIn("No data", html)

    def test_product_explorer_presets_use_explicit_evidence_fields(self) -> None:
        expected = {
            "research_today": {"category_breakout", "new_release_breakout", "seller_mover", "seller_new_push"},
            "proven_demand": {"category_winner", "very_strong_sub_bsr", "seller_leader"},
            "early_opportunity": {"seller_new_push", "new_release_rising", "new_release_watch"},
            "competitor_push": {"seller_mover", "seller_new_push"},
        }

        self.assertEqual({key: set(value["evidence"]) for key, value in v2_pages.PRODUCT_PRESETS.items()}, expected)
        for config in v2_pages.PRODUCT_PRESETS.values():
            self.assertNotIn("score", " ".join(sorted(config["evidence"])))

    def test_product_explorer_preset_url_persistence_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "v2"
            generate_dashboard_v2(output_dir, data=MOCK_PRESENTATION_DATA)
            html = (output_dir / "product_explorer.html").read_text(encoding="utf-8")

        for key in ["research_today", "proven_demand", "early_opportunity", "competitor_push"]:
            self.assertIn(f'data-product-preset="{key}"', html)
        self.assertIn('params.set("preset"', html)
        self.assertIn('next.preset = validPreset(params.get("preset") || DEFAULT_PRESET)', html)
        self.assertIn("popstate", html)

    def test_research_today_default_sort_is_deterministic(self) -> None:
        products = [
            {"asin": "B00B", "title": "Same", "category_breakout": True, "best_seller_movement": 10, "review_count": 5},
            {"asin": "B00A", "title": "Same", "category_breakout": True, "best_seller_movement": 10, "review_count": 5},
            {"asin": "B00C", "title": "Later", "seller_mover": True, "seller_movement": 99, "review_count": 1},
            {"asin": "B00D", "title": "First", "new_release_breakout": True, "new_release_movement": 1, "review_count": 99},
        ]

        sorted_products = v2_pages._sort_products_for_preset(products, "research_today")

        self.assertEqual([product["asin"] for product in sorted_products], ["B00D", "B00A", "B00B", "B00C"])

    def test_product_explorer_primary_evidence_priority_and_overflow_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_service_fixture(root)
            output_dir = root / "v2"
            generate_dashboard_v2(output_dir)
            html = (output_dir / "product_explorer.html").read_text(encoding="utf-8")
            products = _product_payload(output_dir / "product_explorer.html")

        self.assertIn('data-sort-key="evidence_count"', html)
        self.assertIn("Evidence Count", html)
        priority_start = html.index("const PRIMARY_EVIDENCE_PRIORITY")
        priority_end = html.index("];", priority_start)
        priority_block = html[priority_start:priority_end]
        expected_order = [
            "new_release_breakout",
            "category_breakout",
            "seller_mover",
            "seller_new_push",
            "category_winner",
            "new_release_rising",
            "seller_leader",
            "very_strong_sub_bsr",
            "strong_sub_bsr",
            "new_release_watch",
        ]
        positions = [priority_block.index(f'"{key}"') for key in expected_order]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("primaryEvidenceBadge", html)
        self.assertIn("evidence-more", html)
        self.assertIn("+${remaining.length}", html)
        rich_product = next(product for product in products if product["asin"] == "B0REAL0001")
        active_fields = [
            "seller_evidence_leader",
            "seller_evidence_mover",
            "best_seller_evidence_winner",
            "best_seller_evidence_breakout",
            "new_release_evidence_rising",
            "new_release_evidence_breakout",
            "new_release_evidence_watch",
            "bsr_evidence_strong",
            "bsr_evidence_very_strong",
        ]
        self.assertGreater(sum(1 for field in active_fields if rich_product[field]), 3)

    def test_primary_evidence_why_momentum_and_market_proof_rules(self) -> None:
        all_evidence = {
            "new_release_breakout": True,
            "category_breakout": True,
            "seller_mover": True,
            "seller_new_push": True,
            "category_winner": True,
            "new_release_rising": True,
            "seller_leader": True,
            "very_strong_sub_bsr": True,
            "strong_sub_bsr": True,
            "new_release_watch": True,
            "new_release_movement": 39,
            "review_count": 18,
            "best_seller_evidence_best_rank": 12,
            "bsr_evidence_best_sub_bsr": 842,
            "seller_evidence_best_rank": 7,
        }
        seller_mover = {"seller_mover": True, "seller_movement": 39, "review_count": 4}
        missing_movement = {"seller_mover": True}

        self.assertEqual(v2_pages._primary_evidence_key(all_evidence), "new_release_breakout")
        self.assertEqual(v2_pages._why_it_matters(seller_mover), "Improved 39 seller positions")
        self.assertNotIn("score", v2_pages._why_it_matters(seller_mover).lower())
        self.assertEqual(v2_pages._momentum_label(missing_movement), "\u2014")
        self.assertEqual(v2_pages._market_proof(all_evidence), "Best Seller #12")
        self.assertEqual(v2_pages._market_proof({"bsr_evidence_best_sub_bsr": 842, "review_count": 42}), "Sub-BSR #842")
        self.assertEqual(v2_pages._market_proof({"review_count": 42, "seller_evidence_best_rank": 7}), "42 reviews")
        self.assertEqual(v2_pages._market_proof({"seller_evidence_best_rank": 7}), "Seller #7")

    def test_product_explorer_evidence_inspector_sections_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_service_fixture(root)
            output_dir = root / "v2"
            generate_dashboard_v2(output_dir)
            html = (output_dir / "product_explorer.html").read_text(encoding="utf-8")

        self.assertIn("Evidence Inspector", html)
        for section in [
            "Seller Intelligence",
            "Best Seller Intelligence",
            "New Release Intelligence",
            "BSR Evidence",
            "Evidence Reasons",
        ]:
            self.assertIn(section, html)
        for selector in [
            "data-inspector-seller-body",
            "data-inspector-best-seller-body",
            "data-inspector-new-release-body",
            "data-inspector-bsr-body",
            "data-inspector-reasons-body",
        ]:
            self.assertIn(selector, html)
        self.assertIn("sourceDetailList(details)", html)
        self.assertIn("sourceDetailRow(detail, includeBsr)", html)
        self.assertIn("Sub-category BSR", html)
        self.assertIn("primaryBsrCategory", html)
        self.assertIn("subBsrCategory", html)

    def test_product_inspector_defaults_are_compact_with_full_evidence_collapsed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_service_fixture(root)
            output_dir = root / "v2"
            generate_dashboard_v2(output_dir)
            html = (output_dir / "product_explorer.html").read_text(encoding="utf-8")

        summary_start = html.index('data-inspector-product-summary')
        summary_end = html.index("</section>", summary_start)
        summary_block = html[summary_start:summary_end]

        for label in ["Product Summary", "Why It Matters", "Momentum", "Market Proof"]:
            self.assertIn(label, summary_block)
        self.assertNotIn("Seller", summary_block)
        self.assertNotIn("Winner Score", summary_block)
        self.assertIn("data-full-evidence", html)
        self.assertIn("<summary>View Full Evidence</summary>", html)
        for selector in [
            "data-preview-seller",
            "data-preview-price",
            "data-preview-reviews",
            "data-preview-bsr",
            "data-preview-score",
            "data-inspector-source-details",
            "data-inspector-metadata",
        ]:
            self.assertIn(selector, html)
        self.assertIn('data-preview-action="amazon"', html)

    def test_competitor_and_market_default_tables_are_minimal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "v2"
            generate_dashboard_v2(output_dir, data=MOCK_PRESENTATION_DATA)
            competitor_html = (output_dir / "competitor.html").read_text(encoding="utf-8")
            market_html = (output_dir / "market_explorer.html").read_text(encoding="utf-8")

        competitor_head = _first_thead(competitor_html, "data-seller-table")
        for label in ["Seller", "Activity", "New Pushes", "Fast Movers", "Open"]:
            self.assertIn(label, competitor_head)
        for hidden_label in ["Active Products", "Leaders", "Latest Activity"]:
            self.assertNotIn(hidden_label, competitor_head)
        self.assertIn("Seller Summary", competitor_html)
        self.assertIn("Open in Product Explorer &rarr;", competitor_html)
        self.assertNotIn("Median Reviews", competitor_html)

        market_head = _first_thead(market_html, "data-market-table")
        for label in ["Market", "Momentum", "Validation", "Competition", "Open"]:
            self.assertIn(label, market_head)
        for hidden_label in ["Products", "Breakouts"]:
            self.assertNotIn(hidden_label, market_head)
        self.assertIn("marketDetail(row)", market_html)
        self.assertIn('class="panel detail-panel market-preview-panel"', market_html)
        self.assertIn("data-market-detail", market_html)
        self.assertIn("marketProductGrid", market_html)
        self.assertIn("market-product-grid", market_html)
        self.assertIn("Representative Products", market_html)
        self.assertIn("Leading Sellers", market_html)
        self.assertIn("Market Health", market_html)
        self.assertIn("Open Product Explorer &rarr;", market_html)
        self.assertIn('addEventListener("pointerover"', market_html)
        self.assertIn('metric("Breakouts"', market_html)
        for removed_detail_metric in [
            "Median Price",
            "Median Rating",
            "Median Sub-BSR",
            "Coverage",
            "Seller Leaders",
            "Very Strong Sub-BSR",
            "Seller Movers",
            "New Release Rising",
            "Category Breakouts",
        ]:
            self.assertNotIn(f'metric("{removed_detail_metric}"', market_html)

    def test_product_explorer_evidence_statistics_and_sort_controls_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "v2"
            generate_dashboard_v2(output_dir, data=MOCK_PRESENTATION_DATA)
            html = (output_dir / "product_explorer.html").read_text(encoding="utf-8")

        for stat in ["seller-evidence", "best-seller-evidence", "new-release-evidence", "bsr-evidence"]:
            self.assertIn(f"data-stat-{stat}", html)
        for sort_key in [
            "evidence_count",
            "seller_best_rank",
            "seller_movement",
            "best_seller_rank",
            "new_release_movement",
            "sub_bsr",
        ]:
            self.assertIn(f'value="{sort_key}"', html)
            self.assertIn(sort_key, html)
        self.assertIn("const leftMissing", html)
        self.assertIn("return leftMissing ? 1 : -1", html)

    def test_product_explorer_index_payload_excludes_inspector_only_data(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_service_fixture(root)
            output_dir = root / "v2"
            generate_dashboard_v2(output_dir)
            products = _product_payload(output_dir / "product_explorer.html")

        product = next(row for row in products if row["asin"] == "B0REAL0001")
        for inspector_only_field in [
            "source_details",
            "evidence_states",
            "evidence_reasons",
            "pod_relevance_reasons",
            "product_url",
            "amazon_url",
        ]:
            self.assertNotIn(inspector_only_field, product)
        self.assertEqual(product["detail_asset"], "product_explorer_details/b0real0001.js")
        self.assertTrue(product["seller_evidence_leader"])
        self.assertEqual(product["seller_movement"], 16)
        self.assertEqual(product["new_release_movement"], 42)

    def test_product_explorer_detail_chunks_are_deterministic_and_preserve_details(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_service_fixture(root)
            output_dir = root / "v2"
            result = generate_dashboard_v2(output_dir)
            rich_detail = _detail_payload(output_dir / "product_explorer_details" / "b0real0001.js", "B0REAL0001")
            plain_detail = _detail_payload(output_dir / "product_explorer_details" / "b0real0002.js", "B0REAL0002")

        asset_names = {Path(asset["filename"]).as_posix() for asset in result["assets"]}
        self.assertIn("product_explorer_details/b0real0001.js", asset_names)
        self.assertIn("product_explorer_details/b0real0002.js", asset_names)
        self.assertEqual(len(rich_detail["source_details"]["seller"]), 2)
        self.assertEqual(rich_detail["source_details"]["seller"][0]["source_name"], "Real Seller Store")
        self.assertEqual(rich_detail["source_details"]["seller"][1]["source_name"], "Secondary Seller Source")
        self.assertEqual(rich_detail["source_details"]["best_seller"][0]["category_name"], "Novelty Coffee Mugs")
        self.assertEqual(rich_detail["evidence_states"]["seller"]["leader"], "true")
        self.assertEqual(plain_detail["evidence_states"]["seller"]["leader"], "false")
        self.assertEqual(plain_detail["evidence_states"]["best_seller"]["winner"], "no_data")
        self.assertIsNone(plain_detail.get("best_seller_evidence_best_rank"))

    def test_product_explorer_lazy_detail_loader_uses_script_cache_not_fetch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "v2"
            generate_dashboard_v2(output_dir, data=MOCK_PRESENTATION_DATA)
            html = (output_dir / "product_explorer.html").read_text(encoding="utf-8")

        self.assertNotIn("fetch(", html)
        self.assertNotIn("XMLHttpRequest", html)
        self.assertIn("window.AMS_PRODUCT_EXPLORER_INITIAL_DETAIL_COUNT = 0", html)
        self.assertIn("document.createElement(\"script\")", html)
        self.assertIn("script.src = product.detailAsset", html)
        self.assertIn("detailCache.has(product.__id)", html)
        self.assertIn("detailPromises.has(product.__id)", html)
        self.assertIn("window.AMS_PRODUCT_EXPLORER_DETAILS?.[product.__id]", html)
        self.assertIn("scheduleHoverDetailLoad", html)
        self.assertIn("window.setTimeout", html)
        self.assertIn("window.clearTimeout(hoverDetailTimer)", html)
        self.assertIn("Missing detail chunk", html)

    def test_finalized_product_explorer_url_and_keyboard_controls_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "v2"
            generate_dashboard_v2(output_dir, data=MOCK_PRESENTATION_DATA)
            html = (output_dir / "product_explorer.html").read_text(encoding="utf-8")

        self.assertIn('event.key === "/"', html)
        self.assertIn("searchInput?.focus()", html)
        self.assertIn("data-clear-filters", html)
        self.assertIn("displayValueHtml(reviewDisplay(product))", html)
        self.assertIn("displayValueHtml(priceDisplay(product))", html)
        self.assertIn("displayValue(product.asin)", html)
        self.assertIn("renderInspectorLoading(product)", html)

    def test_competitor_and_market_deep_links_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_service_fixture(root)
            output_dir = root / "v2"
            generate_dashboard_v2(output_dir)
            competitor_html = (output_dir / "competitor.html").read_text(encoding="utf-8")
            market_html = (output_dir / "market_explorer.html").read_text(encoding="utf-8")

        self.assertIn("Competitor Explorer", competitor_html)
        self.assertIn('id="seller-search"', competitor_html)
        self.assertIn("data-seller-sort-select", competitor_html)
        self.assertIn("product_explorer.html?seller=", competitor_html)
        self.assertIn("data-seller-detail", competitor_html)
        self.assertIn('id="market-search"', market_html)
        self.assertIn("data-market-mode", market_html)
        self.assertIn("product_explorer.html?type=", market_html)
        self.assertIn("Unknown", market_html)

    def test_idea_dimensions_do_not_mix_entity_types(self) -> None:
        products = [
            {
                "asin": "B0IDEA1",
                "title": "Dad Mug",
                "seller": "Seller A",
                "recipient": "Dad",
                "occasion": "Birthday",
                "theme": "Fishing",
                "product_type": "Mug",
                "category_breakout": True,
                "review_count": 12,
            },
            {
                "asin": "B0IDEA2",
                "title": "Mom Shirt",
                "seller": "Seller B",
                "recipient": "Mom",
                "occasion": "Christmas",
                "theme": "Dogs",
                "product_type": "Shirt",
                "seller_mover": True,
                "seller_movement": 5,
                "review_count": 20,
            },
        ]

        payload = v2_pages._idea_dimension_payload(products, [])

        self.assertEqual({row["idea"] for row in payload["recipient"]}, {"Dad", "Mom"})
        self.assertEqual({row["idea"] for row in payload["occasion"]}, {"Birthday", "Christmas"})
        self.assertEqual({row["idea"] for row in payload["theme"]}, {"Fishing", "Dogs"})
        self.assertEqual({row["idea"] for row in payload["product_type"]}, {"Mug", "Shirt"})

    def test_competitor_default_sorting_is_activity_first(self) -> None:
        products = [
            {"asin": "B0A", "title": "A", "seller": "Quiet", "date": "2026-07-24", "product_type": "Mug"},
            {"asin": "B0B", "title": "B", "seller": "Active", "date": "2026-07-20", "product_type": "Mug", "seller_mover": True},
            {"asin": "B0C", "title": "C", "seller": "Active", "date": "2026-07-21", "product_type": "Mug", "seller_new_push": True},
            {"asin": "B0D", "title": "D", "seller": "One Move", "date": "2026-07-24", "product_type": "Sign", "seller_mover": True},
        ]

        sellers = v2_pages._seller_summaries(products)

        self.assertEqual(sellers[0]["seller"], "Active")
        self.assertEqual(sellers[0]["activity_count"], 2)

    def test_market_default_sorting_is_breakout_first(self) -> None:
        products = [
            {"asin": "B0A", "title": "A", "seller": "S1", "idea": "Low", "product_type": "Mug", "seller_mover": True},
            {"asin": "B0B", "title": "B", "seller": "S2", "idea": "Breakout", "product_type": "Mug", "category_breakout": True},
            {"asin": "B0C", "title": "C", "seller": "S3", "idea": "Breakout", "product_type": "Mug", "new_release_breakout": True},
        ]

        groups = v2_pages._market_groups(products, "category")

        self.assertEqual(groups[0]["label"], "Breakout")
        self.assertEqual(groups[0]["breakout_total"], 2)

    def test_market_preview_uses_display_order_products_and_leading_sellers(self) -> None:
        ranks = [12, 2, 1, 4, 3, 6, 5, 8, 7, 10, 9, 11]
        sellers = ["Alpha"] * 5 + ["Beta"] * 4 + ["Gamma"] * 2 + ["Delta"]
        products = [
            _seller_preview_product(
                index,
                asin=f"B0MARK{index:04d}",
                seller=sellers[index - 1],
                idea="Lake House",
                product_type="Metal Sign",
                theme="Camping",
                occasion="Father's Day",
                recipient="Dad",
                source_rank=rank,
            )
            for index, rank in enumerate(ranks, start=1)
        ]

        groups = v2_pages._market_groups(products, "category")
        row = next(group for group in groups if group["label"] == "Lake House")

        self.assertEqual(row["market_tags"], ["Metal Sign", "Camping", "Father's Day"])
        self.assertEqual(row["leading_sellers"], ["Alpha", "Beta", "Gamma", "Delta"])
        self.assertEqual(len(row["representative_products"]), 10)
        self.assertEqual(
            [card["asin"] for card in row["representative_products"]],
            [
                "B0MARK0003",
                "B0MARK0002",
                "B0MARK0005",
                "B0MARK0004",
                "B0MARK0007",
                "B0MARK0006",
                "B0MARK0009",
                "B0MARK0008",
                "B0MARK0011",
                "B0MARK0010",
            ],
        )
        self.assertTrue(all(card["url"].startswith("product_explorer.html?q=Lake%20House&focus=") for card in row["representative_products"]))

    def test_dashboard_v2_finalization_does_not_introduce_new_scores(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_service_fixture(root)
            output_dir = root / "v2"
            generate_dashboard_v2(output_dir)
            html_by_page = {
                filename: (output_dir / filename).read_text(encoding="utf-8")
                for _, filename, _ in V2_PAGE_ROUTES
            }

        for filename, html in html_by_page.items():
            self.assertNotIn("Decision Score", html, filename)
            self.assertNotIn("Opportunity Score", html, filename)

        self.assertNotIn("decision_score", v2_pages.PRODUCT_INDEX_FIELDS)
        self.assertNotIn("opportunity_score", v2_pages.PRODUCT_INDEX_FIELDS)
        self.assertNotIn("decisionScore", "".join(v2_pages.PRODUCT_INDEX_FIELDS))
        self.assertNotIn("opportunityScore", "".join(v2_pages.PRODUCT_INDEX_FIELDS))

    def test_product_explorer_filters_and_sorting_work_from_index_before_detail_load(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "v2"
            generate_dashboard_v2(output_dir, data=MOCK_PRESENTATION_DATA)
            html = (output_dir / "product_explorer.html").read_text(encoding="utf-8")

        matches_start = html.index("function matchesProduct")
        matches_end = html.index("function sortProducts", matches_start)
        matches_block = html[matches_start:matches_end]
        self.assertIn("product[key] === true", matches_block)
        self.assertNotIn("sourceDetails", matches_block)
        self.assertIn("seller_movement: { label: \"Seller Movement\", type: \"number\", value: (product) => product.sellerMovement }", html)
        self.assertIn("new_release_movement: { label: \"New Release Movement\", type: \"number\", value: (product) => product.newReleaseMovement }", html)

    def test_product_explorer_stale_detail_chunks_are_cleaned(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_service_fixture(root)
            output_dir = root / "v2"
            stale = output_dir / "product_explorer_details" / "stale.js"
            stale.parent.mkdir(parents=True)
            stale.write_text("stale", encoding="utf-8")

            generate_dashboard_v2(output_dir)

            self.assertFalse(stale.exists())
            self.assertTrue((output_dir / "product_explorer_details" / "b0real0001.js").exists())

    def test_dashboard_v2_runtime_does_not_import_mock_data(self) -> None:
        runtime_files = [
            Path("amazon_market_spy/dashboard_v2/generator.py"),
            Path("amazon_market_spy/dashboard_v2/pages.py"),
            Path("amazon_market_spy/dashboard_v2/services/dashboard_service.py"),
        ]
        for path in runtime_files:
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("mock_data", text, str(path))
            self.assertNotIn("MOCK_PRESENTATION_DATA", text, str(path))

    def test_v2_does_not_generate_detail_pages(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "v2"
            generate_dashboard_v2(output_dir, data=MOCK_PRESENTATION_DATA)

            self.assertFalse((output_dir / "product_detail.html").exists())
            self.assertFalse((output_dir / "idea_detail.html").exists())
            self.assertFalse((output_dir / "product_detail").exists())
            self.assertFalse((output_dir / "idea_detail").exists())

    def test_cli_generate_dashboard_v2_reports_output_and_pages(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "v2"
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = main(["generate-dashboard-v2", "--output", str(output_dir)])
            output = stdout.getvalue()

            self.assertEqual(exit_code, 0)
            self.assertIn("Dashboard V2 output directory:", output)
            self.assertIn("Dashboard V2 main page:", output)
            self.assertIn("Home", output)
            self.assertTrue((output_dir / "index.html").exists())

    def test_v1_generation_still_succeeds(self) -> None:
        row = {
            "date": "2026-07-23",
            "alert_type": "opportunity",
            "priority": "High",
            "opportunity_score": "90",
            "asin": "B0V1SMOKE1",
            "title": "V1 Smoke Personalized Mug",
            "product_url": "https://www.amazon.com/dp/B0V1SMOKE1",
            "is_pod": "yes",
            "pod_type": "personalized_mug",
            "pod_score": "80",
            "pod_reason": "personalized mug",
            "niche_primary": "Personalized Mug",
            "niche_secondary": "",
            "niche_tags": "Personalized Mug",
            "niche_score": "40",
            "niche_reason": "personalized mug",
            "display_rank": "3",
            "display_order": "3",
            "previous_display_rank": "18",
            "display_rank_change": "15",
            "days_seen": "2",
            "seller_name": "V1 Seller",
            "source_name": "V1 Seller",
            "source_type": "seller",
            "image_url": "",
            "local_image_path": "",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            paths = write_lark_opportunity_artifacts(output_dir, [row], all_opportunities=[row], products=[row], include_non_pod=True)

            self.assertTrue(Path(paths["priority_board"]).exists())
            self.assertTrue(Path(paths["product_discovery"]).exists())
            self.assertTrue((output_dir / "product_detail" / "B0V1SMOKE1.html").exists())


class DashboardV2ServiceTests(unittest.TestCase):
    def test_service_loads_real_csv_presentation_data(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            _write_service_fixture(output_dir)

            service = DashboardService(output_dir)
            data = service.load()

            self.assertEqual(data["products"][0]["title"], "Real Personalized Mug")
            self.assertEqual(data["products"][0]["reviews"], "17")
            self.assertEqual(data["products"][0]["winner_score"], 87)
            self.assertEqual(data["products"][0]["growth_value"], 24)
            self.assertEqual(data["products"][0]["price_value"], 19.99)
            self.assertEqual(data["products"][0]["recipient"], "Unknown")
            self.assertEqual(data["products"][0]["theme"], "Unknown")
            self.assertEqual(data["products"][0]["occasion"], "Unknown")
            self.assertEqual(data["products"][0]["amazon_url"], "https://www.amazon.com/dp/B0REAL0001")
            self.assertTrue(data["products"][0]["is_winner"])
            self.assertTrue(data["products"][0]["is_rising"])
            self.assertEqual(data["ideas"][0]["idea"], "Dad Gift")
            self.assertEqual(data["competitors"][0]["seller"], "Real Seller")
            self.assertEqual(data["market"]["distribution"][0]["label"], "Dad Gift")
            self.assertIs(service.load(), data)

    def test_service_exposes_product_evidence_summary_and_source_details(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            _write_service_fixture(output_dir)

            product = DashboardService(output_dir).load()["products"][0]

        self.assertTrue(product["seller_evidence_leader"])
        self.assertTrue(product["seller_evidence_mover"])
        self.assertTrue(product["best_seller_evidence_winner"])
        self.assertTrue(product["best_seller_evidence_breakout"])
        self.assertTrue(product["new_release_evidence_rising"])
        self.assertTrue(product["new_release_evidence_breakout"])
        self.assertTrue(product["new_release_evidence_watch"])
        self.assertTrue(product["bsr_evidence_strong"])
        self.assertTrue(product["bsr_evidence_very_strong"])
        self.assertEqual(product["seller_evidence_best_rank"], 6)
        self.assertEqual(product["best_seller_evidence_best_rank"], 28)
        self.assertEqual(product["new_release_evidence_best_rank"], 18)
        self.assertEqual(product["bsr_evidence_best_sub_bsr"], 42)
        self.assertEqual(product["bsr_evidence_best_sub_bsr_category"], "Novelty Coffee Mugs")
        self.assertEqual(len(product["source_details"]["seller"]), 2)
        self.assertEqual(product["source_details"]["seller"][0]["source_name"], "Real Seller Store")
        self.assertEqual(product["source_details"]["seller"][1]["source_name"], "Secondary Seller Source")
        self.assertEqual(product["source_details"]["best_seller"][0]["category_name"], "Novelty Coffee Mugs")
        self.assertEqual(product["source_details"]["new_release"][0]["source_rank_change"], 42)
        self.assertIn("Seller rank #6 for 10 days", product["evidence_reasons"])

    def test_service_distinguishes_false_no_data_and_missing_numeric_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            _write_service_fixture(output_dir)

            products = DashboardService(output_dir).load()["products"]
            plain_product = next(product for product in products if product["asin"] == "B0REAL0002")

        self.assertEqual(plain_product["evidence_states"]["seller"]["leader"], "false")
        self.assertEqual(plain_product["evidence_states"]["seller"]["mover"], "false")
        self.assertEqual(plain_product["evidence_states"]["best_seller"]["winner"], "no_data")
        self.assertEqual(plain_product["evidence_states"]["new_release"]["candidate"], "no_data")
        self.assertEqual(plain_product["evidence_states"]["bsr"]["strong"], "no_data")
        self.assertEqual(len(plain_product["source_details"]["seller"]), 1)
        self.assertEqual(plain_product["source_details"]["best_seller"], [])
        self.assertIsNone(plain_product["best_seller_evidence_best_rank"])
        self.assertIsNone(plain_product["new_release_evidence_best_rank"])
        self.assertIsNone(plain_product["bsr_evidence_best_sub_bsr"])

    def test_service_validates_schema(self) -> None:
        service = DashboardService(Path("output"))
        service.validate(MOCK_PRESENTATION_DATA)

        with self.assertRaises(DashboardDataValidationError):
            service.validate({"morning_brief": {}, "ideas": []})

    def test_service_handles_empty_csv_dataset(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            _write_csv(output_dir / "priority_board.csv", ["asin", "badges"], [])
            _write_csv(output_dir / "seller_intelligence.csv", ["seller_name", "products_tracked"], [])
            _write_csv(output_dir / "niche_intelligence.csv", ["niche", "products_tracked"], [])

            data = DashboardService(output_dir).load()

            self.assertEqual(data["products"], [])
            self.assertEqual(data["ideas"], [])
            self.assertEqual(data["competitors"], [])
            self.assertEqual(data["morning_brief"]["kpis"][0]["value"], "0")

    def test_service_reports_missing_dataset(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(DashboardDataMissing):
                DashboardService(Path(temp_dir)).load()

    def test_service_reports_corrupted_dashboard_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            (output_dir / "dashboard.json").write_text("{not-json", encoding="utf-8")

            with self.assertRaises(DashboardDataValidationError):
                DashboardService(output_dir).load()

    def test_generator_writes_friendly_error_pages_for_missing_data(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "v2"
            generate_dashboard_v2(output_dir)

            html = (output_dir / "index.html").read_text(encoding="utf-8")
            self.assertIn("Dashboard data unavailable", html)
            self.assertIn("analytics CSV artifacts", html)

    def test_v2_primary_pages_generate_from_real_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_service_fixture(root)
            output_dir = root / "v2"
            result = generate_dashboard_v2(output_dir)

            self.assertEqual(len(result["pages"]), 4)
            for _, filename, _ in V2_PAGE_ROUTES:
                self.assertTrue((output_dir / filename).exists(), filename)


def _write_service_fixture(output_dir: Path) -> None:
    _write_csv(
        output_dir / "priority_board.csv",
        [
            "asin",
            "primary_bucket",
            "badges",
            "decision_score",
            "title",
            "seller_name",
            "niche_primary",
            "source_name",
            "display_rank",
            "previous_display_rank",
            "display_rank_change",
            "opportunity_score",
            "product_url",
            "image_url",
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
            "evidence_count",
            "evidence_reasons",
        ],
        [
            {
                "asin": "B0REAL0001",
                "primary_bucket": "Must Review Today",
                "badges": "Top Winner; Fast Mover; POD",
                "decision_score": "144",
                "title": "Real Personalized Mug",
                "seller_name": "Real Seller",
                "niche_primary": "Dad Gift",
                "source_name": "Real Seller Store",
                "display_rank": "4",
                "previous_display_rank": "28",
                "display_rank_change": "24",
                "opportunity_score": "87",
                "product_url": "https://www.amazon.com/dp/B0REAL0001",
                "image_url": "https://example.com/mug.jpg",
                "seller_evidence_leader": "true",
                "seller_evidence_mover": "true",
                "seller_evidence_new_push": "false",
                "seller_evidence_best_rank": "6",
                "seller_evidence_source_count": "2",
                "best_seller_evidence_winner": "true",
                "best_seller_evidence_breakout": "true",
                "best_seller_evidence_stable": "false",
                "best_seller_evidence_best_rank": "28",
                "best_seller_evidence_source_count": "1",
                "new_release_evidence_rising": "true",
                "new_release_evidence_breakout": "true",
                "new_release_evidence_watch": "true",
                "new_release_evidence_best_rank": "18",
                "new_release_evidence_source_count": "1",
                "bsr_evidence_available": "true",
                "bsr_evidence_strong": "true",
                "bsr_evidence_very_strong": "true",
                "bsr_evidence_best_sub_bsr": "42",
                "bsr_evidence_best_sub_bsr_category": "Novelty Coffee Mugs",
                "evidence_source_family_count": "3",
                "evidence_source_families": "seller; category_best_seller; category_new_release",
                "evidence_count": "7",
                "evidence_reasons": "Seller rank #6 for 10 days; New Release improved from #60 to #18",
            },
            {
                "asin": "B0REAL0002",
                "primary_bucket": "Track",
                "badges": "POD",
                "decision_score": "45",
                "title": "Plain Seller Product",
                "seller_name": "Real Seller",
                "niche_primary": "General Gift",
                "source_name": "Real Seller Store",
                "display_rank": "80",
                "previous_display_rank": "90",
                "display_rank_change": "5",
                "opportunity_score": "45",
                "product_url": "https://www.amazon.com/dp/B0REAL0002",
                "image_url": "",
                "seller_evidence_leader": "false",
                "seller_evidence_mover": "false",
                "seller_evidence_new_push": "false",
                "seller_evidence_best_rank": "80",
                "seller_evidence_source_count": "1",
                "best_seller_evidence_winner": "false",
                "best_seller_evidence_breakout": "false",
                "best_seller_evidence_stable": "false",
                "best_seller_evidence_best_rank": "",
                "best_seller_evidence_source_count": "0",
                "new_release_evidence_rising": "false",
                "new_release_evidence_breakout": "false",
                "new_release_evidence_watch": "false",
                "new_release_evidence_best_rank": "",
                "new_release_evidence_source_count": "0",
                "bsr_evidence_available": "false",
                "bsr_evidence_strong": "false",
                "bsr_evidence_very_strong": "false",
                "bsr_evidence_best_sub_bsr": "",
                "bsr_evidence_best_sub_bsr_category": "",
                "evidence_source_family_count": "0",
                "evidence_source_families": "",
                "evidence_count": "",
                "evidence_reasons": "",
            },
        ],
    )
    _write_csv(
        output_dir / "lark_trend_alerts.csv",
        [
            "asin",
            "review_count",
            "pod_type",
            "primary_bsr_rank",
            "primary_bsr_category",
            "sub_bsr_rank",
            "sub_bsr_category",
            "seller_url",
        ],
        [
            {
                "asin": "B0REAL0001",
                "review_count": "17",
                "pod_type": "personalized_mug",
                "primary_bsr_rank": "1200",
                "primary_bsr_category": "Kitchen & Dining",
                "sub_bsr_rank": "42",
                "sub_bsr_category": "Novelty Coffee Mugs",
                "seller_url": "https://www.amazon.com/s?me=SELLER",
            },
            {
                "asin": "B0REAL0002",
                "review_count": "2",
                "pod_type": "unknown",
                "primary_bsr_rank": "",
                "primary_bsr_category": "",
                "sub_bsr_rank": "",
                "sub_bsr_category": "",
                "seller_url": "https://www.amazon.com/s?me=SELLER",
            },
        ],
    )
    _write_csv(
        output_dir / "product_trends.csv",
        ["asin", "latest_price"],
        [
            {"asin": "B0REAL0001", "latest_price": "19.99"},
            {"asin": "B0REAL0002", "latest_price": "14.50"},
        ],
    )
    _write_csv(
        output_dir / "historical_comparison.csv",
        [
            "asin",
            "source_type",
            "source_id",
            "source_name",
            "source_rank",
            "previous_source_rank",
            "source_rank_change",
            "source_days_seen",
            "source_observation_count",
            "category_name",
            "primary_bsr_rank",
            "primary_bsr_category",
            "sub_bsr_rank",
            "sub_bsr_category",
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
            "evidence_reasons",
        ],
        [
            {
                "asin": "B0REAL0001",
                "source_type": "seller",
                "source_id": "seller:amazon.com:real",
                "source_name": "Real Seller Store",
                "source_rank": "6",
                "previous_source_rank": "22",
                "source_rank_change": "16",
                "source_days_seen": "10",
                "source_observation_count": "3",
                "category_name": "",
                "primary_bsr_rank": "",
                "primary_bsr_category": "",
                "sub_bsr_rank": "",
                "sub_bsr_category": "",
                "seller_leader": "true",
                "seller_mover": "true",
                "seller_new_push": "false",
                "category_winner": "false",
                "category_breakout": "false",
                "category_stable": "false",
                "new_release_rising": "false",
                "new_release_breakout": "false",
                "new_release_watch": "false",
                "bsr_available": "false",
                "strong_sub_bsr": "false",
                "very_strong_sub_bsr": "false",
                "evidence_labels": "Seller Leader; Seller Mover",
                "evidence_reasons": "Seller rank #6 for 10 days; Seller improved from #22 to #6",
            },
            {
                "asin": "B0REAL0001",
                "source_type": "seller",
                "source_id": "seller:amazon.com:secondary",
                "source_name": "Secondary Seller Source",
                "source_rank": "12",
                "previous_source_rank": "15",
                "source_rank_change": "3",
                "source_days_seen": "3",
                "source_observation_count": "2",
                "category_name": "",
                "primary_bsr_rank": "",
                "primary_bsr_category": "",
                "sub_bsr_rank": "",
                "sub_bsr_category": "",
                "seller_leader": "false",
                "seller_mover": "false",
                "seller_new_push": "false",
                "category_winner": "false",
                "category_breakout": "false",
                "category_stable": "false",
                "new_release_rising": "false",
                "new_release_breakout": "false",
                "new_release_watch": "false",
                "bsr_available": "false",
                "strong_sub_bsr": "false",
                "very_strong_sub_bsr": "false",
                "evidence_labels": "",
                "evidence_reasons": "",
            },
            {
                "asin": "B0REAL0001",
                "source_type": "category_best_seller",
                "source_id": "category_best_seller:amazon.com:novelty-coffee-mugs",
                "source_name": "Best Sellers: Novelty Coffee Mugs",
                "source_rank": "28",
                "previous_source_rank": "60",
                "source_rank_change": "32",
                "source_days_seen": "9",
                "source_observation_count": "3",
                "category_name": "Novelty Coffee Mugs",
                "primary_bsr_rank": "1200",
                "primary_bsr_category": "Kitchen & Dining",
                "sub_bsr_rank": "42",
                "sub_bsr_category": "Novelty Coffee Mugs",
                "seller_leader": "false",
                "seller_mover": "false",
                "seller_new_push": "false",
                "category_winner": "true",
                "category_breakout": "true",
                "category_stable": "false",
                "new_release_rising": "false",
                "new_release_breakout": "false",
                "new_release_watch": "false",
                "bsr_available": "true",
                "strong_sub_bsr": "true",
                "very_strong_sub_bsr": "true",
                "evidence_labels": "Category Winner; Category Breakout; Very Strong Sub-BSR",
                "evidence_reasons": "Best Seller rank #28 for 9 days in Novelty Coffee Mugs; Very strong sub-category BSR #42 in Novelty Coffee Mugs",
            },
            {
                "asin": "B0REAL0001",
                "source_type": "category_new_release",
                "source_id": "category_new_release:amazon.com:novelty-coffee-mugs",
                "source_name": "New Releases: Novelty Coffee Mugs",
                "source_rank": "18",
                "previous_source_rank": "60",
                "source_rank_change": "42",
                "source_days_seen": "4",
                "source_observation_count": "2",
                "category_name": "Novelty Coffee Mugs",
                "primary_bsr_rank": "",
                "primary_bsr_category": "",
                "sub_bsr_rank": "",
                "sub_bsr_category": "",
                "seller_leader": "false",
                "seller_mover": "false",
                "seller_new_push": "false",
                "category_winner": "false",
                "category_breakout": "false",
                "category_stable": "false",
                "new_release_rising": "true",
                "new_release_breakout": "true",
                "new_release_watch": "true",
                "bsr_available": "false",
                "strong_sub_bsr": "false",
                "very_strong_sub_bsr": "false",
                "evidence_labels": "New Release Rising; New Release Breakout; New Release Watch",
                "evidence_reasons": "New Release improved from #60 to #18 in Novelty Coffee Mugs",
            },
            {
                "asin": "B0REAL0002",
                "source_type": "seller",
                "source_id": "seller:amazon.com:real",
                "source_name": "Real Seller Store",
                "source_rank": "80",
                "previous_source_rank": "90",
                "source_rank_change": "5",
                "source_days_seen": "8",
                "source_observation_count": "2",
                "category_name": "",
                "primary_bsr_rank": "",
                "primary_bsr_category": "",
                "sub_bsr_rank": "",
                "sub_bsr_category": "",
                "seller_leader": "false",
                "seller_mover": "false",
                "seller_new_push": "false",
                "category_winner": "false",
                "category_breakout": "false",
                "category_stable": "false",
                "new_release_rising": "false",
                "new_release_breakout": "false",
                "new_release_watch": "false",
                "bsr_available": "false",
                "strong_sub_bsr": "false",
                "very_strong_sub_bsr": "false",
                "evidence_labels": "",
                "evidence_reasons": "",
            },
        ],
    )
    _write_csv(
        output_dir / "seller_intelligence.csv",
        [
            "seller_name",
            "products_tracked",
            "new_wins",
            "rising_products",
            "pod_opportunities",
        ],
        [
            {
                "seller_name": "Real Seller",
                "products_tracked": "51",
                "new_wins": "3",
                "rising_products": "7",
                "pod_opportunities": "11",
            }
        ],
    )
    _write_csv(
        output_dir / "niche_intelligence.csv",
        [
            "date",
            "niche",
            "products_tracked",
            "opportunities",
            "rising_products",
            "max_opportunity_score",
            "niche_momentum_score",
            "top_seller",
            "top_product_title",
        ],
        [
            {
                "date": "2026-07-23",
                "niche": "Dad Gift",
                "products_tracked": "44",
                "opportunities": "8",
                "rising_products": "5",
                "max_opportunity_score": "87",
                "niche_momentum_score": "91",
                "top_seller": "Real Seller",
                "top_product_title": "Real Personalized Mug",
            }
        ],
    )


def _product_payload(product_explorer_path: Path) -> list[dict[str, object]]:
    html = product_explorer_path.read_text(encoding="utf-8")
    start_marker = '<script type="application/json" id="product-explorer-data">'
    end_marker = "</script>"
    start = html.index(start_marker) + len(start_marker)
    end = html.index(end_marker, start)
    payload = json.loads(html[start:end])
    if not isinstance(payload, list):
        raise AssertionError("Product Explorer payload must be a list.")
    return payload


def _seller_payload(html: str) -> list[dict[str, object]]:
    start_marker = '<script type="application/json" id="seller-explorer-data">'
    end_marker = "</script>"
    start = html.index(start_marker) + len(start_marker)
    end = html.index(end_marker, start)
    payload = json.loads(html[start:end])
    if not isinstance(payload, list):
        raise AssertionError("Seller Explorer payload must be a list.")
    return payload


def _seller_preview_product(index: int, **overrides: object) -> dict[str, object]:
    product = {
        "asin": f"B0SELL{index:04d}",
        "title": f"Seller Preview Product {index}",
        "seller": "Preview Seller",
        "product_type": "Custom Shirt",
        "product_url": f"https://www.amazon.com/example/dp/B0SELL{index:04d}?ref=test",
        "image_url": f"https://example.com/product-{index}.jpg",
        "source_rank": index,
    }
    product.update(overrides)
    return product


def _first_thead(html: str, table_marker: str) -> str:
    table_start = html.index(table_marker)
    start = html.index("<thead>", table_start)
    end = html.index("</thead>", start)
    return html[start:end]


def _detail_payload(detail_path: Path, product_id: str) -> dict[str, object]:
    text = detail_path.read_text(encoding="utf-8")
    marker = f"window.AMS_PRODUCT_EXPLORER_DETAILS[{json.dumps(product_id, ensure_ascii=True)}]="
    start = text.index(marker) + len(marker)
    end = text.rindex(";")
    payload = json.loads(text[start:end])
    if not isinstance(payload, dict):
        raise AssertionError("Product Explorer detail payload must be an object.")
    return payload


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    unittest.main()
