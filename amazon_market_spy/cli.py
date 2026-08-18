from __future__ import annotations

import argparse
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path

from . import __version__
from .artifacts import write_lark_opportunity_artifacts
from .category_rank import (
    CATEGORY_RANK_FIELDS,
    category_rank_cache_from_rows,
    ensure_category_rank_fields,
    extract_bsr_from_product_page,
    merge_category_rank_fields,
)
from .dashboard_v2 import generate_dashboard_v2
from .dashboard_v3 import generate_dashboard_v3
from .evidence_calibration import calibrate_evidence
from .evidence_review_analysis import analyze_evidence_reviews
from .evidence import EVIDENCE_FIELDS, PRODUCT_EVIDENCE_FIELDS
from .excel import write_workbook
from .fetch import (
    BotCheckError,
    FetchedPage,
    FetchError,
    PlaywrightFetcher,
    error_screenshot_path,
    extract_amazon_reported_total_text,
    parse_amazon_reported_total,
    polite_sleep,
    save_html,
    screenshot_path,
    set_amazon_delivery_location,
)
from .models import ScanResult, Source
from .notifications import (
    DEFAULT_REPORT_URL,
    LARK_DEFAULT_CARD_PRODUCT_LIMIT,
    LarkNotificationError,
    build_lark_interactive_card_payloads,
    build_lark_notification_message,
    send_lark_interactive_cards,
    send_lark_message,
)
from .parser import parse_amazon_search_results
from .niche import classify_niche, ensure_niche_fields
from .pod import classify_pod_row, ensure_pod_fields
from .product_details import (
    ensure_detail_fix_fields,
    extract_detail_page_fields,
    is_valid_product_title,
)
from .publish import DEFAULT_REPO_URL, DEFAULT_SITE_URL, PublishError, publish_report
from .reporting import (
    CHANGE_FIELDS,
    DISPLAY_RANK_FIELDS,
    ERROR_FIELDS,
    EXECUTIVE_SUMMARY_FIELDS,
    HISTORICAL_COMPARISON_FIELDS,
    LARK_TREND_ALERT_FIELDS,
    NICHE_INTELLIGENCE_FIELDS,
    PRODUCT_FIELDS,
    RANK_TREND_FIELDS,
    RANK_AUDIT_FIELDS,
    RESEARCH_SCORE_FIELDS,
    SELLER_INTELLIGENCE_FIELDS,
    SUMMARY_FIELDS,
    SOURCE_TREND_FIELDS,
    TREND_ALERT_FIELDS,
    build_executive_summary,
    build_product_history_rows,
    build_rank_trends,
    build_lark_trend_alerts,
    build_master_snapshot,
    build_niche_intelligence,
    build_seller_intelligence,
    build_historical_comparison,
    build_source_trends,
    build_trend_alerts,
    compare_snapshots,
    filter_by_classification,
    normalize_source_identity_rows,
    previous_snapshot,
    read_csv,
    snapshot_paths,
    summarize_sources,
    write_csv,
)
from .source_identity import SOURCE_HISTORY_FIELDS, source_history_key
from .sources import read_sources
from .utils import ensure_parent, is_asin, isoformat_utc, now_utc, slugify, timestamp_for_filename


DEFAULT_SOURCE_CANDIDATES = [
    Path("input/links.csv"),
    Path("input/sources.csv"),
    Path("../amazon_market_spyinput/links.csv.txt"),
]
DEFAULT_SNAPSHOT_DIR = Path("data/snapshots")
DEFAULT_MASTER_SNAPSHOT_PATH = Path("data/master_snapshot.csv")
DEFAULT_MAX_DETAIL_PAGES = 100
DEFAULT_MAX_DETAIL_FIXES = 300
SELLER_PREVIEW_PRODUCT_LIMIT = 15
DEFAULT_DETAIL_DELAY_SECONDS = 3.0
DEFAULT_DETAIL_TIMEOUT_SECONDS = 30
DEFAULT_SELLER_MAX_PAGES = 3
DEFAULT_BEST_SELLER_MAX_PAGES = 2
DEFAULT_NEW_RELEASE_MAX_PAGES = 2
SOURCE_TYPE_PRODUCTS_PER_PAGE = {
    "seller": 16,
    "best_seller": 50,
    "new_release": 50,
}
RANKING_PAGINATED_SOURCE_TYPES = {"best_seller", "new_release"}
BSR_REFRESH_FIELDS = (
    "bsr_rank",
    "bsr_category",
    "category_ranks_raw",
    "raw_bsr_block",
    "primary_bsr_rank",
    "primary_bsr_category",
    "sub_bsr_rank",
    "sub_bsr_category",
    "all_bsr_ranks",
    "subcategory_rank_score",
    "rank_extracted_at",
    "rank_source_url",
    "rank_page_status",
    "rank_parse_method",
    "rank_parse_confidence",
    "rank_parse_warning",
    "accordion_found",
    "accordion_expanded",
    "bsr_visible_after_expand",
)
DETAIL_CACHE_FILENAME = "detail_cache.csv"
DETAIL_CACHE_FIELDS = [
    "asin",
    "title",
    "image_url",
    *CATEGORY_RANK_FIELDS,
    "review_count",
    "review_rating",
    "title_fixed",
    "image_fixed",
    "detail_fixed_at",
]
DEBUG_BSR_ASINS = {"B0GVJX7MWC"}
SOURCE_SCAN_REPORT_FIELDS = [
    "source_name",
    "source_type",
    "raw_total_text",
    "max_pages",
    "expected_products",
    "expected_top_products",
    "collected_products",
    "top_page_coverage",
    "full_coverage",
    "status",
    "pages_scanned",
    "next_clicks",
    "duplicates",
    "filtered",
    "elapsed_seconds",
    "final_url",
    "stop_reason",
]
BSR_DEBUG_FIELDS = (
    "bsr_rank",
    "bsr_category",
    "primary_bsr_rank",
    "primary_bsr_category",
    "sub_bsr_rank",
    "sub_bsr_category",
    "category_ranks_raw",
    "raw_bsr_block",
    "all_bsr_ranks",
    "rank_extracted_at",
    "rank_parse_method",
    "rank_parse_confidence",
)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="amazon-market-spy",
        description="Track ASIN-level listings from Amazon seller, category, and ranking pages.",
    )
    parser.add_argument("--version", action="version", version=f"amazon-market-spy {__version__}")

    subparsers = parser.add_subparsers(dest="command")
    subparsers.required = True

    scan = subparsers.add_parser("scan", help="Fetch/parse sources and write market CSVs.")
    add_source_args(scan)
    scan.add_argument("--output", default="output", help="Output directory. Default: output")
    scan.add_argument(
        "--snapshot-dir",
        default=str(DEFAULT_SNAPSHOT_DIR),
        help="Directory for daily snapshot CSVs. Default: data/snapshots",
    )
    scan.add_argument(
        "--master-snapshot",
        default=str(DEFAULT_MASTER_SNAPSHOT_PATH),
        help="Combined CSV rebuilt from all daily snapshots. Default: data/master_snapshot.csv",
    )
    scan.add_argument("--timeout", type=int, default=30, help="Playwright page timeout in seconds. Default: 30")
    scan.add_argument("--retries", type=int, default=2, help="Retries per live URL after the first attempt. Default: 2")
    scan.add_argument("--delay", type=float, default=3.0, help="Delay between live fetches. Default: 3.0")
    scan.add_argument("--user-agent", default=None, help="Custom HTTP User-Agent.")
    scan.add_argument("--zipcode", default="10001", help="Amazon delivery ZIP code. Default: 10001")
    scan.add_argument(
        "--marketplace-domain",
        default="https://www.amazon.com",
        help="Amazon marketplace domain used to set delivery location. Default: https://www.amazon.com",
    )
    scan.add_argument("--headful", action="store_true", help="Show the Chromium browser instead of running headless.")
    scan.add_argument(
        "--browser-channel",
        default="chrome",
        help="Installed browser channel for Playwright, for example chrome or msedge. Default: chrome",
    )
    scan.add_argument("--browser-executable", default=None, help="Explicit browser executable path for Playwright.")
    scan.add_argument(
        "--wait-until",
        default="domcontentloaded",
        choices=["commit", "domcontentloaded", "load", "networkidle"],
        help="Playwright page.goto wait condition. Default: domcontentloaded",
    )
    scan.add_argument(
        "--ready-timeout",
        type=int,
        default=15,
        help="Seconds to wait for Amazon product/listing selectors after navigation. Default: 15",
    )
    scan.add_argument("--screenshot-dir", default="screenshots", help="Directory for Playwright screenshots.")
    scan.add_argument("--no-screenshots", action="store_true", help="Do not save Playwright screenshots.")
    scan.add_argument("--no-error-screenshots", action="store_true", help="Do not save screenshots when Playwright visits fail.")
    scan.add_argument("--html-dir", default=None, help="Directory of saved HTML files to parse before fetching.")
    scan.add_argument("--offline", action="store_true", help="Parse only saved HTML files; do not fetch.")
    scan.add_argument("--no-save-html", action="store_true", help="Do not save fetched HTML pages.")
    scan.add_argument("--limit-sources", type=int, default=None, help="Scan only the first N sources after sorting.")
    scan.add_argument("--max-products", type=int, default=None, help="Keep only the first N products per source.")
    scan.add_argument("--scroll", action="store_true", help="Auto-scroll live pages before extracting products.")
    scan.add_argument("--max-scrolls", type=int, default=8, help="Maximum scroll attempts per live page. Default: 8")
    scan.add_argument("--scroll-wait-ms", type=int, default=1500, help="Milliseconds to wait after each scroll. Default: 1500")
    scan.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Global maximum Amazon result pages per source. Source-type defaults apply when omitted.",
    )
    scan.add_argument(
        "--seller-max-pages",
        type=int,
        default=None,
        help=f"Maximum pages for seller sources. Default: {DEFAULT_SELLER_MAX_PAGES}",
    )
    scan.add_argument(
        "--best-seller-max-pages",
        type=int,
        default=None,
        help=f"Maximum pages for best_seller sources. Default: {DEFAULT_BEST_SELLER_MAX_PAGES}",
    )
    scan.add_argument(
        "--new-release-max-pages",
        type=int,
        default=None,
        help=f"Maximum pages for new_release sources. Default: {DEFAULT_NEW_RELEASE_MAX_PAGES}",
    )
    scan.add_argument(
        "--scan-report-only",
        action="store_true",
        help="Only write output/source_scan_report.csv; skip product trend and HTML report generation.",
    )
    scan.add_argument(
        "--resume-scan-report",
        action="store_true",
        help="With --scan-report-only, keep existing source_scan_report.csv rows and scan only missing sources.",
    )
    scan.add_argument(
        "--block-assets",
        action="store_true",
        help="Block images, media, fonts, and stylesheets during Playwright source-page fetches.",
    )
    scan.add_argument("--include-non-pod", action="store_true", help="Include non-POD physical products in opportunity reports.")
    scan.add_argument(
        "--fetch-category-rank",
        action="store_true",
        help="Visit detail pages for top opportunity products and extract Amazon BSR fields.",
    )
    scan.add_argument(
        "--max-detail-pages",
        type=int,
        default=DEFAULT_MAX_DETAIL_PAGES,
        help=f"Maximum product detail pages to visit for Amazon BSR extraction. Default: {DEFAULT_MAX_DETAIL_PAGES}",
    )
    scan.add_argument(
        "--fix-missing-details",
        action="store_true",
        help="Fix invalid listing titles or missing images from product detail pages beyond automatic top-opportunity fixes.",
    )
    scan.add_argument(
        "--fix-new-products",
        action="store_true",
        help="Prioritize new ASINs for title/image/BSR detail enrichment.",
    )
    scan.add_argument(
        "--refresh-bsr",
        action="store_true",
        help="Force detail-page BSR refresh for detail candidates even when existing BSR fields are populated.",
    )
    scan.add_argument(
        "--skip-fixed-details",
        dest="skip_fixed_details",
        action="store_true",
        default=True,
        help="Skip product detail pages when output/detail_cache.csv already has valid title, image, and high-confidence BSR. Default: enabled.",
    )
    scan.add_argument(
        "--no-skip-fixed-details",
        dest="skip_fixed_details",
        action="store_false",
        help="Disable detail-cache skipping and evaluate/fetch detail candidates normally.",
    )
    scan.add_argument(
        "--refresh-all-details",
        action="store_true",
        help="Fetch detail pages for all detail candidates, ignoring completed detail-cache entries.",
    )
    scan.add_argument(
        "--max-detail-fixes",
        type=int,
        default=DEFAULT_MAX_DETAIL_FIXES,
        help=f"Maximum detail pages to visit for title/image fixes. Default: {DEFAULT_MAX_DETAIL_FIXES}",
    )
    scan.add_argument(
        "--detail-timeout",
        type=int,
        default=DEFAULT_DETAIL_TIMEOUT_SECONDS,
        help=f"Seconds to wait for product detail title/image selectors. Default: {DEFAULT_DETAIL_TIMEOUT_SECONDS}",
    )
    scan.set_defaults(func=run_scan)

    validate = subparsers.add_parser("validate-sources", help="Validate and summarize the source CSV.")
    add_source_args(validate)
    validate.set_defaults(func=run_validate_sources)

    trend = subparsers.add_parser("trend", help="Regenerate trend CSVs from existing snapshots.")
    trend.add_argument("--output", default="output", help="Output directory for trend reports. Default: output")
    trend.add_argument(
        "--snapshot-dir",
        default=str(DEFAULT_SNAPSHOT_DIR),
        help="Directory containing daily snapshots. Default: data/snapshots",
    )
    trend.add_argument(
        "--master-snapshot",
        default=str(DEFAULT_MASTER_SNAPSHOT_PATH),
        help="Combined CSV rebuilt from all daily snapshots. Default: data/master_snapshot.csv",
    )
    add_source_args(trend)
    trend.add_argument("--include-non-pod", action="store_true", help="Include non-POD physical products in opportunity reports.")
    trend.add_argument(
        "--fetch-category-rank",
        action="store_true",
        help="Visit detail pages for top opportunity products and extract Amazon BSR fields.",
    )
    trend.add_argument(
        "--max-detail-pages",
        type=int,
        default=DEFAULT_MAX_DETAIL_PAGES,
        help=f"Maximum product detail pages to visit for Amazon BSR extraction. Default: {DEFAULT_MAX_DETAIL_PAGES}",
    )
    trend.add_argument(
        "--fix-missing-details",
        action="store_true",
        help="Fix invalid listing titles or missing images from product detail pages.",
    )
    trend.add_argument(
        "--fix-new-products",
        action="store_true",
        help="Prioritize new ASINs for title/image/BSR detail enrichment.",
    )
    trend.add_argument(
        "--refresh-bsr",
        action="store_true",
        help="Force detail-page BSR refresh for detail candidates even when existing BSR fields are populated.",
    )
    trend.add_argument(
        "--skip-fixed-details",
        dest="skip_fixed_details",
        action="store_true",
        default=True,
        help="Skip product detail pages when output/detail_cache.csv already has valid title, image, and high-confidence BSR. Default: enabled.",
    )
    trend.add_argument(
        "--no-skip-fixed-details",
        dest="skip_fixed_details",
        action="store_false",
        help="Disable detail-cache skipping and evaluate/fetch detail candidates normally.",
    )
    trend.add_argument(
        "--refresh-all-details",
        action="store_true",
        help="Fetch detail pages for all detail candidates, ignoring completed detail-cache entries.",
    )
    trend.add_argument(
        "--max-detail-fixes",
        type=int,
        default=DEFAULT_MAX_DETAIL_FIXES,
        help=f"Maximum detail pages to visit for title/image fixes. Default: {DEFAULT_MAX_DETAIL_FIXES}",
    )
    trend.add_argument(
        "--detail-timeout",
        type=int,
        default=DEFAULT_DETAIL_TIMEOUT_SECONDS,
        help=f"Seconds to wait for product detail title/image selectors. Default: {DEFAULT_DETAIL_TIMEOUT_SECONDS}",
    )
    trend.set_defaults(func=run_trend)

    dashboard_v2 = subparsers.add_parser(
        "generate-dashboard-v2",
        help="Generate the Dashboard V2 static workspace from presentation data.",
    )
    dashboard_v2.add_argument(
        "--output",
        default="output/v2",
        help="Output directory for Dashboard V2 pages. Default: output/v2",
    )
    dashboard_v2.set_defaults(func=run_generate_dashboard_v2)

    dashboard_v3 = subparsers.add_parser(
        "generate-dashboard-v3",
        help="Generate the Dashboard V3 foundation shell.",
    )
    dashboard_v3.add_argument(
        "--output",
        default="output/v3",
        help="Output directory for Dashboard V3 pages. Default: output/v3",
    )
    dashboard_v3.set_defaults(func=run_generate_dashboard_v3)

    calibrate = subparsers.add_parser(
        "calibrate-evidence",
        help="Generate source-specific evidence calibration CSVs and an offline HTML report.",
    )
    calibrate.add_argument("--output", default="output", help="Output directory for calibration reports. Default: output")
    calibrate.add_argument(
        "--comparison",
        default=None,
        help="Source-aware historical comparison CSV. Default: <output>/historical_comparison.csv",
    )
    calibrate.set_defaults(func=run_calibrate_evidence)

    analyze_reviews = subparsers.add_parser(
        "analyze-evidence-reviews",
        help="Analyze completed evidence calibration review labels and recommend threshold actions for approval.",
    )
    analyze_reviews.add_argument(
        "--review-file",
        default="output/evidence_calibration_review.csv",
        help="Completed human-review calibration CSV. Default: output/evidence_calibration_review.csv",
    )
    analyze_reviews.add_argument("--output", default="output", help="Output directory for review analysis. Default: output")
    analyze_reviews.add_argument(
        "--summary",
        default=None,
        help="Optional evidence calibration summary CSV. Default: <output>/evidence_calibration_summary.csv",
    )
    analyze_reviews.add_argument(
        "--threshold-simulation",
        default=None,
        help="Optional evidence threshold simulation CSV. Default: <output>/evidence_threshold_simulation.csv",
    )
    analyze_reviews.add_argument(
        "--comparison",
        default=None,
        help="Optional source-aware historical comparison CSV for rebuilding threshold simulations when needed.",
    )
    analyze_reviews.set_defaults(func=run_analyze_evidence_reviews)

    audit_rank = subparsers.add_parser("audit-rank", help="Fetch one Amazon product page and audit parsed BSR fields.")
    audit_rank.add_argument("--asin", required=True, help="Amazon ASIN to label debug artifacts.")
    audit_rank.add_argument("--url", required=True, help="Amazon product URL to inspect.")
    audit_rank.add_argument("--headful", action="store_true", help="Show the Chromium browser instead of running headless.")
    audit_rank.add_argument("--timeout", type=int, default=30, help="Playwright page timeout in seconds. Default: 30")
    audit_rank.add_argument(
        "--detail-timeout",
        type=int,
        default=DEFAULT_DETAIL_TIMEOUT_SECONDS,
        help=f"Seconds to wait for product detail rank sections. Default: {DEFAULT_DETAIL_TIMEOUT_SECONDS}",
    )
    audit_rank.add_argument(
        "--browser-channel",
        default="chrome",
        help="Installed browser channel for Playwright, for example chrome or msedge. Default: chrome",
    )
    audit_rank.add_argument("--browser-executable", default=None, help="Explicit browser executable path for Playwright.")
    audit_rank.add_argument(
        "--wait-until",
        default="domcontentloaded",
        choices=["commit", "domcontentloaded", "load", "networkidle"],
        help="Playwright page.goto wait condition. Default: domcontentloaded",
    )
    audit_rank.set_defaults(func=run_audit_rank)

    repair_asin = subparsers.add_parser("repair-asin", help="Refresh one ASIN BSR and patch existing output CSVs.")
    add_source_args(repair_asin)
    repair_asin.add_argument("--asin", required=True, help="Amazon ASIN to repair.")
    repair_asin.add_argument("--url", required=True, help="Amazon product URL to fetch.")
    repair_asin.add_argument("--output", default="output", help="Output directory. Default: output")
    repair_asin.add_argument(
        "--snapshot-dir",
        default=str(DEFAULT_SNAPSHOT_DIR),
        help="Directory containing daily snapshots. Default: data/snapshots",
    )
    repair_asin.add_argument(
        "--master-snapshot",
        default=str(DEFAULT_MASTER_SNAPSHOT_PATH),
        help="Combined CSV rebuilt from all daily snapshots. Default: data/master_snapshot.csv",
    )
    repair_asin.add_argument("--include-non-pod", action="store_true", help="Include non-POD physical products in rebuilt reports.")
    repair_asin.add_argument("--headful", action="store_true", help="Show the Chromium browser instead of running headless.")
    repair_asin.add_argument("--timeout", type=int, default=30, help="Playwright page timeout in seconds. Default: 30")
    repair_asin.add_argument(
        "--detail-timeout",
        type=int,
        default=DEFAULT_DETAIL_TIMEOUT_SECONDS,
        help=f"Seconds to wait for product detail rank sections. Default: {DEFAULT_DETAIL_TIMEOUT_SECONDS}",
    )
    repair_asin.add_argument(
        "--browser-channel",
        default="chrome",
        help="Installed browser channel for Playwright, for example chrome or msedge. Default: chrome",
    )
    repair_asin.add_argument("--browser-executable", default=None, help="Explicit browser executable path for Playwright.")
    repair_asin.add_argument(
        "--wait-until",
        default="domcontentloaded",
        choices=["commit", "domcontentloaded", "load", "networkidle"],
        help="Playwright page.goto wait condition. Default: domcontentloaded",
    )
    repair_asin.set_defaults(func=run_repair_asin)

    repair_bsr = subparsers.add_parser("repair-bsr", help="Batch-refresh stale or missing BSR for important ASINs.")
    add_source_args(repair_bsr)
    repair_bsr.add_argument("--output", default="output", help="Output directory containing latest_products.csv. Default: output")
    repair_bsr.add_argument(
        "--snapshot-dir",
        default=str(DEFAULT_SNAPSHOT_DIR),
        help="Directory containing daily snapshots. Default: data/snapshots",
    )
    repair_bsr.add_argument(
        "--master-snapshot",
        default=str(DEFAULT_MASTER_SNAPSHOT_PATH),
        help="Combined CSV rebuilt from all daily snapshots. Default: data/master_snapshot.csv",
    )
    repair_bsr.add_argument("--limit", type=non_negative_int, default=300, help="Maximum ASINs to select for BSR refresh. Default: 300")
    repair_bsr.add_argument("--only-missing", action="store_true", help="Refresh only ASINs with missing BSR fields.")
    repair_bsr.add_argument("--force", action="store_true", help="Refresh selected ASINs even when BSR is already high-confidence and fresh today.")
    repair_bsr.add_argument("--min-score", type=int, default=None, help="Only consider ASINs with opportunity_score at or above this value.")
    repair_bsr.add_argument("--include-non-pod", action="store_true", help="Include non-POD physical products in rebuilt reports.")
    repair_bsr.add_argument("--headful", action="store_true", help="Show the Chromium browser instead of running headless.")
    repair_bsr.add_argument("--timeout", type=int, default=30, help="Playwright page timeout in seconds. Default: 30")
    repair_bsr.add_argument("--detail-timeout", type=int, default=60, help="Seconds to wait for product detail rank sections. Default: 60")
    repair_bsr.add_argument(
        "--browser-channel",
        default="chrome",
        help="Installed browser channel for Playwright, for example chrome or msedge. Default: chrome",
    )
    repair_bsr.add_argument("--browser-executable", default=None, help="Explicit browser executable path for Playwright.")
    repair_bsr.add_argument(
        "--wait-until",
        default="domcontentloaded",
        choices=["commit", "domcontentloaded", "load", "networkidle"],
        help="Playwright page.goto wait condition. Default: domcontentloaded",
    )
    repair_bsr.set_defaults(func=run_repair_bsr)

    notify_lark = subparsers.add_parser("notify-lark", help="Send the latest Lark trend summary to a custom bot webhook.")
    notify_lark.add_argument("--webhook", default=None, help="Lark custom bot webhook URL. Defaults to LARK_WEBHOOK_URL.")
    notify_lark.add_argument("--output", default="output", help="Output directory containing Lark CSVs. Default: output")
    notify_lark.add_argument("--report-url", default=None, help=f"Live report URL. Defaults to REPORT_URL or {DEFAULT_REPORT_URL}")
    notify_lark.add_argument("--include-local-path", action="store_true", help="Include the local dashboard index.html path in the message.")
    notify_lark.add_argument("--card", action="store_true", help="Send Lark interactive summary and product cards instead of a single text message.")
    notify_lark.add_argument(
        "--top-products",
        type=non_negative_int,
        default=LARK_DEFAULT_CARD_PRODUCT_LIMIT,
        help=f"Number of product opportunity cards to send with --card. Default: {LARK_DEFAULT_CARD_PRODUCT_LIMIT}",
    )
    notify_lark.set_defaults(func=run_notify_lark)

    publish_report_parser = subparsers.add_parser("publish-report", help="Publish HTML reports to GitHub Pages.")
    publish_report_parser.add_argument("--output", default="output", help="Output directory containing HTML reports. Default: output")
    publish_report_parser.add_argument("--repo-url", default=DEFAULT_REPO_URL, help=f"Git remote URL. Default: {DEFAULT_REPO_URL}")
    publish_report_parser.add_argument("--site-url", default=DEFAULT_SITE_URL, help=f"Published site URL. Default: {DEFAULT_SITE_URL}")
    publish_report_parser.set_defaults(func=run_publish_report)

    return parser


