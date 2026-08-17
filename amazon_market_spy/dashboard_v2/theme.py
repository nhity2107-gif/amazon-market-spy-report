from __future__ import annotations


DESIGN_TOKENS = {
    "colors": {
        "winner": "#16803c",
        "winner_soft": "#e8f6ee",
        "rising": "#b25a00",
        "rising_soft": "#fff3e3",
        "stable": "#1f5fbf",
        "stable_soft": "#eaf1ff",
        "alert": "#c9342f",
        "alert_soft": "#fdecec",
        "idea": "#6d3acb",
        "idea_soft": "#f2edff",
        "neutral_0": "#ffffff",
        "neutral_25": "#fbfcfd",
        "neutral_50": "#f5f7fa",
        "neutral_100": "#e4e8ee",
        "neutral_200": "#cbd3df",
        "neutral_400": "#738194",
        "neutral_600": "#3f4b5b",
        "neutral_800": "#182230",
        "focus": "#245bd6",
    },
    "space": {
        "4": "4px",
        "8": "8px",
        "12": "12px",
        "16": "16px",
        "24": "24px",
        "32": "32px",
        "48": "48px",
    },
    "radius": {
        "card": "12px",
        "control": "9px",
        "pill": "999px",
    },
    "type": {
        "page_title": "28px",
        "section_title": "20px",
        "card_title": "16px",
        "body": "14px",
        "caption": "12px",
    },
}


