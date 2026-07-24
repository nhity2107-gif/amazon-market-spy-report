from __future__ import annotations

import csv
from collections import defaultdict
from collections.abc import Iterable
from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import mean, median
from urllib.parse import parse_qs, urlparse

from .category_rank import (
    CATEGORY_RANK_FIELDS,
    category_rank_cache_from_rows,
    ensure_category_rank_fields,
    merge_category_rank_fields,
)
from .evidence import (
    EVIDENCE_FIELDS,
    PRODUCT_EVIDENCE_FIELDS,
    apply_observation_evidence,
    apply_product_evidence,
)
from .models import Source
from .niche import NICHE_FIELDS, ensure_niche_fields, niche_group, niche_tags
from .pod import ensure_pod_fields, pod_allowed
from .product_details import DETAIL_DEBUG_FIELDS, ensure_detail_fix_fields
from .source_identity import (
    SOURCE_HISTORY_FIELDS,
    SOURCE_IDENTITY_FIELDS,
    normalize_source_identity,
    parse_source_rank,
    source_history_key,
)
from .utils import ensure_parent, is_asin


SourceMetadata = dict[tuple[str, str, str], dict[str, str]]

SCORE_COMPONENT_FIELDS = [
    "pod_component",
    "momentum_component",
    "market_component",
    "competition_component",
    "niche_component",
]

DISPLAY_RANK_FIELDS = [
    "products_in_source",
    "previous_display_rank",
    "display_rank_change",
    "display_rank_pct_change",
    "display_rank_velocity",
    "display_percentile",
]

RANK_AUDIT_FIELDS = [
    "asin",
    "title",
    "product_url",
    "display_rank",
    "source_name",
    "primary_bsr_rank",
    "primary_bsr_category",
    "sub_bsr_rank",
    "sub_bsr_category",
    "category_ranks_raw",
    "raw_bsr_block",
    "rank_extracted_at",
    "rank_parse_method",
    "rank_parse_confidence",
    "rank_parse_warning",
    "accordion_found",
    "accordion_expanded",
    "bsr_visible_after_expand",
]

HOLIDAY_RELEVANCE_TERMS = [
    "father's day",
    "fathers day",
    "mother's day",
    "mothers day",
    "birthday",
    "christmas",
    "halloween",
    "thanksgiving",
    "valentine",
    "easter",
    "4th of july",
    "fourth of july",
    "independence day",
    "graduation",
    "wedding",
    "anniversary",
    "baptism",
    "christening",
    "memorial",
    "retirement",
]

GIFTING_RELEVANCE_TERMS = [
    "gift",
    "gift for",
    "dad",
    "father",
    "mom",
    "mother",
    "teacher",
    "nurse",
    "doctor",
    "coach",
    "boss",
    "coworker",
    "grandma",
    "grandpa",
    "husband",
    "wife",
    "dog mom",
    "dog dad",
    "cat mom",
    "cat dad",
]


PRODUCT_FIELDS = [
    "date",
    "fetched_at",
    "source_name",
    "source_type",
    *SOURCE_IDENTITY_FIELDS,
    *SOURCE_HISTORY_FIELDS,
    "seller_name",
    "seller_id",
    "seller_url",
    "page_type",
    "category",
    "priority",
    "asin",
    "is_pod",
    "pod_type",
    "pod_score",
    "pod_reason",
    *EVIDENCE_FIELDS,
    *PRODUCT_EVIDENCE_FIELDS,
    *NICHE_FIELDS,
    *CATEGORY_RANK_FIELDS,
    "image_url",
    "image_source",
    "image_fixed",
    "display_rank",
    "display_order",
    *DISPLAY_RANK_FIELDS,
    "rank",
    "rank_basis",
    "position",
    "title",
    "raw_title",
    "title_source",
    "title_fixed",
    *DETAIL_DEBUG_FIELDS,
    "price",
    "price_display",
    "rating",
    "review_count",
    "review_rating",
    "bought_past_month",
    "badge",
    "sponsored",
    "product_url",
    "page_url",
]

SUMMARY_FIELDS = [
    "source_name",
    "source_type",
    "seller_name",
    "seller_id",
    "seller_url",
    "page_type",
    "category",
    "priority",
    "products_found",
    "unique_asins",
    "ranked_products",
    "best_rank",
    "worst_rank",
    "priced_products",
    "min_price",
    "median_price",
    "max_price",
    "avg_rating",
    "total_reviews",
    "sponsored_products",
    "new_asins",
    "removed_asins",
    "rank_improvements",
    "rank_declines",
    "price_changes",
]

CHANGE_FIELDS = [
    "detected_at",
    "change_type",
    "source_name",
    "source_type",
    "source_id",
    "source_rank",
    "marketplace",
    "category_id",
    "category_name",
    "page_type",
    "category",
    "asin",
    "old_rank",
    "new_rank",
    "previous_rank",
    "rank_delta",
    "rank_direction",
    "old_price",
    "new_price",
    "old_title",
    "new_title",
    "product_url",
]

RANK_TREND_FIELDS = [
    "source_name",
    "source_type",
    *SOURCE_IDENTITY_FIELDS,
    *SOURCE_HISTORY_FIELDS,
    "seller_name",
    "seller_id",
    "seller_url",
    "page_type",
    "category",
    "asin",
    "image_url",
    "image_source",
    "image_fixed",
    "title",
    "raw_title",
    "title_source",
    "title_fixed",
    *DETAIL_DEBUG_FIELDS,
    "review_count",
    "review_rating",
    "review_growth_7d",
    "review_growth_30d",
    "review_velocity_score",
    *DISPLAY_RANK_FIELDS,
    "is_pod",
    "pod_type",
    "pod_score",
    "pod_reason",
    *EVIDENCE_FIELDS,
    *PRODUCT_EVIDENCE_FIELDS,
    *NICHE_FIELDS,
    *CATEGORY_RANK_FIELDS,
    "observations",
    "days_seen",
    "missed_snapshots",
    "first_seen_at",
    "latest_seen_at",
    "first_rank",
    "latest_rank",
    "best_rank",
    "best_rank_7d",
    "avg_rank_7d",
    "appearances_7d",
    "worst_rank",
    "rank_change",
    "rank_direction",
    "rank_volatility",
    "first_price",
    "latest_price",
    "price_change",
    "product_url",
]

SOURCE_TREND_FIELDS = [
    "source_name",
    "source_type",
    "source_id",
    "marketplace",
    "category_id",
    "category_name",
    "seller_name",
    "seller_id",
    "seller_url",
    "page_type",
    "category",
    "snapshots_seen",
    "first_seen_at",
    "latest_seen_at",
    "first_products",
    "latest_products",
    "product_count_change",
    "total_unique_asins",
    "retained_asins",
    "new_since_first",
    "dropped_since_first",
    "current_best_rank",
    "current_worst_rank",
]

SELLER_INTELLIGENCE_FIELDS = [
    "seller_name",
    "seller_id",
    "seller_url",
    "source_name",
    "source_type",
    "seller",
    "products_tracked",
    "new_wins",
    "rising_products",
    "average_rank",
    "review_growth_7d",
    "review_growth_30d",
    "review_velocity_score",
    "momentum_score",
    "best_mover",
    "best_mover_rank_change",
    "average_rank_improvement",
    "seller_momentum_score",
    "pod_products",
    "pod_opportunities",
    "pod_momentum_score",
    "top_niche",
    "niche_count",
    "best_subcategory_rank",
    "best_subcategory_product",
]

NICHE_INTELLIGENCE_FIELDS = [
    "date",
    "niche",
    "niche_group",
    "products_tracked",
    "pod_products",
    "opportunities",
    "new_wins",
    "rising_products",
    "avg_opportunity_score",
    "max_opportunity_score",
    "avg_rank",
    "best_rank",
    "avg_bsr_rank",
    "best_bsr_rank",
    "best_subcategory_rank",
    "best_subcategory_product",
    "best_mover",
    "best_rank_change",
    "total_review_growth",
    "avg_review_rating",
    "top_seller",
    "top_product_asin",
    "top_product_title",
    "top_product_url",
    "top_product_image_url",
    "niche_momentum_score",
]

HISTORICAL_COMPARISON_FIELDS = [
    "date",
    "source_name",
    "source_type",
    *SOURCE_IDENTITY_FIELDS,
    "seller_name",
    "seller_id",
    "seller_url",
    "page_type",
    "category",
    "asin",
    "is_pod",
    "pod_type",
    "pod_score",
    "pod_reason",
    *EVIDENCE_FIELDS,
    *PRODUCT_EVIDENCE_FIELDS,
    *NICHE_FIELDS,
    *CATEGORY_RANK_FIELDS,
    "image_url",
    "image_source",
    "image_fixed",
    "title",
    "raw_title",
    "title_source",
    "title_fixed",
    *DETAIL_DEBUG_FIELDS,
    "review_count",
    "review_rating",
    "review_growth_7d",
    "review_growth_30d",
    "review_velocity_score",
    "today_rank",
    "previous_rank",
    "previous_latest_rank",
    *SOURCE_HISTORY_FIELDS,
    "rank_change_vs_previous_seen",
    "rank_direction_vs_previous_seen",
    "historical_best_rank",
    "best_rank_7d",
    "avg_rank_7d",
    "appearances_7d",
    "historical_worst_rank",
    "rank_change_vs_best",
    "rank_change_vs_worst",
    "historical_observations",
    "days_seen",
    "first_seen_date",
    "last_seen_before_today",
    "historical_status",
    "classification",
    "opportunity_score",
    *SCORE_COMPONENT_FIELDS,
    *DISPLAY_RANK_FIELDS,
    "today_price",
    "previous_latest_price",
    "price_change_vs_previous_seen",
    "product_url",
]

