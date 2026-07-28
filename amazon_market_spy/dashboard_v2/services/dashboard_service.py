from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from ...evidence import OBSERVATION_EVIDENCE_BOOLEAN_FIELDS, PRODUCT_EVIDENCE_FIELDS
from ...reporting import read_csv


REQUIRED_TOP_LEVEL_KEYS = {"morning_brief", "ideas", "products", "competitors", "market"}
CSV_SOURCE_FILES = (
    "historical_comparison.csv",
    "priority_board.csv",
    "lark_trend_alerts.csv",
    "latest_products.csv",
    "seller_intelligence.csv",
    "niche_intelligence.csv",
    "product_trends.csv",
)
PRODUCT_EVIDENCE_BOOLEAN_FIELDS = (
    "seller_evidence_leader",
    "seller_evidence_mover",
    "seller_evidence_new_push",
    "best_seller_evidence_winner",
    "best_seller_evidence_breakout",
    "best_seller_evidence_stable",
    "new_release_evidence_rising",
    "new_release_evidence_breakout",
    "new_release_evidence_watch",
    "bsr_evidence_available",
    "bsr_evidence_strong",
    "bsr_evidence_very_strong",
)


class DashboardDataError(RuntimeError):
    """Base error for Dashboard V2 presentation data loading."""


class DashboardDataMissing(DashboardDataError):
    """Raised when no presentation source is available."""


class DashboardDataValidationError(DashboardDataError):
    """Raised when a presentation source cannot be normalized safely."""


