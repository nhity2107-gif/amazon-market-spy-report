# amazon-market-spy

Python CLI for tracking Amazon competitor seller, category, best-seller, new-release, and movers-and-shakers pages from a source CSV.

The tool reads tracked Amazon URLs, fetches or parses page HTML, extracts ASIN-level listing data, preserves display order as rank, and writes CSVs for daily market monitoring.

## Install

```powershell
cd D:\amazon_market_spy
python -m pip install -e .
```

The live scanner uses Playwright with the installed Chrome channel by default. If Chrome is not available, use Edge with `--browser-channel msedge` or install Playwright Chromium:

```powershell
python -m playwright install chromium
```

Runtime dependencies are listed in `requirements.txt`.

## Run

Use the source file already present on this machine:

```powershell
amazon-market-spy scan --sources ..\amazon_market_spyinput\links.csv.txt --output output
```

Without installing first:

```powershell
python -m amazon_market_spy scan --sources ..\amazon_market_spyinput\links.csv.txt --output output
```

Regenerate trend reports from existing daily snapshots:

```powershell
python -m amazon_market_spy trend --sources input\links.csv --output output
```

Generate the isolated Dashboard V2 Sprint 1 static shell:

```powershell
python -m amazon_market_spy generate-dashboard-v2 --output output\v2
```

Dashboard V2 is generated separately from the V1 dashboard. It uses isolated mock presentation data for Sprint 1 and writes five pages under `output\v2`: Morning Brief, Idea Explorer, Product Explorer, Competitor, and Market Explorer.

Send the daily Lark custom bot summary after reports are generated:

```powershell
python amazon_market_spy.py notify-lark --webhook WEBHOOK_URL --output output
```

Send Lark interactive cards instead of one plain text message:

```powershell
python amazon_market_spy.py notify-lark --webhook WEBHOOK_URL --output output --card --top-products 5
```

Product images in card mode require Lark image upload credentials. Configure a Lark custom/self-built app with bot ability enabled and grant one of these image upload permissions: `im:resource` or `im:resource:upload`. Then set either a tenant token directly or app credentials so the tool can request one:

```powershell
$env:LARK_APP_ID = "cli_xxx"
$env:LARK_APP_SECRET = "xxx"
# Optional alternative if you already manage token refresh yourself:
$env:LARK_TENANT_ACCESS_TOKEN = "t-xxx"
```

You can also set `LARK_WEBHOOK_URL` and omit `--webhook`. The command prints a warning and skips notification when no webhook is configured. The message links to the live report URL by default:

```text
https://nhity2107-gif.github.io/amazon-market-spy-report/
```

Set `REPORT_URL` or pass `--report-url` to use a different live report URL. Pass `--include-local-path` only when you also want the local `output\index.html` path included.

Publish the current HTML report to GitHub Pages:

```powershell
python amazon_market_spy.py publish-report --output output
```

By default this publishes to:

```text
https://nhity2107-gif.github.io/amazon-market-spy-report/
```

Use `--repo-url` for a different Git remote and `--site-url` for a different printed site URL.

## Input CSV

Required columns:

```csv
source_name,source_type,category,url,priority,active
```

`active` accepts `yes`, `true`, `1`, or `y`.

For seller sources, use the real seller display name in `source_name` when possible, for example `LASFOUR (Warrior)`. If an older source file still uses generic labels such as `Competitor Store 6`, the report display name is resolved from an optional `seller_name` column, then from the seller row's display value in `category`, then from the Amazon seller ID in the URL.

Supported `source_type` values:

- `seller`
- `best-seller` or `best_seller`
- `new-release` or `new_release`
- `movers-and-shakers`, `movers_shakers`, or `movers_and_shakers`
- `category`

Example rows:

```csv
source_name,source_type,category,url,priority,active
LASFOUR (Warrior),seller,Personalized Mugs,https://www.amazon.com/s?i=merchant-items&me=SELLERID,1,yes
Best Sellers - Mugs,best-seller,Personalized Mugs,https://www.amazon.com/Best-Sellers-Kitchen-Dining-Coffee-Mugs/zgbs/kitchen/367145011,1,yes
New Releases - Mugs,new-release,Personalized Mugs,https://www.amazon.com/gp/new-releases/kitchen/367145011,2,yes
Movers - Mugs,movers-and-shakers,Personalized Mugs,https://www.amazon.com/gp/movers-and-shakers/kitchen/367145011,2,yes
Category - Mugs,category,Personalized Mugs,https://www.amazon.com/s?k=personalized+mug,3,yes
```

