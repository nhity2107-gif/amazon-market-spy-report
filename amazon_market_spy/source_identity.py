from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse


CANONICAL_SOURCE_TYPES = {
    "seller",
    "category_best_seller",
    "category_new_release",
    "search_result",
    "unknown",
}

SOURCE_IDENTITY_FIELDS = [
    "source_id",
    "source_rank",
    "marketplace",
    "category_id",
    "category_name",
    "source_identity_method",
    "source_identity_evidence",
    "legacy_source_type",
    "rank_rejected_reason",
    "source_duplicate_count",
]

SOURCE_HISTORY_FIELDS = [
    "previous_source_rank",
    "source_rank_change",
    "source_observation_count",
    "source_days_seen",
]

_SOURCE_TYPE_ALIASES = {
    "seller": "seller",
    "store": "seller",
    "merchant": "seller",
    "best_seller": "category_best_seller",
    "best_sellers": "category_best_seller",
    "best-seller": "category_best_seller",
    "best-sellers": "category_best_seller",
    "bestseller": "category_best_seller",
    "bestsellers": "category_best_seller",
    "category_best_seller": "category_best_seller",
    "category_best_sellers": "category_best_seller",
    "new_release": "category_new_release",
    "new_releases": "category_new_release",
    "new-release": "category_new_release",
    "new-releases": "category_new_release",
    "category_new_release": "category_new_release",
    "category_new_releases": "category_new_release",
    "category": "search_result",
    "search": "search_result",
    "search_result": "search_result",
    "search_results": "search_result",
    "unknown": "unknown",
}

_UNSUPPORTED_EXPLICIT_TYPES = {
    "movers",
    "movers_shakers",
    "movers-and-shakers",
    "movers_and_shakers",
}


@dataclass(frozen=True)
class SourceIdentity:
    source_type: str
    source_id: str
    source_rank: int | None
    marketplace: str
    category_id: str
    category_name: str
    method: str
    evidence: str
    legacy_source_type: str
    rank_rejected_reason: str


def classify_source(row: dict[str, str], source_meta: dict[str, str] | None = None) -> SourceIdentity:
    meta = source_meta or {}
    raw_source_type = _text(row.get("source_type", "") or row.get("page_type", "") or meta.get("source_type", ""))
    source_type, method, evidence = _classify_source_type(row, meta, raw_source_type)
    marketplace = _marketplace_for_row(row, meta)
    category_name = _text(row.get("category_name", "") or row.get("category", "") or meta.get("category", ""))
    category_id = _category_id_for_row(row, meta, category_name)
    if source_type == "seller":
        category_name = ""
        category_id = ""
    source_rank, rank_reason = parse_source_rank(row)
    source_id = _source_id(row, meta, source_type, marketplace, category_id, category_name)
    legacy_source_type = raw_source_type if raw_source_type and raw_source_type != source_type else _text(row.get("legacy_source_type", ""))

    return SourceIdentity(
        source_type=source_type,
        source_id=source_id,
        source_rank=source_rank,
        marketplace=marketplace,
        category_id=category_id,
        category_name=category_name,
        method=method,
        evidence=evidence,
        legacy_source_type=legacy_source_type,
        rank_rejected_reason=rank_reason,
    )


def normalize_source_identity(
    row: dict[str, str],
    source_meta: dict[str, str] | None = None,
) -> dict[str, str]:
    identity = classify_source(row, source_meta)
    row["source_type"] = identity.source_type
    row["source_id"] = identity.source_id
    row["source_rank"] = str(identity.source_rank) if identity.source_rank is not None else ""
    row["marketplace"] = identity.marketplace
    row["category_id"] = identity.category_id
    row["category_name"] = identity.category_name
    row["source_identity_method"] = identity.method
    row["source_identity_evidence"] = identity.evidence
    if identity.legacy_source_type:
        row["legacy_source_type"] = identity.legacy_source_type
    else:
        row.setdefault("legacy_source_type", "")
    row["rank_rejected_reason"] = identity.rank_rejected_reason
    row.setdefault("source_duplicate_count", "1")
    return row


