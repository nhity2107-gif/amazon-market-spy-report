from __future__ import annotations

import re
from collections import defaultdict
from datetime import date, datetime
from html import escape
from pathlib import Path
from urllib.parse import quote
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .category_rank import ensure_category_rank_fields
from .evidence import EVIDENCE_FIELDS, PRODUCT_EVIDENCE_FIELDS, apply_observation_evidence
from .niche import GROUP_LABELS, ensure_niche_fields, niche_group, niche_tags
from .pod import ensure_pod_fields, pod_allowed
from .product_details import display_product_title, ensure_detail_fix_fields
from .reporting import LARK_TREND_ALERT_FIELDS, write_csv
from .source_identity import parse_source_rank
from .utils import ensure_parent, is_asin


IMAGE_TIMEOUT_SECONDS = 20
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125 Safari/537.36"

REPORT_PAGES = {
    "priority_board": "priority_board.html",
    "product_discovery": "product_discovery.html",
    "products": "products.html",
    "competitor": "competitor.html",
    "trend_explorer": "trend_explorer.html",
    "product_detail": "product_detail.html",
    "top_winners": "top_winners.html",
    "new_breakouts": "new_breakouts.html",
    "fast_movers": "fast_movers.html",
    "new_releases": "new_releases.html",
    "trends": "trends.html",
    "database": "database.html",
    "top_opportunities": "top_opportunities.html",
    "image_gallery": "image_gallery.html",
    "all_opportunities": "all_opportunities.html",
    "new_products": "new_products.html",
    "rising_products": "rising_products.html",
    "seller_intelligence": "seller_intelligence.html",
    "niche_intelligence": "niche_intelligence.html",
    "source_explorer": "source_explorer.html",
    "non_pod_excluded": "non_pod_excluded.html",
}

NAV_ITEMS = [
    ("Product Discovery", "product_discovery.html"),
    ("Today", "index.html"),
    ("Competitor", "competitor.html"),
    ("Trend Explorer", "trend_explorer.html"),
]

SORT_OPTIONS = [
    ("", "Current Order"),
    ("winnerSignalScore", "Signal Score"),
    ("decisionScore", "Decision Score"),
    ("opportunityScore", "Opportunity Score"),
    ("bestMovers", "Best Movers"),
    ("largestRankImprovement", "Largest Rank Improvement"),
    ("highestVelocity", "Highest Velocity"),
    ("topPercentile", "Top Percentile"),
    ("subcategoryRank", "Best Subcategory BSR"),
    ("categoryRank", "Amazon BSR"),
    ("reviewCount", "Review Count"),
    ("rankChange", "Rank Change"),
    ("growthVelocity", "Growth Velocity"),
    ("newBreakoutScore", "New Breakout Score"),
    ("podScore", "POD Score"),
]

PRIORITY_BOARD_FIELDS = [
    "asin",
    "primary_bucket",
    "badges",
    "badge_count",
    "decision_score",
    "title",
    "seller_name",
    "niche_primary",
    "source_name",
    "source_type",
    "source_id",
    "source_rank",
    "previous_source_rank",
    "source_rank_change",
    "source_observation_count",
    "source_days_seen",
    "marketplace",
    "category_id",
    "category_name",
    *EVIDENCE_FIELDS,
    *PRODUCT_EVIDENCE_FIELDS,
    "display_rank",
    "previous_display_rank",
    "display_rank_change",
    "growth_velocity",
    "opportunity_score",
    "primary_bsr_rank",
    "sub_bsr_rank",
    "product_url",
    "image_url",
    # Compatibility columns kept for existing downstream imports.
    "badge",
    "days_seen",
    "first_seen",
    "new_breakout_score",
]

SELLER_INTELLIGENCE_FIELDS = [
    "seller_name",
    "seller_id",
    "source_name",
    "source_type",
    "products_tracked",
    "new_wins",
    "rising_products",
    "average_rank",
    "review_growth_7d",
    "review_growth_30d",
    "review_velocity_score",
    "momentum_score",
    "pod_products",
    "pod_opportunities",
    "pod_momentum_score",
    "best_subcategory_rank",
    "best_subcategory_product",
    "seller_url",
]

TODAY_SECTION_LIMITS = {
    "New Winners": 8,
    "Fast Rising": 8,
    "Competitor Launches": 8,
    "Emerging Trends": 6,
}

TODAY_TOTAL_LIMIT = 30
PRODUCT_DETAIL_DIR = "product_detail"

PRODUCT_TYPE_TERMS = {
    "personalized_mug": "Mug",
    "quote_mug": "Mug",
    "custom_shirt": "Shirt",
    "engraved_gift": "Engraved Gift",
    "custom_doormat": "Doormat",
    "personalized_onesie": "Baby Onesie",
    "physical_brand_product": "Physical Product",
}

PRODUCT_TYPE_KEYWORDS = [
    ("t-shirt", "T-Shirt"),
    ("tee", "T-Shirt"),
    ("shirt", "Shirt"),
    ("mug", "Mug"),
    ("hoodie", "Hoodie"),
    ("sweatshirt", "Sweatshirt"),
    ("ornament", "Ornament"),
    ("socks", "Socks"),
    ("tumbler", "Tumbler"),
    ("doormat", "Doormat"),
    ("poster", "Poster"),
    ("sign", "Sign"),
    ("plaque", "Plaque"),
    ("sticker", "Sticker"),
    ("phone case", "Phone Case"),
    ("tote", "Tote Bag"),
    ("candle", "Candle"),
    ("blanket", "Blanket"),
    ("pillow", "Pillow"),
    ("hat", "Hat"),
    ("apron", "Apron"),
]

RECIPIENT_KEYWORDS = [
    ("dog mom", "Dog Mom"),
    ("dog dad", "Dog Dad"),
    ("cat mom", "Cat Mom"),
    ("cat dad", "Cat Dad"),
    ("grandma", "Grandma"),
    ("grandpa", "Grandpa"),
    ("father", "Dad"),
    ("dad", "Dad"),
    ("mother", "Mom"),
    ("mom", "Mom"),
    ("husband", "Husband"),
    ("wife", "Wife"),
    ("teacher", "Teacher"),
    ("nurse", "Nurse"),
    ("doctor", "Doctor"),
    ("coach", "Coach"),
    ("boss", "Boss"),
    ("coworker", "Coworker"),
    ("daughter", "Daughter"),
    ("son", "Son"),
    ("sister", "Sister"),
    ("brother", "Brother"),
    ("friend", "Friend"),
]

OCCASION_KEYWORDS = [
    ("father's day", "Father's Day"),
    ("fathers day", "Father's Day"),
    ("mother's day", "Mother's Day"),
    ("mothers day", "Mother's Day"),
    ("4th of july", "4th of July"),
    ("fourth of july", "4th of July"),
    ("independence day", "4th of July"),
    ("birthday", "Birthday"),
    ("christmas", "Christmas"),
    ("halloween", "Halloween"),
    ("thanksgiving", "Thanksgiving"),
    ("valentine", "Valentine's Day"),
    ("easter", "Easter"),
    ("graduation", "Graduation"),
    ("wedding", "Wedding"),
    ("anniversary", "Anniversary"),
    ("retirement", "Retirement"),
    ("memorial", "Memorial"),
]

THEME_KEYWORDS = [
    ("baseball", "Baseball"),
    ("soccer", "Soccer"),
    ("football", "Football"),
    ("basketball", "Basketball"),
    ("golf", "Golf"),
    ("coffee", "Coffee"),
    ("dog", "Dog"),
    ("cat", "Cat"),
    ("patriotic", "Patriotic"),
    ("american flag", "Patriotic"),
    ("faith", "Faith"),
    ("christian", "Faith"),
    ("funny", "Funny"),
    ("fishing", "Fishing"),
    ("camping", "Camping"),
    ("pickleball", "Pickleball"),
    ("teacher", "Teacher"),
    ("nurse", "Nurse"),
]

QUOTE_KEYWORDS = [
    ("best dad", "Best Dad"),
    ("best mom", "Best Mom"),
    ("dad joke", "Dad Joke"),
    ("mama", "Mama"),
    ("in my era", "In My Era"),
    ("just a girl", "Just A Girl"),
    ("blessed", "Blessed"),
    ("groovy", "Groovy"),
    ("retro", "Retro"),
    ("vintage", "Vintage"),
    ("team bride", "Team Bride"),
    ("proud", "Proud"),
    ("cool", "Cool"),
]