## Outputs

Each scan writes:

- `output/today_snapshot.csv`
- `output/latest_products.csv`
- `output/product_trends.csv`
- `output/trend_alerts.csv`
- `output/lark_trend_alerts.csv`
- `output/priority_board.csv`
- `output/index.html`
- `output/priority_board.html`
- `output/product_discovery.html`
- `output/competitor.html`
- `output/trend_explorer.html`
- `output/product_detail.html`
- `output/products.html`
- `output/top_winners.html`
- `output/new_breakouts.html`
- `output/fast_movers.html`
- `output/new_releases.html`
- `output/trends.html`
- `output/database.html`
- `output/image_gallery.html`
- `output/top_opportunities.html`
- `output/all_opportunities.html`
- `output/new_products.html`
- `output/rising_products.html`
- `output/seller_intelligence.html`
- `output/niche_intelligence.html`
- `output/source_explorer.html`
- `output/non_pod_excluded.html`
- `output/daily_market_spy_report.xlsx`
- `output/source_summary.csv`
- `output/market_changes.csv`
- `output/historical_comparison.csv`
- `output/rank_audit.csv`
- `output/rank_trends.csv`
- `output/source_trends.csv`
- `output/seller_intelligence.csv`
- `output/niche_intelligence.csv`
- `output/source_errors.csv`
- `data/snapshots/YYYY-MM-DD_snapshot.csv`
- `data/master_snapshot.csv`
- `output/pages/*.html` when live pages are fetched
- `output/images/<asin>.jpg` for downloaded opportunity images
- `output/product_detail/<asin>.html` for per-product decision detail pages
- `screenshots/*.png` when live pages are visited with Playwright

The Excel workbook contains:

- `Executive Summary`
- `New Wins`
- `Winners`
- `Rising`
- `Declining`
- `Seller Intelligence`
- `Niche Intelligence`
- `Raw Snapshot`

`latest_products.csv` and each snapshot include `date`, `seller_name`, `seller_id`, `seller_url`, `display_rank`, `display_order`, `rank`, `rank_basis`, `image_url`, `image_source`, `image_fixed`, `review_count`, `review_rating`, `is_pod`, `pod_type`, `pod_score`, `pod_reason`, `niche_primary`, `niche_secondary`, `niche_tags`, `niche_score`, `niche_reason`, `raw_title`, `title_source`, `title_fixed`, `detail_page_status`, `detail_title_found`, `detail_image_found`, `detail_error`, `detail_bsr_found`, `detail_bsr_error`, the BSR fields, and rank audit fields. Products are written in the same order they appear on the rendered Amazon page.

Rank fields are intentionally separated:

- `display_rank`: position inside the tracked seller/category/source page.
- `primary_bsr_rank` and `primary_bsr_category`: the first/top-level Amazon Best Sellers Rank from the product detail page.
- `sub_bsr_rank` and `sub_bsr_category`: the best non-primary subcategory rank from the detail page.
- `raw_bsr_block`: exact Best Sellers Rank block captured from the selected Amazon detail section.
- `category_ranks_raw`: backward-compatible copy of the raw BSR block.

When `--fetch-category-rank` is passed, the scanner visits product detail pages only for the Top 100 opportunity candidates, capped by `--max-detail-pages` (default 100). Before parsing, it expands Amazon Product information accordions such as `Product information`, `Item details`, and `Features & Specs`, then waits for visible `Best Sellers Rank` text. It extracts Amazon BSR in this order: `#productDetails_detailBullets_sections1` as `product_details`, `#detailBullets_feature_div` as `detail_bullets`, `#productDetails_db_sections` as `product_details_db`, expanded Product information > Item details as `product_information_item_details`, then `text_scan` only if all section and accordion extraction paths fail. Selector and accordion parses are `high` confidence. `text_scan` is `medium` when it finds a BSR block and `low` when it cannot. It fills `primary_bsr_rank`, `primary_bsr_category`, `sub_bsr_rank`, `sub_bsr_category`, `raw_bsr_block`, `category_ranks_raw`, `all_bsr_ranks`, `subcategory_rank_score`, and audit fields `rank_extracted_at`, `rank_source_url`, `rank_page_status`, `rank_parse_method`, `rank_parse_confidence`, `rank_parse_warning`, `accordion_found`, `accordion_expanded`, and `bsr_visible_after_expand`. Existing non-empty rank fields are not overwritten with blanks. `output/rank_audit.csv` includes `asin`, `title`, `product_url`, `display_rank`, `source_name`, parsed BSR fields, raw BSR block, extraction time, parse method/confidence, warning text for `text_scan`, and accordion diagnostics.

