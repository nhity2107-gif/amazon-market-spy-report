from __future__ import annotations

import csv
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .models import Source
from .utils import normalize_space


REQUIRED_COLUMNS = ["source_name", "source_type", "category", "url", "priority", "active"]
TRUE_VALUES = {"1", "true", "yes", "y", "active", "on"}
SOURCE_TYPE_ALIASES = {
    "seller": "seller",
    "store": "seller",
    "merchant": "seller",
    "search": "category",
    "category": "category",
    "best_seller": "best_seller",
    "best_sellers": "best_seller",
    "bestseller": "best_seller",
    "bestsellers": "best_seller",
    "new_release": "new_release",
    "new_releases": "new_release",
    "movers": "movers_and_shakers",
    "movers_shakers": "movers_and_shakers",
    "movers_and_shakers": "movers_and_shakers",
}
GENERIC_SOURCE_NAME_RE = re.compile(r"^competitor(?:\s+store)?\s+\d+$", re.IGNORECASE)


def _normalize_header(value: str) -> str:
    return normalize_space(value).lower().replace(" ", "_").replace("-", "_")


def _to_bool(value: str) -> bool:
    return normalize_space(value).lower() in TRUE_VALUES


def _normalize_source_type(value: str) -> str:
    normalized = normalize_space(value).lower().replace(" ", "_").replace("-", "_").replace("&", "and")
    return SOURCE_TYPE_ALIASES.get(normalized, normalized)


def _to_priority(value: str, default: int = 999) -> int:
    text = normalize_space(value)
    if not text:
        return default
    try:
        return int(float(text))
    except ValueError:
        return default


def _looks_like_url(value: str) -> bool:
    return normalize_space(value).lower().startswith(("http://", "https://"))


def _repair_missing_category_row(row: dict[str, str], field_map: dict[str, str]) -> dict[str, str]:
    category_field = field_map["category"]
    url_field = field_map["url"]
    priority_field = field_map["priority"]
    active_field = field_map["active"]
    category = normalize_space(row.get(category_field, ""))
    url = normalize_space(row.get(url_field, ""))
    if not _looks_like_url(category) or _looks_like_url(url):
        return row

    repaired = dict(row)
    repaired[category_field] = ""
    repaired[url_field] = category
    repaired[priority_field] = url
    repaired[active_field] = normalize_space(row.get(priority_field, ""))
    return repaired


def _is_generic_source_name(value: str) -> bool:
    return bool(GENERIC_SOURCE_NAME_RE.fullmatch(normalize_space(value)))


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


def _seller_display_name(source_name: str, source_type: str, category: str, explicit_seller_name: str, seller_id: str) -> str:
    if source_type != "seller":
        return explicit_seller_name
    if explicit_seller_name:
        return explicit_seller_name
    if source_name and not _is_generic_source_name(source_name):
        return source_name
    if category:
        return category
    return seller_id


def read_sources(path: Path, include_inactive: bool = False) -> list[Source]:
    if not path.exists():
        raise FileNotFoundError(f"Source CSV not found: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f"Source CSV is empty: {path}")

        field_map = {_normalize_header(name): name for name in reader.fieldnames}
        missing = [column for column in REQUIRED_COLUMNS if column not in field_map]
        if missing:
            raise ValueError(f"Missing source columns: {', '.join(missing)}")

        sources: list[Source] = []
        for row_number, row in enumerate(reader, start=2):
            row = _repair_missing_category_row(row, field_map)
            active = _to_bool(row.get(field_map["active"], ""))
            if not active and not include_inactive:
                continue

            source_name = normalize_space(row.get(field_map["source_name"], ""))
            source_type = _normalize_source_type(row.get(field_map["source_type"], ""))
            category = normalize_space(row.get(field_map["category"], ""))
            url = normalize_space(row.get(field_map["url"], ""))
            seller_id = _seller_id_from_url(url) if source_type == "seller" else ""
            seller_name = _seller_display_name(
                source_name=source_name,
                source_type=source_type,
                category=category,
                explicit_seller_name=normalize_space(row.get(field_map.get("seller_name", ""), "")),
                seller_id=seller_id,
            )
            source = Source(
                source_name=source_name or seller_name or seller_id,
                source_type=source_type,
                category=category,
                url=url,
                priority=_to_priority(row.get(field_map["priority"], "")),
                active=active,
                row_number=row_number - 1,
                seller_name=seller_name,
                seller_url=url if source_type == "seller" else "",
                seller_id=seller_id,
            )
            if not source.source_name:
                raise ValueError(f"Missing source_name on row {row_number}")
            if not source.url:
                raise ValueError(f"Missing url on row {row_number}")
            sources.append(source)

    return sorted(sources, key=lambda item: (item.priority, item.source_name.lower()))