def add_source_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--sources", default=None, help="Source CSV path.")
    parser.add_argument("--include-inactive", action="store_true", help="Include rows where active is not yes/true/1.")


def non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be 0 or greater")
    return parsed


def source_page_limit(source: Source, args: argparse.Namespace) -> int:
    return source_type_page_limit(source.source_type, args)


def source_scroll_enabled(source: Source, args: argparse.Namespace) -> bool:
    return bool(getattr(args, "scroll", False)) and _source_type_key(source.source_type) not in RANKING_PAGINATED_SOURCE_TYPES


def source_type_page_limit(source_type: str, args: argparse.Namespace) -> int:
    source_type_key = _source_type_key(source_type)
    source_specific_limits = {
        "seller": getattr(args, "seller_max_pages", None),
        "best_seller": getattr(args, "best_seller_max_pages", None),
        "new_release": getattr(args, "new_release_max_pages", None),
    }
    default_limits = {
        "seller": DEFAULT_SELLER_MAX_PAGES,
        "best_seller": DEFAULT_BEST_SELLER_MAX_PAGES,
        "new_release": DEFAULT_NEW_RELEASE_MAX_PAGES,
    }
    configured_limit = source_specific_limits.get(source_type_key)
    if configured_limit is None:
        configured_limit = getattr(args, "max_pages", None)
    if configured_limit is None:
        configured_limit = default_limits.get(source_type_key, 1)
    return max(1, int(configured_limit))


def _source_type_key(source_type: str) -> str:
    return (source_type or "").strip().lower().replace("-", "_").replace(" ", "_")


def _source_products_per_page(source_type: str) -> int:
    return SOURCE_TYPE_PRODUCTS_PER_PAGE.get(_source_type_key(source_type), 0)


def run_validate_sources(args: argparse.Namespace) -> int:
    source_path = resolve_sources_path(args.sources)
    sources = read_sources(source_path, include_inactive=args.include_inactive)
    print(f"Source file: {source_path}")
    print(f"Sources loaded: {len(sources)}")
    for source in sources:
        status = "active" if source.active else "inactive"
        print(f"{source.priority:>3}  {status:<8}  {source.source_type:<18}  {source.display_name}  {source.category}")
    return 0


def run_generate_dashboard_v2(args: argparse.Namespace) -> int:
    result = generate_dashboard_v2(Path(args.output))
    print(f"Dashboard V2 output directory: {result['output_dir']}")
    print(f"Dashboard V2 main page: {result['main_page']}")
    print("Dashboard V2 pages generated:")
    for page in result["pages"]:
        print(f"- {page['label']}: {page['path']}")
    return 0


def run_generate_dashboard_v3(args: argparse.Namespace) -> int:
    result = generate_dashboard_v3(Path(args.output))
    print(f"Dashboard V3 output directory: {result['output_dir']}")
    print(f"Dashboard V3 main page: {result['main_page']}")
    print("Dashboard V3 pages generated:")
    for page in result["pages"]:
        print(f"- {page['label']}: {page['path']}")
    aliases = result.get("aliases", [])
    if aliases:
        print("Dashboard V3 compatibility aliases generated:")
        for alias in aliases:
            print(f"- {alias['filename']} -> {alias['target']}: {alias['path']}")
    return 0


def run_calibrate_evidence(args: argparse.Namespace) -> int:
    result = calibrate_evidence(Path(args.output), Path(args.comparison) if args.comparison else None)
    print(f"Evidence calibration input: {result['comparison_path']}")
    print(f"Products analyzed: {result['product_count']}")
    print(f"Observations analyzed: {result['observation_count']}")
    print("Evidence calibration outputs:")
    for label, path in result["paths"].items():
        print(f"- {label}: {path}")
    return 0


def run_analyze_evidence_reviews(args: argparse.Namespace) -> int:
    result = analyze_evidence_reviews(
        review_file=Path(args.review_file),
        output_dir=Path(args.output),
        summary_file=Path(args.summary) if args.summary else None,
        threshold_file=Path(args.threshold_simulation) if args.threshold_simulation else None,
        comparison_file=Path(args.comparison) if args.comparison else None,
    )
    print(f"Evidence review input: {result['review_file']}")
    print(f"Review rows: {result['total_rows']}")
    print(f"Reviewed rows: {result['reviewed_rows']}")
    print(f"Unreviewed rows: {result['unreviewed_rows']}")
    print(f"Valid reviewed rows: {result['valid_reviewed_rows']}")
    print(f"Recommendation mode: {'diagnostic_only' if result['insufficient_review'] else 'recommendation_ready'}")
    print("Evidence review analysis outputs:")
    for label, path in result["paths"].items():
        print(f"- {label}: {path}")
    return 0


def run_trend(args: argparse.Namespace) -> int:
    output_dir = Path(args.output)
    snapshot_dir = Path(args.snapshot_dir)
    source_path = resolve_sources_path(getattr(args, "sources", None))
    sources = read_sources_if_available(source_path, include_inactive=getattr(args, "include_inactive", False))
    fetcher: PlaywrightFetcher | None = None
    try:
        if (
            getattr(args, "fetch_category_rank", False)
            or getattr(args, "fix_missing_details", False)
            or getattr(args, "fix_new_products", False)
            or getattr(args, "refresh_bsr", False)
            or getattr(args, "refresh_all_details", False)
        ):
            fetcher = PlaywrightFetcher()
            fetcher.__enter__()
        paths = write_trend_outputs(
            output_dir,
            snapshot_dir,
            sources,
            include_non_pod=getattr(args, "include_non_pod", False),
            category_rank_fetcher=fetcher,
            fetch_category_rank=getattr(args, "fetch_category_rank", False),
            max_detail_pages=getattr(args, "max_detail_pages", DEFAULT_MAX_DETAIL_PAGES),
            detail_fix_fetcher=fetcher,
            fix_missing_details=getattr(args, "fix_missing_details", False),
            fix_new_products=getattr(args, "fix_new_products", False),
            max_detail_fixes=getattr(args, "max_detail_fixes", DEFAULT_MAX_DETAIL_FIXES),
            auto_fix_opportunity_details=bool(fetcher),
            refresh_bsr=getattr(args, "refresh_bsr", False),
            skip_fixed_details=getattr(args, "skip_fixed_details", True),
            refresh_all_details=getattr(args, "refresh_all_details", False),
            detail_delay=DEFAULT_DETAIL_DELAY_SECONDS,
            detail_timeout=getattr(args, "detail_timeout", DEFAULT_DETAIL_TIMEOUT_SECONDS),
        )
    finally:
        if fetcher is not None:
            fetcher.close()
    master_path = write_master_snapshot(snapshot_dir, Path(args.master_snapshot))
    workbook_path = output_dir / "daily_market_spy_report.xlsx"
    latest_snapshot_path = snapshot_paths(snapshot_dir)[-1] if snapshot_paths(snapshot_dir) else None
    products = read_csv(latest_snapshot_path) if latest_snapshot_path else []
    historical_rows = build_historical_comparison(snapshot_dir, latest_snapshot_path, sources)
    write_daily_workbook(
        workbook_path=workbook_path,
        products=products,
        historical_rows=historical_rows,
        source_summaries=summarize_sources(products, []),
        errors=[],
        source_metadata=sources,
    )
    print(f"Rank trends: {paths['rank_trends']}")
    print(f"Rank audit: {paths['rank_audit']}")
    print(f"Product trends: {paths['product_trends']}")
    print(f"Trend alerts: {paths['trend_alerts']}")
    print(f"Lark trend alerts: {paths['lark_trend_alerts']}")
    print(f"Today dashboard: {paths['priority_board']}")
    print(f"Priority board CSV: {paths['priority_board_csv']}")
    print(f"Product Discovery: {paths['product_discovery']}")
    print(f"Competitor: {paths['competitor']}")
    print(f"Trend Explorer: {paths['trend_explorer']}")
    print(f"Product Detail: {paths['product_detail']}")
    print(f"Products compatibility page: {paths['products']}")
    print(f"Top winners compatibility page: {paths['top_winners']}")
    print(f"New breakouts compatibility page: {paths['new_breakouts']}")
    print(f"Fast movers compatibility page: {paths['fast_movers']}")
    print(f"New releases compatibility page: {paths['new_releases']}")
    print(f"Trends compatibility page: {paths['trends']}")
    print(f"Database compatibility page: {paths['database']}")
    print(f"Image gallery compatibility page: {paths['image_gallery']}")
    print(f"Top opportunities compatibility page: {paths['top_opportunities']}")
    print(f"All opportunities compatibility page: {paths['all_opportunities']}")
    print(f"New products compatibility page: {paths['new_products']}")
    print(f"Rising products compatibility page: {paths['rising_products']}")
    print(f"Seller intelligence compatibility page: {paths['seller_intelligence_page']}")
    print(f"Niche intelligence compatibility page: {paths['niche_intelligence_page']}")
    print(f"Source explorer compatibility page: {paths['source_explorer']}")
    print(f"Non-POD excluded: {paths['non_pod_excluded']}")
    print(f"Source trends: {paths['source_trends']}")
    print(f"Seller intelligence: {paths['seller_intelligence']}")
    print(f"Niche intelligence: {paths['niche_intelligence']}")
    print(f"Historical comparison: {paths['historical_comparison']}")
    print(f"Workbook: {workbook_path}")
    print(f"Master snapshot: {master_path}")
    return 0


def run_notify_lark(args: argparse.Namespace) -> int:
    output_dir = Path(args.output)
    webhook_url = (getattr(args, "webhook", None) or os.environ.get("LARK_WEBHOOK_URL", "")).strip()
    if not webhook_url:
        print("Warning: Lark webhook missing; skipping notification.")
        return 0

    report_url = (getattr(args, "report_url", None) or os.environ.get("REPORT_URL", "") or DEFAULT_REPORT_URL).strip()
    message = build_lark_notification_message(
        output_dir,
        report_url=report_url,
        include_local_path=getattr(args, "include_local_path", False),
    )
    if getattr(args, "card", False):
        payloads = build_lark_interactive_card_payloads(
            output_dir,
            report_url=report_url,
            include_local_path=getattr(args, "include_local_path", False),
            top_products=getattr(args, "top_products", LARK_DEFAULT_CARD_PRODUCT_LIMIT),
        )
        try:
            send_lark_interactive_cards(webhook_url, payloads)
        except LarkNotificationError as exc:
            print(f"Lark card notification failed: {exc}")
            try:
                send_lark_message(webhook_url, message)
            except LarkNotificationError as fallback_exc:
                print(f"Lark fallback notification failed: {fallback_exc}")
                return 1
            print("Lark notification sent as plain text fallback.")
            return 0

        print("Lark card notification sent.")
        return 0

    try:
        send_lark_message(webhook_url, message)
    except LarkNotificationError as exc:
        print(f"Lark notification failed: {exc}")
        return 1

    print("Lark notification sent.")
    return 0


