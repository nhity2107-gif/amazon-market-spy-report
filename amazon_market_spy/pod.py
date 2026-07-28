from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from .utils import ensure_parent, normalize_space


LEGACY_POD_FIELDS = ["is_pod", "pod_type", "pod_score", "pod_reason"]
POD_FIELDS = [
    "is_pod",
    "production_model",
    "production_confidence",
    "production_reason",
    "pod_type",
    "pod_score",
    "pod_confidence",
    "pod_reason",
]

PRODUCTION_MODEL_TO_IS_POD = {
    "pod": "yes",
    "non_pod": "no",
    "unknown": "maybe",
}

PRODUCTION_MODEL_REPORT_FIELDS = [
    "ASIN",
    "Title",
    "Seller",
    "Production Model",
    "Confidence",
    "Reason",
]

_KEYWORD_PATTERN_CACHE: dict[str, re.Pattern[str]] = {}

DECORATION_METHOD_KEYWORDS = [
    "uv printed",
    "uv print",
    "screen printed",
    "screen print",
    "design printed",
    "dtf",
    "dtg",
    "direct to garment",
    "sublimation",
    "sublimated",
    "printed",
    "print",
    "laser engraved",
    "engraved",
    "engraving",
    "etched",
    "embroidered",
    "embroidery",
    "embroider",
    "artwork",
    "graphic tee",
    "graphic shirt",
]

PERSONALIZATION_KEYWORDS = [
    "personalized",
    "customized",
    "custom name",
    "custom photo",
    "custom text",
    "made to order",
    "choose name",
    "add photo",
    "add text",
    "upload image",
    "upload photo",
    "birth flower",
    "your name",
    "with name",
    "with photo",
    "photo upload",
    "custom portrait",
    "custom family name",
    "custom pet portrait",
    "kids names",
    "kid names",
    "name on sleeve",
    "embroidered name",
    "monogram",
]

CUSTOM_DESIGN_KEYWORDS = [
    "custom design",
    "personalized design",
    "custom",
    "design your own",
    "customize",
    "customizable",
]

ARTWORK_TEXT_KEYWORDS = [
    "friendship elephant",
    "quote",
    "funny quote",
    "saying",
    "phrase",
    "graphic",
    "design",
    "art print",
    "wall art",
    "poster print",
    "novelty",
    "funny",
    "patriotic",
    "america 250",
    "250th anniversary",
    "1776-2026",
    "memorial",
    "welcome",
]

BASE_PRODUCT_KEYWORDS = [
    "coffee mug",
    "t-shirt",
    "tee shirt",
    "t shirt",
    "shirt",
    "shirts",
    "tee",
    "tees",
    "hoodie",
    "hoodies",
    "sweatshirt",
    "sweatshirts",
    "sweater",
    "sweaters",
    "crewneck",
    "onesie",
    "mug",
    "cup",
    "cups",
    "tumbler",
    "ornament",
    "ornaments",
    "poster",
    "canvas",
    "doormat",
    "doormats",
    "door mat",
    "door mats",
    "blanket",
    "pillow",
    "metal sign",
    "wood sign",
    "garden flag",
    "banner",
    "acrylic plaque",
    "whiskey glass",
    "glass",
    "sign",
    "signs",
    "plaque",
    "plaques",
    "flag",
    "flags",
    "cap",
    "hat",
    "jersey",
    "jerseys",
    "socks",
    "sticker",
    "keychain",
    "tray",
    "napkin",
    "napkins",
    "acrylic",
    "desk decor",
    "keepsake",
    "notebook",
    "journal",
    "light box",
    "night light",
    "lamp",
    "ring dish",
    "garden stake",
    "stake",
    "coin",
    "challenge coin",
    "pocket hug",
    "picture frame",
    "frame",
    "storage basket",
    "basket",
    "wine bottle",
    "bottle",
    "bottle lamp",
    "visor clip",
    "tape measure",
    "stone",
    "rock",
    "suncatcher",
    "glassware",
    "wood",
    "wooden",
    "statue",
]

CUSTOM_KEYWORDS = [*PERSONALIZATION_KEYWORDS, *CUSTOM_DESIGN_KEYWORDS]
POD_PRODUCT_TYPE_KEYWORDS = BASE_PRODUCT_KEYWORDS
QUOTE_TEXT_KEYWORDS = ARTWORK_TEXT_KEYWORDS

POD_SELLER_KEYWORDS = [
    "print on demand",
    "pod",
    "wrappiness",
    "shineon",
    "interestprint",
    "gearbubble",
    "custom studio",
    "custom gifts",
    "personalized gifts",
    "embroidery shop",
    "engraving shop",
    "izi pod",
    "nazenti",
    "pofily",
    "polify",
    "pawfect house",
    "wander prints",
    "peties",
    "go pod",
    "gopod",
]

