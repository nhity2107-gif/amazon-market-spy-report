from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from html import escape
from itertools import combinations, product
from pathlib import Path
from statistics import mean, median
from typing import Callable, Iterable

from .reporting import read_csv, write_csv


SIGNAL_NAMES = [
    "seller_leader",
    "seller_mover",
    "seller_new_push",
    "category_winner",
    "category_breakout",
    "category_stable",
    "new_release_rising",
    "new_release_breakout",
    "new_release_watch",
    "strong_sub_bsr",
    "very_strong_sub_bsr",
]

SIGNAL_LABELS = {
    "seller_leader": "Seller Leader",
    "seller_mover": "Seller Mover",
    "seller_new_push": "Seller New Push",
    "category_winner": "Category Winner",
    "category_breakout": "Category Breakout",
    "category_stable": "Category Stable",
    "new_release_rising": "New Release Rising",
    "new_release_breakout": "New Release Breakout",
    "new_release_watch": "New Release Candidate",
    "strong_sub_bsr": "Strong Sub-BSR",
    "very_strong_sub_bsr": "Very Strong Sub-BSR",
}

SIGNAL_FAMILY = {
    "seller_leader": "seller",
    "seller_mover": "seller",
    "seller_new_push": "seller",
    "category_winner": "category_best_seller",
    "category_breakout": "category_best_seller",
    "category_stable": "category_best_seller",
    "new_release_rising": "category_new_release",
    "new_release_breakout": "category_new_release",
    "new_release_watch": "category_new_release",
    "strong_sub_bsr": "bsr",
    "very_strong_sub_bsr": "bsr",
}

REVIEW_SAMPLE_TARGETS = {
    "seller_leader": 50,
    "seller_mover": 50,
    "seller_new_push": 50,
    "category_winner": 50,
    "category_breakout": 50,
    "category_stable": None,
    "new_release_rising": 50,
    "new_release_breakout": None,
    "new_release_watch": 75,
    "strong_sub_bsr": 75,
    "very_strong_sub_bsr": 75,
}

SUMMARY_FIELDS = [
    "signal",
    "signal_label",
    "source_family",
    "total_product_count",
    "eligible_product_count",
    "active_signal_count",
    "signal_rate_eligible",
    "signal_rate_all",
    "no_data_count",
    "false_count",
    "true_count",
    "source_rank_count",
    "source_rank_missing",
    "source_rank_min",
    "source_rank_p10",
    "source_rank_p25",
    "source_rank_mean",
    "source_rank_median",
    "source_rank_p75",
    "source_rank_p90",
    "source_rank_max",
    "previous_source_rank_median",
    "source_rank_change_median",
    "source_days_seen_median",
    "source_observation_count_median",
    "price_median",
    "rating_median",
    "review_count_median",
    "primary_bsr_median",
    "sub_bsr_median",
    "pod_relevance_distribution",
    "product_type_distribution",
    "seller_distribution",
    "category_distribution",
    "sub_bsr_category_distribution",
    "marketplace_distribution",
    "concentration_notes",
]

THRESHOLD_FIELDS = [
    "simulation_signal",
    "thresholds",
    "matching_product_count",
    "eligible_product_count",
    "eligible_coverage_rate",
    "median_reviews",
    "median_price",
    "median_source_rank",
    "median_rank_improvement",
    "pod_relevance_distribution",
    "product_type_distribution",
    "bsr_available_count",
    "median_sub_bsr",
]

OVERLAP_FIELDS = [
    "signal_a",
    "signal_b",
    "source_family_a",
    "source_family_b",
    "intersection_count",
    "union_count",
    "jaccard_similarity",
    "overlap_rate_a",
    "overlap_rate_b",
]

REVIEW_FIELDS = [
    "sample_signal",
    "sample_bucket",
    "marketplace",
    "asin",
    "title",
    "seller",
    "product_type",
    "pod_relevance",
    "review_count",
    "review_rating",
    "price",
    "source_family",
    "source_name",
    "source_id",
    "source_rank",
    "previous_source_rank",
    "source_rank_change",
    "source_days_seen",
    "source_observation_count",
    "category",
    "sub_bsr_rank",
    "sub_bsr_category",
    "primary_bsr_rank",
    "primary_bsr_category",
    "all_evidence_labels",
    "evidence_reasons",
    "product_url",
    "image_url",
    "review_label",
    "pod_validity",
    "idea_quality",
    "duplicability",
    "market_relevance",
    "research_priority",
    "review_notes",
    "reviewer",
    "reviewed_at",
]