def run_audit_rank(args: argparse.Namespace) -> int:
    asin = (getattr(args, "asin", "") or "").strip().upper()
    url = (getattr(args, "url", "") or "").strip()
    debug_dir = Path("debug_rank")
    output_dir = Path("output")
    safe_asin = slugify(asin, fallback="asin")
    html_path = debug_dir / f"{safe_asin}_rank.html"
    screenshot_path = debug_dir / f"{safe_asin}_rank.png"

    if not url:
        print("Error: --url is required.")
        return 2
    if asin and not is_asin(asin):
        print(f"Warning: {asin} does not look like a standard Amazon ASIN; continuing audit.")

    try:
        with PlaywrightFetcher(
            timeout=getattr(args, "timeout", 30),
            headless=not getattr(args, "headful", False),
            wait_until=getattr(args, "wait_until", "domcontentloaded"),
            browser_channel=getattr(args, "browser_channel", "chrome"),
            browser_executable=getattr(args, "browser_executable", None),
        ) as fetcher:
            result = fetcher.fetch_detail_page(
                url,
                timeout=getattr(args, "detail_timeout", DEFAULT_DETAIL_TIMEOUT_SECONDS),
                capture_screenshot=True,
            )
    except (BotCheckError, FetchError) as exc:
        print(f"Rank audit failed: {type(exc).__name__}: {exc}")
        return 1

    ensure_parent(html_path)
    html_path.write_text(result.html, encoding="utf-8", errors="replace")
    if result.screenshot:
        ensure_parent(screenshot_path)
        screenshot_path.write_bytes(result.screenshot)

    rank_fields = extract_bsr_from_product_page(
        result.html,
        source_url=result.url or url,
        page_status=result.status,
        diagnostics=_rank_diagnostics_from_detail_result(result),
    )
    row = {
        "asin": asin,
        "title": "",
        "product_url": url,
        "display_rank": "",
        "source_name": "",
        **rank_fields,
    }
    rank_audit_path = write_rank_audit(output_dir, [row])

    print("Rank audit:")
    print(f"ASIN: {asin or 'n/a'}")
    print(f"URL: {result.url or url}")
    print(f"Page status: {result.status}")
    if result.error:
        print(f"Page error: {result.error}")
    print(f"accordion_found: {_bool_text(getattr(result, 'accordion_found', False))}")
    print(f"accordion_expanded: {_bool_text(getattr(result, 'accordion_expanded', False))}")
    print(f"bsr_visible_after_expand: {_bool_text(getattr(result, 'bsr_visible_after_expand', False))}")
    print("raw_bsr_block:")
    print(rank_fields.get("raw_bsr_block", "") or "n/a")
    print(f"rank_parse_method: {rank_fields.get('rank_parse_method', '') or 'n/a'}")
    print(f"rank_parse_confidence: {rank_fields.get('rank_parse_confidence', '') or 'n/a'}")
    if rank_fields.get("rank_parse_warning", ""):
        print(f"rank_parse_warning: {rank_fields['rank_parse_warning']}")
    print("Parsed fields:")
    for field in (
        "primary_bsr_rank",
        "primary_bsr_category",
        "sub_bsr_rank",
        "sub_bsr_category",
        "rank_extracted_at",
    ):
        print(f"{field}: {rank_fields.get(field, '') or 'n/a'}")
    print(f"HTML: {html_path}")
    if result.screenshot:
        print(f"Screenshot: {screenshot_path}")
    print(f"Rank audit CSV: {rank_audit_path}")
    return 0


def run_repair_asin(args: argparse.Namespace) -> int:
    asin = (getattr(args, "asin", "") or "").strip().upper()
    url = (getattr(args, "url", "") or "").strip()
    output_dir = Path(getattr(args, "output", "output"))
    snapshot_dir = Path(getattr(args, "snapshot_dir", DEFAULT_SNAPSHOT_DIR))
    if not url:
        print("Error: --url is required.")
        return 2
    if not is_asin(asin):
        print(f"Error: {asin or 'blank'} does not look like a standard Amazon ASIN.")
        return 2

    try:
        with PlaywrightFetcher(
            timeout=getattr(args, "timeout", 30),
            headless=not getattr(args, "headful", False),
            wait_until=getattr(args, "wait_until", "domcontentloaded"),
            browser_channel=getattr(args, "browser_channel", "chrome"),
            browser_executable=getattr(args, "browser_executable", None),
        ) as fetcher:
            result = fetcher.fetch_detail_page(
                url,
                timeout=getattr(args, "detail_timeout", DEFAULT_DETAIL_TIMEOUT_SECONDS),
                capture_screenshot=True,
            )
    except (BotCheckError, FetchError) as exc:
        print(f"ASIN repair failed: {type(exc).__name__}: {exc}")
        return 1

    rank_fields = extract_bsr_from_product_page(
        result.html,
        source_url=result.url or url,
        page_status=result.status,
        diagnostics=_rank_diagnostics_from_detail_result(result),
    )
    detail_fields = extract_detail_page_fields(result.html)
    if not _is_successful_high_confidence_bsr(rank_fields):
        print(
            "ASIN repair did not overwrite BSR: "
            f"ASIN={asin} "
            f"primary_bsr_rank={rank_fields.get('primary_bsr_rank', '') or 'blank'} "
            f"sub_bsr_rank={rank_fields.get('sub_bsr_rank', '') or 'blank'} "
            f"rank_parse_confidence={rank_fields.get('rank_parse_confidence', '') or 'blank'}"
        )
        return 1

    repair_row = ensure_detail_fix_fields(ensure_category_rank_fields({
        "asin": asin,
        "product_url": url,
        "title": detail_fields.title,
        "image_url": detail_fields.image_url,
        "detail_page_status": result.status,
        "detail_title_found": "true" if detail_fields.title else "false",
        "detail_image_found": "true" if detail_fields.image_url else "false",
        "detail_bsr_found": "true",
        "detail_bsr_error": "",
        **rank_fields,
    }))
    _log_debug_bsr_state("after detail fetch", repair_row)

    detail_cache_path = output_dir / DETAIL_CACHE_FILENAME
    detail_cache = load_detail_cache(detail_cache_path)
    update_detail_cache_from_fixes(detail_cache_path, detail_cache, [repair_row], {asin: repair_row})
    updated_paths = repair_asin_output_csvs(output_dir, snapshot_dir, asin, repair_row)

    try:
        source_path = resolve_sources_path(getattr(args, "sources", None))
        sources = read_sources_if_available(source_path, include_inactive=getattr(args, "include_inactive", False))
        paths = write_trend_outputs(
            output_dir,
            snapshot_dir,
            sources,
            include_non_pod=getattr(args, "include_non_pod", False),
            detail_delay=0,
            detail_timeout=getattr(args, "detail_timeout", DEFAULT_DETAIL_TIMEOUT_SECONDS),
        )
        write_master_snapshot(snapshot_dir, Path(getattr(args, "master_snapshot", DEFAULT_MASTER_SNAPSHOT_PATH)))
        print(f"Reports rebuilt: {paths.get('priority_board', output_dir / 'priority_board.html')}")
    except (OSError, ValueError) as exc:
        print(f"Warning: CSV repair completed but report rebuild failed: {type(exc).__name__}: {exc}")

    print("ASIN repair complete:")
    print(f"ASIN: {asin}")
    print(f"primary_bsr_rank: {repair_row.get('primary_bsr_rank', '')}")
    print(f"primary_bsr_category: {repair_row.get('primary_bsr_category', '')}")
    print(f"sub_bsr_rank: {repair_row.get('sub_bsr_rank', '')}")
    print(f"sub_bsr_category: {repair_row.get('sub_bsr_category', '')}")
    print(f"rank_parse_method: {repair_row.get('rank_parse_method', '')}")
    print(f"rank_parse_confidence: {repair_row.get('rank_parse_confidence', '')}")
    print(f"Updated CSVs: {len(updated_paths)}")
    for path in updated_paths:
        print(f"  {path}")
    return 0


@dataclass
class BatchBsrRepairResult:
    selected_count: int
    refreshed_count: int
    failed_count: int
    skipped_fresh_count: int
    updated_paths: list[Path]
    examples: list[str]
    failures: list[str]


def run_repair_bsr(args: argparse.Namespace) -> int:
    output_dir = Path(getattr(args, "output", "output"))
    snapshot_dir = Path(getattr(args, "snapshot_dir", DEFAULT_SNAPSHOT_DIR))
    fetcher: PlaywrightFetcher | None = None
    try:
        fetcher = PlaywrightFetcher(
            timeout=getattr(args, "timeout", 30),
            headless=not getattr(args, "headful", False),
            wait_until=getattr(args, "wait_until", "domcontentloaded"),
            browser_channel=getattr(args, "browser_channel", "chrome"),
            browser_executable=getattr(args, "browser_executable", None),
        )
        fetcher.__enter__()
        result = repair_bsr_outputs(
            output_dir=output_dir,
            snapshot_dir=snapshot_dir,
            fetcher=fetcher,
            limit=getattr(args, "limit", 300),
            detail_timeout=getattr(args, "detail_timeout", 60),
            only_missing=getattr(args, "only_missing", False),
            force=getattr(args, "force", False),
            min_score=getattr(args, "min_score", None),
            detail_delay=DEFAULT_DETAIL_DELAY_SECONDS,
        )
    finally:
        if fetcher is not None:
            fetcher.close()

    _print_bsr_repair_summary(result)
    try:
        if snapshot_paths(snapshot_dir):
            source_path = resolve_sources_path(getattr(args, "sources", None))
            sources = read_sources_if_available(source_path, include_inactive=getattr(args, "include_inactive", False))
            paths = write_trend_outputs(
                output_dir,
                snapshot_dir,
                sources,
                include_non_pod=getattr(args, "include_non_pod", False),
                detail_delay=0,
                detail_timeout=getattr(args, "detail_timeout", DEFAULT_DETAIL_TIMEOUT_SECONDS),
            )
            write_master_snapshot(snapshot_dir, Path(getattr(args, "master_snapshot", DEFAULT_MASTER_SNAPSHOT_PATH)))
            print(f"Reports rebuilt: {paths.get('priority_board', output_dir / 'priority_board.html')}")
        else:
            print("No snapshot found for report rebuild. Run: python amazon_market_spy.py trend --output output")
    except (OSError, ValueError) as exc:
        print(f"Warning: CSV repair completed but report rebuild failed: {type(exc).__name__}: {exc}")
        print("Run: python amazon_market_spy.py trend --output output")
    return 0 if result.refreshed_count or result.skipped_fresh_count or result.selected_count == 0 else 1


def repair_bsr_outputs(
    *,
    output_dir: Path,
    snapshot_dir: Path,
    fetcher: PlaywrightFetcher,
    limit: int = 300,
    detail_timeout: int = 60,
    only_missing: bool = False,
    force: bool = False,
    min_score: int | None = None,
    detail_delay: float = 0,
    today: str | None = None,
) -> BatchBsrRepairResult:
    latest_path = output_dir / "latest_products.csv"
    products = read_csv(latest_path)
    if not products:
        print(f"BSR repair: no products found at {latest_path}")
        return BatchBsrRepairResult(0, 0, 0, 0, [], [], [])

    priority_asins, opportunity_scores = _bsr_repair_context(output_dir)
    selected, skipped_fresh = select_bsr_repair_candidates(
        products,
        priority_asins=priority_asins,
        opportunity_scores=opportunity_scores,
        limit=limit,
        only_missing=only_missing,
        force=force,
        min_score=min_score,
        today=today,
    )
    print(f"BSR repair ASINs selected: {len(selected)}")
    repairs_by_asin: dict[str, dict[str, str]] = {}
    examples: list[str] = []
    failures: list[str] = []

    for index, row in enumerate(selected, start=1):
        asin = _row_asin(row)
        url = row.get("product_url", "").strip() or f"https://www.amazon.com/dp/{asin}"
        old_primary = (row.get("primary_bsr_rank", "") or row.get("bsr_rank", "") or "").strip()
        old_sub = (row.get("sub_bsr_rank", "") or "").strip()
        try:
            html, status, error, source_url, diagnostics = _fetch_detail_page_for_rank(
                fetcher,
                url,
                detail_timeout=detail_timeout,
            )
            rank_fields = extract_bsr_from_product_page(
                html,
                source_url=source_url or url,
                page_status=status,
                diagnostics=diagnostics,
            )
        except (BotCheckError, FetchError, OSError, ValueError) as exc:
            failure = f"{asin}: {type(exc).__name__}: {exc}"
            failures.append(failure)
            print(f"BSR repair failed: {failure}")
        else:
            if _is_successful_high_confidence_bsr(rank_fields):
                repairs_by_asin[asin] = rank_fields
                new_primary = (rank_fields.get("primary_bsr_rank", "") or rank_fields.get("bsr_rank", "") or "").strip()
                new_sub = (rank_fields.get("sub_bsr_rank", "") or "").strip()
                example = f"{asin}: primary {old_primary or 'blank'} -> {new_primary or 'blank'}, sub {old_sub or 'blank'} -> {new_sub or 'blank'}"
                if len(examples) < 10:
                    examples.append(example)
                print(f"BSR repair refreshed: {example}")
            else:
                failure = (
                    f"{asin}: no high-confidence BSR "
                    f"(primary={rank_fields.get('primary_bsr_rank', '') or 'blank'}, "
                    f"sub={rank_fields.get('sub_bsr_rank', '') or 'blank'}, "
                    f"confidence={rank_fields.get('rank_parse_confidence', '') or 'blank'}, "
                    f"status={rank_fields.get('rank_page_status', '') or status or 'blank'}, "
                    f"error={error or 'blank'})"
                )
                failures.append(failure)
                print(f"BSR repair failed: {failure}")

        if detail_delay and index < len(selected):
            polite_sleep(detail_delay)

    updated_paths: list[Path] = []
    if repairs_by_asin:
        updated_paths = repair_bsr_output_csvs(output_dir, snapshot_dir, repairs_by_asin)
        _update_detail_cache_from_bsr_repairs(output_dir / DETAIL_CACHE_FILENAME, products, repairs_by_asin)

    return BatchBsrRepairResult(
        selected_count=len(selected),
        refreshed_count=len(repairs_by_asin),
        failed_count=len(failures),
        skipped_fresh_count=skipped_fresh,
        updated_paths=updated_paths,
        examples=examples,
        failures=failures,
    )


def _print_bsr_repair_summary(result: BatchBsrRepairResult) -> None:
    print("BSR repair summary:")
    print(f"ASINs selected: {result.selected_count}")
    print(f"Refreshed successfully: {result.refreshed_count}")
    print(f"Failed: {result.failed_count}")
    print(f"Skipped already high-confidence fresh: {result.skipped_fresh_count}")
    if result.examples:
        print("Old -> new rank examples:")
        for example in result.examples:
            print(f"  {example}")
    if result.failures:
        print("Failures:")
        for failure in result.failures[:10]:
            print(f"  {failure}")
    if result.updated_paths:
        print("Updated outputs:")
        for path in result.updated_paths:
            print(f"  {path}")


def repair_asin_output_csvs(
    output_dir: Path,
    snapshot_dir: Path,
    asin: str,
    repair_fields: dict[str, str],
) -> list[Path]:
    return repair_bsr_output_csvs(output_dir, snapshot_dir, {asin: repair_fields})


def repair_bsr_output_csvs(
    output_dir: Path,
    snapshot_dir: Path,
    repairs_by_asin: dict[str, dict[str, str]],
) -> list[Path]:
    latest_snapshot_path = snapshot_paths(snapshot_dir)[-1] if snapshot_paths(snapshot_dir) else None
    paths = [
        output_dir / "latest_products.csv",
        output_dir / "today_snapshot.csv",
        output_dir / "rank_audit.csv",
        output_dir / "historical_comparison.csv",
        output_dir / "product_trends.csv",
        output_dir / "rank_trends.csv",
        output_dir / "trend_alerts.csv",
        output_dir / "lark_trend_alerts.csv",
    ]
    if latest_snapshot_path is not None:
        paths.append(latest_snapshot_path)

    updated_paths: list[Path] = []
    for path in _unique_paths(paths):
        if _repair_bsr_rows_in_csv(path, repairs_by_asin):
            updated_paths.append(path)
    return updated_paths


def _repair_asin_rows_in_csv(path: Path, asin: str, repair_fields: dict[str, str]) -> bool:
    return _repair_bsr_rows_in_csv(path, {asin: repair_fields})


def _repair_bsr_rows_in_csv(path: Path, repairs_by_asin: dict[str, dict[str, str]]) -> bool:
    rows = read_csv(path)
    if not rows:
        return False
    fields = _csv_fields(path) or list(rows[0].keys())
    updated = False
    for row in rows:
        asin = _row_asin(row)
        repair_fields = repairs_by_asin.get(asin)
        if not repair_fields:
            continue
        if _apply_bsr_fields(row, repair_fields, asin=asin, overwrite=True):
            updated = True
        if _merge_repair_detail_fields(row, repair_fields):
            updated = True
    if updated:
        write_csv(path, rows, fields)
    return updated


def _merge_repair_detail_fields(row: dict[str, str], repair_fields: dict[str, str]) -> bool:
    changed = False
    title = (repair_fields.get("title", "") or "").strip()
    if title and is_valid_product_title(title) and _needs_title_fix(row):
        row["raw_title"] = row.get("raw_title", "") or row.get("title", "")
        row["title"] = title
        row["title_source"] = "detail_page"
        row["title_fixed"] = "true"
        changed = True
    image_url = (repair_fields.get("image_url", "") or "").strip()
    if image_url and _needs_image_fix(row):
        row["image_url"] = image_url
        row["image_source"] = "detail_page"
        row["image_fixed"] = "true"
        changed = True
    return changed