def theme_styles() -> str:
    colors = DESIGN_TOKENS["colors"]
    space = DESIGN_TOKENS["space"]
    radius = DESIGN_TOKENS["radius"]
    type_scale = DESIGN_TOKENS["type"]
    variables = "\n".join(
        [
            *[f"    --color-{name.replace('_', '-')}: {value};" for name, value in colors.items()],
            *[f"    --space-{name}: {value};" for name, value in space.items()],
            *[f"    --radius-{name}: {value};" for name, value in radius.items()],
            *[f"    --type-{name.replace('_', '-')}: {value};" for name, value in type_scale.items()],
        ]
    )
    return f"""
  <style>
  :root {{
{variables}
    --shadow-card: 0 1px 1px rgba(24, 34, 48, 0.04);
    --shell-width: 1440px;
  }}
  * {{ box-sizing: border-box; }}
  [hidden] {{ display: none !important; }}
  html {{ color-scheme: light; }}
  body {{
    margin: 0;
    background: var(--color-neutral-50);
    color: var(--color-neutral-800);
    font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    font-size: var(--type-body);
    line-height: 1.45;
  }}
  a {{ color: inherit; }}
  a:focus-visible, button:focus-visible, input:focus-visible, select:focus-visible {{
    outline: 3px solid rgba(36, 91, 214, 0.35);
    outline-offset: 2px;
  }}
  .app-shell {{
    min-height: 100vh;
  }}
  .top-shell {{
    background: var(--color-neutral-0);
    border-bottom: 1px solid var(--color-neutral-100);
    padding: var(--space-8) var(--space-16);
    position: sticky;
    top: 0;
    z-index: 20;
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    gap: var(--space-16);
    align-items: center;
  }}
  .brand {{
    display: flex;
    align-items: center;
    gap: var(--space-8);
    font-weight: 750;
    white-space: nowrap;
  }}
  .brand-mark {{
    width: 28px;
    height: 28px;
    border-radius: 8px;
    display: grid;
    place-items: center;
    background: var(--color-idea-soft);
    color: var(--color-idea);
    border: 1px solid #ded4fb;
    font-size: 13px;
  }}
  .primary-nav {{
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-4);
    min-width: 0;
  }}
  .nav-link {{
    display: flex;
    align-items: center;
    gap: var(--space-8);
    min-height: 34px;
    padding: 0 var(--space-12);
    border-radius: var(--radius-control);
    color: var(--color-neutral-600);
    text-decoration: none;
    font-weight: 650;
    font-size: 13px;
  }}
  .nav-link svg {{ width: 16px; height: 16px; color: currentColor; }}
  .nav-link[aria-current="page"] {{
    background: var(--color-neutral-800);
    color: var(--color-neutral-0);
  }}
  .dataset-strip {{
    display: flex;
    justify-content: flex-end;
    align-items: center;
    gap: var(--space-8);
    color: var(--color-neutral-400);
    font-size: var(--type-caption);
    white-space: nowrap;
  }}
  .dataset-pill {{
    min-height: 24px;
    display: inline-flex;
    align-items: center;
    border: 1px solid var(--color-neutral-100);
    border-radius: var(--radius-pill);
    background: var(--color-neutral-25);
    color: var(--color-neutral-600);
    padding: 0 8px;
    font-weight: 800;
  }}
  .utility-link {{
    color: var(--color-neutral-600);
    text-decoration: none;
    font-weight: 750;
  }}
  .utility-link:hover {{
    color: var(--color-neutral-800);
    text-decoration: underline;
  }}
  .main {{
    min-width: 0;
    padding: var(--space-16);
  }}
  .page {{
    max-width: var(--shell-width);
    margin: 0 auto;
  }}
  .page-header {{
    display: flex;
    justify-content: space-between;
    gap: var(--space-16);
    align-items: flex-start;
    margin-bottom: var(--space-16);
  }}
  h1 {{
    font-size: var(--type-page-title);
    margin: 0 0 var(--space-4);
    line-height: 1.15;
    letter-spacing: 0;
  }}
  .page-subtitle, .muted {{
    margin: 0;
    color: var(--color-neutral-400);
  }}
  .section-header {{
    display: flex;
    justify-content: space-between;
    align-items: end;
    gap: var(--space-16);
    margin: var(--space-16) 0 var(--space-8);
  }}
  .section-header h2 {{
    font-size: var(--type-section-title);
    margin: 0;
    line-height: 1.2;
    letter-spacing: 0;
  }}
  .kpi-grid {{
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: var(--space-8);
  }}
  .market-pulse-grid, .data-status-grid {{
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: var(--space-8);
  }}
  .data-status-grid {{
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }}
  .minimal-queue-grid {{
    grid-template-columns: minmax(0, 1fr);
  }}
  .kpi-card, .compact-card, .panel, .quick-preview {{
    background: var(--color-neutral-0);
    border: 1px solid var(--color-neutral-100);
    border-radius: var(--radius-card);
    box-shadow: var(--shadow-card);
  }}
  .kpi-card {{
    padding: var(--space-12);
    border-left: 4px solid var(--tone-color, var(--color-neutral-200));
  }}
  .kpi-label {{
    font-size: var(--type-caption);
    color: var(--color-neutral-400);
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: .04em;
  }}
  .kpi-value {{
    display: block;
    margin-top: var(--space-4);
    font-size: 24px;
    line-height: 1;
    font-weight: 800;
  }}
  .kpi-caption {{
    display: block;
    margin-top: var(--space-4);
    color: var(--color-neutral-400);
    font-size: var(--type-caption);
  }}
  .content-grid {{
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--space-8);
  }}
  .compact-card {{
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: var(--space-8);
    align-items: center;
    padding: 10px var(--space-12);
  }}
  .compact-card h3 {{
    margin: 0 0 2px;
    font-size: var(--type-card-title);
    line-height: 1.25;
    letter-spacing: 0;
  }}
  .compact-card p {{ margin: 0; color: var(--color-neutral-400); font-size: var(--type-caption); }}
  .status-badge, .filter-chip {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    border-radius: var(--radius-pill);
    font-size: var(--type-caption);
    font-weight: 750;
    line-height: 1;
    white-space: nowrap;
  }}
  .status-badge {{
    min-height: 24px;
    padding: 0 8px;
    color: var(--tone-color, var(--color-neutral-600));
    background: var(--tone-soft, var(--color-neutral-50));
    border: 1px solid color-mix(in srgb, var(--tone-color, var(--color-neutral-200)) 28%, transparent);
  }}
  .filter-chip {{
    min-height: 28px;
    padding: 0 9px;
    border: 1px solid var(--color-neutral-100);
    background: var(--color-neutral-0);
    color: var(--color-neutral-600);
  }}
  .toolbar, .filters-row {{
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--space-8);
  }}
  .toolbar {{
    justify-content: space-between;
    margin-bottom: var(--space-8);
  }}
  .control-group {{
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--space-8);
  }}
  .btn {{
    border: 1px solid transparent;
    border-radius: var(--radius-control);
    min-height: 32px;
    padding: 0 10px;
    font: inherit;
    font-weight: 750;
    font-size: 13px;
    cursor: pointer;
    background: var(--color-neutral-0);
    color: var(--color-neutral-800);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    text-decoration: none;
  }}
  .btn-primary {{ background: var(--color-neutral-800); color: var(--color-neutral-0); }}
  .btn-secondary {{ border-color: var(--color-neutral-200); }}
  .btn-ghost {{ background: transparent; color: var(--color-neutral-600); }}
  .btn:disabled {{
    cursor: not-allowed;
    opacity: .48;
  }}
  .btn:hover:not(:disabled) {{
    border-color: var(--color-neutral-400);
  }}
  .btn-dropdown::after {{ content: "v"; color: var(--color-neutral-400); font-size: 11px; transform: translateY(-1px); }}
  .search-input, .select-input {{
    min-height: 34px;
    border: 1px solid var(--color-neutral-200);
    border-radius: var(--radius-control);
    background: var(--color-neutral-0);
    color: var(--color-neutral-800);
    padding: 0 var(--space-12);
    font: inherit;
  }}
  .search-input {{ min-width: 320px; }}
  #idea-search.search-input {{ width: 460px; }}
  #product-search.search-input {{ width: 360px; }}
  .panel {{ padding: var(--space-12); }}
  .table-shell {{
    overflow: auto;
    border: 1px solid var(--color-neutral-100);
    border-radius: var(--radius-card);
    background: var(--color-neutral-0);
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: var(--type-body);
  }}
  .product-table {{
    table-layout: fixed;
  }}
  .product-table th {{
    letter-spacing: 0;
  }}
  th, td {{
    padding: 7px 10px;
    border-bottom: 1px solid var(--color-neutral-100);
    text-align: left;
    vertical-align: middle;
  }}
  th {{
    color: var(--color-neutral-400);
    background: var(--color-neutral-25);
    font-size: var(--type-caption);
    text-transform: uppercase;
    letter-spacing: .04em;
    height: 34px;
  }}
  .table-shell thead th {{
    position: sticky;
    top: 0;
    z-index: 2;
  }}
  tbody tr {{ height: 44px; }}
  tbody tr:hover {{ background: #f8faff; }}
  tbody tr.is-focused {{
    background: #f3f7ff;
    box-shadow: inset 3px 0 0 var(--color-focus);
  }}
  tr:last-child td {{ border-bottom: 0; }}
  .product-row {{ height: 50px; cursor: pointer; }}
  .product-row:hover, .product-row.is-hovered {{ background: #f8faff; }}
  .product-row.is-focused {{
    background: #f3f7ff;
    box-shadow: inset 3px 0 0 var(--color-focus);
  }}
  .product-row.is-checked {{
    background: var(--color-neutral-25);
  }}
  .product-row.is-focused.is-checked {{
    background: #eef4ff;
  }}
  .product-row:focus-visible {{
    outline: 3px solid rgba(36, 91, 214, 0.32);
    outline-offset: -3px;
  }}
  .product-table th, .product-table td {{
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    padding-left: 6px;
    padding-right: 6px;
  }}
  .product-table td {{
    height: 50px;
  }}
  .product-table th:nth-child(1), .product-table td:nth-child(1) {{ width: 4%; }}
  .product-table th:nth-child(2), .product-table td:nth-child(2) {{ width: 7%; }}
  .product-table th:nth-child(3), .product-table td:nth-child(3) {{ width: 34%; }}
  .product-table th:nth-child(4), .product-table td:nth-child(4) {{ width: 28%; }}
  .product-table th:nth-child(5), .product-table td:nth-child(5) {{ width: 12%; }}
  .product-table th:nth-child(6), .product-table td:nth-child(6) {{ width: 14%; }}
  .product-table th:nth-child(7), .product-table td:nth-child(7) {{ width: 14%; }}
  .product-table th:nth-child(8), .product-table td:nth-child(8) {{ width: 12%; }}
  .product-table th:nth-child(9), .product-table td:nth-child(9) {{ width: 14%; }}
  .product-table th:nth-child(10), .product-table td:nth-child(10) {{ width: 12%; }}
  .product-table th:nth-child(11), .product-table td:nth-child(11) {{ width: 9%; }}
  .product-table th:nth-child(12), .product-table td:nth-child(12) {{ width: 9%; }}
  .product-table th:nth-child(13), .product-table td:nth-child(13) {{ width: 9%; }}
  .product-table th:nth-child(14), .product-table td:nth-child(14) {{ width: 9%; }}
  .product-table th:nth-child(15), .product-table td:nth-child(15) {{ width: 12%; }}
  .product-table th:nth-child(16), .product-table td:nth-child(16) {{ width: 8%; }}
  .product-table th:nth-child(1), .product-table td:nth-child(1),
  .product-table th:nth-child(2), .product-table td:nth-child(2) {{
    text-overflow: clip;
  }}
  .product-table input[type="checkbox"] {{
    width: 16px;
    height: 16px;
    margin: 0;
    accent-color: var(--color-focus);
  }}
  .numeric-cell {{
    text-align: right;
    font-variant-numeric: tabular-nums;
  }}
  .missing-value {{
    color: var(--color-neutral-400);
  }}
  .row-actions {{
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }}
  .row-action {{
    min-width: 26px;
    min-height: 26px;
    border: 1px solid var(--color-neutral-100);
    border-radius: 7px;
    background: var(--color-neutral-0);
    color: var(--color-neutral-600);
    font: inherit;
    font-size: 11px;
    font-weight: 800;
    cursor: pointer;
  }}
  .row-action:disabled {{
    opacity: .45;
    cursor: not-allowed;
  }}
  .sort-button {{
    width: 100%;
    border: 0;
    padding: 0;
    background: transparent;
    color: inherit;
    font: inherit;
    font-size: inherit;
    font-weight: 800;
    text-transform: inherit;
    letter-spacing: inherit;
    display: inline-flex;
    align-items: center;
    justify-content: flex-start;
    gap: 4px;
    cursor: pointer;
  }}
  .sort-button.is-active {{
    color: var(--color-neutral-800);
  }}
  .sort-button [data-sort-indicator] {{
    min-width: 22px;
    color: var(--color-focus);
    font-size: 10px;
    text-transform: uppercase;
  }}
  .link-button {{
    border: 0;
    background: transparent;
    color: inherit;
    font: inherit;
    padding: 0;
    cursor: pointer;
    text-align: left;
  }}
  .link-button:hover {{
    color: var(--color-focus);
    text-decoration: underline;
  }}
  .product-table .status-badge {{
    min-height: 22px;
    padding: 0 6px;
  }}
  .thumbnail {{
    width: 40px;
    height: 40px;
    border-radius: 8px;
    object-fit: cover;
    border: 1px solid var(--color-neutral-100);
  }}
  .product-title-thumbnail {{
    width: 42px;
    height: 42px;
    border-radius: 8px;
    object-fit: cover;
    border: 1px solid var(--color-neutral-100);
    background: var(--color-neutral-50);
  }}
  .product-title-cell {{
    display: grid;
    gap: 2px;
    min-width: 0;
  }}
  .product-title-cell.has-thumbnail {{
    grid-template-columns: 42px minmax(0, 1fr);
    align-items: center;
    gap: var(--space-8);
  }}
  .product-title-copy {{
    display: grid;
    gap: 2px;
    min-width: 0;
  }}
  .product-title-cell strong, .product-title-cell .caption {{
    display: block;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }}
  .caption {{
    color: var(--color-neutral-400);
    font-size: var(--type-caption);
  }}
  .product-workspace {{
    display: grid;
    grid-template-columns: minmax(210px, 19%) minmax(0, 1fr) minmax(280px, 24%);
    gap: var(--space-8);
    align-items: start;
  }}
  .filter-panel {{
    display: grid;
    gap: var(--space-12);
  }}
  .filter-panel h2, .quick-preview h2, .panel-title {{
    margin: 0 0 var(--space-8);
    font-size: var(--type-card-title);
    line-height: 1.25;
    letter-spacing: 0;
  }}
  .filter-list {{
    display: grid;
    gap: var(--space-8);
  }}
  .filter-list button {{
    justify-content: space-between;
    width: 100%;
    text-align: left;
  }}
  .saved-view-list, .filter-row-list, .preset-list {{
    display: grid;
    gap: 2px;
  }}
  .saved-view, .filter-row, .preset-button {{
    width: 100%;
    min-height: 34px;
    border: 0;
    border-radius: 8px;
    background: transparent;
    color: var(--color-neutral-600);
    display: grid;
    grid-template-columns: 18px minmax(0, 1fr);
    align-items: center;
    gap: var(--space-8);
    padding: 0 8px;
    font: inherit;
    font-size: 13px;
    font-weight: 650;
    text-align: left;
    cursor: pointer;
  }}
  .preset-button {{
    grid-template-columns: minmax(0, 1fr) auto;
  }}
  .saved-view:hover, .filter-row:hover, .preset-button:hover {{
    background: var(--color-neutral-50);
    color: var(--color-neutral-800);
  }}
  .saved-view.is-active, .preset-button.is-active {{
    background: var(--color-neutral-800);
    color: var(--color-neutral-0);
  }}
  .saved-view[disabled], .filter-row[disabled] {{
    cursor: not-allowed;
    color: var(--color-neutral-400);
    opacity: .62;
  }}
  .filter-row.is-active {{
    background: var(--tone-soft, var(--color-neutral-50));
    color: var(--tone-color, var(--color-neutral-800));
  }}
  .filter-row {{
    grid-template-columns: minmax(0, 1fr) auto;
    min-height: 32px;
  }}
  .filter-row strong {{
    min-width: 26px;
    text-align: right;
    color: var(--tone-color, var(--color-neutral-400));
  }}
  .evidence-filter-groups {{
    display: grid;
    gap: var(--space-8);
  }}
  .evidence-filter-group {{
    display: grid;
    gap: 2px;
    margin: 0;
    padding: 0 0 var(--space-8);
    border: 0;
    border-bottom: 1px solid var(--color-neutral-100);
  }}
  .evidence-filter-group:last-child {{ border-bottom: 0; padding-bottom: 0; }}
  .evidence-filter-group legend {{
    margin-bottom: 4px;
    padding: 0;
    color: var(--color-neutral-400);
    font-size: 11px;
    font-weight: 800;
    text-transform: uppercase;
  }}
  .evidence-filter-option {{
    min-height: 30px;
    display: grid;
    grid-template-columns: 16px minmax(0, 1fr) auto;
    align-items: center;
    gap: 6px;
    padding: 0 6px;
    border-radius: 8px;
    color: var(--color-neutral-600);
    font-size: 12px;
    font-weight: 650;
    cursor: pointer;
  }}
  .evidence-filter-option:hover {{
    background: var(--tone-soft, var(--color-neutral-50));
    color: var(--tone-color, var(--color-neutral-800));
  }}
  .evidence-filter-option input {{
    width: 14px;
    height: 14px;
    margin: 0;
    accent-color: var(--tone-color, var(--color-focus));
  }}
  .evidence-filter-option span {{
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }}
  .evidence-filter-option strong {{
    color: var(--tone-color, var(--color-neutral-400));
    font-size: 11px;
  }}
  .small-icon {{
    width: 15px;
    height: 15px;
    color: currentColor;
  }}
  .toolbar-actions {{
    display: flex;
    align-items: center;
    gap: var(--space-8);
    flex-wrap: wrap;
  }}
  .toolbar-divider {{
    width: 1px;
    height: 24px;
    background: var(--color-neutral-100);
  }}
  .select-input {{
    min-height: 32px;
    border: 1px solid var(--color-neutral-200);
    border-radius: var(--radius-control);
    background: var(--color-neutral-0);
    color: var(--color-neutral-700, var(--color-neutral-800));
    padding: 0 8px;
    font: inherit;
    font-size: 12px;
  }}
  .sort-select {{ min-width: 146px; }}
  .sort-direction-select {{ min-width: 76px; }}
  .column-menu-wrap {{
    position: relative;
  }}
  .column-menu {{
    position: absolute;
    right: 0;
    top: calc(100% + 4px);
    z-index: 8;
    min-width: 180px;
    display: grid;
    gap: 2px;
    padding: var(--space-8);
    border: 1px solid var(--color-neutral-100);
    border-radius: var(--radius-control);
    background: var(--color-neutral-0);
    box-shadow: 0 8px 24px rgba(24, 34, 48, 0.12);
  }}
  .column-menu label {{
    display: grid;
    grid-template-columns: 16px minmax(0, 1fr);
    align-items: center;
    gap: 6px;
    min-height: 28px;
    color: var(--color-neutral-600);
    font-size: 12px;
    font-weight: 700;
  }}
  .advanced-filter-controls {{
    display: grid;
    gap: var(--space-8);
  }}
  .filter-control {{
    display: grid;
    gap: 4px;
    color: var(--color-neutral-600);
    font-size: var(--type-caption);
    font-weight: 700;
  }}
  .filter-select {{
    width: 100%;
    min-height: 78px;
    border: 1px solid var(--color-neutral-200);
    border-radius: var(--radius-control);
    background: var(--color-neutral-0);
    color: var(--color-neutral-800);
    padding: 5px;
    font: inherit;
    font-size: 12px;
  }}
  .filter-select option {{
    padding: 3px 4px;
  }}
  .compact-filter-select {{
    min-height: 66px;
  }}
  .more-filters-panel, .data-details-panel, .compact-result-details, .full-evidence-panel, .row-detail, .market-detail {{
    min-width: 0;
  }}
  .more-filters-panel > summary, .data-details-panel > summary, .compact-result-details > summary, .full-evidence-panel > summary, .row-detail > summary, .market-detail > summary {{
    cursor: pointer;
    color: var(--color-neutral-600);
    font-size: var(--type-caption);
    font-weight: 800;
  }}
  .more-filters-panel > summary, .compact-result-details > summary, .full-evidence-panel > summary {{
    min-height: 30px;
    display: flex;
    align-items: center;
  }}
  .more-filters-panel[open], .compact-result-details[open], .full-evidence-panel[open] {{
    border-top: 1px solid var(--color-neutral-100);
    padding-top: var(--space-8);
  }}
  .data-details-panel > summary {{
    min-height: 34px;
    list-style-position: inside;
  }}
  .data-details-panel[open] > summary {{
    margin-bottom: var(--space-8);
  }}
  .row-detail, .market-detail {{
    margin-top: 4px;
  }}
  .row-detail .metric-grid, .market-detail .metric-grid {{
    grid-template-columns: repeat(3, minmax(0, 1fr));
    margin: var(--space-8) 0;
  }}
  .row-open-link {{
    font-weight: 800;
  }}
  .compact-summary-value {{
    display: inline-flex;
    min-height: 24px;
    align-items: center;
    padding: 0 8px;
    border: 1px solid var(--color-neutral-100);
    border-radius: var(--radius-pill);
    background: var(--color-neutral-25);
    color: var(--color-neutral-800);
    font-weight: 800;
  }}
  .range-filter {{
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 6px;
    margin: 0;
    padding: 8px;
    border: 1px solid var(--color-neutral-100);
    border-radius: var(--radius-control);
  }}
  .range-filter legend {{
    padding: 0 4px;
    color: var(--color-neutral-600);
    font-size: var(--type-caption);
    font-weight: 750;
  }}
  .range-filter label {{
    display: grid;
    gap: 3px;
    color: var(--color-neutral-400);
    font-size: 11px;
    font-weight: 700;
  }}
  .range-input {{
    min-width: 0;
    width: 100%;
    min-height: 30px;
    border: 1px solid var(--color-neutral-200);
    border-radius: 8px;
    padding: 0 6px;
    font: inherit;
    font-size: 12px;
  }}
  .product-results-meta {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-8);
    margin: var(--space-4) 0 var(--space-8);
  }}
  .result-count {{
    margin: 0;
    color: var(--color-neutral-600);
    font-size: var(--type-caption);
    font-weight: 700;
  }}
  .result-cap {{
    margin: 0;
    color: var(--color-rising);
    font-weight: 700;
  }}
  .guidance-line, .filter-text-summary {{
    margin: 0 0 var(--space-8);
    color: var(--color-neutral-600);
    font-size: var(--type-caption);
    font-weight: 700;
  }}
  .filter-text-summary {{
    color: var(--color-neutral-400);
  }}
  .result-stats {{
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin: 0 0 var(--space-8);
  }}
  .result-stats span {{
    min-height: 26px;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 0 8px;
    border: 1px solid var(--color-neutral-100);
    border-radius: var(--radius-pill);
    background: var(--color-neutral-25);
    color: var(--color-neutral-400);
    font-size: var(--type-caption);
    font-weight: 700;
  }}
  .result-stats strong {{
    color: var(--color-neutral-800);
  }}
  .active-filter-summary {{
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: var(--space-8);
    margin: var(--space-8) 0;
    padding: var(--space-8);
    border: 1px solid var(--color-neutral-100);
    border-radius: var(--radius-control);
    background: var(--color-neutral-25);
  }}
  .filter-chip-list {{
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }}
  .active-filter-chip {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    min-height: 26px;
    border: 1px solid var(--color-neutral-200);
    border-radius: var(--radius-pill);
    background: var(--color-neutral-0);
    color: var(--color-neutral-600);
    padding: 0 8px;
    font: inherit;
    font-size: var(--type-caption);
    font-weight: 750;
    cursor: pointer;
  }}
  .active-filter-chip:hover {{
    color: var(--color-neutral-800);
    border-color: var(--color-neutral-400);
  }}
  .product-filter-empty {{
    margin-top: var(--space-8);
  }}
  .evidence-cell {{
    min-width: 0;
    display: flex;
    align-items: center;
    gap: 4px;
    overflow: hidden;
  }}
  .evidence-badge, .evidence-more {{
    min-height: 20px;
    display: inline-flex;
    align-items: center;
    flex: 0 0 auto;
    border-radius: var(--radius-pill);
    border: 1px solid var(--tone-color, var(--color-neutral-200));
    background: var(--tone-soft, var(--color-neutral-50));
    color: var(--tone-color, var(--color-neutral-600));
    padding: 0 6px;
    font-size: 11px;
    font-weight: 800;
    line-height: 1;
  }}
  .evidence-badge {{
    max-width: 100px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }}
  .evidence-more {{
    --tone-color: var(--color-neutral-400);
    --tone-soft: var(--color-neutral-50);
  }}
  .why-cell {{
    min-width: 0;
    display: flex;
    align-items: center;
    gap: 6px;
  }}
  .why-cell > span:last-child {{
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }}
  .selection-toolbar {{
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--space-8);
    margin: var(--space-8) 0;
    padding: var(--space-8);
    border: 1px solid var(--color-neutral-100);
    border-radius: var(--radius-control);
    background: var(--color-neutral-25);
  }}
  .selection-toolbar > strong {{
    font-size: 13px;
    margin-right: auto;
  }}
  .pagination-bar {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--space-8);
    margin-top: var(--space-8);
  }}
  .page-size-select {{
    min-width: 72px;
    min-height: 32px;
    padding: 0 8px;
  }}
  .quick-preview {{
    padding: var(--space-12);
    position: sticky;
    top: 68px;
    box-shadow: none;
    border-radius: 10px;
    max-height: calc(100vh - 84px);
    overflow: auto;
  }}
  .preview-image {{
    width: 100%;
    aspect-ratio: 1 / 1;
    border: 1px solid var(--color-neutral-100);
    border-radius: 10px;
    object-fit: cover;
    background: var(--color-neutral-50);
  }}
  .preview-title {{
    margin: var(--space-12) 0 var(--space-8);
    font-size: 16px;
    line-height: 1.25;
  }}
  .preview-meta {{
    display: grid;
    gap: 1px;
    margin-top: var(--space-8);
  }}
  .preview-meta-row {{
    display: grid;
    grid-template-columns: 92px minmax(0, 1fr);
    gap: var(--space-8);
    align-items: center;
    min-height: 28px;
    border-bottom: 1px solid var(--color-neutral-100);
    font-size: 13px;
  }}
  .preview-meta-row > span:first-child {{
    color: var(--color-neutral-400);
    font-size: var(--type-caption);
  }}
  .preview-meta-row strong {{
    min-width: 0;
    text-align: right;
    overflow-wrap: anywhere;
  }}
  .preview-meta-row .status-badge {{
    justify-self: end;
  }}
  .preview-divider {{
    height: 1px;
    background: var(--color-neutral-100);
    margin: var(--space-12) 0;
  }}
  .inspector-heading {{
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: var(--space-8);
    margin-top: var(--space-8);
  }}
  .inspector-heading h2 {{ margin: 0; }}
  .inspector-close {{
    min-width: 28px;
    min-height: 28px;
    padding: 0;
  }}
  .inspector-section {{
    display: grid;
    gap: var(--space-8);
    padding: var(--space-10, 10px) 0;
    border-bottom: 1px solid var(--color-neutral-100);
  }}
  .inspector-section h3 {{
    margin: 0;
    color: var(--color-neutral-600);
    font-size: 13px;
    line-height: 1.25;
  }}
  .inspector-body {{
    display: grid;
    gap: var(--space-8);
  }}
  .inspector-status-list {{
    display: grid;
    gap: 4px;
  }}
  .evidence-status {{
    min-height: 26px;
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: center;
    gap: var(--space-8);
    padding: 0 8px;
    border: 1px solid var(--color-neutral-100);
    border-radius: 8px;
    background: var(--color-neutral-25);
    color: var(--color-neutral-500, var(--color-neutral-600));
    font-size: 12px;
  }}
  .evidence-status span {{
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }}
  .evidence-status strong {{
    font-size: 11px;
    font-weight: 800;
  }}
  .evidence-status.is-true {{
    border-color: var(--color-winner);
    background: var(--color-winner-soft);
    color: var(--color-winner);
  }}
  .evidence-status.is-false {{
    color: var(--color-neutral-400);
  }}
  .evidence-status.is-no-data {{
    border-style: dashed;
    color: var(--color-neutral-400);
  }}
  .inspector-metrics {{
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 4px;
  }}
  .inspector-metric {{
    min-width: 0;
    display: grid;
    gap: 2px;
    padding: 6px;
    border: 1px solid var(--color-neutral-100);
    border-radius: 8px;
    background: var(--color-neutral-25);
  }}
  .inspector-metric span {{
    color: var(--color-neutral-400);
    font-size: 11px;
    font-weight: 700;
  }}
  .inspector-metric strong {{
    min-width: 0;
    overflow-wrap: anywhere;
    font-size: 12px;
  }}
  .source-detail-list {{
    display: grid;
    gap: 4px;
  }}
  .source-detail-row {{
    display: grid;
    gap: 2px;
    padding: 7px 8px;
    border: 1px solid var(--color-neutral-100);
    border-radius: 8px;
    background: var(--color-neutral-0);
    color: var(--color-neutral-500, var(--color-neutral-600));
    font-size: 11px;
  }}
  .source-detail-row strong {{
    color: var(--color-neutral-800);
    font-size: 12px;
  }}
  .source-detail-row span {{
    overflow-wrap: anywhere;
  }}
  .seller-thumbnail-strip {{
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 14px 10px;
    align-items: start;
    justify-content: start;
    margin: 2px 0 20px;
  }}
  [data-seller-detail] {{
    min-height: min(720px, calc(100vh - 120px));
    display: grid;
    grid-template-rows: auto auto auto auto minmax(0, 1fr);
    row-gap: 14px;
  }}
  .seller-preview-header h2 {{
    margin: 0;
    font-size: 18px;
    line-height: 1.2;
  }}
  .seller-focus-section {{
    display: grid;
    gap: 5px;
    margin-bottom: 0;
  }}
  .seller-focus-section > span, .seller-preview-section h3 {{
    margin: 0;
    color: var(--color-neutral-400);
    font-size: 11px;
    font-weight: 800;
    letter-spacing: .04em;
    text-transform: uppercase;
  }}
  .seller-focus-tags {{
    display: flex;
    flex-wrap: wrap;
    gap: 5px;
  }}
  .seller-focus-tags strong {{
    min-height: 24px;
    display: inline-flex;
    align-items: center;
    border: 1px solid var(--color-neutral-100);
    border-radius: var(--radius-pill);
    padding: 0 8px;
    background: var(--color-neutral-25);
    color: var(--color-neutral-600);
    font-size: 12px;
    line-height: 1;
  }}
  .seller-preview-section {{
    display: grid;
    gap: 4px;
  }}
  .seller-thumbnail-card {{
    display: grid;
    gap: 6px;
    width: 100%;
    min-width: 0;
    align-self: start;
    color: inherit;
    text-decoration: none;
  }}
  .seller-thumbnail-image {{
    display: block;
    width: 100%;
    aspect-ratio: 1 / 1;
  }}
  .seller-thumbnail-image img {{
    width: 100%;
    height: 100%;
    border-radius: 6px;
    object-fit: contain;
    border: 0;
    background: var(--color-neutral-50);
  }}
  .seller-thumbnail-card:hover .seller-thumbnail-image img {{
    opacity: .88;
  }}
  .seller-thumbnail-meta {{
    display: grid;
    gap: 3px;
    color: var(--color-neutral-500, var(--color-neutral-600));
    font-size: 10px;
    line-height: 1.2;
  }}
  .seller-thumbnail-meta > span {{
    display: flex;
    min-width: 0;
    align-items: baseline;
    justify-content: space-between;
    gap: 4px;
  }}
  .seller-thumbnail-meta strong {{
    min-width: 0;
    color: var(--color-neutral-400);
    font-weight: 700;
  }}
  .seller-thumbnail-meta em {{
    flex: 0 0 auto;
    color: var(--color-neutral-700);
    font-style: normal;
    font-weight: 800;
  }}
  .seller-thumbnail-placeholder {{
    display: block;
    width: 100%;
    aspect-ratio: 1 / 1;
    align-self: start;
    border-radius: 6px;
    background: var(--color-neutral-50);
  }}
  .seller-preview-stats {{
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 10px;
    margin: 6px 0 0;
  }}
  .seller-preview-stat {{
    min-width: 0;
    display: grid;
    gap: 2px;
    padding: 0;
  }}
  .seller-preview-stat strong {{
    display: block;
    margin: 0;
    color: var(--color-neutral-800);
    font-size: 17px;
    font-weight: 800;
    line-height: 1.1;
  }}
  .seller-preview-stat span {{
    display: block;
    color: var(--color-neutral-400);
    font-size: 11px;
    font-weight: 700;
  }}
  .seller-preview-actions {{
    width: 100%;
    margin-top: auto;
    align-self: end;
    display: grid;
    gap: 8px;
  }}
  .seller-preview-cta {{
    width: 100%;
  }}
  .seller-preview-cta-secondary {{
    background: var(--color-neutral-0);
    color: var(--color-neutral-600);
  }}
  .seller-preview-cta-secondary:disabled {{
    width: 100%;
  }}
  .seller-open-link {{
    display: inline-flex;
    width: 28px;
    min-height: 28px;
    align-items: center;
    justify-content: center;
    border-radius: 7px;
    font-size: 16px;
    line-height: 1;
    text-decoration: none;
  }}
  .seller-open-link:hover {{
    background: var(--color-neutral-50);
    text-decoration: none;
  }}
  .inspector-no-data {{
    min-height: 34px;
    display: grid;
    place-items: center;
    border: 1px dashed var(--color-neutral-200);
    border-radius: 8px;
    color: var(--color-neutral-400);
    background: var(--color-neutral-25);
    font-size: 12px;
    font-weight: 700;
  }}
  .evidence-reason-list {{
    display: grid;
    gap: 4px;
    margin: 0;
    padding-left: 18px;
    color: var(--color-neutral-600);
    font-size: 12px;
  }}
  .metric-grid {{
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--space-8);
    margin: var(--space-12) 0;
  }}
  .metric {{
    border: 1px solid var(--color-neutral-100);
    border-radius: var(--radius-control);
    padding: var(--space-8);
    background: var(--color-neutral-25);
  }}
  .metric span {{ display: block; color: var(--color-neutral-400); font-size: var(--type-caption); }}
  .metric strong {{ display: block; margin-top: 2px; }}
  .preview-actions {{
    display: flex;
    gap: var(--space-8);
    margin-top: var(--space-8);
    flex-wrap: wrap;
  }}
  .preview-actions .btn-primary {{
    flex: 1 1 100%;
  }}
  .preview-actions .btn-secondary, .preview-actions .btn-ghost {{
    flex: 1 1 0;
  }}
  .full-evidence-panel {{
    margin-top: var(--space-8);
  }}
  .full-evidence-panel .inspector-section:last-of-type {{
    border-bottom: 0;
  }}
  .secondary-preview-actions {{
    border-top: 1px solid var(--color-neutral-100);
    padding-top: var(--space-8);
  }}
  .idea-card-list, .mover-list {{
    display: grid;
    gap: var(--space-8);
  }}
  .idea-summary-card, .mover-row {{
    background: var(--color-neutral-0);
    border: 1px solid var(--color-neutral-100);
    border-radius: 10px;
    padding: 10px var(--space-12);
  }}
  .idea-summary-card {{
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: var(--space-12);
    align-items: center;
  }}
  .idea-summary-card h3, .mover-row h3 {{
    margin: 0 0 2px;
    font-size: 15px;
    line-height: 1.25;
  }}
  .idea-summary-card p, .mover-row p {{
    margin: 0;
    color: var(--color-neutral-400);
    font-size: var(--type-caption);
  }}
  .idea-summary-metrics {{
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
    justify-content: flex-end;
  }}
  .mover-row {{
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto auto;
    gap: var(--space-12);
    align-items: center;
  }}
  .mover-row > strong {{
    color: var(--color-neutral-800);
    font-size: 13px;
  }}
  .empty-state {{
    display: grid;
    place-items: center;
    min-height: 140px;
    border: 1px dashed var(--color-neutral-200);
    border-radius: var(--radius-card);
    color: var(--color-neutral-400);
    background: var(--color-neutral-25);
    text-align: center;
    padding: var(--space-16);
  }}
  .skeleton {{
    height: 12px;
    border-radius: var(--radius-pill);
    background: linear-gradient(90deg, var(--color-neutral-100), var(--color-neutral-50), var(--color-neutral-100));
    background-size: 220% 100%;
    animation: skeleton-shimmer 1.8s ease-in-out infinite;
  }}
  @media (prefers-reduced-motion: reduce) {{
    .skeleton {{
      animation: none;
    }}
  }}
  .dashboard-grid {{
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: var(--space-8);
  }}
  .home-activity-grid {{
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--space-8);
  }}
  .research-queue-grid {{
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: var(--space-8);
  }}
  .research-queue-grid.minimal-queue-grid {{
    grid-template-columns: minmax(0, 1fr) minmax(260px, 320px);
  }}
  .research-queue-card .section-header {{
    margin-top: 0;
  }}
  .evidence-card-grid {{
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: var(--space-8);
  }}
  .evidence-overview-card {{
    display: grid;
    gap: var(--space-8);
    padding: var(--space-12);
    text-decoration: none;
    color: inherit;
  }}
  .evidence-overview-card:hover {{
    border-color: var(--tone-color, var(--color-neutral-200));
  }}
  .evidence-overview-card h3 {{
    margin: 0;
    font-size: var(--type-card-title);
    line-height: 1.2;
  }}
  .evidence-overview-card .card-metrics {{
    display: flex;
    gap: var(--space-8);
    flex-wrap: wrap;
    color: var(--color-neutral-400);
    font-size: var(--type-caption);
    font-weight: 700;
  }}
  .activity-list {{
    display: grid;
    gap: 4px;
  }}
  .activity-item {{
    min-height: 42px;
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: var(--space-8);
    align-items: center;
    padding: 7px 8px;
    border: 1px solid var(--color-neutral-100);
    border-radius: 8px;
    color: inherit;
    text-decoration: none;
  }}
  .activity-item:hover {{
    background: var(--color-neutral-25);
  }}
  .research-queue-item {{
    grid-template-columns: 48px minmax(0, 1fr) auto;
  }}
  .research-queue-item.is-pinned {{
    border-color: var(--color-focus);
    background: #f3f7ff;
  }}
  .activity-thumbnail {{
    width: 44px;
    height: 44px;
    border-radius: 8px;
    object-fit: cover;
    border: 1px solid var(--color-neutral-100);
    background: var(--color-neutral-50);
  }}
  .activity-copy {{
    min-width: 0;
  }}
  .activity-item strong, .activity-item span {{
    display: block;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }}
  .home-preview-panel {{
    padding: var(--space-12);
    position: sticky;
    top: 68px;
    align-self: start;
  }}
  .home-preview-panel.is-pinned {{
    border-color: var(--color-focus);
  }}
  .home-preview-image {{
    width: 100%;
    aspect-ratio: 4 / 3;
    border: 1px solid var(--color-neutral-100);
    border-radius: 10px;
    object-fit: cover;
    background: var(--color-neutral-50);
    transition: opacity 120ms ease;
  }}
  .compact-health-panel summary {{
    cursor: pointer;
    color: var(--color-neutral-800);
    font-weight: 800;
  }}
  .compact-health-panel .data-quality-list {{
    margin-top: var(--space-8);
  }}
  .data-quality-list {{
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: var(--space-8);
  }}
  .quality-item {{
    border: 1px solid var(--color-neutral-100);
    border-radius: var(--radius-control);
    padding: var(--space-8);
    background: var(--color-neutral-25);
  }}
  .quality-item span {{
    display: block;
    color: var(--color-neutral-400);
    font-size: var(--type-caption);
  }}
  .quality-item strong {{
    display: block;
    margin-top: 2px;
  }}
  .explorer-layout {{
    display: grid;
    grid-template-columns: minmax(0, 1.25fr) minmax(320px, .75fr);
    gap: var(--space-12);
    align-items: start;
  }}
  .detail-panel {{
    position: sticky;
    top: 68px;
  }}
  .secondary-toolbar {{
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--space-8);
    margin-bottom: var(--space-8);
  }}
  .seller-table {{
    min-width: 720px;
  }}
  [data-market-table] {{
    min-width: 820px;
  }}
  .market-caption {{
    display: block;
    margin-top: 2px;
  }}
  .market-detail {{
    margin-top: var(--space-4);
  }}
  .market-detail summary {{
    cursor: pointer;
    color: var(--color-neutral-400);
    font-size: 11px;
    font-weight: 800;
  }}
  [data-market-detail] {{
    min-height: min(680px, calc(100vh - 120px));
    display: grid;
    grid-template-rows: auto auto auto auto auto minmax(0, 1fr);
    row-gap: 14px;
  }}
  .market-preview-header h2 {{
    margin: 0;
    font-size: 18px;
    line-height: 1.2;
  }}
  .market-preview-header .caption {{
    display: block;
    margin-top: 4px;
  }}
  .market-tags-section {{
    display: grid;
    gap: 5px;
  }}
  .market-tags-section > span, .market-preview-section h3 {{
    margin: 0;
    color: var(--color-neutral-400);
    font-size: 11px;
    font-weight: 800;
    letter-spacing: .04em;
    text-transform: uppercase;
  }}
  .market-tags {{
    display: flex;
    flex-wrap: wrap;
    gap: 5px;
  }}
  .market-tags strong {{
    min-height: 24px;
    display: inline-flex;
    align-items: center;
    border: 1px solid var(--color-neutral-100);
    border-radius: var(--radius-pill);
    padding: 0 8px;
    background: var(--color-neutral-25);
    color: var(--color-neutral-600);
    font-size: 12px;
    line-height: 1;
  }}
  .market-preview-section {{
    display: grid;
    gap: 6px;
  }}
  .market-product-grid {{
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    column-gap: 3px;
    row-gap: 14px;
    align-items: start;
    margin-top: 2px;
  }}
  .market-product-card {{
    display: block;
    position: relative;
    width: 100%;
    min-width: 0;
    aspect-ratio: 1 / 1;
    color: inherit;
    text-decoration: none;
  }}
  .market-product-card img {{
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    border: 0;
    border-radius: 6px;
    object-fit: contain;
    background: var(--color-neutral-50);
  }}
  .market-product-card:hover img {{
    opacity: .88;
  }}
  .market-leading-sellers {{
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }}
  .market-leading-sellers span {{
    min-height: 24px;
    display: inline-flex;
    align-items: center;
    border-radius: var(--radius-pill);
    padding: 0 8px;
    background: var(--color-neutral-50);
    color: var(--color-neutral-600);
    font-size: 12px;
    font-weight: 700;
  }}
  .market-preview-stats {{
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 10px;
  }}
  .market-preview-stat {{
    min-width: 0;
    display: grid;
    gap: 2px;
  }}
  .market-preview-stat strong {{
    display: block;
    margin: 0;
    color: var(--color-neutral-800);
    font-size: 17px;
    font-weight: 800;
    line-height: 1.1;
  }}
  .market-preview-stat span {{
    display: block;
    color: var(--color-neutral-400);
    font-size: 11px;
    font-weight: 700;
  }}
  .market-preview-cta {{
    width: 100%;
    margin-top: auto;
    align-self: end;
  }}
  @keyframes skeleton-shimmer {{
    0% {{ background-position: 120% 0; }}
    100% {{ background-position: -120% 0; }}
  }}
  .bar-list {{
    display: grid;
    gap: var(--space-8);
  }}
  .bar-row {{
    display: grid;
    grid-template-columns: 130px minmax(0, 1fr) 44px;
    gap: var(--space-8);
    align-items: center;
  }}
  .bar-track {{
    height: 10px;
    border-radius: var(--radius-pill);
    background: var(--color-neutral-100);
    overflow: hidden;
  }}
  .bar-fill {{
    width: var(--bar-value);
    height: 100%;
    border-radius: inherit;
    background: var(--tone-color, var(--color-stable));
  }}
  .segment-tabs {{
    display: flex;
    gap: var(--space-8);
    flex-wrap: wrap;
    margin-bottom: var(--space-12);
  }}
  .two-column {{
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--space-12);
  }}
  .tone-winner {{ --tone-color: var(--color-winner); --tone-soft: var(--color-winner-soft); }}
  .tone-rising {{ --tone-color: var(--color-rising); --tone-soft: var(--color-rising-soft); }}
  .tone-stable {{ --tone-color: var(--color-stable); --tone-soft: var(--color-stable-soft); }}
  .tone-alert {{ --tone-color: var(--color-alert); --tone-soft: var(--color-alert-soft); }}
  .tone-idea {{ --tone-color: var(--color-idea); --tone-soft: var(--color-idea-soft); }}
  .tone-neutral {{ --tone-color: var(--color-neutral-400); --tone-soft: var(--color-neutral-50); }}
  @media (max-width: 1100px) {{
    .top-shell {{
      position: static;
      grid-template-columns: 1fr;
      align-items: stretch;
    }}
    .primary-nav {{ justify-content: flex-start; overflow-x: auto; }}
    .dataset-strip {{ justify-content: flex-start; overflow-x: auto; }}
    .nav-link {{ justify-content: center; padding: 0 var(--space-8); }}
    .product-workspace {{ grid-template-columns: 1fr; }}
    .quick-preview {{ position: static; }}
    .dashboard-grid, .evidence-card-grid, .home-activity-grid, .research-queue-grid, .explorer-layout {{ grid-template-columns: 1fr 1fr; }}
    .research-queue-grid.minimal-queue-grid {{ grid-template-columns: 1fr; }}
    .home-preview-panel {{ position: static; }}
  }}
  @media (max-width: 760px) {{
    .main {{ padding: var(--space-16); }}
    .kpi-grid, .content-grid, .two-column, .dashboard-grid, .evidence-card-grid, .home-activity-grid, .research-queue-grid, .explorer-layout, .data-quality-list {{ grid-template-columns: 1fr; }}
    .page-header, .toolbar {{ display: grid; }}
    .primary-nav {{ justify-content: flex-start; }}
    .search-input, #idea-search.search-input, #product-search.search-input {{ min-width: 0; width: 100%; }}
    .mover-row, .idea-summary-card {{ grid-template-columns: 1fr; }}
  }}
  </style>
"""
