from __future__ import annotations

from dataclasses import dataclass, replace
from html import unescape
import re
import time
from pathlib import Path

from .models import Source
from .utils import ensure_parent, slugify


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0 Safari/537.36 amazon-market-spy/0.1"
)

READY_SELECTORS = [
    "[data-asin]",
    "[data-component-type='s-search-result']",
    "a[href*='/dp/']",
    "a[href*='/gp/product/']",
    "a[href*='/gp/aw/d/']",
    "#zg",
    "#zg-ordered-list",
]

DETAIL_READY_SELECTORS = [
    "#productTitle",
    "#landingImage",
    "#imgTagWrapperId img",
    "meta[property='og:title']",
    "meta[property='og:image']",
]

DETAIL_RANK_SELECTORS = [
    "#productDetails_detailBullets_sections1",
    "#detailBullets_feature_div",
    "#productDetails_db_sections",
]

EXPAND_PRODUCT_INFORMATION_ACCORDIONS_SCRIPT = r"""
() => {
    const labelPatterns = [
        /item\s+details/i,
        /product\s+information/i,
        /features\s*&\s*specs/i,
        /best\s+sellers\s+rank/i,
    ];
    const clickableSelector = [
        "button",
        "[role='button']",
        "a",
        "summary",
        "[aria-expanded]",
        ".a-expander-header",
        ".a-accordion-row",
        ".a-section",
        "h2",
        "h3",
    ].join(",");
    const isVisible = (element) => {
        const style = window.getComputedStyle(element);
        const rect = element.getBoundingClientRect();
        return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
    };
    const textOf = (element) => [
        element.innerText || element.textContent || "",
        element.getAttribute("aria-label") || "",
        element.getAttribute("title") || "",
        element.getAttribute("data-csa-c-content-id") || "",
    ].join(" ").replace(/\s+/g, " ").trim();
    const hasTargetLabel = (element) => labelPatterns.some((pattern) => pattern.test(textOf(element)));
    const bestClickTarget = (element) => {
        const direct = element.closest("[aria-expanded], button, [role='button'], a, summary, .a-expander-header, .a-accordion-row");
        if (direct) {
            return direct;
        }
        const nested = element.querySelector("[aria-expanded='false'], button, [role='button'], a, summary, .a-expander-header, .a-accordion-row");
        return nested || element;
    };
    const isCollapsed = (element) => {
        const aria = element.getAttribute("aria-expanded");
        if (aria === "false") {
            return true;
        }
        if (aria === "true") {
            return false;
        }
        if (element.querySelector("[aria-expanded='false']")) {
            return true;
        }
        const classes = element.getAttribute("class") || "";
        return /collapsed|a-expander-prompt/i.test(classes);
    };

    let found = false;
    let expanded = false;
    const seen = new Set();
    for (const element of document.querySelectorAll(clickableSelector)) {
        if (!isVisible(element) || !hasTargetLabel(element)) {
            continue;
        }
        found = true;
        const target = bestClickTarget(element);
        if (!target || seen.has(target)) {
            continue;
        }
        seen.add(target);
        if (!isVisible(target) || !isCollapsed(target)) {
            continue;
        }
        try {
            target.scrollIntoView({block: "center", inline: "nearest"});
            target.click();
            expanded = true;
        } catch (error) {
        }
    }
    return {found, expanded};
}
"""

BSR_VISIBLE_SCRIPT = r"""
() => {
    const isVisible = (element) => {
        const style = window.getComputedStyle(element);
        const rect = element.getBoundingClientRect();
        return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
    };
    for (const element of document.querySelectorAll("body *")) {
        const text = (element.innerText || element.textContent || "").replace(/\s+/g, " ").trim();
        if (/Best Sellers Rank|Sales Rank/i.test(text) && isVisible(element)) {
            return true;
        }
    }
    return false;
}
"""

