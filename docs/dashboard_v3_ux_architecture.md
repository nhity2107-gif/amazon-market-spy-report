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

### Idea Context Data

Purpose: retain product-derived idea dimensions for Product Explorer filters and future grouping without a standalone route.

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
- Deep links from Command Center, Competitor Explorer, and Market Explorer should resolve into Product Explorer filters.

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

## Dashboard V2 Implementation Review

Review date: 2026-07-24

Inspected implementation:

- `amazon_market_spy/dashboard_v2/generator.py`
- `amazon_market_spy/dashboard_v2/pages.py`
- `amazon_market_spy/dashboard_v2/components.py`
- `amazon_market_spy/dashboard_v2/theme.py`
- `amazon_market_spy/dashboard_v2/services/dashboard_service.py`
- `amazon_market_spy/cli.py`
- `tests/test_dashboard_v2.py`
- V2 preservation coverage in `tests/test_evidence_calibration.py` and `tests/test_evidence_review_analysis.py`

Focused V2 test status during review: `python -m pytest tests/test_dashboard_v2.py -q` passed with 51 tests.

### V2 Components To Reuse Unchanged

These behaviors are compatible with V3 and should be preserved exactly unless a later approved design change requires otherwise:

- Existing artifact inputs and CSV schema reads from `priority_board.csv`, `lark_trend_alerts.csv`, `latest_products.csv`, `historical_comparison.csv`, `seller_intelligence.csv`, `niche_intelligence.csv`, `product_trends.csv`, and `evidence_human_review_summary.csv`.
- Evidence boolean field names, evidence family names, and the distinction between `true`, `false`, missing, and `no_data`.
- Deterministic product detail chunk concept for Product Explorer.
- Stale detail chunk cleanup before writing a new generated dashboard.
- Lightweight Product Explorer index payload with drawer-only fields excluded.
- Script-tag detail loading for local static-file compatibility instead of `fetch()` or `XMLHttpRequest`.
- Existing accessibility contracts that already work in V2: semantic table headers, `aria-current`, labeled controls, keyboard row navigation, and explicit empty states.
- Formatting/parsing helpers whose behavior is already tested, including ASIN grouping, numeric coercion, missing-value display, source detail grouping, and evidence-state generation.

### V2 Components To Adapt

These V2 pieces are useful but need V3-specific wrappers or renamed contracts:

- `DashboardService` should become a V3 adapter/service that emits the required V3 top-level model: `dataset_info`, `products`, `ideas`, `competitors`, `market`, and `data_health`.
- `V2_PAGE_ROUTES` should become a V3 route map with six canonical routes, including `data_health.html`.
- The app shell and global navigation should be adapted for V3 labels, `v3/` routes, and a V3 dataset strip while preserving V2's static-file-friendly structure.
- Product Explorer index/detail field lists should be adapted into an explicit V3 data contract. Detail-only fields must remain outside the index.
- Product Explorer URL state should be adapted to accept V3 canonical names while preserving V2 aliases.
- Product Explorer evidence drawer behavior should be adapted from the V2 quick preview/evidence inspector, but renamed around the V3 "evidence drawer" concept.
- Idea, competitor, and market aggregation helpers should be adapted to the V3 model and route responsibilities. Their current summaries are useful, but V3 needs the full listed dimensions and data-health metrics.
- Theme tokens and compact table styling can seed V3, but V3 should use its own module so V2 styling remains frozen.
- CLI integration should be additive through a new V3 command or explicit preview path. Existing V2 CLI behavior must not change.

### V2 Components To Replace

These V2 pieces should not be carried forward as-is:

- `mock_data.py` must remain test/demo-only and must not be imported by runtime V3 generation.
- V2 page renderer names and page copy should be replaced with V3 page responsibilities: Command Center, Product Explorer, Competitor Explorer, Market Explorer, and Data Health.
- V2 route `competitor.html` should not be the only V3 competitor route. V3 should use `competitor_explorer.html` canonically and may generate a compatibility alias only if review approves it.
- V2's `market` service model derived mainly from `niche_intelligence.csv` is too narrow for V3 Market Explorer and should be replaced by product-derived grouping data.
- V2's combined inline product interaction script should be split or generated through smaller V3 responsibilities if that can be done without introducing a build system.
- V2's "score" oriented display labels should be treated as legacy compatibility fields only. V3 must not add Decision Score, Opportunity Score, AI summaries, recommendation algorithms, or new ranking logic.

### Routes And Generated Files Affected

V3 implementation should add files beside V2, not modify V2 outputs.

Expected package additions:

```text
amazon_market_spy/dashboard_v3/
  __init__.py
  generator.py
  pages.py
  components.py
  theme.py
  services/
    __init__.py
    dashboard_service.py
```

