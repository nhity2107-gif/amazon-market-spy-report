from __future__ import annotations

import json
import mimetypes
import os
from pathlib import Path
from time import sleep
from urllib.parse import urlparse
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from .publish import DEFAULT_SITE_URL
from .product_details import display_product_title
from .reporting import read_csv


LARK_TIMEOUT_SECONDS = 20
DEFAULT_REPORT_URL = DEFAULT_SITE_URL
LARK_TOP_OPPORTUNITY_LIMIT = 20
LARK_TOP_NICHE_LIMIT = 3
LARK_DEFAULT_CARD_PRODUCT_LIMIT = 5
LARK_MAX_CARD_PRODUCT_LIMIT = 5
LARK_CARD_SEND_DELAY_SECONDS = 0.25
LARK_API_BASE_URL = "https://open.larksuite.com"
LARK_IMAGE_CACHE_FILENAME = "lark_image_keys.json"
LARK_IMAGE_UPLOAD_TIMEOUT_SECONDS = 30
LARK_MAX_IMAGE_BYTES = 10 * 1024 * 1024
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125 Safari/537.36"


class LarkNotificationError(RuntimeError):
    pass


def build_lark_notification_message(
    output_dir: Path,
    report_url: str = DEFAULT_REPORT_URL,
    include_local_path: bool = False,
) -> str:
    context = _lark_notification_context(output_dir)
    products_tracked = context["products_tracked"]
    new_wins = context["new_wins"]
    rising = context["rising"]
    top_opportunities = context["top_opportunities"]
    top_sellers = context["top_sellers"]
    top_niches = context["top_niches"]
    top_movers = context["top_movers"]
    local_report_path = context["local_report_path"]

    lines = [
        "Amazon Market Spy Daily Report",
        f"Products tracked: {products_tracked}",
        f"New Wins: {new_wins}",
        f"Rising: {rising}",
        "",
        f"Top {LARK_TOP_OPPORTUNITY_LIMIT} opportunities:",
    ]
    if top_opportunities:
        for index, row in enumerate(top_opportunities, start=1):
            score = row.get("opportunity_score", "") or "0"
            title = _shorten(display_product_title(row.get("title", "")) or row.get("asin", "") or "Untitled")
            source = _seller_display_name(row)
            lines.append(f"{index}. {score} - {title} ({source})")
    else:
        lines.append("None")

    lines.extend(["", "Top Movers Today:"])
    if top_movers:
        for index, row in enumerate(top_movers, start=1):
            title = _shorten(display_product_title(row.get("title", "")) or row.get("asin", "") or "Untitled")
            previous_rank = row.get("previous_display_rank", "") or row.get("display_rank", "")
            current_rank = row.get("display_rank", "") or row.get("rank", "") or row.get("position", "")
            change = _to_int(row.get("display_rank_change", "")) or 0
            lines.append(f"{index}. {title}")
            lines.append(f"   #{previous_rank} -> #{current_rank} (+{change})")
    else:
        lines.append("None")

    lines.extend(["", "Top Niches Today:"])
    if top_niches:
        for index, row in enumerate(top_niches, start=1):
            niche = row.get("niche", "") or "Unknown"
            score = row.get("niche_momentum_score", "") or "0"
            new_wins_count = row.get("new_wins", "") or "0"
            lines.append(f"{index}. {niche} - momentum {score} - {new_wins_count} new wins")
    else:
        lines.append("None")

    lines.extend(["", "Top Sellers:"])
    if top_sellers:
        for index, row in enumerate(top_sellers, start=1):
            lines.append(f"{index}. {_seller_display_name(row)}")
    else:
        lines.append("None")

    lines.extend(["", "View live report:", report_url])
    if include_local_path:
        lines.extend(["", f"Local report path: {local_report_path}"])
    return "\n".join(lines)


