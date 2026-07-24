from __future__ import annotations

import re
from html import unescape
from html.parser import HTMLParser

from .utils import isoformat_utc, is_asin, normalize_space, now_utc


CATEGORY_RANK_FIELDS = [
    "bsr_rank",
    "bsr_category",
    "category_ranks_raw",
    "raw_bsr_block",
    "primary_bsr_rank",
    "primary_bsr_category",
    "sub_bsr_rank",
    "sub_bsr_category",
    "all_bsr_ranks",
    "subcategory_rank_score",
    "rank_extracted_at",
    "rank_source_url",
    "rank_page_status",
    "rank_parse_method",
    "rank_parse_confidence",
    "rank_parse_warning",
    "accordion_found",
    "accordion_expanded",
    "bsr_visible_after_expand",
]

RANK_RE = re.compile(
    r"#\s*([0-9][0-9,]*)\s+in\s+(.+?)(?=\s*[;|]?\s+#\s*[0-9]|\s+Best Sellers Rank|$)",
    re.IGNORECASE,
)
SCRIPT_STYLE_RE = re.compile(r"<(?:script|style)\b.*?</(?:script|style)>", re.IGNORECASE | re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")
CATEGORY_STOP_RE = re.compile(
    r"\s+(?:Date First Available|Customer Reviews|ASIN|Manufacturer|Item model number|Product Dimensions|"
    r"Feedback|Warranty|Best Sellers Rank|Domestic Shipping|International Shipping)\b",
    re.IGNORECASE,
)
DETAIL_RANK_SECTIONS = [
    ("productDetails_detailBullets_sections1", "product_details"),
    ("detailBullets_feature_div", "detail_bullets"),
    ("productDetails_db_sections", "product_details_db"),
]
PRODUCT_PAGE_BSR_PARSE_METHODS = {
    "product_details",
    "detail_bullets",
    "product_details_db",
    "product_information_item_details",
    "text_scan",
}
BSR_LABEL_RE = re.compile(r"(?:Best Sellers Rank|Sales Rank)", re.IGNORECASE)
BSR_BLOCK_STOP_RE = re.compile(
    r"\s+(?:Date First Available|Customer Reviews|ASIN|Manufacturer|Item model number|Product Dimensions|"
    r"Package Dimensions|Item Weight|Department|Domestic Shipping|International Shipping|Warranty|Feedback|"
    r"Is Discontinued By Manufacturer)\b",
    re.IGNORECASE,
)
PRODUCT_INFORMATION_RE = re.compile(r"(?:Product information|Item details|Features\s*&\s*Specs)", re.IGNORECASE)


def ensure_category_rank_fields(row: dict[str, str]) -> dict[str, str]:
    for field in CATEGORY_RANK_FIELDS:
        row.setdefault(field, "")
    if row.get("bsr_rank", "") and not row.get("primary_bsr_rank", ""):
        row["primary_bsr_rank"] = row.get("bsr_rank", "")
    if row.get("bsr_category", "") and not row.get("primary_bsr_category", ""):
        row["primary_bsr_category"] = row.get("bsr_category", "")
    if row.get("category_ranks_raw", "") and not row.get("all_bsr_ranks", ""):
        row["all_bsr_ranks"] = row.get("category_ranks_raw", "")
    if row.get("all_bsr_ranks", "") and not row.get("category_ranks_raw", ""):
        row["category_ranks_raw"] = row.get("all_bsr_ranks", "")
    if row.get("category_ranks_raw", "") and not row.get("raw_bsr_block", ""):
        row["raw_bsr_block"] = row.get("category_ranks_raw", "")
    if row.get("raw_bsr_block", "") and not row.get("category_ranks_raw", ""):
        row["category_ranks_raw"] = row.get("raw_bsr_block", "")

    ranks = _rank_entries(row.get("all_bsr_ranks", "") or row.get("raw_bsr_block", "") or row.get("category_ranks_raw", ""))
    if ranks:
        if not row.get("primary_bsr_rank", ""):
            row["primary_bsr_rank"] = ranks[0][0].replace(",", "")
        if not row.get("primary_bsr_category", ""):
            row["primary_bsr_category"] = ranks[0][1]
        if not row.get("bsr_rank", ""):
            row["bsr_rank"] = row.get("primary_bsr_rank", "")
        if not row.get("bsr_category", ""):
            row["bsr_category"] = row.get("primary_bsr_category", "")
        sub_rank_entry = _best_subcategory_entry(ranks)
        if sub_rank_entry:
            if not row.get("sub_bsr_rank", ""):
                row["sub_bsr_rank"] = sub_rank_entry[0].replace(",", "")
            if not row.get("sub_bsr_category", ""):
                row["sub_bsr_category"] = sub_rank_entry[1]
    if row.get("primary_bsr_rank", "") and not row.get("bsr_rank", ""):
        row["bsr_rank"] = row.get("primary_bsr_rank", "")
    if row.get("primary_bsr_category", "") and not row.get("bsr_category", ""):
        row["bsr_category"] = row.get("primary_bsr_category", "")
    if not row.get("subcategory_rank_score", ""):
        row["subcategory_rank_score"] = subcategory_rank_score(row.get("sub_bsr_rank", ""))
    return row


def has_category_rank_data(row: dict[str, str]) -> bool:
    return any(
        (row.get(field, "") or "").strip()
        for field in (
            "bsr_rank",
            "bsr_category",
            "category_ranks_raw",
            "raw_bsr_block",
            "primary_bsr_rank",
            "primary_bsr_category",
            "sub_bsr_rank",
            "sub_bsr_category",
            "all_bsr_ranks",
        )
    )


def merge_category_rank_fields(row: dict[str, str], source: dict[str, str]) -> bool:
    ensure_category_rank_fields(row)
    source_fields = ensure_category_rank_fields(dict(source))
    changed = False
    for field in CATEGORY_RANK_FIELDS:
        value = (source_fields.get(field, "") or "").strip()
        if value and not (row.get(field, "") or "").strip():
            row[field] = value
            changed = True
    if changed:
        ensure_category_rank_fields(row)
    return changed


def is_product_page_bsr_fields(row: dict[str, str]) -> bool:
    return (row.get("rank_parse_method", "") or "").strip() in PRODUCT_PAGE_BSR_PARSE_METHODS


def category_rank_cache_from_rows(
    rows: list[dict[str, str]],
    *,
    require_product_page_source: bool = False,
) -> dict[str, dict[str, str]]:
    cache: dict[str, dict[str, str]] = {}
    for row in rows:
        asin = (row.get("asin", "") or "").strip().upper()
        if not is_asin(asin):
            continue
        if require_product_page_source and not is_product_page_bsr_fields(row):
            continue
        fields = ensure_category_rank_fields(dict(row))
        if not has_category_rank_data(fields):
            continue
        if asin not in cache:
            cache[asin] = {field: fields.get(field, "") for field in CATEGORY_RANK_FIELDS}
        else:
            merge_category_rank_fields(cache[asin], fields)
    return cache


def extract_bsr_from_product_page(
    html: str,
    source_url: str = "",
    page_status: str = "",
    diagnostics: dict[str, str] | None = None,
) -> dict[str, str]:
    block, parse_method, confidence = _best_rank_text_block(html)
    ranks = _rank_entries(block)
    audit_fields = _rank_audit_fields(source_url, page_status, parse_method, confidence, diagnostics)
    if not ranks:
        fields = _empty_rank_fields()
        fields.update(audit_fields)
        fields["raw_bsr_block"] = block
        fields["category_ranks_raw"] = block
        return fields

    raw_bsr_block = block
    all_ranks = "; ".join(raw for _, _, raw in ranks)
    first_rank, first_category, _ = ranks[0]
    fields = {
        "bsr_rank": first_rank.replace(",", ""),
        "bsr_category": first_category,
        "category_ranks_raw": raw_bsr_block,
        "raw_bsr_block": raw_bsr_block,
        "primary_bsr_rank": first_rank.replace(",", ""),
        "primary_bsr_category": first_category,
        "sub_bsr_rank": "",
        "sub_bsr_category": "",
        "all_bsr_ranks": all_ranks,
        "subcategory_rank_score": "",
        **audit_fields,
    }
    sub_entry = _best_subcategory_entry(ranks)
    if sub_entry:
        sub_rank, sub_category, _ = sub_entry
        fields["sub_bsr_rank"] = sub_rank.replace(",", "")
        fields["sub_bsr_category"] = sub_category
    return ensure_category_rank_fields(fields)


def subcategory_rank_score(rank: str | int | None) -> str:
    try:
        value = int(float(str(rank or "").replace(",", "")))
    except (TypeError, ValueError):
        return ""
    if value <= 100:
        return "100"
    if value <= 500:
        return "90"
    if value <= 1000:
        return "80"
    if value <= 5000:
        return "70"
    if value <= 10000:
        return "60"
    return "40"


def _rank_entries(text: str) -> list[tuple[str, str, str]]:
    entries: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str]] = set()
    for match in RANK_RE.finditer(text):
        rank = match.group(1).replace(" ", "")
        category = _clean_category(match.group(2))
        if not category:
            continue
        key = (rank.replace(",", ""), category.lower())
        if key in seen:
            continue
        seen.add(key)
        entries.append((rank, category, f"#{rank} in {category}"))
    return entries


