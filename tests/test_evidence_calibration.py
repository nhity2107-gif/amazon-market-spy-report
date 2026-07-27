from __future__ import annotations

import csv
import contextlib
import io
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from amazon_market_spy.artifacts import write_lark_opportunity_artifacts
from amazon_market_spy.cli import main
from amazon_market_spy.dashboard_v2 import generate_dashboard_v2
from amazon_market_spy.evidence_calibration import (
    OVERLAP_FIELDS,
    REVIEW_FIELDS,
    SIGNAL_NAMES,
    SUMMARY_FIELDS,
    THRESHOLD_FIELDS,
    build_overlap_matrix,
    build_review_sample,
    build_signal_summary,
    build_threshold_simulation,
    calibrate_evidence,
    group_products,
    stats_for,
)


class EvidenceCalibrationTests(unittest.TestCase):
    def test_eligible_denominators_are_source_family_aware(self) -> None:
        groups = group_products(_fixture_rows())

        summary = {row["signal"]: row for row in build_signal_summary(groups)}

        self.assertEqual(summary["seller_leader"]["total_product_count"], "6")
        self.assertEqual(summary["seller_leader"]["eligible_product_count"], "3")
        self.assertEqual(summary["seller_leader"]["active_signal_count"], "1")
        self.assertEqual(summary["seller_leader"]["no_data_count"], "3")
        self.assertEqual(summary["seller_leader"]["false_count"], "2")
        self.assertEqual(summary["strong_sub_bsr"]["eligible_product_count"], "4")
        self.assertEqual(summary["strong_sub_bsr"]["active_signal_count"], "3")

    def test_no_data_is_not_counted_as_false(self) -> None:
        groups = group_products(_fixture_rows())
        summary = {row["signal"]: row for row in build_signal_summary(groups)}

        self.assertEqual(summary["category_winner"]["no_data_count"], "4")
        self.assertEqual(summary["category_winner"]["false_count"], "0")
        self.assertEqual(summary["new_release_watch"]["no_data_count"], "5")
        self.assertEqual(summary["new_release_watch"]["false_count"], "0")

    def test_missing_numeric_values_are_not_converted_to_zero(self) -> None:
        stats = stats_for([{"source_rank": ""}, {"source_rank": "10"}], lambda row: None if not row["source_rank"] else int(row["source_rank"]))

        self.assertEqual(stats["count"], "1")
        self.assertEqual(stats["missing"], "1")
        self.assertEqual(stats["median"], "10")

    def test_threshold_simulation_is_deterministic_and_does_not_modify_rows(self) -> None:
        rows = _fixture_rows()
        original = deepcopy(rows)
        groups = group_products(rows)

        first = build_threshold_simulation(groups)
        second = build_threshold_simulation(groups)

        self.assertEqual(first, second)
        self.assertEqual(rows, original)
        seller_mover = [
            row for row in first
            if row["simulation_signal"] == "seller_mover"
            and row["thresholds"] == "source_rank_change>=10;source_rank<=100;previous_source_rank=present;source_observation_count>=2"
        ][0]
        self.assertEqual(seller_mover["matching_product_count"], "2")

    def test_overlap_counts_and_jaccard_are_correct(self) -> None:
        groups = group_products(_fixture_rows())
        overlap = build_overlap_matrix(groups)
        by_pair = {(row["signal_a"], row["signal_b"]): row for row in overlap}

        pair = by_pair[("seller_leader", "seller_mover")]
        self.assertEqual(pair["intersection_count"], "1")
        self.assertEqual(pair["union_count"], "2")
        self.assertEqual(pair["jaccard_similarity"], "0.5000")

    def test_stratified_review_sample_is_deterministic_and_has_review_columns(self) -> None:
        groups = group_products(_fixture_rows())

        first = build_review_sample(groups)
        second = build_review_sample(groups)

        self.assertEqual(first, second)
        self.assertTrue(first)
        for column in ["review_label", "pod_validity", "idea_quality", "duplicability", "market_relevance", "research_priority", "review_notes", "reviewer", "reviewed_at"]:
            self.assertIn(column, first[0])
            self.assertEqual(first[0][column], "")
        seller_rows = [row for row in first if row["sample_signal"] in {"seller_leader", "seller_mover"}]
        self.assertGreaterEqual(len({row["asin"] for row in seller_rows}), 2)

    def test_csv_and_html_outputs_are_generated(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            comparison_path = output_dir / "historical_comparison.csv"
            _write_csv(comparison_path, _fixture_rows())

            result = calibrate_evidence(output_dir, comparison_path)

            self.assertEqual(result["product_count"], 6)
            for path in result["paths"].values():
                self.assertTrue(Path(path).exists(), path)
            self.assertIn("Evidence Calibration Report", (output_dir / "evidence_calibration.html").read_text(encoding="utf-8"))
            for filename, fields in [
                ("evidence_calibration_summary.csv", SUMMARY_FIELDS),
                ("evidence_threshold_simulation.csv", THRESHOLD_FIELDS),
                ("evidence_overlap_matrix.csv", OVERLAP_FIELDS),
                ("evidence_calibration_review.csv", REVIEW_FIELDS),
            ]:
                with (output_dir / filename).open("r", encoding="utf-8-sig", newline="") as handle:
                    reader = csv.DictReader(handle)
                    self.assertEqual(reader.fieldnames, fields)

    def test_cli_calibrate_evidence_reports_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            comparison_path = output_dir / "historical_comparison.csv"
            _write_csv(comparison_path, _fixture_rows())
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                exit_code = main(["calibrate-evidence", "--output", str(output_dir), "--comparison", str(comparison_path)])

            output = stdout.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("Evidence calibration input:", output)
            self.assertIn("Products analyzed: 6", output)
            self.assertIn("evidence_calibration_summary.csv", output)
            self.assertTrue((output_dir / "evidence_calibration.html").exists())

    def test_v1_and_v2_generation_still_succeed(self) -> None:
        row = {
            "date": "2026-07-23",
            "alert_type": "opportunity",
            "priority": "High",
            "opportunity_score": "90",
            "asin": "B0CALV1001",
            "title": "Calibration V1 Mug",
            "product_url": "https://www.amazon.com/dp/B0CALV1001",
            "is_pod": "yes",
            "pod_type": "personalized_mug",
            "pod_score": "80",
            "pod_reason": "personalized mug",
            "niche_primary": "Personalized Mug",
            "display_rank": "3",
            "display_order": "3",
            "previous_display_rank": "18",
            "display_rank_change": "15",
            "days_seen": "2",
            "seller_name": "Calibration Seller",
            "source_name": "Calibration Seller",
            "source_type": "seller",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            paths = write_lark_opportunity_artifacts(output_dir, [row], all_opportunities=[row], products=[row], include_non_pod=True)
            v2_result = generate_dashboard_v2(output_dir / "v2")

            self.assertTrue(Path(paths["priority_board"]).exists())
            self.assertEqual(len(v2_result["pages"]), 4)


def _fixture_rows() -> list[dict[str, str]]:
    base = {
        "date": "2026-07-23",
        "marketplace": "amazon.com",
        "seller_id": "",
        "seller_url": "",
        "page_type": "",
        "is_pod": "yes",
        "pod_type": "Custom Shirt",
        "pod_score": "80",
        "pod_reason": "fixture",
        "primary_bsr_rank": "",
        "primary_bsr_category": "",
        "sub_bsr_rank": "",
        "sub_bsr_category": "",
        "review_count": "12",
        "review_rating": "4.7",
        "today_price": "19.99",
        "product_url": "https://www.amazon.com/dp/FIXTURE",
        "image_url": "https://example.com/image.jpg",
        "evidence_labels": "",
        "evidence_reasons": "",
        **{signal: "false" for signal in SIGNAL_NAMES},
    }

    def row(**overrides: str) -> dict[str, str]:
        value = dict(base)
        value.update(overrides)
        return value

    return [
        row(
            asin="B0P1",
            title="Seller Leader Product",
            seller_name="Seller A",
            source_type="seller",
            source_id="seller:amazon.com:a",
            source_name="Seller A",
            source_rank="5",
            previous_source_rank="20",
            source_rank_change="15",
            source_days_seen="7",
            source_observation_count="3",
            pod_relevance="high",
            sub_bsr_rank="800",
            sub_bsr_category="Novelty Mugs",
            seller_leader="true",
            seller_mover="true",
            strong_sub_bsr="true",
            very_strong_sub_bsr="true",
            evidence_labels="Seller Leader; Seller Mover; Strong Sub-BSR; Very Strong Sub-BSR",
        ),
        row(
            asin="B0P1",
            title="Seller Leader Product",
            seller_name="Seller A",
            source_type="category_best_seller",
            source_id="category_best_seller:amazon.com:mugs",
            source_name="Best Sellers: Mugs",
            category="Mugs",
            source_rank="20",
            previous_source_rank="40",
            source_rank_change="20",
            source_days_seen="8",
            source_observation_count="3",
            pod_relevance="high",
            category_winner="true",
            category_breakout="true",
            evidence_labels="Category Winner; Category Breakout",
        ),
        row(
            asin="B0P2",
            title="Seller False Product",
            seller_name="Seller B",
            source_type="seller",
            source_id="seller:amazon.com:b",
            source_name="Seller B",
            source_rank="80",
            previous_source_rank="",
            source_rank_change="",
            source_days_seen="8",
            source_observation_count="2",
            pod_relevance="unknown",
        ),
        row(
            asin="B0P3",
            title="Category Product",
            seller_name="Seller C",
            source_type="category_best_seller",
            source_id="category_best_seller:amazon.com:signs",
            source_name="Best Sellers: Signs",
            category="Signs",
            source_rank="25",
            previous_source_rank="50",
            source_rank_change="25",
            source_days_seen="14",
            source_observation_count="5",
            pod_relevance="medium",
            sub_bsr_rank="6000",
            sub_bsr_category="Signs",
            category_winner="true",
            category_breakout="true",
            category_stable="true",
        ),
        row(
            asin="B0P4",
            title="New Release Product",
            seller_name="Seller D",
            source_type="category_new_release",
            source_id="category_new_release:amazon.com:mugs",
            source_name="New Releases: Mugs",
            category="Mugs",
            source_rank="20",
            previous_source_rank="60",
            source_rank_change="40",
            source_days_seen="4",
            source_observation_count="2",
            pod_relevance="high",
            sub_bsr_rank="200",
            sub_bsr_category="Novelty Mugs",
            new_release_rising="true",
            new_release_breakout="true",
            new_release_watch="true",
            strong_sub_bsr="true",
            very_strong_sub_bsr="true",
        ),
        row(
            asin="B0P5",
            title="BSR Only Product",
            seller_name="Seller E",
            source_type="unknown",
            source_id="unknown:amazon.com:fixture",
            source_name="Unknown Source",
            source_rank="",
            previous_source_rank="",
            source_rank_change="",
            source_days_seen="",
            source_observation_count="",
            pod_relevance="unknown",
            sub_bsr_rank="700",
            sub_bsr_category="Ornaments",
            strong_sub_bsr="true",
            very_strong_sub_bsr="true",
        ),
        row(
            asin="B0P6",
            title="Seller Mover Product",
            seller_name="Seller F",
            source_type="seller",
            source_id="seller:amazon.com:f",
            source_name="Seller F",
            source_rank="30",
            previous_source_rank="80",
            source_rank_change="50",
            source_days_seen="5",
            source_observation_count="2",
            pod_relevance="medium",
            seller_mover="true",
        ),
    ]


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({field for row in rows for field in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    unittest.main()