def build_lark_interactive_card_payloads(
    output_dir: Path,
    report_url: str = DEFAULT_REPORT_URL,
    include_local_path: bool = False,
    top_products: int = LARK_DEFAULT_CARD_PRODUCT_LIMIT,
) -> list[dict[str, object]]:
    context = _lark_notification_context(output_dir)
    top_products = min(max(0, top_products), LARK_MAX_CARD_PRODUCT_LIMIT)
    product_rows = _top_card_products(context, top_products)
    image_cache = _load_lark_image_cache(output_dir)
    tenant_access_token = _lark_tenant_access_token()
    product_cards = []
    cache_dirty = False
    for index, row in enumerate(product_rows, start=1):
        card_row = dict(row)
        image_key = upload_lark_image(
            image_url=card_row.get("image_url", ""),
            local_image_path=card_row.get("local_image_path", ""),
            output_dir=output_dir,
            asin=card_row.get("asin", ""),
            tenant_access_token=tenant_access_token,
            cache=image_cache,
        )
        if image_key:
            card_row["_lark_image_key"] = image_key
            cache_dirty = True
        product_cards.append(_product_card(card_row, report_url=report_url, index=index))
    if cache_dirty:
        _save_lark_image_cache(output_dir, image_cache)
    cards = [
        _summary_card(context, report_url=report_url, include_local_path=include_local_path),
        *product_cards,
    ]
    return [{"msg_type": "interactive", "card": card} for card in cards]


def upload_lark_image(
    image_url: str = "",
    local_image_path: str = "",
    *,
    output_dir: Path | None = None,
    asin: str = "",
    tenant_access_token: str = "",
    cache: dict[str, dict[str, str]] | None = None,
    api_base_url: str = LARK_API_BASE_URL,
) -> str:
    normalized_asin = asin.strip().upper()
    image_source = (image_url or local_image_path or "").strip()
    cached = (cache or {}).get(normalized_asin, {}) if normalized_asin else {}
    if cached.get("image_key"):
        _log_lark_image_upload(normalized_asin, image_source, cached["image_key"], created=False)
        return cached["image_key"]

    if not image_source or not tenant_access_token:
        _log_lark_image_upload(normalized_asin, image_source, "", created=False)
        return ""

    try:
        image_data, filename, content_type = _read_lark_image_source(
            image_url=image_url,
            local_image_path=local_image_path,
            output_dir=output_dir,
        )
        image_key = _upload_lark_image_bytes(
            image_data,
            filename=filename,
            content_type=content_type,
            tenant_access_token=tenant_access_token,
            api_base_url=api_base_url,
        )
    except (LarkNotificationError, OSError):
        _log_lark_image_upload(normalized_asin, image_source, "", created=False)
        return ""

    if cache is not None and normalized_asin:
        cache[normalized_asin] = {
            "image_key": image_key,
            "image_url": image_url.strip(),
            "local_image_path": local_image_path.strip(),
        }
    _log_lark_image_upload(normalized_asin, image_source, image_key, created=True)
    return image_key


def _lark_tenant_access_token(api_base_url: str = LARK_API_BASE_URL) -> str:
    existing_token = os.environ.get("LARK_TENANT_ACCESS_TOKEN", "").strip()
    if existing_token:
        return existing_token

    app_id = os.environ.get("LARK_APP_ID", "").strip()
    app_secret = os.environ.get("LARK_APP_SECRET", "").strip()
    if not app_id or not app_secret:
        return ""

    payload = json.dumps({"app_id": app_id, "app_secret": app_secret}).encode("utf-8")
    request = Request(
        f"{api_base_url.rstrip('/')}/open-apis/auth/v3/tenant_access_token/internal",
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=LARK_TIMEOUT_SECONDS) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, OSError, ValueError, json.JSONDecodeError):
        return ""

    if response_payload.get("code") not in (0, None):
        return ""
    return str(response_payload.get("tenant_access_token", "")).strip()


def _read_lark_image_source(
    *,
    image_url: str,
    local_image_path: str,
    output_dir: Path | None,
) -> tuple[bytes, str, str]:
    local_path = _resolve_local_image_path(local_image_path, output_dir)
    if local_path and local_path.exists():
        image_data = local_path.read_bytes()
        filename = local_path.name
        content_type = _content_type(filename)
        return _validate_lark_image_data(image_data), filename, content_type

    if not image_url.strip():
        raise LarkNotificationError("Lark image upload skipped: image missing")

    try:
        request = Request(image_url.strip(), headers={"User-Agent": USER_AGENT})
        with urlopen(request, timeout=LARK_IMAGE_UPLOAD_TIMEOUT_SECONDS) as response:
            image_data = response.read(LARK_MAX_IMAGE_BYTES + 1)
            content_type = response.headers.get_content_type() or _content_type(image_url)
    except (HTTPError, URLError, OSError, ValueError) as exc:
        raise LarkNotificationError(f"Lark image download failed: {type(exc).__name__}") from exc

    filename = Path(urlparse(image_url).path).name or "product-image.jpg"
    return _validate_lark_image_data(image_data), filename, content_type


