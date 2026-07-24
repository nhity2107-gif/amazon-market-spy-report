from __future__ import annotations

import unittest

from amazon_market_spy.niche import classify_niche


class NicheClassifierTests(unittest.TestCase):
    def test_fathers_day_dad_mug(self) -> None:
        result = classify_niche(
            title="Personalized Father's Day Dad Coffee Mug",
            category="Mugs",
            source_name="Mugs Best Sellers",
            pod_type="personalized_mug",
            pod_reason="personalized + mug",
        )

        self.assertIn(result["niche_primary"], {"Dad", "Father's Day"})
        self.assertTagsInclude(result, "Dad", "Father's Day", "Personalized Mug")
        self.assertGreaterEqual(int(result["niche_score"]), 40)

    def test_baptism_ornament(self) -> None:
        result = classify_niche(
            title="Personalized Baptism Ornament for Baby Christening",
            pod_type="custom_ornament",
            pod_reason="personalized + ornament",
        )

        self.assertEqual(result["niche_primary"], "Baptism")
        self.assertTagsInclude(result, "Baptism", "Christian", "Baby")

    def test_dog_mom_shirt(self) -> None:
        result = classify_niche(
            title="Dog Mom Custom Shirt",
            pod_type="custom_shirt",
            pod_reason="custom + shirt",
        )

        self.assertEqual(result["niche_primary"], "Dog Mom")
        self.assertTagsInclude(result, "Dog Mom", "Dog", "Mom", "Custom Shirt")

    def test_custom_camping_doormat(self) -> None:
        result = classify_niche(
            title="Custom Camping Doormat for Camper",
            pod_type="custom_doormat",
            pod_reason="custom + doormat",
        )

        self.assertIn(result["niche_primary"], {"Camping", "Custom Doormat"})
        self.assertTagsInclude(result, "Camping", "Custom Doormat")

    def test_graduation_gift(self) -> None:
        result = classify_niche(title="Class of 2026 Graduation Gift")

        self.assertEqual(result["niche_primary"], "Graduation")
        self.assertTagsInclude(result, "Graduation")

    def test_teacher_appreciation_mug(self) -> None:
        result = classify_niche(
            title="Teacher Appreciation Coffee Mug",
            pod_type="personalized_mug",
            pod_reason="mug",
        )

        self.assertEqual(result["niche_primary"], "Teacher")
        self.assertTagsInclude(result, "Teacher", "Personalized Mug")

    def test_memorial_ornament(self) -> None:
        result = classify_niche(
            title="In Memory Memorial Ornament",
            pod_reason="personalized + ornament",
        )

        self.assertEqual(result["niche_primary"], "Memorial")
        self.assertTagsInclude(result, "Memorial")

    def test_4th_of_july_onesie(self) -> None:
        result = classify_niche(
            title="4th of July Baby Onesie USA",
            pod_type="personalized_onesie",
            pod_reason="custom onesie",
        )

        self.assertEqual(result["niche_primary"], "4th of July")
        self.assertTagsInclude(result, "4th of July", "Baby", "Custom Onesie")

    def assertTagsInclude(self, result: dict[str, str], *expected: str) -> None:
        tags = {tag.strip() for tag in result["niche_tags"].split(";") if tag.strip()}
        for tag in expected:
            self.assertIn(tag, tags)


if __name__ == "__main__":
    unittest.main()