Audit one product page manually:

```powershell
python amazon_market_spy.py audit-rank --asin ASIN --url PRODUCT_URL --headful
```

The audit command prints `accordion_found`, `accordion_expanded`, `bsr_visible_after_expand`, `raw_bsr_block`, `rank_parse_method`, and `rank_parse_confidence`, writes parsed fields to `output/rank_audit.csv`, and saves `debug_rank\<asin>_rank.html` plus `debug_rank\<asin>_rank.png` when a screenshot is available.

Product images are extracted from Amazon listing-card image tags, preferring `img.s-image`, then `img[data-image-latency]`, then `img[src]`.

Listing titles are extracted from Amazon title selectors first: `h2 span`, `h2 a span`, line-clamp title links, and Amazon text-normal title spans. The scraper rejects short option labels such as `A1`, `Gift Idea 1`, `Style 2`, color names, and titles shorter than 20 characters or fewer than 3 words. Live scans automatically try to fix invalid titles or missing images for top opportunity candidates by opening the original product detail URL, including variation URLs with `th=1`, and waiting for `#productTitle`, `#landingImage`, `#imgTagWrapperId img`, `og:title`, or `og:image`. Detail title priority is `#productTitle`, `og:title`, then `document.title`; image priority is `#landingImage src`, `#landingImage data-old-hires`, `#imgTagWrapperId img src`, then `og:image`. The same detail page fetch also waits for BSR sections and extracts `Best Sellers Rank` / `Sales Rank`, filling only blank BSR columns so existing rank values are preserved. Use `--fix-missing-details --max-detail-fixes 300 --detail-timeout 30` to explicitly repair a broader set of products, still capped to avoid fetching every tracked listing. Failed fallbacks write `debug_html/detail_failed_<ASIN>.html` and `screenshots/detail_failed_<ASIN>.png` when available. If a title remains invalid, HTML reports show `Title unavailable - open product` and keep the product URL clickable.

ASINs are validated as Amazon product IDs in `B0XXXXXXXX` format. Numeric widget IDs and other non-product identifiers are ignored, and ASIN is used as the product key across daily snapshots.

`market_changes.csv` compares the current scan to the previous snapshot and flags new ASINs, removed ASINs, rank changes, price changes, and title changes.

`historical_comparison.csv` compares today's snapshot with all earlier snapshots for the same source/category/ASIN, including `seller_name`, `seller_id`, `seller_url`, `previous_rank`, previous latest rank, `days_seen`, `appearances_7d`, `best_rank_7d`, `avg_rank_7d`, historical best/worst rank, rank movement versus history, historical status, `image_url`, `review_count`, `review_rating`, `review_growth_7d`, `review_growth_30d`, `review_velocity_score`, `opportunity_score`, and the score breakdown fields `pod_component`, `momentum_component`, `market_component`, `competition_component`, and `niche_component`.

`trend_alerts.csv` includes classified rows sorted by `opportunity_score` descending.

`lark_trend_alerts.csv` is a top-100 Lark Base import file for market opportunities. It includes `product_url`, adds POD and niche classification fields, includes review count, rating, review growth, and review velocity columns, and includes `seller_name`, `seller_id`, and `seller_url` for seller sources. It excludes declining rows by default and includes `new_win`, `rising`, `winner`, and score-only opportunities with `opportunity_score` of 60 or higher.

Opportunity images are downloaded to `output\images\<asin>.jpg` when `image_url` is available. `product_discovery.html` is the primary working dashboard for product researchers. `priority_board.html` is the Today summary dashboard and is also written to `index.html`.