PRODUCT_COUNT_SCRIPT = r"""
() => {
    const asinPattern = /B0[A-Z0-9]{8}/i;
    const asinFromValue = (value) => {
        const match = asinPattern.exec(value || "");
        return match ? match[0].toUpperCase() : "";
    };
    const asinFromElement = (element) => {
        const dataAsin = asinFromValue(element.getAttribute("data-asin"));
        if (dataAsin) {
            return dataAsin;
        }
        const link = element.matches("a[href]") ? element : element.querySelector("a[href*='/dp/'], a[href*='/gp/product/'], a[href*='/gp/aw/d/']");
        return link ? asinFromValue(link.getAttribute("href")) : "";
    };
    const selectorGroups = [
        ".s-main-slot [data-component-type='s-search-result'][data-asin]",
        "#search .s-main-slot [data-asin]",
        "[data-component-type='s-search-result'][data-asin]",
        "#zg [data-asin]",
        "#zg-ordered-list [data-asin]",
        "#gridItemRoot",
        ".zg-grid-general-faceout",
        ".p13n-grid-content",
        "li.zg-item-immersion"
    ];
    for (const selector of selectorGroups) {
        const asins = new Set();
        for (const element of document.querySelectorAll(selector)) {
            const asin = asinFromElement(element);
            if (asin) {
                asins.add(asin);
            }
        }
        if (asins.size > 0) {
            return asins.size;
        }
    }
    return 0;
}
"""

PRODUCT_ASINS_SCRIPT = r"""
() => {
    const asinPattern = /B0[A-Z0-9]{8}/i;
    const asinFromValue = (value) => {
        const match = asinPattern.exec(value || "");
        return match ? match[0].toUpperCase() : "";
    };
    const asinFromElement = (element) => {
        const dataAsin = asinFromValue(element.getAttribute("data-asin"));
        if (dataAsin) {
            return dataAsin;
        }
        const link = element.matches("a[href]") ? element : element.querySelector("a[href*='/dp/'], a[href*='/gp/product/'], a[href*='/gp/aw/d/']");
        return link ? asinFromValue(link.getAttribute("href")) : "";
    };

    const selectorGroups = [
        ".s-main-slot [data-component-type='s-search-result'][data-asin]",
        "#search .s-main-slot [data-asin]",
        "[data-component-type='s-search-result'][data-asin]",
        "#zg [data-asin]",
        "#zg-ordered-list [data-asin]",
        "#gridItemRoot",
        ".zg-grid-general-faceout",
        ".p13n-grid-content",
        "li.zg-item-immersion",
    ];
    const asins = [];
    for (const selector of selectorGroups) {
        const elements = Array.from(document.querySelectorAll(selector));
        if (elements.length === 0) {
            continue;
        }
        for (const element of elements) {
            const asin = asinFromElement(element);
            if (asin) {
                asins.push(asin);
            }
        }
        if (asins.length > 0) {
            return asins;
        }
    }

    const seen = new Set();
    for (const element of document.querySelectorAll("a[href*='/dp/'], a[href*='/gp/product/'], a[href*='/gp/aw/d/']")) {
        const asin = asinFromElement(element);
        if (asin && !seen.has(asin)) {
            seen.add(asin);
            asins.push(asin);
        }
    }
    return asins;
}
"""

AMAZON_TOTAL_TEXT_RE = re.compile(
    r"\b(?:Showing\s+)?\d{1,3}(?:,\d{3})*\s*[-\u2013\u2014]\s*"
    r"\d{1,3}(?:,\d{3})*\s+of\s+(?:over\s+)?\d{1,3}(?:,\d{3})*"
    r"(?:\s+results?)?\b",
    re.IGNORECASE,
)
AMAZON_TOTAL_COUNT_RE = re.compile(
    r"\b(?:Showing\s+)?(?P<start>\d{1,3}(?:,\d{3})*)\s*[-\u2013\u2014]\s*"
    r"(?P<end>\d{1,3}(?:,\d{3})*)\s+of\s+(?P<over>over\s+)?"
    r"(?P<total>\d{1,3}(?:,\d{3})*)(?:\s+results?)?\b",
    re.IGNORECASE,
)

RESULT_TOTAL_TEXT_SCRIPT = r"""
() => {
    const text = (document.body ? document.body.innerText : "")
        .replace(/\u00a0/g, " ")
        .replace(/\s+/g, " ")
        .trim();
    const pattern = /\b(?:Showing\s+)?\d{1,3}(?:,\d{3})*\s*[-\u2013\u2014]\s*\d{1,3}(?:,\d{3})*\s+of\s+(?:over\s+)?\d{1,3}(?:,\d{3})*(?:\s+results?)?\b/i;
    const match = text.match(pattern);
    return match ? match[0].replace(/\s+/g, " ").trim() : "";
}
"""

