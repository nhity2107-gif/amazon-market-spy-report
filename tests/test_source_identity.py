from __future__ import annotations

import unittest

from amazon_market_spy.source_identity import classify_source, normalize_source_identity, parse_source_rank, source_history_key


class SourceIdentityTests(unittest.TestCase):
    def test_seller_source_uses_seller_id_from_url(self) -> None:
        row = {
            "source_name": "Seller A",
            "source_type": "seller",
            "page_url": "https://www.amazon.com/s?i=merchant-items&me=A1SELLERA",
            "asin": "B0SELLER01",
            "display_rank": "5",
        }

        normalized = normalize_source_identity(row)

        self.assertEqual(normalized["source_type"], "seller")
        self.assertEqual(normalized["source_id"], "seller:amazon.com:A1SELLERA")
        self.assertEqual(normalized["source_rank"], "5")
        self.assertEqual(source_history_key(normalized), ("amazon.com", "seller", "seller:amazon.com:A1SELLERA", "B0SELLER01"))

    def test_best_seller_and_new_release_urls_get_distinct_category_identities(self) -> None:
        best_seller = classify_source(
            {
                "source_name": "Mugs Best Sellers",
                "source_type": "best_seller",
                "page_url": "https://www.amazon.com/Best-Sellers-Kitchen-Dining-Coffee-Mugs/zgbs/kitchen/367155011",
                "asin": "B0CATRANK1",
                "rank": "2",
            }
        )
        new_release = classify_source(
            {
                "source_name": "Mugs New Releases",
                "source_type": "new_release",
                "page_url": "https://www.amazon.com/gp/new-releases/kitchen/367155011",
                "asin": "B0CATRANK1",
                "rank": "2",
            }
        )

        self.assertEqual(best_seller.source_type, "category_best_seller")
        self.assertEqual(new_release.source_type, "category_new_release")
        self.assertNotEqual(best_seller.source_id, new_release.source_id)

    def test_search_result_source_uses_query_identity(self) -> None:
        row = normalize_source_identity(
            {
                "source_name": "Search - Grandpa Mug",
                "source_type": "category",
                "page_url": "https://www.amazon.com/s?k=grandpa+mug",
                "asin": "B0SEARCH01",
                "position": "7",
            }
        )

        self.assertEqual(row["source_type"], "search_result")
        self.assertEqual(row["source_id"], "search_result:amazon.com:k-grandpa-mug")
        self.assertEqual(row["source_rank"], "7")

    def test_rank_zero_is_rejected_and_missing_rank_stays_null(self) -> None:
        zero = normalize_source_identity({"source_name": "Seller A", "source_type": "seller", "asin": "B0ZERORANK", "rank": "0"})
        missing = normalize_source_identity({"source_name": "Seller A", "source_type": "seller", "asin": "B0MISSRANK"})

        self.assertEqual(parse_source_rank(zero), (None, "invalid_non_positive_rank"))
        self.assertEqual(zero["source_rank"], "")
        self.assertEqual(zero["rank_rejected_reason"], "invalid_non_positive_rank")
        self.assertEqual(parse_source_rank(missing), (None, "missing_rank"))
        self.assertEqual(missing["source_rank"], "")
        self.assertEqual(missing["rank_rejected_reason"], "missing_rank")


if __name__ == "__main__":
    unittest.main()