def _best_subcategory_entry(ranks: list[tuple[str, str, str]]) -> tuple[str, str, str] | None:
    if len(ranks) <= 1:
        return None
    candidates = ranks[1:]
    return min(candidates, key=lambda entry: _rank_number(entry[0]) or 10**12)


def _rank_number(value: str) -> int | None:
    try:
        return int(str(value or "").replace(",", ""))
    except ValueError:
        return None


def _clean_category(value: str) -> str:
    text = normalize_space(value)
    text = re.sub(r"\([^)]*Top\s+100[^)]*\)", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\([^)]*See\s+Top[^)]*\)", "", text, flags=re.IGNORECASE)
    text = CATEGORY_STOP_RE.split(text, maxsplit=1)[0]
    text = text.strip(" -:;,.")
    return normalize_space(text)


def _best_sellers_rank_block(text: str, multiline: bool = False) -> str:
    normalized = normalize_space(text)
    match = BSR_LABEL_RE.search(normalized)
    if not match:
        return ""
    block = normalized[match.start() :]
    stop_match = BSR_BLOCK_STOP_RE.search(block, pos=max(1, match.end() - match.start()))
    if stop_match:
        block = block[: stop_match.start()]
    block = normalize_space(block)
    if multiline:
        ranks = _rank_entries(block)
        if ranks:
            label = "Sales Rank" if re.match(r"Sales Rank", block, flags=re.IGNORECASE) else "Best Sellers Rank"
            return "\n".join([label, *(raw for _, _, raw in ranks)])
    return block