def _csv_fields(path: Path) -> list[str]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        import csv

        reader = csv.DictReader(handle)
        return list(reader.fieldnames or [])


def _is_successful_high_confidence_bsr(fields: dict[str, str]) -> bool:
    return (
        (fields.get("rank_parse_confidence", "") or "").strip().lower() == "high"
        and has_extracted_bsr(fields)
    )


def select_bsr_repair_candidates(
    products: list[dict[str, str]],
    *,
    priority_asins: set[str],
    opportunity_scores: dict[str, int],
    limit: int,
    only_missing: bool = False,
    force: bool = False,
    min_score: int | None = None,
    today: str | None = None,
) -> tuple[list[dict[str, str]], int]:
    if limit <= 0:
        return [], 0
    today = today or now_utc().date().isoformat()
    best_by_asin: dict[str, dict[str, str]] = {}
    for source_row in products:
        row = ensure_category_rank_fields(dict(source_row))
        asin = _row_asin(row)
        if not is_asin(asin):
            continue
        score = _repair_opportunity_score(row, opportunity_scores)
        if score and not (row.get("opportunity_score", "") or "").strip():
            row["opportunity_score"] = str(score)
        if min_score is not None and score < min_score:
            continue
        existing = best_by_asin.get(asin)
        if existing is None or _bsr_repair_sort_key(row, priority_asins, today) < _bsr_repair_sort_key(existing, priority_asins, today):
            best_by_asin[asin] = row

    selected: list[dict[str, str]] = []
    skipped_fresh = 0
    sorted_rows = sorted(best_by_asin.values(), key=lambda row: _bsr_repair_sort_key(row, priority_asins, today))
    for row in sorted_rows:
        if only_missing and not _missing_bsr_fields_reason(row):
            continue
        if not force and _is_fresh_high_confidence_bsr(row, today):
            skipped_fresh += 1
            continue
        selected.append(row)
        if len(selected) >= limit:
            break
    return selected, skipped_fresh


def _bsr_repair_context(output_dir: Path) -> tuple[set[str], dict[str, int]]:
    priority_asins: set[str] = set()
    opportunity_scores: dict[str, int] = {}
    for path in (output_dir / "trend_alerts.csv", output_dir / "lark_trend_alerts.csv"):
        for row in read_csv(path):
            asin = _row_asin(row)
            if not is_asin(asin):
                continue
            priority_asins.add(asin)
            score = _to_int(row.get("opportunity_score", "")) or 0
            if score > opportunity_scores.get(asin, 0):
                opportunity_scores[asin] = score
    top_opportunities_path = output_dir / "top_opportunities.html"
    if top_opportunities_path.exists():
        text = top_opportunities_path.read_text(encoding="utf-8", errors="replace")
        for asin in re.findall(r"\bB0[A-Z0-9]{8}\b", text.upper()):
            priority_asins.add(asin)
    return priority_asins, opportunity_scores


def _bsr_repair_sort_key(
    row: dict[str, str],
    priority_asins: set[str],
    today: str,
) -> tuple[int, int, str, int, int, int, int, int, int, int, str]:
    asin = _row_asin(row)
    display_rank = _display_rank_value(row)
    score = _repair_opportunity_score(row, {})
    seller_preview_missing = _is_missing_seller_preview_row(row)
    return (
        0 if seller_preview_missing else 1,
        display_rank if seller_preview_missing else SELLER_PREVIEW_PRODUCT_LIMIT + 1,
        _seller_identity(row) if seller_preview_missing else "",
        0 if asin in priority_asins else 1,
        0 if _missing_bsr_fields_reason(row) else 1,
        0 if (row.get("rank_parse_confidence", "") or "").strip().lower() != "high" else 1,
        0 if _rank_is_stale(row, today) else 1,
        -score,
        0 if display_rank <= 50 else 1,
        display_rank,
        asin,
    )


def _repair_opportunity_score(row: dict[str, str], opportunity_scores: dict[str, int]) -> int:
    asin = _row_asin(row)
    return _to_int(row.get("opportunity_score", "")) or opportunity_scores.get(asin, 0)


def _display_rank_value(row: dict[str, str]) -> int:
    return (
        _to_int(row.get("display_rank", ""))
        or _to_int(row.get("display_order", ""))
        or _to_int(row.get("rank", ""))
        or _to_int(row.get("position", ""))
        or 10**9
    )


def _is_missing_seller_preview_row(row: dict[str, str]) -> bool:
    source_type = (row.get("source_type", "") or row.get("page_type", "") or "").strip().lower()
    display_rank = _display_rank_value(row)
    return (
        source_type == "seller"
        and 1 <= display_rank <= SELLER_PREVIEW_PRODUCT_LIMIT
        and bool(_missing_bsr_fields_reason(row))
    )


def _seller_identity(row: dict[str, str]) -> str:
    return (
        row.get("source_id", "")
        or row.get("seller_id", "")
        or row.get("seller_name", "")
        or row.get("source_name", "")
        or ""
    ).strip().lower()


def _is_fresh_high_confidence_bsr(row: dict[str, str], today: str) -> bool:
    return not _bsr_refresh_reason(row) and not _rank_is_stale(row, today)


def _rank_is_stale(row: dict[str, str], today: str) -> bool:
    extracted_at = (row.get("rank_extracted_at", "") or "").strip()
    if len(extracted_at) < 10:
        return True
    return extracted_at[:10] < today


def _missing_bsr_fields_reason(fields: dict[str, str]) -> str:
    ensured = ensure_category_rank_fields(dict(fields))
    if not has_extracted_bsr(ensured):
        return "missing_bsr"
    required_fields = (
        "bsr_rank",
        "bsr_category",
        "category_ranks_raw",
        "raw_bsr_block",
        "primary_bsr_rank",
        "primary_bsr_category",
        "sub_bsr_rank",
        "sub_bsr_category",
        "all_bsr_ranks",
    )
    missing_fields = [field for field in required_fields if not (ensured.get(field, "") or "").strip()]
    return "missing_bsr_fields" if missing_fields else ""


def _update_detail_cache_from_bsr_repairs(
    path: Path,
    products: list[dict[str, str]],
    repairs_by_asin: dict[str, dict[str, str]],
) -> None:
    products_by_asin: dict[str, dict[str, str]] = {}
    for row in products:
        asin = _row_asin(row)
        if is_asin(asin) and asin not in products_by_asin:
            products_by_asin[asin] = row
    cache_rows: list[dict[str, str]] = []
    fixes_by_asin: dict[str, dict[str, str]] = {}
    for asin, rank_fields in repairs_by_asin.items():
        row = dict(products_by_asin.get(asin, {"asin": asin}))
        row.update(rank_fields)
        row["asin"] = asin
        cache_rows.append(row)
        fixes_by_asin[asin] = row
    update_detail_cache_from_fixes(path, load_detail_cache(path), cache_rows, fixes_by_asin)


def run_publish_report(args: argparse.Namespace) -> int:
    try:
        site_url = publish_report(
            output_dir=Path(args.output),
            repo_url=args.repo_url,
            site_url=args.site_url,
        )
    except PublishError as exc:
        print(f"Publishing failed: {exc}")
        return 1

    print("Report published:")
    print(site_url)
    return 0


def run_scan(args: argparse.Namespace) -> int:
    source_path = resolve_sources_path(getattr(args, "sources", None))
    output_dir = Path(getattr(args, "output", "output"))
    snapshot_dir = Path(getattr(args, "snapshot_dir", DEFAULT_SNAPSHOT_DIR))
    master_snapshot_path = Path(getattr(args, "master_snapshot", DEFAULT_MASTER_SNAPSHOT_PATH))
    started = now_utc()
    timestamp = timestamp_for_filename(started)
    fetched_at = isoformat_utc(started)

    sources = read_sources(source_path, include_inactive=getattr(args, "include_inactive", False))
    if getattr(args, "limit_sources", None):
        sources = sources[: args.limit_sources]

    products: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []
    source_scan_rows: list[dict[str, str]] = []
    if getattr(args, "scan_report_only", False) and getattr(args, "resume_scan_report", False):
        source_scan_rows = read_csv(output_dir / "source_scan_report.csv")
        if source_scan_rows and not all(field in source_scan_rows[0] for field in SOURCE_SCAN_REPORT_FIELDS):
            source_scan_rows = []
        completed_source_names = {
            (row.get("source_name", "") or "").strip()
            for row in source_scan_rows
            if (row.get("source_name", "") or "").strip()
        }
        if completed_source_names:
            sources = [source for source in sources if source.display_name not in completed_source_names]
    html_dir = Path(args.html_dir) if getattr(args, "html_dir", None) else None
    page_dir = output_dir / "pages"
    screenshot_dir = Path(args.screenshot_dir) if not getattr(args, "no_screenshots", False) else None
    fetcher: PlaywrightFetcher | None = None

    print(f"Source file: {source_path}")
    print(f"Sources to scan: {len(sources)}")
    if source_scan_rows:
        print(f"Existing source scan report rows: {len(source_scan_rows)}")

    result: ScanResult | None = None
    try:
        for index, source in enumerate(sources, start=1):
            print(f"[{index}/{len(sources)}] {source.display_name} ({source.source_type})")
            source_started_at = time.monotonic()
            source_max_pages = source_page_limit(source, args)
            html = None
            fetched_pages: list[FetchedPage] = []

            try:
                html_path = find_saved_html(html_dir, source) if html_dir else None
                if html_path:
                    html = html_path.read_text(encoding="utf-8", errors="replace")
                    fetched_pages = [FetchedPage(html=html, url=source.url, page_number=1)]
                elif getattr(args, "offline", False):
                    raise FileNotFoundError(f"No saved HTML file found for {source.display_name}")
                else:
                    if fetcher is None:
                        fetcher = PlaywrightFetcher(
                            timeout=args.timeout,
                            user_agent=args.user_agent,
                            headless=not args.headful,
                            wait_until=args.wait_until,
                            ready_timeout=args.ready_timeout,
                            browser_channel=args.browser_channel,
                            browser_executable=args.browser_executable,
                            block_assets=getattr(args, "block_assets", False),
                        )
                        fetcher.__enter__()
                        location_page = fetcher.new_page()
                        try:
                            set_amazon_delivery_location(
                                location_page,
                                args.zipcode,
                                args.marketplace_domain,
                            )
                        finally:
                            location_page.close()
                    shot_path = screenshot_path(screenshot_dir, source, timestamp) if screenshot_dir else None
                    err_shot_path = (
                        error_screenshot_path(Path(args.screenshot_dir), source, timestamp)
                        if not getattr(args, "no_error_screenshots", False)
                        else None
                    )
                    fetched_pages = fetch_pages_with_retries(
                        fetcher=fetcher,
                        source=source,
                        screenshot_path=shot_path,
                        error_screenshot_path=err_shot_path,
                        retries=args.retries,
                        delay=args.delay,
                        scroll=source_scroll_enabled(source, args),
                        max_scrolls=args.max_scrolls,
                        scroll_wait_ms=args.scroll_wait_ms,
                        max_pages=source_max_pages,
                        capture_first_page_screenshot=True,
                    )
                    html = fetched_pages[0].html if fetched_pages else None
                    if not getattr(args, "no_save_html", False):
                        for fetched_page in fetched_pages:
                            save_html(page_dir, source, fetched_page.html, timestamp, page_number=fetched_page.page_number)

                parsed = parse_source_pages(fetched_pages, source, fetched_at)
                if getattr(args, "max_products", None):
                    parsed = parsed[: args.max_products]
                products.extend(parsed)
                source_scan_row = build_source_scan_report_row(
                    source,
                    fetched_pages,
                    parsed,
                    max_pages=source_max_pages,
                    elapsed_seconds=time.monotonic() - source_started_at,
                )
                if source_scan_row["expected_products"] == "":
                    save_unknown_total_artifacts(output_dir, source, fetched_pages, timestamp)
                source_scan_rows.append(source_scan_row)
                print(f"  products: {len(parsed)}")
            except (BotCheckError, FetchError, OSError, ValueError) as exc:
                source_scan_row = build_source_scan_report_row(
                    source,
                    fetched_pages,
                    [],
                    max_pages=source_max_pages,
                    elapsed_seconds=time.monotonic() - source_started_at,
                    stop_reason=f"{type(exc).__name__}: {exc}",
                )
                if source_scan_row["expected_products"] == "":
                    save_unknown_total_artifacts(output_dir, source, fetched_pages, timestamp)
                source_scan_rows.append(source_scan_row)
                errors.append(
                    {
                        "fetched_at": fetched_at,
                        "source_name": source.display_name,
                        "category": source.category,
                        "url": source.url,
                        "error_type": type(exc).__name__,
                        "message": str(exc),
                    }
                )
                print(f"  error: {type(exc).__name__}: {exc}")

            if getattr(args, "scan_report_only", False):
                write_csv(output_dir / "source_scan_report.csv", source_scan_rows, SOURCE_SCAN_REPORT_FIELDS)

            if index < len(sources) and html is not None and not getattr(args, "offline", False):
                polite_sleep(args.delay)

        if getattr(args, "scan_report_only", False):
            write_csv(output_dir / "source_scan_report.csv", source_scan_rows, SOURCE_SCAN_REPORT_FIELDS)
            print("")
            print(f"Sources scanned: {len(source_scan_rows)}")
            print(f"Errors: {len(errors)}")
            print(f"Source scan report: {output_dir / 'source_scan_report.csv'}")
            return 0 if source_scan_rows else 1

        if (
            (
                getattr(args, "fetch_category_rank", False)
                or getattr(args, "fix_missing_details", False)
                or getattr(args, "fix_new_products", False)
                or getattr(args, "refresh_bsr", False)
                or getattr(args, "refresh_all_details", False)
            )
            and products
            and fetcher is None
        ):
            fetcher = PlaywrightFetcher(
                timeout=args.timeout,
                user_agent=args.user_agent,
                headless=not args.headful,
                wait_until=args.wait_until,
                ready_timeout=args.ready_timeout,
                browser_channel=args.browser_channel,
                browser_executable=args.browser_executable,
                block_assets=getattr(args, "block_assets", False),
            )
            fetcher.__enter__()
            location_page = fetcher.new_page()
            try:
                set_amazon_delivery_location(
                    location_page,
                    args.zipcode,
                    args.marketplace_domain,
                )
            finally:
                location_page.close()

        result = write_outputs(
            output_dir,
            snapshot_dir,
            master_snapshot_path,
            fetched_at,
            products,
            errors,
            sources,
            include_non_pod=getattr(args, "include_non_pod", False),
            category_rank_fetcher=fetcher,
            fetch_category_rank=getattr(args, "fetch_category_rank", False),
            max_detail_pages=getattr(args, "max_detail_pages", DEFAULT_MAX_DETAIL_PAGES),
            detail_fix_fetcher=fetcher,
            fix_missing_details=getattr(args, "fix_missing_details", False),
            fix_new_products=getattr(args, "fix_new_products", False),
            max_detail_fixes=getattr(args, "max_detail_fixes", DEFAULT_MAX_DETAIL_FIXES),
            auto_fix_opportunity_details=bool(fetcher),
            refresh_bsr=getattr(args, "refresh_bsr", False),
            skip_fixed_details=getattr(args, "skip_fixed_details", True),
            refresh_all_details=getattr(args, "refresh_all_details", False),
            detail_delay=getattr(args, "delay", DEFAULT_DETAIL_DELAY_SECONDS),
            detail_timeout=getattr(args, "detail_timeout", DEFAULT_DETAIL_TIMEOUT_SECONDS),
            source_scan_rows=source_scan_rows,
        )
    finally:
        if fetcher is not None:
            fetcher.close()

    if result is None:
        return 1

    print("")
    print(f"Products found: {len(result.products)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Latest products: {result.output_paths['latest_products']}")
    print(f"Today snapshot: {result.output_paths['today_snapshot']}")
    print(f"Summary: {result.output_paths['source_summary']}")
    print(f"Source scan report: {result.output_paths['source_scan_report']}")
    print(f"Changes: {result.output_paths['market_changes']}")
    print(f"Historical comparison: {result.output_paths['historical_comparison']}")
    print(f"Rank audit: {result.output_paths['rank_audit']}")
    print(f"Rank trends: {result.output_paths['rank_trends']}")
    print(f"Product trends: {result.output_paths['product_trends']}")
    print(f"Trend alerts: {result.output_paths['trend_alerts']}")
    print(f"Lark trend alerts: {result.output_paths['lark_trend_alerts']}")
    print(f"Today dashboard: {result.output_paths['priority_board']}")
    print(f"Priority board CSV: {result.output_paths['priority_board_csv']}")
    print(f"Product Discovery: {result.output_paths['product_discovery']}")
    print(f"Competitor: {result.output_paths['competitor']}")
    print(f"Trend Explorer: {result.output_paths['trend_explorer']}")
    print(f"Product Detail: {result.output_paths['product_detail']}")
    print(f"Products compatibility page: {result.output_paths['products']}")
    print(f"Top winners compatibility page: {result.output_paths['top_winners']}")
    print(f"New breakouts compatibility page: {result.output_paths['new_breakouts']}")
    print(f"Fast movers compatibility page: {result.output_paths['fast_movers']}")
    print(f"New releases compatibility page: {result.output_paths['new_releases']}")
    print(f"Trends compatibility page: {result.output_paths['trends']}")
    print(f"Database compatibility page: {result.output_paths['database']}")
    print(f"Image gallery compatibility page: {result.output_paths['image_gallery']}")
    print(f"Top opportunities compatibility page: {result.output_paths['top_opportunities']}")
    print(f"All opportunities compatibility page: {result.output_paths['all_opportunities']}")
    print(f"New products compatibility page: {result.output_paths['new_products']}")
    print(f"Rising products compatibility page: {result.output_paths['rising_products']}")
    print(f"Seller intelligence compatibility page: {result.output_paths['seller_intelligence_page']}")
    print(f"Niche intelligence compatibility page: {result.output_paths['niche_intelligence_page']}")
    print(f"Source explorer compatibility page: {result.output_paths['source_explorer']}")
    print(f"Non-POD excluded: {result.output_paths['non_pod_excluded']}")
    print(f"Source trends: {result.output_paths['source_trends']}")
    print(f"Seller intelligence: {result.output_paths['seller_intelligence']}")
    print(f"Niche intelligence: {result.output_paths['niche_intelligence']}")
    print(f"Workbook: {result.output_paths['workbook']}")
    print(f"Snapshot: {result.output_paths['snapshot']}")
    print(f"Master snapshot: {result.output_paths['master_snapshot']}")
    return 0 if products or errors else 1