def source_history_key(row: dict[str, str], source_meta: dict[str, str] | None = None) -> tuple[str, str, str, str]:
    identity = classify_source(row, source_meta)
    asin = _text(row.get("asin", "")).upper()
    return (identity.marketplace, identity.source_type, identity.source_id, asin)


def parse_source_rank(row: dict[str, str]) -> tuple[int | None, str]:
    saw_value = False
    saw_malformed = False
    for field in ("source_rank", "display_rank", "display_order", "rank", "position"):
        raw = _text(row.get(field, ""))
        if not raw:
            continue
        saw_value = True
        value = _rank_number(raw)
        if value is None:
            saw_malformed = True
            continue
        if value <= 0:
            return None, "invalid_non_positive_rank"
        return value, ""
    if saw_malformed:
        return None, "malformed_rank"
    if saw_value:
        return None, "invalid_rank"
    return None, "missing_rank"


def canonical_source_type(value: str) -> str:
    key = _source_type_key(value)
    if key in CANONICAL_SOURCE_TYPES:
        return key
    return _SOURCE_TYPE_ALIASES.get(key, "unknown")


def _classify_source_type(
    row: dict[str, str],
    meta: dict[str, str],
    raw_source_type: str,
) -> tuple[str, str, str]:
    explicit = _source_type_key(raw_source_type)
    if explicit in _SOURCE_TYPE_ALIASES:
        return _SOURCE_TYPE_ALIASES[explicit], "configured_source_type", raw_source_type
    if explicit in _UNSUPPORTED_EXPLICIT_TYPES:
        return "unknown", "configured_unsupported_source_type", raw_source_type

    page_type = _source_type_key(row.get("page_type", "") or meta.get("page_type", ""))
    if page_type in _SOURCE_TYPE_ALIASES:
        return _SOURCE_TYPE_ALIASES[page_type], "parsed_page_type", page_type
    if page_type in _UNSUPPORTED_EXPLICIT_TYPES:
        return "unknown", "parsed_unsupported_page_type", page_type

    for url in _candidate_urls(row, meta):
        source_type = _source_type_from_url(url)
        if source_type:
            return source_type, "url_pattern", url

    text = " ".join(
        _text(row.get(field, "") or meta.get(field, ""))
        for field in ("source_name", "category", "category_name")
    ).lower()
    normalized = text.replace("-", " ").replace("_", " ")
    if "best seller" in normalized or "best sellers" in normalized:
        return "category_best_seller", "text_fallback", text
    if "new release" in normalized or "new releases" in normalized or "newest arrivals" in normalized:
        return "category_new_release", "text_fallback", text
    if any(term in normalized for term in ("search result", "search results", "category search")):
        return "search_result", "text_fallback", text
    return "unknown", "unknown", text