SCROLL_TO_BOTTOM_SCRIPT = """
() => {
    const body = document.body;
    const documentElement = document.documentElement;
    const height = Math.max(
        body ? body.scrollHeight : 0,
        documentElement ? documentElement.scrollHeight : 0
    );
    window.scrollTo(0, height);
}
"""

NEXT_PAGE_URL_SCRIPT = r"""
() => {
    const disabledSelector = ".s-pagination-disabled, .a-disabled, [aria-disabled='true']";
    const absoluteUrl = (href) => {
        try {
            return new URL(href, document.location.href).href;
        } catch (error) {
            return "";
        }
    };
    const hrefFromElement = (element) => {
        if (!element || element.closest(disabledSelector) || element.matches(disabledSelector)) {
            return "";
        }
        const href = element.getAttribute("href");
        return href ? absoluteUrl(href) : "";
    };
    const currentPageNumber = () => {
        const selected = document.querySelector("nav[aria-label='pagination'] li.a-selected a, .a-pagination li.a-selected a, a[aria-current='page']");
        const selectedText = selected ? (selected.innerText || selected.textContent || "").trim() : "";
        const selectedNumber = parseInt(selectedText, 10);
        if (Number.isFinite(selectedNumber) && selectedNumber > 0) {
            return selectedNumber;
        }
        try {
            const params = new URL(document.location.href).searchParams;
            const value = params.get("pg") || params.get("page");
            const urlNumber = parseInt(value || "", 10);
            if (Number.isFinite(urlNumber) && urlNumber > 0) {
                return urlNumber;
            }
        } catch (error) {
        }
        return 1;
    };
    const selectors = [
        "a.s-pagination-next:not(.s-pagination-disabled)",
        "li.a-last a",
        "nav[aria-label='pagination'] li.a-last a",
        ".a-pagination li.a-last a",
        "a[aria-label='Go to next page']",
        "a[aria-label*='Next']",
        "a[href*='page=']",
        "a[href*='pg=']"
    ];
    const looksLikeNext = (element) => {
        const text = (element.innerText || element.textContent || "").trim().toLowerCase();
        const aria = (element.getAttribute("aria-label") || "").trim().toLowerCase();
        const rel = (element.getAttribute("rel") || "").trim().toLowerCase();
        const classes = (element.getAttribute("class") || "").trim().toLowerCase();
        return text.includes("next") || aria.includes("next") || rel === "next" || classes.includes("pagination-next");
    };

    for (const selector of selectors) {
        for (const element of document.querySelectorAll(selector)) {
            if (looksLikeNext(element)) {
                const href = hrefFromElement(element);
                if (href) {
                    return href;
                }
            }
        }
    }

    const nextPage = currentPageNumber() + 1;
    const pageLabel = `Page ${nextPage}`;
    for (const element of document.querySelectorAll("nav[aria-label='pagination'] li, .a-pagination li")) {
        const aria = (element.getAttribute("aria-label") || "").trim().toLowerCase();
        if (aria === pageLabel.toLowerCase()) {
            const href = hrefFromElement(element.querySelector("a[href]"));
            if (href) {
                return href;
            }
        }
    }
    for (const element of document.querySelectorAll("nav[aria-label='pagination'] a[href], .a-pagination a[href]")) {
        const text = (element.innerText || element.textContent || "").trim();
        if (text === String(nextPage)) {
            const href = hrefFromElement(element);
            if (href) {
                return href;
            }
        }
        const href = element.getAttribute("href") || "";
        try {
            const params = new URL(href, document.location.href).searchParams;
            if (params.get("pg") === String(nextPage) || params.get("page") === String(nextPage)) {
                const url = hrefFromElement(element);
                if (url) {
                    return url;
                }
            }
        } catch (error) {
        }
    }
    return "";
}
"""

LOCATION_BUTTON_SELECTORS = [
    "#nav-global-location-popover-link",
    "#glow-ingress-block",
    "[data-action-type='SELECT_LOCATION']",
]

ZIP_INPUT_SELECTORS = [
    "input#GLUXZipUpdateInput",
    "input[name='zipCode']",
]