Expected generated output under a V3 output directory, for example `output/v3/`:

```text
index.html
product_explorer.html
competitor_explorer.html
market_explorer.html
data_health.html
product_explorer_details/*.js
```

Possible compatibility output, if approved:

```text
competitor.html
```

Affected integration files in later phases:

- `amazon_market_spy/cli.py`, only for an additive V3 generation command or preview flag.
- Tests under `tests/test_dashboard_v3.py`, plus existing V1/V2 regression tests.
- Publication wiring only after V3 parity review and explicit approval.

Files that must remain unaffected by V3 work:

- `amazon_market_spy/artifacts.py`
- crawler, parser, Playwright scraping, BSR extraction, POD classifier, niche classifier, evidence engine, threshold, and analytics modules
- generated CSV schemas and datasets
- Dashboard V2 package and V2 generated output

### URL-State And Deep-Link Compatibility Risks

The V3 draft state contract is close to V2 but does not yet preserve every existing query name. V2 Product Explorer currently supports:

- `q`
- `preset`
- `view`
- `type`
- `recipient`
- `theme`
- `occasion`
- `seller`
- `score_min`, `score_max`
- `growth_min`, `growth_max`
- `reviews_min`, `reviews_max`
- `price_min`, `price_max`
- `seller_evidence`
- `best_seller_evidence`
- `new_release_evidence`
- `supporting_evidence`
- `quick`
- `sort`
- `direction`
- `page`
- `page_size`
- `focus`

V3's proposed canonical contract uses `product_type`, `family`, `evidence`, `dir`, and `selected`, which creates compatibility risk with V2 links that use `type`, family-specific evidence parameters, `direction`, and `focus`.

V3 should handle compatibility as follows:

- Accept `type` as an alias for `product_type`.
- Accept `direction` as an alias for `dir`.
- Accept `focus` as an alias for `selected`.
- Continue accepting V2 evidence parameters: `seller_evidence`, `best_seller_evidence`, `new_release_evidence`, and `supporting_evidence`.
- Preserve repeated query parameters for multi-select filters.
- Preserve `page` and `page_size` if pagination remains part of Product Explorer.
- Preserve `view` and `quick` only if V3 keeps saved views or quick filters; otherwise ignore them harmlessly while retaining `preset`, search, category, seller, sort, and selected product.
- Generate V3 deep links with canonical names, but keep alias parsing so old shared links continue to initialize correctly.
- If V3 changes `competitor.html` to `competitor_explorer.html`, either produce a static compatibility alias or document that V2 route compatibility stops at the `/v2/` boundary.

### Lazy-Loading And Performance Risks

V2 has the correct performance direction: an inline product index plus per-product detail chunks. V3 must preserve this boundary.

Risks to watch:

- Adding source details, evidence reasons, BSR detail, or data-quality detail to the product index would inflate `product_explorer.html` and slow filtering.
- Grouping all details into one large JSON payload would undo lazy loading.
- Generating one chunk per product may create many files for large datasets. Keep the V2 approach for first V3 implementation because it is tested and static-file friendly, then measure before considering bucketed chunks.
- Browser-local reports cannot rely on `fetch()` due local file restrictions. Script-tag chunk loading should remain the default unless V3 introduces a served mode.
- Product detail hover preloading should remain delayed and bounded; eager detail loading would regress large-dashboard performance.
- Data Health and Market pages should use aggregated payloads, not embed all drawer detail records.
- Generated stale chunks must be cleaned for V3 independently of V2.

### Test Coverage To Preserve

V3 work must keep existing V2 tests passing and add analogous V3 tests for:

- generation of all canonical V3 pages without touching V2 output
- additive CLI behavior for V3, if a CLI command is added
- runtime code does not import `mock_data.py`
- V3 service loads existing CSV artifacts and validates the V3 top-level model
- missing CSV data and corrupted `dashboard.json` produce friendly static error pages
- false, missing, and `no_data` evidence states remain distinct
- Product Explorer index excludes drawer-only detail fields
- detail chunks are deterministic, preserve source details, and clean stale V3 chunks
- lazy detail loader uses script-tag cache behavior and does not use `fetch()` or `XMLHttpRequest`
- URL state initializes from both V3 canonical params and V2 aliases
- Command Center, Competitor Explorer, and Market Explorer generate Product Explorer deep links that initialize filters and selected records
- Product Explorer filters and sorting operate from the index before detail chunks load
- no Decision Score, Opportunity Score, AI summaries, recommendations, or new scoring labels are introduced
- V1 focused reports and Dashboard V2 generation remain valid

## V3 Implementation Roadmap

### Task 1 - V3 Adapter Contract

