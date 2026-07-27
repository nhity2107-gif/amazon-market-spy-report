from __future__ import annotations

from html import escape
from urllib.parse import quote

from .theme import theme_styles


V2_NAV_ITEMS = [
    {"key": "morning_brief", "label": "Home", "href": "index.html", "icon": "sun"},
    {"key": "product_explorer", "label": "Product Explorer", "href": "product_explorer.html", "icon": "grid"},
    {"key": "competitor", "label": "Competitor Explorer", "href": "competitor.html", "icon": "store"},
    {"key": "market_explorer", "label": "Market Explorer", "href": "market_explorer.html", "icon": "chart"},
]


def render_app_shell(
    *,
    title: str,
    active_key: str,
    body: str,
    scripts: str = "",
    dataset_info: dict[str, object] | None = None,
) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)} - Amazon Market Spy V2</title>
{theme_styles()}
</head>
<body>
  <div class="app-shell">
    {render_navigation(active_key, dataset_info)}
    <main class="main">
      <div class="page">
{body}
      </div>
    </main>
  </div>
{scripts}
</body>
</html>
"""


def render_navigation(active_key: str, dataset_info: dict[str, object] | None = None) -> str:
    links = []
    for item in V2_NAV_ITEMS:
        active = item["key"] == active_key
        current = ' aria-current="page"' if active else ""
        class_name = "nav-link"
        links.append(
            f"""      <a class="{class_name}" href="{escape(item['href'])}"{current}>
        {inline_icon(item["icon"])}
        <span>{escape(item["label"])}</span>
      </a>"""
        )
    info = dataset_info or {}
    status = str(info.get("status", "No data"))
    generated = str(info.get("generated_at", "Not generated"))
    calibration_html = ""
    if info.get("calibration_report_exists"):
        calibration_status = str(info.get("calibration_status", "Human Review available"))
        calibration_html = f'<a class="utility-link" href="../evidence_human_review_analysis.html">{escape(calibration_status)}</a>'
    return f"""<header class="top-shell">
      <div class="brand">
        <span class="brand-mark" aria-hidden="true">V2</span>
        <span>Amazon Market Spy</span>
      </div>
      <nav class="primary-nav" aria-label="Dashboard V2 primary">
{chr(10).join(links)}
      </nav>
      <div class="dataset-strip" aria-label="Dataset status">
        <span class="dataset-pill">{escape(status)}</span>
        <span class="dataset-generated">Generated {escape(generated)}</span>
        <a class="utility-link" href="#dataset-information">Dataset Information</a>
        {calibration_html}
      </div>
    </header>"""


def page_header(title: str, subtitle: str, action_html: str = "") -> str:
    action = f"\n      <div class=\"control-group\">{action_html}</div>" if action_html else ""
    return f"""    <header class="page-header">
      <div>
        <h1>{escape(title)}</h1>
        <p class="page-subtitle">{escape(subtitle)}</p>
      </div>{action}
    </header>"""


def section_header(title: str, caption: str = "", action_html: str = "") -> str:
    caption_html = f'<p class="muted">{escape(caption)}</p>' if caption else ""
    action = f'<div class="control-group">{action_html}</div>' if action_html else ""
    return f"""    <div class="section-header">
      <div>
        <h2>{escape(title)}</h2>
        {caption_html}
      </div>
      {action}
    </div>"""


def kpi_card(label: str, value: str, caption: str = "", tone: str = "neutral") -> str:
    caption_html = f'<span class="kpi-caption">{escape(caption)}</span>' if caption else ""
    return f"""      <article class="kpi-card tone-{tone_name(tone)}">
        <span class="kpi-label">{escape(label)}</span>
        <strong class="kpi-value">{escape(value)}</strong>
        {caption_html}
      </article>"""


def status_badge(label: str, tone: str = "neutral") -> str:
    return f'<span class="status-badge tone-{tone_name(tone)}">{escape(label)}</span>'


def primary_button(label: str, href: str | None = None) -> str:
    return _button(label, "btn-primary", href)


def secondary_button(label: str, href: str | None = None) -> str:
    return _button(label, "btn-secondary", href)


def ghost_button(label: str, href: str | None = None) -> str:
    return _button(label, "btn-ghost", href)


def dropdown_button(label: str) -> str:
    return f'<button class="btn btn-secondary btn-dropdown" type="button">{escape(label)}</button>'


def search_input(label: str, placeholder: str, name: str = "search") -> str:
    return (
        f'<label class="caption" for="{escape(name)}">{escape(label)}</label>'
        f'<input id="{escape(name)}" class="search-input" type="search" name="{escape(name)}" '
        f'placeholder="{escape(placeholder)}">'
    )


def filter_chip(label: str, tone: str = "neutral") -> str:
    return f'<button class="filter-chip tone-{tone_name(tone)}" type="button">{escape(label)}</button>'


def saved_view_item(
    label: str,
    *,
    icon: str = "dot",
    active: bool = False,
    key: str = "",
    disabled: bool = False,
    title: str = "",
) -> str:
    active_class = " is-active" if active else ""
    current = ' aria-current="true"' if active else ""
    key_attr = f' data-saved-view="{escape(key)}"' if key else ""
    disabled_attr = " disabled" if disabled else ""
    title_attr = f' title="{escape(title)}"' if title else ""
    return f"""<button class="saved-view{active_class}" type="button"{key_attr}{disabled_attr}{title_attr}{current}>
              {small_icon(icon)}
              <span>{escape(label)}</span>
            </button>"""


def compact_filter_row(
    label: str,
    count: int,
    tone: str = "neutral",
    *,
    key: str = "",
    disabled: bool = False,
    title: str = "",
) -> str:
    key_attr = f' data-quick-filter="{escape(key)}"' if key else ""
    disabled_attr = " disabled" if disabled else ""
    title_attr = f' title="{escape(title)}"' if title else ""
    return f"""<button class="filter-row tone-{tone_name(tone)}" type="button"{key_attr}{disabled_attr}{title_attr}>
              <span>{escape(label)}</span>
              <strong>{count}</strong>
            </button>"""


def data_table(headers: list[str], rows: list[list[str]], *, class_name: str = "", caption: str = "") -> str:
    caption_html = f"<caption>{escape(caption)}</caption>" if caption else ""
    header_html = "".join(f"<th scope=\"col\">{escape(header)}</th>" for header in headers)
    body_rows = []
    for row in rows:
        cells = "".join(f"<td>{cell}</td>" for cell in row)
        body_rows.append(f"<tr>{cells}</tr>")
    return f"""    <div class="table-shell {escape(class_name)}">
      <table>
        {caption_html}
        <thead><tr>{header_html}</tr></thead>
        <tbody>
          {''.join(body_rows)}
        </tbody>
      </table>
    </div>"""


def empty_state(title: str, caption: str = "") -> str:
    caption_html = f'<p class="caption">{escape(caption)}</p>' if caption else ""
    return f"""    <div class="empty-state">
      <div>
        <strong>{escape(title)}</strong>
        {caption_html}
      </div>
    </div>"""


def loading_skeleton(lines: int = 3) -> str:
    return "\n".join('<div class="skeleton" aria-hidden="true"></div>' for _ in range(lines))


def quick_preview_shell(product: dict[str, object]) -> str:
    title = str(product.get("title", "Preview product"))
    seller = str(product.get("seller", "Seller"))
    idea = str(product.get("idea", "Idea"))
    product_type = str(product.get("product_type", "Product Type"))
    tone = tone_name(str(product.get("tone", "idea")))
    image = product_image_src(product, tone)
    return f"""      <aside class="quick-preview evidence-inspector" aria-label="Evidence Inspector Quick Preview" data-quick-preview data-evidence-inspector>
        <img class="preview-image" data-preview-image src="{image}" alt="{escape(title)} product image">
        <div class="inspector-heading">
          <h2>Evidence Inspector</h2>
          <button class="btn btn-ghost inspector-close" type="button" data-inspector-close aria-label="Close inspector details">x</button>
        </div>
        <h3 class="preview-title" data-preview-title>{escape(title)}</h3>
        <section class="inspector-section" data-inspector-product-summary>
          <h3>Product Summary</h3>
          <div class="preview-meta">
            {preview_meta_row("Why It Matters", "-", "preview-why")}
            {preview_meta_row("Momentum", "-", "preview-momentum")}
            {preview_meta_row("Market Proof", "-", "preview-proof")}
          </div>
        </section>
        <div class="preview-actions">
          <button class="btn btn-primary" type="button" data-preview-action="amazon">Open Amazon</button>
        </div>
        <details class="full-evidence-panel" data-full-evidence>
          <summary>View Full Evidence</summary>
          <section class="inspector-section" data-inspector-compact-metadata>
            <h3>Metadata</h3>
            <div class="preview-meta">
              {preview_meta_row("Seller", seller, "preview-seller")}
              {preview_meta_row("Idea", idea, "preview-idea")}
              {preview_meta_row("Category", product_type, "preview-type")}
              {preview_meta_row("Price", str(product.get("price", "-")), "preview-price")}
              {preview_meta_row("Reviews", str(product.get("reviews", "-")), "preview-reviews")}
              {preview_meta_row("BSR", str(product.get("bsr", "-")), "preview-bsr")}
              {preview_meta_row("Winner Score", str(product.get("score", "-")), "preview-score", tone)}
              {preview_meta_row("Growth", str(product.get("growth", "-")), "preview-growth", "rising")}
              {preview_meta_row("ASIN", str(product.get("asin", "-")), "preview-asin")}
              {preview_meta_row("Source", str(product.get("source", "-")), "preview-source")}
            </div>
          </section>
          <section class="inspector-section" data-inspector-evidence-summary>
            <h3>Evidence Summary</h3>
            <div class="inspector-body" data-inspector-summary-body>No data</div>
          </section>
          <section class="inspector-section" data-inspector-seller>
            <h3>Seller Intelligence</h3>
            <div class="inspector-body" data-inspector-seller-body>No data</div>
          </section>
          <section class="inspector-section" data-inspector-best-seller>
            <h3>Best Seller Intelligence</h3>
            <div class="inspector-body" data-inspector-best-seller-body>No data</div>
          </section>
          <section class="inspector-section" data-inspector-new-release>
            <h3>New Release Intelligence</h3>
            <div class="inspector-body" data-inspector-new-release-body>No data</div>
          </section>
          <section class="inspector-section" data-inspector-bsr>
            <h3>BSR Evidence</h3>
            <div class="inspector-body" data-inspector-bsr-body>No data</div>
          </section>
          <section class="inspector-section" data-inspector-reasons>
            <h3>Evidence Reasons</h3>
            <div class="inspector-body" data-inspector-reasons-body>No data</div>
          </section>
          <section class="inspector-section" data-inspector-source-details>
            <h3>Source Details</h3>
            <div class="inspector-body" data-inspector-source-details-body>No data</div>
          </section>
          <section class="inspector-section" data-inspector-metadata>
            <h3>Product Metadata</h3>
            <div class="inspector-body" data-inspector-metadata-body>No data</div>
          </section>
          <div class="preview-actions secondary-preview-actions">
          <button class="btn btn-secondary" type="button" data-preview-action="seller">Open Seller</button>
          <button class="btn btn-secondary" type="button" data-preview-action="source">Open Source</button>
          <button class="btn btn-ghost" type="button" data-preview-action="copy-asin">Copy ASIN</button>
          <button class="btn btn-ghost" type="button" data-preview-action="copy-url">Copy URL</button>
          </div>
        </details>
      </aside>"""


def product_image_src(product: dict[str, object], tone: str = "idea") -> str:
    image_url = str(product.get("image_url", "") or product.get("image", "") or "").strip()
    if image_url:
        return image_url
    return mock_product_image(str(product.get("image_label", "P")), tone)


def compact_content_card(title: str, meta: str, signal: str, tone: str = "neutral") -> str:
    return f"""      <article class="compact-card">
        <div>
          <h3>{escape(title)}</h3>
          <p>{escape(meta)}</p>
        </div>
        {status_badge(signal, tone)}
      </article>"""


def metric(label: str, value: str, data_attr: str = "") -> str:
    attr = f' data-{data_attr}' if data_attr else ""
    return f"""<div class="metric">
            <span>{escape(label)}</span>
            <strong{attr}>{escape(value)}</strong>
          </div>"""


def preview_meta_row(label: str, value: str, data_attr: str = "", tone: str = "neutral") -> str:
    attr = f' data-{data_attr}' if data_attr else ""
    value_html = (
        f'<span class="status-badge tone-{tone_name(tone)}"{attr}>{escape(value)}</span>'
        if tone_name(tone) != "neutral"
        else f"<strong{attr}>{escape(value)}</strong>"
    )
    return f"""<div class="preview-meta-row">
            <span>{escape(label)}</span>
            {value_html}
          </div>"""


def bar_list(items: list[dict[str, object]]) -> str:
    rows = []
    max_value = max([int(item.get("value", 0) or 0) for item in items] or [1])
    for item in items:
        value = int(item.get("value", 0) or 0)
        width = max(4, round((value / max_value) * 100))
        tone = tone_name(str(item.get("tone", "stable")))
        rows.append(
            f"""        <div class="bar-row tone-{tone}">
          <strong>{escape(str(item.get("label", "")))}</strong>
          <div class="bar-track" aria-hidden="true"><div class="bar-fill" style="--bar-value: {width}%"></div></div>
          <span class="caption">{escape(str(value))}</span>
        </div>"""
        )
    return f"""      <div class="bar-list">
{chr(10).join(rows)}
      </div>"""


def mock_product_image(label: str, tone: str = "idea") -> str:
    tone = tone_name(tone)
    color_map = {
        "winner": ("#e8f6ee", "#16803c"),
        "rising": ("#fff3e3", "#b25a00"),
        "stable": ("#eaf1ff", "#1f5fbf"),
        "alert": ("#fdecec", "#c9342f"),
        "idea": ("#f2edff", "#6d3acb"),
        "neutral": ("#f5f7fa", "#3f4b5b"),
    }
    background, foreground = color_map.get(tone, color_map["idea"])
    safe_label = escape(label[:3].upper() or "P")
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="320" height="240" viewBox="0 0 320 240">'
        f'<rect width="320" height="240" rx="24" fill="{background}"/>'
        f'<circle cx="160" cy="98" r="42" fill="{foreground}" opacity=".16"/>'
        f'<text x="160" y="148" text-anchor="middle" font-family="Arial, sans-serif" '
        f'font-size="42" font-weight="700" fill="{foreground}">{safe_label}</text>'
        "</svg>"
    )
    return "data:image/svg+xml;charset=utf-8," + quote(svg)


def inline_icon(name: str) -> str:
    icons = {
        "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4 12H2M22 12h-2M5 5l1.4 1.4M17.6 17.6L19 19M19 5l-1.4 1.4M6.4 17.6L5 19"/>',
        "idea": '<path d="M9 18h6"/><path d="M10 22h4"/><path d="M8.5 14.5A6 6 0 1 1 15.5 14.5c-.9.6-1.5 1.7-1.5 2.5h-4c0-.8-.6-1.9-1.5-2.5Z"/>',
        "grid": '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
        "store": '<path d="M4 10h16l-1.5-6h-13L4 10Z"/><path d="M6 10v10h12V10"/><path d="M9 20v-6h6v6"/>',
        "chart": '<path d="M4 19V5"/><path d="M4 19h16"/><path d="M8 16v-5"/><path d="M12 16V8"/><path d="M16 16v-9"/>',
    }
    path = icons.get(name, icons["grid"])
    return f'<svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{path}</svg>'


def small_icon(name: str) -> str:
    icons = {
        "star": '<path d="m12 3 2.7 5.5 6 .9-4.4 4.2 1 6-5.3-2.8-5.3 2.8 1-6-4.4-4.2 6-.9L12 3Z"/>',
        "trend": '<path d="m4 15 5-5 4 4 7-8"/><path d="M15 6h5v5"/>',
        "low": '<path d="M5 12h14"/><path d="M12 5v14"/>',
        "gift": '<path d="M20 12v8H4v-8"/><path d="M2 8h20v4H2z"/><path d="M12 8v12"/><path d="M12 8H8.5A2.5 2.5 0 1 1 12 5.5V8Z"/><path d="M12 8h3.5A2.5 2.5 0 1 0 12 5.5V8Z"/>',
        "mug": '<path d="M5 8h10v7a4 4 0 0 1-4 4H9a4 4 0 0 1-4-4V8Z"/><path d="M15 10h2a2.5 2.5 0 0 1 0 5h-2"/>',
        "sign": '<path d="M5 7h14v10H5z"/><path d="M8 7V4"/><path d="M16 7V4"/>',
        "person": '<path d="M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z"/><path d="M4 21a8 8 0 0 1 16 0"/>',
        "calendar": '<path d="M7 3v4M17 3v4M4 9h16M5 5h14v16H5z"/>',
        "dot": '<circle cx="12" cy="12" r="4"/>',
    }
    path = icons.get(name, icons["dot"])
    return f'<svg class="small-icon" aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">{path}</svg>'


def _button(label: str, class_name: str, href: str | None = None) -> str:
    classes = f"btn {class_name}"
    if href:
        return f'<a class="{classes}" href="{escape(href)}">{escape(label)}</a>'
    return f'<button class="{classes}" type="button">{escape(label)}</button>'


def tone_name(tone: str) -> str:
    normalized = (tone or "neutral").strip().lower().replace("_", "-")
    return normalized if normalized in {"winner", "rising", "stable", "alert", "idea", "neutral"} else "neutral"