ERROR_FIELDS = ["fetched_at", "source_name", "category", "url", "error_type", "message"]
TREND_ALERT_FIELDS = HISTORICAL_COMPARISON_FIELDS
LARK_TREND_ALERT_FIELDS = [
    "date",
    "alert_type",
    "priority",
    "opportunity_score",
    *SCORE_COMPONENT_FIELDS,
    *DISPLAY_RANK_FIELDS,
    "asin",
    "is_pod",
    "pod_type",
    "pod_score",
    "pod_reason",
    *EVIDENCE_FIELDS,
    *PRODUCT_EVIDENCE_FIELDS,
    *NICHE_FIELDS,
    *CATEGORY_RANK_FIELDS,
    "image_url",
    "image_source",
    "image_fixed",
    "local_image_path",
    "review_count",
    "review_rating",
    "review_growth_7d",
    "review_growth_30d",
    "review_velocity_score",
    "title",
    "raw_title",
    "title_source",
    "title_fixed",
    *DETAIL_DEBUG_FIELDS,
    "source_name",
    "source_type",
    *SOURCE_IDENTITY_FIELDS,
    *SOURCE_HISTORY_FIELDS,
    "seller_name",
    "seller_id",
    "seller_url",
    "category",
    "today_rank",
    "previous_rank",
    "rank_change",
    "rank_direction",
    "first_seen",
    "days_seen",
    "product_url",
    "suggested_action",
    "status",
    "owner",
    "note",
]
EXECUTIVE_SUMMARY_FIELDS = ["metric", "value"]


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    ensure_parent(path)
    _preserve_existing_category_rank_fields(path, rows, fields)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _preserve_existing_category_rank_fields(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    if not rows or not path.exists() or not any(field in fields for field in CATEGORY_RANK_FIELDS):
        return
    existing_cache = category_rank_cache_from_rows(read_csv(path), require_product_page_source=True)
    if not existing_cache:
        return
    for row in rows:
        asin = (row.get("asin", "") or "").strip().upper()
        if not asin:
            continue
        existing = existing_cache.get(asin)
        if existing:
            merge_category_rank_fields(row, existing)


def build_source_metadata(sources: Iterable[Source] | None) -> SourceMetadata:
    metadata: SourceMetadata = {}
    for source in sources or []:
        seller_url = source.seller_url or (source.url if _is_seller_source_type(source.source_type) else "")
        seller_id = source.seller_id or _seller_id_from_url(seller_url)
        seller_name = (source.seller_name or source.source_name or seller_id).strip() if _is_seller_source_type(source.source_type) else ""
        display_name = seller_name or source.source_name or seller_id
        entry = {
            "seller_name": seller_name,
            "seller_url": seller_url,
            "seller_id": seller_id,
            "source_name": display_name,
            "original_source_name": source.source_name,
            "source_type": source.source_type,
            "category": source.category,
            "url": source.url,
            "seller_url": seller_url,
            "seller_id": seller_id,
        }
        classified = normalize_source_identity(dict(entry))
        entry.update(
            {
                "source_type": source.source_type,
                "canonical_source_type": classified.get("source_type", ""),
                "source_id": classified.get("source_id", ""),
                "marketplace": classified.get("marketplace", ""),
                "category_id": classified.get("category_id", ""),
                "category_name": classified.get("category_name", ""),
            }
        )
        source_type_candidates = {source.source_type, entry.get("canonical_source_type", "")}
        for source_name in {source.source_name, display_name, seller_name}:
            if source_name:
                for source_type in source_type_candidates:
                    if source_type:
                        metadata[_metadata_key(source_name, source_type, source.category)] = entry
    return metadata


def previous_snapshot(snapshot_dir: Path, current: Path) -> Path | None:
    snapshots = [path for path in snapshot_paths(snapshot_dir) if path != current]
    return snapshots[-1] if snapshots else None


def snapshot_paths(snapshot_dir: Path) -> list[Path]:
    if not snapshot_dir.exists():
        return []
    paths = {path for path in snapshot_dir.glob("*_snapshot.csv") if path.name != "master_snapshot.csv"}
    paths.update(snapshot_dir.glob("market_spy_*.csv"))
    return sorted(paths)


def build_master_snapshot(snapshot_dir: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in snapshot_paths(snapshot_dir):
        rows.extend(
            normalize_source_identity(
                ensure_detail_fix_fields(ensure_niche_fields(ensure_category_rank_fields(ensure_pod_fields(row))))
            )
            for row in _valid_product_rows(read_csv(path))
        )
    return rows


def normalize_source_identity_rows(
    rows: list[dict[str, str]],
    source_metadata: SourceMetadata | Iterable[Source] | None = None,
) -> list[dict[str, str]]:
    metadata = _coerce_source_metadata(source_metadata)
    for row in rows:
        _normalize_source_row(row, metadata)
    return rows


def _normalize_source_row(row: dict[str, str], metadata: SourceMetadata) -> dict[str, str]:
    source_meta = _source_metadata_for_row(row, metadata)
    normalize_source_identity(row, source_meta)
    return row


def _source_identity_values(row: dict[str, str]) -> dict[str, str]:
    return {field: row.get(field, "") for field in SOURCE_IDENTITY_FIELDS}


def _source_history_values(
    *,
    previous_rank: int | None,
    rank_change: int | None,
    observation_count: int,
    days_seen: int,
) -> dict[str, str]:
    return {
        "previous_source_rank": str(previous_rank) if previous_rank is not None else "",
        "source_rank_change": str(rank_change) if rank_change is not None else "",
        "source_observation_count": str(observation_count),
        "source_days_seen": str(days_seen),
    }


def _canonical_history_key(row: dict[str, str], metadata: SourceMetadata) -> tuple[str, str, str, str]:
    _normalize_source_row(row, metadata)
    return source_history_key(row)


def _source_instance_key(row: dict[str, str], metadata: SourceMetadata) -> tuple[str, str, str]:
    _normalize_source_row(row, metadata)
    return (row.get("marketplace", ""), row.get("source_type", ""), row.get("source_id", ""))


def _consolidate_snapshot_rows(
    rows: list[dict[str, str]],
    metadata: SourceMetadata,
) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str, str, str], list[tuple[int, dict[str, str]]]] = defaultdict(list)
    for index, source_row in enumerate(rows):
        row = ensure_detail_fix_fields(ensure_niche_fields(ensure_category_rank_fields(ensure_pod_fields(source_row))))
        if not _valid_asin(row):
            continue
        _normalize_source_row(row, metadata)
        grouped[source_history_key(row)].append((index, row))

    consolidated: list[tuple[int, dict[str, str]]] = []
    for group_rows in grouped.values():
        selected_index, selected = min(group_rows, key=lambda item: _duplicate_sort_key(item[0], item[1]))
        selected["source_duplicate_count"] = str(len(group_rows))
        consolidated.append((selected_index, selected))
    return [row for _, row in sorted(consolidated, key=lambda item: item[0])]


def _duplicate_sort_key(index: int, row: dict[str, str]) -> tuple[int, int, int]:
    rank = _rank(row)
    if rank is None:
        return (1, 10**9, index)
    return (0, rank, index)


def compare_snapshots(previous: list[dict[str, str]], current: list[dict[str, str]], detected_at: str) -> list[dict[str, str]]:
    metadata: SourceMetadata = {}
    old = {source_history_key(row): row for row in _consolidate_snapshot_rows(previous, metadata)}
    new = {source_history_key(row): row for row in _consolidate_snapshot_rows(current, metadata)}
    changes: list[dict[str, str]] = []

    for key in sorted(new.keys() - old.keys()):
        changes.append(_change_row("new_asin", detected_at, None, new[key]))

    for key in sorted(old.keys() - new.keys()):
        changes.append(_change_row("removed_asin", detected_at, old[key], None))

    for key in sorted(old.keys() & new.keys()):
        old_row = old[key]
        new_row = new[key]
        if _rank_changed(old_row, new_row):
            changes.append(_change_row("rank_changed", detected_at, old_row, new_row))
        if _price_changed(old_row.get("price", ""), new_row.get("price", "")):
            changes.append(_change_row("price_changed", detected_at, old_row, new_row))
        if _meaningful_title(old_row.get("title", "")) and _meaningful_title(new_row.get("title", "")):
            if old_row.get("title") != new_row.get("title"):
                changes.append(_change_row("title_changed", detected_at, old_row, new_row))

    return changes