Objective: create a V3 read-only adapter/service that normalizes existing artifacts into the V3 top-level model without generating production UI.

Files likely to change:

- `amazon_market_spy/dashboard_v3/__init__.py`
- `amazon_market_spy/dashboard_v3/services/__init__.py`
- `amazon_market_spy/dashboard_v3/services/dashboard_service.py`
- `tests/test_dashboard_v3.py`

Acceptance criteria:

- Loads the current fixture CSV artifacts.
- Emits `dataset_info`, `products`, `ideas`, `competitors`, `market`, and `data_health`.
- Preserves source field traceability and existing evidence semantics.
- Distinguishes missing, false, and `no_data`.
- Does not import V2 mock data at runtime.

Tests required:

- V3 service schema validation.
- CSV fixture load.
- false/missing/no-data evidence-state tests.
- explicit no-new-score assertions.
- existing V1/V2 regression tests remain green.

Production risks:

- Accidentally changing data semantics while renaming fields.
- Copying V2 score-adjacent fields into V3 as if they were new decision logic.

Explicit items that must not change:

- crawler, parser, analytics, evidence formulas, thresholds, CSV schemas, datasets, classification logic, V1 generation, and V2 generation.

### Task 2 - V3 Product Index And Detail Chunk Writer

Objective: define and test V3 Product Explorer index records and lazy detail chunks before building the full page.

Files likely to change:

- `amazon_market_spy/dashboard_v3/pages.py`
- `amazon_market_spy/dashboard_v3/generator.py`
- `tests/test_dashboard_v3.py`

Acceptance criteria:

- Product index contains only list/filter/sort fields.
- Evidence drawer fields are written to deterministic `product_explorer_details/*.js` chunks.
- Stale V3 detail chunks are cleaned.
- Chunk IDs remain stable by ASIN or fallback id.

Tests required:

- index excludes source details, evidence states, evidence reasons, and external URL detail where drawer-only.
- detail chunk preserves source details and BSR fields.
- stale chunk cleanup.
- no `fetch()`/`XMLHttpRequest` in generated Product Explorer script when implemented.

Production risks:

- Large inline payload regression.
- Broken deep links if selected IDs do not match chunk IDs.

Explicit items that must not change:

- V2 detail chunk directory and file names.
- Existing evidence and BSR fields.

### Task 3 - Static V3 Shell And Route Generator

Objective: generate the six V3 static routes with a shared shell, active navigation, dataset strip, and friendly error pages.

Files likely to change:

- `amazon_market_spy/dashboard_v3/generator.py`
- `amazon_market_spy/dashboard_v3/pages.py`
- `amazon_market_spy/dashboard_v3/components.py`
- `amazon_market_spy/dashboard_v3/theme.py`
- `tests/test_dashboard_v3.py`

Acceptance criteria:

- Generates `index.html`, `product_explorer.html`, `competitor_explorer.html`, `market_explorer.html`, and `data_health.html`.
- V2 route generation and output remain unchanged.
- Navigation uses `aria-current`.
- Dataset status appears on every V3 route using existing metadata only.
- Missing source data generates static error pages.

Tests required:

- all six routes generated.
- V2 still generates its approved primary routes.
- active navigation tests.
- error-page tests.
- runtime does not import mock data.

Production risks:

- Accidentally replacing V2 entrypoints or publication output.
- Route naming drift before deep-link compatibility is solved.

Explicit items that must not change:

- Existing `generate-dashboard-v2` command behavior.
- Existing V2 generated filenames.

### Task 4 - Product Explorer MVP

Objective: build the V3 Product Explorer list, filters, sort, URL state, pagination if retained, and evidence drawer on the V3 adapter.

Files likely to change:

- `amazon_market_spy/dashboard_v3/pages.py`
- `amazon_market_spy/dashboard_v3/components.py`
- `amazon_market_spy/dashboard_v3/theme.py`
- `tests/test_dashboard_v3.py`

Acceptance criteria:

- Default visible columns remain minimal: Product, Why it matters, Momentum, Proof, Open.
- Filtering and sorting work from the index before detail chunks load.
- Evidence drawer lazy-loads details only for focused products.
- Drawer shows product summary, source evidence by family, BSR proof, POD relevance, data quality, and external links.
- URL state accepts V3 canonical params and V2 aliases.

Tests required:

- URL state tests for `product_type` and `type`, `dir` and `direction`, `selected` and `focus`, and family-specific evidence params.
- keyboard navigation tests.
- index-only filtering/sorting tests.
- lazy detail loader tests.
- no-score-label tests.

Production risks:

- Breaking old shared links.
- Eagerly loading detail chunks.
- Presenting legacy score fields as new recommendation logic.

Explicit items that must not change:

- evidence thresholds and boolean meanings.
- lazy product detail loading.
- V2 Product Explorer behavior.

### Task 5 - Command Center

Objective: build the V3 daily triage page from existing product and dataset fields.

Files likely to change:

- `amazon_market_spy/dashboard_v3/pages.py`
- `amazon_market_spy/dashboard_v3/components.py`
- `tests/test_dashboard_v3.py`

Acceptance criteria:

- Shows research queue, evidence pulse, market activity, competitor activity, and data health summary.
- Queue sorting uses existing evidence fields only.
- Deep links open Product Explorer with preserved filters and selected product.
- No hidden priority score or new recommendation calculation is introduced.

Tests required:

- queue dedupe/diversity behavior if retained from V2.
- evidence pulse counts by existing fields.
- deep-link query generation.
- no new score assertions.

Production risks:

- Reintroducing score-like priority language.
- Overloading the page with drawer detail payloads.

Explicit items that must not change:

- analytics, thresholds, product classification, and CSV fields.

### Task 7 - Competitor Explorer

Objective: build seller activity review from product-derived evidence summaries.

Files likely to change:

- `amazon_market_spy/dashboard_v3/pages.py`
- `tests/test_dashboard_v3.py`

Acceptance criteria:

- Seller rows include product count, seller leader count, seller mover count, seller new push count, strong BSR count, and latest activity when available.
- Seller detail panel lists representative products.
- Product links preserve seller and evidence filters.

Tests required:

- seller aggregation tests.
- default activity-first sorting.
- seller deep-link tests.
- optional `competitor.html` alias test if approved.

Production risks:

- Seller summary counts diverging from Product Explorer filters.
- Route compatibility confusion between `competitor.html` and `competitor_explorer.html`.

Explicit items that must not change:

- seller intelligence CSV schema and V2 competitor route.

### Task 8 - Market Explorer

Objective: build segment scanning across category, product type, recipient, occasion, and theme.

Files likely to change:

- `amazon_market_spy/dashboard_v3/pages.py`
- `tests/test_dashboard_v3.py`

Acceptance criteria:

- Segment metrics use only existing product/evidence fields.
- Shows product count, seller count, evidence counts, median sub-BSR when present, and missing BSR count.
- Segment detail deep-links into Product Explorer.

Tests required:

- grouping mode tests for all five dimensions.
- median sub-BSR and missing-BSR tests.
- segment deep-link tests.

Production risks:

- Over-aggregating raw detail data into page payloads.
- Inventing market scores.

Explicit items that must not change:

- market analytics and generated CSV schemas.

### Task 9 - Data Health Route

Objective: make data confidence explicit as a top-level V3 route while keeping the global dataset strip.

Files likely to change:

- `amazon_market_spy/dashboard_v3/pages.py`
- `tests/test_dashboard_v3.py`

Acceptance criteria:

- Shows dataset summary, source family coverage, marketplace coverage, missing title/image/BSR counts, evidence no-data counts, and calibration links when present.
- Uses existing metadata and artifact presence only.
- Links back into related product/source lists when available.

Tests required:

- coverage and missing-field count tests.
- calibration link tests.
- no-data evidence count tests.

Production risks:

- Data Health becoming a second analytics engine.
- Confusing missing evidence with false evidence.

Explicit items that must not change:

- evidence calibration outputs, review analysis outputs, and thresholds.

### Task 10 - Additive CLI And Preview Integration

Objective: expose V3 generation without replacing V1 or V2.

Files likely to change:

- `amazon_market_spy/cli.py`
- `amazon_market_spy/dashboard_v3/__init__.py`
- `tests/test_dashboard_v3.py`
- possibly publication docs after approval

Acceptance criteria:

- Adds an explicit V3 command or approved preview flag.
- Default V2 command remains `generate-dashboard-v2` and still writes V2 output.
- V3 default output is isolated, for example `output/v3`.
- CLI reports generated pages and assets.

Tests required:

- CLI smoke test for V3.
- V2 CLI regression.
- V1 and V2 generation preservation tests.

Production risks:

- Accidentally changing default report publication behavior.
- Publishing V3 before parity review.

Explicit items that must not change:

- existing CLI defaults for V1 reports, trend reports, calibration, and Dashboard V2.

### Recommended First Implementation Task

The smallest safe first implementation task is Task 1: V3 Adapter Contract.

Rationale:

- It is isolated to a new `dashboard_v3` package and tests.
- It creates the data boundary the rest of V3 depends on.
- It can prove the no-new-analytics rule before UI work starts.
- It does not touch Dashboard V2, publication wiring, crawler/parser code, datasets, or generated CSV schemas.
- It gives later UI work a stable fixture and schema contract.

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