def _resolve_local_image_path(local_image_path: str, output_dir: Path | None) -> Path | None:
    text = local_image_path.strip()
    if not text:
        return None
    path = Path(text)
    if path.is_absolute():
        return path
    if output_dir is not None:
        return output_dir / path
    return path


def _validate_lark_image_data(image_data: bytes) -> bytes:
    if not image_data:
        raise LarkNotificationError("Lark image upload skipped: image empty")
    if len(image_data) > LARK_MAX_IMAGE_BYTES:
        raise LarkNotificationError("Lark image upload skipped: image too large")
    return image_data


def _upload_lark_image_bytes(
    image_data: bytes,
    *,
    filename: str,
    content_type: str,
    tenant_access_token: str,
    api_base_url: str,
) -> str:
    body, multipart_content_type = _multipart_image_upload_body(
        image_data,
        filename=filename,
        content_type=content_type,
    )
    request = Request(
        f"{api_base_url.rstrip('/')}/open-apis/im/v1/images",
        data=body,
        headers={
            "Authorization": f"Bearer {tenant_access_token}",
            "Content-Type": multipart_content_type,
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=LARK_IMAGE_UPLOAD_TIMEOUT_SECONDS) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, OSError, ValueError, json.JSONDecodeError) as exc:
        raise LarkNotificationError(f"Lark image upload failed: {type(exc).__name__}") from exc

    if response_payload.get("code") != 0:
        raise LarkNotificationError(f"Lark image upload failed: {response_payload.get('msg', 'unknown error')}")
    image_key = str((response_payload.get("data") or {}).get("image_key", "")).strip()
    if not image_key:
        raise LarkNotificationError("Lark image upload failed: image_key missing")
    return image_key


def _multipart_image_upload_body(image_data: bytes, *, filename: str, content_type: str) -> tuple[bytes, str]:
    boundary = f"----amazon-market-spy-{uuid4().hex}"
    safe_filename = filename.replace('"', "")
    parts = [
        f"--{boundary}\r\n".encode("utf-8"),
        b'Content-Disposition: form-data; name="image_type"\r\n\r\n',
        b"message\r\n",
        f"--{boundary}\r\n".encode("utf-8"),
        f'Content-Disposition: form-data; name="image"; filename="{safe_filename}"\r\n'.encode("utf-8"),
        f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"),
        image_data,
        b"\r\n",
        f"--{boundary}--\r\n".encode("utf-8"),
    ]
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def _content_type(filename_or_url: str) -> str:
    content_type, _ = mimetypes.guess_type(filename_or_url)
    return content_type or "image/jpeg"


def _load_lark_image_cache(output_dir: Path) -> dict[str, dict[str, str]]:
    path = output_dir / LARK_IMAGE_CACHE_FILENAME
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    result: dict[str, dict[str, str]] = {}
    for asin, entry in payload.items():
        if isinstance(asin, str) and isinstance(entry, dict):
            image_key = str(entry.get("image_key", "")).strip()
            if image_key:
                result[asin.strip().upper()] = {
                    "image_key": image_key,
                    "image_url": str(entry.get("image_url", "")).strip(),
                    "local_image_path": str(entry.get("local_image_path", "")).strip(),
                }
    return result


def _save_lark_image_cache(output_dir: Path, cache: dict[str, dict[str, str]]) -> None:
    path = output_dir / LARK_IMAGE_CACHE_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, indent=2, sort_keys=True), encoding="utf-8")


def _log_lark_image_upload(asin: str, image_url: str, image_key: str, *, created: bool) -> None:
    print(
        "Lark image upload: "
        f"ASIN={asin or 'n/a'} "
        f"image_url={image_url or 'n/a'} "
        f"image_key={image_key or 'n/a'} "
        f"created={'yes' if created else 'no'}"
    )