def summarize_sources(products: list[dict[str, str]], changes: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for product in _valid_product_rows(products):
        grouped[_source_key(product)].append(product)

    change_counts: dict[tuple[tuple[str, str, str], str], int] = defaultdict(int)
    rank_directions: dict[tuple[tuple[str, str, str], str], int] = defaultdict(int)
    for change in changes:
        source_key = _source_key(change)
        change_counts[(source_key, change["change_type"])] += 1
        if change["change_type"] == "rank_changed":
            rank_directions[(source_key, change.get("rank_direction", ""))] += 1

    summaries: list[dict[str, str]] = []
    for source_key, rows in sorted(grouped.items()):
        prices = [_to_float(row.get("price", "")) for row in rows]
        prices = [price for price in prices if price is not None]
        ratings = [_review_rating(row) for row in rows]
        ratings = [rating for rating in ratings if rating is not None]
        reviews = [_to_int(row.get("review_count", "")) or 0 for row in rows]
        ranks = [_rank(row) for row in rows]
        ranks = [rank for rank in ranks if rank is not None]
        first = rows[0]

        summaries.append(
            {
                "source_name": first.get("source_name", ""),
                "source_type": _source_type(first),
                "seller_name": first.get("seller_name", ""),
                "seller_id": first.get("seller_id", ""),
                "seller_url": first.get("seller_url", ""),
                "page_type": _page_type(first),
                "category": first.get("category", ""),
                "priority": first.get("priority", ""),
                "products_found": str(len(rows)),
                "unique_asins": str(len({_normalized_asin(row) for row in rows if _valid_asin(row)})),
                "ranked_products": str(len(ranks)),
                "best_rank": str(min(ranks)) if ranks else "",
                "worst_rank": str(max(ranks)) if ranks else "",
                "priced_products": str(len(prices)),
                "min_price": _format_float(min(prices) if prices else None),
                "median_price": _format_float(median(prices) if prices else None),
                "max_price": _format_float(max(prices) if prices else None),
                "avg_rating": _format_float(mean(ratings) if ratings else None),
                "total_reviews": str(sum(reviews)),
                "sponsored_products": str(sum(1 for row in rows if row.get("sponsored") == "yes")),
                "new_asins": str(change_counts[(source_key, "new_asin")]),
                "removed_asins": str(change_counts[(source_key, "removed_asin")]),
                "rank_improvements": str(rank_directions[(source_key, "up")]),
                "rank_declines": str(rank_directions[(source_key, "down")]),
                "price_changes": str(change_counts[(source_key, "price_changed")]),
            }
        )
    return summaries


def build_rank_trends(
    snapshot_dir: Path,
    source_metadata: SourceMetadata | Iterable[Source] | None = None,
) -> list[dict[str, str]]:
    paths = snapshot_paths(snapshot_dir)
    metadata = _coerce_source_metadata(source_metadata)
    rows_by_key: dict[tuple[str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for path in paths:
        for row in _consolidate_snapshot_rows(read_csv(path), metadata):
            key = source_history_key(row)
            rows_by_key[key].append(row)

    trends: list[dict[str, str]] = []
    total_snapshots = len(paths)
    for key, rows in sorted(rows_by_key.items()):
        first = rows[0]
        latest = rows[-1]
        first_rank = _rank(first)
        latest_rank = _rank(latest)
        ranks = [_rank(row) for row in rows]
        ranks = [rank for rank in ranks if rank is not None]
        rank_change = _rank_delta_values(first_rank, latest_rank) if len(ranks) >= 2 else None
        previous_source_rank = first_rank if len(ranks) >= 2 else None
        first_price = _to_float(first.get("price", ""))
        latest_price = _to_float(latest.get("price", ""))
        days_seen = len({_row_date(row) for row in rows if _row_date(row)})
        best_rank_7d = _best_rank_in_window(rows, _row_snapshot_date(latest), days=7)
        avg_rank_7d = _avg_rank_in_window(rows, _row_snapshot_date(latest), days=7)
        appearances_7d = _appearances_in_window(rows, _row_snapshot_date(latest), days=7)
        review_count = _review_count(latest)
        review_rating = _review_rating(latest)
        review_growth_7d = _review_growth_in_window(rows, _row_snapshot_date(latest), days=7)
        review_growth_30d = _review_growth_in_window(rows, _row_snapshot_date(latest), days=30)
        review_velocity_score = _review_velocity_score(review_growth_7d, review_growth_30d)
        source_meta = _source_metadata_for_row(latest, metadata)
        seller_fields = _seller_fields(latest, source_meta)
        pod_fields = ensure_pod_fields(latest)
        niche_fields = ensure_niche_fields(latest)
        category_rank_fields = ensure_category_rank_fields(latest)
        detail_fields = ensure_detail_fix_fields(latest)

        trends.append(
            {
                "source_name": _display_source_name(latest, source_meta),
                "source_type": _source_type(latest),
                **_source_identity_values(latest),
                **_source_history_values(
                    previous_rank=previous_source_rank,
                    rank_change=rank_change,
                    observation_count=len(rows),
                    days_seen=days_seen,
                ),
                "seller_name": seller_fields["seller_name"],
                "seller_id": seller_fields["seller_id"],
                "seller_url": seller_fields["seller_url"],
                "page_type": _page_type(latest),
                "category": latest.get("category", ""),
                "asin": _normalized_asin(latest),
                "title": latest.get("title", "") or first.get("title", ""),
                "image_url": latest.get("image_url", "") or first.get("image_url", ""),
                "image_source": detail_fields.get("image_source", ""),
                "image_fixed": detail_fields.get("image_fixed", ""),
                "raw_title": detail_fields.get("raw_title", ""),
                "title_source": detail_fields.get("title_source", ""),
                "title_fixed": detail_fields.get("title_fixed", ""),
                **{field: detail_fields.get(field, "") for field in DETAIL_DEBUG_FIELDS},
                "review_count": _format_int(review_count),
                "review_rating": _format_rating(review_rating),
                "review_growth_7d": str(review_growth_7d),
                "review_growth_30d": str(review_growth_30d),
                "review_velocity_score": str(review_velocity_score),
                "is_pod": pod_fields.get("is_pod", ""),
                "pod_type": pod_fields.get("pod_type", ""),
                "pod_score": pod_fields.get("pod_score", ""),
                "pod_reason": pod_fields.get("pod_reason", ""),
                "niche_primary": niche_fields.get("niche_primary", ""),
                "niche_secondary": niche_fields.get("niche_secondary", ""),
                "niche_tags": niche_fields.get("niche_tags", ""),
                "niche_score": niche_fields.get("niche_score", ""),
                "niche_reason": niche_fields.get("niche_reason", ""),
                **{field: category_rank_fields.get(field, "") for field in CATEGORY_RANK_FIELDS},
                "observations": str(len(rows)),
                "days_seen": str(days_seen),
                "missed_snapshots": str(max(0, total_snapshots - len(rows))),
                "first_seen_at": first.get("fetched_at", ""),
                "latest_seen_at": latest.get("fetched_at", ""),
                "first_rank": str(first_rank) if first_rank is not None else "",
                "latest_rank": str(latest_rank) if latest_rank is not None else "",
                "best_rank": str(min(ranks)) if ranks else "",
                "best_rank_7d": str(best_rank_7d) if best_rank_7d is not None else "",
                "avg_rank_7d": _format_float(avg_rank_7d),
                "appearances_7d": str(appearances_7d),
                "worst_rank": str(max(ranks)) if ranks else "",
                "rank_change": str(rank_change) if rank_change is not None else "",
                "rank_direction": _rank_direction(rank_change),
                "rank_volatility": str(max(ranks) - min(ranks)) if ranks else "",
                "first_price": _format_float(first_price),
                "latest_price": _format_float(latest_price),
                "price_change": _format_float(_price_delta(first_price, latest_price)),
                "product_url": _product_url(latest) or _product_url(first),
            }
        )
    apply_product_evidence(trends)
    return trends


def build_product_history_rows(
    snapshot_dir: Path,
    source_metadata: SourceMetadata | Iterable[Source] | None = None,
) -> list[dict[str, str]]:
    metadata = _coerce_source_metadata(source_metadata)
    rows: list[dict[str, str]] = []
    for path in snapshot_paths(snapshot_dir):
        for row in _consolidate_snapshot_rows(read_csv(path), metadata):
            source_meta = _source_metadata_for_row(row, metadata)
            seller_fields = _seller_fields(row, source_meta)
            rows.append(
                {
                    "date": _row_date(row),
                    "fetched_at": row.get("fetched_at", ""),
                    "source_name": _display_source_name(row, source_meta),
                    "source_type": _source_type(row),
                    **_source_identity_values(row),
                    "seller_name": seller_fields["seller_name"],
                    "seller_id": seller_fields["seller_id"],
                    "seller_url": seller_fields["seller_url"],
                    "page_type": _page_type(row),
                    "category": row.get("category", ""),
                    "asin": _normalized_asin(row),
                    "title": row.get("title", ""),
                    "raw_title": row.get("raw_title", ""),
                    "image_url": row.get("image_url", ""),
                    "display_rank": row.get("display_rank", "") or row.get("display_order", "") or row.get("rank", "") or row.get("position", ""),
                    "display_order": row.get("display_order", ""),
                    "rank": row.get("rank", ""),
                    "position": row.get("position", ""),
                    "previous_display_rank": row.get("previous_display_rank", ""),
                    "display_rank_change": row.get("display_rank_change", ""),
                    "review_count": row.get("review_count", ""),
                    "review_rating": row.get("review_rating", "") or row.get("rating", ""),
                    "product_url": _product_url(row),
                    **{field: row.get(field, "") for field in CATEGORY_RANK_FIELDS},
                    **{field: row.get(field, "") for field in NICHE_FIELDS},
                    "is_pod": row.get("is_pod", ""),
                    "pod_type": row.get("pod_type", ""),
                    "pod_score": row.get("pod_score", ""),
                    "pod_reason": row.get("pod_reason", ""),
                }
            )
    apply_product_evidence(rows)
    return rows


def build_source_trends(
    snapshot_dir: Path,
    source_metadata: SourceMetadata | Iterable[Source] | None = None,
) -> list[dict[str, str]]:
    paths = snapshot_paths(snapshot_dir)
    metadata = _coerce_source_metadata(source_metadata)
    grouped: dict[tuple[str, str, str], list[tuple[str, list[dict[str, str]]]]] = defaultdict(list)

    for path in paths:
        rows_by_source: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
        for row in read_csv(path):
            if _valid_asin(row):
                _normalize_source_row(row, metadata)
                rows_by_source[_source_instance_key(row, metadata)].append(row)
        for source_key, rows in rows_by_source.items():
            grouped[source_key].append((path.name, rows))

    trends: list[dict[str, str]] = []
    for source_key, snapshots in sorted(grouped.items()):
        first_name, first_rows = snapshots[0]
        latest_name, latest_rows = snapshots[-1]
        first_asins = {_normalized_asin(row) for row in first_rows if _valid_asin(row)}
        latest_asins = {_normalized_asin(row) for row in latest_rows if _valid_asin(row)}
        all_asins = set(first_asins)
        for _, rows in snapshots[1:]:
            all_asins.update(_normalized_asin(row) for row in rows if _valid_asin(row))
        latest_ranks = [_rank(row) for row in latest_rows]
        latest_ranks = [rank for rank in latest_ranks if rank is not None]
        latest = latest_rows[0]
        _normalize_source_row(latest, metadata)
        source_meta = _source_metadata_for_row(latest, metadata)
        seller_fields = _seller_fields(latest, source_meta)

        trends.append(
            {
                "source_name": _display_source_name(latest, source_meta),
                "source_type": _source_type(latest),
                "source_id": latest.get("source_id", ""),
                "marketplace": latest.get("marketplace", ""),
                "category_id": latest.get("category_id", ""),
                "category_name": latest.get("category_name", ""),
                "seller_name": seller_fields["seller_name"],
                "seller_id": seller_fields["seller_id"],
                "seller_url": seller_fields["seller_url"],
                "page_type": _page_type(latest),
                "category": latest.get("category", ""),
                "snapshots_seen": str(len(snapshots)),
                "first_seen_at": first_rows[0].get("fetched_at", first_name) if first_rows else first_name,
                "latest_seen_at": latest_rows[0].get("fetched_at", latest_name) if latest_rows else latest_name,
                "first_products": str(len(first_rows)),
                "latest_products": str(len(latest_rows)),
                "product_count_change": str(len(latest_rows) - len(first_rows)),
                "total_unique_asins": str(len(all_asins)),
                "retained_asins": str(len(first_asins & latest_asins)),
                "new_since_first": str(len(latest_asins - first_asins)),
                "dropped_since_first": str(len(first_asins - latest_asins)),
                "current_best_rank": str(min(latest_ranks)) if latest_ranks else "",
                "current_worst_rank": str(max(latest_ranks)) if latest_ranks else "",
            }
        )
    return trends


def build_historical_comparison(
    snapshot_dir: Path,
    today_snapshot_path: Path | None = None,
    source_metadata: SourceMetadata | Iterable[Source] | None = None,
) -> list[dict[str, str]]:
    paths = snapshot_paths(snapshot_dir)
    if not paths:
        return []
    metadata = _coerce_source_metadata(source_metadata)

    today_path = today_snapshot_path if today_snapshot_path is not None else paths[-1]
    today_rows = _consolidate_snapshot_rows(read_csv(today_path), metadata)
    today_source_counts: dict[tuple[str, str, str], int] = defaultdict(int)
    for row in today_rows:
        if _valid_asin(row):
            today_source_counts[_source_instance_key(row, metadata)] += 1
    try:
        today_index = paths.index(today_path)
    except ValueError:
        today_index = len(paths)
    history_paths = paths[:today_index]
    history_by_key: dict[tuple[str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for path in history_paths:
        for row in _consolidate_snapshot_rows(read_csv(path), metadata):
            key = source_history_key(row)
            history_by_key[key].append(row)

    comparisons: list[dict[str, str]] = []
    for today in today_rows:
        ensure_detail_fix_fields(ensure_niche_fields(ensure_pod_fields(today)))
        if not _valid_asin(today):
            continue
        key = source_history_key(today)
        history = history_by_key.get(key, [])
        latest_previous = history[-1] if history else None
        history_ranks = [_rank(row) for row in history]
        history_ranks = [rank for rank in history_ranks if rank is not None]
        today_rank = _rank(today)
        today_date = _row_snapshot_date(today)
        previous_rank = _rank(latest_previous or {})
        rank_change_previous = _rank_delta_values(previous_rank, today_rank)
        best_rank = min(history_ranks) if history_ranks else None
        worst_rank = max(history_ranks) if history_ranks else None
        today_price = _to_float(today.get("price", ""))
        previous_price = _to_float((latest_previous or {}).get("price", ""))
        all_rows = history + [today]
        days_seen = len({_row_date(row) for row in all_rows if _row_date(row)})
        best_rank_7d = _best_rank_in_window(all_rows, _row_snapshot_date(today), days=7)
        avg_rank_7d = _avg_rank_in_window(all_rows, _row_snapshot_date(today), days=7)
        appearances_7d = _appearances_in_window(all_rows, _row_snapshot_date(today), days=7)
        review_count = _review_count(today)
        review_rating = _review_rating(today)
        review_growth_7d = _review_growth_in_window(all_rows, _row_snapshot_date(today), days=7)
        review_growth_30d = _review_growth_in_window(all_rows, _row_snapshot_date(today), days=30)
        review_velocity_score = _review_velocity_score(review_growth_7d, review_growth_30d)
        first_seen_date = _row_snapshot_date(history[0]) if history else today_date
        source_type = _source_type(today)
        page_type = _page_type(today)
        source_meta = _source_metadata_for_row(today, metadata)
        seller_fields = _seller_fields(today, source_meta)
        pod_fields = ensure_pod_fields(today)
        niche_fields = ensure_niche_fields(today)
        category_rank_fields = ensure_category_rank_fields(today)
        detail_fields = ensure_detail_fix_fields(today)
        display_rank_fields = _display_rank_fields(
            today,
            latest_previous,
            today_source_counts.get(_source_instance_key(today, metadata), 0),
        )
        classification = _classification(
            first_seen_date=first_seen_date,
            current_date=today_date,
            current_rank=today_rank,
            days_seen=days_seen,
            rank_change_previous=rank_change_previous,
        )
        score_breakdown = _opportunity_score_breakdown(
            pod_score=_to_int(pod_fields.get("pod_score", "")) or 0,
            classification=classification,
            days_seen=days_seen,
            rank_change_previous=rank_change_previous,
            category_rank=_to_int(category_rank_fields.get("primary_bsr_rank", "") or category_rank_fields.get("bsr_rank", "")),
            subcategory_rank=_to_int(category_rank_fields.get("sub_bsr_rank", "")),
            subcategory_rank_score=_to_int(category_rank_fields.get("subcategory_rank_score", "")) or 0,
            review_count=review_count,
            review_growth_7d=review_growth_7d,
            review_growth_30d=review_growth_30d,
            review_rating=review_rating,
            niche_score=_to_int(niche_fields.get("niche_score", "")) or 0,
            title=today.get("title", ""),
            category=today.get("category", ""),
            source_name=_display_source_name(today, source_meta),
            niche_primary=niche_fields.get("niche_primary", ""),
            niche_tags=niche_fields.get("niche_tags", ""),
            pod_reason=pod_fields.get("pod_reason", ""),
            display_rank_change=_to_int(display_rank_fields.get("display_rank_change", "")),
            display_percentile=_to_float(display_rank_fields.get("display_percentile", "")),
        )

        comparisons.append(
            {
                "date": today.get("date", today.get("fetched_at", "")[:10]),
                "source_name": _display_source_name(today, source_meta),
                "source_type": source_type,
                **_source_identity_values(today),
                "seller_name": seller_fields["seller_name"],
                "seller_id": seller_fields["seller_id"],
                "seller_url": seller_fields["seller_url"],
                "page_type": page_type,
                "category": today.get("category", ""),
                "asin": _normalized_asin(today),
                "is_pod": pod_fields.get("is_pod", ""),
                "pod_type": pod_fields.get("pod_type", ""),
                "pod_score": pod_fields.get("pod_score", ""),
                "pod_reason": pod_fields.get("pod_reason", ""),
                "niche_primary": niche_fields.get("niche_primary", ""),
                "niche_secondary": niche_fields.get("niche_secondary", ""),
                "niche_tags": niche_fields.get("niche_tags", ""),
                "niche_score": niche_fields.get("niche_score", ""),
                "niche_reason": niche_fields.get("niche_reason", ""),
                **{field: category_rank_fields.get(field, "") for field in CATEGORY_RANK_FIELDS},
                "title": today.get("title", ""),
                "image_url": today.get("image_url", ""),
                "image_source": detail_fields.get("image_source", ""),
                "image_fixed": detail_fields.get("image_fixed", ""),
                "raw_title": detail_fields.get("raw_title", ""),
                "title_source": detail_fields.get("title_source", ""),
                "title_fixed": detail_fields.get("title_fixed", ""),
                **{field: detail_fields.get(field, "") for field in DETAIL_DEBUG_FIELDS},
                **display_rank_fields,
                "review_count": _format_int(review_count),
                "review_rating": _format_rating(review_rating),
                "review_growth_7d": str(review_growth_7d),
                "review_growth_30d": str(review_growth_30d),
                "review_velocity_score": str(review_velocity_score),
                "today_rank": str(today_rank) if today_rank is not None else "",
                "previous_rank": str(previous_rank) if previous_rank is not None else "",
                "previous_latest_rank": str(previous_rank) if previous_rank is not None else "",
                **_source_history_values(
                    previous_rank=previous_rank,
                    rank_change=rank_change_previous,
                    observation_count=len(all_rows),
                    days_seen=days_seen,
                ),
                "rank_change_vs_previous_seen": str(rank_change_previous) if rank_change_previous is not None else "",
                "rank_direction_vs_previous_seen": _rank_direction(rank_change_previous),
                "historical_best_rank": str(best_rank) if best_rank is not None else "",
                "best_rank_7d": str(best_rank_7d) if best_rank_7d is not None else "",
                "avg_rank_7d": _format_float(avg_rank_7d),
                "appearances_7d": str(appearances_7d),
                "historical_worst_rank": str(worst_rank) if worst_rank is not None else "",
                "rank_change_vs_best": _format_int(_rank_delta_values(best_rank, today_rank)),
                "rank_change_vs_worst": _format_int(_rank_delta_values(worst_rank, today_rank)),
                "historical_observations": str(len(history)),
                "days_seen": str(days_seen),
                "first_seen_date": _row_date(history[0]) if history else _row_date(today),
                "last_seen_before_today": _row_date(latest_previous) if latest_previous else "",
                "historical_status": _historical_status(history, rank_change_previous),
                "classification": classification,
                "opportunity_score": score_breakdown["opportunity_score"],
                **{field: score_breakdown[field] for field in SCORE_COMPONENT_FIELDS},
                "today_price": _format_float(today_price),
                "previous_latest_price": _format_float(previous_price),
                "price_change_vs_previous_seen": _format_float(_price_delta(previous_price, today_price)),
                "product_url": _product_url(today),
            }
        )
    apply_product_evidence(comparisons)
    return comparisons


def build_trend_alerts(historical_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    alerts = [
        ensure_detail_fix_fields(ensure_category_rank_fields(ensure_niche_fields(ensure_pod_fields(row))))
        for row in historical_rows
        if _valid_asin(row) and row.get("classification", "").strip()
    ]
    return sorted(alerts, key=lambda row: _to_int(row.get("opportunity_score", "")) or 0, reverse=True)


def build_lark_trend_alerts(
    historical_rows: list[dict[str, str]],
    limit: int = 100,
    source_metadata: SourceMetadata | Iterable[Source] | None = None,
    include_non_pod: bool = False,
) -> list[dict[str, str]]:
    metadata = _coerce_source_metadata(source_metadata)
    apply_product_evidence(historical_rows)
    rows = []
    for row in historical_rows:
        ensure_detail_fix_fields(ensure_category_rank_fields(ensure_niche_fields(ensure_pod_fields(row))))
        _normalize_source_row(row, metadata)
        apply_observation_evidence(row)
        if not _valid_asin(row):
            continue
        if not include_non_pod and not pod_allowed(row):
            continue
        asin = _normalized_asin(row)
        labels = _classification_labels(row.get("classification", ""))
        if "declining" in labels:
            continue
        opportunity_score = _to_int(row.get("opportunity_score", "")) or 0
        if not (labels.intersection({"new_win", "rising", "winner"}) or opportunity_score >= 60):
            continue
        alert_type = _lark_alert_type(labels)
        source_type = row.get("source_type", "")
        source_meta = _source_metadata_for_row(row, metadata)
        seller_fields = _seller_fields(row, source_meta)
        category_rank_fields = ensure_category_rank_fields(row)
        detail_fields = ensure_detail_fix_fields(row)
        rows.append(
            {
                "date": row.get("date", ""),
                "alert_type": alert_type,
                "priority": _lark_priority(opportunity_score),
                "opportunity_score": str(opportunity_score),
                **{field: row.get(field, "") for field in SCORE_COMPONENT_FIELDS},
                **{field: row.get(field, "") for field in DISPLAY_RANK_FIELDS},
                "asin": asin,
                "is_pod": row.get("is_pod", ""),
                "pod_type": row.get("pod_type", ""),
                "pod_score": row.get("pod_score", ""),
                "pod_reason": row.get("pod_reason", ""),
                **{field: row.get(field, "") for field in EVIDENCE_FIELDS},
                **{field: row.get(field, "") for field in PRODUCT_EVIDENCE_FIELDS},
                "niche_primary": row.get("niche_primary", ""),
                "niche_secondary": row.get("niche_secondary", ""),
                "niche_tags": row.get("niche_tags", ""),
                "niche_score": row.get("niche_score", ""),
                "niche_reason": row.get("niche_reason", ""),
                **{field: category_rank_fields.get(field, "") for field in CATEGORY_RANK_FIELDS},
                "image_url": row.get("image_url", ""),
                "image_source": detail_fields.get("image_source", ""),
                "image_fixed": detail_fields.get("image_fixed", ""),
                "local_image_path": row.get("local_image_path", ""),
                "review_count": row.get("review_count", ""),
                "review_rating": row.get("review_rating", ""),
                "review_growth_7d": row.get("review_growth_7d", ""),
                "review_growth_30d": row.get("review_growth_30d", ""),
                "review_velocity_score": row.get("review_velocity_score", ""),
                "title": row.get("title", ""),
                "raw_title": detail_fields.get("raw_title", ""),
                "title_source": detail_fields.get("title_source", ""),
                "title_fixed": detail_fields.get("title_fixed", ""),
                **{field: detail_fields.get(field, "") for field in DETAIL_DEBUG_FIELDS},
                "source_name": _display_source_name(row, source_meta),
                "source_type": source_type,
                **{field: row.get(field, "") for field in SOURCE_IDENTITY_FIELDS},
                **{field: row.get(field, "") for field in SOURCE_HISTORY_FIELDS},
                "seller_name": seller_fields["seller_name"],
                "seller_id": seller_fields["seller_id"],
                "seller_url": seller_fields["seller_url"],
                "category": row.get("category", ""),
                "today_rank": row.get("today_rank", ""),
                "previous_rank": row.get("previous_rank", ""),
                "rank_change": row.get("rank_change_vs_previous_seen", ""),
                "rank_direction": row.get("rank_direction_vs_previous_seen", ""),
                "first_seen": row.get("first_seen_date", ""),
                "days_seen": row.get("days_seen", ""),
                "product_url": _product_url(row),
                "suggested_action": _lark_suggested_action(alert_type),
                "status": "New",
                "owner": "",
                "note": "",
            }
        )
    rows.sort(
        key=lambda row: (
            -(_to_int(row.get("opportunity_score", "")) or 0),
            _to_int(row.get("today_rank", "")) or 10**9,
        )
    )
    unique_rows = []
    seen_asins: set[str] = set()
    for row in rows:
        asin = row.get("asin", "")
        if asin in seen_asins:
            continue
        seen_asins.add(asin)
        unique_rows.append(row)
    return unique_rows[:limit]


def build_seller_intelligence(
    historical_rows: list[dict[str, str]],
    source_metadata: SourceMetadata | Iterable[Source] | None = None,
) -> list[dict[str, str]]:
    metadata = _coerce_source_metadata(source_metadata)
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in historical_rows:
        ensure_detail_fix_fields(ensure_category_rank_fields(ensure_niche_fields(ensure_pod_fields(row))))
        if not _valid_asin(row):
            continue
        source_meta = _source_metadata_for_row(row, metadata)
        seller_name = _seller_display_name(row, source_meta).strip()
        seller_id = source_meta.get("seller_id", "") or row.get("seller_id", "")
        if not seller_name:
            continue
        grouped[(seller_name, seller_id, _source_type(row))].append(row)

    seller_rows = []
    for (seller_name, seller_id, source_type), rows in grouped.items():
        asins = {_normalized_asin(row) for row in rows if _valid_asin(row)}
        pod_rows = [row for row in rows if pod_allowed(row)]
        pod_asins = {_normalized_asin(row) for row in pod_rows if _valid_asin(row)}
        labels = [_classification_labels(row.get("classification", "")) for row in rows]
        ranks = [_to_int(row.get("today_rank", "")) for row in rows]
        ranks = [rank for rank in ranks if rank is not None]
        improvements = [_to_int(row.get("rank_change_vs_previous_seen", "")) for row in rows]
        improvements = [value for value in improvements if value is not None and value > 0]
        display_improvements = [_display_rank_change_value(row) for row in rows]
        display_improvements = [value for value in display_improvements if value is not None and value > 0]
        opportunity_scores = [_to_int(row.get("opportunity_score", "")) or 0 for row in rows]
        review_growth_7d = sum(_to_int(row.get("review_growth_7d", "")) or 0 for row in rows)
        review_growth_30d = sum(_to_int(row.get("review_growth_30d", "")) or 0 for row in rows)
        review_velocity_score = sum(_to_int(row.get("review_velocity_score", "")) or 0 for row in rows)
        new_wins = sum(1 for item in labels if "new_win" in item)
        rising_products = sum(1 for item in labels if "rising" in item)
        best_mover_row = _best_mover_row(rows)
        momentum_score = (
            sum(opportunity_scores)
            + sum(improvements)
            + (new_wins * 20)
            + (rising_products * 10)
            + review_velocity_score
        )
        pod_opportunities = [row for row in pod_rows if _is_opportunity_row(row)]
        pod_momentum_score = _seller_momentum_score(pod_rows)
        niche_counts: dict[str, int] = defaultdict(int)
        for row in pod_rows or rows:
            for niche in niche_tags(row):
                if niche != "Unknown":
                    niche_counts[niche] += 1
        top_niche = ""
        if niche_counts:
            top_niche = sorted(niche_counts.items(), key=lambda item: (-item[1], item[0]))[0][0]
        best_subcategory = _best_subcategory_row(pod_rows or rows)
        average_rank_improvement = _format_float(mean(display_improvements) if display_improvements else None)
        seller_momentum_score = (
            sum(opportunity_scores)
            + min(100, sum(display_improvements))
            + (new_wins * 15)
            + (rising_products * 8)
            + review_velocity_score
            + min(20, len(display_improvements) * 2)
        )
        first = rows[0]
        source_meta = _source_metadata_for_row(first, metadata)
        seller_fields = _seller_fields(first, source_meta)
        seller_rows.append(
            {
                "seller_name": seller_fields["seller_name"] or seller_name,
                "seller_id": seller_fields["seller_id"] or seller_id,
                "seller_url": seller_fields["seller_url"],
                "source_name": _display_source_name(first, source_meta),
                "source_type": source_type,
                "seller": seller_fields["seller_name"] or seller_name,
                "products_tracked": str(len(asins)),
                "new_wins": str(new_wins),
                "rising_products": str(rising_products),
                "average_rank": _format_float(mean(ranks) if ranks else None),
                "review_growth_7d": str(review_growth_7d),
                "review_growth_30d": str(review_growth_30d),
                "review_velocity_score": str(review_velocity_score),
                "momentum_score": str(momentum_score),
                "best_mover": (best_mover_row or {}).get("title", ""),
                "best_mover_rank_change": (
                    str(_display_rank_change_value(best_mover_row)) if best_mover_row and _display_rank_change_value(best_mover_row) is not None else ""
                ),
                "average_rank_improvement": average_rank_improvement,
                "seller_momentum_score": str(seller_momentum_score),
                "pod_products": str(len(pod_asins)),
                "pod_opportunities": str(len(pod_opportunities)),
                "pod_momentum_score": str(pod_momentum_score),
                "top_niche": top_niche,
                "niche_count": str(len(niche_counts)),
                "best_subcategory_rank": (
                    best_subcategory.get("sub_bsr_rank", "") if best_subcategory else ""
                ),
                "best_subcategory_product": (best_subcategory or {}).get("title", ""),
            }
        )
    return sorted(seller_rows, key=lambda row: row.get("seller_name", "").lower())


def build_niche_intelligence(
    historical_rows: list[dict[str, str]],
    include_non_pod: bool = False,
) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in historical_rows:
        ensure_detail_fix_fields(ensure_category_rank_fields(ensure_niche_fields(ensure_pod_fields(row))))
        if not _valid_asin(row):
            continue
        if not include_non_pod and not pod_allowed(row):
            continue
        for niche in niche_tags(row):
            grouped[niche].append(row)

    rows: list[dict[str, str]] = []
    for niche, niche_rows in grouped.items():
        unique_rows = _unique_rows_by_asin(niche_rows)
        pod_rows = [row for row in unique_rows if pod_allowed(row)]
        opportunity_rows = [row for row in unique_rows if _is_opportunity_row(row)]
        labels = [_classification_labels(row.get("classification", "")) for row in unique_rows]
        new_wins = sum(1 for item in labels if "new_win" in item)
        rising_products = sum(1 for item in labels if "rising" in item)
        opportunity_scores = [_to_int(row.get("opportunity_score", "")) or 0 for row in unique_rows]
        display_improvements = [_display_rank_change_value(row) for row in unique_rows]
        display_improvements = [value for value in display_improvements if value is not None and value > 0]
        ranks = [_to_int(row.get("today_rank", "") or row.get("rank", "")) for row in unique_rows]
        ranks = [rank for rank in ranks if rank is not None]
        bsr_ranks = [_to_int(row.get("primary_bsr_rank", "") or row.get("bsr_rank", "")) for row in unique_rows]
        bsr_ranks = [rank for rank in bsr_ranks if rank is not None]
        best_subcategory = _best_subcategory_row(unique_rows)
        review_growth = [_review_growth_value(row) for row in unique_rows]
        review_ratings = [_review_rating(row) for row in unique_rows]
        review_ratings = [rating for rating in review_ratings if rating is not None]
        top_product = _top_niche_product(unique_rows)
        top_seller = _top_niche_seller(unique_rows)
        best_mover_row = _best_mover_row(unique_rows)
        best_rank_change = _display_rank_change_value(best_mover_row)
        momentum_score = _niche_momentum_score(
            unique_rows,
            opportunity_rows,
            new_wins,
            rising_products,
            display_improvements,
        )
        rows.append(
            {
                "date": _row_date(unique_rows[0]) if unique_rows else "",
                "niche": niche,
                "niche_group": niche_group(niche),
                "products_tracked": str(len(unique_rows)),
                "pod_products": str(len(pod_rows)),
                "opportunities": str(len(opportunity_rows)),
                "new_wins": str(new_wins),
                "rising_products": str(rising_products),
                "avg_opportunity_score": _format_float(mean(opportunity_scores) if opportunity_scores else None),
                "max_opportunity_score": str(max(opportunity_scores)) if opportunity_scores else "",
                "avg_rank": _format_float(mean(ranks) if ranks else None),
                "best_rank": str(min(ranks)) if ranks else "",
                "avg_bsr_rank": _format_float(mean(bsr_ranks) if bsr_ranks else None),
                "best_bsr_rank": str(min(bsr_ranks)) if bsr_ranks else "",
                "best_subcategory_rank": (
                    best_subcategory.get("sub_bsr_rank", "") if best_subcategory else ""
                ),
                "best_subcategory_product": (best_subcategory or {}).get("title", ""),
                "best_mover": (best_mover_row or {}).get("title", ""),
                "best_rank_change": str(best_rank_change) if best_rank_change is not None else "",
                "total_review_growth": str(sum(review_growth)),
                "avg_review_rating": _format_rating(mean(review_ratings) if review_ratings else None),
                "top_seller": top_seller,
                "top_product_asin": _normalized_asin(top_product) if top_product else "",
                "top_product_title": (top_product or {}).get("title", ""),
                "top_product_url": _product_url(top_product or {}),
                "top_product_image_url": (top_product or {}).get("image_url", ""),
                "niche_momentum_score": str(momentum_score),
            }
        )
    return sorted(rows, key=lambda row: _to_int(row.get("niche_momentum_score", "")) or 0, reverse=True)


def _unique_rows_by_asin(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    unique_rows = []
    seen_asins: set[str] = set()
    for row in rows:
        asin = _normalized_asin(row)
        if asin in seen_asins:
            continue
        seen_asins.add(asin)
        unique_rows.append(row)
    return unique_rows


def _top_niche_product(rows: list[dict[str, str]]) -> dict[str, str] | None:
    if not rows:
        return None
    return sorted(
        rows,
        key=lambda row: (
            -(_to_int(row.get("opportunity_score", "")) or 0),
            _to_int(row.get("today_rank", "") or row.get("rank", "")) or 10**9,
            _to_int(row.get("sub_bsr_rank", "")) or 10**9,
            _to_int(row.get("primary_bsr_rank", "") or row.get("bsr_rank", "")) or 10**9,
        ),
    )[0]


def _best_subcategory_row(rows: list[dict[str, str]]) -> dict[str, str] | None:
    ranked_rows = [
        row
        for row in rows
        if _to_int(row.get("sub_bsr_rank", "")) is not None
    ]
    if not ranked_rows:
        return None
    return sorted(
        ranked_rows,
        key=lambda row: (
            _to_int(row.get("sub_bsr_rank", "")) or 10**9,
            -(_to_int(row.get("opportunity_score", "")) or 0),
            _to_int(row.get("today_rank", "") or row.get("rank", "")) or 10**9,
        ),
    )[0]


def _top_niche_seller(rows: list[dict[str, str]]) -> str:
    seller_scores: dict[str, int] = defaultdict(int)
    for row in rows:
        seller = row.get("seller_name", "") or row.get("source_name", "") or row.get("seller_id", "")
        if not seller:
            continue
        seller_scores[seller] += (_to_int(row.get("opportunity_score", "")) or 0) + 1
    if not seller_scores:
        return ""
    return sorted(seller_scores.items(), key=lambda item: (-item[1], item[0]))[0][0]


def _niche_momentum_score(
    rows: list[dict[str, str]],
    opportunity_rows: list[dict[str, str]],
    new_wins: int,
    rising_products: int,
    display_improvements: list[int],
) -> int:
    opportunity_scores = [_to_int(row.get("opportunity_score", "")) or 0 for row in rows]
    improvements = [_to_int(row.get("rank_change_vs_previous_seen", "") or row.get("rank_change", "")) or 0 for row in rows]
    improvements = [value for value in improvements if value > 0]
    total_review_growth = sum(_review_growth_value(row) for row in rows)
    avg_opportunity_score = mean(opportunity_scores) if opportunity_scores else 0
    source_strength = sum(_source_strength(row) for row in rows)
    score = (
        min(25, len(opportunity_rows) * 5)
        + min(20, new_wins * 10)
        + min(15, rising_products * 5)
        + min(15, sum(improvements))
        + min(20, sum(display_improvements))
        + min(10, total_review_growth)
        + min(10, int(avg_opportunity_score / 10))
        + min(5, source_strength)
    )
    return max(0, min(100, int(score)))


def _review_growth_value(row: dict[str, str]) -> int:
    return (
        _to_int(row.get("review_growth_7d", ""))
        or _to_int(row.get("review_growth_30d", ""))
        or _to_int(row.get("review_growth", ""))
        or 0
    )


def _source_strength(row: dict[str, str]) -> int:
    source_type = _source_type(row).strip().lower().replace("-", "_")
    if source_type == "best_seller":
        return 2
    if source_type == "new_release":
        return 2
    if source_type in {"movers_shakers", "movers_and_shakers"}:
        return 1
    return 1


def _display_rank_change_value(row: dict[str, str] | None) -> int | None:
    if not row:
        return None
    return _to_int(row.get("display_rank_change", ""))


def _best_mover_row(rows: list[dict[str, str]]) -> dict[str, str] | None:
    movers = [row for row in rows if _display_rank_change_value(row) is not None]
    if not movers:
        return None
    return sorted(
        movers,
        key=lambda row: (
            -max(0, _display_rank_change_value(row) or 0),
            -(_to_int(row.get("opportunity_score", "")) or 0),
            _to_int(row.get("display_rank", "") or row.get("rank", "") or row.get("position", "")) or 10**9,
        ),
    )[0]


def _seller_momentum_score(rows: list[dict[str, str]]) -> int:
    labels = [_classification_labels(row.get("classification", "")) for row in rows]
    improvements = [_to_int(row.get("rank_change_vs_previous_seen", "")) for row in rows]
    improvements = [value for value in improvements if value is not None and value > 0]
    display_improvements = [_display_rank_change_value(row) for row in rows]
    display_improvements = [value for value in display_improvements if value is not None and value > 0]
    opportunity_scores = [_to_int(row.get("opportunity_score", "")) or 0 for row in rows]
    review_velocity_score = sum(_to_int(row.get("review_velocity_score", "")) or 0 for row in rows)
    new_wins = sum(1 for item in labels if "new_win" in item)
    rising_products = sum(1 for item in labels if "rising" in item)
    return (
        sum(opportunity_scores)
        + sum(improvements)
        + min(100, sum(display_improvements))
        + (new_wins * 20)
        + (rising_products * 10)
        + review_velocity_score
    )


def filter_by_classification(rows: list[dict[str, str]], label: str) -> list[dict[str, str]]:
    return [row for row in rows if label in _classification_labels(row.get("classification", ""))]


def _is_opportunity_row(row: dict[str, str]) -> bool:
    labels = _classification_labels(row.get("classification", ""))
    opportunity_score = _to_int(row.get("opportunity_score", "")) or 0
    return bool(labels.intersection({"new_win", "rising", "winner"}) or opportunity_score >= 60)


def build_executive_summary(
    products: list[dict[str, str]],
    historical_rows: list[dict[str, str]],
    source_summaries: list[dict[str, str]],
    errors: list[dict[str, str]],
) -> list[dict[str, str]]:
    labels = _count_classifications(historical_rows)
    for row in products:
        ensure_pod_fields(row)
    unique_asins = {_normalized_asin(row) for row in products if _valid_asin(row)}
    pod_yes = sum(1 for row in products if row.get("is_pod", "") == "yes")
    pod_maybe = sum(1 for row in products if row.get("is_pod", "") == "maybe")
    pod_no = sum(1 for row in products if row.get("is_pod", "") == "no")
    return [
        {"metric": "total_products", "value": str(len(products))},
        {"metric": "products_found", "value": str(len(products))},
        {"metric": "unique_asins", "value": str(len(unique_asins))},
        {"metric": "pod_yes", "value": str(pod_yes)},
        {"metric": "pod_maybe", "value": str(pod_maybe)},
        {"metric": "pod_no", "value": str(pod_no)},
        {"metric": "excluded_non_pod", "value": str(pod_no)},
        {"metric": "sources_with_products", "value": str(len(source_summaries))},
        {"metric": "source_errors", "value": str(len(errors))},
        {"metric": "new_win", "value": str(labels.get("new_win", 0))},
        {"metric": "winner", "value": str(labels.get("winner", 0))},
        {"metric": "rising", "value": str(labels.get("rising", 0))},
        {"metric": "declining", "value": str(labels.get("declining", 0))},
    ]


def _key(row: dict[str, str]) -> tuple[str, ...]:
    return source_history_key(row)


def _valid_product_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [row for row in rows if _valid_asin(row)]


def _valid_asin(row: dict[str, str]) -> bool:
    return is_asin(row.get("asin", ""))


def _normalized_asin(row: dict[str, str]) -> str:
    return row.get("asin", "").strip().upper()


def _product_url(row: dict[str, str]) -> str:
    if row.get("product_url", ""):
        return row.get("product_url", "")
    asin = _normalized_asin(row)
    return f"https://www.amazon.com/dp/{asin}" if is_asin(asin) else ""


def _coerce_source_metadata(source_metadata: SourceMetadata | Iterable[Source] | None) -> SourceMetadata:
    if source_metadata is None:
        return {}
    if isinstance(source_metadata, dict):
        return source_metadata
    return build_source_metadata(source_metadata)


def _source_metadata_for_row(row: dict[str, str], metadata: SourceMetadata) -> dict[str, str]:
    source_name = row.get("source_name", "")
    source_type = _source_type(row)
    category = row.get("category", "")
    key = _metadata_key(source_name, source_type, category)
    if key in metadata:
        return metadata[key]

    source_type_key = _metadata_source_type(source_type)
    source_name_key = _metadata_text(source_name)
    for meta_key, value in metadata.items():
        if meta_key[0] == source_name_key and meta_key[1] == source_type_key:
            return value
    for meta_key, value in metadata.items():
        if meta_key[0] == source_name_key:
            return value
    return _fallback_source_metadata(row)


def _display_source_name(row: dict[str, str], source_meta: dict[str, str]) -> str:
    if _is_seller_source_type(_source_type(row)):
        return _seller_display_name(row, source_meta)
    return row.get("source_name", "") or source_meta.get("source_name", "")


def _seller_display_name(row: dict[str, str], source_meta: dict[str, str]) -> str:
    return (
        source_meta.get("seller_name", "")
        or row.get("seller_name", "")
        or row.get("source_name", "")
        or source_meta.get("seller_id", "")
        or row.get("seller_id", "")
    )


def _seller_fields(row: dict[str, str], source_meta: dict[str, str]) -> dict[str, str]:
    if not _is_seller_source_type(_source_type(row)):
        return {
            "seller_name": row.get("seller_name", ""),
            "seller_id": row.get("seller_id", ""),
            "seller_url": row.get("seller_url", ""),
        }
    return {
        "seller_name": _seller_display_name(row, source_meta),
        "seller_id": source_meta.get("seller_id", "") or row.get("seller_id", ""),
        "seller_url": source_meta.get("seller_url", "") or row.get("seller_url", ""),
    }


def _fallback_source_metadata(row: dict[str, str]) -> dict[str, str]:
    seller_url = row.get("seller_url", "") or row.get("page_url", "")
    seller_id = row.get("seller_id", "") or _seller_id_from_url(seller_url)
    return {
        "seller_name": row.get("seller_name", "") or row.get("source_name", "") or seller_id,
        "seller_url": seller_url,
        "seller_id": seller_id,
        "source_name": row.get("seller_name", "") or row.get("source_name", "") or seller_id,
        "original_source_name": row.get("source_name", ""),
        "source_type": _source_type(row),
        "category": row.get("category", ""),
    }


def _metadata_key(source_name: str, source_type: str, category: str) -> tuple[str, str, str]:
    return (_metadata_text(source_name), _metadata_source_type(source_type), _metadata_text(category))


def _metadata_text(value: str) -> str:
    return " ".join((value or "").strip().split()).lower()


def _metadata_source_type(value: str) -> str:
    return _metadata_text(value).replace("-", "_").replace(" ", "_")


def _seller_id_from_url(url: str) -> str:
    try:
        query = parse_qs(urlparse(url).query)
    except ValueError:
        return ""
    for key in ("m", "me", "seller"):
        values = query.get(key)
        if values:
            return values[0].strip()
    return ""


def _is_seller_source_type(value: str) -> bool:
    return _metadata_source_type(value) == "seller"


def _source_key(row: dict[str, str]) -> tuple[str, str, str]:
    return (row.get("source_name", ""), _source_type(row), row.get("category", ""))


def _resolved_source_key(row: dict[str, str], metadata: SourceMetadata) -> tuple[str, str, str]:
    source_meta = _source_metadata_for_row(row, metadata)
    return (_display_source_name(row, source_meta), _source_type(row), row.get("category", ""))


def _source_type(row: dict[str, str]) -> str:
    return row.get("source_type", "") or row.get("page_type", "")


def _page_type(row: dict[str, str]) -> str:
    return row.get("page_type", "") or row.get("source_type", "")


def _change_row(
    change_type: str,
    detected_at: str,
    old_row: dict[str, str] | None,
    new_row: dict[str, str] | None,
) -> dict[str, str]:
    row = new_row or old_row or {}
    old_rank = _rank(old_row or {})
    new_rank = _rank(new_row or {})
    rank_delta = _rank_delta_values(old_rank, new_rank)
    return {
        "detected_at": detected_at,
        "change_type": change_type,
        "source_name": row.get("source_name", ""),
        "source_type": _source_type(row),
        "source_id": row.get("source_id", ""),
        "source_rank": row.get("source_rank", ""),
        "marketplace": row.get("marketplace", ""),
        "category_id": row.get("category_id", ""),
        "category_name": row.get("category_name", ""),
        "page_type": _page_type(row),
        "category": row.get("category", ""),
        "asin": row.get("asin", ""),
        "old_rank": str(old_rank) if old_rank is not None else "",
        "new_rank": str(new_rank) if new_rank is not None else "",
        "previous_rank": str(old_rank) if old_rank is not None else "",
        "rank_delta": str(rank_delta) if rank_delta is not None else "",
        "rank_direction": _change_rank_direction(change_type, rank_delta),
        "old_price": (old_row or {}).get("price", ""),
        "new_price": (new_row or {}).get("price", ""),
        "old_title": (old_row or {}).get("title", ""),
        "new_title": (new_row or {}).get("title", ""),
        "product_url": row.get("product_url", ""),
    }


def _change_rank_direction(change_type: str, rank_delta: int | None) -> str:
    if change_type == "new_asin":
        return "new"
    if change_type == "removed_asin":
        return "removed"
    return _rank_direction(rank_delta)


def _rank_direction(rank_delta: int | None) -> str:
    if rank_delta is None:
        return ""
    if rank_delta > 0:
        return "up"
    if rank_delta < 0:
        return "down"
    return "flat"


def _rank_delta_values(old_rank: int | None, new_rank: int | None) -> int | None:
    if old_rank is None or new_rank is None:
        return None
    return old_rank - new_rank


def _rank_changed(old_row: dict[str, str], new_row: dict[str, str]) -> bool:
    old_rank = _rank(old_row)
    new_rank = _rank(new_row)
    return old_rank is not None and new_rank is not None and old_rank != new_rank


def _rank(row: dict[str, str]) -> int | None:
    rank, _ = parse_source_rank(row)
    return rank


def _review_count(row: dict[str, str]) -> int | None:
    return _to_int(row.get("review_count", ""))


def _review_rating(row: dict[str, str]) -> float | None:
    return _to_float(row.get("review_rating", "") or row.get("rating", ""))


def _price_changed(old_value: str, new_value: str) -> bool:
    old = _to_float(old_value)
    new = _to_float(new_value)
    if old is None and new is None:
        return False
    if old is None or new is None:
        return True
    return abs(old - new) >= 0.01


def _price_delta(first_price: float | None, latest_price: float | None) -> float | None:
    if first_price is None or latest_price is None:
        return None
    return latest_price - first_price


def _historical_status(history: list[dict[str, str]], rank_delta: int | None) -> str:
    if not history:
        return "new_vs_history"
    if rank_delta is None or rank_delta == 0:
        return "unchanged_vs_previous_seen"
    if rank_delta > 0:
        return "improved_vs_previous_seen"
    return "declined_vs_previous_seen"


def _classification(
    first_seen_date: date | None,
    current_date: date | None,
    current_rank: int | None,
    days_seen: int,
    rank_change_previous: int | None,
) -> str:
    # Legacy Winner/Rising labels kept for compatibility; source-specific evidence lives in evidence.py.
    if first_seen_date is None or current_date is None or current_rank is None:
        return ""
    labels = []
    first_seen_days = (current_date - first_seen_date).days
    rank_improvement = rank_change_previous if rank_change_previous is not None and rank_change_previous > 0 else 0
    rank_drop = abs(rank_change_previous) if rank_change_previous is not None and rank_change_previous < 0 else 0
    if 0 <= first_seen_days <= 7 and current_rank <= 20 and rank_improvement >= 10:
        labels.append("new_win")
    if rank_improvement >= 10 and current_rank <= 100:
        labels.append("rising")
    if current_rank <= 10 and days_seen >= 7:
        labels.append("winner")
    if rank_drop >= 10:
        labels.append("declining")
    return ";".join(labels)


def _opportunity_score_breakdown(
    *,
    pod_score: int,
    classification: str,
    days_seen: int,
    rank_change_previous: int | None,
    category_rank: int | None,
    subcategory_rank: int | None,
    subcategory_rank_score: int,
    review_count: int | None,
    review_growth_7d: int,
    review_growth_30d: int,
    review_rating: float | None,
    niche_score: int,
    title: str,
    category: str,
    source_name: str,
    niche_primary: str,
    niche_tags: str,
    pod_reason: str,
    display_rank_change: int | None,
    display_percentile: float | None,
) -> dict[str, str]:
    labels = _classification_labels(classification)
    components = {
        "pod_component": _weighted_component(_pod_strength_score(pod_score), 30),
        "momentum_component": _weighted_component(
            _momentum_strength_score(rank_change_previous, labels, days_seen, display_rank_change, display_percentile),
            25,
        ),
        "market_component": _weighted_component(
            _market_strength_score(category_rank, subcategory_rank, subcategory_rank_score),
            20,
        ),
        "competition_component": _weighted_component(
            _competition_strength_score(review_count, review_growth_7d, review_growth_30d, review_rating),
            10,
        ),
        "niche_component": _weighted_component(
            _niche_strength_score(
                niche_score=niche_score,
                title=title,
                category=category,
                source_name=source_name,
                niche_primary=niche_primary,
                niche_tags=niche_tags,
                pod_reason=pod_reason,
            ),
            15,
        ),
    }
    components["opportunity_score"] = str(min(100, sum(int(value) for value in components.values())))
    return components


def _weighted_component(raw_score: int, max_points: int) -> str:
    raw = max(0, min(100, raw_score))
    return str(max(0, min(max_points, int(round(raw * max_points / 100)))))


def _pod_strength_score(pod_score: int) -> int:
    return max(0, min(100, pod_score))


def _momentum_strength_score(
    rank_change_previous: int | None,
    labels: set[str],
    days_seen: int,
    display_rank_change: int | None,
    display_percentile: float | None,
) -> int:
    rank_improvement = rank_change_previous if rank_change_previous is not None and rank_change_previous > 0 else 0
    score = min(40, rank_improvement * 2)
    if "new_win" in labels:
        score += 30
    if "rising" in labels:
        score += 25
    if days_seen <= 3:
        score += 20
    elif days_seen <= 7:
        score += 15
    elif days_seen <= 14:
        score += 8
    elif days_seen <= 30:
        score += 4
    score += _display_rank_momentum_bonus(display_rank_change, display_percentile)
    return min(100, score)


def _display_rank_momentum_bonus(display_rank_change: int | None, display_percentile: float | None) -> int:
    bonus = 0
    if display_rank_change is not None:
        if display_rank_change >= 25:
            bonus += 40
        elif display_rank_change >= 15:
            bonus += 30
        elif display_rank_change >= 8:
            bonus += 20
        elif display_rank_change >= 3:
            bonus += 10
        elif display_rank_change > 0:
            bonus += 5

    if display_percentile is not None:
        if display_percentile <= 5:
            bonus += 15
        elif display_percentile <= 10:
            bonus += 10
        elif display_percentile <= 20:
            bonus += 5
    return bonus


def _display_rank_fields(
    today: dict[str, str],
    previous: dict[str, str] | None,
    products_in_source: int,
) -> dict[str, str]:
    current_display_rank = _display_rank_number(today)
    previous_display_rank = _display_rank_number(previous or {})
    previous_date = _row_snapshot_date(previous or {}) if previous else None
    today_date = _row_snapshot_date(today)
    display_rank_change = (
        previous_display_rank - current_display_rank
        if previous_display_rank is not None and current_display_rank is not None
        else None
    )
    pct_change = (
        (display_rank_change / previous_display_rank) * 100
        if display_rank_change is not None and previous_display_rank not in (None, 0)
        else None
    )
    days_between = (
        max(1, (today_date - previous_date).days)
        if today_date is not None and previous_date is not None
        else None
    )
    velocity = (
        display_rank_change / days_between
        if display_rank_change is not None and days_between
        else None
    )
    percentile = (
        (current_display_rank / products_in_source) * 100
        if current_display_rank is not None and products_in_source > 0
        else None
    )
    return {
        "products_in_source": str(products_in_source) if products_in_source > 0 else "",
        "previous_display_rank": str(previous_display_rank) if previous_display_rank is not None else "",
        "display_rank_change": str(display_rank_change) if display_rank_change is not None else "",
        "display_rank_pct_change": _format_float(pct_change),
        "display_rank_velocity": _format_float(velocity),
        "display_percentile": _format_float(percentile),
    }


def _display_rank_number(row: dict[str, str]) -> int | None:
    rank, _ = parse_source_rank(row)
    return rank


def _market_strength_score(category_rank: int | None, subcategory_rank: int | None, subcategory_rank_score: int) -> int:
    sub_score = subcategory_rank_score or _rank_strength_score(subcategory_rank)
    category_score = _rank_strength_score(category_rank)
    if sub_score and category_score:
        return int(round((sub_score * 0.65) + (category_score * 0.35)))
    return sub_score or category_score


def _rank_strength_score(rank: int | None) -> int:
    if rank is None or rank <= 0:
        return 0
    if rank <= 100:
        return 100
    if rank <= 500:
        return 92
    if rank <= 1_000:
        return 86
    if rank <= 5_000:
        return 78
    if rank <= 10_000:
        return 70
    if rank <= 50_000:
        return 58
    if rank <= 200_000:
        return 42
    if rank <= 500_000:
        return 25
    return 10


def _competition_strength_score(
    review_count: int | None,
    review_growth_7d: int,
    review_growth_30d: int,
    review_rating: float | None,
) -> int:
    score = _review_count_opportunity_score(review_count)
    growth = max(0, review_growth_7d, review_growth_30d)
    if review_growth_7d >= 20 or review_growth_30d >= 50:
        score += 35
    elif review_growth_7d >= 10 or review_growth_30d >= 25:
        score += 28
    elif review_growth_7d >= 5 or review_growth_30d >= 10:
        score += 20
    elif growth > 0:
        score += 10

    if review_rating is not None:
        if review_rating >= 4.6:
            score += 25
        elif review_rating >= 4.3:
            score += 20
        elif review_rating >= 4.0:
            score += 12
        elif review_rating > 0:
            score += 5
    return min(100, score)


def _review_count_opportunity_score(review_count: int | None) -> int:
    if review_count is None:
        return 0
    if review_count <= 25:
        return 40
    if review_count <= 100:
        return 35
    if review_count <= 300:
        return 28
    if review_count <= 1_000:
        return 18
    if review_count <= 3_000:
        return 10
    return 4


def _niche_strength_score(
    *,
    niche_score: int,
    title: str,
    category: str,
    source_name: str,
    niche_primary: str,
    niche_tags: str,
    pod_reason: str,
) -> int:
    text = " ".join([title, category, source_name, niche_primary, niche_tags, pod_reason]).lower()
    score = min(45, max(0, niche_score))
    if _contains_any(text, HOLIDAY_RELEVANCE_TERMS) or niche_group(niche_primary) == "occasion":
        score += 35
    if _contains_any(text, GIFTING_RELEVANCE_TERMS) or niche_group(niche_primary) in {"family", "profession", "pet"}:
        score += 25
    return min(100, score)


def _contains_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def _lark_alert_type(labels: set[str]) -> str:
    if "new_win" in labels:
        return "new_win"
    if "winner" in labels:
        return "winner"
    if "rising" in labels:
        return "rising"
    return "opportunity"


def _lark_priority(opportunity_score: int) -> str:
    if opportunity_score >= 80:
        return "High"
    if opportunity_score >= 60:
        return "Medium"
    return "Low"


def _lark_suggested_action(alert_type: str) -> str:
    if alert_type == "new_win":
        return "Research immediately"
    if alert_type == "winner":
        return "Deep-dive competitor listing"
    if alert_type == "rising":
        return "Watch 2-3 days"
    return "Review manually"


def _classification_labels(value: str) -> set[str]:
    return {item.strip() for item in value.split(";") if item.strip()}


def _count_classifications(rows: list[dict[str, str]]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        if not _valid_asin(row):
            continue
        for label in _classification_labels(row.get("classification", "")):
            counts[label] += 1
    return counts


def _row_date(row: dict[str, str] | None) -> str:
    if not row:
        return ""
    return row.get("date", "") or row.get("fetched_at", "")[:10]


def _row_snapshot_date(row: dict[str, str] | None) -> date | None:
    return _parse_date(_row_date(row))


def _best_rank_in_window(rows: list[dict[str, str]], end_date: date | None, days: int) -> int | None:
    ranks = _ranks_in_window(rows, end_date, days)
    return min(ranks) if ranks else None


def _avg_rank_in_window(rows: list[dict[str, str]], end_date: date | None, days: int) -> float | None:
    ranks = _ranks_in_window(rows, end_date, days)
    return mean(ranks) if ranks else None


def _appearances_in_window(rows: list[dict[str, str]], end_date: date | None, days: int) -> int:
    return len({_row_date(row) for row in _rows_in_window(rows, end_date, days) if _row_date(row)})


def _review_growth_in_window(rows: list[dict[str, str]], end_date: date | None, days: int) -> int:
    dated_counts = []
    for row in _rows_in_window(rows, end_date, days):
        count = _review_count(row)
        row_date = _row_snapshot_date(row)
        if count is None or row_date is None:
            continue
        dated_counts.append((row_date, count))
    if len(dated_counts) < 2:
        return 0
    dated_counts.sort(key=lambda item: item[0])
    return max(0, dated_counts[-1][1] - dated_counts[0][1])


def _review_velocity_score(review_growth_7d: int, review_growth_30d: int) -> int:
    if review_growth_7d >= 20 or review_growth_30d >= 50:
        return 20
    if review_growth_7d >= 10 or review_growth_30d >= 25:
        return 15
    if review_growth_7d >= 5 or review_growth_30d >= 10:
        return 10
    if review_growth_7d > 0 or review_growth_30d > 0:
        return 5
    return 0


def _ranks_in_window(rows: list[dict[str, str]], end_date: date | None, days: int) -> list[int]:
    ranks = []
    for row in _rows_in_window(rows, end_date, days):
        rank = _rank(row)
        if rank is not None:
            ranks.append(rank)
    return ranks


def _rows_in_window(rows: list[dict[str, str]], end_date: date | None, days: int) -> list[dict[str, str]]:
    if end_date is None:
        dated_rows = [(row, _row_snapshot_date(row)) for row in rows]
        dates = [row_date for _, row_date in dated_rows if row_date is not None]
        end_date = max(dates) if dates else None
    if end_date is None:
        return []

    start_date = end_date - timedelta(days=max(1, days) - 1)
    window_rows = []
    for row in rows:
        row_date = _row_snapshot_date(row)
        if row_date is None or row_date < start_date or row_date > end_date:
            continue
        window_rows.append(row)
    return window_rows


def _parse_date(value: str) -> date | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _meaningful_title(value: str) -> bool:
    return len(value.strip()) >= 10


def _to_float(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: str) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _format_float(value: float | None) -> str:
    return f"{value:.2f}" if value is not None else ""


def _format_rating(value: float | None) -> str:
    return f"{value:.1f}" if value is not None else ""


def _format_int(value: int | None) -> str:
    return str(value) if value is not None else ""