POD_BRAND_KEYWORDS = [
    "wrappiness",
    "shineon",
    "interestprint",
    "gearbubble",
    "printed mint",
    "gooten",
    "printify",
    "printful",
    "teelaunch",
]

GIFT_RECIPIENT_KEYWORDS = [
    "gift for dad",
    "gift for mom",
    "father's day gift",
    "fathers day gift",
    "mothers day gift",
    "mother's day gift",
    "teacher gift",
    "nurse gift",
    "birthday gift",
    "wedding gift",
    "anniversary gift",
    "memorial gift",
]

RETAIL_BRAND_KEYWORDS = [
    "hallmark",
    "hallmark keepsake",
    "disney",
    "marvel",
    "lego",
    "nike",
    "adidas",
    "funko",
    "hasbro",
    "mattel",
    "barbie",
    "swarovski",
    "command",
    "scentsicles",
    "lenox",
    "puma",
    "under armour",
    "augusta sportswear",
    "richardson",
    "flexfit",
    "carhartt",
    "yupoong",
    "beqhause",
    "olanly",
    "gorilla grip",
    "earthall",
    "hicorfe",
    "my texas house",
    "amyracel",
]

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

LICENSED_FRANCHISE_KEYWORDS = [
    "harry potter",
    "disney",
    "star wars",
    "marvel",
    "dc comics",
    "pokemon",
    "peanuts",
    "snoopy",
    "star trek",
    "shark week",
    "michael myers",
    "playstation",
    "sony",
    "chevrolet",
    "gm ornament",
    "nintendo",
    "lego",
    "barbie",
]