def _lark_notification_context(output_dir: Path) -> dict[str, object]:
    lark_rows = read_csv(output_dir / "lark_trend_alerts.csv")
    trend_alert_rows = read_csv(output_dir / "trend_alerts.csv")
    latest_rows = read_csv(output_dir / "latest_products.csv")
    seller_rows = read_csv(output_dir / "seller_intelligence.csv")
    niche_rows = read_csv(output_dir / "niche_intelligence.csv")
    card_candidate_rows = _card_candidate_rows(lark_rows, trend_alert_rows, latest_rows)

    products_tracked = _products_tracked(seller_rows, latest_rows or card_candidate_rows or lark_rows)
    new_wins = sum(1 for row in card_candidate_rows if _alert_label(row) == "New Win")
    rising = sum(1 for row in card_candidate_rows if _alert_label(row) == "Rising")
    high_opportunity_products = sum(1 for row in card_candidate_rows if _to_int(row.get("opportunity_score", "")) >= 60)
    top_opportunities = _top_lark_opportunities(lark_rows, LARK_TOP_OPPORTUNITY_LIMIT)
    top_sellers = sorted(
        seller_rows,
        key=lambda row: _to_int(row.get("pod_momentum_score", "") or row.get("momentum_score", "")),
        reverse=True,
    )[:3] or _top_sellers_from_products(card_candidate_rows)
    top_niches = sorted(
        niche_rows,
        key=lambda row: _to_int(row.get("niche_momentum_score", "")),
        reverse=True,
    )[:LARK_TOP_NICHE_LIMIT] or _top_niches_from_products(card_candidate_rows)
    top_movers = sorted(
        [
            row
            for row in latest_rows
            if _to_int(row.get("display_rank_change", "")) is not None and _to_int(row.get("display_rank_change", "")) > 0
        ],
        key=lambda row: (
            _to_int(row.get("display_rank_change", "")),
            _to_float(row.get("display_rank_velocity", "")),
            _to_int(row.get("opportunity_score", "")),
        ),
        reverse=True,
    )[:3]
    local_report_path = (output_dir / "index.html").as_posix()

    return {
        "lark_rows": lark_rows,
        "trend_alert_rows": trend_alert_rows,
        "latest_rows": latest_rows,
        "card_candidate_rows": card_candidate_rows,
        "seller_rows": seller_rows,
        "niche_rows": niche_rows,
        "report_date": _report_date(card_candidate_rows or latest_rows or lark_rows),
        "products_tracked": products_tracked,
        "new_wins": new_wins,
        "rising": rising,
        "high_opportunity_products": high_opportunity_products,
        "top_opportunities": top_opportunities,
        "top_sellers": top_sellers,
        "top_niches": top_niches,
        "top_movers": top_movers,
        "local_report_path": local_report_path,
    }


def send_lark_message(webhook_url: str, message: str, timeout: int = LARK_TIMEOUT_SECONDS) -> None:
    _send_lark_payload(webhook_url, {"msg_type": "text", "content": {"text": message}}, timeout=timeout)


def send_lark_interactive_cards(
    webhook_url: str,
    payloads: list[dict[str, object]],
    timeout: int = LARK_TIMEOUT_SECONDS,
    delay_seconds: float = LARK_CARD_SEND_DELAY_SECONDS,
) -> None:
    for index, payload in enumerate(payloads):
        if index and delay_seconds > 0:
            sleep(delay_seconds)
        _send_lark_payload(webhook_url, payload, timeout=timeout)