ZIP_APPLY_SELECTORS = [
    "#GLUXZipUpdate",
    "input[aria-labelledby='GLUXZipUpdate-announce']",
    "span#GLUXZipUpdate",
]


@dataclass(frozen=True)
class FetchedPage:
    html: str
    url: str
    page_number: int
    product_asins: tuple[str, ...] = ()
    raw_total_text: str = ""
    scrolls: int = 0
    scroll_stop_reason: str = ""
    stop_reason: str = ""
    screenshot: bytes | None = None


@dataclass(frozen=True)
class DetailFetchedPage:
    html: str
    url: str
    status: str
    status_code: int | None = None
    error: str = ""
    screenshot: bytes | None = None
    accordion_found: bool = False
    accordion_expanded: bool = False
    bsr_visible_after_expand: bool = False


@dataclass(frozen=True)
class ScrollResult:
    before_count: int
    after_count: int
    iterations: int
    stop_reason: str

    def __iter__(self):
        yield self.before_count
        yield self.after_count


class FetchError(RuntimeError):
    pass


class BotCheckError(FetchError):
    pass


def _is_ranking_paginated_source(source_type: str) -> bool:
    normalized = (source_type or "").strip().lower().replace("-", "_").replace(" ", "_")
    return normalized in {"best_seller", "new_release"}


def detect_bot_check(html: str) -> bool:
    lowered = html.lower()
    signals = [
        "robot check",
        "enter the characters you see below",
        "/errors/validatecaptcha",
        "captcha",
    ]
    return any(signal in lowered for signal in signals)


