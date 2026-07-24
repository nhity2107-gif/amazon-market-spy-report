from __future__ import annotations

from collections import Counter, defaultdict
from html import escape
from itertools import combinations
from math import sqrt
from pathlib import Path

from .evidence_calibration import (
    SIGNAL_FAMILY,
    SIGNAL_LABELS,
    SIGNAL_NAMES,
    build_threshold_simulation,
    float_value,
    format_counter,
    format_number,
    group_products,
    int_value,
    normalize_text,
    price_value,
    product_type,
    rank_value,
    review_count,
    valid_sub_bsr,
)
from .reporting import read_csv, write_csv


REVIEW_COLUMNS = [
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

ALLOWED_VALUES = {
    "review_label": {"high_value", "potential", "weak", "noise", "non_pod", "insufficient_data"},
    "pod_validity": {"clear_pod", "likely_pod", "uncertain", "not_pod"},
    "idea_quality": {"strong", "medium", "weak"},
    "duplicability": {"easy", "moderate", "difficult", "not_relevant"},
    "market_relevance": {"high", "medium", "low", "unknown"},
    "research_priority": {"launch_research", "watch", "ignore"},
}

PRODUCTION_THRESHOLDS = {
    "seller_leader": "source_rank<=10;source_days_seen>=7",
    "seller_mover": "source_rank_change>=10;source_rank<=100;previous_source_rank=present;source_observation_count>=2",
    "seller_new_push": "source_days_seen<=7;source_rank<=20",
    "category_winner": "source_rank<=30;source_days_seen>=7;pod_relevance=not_low",
    "category_breakout": "source_rank_change>=15;source_rank<=50;pod_relevance=not_low;previous_source_rank=present;source_observation_count>=2",
    "category_stable": "source_rank<=100;source_days_seen>=14;pod_relevance=not_low",
    "new_release_rising": "source_rank_change>=10;source_rank<=100;pod_relevance=not_low;previous_source_rank=present;source_observation_count>=2",
    "new_release_breakout": "source_rank_change>=30;source_rank<=30;pod_relevance=not_low;previous_source_rank=present;source_observation_count>=2",
    "new_release_watch": "source_days_seen<=7;source_rank<=100;pod_relevance=not_low",
    "strong_sub_bsr": "sub_bsr_rank<=5000",
    "very_strong_sub_bsr": "sub_bsr_rank<=1000",
}

MIN_TOTAL_VALID_REVIEWS = 30
MIN_REVIEWED_SIGNALS = 3
MIN_SIGNAL_SAMPLE = 10

HUMAN_REVIEW_SUMMARY_FIELDS = ["metric", "value", "details"]

SIGNAL_QUALITY_FIELDS = [
    "row_type",
    "signal",
    "signal_label",
    "breakdown_dimension",
    "breakdown_value",
    "reviewed_rows",
    "valid_reviewed_rows",
    "insufficient_data_rows",
    "precision",
    "precision_ci_low",
    "precision_ci_high",
    "high_value_rate",
    "weak_rate",
    "noise_rate",
    "non_pod_rate",
    "actionable_rate",
    "launch_rate",
    "clear_likely_pod_rate",
    "strong_idea_rate",
    "easy_moderate_duplicability_rate",
    "high_medium_market_rate",
    "warning",
]

THRESHOLD_QUALITY_FIELDS = [
    "simulation_signal",
    "thresholds",
    "reviewed_matching_count",
    "valid_reviewed_count",
    "precision",
    "high_value_rate",
    "noise_rate",
    "actionable_rate",
    "launch_rate",
    "total_matching_product_count",
    "eligible_coverage_rate",
    "warning",
]

REVIEWER_AGREEMENT_FIELDS = [
    "row_type",
    "review_unit",
    "field",
    "reviewer_count",
    "comparison_count",
    "agreement_count",
    "agreement_rate",
    "cohens_kappa",
    "values",
    "warning",
]

RECOMMENDATION_FIELDS = [
    "signal",
    "signal_label",
    "status",
    "current_production_threshold",
    "proposed_threshold",
    "current_full_data_count",
    "proposed_full_data_count",
    "reviewed_sample_size",
    "current_precision",
    "proposed_precision",
    "current_actionable_rate",
    "proposed_actionable_rate",
    "coverage_tradeoff",
    "reasoning",
    "confidence",
]

BREAKDOWN_DIMENSIONS = [
    "sample_bucket",
    "pod_relevance",
    "product_type",
    "seller",
    "source_category",
    "sub_bsr_category",
    "source_rank_band",
    "source_rank_change_band",
    "days_seen_band",
    "review_count_band",
    "price_band",
    "bsr_band",
    "reviewer",
]


def analyze_evidence_reviews(
    review_file: Path,
    output_dir: Path,
    summary_file: Path | None = None,
    threshold_file: Path | None = None,
    comparison_file: Path | None = None,
) -> dict[str, object]:
    output_dir = Path(output_dir)
    review_file = Path(review_file)
    summary_file = Path(summary_file) if summary_file else output_dir / "evidence_calibration_summary.csv"
    threshold_file = Path(threshold_file) if threshold_file else output_dir / "evidence_threshold_simulation.csv"
    comparison_file = Path(comparison_file) if comparison_file else output_dir / "historical_comparison.csv"

    rows = normalize_review_rows(read_csv(review_file))
    summary_rows = read_csv(summary_file) if summary_file.exists() else []
    threshold_rows = load_threshold_rows(threshold_file, comparison_file)

    validation = validate_review_rows(rows)
    quality_rows = build_signal_quality(rows)
    threshold_quality_rows = build_threshold_quality(rows, threshold_rows)
    agreement_rows = build_reviewer_agreement(rows)

    total_valid = sum(1 for row in rows if is_valid_precision_row(row))
    reviewed_signals = {
        row["signal"]
        for row in quality_rows
        if row["row_type"] == "signal_overall" and int_value(row["valid_reviewed_rows"]) and int_value(row["valid_reviewed_rows"]) >= MIN_SIGNAL_SAMPLE
    }
    insufficient = total_valid < MIN_TOTAL_VALID_REVIEWS or len(reviewed_signals) < MIN_REVIEWED_SIGNALS
    recommendations = build_recommendations(quality_rows, threshold_quality_rows, summary_rows, insufficient)
    review_summary_rows = build_review_summary(rows, validation, insufficient, total_valid, reviewed_signals)

    paths = {
        "human_review_summary": output_dir / "evidence_human_review_summary.csv",
        "signal_quality": output_dir / "evidence_signal_quality.csv",
        "threshold_quality": output_dir / "evidence_threshold_quality.csv",
        "reviewer_agreement": output_dir / "evidence_reviewer_agreement.csv",
        "threshold_recommendations": output_dir / "evidence_threshold_recommendations.csv",
        "html": output_dir / "evidence_human_review_analysis.html",
    }
    write_csv(paths["human_review_summary"], review_summary_rows, HUMAN_REVIEW_SUMMARY_FIELDS)
    write_csv(paths["signal_quality"], quality_rows, SIGNAL_QUALITY_FIELDS)
    write_csv(paths["threshold_quality"], threshold_quality_rows, THRESHOLD_QUALITY_FIELDS)
    write_csv(paths["reviewer_agreement"], agreement_rows, REVIEWER_AGREEMENT_FIELDS)
    write_csv(paths["threshold_recommendations"], recommendations, RECOMMENDATION_FIELDS)
    paths["html"].write_text(
        render_review_analysis_html(review_summary_rows, quality_rows, threshold_quality_rows, agreement_rows, recommendations),
        encoding="utf-8",
    )

    return {
        "review_file": str(review_file),
        "total_rows": len(rows),
        "reviewed_rows": validation["reviewed_rows"],
        "unreviewed_rows": validation["unreviewed_rows"],
        "valid_reviewed_rows": total_valid,
        "insufficient_review": insufficient,
        "invalid_values": validation["invalid_values"],
        "paths": {key: str(path) for key, path in paths.items()},
    }


def normalize_review_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    normalized_rows = []
    for row in rows:
        normalized = dict(row)
        for column in REVIEW_COLUMNS:
            normalized.setdefault(column, "")
        normalized_rows.append(normalized)
    return normalized_rows


def load_threshold_rows(threshold_file: Path, comparison_file: Path) -> list[dict[str, str]]:
    if threshold_file.exists():
        return read_csv(threshold_file)
    if comparison_file.exists():
        return build_threshold_simulation(group_products(read_csv(comparison_file)))
    return []


def validate_review_rows(rows: list[dict[str, str]]) -> dict[str, object]:
    invalid_values: dict[str, Counter[str]] = {column: Counter() for column in ALLOWED_VALUES}
    reviewed_rows = [row for row in rows if has_review_activity(row)]
    for row in reviewed_rows:
        for column, allowed in ALLOWED_VALUES.items():
            value = review_value(row, column)
            if value and value not in allowed:
                invalid_values[column][value] += 1
    return {
        "reviewed_rows": len(reviewed_rows),
        "unreviewed_rows": len(rows) - len(reviewed_rows),
        "invalid_values": invalid_values,
        "missing_reviewer": sum(1 for row in reviewed_rows if not review_value(row, "reviewer")),
        "missing_reviewed_at": sum(1 for row in reviewed_rows if not review_value(row, "reviewed_at")),
        "reviewed_by_signal": Counter(review_value(row, "sample_signal") or "unknown" for row in reviewed_rows),
        "reviewed_by_reviewer": Counter(review_value(row, "reviewer") or "missing" for row in reviewed_rows),
    }


def build_review_summary(
    rows: list[dict[str, str]],
    validation: dict[str, object],
    insufficient: bool,
    total_valid: int,
    reviewed_signals: set[str],
) -> list[dict[str, str]]:
    invalid_values = validation["invalid_values"]
    summary = [
        {"metric": "total_rows", "value": str(len(rows)), "details": ""},
        {"metric": "reviewed_rows", "value": str(validation["reviewed_rows"]), "details": ""},
        {"metric": "unreviewed_rows", "value": str(validation["unreviewed_rows"]), "details": ""},
        {"metric": "valid_reviewed_rows", "value": str(total_valid), "details": "Excludes blank and insufficient_data review_label rows."},
        {"metric": "missing_reviewer_names", "value": str(validation["missing_reviewer"]), "details": "Counted only among rows with review activity."},
        {"metric": "missing_reviewed_at_values", "value": str(validation["missing_reviewed_at"]), "details": "Counted only among rows with review activity."},
        {
            "metric": "recommendation_mode",
            "value": "diagnostic_only" if insufficient else "recommendation_ready",
            "details": f"Requires at least {MIN_TOTAL_VALID_REVIEWS} valid labels and {MIN_REVIEWED_SIGNALS} signals with at least {MIN_SIGNAL_SAMPLE} valid labels.",
        },
    ]
    for column in ALLOWED_VALUES:
        values = invalid_values[column]
        summary.append(
            {
                "metric": f"invalid_values_{column}",
                "value": str(sum(values.values())),
                "details": format_counter(values, sum(values.values())) if values else "",
            }
        )
    for signal, count in sorted(validation["reviewed_by_signal"].items()):
        summary.append({"metric": "reviewed_rows_by_sample_signal", "value": str(count), "details": signal})
    for reviewer, count in sorted(validation["reviewed_by_reviewer"].items()):
        summary.append({"metric": "reviewed_rows_by_reviewer", "value": str(count), "details": reviewer})
    return summary


def build_signal_quality(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    quality_rows: list[dict[str, str]] = []
    for signal in SIGNAL_NAMES:
        signal_rows = [row for row in rows if review_value(row, "sample_signal") == signal]
        quality_rows.append(quality_row("signal_overall", signal, "", "", signal_rows))
        reviewed_signal_rows = [row for row in signal_rows if has_review_activity(row)]
        if not reviewed_signal_rows:
            continue
        for dimension in BREAKDOWN_DIMENSIONS:
            grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
            for row in signal_rows:
                grouped[dimension_value(row, dimension)].append(row)
            for value, dimension_rows in sorted(grouped.items()):
                if any(has_review_activity(row) for row in dimension_rows):
                    quality_rows.append(quality_row("breakdown", signal, dimension, value, dimension_rows))
    return quality_rows


def quality_row(row_type: str, signal: str, dimension: str, value: str, rows: list[dict[str, str]]) -> dict[str, str]:
    metrics = quality_metrics(rows)
    return {
        "row_type": row_type,
        "signal": signal,
        "signal_label": SIGNAL_LABELS.get(signal, signal),
        "breakdown_dimension": dimension,
        "breakdown_value": value,
        **metrics,
    }


def quality_metrics(rows: list[dict[str, str]]) -> dict[str, str]:
    reviewed_rows = [row for row in rows if has_review_activity(row)]
    valid_rows = [row for row in rows if is_valid_precision_row(row)]
    insufficient_rows = [row for row in reviewed_rows if review_value(row, "review_label") == "insufficient_data"]
    valid_count = len(valid_rows)
    positive_count = sum(1 for row in valid_rows if review_value(row, "review_label") in {"high_value", "potential"})
    high_value_count = sum(1 for row in valid_rows if review_value(row, "review_label") == "high_value")
    weak_count = sum(1 for row in valid_rows if review_value(row, "review_label") == "weak")
    noise_count = sum(1 for row in valid_rows if review_value(row, "review_label") in {"noise", "non_pod"})
    non_pod_count = sum(1 for row in valid_rows if review_value(row, "review_label") == "non_pod")
    priority_rows = [row for row in rows if review_value(row, "research_priority") in ALLOWED_VALUES["research_priority"]]
    pod_rows = [row for row in rows if review_value(row, "pod_validity") in ALLOWED_VALUES["pod_validity"]]
    idea_rows = [row for row in rows if review_value(row, "idea_quality") in ALLOWED_VALUES["idea_quality"]]
    duplicability_rows = [row for row in rows if review_value(row, "duplicability") in ALLOWED_VALUES["duplicability"]]
    market_rows = [row for row in rows if review_value(row, "market_relevance") in ALLOWED_VALUES["market_relevance"]]
    precision = nullable_rate(positive_count, valid_count)
    ci_low, ci_high = wilson_interval(positive_count, valid_count)
    warning = ""
    if valid_count == 0:
        warning = "no valid reviewed rows"
    elif valid_count < MIN_SIGNAL_SAMPLE:
        warning = f"low sample: {valid_count} valid labels"
    return {
        "reviewed_rows": str(len(reviewed_rows)),
        "valid_reviewed_rows": str(valid_count),
        "insufficient_data_rows": str(len(insufficient_rows)),
        "precision": precision,
        "precision_ci_low": ci_low,
        "precision_ci_high": ci_high,
        "high_value_rate": nullable_rate(high_value_count, valid_count),
        "weak_rate": nullable_rate(weak_count, valid_count),
        "noise_rate": nullable_rate(noise_count, valid_count),
        "non_pod_rate": nullable_rate(non_pod_count, valid_count),
        "actionable_rate": nullable_rate(sum(1 for row in priority_rows if review_value(row, "research_priority") in {"launch_research", "watch"}), len(priority_rows)),
        "launch_rate": nullable_rate(sum(1 for row in priority_rows if review_value(row, "research_priority") == "launch_research"), len(priority_rows)),
        "clear_likely_pod_rate": nullable_rate(sum(1 for row in pod_rows if review_value(row, "pod_validity") in {"clear_pod", "likely_pod"}), len(pod_rows)),
        "strong_idea_rate": nullable_rate(sum(1 for row in idea_rows if review_value(row, "idea_quality") == "strong"), len(idea_rows)),
        "easy_moderate_duplicability_rate": nullable_rate(sum(1 for row in duplicability_rows if review_value(row, "duplicability") in {"easy", "moderate"}), len(duplicability_rows)),
        "high_medium_market_rate": nullable_rate(sum(1 for row in market_rows if review_value(row, "market_relevance") in {"high", "medium"}), len(market_rows)),
        "warning": warning,
    }


def build_threshold_quality(review_rows: list[dict[str, str]], threshold_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for threshold in threshold_rows:
        signal = review_value(threshold, "simulation_signal")
        candidates = [row for row in review_rows if threshold_candidate_matches_signal(row, signal)]
        matching = [row for row in candidates if row_matches_threshold(row, signal, threshold.get("thresholds", ""))]
        metrics = quality_metrics(matching)
        rows.append(
            {
                "simulation_signal": signal,
                "thresholds": threshold.get("thresholds", ""),
                "reviewed_matching_count": metrics["reviewed_rows"],
                "valid_reviewed_count": metrics["valid_reviewed_rows"],
                "precision": metrics["precision"],
                "high_value_rate": metrics["high_value_rate"],
                "noise_rate": metrics["noise_rate"],
                "actionable_rate": metrics["actionable_rate"],
                "launch_rate": metrics["launch_rate"],
                "total_matching_product_count": threshold.get("matching_product_count", ""),
                "eligible_coverage_rate": threshold.get("eligible_coverage_rate", ""),
                "warning": threshold_warning(metrics["valid_reviewed_rows"]),
            }
        )
    return rows


def threshold_candidate_matches_signal(row: dict[str, str], simulation_signal: str) -> bool:
    sample_signal = review_value(row, "sample_signal")
    if simulation_signal == "sub_bsr":
        return sample_signal in {"strong_sub_bsr", "very_strong_sub_bsr"}
    return sample_signal == simulation_signal


def row_matches_threshold(row: dict[str, str], simulation_signal: str, thresholds: str) -> bool:
    if simulation_signal and not threshold_candidate_matches_signal(row, simulation_signal):
        return False
    for condition in [part.strip() for part in thresholds.split(";") if part.strip()]:
        if condition == "previous_source_rank=present":
            if int_value(row.get("previous_source_rank")) is None:
                return False
            continue
        if condition.startswith("pod_relevance="):
            if not pod_mode_matches(row, condition.split("=", 1)[1]):
                return False
            continue
        operator = "<=" if "<=" in condition else ">=" if ">=" in condition else None
        if not operator:
            continue
        field, raw_threshold = [part.strip() for part in condition.split(operator, 1)]
        actual = numeric_for_threshold(row, field)
        expected = float_value(raw_threshold)
        if actual is None or expected is None:
            return False
        if operator == "<=" and actual > expected:
            return False
        if operator == ">=" and actual < expected:
            return False
    return True


def numeric_for_threshold(row: dict[str, str], field: str) -> float | None:
    if field == "source_rank":
        value = rank_value(row)
    elif field == "source_rank_change":
        value = int_value(row.get("source_rank_change"))
    elif field == "source_days_seen":
        value = int_value(row.get("source_days_seen"))
    elif field == "source_observation_count":
        value = int_value(row.get("source_observation_count"))
    elif field == "sub_bsr_rank":
        value = valid_sub_bsr(row)
    else:
        value = float_value(row.get(field, ""))
    return float(value) if value is not None else None


def build_reviewer_agreement(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    review_fields = ["review_label", "pod_validity", "idea_quality", "duplicability", "market_relevance", "research_priority"]
    reviewed = [row for row in rows if has_review_activity(row)]
    by_unit: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in reviewed:
        by_unit[(review_value(row, "marketplace") or "amazon.com", review_value(row, "asin").upper(), review_value(row, "sample_signal"))].append(row)

    rows_out: list[dict[str, str]] = []
    for field in ["all_fields", *review_fields]:
        comparison_count = 0
        agreement_count = 0
        label_pairs: list[tuple[str, str]] = []
        examples = []
        for unit, unit_rows in by_unit.items():
            if len(unit_rows) < 2:
                continue
            for left, right in combinations(unit_rows, 2):
                if field == "all_fields":
                    left_value = tuple(review_value(left, item) for item in review_fields)
                    right_value = tuple(review_value(right, item) for item in review_fields)
                    if not any(left_value) or not any(right_value):
                        continue
                else:
                    left_value = review_value(left, field)
                    right_value = review_value(right, field)
                    if not left_value or not right_value:
                        continue
                    if field == "review_label":
                        label_pairs.append((left_value, right_value))
                comparison_count += 1
                if left_value == right_value:
                    agreement_count += 1
                elif len(examples) < 5:
                    examples.append(f"{'|'.join(unit)}: {left_value} vs {right_value}")
        rows_out.append(
            {
                "row_type": "summary",
                "review_unit": "",
                "field": field,
                "reviewer_count": "",
                "comparison_count": str(comparison_count),
                "agreement_count": str(agreement_count),
                "agreement_rate": nullable_rate(agreement_count, comparison_count),
                "cohens_kappa": format_optional(kappa_for_pairs(label_pairs)) if field == "review_label" else "",
                "values": "; ".join(examples),
                "warning": "" if comparison_count else "no multi-review units",
            }
        )
    for unit, unit_rows in sorted(by_unit.items()):
        if len(unit_rows) < 2:
            continue
        for field in review_fields:
            values = sorted({review_value(row, field) for row in unit_rows if review_value(row, field)})
            if len(values) > 1:
                rows_out.append(
                    {
                        "row_type": "disagreement",
                        "review_unit": "|".join(unit),
                        "field": field,
                        "reviewer_count": str(len({review_value(row, "reviewer") or "missing" for row in unit_rows})),
                        "comparison_count": "",
                        "agreement_count": "",
                        "agreement_rate": "",
                        "cohens_kappa": "",
                        "values": "; ".join(values),
                        "warning": "",
                    }
                )
    return rows_out


def build_recommendations(
    quality_rows: list[dict[str, str]],
    threshold_quality_rows: list[dict[str, str]],
    summary_rows: list[dict[str, str]],
    globally_insufficient: bool,
) -> list[dict[str, str]]:
    quality_by_signal = {row["signal"]: row for row in quality_rows if row["row_type"] == "signal_overall"}
    summary_by_signal = {row.get("signal", ""): row for row in summary_rows}
    recommendations: list[dict[str, str]] = []
    for signal in SIGNAL_NAMES:
        quality = quality_by_signal.get(signal, {})
        current_count = summary_by_signal.get(signal, {}).get("active_signal_count", "")
        reviewed_sample = int_value(quality.get("valid_reviewed_rows")) or 0
        current_precision = quality.get("precision", "")
        current_actionable = quality.get("actionable_rate", "")
        best = best_threshold_candidate(signal, threshold_quality_rows, current_precision, current_count)
        proposed_threshold = PRODUCTION_THRESHOLDS[signal]
        proposed_count = current_count
        proposed_precision = current_precision
        proposed_actionable = current_actionable
        if best:
            proposed_threshold = best["thresholds"]
            proposed_count = best["total_matching_product_count"]
            proposed_precision = best["precision"]
            proposed_actionable = best["actionable_rate"]

        if globally_insufficient or reviewed_sample < MIN_SIGNAL_SAMPLE:
            status = "insufficient_review"
            confidence = "low"
            reasoning = "Review coverage is materially insufficient; production thresholds should not be changed."
        else:
            status, confidence, reasoning = recommendation_status(signal, quality, bool(best))

        recommendations.append(
            {
                "signal": signal,
                "signal_label": SIGNAL_LABELS[signal],
                "status": status,
                "current_production_threshold": PRODUCTION_THRESHOLDS[signal],
                "proposed_threshold": proposed_threshold if status not in {"insufficient_review", "keep"} else "",
                "current_full_data_count": current_count,
                "proposed_full_data_count": proposed_count if status not in {"insufficient_review", "keep"} else "",
                "reviewed_sample_size": str(reviewed_sample),
                "current_precision": current_precision,
                "proposed_precision": proposed_precision if best and status not in {"insufficient_review", "keep"} else "",
                "current_actionable_rate": current_actionable,
                "proposed_actionable_rate": proposed_actionable if best and status not in {"insufficient_review", "keep"} else "",
                "coverage_tradeoff": coverage_tradeoff(current_count, proposed_count) if best and status not in {"insufficient_review", "keep"} else "",
                "reasoning": reasoning,
                "confidence": confidence,
            }
        )
    return recommendations


def best_threshold_candidate(
    signal: str,
    threshold_quality_rows: list[dict[str, str]],
    current_precision: str,
    current_count: str,
) -> dict[str, str] | None:
    simulation_signal = "sub_bsr" if signal in {"strong_sub_bsr", "very_strong_sub_bsr"} else signal
    current_precision_value = float_value(current_precision)
    current_count_value = int_value(current_count) or 0
    viable = []
    for row in threshold_quality_rows:
        if row.get("simulation_signal") != simulation_signal:
            continue
        valid_count = int_value(row.get("valid_reviewed_count")) or 0
        total_count = int_value(row.get("total_matching_product_count")) or 0
        precision = float_value(row.get("precision"))
        if valid_count < MIN_SIGNAL_SAMPLE or precision is None:
            continue
        if total_count < max(20, int(current_count_value * 0.10)):
            continue
        if current_precision_value is not None and precision < current_precision_value + 0.05:
            continue
        viable.append(row)
    if not viable:
        return None
    return sorted(
        viable,
        key=lambda row: (
            float_value(row.get("precision")) or 0,
            float_value(row.get("actionable_rate")) or 0,
            int_value(row.get("total_matching_product_count")) or 0,
        ),
        reverse=True,
    )[0]


def recommendation_status(signal: str, quality: dict[str, str], has_better_threshold: bool) -> tuple[str, str, str]:
    precision = float_value(quality.get("precision"))
    noise = float_value(quality.get("noise_rate"))
    actionable = float_value(quality.get("actionable_rate"))
    sample = int_value(quality.get("valid_reviewed_rows")) or 0
    confidence = "high" if sample >= 30 else "medium" if sample >= 15 else "low"
    if signal == "new_release_watch":
        return (
            "candidate_pool_only",
            confidence,
            "Evaluate as New Release Candidate; broad coverage is useful for a review pool, not a standalone win signal.",
        )
    if signal == "strong_sub_bsr":
        return (
            "supporting_only",
            confidence,
            "Strong Sub-BSR is an ordinal BSR support level and should not be counted as an independent additive confirmation.",
        )
    if signal == "very_strong_sub_bsr":
        return (
            "supporting_only" if (precision is not None and precision < 0.70) else "keep",
            confidence,
            "Very Strong Sub-BSR is the stronger ordinal BSR level; evaluate with source-specific evidence rather than as a separate family.",
        )
    if has_better_threshold and (precision is None or precision < 0.70 or (noise is not None and noise > 0.15)):
        return "tighten", confidence, "A stricter simulated threshold improves reviewed precision without collapsing full-data coverage."
    if precision is not None and precision >= 0.70 and (noise is None or noise <= 0.15) and (actionable is None or actionable >= 0.60):
        return "keep", confidence, "Reviewed sample shows acceptable precision, noise, and actionable rate."
    if "breakout" in signal and precision is not None and precision >= 0.60:
        return "keep", confidence, "Breakout signal is rare but review quality is acceptable; do not retire solely due to low count."
    if precision is not None and precision < 0.35:
        return "retire", confidence, "Reviewed precision is too low for a primary evidence signal."
    if precision is not None and precision < 0.55:
        return "tighten", confidence, "Reviewed precision is weak; use threshold simulations before production changes."
    return "keep", confidence, "No threshold change is recommended from the reviewed evidence."


def coverage_tradeoff(current_count: str, proposed_count: str) -> str:
    current = int_value(current_count)
    proposed = int_value(proposed_count)
    if current is None or proposed is None:
        return ""
    delta = proposed - current
    return f"{delta:+d} products ({nullable_rate(delta, current)})"


def threshold_warning(valid_reviewed_count: str) -> str:
    count = int_value(valid_reviewed_count) or 0
    if count == 0:
        return "no valid reviewed matches"
    if count < MIN_SIGNAL_SAMPLE:
        return f"low sample: {count} valid matches"
    return ""


def has_review_activity(row: dict[str, str]) -> bool:
    return any(review_value(row, column) for column in REVIEW_COLUMNS)


def is_valid_precision_row(row: dict[str, str]) -> bool:
    value = review_value(row, "review_label")
    return value in ALLOWED_VALUES["review_label"] and value != "insufficient_data"


def review_value(row: dict[str, str], column: str) -> str:
    return normalize_text(row.get(column, "")).lower()


def pod_mode_matches(row: dict[str, str], mode: str) -> bool:
    relevance = review_value(row, "pod_relevance") or "unknown"
    if mode == "high_only":
        return relevance == "high"
    if mode == "high_medium":
        return relevance in {"high", "medium"}
    return relevance != "low"


def dimension_value(row: dict[str, str], dimension: str) -> str:
    if dimension == "sample_bucket":
        return normalize_text(row.get("sample_bucket", "")) or "Unknown"
    if dimension == "pod_relevance":
        return normalize_text(row.get("pod_relevance", "")) or "unknown"
    if dimension == "product_type":
        return product_type(row)
    if dimension == "seller":
        return normalize_text(row.get("seller", "")) or "Unknown"
    if dimension == "source_category":
        return normalize_text(row.get("category", "")) or "Unknown"
    if dimension == "sub_bsr_category":
        return normalize_text(row.get("sub_bsr_category", "")) or "Unknown"
    if dimension == "source_rank_band":
        return band(rank_value(row), [(10, "1-10"), (30, "11-30"), (50, "31-50"), (100, "51-100")], "101+")
    if dimension == "source_rank_change_band":
        value = int_value(row.get("source_rank_change"))
        if value is None:
            return "missing"
        if value < 0:
            return "falling"
        if value == 0:
            return "flat"
        return band(value, [(9, "1-9"), (29, "10-29")], "30+")
    if dimension == "days_seen_band":
        return band(int_value(row.get("source_days_seen")), [(3, "0-3"), (7, "4-7"), (14, "8-14")], "15+")
    if dimension == "review_count_band":
        value = review_count(row)
        if value == 0:
            return "0"
        return band(value, [(10, "1-10"), (50, "11-50"), (250, "51-250")], "251+")
    if dimension == "price_band":
        value = price_value(row)
        if value is None:
            return "missing"
        if value < 10:
            return "<10"
        if value < 15:
            return "10-14.99"
        if value < 20:
            return "15-19.99"
        if value < 30:
            return "20-29.99"
        return "30+"
    if dimension == "bsr_band":
        return band(valid_sub_bsr(row), [(100, "<=100"), (1000, "101-1000"), (5000, "1001-5000"), (10000, "5001-10000")], ">10000")
    if dimension == "reviewer":
        return normalize_text(row.get("reviewer", "")) or "missing"
    return "Unknown"


def band(value: int | float | None, thresholds: list[tuple[int, str]], final_label: str) -> str:
    if value is None:
        return "missing"
    previous = 0
    for threshold, label in thresholds:
        if value <= threshold:
            return label
        previous = threshold
    return final_label


def nullable_rate(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return ""
    return f"{numerator / denominator:.4f}"


def wilson_interval(successes: int, total: int) -> tuple[str, str]:
    if total <= 0:
        return "", ""
    z = 1.96
    p = successes / total
    denominator = 1 + (z * z / total)
    center = (p + (z * z / (2 * total))) / denominator
    margin = (z * sqrt((p * (1 - p) / total) + (z * z / (4 * total * total)))) / denominator
    return f"{max(0, center - margin):.4f}", f"{min(1, center + margin):.4f}"


def format_optional(value: float | None) -> str:
    if value is None:
        return ""
    return format_number(value)


def kappa_for_pairs(pairs: list[tuple[str, str]]) -> float | None:
    if len(pairs) < 5:
        return None
    observed = sum(1 for left, right in pairs if left == right) / len(pairs)
    labels = [label for pair in pairs for label in pair]
    counts = Counter(labels)
    total = len(labels)
    expected = sum((count / total) ** 2 for count in counts.values())
    if expected >= 1:
        return None
    return (observed - expected) / (1 - expected)


def render_review_analysis_html(
    review_summary_rows: list[dict[str, str]],
    quality_rows: list[dict[str, str]],
    threshold_quality_rows: list[dict[str, str]],
    agreement_rows: list[dict[str, str]],
    recommendations: list[dict[str, str]],
) -> str:
    signal_rows = [row for row in quality_rows if row["row_type"] == "signal_overall"]
    leaderboard = sorted(
        signal_rows,
        key=lambda row: (float_value(row.get("precision")) if float_value(row.get("precision")) is not None else -1),
        reverse=True,
    )
    top_thresholds = sorted(
        threshold_quality_rows,
        key=lambda row: (
            float_value(row.get("precision")) if float_value(row.get("precision")) is not None else -1,
            int_value(row.get("total_matching_product_count")) or 0,
        ),
        reverse=True,
    )[:40]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Evidence Human Review Analysis</title>
  <style>
    body {{ margin: 0; font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f6f7f9; color: #172033; }}
    main {{ max-width: 1360px; margin: 0 auto; padding: 24px; }}
    h1 {{ font-size: 28px; margin: 0 0 8px; }}
    h2 {{ font-size: 20px; margin: 28px 0 10px; }}
    p {{ color: #4c5a6d; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #e3e8ef; font-size: 13px; }}
    th, td {{ padding: 7px 8px; border-bottom: 1px solid #e3e8ef; text-align: left; vertical-align: top; }}
    th {{ background: #fbfcfd; color: #65758b; font-size: 12px; text-transform: uppercase; }}
    .note {{ background: #fff; border: 1px solid #e3e8ef; border-radius: 8px; padding: 12px; }}
  </style>
</head>
<body>
<main>
  <h1>Evidence Human Review Analysis</h1>
  <p>Static review-quality report. Production thresholds are not changed by this analysis.</p>
  <section class="note">
    <strong>Methodology and limitations</strong>
    <p>Blank review rows are unreviewed, not negative. <code>insufficient_data</code> rows are excluded from precision denominators. BSR signals are treated as ordinal support levels, not independent additive confirmations.</p>
  </section>
  <h2>Review Completion Status</h2>
  {_html_table(review_summary_rows, ["metric", "value", "details"])}
  <h2>Signal Quality Leaderboard</h2>
  {_html_table(leaderboard, ["signal_label", "reviewed_rows", "valid_reviewed_rows", "precision", "precision_ci_low", "precision_ci_high", "noise_rate", "actionable_rate", "warning"])}
  <h2>Precision Versus Coverage</h2>
  {_html_table(recommendations, ["signal_label", "current_precision", "current_full_data_count", "reviewed_sample_size", "current_actionable_rate", "status"])}
  <h2>Threshold Comparisons</h2>
  {_html_table(top_thresholds, ["simulation_signal", "thresholds", "valid_reviewed_count", "precision", "noise_rate", "actionable_rate", "total_matching_product_count", "eligible_coverage_rate", "warning"])}
  <h2>Reviewer Agreement</h2>
  {_html_table(agreement_rows, ["row_type", "field", "comparison_count", "agreement_rate", "cohens_kappa", "values", "warning"])}
  <h2>Recommendation Cards</h2>
  {_html_table(recommendations, ["signal_label", "status", "current_production_threshold", "proposed_threshold", "reviewed_sample_size", "current_precision", "proposed_precision", "coverage_tradeoff", "confidence", "reasoning"])}
  <h2>Low-Sample Warnings</h2>
  {_html_table([row for row in leaderboard if row.get("warning")], ["signal_label", "valid_reviewed_rows", "warning"])}
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
