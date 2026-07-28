from __future__ import annotations

import re
from dataclasses import dataclass, field
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urljoin

from .category_rank import ensure_category_rank_fields
from .models import Source
from .niche import ensure_niche_fields
from .pod import classify_pod_row
from .product_details import clean_title, ensure_detail_fix_fields, image_url_from_attrs, is_valid_product_title
from .utils import is_asin, normalize_space, parse_compact_int, parse_money


ASIN_IN_URL_RE = re.compile(
    r"/(?:dp|gp/product|gp/aw/d)/(B0[A-Z0-9]{8})(?:[/?#]|$)",
    re.IGNORECASE,
)
CURRENCY_RE = re.compile(r"([$\u00a3\u20ac]\s*[0-9][0-9,]*(?:\.[0-9]{1,2})?)")
RATING_RE = re.compile(r"([0-5](?:\.[0-9])?)\s+out of\s+5\s+stars", re.IGNORECASE)
REVIEW_RE = re.compile(r"([0-9][0-9,]*)\s+(?:ratings?|reviews?)", re.IGNORECASE)
BOUGHT_RE = re.compile(r"([0-9][0-9,.]*[kKmM+]*)\s+bought in past month", re.IGNORECASE)
BADGES = ["Amazon's Choice", "Best Seller", "Overall Pick", "Climate Pledge Friendly"]
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


@dataclass
class Tile:
    asin: str
    position: int
    depth: int = 0
    text_parts: list[str] = field(default_factory=list)
    attr_parts: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)
    image_url: str = ""
    image_score: int = 0
    image_alt: str = ""
    title_attr: str = ""
    title_candidates: list[tuple[int, str]] = field(default_factory=list)
    title_parts: list[str] = field(default_factory=list)
    price_parts: list[str] = field(default_factory=list)
    sponsored: bool = False


@dataclass
class LinkCandidate:
    asin: str
    href: str
    position: int
    depth: int = 0
    text_parts: list[str] = field(default_factory=list)
    attr_parts: list[str] = field(default_factory=list)
    image_url: str = ""
    image_score: int = 0
    image_alt: str = ""


class AmazonSearchHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tiles: list[Tile] = []
        self.current: Tile | None = None
        self._tag_stack: list[dict[str, object]] = []
        self._title_depth: int | None = None
        self._title_candidate_depth: int | None = None
        self._title_candidate_priority: int | None = None
        self._title_candidate_parts: list[str] = []
        self._price_depth: int | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key.lower(): value or "" for key, value in attrs}
        data_asin = attr.get("data-asin", "").strip().upper()

        if self.current is None and is_asin(data_asin):
            self.current = Tile(asin=data_asin, position=len(self.tiles) + 1, depth=1)
            self._tag_stack = []
            self._push_frame(tag.lower(), attr)
            self._process_starttag(tag.lower(), attr)
            if tag.lower() in VOID_TAGS:
                self.handle_endtag(tag)
            return

        if self.current is None:
            return

        self.current.depth += 1
        self._push_frame(tag.lower(), attr)
        self._process_starttag(tag.lower(), attr)
        if tag.lower() in VOID_TAGS:
            self.handle_endtag(tag)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag.lower() not in VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if self.current is None:
            return

        if self._title_depth is not None and self.current.depth <= self._title_depth:
            self._title_depth = None
        if self._title_candidate_depth is not None and self.current.depth <= self._title_candidate_depth:
            self._finalize_title_candidate()
        if self._price_depth is not None and self.current.depth <= self._price_depth:
            self._price_depth = None

        if self._tag_stack:
            self._tag_stack.pop()
        self.current.depth -= 1
        if self.current.depth <= 0:
            self.tiles.append(self.current)
            self.current = None
            self._tag_stack = []
            self._title_depth = None
            self._title_candidate_depth = None
            self._title_candidate_priority = None
            self._title_candidate_parts = []
            self._price_depth = None

    def handle_data(self, data: str) -> None:
        if self.current is None:
            return
        text = normalize_space(data)
        if not text:
            return
        self.current.text_parts.append(text)
        if self._title_candidate_depth is not None:
            self._title_candidate_parts.append(text)
        if self._title_depth is not None:
            self.current.title_parts.append(text)
        if self._price_depth is not None:
            self.current.price_parts.append(text)
        if text.lower() == "sponsored":
            self.current.sponsored = True

    def _process_starttag(self, tag: str, attr: dict[str, str]) -> None:
        if self.current is None:
            return

        for value in attr.values():
            text = normalize_space(value)
            if text:
                self.current.attr_parts.append(text)
                if text.lower() == "sponsored":
                    self.current.sponsored = True

        css_class = attr.get("class", "")
        aria_label = normalize_space(attr.get("aria-label", ""))

        title_priority = _title_candidate_priority(tag, attr, self._tag_stack)
        if title_priority is not None:
            self._title_candidate_depth = self.current.depth
            self._title_candidate_priority = title_priority
            self._title_candidate_parts = []

        if tag == "a":
            href = attr.get("href", "")
            if href:
                self.current.links.append(href)
            if aria_label and _looks_like_title(aria_label):
                self.current.title_attr = self.current.title_attr or aria_label

        if tag == "h2":
            self._title_depth = self.current.depth
            if aria_label and _looks_like_title(aria_label):
                self.current.title_attr = self.current.title_attr or aria_label

        if tag == "img":
            image_url = image_url_from_attrs(attr)
            image_score = _image_selector_score(attr)
            if image_url and (not self.current.image_url or image_score > self.current.image_score):
                self.current.image_url = image_url
                self.current.image_score = image_score
            alt = normalize_space(attr.get("alt", ""))
            self.current.image_alt = self.current.image_alt or alt

        if "a-offscreen" in css_class:
            self._price_depth = self.current.depth

    def _push_frame(self, tag: str, attr: dict[str, str]) -> None:
        self._tag_stack.append({"tag": tag, "classes": set(attr.get("class", "").split())})

    def _finalize_title_candidate(self) -> None:
        if self.current is not None and self._title_candidate_priority is not None:
            text = clean_title(" ".join(self._title_candidate_parts))
            if text:
                self.current.title_candidates.append((self._title_candidate_priority, text))
        self._title_candidate_depth = None
        self._title_candidate_priority = None
        self._title_candidate_parts = []


