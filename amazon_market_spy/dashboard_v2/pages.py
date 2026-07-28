from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from html import escape
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

from .components import (
    bar_list,
    compact_content_card,
    compact_filter_row,
    data_table,
    dropdown_button,
    empty_state,
    filter_chip,
    ghost_button,
    kpi_card,
    page_header,
    product_image_src,
    primary_button,
    quick_preview_shell,
    render_app_shell,
    search_input,
    secondary_button,
    section_header,
    saved_view_item,
    status_badge,
    tone_name,
)


PRODUCT_EXPLORER_DETAIL_DIR = "product_explorer_details"


def render_data_error_page(title: str, active_key: str, message: str) -> str:
    body = f"""
{page_header(title, "Dashboard V2 presentation data is unavailable")}
    <section class="panel">
{empty_state("Dashboard data unavailable", message)}
    </section>
"""
    return render_app_shell(title=title, active_key=active_key, body=body)


def render_morning_brief(data: dict[str, object]) -> str:
    products = data["products"]
    dataset_info = _dataset_info(data)
    research_queue = _home_research_today(products)
    market_pulse = _home_market_pulse(products)
    data_status = _home_compact_data_status(dataset_info, products)
    overview = _home_dataset_overview(dataset_info, products)
    evidence_cards = "\n".join(_home_evidence_card(products, key, label, tone, family) for key, label, tone, family in _home_signal_definitions())
    coverage_cards = _home_coverage_cards(products)
    activity = _home_activity_sections(products)
    quality = _home_data_quality(products, dataset_info)
    calibration = _home_calibration_status(dataset_info)
    scripts = f"""  <script>
{_home_research_preview_script()}
  </script>
"""
    body = f"""
{page_header("Dashboard Home", "Daily evidence, coverage, and dataset health for Product Team research", secondary_button("Analytics Frozen"))}
{section_header("Research Today", "What should Product Team investigate first?")}
    <div class="research-queue-grid minimal-queue-grid" data-home-research-queue>
{research_queue}
    </div>
{section_header("Market Pulse", "Compact movement and validation snapshot")}
    <section class="market-pulse-grid" aria-label="Market pulse">
{market_pulse}
    </section>
{section_header("Data Status", "Compact generation and coverage status")}
    <section class="data-status-grid" aria-label="Data status">
{data_status}
    </section>
    <details class="panel data-details-panel" data-home-data-details>
      <summary>Data Details</summary>
{section_header("Evidence Overview", "Click a card to open Product Explorer with the matching explicit evidence filter")}
      <section class="evidence-card-grid" aria-label="Evidence overview">
{evidence_cards}
      </section>
{section_header("Secondary Activity Lists", "Deduplicated representative products from existing source-aware evidence fields")}
      <div class="home-activity-grid">
{activity}
      </div>
{section_header("Dataset Overview", "Current presentation dataset and source-aware observation coverage")}
      <section class="dashboard-grid" aria-label="Dataset overview">
{overview}
      </section>
{section_header("Coverage Overview", "No-data products are counted separately from false evidence")}
      <section class="dashboard-grid" aria-label="Coverage overview">
{coverage_cards}
      </section>
{section_header("Data Quality", "Informational only; no data is modified")}
      <div class="data-quality-list">
{quality}
      </div>
{calibration}
{section_header("Dataset Information", "Presentation metadata")}
      <div class="data-quality-list">
        {_quality_item("Dataset products", _fmt_int(dataset_info.get("presentation_products", len(products))))}
        {_quality_item("Source-aware Observations", _fmt_int(dataset_info.get("source_aware_observations", 0)))}
        {_quality_item("Marketplaces", ", ".join(dataset_info.get("marketplaces", []) or []) or _missing())}
        {_quality_item("Generated", str(dataset_info.get("generated_at", _missing())))}
        {_quality_item("Dashboard version", str(dataset_info.get("dashboard_version", "Dashboard V2")))}
        {_quality_item("Analytics note", str(dataset_info.get("analytics_freeze_note", "")))}
      </div>
    </details>
    <span id="dataset-information"></span>
"""
    return render_app_shell(title="Dashboard Home", active_key="morning_brief", body=body, scripts=scripts, dataset_info=dataset_info)


def render_product_explorer(data: dict[str, object]) -> str:
    products = _product_explorer_products(data)
    first_product = products[0] if products else {}
    product_json = _safe_json_script(_product_index_payload(products))
    table = f"""    <div class="table-shell product-table-shell">
      <table class="product-table">
        <thead>
          <tr>
            <th scope="col" data-column-header="select" data-optional-column hidden><input type="checkbox" data-select-page aria-label="Select all products on current page"></th>
            <th scope="col" data-column-header="image" data-optional-column hidden>Image</th>
            <th scope="col" aria-sort="none"><button class="sort-button" type="button" data-sort-key="title">Product <span data-sort-indicator aria-hidden="true"></span></button></th>
            <th scope="col" data-column-header="why">Why It Matters</th>
            <th scope="col" aria-sort="none" data-column-header="momentum"><button class="sort-button" type="button" data-sort-key="momentum">Momentum <span data-sort-indicator aria-hidden="true"></span></button></th>
            <th scope="col" data-column-header="market_proof">Proof</th>
            <th scope="col" aria-sort="none" data-column-header="seller" data-optional-column hidden><button class="sort-button" type="button" data-sort-key="seller">Seller <span data-sort-indicator aria-hidden="true"></span></button></th>
            <th scope="col" data-column-header="product_type" data-optional-column hidden>Product Type</th>
            <th scope="col" aria-sort="none" data-column-header="primary_evidence" data-optional-column hidden><button class="sort-button" type="button" data-sort-key="evidence_count">Primary Evidence <span data-sort-indicator aria-hidden="true"></span></button></th>
            <th scope="col" aria-sort="none" data-column-header="idea" data-optional-column hidden><button class="sort-button" type="button" data-sort-key="idea">Idea <span data-sort-indicator aria-hidden="true"></span></button></th>
            <th scope="col" aria-sort="none" data-column-header="legacy_score" data-optional-column hidden><button class="sort-button" type="button" data-sort-key="winner_score">Legacy Score <span data-sort-indicator aria-hidden="true"></span></button></th>
            <th scope="col" aria-sort="none" data-column-header="growth" data-optional-column hidden><button class="sort-button" type="button" data-sort-key="growth">Growth <span data-sort-indicator aria-hidden="true"></span></button></th>
            <th scope="col" aria-sort="none" data-column-header="reviews" data-optional-column hidden><button class="sort-button" type="button" data-sort-key="reviews">Reviews <span data-sort-indicator aria-hidden="true"></span></button></th>
            <th scope="col" aria-sort="none" data-column-header="price" data-optional-column hidden><button class="sort-button" type="button" data-sort-key="price">Price <span data-sort-indicator aria-hidden="true"></span></button></th>
            <th scope="col" data-column-header="source" data-optional-column hidden>Source</th>
            <th scope="col">Open</th>
          </tr>
        </thead>
        <tbody data-product-tbody>
        </tbody>
      </table>
    </div>"""
    body = f"""
{page_header("Product Explorer", "Search, filter, inspect, and open source-backed product evidence", secondary_button("Press / to search"))}
    <div class="product-workspace" data-product-workspace>
      <aside class="panel filter-panel" aria-label="Product filters" data-filter-panel>
        <section>
          <h2>Preset</h2>
          <div class="preset-list" data-preset-list>
            {''.join(_product_preset_rows(products))}
          </div>
        </section>
        <section>
          <h2>Product Type</h2>
          {_single_category_filter_control("product_type", "Product Type")}
        </section>
        <section>
          <h2>POD Product</h2>
          {_pod_filter_control()}
        </section>
        <section>
          <h2>Seller</h2>
          {_single_category_filter_control("seller", "Seller")}
        </section>
        <details class="more-filters-panel" data-more-filters>
          <summary>More Filters</summary>
          <section>
            <h2>Saved Views</h2>
            <div class="saved-view-list">
              {''.join(_saved_view_rows(products))}
            </div>
          </section>
          <section>
            <h2>Legacy Signals</h2>
            <div class="filter-row-list">
              {''.join(_legacy_signal_rows(products))}
            </div>
          </section>
          <section>
            <h2>Evidence and Source Filters</h2>
            {_evidence_filter_controls(products)}
          </section>
          <section>
            <h2>Quick Filters</h2>
            <div class="filter-row-list">
              {''.join(_quick_filter_rows(products))}
            </div>
          </section>
          <section>
            <h2>Advanced Filters</h2>
            {_advanced_filter_controls(exclude={"product_type", "seller"})}
          </section>
        </details>
      </aside>
      <section class="panel" aria-label="Product workspace">
        <div class="toolbar">
          <div class="control-group">{search_input("Search products", "Search products, sellers, ideas, or ASINs", "product-search")}</div>
          <div class="toolbar-actions">
            <div class="control-group">
              {_sort_controls()}
              <div class="column-menu-wrap">
                <button class="btn btn-secondary btn-dropdown" type="button" data-columns-toggle aria-expanded="false">Columns</button>
                <div class="column-menu" data-column-menu hidden>
                  <label><input type="checkbox" data-column-toggle="select"> Row Select</label>
                  <label><input type="checkbox" data-column-toggle="image"> Image</label>
                  <label><input type="checkbox" data-column-toggle="seller"> Seller</label>
                  <label><input type="checkbox" data-column-toggle="product_type"> Product Type</label>
                  <label><input type="checkbox" data-column-toggle="primary_evidence"> Primary Evidence</label>
                  <label><input type="checkbox" data-column-toggle="idea"> Idea</label>
                  <label><input type="checkbox" data-column-toggle="legacy_score"> Legacy Score</label>
                  <label><input type="checkbox" data-column-toggle="growth"> Growth</label>
                  <label><input type="checkbox" data-column-toggle="reviews"> Reviews</label>
                  <label><input type="checkbox" data-column-toggle="price"> Price</label>
                  <label><input type="checkbox" data-column-toggle="source"> Source</label>
                </div>
              </div>
              {dropdown_button("Density")}
            </div>
            <span class="toolbar-divider" aria-hidden="true"></span>
            <div class="control-group">
              <button class="btn btn-secondary" type="button" data-clear-filters>Reset Filters</button>
            </div>
          </div>
        </div>
        <div class="product-results-meta">
          <p class="result-count" data-result-count aria-live="polite">Showing 0 of {len(products)} products</p>
          <p class="caption result-cap" data-result-cap hidden></p>
        </div>
        <p class="guidance-line" data-filter-guidance>Start with Research Today to find products with recent movement.</p>
        <p class="filter-text-summary" data-filter-text-summary hidden></p>
        <details class="compact-result-details">
          <summary>Result Details</summary>
          <div class="result-stats" data-result-stats>
            <span><strong data-stat-total>{len(products)}</strong> total</span>
            <span aria-live="polite"><strong data-stat-matching>0</strong> matching</span>
            <span><strong data-stat-sellers>0</strong> sellers</span>
            <span><strong data-stat-ideas>0</strong> ideas</span>
            <span><strong data-stat-types>0</strong> product types</span>
            <span><strong data-stat-seller-evidence>0</strong> seller evidence</span>
            <span><strong data-stat-best-seller-evidence>0</strong> Best Seller evidence</span>
            <span><strong data-stat-new-release-evidence>0</strong> New Release evidence</span>
            <span><strong data-stat-bsr-evidence>0</strong> BSR evidence</span>
          </div>
        </details>
        <div class="active-filter-summary" data-active-filter-summary hidden>
          <div class="filter-chip-list" data-active-filter-chips></div>
          <button class="btn btn-ghost" type="button" data-clear-filters>Clear All</button>
        </div>
        <div class="selection-toolbar" data-selection-toolbar hidden>
          <strong data-selection-count>0 selected</strong>
          <span class="caption" data-hidden-selection-count hidden></span>
          <button class="btn btn-ghost" type="button" data-clear-selection>Clear Selection</button>
        </div>
{table if products else empty_state("No products available", "No product rows found in the presentation data.")}
        <div class="pagination-bar" data-pagination>
          <span class="caption" data-page-range>Showing 0 of 0 products</span>
          <div class="control-group">
            <label class="caption" for="product-page-size">Rows</label>
            <select id="product-page-size" class="select-input page-size-select" data-page-size aria-label="Rows per page">
              <option value="50">50</option>
              <option value="100" selected>100</option>
              <option value="200">200</option>
            </select>
            <button class="btn btn-ghost" type="button" data-page-action="first" aria-label="First page">First</button>
            <button class="btn btn-ghost" type="button" data-page-action="previous" aria-label="Previous page">Previous</button>
            <span class="caption" data-page-status>Page 1 of 1</span>
            <button class="btn btn-ghost" type="button" data-page-action="next" aria-label="Next page">Next</button>
            <button class="btn btn-ghost" type="button" data-page-action="last" aria-label="Last page">Last</button>
          </div>
        </div>
        <div class="empty-state product-filter-empty" data-filter-empty hidden>
          <div>
            <strong data-filter-empty-title>No products match the current search and filters.</strong>
            <p class="caption" data-filter-empty-caption>Adjust the search or remove filters to see products.</p>
            <button class="btn btn-secondary" type="button" data-clear-filters>Clear All Filters</button>
          </div>
        </div>
      </section>
{quick_preview_shell(first_product)}
    </div>
"""
    scripts = f"""  <script type="application/json" id="product-explorer-data">{product_json}</script>
  <script>
{_product_explorer_script()}
  </script>
"""
    return render_app_shell(title="Product Explorer", active_key="product_explorer", body=body, scripts=scripts, dataset_info=_dataset_info(data))


def clean_product_explorer_detail_assets(output_dir: Path) -> None:
    detail_dir = Path(output_dir) / PRODUCT_EXPLORER_DETAIL_DIR
    if not detail_dir.exists():
        return
    for path in detail_dir.glob("*.js"):
        path.unlink()


def write_product_explorer_detail_assets(output_dir: Path, data: dict[str, object]) -> list[dict[str, object]]:
    products = _product_explorer_products(data)
    if not isinstance(products, list):
        return []

    clean_product_explorer_detail_assets(output_dir)
    detail_dir = Path(output_dir) / PRODUCT_EXPLORER_DETAIL_DIR
    detail_dir.mkdir(parents=True, exist_ok=True)

    assets: list[dict[str, object]] = []
    for index, product in enumerate(products):
        if not isinstance(product, dict):
            continue
        product_id = _product_detail_id(product, index)
        relative_path = _product_detail_asset_path(product, index)
        detail_payload = _product_detail_record(product)
        script = (
            "window.AMS_PRODUCT_EXPLORER_DETAILS=window.AMS_PRODUCT_EXPLORER_DETAILS||{};"
            f"window.AMS_PRODUCT_EXPLORER_DETAILS[{json.dumps(product_id, ensure_ascii=True)}]="
            f"{_safe_json_script(detail_payload)};\n"
        )
        path = Path(output_dir) / relative_path
        path.write_text(script, encoding="utf-8")
        assets.append(
            {
                "label": "Product Explorer detail",
                "product_id": product_id,
                "filename": relative_path,
                "path": str(path),
                "size": path.stat().st_size,
            }
        )
    return assets


def render_competitor(data: dict[str, object]) -> str:
    products = data["products"]
    sellers = _seller_summaries(products)
    total_sellers = len(sellers)
    total_leaders = sum(row["seller_leaders"] for row in sellers)
    total_movers = sum(row["seller_movers"] for row in sellers)
    total_pushes = sum(row["seller_new_pushes"] for row in sellers)
    seller_json = _safe_json_script(sellers)
    table_rows = "\n".join(_seller_table_row(row) for row in sellers)
    table_html = f"""    <div class="table-shell">
      <table class="seller-table" data-seller-table>
        <thead>
          <tr>
            <th scope="col"><button class="sort-button" type="button" data-seller-sort="seller">Seller</button></th>
            <th scope="col"><button class="sort-button" type="button" data-seller-sort="activity">Activity</button></th>
            <th scope="col"><button class="sort-button" type="button" data-seller-sort="seller_new_pushes">New Pushes</button></th>
            <th scope="col"><button class="sort-button" type="button" data-seller-sort="seller_movers">Fast Movers</button></th>
            <th scope="col">Open</th>
          </tr>
        </thead>
        <tbody data-seller-tbody>{table_rows}</tbody>
      </table>
    </div>""" if sellers else empty_state("No competitors available", "No seller rows found in the presentation data.")
    body = f"""
{page_header("Competitor Explorer", "What are competitors doing?", secondary_button("Seller evidence only"))}
    <details class="panel compact-result-details">
      <summary>Seller Summary</summary>
      <section class="kpi-grid" aria-label="Competitor KPIs">
      {kpi_card("Tracked Sellers", str(total_sellers), "Active seller groups", "stable")}
      {kpi_card("Seller Leaders", str(total_leaders), "Top seller-source evidence", "winner")}
      {kpi_card("Seller Movers", str(total_movers), "Source-aware movement", "rising")}
      {kpi_card("New Pushes", str(total_pushes), "Fresh seller pushes", "idea")}
      </section>
    </details>
    <div class="explorer-layout">
      <section class="panel">
{section_header("Seller Activity", "Compact seller-level summary")}
        <div class="secondary-toolbar">
          <div class="segment-tabs" aria-label="Competitor preset">
            <button class="btn btn-secondary" type="button" data-seller-preset="most_active" aria-pressed="true">Most Active Sellers</button>
            <button class="btn btn-ghost" type="button" data-seller-preset="new_push" aria-pressed="false">New Push Sellers</button>
            <button class="btn btn-ghost" type="button" data-seller-preset="strong_catalog" aria-pressed="false">Strong Catalog Sellers</button>
          </div>
          {search_input("Search sellers", "Search seller name", "seller-search")}
          <label class="caption" for="seller-sort-select">Sort</label>
          <select id="seller-sort-select" class="select-input" data-seller-sort-select>
            <option value="activity">Activity first</option>
            <option value="products">Product count</option>
            <option value="seller_leaders">Seller Leader count</option>
            <option value="seller_movers">Seller Mover count</option>
            <option value="seller_new_pushes">Seller New Push count</option>
            <option value="strong_sub_bsr">Strong Sub-BSR count</option>
            <option value="latest_activity">Latest activity</option>
          </select>
        </div>
{table_html}
      </section>
      <aside class="panel detail-panel" data-seller-detail>
{empty_state("Select a seller", "Choose a seller row to preview representative products and open Product Explorer.")}
      </aside>
    </div>
"""
    scripts = f"""  <script type="application/json" id="seller-explorer-data">{seller_json}</script>
  <script>
{_competitor_script()}
  </script>
"""
    return render_app_shell(title="Competitor Explorer", active_key="competitor", body=body, scripts=scripts, dataset_info=_dataset_info(data))


def render_market_explorer(data: dict[str, object]) -> str:
    products = data["products"]
    market_payload = _market_group_payload(products)
    market_json = _safe_json_script(market_payload)
    body = f"""
{page_header("Market Explorer", "How is the market distributed and changing?", secondary_button("Existing evidence fields"))}
    <section class="panel">
      <div class="secondary-toolbar">
        <div class="segment-tabs" aria-label="Market grouping mode">
          <button class="btn btn-secondary" type="button" data-market-mode="category" aria-pressed="true">Category</button>
          <button class="btn btn-ghost" type="button" data-market-mode="product_type" aria-pressed="false">Product Type</button>
        </div>
        {search_input("Search market groups", "Search category or product type", "market-search")}
        <label class="caption" for="market-sort-select">Sort</label>
        <select id="market-sort-select" class="select-input" data-market-sort>
          <option value="default">Breakout first</option>
          <option value="product_count">Product count</option>
          <option value="seller_count">Seller count</option>
          <option value="seller_leader_count">Seller Leader count</option>
          <option value="seller_mover_count">Seller Mover count</option>
          <option value="category_winner_count">Category Winner count</option>
          <option value="category_breakout_count">Category Breakout count</option>
          <option value="new_release_rising_count">New Release Rising count</option>
          <option value="new_release_breakout_count">New Release Breakout count</option>
          <option value="strong_sub_bsr_count">Strong Sub-BSR count</option>
          <option value="very_strong_sub_bsr_count">Very Strong Sub-BSR count</option>
          <option value="median_sub_bsr">Median Sub-BSR</option>
        </select>
        <label class="caption" for="market-min-products">Min products</label>
        <input id="market-min-products" class="range-input" type="number" min="0" value="1" data-market-min-products>
        <label class="caption" for="market-source-family">Source family</label>
        <select id="market-source-family" class="select-input" data-market-source-family>
          <option value="">All source families</option>
          <option value="seller">Seller</option>
          <option value="best_seller">Best Seller</option>
          <option value="new_release">New Release</option>
          <option value="bsr">BSR</option>
        </select>
      </div>
    </section>
    <div class="explorer-layout market-explorer-layout">
      <section class="panel">
{section_header("Market List", "Unknown product type remains visible")}
        <div class="table-shell">
          <table data-market-table>
            <thead>
            <tr>
                <th scope="col">Market</th>
                <th scope="col">Momentum</th>
                <th scope="col">Validation</th>
                <th scope="col">Competition</th>
                <th scope="col">Open</th>
              </tr>
            </thead>
            <tbody data-market-tbody></tbody>
          </table>
        </div>
        <div class="empty-state" data-market-empty hidden><strong>No market groups match the current controls.</strong></div>
      </section>
      <aside class="panel detail-panel market-preview-panel" data-market-detail>
{empty_state("Select a market", "Choose a market row to preview products and open Product Explorer.")}
      </aside>
    </div>
"""
    scripts = f"""  <script type="application/json" id="market-explorer-data">{market_json}</script>
  <script>
{_market_script()}
  </script>
"""
    return render_app_shell(title="Market Explorer", active_key="market_explorer", body=body, scripts=scripts, dataset_info=_dataset_info(data))


def _dataset_info(data: dict[str, object]) -> dict[str, object]:
    info = data.get("dataset_info", {}) if isinstance(data, dict) else {}
    return info if isinstance(info, dict) else {}


def _product_explorer_products(data: dict[str, object]) -> list[dict[str, object]]:
    products = data.get("product_explorer_products", data.get("products", [])) if isinstance(data, dict) else []
    return products if isinstance(products, list) else []


PRIMARY_EVIDENCE_PRIORITY = [
    "new_release_breakout",
    "category_breakout",
    "seller_mover",
    "seller_new_push",
    "category_winner",
    "new_release_rising",
    "seller_leader",
    "very_strong_sub_bsr",
    "strong_sub_bsr",
    "new_release_watch",
]

PRODUCT_PRESETS = {
    "research_today": {
        "label": "Research Today",
        "guidance": "Start with Research Today to find products with recent movement.",
        "empty": "No products match Research Today with the current filters.",
        "next": "Proven Demand",
        "evidence": {"category_breakout", "new_release_breakout", "seller_mover", "seller_new_push"},
    },
    "proven_demand": {
        "label": "Proven Demand",
        "guidance": "Use Proven Demand for validated products.",
        "empty": "No products match Proven Demand with the current filters.",
        "next": "Research Today",
        "evidence": {"category_winner", "very_strong_sub_bsr", "seller_leader"},
    },
    "early_opportunity": {
        "label": "Early Opportunity",
        "guidance": "Use Early Opportunity for lower-review products with fresh momentum.",
        "empty": "No products match Early Opportunity with the current filters.",
        "next": "Research Today",
        "evidence": {"seller_new_push", "new_release_rising", "new_release_watch"},
    },
    "competitor_push": {
        "label": "Competitor Push",
        "guidance": "Use Competitor Push to review sellers making visible moves.",
        "empty": "No products match Competitor Push with the current filters.",
        "next": "Early Opportunity",
        "evidence": {"seller_mover", "seller_new_push"},
    },
}


def _home_research_today(products: list[dict[str, object]]) -> str:
    preset = "research_today"
    rows = _diverse_products(_sort_products_for_preset(_preset_products(products, preset), preset), limit=8)
    items = "\n".join(_research_queue_item(product, preset) for product in rows) or empty_state("No qualifying products", "No products match Research Today in the current presentation data.")
    preview_panel = _home_research_preview_panel(rows[0] if rows else None, preset)
    return f"""      <section class="panel research-queue-card minimal-research-card" data-research-queue-group="{escape(preset)}">
{section_header("Research Today", "Breakouts, movers, and new pushes", f'<a class="utility-link" href="product_explorer.html?preset={quote_param(preset)}">Open Product Explorer</a>')}
        <div class="activity-list">{items}</div>
      </section>
{preview_panel}"""


def _home_market_pulse(products: list[dict[str, object]]) -> str:
    momentum = sum(1 for product in products if _product_has_evidence(product, "seller_mover") or _product_has_evidence(product, "new_release_rising"))
    validation = sum(1 for product in products if _product_has_evidence(product, "category_winner") or _product_has_evidence(product, "strong_sub_bsr"))
    breakouts = sum(1 for product in products if _product_has_evidence(product, "category_breakout") or _product_has_evidence(product, "new_release_breakout"))
    new_pushes = sum(1 for product in products if _product_has_evidence(product, "seller_new_push"))
    return "\n".join(
        [
            kpi_card("Momentum", _fmt_int(momentum), "Seller movers + New Release rising", "rising"),
            kpi_card("Validation", _fmt_int(validation), "Winners + Strong Sub-BSR", "winner"),
            kpi_card("Breakouts", _fmt_int(breakouts), "Category + New Release breakouts", "idea"),
            kpi_card("New Pushes", _fmt_int(new_pushes), "Fresh seller pushes", "stable"),
        ]
    )