@dataclass(frozen=True)
class ProductGroup:
    key: tuple[str, str]
    rows: list[dict[str, str]]

    @property
    def marketplace(self) -> str:
        return self.key[0]

    @property
    def asin(self) -> str:
        return self.key[1]


def calibrate_evidence(output_dir: Path, comparison_path: Path | None = None) -> dict[str, object]:
    output_dir = Path(output_dir)
    comparison_path = Path(comparison_path) if comparison_path else output_dir / "historical_comparison.csv"
    rows = read_csv(comparison_path)
    groups = group_products(rows)

    summary_rows = build_signal_summary(groups)
    threshold_rows = build_threshold_simulation(groups)
    overlap_rows = build_overlap_matrix(groups)
    review_rows = build_review_sample(groups)
    signal_distribution = signal_count_distribution(groups)

    paths = {
        "summary": output_dir / "evidence_calibration_summary.csv",
        "threshold_simulation": output_dir / "evidence_threshold_simulation.csv",
        "overlap_matrix": output_dir / "evidence_overlap_matrix.csv",
        "review": output_dir / "evidence_calibration_review.csv",
        "html": output_dir / "evidence_calibration.html",
    }
    write_csv(paths["summary"], summary_rows, SUMMARY_FIELDS)
    write_csv(paths["threshold_simulation"], threshold_rows, THRESHOLD_FIELDS)
    write_csv(paths["overlap_matrix"], overlap_rows, OVERLAP_FIELDS)
    write_csv(paths["review"], review_rows, REVIEW_FIELDS)
    paths["html"].write_text(
        render_calibration_html(summary_rows, threshold_rows, overlap_rows, review_rows, signal_distribution),
        encoding="utf-8",
    )

    return {
        "comparison_path": str(comparison_path),
        "product_count": len(groups),
        "observation_count": len(rows),
        "signal_counts": {row["signal"]: row["active_signal_count"] for row in summary_rows},
        "signal_distribution": dict(signal_distribution),
        "paths": {key: str(path) for key, path in paths.items()},
    }


def group_products(rows: list[dict[str, str]]) -> dict[tuple[str, str], ProductGroup]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        asin = normalize_text(row.get("asin", "")).upper()
        if not asin:
            continue
        marketplace = normalize_text(row.get("marketplace", "")) or "amazon.com"
        grouped[(marketplace, asin)].append(row)
    return {key: ProductGroup(key, value) for key, value in grouped.items()}


def build_signal_summary(groups: dict[tuple[str, str], ProductGroup]) -> list[dict[str, str]]:
    total_products = len(groups)
    rows: list[dict[str, str]] = []
    for signal in SIGNAL_NAMES:
        eligible = [group for group in groups.values() if is_product_eligible(group, signal)]
        active = [group for group in eligible if product_has_signal(group, signal)]
        active_observations = [row for group in active for row in group.rows if truthy(row.get(signal, ""))]
        if not active_observations:
            active_observations = [representative_row(group) for group in active]
        eligible_count = len(eligible)
        active_count = len(active)
        no_data_count = total_products - eligible_count
        false_count = eligible_count - active_count
        distribution = distribution_fields(active_observations)
        categorical = categorical_fields(active_observations, active_count)
        row = {
            "signal": signal,
            "signal_label": SIGNAL_LABELS[signal],
            "source_family": SIGNAL_FAMILY[signal],
            "total_product_count": str(total_products),
            "eligible_product_count": str(eligible_count),
            "active_signal_count": str(active_count),
            "signal_rate_eligible": format_rate(active_count, eligible_count),
            "signal_rate_all": format_rate(active_count, total_products),
            "no_data_count": str(no_data_count),
            "false_count": str(false_count),
            "true_count": str(active_count),
            **distribution,
            **categorical,
        }
        row["concentration_notes"] = concentration_notes(row)
        rows.append(row)
    return rows