class AmazonProductLinkParser(HTMLParser):
    """Fallback parser for rank pages where ASIN containers are not marked."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.candidates: list[LinkCandidate] = []
        self.current: LinkCandidate | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key.lower(): value or "" for key, value in attrs}

        if self.current is None:
            href = attr.get("href", "")
            asin = _asin_from_href(href)
            if tag.lower() == "a" and asin:
                self.current = LinkCandidate(
                    asin=asin,
                    href=href,
                    position=len(self.candidates) + 1,
                    depth=1,
                )
                self._process_starttag(tag.lower(), attr)
                if tag.lower() in VOID_TAGS:
                    self.handle_endtag(tag)
            return

        self.current.depth += 1
        self._process_starttag(tag.lower(), attr)
        if tag.lower() in VOID_TAGS:
            self.handle_endtag(tag)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag.lower() not in VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if self.current is None:
            return
        self.current.depth -= 1
        if self.current.depth <= 0:
            self.candidates.append(self.current)
            self.current = None

    def handle_data(self, data: str) -> None:
        if self.current is None:
            return
        text = normalize_space(data)
        if text:
            self.current.text_parts.append(text)

    def _process_starttag(self, tag: str, attr: dict[str, str]) -> None:
        if self.current is None:
            return
        for key in ("aria-label", "title"):
            value = normalize_space(attr.get(key, ""))
            if value:
                self.current.attr_parts.append(value)
        if tag == "img":
            image_url = image_url_from_attrs(attr)
            image_score = _image_selector_score(attr)
            if image_url and (not self.current.image_url or image_score > self.current.image_score):
                self.current.image_url = image_url
                self.current.image_score = image_score
            alt = normalize_space(attr.get("alt", ""))
            self.current.image_alt = self.current.image_alt or alt
            if alt:
                self.current.attr_parts.append(alt)


def parse_amazon_search_results(
    html: str,
    source: Source,
    fetched_at: str,
    page_url: str | None = None,
) -> list[dict[str, str]]:
    page_url = page_url or source.url
    parser = AmazonSearchHTMLParser()
    parser.feed(html)
    parser.close()

    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for tile in parser.tiles:
        if tile.asin in seen:
            continue
        seen.add(tile.asin)
        records.append(_tile_to_record(tile, source, fetched_at, page_url))

    link_parser = AmazonProductLinkParser()
    link_parser.feed(html)
    link_parser.close()
    for candidate in link_parser.candidates:
        if candidate.asin in seen:
            continue
        seen.add(candidate.asin)
        rank = len(records) + 1
        records.append(_candidate_to_record(candidate, rank, html, source, fetched_at, page_url))

    return records


def _tile_to_record(tile: Tile, source: Source, fetched_at: str, page_url: str) -> dict[str, str]:
    full_text = normalize_space(" ".join(tile.text_parts + tile.attr_parts))
    title = _best_tile_title(tile)
    price_display = _first_price(" ".join(tile.price_parts)) or _first_price(full_text)
    price = parse_money(price_display or "")
    rating = _first_rating(full_text)
    review_count = _first_reviews(full_text)
    bought_text = _first_bought_text(full_text)
    bought_count = parse_compact_int(bought_text or "")
    product_url = _best_product_url(tile.links, tile.asin, page_url)
    badge = _first_badge(full_text)

    return _product_record(
        source=source,
        fetched_at=fetched_at,
        page_url=page_url,
        asin=tile.asin,
        rank=tile.position,
        title=title,
        price=price,
        price_display=price_display or "",
        rating=rating,
        review_count=review_count,
        bought_count=bought_count,
        badge=badge,
        sponsored=tile.sponsored or "sponsored" in full_text.lower(),
        product_url=product_url,
        image_url=tile.image_url,
        pod_text=full_text,
    )


def _candidate_to_record(
    candidate: LinkCandidate,
    rank: int,
    html: str,
    source: Source,
    fetched_at: str,
    page_url: str,
) -> dict[str, str]:
    window_text = _text_window_for_asin(html, candidate.asin)
    link_text = normalize_space(" ".join(candidate.text_parts + candidate.attr_parts))
    full_text = normalize_space(f"{link_text} {window_text}")
    title = _best_candidate_title(link_text, candidate.image_alt)
    price_display = _first_price(full_text)
    price = parse_money(price_display or "")
    rating = _first_rating(full_text)
    review_count = _first_reviews(full_text)
    bought_text = _first_bought_text(full_text)
    bought_count = parse_compact_int(bought_text or "")
    badge = _first_badge(full_text)

    return _product_record(
        source=source,
        fetched_at=fetched_at,
        page_url=page_url,
        asin=candidate.asin,
        rank=rank,
        title=title,
        price=price,
        price_display=price_display or "",
        rating=rating,
        review_count=review_count,
        bought_count=bought_count,
        badge=badge,
        sponsored="sponsored" in full_text.lower(),
        product_url=urljoin(page_url, candidate.href),
        image_url=candidate.image_url,
        pod_text=full_text,
    )


def _product_record(
    source: Source,
    fetched_at: str,
    page_url: str,
    asin: str,
    rank: int,
    title: str,
    price: float | None,
    price_display: str,
    rating: float | None,
    review_count: int | None,
    bought_count: int | None,
    badge: str,
    sponsored: bool,
    product_url: str,
    image_url: str,
    pod_text: str = "",
) -> dict[str, str]:
    raw_title = clean_title(title)
    pod = classify_pod_row(
        {
            "title": title,
            "raw_title": raw_title,
            "product_url": product_url,
            "category": source.category,
            "source_name": source.display_name,
            "source_type": source.source_type,
            "seller_name": source.seller_name,
            "description": pod_text,
        }
    )
    return ensure_detail_fix_fields(
        ensure_niche_fields(
            ensure_category_rank_fields(
            {
                "date": fetched_at[:10],
                "fetched_at": fetched_at,
                "source_name": source.display_name,
                "source_type": source.source_type,
                "seller_name": source.seller_name,
                "seller_id": source.seller_id,
                "seller_url": source.seller_url,
                "page_type": source.source_type,
                "category": source.category,
                "priority": str(source.priority),
                "asin": asin.strip().upper(),
                "is_pod": pod["is_pod"],
                "production_model": pod["production_model"],
                "production_confidence": pod["production_confidence"],
                "production_reason": pod["production_reason"],
                "pod_type": pod["pod_type"],
                "pod_score": pod["pod_score"],
                "pod_confidence": pod["pod_confidence"],
                "pod_reason": pod["pod_reason"],
                "display_rank": str(rank),
                "display_order": str(rank),
                "rank": str(rank),
                "rank_basis": "display_order",
                "position": str(rank),
                "title": raw_title,
                "raw_title": raw_title,
                "title_source": "listing_card" if raw_title else "",
                "title_fixed": "false",
                "price": f"{price:.2f}" if price is not None else "",
                "price_display": price_display,
                "rating": f"{rating:.1f}" if rating is not None else "",
                "review_count": str(review_count) if review_count is not None else "",
                "review_rating": f"{rating:.1f}" if rating is not None else "",
                "bought_past_month": str(bought_count) if bought_count is not None else "",
                "badge": badge,
                "sponsored": "yes" if sponsored else "no",
                "product_url": product_url,
                "image_url": image_url,
                "image_source": "listing_card" if image_url else "",
                "image_fixed": "false",
                "page_url": page_url,
            }
        )
        )
    )


def _looks_like_title(value: str) -> bool:
    text = normalize_space(value)
    lowered = text.lower()
    if len(text) < 12:
        return False
    blocked = ["out of 5 stars", "$", "sponsored", "ratings", "reviews"]
    return not any(item in lowered for item in blocked)


def _clean_title(value: str) -> str:
    return clean_title(value)


def _best_tile_title(tile: Tile) -> str:
    for _, title in sorted(tile.title_candidates, key=lambda item: item[0]):
        if is_valid_product_title(title):
            return clean_title(title)
    for fallback in (tile.title_attr, " ".join(tile.title_parts), tile.image_alt):
        title = clean_title(fallback)
        if title:
            return title
    return ""


def _best_candidate_title(link_text: str, image_alt: str) -> str:
    for value in (link_text, image_alt):
        title = clean_title(value)
        if title:
            return title
    return ""


def _title_candidate_priority(tag: str, attr: dict[str, str], stack: list[dict[str, object]]) -> int | None:
    if tag != "span":
        return None
    if _has_ancestor(stack, "h2"):
        return 1
    if _has_ancestor_with_classes(stack, "a", {"a-link-normal", "s-line-clamp-2"}):
        return 3
    if _has_ancestor_with_classes(stack, "a", {"a-link-normal", "s-line-clamp-3"}):
        return 4
    classes = set(attr.get("class", "").split())
    if {"a-size-base-plus", "a-color-base", "a-text-normal"}.issubset(classes):
        return 5
    if {"a-size-medium", "a-color-base", "a-text-normal"}.issubset(classes):
        return 6
    return None


def _has_ancestor(stack: list[dict[str, object]], tag: str) -> bool:
    return any(frame.get("tag") == tag for frame in stack)


def _has_ancestor_with_classes(stack: list[dict[str, object]], tag: str, required: set[str]) -> bool:
    for frame in stack:
        if frame.get("tag") != tag:
            continue
        classes = frame.get("classes", set())
        if isinstance(classes, set) and required.issubset(classes):
            return True
    return False


def _first_price(value: str) -> str | None:
    match = CURRENCY_RE.search(value)
    return normalize_space(match.group(1)) if match else None


def _first_rating(value: str) -> float | None:
    match = RATING_RE.search(value)
    return float(match.group(1)) if match else None


def _first_reviews(value: str) -> int | None:
    match = REVIEW_RE.search(value)
    if not match:
        return None
    return int(match.group(1).replace(",", ""))


def _first_bought_text(value: str) -> str | None:
    match = BOUGHT_RE.search(value)
    return match.group(1) if match else None


def _first_badge(value: str) -> str:
    lowered = value.lower()
    for badge in BADGES:
        if badge.lower() in lowered:
            return badge
    return ""


def _best_product_url(links: list[str], asin: str, page_url: str) -> str:
    for link in links:
        match = ASIN_IN_URL_RE.search(link)
        if match and match.group(1).upper() == asin:
            return urljoin(page_url, link)
    return f"https://www.amazon.com/dp/{asin}"


def _image_selector_score(attr: dict[str, str]) -> int:
    classes = set(attr.get("class", "").split())
    if "s-image" in classes:
        return 3
    if "data-image-latency" in attr:
        return 2
    if image_url_from_attrs(attr):
        return 1
    return 0


def _asin_from_href(href: str) -> str:
    match = ASIN_IN_URL_RE.search(href or "")
    return match.group(1).upper() if match else ""


def _text_window_for_asin(html: str, asin: str, before: int = 1500, after: int = 2500) -> str:
    index = html.upper().find(asin.upper())
    if index < 0:
        return ""
    chunk = html[max(0, index - before) : index + after]
    chunk = re.sub(r"<script\b.*?</script>", " ", chunk, flags=re.IGNORECASE | re.DOTALL)
    chunk = re.sub(r"<style\b.*?</style>", " ", chunk, flags=re.IGNORECASE | re.DOTALL)
    chunk = re.sub(r"<[^>]+>", _tag_attrs_to_text, chunk)
    return normalize_space(unescape(chunk))


def _tag_attrs_to_text(match: re.Match[str]) -> str:
    tag = match.group(0)
    attr_text = " ".join(
        item.group(2)
        for item in re.finditer(r"\b(?:aria-label|title|alt)=(['\"])(.*?)\1", tag, flags=re.IGNORECASE | re.DOTALL)
    )
    return f" {attr_text} " if attr_text else " "
