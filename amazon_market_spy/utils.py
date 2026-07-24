from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path


ASIN_RE = re.compile(r"^B0[A-Z0-9]{8}$")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def timestamp_for_filename(moment: datetime) -> str:
    return moment.strftime("%Y%m%d_%H%M%S")


def isoformat_utc(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def normalize_space(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def slugify(value: str, fallback: str = "source") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or fallback


def parse_money(value: str) -> float | None:
    text = normalize_space(value)
    match = re.search(r"([$£€])\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)", text)
    if not match:
        return None
    return float(match.group(2).replace(",", ""))


def parse_compact_int(value: str) -> int | None:
    text = normalize_space(value).replace(",", "")
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)([kKmM]?)", text)
    if not match:
        return None
    number = float(match.group(1))
    suffix = match.group(2).lower()
    if suffix == "k":
        number *= 1_000
    elif suffix == "m":
        number *= 1_000_000
    return int(number)


def is_asin(value: str) -> bool:
    return bool(ASIN_RE.match(value.strip().upper()))


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
