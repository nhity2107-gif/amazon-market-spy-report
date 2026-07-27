from __future__ import annotations

import contextlib
import csv
import io
import tempfile
import unittest
from pathlib import Path

from amazon_market_spy.artifacts import write_lark_opportunity_artifacts
from amazon_market_spy.cli import main
from amazon_market_spy.dashboard_v2 import generate_dashboard_v2
from amazon_market_spy.evidence_calibration import calibrate_evidence
from amazon_market_spy.evidence_review_analysis import (
    HUMAN_REVIEW_SUMMARY_FIELDS,
    PRODUCTION_THRESHOLDS,
    RECOMMENDATION_FIELDS,
    REVIEWER_AGREEMENT_FIELDS,
    SIGNAL_QUALITY_FIELDS,
    THRESHOLD_QUALITY_FIELDS,
    analyze_evidence_reviews,
    build_reviewer_agreement,
    build_signal_quality,
    build_threshold_quality,
    quality_metrics,
    recommendation_status,
)


class EvidenceReviewAnalysisTests(unittest.TestCase):
    def test_blank_and_insufficient_reviews_are_excluded_from_precision(self) -> None:
        metrics = quality_metrics([
            _review_row(review_label="high_value", research_priority="launch_research"),
            _review_row(review_label="potential", research_priority="watch"),
            _review_row(review_label="weak", research_priority="ignore"),
            _review_row(review_label="noise", research_priority="ignore"),
            _review_row(review_label="insufficient_data", research_priority="watch"),
            _review_row(
                review_label="",
                pod_validity="",
                idea_quality="",
                duplicability="",
                market_relevance="",
                research_priority="",
                reviewer="",
                reviewed_at="",
            ),
        ])

        self.assertEqual(metrics["reviewed_rows"], "5")
        self.assertEqual(metrics["valid_reviewed_rows"], "4")
        self.assertEqual(metrics["insufficient_data_rows"], "1")
        self.assertEqual(metrics["precision"], "0.5000")
        self.assertEqual(metrics["actionable_rate"], "0.6000")

    def test_invalid_labels_are_reported_and_zero_denominators_are_null(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            review_file = output_dir / "evidence_calibration_review.csv"
            _write_csv(review_file, [_review_row(review_label="great", reviewer="ann", reviewed_at="2026-07-23")])

            result = analyze_evidence_reviews(review_file, output_dir)
            summary = _read_csv(output_dir / "evidence_human_review_summary.csv")
            quality = _read_csv(output_dir / "evidence_signal_quality.csv")

            self.assertEqual(result["invalid_values"]["review_label"]["great"], 1)
            invalid_row = [row for row in summary if row["metric"] == "invalid_values_review_label"][0]
            self.assertEqual(invalid_row["value"], "1")
            seller_quality = [row for row in quality if row["signal"] == "seller_leader" and row["row_type"] == "signal_overall"][0]
            self.assertEqual(seller_quality["precision"], "")

    def test_quality_metrics_by_signal_are_calculated_correctly(self) -> None:
        quality = build_signal_quality([
            _review_row(sample_signal="seller_leader", review_label="high_value", research_priority="launch_research"),
            _review_row(sample_signal="seller_leader", review_label="potential", research_priority="watch"),
            _review_row(sample_signal="seller_leader", review_label="weak", research_priority="ignore"),
            _review_row(sample_signal="seller_mover", review_label="noise", research_priority="ignore"),
        ])
        by_signal = {row["signal"]: row for row in quality if row["row_type"] == "signal_overall"}

        self.assertEqual(by_signal["seller_leader"]["precision"], "0.6667")
        self.assertEqual(by_signal["seller_leader"]["launch_rate"], "0.3333")
        self.assertEqual(by_signal["seller_mover"]["noise_rate"], "1.0000")

    def test_threshold_join_is_deterministic(self) -> None:
        rows = [
            _review_row(sample_signal="seller_leader", asin="B0A", source_rank="5", source_days_seen="7", review_label="high_value"),
            _review_row(sample_signal="seller_leader", asin="B0B", source_rank="8", source_days_seen="8", review_label="weak"),
            _review_row(sample_signal="seller_leader", asin="B0C", source_rank="20", source_days_seen="2", review_label="potential"),
        ]
        threshold_rows = [
            {
                "simulation_signal": "seller_leader",
                "thresholds": "source_rank<=10;source_days_seen>=7",
                "matching_product_count": "2",
                "eligible_coverage_rate": "0.2000",
            },
            {
                "simulation_signal": "seller_leader",
                "thresholds": "source_rank<=5;source_days_seen>=7",
                "matching_product_count": "1",
                "eligible_coverage_rate": "0.1000",
            },
        ]

        first = build_threshold_quality(rows, threshold_rows)
        second = build_threshold_quality(rows, threshold_rows)

        self.assertEqual(first, second)
        self.assertEqual(first[0]["valid_reviewed_count"], "2")
        self.assertEqual(first[0]["precision"], "0.5000")
        self.assertEqual(first[1]["valid_reviewed_count"], "1")
        self.assertIn("low sample", first[1]["warning"])

    def test_reviewer_agreement_uses_marketplace_asin_and_signal_review_unit(self) -> None:
        rows = [
            _review_row(marketplace="amazon.com", asin="B0A", sample_signal="seller_leader", review_label="high_value", reviewer="ann"),
            _review_row(marketplace="amazon.com", asin="B0A", sample_signal="seller_leader", review_label="potential", reviewer="bob"),
            _review_row(marketplace="amazon.com", asin="B0A", sample_signal="seller_mover", review_label="noise", reviewer="ann"),
        ]
        agreement = build_reviewer_agreement(rows)
        review_label = [row for row in agreement if row["row_type"] == "summary" and row["field"] == "review_label"][0]
        disagreements = [row for row in agreement if row["row_type"] == "disagreement"]

        self.assertEqual(review_label["comparison_count"], "1")
        self.assertEqual(review_label["agreement_rate"], "0.0000")
        self.assertEqual(len(disagreements), 1)
        self.assertIn("amazon.com|B0A|seller_leader", disagreements[0]["review_unit"])

    def test_bsr_recommendation_is_ordinal_supporting_evidence(self) -> None:
        status, _confidence, reasoning = recommendation_status(
            "strong_sub_bsr",
            {"valid_reviewed_rows": "20", "precision": "0.8000", "noise_rate": "0.0000", "actionable_rate": "0.9000"},
            False,
        )

        self.assertEqual(status, "supporting_only")
        self.assertIn("ordinal", reasoning)

    def test_outputs_are_generated_and_production_thresholds_are_not_modified(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            review_file = output_dir / "evidence_calibration_review.csv"
            before = dict(PRODUCTION_THRESHOLDS)
            _write_csv(review_file, _review_fixture())

            result = analyze_evidence_reviews(review_file, output_dir)

            self.assertEqual(PRODUCTION_THRESHOLDS, before)
            self.assertFalse(result["insufficient_review"])
            for path in result["paths"].values():
                self.assertTrue(Path(path).exists(), path)
            self.assertIn("Evidence Human Review Analysis", (output_dir / "evidence_human_review_analysis.html").read_text(encoding="utf-8"))
            for filename, fields in [
                ("evidence_human_review_summary.csv", HUMAN_REVIEW_SUMMARY_FIELDS),
                ("evidence_signal_quality.csv", SIGNAL_QUALITY_FIELDS),
                ("evidence_threshold_quality.csv", THRESHOLD_QUALITY_FIELDS),
                ("evidence_reviewer_agreement.csv", REVIEWER_AGREEMENT_FIELDS),
                ("evidence_threshold_recommendations.csv", RECOMMENDATION_FIELDS),
            ]:
                with (output_dir / filename).open("r", encoding="utf-8-sig", newline="") as handle:
                    reader = csv.DictReader(handle)
                    self.assertEqual(reader.fieldnames, fields)

    def test_cli_analyze_reviews_reports_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            review_file = output_dir / "evidence_calibration_review.csv"
            _write_csv(review_file, [_review_row(review_label="")])
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                exit_code = main(["analyze-evidence-reviews", "--review-file", str(review_file), "--output", str(output_dir)])

            output = stdout.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("Evidence review input:", output)
            self.assertIn("Recommendation mode: diagnostic_only", output)
            self.assertTrue((output_dir / "evidence_human_review_analysis.html").exists())

    def test_existing_calibration_command_still_works(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            comparison_path = output_dir / "historical_comparison.csv"
            _write_csv(comparison_path, [_comparison_row()])
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                exit_code = main(["calibrate-evidence", "--output", str(output_dir), "--comparison", str(comparison_path)])

            self.assertEqual(exit_code, 0)
            self.assertTrue((output_dir / "evidence_calibration.html").exists())

    def test_v1_and_v2_generation_remain_valid(self) -> None:
        row = {
            "date": "2026-07-23",
            "alert_type": "opportunity",
            "priority": "High",
            "opportunity_score": "90",
            "asin": "B0REVW1001",
            "title": "Review Analysis V1 Mug",
            "product_url": "https://www.amazon.com/dp/B0REVW1001",
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
            "seller_name": "Review Seller",
            "source_name": "Review Seller",
            "source_type": "seller",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            paths = write_lark_opportunity_artifacts(output_dir, [row], all_opportunities=[row], products=[row], include_non_pod=True)
            v2_result = generate_dashboard_v2(output_dir / "v2")

            self.assertTrue(Path(paths["priority_board"]).exists())
            self.assertEqual(len(v2_result["pages"]), 4)


def _review_fixture() -> list[dict[str, str]]:
    rows = []
    for index in range(12):
        rows.append(
            _review_row(
                asin=f"B0SL{index:03d}",
                sample_signal="seller_leader",
                source_rank="5",
                source_days_seen="8",
                review_label="high_value" if index < 8 else "potential",
                research_priority="launch_research" if index < 6 else "watch",
                reviewer="ann" if index % 2 else "bob",
                reviewed_at="2026-07-23",
            )
        )
    for index in range(10):
        rows.append(
            _review_row(
                asin=f"B0SM{index:03d}",
                sample_signal="seller_mover",
                source_rank="35",
                source_rank_change="20",
                previous_source_rank="55",
                source_observation_count="3",
                review_label="potential" if index < 6 else "weak",
                research_priority="watch" if index < 7 else "ignore",
                reviewer="ann",
                reviewed_at="2026-07-23",
            )
        )
    for index in range(10):
        rows.append(
            _review_row(
                asin=f"B0NR{index:03d}",
                sample_signal="new_release_watch",
                source_rank="30",
                source_days_seen="5",
                pod_relevance="high",
                review_label="potential" if index < 5 else "noise",
                research_priority="watch" if index < 5 else "ignore",
                reviewer="carol",
                reviewed_at="2026-07-23",
            )
        )
    return rows


def _review_row(**overrides: str) -> dict[str, str]:
    row = {
        "sample_signal": "seller_leader",
        "sample_bucket": "threshold_near_rank",
        "marketplace": "amazon.com",
        "asin": "B0TEST",
        "title": "Reviewed Product",
        "seller": "Reviewed Seller",
        "product_type": "custom_shirt",
        "pod_relevance": "high",
        "review_count": "12",
        "review_rating": "4.7",
        "price": "19.99",
        "source_family": "seller",
        "source_name": "Reviewed Seller",
        "source_id": "seller:amazon.com:reviewed",
        "source_rank": "5",
        "previous_source_rank": "15",
        "source_rank_change": "10",
        "source_days_seen": "7",
        "source_observation_count": "2",
        "category": "seller",
        "sub_bsr_rank": "800",
        "sub_bsr_category": "Novelty Mugs",
        "primary_bsr_rank": "12000",
        "primary_bsr_category": "Home & Kitchen",
        "all_evidence_labels": "Seller Leader",
        "evidence_reasons": "Seller rank #5 for 7 days",
        "product_url": "https://www.amazon.com/dp/B0TEST",
        "image_url": "https://example.com/image.jpg",
        "review_label": "high_value",
        "pod_validity": "clear_pod",
        "idea_quality": "strong",
        "duplicability": "easy",
        "market_relevance": "high",
        "research_priority": "launch_research",
        "review_notes": "",
        "reviewer": "ann",
        "reviewed_at": "2026-07-23",
    }
    row.update(overrides)
    return row


def _comparison_row() -> dict[str, str]:
    row = {
        "date": "2026-07-23",
        "marketplace": "amazon.com",
        "asin": "B0COMP",
        "title": "Comparison Product",
        "seller_name": "Comparison Seller",
        "source_type": "seller",
        "source_id": "seller:amazon.com:comparison",
        "source_name": "Comparison Seller",
        "source_rank": "5",
        "previous_source_rank": "20",
        "source_rank_change": "15",
        "source_days_seen": "7",
        "source_observation_count": "2",
        "pod_relevance": "high",
        "review_count": "10",
        "review_rating": "4.5",
        "today_price": "19.99",
        "sub_bsr_rank": "800",
        "sub_bsr_category": "Novelty Mugs",
        "seller_leader": "true",
        "seller_mover": "true",
        "strong_sub_bsr": "true",
        "very_strong_sub_bsr": "true",
    }
    return row


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = list(dict.fromkeys(key for row in rows for key in row))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))
