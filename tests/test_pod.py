from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from amazon_market_spy.pod import build_seller_profiles, classify_pod, classify_pod_row, write_production_model_report, pod_allowed, ensure_pod_fields


class PodClassifierTests(unittest.TestCase):
    def test_classifies_personalized_mug_as_pod(self) -> None:
        result = classify_pod("Personalized Dog Mom Coffee Mug Custom Name Gift for Mom")

        self.assertEqual(result["is_pod"], "yes")
        self.assertEqual(result["production_model"], "pod")
        self.assertEqual(result["production_confidence"], "100")
        self.assertEqual(result["production_reason"], "Personalization detected on a decoratable product.")
        self.assertEqual(result["pod_type"], "personalized_mug")
        self.assertGreaterEqual(int(result["pod_score"]), 40)
        self.assertIn("personalization", result["pod_reason"])

    def test_classifies_physical_brand_bottle_as_non_pod(self) -> None:
        result = classify_pod("Stanley Quencher Stainless Steel Vacuum Insulated Tumbler with Lid and Straw")

        self.assertEqual(result["is_pod"], "no")
        self.assertEqual(result["production_model"], "non_pod")
        self.assertGreaterEqual(int(result["production_confidence"]), 95)
        self.assertEqual(result["pod_type"], "physical_brand_product")
        self.assertLess(int(result["pod_score"]), 25)
        self.assertIn("physical brand", result["pod_reason"])

    def test_strong_custom_signals_can_override_brand_signal(self) -> None:
        result = classify_pod("Custom Photo Stanley Name Tumbler Printed Gift for Mom")

        self.assertEqual(result["is_pod"], "yes")
        self.assertEqual(result["production_model"], "pod")
        self.assertGreaterEqual(int(result["pod_score"]), 40)
        self.assertIn("custom photo", result["pod_reason"])

    def test_classifies_hallmark_keepsake_as_non_pod(self) -> None:
        result = classify_pod("Hallmark Keepsake Harry Potter Christmas Ornament (Quidditch Supplies)")

        self.assertEqual(result["is_pod"], "no")
        self.assertEqual(result["production_model"], "non_pod")
        self.assertIn(result["pod_type"], {"retail_brand_product", "licensed_brand_product"})
        self.assertEqual(result["production_confidence"], "99")
        self.assertIn("Retail brand", result["production_reason"])

    def test_classifies_ordinary_non_custom_doormat_as_non_pod(self) -> None:
        result = classify_pod(
            'BEQHAUSE Dirt Trapper Door Mats 32" x 48", Non-Slip Washable Brown Doormat Indoor Entrance'
        )

        self.assertEqual(result["is_pod"], "no")
        self.assertEqual(result["production_model"], "non_pod")
        self.assertEqual(result["pod_type"], "retail_brand_product")
        self.assertIn("mass retail product", result["pod_reason"])

    def test_classifies_branded_funny_welcome_mat_as_non_pod(self) -> None:
        result = classify_pod("EARTHALL Funny Welcome Mats, Front Door Mat for Outside Entry")

        self.assertEqual(result["is_pod"], "no")
        self.assertEqual(result["production_model"], "non_pod")
        self.assertEqual(result["pod_type"], "retail_brand_product")

    def test_classifies_licensed_branded_ornament_as_non_pod(self) -> None:
        result = classify_pod("Hallmark Keepsake Disney Star Wars Christmas Ornament")

        self.assertEqual(result["is_pod"], "no")
        self.assertEqual(result["production_model"], "non_pod")
        self.assertEqual(result["pod_type"], "licensed_brand_product")
        self.assertIn("licensed franchise", result["pod_reason"])

    def test_classifies_personalized_doormat_as_pod(self) -> None:
        result = classify_pod("Personalized Teacher Classroom Doormat Custom Welcome Rug with Teacher Name")

        self.assertEqual(result["is_pod"], "yes")
        self.assertEqual(result["production_model"], "pod")
        self.assertEqual(result["pod_type"], "custom_doormat")

    def test_classifies_custom_name_shirt_as_pod(self) -> None:
        result = classify_pod("Custom Name Shirt Personalized Baseball Mom Shirt with Kids Name")

        self.assertEqual(result["is_pod"], "yes")
        self.assertEqual(result["production_model"], "pod")
        self.assertEqual(result["pod_type"], "custom_shirt")

    def test_classifies_fixed_design_printed_shirt_as_pod(self) -> None:
        result = classify_pod("Vintage Mountain Graphic Tee Printed Shirt")

        self.assertEqual(result["production_model"], "pod")
        self.assertEqual(result["is_pod"], "yes")
        self.assertGreaterEqual(int(result["production_confidence"]), 98)
        self.assertEqual(result["pod_type"], "printed_shirt")

    def test_classifies_non_personalized_quote_mug_as_pod(self) -> None:
        result = classify_pod("Funny Quote Coffee Mug for Coworker")

        self.assertEqual(result["production_model"], "pod")
        self.assertEqual(result["is_pod"], "yes")
        self.assertEqual(result["pod_type"], "quote_mug")

    def test_classifies_printed_ornament_as_pod(self) -> None:
        result = classify_pod("Printed Ceramic Christmas Ornament with Cardinal Artwork")

        self.assertEqual(result["production_model"], "pod")
        self.assertEqual(result["is_pod"], "yes")
        self.assertEqual(result["pod_type"], "printed_ornament")

    def test_elephant_shape_alone_is_not_decoration_evidence(self) -> None:
        result = classify_pod("Friendship Elephant Ornament")

        self.assertEqual(result["production_model"], "non_pod")
        self.assertEqual(result["is_pod"], "no")

    def test_classifies_printed_quote_doormat_as_pod(self) -> None:
        result = classify_pod("Funny Quote Printed Doormat for Front Porch")

        self.assertEqual(result["production_model"], "pod")
        self.assertEqual(result["is_pod"], "yes")
        self.assertEqual(result["pod_type"], "printed_doormat")

    def test_classifies_engraved_glass_as_pod(self) -> None:
        result = classify_pod("Engraved Whiskey Glass for Dad")

        self.assertEqual(result["production_model"], "pod")
        self.assertEqual(result["is_pod"], "yes")
        self.assertGreaterEqual(int(result["production_confidence"]), 97)
        self.assertEqual(result["pod_type"], "engraved_glass")

    def test_embroidery_alone_does_not_meet_print_or_engraving_requirement(self) -> None:
        result = classify_pod("Embroidered Baseball Cap with Mountain Artwork")

        self.assertEqual(result["production_model"], "non_pod")
        self.assertEqual(result["is_pod"], "no")

    def test_classifies_licensed_figurine_as_non_pod(self) -> None:
        result = classify_pod("Disney Star Wars Collectible Figurine")

        self.assertEqual(result["production_model"], "non_pod")
        self.assertEqual(result["is_pod"], "no")
        self.assertEqual(result["pod_type"], "licensed_brand_product")

    def test_classifies_unknown_physical_product_with_insufficient_evidence(self) -> None:
        result = classify_pod("Ceramic Table Vase Home Decor")

        self.assertEqual(result["is_pod"], "no")
        self.assertEqual(result["production_model"], "non_pod")
        self.assertIn("no product-level evidence", result["production_reason"])

    def test_strong_customization_overrides_generic_product_type(self) -> None:
        result = classify_pod("Add Photo Personalized Ceramic Ornament")

        self.assertEqual(result["is_pod"], "yes")
        self.assertEqual(result["production_model"], "pod")
        self.assertIn("add photo", result["pod_reason"])

    def test_brand_like_seller_name_does_not_reject_personalized_product(self) -> None:
        result = classify_pod_row(
            {
                "title": "Personalized Dog Dad Shirt Custom Name",
                "seller_name": "Hallmark Custom Studio",
            }
        )

        self.assertEqual(result["is_pod"], "yes")
        self.assertEqual(result["production_model"], "pod")
        self.assertEqual(result["pod_type"], "custom_shirt")

    def test_retail_brand_dictionary_classifies_lego_as_non_pod(self) -> None:
        result = classify_pod("LEGO Star Wars Building Set Collectible Toy")

        self.assertEqual(result["production_model"], "non_pod")
        self.assertEqual(result["is_pod"], "no")
        self.assertEqual(result["production_confidence"], "99")
        self.assertIn("Retail brand", result["production_reason"])

    def test_seller_profile_cannot_supply_missing_product_decoration(self) -> None:
        rows = [
            {"title": f"Personalized Family Mug Custom Name {index}", "seller_name": "Profile Decor Studio"}
            for index in range(5)
        ]
        profiles = build_seller_profiles(rows)
        result = classify_pod_row({"title": "Design 12", "seller_name": "Profile Decor Studio"}, profiles)

        self.assertEqual(result["production_model"], "non_pod")
        self.assertEqual(result["is_pod"], "no")
        self.assertIn("no product-level evidence", result["production_reason"])

    def test_strict_decoration_exclusions(self) -> None:
        for title in (
            "Plain Ceramic Mug", "Custom Size Brown Doormat", "Personalized Gift Jar",
            "Funny Halloween Witch Figurine", "Friendship Elephant Ornament",
            "Blank Mug for Sublimation Printing", "Unprinted Custom Name Shirt",
            "Mug without printed text", "Mug in a Printed Gift Box",
            "Glass with Engraved Gift Box", "Mug with Custom Name Gift Card",
            "Custom Name Embroidered Cap", "Laser Engraving Machine for Glass",
            "3D Printed Elephant Statue",
        ):
            with self.subTest(title=title):
                row = {"title": title, "seller_name": "Wrappiness", "category": "Printed Gifts"}
                self.assertFalse(pod_allowed(row))
                self.assertEqual(row["is_pod"], "no")

    def test_metadata_cannot_supply_decoration(self) -> None:
        for field in ("seller_name", "source_name", "category", "product_type", "brand", "product_url"):
            with self.subTest(field=field):
                row = {"title": "Ceramic Mug", field: "Custom Name Printed Mug"}
                self.assertFalse(pod_allowed(row))

    def test_cached_and_legacy_pod_labels_cannot_bypass_gate(self) -> None:
        for cached in (
            {"is_pod": "maybe", "pod_type": "unknown", "pod_score": "20", "pod_reason": "old"},
            classify_pod("Custom Name Printed Mug"),
        ):
            row = {"title": "Plain Ceramic Mug", **cached}
            ensure_pod_fields(row)
            self.assertEqual(row["is_pod"], "no")
            self.assertFalse(pod_allowed(row))

    def test_product_description_can_provide_direct_evidence(self) -> None:
        row = {"title": "Ceramic Coffee Mug", "description": "The mug is printed with a dog portrait."}
        self.assertTrue(pod_allowed(row))

    def test_packaging_evidence_is_not_product_evidence(self) -> None:
        row = {"title": "Glass Cup", "description": "The gift box is engraved with a name."}
        self.assertFalse(pod_allowed(row))

    def test_separate_product_decoration_is_kept_with_packaging(self) -> None:
        row = {"title": "Engraved Glass. Supplied in a gift box."}
        self.assertTrue(pod_allowed(row))

    def test_writes_production_model_report(self) -> None:
        row = {"asin": "B0REPORT01", "title": "Printed Quote Mug", "seller_name": "QA Seller"}
        row.update(classify_pod_row(row))

        with tempfile.TemporaryDirectory() as temp_dir:
            report_path = Path(temp_dir) / "production_model_report.csv"
            write_production_model_report(report_path, [row])
            with report_path.open("r", encoding="utf-8-sig", newline="") as handle:
                report_rows = list(csv.DictReader(handle))

        self.assertEqual(report_rows[0]["ASIN"], "B0REPORT01")
        self.assertEqual(report_rows[0]["Production Model"], "pod")
        self.assertGreaterEqual(int(report_rows[0]["Confidence"]), 90)
        self.assertIn("Production method", report_rows[0]["Reason"])


if __name__ == "__main__":
    unittest.main()
