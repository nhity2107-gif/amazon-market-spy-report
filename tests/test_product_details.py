from __future__ import annotations

import unittest

from amazon_market_spy.product_details import extract_detail_page_fields, is_valid_product_title


class ProductDetailTests(unittest.TestCase):
    def test_rejects_gift_idea_title(self) -> None:
        self.assertFalse(is_valid_product_title("Gift Idea 1"))

    def test_rejects_short_option_label(self) -> None:
        self.assertFalse(is_valid_product_title("A1"))

    def test_extracts_detail_title_and_landing_image(self) -> None:
        html = """
        <html>
          <head><meta property="og:image" content="https://example.com/og.jpg"></head>
          <body>
            <span id="productTitle">Personalized Dad Coffee Mug Custom Father's Day Gift</span>
            <img id="landingImage" src="https://example.com/landing.jpg">
          </body>
        </html>
        """

        fields = extract_detail_page_fields(html)

        self.assertEqual(fields.title, "Personalized Dad Coffee Mug Custom Father's Day Gift")
        self.assertEqual(fields.image_url, "https://example.com/landing.jpg")

    def test_extracts_detail_image_from_og_image(self) -> None:
        html = '<meta property="og:image" content="https://example.com/og.jpg">'

        fields = extract_detail_page_fields(html)

        self.assertEqual(fields.image_url, "https://example.com/og.jpg")

    def test_extracts_clean_title_from_og_title(self) -> None:
        html = """
        <html>
          <head>
            <meta property="og:title" content="Amazon.com: Custom Dad Shirt Personalized Father's Day Gift: Clothing, Shoes &amp; Jewelry">
          </head>
        </html>
        """

        fields = extract_detail_page_fields(html)

        self.assertEqual(fields.title, "Custom Dad Shirt Personalized Father's Day Gift")

    def test_extracts_clean_title_from_document_title(self) -> None:
        html = """
        <html>
          <head><title>Amazon.com: Personalized Mom Coffee Mug Birthday Gift: Clothing, Shoes & Jewelry</title></head>
        </html>
        """

        fields = extract_detail_page_fields(html)

        self.assertEqual(fields.title, "Personalized Mom Coffee Mug Birthday Gift")

    def test_landing_image_falls_back_to_data_old_hires(self) -> None:
        html = '<img id="landingImage" data-old-hires="https://example.com/hires.jpg">'

        fields = extract_detail_page_fields(html)

        self.assertEqual(fields.image_url, "https://example.com/hires.jpg")


if __name__ == "__main__":
    unittest.main()