MASS_RETAIL_PRODUCT_KEYWORDS = [
    "amazon business card",
    "standard retail",
    "mass produced",
    "mass-produced",
    "building set",
    "toy set",
    "action figure",
    "figurine",
    "collectible",
    "dirt trapper",
    "non slip",
    "non-slip",
    "washable",
    "waterproof",
    "all season",
    "absorbent",
    "rubber backing",
    "low profile",
    "indoor outdoor",
    "indoor/outdoor",
    "heavy duty",
    "extra thick",
    "machine washable",
    "muddy paws",
    "alarm clock",
    "wall clock",
    "desk clock",
    "battery operated",
    "pack of",
    "pcs",
    "pieces",
    "set of",
    "artificial",
    "fake",
    "plastic",
    "prefilled",
    "communion cups",
    "jar",
    "cards",
    "dried flower",
    "dried flowers",
    "tassel",
    "keychain charm",
    "cross fidget",
    "serving bowl",
    "wall basket",
    "wreath",
    "folding fan",
    "hand folding fan",
    "wood knot",
    "chain link",
    "marker flags",
    "marking flags",
    "toy figure",
    "figure set",
    "fidget",
    "plain blank",
    "blank plain",
    "practice jersey",
    "training jersey",
    "sports uniform",
    "gift basket",
    "gift baskets",
    "gift box",
    "gifts box",
    "gifts basket",
    "care package",
    "set box",
    "candle",
    "candles",
    "reed diffuser",
    "diffuser",
    "curtain",
    "curtains",
    "table runner",
    "marquee letters",
    "light up letters",
    "galvanized metal letters",
    "paper chain",
    "party decorations",
    "party decor",
    "crafting",
    "craft supplies",
    "fillable",
    "rope light clips",
    "hooks",
    "props",
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
    pod_weight: int = 0
    non_pod_weight: int = 0


@dataclass(frozen=True)
class SellerProductionProfile:
    seller: str
    production_model: str
    production_confidence: int
    product_count: int
    evidence_count: int
    pod_ratio: float
    non_pod_ratio: float

    @property
    def reason(self) -> str:
        ratio = self.pod_ratio if self.production_model == "pod" else self.non_pod_ratio
        return f"Seller profile {self.production_model} ({ratio:.0%} of {self.evidence_count} confident products)."


SIGNAL_GROUPS = [
    SignalGroup("production method", DECORATION_METHOD_KEYWORDS, pod_weight=50),
    SignalGroup("personalization", PERSONALIZATION_KEYWORDS, pod_weight=45),
    SignalGroup("custom design", CUSTOM_DESIGN_KEYWORDS, pod_weight=35),
    SignalGroup("artwork/text design", ARTWORK_TEXT_KEYWORDS, pod_weight=24),
    SignalGroup("blank/base product", BASE_PRODUCT_KEYWORDS, pod_weight=10),
    SignalGroup("POD seller/brand", [*POD_SELLER_KEYWORDS, *POD_BRAND_KEYWORDS], pod_weight=45),
    SignalGroup("gift recipient", GIFT_RECIPIENT_KEYWORDS, pod_weight=8),
    SignalGroup("retail brand", RETAIL_BRAND_KEYWORDS, non_pod_weight=90),
    SignalGroup("licensed franchise", LICENSED_FRANCHISE_KEYWORDS, non_pod_weight=90),
    SignalGroup("physical brand", PHYSICAL_BRAND_KEYWORDS, non_pod_weight=80),
    SignalGroup("mass retail product", MASS_RETAIL_PRODUCT_KEYWORDS, non_pod_weight=55),
    SignalGroup("physical feature", PHYSICAL_FEATURE_KEYWORDS, non_pod_weight=35),
]


def classify_pod(*parts: object) -> dict[str, str]:
    return classify_pod_row({"title": " ".join(str(part or "") for part in parts)})


def classify_pod_row(
    row: dict[str, str],
    seller_profiles: dict[str, SellerProductionProfile] | None = None,
) -> dict[str, str]:
    evidence = _collect_evidence(row, seller_profiles=seller_profiles)
    production_model, confidence, reason = _production_decision(evidence)
    pod_type = _pod_type(evidence, production_model)
    is_pod = PRODUCTION_MODEL_TO_IS_POD[production_model]
    pod_score = evidence["pod_score"] - evidence["non_pod_score"]
    pod_confidence = _confidence_label(confidence)

    detail_reasons = [
        *evidence["pod_reasons"],
        *evidence["non_pod_reasons"],
        reason,
        (
            f"pod_score={evidence['pod_score']}; non_pod_score={evidence['non_pod_score']}; "
            f"production_model={production_model}; production_confidence={confidence}; "
            f"is_pod={is_pod}; pod_type={pod_type}"
        ),
    ]
    return {
        "is_pod": is_pod,
        "production_model": production_model,
        "production_confidence": str(confidence),
        "production_reason": reason,
        "pod_type": pod_type,
        "pod_score": str(pod_score),
        "pod_confidence": pod_confidence,
        "pod_reason": "; ".join(part for part in detail_reasons if part),
    }


def build_seller_profiles(rows: list[dict[str, str]]) -> dict[str, SellerProductionProfile]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        seller_key = _seller_key(row)
        if seller_key:
            grouped[seller_key].append(row)

    profiles: dict[str, SellerProductionProfile] = {}
    for seller_key, seller_rows in grouped.items():
        confident_models: list[str] = []
        for row in seller_rows:
            result = classify_pod_row(row)
            confidence = _int_value(result.get("production_confidence", "0"))
            if confidence >= 80 and result["production_model"] in {"pod", "non_pod"}:
                confident_models.append(result["production_model"])

        evidence_count = len(confident_models)
        if evidence_count < 4:
            continue
        counts = Counter(confident_models)
        pod_ratio = counts["pod"] / evidence_count
        non_pod_ratio = counts["non_pod"] / evidence_count
        model = ""
        ratio = 0.0
        if pod_ratio >= 0.9:
            model = "pod"
            ratio = pod_ratio
        elif non_pod_ratio >= 0.85:
            model = "non_pod"
            ratio = non_pod_ratio
        if not model:
            continue

        confidence = min(98, 78 + int(ratio * 15) + min(evidence_count, 20) // 4)
        profiles[seller_key] = SellerProductionProfile(
            seller=seller_key,
            production_model=model,
            production_confidence=confidence,
            product_count=len(seller_rows),
            evidence_count=evidence_count,
            pod_ratio=pod_ratio,
            non_pod_ratio=non_pod_ratio,
        )
    return profiles


def refresh_pod_fields_for_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    seller_profiles = build_seller_profiles(rows)
    for row in rows:
        refresh_pod_fields(row, seller_profiles=seller_profiles)
    return rows


def ensure_pod_fields(row: dict[str, str]) -> dict[str, str]:
    if all(str(row.get(field, "")).strip() for field in POD_FIELDS):
        return row
    if all(str(row.get(field, "")).strip() for field in LEGACY_POD_FIELDS):
        production_model = row.get("production_model", "") or _production_model_from_is_pod(row.get("is_pod", ""))
        row["production_model"] = production_model
        row["production_confidence"] = row.get("production_confidence", "") or _confidence_number_from_legacy(
            row.get("pod_confidence", ""), row.get("pod_score", ""), production_model
        )
        row["production_reason"] = row.get("production_reason", "") or _short_reason(row.get("pod_reason", ""))
        row["pod_confidence"] = row.get("pod_confidence", "") or _confidence_label(
            _int_value(row["production_confidence"])
        )
        return row
    row.update(classify_pod_row(row))
    return row


def refresh_pod_fields(
    row: dict[str, str],
    seller_profiles: dict[str, SellerProductionProfile] | None = None,
) -> dict[str, str]:
    row.update(classify_pod_row(row, seller_profiles=seller_profiles))
    return row


def pod_allowed(row: dict[str, str]) -> bool:
    ensure_pod_fields(row)
    return row.get("is_pod", "") in {"yes", "maybe"}


def write_production_model_report(path: Path, rows: list[dict[str, str]]) -> None:
    ensure_parent(path)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PRODUCTION_MODEL_REPORT_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "ASIN": row.get("asin", ""),
                    "Title": row.get("title", "") or row.get("raw_title", ""),
                    "Seller": row.get("seller_name", "") or row.get("source_name", ""),
                    "Production Model": row.get("production_model", ""),
                    "Confidence": row.get("production_confidence", ""),
                    "Reason": row.get("production_reason", ""),
                }
            )