Today shows only the highest-value signals, capped to approximately 30 products across four sections: New Winners, Fast Rising, Competitor Launches, and Emerging Trends. Every product card includes 2-4 evidence tags explaining why it appears, such as rank movement, new seller Top10 placement, Best Seller appearance, cross-source confirmation, new tracking, or low review count.

Product Discovery replaces the former Top Winners, Fast Movers, New Breakouts, Best Sellers, and New Releases workflows. It is also written to `products.html` for compatibility and includes filters for New Winner, Fast Rising, Stable Winner, Best Seller, New Release, Seller, Product Type, Niche, Days Tracked, and text search. Cards show image, title, seller, current rank, rank trend, days tracked, Winner Signal Score, evidence tags, Amazon link, and Product Detail link.

The Winner Signal Score is generated in the analytics/dashboard layer from existing historical rows. It combines current rank strength, rank momentum, freshness, cross-source appearance, source quality, and BSR strength. The score is explainable on the card through evidence tags and is not added to existing CSV schemas.

`competitor.html` summarizes seller activity before listing products: New Launches, Winners, Rising Products, and Current Top10. Each seller section lists only current Top10 products and highlights NEW, RISING, FALLING, or DROPPED status. `seller_intelligence.html` is kept as a compatibility copy of this focused competitor view.

`trend_explorer.html` clusters products into POD idea trends using combinations of Product Type, Recipient, Occasion, Theme, and Quote keywords derived from existing metadata and titles. It shows Trend Name, Product Count, Seller Count, Growth, and Signal, with links into Product Discovery for related products. Legacy trend and niche pages route to the new Trend Explorer where appropriate.

`product_detail.html` is an index of product detail pages, and `product_detail\<asin>.html` shows image, title, seller, display-rank timeline, BSR timeline, source history, first seen, days tracked, Winner Signal Score, Amazon link, and the Winner Journey: First Seen -> New Release -> Seller Top10 -> Best Seller -> Stable Winner.

Legacy dashboards are still generated for backward compatibility but now route into the focused workflow: `top_winners.html`, `new_breakouts.html`, `fast_movers.html`, `new_releases.html`, `top_opportunities.html`, `image_gallery.html`, `all_opportunities.html`, `new_products.html`, `rising_products.html`, and `database.html` route to Product Discovery; niche pages route to Trend Explorer; source explorer routes to Competitor. The plain text Lark notification remains capped to the top 20 opportunities to avoid overly long messages.

`priority_board.csv` exports the deduped decision rows with `asin`, `primary_bucket`, `badges`, `badge_count`, `decision_score`, `title`, `seller_name`, `niche_primary`, `source_name`, `display_rank`, `previous_display_rank`, `display_rank_change`, `growth_velocity`, `opportunity_score`, `primary_bsr_rank`, `sub_bsr_rank`, `product_url`, and `image_url`, plus compatibility fields. Growth velocity is `display_rank_change / max(days_seen, 1)`. Decision score is `opportunity_score + top_rank_score + velocity_score + newness_score + bsr_score + pod_score + badge_count * 5`.

Use `notify-lark --card --top-products 5` to send mobile-first Lark interactive cards: one `Amazon POD Market Spy Summary` card plus up to five product opportunity cards sorted by `opportunity_score` descending. The summary card uses a 2x2 KPI layout for Products Tracked, High Opportunity Products, New Wins, and Rising Products, followed by ranked Top Niches, ranked Top Sellers, and a `View Dashboard` button. Each product card uses a signal-specific header color (green for New Win, orange for Rising, blue for Opportunity), an optional product image, a compact Score / Display Rank / Rank Movement row, market evidence, and `Open Amazon` / `View Dashboard` buttons. A visible note warns when BSR parsing confidence is below `high`. Product card rows come from `lark_trend_alerts.csv`, falling back to `trend_alerts.csv` and then `latest_products.csv` if needed. If Lark rejects a card payload, the command sends the existing plain text notification as a fallback.

Lark cards cannot render external Amazon image URLs directly; they require uploaded image keys. In card mode the tool reads `local_image_path` first, otherwise downloads `image_url`, uploads it to `https://open.larksuite.com/open-apis/im/v1/images`, and stores the returned `image_key` in `output\lark_image_keys.json` by ASIN. If image upload fails or credentials are missing, the product card is still sent without an image block. Debug logs include ASIN, source image URL/path, whether an `image_key` was created, and the cached/uploaded key.