def build_threshold_simulation(groups: dict[tuple[str, str], ProductGroup]) -> list[dict[str, str]]:
    simulations: list[tuple[str, str, Callable[[dict[str, str]], bool], Callable[[ProductGroup], bool]]] = []
    for rank, days in product([5, 10, 20], [3, 7, 14]):
        simulations.append((
            "seller_leader",
            f"source_rank<={rank};source_days_seen>={days}",
            lambda row, rank=rank, days=days: source_type(row) == "seller" and rank_value(row) is not None and rank_value(row) <= rank and int_value(row.get("source_days_seen")) is not None and int_value(row.get("source_days_seen")) >= days,
            lambda group: has_source_family(group, "seller"),
        ))
    for improvement, rank in product([5, 10, 15, 20, 30], [20, 50, 100]):
        simulations.append((
            "seller_mover",
            f"source_rank_change>={improvement};source_rank<={rank};previous_source_rank=present;source_observation_count>=2",
            lambda row, improvement=improvement, rank=rank: source_type(row) == "seller"
            and int_value(row.get("previous_source_rank")) is not None
            and int_value(row.get("source_rank_change")) is not None
            and int_value(row.get("source_rank_change")) >= improvement
            and rank_value(row) is not None
            and rank_value(row) <= rank
            and (int_value(row.get("source_observation_count")) or 0) >= 2,
            lambda group: has_source_family(group, "seller"),
        ))
    for days, rank in product([3, 5, 7], [10, 20, 30]):
        simulations.append((
            "seller_new_push",
            f"source_days_seen<={days};source_rank<={rank}",
            lambda row, days=days, rank=rank: source_type(row) == "seller" and int_value(row.get("source_days_seen")) is not None and int_value(row.get("source_days_seen")) <= days and rank_value(row) is not None and rank_value(row) <= rank,
            lambda group: has_source_family(group, "seller"),
        ))
    for rank, days, pod_mode in product([10, 20, 30, 50], [3, 7, 14], ["high_only", "high_medium", "not_low"]):
        simulations.append((
            "category_winner",
            f"source_rank<={rank};source_days_seen>={days};pod_relevance={pod_mode}",
            lambda row, rank=rank, days=days, pod_mode=pod_mode: source_type(row) == "category_best_seller" and pod_allowed(row, pod_mode) and rank_value(row) is not None and rank_value(row) <= rank and int_value(row.get("source_days_seen")) is not None and int_value(row.get("source_days_seen")) >= days,
            lambda group: has_source_family(group, "category_best_seller"),
        ))
    for improvement, rank in product([10, 15, 20, 30], [20, 30, 50]):
        simulations.append((
            "category_breakout",
            f"source_rank_change>={improvement};source_rank<={rank};pod_relevance=not_low;previous_source_rank=present;source_observation_count>=2",
            lambda row, improvement=improvement, rank=rank: source_type(row) == "category_best_seller"
            and pod_allowed(row, "not_low")
            and int_value(row.get("previous_source_rank")) is not None
            and int_value(row.get("source_rank_change")) is not None
            and int_value(row.get("source_rank_change")) >= improvement
            and rank_value(row) is not None
            and rank_value(row) <= rank
            and (int_value(row.get("source_observation_count")) or 0) >= 2,
            lambda group: has_source_family(group, "category_best_seller"),
        ))
    for days, observations in product([7, 10, 14], [3, 5, 7]):
        simulations.append((
            "category_stable",
            f"source_rank<=100;source_days_seen>={days};source_observation_count>={observations};pod_relevance=not_low",
            lambda row, days=days, observations=observations: source_type(row) == "category_best_seller"
            and pod_allowed(row, "not_low")
            and rank_value(row) is not None
            and rank_value(row) <= 100
            and (int_value(row.get("source_days_seen")) or 0) >= days
            and (int_value(row.get("source_observation_count")) or 0) >= observations,
            lambda group: has_source_family(group, "category_best_seller"),
        ))
    for improvement, rank in product([5, 10, 15, 20, 30], [30, 50, 100]):
        simulations.append((
            "new_release_rising",
            f"source_rank_change>={improvement};source_rank<={rank};pod_relevance=not_low;previous_source_rank=present;source_observation_count>=2",
            lambda row, improvement=improvement, rank=rank: source_type(row) == "category_new_release"
            and pod_allowed(row, "not_low")
            and int_value(row.get("previous_source_rank")) is not None
            and int_value(row.get("source_rank_change")) is not None
            and int_value(row.get("source_rank_change")) >= improvement
            and rank_value(row) is not None
            and rank_value(row) <= rank
            and (int_value(row.get("source_observation_count")) or 0) >= 2,
            lambda group: has_source_family(group, "category_new_release"),
        ))
    for improvement, rank in product([15, 20, 30, 40], [10, 20, 30]):
        simulations.append((
            "new_release_breakout",
            f"source_rank_change>={improvement};source_rank<={rank};pod_relevance=not_low;previous_source_rank=present;source_observation_count>=2",
            lambda row, improvement=improvement, rank=rank: source_type(row) == "category_new_release"
            and pod_allowed(row, "not_low")
            and int_value(row.get("previous_source_rank")) is not None
            and int_value(row.get("source_rank_change")) is not None
            and int_value(row.get("source_rank_change")) >= improvement
            and rank_value(row) is not None
            and rank_value(row) <= rank
            and (int_value(row.get("source_observation_count")) or 0) >= 2,
            lambda group: has_source_family(group, "category_new_release"),
        ))
    for days, rank, pod_mode in product([3, 5, 7], [20, 30, 50, 100], ["high_only", "high_medium", "not_low"]):
        simulations.append((
            "new_release_watch",
            f"source_days_seen<={days};source_rank<={rank};pod_relevance={pod_mode}",
            lambda row, days=days, rank=rank, pod_mode=pod_mode: source_type(row) == "category_new_release"
            and pod_allowed(row, pod_mode)
            and int_value(row.get("source_days_seen")) is not None
            and int_value(row.get("source_days_seen")) <= days
            and rank_value(row) is not None
            and rank_value(row) <= rank,
            lambda group: has_source_family(group, "category_new_release"),
        ))
    for threshold in [100, 500, 1000, 2500, 5000, 10000]:
        simulations.append((
            "sub_bsr",
            f"sub_bsr_rank<={threshold}",
            lambda row, threshold=threshold: valid_sub_bsr(row) is not None and valid_sub_bsr(row) <= threshold,
            has_valid_sub_bsr,
        ))

    rows: list[dict[str, str]] = []
    for signal, thresholds, row_predicate, eligible_predicate in simulations:
        eligible = [group for group in groups.values() if eligible_predicate(group)]
        matched_rows_by_product: dict[tuple[str, str], list[dict[str, str]]] = {}
        for group in eligible:
            matching_rows = [row for row in group.rows if row_predicate(row)]
            if matching_rows:
                matched_rows_by_product[group.key] = matching_rows
        matched_rows = [row for rows in matched_rows_by_product.values() for row in rows]
        rows.append(threshold_row(signal, thresholds, len(eligible), matched_rows_by_product, matched_rows))
    return rows