def write_outputs(
    output_dir: Path,
    snapshot_dir: Path,
    master_snapshot_path: Path,
    fetched_at: str,
    products: list[dict[str, str]],
    errors: list[dict[str, str]],
    sources: list[Source] | None = None,
    include_non_pod: bool = False,
    category_rank_fetcher: PlaywrightFetcher | None = None,
    fetch_category_rank: bool = False,
    max_detail_pages: int = DEFAULT_MAX_DETAIL_PAGES,
    detail_fix_fetcher: PlaywrightFetcher | None = None,
    fix_missing_details: bool = False,
    fix_new_products: bool = False,
    max_detail_fixes: int = DEFAULT_MAX_DETAIL_FIXES,
    auto_fix_opportunity_details: bool = False,
    refresh_bsr: bool = False,
    skip_fixed_details: bool = True,
    refresh_all_details: bool = False,
    detail_delay: float = DEFAULT_DETAIL_DELAY_SECONDS,
    detail_timeout: int = DEFAULT_DETAIL_TIMEOUT_SECONDS,
    source_scan_rows: list[dict[str, str]] | None = None,
) -> ScanResult:
    scan_date = fetched_at[:10]
    snapshot_path = snapshot_dir / f"{scan_date}_snapshot.csv"
    latest_path = output_dir / "latest_products.csv"
    today_snapshot_path = output_dir / "today_snapshot.csv"
    changes_path = output_dir / "market_changes.csv"
    summary_path = output_dir / "source_summary.csv"
    source_scan_report_path = output_dir / "source_scan_report.csv"
    historical_comparison_path = output_dir / "historical_comparison.csv"
    rank_audit_path = output_dir / "rank_audit.csv"
    rank_trends_path = output_dir / "rank_trends.csv"
    product_trends_path = output_dir / "product_trends.csv"
    trend_alerts_path = output_dir / "trend_alerts.csv"
    lark_trend_alerts_path = output_dir / "lark_trend_alerts.csv"
    source_trends_path = output_dir / "source_trends.csv"
    seller_intelligence_path = output_dir / "seller_intelligence.csv"
    niche_intelligence_path = output_dir / "niche_intelligence.csv"
    errors_path = output_dir / "source_errors.csv"
    workbook_path = output_dir / "daily_market_spy_report.xlsx"
    detail_cache_path = output_dir / DETAIL_CACHE_FILENAME
    detail_cache = load_detail_cache(detail_cache_path)
    previous_master_rows = read_csv(master_snapshot_path) if master_snapshot_path.exists() else []

    products = [
        ensure_detail_fix_fields(ensure_niche_fields(ensure_category_rank_fields(ensure_pod_fields(row))))
        for row in products
    ]
    normalize_source_identity_rows(products, sources)
    apply_category_rank_backfill(products, load_existing_category_rank_cache(output_dir, snapshot_dir))
    _log_debug_bsr_state("before cache merge", products)
    merge_detail_cache_into_rows(products, detail_cache, merge_bsr=not refresh_bsr)
    _log_debug_bsr_state("after cache merge", products)
    write_csv(snapshot_path, products, PRODUCT_FIELDS)
    write_latest_products_csv(latest_path, products)
    write_csv(today_snapshot_path, products, PRODUCT_FIELDS)

    previous_path = previous_snapshot(snapshot_dir, snapshot_path)
    previous_rows = read_csv(previous_path) if previous_path else []
    changes = compare_snapshots(previous_rows, products, fetched_at) if previous_rows else []
    summaries = summarize_sources(products, changes)

    write_csv(changes_path, changes, CHANGE_FIELDS)
    write_csv(summary_path, summaries, SUMMARY_FIELDS)
    historical_rows = build_historical_comparison(snapshot_dir, snapshot_path, sources)
    if products:
        apply_display_rank_metrics(products, historical_rows)
        write_csv(snapshot_path, products, PRODUCT_FIELDS)
        write_latest_products_csv(latest_path, products)
        write_csv(today_snapshot_path, products, PRODUCT_FIELDS)
    trend_alerts = build_trend_alerts(historical_rows)
    lark_trend_alerts = build_lark_trend_alerts(
        historical_rows,
        source_metadata=sources,
        include_non_pod=include_non_pod,
    )
    mark_detail_candidate_context(
        products,
        historical_rows=historical_rows,
        top_rows=lark_trend_alerts,
        previous_master_rows=previous_master_rows,
        scan_date=scan_date,
    )

    if fix_missing_details or fix_new_products or auto_fix_opportunity_details or refresh_bsr or refresh_all_details:
        detail_candidate_rows = products if (fix_missing_details or fix_new_products or refresh_bsr or refresh_all_details) else lark_trend_alerts
        if detail_fix_fetcher is None:
            print("Warning: detail refresh requested but no browser is available; skipping detail pages.")
        else:
            fixes_by_asin = fetch_detail_fixes_for_products(
                detail_fix_fetcher,
                detail_candidate_rows,
                max_detail_fixes=max_detail_fixes,
                detail_delay=detail_delay,
                detail_timeout=detail_timeout,
                refresh_bsr=refresh_bsr,
                detail_cache_path=detail_cache_path,
                skip_fixed_details=skip_fixed_details,
                refresh_all_details=refresh_all_details,
            )
            if fixes_by_asin:
                apply_detail_fixes(products, fixes_by_asin)
                detail_cache = update_detail_cache_from_rows(detail_cache_path, detail_cache, products, fixes_by_asin)
                write_csv(snapshot_path, products, PRODUCT_FIELDS)
                write_latest_products_csv(latest_path, products)
                write_csv(today_snapshot_path, products, PRODUCT_FIELDS)
                historical_rows = build_historical_comparison(snapshot_dir, snapshot_path, sources)
                apply_display_rank_metrics(products, historical_rows)
                write_csv(snapshot_path, products, PRODUCT_FIELDS)
                write_latest_products_csv(latest_path, products)
                write_csv(today_snapshot_path, products, PRODUCT_FIELDS)
                trend_alerts = build_trend_alerts(historical_rows)
                lark_trend_alerts = build_lark_trend_alerts(
                    historical_rows,
                    source_metadata=sources,
                    include_non_pod=include_non_pod,
                )

    if fetch_category_rank:
        if category_rank_fetcher is None:
            print("Warning: --fetch-category-rank requested but no browser is available; skipping detail pages.")
        else:
            ranks_by_asin = fetch_category_ranks_for_opportunities(
                category_rank_fetcher,
                lark_trend_alerts,
                max_detail_pages=max_detail_pages,
                detail_delay=detail_delay,
                detail_timeout=detail_timeout,
                product_rows=products,
            )
            if ranks_by_asin:
                apply_category_ranks(products, ranks_by_asin)
                write_csv(snapshot_path, products, PRODUCT_FIELDS)
                write_latest_products_csv(latest_path, products)
                write_csv(today_snapshot_path, products, PRODUCT_FIELDS)
                historical_rows = build_historical_comparison(snapshot_dir, snapshot_path, sources)
                apply_display_rank_metrics(products, historical_rows)
                write_csv(snapshot_path, products, PRODUCT_FIELDS)
                write_latest_products_csv(latest_path, products)
                write_csv(today_snapshot_path, products, PRODUCT_FIELDS)
                trend_alerts = build_trend_alerts(historical_rows)
                lark_trend_alerts = build_lark_trend_alerts(
                    historical_rows,
                    source_metadata=sources,
                    include_non_pod=include_non_pod,
                )

    product_trends = build_rank_trends(snapshot_dir, sources)
    product_history_rows = build_product_history_rows(snapshot_dir, sources)
    source_trends = build_source_trends(snapshot_dir, sources)
    seller_intelligence = build_seller_intelligence(historical_rows, sources)
    niche_intelligence = build_niche_intelligence(historical_rows, include_non_pod=include_non_pod)

    write_csv(historical_comparison_path, historical_rows, HISTORICAL_COMPARISON_FIELDS)
    write_rank_audit(output_dir, products)
    write_csv(trend_alerts_path, trend_alerts, TREND_ALERT_FIELDS)
    write_csv(niche_intelligence_path, niche_intelligence, NICHE_INTELLIGENCE_FIELDS)
    artifact_paths = write_lark_opportunity_artifacts(
        output_dir,
        lark_trend_alerts,
        all_opportunities=trend_alerts,
        products=products,
        seller_rows=seller_intelligence,
        niche_rows=niche_intelligence,
        product_history_rows=product_history_rows,
        include_non_pod=include_non_pod,
    )
    write_csv(rank_trends_path, product_trends, RANK_TREND_FIELDS)
    write_csv(product_trends_path, product_trends, RANK_TREND_FIELDS)
    write_csv(source_trends_path, source_trends, SOURCE_TREND_FIELDS)
    write_csv(seller_intelligence_path, seller_intelligence, SELLER_INTELLIGENCE_FIELDS)
    write_master_snapshot(snapshot_dir, master_snapshot_path)
    write_csv(errors_path, errors, ERROR_FIELDS)
    write_csv(source_scan_report_path, source_scan_rows or [], SOURCE_SCAN_REPORT_FIELDS)
    write_daily_workbook(
        workbook_path=workbook_path,
        products=products,
        historical_rows=historical_rows,
        source_summaries=summaries,
        errors=errors,
        source_metadata=sources,
    )

    return ScanResult(
        products=products,
        errors=errors,
        output_paths={
            "snapshot": str(snapshot_path),
            "latest_products": str(latest_path),
            "today_snapshot": str(today_snapshot_path),
            "market_changes": str(changes_path),
            "historical_comparison": str(historical_comparison_path),
            "rank_audit": str(rank_audit_path),
            "source_summary": str(summary_path),
            "source_scan_report": str(source_scan_report_path),
            "rank_trends": str(rank_trends_path),
            "product_trends": str(product_trends_path),
            "trend_alerts": str(trend_alerts_path),
            "lark_trend_alerts": artifact_paths["lark_trend_alerts"],
            "priority_board": artifact_paths["priority_board"],
            "priority_board_csv": artifact_paths["priority_board_csv"],
            "product_discovery": artifact_paths["product_discovery"],
            "products": artifact_paths["products"],
            "competitor": artifact_paths["competitor"],
            "trend_explorer": artifact_paths["trend_explorer"],
            "product_detail": artifact_paths["product_detail"],
            "top_winners": artifact_paths["top_winners"],
            "new_breakouts": artifact_paths["new_breakouts"],
            "fast_movers": artifact_paths["fast_movers"],
            "new_releases": artifact_paths["new_releases"],
            "trends": artifact_paths["trends"],
            "database": artifact_paths["database"],
            "index": artifact_paths["index"],
            "image_gallery": artifact_paths["image_gallery"],
            "top_opportunities": artifact_paths["top_opportunities"],
            "all_opportunities": artifact_paths["all_opportunities"],
            "new_products": artifact_paths["new_products"],
            "rising_products": artifact_paths["rising_products"],
            "seller_intelligence_page": artifact_paths["seller_intelligence"],
            "niche_intelligence_page": artifact_paths["niche_intelligence"],
            "source_explorer": artifact_paths["source_explorer"],
            "non_pod_excluded": artifact_paths["non_pod_excluded"],
            "source_trends": str(source_trends_path),
            "seller_intelligence": str(seller_intelligence_path),
            "niche_intelligence": str(niche_intelligence_path),
            "workbook": str(workbook_path),
            "master_snapshot": str(master_snapshot_path),
            "source_errors": str(errors_path),
        },
    )


def write_rank_audit(output_dir: Path, rows: list[dict[str, str]]) -> str:
    path = output_dir / "rank_audit.csv"
    write_csv(path, build_rank_audit_rows(rows), RANK_AUDIT_FIELDS)
    return str(path)


def write_latest_products_csv(path: Path, rows: list[dict[str, str]]) -> None:
    _log_debug_bsr_state("right before latest_products.csv write", rows, path=path)
    _log_latest_products_bsr_state(path, rows)
    write_csv(path, rows, PRODUCT_FIELDS)


def _log_latest_products_bsr_state(path: Path, rows: list[dict[str, str]]) -> None:
    for row in rows:
        asin = _row_asin(row)
        if not asin:
            continue
        print(
            "BSR CSV write "
            f"path={path} "
            f"ASIN={asin} "
            f"primary_bsr_rank={(row.get('primary_bsr_rank', '') or row.get('bsr_rank', '') or '').strip()} "
            f"sub_bsr_rank={(row.get('sub_bsr_rank', '') or '').strip()} "
            f"rank_parse_method={(row.get('rank_parse_method', '') or '').strip()}"
        )


def _log_debug_bsr_state(stage: str, row_or_rows: dict[str, str] | list[dict[str, str]], *, path: Path | None = None) -> None:
    rows = [row_or_rows] if isinstance(row_or_rows, dict) else row_or_rows
    for row in rows:
        asin = _row_asin(row)
        if asin not in DEBUG_BSR_ASINS:
            continue
        values = " ".join(
            f"{field}={_debug_value(row.get(field, ''))}"
            for field in BSR_DEBUG_FIELDS
        )
        path_note = f" path={path}" if path is not None else ""
        print(f"BSR debug stage={stage}{path_note} ASIN={asin} {values}")


def _debug_value(value: object) -> str:
    text = str(value or "").strip().replace("\r", "\\r").replace("\n", "\\n")
    return text if text else "blank"


def build_rank_audit_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    audit_rows: list[dict[str, str]] = []
    for row in rows:
        ensure_category_rank_fields(row)
        audit_row = {field: row.get(field, "") for field in RANK_AUDIT_FIELDS}
        if audit_row.get("rank_parse_method") == "text_scan" and not audit_row.get("rank_parse_warning", ""):
            confidence = audit_row.get("rank_parse_confidence", "")
            if confidence == "low":
                audit_row["rank_parse_warning"] = "Best Sellers Rank section selectors failed and no BSR block was found in text_scan fallback."
            else:
                audit_row["rank_parse_warning"] = "Best Sellers Rank section selectors failed; parsed from text_scan fallback and should be verified."
        audit_rows.append(audit_row)
    return audit_rows


def _rank_diagnostics_from_detail_result(result: object) -> dict[str, str]:
    return {
        "accordion_found": _bool_text(getattr(result, "accordion_found", False)),
        "accordion_expanded": _bool_text(getattr(result, "accordion_expanded", False)),
        "bsr_visible_after_expand": _bool_text(getattr(result, "bsr_visible_after_expand", False)),
    }


def _bool_text(value: object) -> str:
    return "true" if bool(value) else "false"


def fetch_category_ranks_for_opportunities(
    fetcher: PlaywrightFetcher,
    opportunity_rows: list[dict[str, str]],
    max_detail_pages: int = DEFAULT_MAX_DETAIL_PAGES,
    detail_delay: float = DEFAULT_DETAIL_DELAY_SECONDS,
    detail_timeout: int = DEFAULT_DETAIL_TIMEOUT_SECONDS,
    product_rows: list[dict[str, str]] | None = None,
) -> dict[str, dict[str, str]]:
    priority_rows = _category_rank_priority_rows(product_rows or [], opportunity_rows)
    candidates = _category_rank_candidates(priority_rows, max_detail_pages)
    if not candidates:
        print("Amazon BSR detail pages: 0 candidates")
        return {}

    print(f"Amazon BSR detail pages: {len(candidates)} candidates")
    ranks_by_asin: dict[str, dict[str, str]] = {}
    for index, row in enumerate(candidates, start=1):
        asin = _row_asin(row)
        url = row.get("product_url", "").strip() or f"https://www.amazon.com/dp/{asin}"
        try:
            html, status, error, source_url, diagnostics = _fetch_detail_page_for_rank(
                fetcher,
                url,
                detail_timeout=detail_timeout,
            )
            rank_fields = extract_bsr_from_product_page(
                html,
                source_url=source_url or url,
                page_status=status,
                diagnostics=diagnostics,
            )
        except (BotCheckError, FetchError, OSError, ValueError) as exc:
            rank_fields = extract_bsr_from_product_page(
                "",
                source_url=url,
                page_status=f"{type(exc).__name__}: {exc}",
            )
            ranks_by_asin[asin] = rank_fields
            print(f"  Amazon BSR {index}/{len(candidates)} {asin}: skipped ({type(exc).__name__}: {exc})")
        else:
            raw_rank = rank_fields.get("category_ranks_raw", "")
            ranks_by_asin[asin] = rank_fields
            if raw_rank:
                print(f"  Amazon BSR {index}/{len(candidates)} {asin}: {raw_rank}")
            else:
                status_note = f" ({status}: {error})" if error else f" ({status})"
                print(f"  Amazon BSR {index}/{len(candidates)} {asin}: unavailable{status_note}")

        if index < len(candidates):
            polite_sleep(detail_delay)

    found_count = sum(1 for fields in ranks_by_asin.values() if fields.get("category_ranks_raw", ""))
    print(f"Amazon BSR ranks found: {found_count}/{len(candidates)}")
    return ranks_by_asin


def _fetch_detail_page_for_rank(
    fetcher: PlaywrightFetcher,
    url: str,
    detail_timeout: int = DEFAULT_DETAIL_TIMEOUT_SECONDS,
) -> tuple[str, str, str, str, dict[str, str]]:
    if hasattr(fetcher, "fetch_detail_page"):
        result = fetcher.fetch_detail_page(  # type: ignore[attr-defined]
            url,
            timeout=detail_timeout,
            capture_screenshot=False,
        )
        return (
            str(getattr(result, "html", "") or ""),
            str(getattr(result, "status", "ok") or "ok"),
            str(getattr(result, "error", "") or ""),
            str(getattr(result, "url", url) or url),
            _rank_diagnostics_from_detail_result(result),
        )
    return fetcher.fetch(url), "ok", "", url, {}


