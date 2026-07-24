from __future__ import annotations

import json
import re
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser

from .utils import normalize_space


DETAIL_DEBUG_FIELDS = [
    "detail_fetched_reason",
    "detail_page_status",
    "detail_title_found",
    "detail_image_found",
    "detail_error",
    "detail_bsr_found",
    "detail_bsr_error",
]
DETAIL_FIX_FIELDS = [
    "raw_title",
    "title_source",
    "title_fixed",
    "image_source",
    "image_fixed",
    *DETAIL_DEBUG_FIELDS,
]
UNAVAILABLE_TITLE = "Title unavailable - open product"
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}

INVALID_TITLE_RE = re.compile(
    r"^(?:[AS]\d{1,2}|Gift\s+Idea\s+\d{1,2}|Style\s+\d{1,2}|Color\s+\d{1,2})$",
    re.IGNORECASE,
)
OPTION_ONLY_RE = re.compile(
    r"^(?:"
    r"black|white|red|blue|green|yellow|pink|purple|orange|gray|grey|brown|beige|navy|"
    r"small|medium|large|xl|xxl|one\s+size|style|color|option|variant|"
    r"gift\s+idea|design|pattern|personalized|custom"
    r")(?:\s+\d{1,2})?$",
    re.IGNORECASE,
)


@dataclass
class DetailPageFields:
    title: str = ""
    image_url: str = ""


class ProductDetailHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.og_title: str = ""
        self.document_title_parts: list[str] = []
        self.landing_image: str = ""
        self.landing_image_old_hires: str = ""
        self.wrapper_image: str = ""
        self.og_image: str = ""
        self._in_product_title = False
        self._product_title_depth = 0
        self._in_document_title = False
        self._document_title_depth = 0
        self._in_image_wrapper = False
        self._image_wrapper_depth = 0
        self._depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._depth += 1
        attr = {key.lower(): value or "" for key, value in attrs}
        tag = tag.lower()
        element_id = attr.get("id", "")

        if element_id == "productTitle":
            self._in_product_title = True
            self._product_title_depth = self._depth

        if tag == "title":
            self._in_document_title = True
            self._document_title_depth = self._depth

        if element_id == "imgTagWrapperId":
            self._in_image_wrapper = True
            self._image_wrapper_depth = self._depth

        if tag == "img":
            if element_id == "landingImage":
                if attr.get("src", "").strip() and not self.landing_image:
                    self.landing_image = attr.get("src", "").strip()
                if attr.get("data-old-hires", "").strip() and not self.landing_image_old_hires:
                    self.landing_image_old_hires = attr.get("data-old-hires", "").strip()
                if not self.landing_image and not self.landing_image_old_hires:
                    self.landing_image = image_url_from_attrs(attr)
            if self._in_image_wrapper and attr.get("src", "").strip() and not self.wrapper_image:
                self.wrapper_image = attr.get("src", "").strip()

        if tag == "meta" and attr.get("property", "").lower() == "og:image":
            self.og_image = self.og_image or attr.get("content", "").strip()
        if tag == "meta" and attr.get("property", "").lower() == "og:title":
            self.og_title = self.og_title or attr.get("content", "").strip()

        if tag in VOID_TAGS:
            self.handle_endtag(tag)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag.lower() not in VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if self._in_product_title and self._depth <= self._product_title_depth:
            self._in_product_title = False
        if self._in_document_title and self._depth <= self._document_title_depth:
            self._in_document_title = False
        if self._in_image_wrapper and self._depth <= self._image_wrapper_depth:
            self._in_image_wrapper = False
        self._depth = max(0, self._depth - 1)

    def handle_data(self, data: str) -> None:
        if self._in_product_title:
            text = normalize_space(data)
            if text:
                self.title_parts.append(text)
        if self._in_document_title:
            text = normalize_space(data)
            if text:
                self.document_title_parts.append(text)


def clean_title(value: str) -> str:
    text = normalize_space(unescape(value or ""))
    text = re.sub(r"^Sponsored Ad\s*-\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^Amazon\.com:\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*:\s*Clothing,\s*Shoes\s*&\s*Jewelry\s*$", "", text, flags=re.IGNORECASE)
    return text


def is_valid_product_title(value: str) -> bool:
    title = clean_title(value)
    if len(title) < 20:
        return False
    if INVALID_TITLE_RE.match(title):
        return False
    if OPTION_ONLY_RE.match(title):
        return False
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9'&+-]*", title)
    if len(words) < 3:
        return False
    return True


def display_product_title(value: str) -> str:
    title = clean_title(value)
    return title if is_valid_product_title(title) else UNAVAILABLE_TITLE


def ensure_detail_fix_fields(row: dict[str, str]) -> dict[str, str]:
    row.setdefault("raw_title", row.get("title", ""))
    row.setdefault("title_source", "listing_card" if row.get("title", "") else "")
    row.setdefault("title_fixed", "false")
    row.setdefault("image_source", "listing_card" if row.get("image_url", "") else "")
    row.setdefault("image_fixed", "false")
    row.setdefault("detail_fetched_reason", "")
    row.setdefault("detail_page_status", "")
    row.setdefault("detail_title_found", "")
    row.setdefault("detail_image_found", "")
    row.setdefault("detail_error", "")
    row.setdefault("detail_bsr_found", "")
    row.setdefault("detail_bsr_error", "")
    if not row.get("raw_title", "") and row.get("title", ""):
        row["raw_title"] = row.get("title", "")
    if row.get("image_url", "") and not row.get("image_source", ""):
        row["image_source"] = "listing_card"
    return row


def extract_detail_page_fields(html: str) -> DetailPageFields:
    parser = ProductDetailHTMLParser()
    parser.feed(html or "")
    parser.close()
    title = clean_title(" ".join(parser.title_parts))
    if not title:
        title = clean_title(parser.og_title)
    if not title:
        title = clean_title(" ".join(parser.document_title_parts))
    image_url = parser.landing_image or parser.landing_image_old_hires or parser.wrapper_image or parser.og_image
    return DetailPageFields(title=title, image_url=image_url)


def image_url_from_attrs(attr: dict[str, str]) -> str:
    for key in ("src", "data-src", "data-old-hires"):
        value = attr.get(key, "").strip()
        if value:
            return value
    dynamic = attr.get("data-a-dynamic-image", "").strip()
    if dynamic:
        dynamic_url = _image_from_dynamic_json(dynamic)
        if dynamic_url:
            return dynamic_url
    srcset = attr.get("srcset", "").strip()
    if srcset:
        return _image_from_srcset(srcset)
    return ""


def _image_from_dynamic_json(value: str) -> str:
    text = unescape(value)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"https?://[^\"'\s]+", text)
        return match.group(0) if match else ""
    if not isinstance(data, dict):
        return ""
    best_url = ""
    best_area = -1
    for url, dimensions in data.items():
        area = 0
        if isinstance(dimensions, list) and len(dimensions) >= 2:
            try:
                area = int(dimensions[0]) * int(dimensions[1])
            except (TypeError, ValueError):
                area = 0
        if area > best_area:
            best_url = str(url)
            best_area = area
    return best_url


def _image_from_srcset(value: str) -> str:
    candidates = []
    for item in value.split(","):
        parts = item.strip().split()
        if not parts:
            continue
        url = parts[0]
        width = 0
        if len(parts) > 1 and parts[1].endswith("w"):
            try:
                width = int(parts[1][:-1])
            except ValueError:
                width = 0
        candidates.append((width, url))
    if not candidates:
        return ""
    return sorted(candidates, key=lambda item: item[0], reverse=True)[0][1]