def _send_lark_payload(webhook_url: str, payload: dict[str, object], timeout: int = LARK_TIMEOUT_SECONDS) -> None:
    encoded_payload = json.dumps(payload).encode("utf-8")
    request = Request(
        webhook_url,
        data=encoded_payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            status = getattr(response, "status", None)
            if status is None:
                status = response.getcode()
            response.read()
    except HTTPError as exc:
        raise LarkNotificationError(f"Lark webhook returned HTTP {exc.code}") from exc
    except (URLError, OSError, ValueError) as exc:
        raise LarkNotificationError(f"Lark webhook request failed: {type(exc).__name__}") from exc

    if status < 200 or status >= 300:
        raise LarkNotificationError(f"Lark webhook returned HTTP {status}")


def _top_lark_opportunities(rows: list[dict[str, str]], limit: int) -> list[dict[str, str]]:
    return sorted(
        rows,
        key=lambda row: (_to_int(row.get("opportunity_score", "")), -(_to_int(row.get("today_rank", "")) or 10**9)),
        reverse=True,
    )[:limit]


def _card_candidate_rows(
    lark_rows: list[dict[str, str]],
    trend_alert_rows: list[dict[str, str]],
    latest_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    for rows in (lark_rows, trend_alert_rows, latest_rows):
        if rows:
            return _dedupe_rows(rows)
    return []


def _top_card_products(context: dict[str, object], limit: int) -> list[dict[str, str]]:
    rows = context["card_candidate_rows"]
    return sorted(
        rows,
        key=lambda row: (
            _to_int(row.get("opportunity_score", "")),
            -(_to_int(row.get("display_rank", "") or row.get("today_rank", "") or row.get("rank", "") or row.get("position", "")) or 10**9),
        ),
        reverse=True,
    )[:limit]


def _dedupe_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    result: list[dict[str, str]] = []
    for row in rows:
        key = (row.get("asin", "") or row.get("product_url", "") or row.get("title", "")).strip().upper()
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        result.append(row)
    return result


def _summary_card(context: dict[str, object], report_url: str, include_local_path: bool) -> dict[str, object]:
    top_sellers = context["top_sellers"]
    top_niches = context["top_niches"]
    report_date = str(context["report_date"] or "n/a")
    elements: list[dict[str, object]] = [
        {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": (
                    f"**Report Date:** {report_date}\n"
                    "**Daily market pulse**\n"
                    "Scan the strongest POD signals first, then open the dashboard for full evidence."
                ),
            },
        },
        _metric_row(
            [
                ("Products Tracked", str(context["products_tracked"])),
                ("High Opportunity Products", str(context["high_opportunity_products"])),
            ]
        ),
        _metric_row(
            [
                ("New Wins", str(context["new_wins"])),
                ("Rising Products", str(context["rising"])),
            ]
        ),
        {"tag": "hr"},
        {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**🔥 Top Niches**\n{_top_niches_summary(top_niches)}",
            },
        },
        {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**🏪 Top Sellers**\n{_top_sellers_summary(top_sellers)}",
            },
        },
    ]
    if include_local_path:
        elements.append(
            {
                "tag": "note",
                "elements": [
                    {
                        "tag": "plain_text",
                        "content": f"Local report: {context['local_report_path']}",
                    }
                ],
            }
        )
    elements.append(
        {
            "tag": "action",
            "actions": [
                _button("View Dashboard", report_url, button_type="primary"),
            ],
        }
    )
    return {
        "config": {"wide_screen_mode": True, "enable_forward": True},
        "header": {
            "template": "blue",
            "title": {"tag": "plain_text", "content": "📊 Amazon POD Market Spy Summary"},
            "subtitle": {"tag": "plain_text", "content": "Daily opportunity briefing"},
        },
        "elements": elements,
    }