def extract_amazon_reported_total_text(html: str) -> str:
    cleaned = re.sub(r"<script\b.*?</script>", " ", html or "", flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"<style\b.*?</style>", " ", cleaned, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", cleaned)
    text = re.sub(r"\s+", " ", unescape(text).replace("\xa0", " ")).strip()
    match = AMAZON_TOTAL_TEXT_RE.search(text)
    return re.sub(r"\s+", " ", match.group(0)).strip() if match else ""


def parse_amazon_reported_total(raw_total_text: str) -> int | None:
    match = AMAZON_TOTAL_COUNT_RE.search(raw_total_text or "")
    if not match or match.group("over"):
        return None
    return int(match.group("total").replace(",", ""))


class PlaywrightFetcher:
    def __init__(
        self,
        timeout: int = 30,
        user_agent: str | None = None,
        headless: bool = True,
        wait_until: str = "domcontentloaded",
        ready_timeout: int = 15,
        browser_channel: str | None = "chrome",
        browser_executable: str | None = None,
        block_assets: bool = False,
    ) -> None:
        self.timeout = timeout
        self.user_agent = user_agent or DEFAULT_USER_AGENT
        self.headless = headless
        self.wait_until = wait_until
        self.ready_timeout = ready_timeout
        self.browser_channel = browser_channel
        self.browser_executable = browser_executable
        self.block_assets = block_assets
        self._playwright = None
        self._browser = None
        self._context = None
        self._playwright_error = None
        self._playwright_timeout_error = None

    def __enter__(self) -> "PlaywrightFetcher":
        try:
            from playwright.sync_api import Error, TimeoutError, sync_playwright
        except ImportError as exc:
            raise FetchError(
                "Playwright is not installed. Run: python -m pip install -r requirements.txt"
            ) from exc

        self._playwright_error = Error
        self._playwright_timeout_error = TimeoutError
        try:
            self._playwright = sync_playwright().start()
            # Long scans can otherwise let Chromium's temporary profile grow by
            # several gigabytes and exhaust the system drive before the context
            # is closed. These caches are disposable for our one-pass fetches.
            launch_options = {
                "headless": self.headless,
                "args": [
                    "--disk-cache-size=1",
                    "--media-cache-size=1",
                    "--renderer-process-limit=2",
                    "--disable-extensions",
                    "--disable-background-networking",
                ],
            }
            if self.browser_executable:
                launch_options["executable_path"] = self.browser_executable
            elif self.browser_channel:
                launch_options["channel"] = self.browser_channel
            self._browser = self._playwright.chromium.launch(**launch_options)
            self._context = self._browser.new_context(
                user_agent=self.user_agent,
                locale="en-US",
                viewport={"width": 1365, "height": 900},
                ignore_https_errors=True,
            )
            if self.block_assets:
                self._context.route("**/*", self._route_nonessential_assets)
        except Error as exc:
            self.close()
            raise FetchError(
                "Playwright could not launch a browser. Install Chrome, pass --browser-channel msedge, "
                "or run: python -m playwright install chromium"
            ) from exc
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def close(self) -> None:
        if self._context is not None:
            self._context.close()
            self._context = None
        if self._browser is not None:
            self._browser.close()
            self._browser = None
        if self._playwright is not None:
            self._playwright.stop()
            self._playwright = None

    def fetch(
        self,
        url: str,
        screenshot_path: Path | None = None,
        error_screenshot_path: Path | None = None,
        scroll: bool = False,
        max_scrolls: int = 8,
        scroll_wait_ms: int = 1500,
    ) -> str:
        pages = self.fetch_pages(
            url,
            screenshot_path=screenshot_path,
            error_screenshot_path=error_screenshot_path,
            scroll=scroll,
            max_scrolls=max_scrolls,
            scroll_wait_ms=scroll_wait_ms,
            max_pages=1,
        )
        return pages[0].html

    def fetch_pages(
        self,
        url: str,
        screenshot_path: Path | None = None,
        error_screenshot_path: Path | None = None,
        scroll: bool = False,
        max_scrolls: int = 8,
        scroll_wait_ms: int = 1500,
        max_pages: int = 1,
        capture_first_page_screenshot: bool = False,
        source_type: str = "",
    ) -> list[FetchedPage]:
        page = self.new_page()
        timeout_ms = max(1, self.timeout) * 1000
        page_limit = max(1, max_pages)
        pages: list[FetchedPage] = []
        visited_urls: set[str] = set()
        try:
            response = page.goto(url, wait_until=self.wait_until, timeout=timeout_ms)
            for page_number in range(1, page_limit + 1):
                self.wait_for_page_ready(page, timeout_ms)
                raw_total_text = self.result_total_text(page)
                initial_product_count = self.product_count(page)
                scroll_result = ScrollResult(
                    before_count=initial_product_count,
                    after_count=initial_product_count,
                    iterations=0,
                    stop_reason="scroll_disabled",
                )
                if _is_ranking_paginated_source(source_type):
                    self.reveal_paginated_rank_page(
                        page,
                        initial_product_count=initial_product_count,
                        scroll_wait_ms=scroll_wait_ms,
                    )
                elif scroll:
                    scroll_result = self.scroll_to_load_products(
                        page,
                        max_scrolls=max_scrolls,
                        scroll_wait_ms=scroll_wait_ms,
                    )

                html = page.content()
                product_asins = self.product_asins(page)
                screenshot = self._safe_page_screenshot(page) if capture_first_page_screenshot and page_number == 1 else None
                if screenshot_path is not None:
                    shot_path = _numbered_path(screenshot_path, page_number, page_limit)
                    ensure_parent(shot_path)
                    page.screenshot(path=str(shot_path), full_page=True)

                status = response.status if response is not None else None
                if detect_bot_check(html):
                    raise BotCheckError("Amazon returned a bot check page")
                if status is not None and status >= 400:
                    raise FetchError(f"HTTP {status} from Playwright page visit")

                current_url = str(getattr(page, "url", url) or url)
                pages.append(
                    FetchedPage(
                        html=html,
                        url=current_url,
                        page_number=page_number,
                        product_asins=product_asins,
                        raw_total_text=raw_total_text,
                        scrolls=scroll_result.iterations,
                        scroll_stop_reason=scroll_result.stop_reason,
                        screenshot=screenshot,
                    )
                )
                visited_urls.add(current_url)

                if page_number >= page_limit:
                    pages[-1] = replace(pages[-1], stop_reason="max_pages_reached")
                    break
                next_url = self.next_page_url(page)
                if not next_url:
                    pages[-1] = replace(pages[-1], stop_reason="no_next_page")
                    break
                if next_url in visited_urls:
                    pages[-1] = replace(pages[-1], stop_reason="next_page_already_visited")
                    break
                print(f"  next page detected: {page_number + 1}/{page_limit}")
                previous_url = current_url
                response = page.goto(next_url, wait_until=self.wait_until, timeout=timeout_ms)
                navigated_url = str(getattr(page, "url", next_url) or next_url)
                if navigated_url == previous_url:
                    pages[-1] = replace(pages[-1], stop_reason="url_did_not_change")
                    break
                if navigated_url in visited_urls:
                    pages[-1] = replace(pages[-1], stop_reason="next_page_already_visited")
                    break

            if not pages:
                raise FetchError("No pages were fetched")
            return pages
        except BotCheckError:
            self._save_error_screenshot(page, error_screenshot_path)
            raise
        except self._playwright_timeout_error as exc:
            self._save_error_screenshot(page, error_screenshot_path)
            raise FetchError(f"Playwright timed out after {self.timeout} seconds") from exc
        except self._playwright_error as exc:
            self._save_error_screenshot(page, error_screenshot_path)
            raise FetchError(f"Playwright visit failed: {exc}") from exc
        finally:
            page.close()

    def fetch_detail_page(
        self,
        url: str,
        timeout: int | None = None,
        capture_screenshot: bool = False,
    ) -> DetailFetchedPage:
        page = self.new_page()
        timeout_seconds = max(1, timeout if timeout is not None else self.timeout)
        timeout_ms = timeout_seconds * 1000
        html = ""
        current_url = url
        status = "ok"
        status_code: int | None = None
        error = ""
        screenshot: bytes | None = None
        accordion_found = False
        accordion_expanded = False
        bsr_visible_after_expand = False

        try:
            response = page.goto(url, wait_until=self.wait_until, timeout=timeout_ms)
            status_code = response.status if response is not None else None
            current_url = str(getattr(page, "url", url) or url)
            self.wait_for_page_ready(page, timeout_ms)
            selector_query = ", ".join(DETAIL_READY_SELECTORS)
            try:
                page.wait_for_selector(selector_query, timeout=timeout_ms, state="attached")
            except self._playwright_timeout_error:
                status = "selector_timeout"
                error = f"Timed out waiting for product detail selectors after {timeout_seconds} seconds"

            try:
                page.wait_for_load_state("networkidle", timeout=min(timeout_ms, 10_000))
            except self._playwright_timeout_error:
                pass

            accordion_found, accordion_expanded, bsr_visible_after_expand = self.expand_product_information_accordions(
                page,
                timeout_ms,
            )

            rank_selector_query = ", ".join(DETAIL_RANK_SELECTORS)
            try:
                page.wait_for_selector(rank_selector_query, timeout=min(timeout_ms, 10_000), state="attached")
            except self._playwright_timeout_error:
                pass

            try:
                page.wait_for_function(
                    "() => document.body && /(?:Best Sellers Rank|Sales Rank)/i.test(document.body.innerText || '')",
                    timeout=min(timeout_ms, 10_000),
                )
            except self._playwright_timeout_error:
                pass

            html = self._safe_page_content(page)
            if detect_bot_check(html):
                status = "bot_check"
                error = "Amazon returned a bot check page"
            elif status_code is not None and status_code >= 400:
                status = f"http_{status_code}"
                error = f"HTTP {status_code} from Playwright detail page visit"
        except self._playwright_timeout_error:
            status = "timeout"
            error = f"Playwright timed out after {timeout_seconds} seconds"
            html = self._safe_page_content(page)
            current_url = str(getattr(page, "url", url) or url)
        except self._playwright_error as exc:
            status = "error"
            error = f"Playwright visit failed: {exc}"
            html = self._safe_page_content(page)
            current_url = str(getattr(page, "url", url) or url)
        finally:
            if capture_screenshot:
                screenshot = self._safe_page_screenshot(page)
            page.close()

        return DetailFetchedPage(
            html=html,
            url=current_url,
            status=status,
            status_code=status_code,
            error=error,
            screenshot=screenshot,
            accordion_found=accordion_found,
            accordion_expanded=accordion_expanded,
            bsr_visible_after_expand=bsr_visible_after_expand,
        )

    def expand_product_information_accordions(self, page: object, timeout_ms: int) -> tuple[bool, bool, bool]:
        found = False
        expanded = False
        visible = self._safe_bsr_visible(page)
        for _ in range(3):
            try:
                result = page.evaluate(EXPAND_PRODUCT_INFORMATION_ACCORDIONS_SCRIPT) or {}
            except Exception:
                result = {}
            found = found or bool(result.get("found"))
            expanded = expanded or bool(result.get("expanded"))
            if result.get("expanded"):
                try:
                    page.wait_for_timeout(750)
                except Exception:
                    pass
            visible = self._safe_bsr_visible(page)
            if visible:
                break

        if not visible:
            try:
                page.wait_for_function(BSR_VISIBLE_SCRIPT, timeout=min(timeout_ms, 10_000))
                visible = True
            except self._playwright_timeout_error:
                visible = self._safe_bsr_visible(page)
            except Exception:
                visible = self._safe_bsr_visible(page)
        return found, expanded, visible

    def scroll_to_load_products(self, page: object, max_scrolls: int = 8, scroll_wait_ms: int = 1500) -> ScrollResult:
        scroll_limit = max(0, max_scrolls)
        wait_ms = max(0, scroll_wait_ms)
        before_count = self.product_count(page)
        current_count = before_count
        no_new_scrolls = 0
        iterations = 0
        stop_reason = "scroll_disabled" if scroll_limit == 0 else "max_scrolls_reached"

        print(f"  product count before scrolling: {before_count}")
        for _ in range(scroll_limit):
            page.evaluate(SCROLL_TO_BOTTOM_SCRIPT)
            page.wait_for_timeout(wait_ms)
            iterations += 1
            next_count = self.product_count(page)
            if next_count <= current_count:
                no_new_scrolls += 1
                if no_new_scrolls >= 3:
                    stop_reason = "no_new_asin_after_3_scrolls"
                    break
            else:
                no_new_scrolls = 0
            current_count = max(current_count, next_count)

        print(f"  product count after scrolling: {current_count}")
        return ScrollResult(
            before_count=before_count,
            after_count=current_count,
            iterations=iterations,
            stop_reason=stop_reason,
        )

    def reveal_paginated_rank_page(
        self,
        page: object,
        initial_product_count: int = 0,
        scroll_wait_ms: int = 1500,
    ) -> None:
        wait_ms = max(0, min(scroll_wait_ms, 1500))
        current_count = max(0, initial_product_count)
        for _ in range(2):
            if current_count >= 50:
                break
            page.evaluate(SCROLL_TO_BOTTOM_SCRIPT)
            page.wait_for_timeout(wait_ms)
            next_count = self.product_count(page)
            if next_count <= current_count:
                break
            current_count = next_count

    def product_count(self, page: object) -> int:
        return int(page.evaluate(PRODUCT_COUNT_SCRIPT) or 0)

    def product_asins(self, page: object) -> tuple[str, ...]:
        values = page.evaluate(PRODUCT_ASINS_SCRIPT) or []
        return tuple(str(value).strip().upper() for value in values if str(value).strip())

    def result_total_text(self, page: object) -> str:
        return str(page.evaluate(RESULT_TOTAL_TEXT_SCRIPT) or "").strip()

    def next_page_url(self, page: object) -> str:
        return str(page.evaluate(NEXT_PAGE_URL_SCRIPT) or "")

    def new_page(self) -> object:
        if self._context is None:
            raise FetchError("Playwright browser context is not open")

        page = self._context.new_page()
        page.set_default_timeout(max(1, self.timeout) * 1000)
        return page

    def _save_error_screenshot(self, page: object, path: Path | None) -> None:
        if path is None:
            return
        try:
            ensure_parent(path)
            page.screenshot(path=str(path), full_page=True)
        except Exception:
            pass

    def _safe_page_content(self, page: object) -> str:
        try:
            return str(page.content())
        except Exception:
            return ""

    def _safe_page_screenshot(self, page: object) -> bytes | None:
        try:
            return page.screenshot(full_page=True)
        except Exception:
            return None

    def _safe_bsr_visible(self, page: object) -> bool:
        try:
            return bool(page.evaluate(BSR_VISIBLE_SCRIPT))
        except Exception:
            return False

    def wait_for_page_ready(self, page: object, timeout_ms: int) -> None:
        for state in ("domcontentloaded", "load"):
            try:
                page.wait_for_load_state(state, timeout=min(timeout_ms, 10_000))
            except self._playwright_timeout_error:
                pass

        selector_timeout = min(max(1, self.ready_timeout) * 1000, timeout_ms)
        selector_query = ", ".join(READY_SELECTORS)
        try:
            page.wait_for_selector(selector_query, timeout=selector_timeout)
        except self._playwright_timeout_error:
            pass

        try:
            page.wait_for_load_state("networkidle", timeout=min(timeout_ms, 10_000))
        except self._playwright_timeout_error:
            pass

    def _route_nonessential_assets(self, route: object) -> None:
        try:
            resource_type = route.request.resource_type
            if resource_type in {"image", "media", "font", "stylesheet"}:
                route.abort()
            else:
                route.continue_()
        except Exception:
            try:
                route.continue_()
            except Exception:
                pass


def fetch_url(
    url: str,
    timeout: int = 30,
    user_agent: str | None = None,
    screenshot_path: Path | None = None,
    error_screenshot_path: Path | None = None,
) -> str:
    with PlaywrightFetcher(timeout=timeout, user_agent=user_agent) as fetcher:
        return fetcher.fetch(url, screenshot_path=screenshot_path, error_screenshot_path=error_screenshot_path)


def set_amazon_delivery_location(page: object, zipcode: str, marketplace_domain: str) -> bool:
    print(f"Setting Amazon delivery ZIP to {zipcode}...")
    try:
        page.goto(marketplace_domain, wait_until="domcontentloaded")
        _wait_for_load_state(page, "load", timeout=15_000)
        _click_first_matching(page, LOCATION_BUTTON_SELECTORS)
        _fill_first_matching(page, ZIP_INPUT_SELECTORS, zipcode)
        _click_first_matching(page, ZIP_APPLY_SELECTORS)
        _click_optional(page, "button[name='glowDoneButton']", timeout=5_000)
        page.wait_for_timeout(2_000)
    except Exception:
        _save_zipcode_error_screenshot(page)
        print("Warning: Could not set delivery ZIP. Continuing scan.")
        return False

    print("Delivery ZIP set successfully.")
    return True


def _click_first_matching(page: object, selectors: list[str], timeout: int = 10_000) -> None:
    last_error: Exception | None = None
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            locator.wait_for(state="visible", timeout=timeout)
            locator.click(timeout=timeout)
            return
        except Exception as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    raise FetchError("No matching selector configured")


def _fill_first_matching(page: object, selectors: list[str], value: str, timeout: int = 10_000) -> None:
    last_error: Exception | None = None
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            locator.wait_for(state="visible", timeout=timeout)
            locator.fill(value, timeout=timeout)
            return
        except Exception as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    raise FetchError("No matching selector configured")


def _click_optional(page: object, selector: str, timeout: int = 3_000) -> None:
    try:
        locator = page.locator(selector).first
        locator.wait_for(state="visible", timeout=timeout)
        locator.click(timeout=timeout)
    except Exception:
        pass


def _wait_for_load_state(page: object, state: str, timeout: int) -> None:
    try:
        page.wait_for_load_state(state, timeout=timeout)
    except Exception:
        pass


def _save_zipcode_error_screenshot(page: object) -> None:
    try:
        path = Path("screenshots/zipcode_error.png")
        ensure_parent(path)
        page.screenshot(path=str(path), full_page=True)
    except Exception:
        pass


def save_html(page_dir: Path, source: Source, html: str, timestamp: str, page_number: int = 1) -> Path:
    page_dir.mkdir(parents=True, exist_ok=True)
    page_suffix = "" if page_number <= 1 else f"_page-{page_number}"
    filename = f"{timestamp}_{slugify(source.source_name)}{page_suffix}.html"
    path = page_dir / filename
    path.write_text(html, encoding="utf-8")
    return path


def screenshot_path(screenshot_dir: Path, source: Source, timestamp: str) -> Path:
    return screenshot_dir / f"{timestamp}_{slugify(source.source_name)}.png"


def error_screenshot_path(screenshot_dir: Path, source: Source, timestamp: str) -> Path:
    return screenshot_dir / "errors" / f"{timestamp}_{slugify(source.source_name)}_error.png"


def polite_sleep(seconds: float) -> None:
    if seconds > 0:
        time.sleep(seconds)


def _numbered_path(path: Path, page_number: int, page_limit: int) -> Path:
    if page_limit <= 1:
        return path
    return path.with_name(f"{path.stem}_page-{page_number}{path.suffix}")