def _collect_evidence(
    row: dict[str, str],
    seller_profiles: dict[str, SellerProductionProfile] | None,
) -> dict[str, object]:
    field_text = _field_text(row)
    combined = " ".join(field_text.values())
    matched_by_group: dict[str, list[str]] = {}
    pod_score = 0
    non_pod_score = 0
    pod_reasons: list[str] = []
    non_pod_reasons: list[str] = []

    for group in SIGNAL_GROUPS:
        search_text = combined
        if group.name in {"retail brand", "physical brand", "licensed franchise"}:
            search_text = " ".join([field_text["title"], field_text["brand"], field_text["seller"], field_text["url"]])
        matches = _matched_keywords(search_text, group.keywords)
        if not matches:
            continue
        matched_by_group[group.name] = matches
        if group.pod_weight:
            points = min(group.pod_weight * len(matches), group.pod_weight + 30)
            pod_score += points
            pod_reasons.append(f"+{points} {group.name}: {', '.join(matches)}")
        if group.non_pod_weight:
            points = min(group.non_pod_weight * len(matches), group.non_pod_weight + 40)
            non_pod_score += points
            non_pod_reasons.append(f"+{points} {group.name}: {', '.join(matches)}")

    category_pod, category_non_pod, category_reasons = _category_evidence(field_text, matched_by_group)
    pod_score += category_pod
    non_pod_score += category_non_pod
    for reason in category_reasons:
        if reason.startswith("POD"):
            pod_reasons.append(reason)
        else:
            non_pod_reasons.append(reason)

    seller_profile = None
    seller_key = _seller_key(row)
    if seller_key and seller_profiles:
        seller_profile = seller_profiles.get(seller_key)
        if seller_profile:
            if seller_profile.production_model == "pod":
                pod_score += 35
                pod_reasons.append(f"+35 {seller_profile.reason}")
            elif seller_profile.production_model == "non_pod":
                non_pod_score += 35
                non_pod_reasons.append(f"+35 {seller_profile.reason}")

    return {
        "field_text": field_text,
        "matched_by_group": matched_by_group,
        "pod_score": pod_score,
        "non_pod_score": non_pod_score,
        "pod_reasons": pod_reasons,
        "non_pod_reasons": non_pod_reasons,
        "seller_profile": seller_profile,
    }