def threshold_row(
    signal: str,
    thresholds: str,
    eligible_count: int,
    matched_rows_by_product: dict[tuple[str, str], list[dict[str, str]]],
    matched_rows: list[dict[str, str]],
) -> dict[str, str]:
    matching_count = len(matched_rows_by_product)
    product_rows = [sorted(rows, key=row_sort_key)[0] for rows in matched_rows_by_product.values()]
    return {
        "simulation_signal": signal,
        "thresholds": thresholds,
        "matching_product_count": str(matching_count),
        "eligible_product_count": str(eligible_count),
        "eligible_coverage_rate": format_rate(matching_count, eligible_count),
        "median_reviews": format_number(percentile(numeric_values(product_rows, review_count), 50)),
        "median_price": format_number(percentile(numeric_values(product_rows, price_value), 50)),
        "median_source_rank": format_number(percentile(numeric_values(product_rows, rank_value), 50)),
        "median_rank_improvement": format_number(percentile(numeric_values(product_rows, lambda row: int_value(row.get("source_rank_change"))), 50)),
        "pod_relevance_distribution": format_counter(Counter(normalize_text(row.get("pod_relevance", "")) or "unknown" for row in product_rows), matching_count),
        "product_type_distribution": format_counter(Counter(product_type(row) for row in product_rows), matching_count),
        "bsr_available_count": str(len({product_key(row) for row in matched_rows if valid_sub_bsr(row) is not None})),
        "median_sub_bsr": format_number(percentile(numeric_values(product_rows, valid_sub_bsr), 50)),
    }


def build_overlap_matrix(groups: dict[tuple[str, str], ProductGroup]) -> list[dict[str, str]]:
    active_sets = {signal: {group.key for group in groups.values() if product_has_signal(group, signal)} for signal in SIGNAL_NAMES}
    rows: list[dict[str, str]] = []
    for left, right in combinations(SIGNAL_NAMES, 2):
        intersection = active_sets[left] & active_sets[right]
        union = active_sets[left] | active_sets[right]
        left_count = len(active_sets[left])
        right_count = len(active_sets[right])
        rows.append(
            {
                "signal_a": left,
                "signal_b": right,
                "source_family_a": SIGNAL_FAMILY[left],
                "source_family_b": SIGNAL_FAMILY[right],
                "intersection_count": str(len(intersection)),
                "union_count": str(len(union)),
                "jaccard_similarity": format_rate(len(intersection), len(union)),
                "overlap_rate_a": format_rate(len(intersection), left_count),
                "overlap_rate_b": format_rate(len(intersection), right_count),
            }
        )
    return rows


