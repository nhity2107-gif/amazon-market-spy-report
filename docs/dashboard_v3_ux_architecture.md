# Dashboard V3 Phase 1 UX Architecture

Status: Draft for review
Phase: 1 - UX architecture only
Implementation rule: Do not build production UI until this architecture is reviewed and approved.

## Scope

Dashboard V3 is a new UX layer over the existing Amazon Market Spy reporting artifacts. Phase 1 defines the user workflows, route architecture, page responsibilities, state model, and data boundaries. It does not change analytics, crawler behavior, parser behavior, evidence rules, thresholds, datasets, generated CSV schemas, or performance-sensitive generation paths.

## Non-Goals

- No analytics changes.
- No crawler, parser, Playwright, BSR extraction, detail cache, POD classifier, niche classifier, evidence engine, threshold, or scoring changes.
- No changes to existing output CSV schemas.
- No changes to V1 focused reports or Dashboard V2 generation.
- No production Dashboard V3 HTML, CSS, or JavaScript implementation in Phase 1.
- No new product ranking logic, opportunity scoring, decision scoring, or evidence scoring.

## Roadmap Alignment

Phase 1 establishes the architecture before UI work:

1. Define researcher workflows and information architecture.
2. Define V3 routes and page responsibilities.
3. Define allowed data inputs and adapter boundaries.
4. Define interaction/state contracts for the future UI.
5. Define review gates and acceptance criteria for Phase 2.

Later phases should only start after approval:

- Phase 2: Low-risk prototype shell using fixture data or mock rendering only.
- Phase 3: Production static generator using existing artifacts through a V3 adapter.
- Phase 4: Optional publication/migration path after V3 parity review.
- Phase 5: Usability polish and performance validation without changing analytics.

## Existing System Boundary

V3 should sit beside the existing systems:

- V1 focused report generation remains in `amazon_market_spy/artifacts.py`.
- Dashboard V2 remains in `amazon_market_spy/dashboard_v2`.
- Existing scan/trend output generation remains owned by `amazon_market_spy/cli.py` and `amazon_market_spy/reporting.py`.
- V3 may read existing artifacts from `output/`, but must not require new analytics fields.

The proposed future package boundary is:

```text
amazon_market_spy/dashboard_v3/
  __init__.py
  generator.py
  pages.py
  components.py
  theme.py
  services/
    dashboard_service.py
```

This package should not be created as production UI during Phase 1. It is listed here only to document the intended ownership boundary for later phases.

## UX Principle

Dashboard V3 should be a research operations workspace, not a marketing dashboard. The first screen should help the product researcher decide what to inspect today, move quickly into evidence, and preserve trust by showing why each product appears without inventing new analytics.

Primary UX priorities:

- Fast triage of the daily research queue.
- Evidence-first product validation.
- Clear distinction between true, false, missing, and no-data evidence states.
- Drilldown without losing list context.
- Stable URLs for shared views and review workflows.
- Dense, scannable layouts for repeated daily use.

## Primary Users

Product researcher:

- Opens the dashboard daily.
- Needs a short queue of products to inspect.
- Compares product evidence, source movement, seller context, and BSR proof.

Competitor analyst:

- Reviews seller activity.
- Looks for launches, new pushes, and repeated source movement.
- Needs seller-level summaries that link back to product evidence.

Market planner:

- Reviews ideas, product types, recipients, occasions, themes, and categories.
- Needs market distribution and breakout signals without changing the underlying scoring model.

## Core Workflows

### Daily Triage

Goal: identify what to inspect first today.

Entry route: `v3/index.html`

Flow:

1. Review compact daily queue.
2. Filter by evidence family or source family.
3. Open a product in the evidence drawer.
4. Continue to Product Explorer with the same filters preserved in the URL.

### Product Validation

Goal: decide whether a product is worth deeper research.

Entry route: `v3/product_explorer.html`

Flow:

1. Start from a preset or query string.
2. Scan minimal columns first.
3. Open the evidence drawer.
4. Inspect source details, BSR detail, product links, and data quality.
5. Open Amazon or copy/share the filtered dashboard URL.

### Idea Investigation

Goal: understand whether an idea cluster has enough validation.

Entry route: `v3/idea_explorer.html`

Flow:

1. Select dimension: recipient, occasion, theme, product type, or category.
2. Sort by explicit evidence counts and product count.
3. Inspect representative products.
4. Jump into Product Explorer filtered to that idea context.

### Competitor Review

Goal: review seller movement and launches.

Entry route: `v3/competitor_explorer.html`

Flow:

1. Review sellers by activity.
2. Filter to new pushes, movers, or leader evidence.
3. Inspect seller product set.
4. Jump to Product Explorer filtered by seller and evidence family.

### Market Scan

Goal: compare market segments and find active pockets.

Entry route: `v3/market_explorer.html`

Flow:

1. Group products by category, product type, recipient, occasion, or theme.
2. Compare product count, seller count, evidence count, and BSR coverage.
3. Open segment detail.
4. Jump to Product Explorer with matching filters.

### Data Confidence Review

Goal: understand whether today's dataset is complete enough for research.

Entry route: `v3/data_health.html`

Flow:

1. Review source coverage, marketplace coverage, product count, and generated timestamp.
2. Review missing data counts and no-data evidence states.
3. Open related source or product lists.

## Route Architecture

Phase 1 target route map:

| Route | Working Name | Responsibility |
| --- | --- | --- |
| `v3/index.html` | Command Center | Daily queue, evidence pulse, data health summary, quick jumps |
| `v3/product_explorer.html` | Product Explorer | Primary product search, filter, sort, compare, evidence drawer |
| `v3/idea_explorer.html` | Idea Explorer | Idea dimensions and representative products |
| `v3/competitor_explorer.html` | Competitor Explorer | Seller activity and seller-to-product drilldown |
| `v3/market_explorer.html` | Market Explorer | Segment distribution and movement by existing fields |
| `v3/data_health.html` | Data Health | Dataset status, coverage, missing data, calibration links |

Route constraints:

- Routes must be static-file friendly.
- Query strings must carry state for shareable views.
- V3 routes must not replace existing V1 or V2 routes during Phase 1.
- Publication wiring is out of scope until V3 is approved.

## Global Navigation

Navigation should support a daily research loop:

1. Command Center
2. Products
3. Ideas
4. Competitors
5. Market
6. Data Health

The active route must be visually clear. Dataset status should be visible from every route, using existing metadata only.

## Page Architecture

### Command Center

Purpose: daily triage.

Primary regions:

- Header with generated date, dataset status, and source coverage.
- Research queue with deduped representative products.
- Evidence pulse with counts by existing evidence family.
- Market activity summary.
- Competitor activity summary.
- Data health strip.

Allowed inputs:

- Existing products from the V3 adapter.
- Existing evidence fields.
- Existing dataset metadata.

Forbidden behavior:

- No new scoring.
- No hidden threshold changes.
- No custom "priority" calculation beyond sorting by existing fields.

### Product Explorer

Purpose: primary working surface.

Primary regions:

- Filter rail.
- Toolbar with search, sort, density, columns, and reset.
- Results table with minimal default columns.
- Evidence drawer for the selected product.
- Optional comparison tray in later phases.

Default visible columns:

- Product
- Why it matters
- Momentum
- Proof
- Open

Optional columns:

- Image
- Seller
- Product type
- Idea
- Evidence count
- Legacy score
- Reviews
- Price
- Source

Evidence drawer sections:

- Product summary.
- Source evidence by family.
- BSR proof.
- POD relevance.
- Data quality and missing fields.
- External links.

### Idea Explorer

Purpose: inspect idea contexts without mixing entity types.

Dimensions:

- Recipient
- Occasion
- Theme
- Product type
- Category

Rows should be derived from normalized product records and existing niche/category fields. Legacy niche intelligence values may be shown as supporting context only.

### Competitor Explorer

Purpose: review sellers and their product activity.

Seller rows should summarize:

- Product count.
- Seller leader count.
- Seller mover count.
- Seller new push count.
- Strong BSR count.
- Latest observed activity when available.

The seller detail panel should list representative products and link into Product Explorer.

### Market Explorer

Purpose: scan segment distribution and movement.

Supported grouping modes:

- Category
- Product type
- Recipient
- Occasion
- Theme

Segment metrics must use existing product/evidence fields:

- Product count.
- Seller count.
- Evidence counts.
- Median sub-BSR when present.
- Missing BSR count.

### Data Health

Purpose: make data confidence explicit.

Sections:

- Dataset summary.
- Source family coverage.
- Marketplace coverage.
- Products with missing title/image/BSR.
- Evidence no-data counts.
- Calibration status and links when existing calibration artifacts are present.

## Data Contract

V3 should consume a normalized presentation model built from existing artifacts. The adapter may normalize names and coerce types, but must not create new analytics semantics.

Allowed input artifacts:

- `priority_board.csv`
- `lark_trend_alerts.csv`
- `latest_products.csv`
- `historical_comparison.csv`
- `seller_intelligence.csv`
- `niche_intelligence.csv`
- `product_trends.csv`
- `rank_audit.csv`
- `evidence_human_review_summary.csv`

