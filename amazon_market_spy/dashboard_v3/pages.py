from __future__ import annotations

from pathlib import Path
from typing import Any

from ..dashboard_v2.pages import (
    clean_product_explorer_detail_assets,
    render_competitor,
    render_data_error_page as render_v2_data_error_page,
    render_market_explorer,
    render_morning_brief,
    render_product_explorer,
    write_product_explorer_detail_assets,
)
from .routing import V3Route


# Dashboard V3 keeps its generator/routing/data-loading entry points, but the
# product experience intentionally renders the last stable V2 UI baseline.


def render_data_error_page(route: V3Route, message: str) -> str:
    return render_v2_data_error_page(route.label, route.key, message)


def render_home_page(route: V3Route, data: dict[str, Any]) -> str:
    return render_morning_brief(data)


def render_product_page(route: V3Route, data: dict[str, Any]) -> str:
    return render_product_explorer(data)


def render_competitor_page(route: V3Route, data: dict[str, Any]) -> str:
    return render_competitor(data)


def render_market_page(route: V3Route, data: dict[str, Any]) -> str:
    return render_market_explorer(data)


def clean_product_workspace_detail_assets(output_dir: Path) -> None:
    clean_product_explorer_detail_assets(output_dir)


def write_product_workspace_detail_assets(output_dir: Path, data: dict[str, object]) -> list[dict[str, object]]:
    return write_product_explorer_detail_assets(output_dir, data)