def _home_compact_data_status(dataset_info: dict[str, object], products: list[dict[str, object]]) -> str:
    return "\n".join(
        [
            kpi_card("Products", _fmt_int(dataset_info.get("presentation_products", len(products))), "Visible in V2", "stable"),
            kpi_card("Observations", _fmt_int(dataset_info.get("source_aware_observations", 0)), "Source-aware rows", "idea"),
            kpi_card("Generated", str(dataset_info.get("generated_at", _missing())), "Latest V2 build", "neutral"),
        ]
    )


def _home_research_queue(products: list[dict[str, object]]) -> str:
    groups = [
        ("Must Review Today", "research_today", "Products with breakout, mover, or new seller push evidence"),
        ("Early Opportunities", "early_opportunity", "Fresh momentum with lower review counts preferred"),
        ("Proven Demand", "proven_demand", "Validated products with Best Seller, Sub-BSR, or seller leadership"),
        ("Competitor Pushes", "competitor_push", "Seller movers and new pushes to inspect"),
    ]
    html = []
    for title, preset, caption in groups:
        candidates = _preset_products(products, preset)
        rows = _diverse_products(_sort_products_for_preset(candidates, preset), limit=6)
        items = "\n".join(_research_queue_item(product, preset) for product in rows) or empty_state("No qualifying products", f"No products match {PRODUCT_PRESETS[preset]['label']} in the current presentation data.")
        html.append(f"""      <section class="panel research-queue-card" data-research-queue-group="{escape(preset)}">
{section_header(title, caption, f'<a class="utility-link" href="product_explorer.html?preset={quote_param(preset)}">Open preset</a>')}
        <div class="activity-list">{items}</div>
      </section>""")
    return "\n".join(html)


def _research_queue_item(product: dict[str, object], preset: str) -> str:
    asin = str(product.get("asin", "") or product.get("id", "") or "")
    title = str(product.get("title", "Untitled Product") or "Untitled Product")
    seller = str(product.get("seller", "Unknown Seller") or "Unknown Seller")
    product_type = str(product.get("product_type", "Unknown") or "Unknown")
    href = f"product_explorer.html?preset={quote_param(preset)}&focus={quote_param(asin)}" if asin else f"product_explorer.html?preset={quote_param(preset)}"
    reason = _why_it_matters(product)
    metric = _market_proof(product)
    if metric == _missing():
        metric = _momentum_label(product)
    tone = _primary_evidence_tone(product)
    image = product_image_src(product, tone)
    return f"""          <a class="activity-item research-queue-item" href="{href}" data-home-preview-item data-queue-asin="{escape(asin)}" data-preview-title="{escape(title)}" data-preview-seller="{escape(seller)}" data-preview-type="{escape(product_type)}" data-preview-reason="{escape(reason)}" data-preview-metric="{escape(metric)}" data-preview-image="{escape(image)}" data-preview-href="{escape(href)}">
            <img class="activity-thumbnail" src="{escape(image)}" alt="{escape(title)} thumbnail">
            <span class="activity-copy"><strong>{escape(title)}</strong><span class="caption">{escape(seller)} - {escape(reason)}</span></span>
            {status_badge(metric, _primary_evidence_tone(product))}
          </a>"""


def _home_research_preview_panel(product: dict[str, object] | None, preset: str) -> str:
    if not product:
        return f"""      <aside class="panel home-preview-panel" aria-label="Research Today product preview" data-home-preview-panel>
{empty_state("No preview available", "Research Today has no qualifying products.")}
      </aside>"""
    asin = str(product.get("asin", "") or product.get("id", "") or "")
    title = str(product.get("title", "Untitled Product") or "Untitled Product")
    seller = str(product.get("seller", "Unknown Seller") or "Unknown Seller")
    product_type = str(product.get("product_type", "Unknown") or "Unknown")
    href = f"product_explorer.html?preset={quote_param(preset)}&focus={quote_param(asin)}" if asin else f"product_explorer.html?preset={quote_param(preset)}"
    reason = _why_it_matters(product)
    metric = _market_proof(product)
    if metric == _missing():
        metric = _momentum_label(product)
    image = product_image_src(product, _primary_evidence_tone(product))
    return f"""      <aside class="panel home-preview-panel" aria-label="Research Today product preview" data-home-preview-panel>
        <img class="home-preview-image" data-home-preview-image src="{escape(image)}" alt="{escape(title)} product preview">
        <div class="inspector-heading">
          <h2>Product Preview</h2>
          <span class="caption" data-home-preview-state>Hover preview</span>
        </div>
        <h3 class="preview-title" data-home-preview-title>{escape(title)}</h3>
        <div class="preview-meta">
          <div class="preview-meta-row"><span>Seller</span><strong data-home-preview-seller>{escape(seller)}</strong></div>
          <div class="preview-meta-row"><span>Type</span><strong data-home-preview-type>{escape(product_type)}</strong></div>
          <div class="preview-meta-row"><span>Reason</span><strong data-home-preview-reason>{escape(reason)}</strong></div>
          <div class="preview-meta-row"><span>Signal</span><strong data-home-preview-metric>{escape(metric)}</strong></div>
        </div>
        <div class="preview-actions">
          <a class="btn btn-primary" data-home-preview-link href="{escape(href)}">Open Product Explorer</a>
        </div>
      </aside>"""


def _home_research_preview_script() -> str:
    return r"""(() => {
    const container = document.querySelector("[data-home-research-queue]");
    const panel = document.querySelector("[data-home-preview-panel]");
    if (!container || !panel) return;
    const items = Array.from(container.querySelectorAll("[data-home-preview-item]"));
    if (!items.length) return;
    const fields = {
      image: panel.querySelector("[data-home-preview-image]"),
      title: panel.querySelector("[data-home-preview-title]"),
      seller: panel.querySelector("[data-home-preview-seller]"),
      type: panel.querySelector("[data-home-preview-type]"),
      reason: panel.querySelector("[data-home-preview-reason]"),
      metric: panel.querySelector("[data-home-preview-metric]"),
      state: panel.querySelector("[data-home-preview-state]"),
      link: panel.querySelector("[data-home-preview-link]"),
    };
    let pinnedItem = null;

    items.forEach((item) => {
      item.addEventListener("pointerenter", () => updatePreview(item, false));
      item.addEventListener("focus", () => updatePreview(item, false));
      item.addEventListener("pointerleave", () => {
        if (pinnedItem) updatePreview(pinnedItem, true);
      });
      item.addEventListener("blur", () => {
        if (pinnedItem) updatePreview(pinnedItem, true);
      });
      item.addEventListener("click", (event) => {
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0 || pinnedItem === item) return;
        event.preventDefault();
        pinnedItem = item;
        updatePreview(item, true);
      });
    });

    document.addEventListener("click", (event) => {
      if (!pinnedItem) return;
      if (event.target.closest("[data-home-preview-item]") || event.target.closest("[data-home-preview-panel]")) return;
      pinnedItem = null;
      setPinnedItem(null);
      fields.state && (fields.state.textContent = "Hover preview");
    });

    function updatePreview(item, pinned) {
      if (!item) return;
      setText(fields.title, item.dataset.previewTitle);
      setText(fields.seller, item.dataset.previewSeller);
      setText(fields.type, item.dataset.previewType);
      setText(fields.reason, item.dataset.previewReason);
      setText(fields.metric, item.dataset.previewMetric);
      if (fields.image) {
        fields.image.src = item.dataset.previewImage || "";
        fields.image.alt = `${item.dataset.previewTitle || "Product"} product preview`;
      }
      if (fields.link) fields.link.href = item.dataset.previewHref || "product_explorer.html";
      setPinnedItem(pinned ? item : null);
      fields.state && (fields.state.textContent = pinned ? "Pinned" : "Hover preview");
    }

    function setPinnedItem(item) {
      items.forEach((candidate) => candidate.classList.toggle("is-pinned", candidate === item));
      panel.classList.toggle("is-pinned", Boolean(item));
    }

    function setText(element, value) {
      if (element) element.textContent = String(value || "");
    }
  })();"""


def _preset_products(products: list[dict[str, object]], preset: str) -> list[dict[str, object]]:
    config = PRODUCT_PRESETS.get(preset)
    if not config:
        return list(products)
    evidence_keys = config["evidence"]
    return [product for product in products if any(_product_has_evidence(product, key) for key in evidence_keys)]


def _sort_products_for_preset(products: list[dict[str, object]], preset: str) -> list[dict[str, object]]:
    indexed = list(enumerate(products))

    def fallback(index: int, product: dict[str, object]) -> tuple[object, ...]:
        return (str(product.get("title", "")).lower(), str(product.get("asin", "") or product.get("id", "")).lower(), index)

    def missing_high(value: int | None) -> int:
        return value if value is not None else 10**9

    def missing_low(value: int | None) -> int:
        return value if value is not None else -10**9

    def key_for(item: tuple[int, dict[str, object]]) -> tuple[object, ...]:
        index, product = item
        if preset == "research_today":
            priority = _primary_evidence_index(product)
            movement = _rank_improvement(product)
            reviews = _num_or_none(product.get("review_count", product.get("reviews")))
            return (priority, -missing_low(movement), missing_high(reviews), *fallback(index, product))
        if preset == "proven_demand":
            sub_bsr = _valid_sub_bsr(product)
            category_rank = _num_or_none(product.get("best_seller_evidence_best_rank"))
            reviews = _num_or_none(product.get("review_count", product.get("reviews")))
            return (missing_high(sub_bsr), missing_high(category_rank), -missing_low(reviews), *fallback(index, product))
        if preset == "early_opportunity":
            reviews = _num_or_none(product.get("review_count", product.get("reviews")))
            low_review_bucket = 0 if reviews is not None and reviews <= 100 else 1 if reviews is not None else 2
            return (low_review_bucket, missing_high(reviews), -missing_low(_rank_improvement(product)), missing_high(_source_days_seen(product)), *fallback(index, product))
        if preset == "competitor_push":
            seller_movement = _num_or_none(product.get("seller_movement"))
            return (-missing_low(seller_movement), missing_high(_source_days_seen(product)), *fallback(index, product))
        return fallback(index, product)

    return [product for _, product in sorted(indexed, key=key_for)]


def _diverse_products(
    products: list[dict[str, object]],
    *,
    limit: int,
    seller_cap: int = 2,
    product_type_cap: int = 3,
) -> list[dict[str, object]]:
    selected: list[dict[str, object]] = []
    seen_keys: set[tuple[str, str]] = set()
    seen_titles: set[str] = set()
    seller_counts: Counter[str] = Counter()
    type_counts: Counter[str] = Counter()
    for product in products:
        asin = str(product.get("asin", "") or product.get("id", "") or "").strip().upper()
        marketplace = str(product.get("marketplace", "") or "amazon.com").strip().lower()
        dedupe_key = (marketplace, asin) if asin else (marketplace, _normalized_title(product))
        title_key = _normalized_title(product)
        seller = str(product.get("seller", "") or "Unknown Seller").strip().lower()
        product_type = str(product.get("product_type", "") or "Unknown").strip().lower()
        if dedupe_key in seen_keys or title_key in seen_titles:
            continue
        if seller_counts[seller] >= seller_cap or type_counts[product_type] >= product_type_cap:
            continue
        selected.append(product)
        seen_keys.add(dedupe_key)
        seen_titles.add(title_key)
        seller_counts[seller] += 1
        type_counts[product_type] += 1
        if len(selected) >= limit:
            break
    return selected


def _normalized_title(product: dict[str, object]) -> str:
    return re.sub(r"\s+", " ", str(product.get("title", "") or "").strip().lower())


def _primary_evidence_key(product: dict[str, object]) -> str:
    for key in PRIMARY_EVIDENCE_PRIORITY:
        if _product_has_evidence(product, key):
            return key
    return ""


def _primary_evidence_index(product: dict[str, object]) -> int:
    key = _primary_evidence_key(product)
    return PRIMARY_EVIDENCE_PRIORITY.index(key) if key in PRIMARY_EVIDENCE_PRIORITY else len(PRIMARY_EVIDENCE_PRIORITY)


def _primary_evidence_tone(product: dict[str, object]) -> str:
    key = _primary_evidence_key(product)
    if key in {"new_release_breakout", "category_winner", "seller_leader", "very_strong_sub_bsr"}:
        return "winner"
    if key in {"category_breakout", "seller_mover", "new_release_rising"}:
        return "rising"
    if key in {"seller_new_push", "new_release_watch"}:
        return "idea"
    if key == "strong_sub_bsr":
        return "stable"
    return "neutral"


def _why_it_matters(product: dict[str, object]) -> str:
    key = _primary_evidence_key(product)
    reviews = _num_or_none(product.get("review_count", product.get("reviews")))
    if key == "seller_mover":
        movement = _num_or_none(product.get("seller_movement"))
        return f"Improved {_fmt_int(movement)} seller positions" if movement is not None else "Seller mover"
    if key == "seller_new_push":
        days = _source_days_seen(product)
        return f"New seller push detected {_fmt_int(days)} days ago" if days is not None else "New seller push detected"
    if key == "new_release_breakout":
        return f"New Release breakout with {_fmt_int(reviews)} reviews" if reviews is not None else "New Release breakout"
    if key == "category_breakout":
        movement = _num_or_none(product.get("best_seller_movement"))
        return f"Category breakout improved {_fmt_int(movement)} ranks" if movement is not None else "Category breakout"
    if key == "category_winner":
        rank = _num_or_none(product.get("best_seller_evidence_best_rank"))
        return f"Category Winner at rank #{_fmt_int(rank)}" if rank is not None else "Category Winner"
    if key == "new_release_rising":
        movement = _num_or_none(product.get("new_release_movement"))
        return f"New Release rising +{_fmt_int(movement)} ranks" if movement is not None else "New Release rising"
    if key == "seller_leader":
        rank = _num_or_none(product.get("seller_evidence_best_rank"))
        return f"Seller Leader at rank #{_fmt_int(rank)}" if rank is not None else "Seller Leader"
    if key in {"very_strong_sub_bsr", "strong_sub_bsr"}:
        rank = _valid_sub_bsr(product)
        label = "Very Strong Sub-BSR" if key == "very_strong_sub_bsr" else "Strong Sub-BSR"
        return f"{label} at #{_fmt_int(rank)}" if rank is not None else label
    if key == "new_release_watch":
        days = _source_days_seen(product)
        return f"New Release watch seen {_fmt_int(days)} days" if days is not None else "New Release watch"
    if _num(product.get("evidence_count")) > 1:
        return "Multiple evidence sources"
    return "No primary evidence"


def _momentum_label(product: dict[str, object]) -> str:
    key = _primary_evidence_key(product)
    if key in {"seller_mover", "seller_new_push", "seller_leader"}:
        movement = _num_or_none(product.get("seller_movement"))
        days = _num_or_none(product.get("seller_days_seen")) or _source_days_seen(product)
    elif key in {"category_breakout", "category_winner"}:
        movement = _num_or_none(product.get("best_seller_movement"))
        days = _num_or_none(product.get("best_seller_days_seen")) or _source_days_seen(product)
    elif key in {"new_release_breakout", "new_release_rising", "new_release_watch"}:
        movement = _num_or_none(product.get("new_release_movement"))
        days = _num_or_none(product.get("new_release_days_seen")) or _source_days_seen(product)
    else:
        movement = _rank_improvement(product)
        days = _source_days_seen(product)
    if key in {"seller_new_push", "new_release_watch"} and days is not None:
        return f"New - {_fmt_int(days)} days"
    if movement is not None:
        return f"+{_fmt_int(movement)} ranks"
    if days is not None:
        return f"Stable - {_fmt_int(days)} days"
    return _missing()


def _market_proof(product: dict[str, object]) -> str:
    best_seller = _num_or_none(product.get("best_seller_evidence_best_rank"))
    if best_seller is not None and best_seller > 0:
        return f"Best Seller #{_fmt_int(best_seller)}"
    sub_bsr = _valid_sub_bsr(product)
    if sub_bsr is not None:
        return f"Sub-BSR #{_fmt_int(sub_bsr)}"
    reviews = _num_or_none(product.get("review_count", product.get("reviews")))
    if reviews is not None:
        return f"{_fmt_int(reviews)} reviews"
    seller_rank = _num_or_none(product.get("seller_evidence_best_rank"))
    if seller_rank is not None and seller_rank > 0:
        return f"Seller #{_fmt_int(seller_rank)}"
    return _missing()


def _rank_improvement(product: dict[str, object]) -> int | None:
    values = [
        _num_or_none(product.get("seller_movement")),
        _num_or_none(product.get("best_seller_movement")),
        _num_or_none(product.get("new_release_movement")),
        _num_or_none(product.get("source_rank_change")),
    ]
    valid = [value for value in values if value is not None]
    return max(valid) if valid else None


def _source_days_seen(product: dict[str, object]) -> int | None:
    values = [
        _num_or_none(product.get("seller_days_seen")),
        _num_or_none(product.get("best_seller_days_seen")),
        _num_or_none(product.get("new_release_days_seen")),
        _num_or_none(product.get("source_days_seen")),
    ]
    valid = [value for value in values if value is not None]
    return min(valid) if valid else None


def _product_preset_rows(products: list[dict[str, object]]) -> list[str]:
    rows = []
    for key, config in PRODUCT_PRESETS.items():
        count = len(_preset_products(products, key))
        active = " is-active" if key == "research_today" else ""
        current = ' aria-current="true"' if key == "research_today" else ""
        rows.append(
            f"""<button class="preset-button{active}" type="button" data-product-preset="{escape(key)}"{current}>
              <span>{escape(str(config["label"]))}</span>
              <strong>{_fmt_int(count)}</strong>
            </button>"""
        )
    return rows


def _home_dataset_overview(dataset_info: dict[str, object], products: list[dict[str, object]]) -> str:
    return "\n".join(
        [
            kpi_card("Unique Products", _fmt_int(dataset_info.get("total_unique_products", len(products))), "Across source-aware history", "stable"),
            kpi_card("Source-aware Observations", _fmt_int(dataset_info.get("source_aware_observations", 0)), "Source-aware rows", "idea"),
            kpi_card("Marketplaces", _fmt_int(dataset_info.get("marketplace_count", 0)), "Distinct marketplaces", "stable"),
            kpi_card("Seller Sources", _fmt_int(dataset_info.get("seller_source_count", 0)), "Tracked seller sources", "winner"),
            kpi_card("Best Seller Sources", _fmt_int(dataset_info.get("best_seller_source_count", 0)), "Tracked category sources", "rising"),
            kpi_card("New Release Sources", _fmt_int(dataset_info.get("new_release_source_count", 0)), "Tracked release sources", "alert"),
            kpi_card("Valid Sub-BSR", _fmt_int(dataset_info.get("products_with_valid_bsr", 0)), "Products with valid Sub-BSR", "stable"),
            kpi_card("Last Crawl", str(dataset_info.get("last_crawl_timestamp", _missing())), "Latest observed timestamp", "neutral"),
        ]
    )


def _home_signal_definitions() -> list[tuple[str, str, str, str]]:
    return [
        ("seller_leader", "Seller Leader", "winner", "seller"),
        ("seller_mover", "Seller Mover", "rising", "seller"),
        ("seller_new_push", "Seller New Push", "idea", "seller"),
        ("category_winner", "Category Winner", "winner", "best_seller"),
        ("category_breakout", "Category Breakout", "rising", "best_seller"),
        ("category_stable", "Category Stable", "stable", "best_seller"),
        ("new_release_rising", "New Release Rising", "rising", "new_release"),
        ("new_release_breakout", "New Release Breakout", "winner", "new_release"),
        ("new_release_watch", "New Release Candidate", "idea", "new_release"),
        ("strong_sub_bsr", "Strong Sub-BSR", "stable", "supporting"),
        ("very_strong_sub_bsr", "Very Strong Sub-BSR", "winner", "supporting"),
    ]


def _home_evidence_card(products: list[dict[str, object]], key: str, label: str, tone: str, family: str) -> str:
    active = sum(1 for product in products if _product_has_evidence(product, key))
    eligible = sum(1 for product in products if _product_has_evidence_data(product, family))
    rate = f"{(active / eligible) * 100:.1f}%" if eligible else _missing()
    href = _product_explorer_filter_href(key, family)
    return f"""      <a class="kpi-card evidence-overview-card tone-{tone_name(tone)}" href="{escape(href)}">
        <h3>{escape(label)}</h3>
        <strong class="kpi-value">{_fmt_int(active)}</strong>
        <div class="card-metrics">
          <span>{_fmt_int(eligible)} eligible</span>
          <span>{escape(rate)} rate</span>
        </div>
      </a>"""


def _home_coverage_cards(products: list[dict[str, object]]) -> str:
    seller = sum(1 for product in products if _product_has_evidence_data(product, "seller"))
    best_seller = sum(1 for product in products if _product_has_evidence_data(product, "best_seller"))
    new_release = sum(1 for product in products if _product_has_evidence_data(product, "new_release"))
    bsr = sum(1 for product in products if _product_has_evidence_data(product, "supporting"))
    family_counts = [_source_family_count(product) for product in products]
    return "\n".join(
        [
            kpi_card("Seller Coverage", _fmt_int(seller), "Products with seller observations", "winner"),
            kpi_card("Best Seller Coverage", _fmt_int(best_seller), "Products with Best Seller observations", "rising"),
            kpi_card("New Release Coverage", _fmt_int(new_release), "Products with New Release observations", "alert"),
            kpi_card("BSR Coverage", _fmt_int(bsr), "Products with valid Sub-BSR", "stable"),
            kpi_card("One Source Family", _fmt_int(sum(1 for value in family_counts if value == 1)), "Exactly one source family", "neutral"),
            kpi_card("Two Source Families", _fmt_int(sum(1 for value in family_counts if value == 2)), "Two source families", "idea"),
            kpi_card("Three Source Families", _fmt_int(sum(1 for value in family_counts if value >= 3)), "Three source families", "winner"),
        ]
    )


def _home_activity_sections(products: list[dict[str, object]]) -> str:
    sections = [
        ("Biggest Seller Movers", [product for product in products if _product_has_evidence(product, "seller_mover")], lambda product: _num(product.get("seller_movement")), True, "seller_evidence=seller_mover"),
        ("Newest Seller Pushes", [product for product in products if _product_has_evidence(product, "seller_new_push")], lambda product: -_num(product.get("source_days_seen"), default=10**9), True, "seller_evidence=seller_new_push"),
        ("Strongest Category Breakouts", [product for product in products if _product_has_evidence(product, "category_breakout")], lambda product: -_num(product.get("best_seller_evidence_best_rank"), default=10**9), True, "best_seller_evidence=category_breakout"),
        ("Strongest New Release Breakouts", [product for product in products if _product_has_evidence(product, "new_release_breakout")], lambda product: _num(product.get("new_release_movement")), True, "new_release_evidence=new_release_breakout"),
        ("Strongest Valid Sub-BSR", [product for product in products if _valid_sub_bsr(product) is not None], lambda product: -(_valid_sub_bsr(product) or 10**9), True, "supporting_evidence=very_strong_sub_bsr"),
    ]
    html = []
    for title, rows, sorter, reverse, query in sections:
        sorted_rows = _diverse_products(sorted(rows, key=sorter, reverse=reverse), limit=8)
        items = "\n".join(_activity_item(product, query) for product in sorted_rows) or empty_state("No qualifying products", "No products match this source-aware activity signal.")
        html.append(f"""      <section class="panel">
{section_header(title)}
        <div class="activity-list">{items}</div>
      </section>""")
    return "\n".join(html)


def _activity_item(product: dict[str, object], base_query: str) -> str:
    asin = str(product.get("asin", "") or product.get("id", "") or "")
    title = str(product.get("title", "Untitled Product") or "Untitled Product")
    seller = str(product.get("seller", "Unknown Seller") or "Unknown Seller")
    href = f"product_explorer.html?{base_query}&focus={quote_param(asin)}" if asin else f"product_explorer.html?{base_query}"
    metric_value = _activity_metric(product)
    return f"""          <a class="activity-item" href="{href}">
            <span><strong>{escape(title)}</strong><span class="caption">{escape(seller)}</span></span>
            {status_badge(metric_value, "rising")}
          </a>"""


def _activity_metric(product: dict[str, object]) -> str:
    if _num(product.get("seller_movement")):
        return f"+{_fmt_int(_num(product.get('seller_movement')))}"
    if _num(product.get("new_release_movement")):
        return f"+{_fmt_int(_num(product.get('new_release_movement')))}"
    bsr = _valid_sub_bsr(product)
    if bsr is not None:
        return f"#{_fmt_int(bsr)}"
    return str(product.get("status", "Tracked") or "Tracked")


def _home_data_quality(products: list[dict[str, object]], dataset_info: dict[str, object]) -> str:
    return "\n".join(
        [
            _quality_item("Unknown product type", _fmt_int(sum(1 for product in products if _is_unknown(product.get("product_type"))))),
            _quality_item("Missing image", _fmt_int(sum(1 for product in products if not str(product.get("image_url", "") or "").strip()))),
            _quality_item("Missing product URL", _fmt_int(sum(1 for product in products if not _product_url(product)))),
            _quality_item("Missing review data", _fmt_int(sum(1 for product in products if _num_or_none(product.get("review_count")) is None and _is_missing_display(product.get("reviews"))))),
            _quality_item("Missing price", _fmt_int(sum(1 for product in products if _num_or_none(product.get("price_value")) is None and _is_missing_display(product.get("price"))))),
            _quality_item("Multiple source families", _fmt_int(sum(1 for product in products if _source_family_count(product) > 1))),
            _quality_item("Latest generation status", str(dataset_info.get("status", "Unknown"))),
        ]
    )