def signal_count_distribution(groups: dict[tuple[str, str], ProductGroup]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for group in groups.values():
        active_count = sum(1 for signal in SIGNAL_NAMES if product_has_signal(group, signal))
        if active_count >= 4:
            counts["4+"] += 1
        else:
            counts[str(active_count)] += 1
    return counts


def build_review_sample(groups: dict[tuple[str, str], ProductGroup]) -> list[dict[str, str]]:
    selected_keys: set[tuple[str, str]] = set()
    rows: list[dict[str, str]] = []
    for signal in SIGNAL_NAMES:
        active_groups = [group for group in groups.values() if product_has_signal(group, signal)]
        candidates = sorted(
            ((sample_bucket(signal, representative_signal_row(group, signal)), group) for group in active_groups),
            key=lambda item: (item[0], item[1].marketplace, item[1].asin),
        )
        target = REVIEW_SAMPLE_TARGETS[signal]
        limit = len(candidates) if target is None else min(target, len(candidates))
        chosen: list[tuple[str, ProductGroup]] = []
        for bucket, group in candidates:
            if group.key in selected_keys:
                continue
            chosen.append((bucket, group))
            selected_keys.add(group.key)
            if len(chosen) >= limit:
                break
        if len(chosen) < limit:
            for bucket, group in candidates:
                if (bucket, group) in chosen:
                    continue
                chosen.append((bucket, group))
                if len(chosen) >= limit:
                    break
        for bucket, group in chosen:
            rows.append(review_sample_row(signal, bucket, group))
    return rows


def review_sample_row(signal: str, bucket: str, group: ProductGroup) -> dict[str, str]:
    row = representative_signal_row(group, signal)
    labels = sorted({label for group_row in group.rows for label in split_values(group_row.get("evidence_labels", ""))})
    reasons = sorted({reason for group_row in group.rows for reason in split_values(group_row.get("evidence_reasons", ""))})
    return {
        "sample_signal": signal,
        "sample_bucket": bucket,
        "marketplace": group.marketplace,
        "asin": group.asin,
        "title": first_text(row, "title", "raw_title"),
        "seller": first_text(row, "seller_name", "source_name"),
        "product_type": product_type(row),
        "pod_relevance": first_text(row, "pod_relevance") or "unknown",
        "review_count": first_text(row, "review_count"),
        "review_rating": first_text(row, "review_rating", "rating"),
        "price": first_text(row, "today_price", "price", "latest_price"),
        "source_family": SIGNAL_FAMILY[signal],
        "source_name": first_text(row, "source_name"),
        "source_id": first_text(row, "source_id"),
        "source_rank": first_text(row, "source_rank", "today_rank"),
        "previous_source_rank": first_text(row, "previous_source_rank", "previous_rank"),
        "source_rank_change": first_text(row, "source_rank_change", "rank_change_vs_previous_seen"),
        "source_days_seen": first_text(row, "source_days_seen", "days_seen"),
        "source_observation_count": first_text(row, "source_observation_count", "historical_observations"),
        "category": first_text(row, "category_name", "category"),
        "sub_bsr_rank": first_text(row, "sub_bsr_rank"),
        "sub_bsr_category": first_text(row, "sub_bsr_category"),
        "primary_bsr_rank": first_text(row, "primary_bsr_rank", "bsr_rank"),
        "primary_bsr_category": first_text(row, "primary_bsr_category", "bsr_category"),
        "all_evidence_labels": "; ".join(labels),
        "evidence_reasons": "; ".join(reasons),
        "product_url": first_text(row, "product_url"),
        "image_url": first_text(row, "image_url"),
        "review_label": "",
        "pod_validity": "",
        "idea_quality": "",
        "duplicability": "",
        "market_relevance": "",
        "research_priority": "",
        "review_notes": "",
        "reviewer": "",
        "reviewed_at": "",
    }


def is_product_eligible(group: ProductGroup, signal: str) -> bool:
    family = SIGNAL_FAMILY[signal]
    if family == "bsr":
        return has_valid_sub_bsr(group)
    return has_source_family(group, family)


def has_source_family(group: ProductGroup, family: str) -> bool:
    return any(source_type(row) == family for row in group.rows)


def has_valid_sub_bsr(group: ProductGroup) -> bool:
    return any(valid_sub_bsr(row) is not None for row in group.rows)


def product_has_signal(group: ProductGroup, signal: str) -> bool:
    return any(truthy(row.get(signal, "")) for row in group.rows)


def representative_signal_row(group: ProductGroup, signal: str) -> dict[str, str]:
    family = SIGNAL_FAMILY[signal]
    active_rows = [row for row in group.rows if truthy(row.get(signal, ""))]
    if active_rows:
        return sorted(active_rows, key=row_sort_key)[0]
    if family == "bsr":
        bsr_rows = [row for row in group.rows if valid_sub_bsr(row) is not None]
        if bsr_rows:
            return sorted(bsr_rows, key=lambda row: (valid_sub_bsr(row) or 10**12, row_sort_key(row)))[0]
    family_rows = [row for row in group.rows if source_type(row) == family]
    return sorted(family_rows or group.rows, key=row_sort_key)[0]


def representative_row(group: ProductGroup) -> dict[str, str]:
    return sorted(group.rows, key=row_sort_key)[0]


def distribution_fields(rows: list[dict[str, str]]) -> dict[str, str]:
    values = stats_for(rows, rank_value)
    fields = {
        "source_rank_count": values["count"],
        "source_rank_missing": values["missing"],
        "source_rank_min": values["min"],
        "source_rank_p10": values["p10"],
        "source_rank_p25": values["p25"],
        "source_rank_mean": values["mean"],
        "source_rank_median": values["median"],
        "source_rank_p75": values["p75"],
        "source_rank_p90": values["p90"],
        "source_rank_max": values["max"],
        "previous_source_rank_median": stats_for(rows, lambda row: int_value(row.get("previous_source_rank")))["median"],
        "source_rank_change_median": stats_for(rows, lambda row: int_value(row.get("source_rank_change")))["median"],
        "source_days_seen_median": stats_for(rows, lambda row: int_value(row.get("source_days_seen")))["median"],
        "source_observation_count_median": stats_for(rows, lambda row: int_value(row.get("source_observation_count")))["median"],
        "price_median": stats_for(rows, price_value)["median"],
        "rating_median": stats_for(rows, rating_value)["median"],
        "review_count_median": stats_for(rows, review_count)["median"],
        "primary_bsr_median": stats_for(rows, primary_bsr)["median"],
        "sub_bsr_median": stats_for(rows, valid_sub_bsr)["median"],
    }
    return fields


def categorical_fields(rows: list[dict[str, str]], product_count: int) -> dict[str, str]:
    denominator = max(len(rows), product_count, 1)
    return {
        "pod_relevance_distribution": format_counter(Counter(first_text(row, "pod_relevance") or "unknown" for row in rows), denominator),
        "product_type_distribution": format_counter(Counter(product_type(row) for row in rows), denominator),
        "seller_distribution": format_counter(Counter(first_text(row, "seller_name", "source_name") or "Unknown" for row in rows), denominator),
        "category_distribution": format_counter(Counter(first_text(row, "category_name", "category", "source_name") or "Unknown" for row in rows), denominator),
        "sub_bsr_category_distribution": format_counter(Counter(first_text(row, "sub_bsr_category") or "Unknown" for row in rows), denominator),
        "marketplace_distribution": format_counter(Counter(first_text(row, "marketplace") or "amazon.com" for row in rows), denominator),
    }


def stats_for(rows: list[dict[str, str]], extractor: Callable[[dict[str, str]], float | int | None]) -> dict[str, str]:
    values = numeric_values(rows, extractor)
    missing = len(rows) - len(values)
    return {
        "count": str(len(values)),
        "missing": str(missing),
        "min": format_number(min(values) if values else None),
        "p10": format_number(percentile(values, 10)),
        "p25": format_number(percentile(values, 25)),
        "mean": format_number(mean(values) if values else None),
        "median": format_number(percentile(values, 50)),
        "p75": format_number(percentile(values, 75)),
        "p90": format_number(percentile(values, 90)),
        "max": format_number(max(values) if values else None),
    }


def numeric_values(rows: list[dict[str, str]], extractor: Callable[[dict[str, str]], float | int | None]) -> list[float]:
    values: list[float] = []
    for row in rows:
        value = extractor(row)
        if value is None:
            continue
        values.append(float(value))
    return values


def percentile(values: Iterable[float], percentile_value: int) -> float | None:
    ordered = sorted(values)
    if not ordered:
        return None
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * (percentile_value / 100)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + ((ordered[upper] - ordered[lower]) * fraction)


def sample_bucket(signal: str, row: dict[str, str]) -> str:
    rank = rank_value(row)
    change = int_value(row.get("source_rank_change"))
    days = int_value(row.get("source_days_seen"))
    reviews = review_count(row)
    pod = first_text(row, "pod_relevance") or "unknown"
    if signal in {"seller_leader", "category_winner"} and rank is not None:
        return "threshold_near_rank" if rank <= 35 else "rank_tail"
    if "mover" in signal or "breakout" in signal or "rising" in signal:
        if change is None:
            return "missing_movement"
        return "threshold_near_movement" if change <= 20 else "large_movement"
    if signal in {"seller_new_push", "new_release_watch"} and days is not None:
        return "fresh_low_review" if days <= 5 and (reviews is None or reviews <= 50) else "fresh_other"
    if signal in {"strong_sub_bsr", "very_strong_sub_bsr"}:
        sub_bsr = valid_sub_bsr(row)
        if sub_bsr is not None and sub_bsr <= 1000:
            return f"very_strong_{pod}"
        return f"strong_{pod}"
    return "general"


def concentration_notes(row: dict[str, str]) -> str:
    notes = []
    for field, label in [
        ("product_type_distribution", "product type"),
        ("seller_distribution", "seller"),
        ("category_distribution", "category"),
    ]:
        top = row.get(field, "").split("; ", 1)[0]
        if "(" not in top:
            continue
        percent_text = top.rsplit("(", 1)[-1].rstrip("%)")
        try:
            percent = float(percent_text)
        except ValueError:
            continue
        if percent >= 50:
            notes.append(f"{label} concentration: {top}")
    return "; ".join(notes)


def render_calibration_html(
    summary_rows: list[dict[str, str]],
    threshold_rows: list[dict[str, str]],
    overlap_rows: list[dict[str, str]],
    review_rows: list[dict[str, str]],
    signal_distribution: Counter[str] | None = None,
) -> str:
    top_overlaps = sorted(overlap_rows, key=lambda row: int(row["intersection_count"]), reverse=True)[:20]
    top_thresholds = sorted(threshold_rows, key=lambda row: int(row["matching_product_count"]), reverse=True)[:30]
    signal_distribution_rows = [
        {"active_signal_count": label, "product_count": str(count)}
        for label, count in sorted((signal_distribution or Counter()).items(), key=lambda item: item[0])
    ]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Evidence Calibration Report</title>
  <style>
    body {{ margin: 0; font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f5f7fa; color: #182230; }}
    main {{ max-width: 1320px; margin: 0 auto; padding: 24px; }}
    h1 {{ font-size: 28px; margin: 0 0 8px; }}
    h2 {{ font-size: 20px; margin: 28px 0 10px; }}
    p {{ color: #3f4b5b; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #e4e8ee; font-size: 13px; }}
    th, td {{ padding: 7px 8px; border-bottom: 1px solid #e4e8ee; text-align: left; vertical-align: top; }}
    th {{ background: #fbfcfd; color: #738194; font-size: 12px; text-transform: uppercase; }}
    .note {{ background: #fff; border: 1px solid #e4e8ee; border-radius: 8px; padding: 12px; }}
  </style>
</head>
<body>
<main>
  <h1>Evidence Calibration Report</h1>
  <p>Static report generated from source-aware historical comparison rows. Production evidence thresholds are not changed.</p>
  <section class="note">
    <strong>Methodology</strong>
    <p>Coverage metrics use source-family-aware eligible denominators. Products without a relevant source family are counted as no_data, not false. Threshold simulations are read-only alternatives over current source-aware observation fields.</p>
  </section>
  <h2>Signal Overview</h2>
  {_html_table(summary_rows, ["signal_label", "source_family", "total_product_count", "eligible_product_count", "active_signal_count", "signal_rate_eligible", "signal_rate_all", "no_data_count", "false_count"])}
  <h2>Coverage-Adjusted Metrics</h2>
  {_html_table(summary_rows, ["signal_label", "source_rank_median", "source_rank_change_median", "source_days_seen_median", "review_count_median", "price_median", "sub_bsr_median", "product_type_distribution", "concentration_notes"])}
  <h2>Threshold Simulation</h2>
  {_html_table(top_thresholds, ["simulation_signal", "thresholds", "matching_product_count", "eligible_coverage_rate", "median_reviews", "median_price", "median_source_rank", "median_rank_improvement", "product_type_distribution"])}
  <h2>Overlap Analysis</h2>
  {_html_table(top_overlaps, ["signal_a", "signal_b", "intersection_count", "jaccard_similarity", "overlap_rate_a", "overlap_rate_b"])}
  <h2>Products By Active Signal Count</h2>
  {_html_table(signal_distribution_rows, ["active_signal_count", "product_count"])}
  <h2>Product Type And Category Analysis</h2>
  {_html_table(summary_rows, ["signal_label", "product_type_distribution", "category_distribution", "sub_bsr_category_distribution", "seller_distribution"])}
  <h2>Sample Products</h2>
  {_html_table(review_rows[:80], ["sample_signal", "sample_bucket", "asin", "title", "seller", "product_type", "source_rank", "source_rank_change", "sub_bsr_rank", "product_url"])}
  <h2>Definitions</h2>
  <p>Seller signals use seller source observations. Category signals use category_best_seller observations. New Release signals use category_new_release observations. BSR signals require a valid positive sub-category BSR.</p>
</main>
</body>
</html>"""


def _html_table(rows: list[dict[str, str]], fields: list[str]) -> str:
    if not rows:
        return "<p>No rows available.</p>"
    header = "".join(f"<th>{escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def row_sort_key(row: dict[str, str]) -> tuple[int, str, str]:
    rank = rank_value(row)
    return rank if rank is not None else 10**12, first_text(row, "source_id", "source_name"), first_text(row, "asin")


def product_key(row: dict[str, str]) -> tuple[str, str]:
    return first_text(row, "marketplace") or "amazon.com", first_text(row, "asin").upper()


def source_type(row: dict[str, str]) -> str:
    return normalize_text(row.get("source_type", ""))


def rank_value(row: dict[str, str]) -> int | None:
    return int_value(first_text(row, "source_rank", "today_rank"))


def valid_sub_bsr(row: dict[str, str]) -> int | None:
    value = int_value(first_text(row, "sub_bsr_rank"))
    return value if value is not None and value > 0 else None


def primary_bsr(row: dict[str, str]) -> int | None:
    value = int_value(first_text(row, "primary_bsr_rank", "bsr_rank"))
    return value if value is not None and value > 0 else None


def review_count(row: dict[str, str]) -> int | None:
    value = int_value(first_text(row, "review_count"))
    return value if value is not None and value >= 0 else None


def rating_value(row: dict[str, str]) -> float | None:
    return float_value(first_text(row, "review_rating", "rating"))


def price_value(row: dict[str, str]) -> float | None:
    return float_value(first_text(row, "today_price", "price", "latest_price"))


def product_type(row: dict[str, str]) -> str:
    return first_text(row, "product_type", "pod_type", "niche_primary") or "Unknown"


def pod_allowed(row: dict[str, str], mode: str) -> bool:
    relevance = (first_text(row, "pod_relevance") or "unknown").lower()
    if mode == "high_only":
        return relevance == "high"
    if mode == "high_medium":
        return relevance in {"high", "medium"}
    return relevance != "low"


def truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def first_text(row: dict[str, str], *keys: str) -> str:
    for key in keys:
        value = normalize_text(row.get(key, ""))
        if value:
            return value
    return ""


def normalize_text(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def int_value(value: object) -> int | None:
    text = str(value or "").replace(",", "").replace("#", "").strip()
    if not text:
        return None
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return None


def float_value(value: object) -> float | None:
    text = str(value or "").replace(",", "").replace("$", "").strip()
    if not text:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def split_values(value: object) -> list[str]:
    return [item.strip() for item in str(value or "").replace("|", ";").split(";") if item.strip()]


def format_rate(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return "0.0000"
    return f"{numerator / denominator:.4f}"


def format_number(value: float | int | None) -> str:
    if value is None:
        return ""
    if float(value).is_integer():
        return str(int(value))
    return f"{float(value):.2f}"


def format_counter(counter: Counter[str], denominator: int, limit: int = 5) -> str:
    if not counter:
        return ""
    denominator = max(denominator, 1)
    parts = []
    for label, count in counter.most_common(limit):
        parts.append(f"{label}: {count} ({(count / denominator) * 100:.1f}%)")
    return "; ".join(parts)
