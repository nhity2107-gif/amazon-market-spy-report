from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import parse_qsl, urlencode


MULTI_VALUE_KEYS = {
    "category",
    "evidence",
    "family",
    "occasion",
    "product_type",
    "quick",
    "recipient",
    "seller",
    "theme",
}


V2_PARAM_ALIASES: dict[str, str] = {
    "type": "product_type",
    "direction": "dir",
    "focus": "selected",
    "asin": "selected",
    "ASIN": "selected",
}


V2_EVIDENCE_FAMILY_PARAMS: dict[str, str] = {
    "seller_evidence": "seller",
    "best_seller_evidence": "best_seller",
    "new_release_evidence": "new_release",
    "supporting_evidence": "supporting",
}


CANONICAL_PARAM_ORDER = (
    "q",
    "preset",
    "view",
    "seller",
    "product_type",
    "recipient",
    "occasion",
    "theme",
    "message_intent",
    "category",
    "family",
    "evidence",
    "quick",
    "source_id",
    "source_type",
    "pod_relevance",
    "marketplace",
    "niche",
    "has_bsr",
    "sort",
    "dir",
    "page",
    "page_size",
    "selected",
    "score_min",
    "score_max",
    "growth_min",
    "growth_max",
    "reviews_min",
    "reviews_max",
    "price_min",
    "price_max",
)


def resolve_url_state(query: str | Iterable[tuple[str, str]]) -> dict[str, object]:
    pairs = _query_pairs(query)
    state: dict[str, object] = {key: [] for key in MULTI_VALUE_KEYS}

    for raw_key, raw_value in pairs:
        key = raw_key.strip()
        value = raw_value.strip()
        if not key or not value:
            continue
        if key in V2_EVIDENCE_FAMILY_PARAMS:
            _append_unique(state, "family", V2_EVIDENCE_FAMILY_PARAMS[key])
            _append_unique(state, "evidence", value)
            continue
        canonical = V2_PARAM_ALIASES.get(key, key)
        if canonical in MULTI_VALUE_KEYS:
            _append_unique(state, canonical, value)
        else:
            state[canonical] = value

    return {key: value for key, value in state.items() if value not in ("", [])}


def canonical_query_pairs(state: dict[str, object]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for key in CANONICAL_PARAM_ORDER:
        value = state.get(key)
        if value in (None, "", []):
            continue
        if key in MULTI_VALUE_KEYS and isinstance(value, list):
            pairs.extend((key, str(item)) for item in value if str(item).strip())
        else:
            pairs.append((key, str(value)))
    return pairs


def canonical_query_string(state: dict[str, object]) -> str:
    return urlencode(canonical_query_pairs(state), doseq=True)


def _query_pairs(query: str | Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
    if isinstance(query, str):
        return parse_qsl(query.lstrip("?"), keep_blank_values=False)
    return [(str(key), str(value)) for key, value in query]


def _append_unique(state: dict[str, object], key: str, value: str) -> None:
    items = state.setdefault(key, [])
    if not isinstance(items, list):
        items = []
        state[key] = items
    if value not in items:
        items.append(value)