Optional future input:

- `dashboard_v3.json`, if generated explicitly from the same existing artifacts.

Required top-level model:

```text
{
  "dataset_info": object,
  "products": list,
  "ideas": list,
  "competitors": list,
  "market": object,
  "data_health": object
}
```

Product record groups:

- Identity: `id`, `asin`, `title`, `seller`, `seller_url`, `product_url`, `image_url`.
- Classification: `product_type`, `recipient`, `occasion`, `theme`, `idea`, `category`.
- Existing signals: legacy flags, evidence flags, evidence labels, evidence count.
- Source context: source details grouped by seller, best seller, new release, BSR.
- BSR context: primary BSR, subcategory BSR, parse method/confidence when available.
- Quality context: missing fields, no-data states, generated date.

Data normalization rules:

- Empty string, missing, false, and no-data must remain distinguishable where evidence fields support it.
- Numeric strings may be coerced for sorting/filtering.
- Source-family detail should be preserved for drilldown.
- Existing field names should remain traceable in adapter tests.

## State Contract

V3 should use URL query state for reproducible research views.

Common query parameters:

| Parameter | Applies To | Meaning |
| --- | --- | --- |
| `q` | all explorer pages | Text search |
| `preset` | product, competitor, market | Named view |
| `seller` | product, competitor | Seller filter |
| `product_type` | product, idea, market | Product type filter |
| `recipient` | product, idea, market | Recipient filter |
| `occasion` | product, idea, market | Occasion filter |
| `theme` | product, idea, market | Theme filter |
| `category` | product, market | Category filter |
| `evidence` | product | Evidence key filter |
| `family` | product, market | Source/evidence family |
| `sort` | explorer pages | Sort key |
| `dir` | explorer pages | Sort direction |
| `selected` | explorer pages | Selected product, seller, idea, or segment id |

State rules:

- Query state should initialize the page.
- UI changes should update the URL without full reload when possible.
- Deep links from Command Center, Idea Explorer, Competitor Explorer, and Market Explorer should resolve into Product Explorer filters.

## Component Architecture

Future UI components should be organized by responsibility:

- App shell: global navigation, dataset strip, page container.
- Page header: title, subtitle, route actions.
- Filter rail: presets, quick filters, advanced filters.
- Results table: dense product/seller/segment rows.
- Evidence drawer: selected record detail without leaving context.
- Metric strip: compact KPI and coverage cards.
- Empty state: missing data or no results.
- Data health banner: warnings and coverage summary.

Component constraints:

- Components should render from already-normalized presentation data.
- Components should not read CSVs directly.
- Components should not compute new analytics.
- Components should keep display logic separate from data adapter logic.

## Accessibility And Usability Requirements

- Keyboard navigation must support search focus, row selection, drawer close, and pagination.
- Tables must use semantic headers.
- Active navigation must use `aria-current`.
- Filter controls must have labels.
- Empty, error, and no-data states must be explicit.
- Text must fit in compact table and drawer layouts at desktop and mobile widths.
- Dense operational layout is preferred over marketing-style cards.

## Performance Boundary

Phase 1 does not change performance. Later implementation must preserve performance by design:

- Product Explorer should use a lightweight index payload.
- Heavy per-product detail can be lazy-loaded from deterministic static chunks.
- Filtering and sorting should work from the index before detail chunks load.
- Static output must remain browser-friendly for large datasets.
- No extra network calls are required for local static reports.

## Testing Strategy For Later Phases

Architecture approval should precede code tests. When implementation begins, tests should cover:

- V3 service loads existing CSV artifacts without mutating rows.
- V3 schema validation distinguishes missing, false, and no-data.
- Routes generate without importing mock data at runtime.
- Product index excludes drawer-only detail payload.
- Detail chunks are deterministic and stale chunks are cleaned.
- Deep-link query state initializes filters, sort, and selected records.
- V1 and V2 generation remain unchanged.

## Review Gates

Phase 1 review must approve:

- Route map.
- Core workflows.
- Data contract.
- Query-state contract.
- Component boundaries.
- Non-goals and forbidden changes.

Implementation may not proceed to production UI until these are approved.

## Open Questions

1. Should V3 include `data_health.html` as a top-level route in Phase 2, or keep data health as a global drawer until the first production pass?
2. Should Product Explorer keep V2's separate detail chunk model, or move to grouped chunk files by page/bucket for fewer generated files?
3. Should V3 use `v3/competitor_explorer.html` for clarity, or preserve `v3/competitor.html` for URL familiarity?
4. Should publication include V3 as an opt-in preview path before it replaces any existing report entrypoint?
