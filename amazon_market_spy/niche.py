from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

from .utils import normalize_space


NICHE_FIELDS = ["niche_primary", "niche_secondary", "niche_tags", "niche_score", "niche_reason"]

NICHE_GROUPS = {
    "family": {
        "Dad",
        "Mom",
        "Grandma",
        "Grandpa",
        "Husband",
        "Wife",
        "Couple",
        "Son",
        "Daughter",
        "Baby",
        "Kids",
        "Family",
    },
    "occasion": {
        "Father's Day",
        "Mother's Day",
        "Birthday",
        "Christmas",
        "Halloween",
        "Thanksgiving",
        "Valentine's Day",
        "Easter",
        "4th of July",
        "Graduation",
        "Wedding",
        "Anniversary",
        "Baptism",
        "Memorial",
        "Retirement",
    },
    "profession": {
        "Teacher",
        "Nurse",
        "Doctor",
        "Firefighter",
        "Police",
        "Veteran",
        "Military",
        "Truck Driver",
        "Farmer",
        "Coach",
        "Boss",
        "Coworker",
    },
    "hobby": {
        "Camping",
        "Fishing",
        "Hunting",
        "Golf",
        "Baseball",
        "Football",
        "Soccer",
        "Pickleball",
        "Gym",
        "Fitness",
        "Yoga",
        "Gardening",
        "Cooking",
        "BBQ",
        "Coffee",
        "Wine",
        "Reading",
        "Gaming",
        "Music",
    },
    "pet": {"Dog", "Cat", "Horse", "Pet Memorial", "Dog Mom", "Dog Dad", "Cat Mom", "Cat Dad"},
    "identity": {
        "Christian",
        "Faith",
        "Jesus",
        "Bible",
        "Church",
        "Autism",
        "LGBTQ",
        "Black Pride",
        "Hispanic",
        "Irish",
        "Military Family",
    },
    "product": {
        "Personalized Mug",
        "Quote Mug",
        "Custom Shirt",
        "Custom Onesie",
        "Custom Ornament",
        "Custom Doormat",
        "Custom Sign",
        "Custom Blanket",
        "Custom Tumbler",
        "Custom Necklace",
        "Custom Keychain",
        "Custom Poster",
        "Custom Canvas",
    },
}

GROUP_LABELS = {
    "family": "Family / Relationship",
    "occasion": "Occasion",
    "profession": "Profession",
    "hobby": "Hobby",
    "pet": "Pet",
    "identity": "Identity / Community",
    "product": "Product Type",
    "unknown": "Unknown",
}


@dataclass(frozen=True)
class NicheRule:
    niche: str
    strong_phrases: tuple[str, ...] = ()
    exact_keywords: tuple[str, ...] = ()
    weak_keywords: tuple[str, ...] = ()
    kind: str = "exact"


