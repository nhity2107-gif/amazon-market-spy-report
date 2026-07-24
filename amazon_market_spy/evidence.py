from __future__ import annotations

from collections import defaultdict

from .pod import (
    CUSTOM_KEYWORDS,
    PHYSICAL_BRAND_KEYWORDS,
    PHYSICAL_FEATURE_KEYWORDS,
    POD_PRODUCT_TYPE_KEYWORDS,
    QUOTE_TEXT_KEYWORDS,
    ensure_pod_fields,
)
from .utils import normalize_space


POD_RELEVANCE_FIELDS = ["pod_relevance", "pod_relevance_reasons"]

SELLER_EVIDENCE_FIELDS = ["seller_leader", "seller_mover", "seller_new_push"]
CATEGORY_BEST_SELLER_EVIDENCE_FIELDS = ["category_winner", "category_breakout", "category_stable"]
CATEGORY_NEW_RELEASE_EVIDENCE_FIELDS = ["new_release_rising", "new_release_breakout", "new_release_watch"]
BSR_EVIDENCE_FIELDS = ["bsr_available", "strong_sub_bsr", "very_strong_sub_bsr"]

OBSERVATION_EVIDENCE_BOOLEAN_FIELDS = [
    *SELLER_EVIDENCE_FIELDS,
    *CATEGORY_BEST_SELLER_EVIDENCE_FIELDS,
    *CATEGORY_NEW_RELEASE_EVIDENCE_FIELDS,
    *BSR_EVIDENCE_FIELDS,
]

EVIDENCE_SUMMARY_FIELDS = ["evidence_labels", "evidence_count", "evidence_reasons"]

EVIDENCE_FIELDS = [
    *POD_RELEVANCE_FIELDS,
    *OBSERVATION_EVIDENCE_BOOLEAN_FIELDS,
    *EVIDENCE_SUMMARY_FIELDS,
]

PRODUCT_EVIDENCE_FIELDS = [
    "seller_evidence_leader",
    "seller_evidence_mover",
    "seller_evidence_new_push",
    "seller_evidence_best_rank",
    "seller_evidence_source_count",
    "best_seller_evidence_winner",
    "best_seller_evidence_breakout",
    "best_seller_evidence_stable",
    "best_seller_evidence_best_rank",
    "best_seller_evidence_source_count",
    "new_release_evidence_rising",
    "new_release_evidence_breakout",
    "new_release_evidence_watch",
    "new_release_evidence_best_rank",
    "new_release_evidence_source_count",
    "bsr_evidence_available",
    "bsr_evidence_strong",
    "bsr_evidence_very_strong",
    "bsr_evidence_best_sub_bsr",
    "bsr_evidence_best_sub_bsr_category",
    "evidence_source_family_count",
    "evidence_source_families",
]

VALID_POD_RELEVANCE = {"high", "medium", "low", "unknown"}
SOURCE_FAMILY_NAMES = {
    "seller": "seller",
    "category_best_seller": "category_best_seller",
    "category_new_release": "category_new_release",
}


