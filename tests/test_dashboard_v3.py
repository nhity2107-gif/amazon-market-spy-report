from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from amazon_market_spy.cli import main
from amazon_market_spy.dashboard_v2 import MOCK_PRESENTATION_DATA, V2_PAGE_ROUTES, generate_dashboard_v2
from amazon_market_spy.dashboard_v3 import V3_PAGE_ROUTES, generate_dashboard_v3, resolve_url_state
from amazon_market_spy.dashboard_v3.state import canonical_query_string


class DashboardV3RestoredV2ExperienceTests(unittest.TestCase):
    def test_v3_generation_writes_v2_page_routes_and_compatibility_alias(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "v3"
            result = generate_dashboard_v3(output_dir, data=MOCK_PRESENTATION_DATA)

            expected_files = {"index.html", "product_explorer.html", "competitor.html", "market_explorer.html"}
            generated_files = {Path(page["path"]).name for page in result["pages"]}

            self.assertEqual(generated_files, expected_files)
            self.assertEqual(Path(result["main_page"]), output_dir / "index.html")
            self.assertEqual(
                {alias["filename"]: alias["target"] for alias in result["aliases"]},
                {"competitor_explorer.html": "competitor.html"},
            )
            self.assertTrue((output_dir / "competitor_explorer.html").exists())

    def test_v3_routes_use_restored_v2_navigation_labels(self) -> None:
        route_labels = [route.label for route in V3_PAGE_ROUTES]
        route_filenames = [route.filename for route in V3_PAGE_ROUTES]

        self.assertEqual(
            route_labels,
            ["Home", "Product Explorer", "Competitor Explorer", "Market Explorer"],
        )
        self.assertEqual(
            route_filenames,
            ["index.html", "product_explorer.html", "competitor.html", "market_explorer.html"],
        )

    def test_v3_output_matches_v2_baseline_for_all_primary_pages(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            v2_dir = root / "v2"
            v3_dir = root / "v3"
            generate_dashboard_v2(v2_dir, data=MOCK_PRESENTATION_DATA)
            generate_dashboard_v3(v3_dir, data=MOCK_PRESENTATION_DATA)

            for _, filename, _ in V2_PAGE_ROUTES:
                with self.subTest(filename=filename):
                    self.assertEqual(
                        (v3_dir / filename).read_text(encoding="utf-8"),
                        (v2_dir / filename).read_text(encoding="utf-8"),
                    )

    def test_v3_output_contains_v2_shell_and_not_experimental_v3_flow(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "v3"
            generate_dashboard_v3(output_dir, data=MOCK_PRESENTATION_DATA)
            home_html = (output_dir / "index.html").read_text(encoding="utf-8")
            product_html = (output_dir / "product_explorer.html").read_text(encoding="utf-8")

        for token in [
            'class="top-shell"',
            'class="primary-nav"',
            "Dashboard Home",
            "Research Today",
            "Market Pulse",
            "Data Details",
            "Product Explorer",
            'class="product-workspace"',
            "data-filter-panel",
            "Evidence Inspector",
            "Saved Views",
            "Advanced Filters",
        ]:
            self.assertIn(token, home_html + product_html)

        for forbidden in [
            "data-v3-side-navigation",
            "data-v3-research-page",
            "data-v3-product-workspace-page",
            "Product Discovery",
            "Why It Surfaced",
            "Demand-centric",
            "Highlights",
            "Research Workspace",
            "Product Workspace",
        ]:
            self.assertNotIn(forbidden, home_html + product_html)

    def test_product_explorer_keeps_lazy_detail_chunks_under_restored_ui(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "v3"
            result = generate_dashboard_v3(output_dir, data=MOCK_PRESENTATION_DATA)
            html = (output_dir / "product_explorer.html").read_text(encoding="utf-8")
            detail_dir = output_dir / "product_explorer_details"
            detail_dir_exists = detail_dir.exists()
            detail_chunk_exists = any(detail_dir.glob("*.js"))

        self.assertGreater(len(result["assets"]), 0)
        self.assertTrue(detail_dir_exists)
        self.assertTrue(detail_chunk_exists)
        self.assertIn("document.createElement(\"script\")", html)
        self.assertIn("detailCache", html)
        self.assertIn("window.AMS_PRODUCT_EXPLORER_DETAILS", html)
        self.assertIn('id="product-explorer-data"', html)
        self.assertNotIn("product_workspace_details", html)
        self.assertNotIn("dashboard-v3-product-index", html)

    def test_v3_missing_data_uses_restored_v2_error_page(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "v3"
            generate_dashboard_v3(output_dir)
            html = (output_dir / "index.html").read_text(encoding="utf-8")

        self.assertIn("Dashboard data unavailable", html)
        self.assertIn("analytics CSV artifacts", html)
        self.assertIn('class="top-shell"', html)
        self.assertNotIn("data-v3-empty-state", html)

    def test_v3_url_aliases_still_resolve_v2_and_v3_query_parameters(self) -> None:
        state = resolve_url_state(
            "?q=mug"
            "&preset=research_today"
            "&view=fast_rising"
            "&type=Mug"
            "&product_type=Shirt"
            "&seller=Real%20Seller"
            "&direction=desc"
            "&dir=asc"
            "&focus=B0REAL0001"
            "&selected=B0REAL0002"
            "&ASIN=B0REAL0003"
            "&seller_evidence=seller_mover"
            "&best_seller_evidence=category_breakout"
            "&new_release_evidence=new_release_rising"
            "&supporting_evidence=very_strong_sub_bsr"
            "&evidence=category_winner"
            "&family=best_seller"
            "&quick=low_reviews"
            "&pod_relevance=high"
            "&marketplace=amazon.com"
            "&niche=dad%20gifts"
            "&has_bsr=yes"
            "&page=2"
            "&page_size=50"
        )

        self.assertEqual(state["q"], "mug")
        self.assertEqual(state["preset"], "research_today")
        self.assertEqual(state["view"], "fast_rising")
        self.assertEqual(state["product_type"], ["Mug", "Shirt"])
        self.assertEqual(state["seller"], ["Real Seller"])
        self.assertEqual(state["dir"], "asc")
        self.assertEqual(state["selected"], "B0REAL0003")
        self.assertEqual(state["family"], ["seller", "best_seller", "new_release", "supporting"])
        self.assertEqual(
            state["evidence"],
            [
                "seller_mover",
                "category_breakout",
                "new_release_rising",
                "very_strong_sub_bsr",
                "category_winner",
            ],
        )
        self.assertEqual(state["quick"], ["low_reviews"])
        self.assertEqual(state["pod_relevance"], "high")
        self.assertEqual(state["marketplace"], "amazon.com")
        self.assertEqual(state["niche"], "dad gifts")
        self.assertEqual(state["has_bsr"], "yes")
        self.assertEqual(state["page"], "2")
        self.assertEqual(state["page_size"], "50")

    def test_v3_url_state_serializes_to_canonical_aliases(self) -> None:
        state = resolve_url_state("?type=Mug&direction=desc&focus=B0REAL0001&seller_evidence=seller_mover")

        self.assertEqual(
            canonical_query_string(state),
            "product_type=Mug&family=seller&evidence=seller_mover&dir=desc&selected=B0REAL0001",
        )

    def test_cli_generate_dashboard_v3_reports_restored_pages(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "v3"
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = main(["generate-dashboard-v3", "--output", str(output_dir)])
            output = stdout.getvalue()

        self.assertEqual(exit_code, 0)
        self.assertIn("Dashboard V3 output directory:", output)
        self.assertIn("Dashboard V3 main page:", output)
        self.assertIn("Dashboard V3 compatibility aliases generated:", output)
        self.assertIn("Home", output)
        self.assertIn("Product Explorer", output)
        self.assertIn("competitor_explorer.html -> competitor.html", output)


if __name__ == "__main__":
    unittest.main()