NICHE_RULES = [
    NicheRule("Dad", exact_keywords=("dad", "father", "daddy"), weak_keywords=("papa",), kind="recipient"),
    NicheRule("Mom", exact_keywords=("mom", "mother", "mama", "mommy"), kind="recipient"),
    NicheRule("Grandma", exact_keywords=("grandma", "nana", "gigi"), kind="recipient"),
    NicheRule("Grandpa", exact_keywords=("grandpa", "pawpaw"), weak_keywords=("papa",), kind="recipient"),
    NicheRule("Husband", exact_keywords=("husband",), kind="recipient"),
    NicheRule("Wife", exact_keywords=("wife",), kind="recipient"),
    NicheRule("Couple", exact_keywords=("couple",), strong_phrases=("husband and wife", "mr and mrs"), kind="recipient"),
    NicheRule("Son", exact_keywords=("son",), kind="recipient"),
    NicheRule("Daughter", exact_keywords=("daughter",), kind="recipient"),
    NicheRule("Baby", exact_keywords=("baby", "infant", "newborn"), kind="recipient"),
    NicheRule("Kids", exact_keywords=("kid", "kids", "child", "children", "toddler"), kind="recipient"),
    NicheRule("Family", exact_keywords=("family",), kind="recipient"),
    NicheRule(
        "Father's Day",
        strong_phrases=("father's day", "fathers day", "father s day"),
        exact_keywords=("father day",),
        kind="occasion",
    ),
    NicheRule(
        "Mother's Day",
        strong_phrases=("mother's day", "mothers day", "mother s day"),
        exact_keywords=("mother day",),
        kind="occasion",
    ),
    NicheRule("Birthday", exact_keywords=("birthday", "bday"), kind="occasion"),
    NicheRule("Christmas", exact_keywords=("christmas", "xmas"), kind="occasion"),
    NicheRule("Halloween", exact_keywords=("halloween",), kind="occasion"),
    NicheRule("Thanksgiving", exact_keywords=("thanksgiving",), kind="occasion"),
    NicheRule(
        "Valentine's Day",
        strong_phrases=("valentine's day", "valentines day", "valentine s day"),
        exact_keywords=("valentine",),
        kind="occasion",
    ),
    NicheRule("Easter", exact_keywords=("easter",), kind="occasion"),
    NicheRule("4th of July", strong_phrases=("4th of july", "fourth of july", "independence day"), exact_keywords=("usa", "america"), kind="occasion"),
    NicheRule("Graduation", strong_phrases=("class of",), exact_keywords=("graduation", "graduate", "graduated"), kind="occasion"),
    NicheRule("Wedding", exact_keywords=("wedding", "bride", "groom"), kind="occasion"),
    NicheRule("Anniversary", exact_keywords=("anniversary",), kind="occasion"),
    NicheRule("Baptism", exact_keywords=("baptism", "baptized", "christening"), kind="occasion"),
    NicheRule("Memorial", strong_phrases=("in memory",), exact_keywords=("memorial", "remembrance"), kind="occasion"),
    NicheRule("Retirement", exact_keywords=("retirement", "retired"), kind="occasion"),
    NicheRule("Teacher", exact_keywords=("teacher",), strong_phrases=("teacher appreciation",), kind="profession"),
    NicheRule("Nurse", exact_keywords=("nurse", "rn"), kind="profession"),
    NicheRule("Doctor", exact_keywords=("doctor", "physician", "dr"), kind="profession"),
    NicheRule("Firefighter", exact_keywords=("firefighter", "fireman"), kind="profession"),
    NicheRule("Police", exact_keywords=("police", "cop", "sheriff"), kind="profession"),
    NicheRule("Veteran", exact_keywords=("veteran", "veterans"), kind="profession"),
    NicheRule("Military", exact_keywords=("military", "army", "navy", "marine", "air force"), kind="profession"),
    NicheRule("Truck Driver", exact_keywords=("trucker",), strong_phrases=("truck driver",), kind="profession"),
    NicheRule("Farmer", exact_keywords=("farmer",), kind="profession"),
    NicheRule("Coach", exact_keywords=("coach",), kind="profession"),
    NicheRule("Boss", exact_keywords=("boss",), kind="profession"),
    NicheRule("Coworker", exact_keywords=("coworker", "colleague"), kind="profession"),
    NicheRule("Camping", exact_keywords=("camping", "camper"), kind="exact"),
    NicheRule("Fishing", exact_keywords=("fishing", "fisherman", "angler"), kind="exact"),
    NicheRule("Hunting", exact_keywords=("hunting", "hunter"), kind="exact"),
    NicheRule("Golf", exact_keywords=("golf", "golfer"), kind="exact"),
    NicheRule("Baseball", exact_keywords=("baseball",), kind="exact"),
    NicheRule("Football", exact_keywords=("football",), kind="exact"),
    NicheRule("Soccer", exact_keywords=("soccer",), kind="exact"),
    NicheRule("Pickleball", exact_keywords=("pickleball",), kind="exact"),
    NicheRule("Gym", exact_keywords=("gym",), kind="exact"),
    NicheRule("Fitness", exact_keywords=("fitness", "workout"), kind="exact"),
    NicheRule("Yoga", exact_keywords=("yoga",), kind="exact"),
    NicheRule("Gardening", exact_keywords=("gardening", "garden"), kind="exact"),
    NicheRule("Cooking", exact_keywords=("cooking", "cook", "chef"), kind="exact"),
    NicheRule("BBQ", exact_keywords=("bbq", "barbecue", "grill"), kind="exact"),
    NicheRule("Coffee", exact_keywords=("coffee", "caffeine"), kind="exact"),
    NicheRule("Wine", exact_keywords=("wine",), kind="exact"),
    NicheRule("Reading", exact_keywords=("reading", "reader", "book", "books"), kind="exact"),
    NicheRule("Gaming", exact_keywords=("gaming", "gamer"), kind="exact"),
    NicheRule("Music", exact_keywords=("music", "musician", "guitar", "piano"), kind="exact"),
    NicheRule("Dog Mom", strong_phrases=("dog mom", "dog mama"), kind="recipient"),
    NicheRule("Dog Dad", strong_phrases=("dog dad", "dog father"), kind="recipient"),
    NicheRule("Cat Mom", strong_phrases=("cat mom", "cat mama"), kind="recipient"),
    NicheRule("Cat Dad", strong_phrases=("cat dad", "cat father"), kind="recipient"),
    NicheRule("Pet Memorial", strong_phrases=("pet memorial", "pet loss"), kind="occasion"),
    NicheRule("Dog", exact_keywords=("dog", "puppy"), kind="exact"),
    NicheRule("Cat", exact_keywords=("cat", "kitty", "kitten"), kind="exact"),
    NicheRule("Horse", exact_keywords=("horse", "equestrian"), kind="exact"),
    NicheRule("Christian", exact_keywords=("christian", "baptism", "baptized", "christening"), kind="recipient"),
    NicheRule("Faith", exact_keywords=("faith",), kind="exact"),
    NicheRule("Jesus", exact_keywords=("jesus",), kind="exact"),
    NicheRule("Bible", exact_keywords=("bible", "scripture"), kind="exact"),
    NicheRule("Church", exact_keywords=("church",), kind="exact"),
    NicheRule("Autism", exact_keywords=("autism", "autistic"), kind="exact"),
    NicheRule("LGBTQ", exact_keywords=("lgbtq", "pride"), kind="exact"),
    NicheRule("Black Pride", strong_phrases=("black pride",), kind="exact"),
    NicheRule("Hispanic", exact_keywords=("hispanic", "latina", "latino"), kind="exact"),
    NicheRule("Irish", exact_keywords=("irish",), kind="exact"),
    NicheRule("Military Family", strong_phrases=("military family", "army wife", "military wife"), kind="recipient"),
]

