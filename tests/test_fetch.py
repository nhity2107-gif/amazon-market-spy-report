from __future__ import annotations

import unittest

from amazon_market_spy.fetch import extract_amazon_reported_total_text, parse_amazon_reported_total, PlaywrightFetcher


class FakeTimeoutError(Exception):
    pass


class FakeResponse:
    def __init__(self, status: int = 200) -> None:
        self.status = status


class FakePage:
    def __init__(
        self,
        product_counts: list[int] | None = None,
        pages: dict[str, tuple[str, str]] | None = None,
    ) -> None:
        self.load_states: list[str] = []
        self.selector = ""
        self.product_counts = product_counts or []
        self.product_count_calls = 0
        self.scrolls = 0
        self.waits: list[int] = []
        self.pages = pages or {}
        self.goto_urls: list[str] = []
        self.url = ""
        self.closed = False

    def goto(self, url: str, wait_until: str, timeout: int) -> FakeResponse:
        self.goto_urls.append(url)
        self.url = url
        return FakeResponse()

    def wait_for_load_state(self, state: str, timeout: int) -> None:
        self.load_states.append(state)

    def wait_for_selector(self, selector: str, timeout: int) -> None:
        self.selector = selector

    def evaluate(self, script: str) -> object:
        if "document.body ? document.body.innerText" in script:
            return ""
        if "return asins.size" in script:
            index = min(self.product_count_calls, len(self.product_counts) - 1)
            self.product_count_calls += 1
            return self.product_counts[index] if self.product_counts else 0
        if "selectorGroups" in script:
            return []
        if "looksLikeNext" in script:
            return self.pages.get(self.url, ("", ""))[1]
        self.scrolls += 1
        return None

    def content(self) -> str:
        return self.pages.get(self.url, ("<html></html>", ""))[0]

    def wait_for_timeout(self, timeout: int) -> None:
        self.waits.append(timeout)

    def close(self) -> None:
        self.closed = True


class FakeAccordionPage:
    def __init__(self) -> None:
        self.evaluate_calls = 0
        self.waits: list[int] = []
        self.wait_for_function_calls = 0

    def evaluate(self, script: str) -> object:
        if "labelPatterns" in script:
            self.evaluate_calls += 1
            return {"found": True, "expanded": True}
        if "Best Sellers Rank|Sales Rank" in script:
            return self.evaluate_calls >= 1
        return None

    def wait_for_timeout(self, timeout: int) -> None:
        self.waits.append(timeout)

    def wait_for_function(self, script: str, timeout: int) -> None:
        self.wait_for_function_calls += 1


