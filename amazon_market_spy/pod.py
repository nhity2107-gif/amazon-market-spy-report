from __future__ import annotations

import re
from dataclasses import dataclass

from .utils import normalize_space


POD_FIELDS = ["is_pod", "pod_type", "pod_score", "pod_reason"]

CUSTOM_KEYWORDS = [
    "custom name",
    "custom photo",
    "custom text",
    "personalized",
    "customized",
    "custom",
    "engraved",
    "engraving",
    "monogram",
]

STRONG_POD_KEYWORDS = ["printed", "print", "photo", "name"]

GIFT_RECIPIENT_KEYWORDS = [
    "gift for dad",
    "gift for mom",
    "father's day gift",
    "mothers day gift",
    "mother's day gift",
    "teacher gift",
    "nurse gift",
    "birthday gift",
]

POD_PRODUCT_TYPE_KEYWORDS = [
    "coffee mug",
    "t-shirt",
    "shirt",
    "tee",
    "onesie",
    "mug",
    "ornament",
    "poster",
    "canvas",
    "doormat",
    "blanket",
    "sign",
    "plaque",
]

QUOTE_TEXT_KEYWORDS = ["funny quote", "quote", "custom text", "text"]

PHYSICAL_BRAND_KEYWORDS = [
    "stanley",
    "owala",
    "yeti",
    "hydro flask",
    "simple modern",
    "contigo",
    "zojirushi",
    "tervis",
    "thermos",
    "ello",
    "renoji",
]

PHYSICAL_FEATURE_KEYWORDS = [
    "stainless steel",
    "vacuum insulated",
    "insulated",
    "leak proof",
    "leakproof",
    "spill proof",
    "spillproof",
    "lid",
    "straw",
    "handle",
    "dishwasher safe",
    "bpa free",
    "double wall",
    "water bottle",
    "travel mug",
    "cold cup",
    "car cup holder",
]


@dataclass(frozen=True)
class SignalGroup:
    name: str
    keywords: list[str]
    weight: int


SIGNAL_GROUPS = [
    SignalGroup("custom/personalized/engraved", CUSTOM_KEYWORDS, 35),
    SignalGroup("strong POD", STRONG_POD_KEYWORDS, 25),
    SignalGroup("gift recipient", GIFT_RECIPIENT_KEYWORDS, 15),
    SignalGroup("POD product type", POD_PRODUCT_TYPE_KEYWORDS, 10),
    SignalGroup("quote/funny/text", QUOTE_TEXT_KEYWORDS, 15),
    SignalGroup("physical brand", PHYSICAL_BRAND_KEYWORDS, -40),
    SignalGroup("physical feature", PHYSICAL_FEATURE_KEYWORDS, -20),
]


def classify_pod(*parts: object) -> dict[str, str]:
    text = _normalized_text(" ".join(str(part or "") for part in parts))
    score = 0
    reasons: list[str] = []
    matched_by_group: dict[str, list[str]] = {}

    for group in SIGNAL_GROUPS:
        matches = _matched_keywords(text, group.keywords)
        if not matches:
            continue
        matched_by_group[group.name] = matches
        group_score = group.weight * len(matches)
        score += group_score
        sign = "+" if group_score >= 0 else ""
        reasons.append(f"{sign}{group_score} {group.name}: {', '.join(matches)}")

    is_pod = _pod_status(score)
    pod_type = _pod_type(matched_by_group, is_pod)
    reasons.append(f"score={score}; is_pod={is_pod}; pod_type={pod_type}")
    return {
        "is_pod": is_pod,
        "pod_type": pod_type,
        "pod_score": str(score),
        "pod_reason": "; ".join(reasons),
    }


def ensure_pod_fields(row: dict[str, str]) -> dict[str, str]:
    if all(str(row.get(field, "")).strip() for field in POD_FIELDS):
        return row
    pod = classify_pod(
        row.get("title", ""),
        row.get("category", ""),
        row.get("source_name", ""),
        row.get("seller_name", ""),
        row.get("badge", ""),
    )
    row.update(pod)
    return row


def pod_allowed(row: dict[str, str]) -> bool:
    ensure_pod_fields(row)
    return row.get("is_pod", "") in {"yes", "maybe"}


def _pod_status(score: int) -> str:
    if score >= 40:
        return "yes"
    if score >= 25:
        return "maybe"
    return "no"


def _pod_type(matched_by_group: dict[str, list[str]], is_pod: str) -> str:
    custom = _has_any(matched_by_group, "custom/personalized/engraved")
    quote = _has_any(matched_by_group, "quote/funny/text")
    product_types = set(matched_by_group.get("POD product type", []))

    if is_pod == "no" and matched_by_group.get("physical brand"):
        return "physical_brand_product"
    if "mug" in product_types or "coffee mug" in product_types:
        if quote:
            return "quote_mug"
        if custom:
            return "personalized_mug"
    if {"shirt", "t-shirt", "tee"} & product_types and (custom or _has_any(matched_by_group, "strong POD")):
        return "custom_shirt"
    if "onesie" in product_types and custom:
        return "personalized_onesie"
    if "doormat" in product_types and custom:
        return "custom_doormat"
    if custom and (matched_by_group.get("gift recipient") or {"sign", "plaque"} & product_types):
        return "engraved_gift"
    if matched_by_group.get("physical brand"):
        return "physical_brand_product"
    return "unknown"


def _has_any(groups: dict[str, list[str]], name: str) -> bool:
    return bool(groups.get(name))


def _matched_keywords(text: str, keywords: list[str]) -> list[str]:
    return [keyword for keyword in keywords if _contains_keyword(text, keyword)]


def _contains_keyword(text: str, keyword: str) -> bool:
    phrase = _normalized_text(keyword)
    pattern = r"(?<![a-z0-9])" + re.escape(phrase).replace(r"\ ", r"\s+") + r"(?![a-z0-9])"
    return re.search(pattern, text) is not None


def _normalized_text(value: str) -> str:
    return normalize_space(value).lower().replace("’", "'").replace("-", " ")