PRODUCT_NICHE_KEYWORDS = {
    "Personalized Mug": ("personalized mug", "custom mug", "coffee mug", "mug"),
    "Quote Mug": ("quote mug", "funny mug", "funny quote mug"),
    "Custom Shirt": ("custom shirt", "t-shirt", "t shirt", "tee", "shirt"),
    "Custom Onesie": ("custom onesie", "onesie", "baby bodysuit"),
    "Custom Ornament": ("custom ornament", "personalized ornament", "ornament"),
    "Custom Doormat": ("custom doormat", "personalized doormat", "doormat"),
    "Custom Sign": ("custom sign", "personalized sign", "sign"),
    "Custom Blanket": ("custom blanket", "personalized blanket", "blanket"),
    "Custom Tumbler": ("custom tumbler", "personalized tumbler", "tumbler"),
    "Custom Necklace": ("custom necklace", "personalized necklace", "necklace"),
    "Custom Keychain": ("custom keychain", "personalized keychain", "keychain"),
    "Custom Poster": ("custom poster", "personalized poster", "poster"),
    "Custom Canvas": ("custom canvas", "personalized canvas", "canvas"),
}

POD_TYPE_NICHES = {
    "personalized_mug": "Personalized Mug",
    "quote_mug": "Quote Mug",
    "custom_shirt": "Custom Shirt",
    "personalized_onesie": "Custom Onesie",
    "custom_doormat": "Custom Doormat",
}

CUSTOM_WORDS = ("custom", "personalized", "engraved", "printed", "monogram", "name", "photo", "quote")


