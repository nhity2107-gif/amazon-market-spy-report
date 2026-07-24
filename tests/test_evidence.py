from __future__ import annotations

import unittest

from amazon_market_spy.evidence import apply_observation_evidence, apply_product_evidence


class EvidenceTests(unittest.TestCase):
    def test_seller_signals_only_apply_to_seller_observations(self) -> None:
        seller = apply_observation_evidence(
            {
                "source_type": "seller",
                "source_rank": "6",
                "source_days_seen": "10",
                "source_observation_count": "3",
                "previous_source_rank": "20",
                "source_rank_change": "14",
                "is_pod": "yes",
                "pod_type": "personalized_mug",
                "pod_score": "55",
                "pod_reason": "custom",
            }
        )
        best_seller = apply_observation_evidence(
            {
                "source_type": "category_best_seller",
                "source_rank": "6",
                "source_days_seen": "10",
                "source_observation_count": "3",
                "previous_source_rank": "20",
                "source_rank_change": "14",
                "is_pod": "yes",
                "pod_type": "personalized_mug",
                "pod_score": "55",
                "pod_reason": "custom",
            }
        )

        self.assertEqual(seller["seller_leader"], "true")
        self.assertEqual(seller["seller_mover"], "true")
        self.assertEqual(best_seller["seller_leader"], "false")
        self.assertEqual(best_seller["seller_mover"], "false")

    def test_best_seller_signals_only_apply_to_category_best_seller(self) -> None:
        row = apply_observation_evidence(
            {
                "source_type": "category_best_seller",
                "source_rank": "24",
                "previous_source_rank": "51",
                "source_rank_change": "27",
                "source_observation_count": "4",
                "source_days_seen": "16",
                "category_name": "Novelty Coffee Mugs",
                "pod_relevance": "medium",
            }
        )
        seller = apply_observation_evidence(dict(row, source_type="seller"))

        self.assertEqual(row["category_winner"], "true")
        self.assertEqual(row["category_breakout"], "true")
        self.assertEqual(row["category_stable"], "true")
        self.assertEqual(seller["category_winner"], "false")

    def test_new_release_signals_only_apply_to_category_new_release(self) -> None:
        row = apply_observation_evidence(
            {
                "source_type": "category_new_release",
                "source_rank": "19",
                "previous_source_rank": "82",
                "source_rank_change": "63",
                "source_observation_count": "2",
                "source_days_seen": "4",
                "category_name": "Decorative Signs",
                "pod_relevance": "unknown",
            }
        )
        best_seller = apply_observation_evidence(dict(row, source_type="category_best_seller"))

        self.assertEqual(row["new_release_rising"], "true")
        self.assertEqual(row["new_release_breakout"], "true")
        self.assertEqual(row["new_release_watch"], "true")
        self.assertEqual(best_seller["new_release_rising"], "false")

    def test_missing_previous_rank_cannot_create_mover_rising_or_breakout(self) -> None:
        row = apply_observation_evidence(
            {
                "source_type": "category_new_release",
                "source_rank": "20",
                "source_rank_change": "80",
                "source_observation_count": "3",
                "source_days_seen": "5",
                "pod_relevance": "high",
            }
        )

        self.assertEqual(row["seller_mover"], "false")
        self.assertEqual(row["category_breakout"], "false")
        self.assertEqual(row["new_release_rising"], "false")
        self.assertEqual(row["new_release_breakout"], "false")

    def test_unknown_pod_relevance_is_not_treated_as_low(self) -> None:
        row = apply_observation_evidence(
            {
                "source_type": "category_best_seller",
                "source_rank": "8",
                "source_days_seen": "9",
                "source_observation_count": "2",
                "pod_relevance": "unknown",
            }
        )

        self.assertEqual(row["pod_relevance"], "unknown")
        self.assertEqual(row["category_winner"], "true")

    def test_bsr_non_positive_does_not_create_bsr_evidence(self) -> None:
        row = apply_observation_evidence({"source_type": "seller", "source_rank": "8", "sub_bsr_rank": "0"})

        self.assertEqual(row["bsr_available"], "false")
        self.assertEqual(row["strong_sub_bsr"], "false")
        self.assertEqual(row["very_strong_sub_bsr"], "false")

    def test_product_level_aggregation_keeps_source_families_separate(self) -> None:
        rows = apply_product_evidence(
            [
                {
                    "marketplace": "amazon.com",
                    "asin": "B0FAMILY01",
                    "source_type": "seller",
                    "source_id": "seller:amazon.com:A1",
                    "source_rank": "6",
                    "source_days_seen": "10",
                    "source_observation_count": "2",
                    "pod_relevance": "high",
                },
                {
                    "marketplace": "amazon.com",
                    "asin": "B0FAMILY01",
                    "source_type": "category_best_seller",
                    "source_id": "category_best_seller:amazon.com:mugs",
                    "source_rank": "25",
                    "source_days_seen": "8",
                    "source_observation_count": "2",
                    "pod_relevance": "high",
                },
                {
                    "marketplace": "amazon.com",
                    "asin": "B0FAMILY01",
                    "source_type": "category_new_release",
                    "source_id": "category_new_release:amazon.com:mugs",
                    "source_rank": "18",
                    "source_days_seen": "4",
                    "source_observation_count": "2",
                    "previous_source_rank": "60",
                    "source_rank_change": "42",
                    "pod_relevance": "high",
                },
            ]
        )

        self.assertEqual(rows[0]["seller_evidence_leader"], "true")
        self.assertEqual(rows[0]["best_seller_evidence_winner"], "true")
        self.assertEqual(rows[0]["new_release_evidence_breakout"], "true")
        self.assertEqual(rows[0]["evidence_source_family_count"], "3")
        self.assertEqual(rows[0]["seller_evidence_best_rank"], "6")
        self.assertEqual(rows[0]["best_seller_evidence_best_rank"], "25")
        self.assertEqual(rows[0]["new_release_evidence_best_rank"], "18")

    def test_multiple_seller_sources_aggregate_without_merging_history(self) -> None:
        rows = apply_product_evidence(
            [
                {
                    "marketplace": "amazon.com",
                    "asin": "B0SELLERS1",
                    "source_type": "seller",
                    "source_id": "seller:amazon.com:A1",
                    "source_rank": "9",
                    "source_days_seen": "7",
                    "source_observation_count": "2",
                    "pod_relevance": "high",
                },
                {
                    "marketplace": "amazon.com",
                    "asin": "B0SELLERS1",
                    "source_type": "seller",
                    "source_id": "seller:amazon.com:A2",
                    "source_rank": "18",
                    "source_days_seen": "3",
                    "source_observation_count": "1",
                    "pod_relevance": "high",
                },
            ]
        )

        self.assertEqual(rows[0]["seller_evidence_source_count"], "2")
        self.assertEqual(rows[0]["seller_evidence_best_rank"], "9")
        self.assertEqual(rows[0]["seller_evidence_leader"], "true")
        self.assertEqual(rows[0]["seller_evidence_new_push"], "true")

    def test_evidence_reasons_are_human_readable(self) -> None:
        row = apply_observation_evidence(
            {
                "source_type": "category_new_release",
                "source_rank": "19",
                "previous_source_rank": "82",
                "source_rank_change": "63",
                "source_observation_count": "2",
                "source_days_seen": "4",
                "category_name": "Novelty Coffee Mugs",
                "sub_bsr_rank": "842",
                "sub_bsr_category": "Novelty Coffee Mugs",
                "pod_relevance": "high",
            }
        )

        self.assertIn("New Release improved from #82 to #19", row["evidence_reasons"])
        self.assertIn("Sub-category BSR #842 in Novelty Coffee Mugs", row["evidence_reasons"])
        self.assertIn("New Release Breakout", row["evidence_labels"])


if __name__ == "__main__":
    unittest.main()
