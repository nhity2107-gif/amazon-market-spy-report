from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from amazon_market_spy.artifacts import write_lark_opportunity_artifacts
from amazon_market_spy.reporting import read_csv


class ArtifactTests(unittest.TestCase):
    def test_today_is_focused_summary_and_product_discovery_is_primary(self) -> None:
        rows = [
            _row("B0TODAY001", "New Winner Personalized Mug for Dad", display_rank="4", previous_display_rank="25", display_rank_change="21", days_seen="2"),
            _row("B0TODAY002", "Fast Rising Baseball Shirt", display_rank="18", previous_display_rank="51", display_rank_change="33", days_seen="12"),
            _row("B0TODAY003", "Stable Winner Teacher T-Shirt", display_rank="2", previous_display_rank="3", display_rank_change="1", days_seen="20"),
        ]
        rows[0]["source_type"] = "new_release"
        rows[0]["source_name"] = "Mugs New Releases"
        rows[1]["pod_type"] = "custom_shirt"
        rows[1]["niche_primary"] = "Baseball"
        rows[2]["pod_type"] = "custom_shirt"
        rows[2]["niche_primary"] = "Teacher"

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            paths = write_lark_opportunity_artifacts(output_dir, rows, all_opportunities=rows, products=rows, include_non_pod=True)
            today_html = (output_dir / "priority_board.html").read_text(encoding="utf-8")
            discovery_html = (output_dir / "product_discovery.html").read_text(encoding="utf-8")
            products_html = (output_dir / "products.html").read_text(encoding="utf-8")
            csv_rows = read_csv(output_dir / "priority_board.csv")

        self.assertEqual(paths["product_discovery"], str(output_dir / "product_discovery.html"))
        self.assertIn("Product Discovery", today_html)
        self.assertIn("New Winners", today_html)
        self.assertIn("Fast Rising", today_html)
        self.assertIn("Competitor Launches", today_html)
        self.assertIn("Emerging Trends", today_html)
        self.assertNotIn("Must Review Today", today_html)
        self.assertLessEqual(today_html.count('<article class="card'), 30)
        self.assertIn("Signal Score", today_html)
        self.assertIn("Rank +21 in 7D", today_html)
        self.assertEqual(products_html, discovery_html)
        self.assertIn("New Winner", discovery_html)
        self.assertIn("Fast Rising", discovery_html)
        self.assertIn("Stable Winner", discovery_html)
        self.assertIn("Best Seller", discovery_html)
        self.assertIn("New Release", discovery_html)
        self.assertIn("Product Type", discovery_html)
        self.assertIn("Days Tracked", discovery_html)
        self.assertIn("View Details", discovery_html)
        self.assertIn("primary_bucket", csv_rows[0])
        self.assertIn("decision_score", csv_rows[0])
        self.assertNotIn("winner_signal_score", csv_rows[0])

    def test_legacy_pages_are_compatibility_redirects(self) -> None:
        row = _row("B0LEGACY01", "Legacy Personalized Mug", display_rank="2", previous_display_rank="8", display_rank_change="6")

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            write_lark_opportunity_artifacts(output_dir, [row], all_opportunities=[row], products=[row], include_non_pod=True)
            top_winners = (output_dir / "top_winners.html").read_text(encoding="utf-8")
            database = (output_dir / "database.html").read_text(encoding="utf-8")
            niches = (output_dir / "niche_intelligence.html").read_text(encoding="utf-8")

        self.assertIn("product_discovery.html?signal=stable-winner", top_winners)
        self.assertIn("product_discovery.html", database)
        self.assertIn("trend_explorer.html", niches)

    def test_competitor_page_summarizes_activity_and_limits_to_top10(self) -> None:
        rows = []
        for index in range(1, 13):
            row = _row(
                f"B0COMP{index:04d}",
                f"Competitor Product {index}",
                display_rank=str(index),
                previous_display_rank=str(index + 10),
                display_rank_change="10",
                days_seen="2" if index == 1 else "12",
            )
            row["source_type"] = "seller"
            row["source_name"] = "Seller A"
            row["seller_name"] = "Seller A"
            row["seller_id"] = "A1SELLER"
            rows.append(row)
        seller_rows = [_seller_row()]

        html = _render_named_page("competitor.html", products=rows, seller_rows=seller_rows)

        self.assertIn("New Launches", html)
        self.assertIn("Winners", html)
        self.assertIn("Rising Products", html)
        self.assertIn("Current Top10", html)
        self.assertIn("Dropped From Top10", html)
        self.assertIn("status-new", html)
        self.assertIn("status-rising", html)
        self.assertIn("Competitor Product 10", html)
        self.assertNotIn("Competitor Product 11", html)
        self.assertNotIn("Competitor Product 12", html)

    def test_trend_explorer_clusters_pod_idea_dimensions(self) -> None:
        rows = [
            _row("B0TREND001", "Funny Baseball Dad T-Shirt Gift", display_rank="7", previous_display_rank="30", display_rank_change="23"),
            _row("B0TREND002", "Best Dad Baseball Shirt for Fathers Day", display_rank="12", previous_display_rank="44", display_rank_change="32"),
            _row("B0TREND003", "Coffee Mom Mug Birthday Gift", display_rank="8", previous_display_rank="20", display_rank_change="12"),
        ]
        rows[0]["pod_type"] = "custom_shirt"
        rows[1]["pod_type"] = "custom_shirt"
        rows[2]["pod_type"] = "personalized_mug"

        html = _render_named_page("trend_explorer.html", products=rows)

        self.assertIn("Trend Explorer", html)
        self.assertIn("Dad Baseball", html)
        self.assertIn("Shirt", html)
        self.assertIn("products", html)
        self.assertIn("sellers", html)
        self.assertIn("Growth", html)
        self.assertIn("Signal", html)
        self.assertNotIn("Son Mug", html)

    def test_product_detail_pages_show_history_and_winner_journey(self) -> None:
        current = _row("B0DETAIL01", "Journey Personalized Mug", display_rank="3", previous_display_rank="28", display_rank_change="25", days_seen="15")
        current["source_type"] = "best_seller"
        current["source_name"] = "Mugs Best Sellers"
        history = [
            {**current, "date": "2026-06-01", "source_type": "new_release", "source_name": "Mugs New Releases", "display_rank": "40", "primary_bsr_rank": "90000"},
            {**current, "date": "2026-06-05", "source_type": "seller", "source_name": "Seller A", "display_rank": "8", "primary_bsr_rank": "70000"},
            {**current, "date": "2026-06-16", "source_type": "best_seller", "source_name": "Mugs Best Sellers", "display_rank": "3", "primary_bsr_rank": "12000"},
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            write_lark_opportunity_artifacts(
                output_dir,
                [current],
                all_opportunities=[current],
                products=[current],
                product_history_rows=history,
                include_non_pod=True,
            )
            detail_html = (output_dir / "product_detail" / "B0DETAIL01.html").read_text(encoding="utf-8")

        self.assertIn("Winner Journey", detail_html)
        self.assertIn("First Seen", detail_html)
        self.assertIn("New Release", detail_html)
        self.assertIn("Seller Top10", detail_html)
        self.assertIn("Best Seller", detail_html)
        self.assertIn("Stable Winner", detail_html)
        self.assertIn("Display Rank Timeline", detail_html)
        self.assertIn("BSR Timeline", detail_html)
        self.assertIn("Source History", detail_html)
        self.assertIn("#90,000", detail_html)
        self.assertIn("#12,000", detail_html)

    def test_missing_product_image_uses_placeholder(self) -> None:
        row = _row("B0NOIMG001", "No Image Personalized Mug", display_rank="1")
        row["image_url"] = ""
        row["local_image_path"] = ""

        html = _render_named_page("product_discovery.html", products=[row])

        self.assertIn("image-placeholder", html)
        self.assertIn("No image", html)
        self.assertNotIn('src=""', html)


def _row(
    asin: str,
    title: str,
    *,
    display_rank: str = "",
    previous_display_rank: str = "",
    display_rank_change: str = "",
    days_seen: str = "2",
) -> dict[str, str]:
    return {
        "date": "2026-06-16",
        "alert_type": "opportunity",
        "priority": "High",
        "opportunity_score": "90",
        "pod_component": "24",
        "momentum_component": "18",
        "market_component": "20",
        "competition_component": "8",
        "niche_component": "9",
        "asin": asin,
        "is_pod": "yes",
        "pod_type": "personalized_mug",
        "pod_score": "80",
        "pod_reason": "personalized + mug",
        "niche_primary": "Personalized Mug",
        "niche_secondary": "",
        "niche_tags": "Personalized Mug",
        "niche_score": "40",
        "niche_reason": "personalized mug + personalized_mug",
        "bsr_rank": "12000",
        "bsr_category": "Home & Kitchen",
        "category_ranks_raw": "#12000 in Home & Kitchen; #149 in Decorative Signs & Plaques",
        "primary_bsr_rank": "12000",
        "primary_bsr_category": "Home & Kitchen",
        "sub_bsr_rank": "149",
        "sub_bsr_category": "Decorative Signs & Plaques",
        "all_bsr_ranks": "#12000 in Home & Kitchen; #149 in Decorative Signs & Plaques",
        "subcategory_rank_score": "90",
        "display_rank": display_rank,
        "display_order": display_rank,
        "products_in_source": "100",
        "previous_display_rank": previous_display_rank,
        "display_rank_change": display_rank_change,
        "display_rank_pct_change": "",
        "display_rank_velocity": display_rank_change,
        "display_percentile": "",
        "image_url": "",
        "local_image_path": "",
        "review_count": "47",
        "review_rating": "4.8",
        "review_growth_7d": "12",
        "review_growth_30d": "30",
        "review_velocity_score": "15",
        "title": title,
        "source_name": "Mugs Best Sellers",
        "source_type": "best_seller",
        "seller_name": "Seller A",
        "seller_id": "A1SELLER",
        "seller_url": "https://www.amazon.com/s?me=A1SELLER",
        "category": "Mugs",
        "today_rank": display_rank,
        "rank_change": display_rank_change,
        "rank_direction": "up",
        "first_seen": "2026-06-15",
        "days_seen": days_seen,
        "product_url": f"https://www.amazon.com/dp/{asin}",
    }


def _seller_row() -> dict[str, str]:
    return {
        "seller_name": "Seller A",
        "seller_id": "A1SELLER",
        "source_name": "Seller A",
        "source_type": "seller",
        "products_tracked": "12",
        "new_wins": "1",
        "rising_products": "10",
        "average_rank": "5.50",
        "review_growth_7d": "12",
        "review_growth_30d": "30",
        "review_velocity_score": "15",
        "momentum_score": "88",
        "pod_products": "12",
        "pod_opportunities": "12",
        "pod_momentum_score": "84",
        "best_subcategory_rank": "55",
        "best_subcategory_product": "Competitor Product 1",
        "seller_url": "https://www.amazon.com/s?me=A1SELLER",
    }


def _render_named_page(
    page_name: str,
    *,
    products: list[dict[str, str]],
    seller_rows: list[dict[str, str]] | None = None,
) -> str:
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir)
        write_lark_opportunity_artifacts(
            output_dir,
            products,
            all_opportunities=products,
            products=products,
            seller_rows=seller_rows,
            include_non_pod=True,
        )
        return (output_dir / page_name).read_text(encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
