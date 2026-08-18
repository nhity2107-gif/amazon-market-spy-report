from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from amazon_market_spy.cli import main
from amazon_market_spy.notifications import (
    DEFAULT_REPORT_URL,
    LarkNotificationError,
    build_lark_interactive_card_payloads,
    build_lark_notification_message,
    send_lark_interactive_cards,
    send_lark_message,
    upload_lark_image,
)
from amazon_market_spy.reporting import (
    LARK_TREND_ALERT_FIELDS,
    PRODUCT_FIELDS,
    NICHE_INTELLIGENCE_FIELDS,
    SELLER_INTELLIGENCE_FIELDS,
    TREND_ALERT_FIELDS,
    write_csv,
)


class NotificationTests(unittest.TestCase):
    def test_build_lark_notification_message_summarizes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "output"
            write_csv(
                output_dir / "lark_trend_alerts.csv",
                [
                    {
                        "alert_type": "rising",
                        "opportunity_score": "70",
                        "asin": "B0RISING11",
                        "title": "Rising Personalized Coffee Mug",
                        "source_name": "Pawfect House Gifts (PFH)",
                        "seller_name": "Pawfect House Gifts (PFH)",
                        "today_rank": "4",
                    },
                    {
                        "alert_type": "new_win",
                        "opportunity_score": "95",
                        "asin": "B0NEWWIN11",
                        "title": "New Winner Personalized Coffee Mug",
                        "source_name": "LASFOUR (Warrior)",
                        "seller_name": "LASFOUR (Warrior)",
                        "today_rank": "2",
                    },
                    {
                        "alert_type": "opportunity",
                        "opportunity_score": "60",
                        "asin": "B0OPPORT11",
                        "title": "Manual Review Personalized Coffee Mug",
                        "source_name": "Best Sellers",
                        "today_rank": "10",
                    },
                ],
                LARK_TREND_ALERT_FIELDS,
            )
            write_csv(
                output_dir / "seller_intelligence.csv",
                [
                    {
                        "seller_name": "LASFOUR (Warrior)",
                        "products_tracked": "4",
                        "momentum_score": "180",
                    },
                    {
                        "seller_name": "Pawfect House Gifts (PFH)",
                        "products_tracked": "3",
                        "momentum_score": "120",
                    },
                ],
                SELLER_INTELLIGENCE_FIELDS,
            )
            write_csv(
                output_dir / "niche_intelligence.csv",
                [
                    {
                        "date": "2026-06-16",
                        "niche": "Dog Mom",
                        "niche_group": "pet",
                        "products_tracked": "4",
                        "pod_products": "4",
                        "opportunities": "3",
                        "new_wins": "2",
                        "rising_products": "1",
                        "avg_opportunity_score": "85.00",
                        "max_opportunity_score": "95",
                        "avg_rank": "4.00",
                        "best_rank": "2",
                        "avg_bsr_rank": "1200.00",
                        "best_bsr_rank": "800",
                        "total_review_growth": "18",
                        "avg_review_rating": "4.8",
                        "top_seller": "LASFOUR (Warrior)",
                        "top_product_asin": "B0NEWWIN11",
                        "top_product_title": "New Winner Mug",
                        "top_product_url": "https://www.amazon.com/dp/B0NEWWIN11",
                        "top_product_image_url": "",
                        "niche_momentum_score": "91",
                    }
                ],
                NICHE_INTELLIGENCE_FIELDS,
            )
            write_csv(
                output_dir / "latest_products.csv",
                [
                    {
                        "asin": "B0MOVE001",
                        "title": "Moving Personalized Mug",
                        "display_rank": "3",
                        "previous_display_rank": "31",
                        "display_rank_change": "28",
                        "display_rank_velocity": "28.00",
                        "display_percentile": "3.70",
                        "products_in_source": "81",
                        "opportunity_score": "95",
                    }
                ],
                PRODUCT_FIELDS,
            )

            message = build_lark_notification_message(output_dir)

        self.assertIn("Products tracked: 7", message)
        self.assertIn("New Wins: 1", message)
        self.assertIn("Rising: 1", message)
        self.assertIn("Top 20 opportunities:", message)
        self.assertIn("Top Movers Today:", message)
        self.assertIn("#31 -> #3 (+28)", message)
        self.assertLess(
            message.index("95 - New Winner Personalized Coffee Mug"),
            message.index("70 - Rising Personalized Coffee Mug"),
        )
        self.assertIn("Top Sellers:", message)
        self.assertIn("1. LASFOUR (Warrior)", message)
        self.assertIn("2. Pawfect House Gifts (PFH)", message)
        self.assertIn("Top Niches Today:", message)
        self.assertIn("1. Dog Mom - momentum 91 - 2 new wins", message)
        self.assertNotIn("Competitor Store", message)
        self.assertNotIn("momentum 180", message)
        self.assertIn("View live report:", message)
        self.assertIn(DEFAULT_REPORT_URL, message)
        self.assertNotIn("Local report path:", message)
        self.assertNotIn("output/top_opportunities.html", message)

    def test_build_lark_notification_message_can_include_local_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "output"
            write_csv(output_dir / "lark_trend_alerts.csv", [], LARK_TREND_ALERT_FIELDS)
            write_csv(output_dir / "seller_intelligence.csv", [], SELLER_INTELLIGENCE_FIELDS)

            message = build_lark_notification_message(
                output_dir,
                report_url="https://example.com/live/",
                include_local_path=True,
            )

        self.assertIn("View live report:\nhttps://example.com/live/", message)
        self.assertIn("Local report path:", message)
        self.assertIn("output/index.html", message)

    def test_build_lark_notification_message_limits_opportunity_lines(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "output"
            write_csv(
                output_dir / "lark_trend_alerts.csv",
                [
                    {
                        "alert_type": "opportunity",
                        "opportunity_score": str(101 - index),
                        "asin": f"B0NOTICE{index:02d}",
                        "title": f"Personalized Opportunity Coffee Mug {index}",
                        "source_name": "Best Sellers",
                        "today_rank": str(index),
                    }
                    for index in range(1, 26)
                ],
                LARK_TREND_ALERT_FIELDS,
            )
            write_csv(output_dir / "seller_intelligence.csv", [], SELLER_INTELLIGENCE_FIELDS)

            message = build_lark_notification_message(output_dir)

        self.assertIn("Personalized Opportunity Coffee Mug 20", message)
        self.assertNotIn("Personalized Opportunity Coffee Mug 21", message)

    def test_send_lark_message_posts_text_payload(self) -> None:
        class FakeResponse:
            status = 200

            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, *args: object) -> None:
                return None

            def read(self) -> bytes:
                return b"ok"

        with patch("amazon_market_spy.notifications.urlopen", return_value=FakeResponse()) as urlopen:
            send_lark_message("https://example.invalid/webhook", "Daily summary")

        request = urlopen.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(request.full_url, "https://example.invalid/webhook")
        self.assertEqual(payload, {"msg_type": "text", "content": {"text": "Daily summary"}})

    def test_build_lark_interactive_card_payloads_creates_summary_and_product_cards(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "output"
            write_csv(
                output_dir / "lark_trend_alerts.csv",
                [
                    {
                        "date": "2026-06-18",
                        "alert_type": "rising",
                        "opportunity_score": "70",
                        "asin": "B0RISING11",
                        "title": "Rising Personalized Coffee Mug",
                        "image_url": "https://example.com/rising.jpg",
                        "seller_name": "Pawfect House Gifts (PFH)",
                        "today_rank": "4",
                        "display_rank": "4",
                        "previous_display_rank": "18",
                        "primary_bsr_rank": "65003",
                        "primary_bsr_category": "Home & Kitchen",
                        "sub_bsr_rank": "149",
                        "sub_bsr_category": "Decorative Signs & Plaques",
                        "niche_primary": "Dog Mom",
                        "product_url": "https://www.amazon.com/dp/B0RISING11",
                    },
                    {
                        "date": "2026-06-18",
                        "alert_type": "new_win",
                        "opportunity_score": "95",
                        "asin": "B0NEWWIN11",
                        "title": "New Winner Personalized Coffee Mug",
                        "image_url": "https://example.com/new-win.jpg",
                        "seller_name": "LASFOUR (Warrior)",
                        "today_rank": "2",
                        "display_rank": "2",
                        "previous_display_rank": "31",
                        "primary_bsr_rank": "1200",
                        "primary_bsr_category": "Kitchen & Dining",
                        "sub_bsr_rank": "12",
                        "sub_bsr_category": "Coffee Mugs",
                        "review_count": "1234",
                        "review_rating": "4.7",
                        "niche_primary": "Dad Gift",
                        "product_url": "https://www.amazon.com/dp/B0NEWWIN11",
                    },
                ],
                LARK_TREND_ALERT_FIELDS,
            )
            write_csv(
                output_dir / "seller_intelligence.csv",
                [{"seller_name": "LASFOUR (Warrior)", "products_tracked": "4", "momentum_score": "180"}],
                SELLER_INTELLIGENCE_FIELDS,
            )
            write_csv(
                output_dir / "niche_intelligence.csv",
                [
                    {"niche": "Dad Gift", "niche_momentum_score": "91"},
                    {"niche": "Dog Mom", "niche_momentum_score": "80"},
                ],
                NICHE_INTELLIGENCE_FIELDS,
            )
            (output_dir / "lark_image_keys.json").write_text(
                json.dumps(
                    {
                        "B0NEWWIN11": {
                            "image_key": "img_v3_cached_new_win",
                            "image_url": "https://example.com/new-win.jpg",
                        }
                    }
                ),
                encoding="utf-8",
            )

            payloads = build_lark_interactive_card_payloads(
                output_dir,
                report_url="https://example.com/report/",
                top_products=1,
            )

        self.assertEqual(len(payloads), 2)
        self.assertTrue(all(payload["msg_type"] == "interactive" for payload in payloads))
        summary_card = payloads[0]["card"]
        product_card = payloads[1]["card"]
        summary_json = json.dumps(summary_card)
        product_json = json.dumps(product_card)
        self.assertIn("Amazon POD Market Spy Summary", summary_json)
        self.assertEqual(summary_card["header"]["template"], "blue")
        self.assertEqual(summary_card["header"]["subtitle"]["content"], "Daily opportunity briefing")
        self.assertEqual(
            sum(1 for element in summary_card["elements"] if element["tag"] == "column_set"),
            2,
        )
        self.assertIn("Report Date", summary_json)
        self.assertIn("2026-06-18", summary_json)
        self.assertIn("Products Tracked", summary_json)
        self.assertIn("New Wins", summary_json)
        self.assertIn("Rising Products", summary_json)
        self.assertIn("High Opportunity Products", summary_json)
        self.assertIn("Top Niches", summary_json)
        self.assertIn("Top Sellers", summary_json)
        self.assertIn("Dad Gift", summary_json)
        self.assertIn("LASFOUR (Warrior)", summary_json)
        self.assertIn("View Dashboard", summary_json)
        self.assertIn("https://example.com/report/", summary_json)
        self.assertIn("img_v3_cached_new_win", product_json)
        self.assertIn('"tag": "img"', product_json)
        self.assertNotIn("[Product image]", product_json)
        self.assertEqual(product_card["header"]["template"], "green")
        self.assertTrue(product_card["config"]["enable_forward"])
        self.assertTrue(any(element["tag"] == "column_set" for element in product_card["elements"]))
        self.assertIn("New Win", product_json)
        self.assertIn("New Winner Personalized Coffee Mug", product_json)
        self.assertIn("LASFOUR (Warrior)", product_json)
        self.assertIn("Opportunity Score", product_json)
        self.assertIn("Display Rank Movement", product_json)
        self.assertIn("#31 -> #2", product_json)
        self.assertIn("#1,200 in Kitchen & Dining", product_json)
        self.assertIn("#12 in Coffee Mugs", product_json)
        self.assertIn("1,234 reviews / 4.7 stars", product_json)
        self.assertIn("Dad Gift", product_json)
        self.assertIn("Open Amazon", product_json)
        self.assertIn("View Dashboard", product_json)
        self.assertIn("https://www.amazon.com/dp/B0NEWWIN11", product_json)
        self.assertNotIn("Rising Personalized Coffee Mug", product_json)

    def test_lark_product_card_uses_signal_color_and_rank_confidence_warning(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "output"
            write_csv(
                output_dir / "lark_trend_alerts.csv",
                [
                    {
                        "date": "2026-06-18",
                        "alert_type": "rising",
                        "opportunity_score": "88",
                        "asin": "B0RISING12",
                        "title": "Rising Personalized Ornament",
                        "seller_name": "Signal Seller",
                        "today_rank": "3",
                        "previous_display_rank": "22",
                        "rank_parse_confidence": "medium",
                        "product_url": "https://www.amazon.com/dp/B0RISING12",
                    }
                ],
                LARK_TREND_ALERT_FIELDS,
            )

            payloads = build_lark_interactive_card_payloads(output_dir, top_products=1)

        product_card = payloads[1]["card"]
        product_json = json.dumps(product_card)
        self.assertEqual(product_card["header"]["template"], "orange")
        self.assertIn("🚀 Rising", product_card["header"]["title"]["content"])
        self.assertIn("BSR confidence: medium", product_json)
        self.assertIn("#22 -> #3", product_json)

    def test_build_lark_interactive_card_payloads_respects_top_products_limit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "output"
            write_csv(
                output_dir / "lark_trend_alerts.csv",
                [
                    {
                        "date": "2026-06-18",
                        "alert_type": "opportunity",
                        "opportunity_score": str(100 - index),
                        "asin": f"B0CARD{index:05d}",
                        "title": f"Card Limit Product {index}",
                        "seller_name": "Limit Seller",
                        "today_rank": str(index),
                    }
                    for index in range(1, 6)
                ],
                LARK_TREND_ALERT_FIELDS,
            )

            payloads = build_lark_interactive_card_payloads(output_dir, top_products=10)

        self.assertEqual(len(payloads), 6)
        payload_json = json.dumps(payloads)
        self.assertIn("Card Limit Product 1", payload_json)
        self.assertIn("Card Limit Product 5", payload_json)
        self.assertNotIn("Card Limit Product 6", payload_json)

    def test_build_lark_interactive_card_payloads_falls_back_to_trend_alerts_for_cards(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "output"
            write_csv(output_dir / "lark_trend_alerts.csv", [], LARK_TREND_ALERT_FIELDS)
            write_csv(
                output_dir / "trend_alerts.csv",
                [
                    {
                        "date": "2026-06-18",
                        "classification": "rising",
                        "opportunity_score": "88",
                        "asin": "B0LATEST01",
                        "title": "Latest Product Opportunity",
                        "image_url": "https://example.com/latest.jpg",
                        "seller_name": "Latest Seller",
                        "today_rank": "5",
                        "previous_display_rank": "20",
                        "bsr_rank": "65003",
                        "bsr_category": "Home & Kitchen",
                        "sub_bsr_rank": "149",
                        "sub_bsr_category": "Decorative Signs & Plaques",
                        "review_count": "48",
                        "rating": "4.6",
                        "niche_primary": "Pet Gift",
                        "product_url": "https://www.amazon.com/dp/B0LATEST01",
                    }
                ],
                TREND_ALERT_FIELDS,
            )

            payloads = build_lark_interactive_card_payloads(output_dir, top_products=5)

        self.assertEqual(len(payloads), 2)
        payload_json = json.dumps(payloads)
        self.assertIn("Latest Product Opportunity", payload_json)
        self.assertIn("Rising", payload_json)
        self.assertIn("#20 -> #5", payload_json)
        self.assertIn("#65,003 in Home & Kitchen", payload_json)
        self.assertIn("#149 in Decorative Signs & Plaques", payload_json)

    def test_build_lark_interactive_card_payloads_omits_missing_images(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "output"
            write_csv(
                output_dir / "lark_trend_alerts.csv",
                [
                    {
                        "alert_type": "opportunity",
                        "opportunity_score": "80",
                        "asin": "B0NOIMAGE1",
                        "title": "No Image Personalized Mug",
                        "image_url": "",
                        "seller_name": "Best Seller",
                        "today_rank": "5",
                    }
                ],
                LARK_TREND_ALERT_FIELDS,
            )

            payloads = build_lark_interactive_card_payloads(output_dir, top_products=1)

        product_elements = payloads[1]["card"]["elements"]
        element_json = json.dumps(product_elements)
        self.assertNotIn("Product image", element_json)
        self.assertIn("No Image Personalized Mug", element_json)

    def test_send_lark_interactive_cards_posts_each_interactive_payload(self) -> None:
        class FakeResponse:
            status = 200

            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, *args: object) -> None:
                return None

            def read(self) -> bytes:
                return b"ok"

        payloads = [
            {
                "msg_type": "interactive",
                "card": {
                    "elements": [{"tag": "div", "text": {"tag": "lark_md", "content": f"Card {index}"}}],
                    "header": {"title": {"tag": "plain_text", "content": f"Card {index}"}},
                },
            }
            for index in range(1, 4)
        ]
        with patch("amazon_market_spy.notifications.urlopen", return_value=FakeResponse()) as urlopen:
            send_lark_interactive_cards("https://example.invalid/webhook", payloads, delay_seconds=0)

        self.assertEqual(urlopen.call_count, 3)
        request = urlopen.call_args_list[-1].args[0]
        sent_payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(request.full_url, "https://example.invalid/webhook")
        self.assertEqual(sent_payload, payloads[-1])

    def test_upload_lark_image_uploads_local_image_and_caches_image_key(self) -> None:
        class FakeResponse:
            status = 200

            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, *args: object) -> None:
                return None

            def read(self) -> bytes:
                return json.dumps({"code": 0, "data": {"image_key": "img_v3_uploaded"}, "msg": "success"}).encode("utf-8")

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "output"
            image_path = output_dir / "images" / "B0UPLOAD11.jpg"
            image_path.parent.mkdir(parents=True)
            image_path.write_bytes(b"fake image bytes")
            cache: dict[str, dict[str, str]] = {}
            output = io.StringIO()

            with patch("amazon_market_spy.notifications.urlopen", return_value=FakeResponse()) as urlopen:
                with redirect_stdout(output):
                    image_key = upload_lark_image(
                        image_url="https://example.com/product.jpg",
                        local_image_path="images/B0UPLOAD11.jpg",
                        output_dir=output_dir,
                        asin="B0UPLOAD11",
                        tenant_access_token="tenant-token",
                        cache=cache,
                    )

        self.assertEqual(image_key, "img_v3_uploaded")
        self.assertEqual(cache["B0UPLOAD11"]["image_key"], "img_v3_uploaded")
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://open.larksuite.com/open-apis/im/v1/images")
        self.assertEqual(request.headers["Authorization"], "Bearer tenant-token")
        self.assertIn(b'name="image_type"', request.data)
        self.assertIn(b'name="image"; filename="B0UPLOAD11.jpg"', request.data)
        self.assertIn("ASIN=B0UPLOAD11", output.getvalue())
        self.assertIn("image_key=img_v3_uploaded", output.getvalue())
        self.assertIn("created=yes", output.getvalue())

    def test_upload_lark_image_returns_cached_image_key_without_upload(self) -> None:
        cache = {"B0CACHED11": {"image_key": "img_v3_cached"}}
        output = io.StringIO()

        with patch("amazon_market_spy.notifications.urlopen") as urlopen:
            with redirect_stdout(output):
                image_key = upload_lark_image(
                    image_url="https://example.com/cached.jpg",
                    asin="B0CACHED11",
                    tenant_access_token="tenant-token",
                    cache=cache,
                )

        self.assertEqual(image_key, "img_v3_cached")
        self.assertFalse(urlopen.called)
        self.assertIn("ASIN=B0CACHED11", output.getvalue())
        self.assertIn("created=no", output.getvalue())

    def test_notify_lark_skips_when_webhook_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = io.StringIO()
            old_value = os.environ.pop("LARK_WEBHOOK_URL", None)
            try:
                with redirect_stdout(output):
                    exit_code = main(["notify-lark", "--output", str(Path(temp_dir) / "output")])
            finally:
                if old_value is not None:
                    os.environ["LARK_WEBHOOK_URL"] = old_value

        self.assertEqual(exit_code, 0)
        self.assertIn("Warning: Lark webhook missing; skipping notification.", output.getvalue())

    def test_notify_lark_does_not_log_webhook(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "output"
            write_csv(output_dir / "lark_trend_alerts.csv", [], LARK_TREND_ALERT_FIELDS)
            write_csv(output_dir / "seller_intelligence.csv", [], SELLER_INTELLIGENCE_FIELDS)
            output = io.StringIO()
            secret_url = "https://example.invalid/secret-webhook"

            with patch("amazon_market_spy.cli.send_lark_message") as send_lark_message:
                with redirect_stdout(output):
                    exit_code = main(["notify-lark", "--webhook", secret_url, "--output", str(output_dir)])

        self.assertEqual(exit_code, 0)
        self.assertEqual(send_lark_message.call_args.args[0], secret_url)
        self.assertNotIn(secret_url, output.getvalue())
        self.assertIn("Lark notification sent.", output.getvalue())

    def test_notify_lark_uses_report_url_option(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "output"
            write_csv(output_dir / "lark_trend_alerts.csv", [], LARK_TREND_ALERT_FIELDS)
            write_csv(output_dir / "seller_intelligence.csv", [], SELLER_INTELLIGENCE_FIELDS)
            custom_report_url = "https://example.com/report/"

            with patch("amazon_market_spy.cli.send_lark_message") as send_lark_message:
                exit_code = main(
                    [
                        "notify-lark",
                        "--webhook",
                        "https://example.invalid/webhook",
                        "--output",
                        str(output_dir),
                        "--report-url",
                        custom_report_url,
                    ]
                )

        self.assertEqual(exit_code, 0)
        message = send_lark_message.call_args.args[1]
        self.assertIn(f"View live report:\n{custom_report_url}", message)
        self.assertNotIn("Local report path:", message)

    def test_notify_lark_uses_report_url_env_and_can_include_local_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "output"
            write_csv(output_dir / "lark_trend_alerts.csv", [], LARK_TREND_ALERT_FIELDS)
            write_csv(output_dir / "seller_intelligence.csv", [], SELLER_INTELLIGENCE_FIELDS)
            old_value = os.environ.get("REPORT_URL")
            os.environ["REPORT_URL"] = "https://env.example.com/report/"
            try:
                with patch("amazon_market_spy.cli.send_lark_message") as send_lark_message:
                    exit_code = main(
                        [
                            "notify-lark",
                            "--webhook",
                            "https://example.invalid/webhook",
                            "--output",
                            str(output_dir),
                            "--include-local-path",
                        ]
                    )
            finally:
                if old_value is None:
                    os.environ.pop("REPORT_URL", None)
                else:
                    os.environ["REPORT_URL"] = old_value

        self.assertEqual(exit_code, 0)
        message = send_lark_message.call_args.args[1]
        self.assertIn("View live report:\nhttps://env.example.com/report/", message)
        self.assertIn("Local report path:", message)

    def test_notify_lark_card_sends_interactive_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "output"
            write_csv(
                output_dir / "lark_trend_alerts.csv",
                [
                    {
                        "alert_type": "new_win",
                        "opportunity_score": "95",
                        "asin": "B0NEWWIN11",
                        "title": "New Winner Personalized Coffee Mug",
                        "seller_name": "LASFOUR (Warrior)",
                        "today_rank": "2",
                        "product_url": "https://www.amazon.com/dp/B0NEWWIN11",
                    }
                ],
                LARK_TREND_ALERT_FIELDS,
            )
            output = io.StringIO()

            with patch("amazon_market_spy.cli.send_lark_interactive_cards") as send_cards:
                with patch("amazon_market_spy.cli.send_lark_message") as send_text:
                    with redirect_stdout(output):
                        exit_code = main(
                            [
                                "notify-lark",
                                "--webhook",
                                "https://example.invalid/webhook",
                                "--output",
                                str(output_dir),
                                "--card",
                                "--top-products",
                                "1",
                            ]
                        )

        self.assertEqual(exit_code, 0)
        self.assertFalse(send_text.called)
        self.assertEqual(send_cards.call_args.args[0], "https://example.invalid/webhook")
        payloads = send_cards.call_args.args[1]
        self.assertEqual(len(payloads), 2)
        self.assertTrue(all(payload["msg_type"] == "interactive" for payload in payloads))
        self.assertIn("Lark card notification sent.", output.getvalue())

    def test_notify_lark_card_falls_back_to_plain_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "output"
            write_csv(output_dir / "lark_trend_alerts.csv", [], LARK_TREND_ALERT_FIELDS)
            output = io.StringIO()

            with patch(
                "amazon_market_spy.cli.send_lark_interactive_cards",
                side_effect=LarkNotificationError("HTTP 400"),
            ) as send_cards:
                with patch("amazon_market_spy.cli.send_lark_message") as send_text:
                    with redirect_stdout(output):
                        exit_code = main(
                            [
                                "notify-lark",
                                "--webhook",
                                "https://example.invalid/webhook",
                                "--output",
                                str(output_dir),
                                "--card",
                            ]
                        )

        self.assertEqual(exit_code, 0)
        self.assertTrue(send_cards.called)
        self.assertEqual(send_text.call_args.args[0], "https://example.invalid/webhook")
        self.assertIn("Amazon Market Spy Daily Report", send_text.call_args.args[1])
        self.assertIn("Lark card notification failed: HTTP 400", output.getvalue())
        self.assertIn("Lark notification sent as plain text fallback.", output.getvalue())


if __name__ == "__main__":
    unittest.main()