def apply_observation_evidence(row: dict[str, str]) -> dict[str, str]:
    """Attach source-specific evidence fields without changing legacy classification."""

    ensure_pod_relevance(row)
    for field in OBSERVATION_EVIDENCE_BOOLEAN_FIELDS:
        row[field] = "false"

    labels: list[str] = []
    reasons: list[str] = []

    source_type = _text(row.get("source_type", ""))
    source_rank = _to_int(row.get("source_rank", ""))
    previous_rank = _to_int(row.get("previous_source_rank", ""))
    rank_change = _to_int(row.get("source_rank_change", ""))
    observation_count = _to_int(row.get("source_observation_count", "")) or 0
    days_seen = _to_int(row.get("source_days_seen", "")) or 0
    pod_not_low = row.get("pod_relevance", "unknown") != "low"

    if source_type == "seller":
        if source_rank is not None and source_rank <= 10 and days_seen >= 7:
            _mark(row, labels, reasons, "seller_leader", "Seller Leader", f"Seller rank #{source_rank} for {days_seen} days")
        if (
            previous_rank is not None
            and rank_change is not None
            and source_rank is not None
            and rank_change >= 10
            and source_rank <= 100
            and observation_count >= 2
        ):
            _mark(row, labels, reasons, "seller_mover", "Seller Mover", f"Seller improved from #{previous_rank} to #{source_rank}")
        if source_rank is not None and days_seen <= 7 and source_rank <= 20:
            _mark(
                row,
                labels,
                reasons,
                "seller_new_push",
                "Seller New Push",
                f"Seller rank #{source_rank} in first {days_seen or 1} days",
            )

    if source_type == "category_best_seller" and pod_not_low:
        context = _category_context(row, "Best Seller")
        category_suffix = _category_suffix(row)
        if source_rank is not None and source_rank <= 30 and days_seen >= 7:
            _mark(
                row,
                labels,
                reasons,
                "category_winner",
                "Category Winner",
                f"{context} rank #{source_rank} for {days_seen} days{category_suffix}",
            )
        if (
            previous_rank is not None
            and rank_change is not None
            and source_rank is not None
            and rank_change >= 15
            and source_rank <= 50
            and observation_count >= 2
        ):
            _mark(
                row,
                labels,
                reasons,
                "category_breakout",
                "Category Breakout",
                f"{context} improved from #{previous_rank} to #{source_rank}{category_suffix}",
            )
        if source_rank is not None and source_rank <= 100 and days_seen >= 14:
            _mark(
                row,
                labels,
                reasons,
                "category_stable",
                "Category Stable",
                f"{context} rank #{source_rank} for {days_seen} days{category_suffix}",
            )

    if source_type == "category_new_release" and pod_not_low:
        context = _category_context(row, "New Release")
        category_suffix = _category_suffix(row)
        if (
            previous_rank is not None
            and rank_change is not None
            and source_rank is not None
            and rank_change >= 10
            and source_rank <= 100
            and observation_count >= 2
        ):
            _mark(
                row,
                labels,
                reasons,
                "new_release_rising",
                "New Release Rising",
                f"{context} improved from #{previous_rank} to #{source_rank}{category_suffix}",
            )
        if (
            previous_rank is not None
            and rank_change is not None
            and source_rank is not None
            and rank_change >= 30
            and source_rank <= 30
            and observation_count >= 2
        ):
            _mark(
                row,
                labels,
                reasons,
                "new_release_breakout",
                "New Release Breakout",
                f"{context} improved from #{previous_rank} to #{source_rank}{category_suffix}",
            )
        if source_rank is not None and days_seen <= 7 and source_rank <= 100:
            _mark(
                row,
                labels,
                reasons,
                "new_release_watch",
                "New Release Watch",
                f"{context} rank #{source_rank} in first {days_seen or 1} days{category_suffix}",
            )

    sub_bsr_rank = _to_int(row.get("sub_bsr_rank", ""))
    if sub_bsr_rank is not None and sub_bsr_rank > 0:
        category = _text(row.get("sub_bsr_category", "")) or "unknown sub-category"
        _mark(row, labels, reasons, "bsr_available", "Sub-BSR Available", f"Sub-category BSR #{sub_bsr_rank} in {category}")
        if sub_bsr_rank <= 5000:
            _mark(row, labels, reasons, "strong_sub_bsr", "Strong Sub-BSR", f"Strong sub-category BSR #{sub_bsr_rank} in {category}")
        if sub_bsr_rank <= 1000:
            _mark(
                row,
                labels,
                reasons,
                "very_strong_sub_bsr",
                "Very Strong Sub-BSR",
                f"Very strong sub-category BSR #{sub_bsr_rank} in {category}",
            )

    row["evidence_labels"] = "; ".join(labels)
    row["evidence_count"] = str(len(labels))
    row["evidence_reasons"] = "; ".join(reasons)
    return row