Opportunity cards show display rank and source-rank movement from the tracked source, for example `#31 -> #3 (+28)`. When available, they also show Amazon BSR and best subcategory rank from the product detail page, for example `#65,003 in Home & Kitchen` and `#149 in Decorative Signs & Plaques`. Cards display a rank audit warning when `rank_parse_confidence` is not `high`, so `text_scan` results are visibly flagged. Card sorting includes `Best Subcategory BSR`, `Amazon BSR`, growth velocity, and new breakout score. Secondary fields such as full title, source details, review count, rating, days seen, first seen, tags, raw category ranks, product URL, and source URL are moved into the card detail modal.

By default the opportunity dashboard, Lark import, and Lark notification focus on print-on-demand products: `is_pod=yes` and `is_pod=maybe`. Physical retail products such as branded insulated bottles are excluded unless they have strong custom, personalized, printed, engraved, quote, photo, or gift signals. Use `--include-non-pod` with `scan` or `trend` to include physical products in opportunity reports. `non_pod_excluded.html` shows excluded products with `pod_reason` for classifier review.

POD niche classification assigns `niche_primary`, `niche_secondary`, semicolon-separated `niche_tags`, `niche_score`, and `niche_reason` using product title, category, source name, POD type, and POD reason. Supported niche groups include family/relationships, occasions and holidays, professions, hobbies, pets, identity/community, and POD product types. Unknown products use `niche_primary=Unknown` and `niche_score=0`.

`niche_intelligence.csv` groups POD opportunities by niche and reports products tracked, POD products, opportunities, new wins, rising products, average and max opportunity score, rank and BSR summaries, `best_subcategory_rank`, `best_subcategory_product`, review growth, top seller, top product, and `niche_momentum_score`. The CSV schema remains unchanged for downstream imports. The old `niche_intelligence.html` workflow now routes researchers to Trend Explorer, while `seller_intelligence.html` is kept as a compatibility copy of the focused Competitor page.