def _best_rank_text_block(html: str) -> tuple[str, str, str]:
    for section_id, parse_method in DETAIL_RANK_SECTIONS:
        blocks = _section_text_blocks(html, section_id)
        for block in blocks:
            rank_block = _best_sellers_rank_block(block)
            if _rank_entries(rank_block):
                return rank_block, parse_method, "high"

    for block in _product_information_item_detail_blocks(html):
        rank_block = _best_sellers_rank_block(block, multiline=True)
        if _rank_entries(rank_block):
            return rank_block, "product_information_item_details", "high"

    text = _html_to_text(html)
    rank_block = _best_sellers_rank_block(text)
    if _rank_entries(rank_block):
        return rank_block, "text_scan", "medium"
    return rank_block, "text_scan", "low"


def _section_text_blocks(html: str, section_id: str) -> list[str]:
    parser = _ElementTextByIdParser(section_id)
    try:
        parser.feed(html or "")
        parser.close()
    except Exception:
        pass
    if parser.blocks:
        return parser.blocks

    pattern = re.compile(
        rf"<(?P<tag>[a-zA-Z0-9]+)\b(?=[^>]*\bid\s*=\s*['\"]?{re.escape(section_id)}['\"]?)[^>]*>.*?</(?P=tag)>",
        re.IGNORECASE | re.DOTALL,
    )
    return [_html_to_text(match.group(0)) for match in pattern.finditer(html or "")]