def write_lark_opportunity_artifacts(
    output_dir: Path,
    rows: list[dict[str, str]],
    all_opportunities: list[dict[str, str]] | None = None,
    products: list[dict[str, str]] | None = None,
    seller_rows: list[dict[str, str]] | None = None,
    niche_rows: list[dict[str, str]] | None = None,
    product_history_rows: list[dict[str, str]] | None = None,
    include_non_pod: bool = False,
) -> dict[str, str]:
    rows = [ensure_detail_fix_fields(ensure_category_rank_fields(ensure_niche_fields(ensure_pod_fields(row)))) for row in rows]
    opportunity_rows = [
        ensure_detail_fix_fields(ensure_category_rank_fields(ensure_niche_fields(ensure_pod_fields(row))))
        for row in (all_opportunities if all_opportunities is not None else rows)
    ]
    latest_products = [
        ensure_detail_fix_fields(ensure_category_rank_fields(ensure_niche_fields(ensure_pod_fields(row))))
        for row in (products or [])
    ]
    seller_intelligence = seller_rows or []
    niche_intelligence = niche_rows or []
    visible_opportunities = opportunity_rows if include_non_pod else [row for row in opportunity_rows if pod_allowed(row)]
    visible_products = latest_products if include_non_pod else [row for row in latest_products if pod_allowed(row)]
    excluded_products = [row for row in latest_products if not pod_allowed(row)]
    decision_rows = _decision_product_rows(visible_products, visible_opportunities)
    history_by_asin = _history_by_asin(product_history_rows or [], decision_rows)
    trend_clusters = _trend_clusters(decision_rows)
    today_sections = _today_signal_sections(decision_rows, trend_clusters)

    enrich_local_images(output_dir, rows)
    if opportunity_rows is not rows:
        enrich_local_images(output_dir, opportunity_rows)

    lark_path = output_dir / "lark_trend_alerts.csv"
    write_csv(lark_path, rows, LARK_TREND_ALERT_FIELDS)
    priority_csv_path = output_dir / "priority_board.csv"
    write_csv(priority_csv_path, _priority_board_csv_rows(decision_rows), PRIORITY_BOARD_FIELDS)

    paths = {
        "lark_trend_alerts": str(lark_path),
        "priority_board_csv": str(priority_csv_path),
        "index": str(output_dir / "index.html"),
        **{key: str(output_dir / filename) for key, filename in REPORT_PAGES.items()},
    }

    priority_html = _priority_board_html(
        sections=today_sections,
        all_rows=decision_rows,
        shown_rows=[row for _, section_rows in today_sections for row in section_rows],
    )
    ensure_parent(output_dir / REPORT_PAGES["priority_board"])
    (output_dir / REPORT_PAGES["priority_board"]).write_text(priority_html, encoding="utf-8")
    (output_dir / "index.html").write_text(priority_html, encoding="utf-8")
    discovery_html = _product_discovery_html(decision_rows)
    ensure_parent(output_dir / REPORT_PAGES["product_discovery"])
    (output_dir / REPORT_PAGES["product_discovery"]).write_text(discovery_html, encoding="utf-8")
    (output_dir / REPORT_PAGES["products"]).write_text(discovery_html, encoding="utf-8")
    write_competitor_html(
        output_dir / REPORT_PAGES["competitor"],
        seller_intelligence,
        decision_rows,
    )
    (output_dir / REPORT_PAGES["seller_intelligence"]).write_text(
        (output_dir / REPORT_PAGES["competitor"]).read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    trend_html = _trend_explorer_html(trend_clusters)
    ensure_parent(output_dir / REPORT_PAGES["trend_explorer"])
    (output_dir / REPORT_PAGES["trend_explorer"]).write_text(trend_html, encoding="utf-8")
    (output_dir / REPORT_PAGES["trends"]).write_text(trend_html, encoding="utf-8")
    write_product_detail_pages(
        output_dir,
        decision_rows,
        history_by_asin,
    )
    write_compat_redirect_page(output_dir / REPORT_PAGES["top_winners"], "Top Winners", "product_discovery.html?signal=stable-winner")
    write_compat_redirect_page(output_dir / REPORT_PAGES["new_breakouts"], "New Breakouts", "product_discovery.html?signal=new-winner")
    write_compat_redirect_page(output_dir / REPORT_PAGES["fast_movers"], "Fast Movers", "product_discovery.html?signal=fast-rising")
    write_compat_redirect_page(output_dir / REPORT_PAGES["new_releases"], "New Releases", "product_discovery.html?signal=new-release")
    write_compat_redirect_page(output_dir / REPORT_PAGES["top_opportunities"], "Top Opportunities", "product_discovery.html")
    write_compat_redirect_page(output_dir / REPORT_PAGES["image_gallery"], "Image Gallery", "product_discovery.html")
    write_compat_redirect_page(output_dir / REPORT_PAGES["all_opportunities"], "All Products", "product_discovery.html")
    write_compat_redirect_page(output_dir / REPORT_PAGES["new_products"], "New Products", "product_discovery.html?signal=new-winner")
    write_compat_redirect_page(output_dir / REPORT_PAGES["rising_products"], "Rising Products", "product_discovery.html?signal=fast-rising")
    write_compat_redirect_page(output_dir / REPORT_PAGES["niche_intelligence"], "Niche Intelligence", "trend_explorer.html")
    write_compat_redirect_page(output_dir / REPORT_PAGES["database"], "Database", "product_discovery.html")
    write_compat_redirect_page(output_dir / REPORT_PAGES["source_explorer"], "Source Explorer", "competitor.html")
    write_opportunity_html(
        output_dir / REPORT_PAGES["non_pod_excluded"],
        excluded_products,
        "Non-POD Excluded",
        "Excluded Non-POD",
    )
    return paths


def enrich_local_images(output_dir: Path, rows: list[dict[str, str]]) -> None:
    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    for row in rows:
        row.setdefault("local_image_path", "")
        asin = row.get("asin", "").strip().upper()
        image_url = row.get("image_url", "").strip()
        if not is_asin(asin) or not image_url:
            continue
        target = images_dir / f"{asin}.jpg"
        if not target.exists():
            _download_image(image_url, target)
        if target.exists():
            row["local_image_path"] = f"images/{asin}.jpg"


def _priority_board_html(
    *,
    sections: list[tuple[str, list[dict[str, str]]]],
    all_rows: list[dict[str, str]],
    shown_rows: list[dict[str, str]],
) -> str:
    section_html = "\n".join(_priority_section(title, rows) for title, rows in sections)
    return _page(
        title="Today",
        active_label="Today",
        body=f"""    <section class="summary">
{_summary([
            ("High-value signals", str(len(shown_rows))),
            ("New winners", str(len([row for row in shown_rows if _is_new_winner(row)]))),
            ("Fast rising", str(len([row for row in shown_rows if _is_fast_rising(row)]))),
            ("Competitor launches", str(len([row for row in shown_rows if _is_competitor_launch(row)]))),
        ])}
    </section>
{section_html}""",
    )


def _priority_section(title: str, rows: list[dict[str, str]]) -> str:
    cards = "\n".join(_opportunity_card(row, index, compact=True) for index, row in enumerate(rows))
    if not cards:
        cards = '      <div class="empty">No high-value signals in this section.</div>'
    return f"""    <section class="priority-section">
      <div class="section-heading">
        <h2>{escape(title)}</h2>
        <span>{escape(str(len(rows)))} products</span>
      </div>
      <section class="grid priority-grid" data-sortable-cards>
{cards}
      </section>
    </section>"""


def _product_discovery_html(rows: list[dict[str, str]]) -> str:
    sorted_rows = sorted(rows, key=_signal_sort_key)
    cards = "\n".join(_opportunity_card(row, index) for index, row in enumerate(sorted_rows))
    if not cards:
        cards = '      <div class="empty">No products match current filters.</div>'
    load_more = (
        '    <button class="load-more" type="button" data-card-step="40">Load more</button>'
        if len(sorted_rows) > 60
        else ""
    )
    return _page(
        title="Product Discovery",
        active_label="Product Discovery",
        body=f"""    <section class="summary">
{_summary([
            ("Products", str(len(sorted_rows))),
            ("New winners", str(len([row for row in sorted_rows if _is_new_winner(row)]))),
            ("Fast rising", str(len([row for row in sorted_rows if _is_fast_rising(row)]))),
            ("Stable winners", str(len([row for row in sorted_rows if _is_stable_winner(row)]))),
        ])}
    </section>
{_product_controls(sorted_rows, include_search=True)}
    <div class="empty filter-empty is-hidden" data-filter-empty>No products match current filters.</div>
    <section class="grid discovery-grid" data-sortable-cards>
{cards}
    </section>
{load_more}""",
        extra_script=_card_interaction_script(),
    )


def write_competitor_html(
    path: Path,
    seller_rows: list[dict[str, str]],
    product_rows: list[dict[str, str]],
) -> None:
    ensure_parent(path)
    competitors = _competitor_sections(seller_rows, product_rows)
    body = "\n".join(competitors)
    if not body:
        body = '    <div class="empty">No competitor products found.</div>'
    path.write_text(
        _page(
            title="Competitor",
            active_label="Competitor",
            body=f"""    <section class="summary">
{_summary([
                ("Competitors", str(len(seller_rows))),
                ("Seller products", str(len([row for row in product_rows if _is_seller_source(row)]))),
                ("New launches", str(len([row for row in product_rows if _is_competitor_launch(row)]))),
                ("Rising products", str(len([row for row in product_rows if _is_fast_rising(row)]))),
            ])}
    </section>
{body}""",
        ),
        encoding="utf-8",
    )


def _trend_explorer_html(clusters: list[dict[str, object]]) -> str:
    cards = "\n".join(_trend_cluster_card(cluster, index) for index, cluster in enumerate(clusters[:80]))
    if not cards:
        cards = '      <div class="empty">No trend signals found.</div>'
    return _page(
        title="Trend Explorer",
        active_label="Trend Explorer",
        body=f"""    <section class="summary">
{_summary([
            ("Trend groups", str(len(clusters))),
            ("High-signal groups", str(len([cluster for cluster in clusters if int(cluster.get("signal", 0) or 0) >= 70]))),
            ("Products clustered", str(sum(int(cluster.get("product_count", 0) or 0) for cluster in clusters))),
            ("Seller count", str(len({seller for cluster in clusters for seller in cluster.get("sellers", set())}))),
        ])}
    </section>
    <section class="trend-clusters">
{cards}
    </section>""",
        extra_script=_card_interaction_script(),
    )


def _decision_product_rows(
    product_rows: list[dict[str, str]],
    opportunity_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    opportunity_by_asin: dict[str, dict[str, str]] = {}
    for row in opportunity_rows:
        asin = row.get("asin", "").strip().upper()
        if not asin:
            continue
        current = opportunity_by_asin.get(asin)
        if current is None or _decision_overlay_sort_key(row) < _decision_overlay_sort_key(current):
            opportunity_by_asin[asin] = row

    merged_rows: list[dict[str, str]] = []
    seen_asins: set[str] = set()
    for row in product_rows:
        asin = row.get("asin", "").strip().upper()
        merged = dict(row)
        if asin and asin in opportunity_by_asin:
            _merge_decision_overlay(merged, opportunity_by_asin[asin])
        _ensure_decision_fields(merged)
        merged_rows.append(merged)
        if asin:
            seen_asins.add(asin)

    for asin, row in opportunity_by_asin.items():
        if asin in seen_asins:
            continue
        merged = dict(row)
        _ensure_decision_fields(merged)
        merged_rows.append(merged)

    return sorted(_dedupe_decision_products(merged_rows), key=_today_sort_key)


def _decision_overlay_sort_key(row: dict[str, str]) -> tuple[int, int, str]:
    return (
        _product_display_rank(row),
        -(_to_int(row.get("opportunity_score", "")) or 0),
        row.get("asin", ""),
    )


def _merge_decision_overlay(target: dict[str, str], overlay: dict[str, str]) -> None:
    preserve_fields = {
        "title",
        "raw_title",
        "image_url",
        "local_image_path",
        "product_url",
        "seller_name",
        "seller_id",
        "seller_url",
        "source_name",
        "source_type",
        "page_type",
        "category",
        "display_rank",
        "display_order",
        "rank",
        "position",
    }
    for field, value in overlay.items():
        text = str(value or "").strip()
        if not text:
            continue
        if field in preserve_fields and (target.get(field, "") or "").strip():
            continue
        if not (target.get(field, "") or "").strip():
            target[field] = text


def _dedupe_decision_products(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[str, list[tuple[int, dict[str, str]]]] = defaultdict(list)
    for index, row in enumerate(rows):
        _ensure_decision_fields(row)
        grouped[_dedupe_product_key(row, index)].append((index, row))

    deduped: list[dict[str, str]] = []
    for group_rows in grouped.values():
        rows_only = [row for _, row in group_rows]
        flags = _combined_badge_flags(rows_only)
        source_summary = _combined_source_summary(rows_only)
        best_index, best_row = min(group_rows, key=lambda item: _decision_best_sort_key(item[1], item[0]))
        merged = dict(best_row)
        merged.update(source_summary)
        _apply_badge_flags(merged, flags)
        _ensure_decision_fields(merged)
        deduped.append(merged)
    return deduped


def _combined_source_summary(rows: list[dict[str, str]]) -> dict[str, str]:
    source_keys: dict[str, str] = {}
    source_types: dict[str, str] = {}
    source_names: dict[str, str] = {}
    for row in rows:
        source_name = row.get("source_name", "") or row.get("seller_name", "") or "Unknown"
        source_type = row.get("source_type", "") or row.get("page_type", "") or "Unknown"
        source_key = _join_key(f"{source_type}:{source_name}")
        if source_key:
            source_keys[source_key] = source_name
        type_key = _join_key(source_type)
        if type_key:
            source_types[type_key] = source_type
        name_key = _join_key(source_name)
        if name_key:
            source_names[name_key] = source_name
    return {
        "source_count": str(len(source_keys) or 1),
        "source_types": "; ".join(sorted(source_types.values())),
        "source_names": "; ".join(sorted(source_names.values())),
    }


def _decision_best_sort_key(row: dict[str, str], index: int) -> tuple[int, int, int, str]:
    return (
        -(_to_int(row.get("decision_score", "")) or 0),
        _product_display_rank(row),
        index,
        row.get("asin", ""),
    )


def _combined_badge_flags(rows: list[dict[str, str]]) -> dict[str, bool]:
    flags = {
        "top_winner": False,
        "fast_mover": False,
        "new_breakout": False,
        "new_release": False,
        "top_10": False,
        "pod": False,
    }
    for row in rows:
        row_flags = _derived_badge_flags(row)
        for name, value in row_flags.items():
            flags[name] = flags[name] or value
    return flags


def _derived_badge_flags(row: dict[str, str]) -> dict[str, bool]:
    return {
        "top_winner": _derived_is_top_winner(row),
        "fast_mover": _derived_is_fast_mover(row),
        "new_breakout": _derived_is_new_breakout(row),
        "new_release": _derived_is_new_release_source(row),
        "top_10": _is_top_10(row),
        "pod": pod_allowed(row),
    }


def _apply_badge_flags(row: dict[str, str], flags: dict[str, bool]) -> None:
    for name, value in flags.items():
        row[f"badge_{name}"] = _bool_attr(value)


def _today_sort_key(row: dict[str, str]) -> tuple[int, int, int, str]:
    _ensure_decision_fields(row)
    return (
        -(_to_int(row.get("decision_score", "")) or 0),
        _bucket_sort_order(row.get("primary_bucket", "")),
        _product_display_rank(row),
        row.get("asin", ""),
    )


def _bucket_sort_order(bucket: str) -> int:
    order = {
        "Must Review Today": 0,
        "New Breakouts": 1,
        "Fast Movers": 2,
        "Watchlist": 3,
        "Products": 4,
    }
    return order.get(bucket, 99)


def _today_bucket_sections(rows: list[dict[str, str]]) -> list[tuple[str, list[dict[str, str]]]]:
    buckets = {
        "Must Review Today": [],
        "New Breakouts": [],
        "Fast Movers": [],
        "Watchlist": [],
    }
    for row in rows:
        bucket = row.get("primary_bucket", "") or _primary_bucket(row)
        if bucket not in buckets:
            bucket = "Watchlist"
        buckets[bucket].append(row)
    return [(title, buckets[title]) for title in buckets]


def _today_signal_sections(
    rows: list[dict[str, str]],
    trend_clusters: list[dict[str, object]],
) -> list[tuple[str, list[dict[str, str]]]]:
    used: set[str] = set()
    sections: list[tuple[str, list[dict[str, str]]]] = []

    def pick(candidates: list[dict[str, str]], limit: int) -> list[dict[str, str]]:
        picked: list[dict[str, str]] = []
        for row in sorted(candidates, key=_signal_sort_key):
            key = _dedupe_product_key(row, len(used))
            if key in used:
                continue
            picked.append(row)
            used.add(key)
            if len(picked) >= limit:
                break
        return picked

    sections.append(("New Winners", pick([row for row in rows if _is_new_winner(row)], TODAY_SECTION_LIMITS["New Winners"])))
    sections.append(("Fast Rising", pick([row for row in rows if _is_fast_rising(row)], TODAY_SECTION_LIMITS["Fast Rising"])))
    sections.append(("Competitor Launches", pick([row for row in rows if _is_competitor_launch(row)], TODAY_SECTION_LIMITS["Competitor Launches"])))

    trend_candidates: list[dict[str, str]] = []
    for cluster in trend_clusters:
        for row in cluster.get("products", []):
            if isinstance(row, dict):
                trend_candidates.append(row)
                break
        if len(trend_candidates) >= TODAY_SECTION_LIMITS["Emerging Trends"] * 2:
            break
    sections.append(("Emerging Trends", pick(trend_candidates, TODAY_SECTION_LIMITS["Emerging Trends"])))

    total = 0
    capped_sections: list[tuple[str, list[dict[str, str]]]] = []
    for title, section_rows in sections:
        remaining = max(0, TODAY_TOTAL_LIMIT - total)
        capped = section_rows[:remaining]
        capped_sections.append((title, capped))
        total += len(capped)
    return capped_sections


def _primary_bucket(row: dict[str, str]) -> str:
    if _is_top_winner(row) or _is_top_10(row):
        return "Must Review Today"
    if _is_new_breakout(row):
        return "New Breakouts"
    if _is_fast_mover(row):
        return "Fast Movers"
    return "Watchlist"


def _ensure_decision_fields(row: dict[str, str]) -> None:
    ensure_detail_fix_fields(ensure_category_rank_fields(ensure_niche_fields(ensure_pod_fields(row))))
    apply_observation_evidence(row)
    growth_velocity = _growth_velocity_value(row)
    top_rank_score = _top_rank_score(row)
    velocity_score = _velocity_score(row)
    newness_score = _newness_score(row)
    bsr_score = _bsr_score(row)
    pod_score = _to_int(row.get("pod_score", "")) or 0
    badges = _badges_for_row(row)
    badge_count = len(badges)
    opportunity_score = _to_int(row.get("opportunity_score", "")) or 0
    decision_score = opportunity_score + top_rank_score + velocity_score + newness_score + bsr_score + pod_score + (badge_count * 5)
    winner_signal_score = _winner_signal_score(row)
    row["growth_velocity"] = _format_decimal(growth_velocity)
    row["top_rank_score"] = str(top_rank_score)
    row["velocity_score"] = str(velocity_score)
    row["newness_score"] = str(newness_score)
    row["bsr_score"] = str(bsr_score)
    row["new_breakout_score"] = str(newness_score + velocity_score + top_rank_score + pod_score)
    row["badges"] = "; ".join(badges)
    row["badge_count"] = str(badge_count)
    row["decision_score"] = str(decision_score)
    row["winner_signal_score"] = str(winner_signal_score)
    row["signal_score"] = str(winner_signal_score)
    row["primary_bucket"] = _primary_bucket(row)
    if not row.get("first_seen", ""):
        row["first_seen"] = _first_seen_value(row)


def _top_winner_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(
        [row for row in rows if _is_top_winner(row)],
        key=lambda row: (
            _product_display_rank(row),
            _subcategory_rank_number(row) or 10**9,
            -(_to_int(row.get("opportunity_score", "")) or 0),
            row.get("asin", ""),
        ),
    )


def _fast_mover_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(
        [row for row in rows if _is_fast_mover(row)],
        key=lambda row: (
            -_rank_movement_value(row),
            -(_to_int(row.get("opportunity_score", "")) or 0),
            _product_display_rank(row),
            row.get("asin", ""),
        ),
    )


def _new_breakout_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(
        [row for row in rows if _is_new_breakout(row)],
        key=lambda row: (
            -_rank_movement_value(row),
            _product_display_rank(row),
            -(_to_int(row.get("opportunity_score", "")) or 0),
            row.get("asin", ""),
        ),
    )


def _new_release_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(
        [row for row in rows if _is_new_release_source(row)],
        key=lambda row: (
            _product_display_rank(row),
            -_rank_movement_value(row),
            _to_int(row.get("days_seen", "")) or 10**9,
            row.get("asin", ""),
        ),
    )


def _watchlist_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    priority_asins = {
        row.get("asin", "").strip().upper()
        for group in (_top_winner_rows(rows), _fast_mover_rows(rows), _new_breakout_rows(rows))
        for row in group
    }
    candidates = [row for row in rows if row.get("asin", "").strip().upper() not in priority_asins]
    return sorted(
        candidates,
        key=lambda row: (
            -(_to_int(row.get("opportunity_score", "")) or 0),
            _subcategory_rank_number(row) or 10**9,
            _product_display_rank(row),
            row.get("asin", ""),
        ),
    )


def _priority_board_csv_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    csv_rows: list[dict[str, str]] = []
    for row in sorted(rows, key=_priority_csv_sort_key):
        _ensure_decision_fields(row)
        badges = _badges_for_row(row)
        csv_rows.append(
            {
                "asin": row.get("asin", "").strip().upper(),
                "primary_bucket": row.get("primary_bucket", ""),
                "badges": "; ".join(badges),
                "badge_count": row.get("badge_count", ""),
                "decision_score": row.get("decision_score", ""),
                "title": display_product_title(row.get("title", "")),
                "seller_name": row.get("seller_name", ""),
                "niche_primary": row.get("niche_primary", ""),
                "source_name": row.get("source_name", ""),
                "source_type": row.get("source_type", "") or row.get("page_type", ""),
                "source_id": row.get("source_id", ""),
                "source_rank": row.get("source_rank", ""),
                "previous_source_rank": row.get("previous_source_rank", ""),
                "source_rank_change": row.get("source_rank_change", ""),
                "source_observation_count": row.get("source_observation_count", ""),
                "source_days_seen": row.get("source_days_seen", ""),
                "marketplace": row.get("marketplace", ""),
                "category_id": row.get("category_id", ""),
                "category_name": row.get("category_name", ""),
                **{field: row.get(field, "") for field in EVIDENCE_FIELDS},
                **{field: row.get(field, "") for field in PRODUCT_EVIDENCE_FIELDS},
                "badge": "; ".join(badges) if badges else "Watchlist",
                "display_rank": row.get("display_rank", "") or row.get("source_rank", "") or row.get("display_order", "") or row.get("rank", ""),
                "previous_display_rank": row.get("previous_display_rank", ""),
                "display_rank_change": row.get("display_rank_change", "") or row.get("source_rank_change", "") or _rank_change(row),
                "growth_velocity": row.get("growth_velocity", ""),
                "opportunity_score": row.get("opportunity_score", ""),
                "primary_bsr_rank": row.get("primary_bsr_rank", "") or row.get("bsr_rank", ""),
                "sub_bsr_rank": row.get("sub_bsr_rank", ""),
                "product_url": _amazon_product_url(row),
                "image_url": row.get("image_url", ""),
                "days_seen": row.get("days_seen", ""),
                "first_seen": _first_seen_value(row),
                "new_breakout_score": row.get("new_breakout_score", ""),
            }
        )
    return csv_rows


def _priority_csv_sort_key(row: dict[str, str]) -> tuple[int, int, int, str]:
    return _today_sort_key(row)


def write_opportunity_html(
    path: Path,
    rows: list[dict[str, str]],
    title: str,
    active_label: str,
    summary_items: list[tuple[str, str]] | None = None,
    default_badge: str = "",
) -> None:
    ensure_parent(path)
    cards = "\n".join(_opportunity_card(row, index, default_badge=default_badge) for index, row in enumerate(rows))
    if not cards:
        cards = '      <div class="empty">No records found.</div>'
    summary = _summary(summary_items or [("Records", str(len(rows)))])
    controls = _product_controls(rows)
    load_more = (
        '    <button class="load-more" type="button" data-card-step="40">Load more</button>'
        if len(rows) > 60
        else ""
    )
    path.write_text(
        _page(
            title=title,
            active_label=active_label,
            body=f"""    <section class="summary">
{summary}
    </section>
{controls}
    <section class="grid" data-sortable-cards>
{cards}
    </section>
{load_more}""",
            extra_script=_card_interaction_script(),
        ),
        encoding="utf-8",
    )


def write_products_html(path: Path, rows: list[dict[str, str]]) -> None:
    ensure_parent(path)
    sorted_rows = sorted(rows, key=_today_sort_key)
    cards = "\n".join(_opportunity_card(row, index) for index, row in enumerate(sorted_rows))
    if not cards:
        cards = '      <div class="empty">No products match current filters.</div>'
    load_more = (
        '    <button class="load-more" type="button" data-card-step="40">Load more</button>'
        if len(sorted_rows) > 60
        else ""
    )
    path.write_text(
        _page(
            title="Products",
            active_label="Products",
            body=f"""    <section class="summary">
{_summary([
                ("Products", str(len(sorted_rows))),
                ("Top winners", str(len([row for row in sorted_rows if "Top Winner" in _badges_for_row(row)]))),
                ("Fast movers", str(len([row for row in sorted_rows if "Fast Mover" in _badges_for_row(row)]))),
                ("New releases", str(len([row for row in sorted_rows if "New Release" in _badges_for_row(row)]))),
            ])}
    </section>
{_product_controls(sorted_rows, include_badge_filter=True, include_source_type_filter=True, include_search=True, include_bsr_filter=True)}
    <div class="empty filter-empty is-hidden" data-filter-empty>No products match current filters.</div>
    <section class="grid" data-sortable-cards>
{cards}
    </section>
{load_more}""",
            extra_script=_card_interaction_script(),
        ),
        encoding="utf-8",
    )


def write_filter_redirect_page(path: Path, title: str, badge: str) -> None:
    write_compat_redirect_page(path, title, f"product_discovery.html?signal={_query_value(_signal_query_from_badge(badge))}")


def write_compat_redirect_page(path: Path, title: str, target: str) -> None:
    ensure_parent(path)
    path.write_text(
        f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="0; url={escape(target, quote=True)}">
  <title>{escape(title)}</title>
</head>
<body>
  <p>{escape(title)} moved to <a href="{escape(target, quote=True)}">Product Discovery</a>.</p>
</body>
</html>
""",
        encoding="utf-8",
    )


def write_trends_html(
    path: Path,
    rows: list[dict[str, str]],
    seller_rows: list[dict[str, str]],
    niche_rows: list[dict[str, str]],
) -> None:
    ensure_parent(path)
    product_types = _top_counts(
        (row.get("niche_primary", "") or row.get("category", "") or "Unknown")
        for row in rows
    )
    keywords = _top_counts(_iter_product_tags(rows))
    badge_counts = _badge_counts(rows)
    body = f"""    <section class="summary">
{_summary([
        ("Products", str(len(rows))),
        ("Trending niches", str(len(niche_rows))),
        ("Trending sellers", str(len(seller_rows))),
        ("Badge types", str(len(badge_counts))),
    ])}
    </section>
    <section class="trend-grid">
{_trend_panel("Trending Niches", [(row.get("niche", "") or "Unknown", row.get("niche_momentum_score", "") or row.get("opportunities", "") or "0") for row in niche_rows[:12]])}
{_trend_panel("Trending Sellers", [(row.get("seller", "") or row.get("seller_name", "") or row.get("source_name", "") or "Unknown", row.get("seller_momentum_score", "") or row.get("momentum_score", "") or "0") for row in seller_rows[:12]])}
{_trend_panel("Trending Product Types", product_types[:12])}
{_trend_panel("Trending Keywords / Tags", keywords[:12])}
{_trend_panel("Badge Counts", badge_counts)}
    </section>"""
    path.write_text(_page("Trends", "Trends", body), encoding="utf-8")


def write_database_html(
    path: Path,
    product_rows: list[dict[str, str]],
    opportunity_rows: list[dict[str, str]],
) -> None:
    ensure_parent(path)
    rows = _database_rows(product_rows, opportunity_rows)
    fields = [
        "asin",
        "title",
        "badges",
        "decision_score",
        "opportunity_score",
        "seller_name",
        "niche_primary",
        "source_name",
        "source_type",
        "display_rank",
        "previous_display_rank",
        "display_rank_change",
        "primary_bsr_rank",
        "sub_bsr_rank",
        "product_url",
        "source_url",
    ]
    header = "".join(f'<th><button type="button">{_field_label(field)}</button></th>' for field in fields)
    body = "\n".join(_database_table_row(row, fields) for row in rows)
    if not body:
        body = f'<tr><td colspan="{len(fields)}">No products match current filters.</td></tr>'
    path.write_text(
        _page(
            title="Database",
            active_label="Database",
            body=f"""    <section class="summary">
{_summary([("Rows", str(len(rows))), ("Unique ASINs", str(len({row.get("asin", "") for row in rows if row.get("asin", "")})))])}
    </section>
    <section class="controls product-controls database-controls">
      <div class="control-group">
        <label for="database-search">Search</label>
        <input id="database-search" type="search" data-database-search placeholder="Title or ASIN">
      </div>
      <div class="control-group">
        <label for="database-badge-filter">Badge</label>
        <select id="database-badge-filter" data-database-badge-filter>
          <option value="all">All badges</option>
{_badge_filter_options(rows)}
        </select>
      </div>
      <div class="control-group">
        <label for="database-seller-filter">Seller</label>
        <select id="database-seller-filter" data-database-seller-filter>
          <option value="all">All sellers</option>
{_filter_options(rows, _seller_label)}
        </select>
      </div>
      <div class="control-group">
        <label for="database-niche-filter">Niche</label>
        <select id="database-niche-filter" data-database-niche-filter>
          <option value="all">All niches</option>
{_filter_options(rows, lambda row: row.get("niche_primary", "") or "Unknown")}
        </select>
      </div>
      <button class="quick-link" type="button" data-export-database>Export CSV</button>
    </section>
    <div class="empty filter-empty is-hidden" data-filter-empty>No products match current filters.</div>
    <div class="table-wrap">
      <table class="sortable database-table" data-database-table>
        <thead><tr>{header}</tr></thead>
        <tbody>
{body}
        </tbody>
      </table>
    </div>""",
            extra_script=_sortable_table_script() + _database_script(),
        ),
        encoding="utf-8",
    )


def write_table_html(
    path: Path,
    rows: list[dict[str, str]],
    title: str,
    active_label: str,
    fields: list[str],
) -> None:
    ensure_parent(path)
    header = "".join(f'<th><button type="button">{_field_label(field)}</button></th>' for field in fields)
    body = "\n".join(_table_row(row, fields) for row in rows)
    if not body:
        body = f'<tr><td colspan="{len(fields)}">No records found.</td></tr>'
    path.write_text(
        _page(
            title=title,
            active_label=active_label,
            body=f"""    <section class="summary">
      <div><strong>{len(rows)}</strong><span>sellers</span></div>
    </section>
    <div class="table-wrap">
      <table class="sortable">
        <thead><tr>{header}</tr></thead>
        <tbody>
{body}
        </tbody>
      </table>
    </div>""",
            extra_script=_sortable_table_script(),
        ),
        encoding="utf-8",
    )


def write_seller_intelligence_html(
    path: Path,
    seller_rows: list[dict[str, str]],
    product_rows: list[dict[str, str]],
    title: str,
    active_label: str,
) -> None:
    ensure_parent(path)
    fields = SELLER_INTELLIGENCE_FIELDS
    header = '<th class="drill-control-header">Products</th>' + "".join(
        f'<th><button type="button">{_field_label(field)}</button></th>' for field in fields
    )
    body = "\n".join(
        _seller_table_drill_rows(row, fields, _seller_products(row, product_rows), index)
        for index, row in enumerate(seller_rows)
    )
    if not body:
        body = f'<tr><td colspan="{len(fields) + 1}">No records found.</td></tr>'
    path.write_text(
        _page(
            title=title,
            active_label=active_label,
            body=f"""    <section class="summary">
      <div><strong>{len(seller_rows)}</strong><span>sellers</span></div>
    </section>
    <div class="table-wrap">
      <table class="sortable drill-table">
        <thead><tr>{header}</tr></thead>
        <tbody>
{body}
        </tbody>
      </table>
    </div>""",
            extra_script=_sortable_table_script() + _drilldown_script(),
        ),
        encoding="utf-8",
    )


def write_source_explorer_html(path: Path, rows: list[dict[str, str]], title: str, active_label: str) -> None:
    ensure_parent(path)
    groups = _group_products(rows)
    sections = "\n".join(_source_group_section(name, group_rows) for name, group_rows in groups)
    if not sections:
        sections = '    <div class="empty">No records found.</div>'
    path.write_text(
        _page(
            title=title,
            active_label=active_label,
            body=f"""    <section class="summary">
      <div><strong>{len(rows)}</strong><span>products</span></div>
      <div><strong>{len(groups)}</strong><span>sources</span></div>
    </section>
{_sort_controls()}
{sections}""",
            extra_script=_card_interaction_script(),
        ),
        encoding="utf-8",
    )


def write_niche_intelligence_html(
    path: Path,
    niche_rows: list[dict[str, str]],
    product_rows: list[dict[str, str]],
    title: str,
    active_label: str,
) -> None:
    ensure_parent(path)
    sorted_niches = sorted(niche_rows, key=lambda row: _to_int(row.get("niche_momentum_score", "")) or 0, reverse=True)
    table_fields = [
        "niche",
        "niche_group",
        "niche_momentum_score",
        "products_tracked",
        "opportunities",
        "new_wins",
        "rising_products",
        "best_rank",
        "best_bsr_rank",
        "best_subcategory_rank",
        "avg_opportunity_score",
        "top_seller",
    ]
    products_by_niche = [_niche_products(row, product_rows) for row in sorted_niches]
    table_header = '<th class="drill-control-header">Products</th>' + "".join(f"<th>{escape(_field_label(field))}</th>" for field in table_fields)
    table_body = "\n".join(
        _niche_table_drill_rows(row, table_fields, products, index)
        for index, (row, products) in enumerate(zip(sorted_niches[:50], products_by_niche[:50]))
    )
    if not table_body:
        table_body = f'<tr><td colspan="{len(table_fields) + 1}">No records found.</td></tr>'
    cards = "\n".join(
        _niche_card(row, products, index)
        for index, (row, products) in enumerate(zip(sorted_niches, products_by_niche))
    )
    if not cards:
        cards = '      <div class="empty">No records found.</div>'
    path.write_text(
        _page(
            title=title,
            active_label=active_label,
            body=f"""    <section class="summary">
      <div><strong>{len(sorted_niches)}</strong><span>niches</span></div>
      <div><strong>{sum(_to_int(row.get("opportunities", "")) or 0 for row in sorted_niches)}</strong><span>opportunities</span></div>
    </section>
    <section class="controls">
      <label for="niche-filter">Filter</label>
      <select id="niche-filter" data-niche-filter>
        <option value="all">All niches</option>
        <option value="occasion">Occasion</option>
        <option value="family">Family / Relationship</option>
        <option value="profession">Profession</option>
        <option value="hobby">Hobby</option>
        <option value="pet">Pet</option>
        <option value="product">Product Type</option>
      </select>
    </section>
    <section class="niche-table">
      <h2>Top Trending Niches</h2>
      <div class="table-wrap">
        <table>
          <thead><tr>{table_header}</tr></thead>
          <tbody>
{table_body}
          </tbody>
        </table>
      </div>
    </section>
    <section class="niche-grid">
{cards}
    </section>""",
            extra_script=_niche_filter_script() + _drilldown_script(),
        ),
        encoding="utf-8",
    )


def _download_image(url: str, target: Path) -> None:
    try:
        request = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(request, timeout=IMAGE_TIMEOUT_SECONDS) as response:
            data = response.read()
    except (HTTPError, URLError, OSError, ValueError):
        return
    if not data:
        return
    ensure_parent(target)
    target.write_bytes(data)


def _page(title: str, active_label: str, body: str, extra_script: str = "", path_prefix: str = "") -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    :root {{ color-scheme: light; }}
    body {{ margin: 0; font-family: Arial, sans-serif; background: #f5f7fa; color: #1f2933; }}
    header {{ background: #ffffff; border-bottom: 1px solid #d8dee8; position: sticky; top: 0; z-index: 2; }}
    .bar {{ max-width: 1280px; margin: 0 auto; padding: 14px 22px; display: flex; flex-wrap: wrap; gap: 14px; align-items: center; }}
    .brand {{ font-size: 18px; font-weight: 700; margin-right: 8px; }}
    nav {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    nav a {{ border: 1px solid #cad3df; border-radius: 6px; color: #334e68; padding: 7px 10px; text-decoration: none; font-size: 13px; background: #fff; }}
    nav a.active {{ background: #102a43; border-color: #102a43; color: #fff; }}
    main {{ max-width: 1280px; margin: 0 auto; padding: 22px; }}
    h1 {{ font-size: 24px; margin: 0 0 16px; }}
    h2 {{ font-size: 17px; margin: 0 0 12px; }}
    .summary {{ display: flex; flex-wrap: wrap; gap: 10px; margin: 0 0 16px; }}
    .summary div {{ background: #ffffff; border: 1px solid #d8dee8; border-radius: 8px; padding: 10px 12px; min-width: 120px; }}
    .summary strong {{ display: block; font-size: 20px; color: #102a43; }}
    .summary span {{ display: block; margin-top: 2px; font-size: 12px; color: #627d98; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: 14px; }}
    .card {{ background: #fff; border: 1px solid #d9dee7; border-radius: 8px; overflow: hidden; }}
    .card.is-hidden {{ display: none; }}
    .image {{ aspect-ratio: 4 / 3; background: #edf1f5; display: flex; align-items: center; justify-content: center; }}
    .image img {{ width: 100%; height: 100%; object-fit: contain; display: block; }}
    .image-placeholder {{ color: #829ab1; font-size: 13px; }}
    .body {{ padding: 12px; }}
    .title {{ font-size: 13px; font-weight: 700; line-height: 1.35; min-height: 36px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }}
    .controls {{ margin: 0 0 16px; display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }}
    .controls label {{ font-size: 12px; font-weight: 700; color: #52606d; }}
    .controls select, .controls input {{ border: 1px solid #cad3df; border-radius: 6px; background: #fff; color: #102a43; padding: 8px 10px; font-size: 13px; }}
    .product-controls {{ align-items: flex-end; background: #fff; border: 1px solid #d8dee8; border-radius: 8px; padding: 10px; }}
    .control-group {{ display: grid; gap: 5px; }}
    .search-control input {{ min-width: 220px; }}
    .bsr-range span {{ display: flex; gap: 6px; }}
    .bsr-range input {{ width: 96px; }}
    .filter-toggles {{ display: flex; flex-wrap: wrap; gap: 8px 12px; align-items: center; }}
    .filter-toggles label {{ display: inline-flex; align-items: center; gap: 5px; white-space: nowrap; }}
    .priority-section {{ margin: 0 0 22px; }}
    .section-heading {{ display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin: 0 0 10px; }}
    .section-heading span {{ color: #627d98; font-size: 12px; }}
    .priority-grid {{ grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); }}
    .discovery-grid {{ grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); }}
    .meta {{ margin-top: 10px; display: grid; gap: 8px; font-size: 12px; color: #52606d; }}
    .metric span, .category-rank span {{ display: block; font-size: 11px; font-weight: 700; color: #627d98; text-transform: uppercase; }}
    .metric strong, .category-rank strong {{ display: block; margin-top: 2px; font-size: 13px; color: #1f2933; font-weight: 700; }}
    .metric small {{ display: block; margin-top: 2px; font-size: 12px; color: #52606d; }}
    .compact-meta {{ gap: 7px; }}
    .movement-metric strong {{ color: #0b7285; font-size: 15px; }}
    .badge-list {{ display: flex; flex-wrap: wrap; gap: 6px; margin: 0 0 8px; }}
    .badge {{ border: 1px solid #88bdbc; border-radius: 999px; background: #e6f4f1; color: #125c59; padding: 4px 8px; font-size: 11px; font-weight: 700; }}
    .evidence-tags {{ display: flex; flex-wrap: wrap; gap: 6px; margin: 9px 0 0; }}
    .evidence-tag {{ border: 1px solid #b8c2cc; border-radius: 999px; background: #f7f7f2; color: #2f3a45; padding: 4px 8px; font-size: 11px; font-weight: 700; line-height: 1.2; }}
    .score-components {{ display: flex; flex-wrap: wrap; gap: 6px; color: #52606d; font-size: 11px; }}
    .score-components span {{ border: 1px solid #d8dee8; border-radius: 6px; background: #f8fafc; padding: 4px 6px; }}
    .score-components strong {{ color: #102a43; }}
    .card-actions {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }}
    .category-rank {{ border: 1px solid #cfd8e3; border-left-width: 5px; border-radius: 7px; padding: 9px 10px; background: #f7f9fb; }}
    .category-rank strong {{ font-size: 15px; color: #102a43; }}
    .category-rank--green {{ border-color: #2f855a; background: #edf8f1; }}
    .category-rank--green strong {{ color: #276749; }}
    .category-rank--blue {{ border-color: #2b6cb0; background: #edf5ff; }}
    .category-rank--blue strong {{ color: #2c5282; }}
    .category-rank--orange {{ border-color: #c05621; background: #fff4e6; }}
    .category-rank--orange strong {{ color: #9c4221; }}
    .category-rank--gray {{ border-color: #9aa5b1; background: #f2f4f7; }}
    .category-rank--gray strong {{ color: #52606d; }}
    .rank-audit-warning {{ border-color: #b7791f; background: #fffaf0; }}
    .rank-audit-warning strong {{ color: #975a16; }}
    .display-rank {{ border: 1px solid #cfd8e3; border-left-width: 5px; border-radius: 7px; padding: 9px 10px; background: #f7f9fb; }}
    .display-rank strong {{ font-size: 15px; color: #102a43; }}
    .display-rank--green {{ border-color: #2f855a; background: #edf8f1; }}
    .display-rank--green strong {{ color: #276749; }}
    .display-rank--blue {{ border-color: #2b6cb0; background: #edf5ff; }}
    .display-rank--blue strong {{ color: #2c5282; }}
    .display-rank--light-green {{ border-color: #38a169; background: #f0fff4; }}
    .display-rank--light-green strong {{ color: #2f855a; }}
    .display-rank--gray {{ border-color: #9aa5b1; background: #f2f4f7; }}
    .display-rank--gray strong {{ color: #52606d; }}
    .display-rank--red {{ border-color: #c53030; background: #fff5f5; }}
    .display-rank--red strong {{ color: #9b2c2c; }}
    .score {{ font-size: 15px; font-weight: 700; color: #102a43; }}
    .score-breakdown {{ position: relative; }}
    .score-breakdown::after {{ content: attr(data-tooltip); display: none; position: absolute; left: 0; top: calc(100% + 6px); width: max-content; max-width: 260px; white-space: pre-line; background: #102a43; color: #fff; border-radius: 6px; padding: 8px 10px; font-size: 12px; line-height: 1.4; z-index: 3; box-shadow: 0 8px 20px rgba(16, 42, 67, 0.18); }}
    .score-breakdown:hover::after, .score-breakdown:focus::after {{ display: block; }}
    .table-wrap {{ overflow: auto; background: #fff; border: 1px solid #d8dee8; border-radius: 8px; }}
    table {{ border-collapse: collapse; min-width: 100%; font-size: 13px; }}
    th, td {{ border-bottom: 1px solid #edf1f5; padding: 9px 10px; text-align: left; vertical-align: top; }}
    th {{ background: #f0f4f8; position: sticky; top: 58px; z-index: 1; }}
    th button {{ all: unset; cursor: pointer; font-weight: 700; color: #102a43; }}
    td a, .card a {{ color: inherit; }}
    details {{ background: #fff; border: 1px solid #d8dee8; border-radius: 8px; margin: 0 0 14px; padding: 12px; }}
    summary {{ cursor: pointer; font-weight: 700; }}
    .source-grid {{ margin-top: 12px; display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: 10px; }}
    .niche-table {{ margin: 0 0 16px; }}
    .niche-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 14px; margin: 0 0 18px; }}
    .niche-card {{ background: #fff; border: 1px solid #d9dee7; border-radius: 8px; overflow: hidden; }}
    .niche-card.is-hidden, .niche-detail.is-hidden {{ display: none; }}
    .niche-card img {{ width: 100%; aspect-ratio: 1 / 1; object-fit: contain; display: block; background: #edf1f5; }}
    .niche-card-body {{ padding: 12px; display: grid; gap: 8px; }}
    .niche-card h3 {{ font-size: 16px; margin: 0; }}
    .niche-score {{ font-size: 24px; font-weight: 700; color: #102a43; }}
    .niche-stats {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; font-size: 12px; color: #52606d; }}
    .niche-stats strong {{ display: block; color: #1f2933; font-size: 14px; }}
    .niche-product-title {{ font-size: 13px; line-height: 1.35; font-weight: 700; }}
    .niche-details {{ display: grid; gap: 12px; }}
    .niche-products {{ margin-top: 12px; display: grid; gap: 8px; }}
    .niche-product {{ display: grid; grid-template-columns: 72px minmax(0, 1fr); gap: 10px; border-top: 1px solid #edf1f5; padding-top: 8px; }}
    .niche-product img {{ width: 72px; height: 72px; object-fit: contain; background: #edf1f5; }}
    .niche-product-title a {{ color: #102a43; }}
    .niche-product-meta {{ margin-top: 5px; display: flex; flex-wrap: wrap; gap: 8px; font-size: 12px; color: #52606d; }}
    .is-hidden {{ display: none !important; }}
    .drill-table tr[data-drill-row] {{ cursor: pointer; }}
    .drill-parent-row.is-expanded td {{ background: #f8fafc; }}
    .drill-row > td {{ background: #ffffff; padding: 0; }}
    .drill-control-header, .drill-control-cell {{ width: 92px; white-space: nowrap; }}
    .drill-toggle {{ width: 28px; height: 28px; border: 1px solid #9fb3c8; border-radius: 6px; background: #fff; color: #102a43; cursor: pointer; font-weight: 700; line-height: 1; }}
    .drill-product-count {{ margin-left: 8px; color: #52606d; font-size: 12px; }}
    .drill-panel {{ padding: 14px; border-top: 1px solid #d8dee8; }}
    .drill-toolbar {{ display: flex; flex-wrap: wrap; justify-content: space-between; gap: 10px; margin: 0 0 12px; }}
    .drill-filters {{ display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }}
    .drill-filters label {{ display: inline-flex; gap: 6px; align-items: center; font-size: 12px; color: #334e68; }}
    .drill-actions {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }}
    .drill-actions button, .quick-actions button, .quick-link {{ border: 1px solid #9fb3c8; border-radius: 6px; background: #fff; color: #102a43; padding: 7px 9px; font-size: 12px; line-height: 1.2; cursor: pointer; text-decoration: none; }}
    .drill-actions button:hover, .quick-actions button:hover, .quick-link:hover {{ border-color: #486581; }}
    .drill-status {{ font-size: 12px; color: #52606d; }}
    .drill-products {{ display: grid; gap: 8px; }}
    .drill-product {{ display: grid; grid-template-columns: 58px 72px minmax(0, 1fr); gap: 10px; align-items: start; border: 1px solid #e1e8f0; border-radius: 8px; background: #fff; padding: 9px; }}
    .drill-rank {{ font-size: 13px; font-weight: 700; color: #102a43; }}
    .drill-thumb {{ width: 72px; height: 72px; display: flex; align-items: center; justify-content: center; background: #edf1f5; border-radius: 6px; overflow: hidden; color: #829ab1; font-size: 11px; text-align: center; }}
    .drill-thumb img {{ width: 100%; height: 100%; object-fit: contain; display: block; }}
    .drill-thumb--empty {{ border: 1px dashed #bcccdc; }}
    .drill-main {{ min-width: 0; }}
    .drill-title {{ font-size: 13px; font-weight: 700; line-height: 1.35; color: #102a43; }}
    .drill-title a {{ color: #102a43; }}
    .drill-meta {{ margin-top: 7px; display: flex; flex-wrap: wrap; gap: 7px 12px; font-size: 12px; color: #52606d; }}
    .drill-meta strong {{ color: #334e68; }}
    .quick-actions {{ margin-top: 9px; display: flex; flex-wrap: wrap; gap: 7px; }}
    .drill-groups {{ display: grid; gap: 14px; padding: 14px; }}
    .drill-group {{ border: 1px solid #e1e8f0; border-radius: 8px; background: #fbfcfd; }}
    .drill-group h3 {{ margin: 0; padding: 10px 12px 0; font-size: 14px; color: #102a43; }}
    .drill-group .drill-panel {{ border-top: 0; }}
    .drill-overview {{ padding-bottom: 10px; }}
    .drill-overview-grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; padding: 10px 12px 0; }}
    .drill-overview-grid div {{ border: 1px solid #e1e8f0; border-radius: 6px; background: #fff; padding: 8px; }}
    .drill-overview-grid strong {{ display: block; color: #102a43; font-size: 16px; }}
    .drill-overview-grid span, .drill-overview p {{ color: #52606d; font-size: 12px; }}
    .drill-overview p {{ margin: 8px 12px 0; }}
    .niche-card-drilldown {{ margin: 4px 0 0; padding: 10px; }}
    .niche-card-drilldown .drill-panel {{ padding: 10px 0 0; border-top: 0; }}
    .niche-card-drilldown .drill-product {{ grid-template-columns: 42px 54px minmax(0, 1fr); }}
    .niche-card-drilldown .drill-thumb {{ width: 54px; height: 54px; }}
    .empty {{ background: #fff; border: 1px solid #d8dee8; border-radius: 8px; padding: 18px; color: #52606d; }}
    .load-more {{ margin: 18px auto 0; display: block; border: 1px solid #102a43; border-radius: 6px; background: #102a43; color: #fff; padding: 10px 16px; cursor: pointer; font-weight: 700; }}
    .detail-modal {{ width: min(860px, calc(100vw - 32px)); border: 1px solid #bcccdc; border-radius: 8px; padding: 0; color: #1f2933; }}
    .detail-modal::backdrop {{ background: rgba(16, 42, 67, 0.35); }}
    .detail-modal-header {{ display: flex; justify-content: space-between; gap: 12px; align-items: start; padding: 14px 16px; border-bottom: 1px solid #e1e8f0; }}
    .detail-modal-header h2 {{ margin: 0; font-size: 16px; line-height: 1.35; }}
    .detail-modal-header button {{ border: 1px solid #9fb3c8; border-radius: 6px; background: #fff; color: #102a43; padding: 7px 9px; cursor: pointer; }}
    .detail-modal-body {{ padding: 14px 16px 16px; }}
    .detail-title {{ font-weight: 700; color: #102a43; margin-bottom: 10px; }}
    .detail-meta {{ grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); }}
    .detail-meta .metric {{ border: 1px solid #e1e8f0; border-radius: 7px; padding: 8px; background: #fbfcfd; overflow-wrap: anywhere; }}
    .trend-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 14px; }}
    .trend-panel {{ background: #fff; border: 1px solid #d8dee8; border-radius: 8px; padding: 12px; }}
    .trend-panel h2 {{ margin-bottom: 10px; }}
    .trend-panel ol {{ list-style: none; padding: 0; margin: 0; display: grid; gap: 7px; }}
    .trend-panel li {{ display: flex; justify-content: space-between; gap: 12px; border-bottom: 1px solid #edf1f5; padding-bottom: 7px; font-size: 13px; }}
    .trend-panel li:last-child {{ border-bottom: 0; padding-bottom: 0; }}
    .trend-panel span {{ color: #334e68; }}
    .trend-panel strong {{ color: #102a43; }}
    .database-controls button {{ align-self: end; }}
    .database-table tr.is-hidden {{ display: none; }}
    .competitor-panel {{ background: #fff; border: 1px solid #d8dee8; border-radius: 8px; padding: 14px; margin: 0 0 16px; }}
    .competitor-heading {{ display: flex; justify-content: space-between; gap: 12px; align-items: start; margin-bottom: 12px; }}
    .competitor-heading h2 {{ margin-bottom: 2px; }}
    .competitor-heading span {{ color: #627d98; font-size: 12px; }}
    .competitor-summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 8px; margin-bottom: 12px; }}
    .competitor-summary div {{ border: 1px solid #e1e8f0; border-radius: 7px; background: #fbfcfd; padding: 8px; }}
    .competitor-summary strong {{ display: block; color: #102a43; font-size: 18px; }}
    .competitor-summary span {{ color: #52606d; font-size: 12px; }}
    .competitor-products {{ display: grid; gap: 8px; }}
    .competitor-product {{ display: grid; gap: 6px; }}
    .status-tag {{ justify-self: start; border-radius: 999px; padding: 4px 8px; font-size: 11px; font-weight: 700; background: #eef2f7; color: #334e68; }}
    .status-new, .status-rising {{ background: #edf8f1; color: #276749; }}
    .status-falling, .status-dropped {{ background: #fff5f5; color: #9b2c2c; }}
    .trend-clusters {{ display: grid; gap: 10px; }}
    .trend-cluster {{ padding: 0; overflow: hidden; }}
    .trend-cluster summary {{ display: grid; grid-template-columns: minmax(180px, 1.5fr) repeat(4, minmax(96px, auto)); gap: 10px; align-items: center; padding: 12px; }}
    .trend-name {{ font-weight: 700; color: #102a43; }}
    .detail-index {{ background: #fff; border: 1px solid #d8dee8; border-radius: 8px; padding: 14px 18px; }}
    .detail-index li {{ margin: 6px 0; }}
    .detail-hero {{ display: grid; grid-template-columns: minmax(180px, 280px) minmax(0, 1fr); gap: 18px; align-items: start; margin-bottom: 18px; }}
    .detail-hero-image {{ background: #fff; border: 1px solid #d8dee8; border-radius: 8px; aspect-ratio: 1 / 1; display: flex; align-items: center; justify-content: center; overflow: hidden; }}
    .detail-hero-image img {{ width: 100%; height: 100%; object-fit: contain; }}
    .detail-hero-main {{ min-width: 0; }}
    .detail-hero-main h2 {{ font-size: 22px; line-height: 1.25; margin: 10px 0 12px; }}
    .detail-summary-grid, .source-history-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 8px; }}
    .detail-summary-grid div, .source-history-grid div {{ border: 1px solid #e1e8f0; border-radius: 7px; background: #fff; padding: 9px; overflow-wrap: anywhere; }}
    .detail-summary-grid span, .source-history-grid span {{ display: block; color: #627d98; font-size: 11px; font-weight: 700; text-transform: uppercase; }}
    .detail-summary-grid strong, .source-history-grid strong {{ display: block; margin-top: 3px; color: #102a43; font-size: 14px; }}
    .source-history-grid small {{ display: block; margin-top: 3px; color: #52606d; }}
    .detail-section {{ margin: 0 0 18px; }}
    .timeline-strip, .journey {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 8px; }}
    .timeline-point, .journey-step {{ border: 1px solid #d8dee8; border-radius: 8px; background: #fff; padding: 9px; }}
    .timeline-point span, .journey-step span {{ display: block; color: #627d98; font-size: 11px; font-weight: 700; text-transform: uppercase; }}
    .timeline-point strong, .journey-step strong {{ display: block; margin-top: 3px; color: #102a43; font-size: 15px; }}
    .timeline-point small {{ display: block; margin-top: 3px; color: #52606d; }}
    .journey-step.is-complete {{ border-color: #38a169; background: #f0fff4; }}
    @media (max-width: 720px) {{
      main {{ padding: 14px; }}
      th, td {{ padding: 8px; }}
      .drill-panel {{ padding: 10px; }}
      .drill-product {{ grid-template-columns: 44px 58px minmax(0, 1fr); }}
      .drill-thumb {{ width: 58px; height: 58px; }}
      .drill-toolbar, .drill-actions {{ align-items: stretch; }}
      .drill-actions button, .quick-actions button, .quick-link {{ flex: 1 1 auto; text-align: center; }}
      .trend-cluster summary {{ grid-template-columns: 1fr; }}
      .detail-hero {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="bar">
      <div class="brand">Amazon Market Spy</div>
      <nav>
{_nav(active_label, path_prefix)}
      </nav>
    </div>
  </header>
  <main>
    <h1>{escape(title)}</h1>
{body}
  </main>
{extra_script}
</body>
</html>
"""


def _nav(active_label: str, path_prefix: str = "") -> str:
    links = []
    for label, href in NAV_ITEMS:
        css_class = ' class="active"' if label == active_label else ""
        links.append(f'        <a href="{escape(path_prefix + href, quote=True)}"{css_class}>{escape(label)}</a>')
    return "\n".join(links)


def _summary(items: list[tuple[str, str]]) -> str:
    return "\n".join(
        f"      <div><strong>{escape(value)}</strong><span>{escape(label)}</span></div>"
        for label, value in items
    )


def _product_controls(
    rows: list[dict[str, str]],
    *,
    include_badge_filter: bool = False,
    include_source_type_filter: bool = False,
    include_search: bool = False,
    include_bsr_filter: bool = False,
) -> str:
    seller_options = _filter_options(rows, _seller_label)
    niche_options = _filter_options(rows, lambda row: row.get("niche_primary", "") or "Unknown")
    product_type_options = _filter_options(rows, _product_type_label)
    search_filter = ""
    if include_search:
        search_filter = """      <div class="control-group search-control">
        <label for="product-search">Search</label>
        <input id="product-search" type="search" data-product-search placeholder="Title or ASIN">
      </div>
"""
    bsr_filter = ""
    if include_bsr_filter:
        bsr_filter = """      <div class="control-group bsr-range">
        <label>BSR range</label>
        <span><input type="number" min="1" data-product-bsr-min placeholder="Min"><input type="number" min="1" data-product-bsr-max placeholder="Max"></span>
      </div>
"""
    return f"""    <section class="controls product-controls">
{search_filter}
      <div class="control-group">
        <label for="card-sort">Sort</label>
        <select id="card-sort" data-card-sort>
{_sort_option_html()}
        </select>
      </div>
      <div class="control-group filter-toggles" aria-label="Product filters">
        <label><input type="checkbox" data-card-filter="newWinner"> New Winner</label>
        <label><input type="checkbox" data-card-filter="fastRising"> Fast Rising</label>
        <label><input type="checkbox" data-card-filter="stableWinner"> Stable Winner</label>
        <label><input type="checkbox" data-card-filter="bestSeller"> Best Seller</label>
        <label><input type="checkbox" data-card-filter="newRelease"> New Release</label>
      </div>
{bsr_filter}
      <div class="control-group">
        <label for="seller-filter">Seller</label>
        <select id="seller-filter" data-product-seller-filter>
          <option value="all">All sellers</option>
{seller_options}
        </select>
      </div>
      <div class="control-group">
        <label for="product-niche-filter">Niche</label>
        <select id="product-niche-filter" data-product-niche-filter>
          <option value="all">All niches</option>
{niche_options}
        </select>
      </div>
      <div class="control-group">
        <label for="product-type-filter">Product Type</label>
        <select id="product-type-filter" data-product-type-filter>
          <option value="all">All product types</option>
{product_type_options}
        </select>
      </div>
      <div class="control-group">
        <label for="days-filter">Days Tracked</label>
        <select id="days-filter" data-product-days-filter>
          <option value="all">Any age</option>
          <option value="3">3 days or less</option>
          <option value="7">7 days or less</option>
          <option value="14">14 days or less</option>
          <option value="30">30 days or more</option>
        </select>
      </div>
    </section>"""


def _filter_options(rows: list[dict[str, str]], label_fn) -> str:
    options: dict[str, str] = {}
    for row in rows:
        label = str(label_fn(row) or "").strip()
        key = _filter_key(label)
        if key and key not in options:
            options[key] = label
    return "\n".join(
        f'          <option value="{escape(key, quote=True)}">{escape(label)}</option>'
        for key, label in sorted(options.items(), key=lambda item: item[1].lower())
    )


def _badge_filter_options(rows: list[dict[str, str]]) -> str:
    labels: dict[str, str] = {}
    for row in rows:
        for badge in _badges_for_row(row):
            key = _filter_key(badge)
            if key:
                labels[key] = badge
    return "\n".join(
        f'          <option value="{escape(key, quote=True)}">{escape(label)}</option>'
        for key, label in sorted(labels.items(), key=lambda item: item[1].lower())
    )


def _sort_controls() -> str:
    return f"""    <section class="controls">
      <label for="card-sort">Sort</label>
      <select id="card-sort" data-card-sort>
{_sort_option_html()}
      </select>
    </section>"""


def _sort_option_html() -> str:
    return "\n".join(
        f'        <option value="{escape(value, quote=True)}">{escape(label)}</option>'
        for value, label in SORT_OPTIONS
    )


def _opportunity_card(row: dict[str, str], index: int = 0, *, default_badge: str = "", compact: bool = False) -> str:
    ensure_category_rank_fields(row)
    ensure_detail_fix_fields(row)
    ensure_niche_fields(row)
    _ensure_decision_fields(row)
    image_src = row.get("local_image_path", "") or row.get("image_url", "")
    product_url = row.get("product_url", "")
    title = display_product_title(row.get("title", ""))
    seller = row.get("seller_name", "") or row.get("source_name", "") or row.get("seller_id", "") or row.get("source_type", "")
    signal_score = row.get("winner_signal_score", "") or row.get("signal_score", "") or row.get("opportunity_score", "") or "0"
    evidence = _evidence_tags_html(row)
    rank_flow = _source_rank_flow_text(row)
    detail_url = _product_detail_url(row)
    actions = _card_actions_html(_amazon_product_url(row), detail_url)
    image_html = (
        f'<img src="{escape(image_src, quote=True)}" alt="{escape(title, quote=True)}">'
        if image_src
        else '<div class="image-placeholder" aria-hidden="true">No image</div>'
    )
    open_link = f'<a href="{escape(product_url, quote=True)}" target="_blank" rel="noopener">' if product_url else ""
    close_link = "</a>" if product_url else ""
    hidden_class = " is-hidden" if index >= 60 else ""
    days_seen = row.get("days_seen", "") or "1"
    current_rank = row.get("display_rank", "") or row.get("display_order", "") or row.get("today_rank", "") or row.get("rank", "") or row.get("position", "")
    product_type = _product_type_label(row)
    return f"""      <article class="card{hidden_class}" {_card_data_attrs(row, index)}>
        {open_link}<div class="image">{image_html}</div>{close_link}
        <div class="body">
          <div class="title">{escape(title)}</div>
          {evidence}
          <div class="meta compact-meta">
            <div class="metric score"><span>Signal Score:</span><strong>{escape(signal_score)}</strong></div>
            <div class="metric"><span>Seller:</span><strong>{escape(seller)}</strong></div>
            <div class="metric"><span>Current Rank:</span><strong>{escape(_rank_label(current_rank) or "-")}</strong></div>
            <div class="metric movement-metric"><span>Rank Trend:</span><strong>{rank_flow}</strong></div>
            <div class="metric"><span>Days Tracked:</span><strong>{escape(days_seen)}</strong></div>
            <div class="metric"><span>Product Type:</span><strong>{escape(product_type)}</strong></div>
          </div>
          {actions}
        </div>
      </article>"""


def _source_product_card(row: dict[str, str], index: int = 0) -> str:
    ensure_category_rank_fields(row)
    ensure_detail_fix_fields(row)
    ensure_niche_fields(row)
    image_src = row.get("local_image_path", "") or row.get("image_url", "")
    product_url = row.get("product_url", "")
    title = display_product_title(row.get("title", ""))
    seller = row.get("seller_name", "") or row.get("source_name", "") or row.get("seller_id", "") or row.get("source_type", "")
    rank_change = _rank_change(row)
    today_rank = row.get("today_rank", "") or row.get("rank", "") or row.get("display_rank", "")
    display_rank = row.get("display_rank", "") or row.get("rank", "") or row.get("position", "")
    products_in_source = row.get("products_in_source", "")
    source_name = row.get("source_name", "")
    previous_display_rank = row.get("previous_display_rank", "")
    display_rank_change = _display_rank_change_value(row)
    display_rank_velocity = row.get("display_rank_velocity", "")
    display_percentile = row.get("display_percentile", "")
    category_rank = _category_rank(row)
    category_rank_class = _category_rank_class(row)
    subcategory_rank = _subcategory_rank(row)
    subcategory_rank_class = _subcategory_rank_class(row)
    category_rank_html = _rank_metric_html("Amazon BSR:", category_rank, category_rank_class)
    subcategory_rank_html = _rank_metric_html("Best Subcategory Rank:", subcategory_rank, subcategory_rank_class)
    rank_audit_html = _rank_audit_warning_html(row)
    display_rank_html = _display_rank_metric_html(display_rank, source_name, products_in_source, previous_display_rank, display_rank_change, display_rank_velocity, display_percentile)
    review_count = row.get("review_count", "")
    review_rating = row.get("review_rating", "") or row.get("rating", "")
    days_seen = row.get("days_seen", "")
    pod_score = row.get("pod_score", "")
    niche = row.get("niche_primary", "")
    tags = row.get("niche_tags", "")
    image_html = (
        f'<img src="{escape(image_src, quote=True)}" alt="{escape(title, quote=True)}">'
        if image_src
        else '<div class="image-placeholder" aria-hidden="true">No image</div>'
    )
    open_link = f'<a href="{escape(product_url, quote=True)}" target="_blank" rel="noopener">' if product_url else ""
    close_link = "</a>" if product_url else ""
    return f"""        <article class="card" {_card_data_attrs(row, index)}>
          {open_link}<div class="image">{image_html}</div>{close_link}
          <div class="body">
            <div class="title">{escape(title)}</div>
            <div class="meta">
              <div class="metric"><span>Seller:</span><strong>{escape(seller)}</strong></div>
              {display_rank_html}
              {category_rank_html}
              {subcategory_rank_html}
              {rank_audit_html}
              <div class="metric"><span>Reviews:</span><strong>{escape(_review_count_label(review_count))}</strong><small>Rating: {escape(review_rating)}</small></div>
              <div class="metric"><span>Source Rank:</span><strong>{escape(_rank_label(today_rank))}</strong></div>
              <div class="metric"><span>Source Rank Change:</span><strong>{escape(rank_change)}</strong></div>
              <div class="metric"><span>Days Seen:</span><strong>{escape(days_seen)}</strong></div>
              <div class="metric"><span>POD Score:</span><strong>{escape(pod_score)}</strong></div>
              <div class="metric"><span>Niche:</span><strong>{escape(niche)}</strong></div>
              <div class="metric"><span>Tags:</span><strong>{escape(tags)}</strong></div>
            </div>
          </div>
        </article>"""


def _badges_for_row(row: dict[str, str], *, default_badge: str = "") -> list[str]:
    badges: list[str] = []
    if default_badge:
        badges.append(default_badge)
    if _is_top_winner(row):
        badges.append("Top Winner")
    if _is_fast_mover(row):
        badges.append("Fast Mover")
    if _is_new_breakout(row):
        badges.append("New Breakout")
    if _is_new_release_source(row):
        badges.append("New Release")
    if _is_top_10(row):
        badges.append("Top 10")
    if _truthy(row.get("badge_pod", "")) or pod_allowed(row):
        badges.append("POD")
    unique: list[str] = []
    for badge in badges:
        if badge and badge not in unique:
            unique.append(badge)
    return unique


def _badge_html(badges: list[str]) -> str:
    if not badges:
        return ""
    items = "".join(f'<span class="badge">{escape(badge)}</span>' for badge in badges)
    return f'<div class="badge-list">{items}</div>'


def _evidence_tags_html(row: dict[str, str]) -> str:
    tags = _evidence_tags(row)
    if not tags:
        return ""
    items = "".join(f'<span class="evidence-tag">{escape(tag)}</span>' for tag in tags[:4])
    return f'<div class="evidence-tags">{items}</div>'


def _evidence_tags(row: dict[str, str]) -> list[str]:
    tags: list[str] = []
    movement = _rank_movement_value(row)
    if movement > 0:
        tags.append(f"Rank +{movement} in 7D")
    if _is_competitor_launch(row):
        tags.append("New Seller Top10")
    elif _is_seller_source(row) and _is_top_10(row):
        tags.append("Seller Top10")
    if _is_best_seller(row):
        tags.append("Appears in Best Seller")
    if (_to_int(row.get("source_count", "")) or 1) >= 2:
        tags.append("Cross-source confirmed")
    if _is_recent_product(row):
        tags.append("Newly tracked")
    review_count = _to_int(row.get("review_count", ""))
    if review_count is not None and review_count <= 100:
        tags.append("Low reviews")
    if _is_new_release_source(row):
        tags.append("New Release signal")
    if _is_stable_winner(row):
        tags.append("Stable Top10")
    if _subcategory_rank_number(row) is not None and (_subcategory_rank_number(row) or 10**9) <= 500:
        tags.append("Strong BSR")
    if not tags and _is_top_10(row):
        tags.append("Current Top10")
    if not tags and pod_allowed(row):
        tags.append("POD signal")
    unique: list[str] = []
    for tag in tags:
        if tag and tag not in unique:
            unique.append(tag)
    return unique[:4]


def _score_components_html(row: dict[str, str]) -> str:
    components = [
        ("Top Rank", row.get("top_rank_score", "")),
        ("Velocity", row.get("velocity_score", "")),
        ("Newness", row.get("newness_score", "")),
        ("BSR", row.get("bsr_score", "")),
        ("POD", row.get("pod_score", "")),
    ]
    items = "".join(
        f"<span>{escape(label)} <strong>{escape(str(value or '0'))}</strong></span>"
        for label, value in components
    )
    return f'<div class="score-components">{items}</div>'


def _card_actions_html(product_url: str, detail_url: str = "") -> str:
    links = []
    if product_url:
        links.append(f'<a class="quick-link" href="{escape(product_url, quote=True)}" target="_blank" rel="noopener">Open Amazon</a>')
    if detail_url:
        links.append(f'<a class="quick-link" href="{escape(detail_url, quote=True)}">View Details</a>')
    if not links:
        return ""
    return f'<div class="card-actions">{"".join(links)}</div>'


def _product_detail_url(row: dict[str, str]) -> str:
    asin = row.get("asin", "").strip().upper()
    if not is_asin(asin):
        return ""
    return f"{PRODUCT_DETAIL_DIR}/{asin}.html"


def _history_by_asin(
    product_history_rows: list[dict[str, str]],
    fallback_rows: list[dict[str, str]],
) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in product_history_rows:
        asin = row.get("asin", "").strip().upper()
        if asin:
            grouped[asin].append(ensure_detail_fix_fields(ensure_category_rank_fields(ensure_niche_fields(ensure_pod_fields(dict(row))))))
    for row in fallback_rows:
        asin = row.get("asin", "").strip().upper()
        if asin and not grouped.get(asin):
            grouped[asin].append(row)
    for asin, rows in grouped.items():
        grouped[asin] = sorted(rows, key=lambda item: (_row_date_value(item), _product_display_rank(item), item.get("source_name", "")))
    return grouped


def write_product_detail_pages(
    output_dir: Path,
    rows: list[dict[str, str]],
    history_by_asin: dict[str, list[dict[str, str]]],
) -> None:
    detail_dir = output_dir / PRODUCT_DETAIL_DIR
    detail_dir.mkdir(parents=True, exist_ok=True)
    deduped = sorted(_dedupe_products(rows), key=_signal_sort_key)
    index_links = []
    for row in deduped:
        asin = row.get("asin", "").strip().upper()
        if not is_asin(asin):
            continue
        history = history_by_asin.get(asin, [row])
        page = _product_detail_html(row, history)
        (detail_dir / f"{asin}.html").write_text(page, encoding="utf-8")
        index_links.append(f'<li><a href="{PRODUCT_DETAIL_DIR}/{escape(asin, quote=True)}.html">{escape(display_product_title(row.get("title", "")))}</a></li>')
    index_body = "\n".join(index_links[:200]) or "<li>No product details found.</li>"
    (output_dir / REPORT_PAGES["product_detail"]).write_text(
        _page(
            title="Product Detail",
            active_label="Product Discovery",
            body=f"""    <section class="summary">
{_summary([("Detail pages", str(len(index_links)))])}
    </section>
    <ul class="detail-index">
{index_body}
    </ul>""",
        ),
        encoding="utf-8",
    )


def _product_detail_html(row: dict[str, str], history: list[dict[str, str]]) -> str:
    _ensure_decision_fields(row)
    title = display_product_title(row.get("title", ""))
    image_src = row.get("local_image_path", "") or row.get("image_url", "")
    image_html = (
        f'<img src="../{escape(image_src, quote=True)}" alt="{escape(title, quote=True)}">'
        if image_src and not image_src.startswith("http")
        else (f'<img src="{escape(image_src, quote=True)}" alt="{escape(title, quote=True)}">' if image_src else '<div class="image-placeholder">No image</div>')
    )
    amazon_link = _detail_link(_amazon_product_url(row))
    source_history = _source_history_html(history)
    display_timeline = _rank_timeline_html(history, "display")
    bsr_timeline = _rank_timeline_html(history, "bsr")
    journey = _winner_journey_html(row, history)
    return _page(
        title="Product Detail",
        active_label="Product Discovery",
        body=f"""    <section class="detail-hero">
      <div class="detail-hero-image">{image_html}</div>
      <div class="detail-hero-main">
        <div class="evidence-tags">{''.join(f'<span class="evidence-tag">{escape(tag)}</span>' for tag in _evidence_tags(row))}</div>
        <h2>{escape(title)}</h2>
        <div class="detail-summary-grid">
          <div><span>Seller</span><strong>{escape(_seller_label(row))}</strong></div>
          <div><span>Signal Score</span><strong>{escape(row.get("winner_signal_score", ""))}</strong></div>
          <div><span>First Seen</span><strong>{escape(_first_seen_from_history(row, history))}</strong></div>
          <div><span>Days Tracked</span><strong>{escape(row.get("days_seen", "") or str(len({_row_date_value(item) for item in history if _row_date_value(item)})))}</strong></div>
          <div><span>Amazon Link</span><strong>{amazon_link}</strong></div>
        </div>
      </div>
    </section>
    <section class="detail-section">
      <h2>Winner Journey</h2>
{journey}
    </section>
    <section class="detail-section">
      <h2>Display Rank Timeline</h2>
{display_timeline}
    </section>
    <section class="detail-section">
      <h2>BSR Timeline</h2>
{bsr_timeline}
    </section>
    <section class="detail-section">
      <h2>Source History</h2>
{source_history}
    </section>""",
        path_prefix="../",
    )


def _rank_timeline_html(history: list[dict[str, str]], kind: str) -> str:
    points = _timeline_points(history, kind)
    if not points:
        return '<div class="empty">No timeline data available.</div>'
    items = "\n".join(
        f"""        <div class="timeline-point">
          <span>{escape(point["date"])}</span>
          <strong>{escape(_rank_label(point["rank"]) or "-")}</strong>
          <small>{escape(point["label"])}</small>
        </div>"""
        for point in points[-20:]
    )
    return f"""      <div class="timeline-strip">
{items}
      </div>"""


def _timeline_points(history: list[dict[str, str]], kind: str) -> list[dict[str, str]]:
    best_by_date: dict[str, dict[str, str]] = {}
    for row in history:
        row_date = _row_date_value(row)
        if not row_date:
            continue
        if kind == "bsr":
            rank = _category_rank_number(row) or _subcategory_rank_number(row)
            label = row.get("primary_bsr_category", "") or row.get("sub_bsr_category", "") or "Amazon BSR"
        else:
            rank = _to_int(row.get("display_rank", "") or row.get("display_order", "") or row.get("today_rank", "") or row.get("rank", "") or row.get("position", ""))
            label = row.get("source_name", "") or "Source rank"
        if rank is None:
            continue
        current = best_by_date.get(row_date)
        if current is None or rank < (_to_int(current.get("rank", "")) or 10**9):
            best_by_date[row_date] = {"date": row_date, "rank": str(rank), "label": label}
    return [best_by_date[key] for key in sorted(best_by_date)]


def _source_history_html(history: list[dict[str, str]]) -> str:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in history:
        source = row.get("source_name", "") or row.get("source_type", "") or "Unknown"
        grouped[source].append(row)
    if not grouped:
        return '<div class="empty">No source history available.</div>'
    cards = []
    for source, rows in sorted(grouped.items(), key=lambda item: item[0].lower()):
        dates = [_row_date_value(item) for item in rows if _row_date_value(item)]
        ranks = [_product_display_rank(item) for item in rows]
        ranks = [rank for rank in ranks if rank < 10**9]
        cards.append(
            f"""        <div>
          <span>{escape(source)}</span>
          <strong>{escape(_rank_label(str(min(ranks))) if ranks else "-")}</strong>
          <small>{escape(min(dates) if dates else "")} to {escape(max(dates) if dates else "")}</small>
        </div>"""
        )
    return f"""      <div class="source-history-grid">
{chr(10).join(cards)}
      </div>"""


def _winner_journey_html(row: dict[str, str], history: list[dict[str, str]]) -> str:
    milestones = _winner_journey(row, history)
    items = "\n".join(
        f"""        <div class="journey-step {'is-complete' if date_value else ''}">
          <span>{escape(label)}</span>
          <strong>{escape(date_value or "Pending")}</strong>
        </div>"""
        for label, date_value in milestones
    )
    return f"""      <div class="journey">
{items}
      </div>"""


def _winner_journey(row: dict[str, str], history: list[dict[str, str]]) -> list[tuple[str, str]]:
    return [
        ("First Seen", _first_seen_from_history(row, history)),
        ("New Release", _first_history_date(history, _is_new_release_source)),
        ("Seller Top10", _first_history_date(history, lambda item: _is_seller_source(item) and _product_display_rank(item) <= 10)),
        ("Best Seller", _first_history_date(history, _is_best_seller)),
        ("Stable Winner", _stable_winner_date(row, history)),
    ]


def _first_seen_from_history(row: dict[str, str], history: list[dict[str, str]]) -> str:
    dates = [_row_date_value(item) for item in history if _row_date_value(item)]
    return min(dates) if dates else _first_seen_value(row)


def _first_history_date(history: list[dict[str, str]], predicate) -> str:
    dates = [_row_date_value(row) for row in history if predicate(row) and _row_date_value(row)]
    return min(dates) if dates else ""


def _stable_winner_date(row: dict[str, str], history: list[dict[str, str]]) -> str:
    dates = sorted({_row_date_value(item) for item in history if _product_display_rank(item) <= 10 and _row_date_value(item)})
    if len(dates) >= 2:
        return dates[-1]
    if _is_stable_winner(row):
        return row.get("date", "") or row.get("latest_seen_at", "")[:10] or _row_date_value(row)
    return ""


def _row_date_value(row: dict[str, str]) -> str:
    return (
        row.get("date", "")
        or row.get("first_seen_date", "")
        or row.get("latest_seen_at", "")[:10]
        or row.get("fetched_at", "")[:10]
    )


def _detail_modal_id(row: dict[str, str], index: int) -> str:
    key = row.get("asin", "").strip().upper() or str(index)
    safe = "".join(char.lower() if char.isalnum() else "-" for char in key)
    return f"product-detail-{safe}-{index}"


def _detail_modal_html(
    row: dict[str, str],
    index: int,
    title: str,
    source_url: str,
    tags: str,
    score_tooltip: str,
) -> str:
    modal_id = _detail_modal_id(row, index)
    product_url = _amazon_product_url(row)
    source_link = _detail_link(source_url)
    product_link = _detail_link(product_url)
    product_url_html = f'<div class="metric"><span>Product URL:</span><strong>{product_link}</strong></div>' if product_link else ""
    source_url_html = f'<div class="metric"><span>Source URL:</span><strong>{source_link}</strong></div>' if source_link else ""
    category_ranks_raw = row.get("category_ranks_raw", "") or row.get("all_bsr_ranks", "")
    category_ranks_html = (
        f'<div class="metric"><span>Category Ranks Raw:</span><strong>{escape(category_ranks_raw)}</strong></div>'
        if category_ranks_raw
        else ""
    )
    review_rating = row.get("review_rating", "") or row.get("rating", "")
    display_rank = row.get("display_rank", "") or row.get("rank", "") or row.get("position", "")
    products_in_source = row.get("products_in_source", "")
    source_name = row.get("source_name", "")
    previous_display_rank = row.get("previous_display_rank", "")
    display_rank_change = _display_rank_change_value(row)
    display_rank_velocity = row.get("display_rank_velocity", "")
    display_percentile = row.get("display_percentile", "")
    rank_change_html = _optional_detail_metric("Source Rank Change", _rank_change(row))
    days_seen_html = _optional_detail_metric("Days Seen", row.get("days_seen", ""))
    first_seen_html = _optional_detail_metric("First Seen", _first_seen_value(row))
    return f"""          <dialog class="detail-modal" id="{escape(modal_id, quote=True)}">
            <div class="detail-modal-header">
              <h2>{escape(title)}</h2>
              <button type="button" data-close-modal aria-label="Close details">Close</button>
            </div>
            <div class="detail-modal-body">
              <div class="detail-title">{escape(title)}</div>
              <div class="meta detail-meta">
                <div class="metric"><span>Full Title:</span><strong>{escape(title)}</strong></div>
                <div class="metric"><span>Decision Score:</span><strong>{escape(row.get("decision_score", ""))}</strong></div>
                {_score_components_html(row)}
                <div class="metric score-breakdown" tabindex="0" title="{escape(score_tooltip, quote=True)}" data-tooltip="{escape(score_tooltip, quote=True)}"><span>Score Components:</span><strong>View breakdown</strong></div>
                <div class="metric"><span>Source Name:</span><strong>{escape(row.get("source_name", ""))}</strong></div>
                <div class="metric"><span>Source Type:</span><strong>{escape(row.get("source_type", "") or row.get("page_type", ""))}</strong></div>
                {_display_rank_metric_html(display_rank, source_name, products_in_source, previous_display_rank, display_rank_change, display_rank_velocity, display_percentile)}
                {rank_change_html}
                <div class="metric"><span>Review Count:</span><strong>{escape(_review_count_label(row.get("review_count", "")))}</strong></div>
                <div class="metric"><span>Reviews:</span><strong>{escape(_review_count_label(row.get("review_count", "")))}</strong><small>Rating: {escape(review_rating)}</small></div>
                <div class="metric"><span>Rating:</span><strong>{escape(review_rating)}</strong></div>
                {days_seen_html}
                {first_seen_html}
                <div class="metric"><span>Growth Velocity:</span><strong>{escape(row.get("growth_velocity", ""))}</strong></div>
                <div class="metric"><span>New Breakout Score:</span><strong>{escape(row.get("new_breakout_score", ""))}</strong></div>
                <div class="metric"><span>POD Score:</span><strong>{escape(row.get("pod_score", ""))}</strong></div>
                <div class="metric"><span>Niche:</span><strong>{escape(row.get("niche_primary", ""))}</strong></div>
                <div class="metric"><span>Tags:</span><strong>{escape(tags)}</strong></div>
                {category_ranks_html}
                {_rank_audit_warning_html(row)}
                {product_url_html}
                {source_url_html}
              </div>
            </div>
          </dialog>"""


def _detail_link(url: str) -> str:
    if not url:
        return ""
    safe = escape(url, quote=True)
    return f'<a href="{safe}" target="_blank" rel="noopener">{escape(url)}</a>'


def _optional_detail_metric(label: str, value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return f'<div class="metric"><span>{escape(label)}:</span><strong>{escape(text)}</strong></div>'


def _source_rank_flow_text(row: dict[str, str]) -> str:
    previous = row.get("previous_display_rank", "")
    current = row.get("display_rank", "") or row.get("display_order", "") or row.get("today_rank", "") or row.get("rank", "") or row.get("position", "")
    change = row.get("display_rank_change", "") or _rank_change(row)
    previous_label = escape(_rank_label(previous))
    current_label = escape(_rank_label(current))
    change_value = _to_int(change)
    if change_value is not None and change_value > 0:
        change_label = f" (+{change_value})"
    elif change_value is not None and change_value < 0:
        change_label = f" ({change_value})"
    elif change_value == 0:
        change_label = " (+0)"
    else:
        change_label = ""
    if previous_label and current_label:
        return f"{previous_label} &rarr; {current_label}{change_label}"
    if current_label:
        return f"{current_label}{change_label}"
    return "-"


def _table_row(row: dict[str, str], fields: list[str]) -> str:
    cells = "".join(f"<td>{_table_value(row.get(field, ''))}</td>" for field in fields)
    return f"          <tr>{cells}</tr>"


def _table_value(value: str) -> str:
    text = str(value or "")
    if text.startswith("http://") or text.startswith("https://"):
        safe = escape(text, quote=True)
        return f'<a href="{safe}" target="_blank" rel="noopener">{escape(text)}</a>'
    return escape(text)


def _database_rows(
    product_rows: list[dict[str, str]],
    opportunity_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    opportunity_by_asin = {
        row.get("asin", "").strip().upper(): row
        for row in opportunity_rows
        if row.get("asin", "").strip()
    }
    rows = []
    for row in product_rows:
        merged = dict(row)
        asin = merged.get("asin", "").strip().upper()
        if asin and asin in opportunity_by_asin:
            _merge_decision_overlay(merged, opportunity_by_asin[asin])
        _ensure_decision_fields(merged)
        merged["asin"] = asin
        merged["badges"] = "; ".join(_badges_for_row(merged))
        merged["source_url"] = _seller_source_url(merged)
        rows.append(merged)
    return sorted(rows, key=lambda row: (_product_display_rank(row), row.get("asin", "")))


def _database_table_row(row: dict[str, str], fields: list[str]) -> str:
    search = " ".join([row.get("asin", ""), row.get("title", "")]).lower()
    attrs = {
        "database-row": "true",
        "seller-key": _filter_key(_seller_label(row)),
        "niche-key": _filter_key(row.get("niche_primary", "") or "Unknown"),
        "badges": "|".join(_filter_key(badge) for badge in _badges_for_row(row)),
        "search": search,
    }
    attr_html = " ".join(f'data-{name}="{escape(value, quote=True)}"' for name, value in attrs.items())
    cells = "".join(f"<td>{_table_value(row.get(field, ''))}</td>" for field in fields)
    return f"          <tr {attr_html}>{cells}</tr>"


def _top_counts(values) -> list[tuple[str, str]]:
    counts: dict[str, int] = defaultdict(int)
    labels: dict[str, str] = {}
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        key = _join_key(text)
        if not key:
            continue
        counts[key] += 1
        labels.setdefault(key, text)
    return [(labels[key], str(count)) for key, count in sorted(counts.items(), key=lambda item: (-item[1], labels[item[0]].lower()))]


def _iter_product_tags(rows: list[dict[str, str]]):
    for row in rows:
        raw = row.get("niche_tags", "")
        for separator in ("|", ","):
            raw = raw.replace(separator, ";")
        for tag in raw.split(";"):
            text = tag.strip()
            if text:
                yield text


def _badge_counts(rows: list[dict[str, str]]) -> list[tuple[str, str]]:
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        for badge in _badges_for_row(row):
            counts[badge] += 1
    return [(badge, str(count)) for badge, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))]


def _trend_panel(title: str, rows: list[tuple[str, str]]) -> str:
    if not rows:
        items = '<li><span>No records found.</span><strong>0</strong></li>'
    else:
        items = "\n".join(f"<li><span>{escape(label)}</span><strong>{escape(_format_number(value))}</strong></li>" for label, value in rows)
    return f"""      <article class="trend-panel">
        <h2>{escape(title)}</h2>
        <ol>
{items}
        </ol>
      </article>"""


def _trend_clusters(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    labels: dict[str, str] = {}
    dimensions: dict[str, dict[str, str]] = {}
    for row in rows:
        parts = _trend_dimensions(row)
        key_parts = _trend_key_parts(parts)
        key = "|".join(_filter_key(part) for part in key_parts if part)
        if not key:
            continue
        label = _trend_name(parts, key_parts)
        grouped[key].append(row)
        labels[key] = label
        dimensions[key] = parts

    clusters: list[dict[str, object]] = []
    for key, cluster_rows in grouped.items():
        deduped = sorted(_dedupe_products(cluster_rows), key=_signal_sort_key)
        if len(deduped) < 2:
            continue
        sellers = {_seller_label(row) for row in deduped if _seller_label(row)}
        growth = sum(max(0, _rank_movement_value(row)) for row in deduped)
        growth += len([row for row in deduped if _is_recent_product(row)]) * 5
        signal_values = [_to_int(row.get("winner_signal_score", "")) or _winner_signal_score(row) for row in deduped]
        signal = max(signal_values) if signal_values else 0
        clusters.append(
            {
                "key": key,
                "name": labels[key],
                "dimensions": dimensions[key],
                "products": deduped,
                "product_count": len(deduped),
                "seller_count": len(sellers),
                "sellers": sellers,
                "growth": growth,
                "signal": signal,
            }
        )
    return sorted(
        clusters,
        key=lambda cluster: (
            -int(cluster.get("signal", 0) or 0),
            -int(cluster.get("growth", 0) or 0),
            -int(cluster.get("product_count", 0) or 0),
            str(cluster.get("name", "")),
        ),
    )


def _trend_dimensions(row: dict[str, str]) -> dict[str, str]:
    text = _trend_text(row)
    product_type = _product_type_label(row)
    recipient = _first_keyword_label(text, RECIPIENT_KEYWORDS)
    occasion = _first_keyword_label(text, OCCASION_KEYWORDS)
    theme = _first_keyword_label(text, THEME_KEYWORDS)
    quote = _first_keyword_label(text, QUOTE_KEYWORDS)
    return {
        "product_type": product_type,
        "recipient": recipient,
        "occasion": occasion,
        "theme": theme,
        "quote": quote,
    }


def _trend_key_parts(parts: dict[str, str]) -> list[str]:
    product_type = parts.get("product_type", "") or "POD Product"
    recipient = parts.get("recipient", "")
    occasion = parts.get("occasion", "")
    theme = parts.get("theme", "")
    quote = parts.get("quote", "")
    if recipient and theme:
        return [recipient, theme, product_type]
    if occasion and recipient:
        return [occasion, recipient, product_type]
    if occasion and theme:
        return [occasion, theme, product_type]
    if quote and product_type:
        return [quote, product_type]
    if theme and product_type:
        return [theme, product_type]
    if recipient and product_type:
        return [recipient, product_type]
    if occasion and product_type:
        return [occasion, product_type]
    return [product_type]


def _trend_name(parts: dict[str, str], key_parts: list[str] | None = None) -> str:
    primary = key_parts if key_parts is not None else _trend_key_parts(parts)
    prefix = " ".join(part for part in primary if part)
    product_type = parts.get("product_type", "") or "POD Product"
    if prefix:
        return prefix
    return product_type


def _trend_text(row: dict[str, str]) -> str:
    return " ".join(
        str(row.get(field, "") or "")
        for field in (
            "title",
            "raw_title",
            "niche_primary",
            "niche_secondary",
            "niche_tags",
            "pod_type",
            "pod_reason",
            "category",
            "source_name",
        )
    ).lower()


def _product_type_label(row: dict[str, str]) -> str:
    pod_type = _filter_key(row.get("pod_type", ""))
    if pod_type in PRODUCT_TYPE_TERMS:
        return PRODUCT_TYPE_TERMS[pod_type]
    text = _trend_text(row)
    label = _first_keyword_label(text, PRODUCT_TYPE_KEYWORDS)
    if label:
        return label
    niche = row.get("niche_primary", "").strip()
    return niche or "POD Product"


def _first_keyword_label(text: str, patterns: list[tuple[str, str]]) -> str:
    for keyword, label in patterns:
        pattern = r"(?<![a-z0-9])" + re.escape(keyword.lower()) + r"(?![a-z0-9])"
        if re.search(pattern, text.lower()):
            return label
    return ""


def _trend_cluster_card(cluster: dict[str, object], index: int) -> str:
    products = cluster.get("products", [])
    product_rows = [row for row in products if isinstance(row, dict)]
    related = "\n".join(_drill_product_row(row, product_index) for product_index, row in enumerate(product_rows[:10]))
    if not related:
        related = '<div class="empty">No related products found.</div>'
    return f"""      <details class="trend-cluster" data-trend-key="{escape(str(cluster.get("key", "")), quote=True)}">
        <summary>
          <span class="trend-name">{escape(str(cluster.get("name", "Unknown Trend")))}</span>
          <span>{escape(_format_number(str(cluster.get("product_count", "0"))))} products</span>
          <span>{escape(_format_number(str(cluster.get("seller_count", "0"))))} sellers</span>
          <span>Growth {escape(_format_number(str(cluster.get("growth", "0"))))}</span>
          <strong>Signal {escape(str(cluster.get("signal", "0")))}</strong>
        </summary>
        <div class="drill-panel" data-drill-panel>
          <div class="drill-products">
{related}
          </div>
        </div>
      </details>"""


def _field_label(field: str) -> str:
    labels = {
        "coverage": "Top-page coverage",
        "top_page_coverage": "Top-page coverage",
        "full_coverage": "Full coverage",
        "expected_top_products": "Expected top products",
    }
    return labels.get(field, field.replace("_", " ").title())


def _new_product_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [row for row in rows if _is_recent_product(row)]


def _rising_product_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(rows, key=lambda row: _rank_movement_value(row), reverse=True)


def _signal_sort_key(row: dict[str, str]) -> tuple[int, int, int, str]:
    _ensure_decision_fields(row)
    return (
        -(_to_int(row.get("winner_signal_score", "")) or 0),
        -(_rank_movement_value(row)),
        _product_display_rank(row),
        row.get("asin", ""),
    )


def _winner_signal_score(row: dict[str, str]) -> int:
    rank_score = _winner_rank_score(row)
    momentum_score = _winner_momentum_score(row)
    freshness_score = _winner_freshness_score(row)
    cross_source_score = 10 if (_to_int(row.get("source_count", "")) or 1) >= 2 else 0
    source_quality_score = _winner_source_quality_score(row)
    bsr_score = min(10, _bsr_score(row) // 2)
    return min(100, rank_score + momentum_score + freshness_score + cross_source_score + source_quality_score + bsr_score)


def _winner_rank_score(row: dict[str, str]) -> int:
    rank = _product_display_rank(row)
    if rank <= 3:
        return 35
    if rank <= 10:
        return 30
    if rank <= 20:
        return 22
    if rank <= 50:
        return 14
    if rank <= 100:
        return 8
    return 0


def _winner_momentum_score(row: dict[str, str]) -> int:
    movement = _rank_movement_value(row)
    if movement >= 25:
        return 25
    if movement >= 15:
        return 20
    if movement >= 10:
        return 16
    if movement >= 5:
        return 10
    if movement > 0:
        return 5
    return 0


def _winner_freshness_score(row: dict[str, str]) -> int:
    days_seen = _to_int(row.get("days_seen", ""))
    if days_seen is not None:
        if days_seen <= 1:
            return 20
        if days_seen <= 3:
            return 16
        if days_seen <= 7:
            return 10
        if days_seen <= 14:
            return 5
        return 0
    if _first_seen_recent(row, recent_days=1):
        return 16
    if _first_seen_recent(row, recent_days=7):
        return 8
    return 0


def _winner_source_quality_score(row: dict[str, str]) -> int:
    score = 0
    if _is_best_seller(row):
        score += 5
    if _is_new_release_source(row):
        score += 4
    if _is_seller_source(row) and _is_top_10(row):
        score += 5
    return min(10, score)


def _is_new_winner(row: dict[str, str]) -> bool:
    labels = _classification_labels(row)
    return (
        "new_win" in labels
        or (_is_recent_product(row) and _product_display_rank(row) <= 20)
        or (_is_new_release_source(row) and _product_display_rank(row) <= 20 and _rank_movement_value(row) >= 3)
    )


def _is_fast_rising(row: dict[str, str]) -> bool:
    return _rank_movement_value(row) >= 10


def _is_stable_winner(row: dict[str, str]) -> bool:
    labels = _classification_labels(row)
    days_seen = _to_int(row.get("days_seen", "")) or 0
    return "winner" in labels or (_product_display_rank(row) <= 10 and days_seen >= 7)


def _is_best_seller(row: dict[str, str]) -> bool:
    text = " ".join(
        str(row.get(field, "") or "")
        for field in ("source_type", "page_type", "source_name", "source_types")
    ).lower()
    normalized = text.replace("-", "_").replace(" ", "_")
    return "best_seller" in normalized or "best_sellers" in normalized or "category_best_seller" in normalized


def _is_seller_source(row: dict[str, str]) -> bool:
    source_type = _filter_key(row.get("source_type", "") or row.get("page_type", ""))
    return source_type == "seller"


def _is_competitor_launch(row: dict[str, str]) -> bool:
    return _is_seller_source(row) and _is_recent_product(row) and _product_display_rank(row) <= 10


def _signal_keys(row: dict[str, str]) -> list[str]:
    keys = []
    if _is_new_winner(row):
        keys.append("new-winner")
    if _is_fast_rising(row):
        keys.append("fast-rising")
    if _is_stable_winner(row):
        keys.append("stable-winner")
    if _is_best_seller(row):
        keys.append("best-seller")
    if _is_new_release_source(row):
        keys.append("new-release")
    return keys


def _signal_query_from_badge(value: str) -> str:
    key = _filter_key(value)
    mapping = {
        "top winner": "stable-winner",
        "new breakout": "new-winner",
        "fast mover": "fast-rising",
        "new release": "new-release",
        "top 10": "stable-winner",
    }
    return mapping.get(key, key.replace(" ", "-"))


def _trend_key_for_row(row: dict[str, str]) -> str:
    parts = _trend_dimensions(row)
    key_parts = _trend_key_parts(parts)
    return "|".join(_filter_key(part) for part in key_parts if part)


def _is_top_winner(row: dict[str, str]) -> bool:
    return _truthy(row.get("badge_top_winner", "")) or _derived_is_top_winner(row)


def _is_fast_mover(row: dict[str, str]) -> bool:
    return _truthy(row.get("badge_fast_mover", "")) or _derived_is_fast_mover(row)


def _is_new_breakout(row: dict[str, str]) -> bool:
    return _truthy(row.get("badge_new_breakout", "")) or _derived_is_new_breakout(row)


def _is_top_10(row: dict[str, str]) -> bool:
    return _truthy(row.get("badge_top_10", "")) or _product_display_rank(row) <= 10


def _derived_is_top_winner(row: dict[str, str]) -> bool:
    labels = _classification_labels(row)
    alert_type = row.get("alert_type", "").strip().lower()
    return "winner" in labels or alert_type == "winner" or _product_display_rank(row) <= 10


def _derived_is_fast_mover(row: dict[str, str]) -> bool:
    return _rank_movement_value(row) >= 10


def _derived_is_new_breakout(row: dict[str, str]) -> bool:
    labels = _classification_labels(row)
    return "new_win" in labels or (_is_recent_product(row) and (_rank_movement_value(row) >= 5 or _product_display_rank(row) <= 20))


def _is_recent_product(row: dict[str, str]) -> bool:
    days_seen = _to_int(row.get("days_seen", ""))
    if days_seen is not None and days_seen <= 3:
        return True
    return _first_seen_recent(row, recent_days=3)


def _is_new_release_source(row: dict[str, str]) -> bool:
    if _truthy(row.get("badge_new_release", "")):
        return True
    return _derived_is_new_release_source(row)


def _derived_is_new_release_source(row: dict[str, str]) -> bool:
    text = " ".join(
        str(row.get(field, "") or "")
        for field in ("source_name", "source_type", "page_type", "category")
    ).lower()
    normalized = text.replace("-", " ").replace("_", " ")
    return any(
        phrase in normalized
        for phrase in ("new release", "new releases", "newest arrivals", "recently launched")
    )


def _rank_movement_value(row: dict[str, str]) -> int:
    return max(0, _display_rank_change_value(row) or 0, _to_int(_rank_change(row)) or 0)


def _growth_velocity_value(row: dict[str, str]) -> float:
    display_change = _display_rank_change_value(row) or 0
    days_seen = max(_to_int(row.get("days_seen", "")) or 1, 1)
    return display_change / days_seen


def _top_rank_score(row: dict[str, str]) -> int:
    rank = _product_display_rank(row)
    if rank <= 3:
        return 30
    if rank <= 10:
        return 25
    if rank <= 20:
        return 18
    if rank <= 50:
        return 10
    return 0


def _velocity_score(row: dict[str, str]) -> int:
    movement = _rank_movement_value(row)
    if movement >= 25:
        return 30
    if movement >= 15:
        return 24
    if movement >= 10:
        return 18
    if movement >= 5:
        return 12
    if movement > 0:
        return 6
    return 0


def _newness_score(row: dict[str, str]) -> int:
    days_seen = _to_int(row.get("days_seen", ""))
    if days_seen is not None:
        if days_seen <= 1:
            return 25
        if days_seen <= 3:
            return 20
        if days_seen <= 7:
            return 12
        if days_seen <= 14:
            return 6
        return 0
    if _first_seen_recent(row, recent_days=1):
        return 20
    if _first_seen_recent(row, recent_days=3):
        return 12
    return 0


def _bsr_score(row: dict[str, str]) -> int:
    subcategory_rank = _subcategory_rank_number(row)
    if subcategory_rank is not None:
        if subcategory_rank <= 100:
            return 20
        if subcategory_rank <= 500:
            return 16
        if subcategory_rank <= 1000:
            return 12
        if subcategory_rank <= 5000:
            return 8
    category_rank = _category_rank_number(row)
    if category_rank is not None:
        if category_rank <= 10000:
            return 10
        if category_rank <= 50000:
            return 6
        if category_rank <= 100000:
            return 3
    return 0


def _first_seen_value(row: dict[str, str]) -> str:
    return (
        row.get("first_seen", "")
        or row.get("first_seen_date", "")
        or row.get("first_seen_at", "")
        or ""
    )


def _first_seen_recent(row: dict[str, str], *, recent_days: int) -> bool:
    first_seen = _parse_date(_first_seen_value(row))
    current = _parse_date(row.get("date", "") or row.get("last_seen_date", "") or row.get("fetched_at", ""))
    if first_seen is None or current is None:
        return False
    age = (current - first_seen).days
    return 0 <= age <= recent_days


def _parse_date(value: str) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    for candidate in (text[:10], text.replace("Z", "+00:00")):
        try:
            return date.fromisoformat(candidate[:10])
        except ValueError:
            pass
        try:
            return datetime.fromisoformat(candidate).date()
        except ValueError:
            pass
    return None


def _card_data_attrs(row: dict[str, str], index: int) -> str:
    _ensure_decision_fields(row)
    badges = _badges_for_row(row)
    search_text = " ".join([row.get("asin", ""), display_product_title(row.get("title", ""))]).lower()
    attrs = {
        "card-index": str(index),
        "asin": row.get("asin", "").strip().upper(),
        "winner-signal-score": _sort_number(row.get("winner_signal_score", "")),
        "opportunity-score": _sort_number(row.get("opportunity_score", "")),
        "decision-score": _sort_number(row.get("decision_score", "")),
        "display-rank-change": _sort_signed_number(_display_rank_change_value(row)),
        "display-rank-velocity": _sort_signed_float(row.get("display_rank_velocity", "")),
        "top-percentile": _sort_percentile(row.get("display_percentile", "")),
        "category-rank": _sort_category_rank(row),
        "subcategory-rank": _sort_subcategory_rank(row),
        "bsr-rank": _sort_best_bsr_rank(row),
        "review-count": _sort_number(row.get("review_count", "")),
        "rank-change": _sort_number(_rank_change(row)),
        "growth-velocity": _sort_signed_float(row.get("growth_velocity", "")),
        "new-breakout-score": _sort_number(row.get("new_breakout_score", "")),
        "pod-score": _sort_number(row.get("pod_score", "")),
        "pod": _bool_attr(pod_allowed(row)),
        "new": _bool_attr(_is_recent_product(row)),
        "rank-mover": _bool_attr(_is_rank_mover(row)),
        "top10": _bool_attr(_is_top_10(row)),
        "new-winner": _bool_attr(_is_new_winner(row)),
        "fast-rising": _bool_attr(_is_fast_rising(row)),
        "stable-winner": _bool_attr(_is_stable_winner(row)),
        "best-seller": _bool_attr(_is_best_seller(row)),
        "new-release": _bool_attr(_is_new_release_source(row)),
        "seller-key": _filter_key(_seller_label(row)),
        "niche-key": _filter_key(row.get("niche_primary", "") or "Unknown"),
        "product-type-key": _filter_key(_product_type_label(row)),
        "days-tracked": _sort_number(row.get("days_seen", "")),
        "source-type-key": _filter_key(row.get("source_type", "") or row.get("page_type", "") or "Unknown"),
        "badges": "|".join(_filter_key(badge) for badge in badges),
        "signal-keys": "|".join(_signal_keys(row)),
        "trend-key": _trend_key_for_row(row),
        "search": search_text,
    }
    return " ".join(f'data-{name}="{escape(value, quote=True)}"' for name, value in attrs.items())


def _display_rank_change_value(row: dict[str, str]) -> int | None:
    return _to_int(row.get("display_rank_change", "") or row.get("source_rank_change", ""))


def _rank_change(row: dict[str, str]) -> str:
    return row.get("source_rank_change", "") or row.get("rank_change", "") or row.get("rank_change_vs_previous_seen", "")


def _category_rank(row: dict[str, str]) -> str:
    rank = row.get("primary_bsr_rank", "").strip() or row.get("bsr_rank", "").strip()
    category = row.get("primary_bsr_category", "").strip() or row.get("bsr_category", "").strip()
    if rank and category:
        return f"#{_format_number(rank)} in {category}"
    return ""


def _subcategory_rank(row: dict[str, str]) -> str:
    rank = row.get("sub_bsr_rank", "").strip()
    category = row.get("sub_bsr_category", "").strip()
    if rank and category:
        return f"#{_format_number(rank)} in {category}"
    return ""


def _rank_metric_html(label: str, value: str, css_class: str) -> str:
    if not value:
        return ""
    return f'<div class="category-rank {escape(css_class, quote=True)}"><span>{escape(label)}</span><strong>{escape(value)}</strong></div>'


def _rank_audit_warning_html(row: dict[str, str]) -> str:
    parse_method = row.get("rank_parse_method", "").strip()
    confidence = row.get("rank_parse_confidence", "").strip()
    if not parse_method or confidence == "high":
        return ""
    warning = row.get("rank_parse_warning", "").strip()
    label = f"{parse_method} / {confidence or 'unknown'}"
    small = f"<small>{escape(warning)}</small>" if warning else ""
    return f'<div class="category-rank rank-audit-warning"><span>Rank Audit:</span><strong>{escape(label)}</strong>{small}</div>'


def _display_rank_metric_html(
    display_rank: str,
    source_name: str,
    products_in_source: str,
    previous_display_rank: str,
    display_rank_change: int | None,
    display_rank_velocity: str,
    display_percentile: str,
) -> str:
    if not display_rank:
        return ""
    css_class = _display_rank_class(display_rank_change)
    title = f"#{_format_number(display_rank)}"
    if source_name:
        title = f"{title} in {source_name}"
    elif products_in_source:
        title = f"{title} of {_format_number(products_in_source)}"
    parts = [f'<div class="metric display-rank {escape(css_class, quote=True)}"><span>Display Rank:</span><strong>{escape(title)}</strong>']
    if display_percentile:
        parts.append(f"<small>Top {_format_percent(display_percentile)}%</small>")
    parts.append("</div>")
    if previous_display_rank:
        parts.append(
            f'<div class="metric display-rank {escape(css_class, quote=True)}"><span>Previous Display Rank:</span><strong>#{escape(_format_number(previous_display_rank))}</strong></div>'
        )
    if display_rank_change is not None:
        movement = _display_rank_movement_text(display_rank_change)
        parts.append(
            f'<div class="metric display-rank {escape(css_class, quote=True)}"><span>Movement:</span><strong>{escape(movement)}</strong>'
        )
        if display_rank_velocity:
            parts[-1] += f"<small>Velocity: {escape(_format_signed_float(display_rank_velocity))}</small>"
        parts[-1] += "</div>"
    return "".join(parts)


def _display_rank_class(display_rank_change: int | None) -> str:
    if display_rank_change is None:
        return "display-rank--gray"
    if display_rank_change >= 20:
        return "display-rank--green"
    if display_rank_change >= 10:
        return "display-rank--blue"
    if display_rank_change >= 1:
        return "display-rank--light-green"
    if display_rank_change == 0:
        return "display-rank--gray"
    return "display-rank--red"


def _display_rank_movement_text(display_rank_change: int) -> str:
    if display_rank_change > 0:
        return f"Up {display_rank_change} positions"
    if display_rank_change < 0:
        return f"Down {abs(display_rank_change)} positions"
    return "No change"


def _score_breakdown_tooltip(row: dict[str, str]) -> str:
    return "\n".join(
        [
            f"POD: {row.get('pod_component', '') or '0'}/30",
            f"Momentum: {row.get('momentum_component', '') or '0'}/25",
            f"Market: {row.get('market_component', '') or '0'}/20",
            f"Competition: {row.get('competition_component', '') or '0'}/10",
            f"Niche: {row.get('niche_component', '') or '0'}/15",
        ]
    )


def _category_rank_class(row: dict[str, str]) -> str:
    rank = _category_rank_number(row)
    return _rank_band_class(rank)


def _subcategory_rank_class(row: dict[str, str]) -> str:
    rank = _subcategory_rank_number(row)
    return _rank_band_class(rank)


def _rank_band_class(rank: int | None) -> str:
    if rank is None:
        return "category-rank--gray"
    if rank <= 10_000:
        return "category-rank--green"
    if rank <= 50_000:
        return "category-rank--blue"
    if rank <= 200_000:
        return "category-rank--orange"
    return "category-rank--gray"


def _category_rank_number(row: dict[str, str]) -> int | None:
    rank = _to_int(row.get("primary_bsr_rank", "") or row.get("bsr_rank", ""))
    if rank is not None:
        return rank
    raw = row.get("all_bsr_ranks", "") or row.get("category_ranks_raw", "")
    if raw.startswith("#"):
        return _to_int(raw.split(" in ", 1)[0].lstrip("#"))
    return None


def _subcategory_rank_number(row: dict[str, str]) -> int | None:
    rank = _to_int(row.get("sub_bsr_rank", ""))
    return rank


def _review_count_label(value: str) -> str:
    text = _format_number(value)
    return f"{text} reviews" if text else ""


def _rank_label(value: str) -> str:
    text = _format_number(value)
    return f"#{text}" if text else ""


def _format_number(value: str) -> str:
    number = _to_int(value)
    if number is None:
        return value
    return f"{number:,}"


def _format_decimal(value: float | None) -> str:
    if value is None:
        return ""
    text = f"{value:.2f}"
    return text.rstrip("0").rstrip(".")


def _sort_number(value: str) -> str:
    number = _to_int(value)
    return str(number) if number is not None else "0"


def _sort_signed_number(value: int | None) -> str:
    return str(value) if value is not None else "0"


def _sort_signed_float(value: str) -> str:
    number = _to_float(value)
    return str(number) if number is not None else "0"


def _sort_percentile(value: str) -> str:
    number = _to_float(value)
    return str(number) if number is not None else "999999"


def _format_percent(value: str) -> str:
    number = _to_float(value)
    if number is None:
        return value
    text = f"{number:.1f}"
    return text.rstrip("0").rstrip(".")


def _format_signed_float(value: str) -> str:
    number = _to_float(value)
    if number is None:
        return value
    return f"{number:+.1f}".rstrip("0").rstrip(".")


def _sort_category_rank(row: dict[str, str]) -> str:
    rank = _category_rank_number(row)
    return str(rank) if rank is not None else "9007199254740991"


def _sort_subcategory_rank(row: dict[str, str]) -> str:
    rank = _subcategory_rank_number(row)
    return str(rank) if rank is not None else "9007199254740991"


def _sort_best_bsr_rank(row: dict[str, str]) -> str:
    rank = _subcategory_rank_number(row) or _category_rank_number(row)
    return str(rank) if rank is not None else "9007199254740991"


def _group_products(rows: list[dict[str, str]]) -> list[tuple[str, list[dict[str, str]]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        group_name = row.get("seller_name", "") or row.get("source_name", "") or row.get("seller_id", "") or "Unknown Source"
        grouped[group_name].append(row)
    return sorted(grouped.items(), key=lambda item: item[0].lower())


def _source_group_section(name: str, rows: list[dict[str, str]]) -> str:
    sorted_rows = sorted(rows, key=lambda row: _to_int(row.get("rank", "") or row.get("display_rank", "")) or 10**9)
    cards = "\n".join(_source_product_card(row, index) for index, row in enumerate(sorted_rows))
    return f"""    <details>
      <summary>{escape(name)} ({len(rows)} products)</summary>
      <div class="source-grid" data-sortable-cards>
{cards}
      </div>
    </details>"""


def _competitor_sections(seller_rows: list[dict[str, str]], product_rows: list[dict[str, str]]) -> list[str]:
    sellers = seller_rows or _seller_rows_from_products(product_rows)
    sections: list[str] = []
    for index, seller_row in enumerate(sellers):
        products = _seller_products(seller_row, product_rows)
        top10 = [row for row in products if _product_display_rank(row) <= 10][:10]
        if not top10 and not products:
            continue
        label = _seller_label(seller_row)
        new_launches = len([row for row in products if _is_competitor_launch(row)])
        winners = len([row for row in products if _is_stable_winner(row) or _is_top_10(row)])
        rising = len([row for row in products if _is_fast_rising(row)])
        dropped = len([row for row in products if _dropped_from_top10(row)])
        cards = "\n".join(_competitor_product_row(row, product_index) for product_index, row in enumerate(top10))
        if not cards:
            cards = '        <div class="empty">No current Top10 products.</div>'
        seller_url = _seller_source_url(seller_row)
        seller_link = (
            f'<a class="quick-link" href="{escape(seller_url, quote=True)}" target="_blank" rel="noopener">Open Seller</a>'
            if seller_url
            else ""
        )
        sections.append(
            f"""    <section class="competitor-panel">
      <div class="competitor-heading">
        <div>
          <h2>{escape(label)}</h2>
          <span>{escape(_format_number(str(len(products))))} tracked products</span>
        </div>
        {seller_link}
      </div>
      <div class="competitor-summary">
        <div><strong>{escape(_format_number(str(new_launches)))}</strong><span>New Launches</span></div>
        <div><strong>{escape(_format_number(str(winners)))}</strong><span>Winners</span></div>
        <div><strong>{escape(_format_number(str(rising)))}</strong><span>Rising Products</span></div>
        <div><strong>{escape(_format_number(str(len(top10))))}</strong><span>Current Top10</span></div>
        <div><strong>{escape(_format_number(str(dropped)))}</strong><span>Dropped From Top10</span></div>
      </div>
      <div class="competitor-products">
{cards}
      </div>
    </section>"""
        )
    return sections


def _seller_rows_from_products(product_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[str, dict[str, str]] = {}
    for row in product_rows:
        if not _is_seller_source(row):
            continue
        key = _filter_key(_seller_label(row))
        if key and key not in grouped:
            grouped[key] = {
                "seller_name": _seller_label(row),
                "seller_id": row.get("seller_id", ""),
                "seller_url": row.get("seller_url", ""),
                "source_name": row.get("source_name", ""),
                "source_type": row.get("source_type", "seller"),
            }
    return sorted(grouped.values(), key=lambda row: _seller_label(row).lower())


def _competitor_product_row(row: dict[str, str], index: int) -> str:
    status = _competitor_status(row)
    return f"""        <div class="competitor-product">
          <span class="status-tag status-{escape(_filter_key(status), quote=True)}">{escape(status)}</span>
{_drill_product_row(row, index)}
        </div>"""


def _competitor_status(row: dict[str, str]) -> str:
    if _is_competitor_launch(row):
        return "NEW"
    if _dropped_from_top10(row):
        return "DROPPED"
    display_change = _display_rank_change_value(row)
    rank_change = _to_int(_rank_change(row))
    movement = display_change if display_change is not None else rank_change
    if movement is not None and movement > 0:
        return "RISING"
    if movement is not None and movement < 0:
        return "FALLING"
    return "STABLE"


def _dropped_from_top10(row: dict[str, str]) -> bool:
    previous = _to_int(row.get("previous_display_rank", "") or row.get("previous_rank", ""))
    current = _product_display_rank(row)
    return previous is not None and previous <= 10 and current > 10


def _seller_table_drill_rows(row: dict[str, str], fields: list[str], products: list[dict[str, str]], index: int) -> str:
    drill_id = f"seller-drill-{index}"
    label = _seller_label(row)
    cells = "".join(f"<td>{_table_value(row.get(field, ''))}</td>" for field in fields)
    panel = _grouped_product_drilldown_panel(
        products,
        _entity_product_groups(products),
        f"No products found for {label}.",
    )
    return f"""          <tr class="drill-parent-row" data-drill-row data-drill-target="{escape(drill_id, quote=True)}">
            {_drill_control_cell(drill_id, label, len(products))}
            {cells}
          </tr>
          <tr class="drill-row" id="{escape(drill_id, quote=True)}" hidden>
            <td colspan="{len(fields) + 1}">
{panel}
            </td>
          </tr>"""


def _niche_table_drill_rows(row: dict[str, str], fields: list[str], products: list[dict[str, str]], index: int) -> str:
    drill_id = f"niche-drill-{index}"
    niche = row.get("niche", "") or "Unknown"
    group = row.get("niche_group", "") or niche_group(niche)
    cells = "".join(f"<td>{_niche_table_value(field, row.get(field, ''))}</td>" for field in fields)
    panel = _grouped_product_drilldown_panel(
        products,
        _entity_product_groups(products),
        f"No products found for {niche}.",
    )
    return f"""          <tr class="drill-parent-row" data-drill-row data-drill-target="{escape(drill_id, quote=True)}" data-niche-group="{escape(group, quote=True)}">
            {_drill_control_cell(drill_id, niche, len(products))}
            {cells}
          </tr>
          <tr class="drill-row" id="{escape(drill_id, quote=True)}" data-niche-group="{escape(group, quote=True)}" hidden>
            <td colspan="{len(fields) + 1}">
{panel}
            </td>
          </tr>"""


def _drill_control_cell(drill_id: str, label: str, product_count: int) -> str:
    return (
        '<td class="drill-control-cell">'
        f'<button class="drill-toggle" type="button" aria-expanded="false" '
        f'aria-controls="{escape(drill_id, quote=True)}" aria-label="Toggle products for {escape(label, quote=True)}" '
        'data-drill-toggle>+</button>'
        f'<span class="drill-product-count">{escape(_format_number(str(product_count)))}</span>'
        "</td>"
    )


def _niche_table_value(field: str, value: str) -> str:
    if field == "niche_group":
        return escape(GROUP_LABELS.get(value, value or GROUP_LABELS["unknown"]))
    if field in {
        "niche_momentum_score",
        "products_tracked",
        "opportunities",
        "new_wins",
        "rising_products",
        "best_rank",
        "best_bsr_rank",
        "best_subcategory_rank",
    }:
        return escape(_format_number(value))
    return _table_value(value)


def _niche_card(row: dict[str, str], products: list[dict[str, str]], index: int) -> str:
    niche = row.get("niche", "") or "Unknown"
    group = row.get("niche_group", "") or niche_group(niche)
    group_label = GROUP_LABELS.get(group, group or GROUP_LABELS["unknown"])
    image_url = row.get("top_product_image_url", "")
    image_html = f'<img src="{escape(image_url, quote=True)}" alt="{escape(niche, quote=True)}">' if image_url else ""
    top_url = row.get("top_product_url", "")
    top_title = display_product_title(row.get("top_product_title", "")) if row.get("top_product_title", "") else "No top product"
    open_link = f'<a href="{escape(top_url, quote=True)}" target="_blank" rel="noopener">' if top_url else ""
    close_link = "</a>" if top_url else ""
    drill_panel = _grouped_product_drilldown_panel(
        products,
        _entity_product_groups(products),
        f"No products found for {niche}.",
    )
    return f"""      <article class="niche-card" data-niche-group="{escape(group, quote=True)}">
        {open_link}{image_html}{close_link}
        <div class="niche-card-body">
          <div>
            <h3>{escape(niche)}</h3>
            <div class="metric"><span>{escape(group_label)}</span></div>
          </div>
          <div class="niche-score">{escape(row.get("niche_momentum_score", "") or "0")}</div>
          <div class="niche-stats">
            <div><strong>{escape(_format_number(row.get("products_tracked", "")))}</strong>products tracked</div>
            <div><strong>{escape(_format_number(row.get("new_wins", "")))}</strong>new wins</div>
            <div><strong>{escape(_format_number(row.get("rising_products", "")))}</strong>rising products</div>
            <div><strong>{escape(_rank_label(row.get("best_rank", "")))}</strong>best rank</div>
            <div><strong>{escape(_rank_label(row.get("best_subcategory_rank", "")))}</strong>best subcategory</div>
          </div>
          <div class="niche-product-title">{open_link}{escape(top_title)}{close_link}</div>
          <div class="metric"><span>Top Seller:</span><strong>{escape(row.get("top_seller", ""))}</strong></div>
          <details class="niche-card-drilldown" data-drill-details>
            <summary>Products ({escape(_format_number(str(len(products))))})</summary>
{drill_panel}
          </details>
        </div>
      </article>"""


def _grouped_product_drilldown_panel(
    products: list[dict[str, str]],
    groups: list[tuple[str, list[dict[str, str]]]],
    empty_message: str,
) -> str:
    if not products:
        return _product_drilldown_panel(products, empty_message)
    sections = [_drill_overview_section(products)]
    used_keys: set[str] = set()
    for label, group_rows in groups:
        visible_rows: list[dict[str, str]] = []
        for row in group_rows:
            key = _group_product_key(row)
            if key in used_keys:
                continue
            used_keys.add(key)
            visible_rows.append(row)
        sections.append(
            f"""                <section class="drill-group">
                  <h3>{escape(label)}</h3>
{_product_drilldown_panel(visible_rows, f"No {label.lower()} found.")}
                </section>"""
        )
    if not sections:
        return _product_drilldown_panel(products, empty_message)
    return f"""              <div class="drill-groups">
{chr(10).join(sections)}
              </div>"""


def _entity_product_groups(products: list[dict[str, str]]) -> list[tuple[str, list[dict[str, str]]]]:
    deduped = sorted(_dedupe_products(products), key=_today_sort_key)
    assigned: dict[str, list[dict[str, str]]] = {
        "Top Products": [],
        "New Breakouts": [],
        "Fast Movers": [],
        "New Releases": [],
    }
    for row in deduped:
        if _is_top_winner(row) or _is_top_10(row):
            assigned["Top Products"].append(row)
        elif _is_new_breakout(row):
            assigned["New Breakouts"].append(row)
        elif _is_fast_mover(row):
            assigned["Fast Movers"].append(row)
        elif _is_new_release_source(row):
            assigned["New Releases"].append(row)
        else:
            assigned["Top Products"].append(row)
    return [(label, assigned[label]) for label in ("Top Products", "New Breakouts", "Fast Movers", "New Releases")]


def _drill_overview_section(products: list[dict[str, str]]) -> str:
    unique_products = _dedupe_products(products)
    badge_counts = _badge_counts(unique_products)
    badge_text = ", ".join(f"{label}: {count}" for label, count in badge_counts) or "No badges"
    avg_score_values = [_to_int(row.get("opportunity_score", "")) for row in unique_products]
    avg_score_values = [value for value in avg_score_values if value is not None]
    avg_score = str(round(sum(avg_score_values) / len(avg_score_values))) if avg_score_values else "0"
    return f"""                <section class="drill-group drill-overview">
                  <h3>Overview</h3>
                  <div class="drill-overview-grid">
                    <div><strong>{escape(_format_number(str(len(unique_products))))}</strong><span>products</span></div>
                    <div><strong>{escape(avg_score)}</strong><span>avg opportunity</span></div>
                    <div><strong>{escape(_format_number(str(len([row for row in unique_products if _is_rank_mover(row)]))))}</strong><span>rank movers</span></div>
                    <div><strong>{escape(_format_number(str(len([row for row in unique_products if _is_new_release_source(row)]))))}</strong><span>new releases</span></div>
                  </div>
                  <p>{escape(badge_text)}</p>
                </section>"""


def _group_product_key(row: dict[str, str]) -> str:
    asin = row.get("asin", "").strip().upper()
    if asin:
        return asin
    product_url = row.get("product_url", "").strip().lower()
    if product_url:
        return product_url
    return str(id(row))


def _product_drilldown_panel(products: list[dict[str, str]], empty_message: str) -> str:
    if not products:
        return f"""              <div class="drill-panel" data-drill-panel>
                <div class="empty">{escape(empty_message)}</div>
              </div>"""
    product_html = "\n".join(_drill_product_row(row, index) for index, row in enumerate(products))
    shown = min(len(products), 10)
    return f"""              <div class="drill-panel" data-drill-panel data-showing-all="false">
                <div class="drill-toolbar">
                  <div class="drill-filters" aria-label="Product filters">
                    <label><input type="checkbox" data-drill-filter="newWin"> New Wins only</label>
                    <label><input type="checkbox" data-drill-filter="rising"> Rising only</label>
                    <label><input type="checkbox" data-drill-filter="pod"> POD only</label>
                    <label><input type="checkbox" data-drill-filter="rankMover"> Rank movers only</label>
                  </div>
                  <div class="drill-actions">
                    <span class="drill-status"><span data-visible-count>{shown}</span> of <span data-total-count>{len(products)}</span> shown</span>
                    <button type="button" data-show-all-products>Show all products</button>
                    <button type="button" data-collapse-drilldown>Collapse</button>
                  </div>
                </div>
                <div class="drill-products" data-default-limit="10">
{product_html}
                </div>
              </div>"""


def _drill_product_row(row: dict[str, str], index: int) -> str:
    ensure_category_rank_fields(row)
    ensure_detail_fix_fields(row)
    ensure_niche_fields(row)
    image_src = row.get("local_image_path", "") or row.get("image_url", "")
    title = display_product_title(row.get("title", ""))
    if not title:
        title = row.get("asin", "") or "Untitled"
    asin = row.get("asin", "").strip().upper()
    product_url = _amazon_product_url(row)
    seller_source_url = _seller_source_url(row)
    display_rank = row.get("display_rank", "") or row.get("display_order", "") or row.get("today_rank", "") or row.get("rank", "") or row.get("position", "")
    display_rank_change = _display_rank_change_value(row)
    display_rank_change_text = _display_rank_movement_text(display_rank_change) if display_rank_change is not None else ""
    rating = row.get("review_rating", "") or row.get("rating", "")
    extra_class = " is-extra is-hidden" if index >= 10 else ""
    thumb_class = "drill-thumb" if image_src else "drill-thumb drill-thumb--empty"
    image_html = f'<img src="{escape(image_src, quote=True)}" alt="{escape(title, quote=True)}">' if image_src else "No image"
    amazon_link = (
        f'<a class="quick-link" href="{escape(product_url, quote=True)}" target="_blank" rel="noopener">Open Amazon</a>'
        if product_url
        else ""
    )
    source_link = (
        f'<a class="quick-link" href="{escape(seller_source_url, quote=True)}" target="_blank" rel="noopener">Open seller source</a>'
        if seller_source_url
        else ""
    )
    copy_button = f'<button type="button" data-copy-asin="{escape(asin, quote=True)}">Copy ASIN</button>' if asin else ""
    title_html = (
        f'<a href="{escape(product_url, quote=True)}" target="_blank" rel="noopener">{escape(title)}</a>'
        if product_url
        else escape(title)
    )
    badges = _badge_html(_badges_for_row(row))
    return f"""                  <article class="drill-product{extra_class}" {_drill_product_data_attrs(row, index)}>
                    <div class="drill-rank">{escape(_rank_label(display_rank) or "-")}</div>
                    <div class="{thumb_class}">{image_html}</div>
                    <div class="drill-main">
                      {badges}
                      <div class="drill-title">{title_html}</div>
                      <div class="drill-meta">
                        {_drill_meta_item("ASIN", asin)}
                        {_drill_meta_item("Opportunity Score", row.get("opportunity_score", ""))}
                        {_drill_meta_item("Source Rank Change", _rank_change(row))}
                        {_drill_meta_item("Display Rank Change", display_rank_change_text)}
                        {_drill_meta_item("Amazon BSR", _category_rank(row))}
                        {_drill_meta_item("Best Subcategory Rank", _subcategory_rank(row))}
                        {_drill_meta_item("Reviews", _format_number(row.get("review_count", "")))}
                        {_drill_meta_item("Rating", rating)}
                        {_drill_meta_item("Niche", row.get("niche_primary", ""))}
                      </div>
                      <div class="quick-actions">
                        {amazon_link}
                        {copy_button}
                        {source_link}
                      </div>
                    </div>
                  </article>"""


def _drill_meta_item(label: str, value: str) -> str:
    text = str(value or "").strip()
    if not text:
        text = "-"
    return f"<span><strong>{escape(label)}:</strong> {escape(text)}</span>"


def _drill_product_data_attrs(row: dict[str, str], index: int) -> str:
    attrs = {
        "drill-index": str(index),
        "new-win": _bool_attr(_is_new_win(row)),
        "rising": _bool_attr(_is_rising(row)),
        "pod": _bool_attr(pod_allowed(row)),
        "rank-mover": _bool_attr(_is_rank_mover(row)),
    }
    return " ".join(f'data-{name}="{escape(value, quote=True)}"' for name, value in attrs.items())


def _seller_products(seller_row: dict[str, str], product_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    matches = [row for row in product_rows if _seller_matches_product(seller_row, row)]
    return sorted(_dedupe_products(matches), key=_seller_product_sort_key)


def _niche_products(niche_row: dict[str, str], product_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    niche = _join_key(niche_row.get("niche", "") or "Unknown")
    matches = [row for row in product_rows if niche in _product_niche_keys(row)]
    return sorted(_dedupe_products(matches), key=_niche_product_sort_key)


def _dedupe_products(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    best: dict[str, tuple[tuple[int, int, int], dict[str, str]]] = {}
    for index, row in enumerate(rows):
        key = _dedupe_product_key(row, index)
        sort_key = (
            _product_display_rank(row),
            -(_to_int(row.get("opportunity_score", "")) or 0),
            index,
        )
        current = best.get(key)
        if current is None or sort_key < current[0]:
            best[key] = (sort_key, row)
    return [item[1] for item in best.values()]


def _dedupe_product_key(row: dict[str, str], index: int) -> str:
    asin = row.get("asin", "").strip().upper()
    if asin:
        return asin
    product_url = row.get("product_url", "").strip().lower()
    if product_url:
        return product_url
    return f"__row_{index}"


def _seller_matches_product(seller_row: dict[str, str], product_row: dict[str, str]) -> bool:
    seller_id = _join_key(seller_row.get("seller_id", ""))
    product_seller_id = _join_key(product_row.get("seller_id", ""))
    if seller_id and product_seller_id and seller_id == product_seller_id:
        return True
    seller_names = _seller_join_keys(seller_row)
    product_names = _seller_join_keys(product_row)
    return bool(seller_names & product_names)


def _seller_join_keys(row: dict[str, str]) -> set[str]:
    return {
        key
        for key in (
            _join_key(row.get("seller_name", "")),
            _join_key(row.get("source_name", "")),
            _join_key(row.get("seller_id", "")),
        )
        if key
    }


def _product_niche_keys(row: dict[str, str]) -> set[str]:
    keys = {_join_key(row.get("niche_primary", ""))}
    raw_tags = row.get("niche_tags", "")
    for separator in ("|", ","):
        raw_tags = raw_tags.replace(separator, ";")
    keys.update(_join_key(tag) for tag in raw_tags.split(";") if tag.strip())
    keys.update(_join_key(tag) for tag in niche_tags(row) if tag.strip())
    keys.discard("")
    return keys


def _seller_product_sort_key(row: dict[str, str]) -> tuple[int, str, str]:
    return (_product_display_rank(row), display_product_title(row.get("title", "")).lower(), row.get("asin", ""))


def _niche_product_sort_key(row: dict[str, str]) -> tuple[int, int, str, str]:
    return (
        -(_to_int(row.get("opportunity_score", "")) or 0),
        _product_display_rank(row),
        display_product_title(row.get("title", "")).lower(),
        row.get("asin", ""),
    )


def _product_display_rank(row: dict[str, str]) -> int:
    rank, _ = parse_source_rank(row)
    if rank is not None:
        return rank
    today_rank = _to_int(row.get("today_rank", ""))
    return today_rank if today_rank is not None and today_rank > 0 else 10**9


def _amazon_product_url(row: dict[str, str]) -> str:
    product_url = row.get("product_url", "").strip()
    if product_url:
        return product_url
    asin = row.get("asin", "").strip().upper()
    return f"https://www.amazon.com/dp/{asin}" if is_asin(asin) else ""


def _seller_source_url(row: dict[str, str]) -> str:
    return (
        row.get("seller_url", "").strip()
        or row.get("source_url", "").strip()
        or row.get("page_url", "").strip()
    )


def _seller_label(row: dict[str, str]) -> str:
    return row.get("seller_name", "") or row.get("source_name", "") or row.get("seller_id", "") or "Unknown seller"


def _join_key(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _filter_key(value: str) -> str:
    return _join_key(value)


def _query_value(value: str) -> str:
    return quote(value, safe="")


def _bool_attr(value: bool) -> str:
    return "true" if value else "false"


def _truthy(value: str) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _classification_labels(row: dict[str, str]) -> set[str]:
    raw = row.get("classification", "") or row.get("alert_type", "")
    return {item.strip().lower() for item in str(raw).replace(",", ";").split(";") if item.strip()}


def _is_new_win(row: dict[str, str]) -> bool:
    alert_type = row.get("alert_type", "").lower()
    return (
        "new" in alert_type
        or str(row.get("is_new_win", "")).strip().lower() in {"1", "true", "yes", "y"}
        or ((_to_int(row.get("days_seen", "")) or 10**9) <= 3)
    )


def _is_rising(row: dict[str, str]) -> bool:
    alert_type = row.get("alert_type", "").lower()
    rank_change = _to_int(_rank_change(row)) or 0
    display_change = _display_rank_change_value(row) or 0
    return "rising" in alert_type or rank_change > 0 or display_change > 0


def _is_rank_mover(row: dict[str, str]) -> bool:
    rank_change = _to_int(_rank_change(row))
    display_change = _display_rank_change_value(row)
    return (rank_change is not None and rank_change != 0) or (display_change is not None and display_change != 0)


def _sortable_table_script() -> str:
    return """  <script>
    document.querySelectorAll("table.sortable th button").forEach((button) => {
      button.addEventListener("click", () => {
        const table = button.closest("table");
        const tbody = table.querySelector("tbody");
        const columnIndex = Array.from(button.closest("tr").children).indexOf(button.closest("th"));
        const pairs = Array.from(tbody.querySelectorAll("tr:not(.drill-row)")).map((row) => ({
          row,
          detail: row.nextElementSibling && row.nextElementSibling.classList.contains("drill-row") ? row.nextElementSibling : null,
        }));
        const direction = button.dataset.direction === "asc" ? "desc" : "asc";
        table.querySelectorAll("th button").forEach((item) => item.dataset.direction = "");
        button.dataset.direction = direction;
        pairs.sort((left, right) => {
          const a = (left.row.children[columnIndex] || left.row).innerText.trim();
          const b = (right.row.children[columnIndex] || right.row).innerText.trim();
          const an = Number(a.replace(/,/g, ""));
          const bn = Number(b.replace(/,/g, ""));
          const result = Number.isFinite(an) && Number.isFinite(bn) ? an - bn : a.localeCompare(b);
          return direction === "asc" ? result : -result;
        });
        pairs.forEach((pair) => {
          tbody.appendChild(pair.row);
          if (pair.detail) {
            tbody.appendChild(pair.detail);
          }
        });
      });
    });
  </script>"""


def _drilldown_script() -> str:
    return """  <script>
    const isInteractive = (element) => Boolean(element.closest("a, button, input, select, textarea, summary"));
    const setRowExpanded = (row, expanded) => {
      const targetId = row.dataset.drillTarget;
      if (!targetId) {
        return;
      }
      const target = document.getElementById(targetId);
      const toggle = row.querySelector("[data-drill-toggle]");
      if (!target) {
        return;
      }
      target.hidden = !expanded;
      row.classList.toggle("is-expanded", expanded);
      if (toggle) {
        toggle.setAttribute("aria-expanded", expanded ? "true" : "false");
        toggle.textContent = expanded ? "-" : "+";
      }
      if (expanded) {
        const panel = target.querySelector("[data-drill-panel]");
        if (panel) {
          applyDrillFilters(panel);
        }
      }
    };
    const collapsePanel = (panel) => {
      const detailRow = panel.closest(".drill-row");
      if (detailRow) {
        const parent = document.querySelector(`[data-drill-target="${detailRow.id}"]`);
        if (parent) {
          setRowExpanded(parent, false);
          return;
        }
      }
      const details = panel.closest("details");
      if (details) {
        details.open = false;
      }
    };
    const productMatchesFilters = (product, panel) => {
      return Array.from(panel.querySelectorAll("[data-drill-filter]:checked")).every((input) => {
        const key = input.dataset.drillFilter;
        return product.dataset[key] === "true";
      });
    };
    const applyDrillFilters = (panel) => {
      const limit = Number(panel.querySelector(".drill-products")?.dataset.defaultLimit || "10");
      const showingAll = panel.dataset.showingAll === "true";
      const products = Array.from(panel.querySelectorAll(".drill-product"));
      const matched = products.filter((product) => productMatchesFilters(product, panel));
      products.forEach((product) => product.classList.add("is-hidden"));
      matched.forEach((product, index) => {
        product.classList.toggle("is-hidden", !showingAll && index >= limit);
      });
      const visibleCount = panel.querySelector("[data-visible-count]");
      const totalCount = panel.querySelector("[data-total-count]");
      if (visibleCount) {
        visibleCount.textContent = String(showingAll ? matched.length : Math.min(matched.length, limit));
      }
      if (totalCount) {
        totalCount.textContent = String(matched.length);
      }
      const showAllButton = panel.querySelector("[data-show-all-products]");
      if (showAllButton) {
        showAllButton.hidden = showingAll || matched.length <= limit;
      }
    };
    document.querySelectorAll("[data-drill-row]").forEach((row) => {
      row.addEventListener("click", (event) => {
        if (isInteractive(event.target)) {
          return;
        }
        const target = document.getElementById(row.dataset.drillTarget);
        setRowExpanded(row, !target || target.hidden);
      });
      const toggle = row.querySelector("[data-drill-toggle]");
      if (toggle) {
        toggle.addEventListener("click", (event) => {
          event.stopPropagation();
          const target = document.getElementById(row.dataset.drillTarget);
          setRowExpanded(row, !target || target.hidden);
        });
      }
    });
    document.querySelectorAll("[data-drill-panel]").forEach((panel) => {
      panel.querySelectorAll("[data-drill-filter]").forEach((input) => {
        input.addEventListener("change", () => {
          panel.dataset.showingAll = "false";
          applyDrillFilters(panel);
        });
      });
      const showAllButton = panel.querySelector("[data-show-all-products]");
      if (showAllButton) {
        showAllButton.addEventListener("click", () => {
          panel.dataset.showingAll = "true";
          applyDrillFilters(panel);
        });
      }
      const collapseButton = panel.querySelector("[data-collapse-drilldown]");
      if (collapseButton) {
        collapseButton.addEventListener("click", () => collapsePanel(panel));
      }
      applyDrillFilters(panel);
    });
    document.querySelectorAll("[data-copy-asin]").forEach((button) => {
      button.addEventListener("click", async () => {
        const asin = button.dataset.copyAsin || "";
        if (!asin) {
          return;
        }
        try {
          await navigator.clipboard.writeText(asin);
          button.textContent = "Copied";
          setTimeout(() => button.textContent = "Copy ASIN", 1200);
        } catch (error) {
          const fallback = document.createElement("textarea");
          fallback.value = asin;
          document.body.appendChild(fallback);
          fallback.select();
          document.execCommand("copy");
          fallback.remove();
        }
      });
    });
  </script>"""


def _card_interaction_script() -> str:
    return """  <script>
    const sortControl = document.querySelector("[data-card-sort]");
    const sortableContainers = Array.from(document.querySelectorAll("[data-sortable-cards]"));
    const button = document.querySelector(".load-more");
    const filterInputs = Array.from(document.querySelectorAll("[data-card-filter]"));
    const sellerFilter = document.querySelector("[data-product-seller-filter]");
    const nicheFilter = document.querySelector("[data-product-niche-filter]");
    const badgeFilter = document.querySelector("[data-product-badge-filter]");
    const sourceTypeFilter = document.querySelector("[data-product-source-type-filter]");
    const productTypeFilter = document.querySelector("[data-product-type-filter]");
    const daysFilter = document.querySelector("[data-product-days-filter]");
    const searchInput = document.querySelector("[data-product-search]");
    const bsrMinInput = document.querySelector("[data-product-bsr-min]");
    const bsrMaxInput = document.querySelector("[data-product-bsr-max]");
    const emptyMessage = document.querySelector("[data-filter-empty]");
    const params = new URLSearchParams(window.location.search);
    const requestedTrend = (params.get("trend") || "").trim().toLowerCase();
    let visible = 60;
    const directions = {
      winnerSignalScore: "desc",
      decisionScore: "desc",
      opportunityScore: "desc",
      bestMovers: "desc",
      largestRankImprovement: "desc",
      highestVelocity: "desc",
      topPercentile: "asc",
      subcategoryRank: "asc",
      categoryRank: "asc",
      reviewCount: "desc",
      rankChange: "desc",
      growthVelocity: "desc",
      newBreakoutScore: "desc",
      podScore: "desc",
    };
    const allCards = () => Array.from(document.querySelectorAll("[data-sortable-cards] > [data-card-index]"));
    const cardMatchesFilters = (card) => {
      const checked = filterInputs.filter((input) => input.checked);
      const togglesMatch = checked.every((input) => {
        const key = input.dataset.cardFilter;
        return card.dataset[key] === "true";
      });
      const sellerMatches = !sellerFilter || sellerFilter.value === "all" || card.dataset.sellerKey === sellerFilter.value;
      const nicheMatches = !nicheFilter || nicheFilter.value === "all" || card.dataset.nicheKey === nicheFilter.value;
      const badgeMatches = !badgeFilter || badgeFilter.value === "all" || (card.dataset.badges || "").split("|").includes(badgeFilter.value);
      const sourceTypeMatches = !sourceTypeFilter || sourceTypeFilter.value === "all" || card.dataset.sourceTypeKey === sourceTypeFilter.value;
      const productTypeMatches = !productTypeFilter || productTypeFilter.value === "all" || card.dataset.productTypeKey === productTypeFilter.value;
      const daysValue = daysFilter?.value || "all";
      const days = Number(card.dataset.daysTracked || "0");
      const daysMatches = daysValue === "all" || (daysValue === "30" ? days >= 30 : days > 0 && days <= Number(daysValue));
      const trendMatches = !requestedTrend || (card.dataset.trendKey || "").toLowerCase() === requestedTrend;
      const searchText = (searchInput?.value || "").trim().toLowerCase();
      const searchMatches = !searchText || (card.dataset.search || "").includes(searchText);
      const bsr = Number(card.dataset.bsrRank || "0");
      const minBsr = Number(bsrMinInput?.value || "0");
      const maxBsr = Number(bsrMaxInput?.value || "0");
      const bsrMatches = (!minBsr || (Number.isFinite(bsr) && bsr >= minBsr)) && (!maxBsr || (Number.isFinite(bsr) && bsr <= maxBsr));
      return togglesMatch && sellerMatches && nicheMatches && badgeMatches && sourceTypeMatches && productTypeMatches && daysMatches && trendMatches && searchMatches && bsrMatches;
    };
    const updateCards = () => {
      let matchedTotal = 0;
      const limit = button ? visible : Number.POSITIVE_INFINITY;
      allCards().forEach((card) => {
        const matched = cardMatchesFilters(card);
        const shouldShow = matched && matchedTotal < limit;
        if (matched) {
          matchedTotal += 1;
        }
        card.classList.toggle("is-hidden", !shouldShow);
      });
      if (button && visible >= matchedTotal) {
        button.style.display = "none";
      } else if (button) {
        button.style.display = "block";
      }
      if (emptyMessage) {
        emptyMessage.classList.toggle("is-hidden", matchedTotal !== 0);
      }
    };
    const numericValue = (card, key) => {
      const value = Number(card.dataset[key] || "0");
      return Number.isFinite(value) ? value : 0;
    };
    const percentileValue = (card) => {
      const value = Number(card.dataset.topPercentile || "999999");
      return Number.isFinite(value) ? value : 999999;
    };
    const sortContainer = (container, key) => {
      const direction = directions[key] || "desc";
      const items = Array.from(container.querySelectorAll(":scope > [data-card-index]"));
      items.sort((left, right) => {
        if (!key) {
          return numericValue(left, "cardIndex") - numericValue(right, "cardIndex");
        }
        if (key === "topPercentile") {
          const diff = percentileValue(left) - percentileValue(right);
          if (diff !== 0) {
            return direction === "asc" ? diff : -diff;
          }
          return numericValue(left, "cardIndex") - numericValue(right, "cardIndex");
        }
        const diff = numericValue(left, key) - numericValue(right, key);
        if (diff !== 0) {
          return direction === "asc" ? diff : -diff;
        }
        return numericValue(left, "cardIndex") - numericValue(right, "cardIndex");
      });
      items.forEach((item) => container.appendChild(item));
    };
    if (sortControl) {
      sortControl.addEventListener("change", () => {
        sortableContainers.forEach((container) => sortContainer(container, sortControl.value));
        visible = 60;
        updateCards();
      });
    }
    filterInputs.forEach((input) => {
      input.addEventListener("change", () => {
        visible = 60;
        updateCards();
      });
    });
    [sellerFilter, nicheFilter, badgeFilter, sourceTypeFilter, productTypeFilter, daysFilter, searchInput, bsrMinInput, bsrMaxInput].forEach((filter) => {
      if (filter) {
        filter.addEventListener("input", () => {
          visible = 60;
          updateCards();
        });
        filter.addEventListener("change", () => {
          visible = 60;
          updateCards();
        });
      }
    });
    if (button) {
      button.addEventListener("click", () => {
        visible += Number(button.dataset.cardStep || 40);
        updateCards();
      });
    }
    const requestedBadge = params.get("badge");
    if (badgeFilter && requestedBadge) {
      const key = requestedBadge.trim().toLowerCase();
      const option = Array.from(badgeFilter.options).find((item) => item.value === key || item.textContent.trim().toLowerCase() === key);
      if (option) {
        badgeFilter.value = option.value;
      }
    }
    const requestedSignal = (params.get("signal") || requestedBadge || "").trim().toLowerCase().replace(/\\s+/g, "-");
    if (requestedSignal) {
      filterInputs.forEach((input) => {
        const key = (input.dataset.cardFilter || "").replace(/[A-Z]/g, (char) => "-" + char.toLowerCase()).replace(/^-/, "");
        if (key === requestedSignal) {
          input.checked = true;
        }
      });
    }
    updateCards();
    document.querySelectorAll("[data-open-modal]").forEach((button) => {
      button.addEventListener("click", () => {
        const modal = document.getElementById(button.dataset.openModal || "");
        if (!modal) {
          return;
        }
        if (typeof modal.showModal === "function") {
          modal.showModal();
        } else {
          modal.setAttribute("open", "");
        }
      });
    });
    document.querySelectorAll("[data-close-modal]").forEach((button) => {
      button.addEventListener("click", () => {
        const modal = button.closest("dialog");
        if (modal && typeof modal.close === "function") {
          modal.close();
        } else if (modal) {
          modal.removeAttribute("open");
        }
      });
    });
  </script>"""


def _niche_filter_script() -> str:
    return """  <script>
    const nicheFilter = document.querySelector("[data-niche-filter]");
    const applyNicheFilter = () => {
      const value = nicheFilter ? nicheFilter.value : "all";
      document.querySelectorAll("[data-niche-group]").forEach((item) => {
        const visible = value === "all" || item.dataset.nicheGroup === value;
        item.classList.toggle("is-hidden", !visible);
      });
    };
    if (nicheFilter) {
      nicheFilter.addEventListener("change", applyNicheFilter);
      applyNicheFilter();
    }
  </script>"""


def _database_script() -> str:
    return """  <script>
    const databaseSearch = document.querySelector("[data-database-search]");
    const databaseBadgeFilter = document.querySelector("[data-database-badge-filter]");
    const databaseSellerFilter = document.querySelector("[data-database-seller-filter]");
    const databaseNicheFilter = document.querySelector("[data-database-niche-filter]");
    const databaseEmpty = document.querySelector("[data-filter-empty]");
    const databaseRows = () => Array.from(document.querySelectorAll("[data-database-row]"));
    const databaseRowMatches = (row) => {
      const searchText = (databaseSearch?.value || "").trim().toLowerCase();
      const searchMatches = !searchText || (row.dataset.search || "").includes(searchText);
      const badgeMatches = !databaseBadgeFilter || databaseBadgeFilter.value === "all" || (row.dataset.badges || "").split("|").includes(databaseBadgeFilter.value);
      const sellerMatches = !databaseSellerFilter || databaseSellerFilter.value === "all" || row.dataset.sellerKey === databaseSellerFilter.value;
      const nicheMatches = !databaseNicheFilter || databaseNicheFilter.value === "all" || row.dataset.nicheKey === databaseNicheFilter.value;
      return searchMatches && badgeMatches && sellerMatches && nicheMatches;
    };
    const applyDatabaseFilters = () => {
      let visibleRows = 0;
      databaseRows().forEach((row) => {
        const visible = databaseRowMatches(row);
        row.classList.toggle("is-hidden", !visible);
        if (visible) {
          visibleRows += 1;
        }
      });
      if (databaseEmpty) {
        databaseEmpty.classList.toggle("is-hidden", visibleRows !== 0);
      }
    };
    [databaseSearch, databaseBadgeFilter, databaseSellerFilter, databaseNicheFilter].forEach((control) => {
      if (!control) {
        return;
      }
      control.addEventListener("input", applyDatabaseFilters);
      control.addEventListener("change", applyDatabaseFilters);
    });
    document.querySelector("[data-export-database]")?.addEventListener("click", () => {
      const table = document.querySelector("[data-database-table]");
      if (!table) {
        return;
      }
      const rows = [Array.from(table.querySelectorAll("thead th")).map((cell) => cell.innerText.trim())];
      databaseRows().filter((row) => !row.classList.contains("is-hidden")).forEach((row) => {
        rows.push(Array.from(row.children).map((cell) => cell.innerText.trim()));
      });
      const csv = rows.map((row) => row.map((value) => `"${value.replace(/"/g, '""')}"`).join(",")).join("\\n");
      const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "amazon-market-spy-products.csv";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    });
    applyDatabaseFilters();
  </script>"""


def _to_int(value: str) -> int | None:
    try:
        return int(float(str(value or "").replace(",", "")))
    except (TypeError, ValueError):
        return None


def _to_float(value: str) -> float | None:
    try:
        return float(str(value or "").replace(",", ""))
    except (TypeError, ValueError):
        return None