class DashboardService:
    """Load and normalize existing analytics artifacts for Dashboard V2 pages."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = Path(output_dir)
        self._cache: dict[str, Any] | None = None

    @classmethod
    def for_v2_output(cls, output_dir: Path) -> "DashboardService":
        output_dir = Path(output_dir)
        source_dir = output_dir.parent if output_dir.name.lower() == "v2" else output_dir
        return cls(source_dir)

    def load(self) -> dict[str, Any]:
        return self.cache()

    def cache(self) -> dict[str, Any]:
        if self._cache is None:
            data = self._load_source()
            self.validate(data)
            self._cache = data
        return self._cache

    def validate(self, data: dict[str, Any] | None = None) -> None:
        payload = self._cache if data is None else data
        if not isinstance(payload, dict):
            raise DashboardDataValidationError("Dashboard V2 presentation data must be a JSON object.")

        missing = REQUIRED_TOP_LEVEL_KEYS.difference(payload)
        if missing:
            missing_list = ", ".join(sorted(missing))
            raise DashboardDataValidationError(f"Dashboard V2 presentation data is missing: {missing_list}.")

        if not isinstance(payload["morning_brief"], dict):
            raise DashboardDataValidationError("Dashboard V2 summary must be an object.")
        for key in ("ideas", "products", "competitors"):
            if not isinstance(payload[key], list):
                raise DashboardDataValidationError(f"Dashboard V2 {key} must be a list.")
        if not isinstance(payload["market"], dict):
            raise DashboardDataValidationError("Dashboard V2 market must be an object.")

        summary = payload["morning_brief"]
        for key in ("date_label", "kpis", "top_ideas", "biggest_movers", "competitor_alerts", "emerging_ideas"):
            if key not in summary:
                raise DashboardDataValidationError(f"Dashboard V2 summary is missing: {key}.")
        if not isinstance(summary["kpis"], list):
            raise DashboardDataValidationError("Dashboard V2 summary kpis must be a list.")

        market = payload["market"]
        for key in ("segments", "distribution", "growth", "top_ideas"):
            if key not in market:
                raise DashboardDataValidationError(f"Dashboard V2 market is missing: {key}.")
            if not isinstance(market[key], list):
                raise DashboardDataValidationError(f"Dashboard V2 market {key} must be a list.")

    def get_summary(self) -> dict[str, Any]:
        return self.cache()["morning_brief"]

    def get_products(self) -> list[dict[str, Any]]:
        return self.cache()["products"]

    def get_ideas(self) -> list[dict[str, Any]]:
        return self.cache()["ideas"]

    def get_competitors(self) -> list[dict[str, Any]]:
        return self.cache()["competitors"]

    def get_market(self) -> dict[str, Any]:
        return self.cache()["market"]

    def _load_source(self) -> dict[str, Any]:
        dashboard_json = self.output_dir / "dashboard.json"
        if dashboard_json.exists():
            return self._load_dashboard_json(dashboard_json)

        if not any((self.output_dir / filename).exists() for filename in CSV_SOURCE_FILES):
            raise DashboardDataMissing(
                f"Dashboard V2 could not find dashboard.json or analytics CSV artifacts in {self.output_dir}."
            )
        return self._load_csv_adapter()

    def _load_dashboard_json(self, path: Path) -> dict[str, Any]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise DashboardDataValidationError(f"Dashboard V2 dashboard.json is not valid JSON: {exc.msg}.") from exc
        except OSError as exc:
            raise DashboardDataError(f"Dashboard V2 could not read {path}: {exc}") from exc
        if not isinstance(payload, dict):
            raise DashboardDataValidationError("Dashboard V2 dashboard.json must contain an object.")
        return payload

    def _load_csv_adapter(self) -> dict[str, Any]:
        priority_rows = self._read_csv("priority_board.csv")
        lark_rows = self._read_csv("lark_trend_alerts.csv")
        latest_rows = self._read_csv("latest_products.csv")
        seller_rows = self._read_csv("seller_intelligence.csv")
        niche_rows = self._read_csv("niche_intelligence.csv")
        trend_rows = self._read_csv("product_trends.csv")
        historical_rows = self._read_csv("historical_comparison.csv")

        lark_by_asin = _rows_by_asin(lark_rows)
        priority_by_asin = _rows_by_asin(priority_rows)
        latest_by_asin = _rows_by_asin(latest_rows)
        trend_by_asin = _rows_by_asin(trend_rows)
        historical_by_asin = _rows_grouped_by_asin(historical_rows)
        source_products = priority_rows or lark_rows or latest_rows
        products = [
            self._product_from_row(row, priority_by_asin, lark_by_asin, latest_by_asin, trend_by_asin, historical_by_asin)
            for row in source_products
        ]
        product_explorer_products = [
            self._product_from_row(row, priority_by_asin, lark_by_asin, latest_by_asin, trend_by_asin, historical_by_asin)
            for row in _product_explorer_source_rows(latest_rows, priority_rows, lark_rows)
        ]
        ideas = [self._idea_from_row(row) for row in niche_rows[:80]]
        competitors = [self._competitor_from_row(row) for row in seller_rows[:80]]

        return {
            "morning_brief": self._summary(priority_rows, seller_rows, niche_rows),
            "ideas": ideas,
            "products": products,
            "product_explorer_products": product_explorer_products,
            "competitors": competitors,
            "market": self._market(niche_rows),
            "dataset_info": self._dataset_info(historical_rows, products),
        }

    def _read_csv(self, filename: str) -> list[dict[str, str]]:
        path = self.output_dir / filename
        if not path.exists():
            return []
        try:
            return read_csv(path)
        except OSError as exc:
            raise DashboardDataError(f"Dashboard V2 could not read {path}: {exc}") from exc

    def _summary(
        self,
        priority_rows: list[dict[str, str]],
        seller_rows: list[dict[str, str]],
        niche_rows: list[dict[str, str]],
    ) -> dict[str, Any]:
        new_winners = [row for row in priority_rows if _has_badge(row, "Top Winner") or _has_badge(row, "New Breakout")]
        fast_rising = [row for row in priority_rows if _has_badge(row, "Fast Mover")]
        competitor_alerts = [
            row for row in seller_rows if _to_int(row.get("new_wins")) > 0 or _to_int(row.get("rising_products")) > 0
        ]
        emerging_ideas = [row for row in niche_rows if _to_int(row.get("opportunities")) > 0]

        return {
            "date_label": self._date_label(niche_rows, priority_rows),
            "kpis": [
                {
                    "label": "New Winners",
                    "value": str(len(new_winners)),
                    "tone": "winner",
                    "caption": "From priority board",
                },
                {
                    "label": "Fast Rising",
                    "value": str(len(fast_rising)),
                    "tone": "rising",
                    "caption": "From priority board",
                },
                {
                    "label": "Competitor Alerts",
                    "value": str(len(competitor_alerts)),
                    "tone": "alert",
                    "caption": "From seller intelligence",
                },
                {
                    "label": "Emerging Ideas",
                    "value": str(len(emerging_ideas)),
                    "tone": "idea",
                    "caption": "From niche intelligence",
                },
            ],
            "top_ideas": [self._summary_idea(row) for row in niche_rows[:4]],
            "biggest_movers": [self._summary_product(row) for row in fast_rising[:4]],
            "competitor_alerts": [self._summary_competitor(row) for row in competitor_alerts[:4]],
            "emerging_ideas": [self._summary_idea(row) for row in emerging_ideas[:4]],
        }

    def _date_label(self, niche_rows: list[dict[str, str]], priority_rows: list[dict[str, str]]) -> str:
        for row in [*niche_rows, *priority_rows]:
            value = _first_text(row, "date", "first_seen")
            if value:
                return value[:10]
        candidates = [self.output_dir / filename for filename in CSV_SOURCE_FILES if (self.output_dir / filename).exists()]
        if not candidates:
            return "No data"
        latest = max(path.stat().st_mtime for path in candidates)
        return datetime.fromtimestamp(latest).date().isoformat()

    def _summary_idea(self, row: dict[str, str]) -> dict[str, str]:
        score = _first_text(row, "niche_momentum_score", "max_opportunity_score", default="0")
        growth = _first_text(row, "rising_products", "best_rank_change", default="0")
        products = _first_text(row, "products_tracked", "pod_products", default="0")
        top_seller = _first_text(row, "top_seller", default="Top seller unavailable")
        return {
            "title": _first_text(row, "niche", "niche_group", default="Untitled Idea"),
            "meta": f"{products} products - {top_seller}",
            "signal": f"Score {score}",
            "score": score,
            "growth": _format_positive(growth),
            "competition": _competition_label(row),
            "tone": _tone_from_score(score),
        }

    def _summary_product(self, row: dict[str, str]) -> dict[str, str]:
        return {
            "title": _first_text(row, "title", default="Untitled Product"),
            "meta": f"Rank {_format_positive(_first_text(row, 'display_rank_change', 'rank_change', default='0'))}",
            "signal": _first_text(row, "badges", "primary_bucket", default="Tracked"),
            "seller": _seller_name(row),
            "growth": _format_positive(_first_text(row, "display_rank_change", "rank_change", default="0")),
            "tone": _tone_from_badges(row),
        }

    def _summary_competitor(self, row: dict[str, str]) -> dict[str, str]:
        rising = _first_text(row, "rising_products", default="0")
        new_wins = _first_text(row, "new_wins", default="0")
        return {
            "title": _seller_name(row),
            "meta": f"{new_wins} new wins - {rising} rising",
            "signal": f"{_first_text(row, 'products_tracked', default='0')} products",
            "tone": "alert" if _to_int(new_wins) else "rising",
        }

    def _product_from_row(
        self,
        row: dict[str, str],
        priority_by_asin: dict[str, dict[str, str]],
        lark_by_asin: dict[str, dict[str, str]],
        latest_by_asin: dict[str, dict[str, str]],
        trend_by_asin: dict[str, dict[str, str]],
        historical_by_asin: dict[str, list[dict[str, str]]],
    ) -> dict[str, Any]:
        asin = row.get("asin", "").strip().upper()
        merged = _merge_row(
            row,
            priority_by_asin.get(asin, {}),
            lark_by_asin.get(asin, {}),
            latest_by_asin.get(asin, {}),
            trend_by_asin.get(asin, {}),
        )
        evidence_rows = historical_by_asin.get(asin) or ([merged] if _has_source_context(merged) else [])
        title = _first_text(merged, "title", "raw_title", default=asin or "Untitled Product")
        product_type = _product_type(merged)
        idea = _first_text(merged, "niche_primary", "niche", "category", default="Uncategorized")
        score = _first_text(merged, "opportunity_score", "validation_score", "decision_score", "pod_momentum_score", default="0")
        growth = _format_positive(_first_text(merged, "display_rank_change", "rank_change", "best_mover_rank_change", default="0"))
        badges = _badges(merged)
        product_url = _first_text(merged, "product_url", default="")
        seller_url = _first_text(merged, "seller_url", default="")
        status = _first_text(merged, "primary_bucket", "badges", "badge", "alert_type", "source_type", default="Tracked")
        return {
            "id": asin or title,
            "asin": asin,
            "date": _first_text(merged, "date", "fetched_at", default=""),
            "title": title,
            "seller": _seller_name(merged),
            "idea": idea,
            "score": score,
            "winner_score": _to_int(score),
            "display_strength": _to_optional_int(_first_text(merged, "display_strength", default="")),
            "rank_strength": _to_optional_int(_first_text(merged, "rank_strength", default="")),
            "display_momentum": _to_optional_int(_first_text(merged, "display_momentum", default="")),
            "rank_momentum": _to_optional_int(_first_text(merged, "rank_momentum", default="")),
            "validation_score": _to_optional_int(_first_text(merged, "validation_score", default="")),
            "momentum_score": _to_optional_int(_first_text(merged, "momentum_score", default="")),
            "stability_score": _to_optional_int(_first_text(merged, "stability_score", default="")),
            "freshness_score": _to_optional_int(_first_text(merged, "freshness_score", default="")),
            "opportunity_score": _to_optional_int(_first_text(merged, "opportunity_score", default="")),
            "validation_confidence": _to_optional_int(_first_text(merged, "validation_confidence", default="")),
            "momentum_confidence": _to_optional_int(_first_text(merged, "momentum_confidence", default="")),
            "stability_confidence": _to_optional_int(_first_text(merged, "stability_confidence", default="")),
            "research_segment": _first_text(merged, "research_segment", default=""),
            "score_reason": _first_text(merged, "score_reason", default=""),
            "growth": growth,
            "growth_value": _to_int(growth),
            "reviews": _first_text(merged, "review_count", default="-"),
            "review_count": _to_optional_int(_first_text(merged, "review_count", default="")),
            "review_rating": _to_optional_float(_first_text(merged, "review_rating", "rating", default="")),
            "price": _format_price(_first_text(merged, "latest_price", "price", default="")),
            "price_value": _to_optional_float(_first_text(merged, "latest_price", "price", default="")),
            "bsr": _format_rank(_first_text(merged, "sub_bsr_rank", "primary_bsr_rank", "bsr_rank", default="")),
            "source": _first_text(merged, "source_name", "primary_bucket", "source_type", default="Tracked"),
            "source_url": _first_text(merged, "source_url", default=""),
            "source_type": _first_text(merged, "source_type", default="unknown"),
            "source_id": _first_text(merged, "source_id", default=""),
            "source_rank": _to_optional_int(_first_text(merged, "source_rank", "display_rank", "today_rank", "rank", default="")),
            "previous_source_rank": _to_optional_int(_first_text(merged, "previous_source_rank", "previous_display_rank", "previous_rank", default="")),
            "source_rank_change": _to_optional_int(_first_text(merged, "source_rank_change", "display_rank_change", "rank_change", default="")),
            "source_observation_count": _to_optional_int(_first_text(merged, "source_observation_count", "historical_observations", default="")),
            "source_days_seen": _to_optional_int(_first_text(merged, "source_days_seen", "days_seen", default="")),
            "marketplace": _first_text(merged, "marketplace", default=""),
            "category_id": _first_text(merged, "category_id", default=""),
            "category_name": _first_text(merged, "category_name", "category", default=""),
            "primary_bsr_rank": _to_optional_int(_first_text(merged, "primary_bsr_rank", "bsr_rank", default="")),
            "primary_bsr_category": _first_text(merged, "primary_bsr_category", "bsr_category", default=""),
            "sub_bsr_rank": _to_optional_int(_first_text(merged, "sub_bsr_rank", default="")),
            "sub_bsr_category": _first_text(merged, "sub_bsr_category", default=""),
            "product_type": product_type,
            "is_pod": _first_text(merged, "is_pod", default=""),
            "production_model": _first_text(merged, "production_model", default=""),
            "recipient": _first_text(merged, "recipient", default="Unknown"),
            "theme": _first_text(merged, "theme", default="Unknown"),
            "occasion": _first_text(merged, "occasion", default="Unknown"),
            "status": status,
            "badges": badges,
            **_evidence_payload(merged, evidence_rows),
            "is_winner": _is_winner(merged),
            "is_rising": _is_rising(merged),
            "is_new_launch": _is_new_launch(merged),
            "image_label": _image_label(idea, asin),
            "image_url": _first_text(merged, "image_url", default=""),
            "product_url": product_url,
            "amazon_url": product_url,
            "seller_url": seller_url,
            "tone": _tone_from_badges(merged),
        }

    def _idea_from_row(self, row: dict[str, str]) -> dict[str, Any]:
        score = _first_text(row, "niche_momentum_score", "max_opportunity_score", default="0")
        growth = _format_positive(_first_text(row, "rising_products", "best_rank_change", default="0"))
        return {
            "idea": _first_text(row, "niche", "niche_group", default="Untitled Idea"),
            "products": _first_text(row, "products_tracked", "pod_products", default="0"),
            "sellers": _first_text(row, "seller_count", default="-"),
            "growth": growth,
            "competition": _competition_label(row),
            "winner_score": _to_int(score),
            "top_product": _first_text(row, "top_product_title", "best_subcategory_product", default="-"),
            "top_seller": _first_text(row, "top_seller", default="-"),
            "tone": _tone_from_score(score),
        }

    def _competitor_from_row(self, row: dict[str, str]) -> dict[str, Any]:
        return {
            "seller": _seller_name(row),
            "products": _first_text(row, "products_tracked", default="0"),
            "winners": _first_text(row, "pod_opportunities", "new_wins", default="0"),
            "fast_rising": _first_text(row, "rising_products", default="0"),
            "new_launches": _first_text(row, "new_wins", default="0"),
            "last_activity": "Latest report",
        }

    def _market(self, niche_rows: list[dict[str, str]]) -> dict[str, Any]:
        return {
            "segments": ["Recipient", "Occasion", "Theme", "Product Type"],
            "distribution": [
                {
                    "label": _first_text(row, "niche", default="Unknown"),
                    "value": _to_int(_first_text(row, "products_tracked", default="0")),
                    "tone": "stable",
                }
                for row in niche_rows[:8]
            ],
            "growth": [
                {
                    "label": _first_text(row, "niche", default="Unknown"),
                    "value": _to_int(_first_text(row, "rising_products", "best_rank_change", default="0")),
                    "tone": "rising",
                }
                for row in niche_rows[:8]
            ],
            "top_ideas": [
                {
                    "label": _first_text(row, "niche", default="Unknown"),
                    "value": _to_int(_first_text(row, "niche_momentum_score", "max_opportunity_score", default="0")),
                    "tone": _tone_from_score(_first_text(row, "niche_momentum_score", "max_opportunity_score", default="0")),
                }
                for row in niche_rows[:8]
            ],
        }

    def _dataset_info(self, historical_rows: list[dict[str, str]], products: list[dict[str, Any]]) -> dict[str, Any]:
        product_keys = {
            (_first_text(row, "marketplace", default="amazon.com"), row.get("asin", "").strip().upper())
            for row in historical_rows
            if row.get("asin", "").strip()
        }
        source_types = Counter(_first_text(row, "source_type", default="unknown") for row in historical_rows)
        source_ids_by_type: dict[str, set[str]] = {}
        for row in historical_rows:
            source_type = _first_text(row, "source_type", default="unknown")
            source_id = _first_text(row, "source_id", "source_name", default="")
            if source_id:
                source_ids_by_type.setdefault(source_type, set()).add(source_id)
        marketplace_values = {
            _first_text(row, "marketplace", default="amazon.com")
            for row in historical_rows
            if _first_text(row, "marketplace", default="amazon.com")
        }
        product_source_family_counts = Counter(str(product.get("evidence_source_family_count", 0) or 0) for product in products)
        calibration = self._calibration_status()
        return {
            "status": "Ready" if products or historical_rows else "Empty dataset",
            "generated_at": datetime.now().replace(microsecond=0).isoformat(sep=" "),
            "dashboard_version": "Dashboard V2",
            "analytics_freeze_note": "Dashboard evidence reflects the current production evidence rules. Decision scoring and threshold recommendations are not active.",
            "total_unique_products": len(product_keys) if product_keys else len(products),
            "presentation_products": len(products),
            "source_aware_observations": len(historical_rows),
            "marketplace_count": len(marketplace_values),
            "marketplaces": sorted(marketplace_values),
            "source_type_counts": dict(source_types),
            "seller_source_count": len(source_ids_by_type.get("seller", set())),
            "best_seller_source_count": len(source_ids_by_type.get("category_best_seller", set())),
            "new_release_source_count": len(source_ids_by_type.get("category_new_release", set())),
            "products_with_valid_bsr": sum(1 for product in products if _to_optional_int(product.get("bsr_evidence_best_sub_bsr")) is not None or _to_optional_int(product.get("sub_bsr_rank")) is not None),
            "source_family_product_counts": dict(product_source_family_counts),
            "last_crawl_timestamp": self._latest_timestamp(historical_rows, products),
            **calibration,
        }

    def _latest_timestamp(self, historical_rows: list[dict[str, str]], products: list[dict[str, Any]]) -> str:
        for row in sorted(historical_rows, key=lambda item: _first_text(item, "fetched_at", "date", default=""), reverse=True):
            value = _first_text(row, "fetched_at", "date", default="")
            if value:
                return value
        for product in sorted(products, key=lambda item: str(item.get("date", "")), reverse=True):
            value = str(product.get("date", "") or "")
            if value:
                return value
        return "Unknown"

    def _calibration_status(self) -> dict[str, Any]:
        summary_path = self.output_dir / "evidence_human_review_summary.csv"
        if not summary_path.exists():
            return {
                "calibration_report_exists": False,
                "calibration_status": "Human Review: unavailable",
                "calibration_reviewed_rows": 0,
                "calibration_total_rows": 0,
                "calibration_mode": "Unavailable",
            }
        rows = read_csv(summary_path)
        metrics = {row.get("metric", ""): row.get("value", "") for row in rows}
        reviewed = _to_int(metrics.get("reviewed_rows", "0"))
        total = _to_int(metrics.get("total_rows", "0"))
        mode = metrics.get("recommendation_mode", "diagnostic_only") or "diagnostic_only"
        mode_label = "Diagnostic Only" if mode == "diagnostic_only" else "Recommendation Ready"
        return {
            "calibration_report_exists": True,
            "calibration_status": f"Human Review: {reviewed} / {total} completed",
            "calibration_reviewed_rows": reviewed,
            "calibration_total_rows": total,
            "calibration_mode": mode_label,
        }


def _rows_by_asin(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row["asin"].strip().upper(): row for row in rows if row.get("asin", "").strip()}


def _rows_grouped_by_asin(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        asin = row.get("asin", "").strip().upper()
        if not asin:
            continue
        grouped.setdefault(asin, []).append(row)
    return grouped


def _product_explorer_source_rows(
    latest_rows: list[dict[str, str]],
    priority_rows: list[dict[str, str]],
    lark_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    if latest_rows:
        rows = list(latest_rows)
        seen = {_product_identity(row) for row in rows}
        for fallback_row in [*priority_rows, *lark_rows]:
            identity = _product_identity(fallback_row)
            if identity and identity not in seen:
                rows.append(fallback_row)
                seen.add(identity)
        return rows
    return priority_rows or lark_rows


def _product_identity(row: dict[str, str]) -> str:
    asin = str(row.get("asin", "") or "").strip().upper()
    if asin:
        return f"asin:{asin}"
    product_url = str(row.get("product_url", "") or row.get("amazon_url", "") or "").strip().lower()
    if product_url:
        return f"url:{product_url}"
    title = str(row.get("title", "") or row.get("raw_title", "") or "").strip().lower()
    seller = _seller_name(row).strip().lower()
    return f"title:{title}|seller:{seller}" if title else ""


def _evidence_payload(row: dict[str, str], evidence_rows: list[dict[str, str]]) -> dict[str, Any]:
    source_details = _source_details(evidence_rows)
    payload: dict[str, Any] = {
        "pod_relevance": _first_text(row, "pod_relevance", default="unknown"),
        "pod_relevance_reasons": _split_values(_first_text(row, "pod_relevance_reasons", default="")),
        "evidence_labels": _split_values(_first_text(row, "evidence_labels", default="")),
        "evidence_count": _to_optional_int(_first_text(row, "evidence_count", default="0")) or 0,
        "evidence_reasons": _split_values(_first_text(row, "evidence_reasons", default="")),
        "source_details": source_details,
        "evidence_states": _evidence_states(row, source_details),
    }
    for field in OBSERVATION_EVIDENCE_BOOLEAN_FIELDS:
        payload[field] = _truthy(_first_text(row, field, default="false"))
    for field in PRODUCT_EVIDENCE_FIELDS:
        value = _first_text(row, field, default="")
        if field in PRODUCT_EVIDENCE_BOOLEAN_FIELDS:
            payload[field] = _truthy(value)
        elif field.endswith("_count") or field.endswith("_rank") or field == "bsr_evidence_best_sub_bsr":
            payload[field] = _to_optional_int(value)
        elif field == "evidence_source_families":
            payload[field] = _split_values(value)
        else:
            payload[field] = value
    return payload


def _source_details(rows: list[dict[str, str]]) -> dict[str, list[dict[str, Any]]]:
    details: dict[str, list[dict[str, Any]]] = {"seller": [], "best_seller": [], "new_release": [], "bsr": []}
    for row in rows:
        source_type = _first_text(row, "source_type", default="unknown")
        family = {
            "seller": "seller",
            "category_best_seller": "best_seller",
            "category_new_release": "new_release",
        }.get(source_type)
        detail = _source_detail(row)
        if family:
            details[family].append(detail)
        if _to_optional_int(_first_text(row, "sub_bsr_rank", "primary_bsr_rank", "bsr_rank", default="")) is not None:
            details["bsr"].append(detail)
    return details


def _source_detail(row: dict[str, str]) -> dict[str, Any]:
    return {
        "source_name": _first_text(row, "source_name", default="Unknown source"),
        "source_type": _first_text(row, "source_type", default="unknown"),
        "source_id": _first_text(row, "source_id", default=""),
        "marketplace": _first_text(row, "marketplace", default="amazon.com"),
        "source_rank": _to_optional_int(_first_text(row, "source_rank", "today_rank", "display_rank", "rank", default="")),
        "previous_source_rank": _to_optional_int(_first_text(row, "previous_source_rank", "previous_rank", default="")),
        "source_rank_change": _to_optional_int(_first_text(row, "source_rank_change", "rank_change_vs_previous_seen", default="")),
        "source_days_seen": _to_optional_int(_first_text(row, "source_days_seen", "days_seen", default="")),
        "source_observation_count": _to_optional_int(_first_text(row, "source_observation_count", "historical_observations", default="")),
        "category_name": _first_text(row, "category_name", "category", default=""),
        "category_id": _first_text(row, "category_id", default=""),
        "primary_bsr_rank": _to_optional_int(_first_text(row, "primary_bsr_rank", "bsr_rank", default="")),
        "primary_bsr_category": _first_text(row, "primary_bsr_category", "bsr_category", default=""),
        "sub_bsr_rank": _to_optional_int(_first_text(row, "sub_bsr_rank", default="")),
        "sub_bsr_category": _first_text(row, "sub_bsr_category", default=""),
        "evidence_labels": _split_values(_first_text(row, "evidence_labels", default="")),
        "evidence_reasons": _split_values(_first_text(row, "evidence_reasons", default="")),
        **{field: _truthy(_first_text(row, field, default="false")) for field in OBSERVATION_EVIDENCE_BOOLEAN_FIELDS},
    }


def _evidence_states(row: dict[str, str], source_details: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, str]]:
    return {
        "seller": _family_states(
            _family_has_data(row, source_details, "seller", "seller_evidence_source_count"),
            row,
            {
                "leader": "seller_evidence_leader",
                "mover": "seller_evidence_mover",
                "new_push": "seller_evidence_new_push",
            },
        ),
        "best_seller": _family_states(
            _family_has_data(row, source_details, "best_seller", "best_seller_evidence_source_count"),
            row,
            {
                "winner": "best_seller_evidence_winner",
                "breakout": "best_seller_evidence_breakout",
                "stable": "best_seller_evidence_stable",
            },
        ),
        "new_release": _family_states(
            _family_has_data(row, source_details, "new_release", "new_release_evidence_source_count"),
            row,
            {
                "rising": "new_release_evidence_rising",
                "breakout": "new_release_evidence_breakout",
                "candidate": "new_release_evidence_watch",
            },
        ),
        "bsr": _family_states(
            _bsr_has_data(row, source_details),
            row,
            {
                "strong": "bsr_evidence_strong",
                "very_strong": "bsr_evidence_very_strong",
            },
        ),
    }


def _family_states(has_data: bool, row: dict[str, str], field_map: dict[str, str]) -> dict[str, str]:
    if not has_data:
        return {label: "no_data" for label in field_map}
    return {label: "true" if _truthy(_first_text(row, field, default="false")) else "false" for label, field in field_map.items()}


def _family_has_data(
    row: dict[str, str],
    source_details: dict[str, list[dict[str, Any]]],
    family: str,
    count_field: str,
) -> bool:
    source_count = _to_optional_int(_first_text(row, count_field, default=""))
    return bool(source_count and source_count > 0) or bool(source_details.get(family))


def _bsr_has_data(row: dict[str, str], source_details: dict[str, list[dict[str, Any]]]) -> bool:
    return (
        _to_optional_int(_first_text(row, "bsr_evidence_best_sub_bsr", "sub_bsr_rank", "primary_bsr_rank", default="")) is not None
        or bool(source_details.get("bsr"))
    )


def _has_source_context(row: dict[str, str]) -> bool:
    return bool(_first_text(row, "source_type", "source_rank", "source_name", "sub_bsr_rank", "primary_bsr_rank", default=""))


def _merge_row(primary: dict[str, str], *fallbacks: dict[str, str]) -> dict[str, str]:
    merged = dict(primary)
    for fallback in fallbacks:
        for key, value in fallback.items():
            if not str(merged.get(key, "") or "").strip() and str(value or "").strip():
                merged[key] = value
    return merged


def _first_text(row: dict[str, str], *keys: str, default: str = "") -> str:
    for key in keys:
        value = str(row.get(key, "") or "").strip()
        if value:
            return value
    return default


def _to_int(value: object) -> int:
    try:
        return int(float(str(value or "").replace(",", "")))
    except (TypeError, ValueError):
        return 0


def _to_optional_int(value: object) -> int | None:
    text = str(value or "").replace(",", "").replace("#", "").strip()
    if not text:
        return None
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return None


def _to_float(value: object) -> float:
    text = str(value or "").replace(",", "").replace("$", "").strip()
    if not text:
        return 0.0


def _to_optional_float(value: object) -> float | None:
    text = str(value or "").replace(",", "").replace("$", "").strip()
    if not text:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return 0.0


def _format_positive(value: str) -> str:
    number = _to_int(value)
    if number > 0:
        return f"+{number}"
    return str(number)


def _format_rank(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return "-"
    if text.startswith("#"):
        return text
    return f"#{text}"


def _format_price(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return "-"
    if text.startswith("$"):
        return text
    try:
        return f"${float(text):.2f}"
    except ValueError:
        return text


def _has_badge(row: dict[str, str], badge: str) -> bool:
    values = f"{row.get('badges', '')};{row.get('badge', '')}".lower()
    return badge.lower() in values


def _badges(row: dict[str, str]) -> list[str]:
    values = f"{row.get('badges', '')};{row.get('badge', '')}"
    badges: list[str] = []
    for raw_value in values.replace(",", ";").split(";"):
        value = raw_value.strip()
        if value and value not in badges:
            badges.append(value)
    return badges


def _split_values(value: str) -> list[str]:
    items: list[str] = []
    for raw_value in str(value or "").replace("|", ";").split(";"):
        item = raw_value.strip()
        if item:
            items.append(item)
    return items


def _truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _is_winner(row: dict[str, str]) -> bool:
    status = f"{row.get('badges', '')};{row.get('badge', '')};{row.get('primary_bucket', '')};{row.get('alert_type', '')};{row.get('research_segment', '')}".lower()
    return "top winner" in status or "winner" in status or "new breakout" in status


def _is_rising(row: dict[str, str]) -> bool:
    status = f"{row.get('badges', '')};{row.get('badge', '')};{row.get('primary_bucket', '')};{row.get('alert_type', '')};{row.get('research_segment', '')}".lower()
    return "fast mover" in status or "rising" in status


def _is_new_launch(row: dict[str, str]) -> bool:
    status = f"{row.get('badges', '')};{row.get('badge', '')};{row.get('primary_bucket', '')};{row.get('alert_type', '')};{row.get('research_segment', '')}".lower()
    return "new release" in status or "new launch" in status


def _tone_from_badges(row: dict[str, str]) -> str:
    badges = f"{row.get('badges', '')};{row.get('badge', '')};{row.get('primary_bucket', '')};{row.get('research_segment', '')}".lower()
    if "fast mover" in badges or "rising" in badges:
        return "rising"
    if "top winner" in badges or "winner" in badges:
        return "winner"
    if "new release" in badges:
        return "alert"
    if "new breakout" in badges:
        return "idea"
    return _tone_from_score(_first_text(row, "opportunity_score", "decision_score", default="0"))


def _tone_from_score(value: str) -> str:
    score = _to_int(value)
    if score >= 80:
        return "winner"
    if score >= 60:
        return "idea"
    if score >= 40:
        return "stable"
    return "neutral"


def _competition_label(row: dict[str, str]) -> str:
    return _first_text(row, "competition", "competition_label", "market_competition", default="Unknown")


def _seller_name(row: dict[str, str]) -> str:
    return _first_text(row, "seller_name", "seller", "source_name", default="Unknown Seller")


def _product_type(row: dict[str, str]) -> str:
    value = _first_text(row, "pod_type", "product_type", default="")
    if value:
        return value.replace("_", " ").replace("-", " ").title()
    return _first_text(row, "category", "niche_primary", default="Unknown")


def _image_label(idea: str, asin: str) -> str:
    words = [word for word in idea.replace("-", " ").split() if word]
    if words:
        return "".join(word[0] for word in words[:2]).upper()
    return (asin[-2:] if asin else "P").upper()