class FetchTests(unittest.TestCase):
    def test_parse_amazon_reported_total_examples(self) -> None:
        self.assertEqual(parse_amazon_reported_total("1-24 of 127 results"), 127)
        self.assertEqual(parse_amazon_reported_total("Showing 1-48 of 312 results"), 312)
        self.assertIsNone(parse_amazon_reported_total("1-16 of over 1,000 results"))

    def test_extract_amazon_reported_total_text_from_html(self) -> None:
        html = "<html><body><span>Showing 1-48 of 312 results</span></body></html>"

        self.assertEqual(extract_amazon_reported_total_text(html), "Showing 1-48 of 312 results")

    def test_wait_for_page_ready_waits_for_load_and_product_selectors(self) -> None:
        fetcher = PlaywrightFetcher(ready_timeout=7)
        fetcher._playwright_timeout_error = FakeTimeoutError
        page = FakePage()

        fetcher.wait_for_page_ready(page, timeout_ms=30_000)

        self.assertEqual(page.load_states, ["domcontentloaded", "load", "networkidle"])
        self.assertIn("[data-asin]", page.selector)
        self.assertIn("a[href*='/dp/']", page.selector)

    def test_scroll_to_load_products_stops_after_three_scrolls_without_new_asin(self) -> None:
        fetcher = PlaywrightFetcher()
        page = FakePage(product_counts=[2, 5, 5])

        result = fetcher.scroll_to_load_products(page, max_scrolls=8, scroll_wait_ms=1500)
        before_count, after_count = result

        self.assertEqual(before_count, 2)
        self.assertEqual(after_count, 5)
        self.assertEqual(result.iterations, 4)
        self.assertEqual(result.stop_reason, "no_new_asin_after_3_scrolls")
        self.assertEqual(page.scrolls, 4)
        self.assertEqual(page.waits, [1500, 1500, 1500, 1500])

    def test_scroll_to_load_products_respects_max_scrolls(self) -> None:
        fetcher = PlaywrightFetcher()
        page = FakePage(product_counts=[2, 5, 7, 9])

        result = fetcher.scroll_to_load_products(page, max_scrolls=2, scroll_wait_ms=750)
        before_count, after_count = result

        self.assertEqual(before_count, 2)
        self.assertEqual(after_count, 7)
        self.assertEqual(result.iterations, 2)
        self.assertEqual(result.stop_reason, "max_scrolls_reached")
        self.assertEqual(page.scrolls, 2)
        self.assertEqual(page.waits, [750, 750])

    def test_fetch_pages_crawls_until_max_pages(self) -> None:
        pages = {
            "https://www.amazon.com/s?k=mugs": ("<html>page 1 B0PAGE1111</html>", "https://www.amazon.com/s?k=mugs&page=2"),
            "https://www.amazon.com/s?k=mugs&page=2": (
                "<html>page 2 B0PAGE2222</html>",
                "https://www.amazon.com/s?k=mugs&page=3",
            ),
            "https://www.amazon.com/s?k=mugs&page=3": ("<html>page 3 B0PAGE3333</html>", ""),
        }
        page = FakePage(pages=pages)
        fetcher = PlaywrightFetcher()
        fetcher._playwright_timeout_error = FakeTimeoutError
        fetcher.new_page = lambda: page  # type: ignore[method-assign]

        fetched_pages = fetcher.fetch_pages("https://www.amazon.com/s?k=mugs", max_pages=2)

        self.assertEqual([item.page_number for item in fetched_pages], [1, 2])
        self.assertEqual([item.url for item in fetched_pages], list(pages.keys())[:2])
        self.assertEqual(page.goto_urls, list(pages.keys())[:2])
        self.assertTrue(page.closed)

    def test_fetch_pages_stops_when_next_url_does_not_change_page_url(self) -> None:
        class StalledPage(FakePage):
            def goto(self, url: str, wait_until: str, timeout: int) -> FakeResponse:
                self.goto_urls.append(url)
                if not self.url:
                    self.url = url
                return FakeResponse()

        pages = {
            "https://www.amazon.com/s?k=mugs": ("<html>page 1 B0PAGE1111</html>", "https://www.amazon.com/s?k=mugs&page=2"),
        }
        page = StalledPage(pages=pages)
        fetcher = PlaywrightFetcher()
        fetcher._playwright_timeout_error = FakeTimeoutError
        fetcher.new_page = lambda: page  # type: ignore[method-assign]

        fetched_pages = fetcher.fetch_pages("https://www.amazon.com/s?k=mugs", max_pages=3)

        self.assertEqual(len(fetched_pages), 1)
        self.assertEqual(fetched_pages[0].stop_reason, "url_did_not_change")
        self.assertEqual(
            page.goto_urls,
            ["https://www.amazon.com/s?k=mugs", "https://www.amazon.com/s?k=mugs&page=2"],
        )
        self.assertTrue(page.closed)

    def test_fetch_pages_reveals_ranking_page_without_reporting_scrolls(self) -> None:
        pages = {
            "https://www.amazon.com/gp/bestsellers/kitchen/367142011": (
                "<html>page 1 B0PAGE1111</html>",
                "",
            ),
        }
        page = FakePage(product_counts=[30, 50], pages=pages)
        fetcher = PlaywrightFetcher()
        fetcher._playwright_timeout_error = FakeTimeoutError
        fetcher.new_page = lambda: page  # type: ignore[method-assign]

        fetched_pages = fetcher.fetch_pages(
            "https://www.amazon.com/gp/bestsellers/kitchen/367142011",
            source_type="best_seller",
        )

        self.assertEqual(len(fetched_pages), 1)
        self.assertEqual(page.scrolls, 1)
        self.assertEqual(fetched_pages[0].scrolls, 0)

    def test_expand_product_information_accordions_clicks_and_waits_for_bsr(self) -> None:
        fetcher = PlaywrightFetcher()
        fetcher._playwright_timeout_error = FakeTimeoutError
        page = FakeAccordionPage()

        found, expanded, visible = fetcher.expand_product_information_accordions(page, timeout_ms=30_000)

        self.assertTrue(found)
        self.assertTrue(expanded)
        self.assertTrue(visible)
        self.assertEqual(page.waits, [750])
        self.assertEqual(page.wait_for_function_calls, 0)


if __name__ == "__main__":
    unittest.main()
