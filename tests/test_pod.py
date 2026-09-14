import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from amazon_market_spy.pod import classify_pod, classify_pod_row, ensure_pod_fields, pod_allowed
from amazon_market_spy.main_image_review import POLICY, save


class PodClassifierTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = patch.dict(os.environ, {"POD_IMAGE_REVIEW_CACHE": str(Path(self.tmp.name) / "reviews.json")})
        self.env.start()
        self.addCleanup(self.env.stop)

    def review(self, status="yes", confidence=95):
        save({"https://m.media-amazon.com/a.jpg": {"image_url": "https://m.media-amazon.com/a.jpg", "policy": POLICY,
            "status": status, "confidence": confidence, "evidence": "Visible text on mug surface.", "image_sha256": "abc", "model": "test"}})

    def test_all_text_only_inputs_need_image_review(self):
        for text in ("Printed Quote Mug", "Blank Mug", "Stanley Bottle", "Custom Photo Mug", "Laser Engraved Sign", "Embroidery Machine"):
            with self.subTest(text=text):
                self.assertEqual(classify_pod(text)["is_pod"], "maybe")

    def test_same_image_same_decision_despite_conflicting_text(self):
        self.review()
        for title in ("Blank Mug", "Printed Gift", "Industrial Machine", ""):
            row = {"image_url": "https://m.media-amazon.com/a.jpg", "title": title, "seller_name": "random"}
            self.assertTrue(pod_allowed(row))
            self.assertEqual(row["production_confidence"], "95")

    def test_plain_image_excludes_even_with_personalization_keywords(self):
        self.review("no")
        row = {"image_url": "https://m.media-amazon.com/a.jpg", "title": "Custom Photo Printed Mug"}
        self.assertEqual(classify_pod_row(row)["is_pod"], "no")

    def test_changed_image_invalidates_complete_old_label(self):
        self.review()
        row = {"image_url": "https://m.media-amazon.com/a.jpg"}
        ensure_pod_fields(row)
        row["image_url"] = "https://m.media-amazon.com/b.jpg"
        ensure_pod_fields(row)
        self.assertEqual(row["is_pod"], "maybe")

    def test_legacy_yes_and_no_are_invalidated(self):
        for label in ("yes", "no"):
            row = {"is_pod": label, "production_model": "pod", "production_confidence": "100", "production_reason": "keywords",
                   "pod_type": "mug", "pod_score": "100", "pod_confidence": "high", "pod_reason": "keywords"}
            self.assertEqual(ensure_pod_fields(row)["is_pod"], "maybe")

    def test_uncertain_and_low_confidence_never_exclude(self):
        for status, confidence in (("uncertain", 95), ("no", 70), ("yes", 70)):
            self.review(status, confidence)
            self.assertEqual(classify_pod_row({"image_url": "https://m.media-amazon.com/a.jpg"})["is_pod"], "maybe")

    def test_old_policy_is_not_reused(self):
        save({"a": {"image_url":"a", "policy":"keyword-v1", "status":"yes", "image_sha256":"abc", "evidence":"printed title"}})
        self.assertEqual(classify_pod_row({"image_url":"a"})["is_pod"], "maybe")