`publish-report` creates or updates the local `publish\` folder for GitHub Pages. It copies `output\priority_board.html` to `publish\index.html`, publishes the focused dashboard pages including Product Discovery, Competitor, Trend Explorer, Product Detail, and compatibility redirects, and copies product images from `output\images\` plus `output\product_detail\` when present. If `output\images\` does not exist, it falls back to `images\`. The command initializes `publish\` as a Git repository, sets the branch to `main`, adds or updates the `origin` remote, commits the report, pushes to GitHub, then prints the site URL.

`classification` can include multiple semicolon-separated labels:

- `new_win`: first seen within the last 7 days, today's rank is 20 or better, and rank improved by at least 10 positions.
- `rising`: rank improved by at least 10 positions and today's rank is 100 or better.
- `winner`: today's rank is 10 or better and `days_seen` is at least 7.
- `declining`: rank dropped by at least 10 positions.

`opportunity_score` is capped at 100 and now prioritizes business opportunity over POD detection. It is the sum of five weighted components: `pod_component` contributes up to 30 points from POD score, `momentum_component` contributes up to 25 points from rank change, `new_win`, `rising`, and `days_seen`, `market_component` contributes up to 20 points from subcategory and category BSR strength, `niche_component` contributes up to 15 points from niche strength, holiday relevance, and gifting relevance, and `competition_component` contributes up to 10 points from review count, review growth, and review rating. Product cards show this breakdown in the Opportunity Score hover/focus tooltip. `review_velocity_score` is still based on review growth over the last 7 and 30 days, and `subcategory_rank_score` remains available as the normalized subcategory BSR signal.

Rank is based on display order within each tracked source. When `--max-pages` is greater than 1, ranks continue across crawled Amazon result pages. `rank_delta` is positive when a product moves up, for example rank 5 to rank 2 gives `rank_delta = 3` and `rank_direction = up`.

`rank_trends.csv` and `product_trends.csv` summarize each ASIN across all snapshots and include the latest `seller_name`, `seller_id`, `seller_url`, `image_url`, `review_count`, `review_rating`, `review_growth_7d`, `review_growth_30d`, and `review_velocity_score`. `source_trends.csv` summarizes product count and ASIN churn for each tracked source/page and includes `seller_name`, `seller_id`, and `seller_url` from the source CSV when available.

`seller_intelligence.csv` groups by `seller_name` and summarizes each seller/source with `seller_name`, `seller_id`, `seller_url`, `source_name`, `source_type`, products tracked, new wins, rising products, average rank, review growth, review velocity, momentum score, `pod_products`, `pod_opportunities`, `pod_momentum_score`, `top_niche`, `niche_count`, `best_subcategory_rank`, and `best_subcategory_product`. Rows are sorted by `seller_name`. `seller_url` comes from the original source CSV URL; `seller_id` is extracted from Amazon seller URL parameters `m`, `me`, or `seller` when present.

## Offline HTML Mode

If Amazon blocks automated requests, save pages manually from the browser and parse them:

```powershell
amazon-market-spy scan --sources ..\amazon_market_spyinput\links.csv.txt --html-dir saved_pages --offline --output output
```

For each source, name the saved HTML file with either the source slug or row number, for example:

- `competitor-store-1.html`
- `source-1.html`

Live scans visit each active URL with Playwright Chromium, wait for the page load state, wait for common Amazon product/listing selectors, optionally crawl Amazon result pagination up to `--max-pages`, then parse the rendered HTML. With `--fetch-category-rank` or detail title/image fixes, the tool waits between product detail page requests using the scan delay. The tool does not bypass login, CAPTCHA, paywalls, or access restrictions. Use conservative delays and comply with Amazon's terms and your internal policies.

## Daily Tracking

Run the same scan command once per day. Each run creates or replaces that day's snapshot in `data/snapshots/YYYY-MM-DD_snapshot.csv`, rebuilds `data/master_snapshot.csv` from all daily snapshots, and refreshes the trend reports.

Regenerate the dashboard import after snapshots are available:

```powershell
python .\amazon_market_spy.py trend --sources input\links.csv --output output
```

Open the Product Discovery dashboard after regenerating reports:

```powershell
python .\amazon_market_spy.py trend --output output
start output\product_discovery.html
```

Then import `output\lark_trend_alerts.csv` into Lark Base.

Send a short Lark notification with product counts, new wins, rising count, top opportunities, top niches, top sellers, and the live GitHub Pages report URL. The `Top Sellers` section uses `seller_name`, for example `LASFOUR (Warrior)`, instead of generic `Competitor Store` labels:

```powershell
python .\amazon_market_spy.py notify-lark --output output
```

Send interactive Lark cards for mobile scanning:

```powershell
python .\amazon_market_spy.py notify-lark --output output --card --top-products 5
```

Override the live report URL with an environment variable or CLI option:

```powershell
$env:REPORT_URL = "https://nhity2107-gif.github.io/amazon-market-spy-report/"
python .\amazon_market_spy.py notify-lark --output output
python .\amazon_market_spy.py notify-lark --output output --report-url "https://example.com/report/"
```

Include the local HTML path only when needed:

```powershell
python .\amazon_market_spy.py notify-lark --output output --include-local-path
```

Publish the HTML report to GitHub Pages:

```powershell
python .\amazon_market_spy.py publish-report --output output
```

## Windows PowerShell Usage

Install:

```powershell
cd D:\amazon_market_spy
python -m pip install -r requirements.txt
python -m pip install -e .
```

Validate the input file:

```powershell
python .\amazon_market_spy.py validate-sources --sources input\links.csv
```

Run a daily scan:

```powershell
python .\amazon_market_spy.py scan --sources input\links.csv --output output
```

Run a daily scan after setting Amazon delivery location to a US ZIP code:

```powershell
python .\amazon_market_spy.py scan --sources input\links.csv --output output --headful --zipcode 10001
```

Run with conservative retry and delay settings:

```powershell
python .\amazon_market_spy.py scan --sources input\links.csv --output output --retries 2 --delay 5 --timeout 60 --ready-timeout 30
```

Auto-scroll live Amazon pages before parsing so lazy-loaded listings are included:

```powershell
python .\amazon_market_spy.py scan --sources input\links.csv --output output --scroll --max-scrolls 8 --scroll-wait-ms 1500
```

Crawl multiple Amazon result pages per source:

```powershell
python .\amazon_market_spy.py scan --sources input\links.csv --output output --max-pages 3
```

Include non-POD physical retail products in opportunity reports:

```powershell
python .\amazon_market_spy.py scan --sources input\links.csv --output output --include-non-pod
python .\amazon_market_spy.py trend --sources input\links.csv --output output --include-non-pod
```

Fetch Amazon product detail BSR fields for top opportunities:

```powershell
python .\amazon_market_spy.py scan --sources input\links.csv --output output --fetch-category-rank --max-detail-pages 100
python .\amazon_market_spy.py trend --sources input\links.csv --output output --fetch-category-rank --max-detail-pages 100
```

Fix invalid listing titles and missing images from product detail pages:

```powershell
python .\amazon_market_spy.py scan --sources input\links.csv --output output --fix-missing-details --max-detail-fixes 300 --detail-timeout 30
python .\amazon_market_spy.py trend --sources input\links.csv --output output --fix-missing-details --max-detail-fixes 300 --detail-timeout 30
```

Use a custom user agent:

```powershell
python .\amazon_market_spy.py scan --sources input\links.csv --output output --user-agent "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125 Safari/537.36"
```

Save screenshots only on errors:

```powershell
python .\amazon_market_spy.py scan --sources input\links.csv --output output --no-screenshots
```

Disable error screenshots:

```powershell
python .\amazon_market_spy.py scan --sources input\links.csv --output output --no-error-screenshots
```

Regenerate reports from existing snapshots:

```powershell
python .\amazon_market_spy.py trend --sources input\links.csv --output output
```

Send the Lark notification after scan or trend:

```powershell
$env:LARK_WEBHOOK_URL = "https://open.larksuite.com/open-apis/bot/v2/hook/..."
python .\amazon_market_spy.py notify-lark --output output
python .\amazon_market_spy.py notify-lark --output output --card --top-products 5
```

The webhook URL is not printed in logs. The notification shows `View live report:` with `https://nhity2107-gif.github.io/amazon-market-spy-report/` unless `REPORT_URL` or `--report-url` overrides it. In card mode, the dashboard button uses the same report URL.