def _home_calibration_status(dataset_info: dict[str, object]) -> str:
    if not dataset_info.get("calibration_report_exists"):
        return f"""    <section class="panel">
{section_header("Calibration Status", "Human-review analysis is not part of the main workflow")}
{empty_state("Calibration report unavailable", "Run analyze-evidence-reviews after the review file is completed.")}
    </section>"""
    reviewed = _fmt_int(dataset_info.get("calibration_reviewed_rows", 0))
    total = _fmt_int(dataset_info.get("calibration_total_rows", 0))
    mode = str(dataset_info.get("calibration_mode", "Diagnostic Only"))
    return f"""    <section class="panel">
{section_header("Calibration Status", "Secondary review diagnostic")}
      <div class="data-quality-list">
        {_quality_item("Human Review", f"{reviewed} / {total} completed")}
        {_quality_item("Mode", mode)}
        {_quality_item("Report", '<a class="utility-link" href="../evidence_human_review_analysis.html">Open calibration report</a>', raw=True)}
      </div>
    </section>"""


def _quality_item(label: str, value: object, *, raw: bool = False) -> str:
    value_html = str(value) if raw else escape(str(value))
    return f"""        <div class="quality-item">
          <span>{escape(label)}</span>
          <strong>{value_html}</strong>
        </div>"""


def _product_explorer_filter_href(key: str, family: str) -> str:
    param = {
        "seller": "seller_evidence",
        "best_seller": "best_seller_evidence",
        "new_release": "new_release_evidence",
        "supporting": "supporting_evidence",
    }[family]
    return f"product_explorer.html?{param}={key}"


def _product_has_evidence(product: dict[str, object], key: str) -> bool:
    return bool(product.get(key) or product.get(_product_evidence_field(key)))


def _product_has_evidence_data(product: dict[str, object], family: str) -> bool:
    if family == "seller":
        return _num(product.get("seller_evidence_source_count")) > 0 or bool(product.get("source_details", {}).get("seller") if isinstance(product.get("source_details"), dict) else False)
    if family == "best_seller":
        return _num(product.get("best_seller_evidence_source_count")) > 0 or bool(product.get("source_details", {}).get("best_seller") if isinstance(product.get("source_details"), dict) else False)
    if family == "new_release":
        return _num(product.get("new_release_evidence_source_count")) > 0 or bool(product.get("source_details", {}).get("new_release") if isinstance(product.get("source_details"), dict) else False)
    return _valid_sub_bsr(product) is not None or bool(product.get("source_details", {}).get("bsr") if isinstance(product.get("source_details"), dict) else False)


def _source_family_count(product: dict[str, object]) -> int:
    explicit = _num_or_none(product.get("evidence_source_family_count"))
    if explicit is not None:
        return explicit
    return sum(1 for family in ["seller", "best_seller", "new_release"] if _product_has_evidence_data(product, family))


def _valid_sub_bsr(product: dict[str, object]) -> int | None:
    value = _num_or_none(product.get("bsr_evidence_best_sub_bsr"))
    if value is None:
        value = _num_or_none(product.get("sub_bsr_rank"))
    return value if value is not None and value > 0 else None


def _product_url(product: dict[str, object]) -> str:
    return str(product.get("amazon_url", "") or product.get("product_url", "") or "").strip()


def _fmt_int(value: object) -> str:
    number = _num_or_none(value)
    return f"{number:,}" if number is not None else _missing()


def _missing() -> str:
    return "\u2014"


def _num(value: object, *, default: int = 0) -> int:
    parsed = _num_or_none(value)
    return parsed if parsed is not None else default


def _num_or_none(value: object) -> int | None:
    text = str(value or "").replace(",", "").replace("#", "").replace("+", "").strip()
    if not text or text in {"-", "&mdash;"}:
        return None
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return None


def _is_unknown(value: object) -> bool:
    return str(value or "").strip().lower() in {"", "unknown", "uncategorized"}


def _is_missing_display(value: object) -> bool:
    return str(value or "").strip() in {"", "-", "&mdash;"}


def _float_or_none(value: object) -> float | None:
    text = str(value or "").replace(",", "").replace("$", "").strip()
    if not text or text in {"-", "&mdash;"}:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _median(values: list[int | None]) -> int | None:
    valid = sorted(value for value in values if value is not None)
    if not valid:
        return None
    mid = len(valid) // 2
    if len(valid) % 2:
        return valid[mid]
    return round((valid[mid - 1] + valid[mid]) / 2)


def _median_float(values: list[float | None]) -> float | None:
    valid = sorted(value for value in values if value is not None)
    if not valid:
        return None
    mid = len(valid) // 2
    if len(valid) % 2:
        return valid[mid]
    return (valid[mid - 1] + valid[mid]) / 2


def _rank_or_missing(value: object) -> str:
    number = _num_or_none(value)
    return f"#{number:,}" if number is not None and number > 0 else _missing()


def quote_param(value: str) -> str:
    return quote(value, safe="")


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "unknown"


