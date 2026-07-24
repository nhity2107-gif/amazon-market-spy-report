from __future__ import annotations

import unittest

from amazon_market_spy.pod import classify_pod


class PodClassifierTests(unittest.TestCase):
    def test_classifies_personalized_mug_as_pod(self) -> None:
        result = classify_pod("Personalized Dog Mom Coffee Mug Custom Name Gift for Mom")

        self.assertEqual(result["is_pod"], "yes")
        self.assertEqual(result["pod_type"], "personalized_mug")
        self.assertGreaterEqual(int(result["pod_score"]), 40)
        self.assertIn("custom/personalized/engraved", result["pod_reason"])

    def test_classifies_physical_brand_bottle_as_non_pod(self) -> None:
        result = classify_pod("Stanley Quencher Stainless Steel Vacuum Insulated Tumbler with Lid and Straw")

        self.assertEqual(result["is_pod"], "no")
        self.assertEqual(result["pod_type"], "physical_brand_product")
        self.assertLess(int(result["pod_score"]), 25)
        self.assertIn("physical brand", result["pod_reason"])

    def test_strong_custom_signals_can_override_brand_signal(self) -> None:
        result = classify_pod("Custom Photo Stanley Name Tumbler Printed Gift for Mom")

        self.assertIn(result["is_pod"], {"yes", "maybe"})
        self.assertGreaterEqual(int(result["pod_score"]), 25)
        self.assertIn("custom photo", result["pod_reason"])


if __name__ == "__main__":
    unittest.main()
