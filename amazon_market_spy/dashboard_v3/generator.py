from __future__ import annotations

from pathlib import Path
from typing import Any

from ..utils import ensure_parent
from .pages import (
    clean_product_workspace_detail_assets,
    render_competitor_page,
    render_data_error_page,
    render_home_page,
    render_market_page,
    render_product_page,
    write_product_workspace_detail_assets,
)
from .routing import V3_PAGE_ROUTES, V3_ROUTE_ALIASES, route_for_filename
from .services import DashboardDataError, DashboardService


def generate_dashboard_v3(output_dir: Path, data: dict[str, Any] | None = None) -> dict[str, object]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if data is None:
        service = DashboardService.for_v3_output(output_dir)
        try:
            presentation_data = service.load()
            data_error = None
        except DashboardDataError as exc:
            presentation_data = None
            data_error = exc
    else:
        service = DashboardService.for_v3_output(output_dir)
        service.validate(data)
        presentation_data = data
        data_error = None

    clean_product_workspace_detail_assets(output_dir)
    assets: list[dict[str, object]] = []
    if data_error is None and presentation_data is not None:
        assets = write_product_workspace_detail_assets(output_dir, presentation_data)

    pages: list[dict[str, str]] = []
    for route in V3_PAGE_ROUTES:
        path = output_dir / route.filename
        ensure_parent(path)
        if data_error is not None:
            html = render_data_error_page(route, str(data_error))
        elif route.key == "morning_brief":
            html = render_home_page(route, presentation_data)
        elif route.key == "product_explorer":
            html = render_product_page(route, presentation_data)
        elif route.key == "competitor":
            html = render_competitor_page(route, presentation_data)
        elif route.key == "market_explorer":
            html = render_market_page(route, presentation_data)
        else:
            html = render_data_error_page(route, f"Unknown dashboard route: {route.key}")
        path.write_text(html, encoding="utf-8")
        pages.append({"label": route.label, "filename": route.filename, "path": str(path)})

    aliases: list[dict[str, str]] = []
    for alias, target in V3_ROUTE_ALIASES.items():
        route = route_for_filename(target)
        path = output_dir / alias
        ensure_parent(path)
        if data_error is not None:
            html = render_data_error_page(route, str(data_error))
        elif route.key == "competitor":
            html = render_competitor_page(route, presentation_data)
        else:
            html = render_data_error_page(route, f"Unsupported compatibility alias target: {target}")
        path.write_text(html, encoding="utf-8")
        aliases.append({"label": route.label, "filename": alias, "target": target, "path": str(path)})

    return {
        "output_dir": str(output_dir),
        "main_page": str(output_dir / "index.html"),
        "pages": pages,
        "aliases": aliases,
        "assets": assets,
    }