def _source_type_from_url(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.lower()
    query = parse_qs(parsed.query)
    if any(query.get(key) for key in ("m", "me", "seller")):
        return "seller"
    if "/sp" in path and "seller" in query:
        return "seller"
    if "new-releases" in path or "newreleases" in path:
        return "category_new_release"
    if "best-sellers" in path or "/zgbs/" in path or "/bestsellers/" in path:
        return "category_best_seller"
    if path.rstrip("/") in {"", "/s"} or path.startswith("/s/") or query.get("k") or query.get("rh"):
        return "search_result"
    return ""


def _source_id(
    row: dict[str, str],
    meta: dict[str, str],
    source_type: str,
    marketplace: str,
    category_id: str,
    category_name: str,
) -> str:
    explicit = _text(row.get("source_id", "") or meta.get("source_id", ""))
    if explicit:
        return explicit
    if source_type == "seller":
        seller_id = _seller_id(row, meta)
        if seller_id:
            return f"seller:{marketplace}:{seller_id.upper()}"
        seller_name = _slug(_text(row.get("seller_name", "") or meta.get("seller_name", "") or row.get("source_name", "")))
        return f"seller:{marketplace}:{seller_name or _url_fingerprint(row, meta)}"
    if source_type in {"category_best_seller", "category_new_release"}:
        key = category_id or _slug(category_name) or _url_fingerprint(row, meta)
        return f"{source_type}:{marketplace}:{key}"
    if source_type == "search_result":
        return f"search_result:{marketplace}:{_search_key(row, meta, category_name)}"
    return f"unknown:{marketplace}:{_url_fingerprint(row, meta) or _slug(category_name) or 'source'}"


def _marketplace_for_row(row: dict[str, str], meta: dict[str, str]) -> str:
    for url in _candidate_urls(row, meta):
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        if host:
            if host.startswith("www."):
                host = host[4:]
            return host
    return _text(row.get("marketplace", "") or meta.get("marketplace", "")) or "amazon.com"


def _category_id_for_row(row: dict[str, str], meta: dict[str, str], category_name: str) -> str:
    explicit = _text(row.get("category_id", "") or meta.get("category_id", ""))
    if explicit:
        return explicit
    for url in _candidate_urls(row, meta):
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        for key in ("node", "bbn"):
            value = _first_query_value(query, key)
            if value:
                return value
        path_parts = [part for part in parsed.path.split("/") if part]
        for part in reversed(path_parts):
            if part.isdigit():
                return part
    return _slug(category_name)


def _search_key(row: dict[str, str], meta: dict[str, str], category_name: str) -> str:
    for url in _candidate_urls(row, meta):
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        parts = []
        for key in ("k", "i", "rh", "node", "bbn"):
            values = query.get(key)
            if values:
                parts.append(f"{key}-{_slug(values[0])}")
        if parts:
            return "--".join(parts)
        path = _slug(parsed.path)
        if path:
            return path
    return _slug(category_name) or _url_fingerprint(row, meta)


def _seller_id(row: dict[str, str], meta: dict[str, str]) -> str:
    explicit = _text(row.get("seller_id", "") or meta.get("seller_id", ""))
    if explicit:
        return explicit
    for url in _candidate_urls(row, meta):
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        for key in ("m", "me", "seller"):
            value = _first_query_value(query, key)
            if value:
                return value
    return ""


def _candidate_urls(row: dict[str, str], meta: dict[str, str]) -> list[str]:
    urls: list[str] = []
    for field in ("source_url", "page_url", "seller_url", "url", "rank_source_url"):
        value = _text(row.get(field, "") or meta.get(field, ""))
        if value and value not in urls:
            urls.append(value)
    return urls


def _url_fingerprint(row: dict[str, str], meta: dict[str, str]) -> str:
    for url in _candidate_urls(row, meta):
        parsed = urlparse(url)
        stable = f"{parsed.path}?{parsed.query}".strip("?")
        if stable:
            return hashlib.sha1(stable.encode("utf-8")).hexdigest()[:12]
    fallback = "|".join(
        _text(row.get(field, "") or meta.get(field, ""))
        for field in ("source_name", "category", "category_name", "page_type", "source_type")
    )
    return hashlib.sha1(fallback.encode("utf-8")).hexdigest()[:12] if fallback else ""


def _first_query_value(query: dict[str, list[str]], key: str) -> str:
    values = query.get(key)
    return _text(values[0]) if values else ""


def _rank_number(value: str) -> int | None:
    text = _text(value).replace(",", "").replace("#", "")
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _source_type_key(value: str) -> str:
    return _text(value).lower().replace("-", "_").replace(" ", "_").replace("&", "and")


def _slug(value: str) -> str:
    text = _text(value).lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def _text(value: object) -> str:
    return " ".join(str(value or "").strip().split())