def apply_category_ranks(rows: list[dict[str, str]], ranks_by_asin: dict[str, dict[str, str]]) -> int:
    updated = 0
    for row in rows:
        ensure_category_rank_fields(row)
        asin = _row_asin(row)
        rank_fields = ranks_by_asin.get(asin)
        if not rank_fields:
            continue
        if _apply_bsr_fields(row, rank_fields, asin=asin, overwrite=True):
            updated += 1
    return updated


def _apply_bsr_fields(
    row: dict[str, str],
    source: dict[str, str],
    *,
    asin: str,
    overwrite: bool,
) -> bool:
    ensure_category_rank_fields(row)
    source_fields = ensure_category_rank_fields(dict(source))
    if not has_extracted_bsr(source_fields):
        return False
    old_primary_bsr_rank = (row.get("primary_bsr_rank", "") or row.get("bsr_rank", "") or "").strip()
    old_sub_bsr_rank = (row.get("sub_bsr_rank", "") or "").strip()
    authoritative_refresh = _is_authoritative_bsr_refresh(source_fields)
    changed = False
    for field in BSR_REFRESH_FIELDS:
        value = (source_fields.get(field, "") or "").strip()
        if not value and not authoritative_refresh:
            continue
        if overwrite:
            should_apply = row.get(field, "") != value
        else:
            should_apply = not (row.get(field, "") or "").strip()
        if should_apply:
            row[field] = value
            changed = True
    if changed:
        ensure_category_rank_fields(row)
        _log_bsr_update(
            asin=asin,
            old_primary_bsr_rank=old_primary_bsr_rank,
            new_primary_bsr_rank=(row.get("primary_bsr_rank", "") or row.get("bsr_rank", "") or "").strip(),
            old_sub_bsr_rank=old_sub_bsr_rank,
            new_sub_bsr_rank=(row.get("sub_bsr_rank", "") or "").strip(),
            rank_parse_confidence=(source_fields.get("rank_parse_confidence", "") or "").strip(),
            bsr_source=_bsr_source(source_fields),
        )
    return changed


def _is_authoritative_bsr_refresh(fields: dict[str, str]) -> bool:
    return _is_successful_high_confidence_bsr(fields)


def _bsr_source(fields: dict[str, str]) -> str:
    return (
        (fields.get("rank_parse_method", "") or "").strip()
        or (fields.get("rank_source_url", "") or "").strip()
        or "unknown"
    )


def _log_bsr_update(
    *,
    asin: str,
    old_primary_bsr_rank: str,
    new_primary_bsr_rank: str,
    old_sub_bsr_rank: str,
    new_sub_bsr_rank: str,
    rank_parse_confidence: str,
    bsr_source: str,
) -> None:
    print(
        "BSR update "
        f"ASIN={asin or 'n/a'} "
        f"primary_bsr_rank={old_primary_bsr_rank or 'blank'} -> {new_primary_bsr_rank or 'blank'} "
        f"sub_bsr_rank={old_sub_bsr_rank or 'blank'} -> {new_sub_bsr_rank or 'blank'} "
        f"rank_parse_confidence={rank_parse_confidence or 'unknown'} "
        f"bsr_source={bsr_source}"
    )


def apply_category_rank_backfill(rows: list[dict[str, str]], ranks_by_asin: dict[str, dict[str, str]]) -> int:
    updated = 0
    if not ranks_by_asin:
        return updated
    for row in rows:
        asin = _row_asin(row)
        rank_fields = ranks_by_asin.get(asin)
        if rank_fields and _apply_bsr_fields(row, rank_fields, asin=asin, overwrite=False):
            updated += 1
    return updated


def load_existing_category_rank_cache(output_dir: Path, snapshot_dir: Path) -> dict[str, dict[str, str]]:
    cache: dict[str, dict[str, str]] = {}
    csv_paths = [
        output_dir / "latest_products.csv",
        output_dir / "today_snapshot.csv",
        output_dir / "rank_audit.csv",
        output_dir / "historical_comparison.csv",
        output_dir / "product_trends.csv",
        output_dir / "trend_alerts.csv",
        output_dir / "lark_trend_alerts.csv",
        output_dir / "rank_trends.csv",
        snapshot_dir.parent / "master_snapshot.csv",
        *snapshot_paths(snapshot_dir),
    ]
    for path in _unique_paths(csv_paths):
        if path.exists():
            _merge_category_rank_cache(
                cache,
                category_rank_cache_from_rows(read_csv(path), require_product_page_source=True),
            )
    return cache


def _merge_category_rank_cache(
    target: dict[str, dict[str, str]],
    source: dict[str, dict[str, str]],
) -> None:
    for asin, fields in source.items():
        if asin not in target:
            target[asin] = dict(fields)
        else:
            merge_category_rank_fields(target[asin], fields)


def _unique_paths(paths: list[Path]) -> list[Path]:
    unique: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path.resolve()) if path.exists() else str(path.absolute())
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def apply_display_rank_metrics(rows: list[dict[str, str]], historical_rows: list[dict[str, str]]) -> int:
    metrics_by_source_key = {
        source_history_key(row): row
        for row in historical_rows
        if _row_asin(row)
    }
    updated = 0
    for row in rows:
        source_row = metrics_by_source_key.get(source_history_key(row))
        if not source_row:
            continue
        changed = False
        for field in [*DISPLAY_RANK_FIELDS, *RESEARCH_SCORE_FIELDS, *SOURCE_HISTORY_FIELDS, *EVIDENCE_FIELDS, *PRODUCT_EVIDENCE_FIELDS]:
            value = source_row.get(field, "")
            if value and row.get(field, "") != value:
                row[field] = value
                changed = True
        if changed:
            updated += 1
    return updated


def mark_detail_candidate_context(
    rows: list[dict[str, str]],
    *,
    historical_rows: list[dict[str, str]],
    top_rows: list[dict[str, str]],
    previous_master_rows: list[dict[str, str]],
    scan_date: str,
) -> None:
    previous_master_asins = {_row_asin(row) for row in previous_master_rows if is_asin(_row_asin(row))}
    historical_by_asin: dict[str, dict[str, str]] = {}
    for row in historical_rows:
        asin = _row_asin(row)
        if is_asin(asin) and asin not in historical_by_asin:
            historical_by_asin[asin] = row
    top_asins = {_row_asin(row) for row in top_rows if is_asin(_row_asin(row))}
    for row in rows:
        asin = _row_asin(row)
        if not is_asin(asin):
            continue
        history_row = historical_by_asin.get(asin, {})
        first_seen = (
            history_row.get("first_seen_date", "")
            or history_row.get("first_seen", "")
            or row.get("first_seen_date", "")
            or row.get("first_seen", "")
        )
        days_seen = history_row.get("days_seen", "") or row.get("days_seen", "")
        is_new_today = (
            (bool(previous_master_rows) and asin not in previous_master_asins)
            or days_seen == "1"
            or first_seen[:10] == scan_date
        )
        if is_new_today:
            row["_new_asin_today"] = "true"
        if asin in top_asins:
            row["_top_opportunity"] = "true"


@dataclass
class DetailCandidateSelection:
    candidates: list[dict[str, str]]
    reasons_by_asin: dict[str, str]
    skipped_from_cache: int = 0
    new_asins: int = 0
    new_asins_detail_fetched: int = 0


def load_detail_cache(path: Path) -> dict[str, dict[str, str]]:
    cache: dict[str, dict[str, str]] = {}
    for row in read_csv(path):
        asin = (row.get("asin", "") or "").strip().upper()
        if not is_asin(asin):
            continue
        entry = {field: (row.get(field, "") or "").strip() for field in DETAIL_CACHE_FIELDS}
        entry["asin"] = asin
        ensure_category_rank_fields(entry)
        cache[asin] = entry
    return cache


def write_detail_cache(path: Path, cache: dict[str, dict[str, str]]) -> None:
    rows: list[dict[str, str]] = []
    for asin, entry in sorted(cache.items()):
        row = {field: (entry.get(field, "") or "").strip() for field in DETAIL_CACHE_FIELDS}
        row["asin"] = asin
        rows.append(row)
    write_csv(path, rows, DETAIL_CACHE_FIELDS)


def merge_detail_cache_into_rows(
    rows: list[dict[str, str]],
    detail_cache: dict[str, dict[str, str]],
    *,
    merge_bsr: bool = True,
) -> int:
    if not detail_cache:
        return 0
    updated = 0
    for row in rows:
        asin = _row_asin(row)
        cached = detail_cache.get(asin)
        if cached and _merge_detail_cache_entry(row, cached, merge_bsr=merge_bsr):
            updated += 1
    return updated


def update_detail_cache_from_rows(
    path: Path,
    detail_cache: dict[str, dict[str, str]],
    rows: list[dict[str, str]],
    fixes_by_asin: dict[str, dict[str, str]],
) -> dict[str, dict[str, str]]:
    updated_cache = {asin: dict(entry) for asin, entry in detail_cache.items()}
    fixed_asins = {asin for asin in fixes_by_asin if is_asin(asin)}
    if not fixed_asins:
        return updated_cache
    changed = False
    detail_fixed_at = isoformat_utc(now_utc())
    seen_asins: set[str] = set()
    for row in rows:
        asin = _row_asin(row)
        if asin not in fixed_asins or asin in seen_asins:
            continue
        seen_asins.add(asin)
        entry = _detail_cache_entry_from_row(row, detail_fixed_at=detail_fixed_at)
        if _merge_detail_cache_update(updated_cache.setdefault(asin, {"asin": asin}), entry):
            changed = True
    if changed:
        write_detail_cache(path, updated_cache)
    return updated_cache


def update_detail_cache_from_fixes(
    path: Path,
    detail_cache: dict[str, dict[str, str]],
    rows: list[dict[str, str]],
    fixes_by_asin: dict[str, dict[str, str]],
) -> dict[str, dict[str, str]]:
    updated_cache = {asin: dict(entry) for asin, entry in detail_cache.items()}
    if not fixes_by_asin:
        return updated_cache
    changed = False
    detail_fixed_at = isoformat_utc(now_utc())
    for row in rows:
        asin = _row_asin(row)
        fix = fixes_by_asin.get(asin)
        if not fix:
            continue
        combined = dict(row)
        combined.update(fix)
        combined["asin"] = asin
        entry = _detail_cache_entry_from_row(combined, detail_fixed_at=detail_fixed_at)
        if _merge_detail_cache_update(updated_cache.setdefault(asin, {"asin": asin}), entry):
            changed = True
    if changed:
        write_detail_cache(path, updated_cache)
    return updated_cache


def _detail_cache_entry_from_row(row: dict[str, str], *, detail_fixed_at: str) -> dict[str, str]:
    ensured = ensure_category_rank_fields(dict(row))
    entry = {field: (ensured.get(field, "") or "").strip() for field in DETAIL_CACHE_FIELDS}
    entry["asin"] = _row_asin(row)
    entry["detail_fixed_at"] = detail_fixed_at
    return entry


def _merge_detail_cache_update(existing: dict[str, str], update: dict[str, str]) -> bool:
    changed = False
    update_has_high_bsr = _has_high_confidence_bsr(update)
    existing_has_high_bsr = _has_high_confidence_bsr(existing)
    for field in DETAIL_CACHE_FIELDS:
        value = (update.get(field, "") or "").strip()
        if field == "asin":
            value = value.upper()
        if not value:
            continue
        if field == "title" and not is_valid_product_title(value):
            continue
        if field == "image_url" and not _has_valid_image_url(update):
            continue
        if field in ("title_fixed", "image_fixed") and existing.get(field, "") == "true" and value != "true":
            continue
        if field in _detail_cache_bsr_fields() and existing_has_high_bsr and not update_has_high_bsr:
            continue
        if existing.get(field, "") != value:
            existing[field] = value
            changed = True
    return changed


def _merge_detail_cache_entry(row: dict[str, str], cached: dict[str, str], *, merge_bsr: bool = True) -> bool:
    ensure_detail_fix_fields(row)
    ensure_category_rank_fields(row)
    changed = False
    cached_title = (cached.get("title", "") or "").strip()
    if is_valid_product_title(cached_title) and _needs_title_fix(row):
        row["raw_title"] = row.get("raw_title", "") or row.get("title", "")
        row["title"] = cached_title
        row["title_source"] = "detail_cache"
        row["title_fixed"] = cached.get("title_fixed", "") or "true"
        row.update(classify_pod_row(row))
        row.update(
            classify_niche(
                title=row.get("title", ""),
                category=row.get("category", ""),
                source_name=row.get("source_name", ""),
                pod_type=row.get("pod_type", ""),
                pod_reason=row.get("pod_reason", ""),
            )
        )
        changed = True
    cached_image_url = (cached.get("image_url", "") or "").strip()
    if cached_image_url and _needs_image_fix(row):
        row["image_url"] = cached_image_url
        row["image_source"] = "detail_cache"
        row["image_fixed"] = cached.get("image_fixed", "") or "true"
        changed = True
    if merge_bsr and _has_high_confidence_bsr(cached) and not _has_high_confidence_bsr(row):
        cached_rank_fields = ensure_category_rank_fields(dict(cached))
        for field in CATEGORY_RANK_FIELDS:
            value = (cached_rank_fields.get(field, "") or "").strip()
            if value and row.get(field, "") != value:
                row[field] = value
                changed = True
        if changed:
            ensure_category_rank_fields(row)
    for field in ("review_count", "review_rating"):
        value = (cached.get(field, "") or "").strip()
        if value and not (row.get(field, "") or "").strip():
            row[field] = value
            changed = True
    return changed


def _detail_cache_is_complete(entry: dict[str, str]) -> bool:
    return (
        is_valid_product_title(entry.get("title", ""))
        and _has_valid_image_url(entry)
        and _has_high_confidence_bsr(entry)
    )


def _has_valid_image_url(entry: dict[str, str]) -> bool:
    return bool((entry.get("image_url", "") or "").strip())


def _has_high_confidence_bsr(fields: dict[str, str]) -> bool:
    return not _bsr_refresh_reason(fields)


def _bsr_refresh_reason(fields: dict[str, str]) -> str:
    ensured = ensure_category_rank_fields(dict(fields))
    missing_reason = _missing_bsr_fields_reason(ensured)
    if missing_reason:
        return missing_reason
    if (ensured.get("rank_parse_confidence", "") or "").strip().lower() != "high":
        return "rank_parse_confidence_not_high"
    return ""


def _detail_cache_bsr_fields() -> set[str]:
    return set(CATEGORY_RANK_FIELDS)


def fetch_detail_fixes_for_products(
    fetcher: PlaywrightFetcher,
    rows: list[dict[str, str]],
    max_detail_fixes: int = DEFAULT_MAX_DETAIL_FIXES,
    detail_delay: float = DEFAULT_DETAIL_DELAY_SECONDS,
    detail_timeout: int = DEFAULT_DETAIL_TIMEOUT_SECONDS,
    debug_html_dir: Path = Path("debug_html"),
    screenshot_dir: Path = Path("screenshots"),
    refresh_bsr: bool = False,
    detail_cache_path: Path | None = None,
    skip_fixed_details: bool = True,
    refresh_all_details: bool = False,
) -> dict[str, dict[str, str]]:
    detail_cache = load_detail_cache(detail_cache_path) if detail_cache_path else {}
    if detail_cache:
        _log_debug_bsr_state("before cache merge", rows)
        merge_detail_cache_into_rows(rows, detail_cache, merge_bsr=not refresh_bsr)
        _log_debug_bsr_state("after cache merge", rows)
    selection = _select_detail_fix_candidates(
        rows,
        max_detail_fixes,
        detail_cache=detail_cache,
        detail_cache_enabled=detail_cache_path is not None,
        skip_fixed_details=skip_fixed_details,
        refresh_bsr=refresh_bsr,
        refresh_all_details=refresh_all_details,
    )
    candidates = selection.candidates
    if not candidates:
        print("Detail title/image fixes: 0 candidates")
        print("Detail pages fetched: 0")
        print(f"Detail pages skipped from cache: {selection.skipped_from_cache}")
        print(f"New ASINs: {selection.new_asins}")
        print(f"New ASINs found: {selection.new_asins}")
        print("New ASINs detail fetched: 0")
        print("New ASINs title fixed: 0")
        print("New ASINs image fixed: 0")
        return {}

    print(f"Detail title/image fixes: {len(candidates)} candidates")
    fixes_by_asin: dict[str, dict[str, str]] = {}
    new_asin_title_fixed = 0
    new_asin_image_fixed = 0
    for index, row in enumerate(candidates, start=1):
        asin = _row_asin(row)
        reason = selection.reasons_by_asin.get(asin, "detail_refresh_needed")
        needs_title = _needs_title_fix(row)
        needs_image = _needs_image_fix(row)
        url = row.get("product_url", "").strip() or f"https://www.amazon.com/dp/{asin}"
        fixed_any = False
        print(f"Detail fetched: {asin} reason={reason}")
        fix: dict[str, str] = {
            "detail_fetched_reason": reason,
            "detail_page_status": "ok",
            "detail_title_found": "false",
            "detail_image_found": "false",
            "detail_error": "",
            "detail_bsr_found": "false",
            "detail_bsr_error": "",
        }
        html = ""
        screenshot: bytes | None = None
        try:
            html, status, error, screenshot, rank_source_url, diagnostics = _fetch_detail_page_for_fix(
                fetcher,
                url,
                detail_timeout=detail_timeout,
            )
            fix["detail_page_status"] = status
            fix["detail_error"] = error
            detail_fields = extract_detail_page_fields(html)
            rank_fields = extract_bsr_from_product_page(
                html,
                source_url=rank_source_url or url,
                page_status=status,
                diagnostics=diagnostics,
            )
        except (BotCheckError, FetchError, OSError, ValueError) as exc:
            fix["detail_page_status"] = "error"
            fix["detail_error"] = f"{type(exc).__name__}: {exc}"
            fix["detail_bsr_error"] = fix["detail_error"]
            fixes_by_asin[asin] = fix
            _save_failed_detail_artifacts(asin, html, screenshot, debug_html_dir, screenshot_dir)
            print(f"Failed detail fallback: {asin} - {fix['detail_error']}")
        else:
            title_found = bool(detail_fields.title)
            image_found = bool(detail_fields.image_url)
            bsr_found = bool(rank_fields.get("category_ranks_raw", ""))
            fix["detail_title_found"] = "true" if title_found else "false"
            fix["detail_image_found"] = "true" if image_found else "false"
            fix["detail_bsr_found"] = "true" if bsr_found else "false"
            if bsr_found:
                fix.update({field: rank_fields.get(field, "") for field in CATEGORY_RANK_FIELDS})
                _log_debug_bsr_state("after detail fetch", {"asin": asin, **fix})
                if refresh_bsr:
                    print(f"Detail refreshed BSR: {asin}")
            else:
                fix["detail_bsr_error"] = "BSR unavailable on detail page"
            if needs_title and is_valid_product_title(detail_fields.title):
                fix["title"] = detail_fields.title
                print(f"Fixed title from detail page: {asin}")
                fixed_any = True
                if reason == "new_asin":
                    new_asin_title_fixed += 1
            if needs_image and detail_fields.image_url:
                fix["image_url"] = detail_fields.image_url
                print(f"Fixed image from detail page: {asin}")
                fixed_any = True
                if reason == "new_asin":
                    new_asin_image_fixed += 1
            failure_reason = _detail_fallback_failure_reason(
                status=fix["detail_page_status"],
                error=fix["detail_error"],
                needs_title=needs_title,
                needs_image=needs_image,
                detail_title=detail_fields.title,
                detail_image_url=detail_fields.image_url,
            )
            if failure_reason:
                fix["detail_error"] = failure_reason
                _save_failed_detail_artifacts(asin, html, screenshot, debug_html_dir, screenshot_dir)
                print(f"Failed detail fallback: {asin} - {failure_reason}")
            elif fixed_any and fix["detail_page_status"] == "ok":
                fix["detail_error"] = ""
            fixes_by_asin[asin] = fix

        if index < len(candidates):
            polite_sleep(detail_delay)

    print(f"Detail title/image fixes applied: {len(fixes_by_asin)}/{len(candidates)}")
    if detail_cache_path is not None:
        update_detail_cache_from_fixes(detail_cache_path, detail_cache, candidates, fixes_by_asin)
    print(f"Detail pages fetched: {len(candidates)}")
    print(f"Detail pages skipped from cache: {selection.skipped_from_cache}")
    print(f"New ASINs: {selection.new_asins}")
    print(f"New ASINs found: {selection.new_asins}")
    print(f"New ASINs detail fetched: {selection.new_asins_detail_fetched}")
    print(f"New ASINs title fixed: {new_asin_title_fixed}")
    print(f"New ASINs image fixed: {new_asin_image_fixed}")
    return fixes_by_asin


