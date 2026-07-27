from __future__ import annotations

import datetime as dt
import json
import re
from html import escape

from ..dashboard_v2.components import (
    empty_state,
    loading_skeleton,
    page_header,
    product_image_src,
    render_app_shell as render_v2_app_shell,
    render_navigation,
)
from .routing import V3Route


def render_app_shell(
    *,
    route: V3Route,
    body: str,
    scripts: str = "",
    dataset_info: dict[str, object] | None = None,
) -> str:
    return render_v2_app_shell(
        title=route.title,
        active_key=route.key,
        body=body,
        scripts=scripts,
        dataset_info=dataset_info,
    )


def top_navigation(route: V3Route, *, dataset_info: dict[str, object] | None = None) -> str:
    return render_navigation(route.key, dataset_info)


def side_navigation(active_route: V3Route) -> str:
    return ""


def workspace_layout(*, route: V3Route, content: str, header_action_html: str = "") -> str:
    return f"""    <section class="panel" aria-labelledby="page-title">
{page_header(route.title, route.description, action_html=header_action_html)}
{content}
    </section>"""


def search_bar() -> str:
    return ""


def loading_state(label: str = "Loading state") -> str:
    return loading_skeleton(3)


def placeholder_panel(route: V3Route) -> str:
    return f"""    <section class="panel" aria-label="{escape(route.section)}">
{empty_state(route.title, route.description)}
    </section>"""


def product_state_placeholder() -> str:
    return ""


def data_freshness_label(dataset_info: dict[str, object]) -> str:
    for key in (
        "latest_snapshot_date",
        "snapshot_date",
        "last_crawl_date",
        "last_crawl_timestamp",
        "generated_at",
        "updated_at",
    ):
        value = str(dataset_info.get(key, "") or "").strip()
        if not value:
            continue
        parsed = _parse_date(value)
        if parsed:
            return f"Data: {_format_date(parsed)}"
    return ""


def global_state_script() -> str:
    return ""


def _parse_date(value: str) -> dt.date | None:
    match = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", value)
    if match:
        try:
            return dt.date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _format_date(value: dt.date) -> str:
    months = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
    return f"{months[value.month - 1]} {value.day}, {value.year}"


def _json_script(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":")).replace("</", "<\\/")