`run_daily.bat` runs:

```bat
python amazon_market_spy.py scan --sources input\links.csv --output output --zipcode 10001
if errorlevel 1 exit /b %errorlevel%
python amazon_market_spy.py trend --output output
if errorlevel 1 exit /b %errorlevel%
python amazon_market_spy.py publish-report --output output
if errorlevel 1 exit /b %errorlevel%
if defined LARK_WEBHOOK_URL python amazon_market_spy.py notify-lark --output output
start "" "output\index.html"
```

On Windows Task Scheduler, use:

```text
Program/script: python
Arguments: -m amazon_market_spy scan --sources D:\amazon_market_spy\input\links.csv --output D:\amazon_market_spy\output --snapshot-dir D:\amazon_market_spy\data\snapshots --master-snapshot D:\amazon_market_spy\data\master_snapshot.csv
Start in: D:\amazon_market_spy
```

## Useful Options

```powershell
amazon-market-spy scan --help
amazon-market-spy validate-sources --sources ..\amazon_market_spyinput\links.csv.txt
amazon-market-spy trend --sources input\links.csv --output output
amazon-market-spy publish-report --output output
```

Skip screenshots if disk space is tight:

```powershell
amazon-market-spy scan --sources input\links.csv --output output --no-screenshots
```

Wait longer for slow Amazon pages:

```powershell
amazon-market-spy scan --sources input\links.csv --output output --ready-timeout 30 --timeout 60
```

Load more lazy-rendered products before extraction:

```powershell
amazon-market-spy scan --sources input\links.csv --output output --scroll --max-scrolls 8 --scroll-wait-ms 1500
```

Crawl multiple result pages and keep ranks continuous:

```powershell
amazon-market-spy scan --sources input\links.csv --output output --scroll --max-pages 3
```

Include physical retail products in opportunity reports:

```powershell
amazon-market-spy trend --sources input\links.csv --output output --include-non-pod
```

Fetch Amazon BSR fields for top opportunity detail pages:

```powershell
amazon-market-spy scan --sources input\links.csv --output output --fetch-category-rank --max-detail-pages 100
```

Fix missing detail titles/images:

```powershell
amazon-market-spy trend --sources input\links.csv --output output --fix-missing-details --max-detail-fixes 300 --detail-timeout 30
```

Use Microsoft Edge instead of Chrome:

```powershell
amazon-market-spy scan --sources input\links.csv --output output --browser-channel msedge
```