def _product_card(row: dict[str, str], report_url: str, index: int) -> dict[str, object]:
    title = display_product_title(row.get("title", "")) or row.get("asin", "") or "Untitled"
    seller = _seller_display_name(row)
    score = row.get("opportunity_score", "") or "0"
    previous_display_rank = row.get("previous_display_rank", "")
    display_rank = row.get("display_rank", "") or row.get("today_rank", "") or row.get("rank", "") or row.get("position", "")
    category_rank = _category_rank(row)
    subcategory_rank = _subcategory_rank(row)
    reviews_rating = _reviews_rating(row)
    niche = row.get("niche_primary", "") or "Unknown"
    product_url = row.get("product_url", "")
    image_key = row.get("_lark_image_key", "").strip()
    alert_label = _alert_label(row)

    elements: list[dict[str, object]] = []
    image_element = _image_element(image_key, title)
    if image_element:
        elements.append(image_element)

    elements.append(
        {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": "\n".join(
                    [
                        f"**{_escape_lark_markdown(_shorten(title, 68))}**",
                        f"Seller: {_escape_lark_markdown(_shorten(seller, 44))}",
                    ]
                ),
            },
        }
    )
    elements.append(
        _metric_row(
            [
                ("Opportunity Score", score),
                ("Display Rank", _display_rank_for_source(row)),
                ("Display Rank Movement", _display_rank_movement(previous_display_rank, display_rank)),
            ]
        )
    )
    elements.extend(
        [
            {"tag": "hr"},
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": "\n".join(
                        [
                            "**Market evidence**",
                            f"Amazon BSR: {_escape_lark_markdown(category_rank or 'n/a')}",
                            f"Best Subcategory Rank: {_escape_lark_markdown(subcategory_rank or 'n/a')}",
                            f"Reviews: {_escape_lark_markdown(reviews_rating)}",
                            f"Niche: {_escape_lark_markdown(_shorten(niche, 44))}",
                        ]
                    ),
                },
            },
        ]
    )
    rank_warning = _rank_confidence_warning(row)
    if rank_warning:
        elements.append(
            {
                "tag": "note",
                "elements": [{"tag": "plain_text", "content": rank_warning}],
            }
        )

    actions = []
    if product_url:
        actions.append(_button("Open Amazon", product_url, button_type="primary"))
    actions.append(_button("View Dashboard", report_url))
    elements.append({"tag": "action", "actions": actions})

    return {
        "config": {"wide_screen_mode": True, "enable_forward": True},
        "header": {
            "template": _alert_header_template(alert_label),
            "title": {
                "tag": "plain_text",
                "content": _shorten(f"#{index} · {_alert_icon(alert_label)} {alert_label} · Score {score}", 78),
            },
            "subtitle": {"tag": "plain_text", "content": _shorten(title, 78)},
        },
        "elements": elements,
    }


def _image_element(image_key: str, title: str) -> dict[str, object] | None:
    if not image_key:
        return None
    return {
        "tag": "img",
        "img_key": image_key,
        "mode": "fit_horizontal",
        "alt": {"tag": "plain_text", "content": _shorten(title, 80)},
        "preview": True,
    }


def _alert_label(row: dict[str, str]) -> str:
    alert_type = row.get("alert_type", "").strip().lower()
    classification = row.get("classification", "").strip().lower()
    labels = {label.strip() for label in classification.replace(",", ";").split(";") if label.strip()}
    if alert_type == "new_win" or "new_win" in labels:
        return "New Win"
    if alert_type == "rising" or "rising" in labels:
        return "Rising"
    return "Opportunity"


def _alert_icon(alert_label: str) -> str:
    return {
        "New Win": "🏆",
        "Rising": "🚀",
        "Opportunity": "⭐",
    }.get(alert_label, "⭐")


def _alert_header_template(alert_label: str) -> str:
    return {
        "New Win": "green",
        "Rising": "orange",
        "Opportunity": "blue",
    }.get(alert_label, "blue")


def _metric_row(metrics: list[tuple[str, str]]) -> dict[str, object]:
    return {
        "tag": "column_set",
        "flex_mode": "none",
        "background_style": "default",
        "columns": [
            {
                "tag": "column",
                "width": "weighted",
                "weight": 1,
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": (
                                f"**{_escape_lark_markdown(value or '0')}**\n"
                                f"{_escape_lark_markdown(label)}"
                            ),
                        },
                    }
                ],
            }
            for label, value in metrics
        ],
    }


def _rank_confidence_warning(row: dict[str, str]) -> str:
    confidence = row.get("rank_parse_confidence", "").strip().lower()
    if not confidence or confidence == "high":
        return ""
    return f"⚠️ BSR confidence: {confidence}. Verify rank evidence before acting."


def _top_niches_summary(rows: list[dict[str, str]]) -> str:
    if not rows:
        return "None"
    return "\n".join(
        (
            f"{index}. **{_escape_lark_markdown(_shorten(row.get('niche', '') or row.get('niche_primary', '') or 'Unknown', 32))}**"
            f" · momentum {_format_number(row.get('niche_momentum_score', '') or '0')}"
        )
        for index, row in enumerate(rows[:LARK_TOP_NICHE_LIMIT], start=1)
    )


def _top_sellers_summary(rows: list[dict[str, str]]) -> str:
    if not rows:
        return "None"
    return "\n".join(
        (
            f"{index}. **{_escape_lark_markdown(_shorten(_seller_display_name(row), 32))}**"
            f" · momentum {_format_number(row.get('pod_momentum_score', '') or row.get('momentum_score', '') or '0')}"
        )
        for index, row in enumerate(rows[:3], start=1)
    )