def _seller_summaries(products: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for product in products:
        seller = str(product.get("seller", "") or "Unknown Seller").strip() or "Unknown Seller"
        grouped.setdefault(seller, []).append(product)
    summaries = []
    for seller, rows in grouped.items():
        product_types = Counter(str(row.get("product_type", "") or "Unknown") for row in rows)
        seller_focus_tags = _seller_focus_tags(rows)
        seller_focus = seller_focus_tags[0] if seller_focus_tags else ""
        summary = {
            "key": _slug(seller),
            "seller": seller,
            "products": len(rows),
            "seller_leaders": sum(1 for row in rows if _product_has_evidence(row, "seller_leader")),
            "seller_movers": sum(1 for row in rows if _product_has_evidence(row, "seller_mover")),
            "seller_new_pushes": sum(1 for row in rows if _product_has_evidence(row, "seller_new_push")),
            "strong_sub_bsr": sum(1 for row in rows if _product_has_evidence(row, "strong_sub_bsr")),
            "seller_focus": seller_focus,
            "seller_focus_tags": seller_focus_tags,
            "latest_activity": max([str(row.get("date", "") or "") for row in rows] or [""]) or _missing(),
            "representative_products": _seller_product_cards(rows, "title", reverse=False, limit=10),
            "product_explorer_url": f"product_explorer.html?seller={quote_param(seller)}",
            "seller_url": _seller_storefront_url(rows),
        }
        summary["activity_count"] = int(summary["seller_movers"]) + int(summary["seller_new_pushes"])
        summaries.append(summary)
    return sorted(summaries, key=lambda row: (-int(row["activity_count"]), -_date_sort_number(row["latest_activity"]), str(row["seller"]).lower()))


def _seller_storefront_url(rows: list[dict[str, object]]) -> str:
    for row in rows:
        seller_url = str(row.get("seller_url", "") or "").strip()
        if seller_url:
            return seller_url
    return ""


_LOW_VALUE_FOCUS_VALUES = {
    "unknown",
    "uncategorized",
    "n/a",
    "none",
    "-",
    "seller",
    "sellers",
    "product",
    "products",
    "gift",
    "gifts",
    "amazon",
    "custom",
    "personalized",
}
_LOW_VALUE_FOCUS_WORDS = {
    "amazon",
    "gift",
    "gifts",
    "product",
    "products",
    "seller",
    "sellers",
}
_FOCUS_QUALIFIER_WORDS = {"custom", "personalized"}


def _seller_focus_tags(rows: list[dict[str, object]], limit: int = 3) -> list[str]:
    counters: list[Counter[str]] = []
    for fields in (
        ("theme", "idea", "niche_primary", "niche", "category_name"),
        ("product_type",),
        ("style", "occasion", "recipient"),
    ):
        counter: Counter[str] = Counter()
        for row in rows:
            for field in fields:
                value = _clean_focus_value(row.get(field))
                if value:
                    counter[value] += 1
        counters.append(counter)

    tags: list[str] = []
    seen: set[str] = set()
    for counter in counters:
        for label, _ in counter.most_common():
            key = label.casefold()
            if key in seen:
                continue
            tags.append(label)
            seen.add(key)
            if len(tags) >= limit:
                return tags
    return tags


def _clean_focus_value(value: object) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if not text:
        return ""
    normalized = text.casefold()
    if normalized in {*_LOW_VALUE_FOCUS_VALUES, _missing().casefold()}:
        return ""
    tokens = re.findall(r"[a-z0-9]+", normalized)
    if not tokens or all(token in _LOW_VALUE_FOCUS_VALUES for token in tokens):
        return ""
    cleaned_parts = []
    for part in re.split(r"(\W+)", text):
        if re.fullmatch(r"[A-Za-z0-9]+", part) and part.casefold() in _LOW_VALUE_FOCUS_WORDS:
            continue
        cleaned_parts.append(part)
    cleaned = re.sub(r"\s+", " ", "".join(cleaned_parts)).strip(" -/|,")
    cleaned = re.sub(r"^(for|and|the)\s+", "", cleaned, flags=re.IGNORECASE).strip(" -/|,")
    cleaned = re.sub(r"\s+(for|and|the)$", "", cleaned, flags=re.IGNORECASE).strip(" -/|,")
    cleaned_tokens = re.findall(r"[a-z0-9]+", cleaned.casefold())
    if not cleaned_tokens or all(token in _FOCUS_QUALIFIER_WORDS for token in cleaned_tokens):
        return ""
    return cleaned


def _date_sort_number(value: object) -> int:
    digits = re.sub(r"\D+", "", str(value or ""))
    return _num(digits[:8]) if digits else 0


def _seller_table_row(row: dict[str, object]) -> str:
    seller = str(row["seller"])
    product_explorer_url = str(row["product_explorer_url"])
    return f"""          <tr data-seller-row data-seller-key="{escape(str(row['key']))}">
            <td><button class="link-button" type="button" data-seller-select="{escape(str(row['key']))}"><strong>{escape(seller)}</strong></button></td>
            <td class="numeric-cell">{_fmt_int(row['activity_count'])}</td>
            <td class="numeric-cell">{status_badge(_fmt_int(row['seller_new_pushes']), "idea")}</td>
            <td class="numeric-cell">{status_badge(_fmt_int(row['seller_movers']), "rising")}</td>
            <td><a class="utility-link row-open-link seller-open-link" href="{escape(product_explorer_url)}" aria-label="Open {escape(seller)} in Product Explorer" title="Open in Product Explorer">&rarr;</a></td>
          </tr>"""


def _seller_product_cards(rows: list[dict[str, object]], sort_field: str, *, reverse: bool, limit: int = 10) -> list[dict[str, str]]:
    cards = []
    for product, image, image_field in _seller_representative_products(rows, limit=limit):
        asin = str(product.get("asin", "") or "")
        tone = _primary_evidence_tone(product)
        cards.append(
            {
                "title": str(product.get("title", "Untitled Product") or "Untitled Product"),
                "asin": asin,
                "meta": f"{product.get('product_type', 'Unknown')} - {_rank_or_missing(product.get('seller_evidence_best_rank'))}",
                "url": f"product_explorer.html?seller={quote_param(str(product.get('seller', '') or 'Unknown Seller'))}&focus={quote_param(asin)}" if asin else "product_explorer.html",
                "image": image,
                "image_field": image_field,
                "tone": tone,
            }
        )
    return cards


_SELLER_THUMBNAIL_FIELDS = ("thumbnail_url", "image_url", "main_image", "image")
_SELLER_IMAGE_COLLECTION_FIELDS = ("images", "image_urls", "additional_images")
_SELLER_IDENTITY_FIELDS = ("asin", "product_id", "productId", "id", "listing_id", "listingId")
_SELLER_URL_IDENTITY_FIELDS = ("canonical_url", "product_url", "listing_url", "url")


def _seller_representative_products(rows: list[dict[str, object]], *, limit: int = 10) -> list[tuple[dict[str, object], str, str]]:
    indexed = list(enumerate(rows))
    selected: list[tuple[dict[str, object], str, str]] = []
    seen: set[tuple[str, str]] = set()
    for index, product in sorted(indexed, key=lambda item: _seller_product_rank_key(item[1], item[0])):
        image, image_field = _seller_thumbnail_src(product)
        if not image:
            continue
        identity = _seller_product_identity(product, index)
        if identity in seen:
            continue
        seen.add(identity)
        selected.append((product, image, image_field))
        if len(selected) >= limit:
            break
    return selected


def _seller_thumbnail_src(product: dict[str, object]) -> tuple[str, str]:
    for field in _SELLER_THUMBNAIL_FIELDS:
        image = _clean_image_src(product.get(field))
        if image:
            return image, field

    for field in _SELLER_IMAGE_COLLECTION_FIELDS:
        image, image_field = _first_image_from_collection(product.get(field), field)
        if image:
            return image, image_field
    return "", ""


def _first_image_from_collection(value: object, field: str) -> tuple[str, str]:
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return "", ""
        if text.startswith("[") or text.startswith("{"):
            try:
                return _first_image_from_collection(json.loads(text), field)
            except json.JSONDecodeError:
                pass
        for item in re.split(r"[;,]\s*", text):
            image = _clean_image_src(item)
            if image:
                return image, field
        return "", ""

    if isinstance(value, dict):
        for nested_field in ("thumbnail_url", "image_url", "main_image", "image", "url", "src"):
            image = _clean_image_src(value.get(nested_field))
            if image:
                return image, f"{field}.{nested_field}"
        return "", ""

    if isinstance(value, (list, tuple, set)):
        for item in value:
            if isinstance(item, dict):
                image, image_field = _first_image_from_collection(item, field)
            else:
                image = _clean_image_src(item)
                image_field = field
            if image:
                return image, image_field
    return "", ""


def _clean_image_src(value: object) -> str:
    text = str(value or "").strip()
    if not text or text.casefold() in {"-", "n/a", "none", "null", "no image", _missing().casefold()}:
        return ""
    if text.startswith("data:image/svg+xml"):
        return ""
    return text


def _seller_product_identity(product: dict[str, object], index: int) -> tuple[str, str]:
    for field in _SELLER_IDENTITY_FIELDS:
        value = str(product.get(field, "") or "").strip()
        if value:
            normalized = value.upper() if field == "asin" else value.casefold()
            return (field.casefold(), normalized)

    for field in _SELLER_URL_IDENTITY_FIELDS:
        value = _canonical_product_url(product.get(field))
        if value:
            return ("url", value)
    return ("row", str(index))


def _canonical_product_url(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    parsed = urlsplit(text)
    if parsed.scheme and parsed.netloc:
        return urlunsplit((parsed.scheme.casefold(), parsed.netloc.casefold(), parsed.path.rstrip("/"), "", ""))
    return re.split(r"[?#]", text, maxsplit=1)[0].rstrip("/").casefold()


def _seller_product_rank_key(product: dict[str, object], index: int) -> tuple[object, ...]:
    return (
        _missing_high(_seller_display_order_rank(product)),
        _seller_product_identity_sort_value(product, index),
        index,
    )


def _seller_display_order_rank(product: dict[str, object]) -> int | None:
    for field in (
        "source_rank",
        "display_order_rank",
        "display_rank",
        "seller_display_order",
        "display_order",
        "order_rank",
        "rank",
        "position",
    ):
        value = _num_or_none(product.get(field))
        if value is not None:
            return value
    return None


def _seller_product_identity_sort_value(product: dict[str, object], index: int) -> tuple[str, str]:
    identity = _seller_product_identity(product, index)
    if identity[0] != "row":
        return identity
    fallback = str(product.get("title", "") or product.get("asin", "") or index).casefold()
    return ("row", fallback)


def _missing_high(value: int | float | None) -> int | float:
    return value if value is not None else 10**9


def _counter_rows(counter: Counter[str], limit: int = 6) -> list[dict[str, object]]:
    total = sum(counter.values()) or 1
    return [
        {"label": label, "count": count, "share": f"{(count / total) * 100:.1f}%"}
        for label, count in counter.most_common(limit)
    ]


def _competitor_script() -> str:
    return r"""(() => {
    const data = JSON.parse(document.getElementById("seller-explorer-data")?.textContent || "[]");
    const tbody = document.querySelector("[data-seller-tbody]");
    const search = document.getElementById("seller-search");
    const sortSelect = document.querySelector("[data-seller-sort-select]");
    const detail = document.querySelector("[data-seller-detail]");
    let currentSort = "activity";
    let currentPreset = "most_active";
    let pinnedKey = data[0]?.key || "";
    let hoverKey = "";

    render();
    renderDetail(pinnedKey);

    search?.addEventListener("input", render);
    sortSelect?.addEventListener("change", () => {
      currentSort = sortSelect.value || "activity";
      render();
    });
    document.querySelectorAll("[data-seller-preset]").forEach((button) => {
      button.addEventListener("click", () => {
        currentPreset = button.dataset.sellerPreset || "most_active";
        document.querySelectorAll("[data-seller-preset]").forEach((item) => {
          const active = item.dataset.sellerPreset === currentPreset;
          item.classList.toggle("btn-secondary", active);
          item.classList.toggle("btn-ghost", !active);
          item.setAttribute("aria-pressed", active ? "true" : "false");
        });
        render();
      });
    });
    document.querySelector("[data-seller-table]")?.addEventListener("click", (event) => {
      const sortButton = event.target.closest("[data-seller-sort]");
      if (sortButton) {
        currentSort = sortButton.dataset.sellerSort;
        if (sortSelect) sortSelect.value = currentSort;
        render();
        return;
      }
      const select = event.target.closest("[data-seller-select]");
      if (select) {
        pinnedKey = select.dataset.sellerSelect;
        hoverKey = "";
        renderDetail(pinnedKey);
        renderSelection();
        return;
      }
      const row = event.target.closest("[data-seller-row]");
      if (row && !event.target.closest(".row-open-link")) {
        pinnedKey = row.dataset.sellerKey;
        hoverKey = "";
        renderDetail(pinnedKey);
        renderSelection();
      }
    });
    document.querySelector("[data-seller-table]")?.addEventListener("pointerover", (event) => {
      const row = event.target.closest("[data-seller-row]");
      if (!row || row.dataset.sellerKey === hoverKey) return;
      hoverKey = row.dataset.sellerKey;
      renderDetail(hoverKey, { temporary: true });
    });
    document.querySelector("[data-seller-table]")?.addEventListener("pointerout", (event) => {
      const row = event.target.closest("[data-seller-row]");
      if (!row) return;
      if (event.relatedTarget && row.contains(event.relatedTarget)) return;
      if (hoverKey === row.dataset.sellerKey) hoverKey = "";
      renderDetail(pinnedKey);
    });

    function render() {
      if (!tbody) return;
      const query = (search?.value || "").trim().toLowerCase();
      const rows = data
        .filter((seller) => presetMatches(seller))
        .filter((seller) => !query || seller.seller.toLowerCase().includes(query));
      rows.sort((left, right) => compareSeller(left, right, currentSort));
      tbody.innerHTML = rows.map(sellerRowHtml).join("");
      renderSelection();
    }

    function compareSeller(left, right, key) {
      if (key === "activity") {
        return Number(right.activity_count || 0) - Number(left.activity_count || 0)
          || compareLatestActivity(left.latest_activity, right.latest_activity)
          || String(left.seller || "").localeCompare(String(right.seller || ""), undefined, { sensitivity: "base", numeric: true });
      }
      const leftValue = left[key];
      const rightValue = right[key];
      const leftMissing = leftValue === "" || leftValue === null || leftValue === "\u2014";
      const rightMissing = rightValue === "" || rightValue === null || rightValue === "\u2014";
      if (leftMissing !== rightMissing) return leftMissing ? 1 : -1;
      if (key === "latest_activity") return compareLatestActivity(leftValue, rightValue);
      if (typeof leftValue === "number" || typeof rightValue === "number") return Number(rightValue || 0) - Number(leftValue || 0);
      return String(leftValue || "").localeCompare(String(rightValue || ""), undefined, { sensitivity: "base", numeric: true });
    }

    function presetMatches(seller) {
      if (currentPreset === "new_push") return Number(seller.seller_new_pushes || 0) > 0;
      if (currentPreset === "strong_catalog") return Number(seller.seller_leaders || 0) > 0 || Number(seller.strong_sub_bsr || 0) > 0;
      return true;
    }

    function compareLatestActivity(left, right) {
      const leftDate = Date.parse(left || "");
      const rightDate = Date.parse(right || "");
      const leftMissing = !Number.isFinite(leftDate);
      const rightMissing = !Number.isFinite(rightDate);
      if (leftMissing !== rightMissing) return leftMissing ? 1 : -1;
      if (!leftMissing && leftDate !== rightDate) return rightDate - leftDate;
      return String(right || "").localeCompare(String(left || ""), undefined, { sensitivity: "base", numeric: true });
    }

    function sellerRowHtml(row) {
      return `<tr data-seller-row data-seller-key="${escapeHtml(row.key)}">
        <td><button class="link-button" type="button" data-seller-select="${escapeHtml(row.key)}"><strong>${escapeHtml(row.seller)}</strong></button></td>
        <td class="numeric-cell">${formatNumber(row.activity_count)}</td>
        <td class="numeric-cell">${badge(row.seller_new_pushes, "idea")}</td>
        <td class="numeric-cell">${badge(row.seller_movers, "rising")}</td>
        <td><a class="utility-link row-open-link seller-open-link" href="${escapeHtml(row.product_explorer_url)}" aria-label="Open ${escapeHtml(row.seller)} in Product Explorer" title="Open in Product Explorer">&rarr;</a></td>
      </tr>`;
    }

    function renderSelection() {
      document.querySelectorAll("[data-seller-row]").forEach((row) => row.classList.toggle("is-focused", row.dataset.sellerKey === pinnedKey));
    }

    function renderDetail(key, { temporary = false } = {}) {
      const seller = data.find((row) => row.key === key);
      if (!detail || !seller) return;
      detail.innerHTML = `<div class="seller-preview-header">
          <h2>${escapeHtml(seller.seller)}</h2>
        </div>
        ${sellerFocusHtml(seller)}
        <section class="seller-preview-section">
          <h3>Display Order Preview</h3>
          ${sellerThumbnailStrip(seller.representative_products)}
        </section>
        <div class="seller-preview-stats" aria-label="Seller activity">
          ${sellerStat("Products", formatNumber(seller.products))}
          ${sellerStat("Fast Movers", formatNumber(seller.seller_movers))}
          ${sellerStat("New Pushes", formatNumber(seller.seller_new_pushes))}
        </div>
        <div class="seller-preview-actions">
          <a class="btn btn-primary seller-preview-cta" href="${escapeHtml(seller.product_explorer_url)}">Open in Product Explorer &rarr;</a>
          ${sellerStoreCta(seller)}
        </div>`;
      detail.classList.toggle("is-previewing", temporary);
    }

    function sellerStoreCta(seller) {
      const storeUrl = String(seller.seller_url || "").trim();
      if (!storeUrl) {
        return `<button class="btn btn-secondary seller-preview-cta seller-preview-cta-secondary" type="button" disabled>Store unavailable</button>`;
      }
      return `<a class="btn btn-secondary seller-preview-cta seller-preview-cta-secondary" href="${escapeHtml(storeUrl)}" target="_blank" rel="noopener">View Amazon Store &#8599;</a>`;
    }

    function sellerFocusHtml(seller) {
      const tags = Array.isArray(seller.seller_focus_tags)
        ? seller.seller_focus_tags
        : String(seller.seller_focus || "").split(/[;,]/);
      const cleanTags = tags.map((tag) => String(tag || "").trim()).filter((tag) => tag && tag.toLowerCase() !== "unknown").slice(0, 3);
      if (!cleanTags.length) return "";
      return `<section class="seller-focus-section" aria-label="Seller focus">
        <span>Seller Focus</span>
        <div class="seller-focus-tags">${cleanTags.map((tag) => `<strong>${escapeHtml(tag)}</strong>`).join("")}</div>
      </section>`;
    }

    function sellerThumbnailStrip(rows) {
      const products = Array.isArray(rows) ? rows.slice(0, 10) : [];
      const productCells = products.map((row) => `<a class="seller-thumbnail-card" href="${escapeHtml(row.url)}" title="${escapeHtml(row.title)}" aria-label="${escapeHtml(row.title)}">
        <img src="${escapeHtml(row.image || "")}" alt="${escapeHtml(row.title)} thumbnail">
      </a>`).join("");
      return `<div class="seller-thumbnail-strip" aria-label="Display order products">${productCells}</div>`;
    }

    function sellerStat(label, value) {
      return `<div class="seller-preview-stat"><strong>${escapeHtml(value)}</strong><span>${escapeHtml(label)}</span></div>`;
    }
    function badge(value, tone) {
      return `<span class="status-badge tone-${tone}">${formatNumber(value)}</span>`;
    }
    function formatNumber(value) {
      return Number(value || 0).toLocaleString();
    }
    function escapeHtml(value) {
      return String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
    }
  })();"""


def _market_group_payload(products: list[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    return {
        "category": _market_groups(products, "category"),
        "product_type": _market_groups(products, "product_type"),
    }


def _market_groups(products: list[dict[str, object]], mode: str) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for product in products:
        label = _market_group_label(product, mode)
        grouped.setdefault(label, []).append(product)
    rows = []
    for label, group_products in grouped.items():
        price_values = [_float_or_none(product.get("price_value")) for product in group_products if _float_or_none(product.get("price_value")) is not None]
        rating_values = [_float_or_none(product.get("review_rating")) for product in group_products if _float_or_none(product.get("review_rating")) is not None]
        review_values = [_num_or_none(product.get("review_count")) for product in group_products if _num_or_none(product.get("review_count")) is not None]
        sub_bsr_values = [_valid_sub_bsr(product) for product in group_products if _valid_sub_bsr(product) is not None]
        coverage = {
            "seller": sum(1 for product in group_products if _product_has_evidence_data(product, "seller")),
            "best_seller": sum(1 for product in group_products if _product_has_evidence_data(product, "best_seller")),
            "new_release": sum(1 for product in group_products if _product_has_evidence_data(product, "new_release")),
            "bsr": sum(1 for product in group_products if _product_has_evidence_data(product, "supporting")),
        }
        rows.append(
            {
                "key": f"{mode}:{_slug(label)}",
                "label": label,
                "mode": mode,
                "market_tags": _market_tags(label, mode, group_products),
                "representative_products": _market_product_cards(group_products, mode, label, limit=10),
                "leading_sellers": _market_leading_sellers(group_products, limit=5),
                "product_count": len(group_products),
                "seller_count": len({str(product.get("seller", "") or "Unknown Seller") for product in group_products}),
                "coverage": coverage,
                "seller_leader_count": sum(1 for product in group_products if _product_has_evidence(product, "seller_leader")),
                "seller_mover_count": sum(1 for product in group_products if _product_has_evidence(product, "seller_mover")),
                "category_winner_count": sum(1 for product in group_products if _product_has_evidence(product, "category_winner")),
                "category_breakout_count": sum(1 for product in group_products if _product_has_evidence(product, "category_breakout")),
                "new_release_rising_count": sum(1 for product in group_products if _product_has_evidence(product, "new_release_rising")),
                "new_release_breakout_count": sum(1 for product in group_products if _product_has_evidence(product, "new_release_breakout")),
                "strong_sub_bsr_count": sum(1 for product in group_products if _product_has_evidence(product, "strong_sub_bsr")),
                "very_strong_sub_bsr_count": sum(1 for product in group_products if _product_has_evidence(product, "very_strong_sub_bsr")),
                "median_price": _median_float(price_values),
                "median_rating": _median_float(rating_values),
                "median_review_count": _median(review_values),
                "median_sub_bsr": _median(sub_bsr_values),
                "product_explorer_url": _market_deep_link(mode, label),
            }
        )
    for row in rows:
        row["momentum_total"] = int(row["seller_mover_count"]) + int(row["new_release_rising_count"])
        row["validation_total"] = int(row["category_winner_count"]) + int(row["strong_sub_bsr_count"])
        row["breakout_total"] = int(row["category_breakout_count"]) + int(row["new_release_breakout_count"])
    return sorted(rows, key=lambda row: (-int(row["breakout_total"]), -int(row["momentum_total"]), -int(row["product_count"]), str(row["label"]).lower()))


def _market_tags(label: str, mode: str, products: list[dict[str, object]], limit: int = 3) -> list[str]:
    if mode == "product_type":
        tag_fields = ("idea", "category_name", "theme", "occasion", "recipient")
    else:
        tag_fields = ("product_type", "theme", "occasion", "recipient")
    tags: list[str] = []
    seen = {label.casefold()}
    for field in tag_fields:
        counter: Counter[str] = Counter()
        for product in products:
            value = _clean_focus_value(product.get(field))
            if value and value.casefold() not in seen:
                counter[value] += 1
        for value, _ in counter.most_common():
            key = value.casefold()
            if key in seen:
                continue
            tags.append(value)
            seen.add(key)
            if len(tags) >= limit:
                return tags
    return tags


def _market_product_cards(rows: list[dict[str, object]], mode: str, label: str, *, limit: int = 10) -> list[dict[str, str]]:
    cards = []
    base_url = _market_deep_link(mode, label)
    for product, image, image_field in _seller_representative_products(rows, limit=limit):
        asin = str(product.get("asin", "") or "")
        href = f"{base_url}&focus={quote_param(asin)}" if asin and "?" in base_url else f"{base_url}?focus={quote_param(asin)}" if asin else base_url
        cards.append(
            {
                "title": str(product.get("title", "Untitled Product") or "Untitled Product"),
                "asin": asin,
                "url": href,
                "image": image,
                "image_field": image_field,
            }
        )
    return cards


def _market_leading_sellers(products: list[dict[str, object]], limit: int = 5) -> list[str]:
    counter: Counter[str] = Counter()
    for product in products:
        seller = str(product.get("seller", "") or "Unknown Seller").strip() or "Unknown Seller"
        counter[seller] += 1
    return [seller for seller, _ in sorted(counter.items(), key=lambda item: (-item[1], item[0].casefold()))[:limit]]


def _market_group_label(product: dict[str, object], mode: str) -> str:
    if mode == "product_type":
        return str(product.get("product_type", "") or "Unknown")
    return str(product.get("idea", "") or product.get("category_name", "") or "Unknown")


def _market_deep_link(mode: str, label: str) -> str:
    if mode == "product_type":
        return f"product_explorer.html?type={quote_param(label)}"
    return f"product_explorer.html?q={quote_param(label)}"


def _market_script() -> str:
    return r"""(() => {
    const payload = JSON.parse(document.getElementById("market-explorer-data")?.textContent || "{}");
    const tbody = document.querySelector("[data-market-tbody]");
    const empty = document.querySelector("[data-market-empty]");
    const detail = document.querySelector("[data-market-detail]");
    const search = document.getElementById("market-search");
    const sortSelect = document.querySelector("[data-market-sort]");
    const minProducts = document.querySelector("[data-market-min-products]");
    const sourceFamily = document.querySelector("[data-market-source-family]");
    let mode = "category";
    let pinnedKey = "";
    let hoverKey = "";
    let currentRows = [];

    renderMarket();
    document.querySelectorAll("[data-market-mode]").forEach((button) => {
      button.addEventListener("click", () => {
        mode = button.dataset.marketMode;
        pinnedKey = "";
        hoverKey = "";
        document.querySelectorAll("[data-market-mode]").forEach((item) => {
          const active = item.dataset.marketMode === mode;
          item.classList.toggle("btn-secondary", active);
          item.classList.toggle("btn-ghost", !active);
          item.setAttribute("aria-pressed", active ? "true" : "false");
        });
        renderMarket();
      });
    });
    [search, sortSelect, minProducts, sourceFamily].forEach((control) => control?.addEventListener("input", renderMarket));
    [sortSelect, sourceFamily].forEach((control) => control?.addEventListener("change", renderMarket));
    document.querySelector("[data-market-table]")?.addEventListener("click", (event) => {
      if (event.target.closest(".row-open-link") || event.target.closest(".market-detail summary")) return;
      const select = event.target.closest("[data-market-select]");
      const row = select ? select.closest("[data-market-row]") : event.target.closest("[data-market-row]");
      if (!row) return;
      pinnedKey = row.dataset.marketKey || "";
      hoverKey = "";
      renderDetail(pinnedKey);
      renderSelection();
    });
    document.querySelector("[data-market-table]")?.addEventListener("pointerover", (event) => {
      const row = event.target.closest("[data-market-row]");
      if (!row || row.dataset.marketKey === hoverKey) return;
      hoverKey = row.dataset.marketKey || "";
      renderDetail(hoverKey, { temporary: true });
    });
    document.querySelector("[data-market-table]")?.addEventListener("pointerout", (event) => {
      const row = event.target.closest("[data-market-row]");
      if (!row) return;
      if (event.relatedTarget && row.contains(event.relatedTarget)) return;
      if (hoverKey === row.dataset.marketKey) hoverKey = "";
      renderDetail(pinnedKey);
    });

    function renderMarket() {
      const query = (search?.value || "").trim().toLowerCase();
      const sortKey = sortSelect?.value || "default";
      const minCount = Number(minProducts?.value || 0);
      const family = sourceFamily?.value || "";
      currentRows = (payload[mode] || [])
        .filter((row) => row.product_count >= minCount)
        .filter((row) => !query || row.label.toLowerCase().includes(query))
        .filter((row) => !family || Number(row.coverage?.[family] || 0) > 0)
        .sort((left, right) => compareMarket(left, right, sortKey));
      if (tbody) tbody.innerHTML = currentRows.map(marketRowHtml).join("");
      if (empty) empty.hidden = currentRows.length > 0;
      if (!currentRows.find((row) => row.key === pinnedKey)) pinnedKey = currentRows[0]?.key || "";
      renderDetail(pinnedKey);
      renderSelection();
    }

    function compareMarket(left, right, key) {
      if (key === "default") {
        return Number(right.breakout_total || 0) - Number(left.breakout_total || 0)
          || Number(right.momentum_total || 0) - Number(left.momentum_total || 0)
          || Number(right.product_count || 0) - Number(left.product_count || 0)
          || String(left.label || "").localeCompare(String(right.label || ""), undefined, { sensitivity: "base", numeric: true });
      }
      const leftValue = left[key];
      const rightValue = right[key];
      const leftMissing = leftValue === null || leftValue === undefined || leftValue === "";
      const rightMissing = rightValue === null || rightValue === undefined || rightValue === "";
      if (leftMissing !== rightMissing) return leftMissing ? 1 : -1;
      if (key === "median_sub_bsr") return Number(leftValue || 0) - Number(rightValue || 0);
      if (typeof leftValue === "number" || typeof rightValue === "number") return Number(rightValue || 0) - Number(leftValue || 0);
      return String(leftValue || "").localeCompare(String(rightValue || ""), undefined, { sensitivity: "base", numeric: true });
    }

    function marketRowHtml(row) {
      return `<tr data-market-row data-market-key="${escapeHtml(row.key)}">
        <td><button class="link-button" type="button" data-market-select="${escapeHtml(row.key)}"><strong>${escapeHtml(row.label)}</strong></button>${marketDetail(row)}</td>
        <td>${summaryValue("Momentum", Number(row.seller_mover_count || 0) + Number(row.new_release_rising_count || 0))}</td>
        <td>${summaryValue("Validation", Number(row.category_winner_count || 0) + Number(row.strong_sub_bsr_count || 0))}</td>
        <td>${escapeHtml(`${formatNumber(row.seller_count)} sellers`)}<span class="caption market-caption">${escapeHtml(row.median_review_count === null ? "Median reviews unknown" : `Median ${formatNumber(row.median_review_count)} reviews`)}</span></td>
        <td><a class="utility-link row-open-link" href="${escapeHtml(row.product_explorer_url)}">Open</a></td>
      </tr>`;
    }

    function marketDetail(row) {
      return `<details class="market-detail"><summary>Details</summary>
        <div class="metric-grid">
          ${metric("Products", formatNumber(row.product_count))}
          ${metric("Active Sellers", formatNumber(row.seller_count))}
          ${metric("Breakouts", formatNumber(Number(row.category_breakout_count || 0) + Number(row.new_release_breakout_count || 0)))}
        </div>
        ${marketLeadingSellers(row.leading_sellers, "Leading Sellers")}
      </details>`;
    }

    function renderSelection() {
      document.querySelectorAll("[data-market-row]").forEach((row) => row.classList.toggle("is-focused", row.dataset.marketKey === pinnedKey));
    }

    function renderDetail(key, { temporary = false } = {}) {
      const row = currentRows.find((item) => item.key === key) || (payload[mode] || []).find((item) => item.key === key);
      if (!detail) return;
      if (!row) {
        detail.innerHTML = `<div class="empty-state"><strong>Select a market</strong><p>Choose a market row to preview products and open Product Explorer.</p></div>`;
        return;
      }
      detail.innerHTML = `<div class="market-preview-header">
          <h2>${escapeHtml(row.label)}</h2>
          <p class="caption">${escapeHtml(labelForMode(row.mode || mode))} market</p>
        </div>
        ${marketTags(row)}
        <section class="market-preview-section">
          <h3>Representative Products</h3>
          ${marketProductGrid(row.representative_products)}
        </section>
        <section class="market-preview-section">
          <h3>Leading Sellers</h3>
          ${marketLeadingSellers(row.leading_sellers, "Leading sellers")}
        </section>
        <section class="market-preview-section">
          <h3>Market Health</h3>
          <div class="market-preview-stats" aria-label="Market health">
            ${marketStat("Products", formatNumber(row.product_count))}
            ${marketStat("Active Sellers", formatNumber(row.seller_count))}
            ${marketStat("Breakouts", formatNumber(Number(row.category_breakout_count || 0) + Number(row.new_release_breakout_count || 0)))}
          </div>
        </section>
        <a class="btn btn-primary market-preview-cta" href="${escapeHtml(row.product_explorer_url)}">Open Product Explorer &rarr;</a>`;
      detail.classList.toggle("is-previewing", temporary);
    }

    function marketTags(row) {
      const tags = Array.isArray(row.market_tags) ? row.market_tags.slice(0, 3) : [];
      if (!tags.length) return "";
      return `<section class="market-tags-section" aria-label="Market tags">
        <span>Market Tags</span>
        <div class="market-tags">${tags.map((tag) => `<strong>${escapeHtml(tag)}</strong>`).join("")}</div>
      </section>`;
    }

    function marketProductGrid(rows) {
      const products = Array.isArray(rows) ? rows.slice(0, 10) : [];
      if (!products.length) return `<div class="inspector-no-data">No product images available</div>`;
      return `<div class="market-product-grid" aria-label="Representative products">${products.map((row) => `<a class="market-product-card" href="${escapeHtml(row.url)}" title="${escapeHtml(row.title)}" aria-label="${escapeHtml(row.title)}">
        <img src="${escapeHtml(row.image || "")}" alt="${escapeHtml(row.title)} thumbnail">
      </a>`).join("")}</div>`;
    }

    function marketLeadingSellers(values, label) {
      const sellers = Array.isArray(values) ? values.slice(0, 5).filter(Boolean) : [];
      if (!sellers.length) return `<div class="inspector-no-data">No seller data available</div>`;
      return `<div class="market-leading-sellers" aria-label="${escapeHtml(label)}">${sellers.map((seller) => `<span>${escapeHtml(seller)}</span>`).join("")}</div>`;
    }

    function marketStat(label, value) {
      return `<div class="market-preview-stat"><strong>${escapeHtml(value)}</strong><span>${escapeHtml(label)}</span></div>`;
    }

    function summaryValue(label, value) {
      return `<span class="compact-summary-value" title="${escapeHtml(label)}">${formatNumber(value)}</span>`;
    }

    function metric(label, value) {
      return `<div class="metric"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`;
    }

    function labelForMode(value) {
      return value === "product_type" ? "Product Type" : "Category";
    }
    function formatNumber(value) {
      return Number(value || 0).toLocaleString();
    }
    function escapeHtml(value) {
      return String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
    }
  })();"""


def _idea_dimension_payload(products: list[dict[str, object]], ideas: list[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    legacy_scores = {str(row.get("idea", "") or "").strip().lower(): row.get("winner_score") for row in ideas if isinstance(row, dict)}
    return {
        "recipient": _idea_dimension_rows(products, "recipient", legacy_scores),
        "occasion": _idea_dimension_rows(products, "occasion", legacy_scores),
        "theme": _idea_dimension_rows(products, "theme", legacy_scores),
        "product_type": _idea_dimension_rows(products, "product_type", legacy_scores),
    }


def _idea_dimension_rows(
    products: list[dict[str, object]],
    field: str,
    legacy_scores: dict[str, object],
) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for product in products:
        label = str(product.get(field, "") or "Unknown").strip() or "Unknown"
        grouped.setdefault(label, []).append(product)
    rows = []
    for label, group_products in grouped.items():
        movers = sum(1 for product in group_products if _product_has_evidence(product, "seller_mover"))
        new_pushes = sum(1 for product in group_products if _product_has_evidence(product, "seller_new_push"))
        winners = sum(1 for product in group_products if _product_has_evidence(product, "category_winner") or _product_has_evidence(product, "seller_leader"))
        breakouts = sum(1 for product in group_products if _product_has_evidence(product, "category_breakout") or _product_has_evidence(product, "new_release_breakout"))
        low_review = sum(
            1
            for product in group_products
            if (reviews := _num_or_none(product.get("review_count", product.get("reviews")))) is not None and reviews <= 100
        )
        product_explorer_url = f"product_explorer.html?{_dimension_product_param(field)}={quote_param(label)}"
        preview_products = _idea_product_cards(group_products, field, label, limit=10)
        representative = _diverse_products(_sort_products_for_preset(group_products, "research_today"), limit=1)
        product = representative[0] if representative else group_products[0]
        asin = str(product.get("asin", "") or product.get("id", "") or "")
        representative_url = preview_products[0]["url"] if preview_products else f"{product_explorer_url}&focus={quote_param(asin)}" if asin else product_explorer_url
        rows.append(
            {
                "idea": label,
                "dimension": field,
                "products": len(group_products),
                "active_sellers": len({str(product.get("seller", "") or "Unknown Seller") for product in group_products}),
                "movers": movers,
                "new_pushes": new_pushes,
                "winners": winners,
                "breakouts": breakouts,
                "low_review_opportunities": low_review,
                "idea_tags": _idea_preview_tags(label, field, group_products),
                "representative_products": preview_products,
                "representative_product": str(product.get("title", "Untitled Product") or "Untitled Product"),
                "representative_seller": str(product.get("seller", "Unknown Seller") or "Unknown Seller"),
                "representative_reason": _why_it_matters(product),
                "representative_url": representative_url,
                "product_explorer_url": product_explorer_url,
                "legacy_score": legacy_scores.get(label.lower()),
            }
        )
    return sorted(rows, key=lambda row: (-int(row["breakouts"]), -int(row["movers"]), -int(row["products"]), str(row["idea"]).lower()))


def _idea_product_cards(rows: list[dict[str, object]], field: str, label: str, *, limit: int = 10) -> list[dict[str, str]]:
    cards = []
    product_explorer_url = f"product_explorer.html?{_dimension_product_param(field)}={quote_param(label)}"
    for product, image, image_field in _seller_representative_products(rows, limit=limit):
        asin = str(product.get("asin", "") or "")
        cards.append(
            {
                "title": str(product.get("title", "Untitled Product") or "Untitled Product"),
                "asin": asin,
                "url": f"{product_explorer_url}&focus={quote_param(asin)}" if asin else product_explorer_url,
                "image": image,
                "image_field": image_field,
            }
        )
    return cards


def _idea_preview_tags(label: str, field: str, products: list[dict[str, object]], limit: int = 3) -> list[str]:
    tag_fields = [name for name in ("theme", "product_type", "occasion", "recipient") if name != field]
    tags: list[str] = []
    seen = {label.casefold()}
    for tag_field in tag_fields:
        counter: Counter[str] = Counter()
        for product in products:
            value = _clean_focus_value(product.get(tag_field))
            if value and value.casefold() not in seen:
                counter[value] += 1
        for value, _ in counter.most_common():
            key = value.casefold()
            if key in seen:
                continue
            tags.append(value)
            seen.add(key)
            if len(tags) >= limit:
                return tags
    return tags


def _dimension_product_param(field: str) -> str:
    return {
        "product_type": "type",
        "recipient": "recipient",
        "theme": "theme",
        "occasion": "occasion",
    }.get(field, "q")


def _idea_evidence_views(products: list[dict[str, object]]) -> str:
    views = [
        ("Seller Momentum", [product for product in products if _product_has_evidence(product, "seller_mover")], "seller_movement", True, "Ordered by Seller Movement"),
        ("Category Validation", [product for product in products if _product_has_evidence(product, "category_winner")], "best_seller_evidence_best_rank", False, "Ordered by Best Seller Rank"),
        ("New Release Momentum", [product for product in products if _product_has_evidence(product, "new_release_rising")], "new_release_movement", True, "Ordered by New Release Movement"),
        ("Strong BSR Support", [product for product in products if _product_has_evidence(product, "strong_sub_bsr")], "bsr_evidence_best_sub_bsr", False, "Ordered by Sub-BSR"),
        ("Multi-Evidence Products", [product for product in products if _num(product.get("evidence_count")) >= 2], "evidence_count", True, "Ordered by Evidence Count"),
    ]
    sections = []
    for title, rows, sort_field, reverse, ordering in views:
        sorted_rows = _diverse_products(sorted(rows, key=lambda product: _sort_product_value(product, sort_field, reverse), reverse=reverse), limit=8)
        items = "\n".join(_idea_product_item(product, ordering) for product in sorted_rows) or empty_state("No qualifying products", "This evidence-led view has no matching products.")
        sections.append(f"""      <section class="panel">
{section_header(title, ordering)}
        <div class="activity-list">{items}</div>
      </section>""")
    return "\n".join(sections)


def _sort_product_value(product: dict[str, object], field: str, reverse: bool) -> object:
    value = _num_or_none(product.get(field))
    if value is None:
        return -10**9 if reverse else 10**9
    return value


def _idea_product_item(product: dict[str, object], ordering: str) -> str:
    asin = str(product.get("asin", "") or "")
    title = str(product.get("title", "Untitled Product") or "Untitled Product")
    idea = str(product.get("idea", "Uncategorized") or "Uncategorized")
    href = f"product_explorer.html?q={quote_param(idea)}&focus={quote_param(asin)}" if asin else f"product_explorer.html?q={quote_param(idea)}"
    return f"""          <a class="activity-item" href="{href}">
            <span><strong>{escape(title)}</strong><span class="caption">{escape(idea)} - {escape(ordering)}</span></span>
            {status_badge(str(product.get("evidence_count", "0") or "0"), "idea")}
          </a>"""


def _top_idea_card(item: dict[str, object]) -> str:
    growth = str(item.get("growth", item.get("signal", "")) or "")
    competition = str(item.get("competition", "Unknown") or "Unknown")
    score = str(item.get("score", item.get("winner_score", "0")) or "0")
    return f"""          <article class="idea-summary-card">
            <div>
              <h3>{escape(str(item["title"]))}</h3>
              <p>{escape(str(item["meta"]))}</p>
            </div>
            <div class="idea-summary-metrics">
              {status_badge(score, _score_tone(int(score)))}
              {status_badge(growth, "rising")}
              {status_badge(competition, _competition_tone(competition))}
            </div>
          </article>"""


def _mover_row(item: dict[str, object]) -> str:
    seller = str(item.get("seller", "Unknown Seller") or "Unknown Seller")
    growth = str(item.get("growth", item.get("signal", "")) or "")
    return f"""          <article class="mover-row">
            <div>
              <h3>{escape(str(item["title"]))}</h3>
              <p>{escape(seller)}</p>
            </div>
            <span>{status_badge(growth, "rising")}</span>
            <strong>{escape(str(item["meta"]))}</strong>
          </article>"""


def _bar_or_empty(items: list[dict[str, object]], title: str) -> str:
    return bar_list(items) if items else empty_state(title, "No rows found in the presentation data.")


def _saved_view_rows(products: list[dict[str, object]]) -> list[str]:
    return [
        saved_view_item("All Products", icon="grid", active=True, key="all"),
        saved_view_item("New Winners", icon="star", key="new_winners"),
        saved_view_item("Fast Rising", icon="trend", key="fast_rising"),
        saved_view_item(
            "Low Competition",
            icon="low",
            key="low_competition",
            disabled=True,
            title="Competition is not available in the current Product contract.",
        ),
        saved_view_item("Christmas", icon="calendar", key="christmas"),
        saved_view_item("Grandpa", icon="person", key="grandpa"),
        saved_view_item("Mug", icon="mug", key="mug"),
        saved_view_item("Metal Sign", icon="sign", key="metal_sign"),
    ]


EVIDENCE_FILTER_GROUPS = [
    (
        "seller",
        "Seller Evidence",
        [
            ("seller_leader", "Seller Leader", "winner", "Top 10 in the same tracked seller source for at least 7 days."),
            ("seller_mover", "Seller Mover", "rising", "Improved at least 10 positions within the same seller source."),
            ("seller_new_push", "Seller New Push", "idea", "Recently observed product currently in the seller source top 20."),
        ],
    ),
    (
        "best_seller",
        "Best Seller Evidence",
        [
            ("category_winner", "Category Winner", "winner", "Top 30 in a tracked Best Seller category with sufficient observation history."),
            ("category_breakout", "Category Breakout", "rising", "Improved at least 15 positions and reached the category top 50."),
            ("category_stable", "Category Stable", "stable", "Stayed in a tracked Best Seller category top 100 for at least 14 days."),
        ],
    ),
    (
        "new_release",
        "New Release Evidence",
        [
            ("new_release_rising", "New Release Rising", "rising", "Improved at least 10 positions in the same New Release category."),
            ("new_release_breakout", "New Release Breakout", "winner", "Improved at least 30 positions and reached the New Release top 30."),
            ("new_release_watch", "New Release Candidate", "idea", "Recently observed product in a tracked New Release top 100."),
        ],
    ),
    (
        "supporting",
        "Supporting Evidence",
        [
            ("strong_sub_bsr", "Strong Sub-BSR", "stable", "Sub-category BSR is 5,000 or better."),
            ("very_strong_sub_bsr", "Very Strong Sub-BSR", "winner", "Sub-category BSR is 1,000 or better."),
        ],
    ),
]


def _legacy_signal_rows(products: list[dict[str, object]]) -> list[str]:
    return [
        compact_filter_row("Legacy Winner", _quick_count(products, "winner"), "winner", key="winner", title="Legacy analytics signal kept for compatibility."),
        compact_filter_row("Legacy Rising", _quick_count(products, "rising"), "rising", key="rising", title="Legacy analytics signal kept for compatibility."),
    ]


def _quick_filter_rows(products: list[dict[str, object]]) -> list[str]:
    return [
        compact_filter_row("Low Review", _quick_count(products, "low_reviews"), "idea", key="low_reviews"),
        compact_filter_row(
            "New Launch",
            _quick_count(products, "new_launch"),
            "alert",
            key="new_launch",
            title="Mapped to the existing New Release/New Launch classification.",
        ),
    ]


def _evidence_filter_controls(products: list[dict[str, object]]) -> str:
    groups = []
    for family, label, options in EVIDENCE_FILTER_GROUPS:
        option_html = "\n".join(
            f"""              <label class="evidence-filter-option tone-{tone_name(tone)}" title="{escape(definition)}">
                <input type="checkbox" data-evidence-family="{escape(family)}" data-evidence-filter="{escape(key)}">
                <span>{escape(option_label)}</span>
                <strong>{_evidence_count(products, key)}</strong>
              </label>"""
            for key, option_label, tone, definition in options
        )
        groups.append(
            f"""            <fieldset class="evidence-filter-group" data-evidence-filter-group="{escape(family)}">
              <legend>{escape(label)}</legend>
{option_html}
            </fieldset>"""
        )
    return f"""          <div class="evidence-filter-groups" data-evidence-filters>
{chr(10).join(groups)}
          </div>"""


def _sort_controls() -> str:
    options = [
        ("", "Sort"),
        ("momentum", "Momentum"),
        ("title", "Product"),
        ("seller", "Seller"),
        ("idea", "Idea"),
        ("winner_score", "Winner Score"),
        ("growth", "Growth"),
        ("reviews", "Reviews"),
        ("price", "Price"),
        ("evidence_count", "Evidence Count"),
        ("seller_best_rank", "Seller Best Rank"),
        ("seller_movement", "Seller Movement"),
        ("best_seller_rank", "Best Seller Rank"),
        ("best_seller_movement", "Best Seller Movement"),
        ("new_release_rank", "New Release Rank"),
        ("new_release_movement", "New Release Movement"),
        ("sub_bsr", "Sub-category BSR"),
    ]
    option_html = "".join(f'<option value="{escape(value)}">{escape(label)}</option>' for value, label in options)
    return f"""<label class="caption" for="product-sort-select">Sort</label>
              <select id="product-sort-select" class="select-input sort-select" data-sort-select aria-label="Sort products">
                {option_html}
              </select>
              <select class="select-input sort-direction-select" data-sort-direction-select aria-label="Sort direction">
                <option value="asc">Asc</option>
                <option value="desc">Desc</option>
              </select>"""


def _evidence_count(products: list[dict[str, object]], key: str) -> int:
    return sum(1 for product in products if bool(product.get(key) or product.get(_product_evidence_field(key))))


def _product_evidence_field(key: str) -> str:
    return {
        "seller_leader": "seller_evidence_leader",
        "seller_mover": "seller_evidence_mover",
        "seller_new_push": "seller_evidence_new_push",
        "category_winner": "best_seller_evidence_winner",
        "category_breakout": "best_seller_evidence_breakout",
        "category_stable": "best_seller_evidence_stable",
        "new_release_rising": "new_release_evidence_rising",
        "new_release_breakout": "new_release_evidence_breakout",
        "new_release_watch": "new_release_evidence_watch",
        "strong_sub_bsr": "bsr_evidence_strong",
        "very_strong_sub_bsr": "bsr_evidence_very_strong",
    }.get(key, key)


def _single_category_filter_control(field: str, label: str) -> str:
    return f"""            <label class="filter-control minimal-filter-control" for="product-filter-{escape(field)}">
              <span>{escape(label)}</span>
              <select id="product-filter-{escape(field)}" class="filter-select compact-filter-select" multiple size="4" data-filter-select="{escape(field)}" aria-label="{escape(label)} filter"></select>
            </label>"""


DEFAULT_POD_FILTER = "pod"
POD_FILTER_OPTIONS = (
    ("all", "All Products"),
    ("pod", "POD Products"),
    ("non_pod", "Non-POD Products"),
    ("unknown", "Unknown"),
)
POD_FILTER_VALUES = {value for value, _ in POD_FILTER_OPTIONS}
POD_PRODUCT_VALUES = {"yes", "maybe"}
NON_POD_PRODUCT_VALUES = {"no"}


def _pod_filter_control() -> str:
    options = "".join(
        f'<option value="{escape(value)}"{" selected" if value == DEFAULT_POD_FILTER else ""}>{escape(label)}</option>'
        for value, label in POD_FILTER_OPTIONS
    )
    return f"""            <label class="filter-control minimal-filter-control" for="product-filter-pod">
              <span>POD Product</span>
              <select id="product-filter-pod" class="select-input" data-pod-filter aria-label="POD Product filter">
                {options}
              </select>
            </label>"""


def _pod_filter_bucket(product: dict[str, object]) -> str:
    value = str(product.get("is_pod", "") or "").strip().lower()
    if value in POD_PRODUCT_VALUES:
        return "pod"
    if value in NON_POD_PRODUCT_VALUES:
        return "non_pod"
    return "unknown"


def _normalize_pod_filter(value: object, *, default: str = DEFAULT_POD_FILTER) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in POD_FILTER_VALUES:
        return normalized
    return default


def _pod_filter_matches(product: dict[str, object], pod_filter: object = DEFAULT_POD_FILTER) -> bool:
    normalized = _normalize_pod_filter(pod_filter)
    return normalized == "all" or _pod_filter_bucket(product) == normalized


def _filter_products_by_pod(products: list[dict[str, object]], pod_filter: object = DEFAULT_POD_FILTER) -> list[dict[str, object]]:
    return [product for product in products if _pod_filter_matches(product, pod_filter)]


def _advanced_filter_controls(*, exclude: set[str] | None = None) -> str:
    excluded = exclude or set()
    category_controls = [
        ("product_type", "Product Type"),
        ("recipient", "Recipient"),
        ("theme", "Theme"),
        ("occasion", "Occasion"),
        ("seller", "Seller"),
    ]
    numeric_controls = [
        ("score", "Winner Score"),
        ("growth", "Growth"),
        ("reviews", "Reviews"),
        ("price", "Price"),
    ]
    categories = "\n".join(
        f"""            <label class="filter-control" for="product-filter-{field}">
              <span>{label}</span>
              <select id="product-filter-{field}" class="filter-select" multiple size="4" data-filter-select="{field}" aria-label="{label} filter"></select>
            </label>"""
        for field, label in category_controls
        if field not in excluded
    )
    ranges = "\n".join(
        f"""            <fieldset class="range-filter">
              <legend>{label}</legend>
              <label for="product-filter-{field}-min">Min
                <input id="product-filter-{field}-min" class="range-input" type="number" inputmode="decimal" data-range-min="{field}">
              </label>
              <label for="product-filter-{field}-max">Max
                <input id="product-filter-{field}-max" class="range-input" type="number" inputmode="decimal" data-range-max="{field}">
              </label>
            </fieldset>"""
        for field, label in numeric_controls
    )
    return f"""          <div class="advanced-filter-controls" data-advanced-filters>
{categories}
{ranges}
          </div>"""


def _quick_count(products: list[dict[str, object]], key: str) -> int:
    return sum(1 for product in products if _quick_matches(product, key))


def _quick_matches(product: dict[str, object], key: str) -> bool:
    if key == "winner":
        return bool(product.get("is_winner"))
    if key == "rising":
        return bool(product.get("is_rising"))
    if key == "low_reviews":
        value = product.get("review_count", product.get("reviews", ""))
        return str(value or "").strip() not in {"", "-"} and _safe_int(value) < 50
    if key == "new_launch":
        return bool(product.get("is_new_launch"))
    return False


def _product_table_row(product: dict[str, object], image: str, tone: str, *, selected: bool = False) -> str:
    title = str(product["title"])
    selected_class = " is-selected" if selected else ""
    return f"""          <tr class="product-row{selected_class}" tabindex="0" data-product-row>
            <td><input type="checkbox" aria-label="Select {escape(title)}"></td>
            <td><img class="thumbnail" src="{image}" alt="{escape(title)} thumbnail"></td>
            <td>
              <span class="product-title-cell">
                <strong>{escape(title)}</strong>
                <span class="caption">{escape(str(product["product_type"]))}</span>
              </span>
            </td>
            <td>{escape(str(product["seller"]))}</td>
            <td>{escape(str(product["idea"]))}</td>
            <td>{status_badge(str(product["score"]), tone)}</td>
            <td>{status_badge(str(product["growth"]), "rising")}</td>
            <td>{escape(str(product["reviews"]))}</td>
            <td>{escape(str(product["price"]))}</td>
          </tr>"""


PRODUCT_INDEX_FIELDS = (
    "id",
    "asin",
    "title",
    "seller",
    "idea",
    "winner_score",
    "growth",
    "growth_value",
    "review_count",
    "price_value",
    "source",
    "source_days_seen",
    "source_rank_change",
    "product_type",
    "is_pod",
    "recipient",
    "theme",
    "occasion",
    "status",
    "is_winner",
    "is_rising",
    "is_new_launch",
    "image_url",
    "seller_url",
    "tone",
    "seller_evidence_leader",
    "seller_evidence_mover",
    "seller_evidence_new_push",
    "seller_evidence_best_rank",
    "seller_movement",
    "best_seller_evidence_winner",
    "best_seller_evidence_breakout",
    "best_seller_evidence_stable",
    "best_seller_evidence_best_rank",
    "best_seller_movement",
    "new_release_evidence_rising",
    "new_release_evidence_breakout",
    "new_release_evidence_watch",
    "new_release_evidence_best_rank",
    "new_release_movement",
    "bsr_evidence_available",
    "bsr_evidence_strong",
    "bsr_evidence_very_strong",
    "bsr_evidence_best_sub_bsr",
    "bsr_evidence_best_sub_bsr_category",
    "evidence_source_family_count",
    "evidence_count",
)


PRODUCT_DETAIL_FIELDS = (
    "amazon_url",
    "product_url",
    "seller_url",
    "source_url",
    "primary_bsr_rank",
    "primary_bsr_category",
    "sub_bsr_rank",
    "sub_bsr_category",
    "pod_relevance",
    "pod_relevance_reasons",
    "evidence_labels",
    "evidence_count",
    "evidence_reasons",
    "evidence_states",
    "source_details",
)


def _product_index_payload(products: list[dict[str, object]]) -> list[dict[str, object]]:
    return [_product_index_record(product, index) for index, product in enumerate(products)]


def _product_index_record(product: dict[str, object], index: int) -> dict[str, object]:
    record = {
        key: value
        for key in PRODUCT_INDEX_FIELDS
        if not _is_empty_index_value(value := product.get(key))
    }
    record["detail_asset"] = _product_detail_asset_path(product, index)
    record["seller_movement"] = _best_source_movement(product, "seller")
    record["best_seller_movement"] = _best_source_movement(product, "best_seller")
    record["new_release_movement"] = _best_source_movement(product, "new_release")
    record["seller_days_seen"] = _best_source_days_seen(product, "seller")
    record["best_seller_days_seen"] = _best_source_days_seen(product, "best_seller")
    record["new_release_days_seen"] = _best_source_days_seen(product, "new_release")
    record["pod_filter"] = _pod_filter_bucket(product)
    asin = str(product.get("asin", "") or "").strip().upper()
    if asin:
        record["amazon_path"] = f"/dp/{asin}"
    else:
        amazon_url = str(product.get("amazon_url", "") or product.get("product_url", "") or "").strip()
        if amazon_url:
            record["amazon_url"] = amazon_url
    return record


def _product_detail_record(product: dict[str, object]) -> dict[str, object]:
    return {
        key: value
        for key in PRODUCT_DETAIL_FIELDS
        if not _is_empty_detail_value(value := product.get(key))
    }


def _product_detail_asset_path(product: dict[str, object], index: int) -> str:
    return f"{PRODUCT_EXPLORER_DETAIL_DIR}/{_product_detail_file_stem(product, index)}.js"


def _product_detail_file_stem(product: dict[str, object], index: int) -> str:
    candidate = str(product.get("asin", "") or product.get("id", "") or f"product-{index}").strip().upper()
    slug = re.sub(r"[^A-Z0-9_-]+", "-", candidate).strip("-").lower()
    if not slug:
        slug = f"product-{index}"
    if len(slug) <= 48:
        return slug
    digest = hashlib.sha1(candidate.encode("utf-8")).hexdigest()[:10]
    return f"{slug[:37]}-{digest}"


def _product_detail_id(product: dict[str, object], index: int) -> str:
    candidate = str(product.get("asin", "") or product.get("id", "") or f"product-{index}").strip()
    return candidate or f"product-{index}"


def _best_source_movement(product: dict[str, object], family: str) -> int | None:
    source_details = product.get("source_details")
    if not isinstance(source_details, dict):
        return None
    rows = source_details.get(family)
    if not isinstance(rows, list):
        return None
    values = [
        _optional_int(row.get("source_rank_change"))
        for row in rows
        if isinstance(row, dict)
    ]
    valid_values = [value for value in values if value is not None]
    return max(valid_values) if valid_values else None


def _best_source_days_seen(product: dict[str, object], family: str) -> int | None:
    source_details = product.get("source_details")
    if not isinstance(source_details, dict):
        return None
    rows = source_details.get(family)
    if not isinstance(rows, list):
        return None
    values = [
        _optional_int(row.get("source_days_seen"))
        for row in rows
        if isinstance(row, dict)
    ]
    valid_values = [value for value in values if value is not None]
    return min(valid_values) if valid_values else None


def _optional_int(value: object) -> int | None:
    text = str(value or "").replace(",", "").replace("#", "").strip()
    if not text:
        return None
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return None


def _is_empty_index_value(value: object) -> bool:
    return value is None or value == "" or value == [] or value == {}


def _is_empty_detail_value(value: object) -> bool:
    return value is None or value == "" or value == [] or value == {}


def _safe_json_script(value: object) -> str:
    return (
        json.dumps(value, ensure_ascii=True, separators=(",", ":"))
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


def _product_explorer_script() -> str:
    return r"""(() => {
    const dataElement = document.getElementById("product-explorer-data");
    const tbody = document.querySelector("[data-product-tbody]");
    const table = document.querySelector(".product-table");
    const tableShell = document.querySelector(".product-table-shell");
    const searchInput = document.getElementById("product-search");
    const resultCount = document.querySelector("[data-result-count]");
    const resultCap = document.querySelector("[data-result-cap]");
    const emptyState = document.querySelector("[data-filter-empty]");
    const emptyStateTitle = document.querySelector("[data-filter-empty-title]");
    const emptyStateCaption = document.querySelector("[data-filter-empty-caption]");
    const filterGuidance = document.querySelector("[data-filter-guidance]");
    const filterTextSummary = document.querySelector("[data-filter-text-summary]");
    const filterSummary = document.querySelector("[data-active-filter-summary]");
    const filterChips = document.querySelector("[data-active-filter-chips]");
    const podFilter = document.querySelector("[data-pod-filter]");
    const preview = document.querySelector("[data-quick-preview]");
    const columnsToggle = document.querySelector("[data-columns-toggle]");
    const columnMenu = document.querySelector("[data-column-menu]");
    const selectPageCheckbox = document.querySelector("[data-select-page]");
    const selectionToolbar = document.querySelector("[data-selection-toolbar]");
    const selectionCount = document.querySelector("[data-selection-count]");
    const hiddenSelectionCount = document.querySelector("[data-hidden-selection-count]");
    const clearSelectionButton = document.querySelector("[data-clear-selection]");
    const pageSizeSelect = document.querySelector("[data-page-size]");
    const pageRange = document.querySelector("[data-page-range]");
    const pageStatus = document.querySelector("[data-page-status]");
    const statTotal = document.querySelector("[data-stat-total]");
    const statMatching = document.querySelector("[data-stat-matching]");
    const statSellers = document.querySelector("[data-stat-sellers]");
    const statIdeas = document.querySelector("[data-stat-ideas]");
    const statTypes = document.querySelector("[data-stat-types]");
    const statSellerEvidence = document.querySelector("[data-stat-seller-evidence]");
    const statBestSellerEvidence = document.querySelector("[data-stat-best-seller-evidence]");
    const statNewReleaseEvidence = document.querySelector("[data-stat-new-release-evidence]");
    const statBsrEvidence = document.querySelector("[data-stat-bsr-evidence]");
    const pageButtons = Array.from(document.querySelectorAll("[data-page-action]"));
    const sortSelect = document.querySelector("[data-sort-select]");
    const sortDirectionSelect = document.querySelector("[data-sort-direction-select]");
    const DEFAULT_PAGE_SIZE = 100;
    const PAGE_SIZES = [50, 100, 200];
    const LOW_REVIEW_LIMIT = 50;
    const DEFAULT_PRESET = "research_today";
    const DEFAULT_POD_FILTER = "pod";
    const DEFAULT_COLUMNS = new Set(["why", "momentum", "market_proof"]);
    const OPTIONAL_COLUMNS = {
      select: "Row Select",
      image: "Image",
      seller: "Seller",
      product_type: "Product Type",
      primary_evidence: "Primary Evidence",
      idea: "Idea",
      legacy_score: "Legacy Score",
      growth: "Growth",
      reviews: "Reviews",
      price: "Price",
      source: "Source",
    };
    window.AMS_PRODUCT_EXPLORER_INITIAL_DETAIL_COUNT = 0;
    const CATEGORY_FIELDS = {
      product_type: { label: "Product Type", param: "type" },
      recipient: { label: "Recipient", param: "recipient" },
      theme: { label: "Theme", param: "theme" },
      occasion: { label: "Occasion", param: "occasion" },
      seller: { label: "Seller", param: "seller" },
    };
    const POD_FILTERS = {
      all: { label: "All Products" },
      pod: { label: "POD Products" },
      non_pod: { label: "Non-POD Products" },
      unknown: { label: "Unknown" },
    };
    const POD_BUCKETS = new Set(["pod", "non_pod", "unknown"]);
    const RANGE_FIELDS = {
      score: { label: "Score", minParam: "score_min", maxParam: "score_max", value: (product) => product.scoreValue },
      growth: { label: "Growth", minParam: "growth_min", maxParam: "growth_max", value: (product) => product.growthValue },
      reviews: { label: "Reviews", minParam: "reviews_min", maxParam: "reviews_max", value: (product) => product.reviewValue },
      price: { label: "Price", minParam: "price_min", maxParam: "price_max", value: (product) => product.priceValue },
    };
    const EVIDENCE_FILTER_GROUPS = {
      seller: {
        label: "Seller Evidence",
        param: "seller_evidence",
        fields: {
          seller_leader: { label: "Seller Leader", statePath: ["seller", "leader"], field: "seller_evidence_leader", tone: "winner", definition: "Top 10 in the same tracked seller source for at least 7 days." },
          seller_mover: { label: "Seller Mover", statePath: ["seller", "mover"], field: "seller_evidence_mover", tone: "rising", definition: "Improved at least 10 positions within the same seller source." },
          seller_new_push: { label: "Seller New Push", statePath: ["seller", "new_push"], field: "seller_evidence_new_push", tone: "idea", definition: "Recently observed product currently in the seller source top 20." },
        },
      },
      best_seller: {
        label: "Best Seller Evidence",
        param: "best_seller_evidence",
        fields: {
          category_winner: { label: "Category Winner", statePath: ["best_seller", "winner"], field: "best_seller_evidence_winner", tone: "winner", definition: "Top 30 in a tracked Best Seller category with sufficient observation history." },
          category_breakout: { label: "Category Breakout", statePath: ["best_seller", "breakout"], field: "best_seller_evidence_breakout", tone: "rising", definition: "Improved at least 15 positions and reached the category top 50." },
          category_stable: { label: "Category Stable", statePath: ["best_seller", "stable"], field: "best_seller_evidence_stable", tone: "stable", definition: "Stayed in a tracked Best Seller category top 100 for at least 14 days." },
        },
      },
      new_release: {
        label: "New Release Evidence",
        param: "new_release_evidence",
        fields: {
          new_release_rising: { label: "New Release Rising", statePath: ["new_release", "rising"], field: "new_release_evidence_rising", tone: "rising", definition: "Improved at least 10 positions in the same New Release category." },
          new_release_breakout: { label: "New Release Breakout", statePath: ["new_release", "breakout"], field: "new_release_evidence_breakout", tone: "winner", definition: "Improved at least 30 positions and reached the New Release top 30." },
          new_release_watch: { label: "New Release Candidate", statePath: ["new_release", "candidate"], field: "new_release_evidence_watch", tone: "idea", definition: "Recently observed product in a tracked New Release top 100." },
        },
      },
      supporting: {
        label: "Supporting Evidence",
        param: "supporting_evidence",
        fields: {
          very_strong_sub_bsr: { label: "Very Strong Sub-BSR", statePath: ["bsr", "very_strong"], field: "bsr_evidence_very_strong", tone: "winner", definition: "Sub-category BSR is 1,000 or better." },
          strong_sub_bsr: { label: "Strong Sub-BSR", statePath: ["bsr", "strong"], field: "bsr_evidence_strong", tone: "stable", definition: "Sub-category BSR is 5,000 or better." },
        },
      },
    };
    const PRIMARY_EVIDENCE_PRIORITY = [
      "new_release_breakout",
      "category_breakout",
      "seller_mover",
      "seller_new_push",
      "category_winner",
      "new_release_rising",
      "seller_leader",
      "very_strong_sub_bsr",
      "strong_sub_bsr",
      "new_release_watch",
    ];
    const EVIDENCE_BADGE_PRIORITY = [
      "new_release_breakout",
      "category_breakout",
      "seller_mover",
      "seller_new_push",
      "category_winner",
      "new_release_rising",
      "seller_leader",
      "very_strong_sub_bsr",
      "strong_sub_bsr",
      "new_release_watch",
      "category_stable",
    ];
    const SORT_FIELDS = {
      title: { label: "Product", type: "text", value: (product) => product.title },
      seller: { label: "Seller", type: "text", value: (product) => product.seller },
      idea: { label: "Idea", type: "text", value: (product) => product.idea },
      momentum: { label: "Momentum", type: "number", value: (product) => rankImprovement(product) },
      winner_score: { label: "Winner Score", type: "number", value: (product) => product.scoreValue },
      growth: { label: "Growth", type: "number", value: (product) => product.growthValue },
      reviews: { label: "Reviews", type: "number", value: (product) => product.reviewValue },
      price: { label: "Price", type: "number", value: (product) => product.priceValue },
      evidence_count: { label: "Evidence Count", type: "number", value: (product) => product.evidenceCount },
      seller_best_rank: { label: "Seller Best Rank", type: "number", value: (product) => product.sellerBestRank },
      seller_movement: { label: "Seller Movement", type: "number", value: (product) => product.sellerMovement },
      best_seller_rank: { label: "Best Seller Rank", type: "number", value: (product) => product.bestSellerBestRank },
      best_seller_movement: { label: "Best Seller Movement", type: "number", value: (product) => product.bestSellerMovement },
      new_release_rank: { label: "New Release Rank", type: "number", value: (product) => product.newReleaseBestRank },
      new_release_movement: { label: "New Release Movement", type: "number", value: (product) => product.newReleaseMovement },
      sub_bsr: { label: "Sub-category BSR", type: "number", value: (product) => product.subBsrRank },
    };
    const QUICK_FILTERS = {
      winner: { label: "Winner", predicate: (product) => product.isWinner },
      rising: { label: "Rising", predicate: (product) => product.isRising },
      low_reviews: { label: "Low Reviews", predicate: (product) => product.reviewValue !== null && product.reviewValue < LOW_REVIEW_LIMIT },
      new_launch: { label: "New Launch", predicate: (product) => product.isNewLaunch },
    };
    const PRODUCT_PRESETS = {
      research_today: {
        label: "Research Today",
        guidance: "Start with Research Today to find products with recent movement.",
        empty: "No products match Research Today with the current filters.",
        next: "Proven Demand",
        evidence: ["category_breakout", "new_release_breakout", "seller_mover", "seller_new_push"],
      },
      proven_demand: {
        label: "Proven Demand",
        guidance: "Use Proven Demand for validated products.",
        empty: "No products match Proven Demand with the current filters.",
        next: "Research Today",
        evidence: ["category_winner", "very_strong_sub_bsr", "seller_leader"],
      },
      early_opportunity: {
        label: "Early Opportunity",
        guidance: "Use Early Opportunity for lower-review products with fresh momentum.",
        empty: "No products match Early Opportunity with the current filters.",
        next: "Research Today",
        evidence: ["seller_new_push", "new_release_rising", "new_release_watch"],
      },
      competitor_push: {
        label: "Competitor Push",
        guidance: "Use Competitor Push to review sellers making visible moves.",
        empty: "No products match Competitor Push with the current filters.",
        next: "Early Opportunity",
        evidence: ["seller_mover", "seller_new_push"],
      },
    };
    const SAVED_VIEWS = {
      all: { label: "All Products" },
      new_winners: { label: "New Winners", predicate: (product) => product.isWinner },
      fast_rising: { label: "Fast Rising", predicate: (product) => product.isRising },
      christmas: { label: "Christmas", text: "christmas" },
      grandpa: { label: "Grandpa", text: "grandpa" },
      mug: { label: "Mug", fieldContains: { field: "product_type", value: "mug" } },
      metal_sign: { label: "Metal Sign", text: "metal sign" },
      low_competition: { label: "Low Competition", disabled: true },
    };
    const SELECTORS = Object.fromEntries(Object.keys(CATEGORY_FIELDS).map((field) => [field, document.querySelector(`[data-filter-select="${field}"]`)]));
    const rangeInputs = {
      min: Object.fromEntries(Object.keys(RANGE_FIELDS).map((field) => [field, document.querySelector(`[data-range-min="${field}"]`)])),
      max: Object.fromEntries(Object.keys(RANGE_FIELDS).map((field) => [field, document.querySelector(`[data-range-max="${field}"]`)])),
    };
    const availableValues = Object.fromEntries(Object.keys(CATEGORY_FIELDS).map((field) => [field, new Set()]));
    const rawProducts = parseProducts(dataElement);
    const products = rawProducts.map(normalizeProduct);
    const productById = new Map(products.map((product) => [product.__id, product]));
    let focusedId = products[0]?.__id || "";
    let hoverId = "";
    let previewId = "";
    let selectedIds = new Set();
    let currentMatched = [];
    let currentSorted = [];
    let currentPageItems = [];
    let state = emptyStateObject();
    let debounceTimer = 0;
    let hoverDetailTimer = 0;
    let previewRequestId = 0;
    const detailCache = new Map();
    const detailPromises = new Map();
    window.AMS_PRODUCT_EXPLORER_DETAILS = window.AMS_PRODUCT_EXPLORER_DETAILS || {};

    buildFilterOptions();
    state = stateFromUrl();
    focusedId = validFocusId(state.focus) || focusedId;
    syncControls();
    applyWorkspace({ updateUrl: false });

    searchInput?.addEventListener("input", () => {
      window.clearTimeout(debounceTimer);
      debounceTimer = window.setTimeout(() => {
        state.q = cleanQuery(searchInput.value);
        resetPage();
        applyWorkspace({ updateUrl: true, replaceUrl: true });
      }, 180);
    });

    document.querySelector("[data-filter-panel]")?.addEventListener("click", (event) => {
      const presetButton = event.target.closest("[data-product-preset]");
      if (presetButton && !presetButton.disabled) {
        state.preset = validPreset(presetButton.dataset.productPreset);
        resetPage();
        applyWorkspace({ updateUrl: true });
        return;
      }
      const savedButton = event.target.closest("[data-saved-view]");
      if (savedButton && !savedButton.disabled) {
        state.savedView = validSavedView(savedButton.dataset.savedView);
        resetPage();
        applyWorkspace({ updateUrl: true });
        return;
      }
      const quickButton = event.target.closest("[data-quick-filter]");
      if (quickButton && !quickButton.disabled) {
        const key = quickButton.dataset.quickFilter;
        if (state.quick.has(key)) {
          state.quick.delete(key);
        } else if (QUICK_FILTERS[key]) {
          state.quick.add(key);
        }
        resetPage();
        applyWorkspace({ updateUrl: true });
      }
    });

    Object.entries(SELECTORS).forEach(([field, select]) => {
      select?.addEventListener("change", () => {
        state.categories[field] = new Set(Array.from(select.selectedOptions).map((option) => option.value));
        resetPage();
        applyWorkspace({ updateUrl: true });
      });
    });

    podFilter?.addEventListener("change", () => {
      state.pod = validPodFilter(podFilter.value, DEFAULT_POD_FILTER);
      resetPage();
      applyWorkspace({ updateUrl: true });
    });

    columnsToggle?.addEventListener("click", () => {
      const isOpen = !columnMenu?.hidden;
      if (columnMenu) columnMenu.hidden = isOpen;
      columnsToggle.setAttribute("aria-expanded", isOpen ? "false" : "true");
    });

    columnMenu?.addEventListener("change", (event) => {
      const checkbox = event.target.closest("[data-column-toggle]");
      if (!checkbox) return;
      const key = checkbox.dataset.columnToggle;
      if (!OPTIONAL_COLUMNS[key]) return;
      if (checkbox.checked) state.columns.add(key);
      else state.columns.delete(key);
      syncColumnVisibility();
    });

    document.querySelectorAll("[data-evidence-filter]").forEach((checkbox) => {
      checkbox.addEventListener("change", () => {
        const family = checkbox.dataset.evidenceFamily;
        const key = checkbox.dataset.evidenceFilter;
        if (!state.evidence[family] || !evidenceFilterConfig(family, key)) return;
        if (checkbox.checked) state.evidence[family].add(key);
        else state.evidence[family].delete(key);
        resetPage();
        applyWorkspace({ updateUrl: true });
      });
    });

    Object.keys(RANGE_FIELDS).forEach((field) => {
      rangeInputs.min[field]?.addEventListener("input", () => setRangeFromControl(field, "min"));
      rangeInputs.max[field]?.addEventListener("input", () => setRangeFromControl(field, "max"));
    });

    filterSummary?.addEventListener("click", (event) => {
      const chip = event.target.closest("[data-remove-filter]");
      if (!chip) return;
      removeFilter(chip);
      resetPage();
      applyWorkspace({ updateUrl: true });
    });

    document.querySelectorAll("[data-clear-filters]").forEach((button) => {
      button.addEventListener("click", () => {
        state = emptyStateObject();
        focusedId = products[0]?.__id || "";
        hoverId = "";
        syncControls();
        applyWorkspace({ updateUrl: true });
      });
    });

    table?.addEventListener("click", (event) => {
      const sortButton = event.target.closest("[data-sort-key]");
      if (!sortButton) return;
      cycleSort(sortButton.dataset.sortKey);
    });

    selectPageCheckbox?.addEventListener("change", () => {
      const shouldSelect = Boolean(selectPageCheckbox.checked);
      currentPageItems.forEach((product) => {
        if (shouldSelect) selectedIds.add(product.__id);
        else selectedIds.delete(product.__id);
      });
      renderVisibleSelectionState();
      renderSelectionToolbar();
      updateSelectPageState();
    });

    clearSelectionButton?.addEventListener("click", () => {
      selectedIds = new Set();
      renderVisibleSelectionState();
      renderSelectionToolbar();
      updateSelectPageState();
    });

    pageSizeSelect?.addEventListener("change", () => {
      const nextSize = Number(pageSizeSelect.value);
      state.pageSize = PAGE_SIZES.includes(nextSize) ? nextSize : DEFAULT_PAGE_SIZE;
      resetPage();
      applyWorkspace({ updateUrl: true });
    });

    sortSelect?.addEventListener("change", () => {
      const key = sortSelect.value || "";
      if (!key) {
        state.sort = { key: "", direction: "" };
      } else if (SORT_FIELDS[key]) {
        state.sort = { key, direction: sortDirectionSelect?.value === "desc" ? "desc" : "asc" };
      }
      applyWorkspace({ updateUrl: true });
    });

    sortDirectionSelect?.addEventListener("change", () => {
      if (!state.sort.key || !SORT_FIELDS[state.sort.key]) return;
      state.sort.direction = sortDirectionSelect.value === "desc" ? "desc" : "asc";
      applyWorkspace({ updateUrl: true });
    });

    pageButtons.forEach((button) => {
      button.addEventListener("click", () => {
        const totalPages = pageCount();
        const action = button.dataset.pageAction;
        if (action === "first") state.page = 1;
        if (action === "previous") state.page = Math.max(1, state.page - 1);
        if (action === "next") state.page = Math.min(totalPages, state.page + 1);
        if (action === "last") state.page = totalPages;
        applyWorkspace({ updateUrl: true });
      });
    });

    tbody?.addEventListener("click", (event) => {
      const rowAction = event.target.closest("[data-row-action]");
      if (rowAction) {
        event.stopPropagation();
        handleRowAction(rowAction);
        return;
      }
      if (event.target.closest("[data-row-checkbox]")) return;
      const row = event.target.closest("[data-product-row]");
      if (row) focusProduct(row.dataset.productId, { scroll: false, updateUrl: true, moveDomFocus: true });
    });

    tbody?.addEventListener("change", (event) => {
      const checkbox = event.target.closest("[data-row-checkbox]");
      if (!checkbox) return;
      if (checkbox.checked) selectedIds.add(checkbox.value);
      else selectedIds.delete(checkbox.value);
      renderVisibleSelectionState();
      renderSelectionToolbar();
      updateSelectPageState();
    });

    tbody?.addEventListener("pointerover", (event) => {
      const row = event.target.closest("[data-product-row]");
      if (!row) return;
      if (hoverId === row.dataset.productId) return;
      clearHoverClass();
      hoverId = row.dataset.productId;
      row.classList.add("is-hovered");
      updatePreview(productById.get(hoverId), { loadDetail: false });
      scheduleHoverDetailLoad(hoverId);
    });

    tbody?.addEventListener("pointerout", (event) => {
      const row = event.target.closest("[data-product-row]");
      if (!row) return;
      if (event.relatedTarget && row.contains(event.relatedTarget)) return;
      if (hoverId === row.dataset.productId) hoverId = "";
      window.clearTimeout(hoverDetailTimer);
      row.classList.remove("is-hovered");
      updatePreview(focusedProduct(), { loadDetail: Boolean(focusedProduct()?.__detailLoaded) });
    });

    tbody?.addEventListener("error", (event) => {
      const image = event.target;
      if (!image.matches?.(".thumbnail, .product-title-thumbnail") || image.dataset.fallback === "true") return;
      const product = productById.get(image.closest("[data-product-row]")?.dataset.productId || "");
      image.dataset.fallback = "true";
      image.src = fallbackImage(product);
    }, true);

    preview?.querySelector("[data-preview-image]")?.addEventListener("error", (event) => {
      const image = event.target;
      if (image.dataset.fallback === "true") return;
      image.dataset.fallback = "true";
      image.src = fallbackImage(productById.get(previewId));
    });

    preview?.addEventListener("click", (event) => {
      if (event.target.closest("[data-inspector-close]")) {
        collapseInspectorDetails();
        return;
      }
      const action = event.target.closest("[data-preview-action]");
      if (!action) return;
      const product = productById.get(previewId);
      handlePreviewAction(action.dataset.previewAction, product);
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "/" && !isInteractiveTarget(event.target)) {
        event.preventDefault();
        searchInput?.focus();
        searchInput?.select?.();
        return;
      }
      if (!["ArrowDown", "ArrowUp", "Home", "End", " ", "Enter", "Escape"].includes(event.key)) return;
      if (isInteractiveTarget(event.target)) return;
      if (event.key === "Escape") {
        event.preventDefault();
        if (selectedIds.size > 0) {
          selectedIds = new Set();
          renderVisibleSelectionState();
          renderSelectionToolbar();
          updateSelectPageState();
        } else {
          hoverId = "";
          clearHoverClass();
          collapseInspectorDetails();
        }
        return;
      }
      if (!currentPageItems.length) return;
      const currentPosition = Math.max(0, currentPageItems.findIndex((product) => product.__id === focusedId));
      let nextPosition = currentPosition;
      if (event.key === "ArrowDown") nextPosition = Math.min(currentPageItems.length - 1, currentPosition + 1);
      if (event.key === "ArrowUp") nextPosition = Math.max(0, currentPosition - 1);
      if (event.key === "Home") nextPosition = 0;
      if (event.key === "End") nextPosition = currentPageItems.length - 1;
      if (event.key === " ") {
        event.preventDefault();
        toggleSelection(focusedId);
        return;
      }
      if (event.key === "Enter") {
        event.preventDefault();
        focusProduct(focusedId, { scroll: true, updateUrl: true, moveDomFocus: true });
        return;
      }
      event.preventDefault();
      focusProduct(currentPageItems[nextPosition].__id, { scroll: true, updateUrl: true, moveDomFocus: true });
    });

    window.addEventListener("popstate", () => {
      state = stateFromUrl();
      focusedId = validFocusId(state.focus) || focusedId;
      hoverId = "";
      syncControls();
      applyWorkspace({ updateUrl: false });
    });

    function parseProducts(element) {
      if (!element) return [];
      try {
        const parsed = JSON.parse(element.textContent || "[]");
        return Array.isArray(parsed) ? parsed : [];
      } catch (error) {
        return [];
      }
    }

    function normalizeProduct(product, index) {
      const normalized = { ...product };
      normalized.__index = index;
      normalized.__id = stableProductId(product, index);
      normalized.product_type = textValue(product.product_type, "Unknown");
      normalized.recipient = textValue(product.recipient, "Unknown");
      normalized.theme = textValue(product.theme, "Unknown");
      normalized.occasion = textValue(product.occasion, "Unknown");
      normalized.pod_filter = validPodBucket(product.pod_filter) || podFilterBucket(product.is_pod);
      normalized.seller = textValue(product.seller, "Unknown Seller");
      normalized.idea = textValue(product.idea, "Uncategorized");
      normalized.title = textValue(product.title, "Untitled Product");
      normalized.asin = textValue(product.asin, "");
      normalized.scoreValue = numberValue(product.winner_score);
      normalized.growthValue = numberValue(product.growth_value ?? product.growth);
      normalized.reviewValue = numberValue(product.review_count);
      normalized.priceValue = numberValue(product.price_value);
      normalized.statusText = `${textValue(product.status, "")} ${textValue(product.source, "")}`.toLowerCase();
      normalized.isWinner = Boolean(product.is_winner) || normalized.statusText.includes("winner") || normalized.statusText.includes("new breakout");
      normalized.isRising = Boolean(product.is_rising) || normalized.statusText.includes("fast mover") || normalized.statusText.includes("rising");
      normalized.isNewLaunch = Boolean(product.is_new_launch) || normalized.statusText.includes("new release") || normalized.statusText.includes("new launch");
      normalized.sourceDetails = normalizeSourceDetails(product.source_details);
      normalized.evidenceStates = normalizeEvidenceStates(product.evidence_states, normalized.sourceDetails);
      normalized.evidenceCount = numberValue(product.evidence_count);
      normalized.evidenceReasons = Array.isArray(product.evidence_reasons) ? product.evidence_reasons : splitValues(product.evidence_reasons);
      normalized.podRelevanceReasons = Array.isArray(product.pod_relevance_reasons) ? product.pod_relevance_reasons : splitValues(product.pod_relevance_reasons);
      normalized.sellerBestRank = numberValue(product.seller_evidence_best_rank);
      normalized.bestSellerBestRank = numberValue(product.best_seller_evidence_best_rank);
      normalized.newReleaseBestRank = numberValue(product.new_release_evidence_best_rank);
      normalized.subBsrRank = numberValue(product.bsr_evidence_best_sub_bsr ?? product.sub_bsr_rank);
      normalized.primaryBsrRank = numberValue(product.primary_bsr_rank);
      normalized.primaryBsrCategory = textValue(product.primary_bsr_category, "");
      normalized.subBsrCategory = textValue(product.bsr_evidence_best_sub_bsr_category || product.sub_bsr_category, "");
      normalized.detailAsset = textValue(product.detail_asset, "");
      normalized.amazonPath = textValue(product.amazon_path, "");
      normalized.sourceUrl = textValue(product.source_url, "");
      normalized.sellerMovement = numberValue(product.seller_movement);
      normalized.bestSellerMovement = numberValue(product.best_seller_movement);
      normalized.newReleaseMovement = numberValue(product.new_release_movement);
      normalized.sourceDaysSeen = numberValue(product.source_days_seen);
      normalized.sellerDaysSeen = numberValue(product.seller_days_seen);
      normalized.bestSellerDaysSeen = numberValue(product.best_seller_days_seen);
      normalized.newReleaseDaysSeen = numberValue(product.new_release_days_seen);
      normalized.sourceRankChange = numberValue(product.source_rank_change);
      Object.values(EVIDENCE_FILTER_GROUPS).forEach((group) => {
        Object.entries(group.fields).forEach(([key, config]) => {
          normalized[key] = explicitEvidenceValue(product, config);
        });
      });
      normalized.hasSellerEvidence = ["seller_leader", "seller_mover", "seller_new_push"].some((key) => normalized[key]);
      normalized.hasBestSellerEvidence = ["category_winner", "category_breakout", "category_stable"].some((key) => normalized[key]);
      normalized.hasNewReleaseEvidence = ["new_release_rising", "new_release_breakout", "new_release_watch"].some((key) => normalized[key]);
      normalized.hasBsrEvidence = ["strong_sub_bsr", "very_strong_sub_bsr"].some((key) => normalized[key]);
      normalized.evidenceBadges = evidenceBadges(normalized);
      normalized.primaryEvidence = primaryEvidenceBadge(normalized);
      if (normalized.evidenceCount === null) normalized.evidenceCount = normalized.evidenceBadges.length;
      normalized.tone = toneName(product.tone);
      normalized.__search = normalizeSearch([
        normalized.title,
        normalized.seller,
        normalized.idea,
        normalized.asin,
        normalized.product_type,
        normalized.recipient,
        normalized.theme,
        normalized.occasion,
      ].join(" "));
      Object.keys(CATEGORY_FIELDS).forEach((field) => availableValues[field].add(textValue(normalized[field], "Unknown")));
      return normalized;
    }

    function normalizeSourceDetails(raw) {
      const details = { seller: [], best_seller: [], new_release: [], bsr: [] };
      if (!raw || typeof raw !== "object") return details;
      Object.keys(details).forEach((family) => {
        const rows = Array.isArray(raw[family]) ? raw[family] : [];
        details[family] = rows.map((row) => normalizeSourceDetail(row));
      });
      return details;
    }

    function normalizeSourceDetail(row) {
      const detail = { ...(row || {}) };
      ["source_rank", "previous_source_rank", "source_rank_change", "source_days_seen", "source_observation_count", "primary_bsr_rank", "sub_bsr_rank"].forEach((field) => {
        detail[field] = numberValue(detail[field]);
      });
      detail.source_name = textValue(detail.source_name, "Unknown source");
      detail.source_type = textValue(detail.source_type, "unknown");
      detail.marketplace = textValue(detail.marketplace, "");
      detail.category_name = textValue(detail.category_name, "");
      detail.primary_bsr_category = textValue(detail.primary_bsr_category, "");
      detail.sub_bsr_category = textValue(detail.sub_bsr_category, "");
      detail.evidence_labels = Array.isArray(detail.evidence_labels) ? detail.evidence_labels : splitValues(detail.evidence_labels);
      detail.evidence_reasons = Array.isArray(detail.evidence_reasons) ? detail.evidence_reasons : splitValues(detail.evidence_reasons);
      Object.values(EVIDENCE_FILTER_GROUPS).forEach((group) => {
        Object.keys(group.fields).forEach((key) => {
          detail[key] = Boolean(detail[key]);
        });
      });
      return detail;
    }

    function normalizeEvidenceStates(raw, sourceDetails) {
      const states = {
        seller: stateGroup(raw?.seller, Boolean(sourceDetails.seller.length), ["leader", "mover", "new_push"]),
        best_seller: stateGroup(raw?.best_seller, Boolean(sourceDetails.best_seller.length), ["winner", "breakout", "stable"]),
        new_release: stateGroup(raw?.new_release, Boolean(sourceDetails.new_release.length), ["rising", "breakout", "candidate"]),
        bsr: stateGroup(raw?.bsr, Boolean(sourceDetails.bsr.length), ["strong", "very_strong"]),
      };
      return states;
    }

    function stateGroup(raw, hasData, signals) {
      const group = {};
      signals.forEach((signal) => {
        const value = textValue(raw?.[signal], "");
        group[signal] = ["true", "false", "no_data"].includes(value) ? value : (hasData ? "false" : "no_data");
      });
      return group;
    }

    function explicitEvidenceValue(product, config) {
      if (Boolean(product[config.field])) return true;
      const [family, signal] = config.statePath;
      return product.evidence_states?.[family]?.[signal] === "true";
    }

    function evidenceFilterConfig(family, key) {
      return EVIDENCE_FILTER_GROUPS[family]?.fields?.[key] || null;
    }

    function evidenceConfigByKey(key) {
      for (const group of Object.values(EVIDENCE_FILTER_GROUPS)) {
        if (group.fields[key]) return group.fields[key];
      }
      return null;
    }

    function evidenceBadges(product) {
      return EVIDENCE_BADGE_PRIORITY
        .map((key) => {
          const config = evidenceConfigByKey(key);
          if (!config || product[key] !== true) return null;
          return { key, label: config.label, tone: config.tone, definition: config.definition };
        })
        .filter(Boolean);
    }

    function primaryEvidenceBadge(product) {
      for (const key of PRIMARY_EVIDENCE_PRIORITY) {
        const config = evidenceConfigByKey(key);
        if (config && product[key] === true) return { key, label: config.label, tone: config.tone, definition: config.definition };
      }
      return null;
    }

    function primaryEvidenceIndex(product) {
      const key = product.primaryEvidence?.key || "";
      const index = PRIMARY_EVIDENCE_PRIORITY.indexOf(key);
      return index >= 0 ? index : PRIMARY_EVIDENCE_PRIORITY.length;
    }

    function evidenceCellHtml(product) {
      const badges = product.evidenceBadges || [];
      if (!badges.length) return '<span class="caption">No evidence</span>';
      const primary = product.primaryEvidence || badges[0];
      const remaining = badges.filter((badge) => badge.key !== primary.key);
      const visible = evidenceBadgeHtml(primary);
      const extra = remaining.length ? `<span class="evidence-more" title="${escapeHtml(remaining.map((badge) => badge.label).join(", "))}">+${remaining.length}</span>` : "";
      return `<div class="evidence-cell">${visible}${extra}</div>`;
    }

    function rawEvidenceCellHtml(product) {
      const badges = product.evidenceBadges || [];
      if (!badges.length) return '<span class="caption">No evidence</span>';
      return `<div class="evidence-cell">${badges.map((badge) => evidenceBadgeHtml(badge)).join("")}</div>`;
    }

    function evidenceBadgeHtml(badge) {
      return `<span class="evidence-badge tone-${toneName(badge.tone)}" title="${escapeHtml(badge.definition)}">${escapeHtml(badge.label)}</span>`;
    }

    function whyItMattersHtml(product) {
      const primary = product.primaryEvidence;
      const label = primary ? evidenceBadgeHtml(primary) : "";
      return `<div class="why-cell">${label}<span>${escapeHtml(whyItMatters(product))}</span></div>`;
    }

    function whyItMatters(product) {
      const key = product.primaryEvidence?.key || "";
      if (key === "seller_mover") {
        return product.sellerMovement !== null ? `Improved ${formatNumber(product.sellerMovement)} seller positions` : "Seller mover";
      }
      if (key === "seller_new_push") {
        const days = sourceDaysSeen(product, "seller");
        return days !== null ? `New seller push detected ${formatNumber(days)} days ago` : "New seller push detected";
      }
      if (key === "new_release_breakout") {
        return product.reviewValue !== null ? `New Release breakout with ${formatNumber(product.reviewValue)} reviews` : "New Release breakout";
      }
      if (key === "category_breakout") {
        return product.bestSellerMovement !== null ? `Category breakout improved ${formatNumber(product.bestSellerMovement)} ranks` : "Category breakout";
      }
      if (key === "category_winner") {
        return product.bestSellerBestRank !== null ? `Category Winner at rank #${formatNumber(product.bestSellerBestRank)}` : "Category Winner";
      }
      if (key === "new_release_rising") {
        return product.newReleaseMovement !== null ? `New Release rising +${formatNumber(product.newReleaseMovement)} ranks` : "New Release rising";
      }
      if (key === "seller_leader") {
        return product.sellerBestRank !== null ? `Seller Leader at rank #${formatNumber(product.sellerBestRank)}` : "Seller Leader";
      }
      if (key === "very_strong_sub_bsr" || key === "strong_sub_bsr") {
        const label = key === "very_strong_sub_bsr" ? "Very Strong Sub-BSR" : "Strong Sub-BSR";
        return product.subBsrRank !== null ? `${label} at #${formatNumber(product.subBsrRank)}` : label;
      }
      if (key === "new_release_watch") {
        const days = sourceDaysSeen(product, "new_release");
        return days !== null ? `New Release watch seen ${formatNumber(days)} days` : "New Release watch";
      }
      if ((product.evidenceBadges || []).length > 1 || Number(product.evidence_source_family_count || 0) > 1) return "Multiple evidence sources";
      return "No primary evidence";
    }

    function momentumLabel(product) {
      const key = product.primaryEvidence?.key || "";
      if (key === "seller_new_push") {
        const days = sourceDaysSeen(product, "seller");
        return days === null ? "\u2014" : `New \u00b7 ${formatNumber(days)} days`;
      }
      if (key === "new_release_watch") {
        const days = sourceDaysSeen(product, "new_release");
        return days === null ? "\u2014" : `New \u00b7 ${formatNumber(days)} days`;
      }
      const movement = movementForPrimary(product);
      if (movement !== null) return `+${formatNumber(movement)} ranks`;
      const days = sourceDaysSeen(product, familyForEvidence(key));
      if (days !== null) return `Stable \u00b7 ${formatNumber(days)} days`;
      return "\u2014";
    }

    function marketProof(product) {
      if (product.bestSellerBestRank !== null && product.bestSellerBestRank > 0) return `Best Seller #${formatNumber(product.bestSellerBestRank)}`;
      if (product.subBsrRank !== null && product.subBsrRank > 0) return `Sub-BSR #${formatNumber(product.subBsrRank)}`;
      if (product.reviewValue !== null) return `${formatNumber(product.reviewValue)} reviews`;
      if (product.sellerBestRank !== null && product.sellerBestRank > 0) return `Seller #${formatNumber(product.sellerBestRank)}`;
      return "\u2014";
    }

    function rankImprovement(product) {
      const values = [product.sellerMovement, product.bestSellerMovement, product.newReleaseMovement, product.sourceRankChange].filter((value) => value !== null);
      return values.length ? Math.max(...values) : null;
    }

    function movementForPrimary(product) {
      const family = familyForEvidence(product.primaryEvidence?.key || "");
      if (family === "seller") return product.sellerMovement;
      if (family === "best_seller") return product.bestSellerMovement;
      if (family === "new_release") return product.newReleaseMovement;
      return rankImprovement(product);
    }

    function sourceDaysSeen(product, family = "") {
      if (family === "seller") return product.sellerDaysSeen ?? product.sourceDaysSeen;
      if (family === "best_seller") return product.bestSellerDaysSeen ?? product.sourceDaysSeen;
      if (family === "new_release") return product.newReleaseDaysSeen ?? product.sourceDaysSeen;
      const values = [product.sellerDaysSeen, product.bestSellerDaysSeen, product.newReleaseDaysSeen, product.sourceDaysSeen].filter((value) => value !== null);
      return values.length ? Math.min(...values) : null;
    }

    function familyForEvidence(key) {
      if (["seller_mover", "seller_new_push", "seller_leader"].includes(key)) return "seller";
      if (["category_breakout", "category_winner"].includes(key)) return "best_seller";
      if (["new_release_breakout", "new_release_rising", "new_release_watch"].includes(key)) return "new_release";
      return "";
    }

    function splitValues(value) {
      if (Array.isArray(value)) return value.filter(Boolean).map((item) => textValue(item, "")).filter(Boolean);
      return String(value || "").split(/[;|]/).map((item) => item.trim()).filter(Boolean);
    }

    function bestMovement(details) {
      const values = (details || []).map((detail) => detail.source_rank_change).filter((value) => value !== null);
      return values.length ? Math.max(...values) : null;
    }

    function bestRank(details) {
      const values = (details || []).map((detail) => detail.source_rank).filter((value) => value !== null && value > 0);
      return values.length ? Math.min(...values) : null;
    }

    function bestPreviousRank(details) {
      const values = (details || []).map((detail) => detail.previous_source_rank).filter((value) => value !== null && value > 0);
      return values.length ? Math.min(...values) : null;
    }

    function maxDaysSeen(details) {
      const values = (details || []).map((detail) => detail.source_days_seen).filter((value) => value !== null);
      return values.length ? Math.max(...values) : null;
    }

    function maxObservationCount(details) {
      const values = (details || []).map((detail) => detail.source_observation_count).filter((value) => value !== null);
      return values.length ? Math.max(...values) : null;
    }

    function stableProductId(product, index) {
      const candidate = textValue(product.asin || product.id, "");
      return candidate || `product-${index}`;
    }

    function buildFilterOptions() {
      Object.entries(SELECTORS).forEach(([field, select]) => {
        if (!select) return;
        const values = Array.from(availableValues[field]).filter(Boolean).sort((left, right) => left.localeCompare(right));
        select.innerHTML = values.map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join("");
      });
    }

    function stateFromUrl() {
      const params = new URLSearchParams(window.location.search);
      const next = emptyStateObject();
      next.q = cleanQuery(params.get("q") || "");
      next.preset = validPreset(params.get("preset") || DEFAULT_PRESET);
      next.savedView = validSavedView(params.get("view") || "all");
      Object.entries(CATEGORY_FIELDS).forEach(([field, config]) => {
        next.categories[field] = new Set(params.getAll(config.param).filter((value) => availableValues[field].has(value)));
      });
      next.pod = validPodFilter(params.get("pod_filter") || params.get("pod") || DEFAULT_POD_FILTER, DEFAULT_POD_FILTER);
      Object.entries(RANGE_FIELDS).forEach(([field, config]) => {
        const min = validRangeValue(params.get(config.minParam));
        const max = validRangeValue(params.get(config.maxParam));
        if (min !== "" && max !== "" && Number(min) > Number(max)) return;
        next.ranges[field] = { min, max };
      });
      Object.entries(EVIDENCE_FILTER_GROUPS).forEach(([family, config]) => {
        next.evidence[family] = new Set(params.getAll(config.param).filter((value) => Boolean(evidenceFilterConfig(family, value))));
      });
      params.getAll("quick").forEach((value) => {
        if (QUICK_FILTERS[value]) next.quick.add(value);
      });
      const sort = params.get("sort") || "";
      const direction = params.get("direction") || "";
      if (SORT_FIELDS[sort] && ["asc", "desc"].includes(direction)) {
        next.sort = { key: sort, direction };
      }
      next.pageSize = validPageSize(params.get("page_size"));
      next.page = validPage(params.get("page"));
      next.focus = textValue(params.get("focus"), "");
      return next;
    }

    function emptyStateObject() {
      return {
        q: "",
        preset: DEFAULT_PRESET,
        savedView: "all",
        categories: Object.fromEntries(Object.keys(CATEGORY_FIELDS).map((field) => [field, new Set()])),
        pod: DEFAULT_POD_FILTER,
        ranges: Object.fromEntries(Object.keys(RANGE_FIELDS).map((field) => [field, { min: "", max: "" }])),
        evidence: Object.fromEntries(Object.keys(EVIDENCE_FILTER_GROUPS).map((family) => [family, new Set()])),
        quick: new Set(),
        sort: { key: "", direction: "" },
        columns: new Set(),
        page: 1,
        pageSize: DEFAULT_PAGE_SIZE,
        focus: "",
      };
    }

    function applyWorkspace({ updateUrl = true, replaceUrl = false } = {}) {
      syncControls();
      currentMatched = [];
      for (const product of products) {
        if (matchesProduct(product)) currentMatched.push(product);
      }
      currentSorted = sortProducts(currentMatched);
      state.page = clamp(state.page, 1, pageCount());
      currentPageItems = currentSorted.slice(pageStartIndex(), pageStartIndex() + state.pageSize);
      ensureFocusedProduct();
      renderRows();
      renderActiveFilters();
      renderResultCount();
      renderStats();
      renderPagination();
      renderSortHeaders();
      renderSelectionToolbar();
      updateSelectPageState();
      syncColumnVisibility();
      updatePreview(focusedProduct(), { loadDetail: Boolean(focusedProduct()?.__detailLoaded) });
      if (updateUrl) updateUrlState(replaceUrl);
    }

    function matchesProduct(product) {
      const preset = PRODUCT_PRESETS[state.preset] || PRODUCT_PRESETS[DEFAULT_PRESET];
      if (preset?.evidence?.length && !preset.evidence.some((key) => product[key] === true)) return false;
      const view = SAVED_VIEWS[state.savedView] || SAVED_VIEWS.all;
      if (view.predicate && !view.predicate(product)) return false;
      if (view.text && !product.__search.includes(normalizeSearch(view.text))) return false;
      if (view.fieldContains) {
        const value = normalizeSearch(product[view.fieldContains.field] || "");
        if (!value.includes(normalizeSearch(view.fieldContains.value))) return false;
      }
      if (state.q && !product.__search.includes(normalizeSearch(state.q))) return false;
      for (const field of Object.keys(CATEGORY_FIELDS)) {
        const values = state.categories[field];
        if (values.size > 0 && !values.has(textValue(product[field], "Unknown"))) return false;
      }
      if (state.pod !== "all" && product.pod_filter !== state.pod) return false;
      for (const [field, config] of Object.entries(RANGE_FIELDS)) {
        const value = config.value(product);
        const range = state.ranges[field];
        if (range.min !== "" && (value === null || value < Number(range.min))) return false;
        if (range.max !== "" && (value === null || value > Number(range.max))) return false;
      }
      for (const [family, selected] of Object.entries(state.evidence)) {
        if (selected.size === 0) continue;
        let familyMatch = false;
        selected.forEach((key) => {
          const config = evidenceFilterConfig(family, key);
          if (config && product[key] === true) familyMatch = true;
        });
        if (!familyMatch) return false;
      }
      for (const key of state.quick) {
        const quick = QUICK_FILTERS[key];
        if (quick && !quick.predicate(product)) return false;
      }
      return true;
    }

    function sortProducts(matched) {
      const { key, direction } = state.sort;
      if (!SORT_FIELDS[key] || !["asc", "desc"].includes(direction)) {
        return matched.slice().sort((left, right) => comparePresetProducts(left, right, state.preset));
      }
      const config = SORT_FIELDS[key];
      return matched.slice().sort((left, right) => {
        const leftValue = config.value(left);
        const rightValue = config.value(right);
        const leftMissing = leftValue === null || leftValue === "";
        const rightMissing = rightValue === null || rightValue === "";
        if (leftMissing !== rightMissing) return leftMissing ? 1 : -1;
        let result = 0;
        if (config.type === "number") {
          result = Number(leftValue) - Number(rightValue);
        } else {
          result = String(leftValue).localeCompare(String(rightValue), undefined, { sensitivity: "base", numeric: true });
        }
        if (result === 0) result = left.__index - right.__index;
        return direction === "asc" ? result : -result;
      });
    }

    function comparePresetProducts(left, right, preset) {
      const key = validPreset(preset);
      if (key === "research_today") {
        return compareNumber(primaryEvidenceIndex(left), primaryEvidenceIndex(right), "asc")
          || compareNumber(rankImprovement(left), rankImprovement(right), "desc")
          || compareNumber(left.reviewValue, right.reviewValue, "asc")
          || compareFallback(left, right);
      }
      if (key === "proven_demand") {
        return compareNumber(left.subBsrRank, right.subBsrRank, "asc")
          || compareNumber(left.bestSellerBestRank, right.bestSellerBestRank, "asc")
          || compareNumber(left.reviewValue, right.reviewValue, "desc")
          || compareFallback(left, right);
      }
      if (key === "early_opportunity") {
        return compareNumber(reviewPreference(left), reviewPreference(right), "asc")
          || compareNumber(left.reviewValue, right.reviewValue, "asc")
          || compareNumber(rankImprovement(left), rankImprovement(right), "desc")
          || compareNumber(sourceDaysSeen(left), sourceDaysSeen(right), "asc")
          || compareFallback(left, right);
      }
      if (key === "competitor_push") {
        return compareNumber(left.sellerMovement, right.sellerMovement, "desc")
          || compareNumber(sourceDaysSeen(left), sourceDaysSeen(right), "asc")
          || compareFallback(left, right);
      }
      return compareFallback(left, right);
    }

    function reviewPreference(product) {
      if (product.reviewValue === null) return 2;
      return product.reviewValue <= 100 ? 0 : 1;
    }

    function compareNumber(left, right, direction) {
      const leftMissing = left === null || left === undefined || left === "";
      const rightMissing = right === null || right === undefined || right === "";
      if (leftMissing !== rightMissing) return leftMissing ? 1 : -1;
      if (leftMissing && rightMissing) return 0;
      const result = Number(left) - Number(right);
      return direction === "asc" ? result : -result;
    }

    function compareFallback(left, right) {
      return String(left.title || "").localeCompare(String(right.title || ""), undefined, { sensitivity: "base", numeric: true })
        || String(left.asin || left.__id || "").localeCompare(String(right.asin || right.__id || ""), undefined, { sensitivity: "base", numeric: true })
        || left.__index - right.__index;
    }

    function renderRows() {
      if (!tbody) return;
      tbody.innerHTML = currentPageItems.map(productRowHtml).join("");
      if (emptyState) emptyState.hidden = products.length === 0 || currentMatched.length !== 0;
      renderEmptyStateMessage();
      tableShell?.toggleAttribute("hidden", products.length === 0 || currentMatched.length === 0);
      document.querySelector("[data-pagination]")?.toggleAttribute("hidden", products.length === 0 || currentMatched.length === 0);
      if (resultCap) resultCap.hidden = true;
    }

    function renderEmptyStateMessage() {
      if (!emptyStateTitle || !emptyStateCaption) return;
      const preset = PRODUCT_PRESETS[state.preset] || PRODUCT_PRESETS[DEFAULT_PRESET];
      if (currentMatched.length === 0 && preset) {
        emptyStateTitle.textContent = preset.empty;
        emptyStateCaption.textContent = `Remove an active filter or open ${preset.next}.`;
      } else {
        emptyStateTitle.textContent = "No products match the current search and filters.";
        emptyStateCaption.textContent = "Adjust the search or remove filters to see products.";
      }
    }

    function productRowHtml(product) {
      const focused = product.__id === focusedId;
      const checked = selectedIds.has(product.__id);
      const classes = ["product-row", focused ? "is-focused" : "", checked ? "is-checked" : ""].filter(Boolean).join(" ");
      const subtitle = [product.seller, product.product_type].filter(Boolean).join(" \u00b7 ");
      return `<tr class="${classes}" tabindex="${focused ? "0" : "-1"}" data-product-row data-product-id="${escapeHtml(product.__id)}" data-product-index="${product.__index}" aria-selected="${focused ? "true" : "false"}">
            <td data-column="select" data-optional-column><input type="checkbox" data-row-checkbox value="${escapeHtml(product.__id)}" ${checked ? "checked" : ""} aria-label="Select ${escapeHtml(product.title)}"></td>
            <td data-column="image" data-optional-column><img class="thumbnail" src="${escapeHtml(productImage(product))}" alt="${escapeHtml(product.title)} thumbnail"></td>
            <td>
              <span class="product-title-cell has-thumbnail">
                <img class="product-title-thumbnail" src="${escapeHtml(productImage(product))}" alt="${escapeHtml(product.title)} thumbnail">
                <span class="product-title-copy">
                  <strong>${escapeHtml(product.title)}</strong>
                  <span class="caption">${escapeHtml(subtitle)}</span>
                </span>
              </span>
            </td>
            <td data-column="why">${whyItMattersHtml(product)}</td>
            <td class="numeric-cell" data-column="momentum">${displayValueHtml(momentumLabel(product))}</td>
            <td data-column="market_proof">${displayValueHtml(marketProof(product))}</td>
            <td data-column="seller" data-optional-column>${escapeHtml(product.seller)}</td>
            <td data-column="product_type" data-optional-column>${escapeHtml(product.product_type)}</td>
            <td data-column="primary_evidence" data-optional-column>${evidenceCellHtml(product)}</td>
            <td data-column="idea" data-optional-column>${escapeHtml(product.idea)}</td>
            <td class="numeric-cell" data-column="legacy_score" data-optional-column>${statusBadge(displayValue(product.winner_score), product.tone)}</td>
            <td class="numeric-cell" data-column="growth" data-optional-column>${statusBadge(displayValue(product.growth), "rising")}</td>
            <td class="numeric-cell" data-column="reviews" data-optional-column>${displayValueHtml(reviewDisplay(product))}</td>
            <td class="numeric-cell" data-column="price" data-optional-column>${displayValueHtml(priceDisplay(product))}</td>
            <td data-column="source" data-optional-column>${displayValueHtml(product.source || product.status)}</td>
            <td>${rowActionsHtml(product)}</td>
          </tr>`;
    }

    function rowActionsHtml(product) {
      const amazon = productAmazonUrl(product);
      return `<div class="row-actions" aria-label="Product actions">
        ${rowActionButton("amazon", "Open", Boolean(amazon))}
      </div>`;
    }

    function rowActionButton(action, label, enabled) {
      return `<button class="row-action" type="button" data-row-action="${action}" ${enabled ? "" : "disabled"} title="${escapeHtml(label)}">${escapeHtml(label)}</button>`;
    }

    function renderResultCount() {
      if (!resultCount) return;
      resultCount.textContent = visibleRangeText();
    }

    function renderStats() {
      if (statTotal) statTotal.textContent = formatNumber(products.length);
      if (statMatching) statMatching.textContent = formatNumber(currentMatched.length);
      if (statSellers) statSellers.textContent = formatNumber(uniqueMeaningfulCount(currentMatched, "seller"));
      if (statIdeas) statIdeas.textContent = formatNumber(uniqueMeaningfulCount(currentMatched, "idea"));
      if (statTypes) statTypes.textContent = formatNumber(uniqueMeaningfulCount(currentMatched, "product_type"));
      if (statSellerEvidence) statSellerEvidence.textContent = formatNumber(currentMatched.filter((product) => product.hasSellerEvidence).length);
      if (statBestSellerEvidence) statBestSellerEvidence.textContent = formatNumber(currentMatched.filter((product) => product.hasBestSellerEvidence).length);
      if (statNewReleaseEvidence) statNewReleaseEvidence.textContent = formatNumber(currentMatched.filter((product) => product.hasNewReleaseEvidence).length);
      if (statBsrEvidence) statBsrEvidence.textContent = formatNumber(currentMatched.filter((product) => product.hasBsrEvidence).length);
    }

    function renderPagination() {
      const totalPages = pageCount();
      if (pageSizeSelect && Number(pageSizeSelect.value) !== state.pageSize) pageSizeSelect.value = String(state.pageSize);
      if (pageRange) pageRange.textContent = visibleRangeText();
      if (pageStatus) pageStatus.textContent = `Page ${formatNumber(state.page)} of ${formatNumber(totalPages)}`;
      pageButtons.forEach((button) => {
        const action = button.dataset.pageAction;
        button.disabled = (action === "first" || action === "previous") ? state.page <= 1 : state.page >= totalPages;
      });
    }

    function renderSortHeaders() {
      document.querySelectorAll("[data-sort-key]").forEach((button) => {
        const active = state.sort.key === button.dataset.sortKey && state.sort.direction;
        const th = button.closest("th");
        const indicator = button.querySelector("[data-sort-indicator]");
        button.classList.toggle("is-active", Boolean(active));
        if (indicator) indicator.textContent = active ? state.sort.direction : "";
        if (th) th.setAttribute("aria-sort", active ? (state.sort.direction === "asc" ? "ascending" : "descending") : "none");
      });
    }

    function renderSelectionToolbar() {
      if (!selectionToolbar || !selectionCount) return;
      const hiddenCount = hiddenSelectedCount();
      selectionToolbar.hidden = selectedIds.size === 0;
      selectionCount.textContent = `${formatNumber(selectedIds.size)} selected`;
      if (hiddenSelectionCount) {
        hiddenSelectionCount.hidden = hiddenCount === 0;
        hiddenSelectionCount.textContent = `${formatNumber(hiddenCount)} hidden by current filters`;
      }
    }

    function renderActiveFilters() {
      if (!filterSummary || !filterChips) return;
      const chips = [];
      const preset = PRODUCT_PRESETS[state.preset] || PRODUCT_PRESETS[DEFAULT_PRESET];
      chips.push(chipHtml(`Preset: ${preset.label}`, "preset", state.preset));
      if (state.savedView !== "all") {
        chips.push(chipHtml(`Saved View: ${SAVED_VIEWS[state.savedView]?.label || state.savedView}`, "saved_view", state.savedView));
      }
      if (state.q) chips.push(chipHtml(`Search: ${state.q}`, "search", "q"));
      Object.entries(CATEGORY_FIELDS).forEach(([field, config]) => {
        Array.from(state.categories[field]).sort().forEach((value) => {
          chips.push(chipHtml(`${config.label}: ${value}`, "category", value, field));
        });
      });
      if (state.pod !== "all") chips.push(chipHtml(`POD Product: ${POD_FILTERS[state.pod]?.label || state.pod}`, "pod", state.pod));
      Object.entries(RANGE_FIELDS).forEach(([field, config]) => {
        const range = state.ranges[field];
        if (range.min !== "" || range.max !== "") {
          chips.push(chipHtml(`${config.label}: ${range.min || "Any"}-${range.max || "Any"}`, "range", field));
        }
      });
      Object.entries(EVIDENCE_FILTER_GROUPS).forEach(([family, group]) => {
        Array.from(state.evidence[family]).sort().forEach((key) => {
          const config = evidenceFilterConfig(family, key);
          if (config) chips.push(chipHtml(`${group.label}: ${config.label}`, "evidence", key, family));
        });
      });
      Array.from(state.quick).forEach((key) => {
        chips.push(chipHtml(`Quick: ${QUICK_FILTERS[key]?.label || key}`, "quick", key));
      });
      filterChips.innerHTML = chips.join("");
      filterSummary.hidden = chips.length === 0;
      if (filterGuidance) filterGuidance.textContent = preset.guidance;
      if (filterTextSummary) {
        const filterCount = chips.length;
        filterTextSummary.hidden = false;
        filterTextSummary.textContent = `${preset.label}: ${formatNumber(currentMatched.length)} matching products across ${formatNumber(uniqueMeaningfulCount(currentMatched, "seller"))} sellers. ${filterCount > 1 ? `${formatNumber(filterCount - 1)} additional filters active.` : "No additional filters active."}`;
      }
    }

    function chipHtml(label, type, value, field = "") {
      return `<button class="active-filter-chip" type="button" data-remove-filter="${escapeHtml(type)}" data-value="${escapeHtml(value)}" data-field="${escapeHtml(field)}">
        <span>${escapeHtml(label)}</span><span aria-hidden="true">x</span>
      </button>`;
    }

    function removeFilter(chip) {
      const type = chip.dataset.removeFilter;
      const value = chip.dataset.value || "";
      const field = chip.dataset.field || "";
      if (type === "preset") state.preset = DEFAULT_PRESET;
      if (type === "saved_view") state.savedView = "all";
      if (type === "search") state.q = "";
      if (type === "category" && state.categories[field]) state.categories[field].delete(value);
      if (type === "pod") state.pod = "all";
      if (type === "range" && state.ranges[value]) state.ranges[value] = { min: "", max: "" };
      if (type === "evidence" && state.evidence[field]) state.evidence[field].delete(value);
      if (type === "quick") state.quick.delete(value);
    }

    function syncControls() {
      if (searchInput && searchInput.value !== state.q) searchInput.value = state.q;
      Object.entries(SELECTORS).forEach(([field, select]) => {
        if (!select) return;
        Array.from(select.options).forEach((option) => {
          option.selected = state.categories[field].has(option.value);
        });
      });
      if (podFilter && podFilter.value !== state.pod) podFilter.value = state.pod;
      Object.keys(RANGE_FIELDS).forEach((field) => {
        if (rangeInputs.min[field]) rangeInputs.min[field].value = state.ranges[field].min;
        if (rangeInputs.max[field]) rangeInputs.max[field].value = state.ranges[field].max;
      });
      document.querySelectorAll("[data-evidence-filter]").forEach((checkbox) => {
        const family = checkbox.dataset.evidenceFamily;
        const key = checkbox.dataset.evidenceFilter;
        checkbox.checked = Boolean(state.evidence[family]?.has(key));
      });
      document.querySelectorAll("[data-quick-filter]").forEach((button) => {
        const active = state.quick.has(button.dataset.quickFilter);
        button.classList.toggle("is-active", active);
        button.setAttribute("aria-pressed", active ? "true" : "false");
      });
      document.querySelectorAll("[data-product-preset]").forEach((button) => {
        const active = state.preset === button.dataset.productPreset;
        button.classList.toggle("is-active", active);
        if (active) button.setAttribute("aria-current", "true");
        else button.removeAttribute("aria-current");
      });
      document.querySelectorAll("[data-saved-view]").forEach((button) => {
        const active = state.savedView === button.dataset.savedView;
        button.classList.toggle("is-active", active);
        if (active) button.setAttribute("aria-current", "true");
        else button.removeAttribute("aria-current");
      });
      if (pageSizeSelect && Number(pageSizeSelect.value) !== state.pageSize) pageSizeSelect.value = String(state.pageSize);
      if (sortSelect) sortSelect.value = state.sort.key || "";
      if (sortDirectionSelect) sortDirectionSelect.value = state.sort.direction || "asc";
      columnMenu?.querySelectorAll("[data-column-toggle]").forEach((checkbox) => {
        checkbox.checked = state.columns.has(checkbox.dataset.columnToggle);
      });
      syncColumnVisibility();
    }

    function syncColumnVisibility() {
      document.querySelectorAll("[data-optional-column]").forEach((cell) => {
        const key = cell.dataset.column || cell.dataset.columnHeader || "";
        cell.hidden = !state.columns.has(key);
      });
    }

    function setRangeFromControl(field, side) {
      const input = rangeInputs[side][field];
      const value = validRangeValue(input?.value || "");
      state.ranges[field][side] = value;
      resetPage();
      applyWorkspace({ updateUrl: true, replaceUrl: true });
    }

    function cycleSort(key) {
      if (!SORT_FIELDS[key]) return;
      if (state.sort.key !== key) {
        state.sort = { key, direction: "asc" };
      } else if (state.sort.direction === "asc") {
        state.sort = { key, direction: "desc" };
      } else {
        state.sort = { key: "", direction: "" };
      }
      applyWorkspace({ updateUrl: true });
    }

    function updateUrlState(replaceUrl) {
      const params = new URLSearchParams();
      params.set("preset", state.preset || DEFAULT_PRESET);
      if (state.q) params.set("q", state.q);
      if (state.savedView !== "all") params.set("view", state.savedView);
      params.set("pod_filter", validPodFilter(state.pod, DEFAULT_POD_FILTER));
      Object.entries(CATEGORY_FIELDS).forEach(([field, config]) => {
        Array.from(state.categories[field]).sort().forEach((value) => params.append(config.param, value));
      });
      Object.entries(RANGE_FIELDS).forEach(([field, config]) => {
        const range = state.ranges[field];
        if (range.min !== "") params.set(config.minParam, range.min);
        if (range.max !== "") params.set(config.maxParam, range.max);
      });
      Object.entries(EVIDENCE_FILTER_GROUPS).forEach(([family, config]) => {
        Array.from(state.evidence[family]).sort().forEach((value) => params.append(config.param, value));
      });
      Array.from(state.quick).sort().forEach((value) => params.append("quick", value));
      if (state.sort.key && state.sort.direction) {
        params.set("sort", state.sort.key);
        params.set("direction", state.sort.direction);
      }
      if (state.page > 1) params.set("page", String(state.page));
      if (state.pageSize !== DEFAULT_PAGE_SIZE) params.set("page_size", String(state.pageSize));
      const focus = compactFocusId(focusedId);
      if (focus) params.set("focus", focus);
      const query = params.toString();
      const nextUrl = `${window.location.pathname}${query ? `?${query}` : ""}`;
      const currentUrl = `${window.location.pathname}${window.location.search}`;
      if (nextUrl === currentUrl) return;
      window.history[replaceUrl ? "replaceState" : "pushState"]({}, "", nextUrl);
    }

    function validSavedView(key) {
      return key && SAVED_VIEWS[key] && !SAVED_VIEWS[key].disabled ? key : "all";
    }

    function validPreset(key) {
      return key && PRODUCT_PRESETS[key] ? key : DEFAULT_PRESET;
    }

    function validPodFilter(key, fallback = "") {
      return key && POD_FILTERS[key] ? key : fallback;
    }

    function validPodBucket(key) {
      return POD_BUCKETS.has(key) ? key : "";
    }

    function podFilterBucket(value) {
      const normalized = textValue(value, "").toLowerCase();
      if (normalized === "yes" || normalized === "maybe") return "pod";
      if (normalized === "no") return "non_pod";
      return "unknown";
    }

    function validRangeValue(value) {
      const number = numberValue(value);
      return number === null ? "" : String(number);
    }

    function validPage(value) {
      const number = Number(value);
      return Number.isInteger(number) && number > 0 ? number : 1;
    }

    function validPageSize(value) {
      const number = Number(value);
      return PAGE_SIZES.includes(number) ? number : DEFAULT_PAGE_SIZE;
    }

    function validFocusId(value) {
      const text = textValue(value, "");
      return productById.has(text) ? text : "";
    }

    function compactFocusId(value) {
      const text = textValue(value, "");
      return text && text.length <= 64 ? text : "";
    }

    function focusedProduct() {
      return productById.get(focusedId) || null;
    }

    function focusProduct(id, { scroll = false, updateUrl = false, moveDomFocus = false, loadDetail = true } = {}) {
      if (!productById.has(id)) return;
      focusedId = id;
      hoverId = "";
      window.clearTimeout(hoverDetailTimer);
      clearHoverClass();
      renderFocusedRows();
      updatePreview(focusedProduct(), { loadDetail });
      const row = rowForProduct(id);
      if (row && moveDomFocus) row.focus({ preventScroll: true });
      if (row && scroll) row.scrollIntoView({ block: "nearest" });
      if (updateUrl) updateUrlState(false);
    }

    function ensureFocusedProduct() {
      if (currentPageItems.some((product) => product.__id === focusedId)) return;
      focusedId = currentPageItems[0]?.__id || "";
    }

    function renderFocusedRows() {
      tbody?.querySelectorAll("[data-product-row]").forEach((row) => {
        const focused = row.dataset.productId === focusedId;
        row.classList.toggle("is-focused", focused);
        row.setAttribute("aria-selected", focused ? "true" : "false");
        row.tabIndex = focused ? 0 : -1;
      });
    }

    function toggleSelection(id) {
      if (!productById.has(id)) return;
      if (selectedIds.has(id)) selectedIds.delete(id);
      else selectedIds.add(id);
      renderVisibleSelectionState();
      renderSelectionToolbar();
      updateSelectPageState();
    }

    function renderVisibleSelectionState() {
      tbody?.querySelectorAll("[data-product-row]").forEach((row) => {
        const checked = selectedIds.has(row.dataset.productId);
        row.classList.toggle("is-checked", checked);
        const checkbox = row.querySelector("[data-row-checkbox]");
        if (checkbox) checkbox.checked = checked;
      });
    }

    function updateSelectPageState() {
      if (!selectPageCheckbox) return;
      const pageCount = currentPageItems.length;
      const selectedOnPage = currentPageItems.filter((product) => selectedIds.has(product.__id)).length;
      selectPageCheckbox.disabled = pageCount === 0;
      selectPageCheckbox.checked = pageCount > 0 && selectedOnPage === pageCount;
      selectPageCheckbox.indeterminate = selectedOnPage > 0 && selectedOnPage < pageCount;
    }

    function hiddenSelectedCount() {
      const matchedIds = new Set(currentMatched.map((product) => product.__id));
      let hidden = 0;
      selectedIds.forEach((id) => {
        if (!matchedIds.has(id)) hidden += 1;
      });
      return hidden;
    }

    function clearHoverClass() {
      tbody?.querySelectorAll(".is-hovered").forEach((row) => row.classList.remove("is-hovered"));
    }

    function rowForProduct(id) {
      return Array.from(tbody?.querySelectorAll("[data-product-row]") || []).find((row) => row.dataset.productId === id) || null;
    }

    function updatePreview(product, { loadDetail = false } = {}) {
      if (!preview || !product) return;
      const sameProduct = previewId === product.__id;
      previewRequestId += 1;
      const requestId = previewRequestId;
      if (sameProduct && !loadDetail && !product.__detailLoaded) return;
      previewId = product.__id;
      setText("[data-preview-title]", product.title);
      setText("[data-preview-why]", whyItMatters(product));
      setText("[data-preview-momentum]", momentumLabel(product));
      setText("[data-preview-proof]", marketProof(product));
      setText("[data-preview-seller]", product.seller);
      setText("[data-preview-idea]", product.idea);
      setText("[data-preview-type]", product.product_type);
      setText("[data-preview-price]", priceDisplay(product));
      setText("[data-preview-reviews]", reviewDisplay(product));
      setText("[data-preview-bsr]", bsrDisplay(product));
      setText("[data-preview-score]", displayValue(product.winner_score));
      setText("[data-preview-growth]", displayValue(product.growth));
      setText("[data-preview-asin]", displayValue(product.asin));
      setText("[data-preview-source]", displayValue(product.source || product.status));
      const image = preview.querySelector("[data-preview-image]");
      if (image) {
        image.dataset.fallback = "false";
        image.src = productImage(product);
        image.alt = `${product.title} product image`;
      }
      setPreviewAction("amazon", productAmazonUrl(product));
      setPreviewAction("seller", product.seller_url || "");
      setPreviewAction("source", product.sourceUrl || "");
      setPreviewAction("copy-asin", product.asin || "");
      setPreviewAction("copy-url", productAmazonUrl(product));
      if (product.__detailLoaded) {
        renderEvidenceInspector(product);
      } else {
        renderInspectorPending(product);
      }
      if (loadDetail) requestProductDetail(product, requestId);
    }

    function setText(selector, value) {
      const element = preview.querySelector(selector);
      if (element) element.textContent = String(value);
    }

    function setPreviewAction(action, url) {
      const button = preview.querySelector(`[data-preview-action="${action}"]`);
      if (!button) return;
      if (url) {
        button.disabled = false;
      } else {
        button.disabled = true;
      }
    }

    function productAmazonUrl(product) {
      const explicitUrl = textValue(product.amazon_url || product.product_url, "");
      if (explicitUrl) return explicitUrl;
      const asin = textValue(product.asin, "");
      if (asin) return `https://www.amazon.com/dp/${encodeURIComponent(asin)}`;
      const path = textValue(product.amazonPath, "");
      return path ? `https://www.amazon.com${path}` : "";
    }

    function handleRowAction(button) {
      const row = button.closest("[data-product-row]");
      const product = productById.get(row?.dataset.productId || "");
      handlePreviewAction(button.dataset.rowAction, product);
    }

    function handlePreviewAction(action, product) {
      if (!product) return;
      if (action === "amazon") openUrl(productAmazonUrl(product));
      if (action === "seller") openUrl(product.seller_url || "");
      if (action === "source") openUrl(product.sourceUrl || "");
      if (action === "copy-asin") copyText(product.asin || "");
      if (action === "copy-url") copyText(productAmazonUrl(product));
    }

    function openUrl(url) {
      if (url) window.open(url, "_blank", "noopener");
    }

    function copyText(value) {
      const text = textValue(value, "");
      if (!text) return;
      if (navigator.clipboard?.writeText) {
        navigator.clipboard.writeText(text).catch(() => {});
      }
    }

    function collapseInspectorDetails() {
      hoverId = "";
      clearHoverClass();
      const product = focusedProduct();
      if (product) {
        product.__detailLoaded = false;
        updatePreview(product, { loadDetail: false });
      }
    }

    function renderInspectorPending(product) {
      const hasDetail = Boolean(product.detailAsset);
      const message = hasDetail ? "Evidence details load when this product is focused." : "No detail payload is available for this product.";
      setHtml("[data-inspector-summary-body]", evidenceSummaryHtml(product));
      setHtml("[data-inspector-seller-body]", `<div class="inspector-no-data">${escapeHtml(message)}</div>`);
      setHtml("[data-inspector-best-seller-body]", noDataHtml());
      setHtml("[data-inspector-new-release-body]", noDataHtml());
      setHtml("[data-inspector-bsr-body]", noDataHtml());
      setHtml("[data-inspector-reasons-body]", noDataHtml());
      setHtml("[data-inspector-source-details-body]", noDataHtml());
      setHtml("[data-inspector-metadata-body]", productMetadataHtml(product));
    }

    function requestProductDetail(product, requestId) {
      renderInspectorLoading(product);
      loadProductDetail(product).then((detail) => {
        if (previewId !== product.__id || requestId !== previewRequestId) return;
        applyProductDetail(product, detail);
        setPreviewAction("amazon", productAmazonUrl(product));
        setPreviewAction("seller", product.seller_url || "");
        setPreviewAction("source", product.sourceUrl || "");
        setPreviewAction("copy-asin", product.asin || "");
        setPreviewAction("copy-url", productAmazonUrl(product));
        renderEvidenceInspector(product);
      }).catch(() => {
        if (previewId !== product.__id || requestId !== previewRequestId) return;
        setHtml("[data-inspector-seller-body]", '<div class="inspector-no-data">Evidence details could not be loaded.</div>');
        setHtml("[data-inspector-best-seller-body]", noDataHtml());
        setHtml("[data-inspector-new-release-body]", noDataHtml());
        setHtml("[data-inspector-bsr-body]", noDataHtml());
        setHtml("[data-inspector-source-details-body]", '<div class="inspector-no-data">Missing detail chunk</div>');
      });
    }

    function renderInspectorLoading(product) {
      setHtml("[data-inspector-summary-body]", evidenceSummaryHtml(product));
      const skeleton = '<div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div>';
      setHtml("[data-inspector-seller-body]", skeleton);
      setHtml("[data-inspector-best-seller-body]", skeleton);
      setHtml("[data-inspector-new-release-body]", skeleton);
      setHtml("[data-inspector-bsr-body]", skeleton);
      setHtml("[data-inspector-reasons-body]", skeleton);
      setHtml("[data-inspector-source-details-body]", skeleton);
      setHtml("[data-inspector-metadata-body]", productMetadataHtml(product));
    }

    function loadProductDetail(product) {
      if (!product?.detailAsset) return Promise.resolve({});
      if (detailCache.has(product.__id)) return Promise.resolve(detailCache.get(product.__id));
      const globalDetail = window.AMS_PRODUCT_EXPLORER_DETAILS?.[product.__id];
      if (globalDetail) {
        detailCache.set(product.__id, globalDetail);
        return Promise.resolve(globalDetail);
      }
      if (detailPromises.has(product.__id)) return detailPromises.get(product.__id);
      const promise = new Promise((resolve, reject) => {
        const script = document.createElement("script");
        script.src = product.detailAsset;
        script.async = true;
        script.dataset.productDetailAsset = product.__id;
        script.onload = () => {
          const detail = window.AMS_PRODUCT_EXPLORER_DETAILS?.[product.__id] || {};
          detailCache.set(product.__id, detail);
          detailPromises.delete(product.__id);
          resolve(detail);
        };
        script.onerror = () => {
          detailPromises.delete(product.__id);
          reject(new Error(`Unable to load ${product.detailAsset}`));
        };
        document.head.appendChild(script);
      });
      detailPromises.set(product.__id, promise);
      return promise;
    }

    function applyProductDetail(product, detail) {
      if (!detail || typeof detail !== "object") detail = {};
      if (detail.amazon_url) product.amazon_url = detail.amazon_url;
      if (detail.product_url) product.product_url = detail.product_url;
      if (detail.seller_url) product.seller_url = detail.seller_url;
      if (detail.source_url) product.sourceUrl = detail.source_url;
      product.sourceDetails = normalizeSourceDetails(detail.source_details);
      product.evidenceStates = normalizeEvidenceStates(detail.evidence_states, product.sourceDetails);
      product.evidenceReasons = Array.isArray(detail.evidence_reasons) ? detail.evidence_reasons : splitValues(detail.evidence_reasons);
      product.podRelevanceReasons = Array.isArray(detail.pod_relevance_reasons) ? detail.pod_relevance_reasons : splitValues(detail.pod_relevance_reasons);
      product.primaryBsrRank = numberValue(detail.primary_bsr_rank ?? product.primaryBsrRank);
      product.primaryBsrCategory = textValue(detail.primary_bsr_category, product.primaryBsrCategory);
      product.subBsrRank = numberValue(detail.bsr_evidence_best_sub_bsr ?? detail.sub_bsr_rank ?? product.subBsrRank);
      product.subBsrCategory = textValue(detail.bsr_evidence_best_sub_bsr_category || detail.sub_bsr_category, product.subBsrCategory);
      product.__detailLoaded = true;
    }

    function scheduleHoverDetailLoad(productId) {
      window.clearTimeout(hoverDetailTimer);
      hoverDetailTimer = window.setTimeout(() => {
        if (hoverId !== productId || previewId !== productId) return;
        const product = productById.get(productId);
        if (product && !product.__detailLoaded) requestProductDetail(product, previewRequestId);
      }, 220);
    }

    function renderEvidenceInspector(product) {
      setHtml("[data-inspector-summary-body]", evidenceSummaryHtml(product));
      setHtml("[data-inspector-seller-body]", sourceFamilyInspector(product, "seller", "seller", [
        ["leader", "Seller Leader"],
        ["mover", "Seller Mover"],
        ["new_push", "Seller New Push"],
      ]));
      setHtml("[data-inspector-best-seller-body]", sourceFamilyInspector(product, "best_seller", "best_seller", [
        ["winner", "Category Winner"],
        ["breakout", "Category Breakout"],
        ["stable", "Category Stable"],
      ]));
      setHtml("[data-inspector-new-release-body]", sourceFamilyInspector(product, "new_release", "new_release", [
        ["rising", "New Release Rising"],
        ["breakout", "New Release Breakout"],
        ["candidate", "New Release Candidate"],
      ]));
      setHtml("[data-inspector-bsr-body]", bsrInspector(product));
      setHtml("[data-inspector-reasons-body]", reasonsInspector(product));
      setHtml("[data-inspector-source-details-body]", allSourceDetailsInspector(product));
      setHtml("[data-inspector-metadata-body]", productMetadataHtml(product));
    }

    function evidenceSummaryHtml(product) {
      const badges = product.evidenceBadges || [];
      if (!badges.length) return noDataHtml();
      return `<div class="evidence-cell">${badges.map((badge) => evidenceBadgeHtml(badge)).join("")}</div>
        <div class="inspector-metrics">
          ${inspectorMetric("Evidence count", formatPlain(product.evidenceCount))}
          ${inspectorMetric("Source families", formatPlain(product.evidence_source_family_count))}
        </div>`;
    }

    function sourceFamilyInspector(product, familyKey, stateKey, signals) {
      const details = product.sourceDetails?.[familyKey] || [];
      const states = product.evidenceStates?.[stateKey] || {};
      const sourceCount = details.length;
      if (!sourceCount && Object.values(states).every((value) => value === "no_data")) return noDataHtml();
      return `<div class="inspector-status-list">${signals.map(([key, label]) => evidenceStatus(label, states[key] || "no_data")).join("")}</div>
        <div class="inspector-metrics">
          ${inspectorMetric("Best/current rank", formatRank(bestRank(details)))}
          ${inspectorMetric("Previous rank", formatRank(bestPreviousRank(details)))}
          ${inspectorMetric("Movement", formatSigned(bestMovement(details)))}
          ${inspectorMetric("Days seen", formatPlain(maxDaysSeen(details)))}
          ${inspectorMetric("Source count", formatPlain(sourceCount || maxObservationCount(details)))}
        </div>
        ${sourceDetailList(details)}`;
    }

    function bsrInspector(product) {
      const details = product.sourceDetails?.bsr || [];
      const states = product.evidenceStates?.bsr || {};
      const hasBsrData = product.subBsrRank !== null || product.primaryBsrRank !== null || details.length > 0;
      if (!hasBsrData) return noDataHtml();
      return `<div class="inspector-status-list">
          ${evidenceStatus("Strong Sub-BSR", states.strong || "no_data")}
          ${evidenceStatus("Very Strong Sub-BSR", states.very_strong || "no_data")}
        </div>
        <div class="inspector-metrics">
          ${inspectorMetric("Sub-category BSR", formatRank(product.subBsrRank))}
          ${inspectorMetric("Sub-category", product.subBsrCategory || "No data")}
          ${inspectorMetric("Primary BSR", formatRank(product.primaryBsrRank))}
          ${inspectorMetric("Primary category", product.primaryBsrCategory || "No data")}
        </div>
        ${sourceDetailList(details, { includeBsr: true })}`;
    }

    function reasonsInspector(product) {
      const reasons = new Set(product.evidenceReasons || []);
      Object.values(product.sourceDetails || {}).flat().forEach((detail) => {
        (detail.evidence_reasons || []).forEach((reason) => reasons.add(reason));
      });
      if (!reasons.size) return noDataHtml();
      return `<ul class="evidence-reason-list">${Array.from(reasons).slice(0, 8).map((reason) => `<li>${escapeHtml(reason)}</li>`).join("")}</ul>`;
    }

    function allSourceDetailsInspector(product) {
      const families = [
        ["seller", "Seller"],
        ["best_seller", "Best Seller"],
        ["new_release", "New Release"],
        ["bsr", "BSR"],
      ];
      const rows = [];
      families.forEach(([family, label]) => {
        (product.sourceDetails?.[family] || []).forEach((detail) => {
          rows.push(sourceDetailRow({ ...detail, source_family_label: label }, true));
        });
      });
      return rows.length ? `<div class="source-detail-list">${rows.join("")}</div>` : noDataHtml();
    }

    function productMetadataHtml(product) {
      const firstDetail = firstSourceDetail(product);
      return `<div class="inspector-metrics">
        ${inspectorMetric("ASIN", displayValue(product.asin))}
        ${inspectorMetric("Marketplace", displayValue(product.marketplace || firstDetail.marketplace))}
        ${inspectorMetric("Product type", displayValue(product.product_type))}
        ${inspectorMetric("Recipient", displayValue(product.recipient))}
        ${inspectorMetric("Theme", displayValue(product.theme))}
        ${inspectorMetric("Occasion", displayValue(product.occasion))}
        ${inspectorMetric("Source ID", displayValue(product.source_id || firstDetail.source_id))}
        ${inspectorMetric("Source type", displayValue(product.source_type || firstDetail.source_type))}
      </div>`;
    }

    function firstSourceDetail(product) {
      return Object.values(product.sourceDetails || {}).flat()[0] || {};
    }

    function evidenceStatus(label, state) {
      const normalized = ["true", "false", "no_data"].includes(state) ? state : "no_data";
      const text = normalized === "true" ? "Active" : normalized === "false" ? "Not active" : "No data";
      return `<div class="evidence-status is-${normalized.replace("_", "-")}">
        <span>${escapeHtml(label)}</span>
        <strong>${text}</strong>
      </div>`;
    }

    function inspectorMetric(label, value) {
      return `<div class="inspector-metric"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value || "No data")}</strong></div>`;
    }

    function sourceDetailList(details, { includeBsr = false } = {}) {
      if (!details.length) return "";
      return `<div class="source-detail-list">${details.map((detail) => sourceDetailRow(detail, includeBsr)).join("")}</div>`;
    }

    function sourceDetailRow(detail, includeBsr) {
      const rankLine = [
        `Rank ${formatRank(detail.source_rank)}`,
        `Prev ${formatRank(detail.previous_source_rank)}`,
        `Move ${formatSigned(detail.source_rank_change)}`,
        `Days ${formatPlain(detail.source_days_seen)}`,
        `Obs ${formatPlain(detail.source_observation_count)}`,
      ].join(" | ");
      const category = detail.category_name ? `<span>${escapeHtml(detail.category_name)}</span>` : "";
      const sourceType = detail.source_type ? `<span>${escapeHtml(detail.source_type)}${detail.source_id ? ` - ${escapeHtml(detail.source_id)}` : ""}</span>` : "";
      const marketplace = detail.marketplace ? `<span>${escapeHtml(detail.marketplace)}</span>` : "";
      const family = detail.source_family_label ? `<span>${escapeHtml(detail.source_family_label)}</span>` : "";
      const bsr = includeBsr ? `<span>Sub ${formatRank(detail.sub_bsr_rank)} ${escapeHtml(detail.sub_bsr_category || "")}</span><span>Primary ${formatRank(detail.primary_bsr_rank)} ${escapeHtml(detail.primary_bsr_category || "")}</span>` : "";
      return `<article class="source-detail-row">
        <strong>${escapeHtml(detail.source_name)}</strong>
        ${family}
        ${sourceType}
        ${marketplace}
        ${category}
        <span>${escapeHtml(rankLine)}</span>
        ${bsr}
      </article>`;
    }

    function noDataHtml() {
      return '<div class="inspector-no-data">No data</div>';
    }

    function setHtml(selector, value) {
      const element = preview.querySelector(selector);
      if (element) element.innerHTML = value;
    }

    function formatRank(value) {
      return value === null || value === undefined || value === "" ? "No data" : `#${formatNumber(value)}`;
    }

    function formatSigned(value) {
      if (value === null || value === undefined || value === "") return "No data";
      return Number(value) > 0 ? `+${formatNumber(value)}` : formatNumber(value);
    }

    function formatPlain(value) {
      return value === null || value === undefined || value === "" ? "No data" : formatNumber(value);
    }

    function productImage(product) {
      const image = textValue(product.image_url || product.image, "");
      return image || placeholderImage(product.product_type || product.asin || "P", product.tone);
    }

    function fallbackImage(product) {
      return placeholderImage(product?.product_type || product?.asin || "P", product?.tone || "neutral");
    }

    function visibleRangeText() {
      if (products.length === 0) return "Showing 0 of 0 products";
      if (currentMatched.length === 0) return `Showing 0 of ${formatNumber(products.length)} products`;
      const start = pageStartIndex() + 1;
      const end = Math.min(pageStartIndex() + state.pageSize, currentMatched.length);
      return `Showing ${formatNumber(start)}-${formatNumber(end)} of ${formatNumber(currentMatched.length)} products`;
    }

    function pageStartIndex() {
      return (state.page - 1) * state.pageSize;
    }

    function pageCount() {
      return Math.max(1, Math.ceil(currentSorted.length / state.pageSize));
    }

    function resetPage() {
      state.page = 1;
    }

    function uniqueMeaningfulCount(items, field) {
      const meaningful = new Set();
      const fallback = new Set();
      items.forEach((item) => {
        const value = textValue(item[field], "");
        if (!value) return;
        fallback.add(value);
        if (!["unknown", "uncategorized", "unknown seller"].includes(value.toLowerCase())) meaningful.add(value);
      });
      return meaningful.size || fallback.size;
    }

    function isInteractiveTarget(target) {
      return Boolean(target.closest?.("input, textarea, select, button, a, [contenteditable='true']"));
    }

    function clamp(value, min, max) {
      return Math.min(Math.max(Number(value) || min, min), max);
    }

    function placeholderImage(label, tone) {
      const colors = {
        winner: ["#e8f6ee", "#16803c"],
        rising: ["#fff3e3", "#b25a00"],
        stable: ["#eaf1ff", "#1f5fbf"],
        alert: ["#fdecec", "#c9342f"],
        idea: ["#f2edff", "#6d3acb"],
        neutral: ["#f5f7fa", "#3f4b5b"],
      };
      const [background, foreground] = colors[toneName(tone)] || colors.idea;
      const safeLabel = textValue(label, "P").slice(0, 3).toUpperCase();
      const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="320" height="240" viewBox="0 0 320 240"><rect width="320" height="240" rx="24" fill="${background}"/><circle cx="160" cy="98" r="42" fill="${foreground}" opacity=".16"/><text x="160" y="148" text-anchor="middle" font-family="Arial, sans-serif" font-size="42" font-weight="700" fill="${foreground}">${escapeHtml(safeLabel)}</text></svg>`;
      return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
    }

    function statusBadge(value, tone) {
      return `<span class="status-badge tone-${toneName(tone)}">${escapeHtml(value)}</span>`;
    }

    function displayValue(value) {
      const text = textValue(value, "");
      return text && text !== "-" ? text : "\u2014";
    }

    function displayValueHtml(value) {
      const text = displayValue(value);
      return text === "\u2014" ? '<span class="missing-value">\u2014</span>' : escapeHtml(text);
    }

    function reviewDisplay(product) {
      return product.reviewValue === null ? "\u2014" : formatNumber(product.reviewValue);
    }

    function priceDisplay(product) {
      return product.priceValue === null ? "\u2014" : `$${Number(product.priceValue).toFixed(2)}`;
    }

    function bsrDisplay(product) {
      if (product.subBsrRank !== null) return `#${formatNumber(product.subBsrRank)}`;
      if (product.primaryBsrRank !== null) return `#${formatNumber(product.primaryBsrRank)}`;
      return "\u2014";
    }

    function textValue(value, fallback = "") {
      const text = String(value ?? "").trim();
      return text || fallback;
    }

    function cleanQuery(value) {
      return String(value || "").replace(/\s+/g, " ").trim();
    }

    function normalizeSearch(value) {
      return cleanQuery(value).toLowerCase();
    }

    function numberValue(value) {
      const text = String(value ?? "").replace(/[^0-9.+-]/g, "");
      if (!text || text === "+" || text === "-" || text === ".") return null;
      const number = Number(text);
      return Number.isFinite(number) ? number : null;
    }

    function toneName(tone) {
      const value = String(tone || "neutral").toLowerCase().replace(/_/g, "-");
      return ["winner", "rising", "stable", "alert", "idea", "neutral"].includes(value) ? value : "neutral";
    }

    function escapeHtml(value) {
      return String(value ?? "").replace(/[&<>"']/g, (char) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      }[char]));
    }

    function formatNumber(value) {
      return Number(value || 0).toLocaleString();
    }
  })();"""


def _safe_int(value: object) -> int:
    try:
        return int(float(str(value or "").replace(",", "")))
    except (TypeError, ValueError):
        return 0


def _competition_tone(value: str) -> str:
    key = value.strip().lower()
    if key == "low":
        return "winner"
    if key == "medium":
        return "stable"
    if key == "high":
        return "alert"
    return "neutral"


def _score_tone(value: int) -> str:
    if value >= 84:
        return "winner"
    if value >= 80:
        return "idea"
    if value >= 75:
        return "stable"
    return "neutral"
