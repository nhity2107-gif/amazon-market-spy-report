import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from amazon_market_spy.main_image_review import review_rows, reviews, MODEL, POLICY, lookup, save
from amazon_market_spy.dashboard_v2.pages import _pod_filter_bucket

class DecorationReviewTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        env = patch.dict(os.environ, {"POD_IMAGE_REVIEW_CACHE": str(Path(tmp.name)/"cache.json"), "GEMINI_API_KEY":"test-only"})
        env.start();self.addCleanup(env.stop)

    @patch("amazon_market_spy.main_image_review.analyze")
    @patch("amazon_market_spy.main_image_review.download", return_value=(b"main-image", "image/jpeg"))
    def test_only_image_bytes_go_to_vision_and_same_bytes_are_cached(self, download, analyze):
        analyze.return_value = {"status":"yes", "confidence":95, "evidence":"Graphic on front of mug"}
        row = {"image_url":"https://m.media-amazon.com/a.jpg", "title":"SECRET TITLE", "description":"DO NOT TRANSMIT"}
        review_rows([row, row], workers=1)
        self.assertEqual(analyze.call_count, 1)
        self.assertEqual(analyze.call_args.args, (b"main-image", "image/jpeg", "test-only"))
        review_rows([row], workers=1)
        self.assertEqual(analyze.call_count, 1)
        download.return_value = (b"changed-image", "image/jpeg")
        review_rows([row], workers=1)
        self.assertEqual(analyze.call_count, 2)

    @patch("amazon_market_spy.main_image_review.download", side_effect=ValueError("missing"))
    def test_download_failure_invalidates_stale_result(self, download):
        save({"u":{"image_url":"u", "policy":POLICY, "model":MODEL, "image_sha256":"abc", "status":"yes", "evidence":"old"}})
        result=review_rows([{"image_url":"u"}],workers=1)
        self.assertEqual(result["errors"],1)
        self.assertIsNone(lookup({"image_url":"u"}))

    @patch("amazon_market_spy.main_image_review.download", side_effect=HTTPError("u",429,"quota",{},None))
    def test_quota_stops_without_false_classification(self, download):
        result=review_rows([{"image_url":"u"}],workers=1)
        self.assertEqual(result["errors"],1)
        self.assertEqual(reviews(),{})

    def test_unknown_is_separate_ui_bucket(self):
        self.assertEqual(_pod_filter_bucket({"is_pod":"maybe"}),"unknown")
        self.assertEqual(_pod_filter_bucket({"is_pod":"yes"}),"pod")