def apply_product_evidence(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    for row in rows:
        apply_observation_evidence(row)
    summaries = product_evidence_summaries(rows)
    for row in rows:
        row.update(summaries.get(_product_key(row), _empty_product_summary()))
    return rows


def product_evidence_summaries(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        key = _product_key(row)
        if key[1]:
            grouped[key].append(row)

    return {key: _summarize_product_evidence(group_rows) for key, group_rows in grouped.items()}


def ensure_pod_relevance(row: dict[str, str]) -> dict[str, str]:
    existing = _text(row.get("pod_relevance", "")).lower()
    if existing in VALID_POD_RELEVANCE:
        row["pod_relevance"] = existing
        row["pod_relevance_reasons"] = _text(row.get("pod_relevance_reasons", "")) or f"Existing POD relevance: {existing}"
        return row

    ensure_pod_fields(row)
    text = _normalized_product_text(row)
    pod_score = _to_int(row.get("pod_score", "")) or 0
    is_pod = _text(row.get("is_pod", "")).lower()
    pod_type = _text(row.get("pod_type", "")).lower()
    pod_reason = _text(row.get("pod_reason", "")).lower()

    custom_matches = _matched_terms(text, CUSTOM_KEYWORDS)
    product_type_matches = _matched_terms(text, POD_PRODUCT_TYPE_KEYWORDS)
    quote_matches = _matched_terms(text, QUOTE_TEXT_KEYWORDS)
    low_matches = _matched_terms(text, [*PHYSICAL_BRAND_KEYWORDS, *PHYSICAL_FEATURE_KEYWORDS])

    reasons: list[str] = []
    if is_pod == "yes":
        reasons.append("Existing POD classifier marked yes")
    if is_pod == "maybe":
        reasons.append("Existing POD classifier marked maybe")
    if pod_type and pod_type not in {"unknown", "physical_brand_product"}:
        reasons.append(f"Known POD product type: {pod_type}")
    if custom_matches:
        reasons.append(f"Customization language: {', '.join(custom_matches[:3])}")
    if product_type_matches:
        reasons.append(f"POD product keyword: {', '.join(product_type_matches[:3])}")
    if quote_matches:
        reasons.append(f"Quote/text language: {', '.join(quote_matches[:3])}")
    if low_matches:
        reasons.append(f"Physical product language: {', '.join(low_matches[:3])}")
    if pod_reason:
        reasons.append("POD classifier reasons available")

    if is_pod == "yes" or pod_score >= 40 or custom_matches:
        relevance = "high"
    elif is_pod == "maybe" or pod_score >= 25 or (product_type_matches and quote_matches) or (
        product_type_matches and pod_type not in {"", "unknown", "physical_brand_product"}
    ):
        relevance = "medium"
    elif (is_pod == "no" and pod_type == "physical_brand_product") or (pod_score <= -20 and low_matches and not custom_matches):
        relevance = "low"
    else:
        relevance = "unknown"
        reasons.append("No reliable POD relevance evidence")

    row["pod_relevance"] = relevance
    row["pod_relevance_reasons"] = "; ".join(reasons)
    return row


def _summarize_product_evidence(rows: list[dict[str, str]]) -> dict[str, str]:
    summary = _empty_product_summary()
    source_ids = {
        "seller": set(),
        "category_best_seller": set(),
        "category_new_release": set(),
    }
    best_ranks: dict[str, int | None] = {
        "seller": None,
        "category_best_seller": None,
        "category_new_release": None,
    }
    active_families: set[str] = set()

    for row in rows:
        source_type = _text(row.get("source_type", ""))
        if source_type in source_ids:
            source_ids[source_type].add(_source_identity(row))
            rank = _to_int(row.get("source_rank", ""))
            if rank is not None and rank > 0:
                current_best = best_ranks[source_type]
                best_ranks[source_type] = rank if current_best is None else min(current_best, rank)

        if _is_true(row.get("seller_leader", "")):
            summary["seller_evidence_leader"] = "true"
            active_families.add("seller")
        if _is_true(row.get("seller_mover", "")):
            summary["seller_evidence_mover"] = "true"
            active_families.add("seller")
        if _is_true(row.get("seller_new_push", "")):
            summary["seller_evidence_new_push"] = "true"
            active_families.add("seller")

        if _is_true(row.get("category_winner", "")):
            summary["best_seller_evidence_winner"] = "true"
            active_families.add("category_best_seller")
        if _is_true(row.get("category_breakout", "")):
            summary["best_seller_evidence_breakout"] = "true"
            active_families.add("category_best_seller")
        if _is_true(row.get("category_stable", "")):
            summary["best_seller_evidence_stable"] = "true"
            active_families.add("category_best_seller")

        if _is_true(row.get("new_release_rising", "")):
            summary["new_release_evidence_rising"] = "true"
            active_families.add("category_new_release")
        if _is_true(row.get("new_release_breakout", "")):
            summary["new_release_evidence_breakout"] = "true"
            active_families.add("category_new_release")
        if _is_true(row.get("new_release_watch", "")):
            summary["new_release_evidence_watch"] = "true"
            active_families.add("category_new_release")

        sub_bsr_rank = _to_int(row.get("sub_bsr_rank", ""))
        if sub_bsr_rank is not None and sub_bsr_rank > 0:
            summary["bsr_evidence_available"] = "true"
            best_bsr = _to_int(summary["bsr_evidence_best_sub_bsr"])
            if best_bsr is None or sub_bsr_rank < best_bsr:
                summary["bsr_evidence_best_sub_bsr"] = str(sub_bsr_rank)
                summary["bsr_evidence_best_sub_bsr_category"] = _text(row.get("sub_bsr_category", ""))
        if _is_true(row.get("strong_sub_bsr", "")):
            summary["bsr_evidence_strong"] = "true"
        if _is_true(row.get("very_strong_sub_bsr", "")):
            summary["bsr_evidence_very_strong"] = "true"

    summary["seller_evidence_source_count"] = str(len(source_ids["seller"]))
    summary["best_seller_evidence_source_count"] = str(len(source_ids["category_best_seller"]))
    summary["new_release_evidence_source_count"] = str(len(source_ids["category_new_release"]))
    summary["seller_evidence_best_rank"] = _format_rank(best_ranks["seller"])
    summary["best_seller_evidence_best_rank"] = _format_rank(best_ranks["category_best_seller"])
    summary["new_release_evidence_best_rank"] = _format_rank(best_ranks["category_new_release"])
    ordered_families = [family for family in ("seller", "category_best_seller", "category_new_release") if family in active_families]
    summary["evidence_source_family_count"] = str(len(ordered_families))
    summary["evidence_source_families"] = "; ".join(ordered_families)
    return summary


def _empty_product_summary() -> dict[str, str]:
    return {
        "seller_evidence_leader": "false",
        "seller_evidence_mover": "false",
        "seller_evidence_new_push": "false",
        "seller_evidence_best_rank": "",
        "seller_evidence_source_count": "0",
        "best_seller_evidence_winner": "false",
        "best_seller_evidence_breakout": "false",
        "best_seller_evidence_stable": "false",
        "best_seller_evidence_best_rank": "",
        "best_seller_evidence_source_count": "0",
        "new_release_evidence_rising": "false",
        "new_release_evidence_breakout": "false",
        "new_release_evidence_watch": "false",
        "new_release_evidence_best_rank": "",
        "new_release_evidence_source_count": "0",
        "bsr_evidence_available": "false",
        "bsr_evidence_strong": "false",
        "bsr_evidence_very_strong": "false",
        "bsr_evidence_best_sub_bsr": "",
        "bsr_evidence_best_sub_bsr_category": "",
        "evidence_source_family_count": "0",
        "evidence_source_families": "",
    }


def _mark(
    row: dict[str, str],
    labels: list[str],
    reasons: list[str],
    field: str,
    label: str,
    reason: str,
) -> None:
    row[field] = "true"
    labels.append(label)
    reasons.append(reason)


def _product_key(row: dict[str, str]) -> tuple[str, str]:
    marketplace = _text(row.get("marketplace", "")) or "amazon.com"
    asin = _text(row.get("asin", "")).upper()
    return marketplace, asin


def _source_identity(row: dict[str, str]) -> str:
    return (
        _text(row.get("source_id", ""))
        or _text(row.get("source_name", ""))
        or f"{_text(row.get('source_type', 'unknown'))}:{_text(row.get('category_name', ''))}"
    )


def _category_context(row: dict[str, str], label: str) -> str:
    return label


def _category_suffix(row: dict[str, str]) -> str:
    category = _text(row.get("category_name", "")) or _text(row.get("category", ""))
    return f" in {category}" if category else ""


def _format_rank(value: int | None) -> str:
    return str(value) if value is not None else ""


def _to_int(value: object) -> int | None:
    text = str(value or "").replace(",", "").replace("#", "").strip()
    if not text:
        return None
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return None


def _is_true(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _text(value: object) -> str:
    return normalize_space(str(value or ""))


def _normalized_product_text(row: dict[str, str]) -> str:
    return _text(
        " ".join(
            [
                row.get("title", ""),
                row.get("category", ""),
                row.get("category_name", ""),
                row.get("sub_bsr_category", ""),
                row.get("source_name", ""),
                row.get("seller_name", ""),
                row.get("pod_type", ""),
                row.get("pod_reason", ""),
            ]
        )
    ).lower().replace("-", " ")


def _matched_terms(text: str, terms: list[str]) -> list[str]:
    matches: list[str] = []
    for term in terms:
        normalized = _text(term).lower().replace("-", " ")
        if normalized and normalized in text and normalized not in matches:
            matches.append(normalized)
    return matches