def _product_information_item_detail_blocks(html: str) -> list[str]:
    parser = _ProductInformationRankBlockParser()
    try:
        parser.feed(html or "")
        parser.close()
    except Exception:
        pass
    return parser.blocks


class _ElementTextByIdParser(HTMLParser):
    def __init__(self, target_id: str) -> None:
        super().__init__(convert_charrefs=True)
        self.target_id = target_id
        self.blocks: list[str] = []
        self._capturing = False
        self._depth = 0
        self._current: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {name.lower(): value for name, value in attrs}
        if self._capturing:
            self._depth += 1
            return
        if (attrs_dict.get("id") or "") == self.target_id:
            self._capturing = True
            self._depth = 1
            self._current = []

    def handle_endtag(self, tag: str) -> None:
        if not self._capturing:
            return
        self._depth -= 1
        if self._depth <= 0:
            block = normalize_space(" ".join(self._current))
            if block:
                self.blocks.append(block)
            self._capturing = False
            self._current = []

    def handle_data(self, data: str) -> None:
        if self._capturing and data:
            self._current.append(data)


class _ProductInformationRankBlockParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[str] = []
        self._stack: list[dict[str, object]] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style", "noscript"}:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        attrs_text = " ".join(value or "" for _, value in attrs)
        self._stack.append({"tag": tag.lower(), "text": [], "attrs": attrs_text})

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if self._skip_depth or not self._stack:
            return
        item = self._stack.pop()
        text = normalize_space(" ".join(item["text"]))  # type: ignore[arg-type]
        attrs_text = str(item.get("attrs", ""))
        tag_name = str(item.get("tag", ""))
        searchable = normalize_space(f"{attrs_text} {text}")
        if (
            tag_name not in {"html", "body"}
            and BSR_LABEL_RE.search(text)
            and (PRODUCT_INFORMATION_RE.search(searchable) or _looks_like_product_information_attrs(attrs_text))
        ):
            self.blocks.append(text)
        if self._stack and text:
            self._stack[-1]["text"].append(text)  # type: ignore[index, union-attr]

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        return

    def handle_data(self, data: str) -> None:
        if self._skip_depth or not self._stack or not data:
            return
        self._stack[-1]["text"].append(data)  # type: ignore[index, union-attr]


def _looks_like_product_information_attrs(attrs_text: str) -> bool:
    return bool(re.search(r"(?:product[-_ ]?information|item[-_ ]?details|feature[-_ ]?spec)", attrs_text, re.IGNORECASE))


def _rank_audit_fields(
    source_url: str,
    page_status: str,
    parse_method: str,
    confidence: str,
    diagnostics: dict[str, str] | None = None,
) -> dict[str, str]:
    diagnostics = diagnostics or {}
    return {
        "rank_extracted_at": isoformat_utc(now_utc()),
        "rank_source_url": source_url,
        "rank_page_status": page_status,
        "rank_parse_method": parse_method,
        "rank_parse_confidence": confidence,
        "rank_parse_warning": _rank_parse_warning(parse_method, confidence),
        "accordion_found": diagnostics.get("accordion_found", ""),
        "accordion_expanded": diagnostics.get("accordion_expanded", ""),
        "bsr_visible_after_expand": diagnostics.get("bsr_visible_after_expand", ""),
    }


def _rank_parse_warning(parse_method: str, confidence: str) -> str:
    if parse_method == "text_scan":
        if confidence == "low":
            return "Best Sellers Rank section selectors failed and no BSR block was found in text_scan fallback."
        return "Best Sellers Rank section selectors failed; parsed from text_scan fallback and should be verified."
    return ""


def _html_to_text(html: str) -> str:
    text = SCRIPT_STYLE_RE.sub(" ", html or "")
    text = TAG_RE.sub(" ", text)
    return normalize_space(unescape(text))


def _empty_rank_fields() -> dict[str, str]:
    return {field: "" for field in CATEGORY_RANK_FIELDS}