def _button(label: str, url: str, button_type: str = "default") -> dict[str, object]:
    return {
        "tag": "button",
        "text": {"tag": "plain_text", "content": label},
        "url": url,
        "type": button_type,
        "value": {},
    }


def _display_rank_movement(previous_display_rank: str, display_rank: str) -> str:
    previous = _rank_label(previous_display_rank)
    current = _rank_label(display_rank)
    if previous and current:
        return f"{previous} -> {current}"
    return current or previous or "n/a"


def _display_rank_for_source(row: dict[str, str]) -> str:
    display_rank = row.get("display_rank", "") or row.get("today_rank", "") or row.get("rank", "") or row.get("position", "")
    current = _rank_label(display_rank)
    source_name = row.get("source_name", "").strip()
    if current and source_name:
        return f"{current} in {source_name}"
    return current or "n/a"


def _category_rank(row: dict[str, str]) -> str:
    rank = row.get("primary_bsr_rank", "").strip() or row.get("bsr_rank", "").strip()
    category = row.get("primary_bsr_category", "").strip() or row.get("bsr_category", "").strip()
    if rank and category:
        return f"{_rank_label(rank)} in {category}"
    return ""


def _subcategory_rank(row: dict[str, str]) -> str:
    rank = (
        row.get("primary_sub_rank", "").strip()
        or row.get("primary_subcategory_rank", "").strip()
        or row.get("sub_bsr_rank", "").strip()
    )
    category = (
        row.get("primary_sub_category", "").strip()
        or row.get("primary_subcategory_category", "").strip()
        or row.get("sub_bsr_category", "").strip()
    )
    if rank and category:
        return f"{_rank_label(rank)} in {category}"
    return ""


def _reviews_rating(row: dict[str, str]) -> str:
    reviews = row.get("review_count", "").strip()
    rating = (row.get("review_rating", "") or row.get("rating", "")).strip()
    reviews_text = f"{_format_number(reviews)} reviews" if reviews else "n/a reviews"
    rating_text = f"{rating} stars" if rating else "n/a rating"
    return f"{reviews_text} / {rating_text}"


def _report_date(rows: list[dict[str, str]]) -> str:
    dates = sorted({row.get("date", "").strip() for row in rows if row.get("date", "").strip()}, reverse=True)
    return dates[0] if dates else ""


def _top_sellers_from_products(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    scores: dict[str, int] = {}
    for row in rows:
        seller = _seller_display_name(row)
        scores[seller] = scores.get(seller, 0) + _to_int(row.get("opportunity_score", ""))
    return [
        {"seller_name": seller, "momentum_score": str(score)}
        for seller, score in sorted(scores.items(), key=lambda item: item[1], reverse=True)[:3]
        if seller
    ]


def _top_niches_from_products(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    scores: dict[str, int] = {}
    for row in rows:
        niche = row.get("niche_primary", "").strip() or "Unknown"
        scores[niche] = scores.get(niche, 0) + _to_int(row.get("opportunity_score", ""))
    return [
        {"niche": niche, "niche_momentum_score": str(score)}
        for niche, score in sorted(scores.items(), key=lambda item: item[1], reverse=True)[:LARK_TOP_NICHE_LIMIT]
    ]


def _rank_label(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return f"#{_format_number(text)}"


def _format_number(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        return f"{int(float(text.replace(',', ''))):,}"
    except ValueError:
        return text


def _escape_lark_markdown(value: str) -> str:
    return str(value or "").replace("\\", "\\\\").replace("*", "\\*").replace("_", "\\_")


def _products_tracked(seller_rows: list[dict[str, str]], lark_rows: list[dict[str, str]]) -> int:
    tracked = sum(_to_int(row.get("pod_products", "") or row.get("products_tracked", "")) for row in seller_rows)
    if tracked:
        return tracked
    return len({row.get("asin", "").strip().upper() for row in lark_rows if row.get("asin", "").strip()})


def _to_int(value: str) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _to_float(value: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _shorten(value: str, limit: int = 80) -> str:
    text = " ".join((value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _seller_display_name(row: dict[str, str]) -> str:
    return (
        row.get("seller_name", "")
        or row.get("source_name", "")
        or row.get("seller", "")
        or row.get("seller_id", "")
        or "Unknown seller"
    )