def _fetch_detail_page_for_fix(
    fetcher: PlaywrightFetcher,
    url: str,
    detail_timeout: int = DEFAULT_DETAIL_TIMEOUT_SECONDS,
) -> tuple[str, str, str, bytes | None, str, dict[str, str]]:
    if hasattr(fetcher, "fetch_detail_page"):
        result = fetcher.fetch_detail_page(  # type: ignore[attr-defined]
            url,
            timeout=detail_timeout,
            capture_screenshot=True,
        )
        return (
            str(getattr(result, "html", "") or ""),
            str(getattr(result, "status", "ok") or "ok"),
            str(getattr(result, "error", "") or ""),
            getattr(result, "screenshot", None),
            str(getattr(result, "url", url) or url),
            _rank_diagnostics_from_detail_result(result),
        )
    return fetcher.fetch(url), "ok", "", None, url, {}


def _detail_fallback_failure_reason(
    status: str,
    error: str,
    needs_title: bool,
    needs_image: bool,
    detail_title: str,
    detail_image_url: str,
) -> str:
    reasons: list[str] = []
    title_failed = needs_title and not is_valid_product_title(detail_title)
    image_failed = needs_image and not detail_image_url
    if (title_failed or image_failed) and status and status != "ok":
        reasons.append(error or status)
    if title_failed:
        if detail_title:
            reasons.append("invalid detail title")
        else:
            reasons.append("title unavailable")
    if image_failed:
        reasons.append("image unavailable")
    return "; ".join(dict.fromkeys(reason for reason in reasons if reason))


def _save_failed_detail_artifacts(
    asin: str,
    html: str,
    screenshot: bytes | None,
    debug_html_dir: Path,
    screenshot_dir: Path,
) -> None:
    if html:
        html_path = debug_html_dir / f"detail_failed_{asin}.html"
        ensure_parent(html_path)
        html_path.write_text(html, encoding="utf-8", errors="replace")
    if screenshot:
        screenshot_path = screenshot_dir / f"detail_failed_{asin}.png"
        ensure_parent(screenshot_path)
        screenshot_path.write_bytes(screenshot)


def apply_detail_fixes(rows: list[dict[str, str]], fixes_by_asin: dict[str, dict[str, str]]) -> int:
    updated = 0
    for row in rows:
        ensure_detail_fix_fields(row)
        ensure_category_rank_fields(row)
        fix = fixes_by_asin.get(_row_asin(row))
        if not fix:
            continue
        changed = False
        for field in (
            "detail_fetched_reason",
            "detail_page_status",
            "detail_title_found",
            "detail_image_found",
            "detail_error",
            "detail_bsr_found",
            "detail_bsr_error",
        ):
            if field in fix and row.get(field, "") != fix.get(field, ""):
                row[field] = fix.get(field, "")
                changed = True
        if _merge_detail_category_rank_fields(row, fix):
            changed = True
        if fix.get("title") and row.get("title", "") != fix["title"]:
            row["raw_title"] = row.get("raw_title", "") or row.get("title", "")
            row["title"] = fix["title"]
            row["title_source"] = "detail_page"
            row["title_fixed"] = "true"
            row.update(classify_pod_row(row))
            row.update(
                classify_niche(
                    title=row.get("title", ""),
                    category=row.get("category", ""),
                    source_name=row.get("source_name", ""),
                    pod_type=row.get("pod_type", ""),
                    pod_reason=row.get("pod_reason", ""),
                )
            )
            changed = True
        if fix.get("image_url") and row.get("image_url", "") != fix["image_url"]:
            row["image_url"] = fix["image_url"]
            row["image_source"] = "detail_page"
            row["image_fixed"] = "true"
            changed = True
        if changed:
            updated += 1
    return updated


def _merge_detail_category_rank_fields(row: dict[str, str], fix: dict[str, str]) -> bool:
    if not has_extracted_bsr(fix):
        return False
    return _apply_bsr_fields(row, fix, asin=_row_asin(row), overwrite=True)


def has_extracted_bsr(fields: dict[str, str]) -> bool:
    return any(
        (fields.get(field, "") or "").strip()
        for field in (
            "category_ranks_raw",
            "raw_bsr_block",
            "primary_bsr_rank",
            "primary_bsr_category",
            "sub_bsr_rank",
            "sub_bsr_category",
            "bsr_rank",
            "bsr_category",
            "all_bsr_ranks",
        )
    )


def _detail_fix_candidates(
    rows: list[dict[str, str]],
    max_detail_fixes: int,
    *,
    refresh_bsr: bool = False,
) -> list[dict[str, str]]:
    return _select_detail_fix_candidates(
        rows,
        max_detail_fixes,
        detail_cache={},
        detail_cache_enabled=False,
        skip_fixed_details=False,
        refresh_bsr=refresh_bsr,
        refresh_all_details=False,
    ).candidates


def _select_detail_fix_candidates(
    rows: list[dict[str, str]],
    max_detail_fixes: int,
    *,
    detail_cache: dict[str, dict[str, str]],
    detail_cache_enabled: bool = True,
    skip_fixed_details: bool = True,
    refresh_bsr: bool = False,
    refresh_all_details: bool = False,
) -> DetailCandidateSelection:
    limit = max(0, max_detail_fixes)
    if limit == 0:
        return DetailCandidateSelection(candidates=[], reasons_by_asin={})
    candidate_entries: list[tuple[tuple[int, int, int, str], dict[str, str], str]] = []
    reasons_by_asin: dict[str, str] = {}
    seen_asins: set[str] = set()
    skipped_from_cache = 0
    new_asins = 0
    new_asins_detail_fetched = 0
    candidate_rows = sorted(rows, key=_detail_refresh_candidate_key) if (refresh_bsr or refresh_all_details) else rows
    for row in candidate_rows:
        ensure_detail_fix_fields(row)
        ensure_category_rank_fields(row)
        asin = _row_asin(row)
        if not is_asin(asin) or asin in seen_asins:
            continue
        seen_asins.add(asin)
        cache_entry = detail_cache.get(asin)
        is_new_today = _is_new_asin_today(row)
        is_new_to_cache = detail_cache_enabled and cache_entry is None
        is_new_asin = is_new_today or is_new_to_cache
        if is_new_asin:
            new_asins += 1
        if is_new_today and not refresh_bsr and not refresh_all_details and _new_asin_detail_complete(row, cache_entry):
            skipped_from_cache += 1
            continue
        if (
            detail_cache_enabled
            and skip_fixed_details
            and cache_entry is not None
            and _detail_cache_is_complete(cache_entry)
            and not refresh_bsr
            and not refresh_all_details
        ):
            print(f"Detail skipped from cache: {asin}")
            skipped_from_cache += 1
            continue
        reason = _detail_fetch_reason(
            row,
            is_new_asin=is_new_asin,
            refresh_bsr=refresh_bsr,
            refresh_all_details=refresh_all_details,
        )
        if not reason:
            continue
        candidate_entries.append((_detail_fix_priority_key(row, reason), row, reason))
    candidates: list[dict[str, str]] = []
    for _, row, reason in sorted(candidate_entries, key=lambda entry: entry[0])[:limit]:
        asin = _row_asin(row)
        candidates.append(row)
        reasons_by_asin[asin] = reason
        if reason == "new_asin":
            new_asins_detail_fetched += 1
    return DetailCandidateSelection(
        candidates=candidates,
        reasons_by_asin=reasons_by_asin,
        skipped_from_cache=skipped_from_cache,
        new_asins=new_asins,
        new_asins_detail_fetched=new_asins_detail_fetched,
    )


def _detail_fetch_reason(
    row: dict[str, str],
    *,
    is_new_asin: bool,
    refresh_bsr: bool,
    refresh_all_details: bool,
) -> str:
    if refresh_all_details:
        return "refresh_all_details"
    if refresh_bsr:
        return "refresh_bsr"
    if is_new_asin:
        return "new_asin"
    reasons: list[str] = []
    if _needs_title_fix(row):
        reasons.append("missing_or_invalid_title")
    if _needs_image_fix(row):
        reasons.append("missing_image")
    bsr_reason = _bsr_refresh_reason(row)
    if bsr_reason:
        reasons.append(bsr_reason)
    return ",".join(reasons)


def _detail_fix_priority_key(row: dict[str, str], reason: str) -> tuple[int, int, int, str]:
    new_asin = reason == "new_asin" or _is_new_asin_today(row)
    top = _is_top_opportunity(row)
    needs_title_or_image = _needs_title_fix(row) or _needs_image_fix(row)
    missing_bsr = bool(_bsr_refresh_reason(row))
    if new_asin and needs_title_or_image:
        bucket = 0
    elif new_asin and missing_bsr:
        bucket = 1
    elif _is_missing_seller_preview_row(row):
        bucket = 2
    elif top and needs_title_or_image:
        bucket = 3
    elif top and missing_bsr:
        bucket = 4
    else:
        bucket = 5
    display_rank = _display_rank_value(row)
    opportunity_score = _to_int(row.get("opportunity_score", "")) or 0
    return (bucket, display_rank, -opportunity_score, _row_asin(row))


def _is_new_asin_today(row: dict[str, str]) -> bool:
    return (row.get("_new_asin_today", "") or "").strip().lower() == "true"


def _is_top_opportunity(row: dict[str, str]) -> bool:
    if (row.get("_top_opportunity", "") or "").strip().lower() == "true":
        return True
    return bool((row.get("alert_type", "") or "").strip())


def _new_asin_detail_complete(row: dict[str, str], cache_entry: dict[str, str] | None) -> bool:
    return (
        cache_entry is not None
        and is_valid_product_title(row.get("title", ""))
        and bool((row.get("image_url", "") or "").strip())
        and not _bsr_refresh_reason(row)
    )


def _detail_refresh_candidate_key(row: dict[str, str]) -> tuple[int, int, str, int, int, str]:
    display_rank = _display_rank_value(row)
    missing_bsr = 0 if not has_extracted_bsr(row) else 1
    opportunity_score = _to_int(row.get("opportunity_score", "")) or 0
    seller_preview_missing = _is_missing_seller_preview_row(row)
    return (
        0 if seller_preview_missing else 1,
        display_rank,
        _seller_identity(row) if seller_preview_missing else "",
        missing_bsr,
        -opportunity_score,
        _row_asin(row),
    )


def _to_int(value: str) -> int | None:
    try:
        return int(float(str(value or "").replace(",", "")))
    except (TypeError, ValueError):
        return None


def _needs_title_fix(row: dict[str, str]) -> bool:
    return not is_valid_product_title(row.get("title", ""))


def _needs_image_fix(row: dict[str, str]) -> bool:
    return not row.get("image_url", "").strip()


def _category_rank_candidates(rows: list[dict[str, str]], max_detail_pages: int) -> list[dict[str, str]]:
    limit = max(0, max_detail_pages)
    if limit == 0:
        return []
    candidates: list[dict[str, str]] = []
    seen_asins: set[str] = set()
    for row in rows:
        asin = _row_asin(row)
        if not is_asin(asin) or asin in seen_asins:
            continue
        seen_asins.add(asin)
        candidates.append(row)
        if len(candidates) >= limit:
            break
    return candidates