def _production_decision(evidence: dict[str, object]) -> tuple[str, int, str]:
    matched_by_group: dict[str, list[str]] = evidence["matched_by_group"]  # type: ignore[assignment]
    pod_score = int(evidence["pod_score"])
    non_pod_score = int(evidence["non_pod_score"])
    field_text: dict[str, str] = evidence["field_text"]  # type: ignore[assignment]
    seller_profile: SellerProductionProfile | None = evidence["seller_profile"]  # type: ignore[assignment]

    has_method = _has_any(matched_by_group, "production method")
    has_personalization = _has_any(matched_by_group, "personalization")
    has_custom_design = _has_any(matched_by_group, "custom design")
    has_artwork = _has_any(matched_by_group, "artwork/text design")
    has_base = _has_any(matched_by_group, "blank/base product")
    has_retail_brand = _has_any(matched_by_group, "retail brand")
    has_physical_brand = _has_any(matched_by_group, "physical brand")
    has_license = _has_any(matched_by_group, "licensed franchise")
    has_mass_retail = _has_any(matched_by_group, "mass retail product")
    has_pod_seller = _has_any(matched_by_group, "POD seller/brand")
    retail_blockers = _retail_blockers(matched_by_group)

    if (has_retail_brand or has_license) and not (has_personalization or has_custom_design):
        return "non_pod", 99, f"Retail brand or licensed property: {', '.join(retail_blockers)}."
    if has_physical_brand and not (has_personalization or has_custom_design):
        return "non_pod", 96, f"Finished retail brand: {', '.join(retail_blockers)}."
    if has_personalization and (has_base or has_method or has_custom_design or has_pod_seller):
        return "pod", 100, "Personalization detected on a decoratable product."
    if has_method and has_base and not (has_retail_brand or has_license):
        return "pod", 98, "Production method applied to a blank/base product."
    if has_custom_design and has_base and not (has_retail_brand or has_license):
        return "pod", 96, "Custom design evidence on a blank/base product."
    if has_method and has_base and has_physical_brand and (has_personalization or has_custom_design):
        return "pod", 96, "Custom production method overrides physical brand signal."
    if has_pod_seller and (has_base or has_personalization or has_artwork) and not retail_blockers:
        return "pod", 94, "POD seller or brand with decoratable product."
    if has_mass_retail and not (has_method or has_personalization or has_custom_design):
        return "non_pod", 92, "Mass-retail finished product signals."

    if seller_profile and not retail_blockers:
        if seller_profile.production_model == "pod" and non_pod_score < 55:
            return "pod", max(84, min(94, seller_profile.production_confidence - 4)), seller_profile.reason
        if seller_profile.production_model == "non_pod" and pod_score < 55:
            return "non_pod", max(82, min(94, seller_profile.production_confidence - 4)), seller_profile.reason

    source_reason = _source_reason(field_text)
    if source_reason and non_pod_score >= pod_score + 20:
        return "non_pod", min(94, 72 + non_pod_score // 3), source_reason
    if source_reason and pod_score >= non_pod_score + 20:
        return "pod", min(95, 72 + pod_score // 3), source_reason

    if seller_profile and has_base and abs(pod_score - non_pod_score) >= 20:
        model = "pod" if pod_score > non_pod_score else "non_pod"
        confidence = max(82, min(96, seller_profile.production_confidence - 3))
        return model, confidence, seller_profile.reason

    if pod_score >= non_pod_score + 35 and pod_score >= 55 and (has_base or has_method or has_pod_seller):
        confidence = min(94, 60 + (pod_score - non_pod_score) // 2)
        if has_artwork and has_base:
            confidence = max(confidence, 88)
        return "pod", confidence, "Weighted POD evidence exceeds retail evidence."
    if non_pod_score >= pod_score + 35 and non_pod_score >= 55:
        confidence = min(94, 60 + (non_pod_score - pod_score) // 2)
        return "non_pod", confidence, "Weighted retail evidence exceeds POD evidence."

    if _looks_like_unbranded_finished_retail(field_text, matched_by_group):
        return "non_pod", 76, "Finished product with no production-method evidence."
    if _looks_like_unbranded_pod(field_text, matched_by_group):
        return "pod", 82, "Design-oriented base product with no retail blocker."

    confidence = min(45, 20 + max(pod_score, non_pod_score) // 4)
    return "unknown", confidence, "Insufficient evidence."


def _category_evidence(field_text: dict[str, str], matched_by_group: dict[str, list[str]]) -> tuple[int, int, list[str]]:
    title = field_text["title"]
    category = field_text["category"]
    source = field_text["source"]
    context = " ".join([category, source])
    reasons: list[str] = []
    pod_points = 0
    non_pod_points = 0
    has_base = _has_any(matched_by_group, "blank/base product")
    has_method = _has_any(matched_by_group, "production method")
    has_personalization = _has_any(matched_by_group, "personalization")
    has_custom_design = _has_any(matched_by_group, "custom design")
    has_artwork = _has_any(matched_by_group, "artwork/text design")
    has_retail = bool(_retail_blockers(matched_by_group))
    has_mass_retail = _has_any(matched_by_group, "mass retail product")

    if "decorative signs" in context and (has_base or _contains_any(title, ["gift", "gifts", "decor", "acrylic", "inspirational", "quote", "appreciation"])) and not has_retail:
        pod_points += 45
        reasons.append("POD category evidence: decorative sign/plaque market.")
    if ("mugs" in context or "coffee mugs" in context) and has_base and (has_artwork or has_method or has_personalization):
        pod_points += 42
        reasons.append("POD category evidence: designed mug market.")
    if ("outdoor flags" in context or "banners" in context) and has_base and not has_retail:
        pod_points += 42
        reasons.append("POD category evidence: printed flag/banner market.")
    if ("novelty" in context or "t-shirt" in context) and _has_apparel_base(matched_by_group) and not has_retail:
        if has_artwork or has_method or has_personalization or has_custom_design:
            pod_points += 40
            reasons.append("POD category evidence: novelty apparel market.")
    if ("baseball caps" in context or "caps" in context) and has_method and not has_retail:
        pod_points += 40
        reasons.append("POD category evidence: decorated cap market.")
    if ("baseball caps" in context or "caps" in context) and (has_custom_design or _contains_any(title, ["american flag", "veteran", "patriotic", "air force", "gulf war"])) and not has_retail:
        pod_points += 36
        reasons.append("POD category evidence: designed cap market.")
    if (
        ("soccer jerseys" in context or "baseball jerseys" in context or "button-down shirts" in context)
        and _has_apparel_base(matched_by_group)
        and not has_retail
    ):
        if _contains_any(
            title,
            [
                "fan",
                "mexico",
                "mexican",
                "world cup",
                "retro",
                "90s",
                "patriotic",
                "america",
                "brazil",
                "argentina",
                "usa",
                "football",
                "gift",
            ],
        ):
            pod_points += 36
            reasons.append("POD category evidence: designed fan apparel.")
    if "handmade" in context and has_base and (has_personalization or has_custom_design or has_method):
        pod_points += 38
        reasons.append("POD category evidence: handmade/custom base product.")
    if "hanging ornaments" in context and (
        has_base
        or _contains_any(title, ["gift", "gifts", "decor", "keepsake", "wedding", "engagement", "christmas"])
    ) and not has_retail and not has_mass_retail:
        pod_points += 50
        reasons.append("POD category evidence: designed ornament market.")

    if "insulated tumblers" in context and not (has_personalization or has_custom_design or has_method):
        non_pod_points += 60
        reasons.append("Retail category evidence: insulated tumbler finished goods.")
    if ("mugs" in context or "tumblers & water glasses" in context) and _contains_any(
        title, ["gift basket", "gift baskets", "gift box", "gifts box", "gifts basket", "care package"]
    ):
        non_pod_points += 60
        reasons.append("Retail category evidence: bundled gift set.")
    if ("mugs" in context or "tumblers & water glasses" in context) and has_base and not (
        has_personalization or has_custom_design or has_method or has_artwork
    ):
        non_pod_points += 50
        reasons.append("Retail category evidence: plain mug/glass drinkware.")
    if "novelty socks" in context and not (has_personalization or has_custom_design or has_method):
        non_pod_points += 58
        reasons.append("Retail category evidence: mass-produced novelty socks.")
    if "jewelry trays" in context and not (has_personalization or has_custom_design or has_method):
        non_pod_points += 58
        reasons.append("Retail category evidence: finished jewelry tray.")
    if "old fashioned glasses" in context and not (has_personalization or has_custom_design or has_method):
        non_pod_points += 55
        reasons.append("Retail category evidence: finished drinking glass.")
    if ("baseball caps" in context or "caps" in context) and not (has_personalization or has_custom_design or has_method):
        non_pod_points += 55
        reasons.append("Retail category evidence: finished cap.")
    if (
        ("soccer jerseys" in context or "baseball jerseys" in context or "button-down shirts" in context)
        and _contains_any(title, ["plain", "blank", "training", "practice", "uniform", "sportswear", "cool dry"])
        and not (has_personalization or has_custom_design or has_method)
    ):
        non_pod_points += 55
        reasons.append("Retail category evidence: blank or performance apparel.")
    if _contains_any(title, ["gift basket", "gift box", "care package", "set box"]):
        non_pod_points += 58
        reasons.append("Retail category evidence: bundled gift set.")
    if _contains_any(title, ["candle", "candles", "reed diffuser", "curtain", "table runner"]):
        non_pod_points += 52
        reasons.append("Retail category evidence: finished home decor.")
    if "hanging ornaments" in context and (_contains_any(
        title,
        ["pack", "pcs", "pieces", "artificial", "plastic", "paper", "craft", "fillable", "clip", "props"],
    ) or _has_numbered_pack(title)):
        non_pod_points += 55
        reasons.append("Retail category evidence: ornament craft/decor supply.")
    if _contains_any(title, ["officially licensed", "fan event", "comic book cover"]):
        non_pod_points += 65
        reasons.append("Retail category evidence: licensed merchandise.")

    return pod_points, non_pod_points, reasons


def _pod_type(evidence: dict[str, object], production_model: str) -> str:
    matched_by_group: dict[str, list[str]] = evidence["matched_by_group"]  # type: ignore[assignment]
    product_types = set(matched_by_group.get("blank/base product", []))
    has_personalization = _has_any(matched_by_group, "personalization")
    has_quote = _has_any(matched_by_group, "artwork/text design")
    has_method = _has_any(matched_by_group, "production method")

    if production_model == "non_pod":
        if matched_by_group.get("licensed franchise"):
            return "licensed_brand_product"
        if matched_by_group.get("retail brand"):
            return "retail_brand_product"
        if matched_by_group.get("physical brand"):
            return "physical_brand_product"
        if matched_by_group.get("mass retail product"):
            return "mass_retail_product"
        return "finished_retail_product"
    if production_model == "unknown":
        return "unknown"

    if "mug" in product_types or "coffee mug" in product_types:
        if has_personalization:
            return "personalized_mug"
        if has_quote or has_method:
            return "quote_mug"
    if {
        "shirt",
        "shirts",
        "t-shirt",
        "t shirt",
        "tee shirt",
        "tee",
        "tees",
        "hoodie",
        "hoodies",
        "sweatshirt",
        "sweatshirts",
        "sweater",
        "sweaters",
        "crewneck",
        "jersey",
        "jerseys",
    } & product_types:
        return "custom_shirt" if has_personalization else "printed_shirt"
    if "doormat" in product_types or "door mat" in product_types:
        return "custom_doormat" if has_personalization else "printed_doormat"
    if "ornament" in product_types:
        return "custom_ornament" if has_personalization else "printed_ornament"
    if "glass" in product_types or "whiskey glass" in product_types or "glassware" in product_types:
        return "engraved_glass" if has_method or has_personalization else "decorated_glass"
    if "cap" in product_types or "hat" in product_types:
        return "embroidered_cap" if has_method or has_personalization else "decorated_cap"
    if "blanket" in product_types:
        return "printed_blanket"
    if "pillow" in product_types:
        return "printed_pillow"
    if {"sign", "metal sign", "wood sign", "plaque", "acrylic plaque"} & product_types:
        if has_personalization or has_method:
            return "engraved_gift"
        return "printed_sign"
    if "garden flag" in product_types or "flag" in product_types or "banner" in product_types:
        return "printed_flag"
    if "poster" in product_types:
        return "printed_poster"
    if "canvas" in product_types:
        return "printed_canvas"
    if "sticker" in product_types:
        return "printed_sticker"
    if {"notebook", "journal", "light box", "night light", "ring dish", "garden stake", "coin", "challenge coin", "pocket hug", "picture frame", "frame", "storage basket", "basket", "wine bottle", "bottle", "bottle lamp", "visor clip", "tape measure", "stone", "rock", "suncatcher", "wood", "wooden", "statue"} & product_types:
        return "decorated_blank_product"
    if production_model == "pod":
        return "decorated_blank_product"
    return "unknown"


def _looks_like_unbranded_finished_retail(
    field_text: dict[str, str],
    matched_by_group: dict[str, list[str]],
) -> bool:
    title = field_text["title"]
    context = " ".join([field_text["category"], field_text["source"]])
    if _has_any(matched_by_group, "production method") or _has_any(matched_by_group, "personalization"):
        return False
    if _contains_any(
        title,
        [
            "table runner",
            "suncatcher",
            "wind chime",
            "paper",
            "plastic",
            "artificial",
            "decorations",
            "mirror",
            "clip",
            "hooks",
            "crystal",
            "crochet",
            "knitted",
            "tray",
            "socks",
            "coaster",
            "mat",
            "rug",
        ],
    ) or _has_numbered_pack(title):
        return True
    if _contains_any(context, ["jewelry trays", "novelty socks", "insulated tumblers", "old fashioned glasses"]):
        return True
    return False


def _looks_like_unbranded_pod(field_text: dict[str, str], matched_by_group: dict[str, list[str]]) -> bool:
    if not _has_any(matched_by_group, "blank/base product") or _retail_blockers(matched_by_group):
        return False
    title = field_text["title"]
    context = " ".join([field_text["category"], field_text["source"]])
    if _has_any(matched_by_group, "artwork/text design"):
        return True
    if _contains_any(
        context,
        ["decorative signs", "novelty coffee mugs", "outdoor flags", "banners", "novelty t-shirts"],
    ):
        return True
    if _contains_any(
        title,
        [
            "america",
            "patriotic",
            "teacher",
            "dad",
            "mom",
            "grandpa",
            "grandma",
            "memorial",
            "gift",
            "gifts",
            "keepsake",
            "friendship",
            "engagement",
            "wedding",
        ],
    ):
        return True
    return False


def _field_text(row: dict[str, str]) -> dict[str, str]:
    return {
        "title": _normalized_text(" ".join(_first_values(row, ["title", "raw_title"]))),
        "product_type": _normalized_text(" ".join(_first_values(row, ["product_type"]))),
        "seller": _normalized_text(" ".join(_first_values(row, ["seller_name", "source_name"]))),
        "category": _normalized_text(
            " ".join(_first_values(row, ["category", "category_name", "page_type", "source_type"]))
        ),
        "source": _normalized_text(" ".join(_first_values(row, ["source_name", "source_type", "page_type"]))),
        "brand": _normalized_text(" ".join(_first_values(row, ["brand", "manufacturer"]))),
        "url": _normalized_text(" ".join(_first_values(row, ["product_url", "page_url", "source_url"]))),
        "description": _normalized_text(
            " ".join(_first_values(row, ["description", "product_description", "features", "bullets"]))
        ),
    }


def _source_reason(field_text: dict[str, str]) -> str:
    source = " ".join([field_text["category"], field_text["source"]])
    if _contains_any(source, ["decorative signs", "novelty coffee mugs", "outdoor flags", "banners"]):
        return "Source/category supports decorated blank-product production."
    if _contains_any(source, ["insulated tumblers", "novelty socks", "jewelry trays", "old fashioned glasses"]):
        return "Source/category supports finished retail product."
    return ""


def _seller_key(row: dict[str, str]) -> str:
    seller = normalize_space(row.get("seller_name", "") or "")
    if not seller:
        source_name = normalize_space(row.get("source_name", "") or "")
        source_type = normalize_space(row.get("source_type", "") or row.get("page_type", "")).lower()
        if source_type == "seller" and not _looks_like_source_collection(source_name):
            seller = source_name
    if not seller or _looks_like_source_collection(seller):
        return ""
    return _normalized_text(seller)


def _looks_like_source_collection(value: str) -> bool:
    text = _normalized_text(value)
    return any(marker in text for marker in ["best sellers", "new releases", "most wished", "movers & shakers"])


def _retail_blockers(matched_by_group: dict[str, list[str]]) -> list[str]:
    blockers: list[str] = []
    for group in ["retail brand", "licensed franchise", "mass retail product", "physical brand"]:
        matches = matched_by_group.get(group)
        if matches:
            blockers.append(f"{group}: {', '.join(matches)}")
    return blockers


def _has_apparel_base(groups: dict[str, list[str]]) -> bool:
    product_types = set(groups.get("blank/base product", []))
    return bool(
        {
            "shirt",
            "shirts",
            "t-shirt",
            "t shirt",
            "tee shirt",
            "tee",
            "tees",
            "hoodie",
            "hoodies",
            "sweatshirt",
            "sweatshirts",
            "sweater",
            "sweaters",
            "crewneck",
            "jersey",
            "jerseys",
        }
        & product_types
    )


def _production_model_from_is_pod(is_pod: str) -> str:
    normalized = str(is_pod or "").strip().lower()
    if normalized == "yes":
        return "pod"
    if normalized == "no":
        return "non_pod"
    return "unknown"


def _confidence_number_from_legacy(pod_confidence: str, pod_score: str, production_model: str) -> str:
    confidence = str(pod_confidence or "").strip().lower()
    if confidence == "high":
        return "95" if production_model != "unknown" else "45"
    if confidence == "medium":
        return "78" if production_model != "unknown" else "40"
    if confidence == "low":
        return "45" if production_model != "unknown" else "25"
    score = abs(_int_value(pod_score))
    if production_model == "unknown":
        return str(min(45, max(25, score)))
    return str(min(95, max(60, score)))


def _confidence_label(confidence: int) -> str:
    if confidence >= 90:
        return "high"
    if confidence >= 70:
        return "medium"
    return "low"


def _short_reason(reason: str) -> str:
    text = normalize_space(reason)
    if not text:
        return "Insufficient evidence."
    return text.split(";")[0].strip()[:220]


def _first_values(row: dict[str, str], fields: list[str]) -> list[str]:
    values = []
    for field in fields:
        value = row.get(field, "")
        if value:
            values.append(str(value))
    return values


def _has_any(groups: dict[str, list[str]], name: str) -> bool:
    return bool(groups.get(name))


def _matched_keywords(text: str, keywords: list[str]) -> list[str]:
    return [keyword for keyword in keywords if _contains_keyword(text, keyword)]


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(_contains_keyword(text, keyword) for keyword in keywords)


def _has_numbered_pack(text: str) -> bool:
    return re.search(r"(?<![a-z0-9])\d+\s*pack(?![a-z0-9])", text) is not None


def _contains_keyword(text: str, keyword: str) -> bool:
    phrase = _normalized_text(keyword)
    pattern = _KEYWORD_PATTERN_CACHE.get(phrase)
    if pattern is None:
        pattern = re.compile(r"(?<![a-z0-9])" + re.escape(phrase).replace(r"\ ", r"\s+") + r"(?![a-z0-9])")
        _KEYWORD_PATTERN_CACHE[phrase] = pattern
    return pattern.search(text) is not None


def _normalized_text(value: str) -> str:
    return (
        normalize_space(value)
        .lower()
        .replace("\u2019", "'")
        .replace("\u00e2\u20ac\u2122", "'")
        .replace("-", " ")
    )


def _int_value(value: object) -> int:
    try:
        return int(float(str(value or "").strip()))
    except ValueError:
        return 0