def classify_niche(
    title: str = "",
    category: str = "",
    source_name: str = "",
    pod_type: str = "",
    pod_reason: str = "",
) -> dict[str, str]:
    title_text = _clean(title)
    category_text = _clean(category)
    source_text = _clean(source_name)
    pod_text = _clean(f"{pod_type} {pod_reason}")
    all_text = _clean(f"{title_text} {category_text} {source_text} {pod_text}")
    source_category_text = _clean(f"{category_text} {source_text}")

    scores: dict[str, int] = defaultdict(int)
    reasons: dict[str, list[str]] = defaultdict(list)

    for rule in NICHE_RULES:
        for phrase in rule.strong_phrases:
            if _contains_phrase(all_text, phrase):
                _add_score(scores, reasons, rule.niche, 60, phrase)
            if _contains_phrase(source_category_text, phrase):
                _add_score(scores, reasons, rule.niche, 15, phrase)
        for keyword in rule.exact_keywords:
            if _contains_phrase(all_text, keyword):
                value = 35 if rule.kind == "occasion" else 30 if rule.kind == "recipient" else 40
                _add_score(scores, reasons, rule.niche, value, keyword)
            if _contains_phrase(source_category_text, keyword):
                _add_score(scores, reasons, rule.niche, 15, keyword)
        for keyword in rule.weak_keywords:
            if _contains_phrase(all_text, keyword):
                _add_score(scores, reasons, rule.niche, 10, keyword)

    for niche, keywords in PRODUCT_NICHE_KEYWORDS.items():
        for keyword in keywords:
            if _contains_phrase(all_text, keyword):
                _add_score(scores, reasons, niche, 20, keyword)
                break

    pod_niche = POD_TYPE_NICHES.get((pod_type or "").strip().lower())
    if pod_niche:
        _add_score(scores, reasons, pod_niche, 20, pod_type)

    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    if not ranked:
        return {
            "niche_primary": "Unknown",
            "niche_secondary": "",
            "niche_tags": "Unknown",
            "niche_score": "0",
            "niche_reason": "",
        }

    primary, primary_score = ranked[0]
    secondary = next((niche for niche, score in ranked[1:] if score >= 30), "")
    tags = [niche for niche, score in ranked if score >= 30]
    if not tags:
        tags = [primary]

    return {
        "niche_primary": primary,
        "niche_secondary": secondary,
        "niche_tags": ";".join(tags),
        "niche_score": str(primary_score),
        "niche_reason": " + ".join(reasons[primary][:3]),
    }


def ensure_niche_fields(row: dict[str, str]) -> dict[str, str]:
    if all(str(row.get(field, "")).strip() for field in ("niche_primary", "niche_score")):
        for field in NICHE_FIELDS:
            row.setdefault(field, "")
        return row
    row.update(
        classify_niche(
            title=row.get("title", ""),
            category=row.get("category", ""),
            source_name=row.get("source_name", ""),
            pod_type=row.get("pod_type", ""),
            pod_reason=row.get("pod_reason", ""),
        )
    )
    return row


def niche_tags(row: dict[str, str]) -> list[str]:
    ensure_niche_fields(row)
    tags = [item.strip() for item in row.get("niche_tags", "").split(";") if item.strip()]
    return tags or ["Unknown"]


def niche_group(niche: str) -> str:
    for group, names in NICHE_GROUPS.items():
        if niche in names:
            return group
    return "unknown"


def niche_group_label(niche: str) -> str:
    return GROUP_LABELS.get(niche_group(niche), GROUP_LABELS["unknown"])


def _add_score(scores: dict[str, int], reasons: dict[str, list[str]], niche: str, value: int, reason: str) -> None:
    scores[niche] += value
    label = normalize_space(reason).lower()
    if label and label not in reasons[niche]:
        reasons[niche].append(label)


def _contains_phrase(text: str, phrase: str) -> bool:
    phrase_text = _clean(phrase)
    if not phrase_text:
        return False
    return re.search(rf"(?<![a-z0-9]){re.escape(phrase_text)}(?![a-z0-9])", text) is not None


def _clean(value: str) -> str:
    text = normalize_space(value).lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9']+", " ", text)
    return normalize_space(text)
