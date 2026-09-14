# Main-image POD eligibility

POD eligibility is determined only from the selected main-image bytes. Titles,
descriptions, seller identity and category are never sent to vision and never
produce a yes/no decision. Text still names product types/niches for navigation.

- Yes: visible printed/engraved text, artwork or printed decorative pattern on the product.
- No: clearly no qualifying surface decoration.
- Needs Image Review: unprocessed/missing/unclear images, ambiguous technique, non-product images, or API/download failures.

Packaging, watermarks, screen UI, payment-card numbers, molded/painted figurine
details and embroidery do not establish qualifying decoration. AI decisions are
fallible; individual manual image reviews are stored with evidence and byte hash.

The scan and data-rebuild paths run visual review after detail/image repair and
before final analytics. CSV dashboard loads invalidate all old keyword labels.
The raw dataset is retained; only reviewed positives enter confirmed-POD views.

## Configuration and resuming

Set GEMINI_API_KEY in the process environment. No key is stored in source or logs.
The default model is gemini-2.5-flash. Default pacing is 4 requests/minute; quota
and authorization failures stop the run after saving progress. Unprocessed images
remain reviewable and are never automatically excluded.

Run from the project root:

```powershell
python -m amazon_market_spy.main_image_review output/latest_products.csv --workers 1 --rpm 4
```

Use --limit 20 for a bounded run and --refresh to request fresh AI decisions.
POD_IMAGE_REVIEW_CACHE optionally selects the JSON cache; default is
output/main_image_reviews.json. Keep this cache alongside the source installation
when regenerating reports. Cache entries bind exact URL, SHA256, policy version,
model, confidence, timestamp and visual evidence. A normal scan redownloads the
main image to check byte changes, reuses matching reviewed bytes, and invalidates
failed downloads. Offline dashboard rendering uses the last successful image
review; it does not claim to fetch a fresh Amazon image.

The current account reported a free-tier limit of 5 requests/minute. A full pass
of roughly 5,800 distinct image URLs therefore takes about 24 hours at the default
pace, subject to daily quota. The local preview is a partial image review, not a
completed full-dataset vision pass. Its unprocessed rows remain in Needs Image Review.

## Overview coverage

Home, Competitor Explorer and Market Explorer always use all current observations.
Unreviewed images never remove a seller, source or market group. Product Explorer
keeps separate POD/non-POD/Needs Image Review filters. Coverage-page deep links
include pod=all so a seller does not appear empty while image review is pending.
Rebuild with scripts/rebuild_image_dashboard.py SOURCE OUTPUT; this preserves
complete history and source tables and does not filter them through POD approval.