def _category_rank_priority_rows(
    product_rows: list[dict[str, str]],
    opportunity_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    seller_preview_rows = sorted(
        (row for row in product_rows if _is_missing_seller_preview_row(row)),
        key=lambda row: (_display_rank_value(row), _seller_identity(row), _row_asin(row)),
    )
    return [*seller_preview_rows, *opportunity_rows]


def _row_asin(row: dict[str, str]) -> str:
    return row.get("asin", "").strip().upper()


def fetch_with_retries(
    fetcher: PlaywrightFetcher,
    source: Source,
    screenshot_path: Path | None,
    error_screenshot_path: Path | None,
    retries: int,
    delay: float,
    scroll: bool = False,
    max_scrolls: int = 8,
    scroll_wait_ms: int = 1500,
) -> str:
    last_error: FetchError | BotCheckError | None = None
    attempts = max(0, retries) + 1
    for attempt in range(1, attempts + 1):
        try:
            return fetcher.fetch(
                source.url,
                screenshot_path=screenshot_path,
                error_screenshot_path=error_screenshot_path,
                scroll=scroll,
                max_scrolls=max_scrolls,
                scroll_wait_ms=scroll_wait_ms,
            )
        except (BotCheckError, FetchError) as exc:
            last_error = exc
            if isinstance(exc, BotCheckError) or attempt >= attempts:
                break
            print(f"  retry {attempt}/{attempts - 1}: {exc}")
            polite_sleep(delay)
    if last_error is None:
        raise FetchError("Unknown Playwright fetch failure")
    raise last_error


def fetch_pages_with_retries(
    fetcher: PlaywrightFetcher,
    source: Source,
    screenshot_path: Path | None,
    error_screenshot_path: Path | None,
    retries: int,
    delay: float,
    scroll: bool = False,
    max_scrolls: int = 8,
    scroll_wait_ms: int = 1500,
    max_pages: int = 1,
    capture_first_page_screenshot: bool = False,
) -> list[FetchedPage]:
    last_error: FetchError | BotCheckError | None = None
    attempts = max(0, retries) + 1
    for attempt in range(1, attempts + 1):
        try:
            return fetcher.fetch_pages(
                source.url,
                screenshot_path=screenshot_path,
                error_screenshot_path=error_screenshot_path,
                scroll=scroll,
                max_scrolls=max_scrolls,
                scroll_wait_ms=scroll_wait_ms,
                max_pages=max_pages,
                capture_first_page_screenshot=capture_first_page_screenshot,
                source_type=source.source_type,
            )
        except (BotCheckError, FetchError) as exc:
            last_error = exc
            if isinstance(exc, BotCheckError) or attempt >= attempts:
                break
            print(f"  retry {attempt}/{attempts - 1}: {exc}")
            polite_sleep(delay)
    if last_error is None:
        raise FetchError("Unknown Playwright fetch failure")
    raise last_error


def build_source_scan_report_row(
    source: Source,
    pages: list[FetchedPage],
    products: list[dict[str, str]],
    *,
    max_pages: int,
    elapsed_seconds: float,
    stop_reason: str = "",
) -> dict[str, str]:
    page_asins: list[str] = []
    for page in pages:
        page_asins.extend(_page_product_asins(page))

    collected_asins = {asin for asin in page_asins if asin}
    duplicates = max(0, len(page_asins) - len(collected_asins))
    raw_total_text = _source_raw_total_text(pages)
    expected_total = parse_amazon_reported_total(raw_total_text)
    parsed_asins = {
        asin
        for asin in (_row_asin(product) for product in products)
        if asin
    }
    collected_products = len(collected_asins)
    filtered = max(0, len(collected_asins - parsed_asins))
    final_stop_reason = stop_reason or _source_stop_reason(pages)
    expected_top_products = _expected_top_products(source.source_type, max_pages, expected_total)
    can_compute_top_coverage = expected_top_products is not None and (
        expected_total is not None or _source_type_key(source.source_type) in RANKING_PAGINATED_SOURCE_TYPES
    )
    if not can_compute_top_coverage:
        top_page_coverage = None
        full_coverage = None
        status = "UNKNOWN"
    else:
        top_page_coverage = (
            collected_products / expected_top_products
            if expected_top_products
            else None
        )
        full_coverage = (collected_products / expected_total) if expected_total else None
        if top_page_coverage is not None and top_page_coverage < 0.9:
            status = "LOW_TOP_PAGE_COVERAGE"
        elif full_coverage is not None and full_coverage < 0.9:
            status = "PARTIAL_BY_DESIGN"
        else:
            status = "OK"

    return {
        "source_name": source.display_name,
        "source_type": source.source_type,
        "raw_total_text": raw_total_text,
        "max_pages": str(max(1, int(max_pages))),
        "expected_products": str(expected_total) if expected_total is not None else "",
        "expected_top_products": str(expected_top_products) if expected_top_products is not None else "",
        "collected_products": str(collected_products),
        "top_page_coverage": _format_coverage(top_page_coverage),
        "full_coverage": _format_coverage(full_coverage),
        "status": status,
        "pages_scanned": str(len(pages)),
        "next_clicks": str(max(0, len(pages) - 1)),
        "duplicates": str(duplicates),
        "filtered": str(filtered),
        "elapsed_seconds": f"{max(0.0, elapsed_seconds):.2f}",
        "final_url": pages[-1].url if pages else source.url,
        "stop_reason": final_stop_reason,
    }


def _expected_top_products(source_type: str, max_pages: int, expected_total: int | None) -> int | None:
    products_per_page = _source_products_per_page(source_type)
    if products_per_page <= 0:
        return expected_total
    configured_top_products = products_per_page * max(1, int(max_pages))
    if _source_type_key(source_type) in RANKING_PAGINATED_SOURCE_TYPES:
        return configured_top_products
    if expected_total is None:
        return configured_top_products
    return min(expected_total, configured_top_products)


def _source_raw_total_text(pages: list[FetchedPage]) -> str:
    for page in pages:
        raw_total_text = (page.raw_total_text or "").strip()
        if raw_total_text:
            return raw_total_text
    for page in pages:
        raw_total_text = extract_amazon_reported_total_text(page.html)
        if raw_total_text:
            return raw_total_text
    return ""


def _page_product_asins(page: FetchedPage) -> list[str]:
    if page.product_asins:
        return [asin for asin in (value.strip().upper() for value in page.product_asins) if asin]
    html = page.html or ""
    data_asins = [
        match.group(1).upper()
        for match in re.finditer(r"\bdata-asin=[\"'](B0[A-Z0-9]{8})[\"']", html, flags=re.IGNORECASE)
    ]
    if data_asins:
        return data_asins
    link_asins = [
        match.group(1).upper()
        for match in re.finditer(r"/(?:dp|gp/product|gp/aw/d)/(B0[A-Z0-9]{8})(?:[/?#\"']|$)", html, flags=re.IGNORECASE)
    ]
    return list(dict.fromkeys(link_asins))


def _duplicate_count(asins: list[str]) -> int:
    duplicates = 0
    seen: set[str] = set()
    for asin in asins:
        if asin in seen:
            duplicates += 1
        else:
            seen.add(asin)
    return duplicates


def _source_stop_reason(pages: list[FetchedPage]) -> str:
    if not pages:
        return "no_pages_fetched"
    last = pages[-1]
    return last.stop_reason or last.scroll_stop_reason or "completed"


def _format_coverage(ratio: float | None) -> str:
    if ratio is None:
        return ""
    return f"{max(0.0, ratio) * 100:.2f}%"


def save_unknown_total_artifacts(output_dir: Path, source: Source, pages: list[FetchedPage], timestamp: str) -> None:
    if not pages:
        return
    page = pages[0]
    artifact_dir = output_dir / "source_scan_unknown"
    base = f"{timestamp}_{slugify(source.display_name or source.source_name)}_unknown_total"
    html_path = artifact_dir / f"{base}.html"
    ensure_parent(html_path)
    html_path.write_text(page.html or "", encoding="utf-8")
    if page.screenshot:
        screenshot_file = artifact_dir / f"{base}.png"
        ensure_parent(screenshot_file)
        screenshot_file.write_bytes(page.screenshot)


def parse_source_pages(pages: list[FetchedPage], source: Source, fetched_at: str) -> list[dict[str, str]]:
    products: list[dict[str, str]] = []
    seen_asins: set[str] = set()
    for page in pages:
        page_products = parse_amazon_search_results(page.html, source, fetched_at, page.url)
        for product in page_products:
            asin = product.get("asin", "").strip().upper()
            if asin and asin in seen_asins:
                continue
            if asin:
                seen_asins.add(asin)
            _set_display_rank(product, len(products) + 1)
            products.append(product)
    return products


def _set_display_rank(product: dict[str, str], rank: int) -> None:
    value = str(rank)
    for field in ("display_rank", "display_order", "rank", "position"):
        product[field] = value


def write_master_snapshot(snapshot_dir: Path, master_snapshot_path: Path) -> str:
    write_csv(master_snapshot_path, build_master_snapshot(snapshot_dir), PRODUCT_FIELDS)
    return str(master_snapshot_path)


def write_trend_outputs(
    output_dir: Path,
    snapshot_dir: Path = DEFAULT_SNAPSHOT_DIR,
    sources: list[Source] | None = None,
    include_non_pod: bool = False,
    category_rank_fetcher: PlaywrightFetcher | None = None,
    fetch_category_rank: bool = False,
    max_detail_pages: int = DEFAULT_MAX_DETAIL_PAGES,
    detail_fix_fetcher: PlaywrightFetcher | None = None,
    fix_missing_details: bool = False,
    fix_new_products: bool = False,
    max_detail_fixes: int = DEFAULT_MAX_DETAIL_FIXES,
    auto_fix_opportunity_details: bool = False,
    refresh_bsr: bool = False,
    skip_fixed_details: bool = True,
    refresh_all_details: bool = False,
    detail_delay: float = DEFAULT_DETAIL_DELAY_SECONDS,
    detail_timeout: int = DEFAULT_DETAIL_TIMEOUT_SECONDS,
) -> dict[str, str]:
    rank_trends_path = output_dir / "rank_trends.csv"
    product_trends_path = output_dir / "product_trends.csv"
    trend_alerts_path = output_dir / "trend_alerts.csv"
    lark_trend_alerts_path = output_dir / "lark_trend_alerts.csv"
    source_trends_path = output_dir / "source_trends.csv"
    seller_intelligence_path = output_dir / "seller_intelligence.csv"
    niche_intelligence_path = output_dir / "niche_intelligence.csv"
    historical_comparison_path = output_dir / "historical_comparison.csv"
    rank_audit_path = output_dir / "rank_audit.csv"
    detail_cache_path = output_dir / DETAIL_CACHE_FILENAME
    detail_cache = load_detail_cache(detail_cache_path)
    latest_snapshot_path = snapshot_paths(snapshot_dir)[-1] if snapshot_paths(snapshot_dir) else None
    products = read_csv(latest_snapshot_path) if latest_snapshot_path else []
    products = [
        ensure_detail_fix_fields(ensure_niche_fields(ensure_category_rank_fields(ensure_pod_fields(row))))
        for row in products
    ]
    normalize_source_identity_rows(products, sources)
    apply_category_rank_backfill(products, load_existing_category_rank_cache(output_dir, snapshot_dir))
    _log_debug_bsr_state("before cache merge", products)
    merge_detail_cache_into_rows(products, detail_cache, merge_bsr=not refresh_bsr)
    _log_debug_bsr_state("after cache merge", products)
    if products:
        write_latest_products_csv(output_dir / "latest_products.csv", products)
        write_csv(output_dir / "today_snapshot.csv", products, PRODUCT_FIELDS)
        if latest_snapshot_path is not None:
            write_csv(latest_snapshot_path, products, PRODUCT_FIELDS)
    historical_rows = build_historical_comparison(snapshot_dir, latest_snapshot_path, sources)
    if products:
        apply_display_rank_metrics(products, historical_rows)
        if latest_snapshot_path is not None:
            write_csv(latest_snapshot_path, products, PRODUCT_FIELDS)
        write_latest_products_csv(output_dir / "latest_products.csv", products)
        write_csv(output_dir / "today_snapshot.csv", products, PRODUCT_FIELDS)
    trend_alerts = build_trend_alerts(historical_rows)
    lark_trend_alerts = build_lark_trend_alerts(
        historical_rows,
        source_metadata=sources,
        include_non_pod=include_non_pod,
    )
    mark_detail_candidate_context(
        products,
        historical_rows=historical_rows,
        top_rows=lark_trend_alerts,
        previous_master_rows=[],
        scan_date=(latest_snapshot_path.stem[:10] if latest_snapshot_path is not None else now_utc().date().isoformat()),
    )

    if fix_missing_details or fix_new_products or auto_fix_opportunity_details or refresh_bsr or refresh_all_details:
        detail_candidate_rows = products if (fix_missing_details or fix_new_products or refresh_bsr or refresh_all_details) else lark_trend_alerts
        if detail_fix_fetcher is None:
            print("Warning: detail refresh requested but no browser is available; skipping detail pages.")
        else:
            fixes_by_asin = fetch_detail_fixes_for_products(
                detail_fix_fetcher,
                detail_candidate_rows,
                max_detail_fixes=max_detail_fixes,
                detail_delay=detail_delay,
                detail_timeout=detail_timeout,
                refresh_bsr=refresh_bsr,
                detail_cache_path=detail_cache_path,
                skip_fixed_details=skip_fixed_details,
                refresh_all_details=refresh_all_details,
            )
            if fixes_by_asin:
                apply_detail_fixes(products, fixes_by_asin)
                detail_cache = update_detail_cache_from_rows(detail_cache_path, detail_cache, products, fixes_by_asin)
                if latest_snapshot_path is not None:
                    write_csv(latest_snapshot_path, products, PRODUCT_FIELDS)
                write_latest_products_csv(output_dir / "latest_products.csv", products)
                write_csv(output_dir / "today_snapshot.csv", products, PRODUCT_FIELDS)
                historical_rows = build_historical_comparison(snapshot_dir, latest_snapshot_path, sources)
                apply_display_rank_metrics(products, historical_rows)
                if latest_snapshot_path is not None:
                    write_csv(latest_snapshot_path, products, PRODUCT_FIELDS)
                write_latest_products_csv(output_dir / "latest_products.csv", products)
                write_csv(output_dir / "today_snapshot.csv", products, PRODUCT_FIELDS)
                trend_alerts = build_trend_alerts(historical_rows)
                lark_trend_alerts = build_lark_trend_alerts(
                    historical_rows,
                    source_metadata=sources,
                    include_non_pod=include_non_pod,
                )

    if fetch_category_rank:
        if category_rank_fetcher is None:
            print("Warning: --fetch-category-rank requested but no browser is available; skipping detail pages.")
        else:
            ranks_by_asin = fetch_category_ranks_for_opportunities(
                category_rank_fetcher,
                lark_trend_alerts,
                max_detail_pages=max_detail_pages,
                detail_delay=detail_delay,
                detail_timeout=detail_timeout,
                product_rows=products,
            )
            if ranks_by_asin:
                apply_category_ranks(products, ranks_by_asin)
                if latest_snapshot_path is not None:
                    write_csv(latest_snapshot_path, products, PRODUCT_FIELDS)
                write_latest_products_csv(output_dir / "latest_products.csv", products)
                write_csv(output_dir / "today_snapshot.csv", products, PRODUCT_FIELDS)
                historical_rows = build_historical_comparison(snapshot_dir, latest_snapshot_path, sources)
                apply_display_rank_metrics(products, historical_rows)
                if latest_snapshot_path is not None:
                    write_csv(latest_snapshot_path, products, PRODUCT_FIELDS)
                write_latest_products_csv(output_dir / "latest_products.csv", products)
                write_csv(output_dir / "today_snapshot.csv", products, PRODUCT_FIELDS)
                trend_alerts = build_trend_alerts(historical_rows)
                lark_trend_alerts = build_lark_trend_alerts(
                    historical_rows,
                    source_metadata=sources,
                    include_non_pod=include_non_pod,
                )

    product_trends = build_rank_trends(snapshot_dir, sources)
    product_history_rows = build_product_history_rows(snapshot_dir, sources)
    seller_intelligence = build_seller_intelligence(historical_rows, sources)
    niche_intelligence = build_niche_intelligence(historical_rows, include_non_pod=include_non_pod)
    write_csv(
        historical_comparison_path,
        historical_rows,
        HISTORICAL_COMPARISON_FIELDS,
    )
    write_rank_audit(output_dir, products)
    write_csv(rank_trends_path, product_trends, RANK_TREND_FIELDS)
    write_csv(product_trends_path, product_trends, RANK_TREND_FIELDS)
    write_csv(trend_alerts_path, trend_alerts, TREND_ALERT_FIELDS)
    write_csv(niche_intelligence_path, niche_intelligence, NICHE_INTELLIGENCE_FIELDS)
    artifact_paths = write_lark_opportunity_artifacts(
        output_dir,
        lark_trend_alerts,
        all_opportunities=trend_alerts,
        products=products,
        seller_rows=seller_intelligence,
        niche_rows=niche_intelligence,
        product_history_rows=product_history_rows,
        include_non_pod=include_non_pod,
    )
    write_csv(source_trends_path, build_source_trends(snapshot_dir, sources), SOURCE_TREND_FIELDS)
    write_csv(seller_intelligence_path, seller_intelligence, SELLER_INTELLIGENCE_FIELDS)
    return {
        "rank_trends": str(rank_trends_path),
        "product_trends": str(product_trends_path),
        "trend_alerts": str(trend_alerts_path),
        "lark_trend_alerts": artifact_paths["lark_trend_alerts"],
        "priority_board": artifact_paths["priority_board"],
        "priority_board_csv": artifact_paths["priority_board_csv"],
        "product_discovery": artifact_paths["product_discovery"],
        "products": artifact_paths["products"],
        "competitor": artifact_paths["competitor"],
        "trend_explorer": artifact_paths["trend_explorer"],
        "product_detail": artifact_paths["product_detail"],
        "top_winners": artifact_paths["top_winners"],
        "new_breakouts": artifact_paths["new_breakouts"],
        "fast_movers": artifact_paths["fast_movers"],
        "new_releases": artifact_paths["new_releases"],
        "trends": artifact_paths["trends"],
        "database": artifact_paths["database"],
        "index": artifact_paths["index"],
        "image_gallery": artifact_paths["image_gallery"],
        "top_opportunities": artifact_paths["top_opportunities"],
        "all_opportunities": artifact_paths["all_opportunities"],
        "new_products": artifact_paths["new_products"],
        "rising_products": artifact_paths["rising_products"],
        "seller_intelligence_page": artifact_paths["seller_intelligence"],
        "niche_intelligence_page": artifact_paths["niche_intelligence"],
        "source_explorer": artifact_paths["source_explorer"],
        "non_pod_excluded": artifact_paths["non_pod_excluded"],
        "source_trends": str(source_trends_path),
        "seller_intelligence": str(seller_intelligence_path),
        "niche_intelligence": str(niche_intelligence_path),
        "historical_comparison": str(historical_comparison_path),
        "rank_audit": str(rank_audit_path),
    }


def write_daily_workbook(
    workbook_path: Path,
    products: list[dict[str, str]],
    historical_rows: list[dict[str, str]],
    source_summaries: list[dict[str, str]],
    errors: list[dict[str, str]],
    source_metadata: list[Source] | None = None,
) -> None:
    summary_rows = build_executive_summary(products, historical_rows, source_summaries, errors)
    seller_intelligence = build_seller_intelligence(historical_rows, source_metadata)
    niche_intelligence = build_niche_intelligence(historical_rows)
    write_workbook(
        workbook_path,
        [
            ("Executive Summary", summary_rows, EXECUTIVE_SUMMARY_FIELDS),
            ("New Wins", filter_by_classification(historical_rows, "new_win"), HISTORICAL_COMPARISON_FIELDS),
            ("Winners", filter_by_classification(historical_rows, "winner"), HISTORICAL_COMPARISON_FIELDS),
            ("Rising", filter_by_classification(historical_rows, "rising"), HISTORICAL_COMPARISON_FIELDS),
            ("Declining", filter_by_classification(historical_rows, "declining"), HISTORICAL_COMPARISON_FIELDS),
            ("Seller Intelligence", seller_intelligence, SELLER_INTELLIGENCE_FIELDS),
            ("Niche Intelligence", niche_intelligence, NICHE_INTELLIGENCE_FIELDS),
            ("Raw Snapshot", products, PRODUCT_FIELDS),
        ],
    )


def resolve_sources_path(path_value: str | None) -> Path:
    if path_value:
        return Path(path_value)
    for candidate in DEFAULT_SOURCE_CANDIDATES:
        if candidate.exists():
            return candidate
    return DEFAULT_SOURCE_CANDIDATES[0]


def read_sources_if_available(path: Path, include_inactive: bool = False) -> list[Source]:
    try:
        return read_sources(path, include_inactive=include_inactive)
    except FileNotFoundError:
        return []


def find_saved_html(html_dir: Path | None, source: Source) -> Path | None:
    if html_dir is None:
        return None
    slugs = list(
        dict.fromkeys(
            slug
            for slug in (
                slugify(source.source_name),
                slugify(source.display_name),
                slugify(source.category, fallback="category"),
                slugify(source.seller_name),
            )
            if slug
        )
    )
    slug = slugs[0]
    category_slug = slugify(source.category, fallback="category")
    candidates = [
        html_dir / f"{slug}.html",
        html_dir / f"{slug}-{category_slug}.html",
        html_dir / f"{source.source_type}-{slug}.html",
        html_dir / f"source-{source.row_number}.html",
        html_dir / f"source-{source.row_number}-{source.source_type}.html",
        html_dir / f"{source.row_number}.html",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    for slug in slugs:
        matches = sorted(html_dir.glob(f"*_{slug}.html"), key=lambda path: (path.stat().st_mtime, path.name), reverse=True)
        if matches:
            return matches[0].resolve()
    return None
